package org.oguzdows.mobile

/** Product layout families, not emulated foreign operating systems. Pure/bounded rules. */
data class ShellLayout(val id: String, val label: String, val columns: Int, val tiles: Boolean = false, val rail: Boolean = false)
object ShellStyles {
    // Stable IDs are the desktop profiles.PROFILES IDs; geometry is adapted to touch.
    val layouts = listOf(
        ShellLayout("oguzdows", "OğuzDows", 4),
        ShellLayout("kde", "Plasma", 3, tiles = true),
        ShellLayout("gnome", "GNOME / Ubuntu", 3, rail = true),
        ShellLayout("xfce", "Klasik Xfce", 5),
        ShellLayout("windows11", "Windows 11", 4),
        ShellLayout("mac", "macOS iskelesi", 4),
    )
    fun layout(id: String) = layouts.firstOrNull { it.id == id } ?: layouts.first()
    @JvmStatic fun accent(wallpaper: Int, dark: Boolean): Int = (if (dark)
        longArrayOf(0xFFA0D9D6, 0xFFF1C89E, 0xFFBCD7B5, 0xFFDEC1E6)
        else longArrayOf(0xFF205F65, 0xFF7C4A2C, 0xFF395F3A, 0xFF704873))[wallpaper.coerceIn(0, 3)].toInt()
    @JvmStatic fun webAccent(wallpaper: Int) = when (wallpaper.coerceIn(0, 3)) { 1 -> "copper"; 3 -> "plum"; else -> "sea" }
}
