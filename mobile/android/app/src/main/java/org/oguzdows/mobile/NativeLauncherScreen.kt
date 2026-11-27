package org.oguzdows.mobile

import android.app.role.RoleManager
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import kotlinx.coroutines.launch
import java.time.format.DateTimeFormatter
import java.util.Locale

val ShellWallpapers = listOf(R.drawable.shell_bosphorus, R.drawable.shell_cappadocia, R.drawable.shell_mountains, R.drawable.shell_salt_lake)
val ShellWallpaperNames = listOf("Boğaz sabahı", "Kapadokya ışığı", "Kaçkar sisi", "Tuz Gölü akşamı")

@OptIn(ExperimentalMaterial3Api::class, androidx.compose.ui.ExperimentalComposeUiApi::class)
@Composable
fun NativeLauncherScreen(
    state: LauncherUiState, model: LauncherViewModel, widgets: LauncherWidgets, homeSignal: Int,
    route: (String) -> Unit, launch: (String) -> Unit, role: (String) -> Unit, system: (String) -> Unit,
    report: (String) -> Unit, brightness: (Float) -> Unit,
) {
    val colors = if (state.dark) darkColorScheme(primary=Color(0xFFA0D9C1), background=Color(0xFF17262B), surface=Color(0xFF17262B), onSurface=Color(0xFFE2EEEB))
                 else lightColorScheme(primary=Color(0xFF246254), background=Color(0xFFF3F6F1), surface=Color(0xFFF3F6F1), onSurface=Color(0xFF263C38))
    MaterialTheme(colorScheme = colors) {
        var panel by rememberSaveable { mutableStateOf<String?>(null) }
        val pager = rememberPagerState(pageCount = { 3 })
        val scope = rememberCoroutineScope()
        val view = LocalView.current
        val context = LocalContext.current
        SideEffect {
            (context as? android.app.Activity)?.let {
                WindowCompat.getInsetsController(it.window, view).apply {
                    isAppearanceLightStatusBars = false; isAppearanceLightNavigationBars = false
                }
            }
        }
        fun open(key: String) {
            when (LauncherRules.internalRoute(key)) {
                "rifki" -> panel = "rifki"
                "settings", "monitor", "culture" -> panel = "controls"
                null -> { panel = null; launch(key) }
                else -> { panel = null; route(LauncherRules.internalRoute(key)!!) }
            }
        }
        LaunchedEffect(homeSignal) { if (homeSignal > 0) { panel = null; pager.scrollToPage(0) } }
        BackHandler { if (panel != null) panel = null else scope.launch { pager.animateScrollToPage(0) } }
        BoxWithConstraints(Modifier.fillMaxSize().testTag("launcher-root").semantics { testTagsAsResourceId = true }) {
            val compact = maxHeight < 730.dp
            Image(painterResource(ShellWallpapers[state.wallpaper]), null, Modifier.fillMaxSize(), contentScale=ContentScale.Crop)
            Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0x8033443F), Color(0x20503C35), Color(0xD011282A)))))
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal=20.dp)) {
                var downward by remember { mutableFloatStateOf(0f) }
                val threshold = with(LocalDensity.current) { 40.dp.toPx() }
                Row(Modifier.fillMaxWidth().height(54.dp).pointerInput(Unit) {
                    detectVerticalDragGestures(onDragStart={downward=0f}, onDragEnd={if(downward>threshold) panel="controls"}) { _, delta -> downward += delta }
                }, verticalAlignment=Alignment.CenterVertically) {
                    Image(painterResource(R.drawable.nazar), "OğuzDows nazar güç simgesi", Modifier.size(30.dp))
                    Spacer(Modifier.width(9.dp))
                    Column(Modifier.weight(1f)) {
                        Text("oğuzdows", fontSize=20.sp, letterSpacing=(-.6).sp, fontWeight=FontWeight.Bold, color=Color.White)
                        Text("C E B İ N D E K İ  M A S A Ü S T Ü", fontSize=7.sp, letterSpacing=.8.sp, color=Color.White.copy(.8f))
                    }
                    TextButton(onClick={panel="controls"}, modifier=Modifier.testTag("launcher-controls")) {
                        Text(state.battery?.let { "%$it${if(state.charging) " +" else ""}" } ?: "Pil —", color=Color.White, fontSize=12.sp)
                        Spacer(Modifier.width(8.dp)); ShellGlyph("controls", Modifier.size(22.dp), Color.White)
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top=if(compact) 0.dp else 10.dp, bottom=10.dp), verticalAlignment=Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(state.clock.format(DateTimeFormatter.ofPattern("HH:mm")), fontSize=if(compact) 48.sp else 64.sp,
                            lineHeight=if(compact) 52.sp else 70.sp, fontWeight=FontWeight.Light, letterSpacing=(-3).sp, color=Color.White)
                        Text(state.clock.format(DateTimeFormatter.ofPattern("d MMMM EEEE", Locale.forLanguageTag("tr-TR"))),
                            color=Color.White.copy(.92f), fontSize=12.sp)
                    }
                    if (!state.homeHeld) TextButton(onClick={role(RoleManager.ROLE_HOME)}, modifier=Modifier.testTag("launcher-set-home")) {
                        Text("Ana ekran yap", color=Color.White, fontSize=12.sp)
                    } else Text("SENİN\nALANIN.", color=Color.White.copy(.75f), fontSize=10.sp, lineHeight=15.sp, letterSpacing=2.sp)
                }
                GlassSurface(Modifier.fillMaxWidth().height(49.dp).clickable { panel="apps" }.testTag("launcher-search-open"), light=state.lightEffects) {
                    Row(Modifier.fillMaxSize().padding(horizontal=16.dp), verticalAlignment=Alignment.CenterVertically) {
                        ShellGlyph("search", Modifier.size(21.dp)); Spacer(Modifier.width(10.dp))
                        Text("Bir uygulama, bir fikir…", color=Color(0xFF405C55), fontSize=13.sp, modifier=Modifier.weight(1f))
                        Text("ARA", color=Color(0xFF496C60), fontSize=9.sp, letterSpacing=1.4.sp)
                    }
                }
                if (state.warning != null) Text(state.warning, color=Color.White, fontSize=11.sp, maxLines=2, modifier=Modifier.padding(top=6.dp))
                HorizontalPager(pager, Modifier.fillMaxWidth().weight(1f).testTag("launcher-pages"), verticalAlignment=Alignment.Top) { page ->
                    if (page < 2) Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(top=12.dp)) {
                        val pagePins = state.pins.drop(page * 8).take(8)
                        for (row in 0..1) Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(5.dp)) {
                            for (column in 0..3) {
                                val key = pagePins.getOrNull(row * 4 + column)
                                if (key == null) Box(Modifier.weight(1f).height(94.dp).clip(RoundedCornerShape(14.dp))
                                    .clickable { panel="apps" }.semantics { contentDescription="Kısayol ekle" }, contentAlignment=Alignment.Center) {
                                    ShellGlyph("plus", tint=Color.White.copy(.45f))
                                } else HomeShortcut(key, state, model.repository, ::open, { panel="edit:$it" }, Modifier.weight(1f))
                            }
                        }
                        if (page == 1) Text("Uygulamalarda + ile sabitle · kısayola basılı tutarak düzenle", color=Color.White.copy(.8f),
                            fontSize=10.sp, lineHeight=15.sp, modifier=Modifier.padding(horizontal=6.dp, vertical=10.dp))
                    } else WidgetWorkspace(state, widgets, {panel="widgets"})
                }
                Row(Modifier.fillMaxWidth().height(34.dp), horizontalArrangement=Arrangement.Center, verticalAlignment=Alignment.CenterVertically) {
                    for (i in 0..2) Box(Modifier.width(48.dp).fillMaxHeight().clickable { scope.launch { pager.animateScrollToPage(i) } }
                        .semantics { contentDescription=if(i==2) "Widget alanı" else "Masaüstü ${i+1}" }, contentAlignment=Alignment.Center) {
                        Box(Modifier.width(if(pager.currentPage==i) 22.dp else 6.dp).height(5.dp)
                            .background(Color.White.copy(if(pager.currentPage==i) 1f else .4f), CircleShape))
                    }
                }
                val reaction = RifkiBehavior.reaction(RifkiContext(state.clock.hour, state.battery, state.charging, state.inCall))
                GlassSurface(Modifier.fillMaxWidth().clickable { panel="rifki" }.testTag("launcher-rifki").height(if(compact) 76.dp else 90.dp), state.dark, state.lightEffects) {
                    Row(Modifier.fillMaxSize().padding(horizontal=10.dp), verticalAlignment=Alignment.CenterVertically,
                        horizontalArrangement=if(state.catRight) Arrangement.Start else Arrangement.End) {
                        @Composable fun cat() {
                            var travel by remember { mutableFloatStateOf(0f) }
                            Image(painterResource(R.drawable.rifki), "Rıfkı, dokun konuş; sürükle yerini değiştir", Modifier.size(if(compact) 59.dp else 72.dp)
                                .pointerInput(Unit) { detectHorizontalDragGestures(onDragStart={travel=0f}, onDragEnd={ if(kotlin.math.abs(travel)>30) model.catSide(travel>0) }) { change, dx -> change.consume(); travel+=dx } })
                        }
                        if (!state.catRight) cat()
                        Column(Modifier.weight(1f).padding(horizontal=8.dp)) {
                            Text("RIFKI  /  ${reaction.mood.uppercase(Locale.forLanguageTag("tr"))}", color=MaterialTheme.colorScheme.primary,
                                fontSize=9.sp, letterSpacing=1.1.sp, fontWeight=FontWeight.Bold)
                            Spacer(Modifier.height(4.dp))
                            Text(reaction.line, fontSize=12.sp, lineHeight=16.sp, maxLines=2, overflow=TextOverflow.Ellipsis,
                                color=MaterialTheme.colorScheme.onSurface)
                        }
                        if (state.catRight) cat()
                    }
                }
                Spacer(Modifier.height(10.dp))
                GlassSurface(Modifier.fillMaxWidth().height(64.dp), dark=true, light=state.lightEffects) {
                    Row(Modifier.fillMaxSize().padding(horizontal=4.dp), verticalAlignment=Alignment.CenterVertically) {
                        val dock = listOf("phone" to "Telefon", "messages" to "Mesajlar", "apps" to "Uygulamalar", "store" to "Mağaza", "settings" to "Ayarlar")
                        dock.forEach { (id, label) ->
                            Column(Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(14.dp)).clickable {
                                if(id=="apps") panel="apps" else open("internal:$id")
                            }.semantics { contentDescription=if(id=="apps") "Uygulama çekmecesi" else "Dock: $label" },
                                horizontalAlignment=Alignment.CenterHorizontally, verticalArrangement=Arrangement.Center) {
                                ShellGlyph(when(id){"settings"->"controls";"messages"->"message";else->id}, Modifier.size(24.dp), Color(0xFFE5F0E9))
                                Spacer(Modifier.height(4.dp)); Text(label, fontSize=8.sp, color=Color(0xFFD4E7DD))
                            }
                        }
                    }
                }
                Spacer(Modifier.height(7.dp))
            }
        }
        if (panel != null) ModalBottomSheet(onDismissRequest={panel=null}, containerColor=MaterialTheme.colorScheme.surface,
            modifier=Modifier.imePadding(), dragHandle={BottomSheetDefaults.DragHandle()}) {
            when {
                panel=="apps" -> LauncherDrawer(state, model, ::open, {panel="edit:$it"}, report)
                panel=="controls" -> LauncherControls(state, model, role, system, brightness, {panel=null;route("settings")}, report)
                panel=="rifki" -> RifkiPanel(state) { suggestion ->
                    when(suggestion) {
                        ShellSuggestion.DARK -> model.dark(true)
                        ShellSuggestion.LIGHT -> model.dark(false)
                        ShellSuggestion.CONTROLS -> panel="controls"
                        ShellSuggestion.APPS -> panel="apps"
                        ShellSuggestion.PHONE -> open("internal:phone")
                        ShellSuggestion.MESSAGES -> open("internal:messages")
                        ShellSuggestion.STORE -> open("internal:store")
                        ShellSuggestion.TOOLS -> open("internal:workbench")
                    }
                }
                panel=="widgets" -> WidgetPicker(widgets) { provider -> panel=null; widgets.add(provider) }
                panel!!.startsWith("edit:") -> ShortcutEditor(panel!!.removePrefix("edit:"), state, model, {panel=null}, report)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
