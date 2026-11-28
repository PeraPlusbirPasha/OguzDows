package org.oguzdows.mobile

import android.app.Activity
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

data class AeroSettings(val dark: Boolean = false, val glass: Boolean = true, val light: Boolean = false)
val LocalAero = staticCompositionLocalOf { AeroSettings() }

@Composable
fun ConnectedTheme(dark: Boolean, wallpaper: Int, glass: Boolean = true, light: Boolean = false, content: @Composable () -> Unit) {
    val primary = Color(ShellStyles.accent(wallpaper, dark))
    val colors = if (dark) darkColorScheme(primary = primary, surface = Color(0xFF17262B), background = Color(0xFF17262B), onSurface = Color(0xFFE2EEEB))
        else lightColorScheme(primary = primary, surface = Color(0xFFF3F6F1), background = Color(0xFFF3F6F1), onSurface = Color(0xFF263C38))
    CompositionLocalProvider(LocalAero provides AeroSettings(dark, glass, light)) { MaterialTheme(colorScheme = colors, content = content) }
}

fun Activity.shellFullscreen(enabled: Boolean) {
    WindowCompat.setDecorFitsSystemWindows(window, false)
    WindowCompat.getInsetsController(window, window.decorView).apply {
        systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        if (enabled) hide(WindowInsetsCompat.Type.systemBars()) else show(WindowInsetsCompat.Type.systemBars())
    }
}

/** Only our own window; never blocks SystemUI's secure edges, keyguard, or other apps. */
@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
@Composable
fun FullAeroPanel(state: LauncherUiState, close: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        val view = LocalView.current
        LaunchedEffect(view, state.fullscreen) {
            val window = (view.parent as? DialogWindowProvider)?.window
            if (window != null) WindowCompat.getInsetsController(window, view).apply {
                systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                if (state.fullscreen) hide(WindowInsetsCompat.Type.systemBars()) else show(WindowInsetsCompat.Type.systemBars())
            }
        }
        Box(Modifier.fillMaxSize().semantics{testTagsAsResourceId=true}) {
            Image(painterResource(ShellWallpapers[state.wallpaper]), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            Box(Modifier.fillMaxSize().background(if (state.dark) Color(0xDD10262F) else Color(0xDFF1F6F2)))
            Column(Modifier.fillMaxSize().systemBarsPadding().imePadding()) {
                var travel by remember {mutableFloatStateOf(0f)}
                Row(Modifier.fillMaxWidth().height(56.dp).pointerInput(Unit){detectVerticalDragGestures(onDragStart={travel=0f},onDragEnd={if(kotlin.math.abs(travel)>50)close()}){change,dy->change.consume();travel+=dy}}.padding(horizontal = 18.dp), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = close) { Text("Kapat") }
                }
                content()
            }
        }
    }
}
