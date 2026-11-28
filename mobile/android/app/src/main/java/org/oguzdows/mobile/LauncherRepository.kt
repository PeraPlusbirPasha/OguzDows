package org.oguzdows.mobile

import android.content.ComponentName
import android.content.Context
import android.content.pm.LauncherActivityInfo
import android.content.pm.LauncherApps
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Handler
import android.os.Looper
import android.os.UserHandle
import android.os.UserManager
import android.util.LruCache
import java.util.concurrent.Executors

/** Real, profile-qualified launchable activities; no QUERY_ALL_PACKAGES or guessed intents. */
data class LauncherEntry(
    val key: String, val label: String, val packageName: String,
    val component: ComponentName, val user: UserHandle, val info: LauncherActivityInfo,
)

class LauncherRepository(private val context: Context) {
    private val launcher = context.getSystemService(LauncherApps::class.java)
    private val users = context.getSystemService(UserManager::class.java)
    private val worker = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var active = false
    @Volatile private var generation = 0
    private var listener: ((List<LauncherEntry>, String?) -> Unit)? = null
    private val icons = object : LruCache<String, Bitmap>(3 * 1024 * 1024) {
        override fun sizeOf(key: String, value: Bitmap) = value.allocationByteCount
    }
    private val callback = object : LauncherApps.Callback() {
        override fun onPackageAdded(packageName: String, user: UserHandle) = refresh()
        override fun onPackageRemoved(packageName: String, user: UserHandle) = refresh()
        override fun onPackageChanged(packageName: String, user: UserHandle) = refresh()
        override fun onPackagesAvailable(packageNames: Array<out String>, user: UserHandle, replacing: Boolean) = refresh()
        override fun onPackagesUnavailable(packageNames: Array<out String>, user: UserHandle, replacing: Boolean) = refresh()
    }
    fun start(onChange: (List<LauncherEntry>, String?) -> Unit) {
        listener = onChange
        if (!active) { active = true; launcher.registerCallback(callback, main) }
        refresh()
    }
    fun stop() { if (active) launcher.unregisterCallback(callback); active = false; generation++; listener = null }
    fun refresh() {
        if (!active) return
        val ticket = ++generation
        worker.execute {
            val entries = mutableListOf<LauncherEntry>()
            var warning: String? = null
            try {
                for (profile in users.userProfiles) {
                    try {
                        val serial = users.getSerialNumberForUser(profile)
                        if (serial < 0) continue
                        for (info in launcher.getActivityList(null, profile)) {
                            if (info.applicationInfo.packageName == context.packageName) continue
                            val key = "app:$serial:${info.componentName.flattenToShortString()}"
                            if (LauncherRules.validPin(key)) entries.add(LauncherEntry(key,
                                info.label.toString().take(120), info.applicationInfo.packageName, info.componentName, profile, info))
                        }
                    } catch (_: SecurityException) { warning = "Bazı kullanıcı profilleri sistem tarafından kapalı." }
                }
            } catch (_: Exception) { warning = "Uygulama listesi okunamadı. Sistem profilini kontrol et." }
            val result = entries.distinctBy { it.key }.sortedWith(compareBy({ LauncherRules.normalize(it.label) }, { it.key })).take(1000)
            main.post { if (active && generation == ticket) { icons.evictAll(); listener?.invoke(result, warning) } }
        }
    }
    fun launch(entry: LauncherEntry): Boolean = try {
        if (!launcher.isActivityEnabled(entry.component, entry.user)) false
        else { launcher.startMainActivity(entry.component, entry.user, null, null); true }
    } catch (_: Exception) { false }
    fun details(entry: LauncherEntry): Boolean = try {
        launcher.startAppDetailsActivity(entry.component, entry.user, null, null); true
    } catch (_: Exception) { false }
    fun icon(entry: LauncherEntry): Bitmap? {
        icons.get(entry.key)?.let { return it }
        return try {
            val drawable = entry.info.getBadgedIcon(context.resources.displayMetrics.densityDpi)
            val size = (48 * context.resources.displayMetrics.density).toInt().coerceIn(48, 144)
            val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
            drawable.setBounds(0, 0, size, size); drawable.draw(Canvas(bitmap))
            icons.put(entry.key, bitmap); bitmap
        } catch (_: Exception) { null }
    }
    fun close() { stop(); worker.shutdownNow(); icons.evictAll() }
}
