package org.oguzdows.mobile

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.RectF
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.DragEvent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.net.Inet4Address
import java.net.NetworkInterface

/** PC / phone / ARM share the same versioned, certificate-pinned, locally approved protocol. */
class BridgeActivity : ComponentActivity() {
    val model: BridgeViewModel by viewModels()
    private var systemWindow = false
    private var mirrorPeer: String? = null
    private val handler = Handler(Looper.getMainLooper())
    private val expireChooser = Runnable { if (!BridgeRuntime.visible && !BridgeMirrorService.running) model.stop() }
    private val chooseFiles = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        systemWindow = false
        if (uris.isNotEmpty()) model.stage(uris)
    }
    private val saveFile = registerForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        systemWindow = false
        if (uri != null) model.save(uri) else model.pendingExport = null
    }
    private val capture = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        systemWindow = false
        val host = model.host; val peer = mirrorPeer; mirrorPeer = null
        if (result.resultCode == Activity.RESULT_OK && result.data != null && host != null && peer != null) {
            try {
                host.permitMirror(peer)
                ContextCompat.startForegroundService(this, Intent(this, BridgeMirrorService::class.java)
                    .putExtra("result", result.resultCode).putExtra("consent", result.data))
                model.report("Sistemin ekran izni alındı. Paylaşım başlatılamazsa canlı görüntü varmış gibi gösterilmez. Bildirimden veya buradan durdur.")
            } catch (_: Exception) { host.stopMirror(); model.report("Ekran paylaşımı başlatılamadı.") }
        } else model.report("Ekran izni verilmedi; yansıtma başlamadı.")
    }
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { allowed ->
        if (allowed) requestCapture() else { mirrorPeer = null; model.report("Durdurma bildirimi için bildirim izni gerekli. Ekran paylaşılmadı.") }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        NativeUi.theme(this); super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE) // Invitations and received files are not themselves mirrored.
        window.decorView.setOnDragListener { _, event ->
            when (event.action) {
                DragEvent.ACTION_DRAG_STARTED -> event.clipDescription?.hasMimeType("text/uri-list") == true || event.clipDescription?.filterMimeTypes("*/*")?.isNotEmpty() == true
                DragEvent.ACTION_DROP -> {
                    val grant = requestDragAndDropPermissions(event)
                    val uris = (0 until (event.clipData?.itemCount ?: 0)).mapNotNull { event.clipData?.getItemAt(it)?.uri }
                    if (uris.isNotEmpty()) model.stage(uris) { grant?.release() } else { grant?.release(); model.report("Yalnız sistemin okuma izni verdiği belge URI’leri bırakılabilir.") }
                    true
                }
                else -> true
            }
        }
        setContent {
            val store = remember { LauncherStore(this) }
            ConnectedTheme(NativeUi.dark(this), store.wallpaper(), store.glass(), store.lightEffects()) { Screen(store) }
        }
    }
    override fun onStart() { super.onStart(); BridgeRuntime.visible = true }
    override fun onResume() { super.onResume(); systemWindow = false; handler.removeCallbacks(expireChooser); shellFullscreen(LauncherStore(this).fullscreen()) }
    override fun onStop() {
        BridgeRuntime.visible = false
        if (!isChangingConfigurations && !BridgeMirrorService.running) {
            if (systemWindow) handler.postDelayed(expireChooser, 60000) else model.stop()
        }
        super.onStop()
    }
    override fun onDestroy() { handler.removeCallbacks(expireChooser); super.onDestroy() }
    private fun chooser(open: () -> Unit) { systemWindow = true; try { open() } catch (_: Exception) { systemWindow = false; model.report("Bu cihazda sistem belge/ekran seçicisi bulunamadı.") } }
    private fun requestCapture() = chooser { capture.launch(getSystemService(MediaProjectionManager::class.java).createScreenCaptureIntent()) }
    private fun mirror(peer: String) {
        mirrorPeer = peer
        if (Build.VERSION.SDK_INT >= 33 && !PlatformState.granted(this, Manifest.permission.POST_NOTIFICATIONS)) notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        else requestCapture()
    }
    private fun export(item: BridgeItem, file: java.io.File) {
        model.pendingExport = item to file
        chooser { saveFile.launch(item.name) }
    }
    @OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
    @Composable private fun Screen(store: LauncherStore) {
        val lifecycle = LocalLifecycleOwner.current
        LaunchedEffect(lifecycle) { lifecycle.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) { while (true) { model.pollRemote(); delay(1500) } } }
        var input by remember { mutableStateOf("") } // Never rememberSaveable: invitation includes a temporary secret.
        var confirmMirror by remember { mutableStateOf<BridgePeer?>(null) }
        var dropBounds by remember { mutableStateOf(Rect.Zero) }
        var dragging by remember { mutableStateOf("") }
        var dragPoint by remember { mutableStateOf(Offset.Zero) }
        var watch by rememberSaveable { mutableStateOf(false) }
        val localAddresses = remember { try {
            NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }.flatMap { iface ->
                iface.inetAddresses.toList().filterIsInstance<Inet4Address>().mapNotNull { it.hostAddress }.filter(BridgeRules::localAddress).map { iface.displayName to it }
            }
        } catch (_: Exception) { emptyList() } }
        Box(Modifier.fillMaxSize().testTag("oguz-bridge").semantics { testTagsAsResourceId = true }) {
            Image(painterResource(ShellWallpapers[store.wallpaper()]), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            Box(Modifier.fillMaxSize().background(if (NativeUi.dark(this@BridgeActivity)) Color(0xD9102730) else Color(0xDFF1F6F2)))
            Column(Modifier.fillMaxSize().systemBarsPadding().imePadding().verticalScroll(rememberScrollState()).testTag("bridge-scroll").padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { model.stop(); finish() }) { Text("Geri") }
                    TextButton(onClick = model::stop, modifier = Modifier.testTag("bridge-stop")) { Text("Oturumu kapat") }
                }
                Text("OğuzKöprü.", style = MaterialTheme.typography.headlineLarge)
                Text("PC · telefon · ARM / aynı ağ, aynı masa", style = MaterialTheme.typography.titleSmall)
                Text("Dosyayı seç veya belge uygulamasından bırak. Aşağıdaki cihaza/masaya uzun basıp sürükleyebilirsin. Uzaktan fare/klavye, rehber, SMS veya kurulum yetkisi paylaşılmaz.", fontSize = 12.sp)
                GlassSurface(Modifier.fillMaxWidth()) { Text(model.message, modifier = Modifier.padding(16.dp).testTag("bridge-status"), fontSize = 13.sp) }
                if (model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (model.host == null && model.client == null) {
                    Button(enabled = !model.busy, onClick = model::startHost, modifier = Modifier.fillMaxWidth().testTag("bridge-host")) { Text("Bu cihazda 15 dakikalık masa aç") }
                    OutlinedTextField(input, { input = it.take(1200) }, label = { Text("Diğer cihazın oguzkopru1: daveti") }, modifier = Modifier.fillMaxWidth().testTag("bridge-invitation"), maxLines = 4)
                    OutlinedButton(enabled = input.isNotBlank() && !model.busy, onClick = { val value = input; input = ""; model.connect(value) }, modifier = Modifier.fillMaxWidth().testTag("bridge-connect")) { Text("Davetle eşleşme iste") }
                }
                model.host?.let { host ->
                    Text("YEREL MASA · TLS · en çok 2 onaylı cihaz", fontSize = 10.sp)
                    if (localAddresses.isEmpty()) Text("Yerel IPv4 bulunamadı. Wi-Fi/Ethernet’e bağlanıp ekranı yeniden aç.")
                    localAddresses.forEach { (iface, ip) -> OutlinedButton(onClick = { model.invite(ip) }, enabled = !model.busy) { Text("$iface · $ip · davet göster") } }
                    if (model.invitation.isNotEmpty()) {
                        SelectionContainer { Text(model.invitation, fontSize = 11.sp, modifier = Modifier.testTag("bridge-local-invitation")) }
                        TextButton(onClick = model::hideInvitation) { Text("Gizle · daveti herkese açık paylaşma") }
                    }
                    model.pairs.filter { it.status == "pending" }.forEach { pair ->
                        GlassSurface(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) {
                            Text("${pair.name} · ${pair.code}", style = MaterialTheme.typography.titleMedium)
                            Text("Kod diğer ekranda birebir aynı mı? İsim tek başına kimlik kanıtı değildir.", fontSize = 12.sp)
                            Row { TextButton(onClick = { model.approvePair(pair.id, true) }) { Text("Kod aynı · izin ver") }; TextButton(onClick = { model.approvePair(pair.id, false) }) { Text("Reddet") } }
                        } }
                    }
                    model.peers.forEach { peer ->
                        GlassSurface(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp)) {
                            Text("${peer.name} · ${peer.code}")
                            Row { TextButton(onClick = { model.revoke(peer.id) }) { Text("Erişimi kes") }; TextButton(onClick = { confirmMirror = peer }) { Text("Ekranımı paylaş…") } }
                        } }
                    }
                    if (host.viewer != null || BridgeMirrorService.running) Button(onClick = { host.stopMirror(); stopService(Intent(this@BridgeActivity, BridgeMirrorService::class.java)) }) { Text("Ekran paylaşımını DURDUR") }
                    model.incoming.forEach { item ->
                        ListItem(headlineContent = { Text(item.name) }, supportingContent = { Text("${item.bytes} bayt · ${item.status}") }, trailingContent = {
                            when (item.status) {
                                "pending" -> Row { TextButton(onClick = { model.approveFile(item.id, true) }) { Text("Kabul") }; TextButton(onClick = { model.approveFile(item.id, false) }) { Text("Reddet") } }
                                "ready" -> TextButton(onClick = { try { val value = host.received(item.id); export(value.first, value.second) } catch (_: Exception) { model.report("Alınan dosya artık bu oturumda değil.") } }) { Text("Kaydet…") }
                            }
                        })
                    }
                }
                if (model.client != null && !model.connected) {
                    Text("KARŞILAŞTIR: ${model.pairCode}", style = MaterialTheme.typography.headlineSmall)
                    Button(onClick = model::confirmPair, enabled = !model.busy, modifier = Modifier.testTag("bridge-confirm-code")) { Text("Kod aynı · onayı denetle") }
                }
                val dropReady = model.connected || model.host != null
                GlassSurface(Modifier.fillMaxWidth().heightIn(min = 100.dp).onGloballyPositioned { dropBounds = it.boundsInRoot() }.testTag("bridge-drop-target")) {
                    Column(Modifier.fillMaxWidth().padding(18.dp)) {
                        Text(if (model.connected) model.remote?.name ?: "Eşleşen cihaz" else "Paylaşım masası · ${model.peers.size} cihaz", style = MaterialTheme.typography.titleMedium)
                        Text(if (dropReady) if (dragging.isNotEmpty()) "BIRAK: $dragging" else "Seçilmiş dosyayı buraya sürükle · düğmeler de aynı işi yapar" else "Önce bir oturum aç veya eşleş", fontSize = 12.sp)
                        if (model.host != null) Text("Masaya koyulan dosyalar bu oturumun tüm onaylı cihazlarına görünür.", fontSize = 11.sp)
                    }
                }
                OutlinedButton(onClick = { chooser { chooseFiles.launch(arrayOf("*/*")) } }, enabled = !model.busy, modifier = Modifier.fillMaxWidth().testTag("bridge-choose-files")) { Text("+ Sistemden dosya seç / buraya belge bırak") }
                Text("En çok 8 dosya/kuyruk · dosya başına 128 MiB · 256 MiB/kuyruk. Klasör/arşiv açma ve otomatik dosya çalıştırma yok.", fontSize = 11.sp)
                model.staged.forEach { item ->
                    var bounds by remember(item.id) { mutableStateOf(Rect.Zero) }
                    GlassSurface(Modifier.fillMaxWidth().onGloballyPositioned { bounds = it.boundsInRoot() }
                        .pointerInput(item.id, dropReady, model.client, model.host) {
                            detectDragGesturesAfterLongPress(onDragStart = { dragging = item.name; dragPoint = bounds.topLeft + it },
                                onDragCancel = { dragging = "" }, onDragEnd = {
                                    if (dropReady && dropBounds.contains(dragPoint)) { if (model.connected) model.propose(item) else model.publish(item) }; dragging = ""
                                }) { change, amount -> change.consume(); dragPoint += amount }
                        }) { Column(Modifier.padding(14.dp)) {
                        Text(item.name, style = MaterialTheme.typography.titleSmall); Text("${item.bytes} bayt · ${item.sha256.take(12)}…", fontSize = 11.sp)
                        Row {
                            if (model.host != null) TextButton(enabled = !model.busy, onClick = { model.publish(item) }) { Text("Masaya koy") }
                            if (model.connected) {
                                TextButton(enabled = !model.busy, onClick = { model.propose(item) }) { Text("Gönderim öner") }
                                if (model.uploads.containsKey(item.id)) TextButton(enabled = !model.busy, onClick = { model.sendApproved(item) }) { Text("Alıcı onayladıysa gönder") }
                            }
                        }
                    } }
                }
                model.remote?.let { state ->
                    Text("${state.name} · seçilmiş dosyalar", style = MaterialTheme.typography.titleMedium)
                    state.files.forEach { item -> ListItem(headlineContent = { Text(item.name) }, supportingContent = { Text("${item.bytes} bayt · SHA-256 doğrulanır") }, trailingContent = {
                        val file = model.downloaded[item.id]
                        if (file == null) TextButton(enabled = !model.busy, onClick = { model.receive(item) }) { Text("Al") }
                        else TextButton(enabled = !model.busy, onClick = { export(item, file) }) { Text("Kaydet…") }
                    }) }
                    if (state.mirror) {
                        Button(onClick = { watch = !watch }) { Text(if (watch) "Görüntülemeyi kapat" else "İzinli ekranı görüntüle") }
                        if (watch) model.client?.let { LiveMirror(it) }
                    } else Text("Diğer cihaz ekran paylaşımına izin vermedi. Sahte görüntü yok.", fontSize = 12.sp)
                }
                Text("OğuzKöprü/1 · ekran salt görüntü, ses yok · en çok 2 kare/sn, 1280 px uzun kenar. OğuzDows’tan çıkışta oturum kapanır; yalnız sistem izniyle açık ekran paylaşımı bildirimle sürebilir. Sistem seçicileri için 60 sn süre tanınır.", fontSize = 11.sp)
                Spacer(Modifier.height(16.dp))
            }
        }
        confirmMirror?.let { peer -> AlertDialog(onDismissRequest = { confirmMirror = null }, title = { Text("${peer.name} ekranını görebilsin mi?") },
            text = { Text("Ekranındaki özel bilgiler de görünebilir. Sistem bir sonraki adımda uygulama/tüm ekran seçimini ve son izni sorar. Ses, dokunma, klavye, SMS veya kurulum yetkisi verilmez. Kilitlenince/durdurunca paylaşım biter. Güvenli pencereler siyah kalır.") },
            confirmButton = { TextButton(onClick = { confirmMirror = null; mirror(peer.id) }) { Text("Sistem ekran iznine geç") } }, dismissButton = { TextButton(onClick = { confirmMirror = null }) { Text("Vazgeç") } }) }
    }
}

@Composable
private fun LiveMirror(client: BridgeClient) {
    val lifecycle = LocalLifecycleOwner.current
    var frame by remember(client) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    var notice by remember(client) { mutableStateOf("Canlı kare bekleniyor; kayıt oynatılmaz.") }
    LaunchedEffect(client, lifecycle) { lifecycle.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        while (true) {
            try {
                val image = withContext(Dispatchers.IO) {
                    val bytes = client.frame()
                    if (bytes.isEmpty()) null else {
                        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                        require(bounds.outWidth in 1..1280 && bounds.outHeight in 1..1280)
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
                    }
                }
                frame = image; notice = if (image == null) "Yeni kare yok; durmuş görüntü canlı diye gösterilmez." else "Salt görüntü · dokunma/uzaktan kontrol yok"
            } catch (_: Exception) { frame = null; notice = "Ekran izni/bağlantısı kapalı. Önceki kare gösterilmedi." }
            delay(500)
        }
    } }
    Column {
        frame?.let { Image(it, "İzinli cihaz ekranı", Modifier.fillMaxWidth().heightIn(max = 440.dp), contentScale = ContentScale.Fit) }
        Text(notice, fontSize = 11.sp)
    }
}
