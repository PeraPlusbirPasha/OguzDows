package org.oguzdows.mobile

import android.app.Activity
import android.appwidget.AppWidgetHost
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProviderInfo
import android.content.Context
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/** Real AppWidgetHost; bind/configure require the platform path, only after a user selection. */
class LauncherWidgets(
    private val activity: ComponentActivity,
    private val ids: () -> List<Int>,
    private val changed: (List<Int>) -> Unit,
    private val report: (String) -> Unit,
) {
    val host = AppWidgetHost(activity, 17031)
    val manager: AppWidgetManager = AppWidgetManager.getInstance(activity)
    private val prefs = activity.getSharedPreferences("launcher-widget-host", Context.MODE_PRIVATE)
    private var pending: Int
        get() = prefs.getInt("pending", -1)
        set(value) { prefs.edit().putInt("pending", value).apply() }
    private val configure = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) finish() else cancel()
    }
    private val bind = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) configureOrFinish() else cancel()
    }
    fun providers(): List<AppWidgetProviderInfo> = try {
        manager.installedProviders.sortedBy { LauncherRules.normalize(it.loadLabel(activity.packageManager)) }.take(200)
    } catch (_: Exception) { emptyList() }
    fun add(provider: AppWidgetProviderInfo) {
        if (ids().size >= 2) { report("Bu alanda en çok iki widget var. Önce birini kaldır."); return }
        if (pending > 0) cancel()
        val id = host.allocateAppWidgetId(); pending = id
        try {
            if (manager.bindAppWidgetIdIfAllowed(id, provider.provider)) configureOrFinish()
            else bind.launch(Intent(AppWidgetManager.ACTION_APPWIDGET_BIND)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_PROVIDER, provider.provider))
        } catch (_: Exception) { cancel(); report("Widget için sistem bağlama ekranı açılamadı.") }
    }
    private fun configureOrFinish() {
        val id = pending
        val info = if (id > 0) manager.getAppWidgetInfo(id) else null
        if (info == null) { cancel(); report("Widget bağlanmadı; alana eklenmedi."); return }
        if (info.configure == null) finish()
        else try {
            configure.launch(Intent(AppWidgetManager.ACTION_APPWIDGET_CONFIGURE)
                .setComponent(info.configure).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id))
        } catch (_: Exception) { cancel(); report("Widget yapılandırması açılamadı; eklenmedi.") }
    }
    private fun finish() {
        val id = pending
        if (id <= 0 || manager.getAppWidgetInfo(id) == null || ids().size >= 2) { cancel(); return }
        changed((ids() + id).distinct()); pending = -1
    }
    private fun cancel() { val id = pending; if (id > 0) host.deleteAppWidgetId(id); pending = -1 }
    fun remove(id: Int) { if (id !in ids()) return; host.deleteAppWidgetId(id); changed(ids().filterNot { it == id }) }
    fun start() { try { host.startListening() } catch (_: Exception) { report("Widget güncellemeleri şu anda kullanılamıyor.") } }
    fun stop() { host.stopListening() }
}
