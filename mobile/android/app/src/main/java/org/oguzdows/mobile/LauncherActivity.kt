package org.oguzdows.mobile

import android.app.role.RoleManager
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/** Actual HOME/LAUNCHER entry point. The home surface is native Compose, not a website. */
class LauncherActivity : ComponentActivity() {
    val model: LauncherViewModel by viewModels()
    lateinit var widgets: LauncherWidgets
        private set
    private var homeSignal by mutableIntStateOf(0)
    private val roleResult = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { model.refreshSystem() }
    override fun onCreate(savedInstanceState: Bundle?) {
        NativeUi.theme(this); super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        widgets = LauncherWidgets(this, { model.ui.value.widgetIds }, model::widgets, ::report)
        setContent {
            val state by model.ui.collectAsStateWithLifecycle()
            NativeLauncherScreen(state, model, widgets, homeSignal, ::openRoute, ::openEntry, ::requestRole, ::systemPanel, ::report,
                brightness = { value -> window.attributes = window.attributes.apply { screenBrightness = value.coerceIn(.08f, 1f) } })
        }
    }
    override fun onStart() { super.onStart(); model.start(); widgets.start() }
    override fun onResume() { super.onResume(); model.refreshSystem(); shellFullscreen(model.ui.value.fullscreen) }
    override fun onWindowFocusChanged(hasFocus: Boolean) { super.onWindowFocusChanged(hasFocus); if(hasFocus) shellFullscreen(model.ui.value.fullscreen) }
    override fun onStop() { widgets.stop(); model.stop(); super.onStop() }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); homeSignal++ }
    private fun report(message: String) { Toast.makeText(this, message, Toast.LENGTH_LONG).show() }
    private fun openEntry(key: String) {
        val entry = model.ui.value.entries.find { it.key == key }
        if (entry == null || !model.repository.launch(entry)) report("Uygulama açılamadı. Kaldırılmış veya profil kapalı olabilir.")
    }
    private fun openRoute(route: String) {
        if (LauncherRules.destinations.none { it.id == route }) return
        try {
            when (route) {
                "contacts" -> startActivity(Intent(this, ContactsActivity::class.java))
                "files" -> startActivity(Intent(this, BridgeActivity::class.java))
                "store" -> startActivity(Intent(this, SourceStoreActivity::class.java))
                else -> startActivity(Intent(this, HomeActivity::class.java).putExtra("screen", route)
                    .putExtra("fromLauncher", true).putExtra("launcherTheme", if (model.ui.value.dark) "dark" else "light"))
            }
        } catch (_: Exception) { report("Bu ekran şu anda açılamadı.") }
    }
    private fun requestRole(role: String) {
        if (role !in listOf(RoleManager.ROLE_HOME, RoleManager.ROLE_ASSISTANT)) return
        val manager = getSystemService(RoleManager::class.java)
        if (!manager.isRoleAvailable(role)) { report("Bu sistemde bu rol seçilemiyor."); return }
        if (manager.isRoleHeld(role)) { report("OğuzDows zaten seçili."); return }
        roleResult.launch(manager.createRequestRoleIntent(role))
    }
    private fun systemPanel(panel: String) {
        val action = when (panel) {
            "wifi" -> Settings.Panel.ACTION_WIFI
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "dnd" -> Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS
            "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
            "all" -> Settings.ACTION_SETTINGS
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "security" -> Settings.ACTION_SECURITY_SETTINGS
            "notifications" -> Settings.ACTION_APP_NOTIFICATION_SETTINGS
            "defaults" -> Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS
            "lock" -> { startActivity(Intent(this, LockActivity::class.java)); return }
            "bridge" -> { startActivity(Intent(this, BridgeActivity::class.java)); return }
            "contacts" -> { startActivity(Intent(this, ContactsActivity::class.java)); return }
            else -> return
        }
        try { startActivity(Intent(action).apply { if(panel=="notifications") putExtra(Settings.EXTRA_APP_PACKAGE, packageName) }) } catch (_: Exception) { report("Bu sistem paneli bulunamadı.") }
    }
}
