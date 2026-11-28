package org.oguzdows.mobile

import android.content.Context
import org.json.JSONArray

/** Small, private versioned launcher layout. Never overwrites a corrupt record silently. */
class LauncherStore(context: Context) {
    private val prefs = context.getSharedPreferences("launcher-layout-v1", Context.MODE_PRIVATE)
    var writable = true
        private set
    fun pins(): List<String> {
        val raw = prefs.getString("pins", null) ?: return LauncherRules.defaultPins
        return try {
            require(raw.length <= 10000)
            val json = JSONArray(raw)
            require(json.length() <= LauncherRules.MAX_PINS)
            val values = (0 until json.length()).map { json.getString(it) }
            require(values.all(LauncherRules::validPin) && values.distinct().size == values.size)
            values
        } catch (_: Exception) { writable = false; LauncherRules.defaultPins }
    }
    fun savePins(pins: List<String>): Boolean {
        if (!writable) return false
        return prefs.edit().putString("pins", JSONArray(LauncherRules.sanitizePins(pins)).toString()).commit()
    }
    fun widgetIds(): List<Int> = prefs.getString("widgets", "")!!.split(',').mapNotNull(String::toIntOrNull)
        .filter { it > 0 }.distinct().take(2)
    fun saveWidgets(ids: List<Int>) { prefs.edit().putString("widgets", ids.filter { it > 0 }.distinct().take(2).joinToString(",")).apply() }
    fun wallpaper(): Int = prefs.getInt("wallpaper", 0).coerceIn(0, 3)
    fun wallpaper(index: Int) { prefs.edit().putInt("wallpaper", index.coerceIn(0, 3)).apply() }
    fun lightEffects(): Boolean = prefs.getBoolean("light-effects", false)
    fun lightEffects(value: Boolean) { prefs.edit().putBoolean("light-effects", value).apply() }
    fun catSide(): Boolean = prefs.getBoolean("cat-right", true)
    fun catSide(right: Boolean) { prefs.edit().putBoolean("cat-right", right).apply() }
    fun layout(): String = ShellStyles.layout(prefs.getString("layout", "oguzdows") ?: "oguzdows").id
    fun layout(id: String) { prefs.edit().putString("layout", ShellStyles.layout(id).id).apply() }
    fun glass(): Boolean = prefs.getBoolean("glass", true)
    fun glass(enabled: Boolean) { prefs.edit().putBoolean("glass", enabled).apply() }
    fun fullscreen(): Boolean = prefs.getBoolean("fullscreen", true)
    fun fullscreen(enabled: Boolean) { prefs.edit().putBoolean("fullscreen", enabled).apply() }
    fun reset() { prefs.edit().remove("pins").commit(); writable = true }
}
