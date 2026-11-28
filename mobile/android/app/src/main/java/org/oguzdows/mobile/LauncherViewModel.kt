package org.oguzdows.mobile

import android.app.Application
import android.app.role.RoleManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.time.LocalDateTime

/** UI observes actual system snapshots. No polling while the launcher is stopped. */
data class LauncherUiState(
    val entries: List<LauncherEntry> = emptyList(), val pins: List<String> = LauncherRules.defaultPins,
    val layout: String = "oguzdows", val glass: Boolean = true, val fullscreen: Boolean = true,
    val dark: Boolean = false, val wallpaper: Int = 0, val lightEffects: Boolean = false,
    val clock: LocalDateTime = LocalDateTime.now(), val battery: Int? = null,
    val charging: Boolean = false, val inCall: Boolean = false, val mediaVolume: Float = 0f,
    val homeHeld: Boolean = false, val warning: String? = null, val catRight: Boolean = true,
    val widgetIds: List<Int> = emptyList(), val loading: Boolean = true,
)
class LauncherViewModel(application: Application) : AndroidViewModel(application) {
    private val context = application
    val store = LauncherStore(application)
    val repository = LauncherRepository(application)
    private val state = MutableStateFlow(LauncherUiState(pins = store.pins(), dark = NativeUi.dark(context),
        layout = store.layout(), glass = store.glass(), fullscreen = store.fullscreen(), wallpaper = store.wallpaper(), lightEffects = store.lightEffects(), catRight = store.catSide(), widgetIds = store.widgetIds()))
    val ui = state.asStateFlow()
    private var active = false
    private val writes = Mutex()
    private val handler = Handler(Looper.getMainLooper())
    private val tick = object : Runnable { override fun run() { refreshSystem(); if (active) handler.postDelayed(this, 60000) } }
    private val receiver = object : BroadcastReceiver() { override fun onReceive(c: Context, i: Intent) { refreshSystem() } }
    fun start() {
        if (active) return
        active = true
        repository.start { entries, warning ->
            state.value = state.value.copy(entries = entries, loading = false,
                warning = warning ?: if (!store.writable) "Kayıtlı düzen okunamadı; üzerine yazılmadı. Ayarlar’dan açıkça sıfırlayabilirsin." else null)
        }
        val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED).apply {
            addAction(Intent.ACTION_TIME_CHANGED); addAction(Intent.ACTION_TIMEZONE_CHANGED); addAction(PlatformState.CHANGED)
        }
        ContextCompat.registerReceiver(context, receiver, filter, ContextCompat.RECEIVER_NOT_EXPORTED)
        tick.run()
    }
    fun stop() {
        if (!active) return
        active = false; handler.removeCallbacks(tick); context.unregisterReceiver(receiver); repository.stop()
    }
    fun refreshSystem() {
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val audio = context.getSystemService(AudioManager::class.java)
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        state.value = state.value.copy(clock = LocalDateTime.now(), battery = if (level >= 0 && scale > 0) level * 100 / scale else null,
            charging = (battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0,
            inCall = CallController.snapshot() != null, dark = NativeUi.dark(context),
            mediaVolume = if (max > 0) audio.getStreamVolume(AudioManager.STREAM_MUSIC).toFloat() / max else 0f,
            homeHeld = PlatformState.role(context, RoleManager.ROLE_HOME))
    }
    private fun persistPins(next: List<String>) {
        if (!store.writable) return
        state.value = state.value.copy(pins = next)
        // Acquire in main-dispatch order, then write off-main; rapid pin/move operations
        // cannot race IO dispatcher scheduling and put an older layout back on disk.
        viewModelScope.launch {
            writes.withLock {
                if (!withContext(Dispatchers.IO) { store.savePins(next) })
                    state.value = state.value.copy(warning = "Düzen kalıcı kaydedilemedi; bu oturumda açık.")
            }
        }
    }
    fun pin(key: String): Boolean {
        if (!store.writable || !LauncherRules.validPin(key)) return false
        val next = LauncherRules.pin(state.value.pins, key)
        if (key !in next) return false
        persistPins(next); return true
    }
    fun unpin(key: String) = persistPins(state.value.pins.filterNot { it == key })
    fun move(key: String, delta: Int) = persistPins(LauncherRules.move(state.value.pins, key, delta))
    fun resetPins() { viewModelScope.launch { writes.withLock { withContext(Dispatchers.IO) { store.reset() }; state.value = state.value.copy(pins = LauncherRules.defaultPins, warning = null) } } }
    fun dark(value: Boolean) {
        context.getSharedPreferences("native-ui", Context.MODE_PRIVATE).edit().putBoolean("dark", value).apply()
        state.value = state.value.copy(dark = value); PlatformState.changed(context)
    }
    fun wallpaper(index: Int) { store.wallpaper(index); state.value = state.value.copy(wallpaper = store.wallpaper()); PlatformState.changed(context) }
    fun layout(id: String) { store.layout(id); state.value = state.value.copy(layout = store.layout()) }
    fun glass(value: Boolean) { store.glass(value); state.value = state.value.copy(glass = value) }
    fun fullscreen(value: Boolean) { store.fullscreen(value); state.value = state.value.copy(fullscreen = value) }
    fun lightEffects(value: Boolean) { store.lightEffects(value); state.value = state.value.copy(lightEffects = value) }
    fun catSide(right: Boolean) { store.catSide(right); state.value = state.value.copy(catRight = right) }
    fun volume(value: Float) {
        val audio = context.getSystemService(AudioManager::class.java)
        val max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, kotlin.math.round(value.coerceIn(0f, 1f) * max).toInt(), 0)
        refreshSystem()
    }
    fun widgets(ids: List<Int>) { store.saveWidgets(ids); state.value = state.value.copy(widgetIds = store.widgetIds()) }
    override fun onCleared() { stop(); repository.close(); super.onCleared() }
}
