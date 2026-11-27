package org.oguzdows.mobile

import android.app.Activity
import android.app.role.RoleManager
import android.appwidget.AppWidgetProviderInfo
import android.graphics.Color as AndroidColor
import android.widget.TextView
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun LauncherDrawer(state: LauncherUiState, model: LauncherViewModel, onOpen: (String)->Unit,
                   edit: (String)->Unit, report:(String)->Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableIntStateOf(0) }
    val q = LauncherRules.normalize(query).trim()
    val builtins = LauncherRules.destinations.filter { q.isEmpty() || LauncherRules.normalize(it.label+" "+it.keywords).contains(q) }
    val installed = state.entries.filter { q.isEmpty() || LauncherRules.normalize(it.label+" "+it.packageName).contains(q) }
    Column(Modifier.fillMaxWidth().fillMaxHeight(.88f).padding(horizontal=20.dp).testTag("launcher-drawer")) {
        Text("Her şey, elinin altında.", style=MaterialTheme.typography.headlineSmall, fontWeight=FontWeight.SemiBold)
        Text("${state.entries.size} kurulu giriş · 20 OğuzDows modülü", fontSize=12.sp,
            color=MaterialTheme.colorScheme.onSurfaceVariant, modifier=Modifier.padding(top=4.dp, bottom=14.dp))
        OutlinedTextField(query, {query=it.take(120)}, singleLine=true,
            placeholder={Text("Uygulama ara")}, leadingIcon={ShellGlyph("search", tint=MaterialTheme.colorScheme.primary)},
            modifier=Modifier.fillMaxWidth().testTag("launcher-search"), shape=RoundedCornerShape(16.dp))
        Row(Modifier.fillMaxWidth().padding(vertical=6.dp), horizontalArrangement=Arrangement.spacedBy(6.dp)) {
            listOf("Tümü", "OğuzDows", "Kurulu").forEachIndexed { i, label ->
                FilterChip(selected=filter==i, onClick={filter=i}, label={Text(label)}, modifier=Modifier.testTag("launcher-filter-$i"))
            }
        }
        LazyColumn(Modifier.weight(1f), contentPadding=PaddingValues(bottom=24.dp)) {
            if (filter!=2 && builtins.isNotEmpty()) {
                item { Text("OĞUZDOWS", fontSize=10.sp, letterSpacing=2.sp, fontWeight=FontWeight.Bold, color=MaterialTheme.colorScheme.primary, modifier=Modifier.padding(vertical=12.dp)) }
                items(builtins.chunked(4), key={"internal-row-"+it.first().id}) { row ->
                    Row(Modifier.fillMaxWidth().padding(bottom=8.dp)) {
                        row.forEach { d ->
                            Column(Modifier.weight(1f).clip(RoundedCornerShape(12.dp)).combinedClickable(onClick={onOpen("internal:${d.id}")},onLongClick={edit("internal:${d.id}")})
                                .padding(vertical=9.dp).semantics {contentDescription="Modülü aç: ${d.label}"}, horizontalAlignment=Alignment.CenterHorizontally) {
                                DestinationIcon(d, 46); Spacer(Modifier.height(6.dp))
                                Text(d.label, fontSize=11.sp, maxLines=1, overflow=TextOverflow.Ellipsis)
                            }
                        }
                        repeat(4-row.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
            }
            if (filter!=1 && installed.isNotEmpty()) {
                item { Text("CİHAZINDAKİ UYGULAMALAR", fontSize=10.sp, letterSpacing=1.5.sp, fontWeight=FontWeight.Bold, color=MaterialTheme.colorScheme.primary, modifier=Modifier.padding(vertical=12.dp)) }
                items(installed, key={it.key}) { entry ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).combinedClickable(onClick={onOpen(entry.key)}, onLongClick={edit(entry.key)})
                        .padding(vertical=6.dp).semantics {contentDescription="Uygulamayı aç: ${entry.label}"}, verticalAlignment=Alignment.CenterVertically) {
                        InstalledIcon(entry, model.repository, 42); Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(entry.label, fontSize=14.sp, maxLines=1, overflow=TextOverflow.Ellipsis)
                            Text(entry.packageName, fontSize=10.sp, maxLines=1, overflow=TextOverflow.Ellipsis, color=MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        val pinned = entry.key in state.pins
                        IconButton(onClick={
                            if(pinned) edit(entry.key)
                            else report(if(model.pin(entry.key)) "Ana ekrana eklendi. İkinci sayfada da yer olabilir." else "Düzen dolu veya kaydı korumaya alındı. Önce bir kısayol kaldır.")
                        }, modifier=Modifier.semantics {contentDescription=if(pinned) "Kısayolu düzenle: ${entry.label}" else "Uygulamayı sabitle: ${entry.label}"}) {
                            if(pinned) Text("✓", color=MaterialTheme.colorScheme.primary) else ShellGlyph("plus", tint=MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
            if ((filter==2 || builtins.isEmpty()) && (filter==1 || installed.isEmpty())) item {
                Text(if(state.loading) "Sistem uygulamaları okunuyor…" else "Burada bir eşleşme yok. Başka bir ad deneyelim.", modifier=Modifier.padding(vertical=28.dp))
            }
        }
    }
}

@Composable
fun LauncherControls(state: LauncherUiState, model: LauncherViewModel, role:(String)->Unit,
                     system:(String)->Unit, brightness:(Float)->Unit, advanced:()->Unit, report:(String)->Unit) {
    val context = LocalContext.current
    var ownBrightness by rememberSaveable { mutableFloatStateOf((context as? Activity)?.window?.attributes?.screenBrightness?.takeIf{it>=0} ?: 1f) }
    var confirmReset by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { while(true) { model.refreshSystem(); delay(1000) } }
    Column(Modifier.fillMaxWidth().heightIn(max=650.dp).verticalScroll(rememberScrollState()).padding(horizontal=24.dp).testTag("launcher-control-panel")) {
        Text("Biraz sana göre.", style=MaterialTheme.typography.headlineSmall, fontWeight=FontWeight.SemiBold)
        Text("OğuzDows 0.3 · yerel kabuk", fontSize=12.sp, color=MaterialTheme.colorScheme.onSurfaceVariant)
        Row(Modifier.fillMaxWidth().padding(top=14.dp), verticalAlignment=Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { Text("Gece mavisi", fontWeight=FontWeight.Medium); Text("Kendi uygulama ekranlarımızda ortak tema", fontSize=11.sp) }
            Switch(checked=state.dark, onCheckedChange=model::dark, modifier=Modifier.testTag("launcher-dark-switch").semantics{contentDescription="Gece görünümü"})
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment=Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { Text("Hafif görünüm", fontWeight=FontWeight.Medium); Text("Daha sade yüzey ve karakter hareketi", fontSize=11.sp) }
            Switch(checked=state.lightEffects, onCheckedChange=model::lightEffects, modifier=Modifier.semantics{contentDescription="Hafif görünüm"})
        }
        Text("DUVAR KÂĞIDI", fontSize=10.sp, letterSpacing=1.5.sp, color=MaterialTheme.colorScheme.primary, modifier=Modifier.padding(top=18.dp,bottom=10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement=Arrangement.spacedBy(9.dp)) {
            ShellWallpapers.forEachIndexed { i, drawable ->
                Box(Modifier.weight(1f).height(84.dp).clip(RoundedCornerShape(12.dp)).clickable {model.wallpaper(i)}
                    .semantics{contentDescription="Duvar kâğıdı: ${ShellWallpaperNames[i]}"}) {
                    Image(painterResource(drawable), null, Modifier.fillMaxSize(), contentScale=ContentScale.Crop)
                    if(state.wallpaper==i) Text("✓", color=Color.White, modifier=Modifier.align(Alignment.BottomEnd).padding(8.dp), fontWeight=FontWeight.Bold)
                }
            }
        }
        Text("${ShellWallpaperNames[state.wallpaper]} · yalnız OğuzDows arka planı", fontSize=11.sp, modifier=Modifier.padding(top=7.dp))
        Text("Medya sesi · %${(state.mediaVolume*100).toInt()}", modifier=Modifier.padding(top=20.dp))
        Slider(value=state.mediaVolume, onValueChange=model::volume, modifier=Modifier.fillMaxWidth().testTag("launcher-volume").semantics{contentDescription="Gerçek sistem medya sesi"})
        Text("Pencere parlaklığı · %${(ownBrightness*100).toInt()}")
        Slider(value=ownBrightness, onValueChange={ownBrightness=it;brightness(it)}, valueRange=.08f..1f, modifier=Modifier.fillMaxWidth().semantics{contentDescription="OğuzDows pencere parlaklığı"})
        Text("Radyo ve odak durumu uydurulmaz; gerçek sistem panelleri açılır.", fontSize=11.sp, color=MaterialTheme.colorScheme.onSurfaceVariant)
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick={system("wifi")}) {Text("Wi-Fi")}
            OutlinedButton(onClick={system("bluetooth")}) {Text("Bluetooth")}
            OutlinedButton(onClick={system("dnd")}) {Text("Odak")}
        }
        if(!state.homeHeld) FilledTonalButton(onClick={role(RoleManager.ROLE_HOME)}, modifier=Modifier.fillMaxWidth()) {Text("Varsayılan ana ekran olarak seç")}
        OutlinedButton(onClick={role(RoleManager.ROLE_ASSISTANT)}, modifier=Modifier.fillMaxWidth()) {Text("Rıfkı’yı sistem yardımcısı seç")}
        Text("Sistem yardımcısı şu an metin tabanlıdır. Bulut, mikrofon ve uyandırma kelimesi bağlı değildir.", fontSize=11.sp, color=MaterialTheme.colorScheme.onSurfaceVariant)
        TextButton(onClick=advanced, modifier=Modifier.fillMaxWidth()) {Text("Diğer OğuzDows ayarları ve lisanslar")}
        TextButton(onClick={confirmReset=true}, modifier=Modifier.fillMaxWidth()) {Text("Yalnız ana ekran kısayollarını sıfırla")}
        Text("Nazar güç kimliğimizdir. Kapatma/kilit için telefonun fiziksel sistem menüsünü kullan; burada sahte kilit yok.", fontSize=11.sp, color=MaterialTheme.colorScheme.onSurfaceVariant, modifier=Modifier.padding(bottom=14.dp))
    }
    if(confirmReset) AlertDialog(onDismissRequest={confirmReset=false}, title={Text("Kısayol düzeni sıfırlansın mı?")},
        text={Text("Yalnız bu launcher’ın kısayolları varsayılana döner. Widget, SMS, kişi, uygulama ve roller silinmez.")},
        confirmButton={TextButton(onClick={model.resetPins();confirmReset=false}){Text("Düzeni sıfırla")}},
        dismissButton={TextButton(onClick={confirmReset=false}){Text("Vazgeç")}})
}

@Composable
fun RifkiPanel(state:LauncherUiState, act:(ShellSuggestion)->Unit) {
    var input by remember { mutableStateOf("") }
    var answer by remember { mutableStateOf(RifkiAnswer("Merhaba, ben Rıfkı. Evin kedisi, yerel rehberin. Tema, uygulamalar, Telefon ve Mağaza için buradayım.")) }
    var perk by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val tilt by animateFloatAsState(if(perk) -9f else 0f, tween(if(state.lightEffects) 0 else 180), label="Rıfkı baş eğme")
    Column(Modifier.fillMaxWidth().heightIn(max=600.dp).verticalScroll(rememberScrollState()).padding(horizontal=24.dp).testTag("launcher-rifki-panel")) {
        Row(verticalAlignment=Alignment.CenterVertically) {
            Image(painterResource(R.drawable.rifki), "Rıfkı’yı sev", Modifier.size(100.dp).graphicsLayer {rotationZ=tilt;scaleX=if(perk)1.04f else 1f;scaleY=scaleX}
                .clickable { answer=RifkiAnswer("Mrr. Tamam, iki saniyeliğine sevebilirsin. Şimdi ne yapıyoruz?");scope.launch{perk=true;delay(450);perk=false} })
            Column(Modifier.padding(start=14.dp)) {
                Text("Rıfkı.", style=MaterialTheme.typography.headlineLarge, fontWeight=FontWeight.SemiBold)
                Text(RifkiBehavior.reaction(RifkiContext(state.clock.hour,state.battery,state.charging,state.inCall)).mood, color=MaterialTheme.colorScheme.primary)
            }
        }
        Surface(color=MaterialTheme.colorScheme.secondaryContainer, shape=RoundedCornerShape(12.dp), modifier=Modifier.fillMaxWidth().padding(vertical=12.dp)) {
            Text("YEREL REHBER · Bulut bağlı değil · Mikrofon kapalı", fontSize=10.sp, lineHeight=16.sp, modifier=Modifier.padding(12.dp))
        }
        Text(answer.text, fontSize=16.sp, lineHeight=24.sp, modifier=Modifier.padding(vertical=12.dp).testTag("rifki-answer"))
        answer.suggestion?.let { suggestion -> FilledTonalButton(onClick={act(suggestion)}, modifier=Modifier.fillMaxWidth().testTag("rifki-suggestion")) {Text(answer.label)} }
        OutlinedTextField(input,{input=it.take(2000)},label={Text("Rıfkı’ya yaz")}, modifier=Modifier.fillMaxWidth().padding(top=14.dp).testTag("rifki-input"),maxLines=3,shape=RoundedCornerShape(14.dp))
        Button(onClick={answer=RifkiBehavior.answer(input);input=""},modifier=Modifier.fillMaxWidth().padding(top=10.dp).testTag("rifki-send")){Text("Söyle bakalım")}
        Text("Öneri düğmesine basılmadan işlem yapılmaz. Arama/SMS ayrıca kendi son onayını ister.",fontSize=11.sp,color=MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.padding(vertical=12.dp))
    }
}

@Composable
fun ShortcutEditor(key:String,state:LauncherUiState,model:LauncherViewModel,dismiss:()->Unit,report:(String)->Unit) {
    val label=LauncherRules.internalRoute(key)?.let{id->LauncherRules.destinations.find{it.id==id}?.label}
        ?:state.entries.find{it.key==key}?.label ?: "Kullanılamayan kısayol"
    Column(Modifier.fillMaxWidth().padding(horizontal=24.dp).testTag("launcher-shortcut-editor")) {
        Text(label,style=MaterialTheme.typography.headlineSmall)
        if(key in state.pins) {
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick={model.move(key,-1)},modifier=Modifier.weight(1f)){Text("Öne al")}
                OutlinedButton(onClick={model.move(key,1)},modifier=Modifier.weight(1f)){Text("Sona al")}
            }
            FilledTonalButton(onClick={model.unpin(key);dismiss()},modifier=Modifier.fillMaxWidth()){Text("Sabitlemeyi kaldır")}
        } else FilledTonalButton(onClick={report(if(model.pin(key))"Ana ekrana eklendi."else"Önce bir kısayol kaldır veya bozuk düzeni açıkça sıfırla.");dismiss()},modifier=Modifier.fillMaxWidth()){Text("Ana ekrana ekle")}
        val entry=state.entries.find{it.key==key}
        if(entry!=null) TextButton(onClick={if(!model.repository.details(entry))report("Uygulama bilgisi açılamadı.")}){Text("Sistem uygulama bilgisi")}
        Text("Bu işlem uygulamayı silmez. Düzen telefonda saklanır.",fontSize=12.sp,modifier=Modifier.padding(vertical=12.dp))
    }
}

@Composable
fun WidgetWorkspace(state:LauncherUiState, widgets:LauncherWidgets, pick:()->Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(top=16.dp).testTag("launcher-widget-space")) {
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Senin alanın.",color=Color.White,fontSize=22.sp,fontWeight=FontWeight.SemiBold)
                Text("Gerçek sistem widget’ları",color=Color.White.copy(.85f),fontSize=11.sp)
            }
            TextButton(onClick=pick,modifier=Modifier.testTag("launcher-add-widget")){Text("+ Widget",color=Color.White)}
        }
        if(state.widgetIds.isEmpty()) GlassSurface(Modifier.fillMaxWidth().padding(top=20.dp).clickable(onClick=pick),state.dark,state.lightEffects) {
            Column(Modifier.padding(22.dp)) {
                ShellGlyph("plus",tint=MaterialTheme.colorScheme.primary)
                Text("Bir pencere de sen aç.",fontSize=18.sp,fontWeight=FontWeight.Medium,modifier=Modifier.padding(top=10.dp))
                Text("Saat, takvim veya uygulamanın sunduğu gerçek widget’ı seç. Bağlama ve yapılandırma izni sistemden geçer.",fontSize=12.sp,lineHeight=18.sp,modifier=Modifier.padding(top=8.dp))
            }
        }
        state.widgetIds.forEach { id ->
            val info=widgets.manager.getAppWidgetInfo(id)
            GlassSurface(Modifier.fillMaxWidth().padding(top=12.dp),state.dark,state.lightEffects) {
                Column(Modifier.padding(10.dp)) {
                    Row(verticalAlignment=Alignment.CenterVertically) {
                        Text(info?.loadLabel(LocalContext.current.packageManager)?:"Widget kullanılamıyor",modifier=Modifier.weight(1f),fontSize=11.sp,maxLines=1)
                        IconButton(onClick={widgets.remove(id)},modifier=Modifier.size(48.dp).semantics{contentDescription="Widget kaldır: $id"}) {ShellGlyph("close",tint=MaterialTheme.colorScheme.onSurface)}
                    }
                    if(info!=null) {
                        val density=LocalDensity.current.density
                        AndroidView(factory={context->widgets.host.createView(context,id,info)},
                            modifier=Modifier.fillMaxWidth().height(160.dp).testTag("launcher-widget-$id"),
                            update={host->host.post {val width=(host.width/density).toInt().coerceAtLeast(100);host.updateAppWidgetSize(null,width,160,width,160)}})
                    } else Text("Sağlayıcı kaldırılmış veya profil kapalı olabilir. İstersen bu alandan kaldırabilirsin.",fontSize=12.sp)
                }
            }
        }
    }
}

@Composable
fun WidgetPicker(widgets:LauncherWidgets, select:(AppWidgetProviderInfo)->Unit) {
    val context=LocalContext.current
    var providers by remember { mutableStateOf<List<AppWidgetProviderInfo>?>(null) }
    LaunchedEffect(Unit) { providers = withContext(Dispatchers.IO) { widgets.providers() } }
    Column(Modifier.fillMaxWidth().fillMaxHeight(.8f).padding(horizontal=24.dp).testTag("launcher-widget-picker")) {
        Text("Kendi pencereni seç.",style=MaterialTheme.typography.headlineSmall)
        Text("Yalnız cihazındaki widget sağlayıcıları. Uygun olduğunda sistem izin ve ayar ekranını açar.",fontSize=12.sp,modifier=Modifier.padding(vertical=12.dp))
        LazyColumn {
            if(providers==null) item{Text("Sistem widget’ları okunuyor…")}
            else if(providers!!.isEmpty()) item{Text("Bu profilde erişilebilir widget bulunamadı.")}
            else items(providers!!,key={it.provider.flattenToString()}) {provider->
                ListItem(headlineContent={Text(provider.loadLabel(context.packageManager))},supportingContent={Text(provider.provider.packageName,fontSize=10.sp)},
                    modifier=Modifier.clickable{select(provider)}.semantics{contentDescription="Widget seç: ${provider.loadLabel(context.packageManager)}"})
            }
        }
    }
}
