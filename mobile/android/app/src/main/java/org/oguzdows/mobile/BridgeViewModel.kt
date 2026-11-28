package org.oguzdows.mobile

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.SystemClock
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Activity-owned session, explicit foreground-service exception only for consented screen sharing. */
class BridgeViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application
    private val root = File(app.cacheDir, "kopru-ui-${BridgeRules.token(16)}").apply { check(mkdirs()) }
    var host by mutableStateOf<BridgeHost?>(null); private set
    var pairs by mutableStateOf(emptyList<BridgePair>()); private set
    var peers by mutableStateOf(emptyList<BridgePeer>()); private set
    var incoming by mutableStateOf(emptyList<BridgeItem>()); private set
    var staged by mutableStateOf(emptyList<BridgeItem>()); private set
    var remote by mutableStateOf<BridgeRemoteState?>(null); private set
    var client by mutableStateOf<BridgeClient?>(null); private set
    var pairCode by mutableStateOf(""); private set
    var connected by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    var message by mutableStateOf("Aynı yerel ağda, iki cihazda da OğuzKöprü’yü aç. Otomatik keşif veya bulut aktarımı yok."); private set
    var invitation by mutableStateOf(""); private set
    var uploads by mutableStateOf<Map<String, String>>(emptyMap()); private set
    var downloaded by mutableStateOf<Map<String, File>>(emptyMap()); private set
    var pendingExport: Pair<BridgeItem, File>? = null
    private var epoch = 0
    private var pairedAt = 0L
    init {
        // Remove orphaned private copies from an earlier process crash; never an active capture host.
        val active = BridgeRuntime.host?.root
        viewModelScope.launch(Dispatchers.IO) {
            app.cacheDir.listFiles()?.filter { it != root && it != active && it.name.matches(Regex("kopru-(ui-)?[a-f0-9]{32}")) }?.forEach { it.deleteRecursively() }
        }
    }

    private fun work(block: suspend () -> Unit) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try { block() }
            catch (_: Exception) { message = "İşlem tamamlanmadı. Ağ/izin/oturum, dosya sınırı veya özet uyuşmamış olabilir; otomatik tekrar yapılmadı." }
            finally { busy = false }
        }
    }
    fun startHost() = work {
        val generation = epoch
        val opened = withContext(Dispatchers.IO) { BridgeHost(app, "OğuzDows telefon").start() }
        if (generation != epoch || !BridgeRuntime.visible) { withContext(Dispatchers.IO) { opened.close() }; return@work }
        host = opened; BridgeRuntime.host = opened
        message = "Sunucu yalnız bu oturumda açık. Aşağıdaki yerel IP’yi seçip iki dakikalık daveti göster."
    }
    fun invite(address: String) {
        val h = host ?: return
        try {
            require(BridgeRules.localAddress(address) && !address.startsWith("127."))
            h.renew(); invitation = BridgeInvitation(address, h.server.port, h.server.pin, h.secret).encode()
            message = "Davet 2 dakika, eşleşme en çok 15 dakika geçerli. Daveti özel kanaldan aktar; iki ekrandaki 8 haneli kodu karşılaştır."
        } catch (_: Exception) { message = "Bu oturum için geçerli bir yerel ağ IPv4 adresi seç." }
    }
    fun hideInvitation() { invitation = "" }
    fun connect(text: String) = work {
        val generation = epoch
        val c = BridgeClient(BridgeInvitation.parse(text))
        val reply = withContext(Dispatchers.IO) { c.pair("OğuzDows telefon") }
        if (generation != epoch) { c.forget(); return@work }
        client = c; pairCode = reply.getString("code"); pairedAt = SystemClock.elapsedRealtime()
        message = "Kodu diğer ekrandan doğrula. Karşı taraf onayladıktan sonra ‘Kod aynı’ düğmesine bas."
    }
    fun confirmPair() = work {
        val c = client ?: return@work
        val status = withContext(Dispatchers.IO) { c.pollPair() }
        if (c !== client) return@work
        connected = status == "approved"
        message = when (status) { "approved" -> "Sertifika sabitlemeli TLS oturumu açık. Yalnız seçtiğin dosyalar ve ayrıca onaylanan ekran paylaşılır."; "pending" -> "Diğer cihaz henüz onaylamadı."; else -> "Eşleşme reddedildi; yeni davet gerekir." }
    }
    fun approvePair(id: String, allow: Boolean) { try { host?.approvePair(id, allow); refreshHost() } catch (_: Exception) { message = "Eşleşme isteğinin süresi dolmuş olabilir." } }
    fun approveFile(id: String, allow: Boolean) { try { host?.approveInbox(id, allow); refreshHost() } catch (_: Exception) { message = "Dosya isteği artık uygun değil." } }
    fun revoke(id: String) { host?.revoke(id); refreshHost(); message = "Cihazın erişimi ve varsa ekran paylaşımı geri alındı." }
    fun refreshHost() {
        val h = host ?: return
        if (h.closed || SystemClock.elapsedRealtime() - h.started > BridgeRules.TTL) { stop(); return }
        val values = h.snapshot(); pairs = values.first; peers = values.second; incoming = values.third
    }
    suspend fun pollRemote() {
        refreshHost()
        val c = client ?: return
        if (SystemClock.elapsedRealtime() - pairedAt > BridgeRules.TTL) { stop(); return }
        if (!connected || busy) return
        try {
            val value = withContext(Dispatchers.IO) { c.state() }
            if (c === client) remote = value
        } catch (_: Exception) { if (c === client) { remote = null; message = "Cihaza ulaşılamadı; çevrimiçi varsayılmadı. Oturumu kapatıp yeni davetle eşleşebilirsin." } }
    }
    fun stage(uris: List<Uri>, completed: () -> Unit = {}) {
        if (busy) { completed(); return }
        val generation = epoch
        work {
            try {
                val free = BridgeRules.MAX_ITEMS - staged.size
                require(uris.size in 1..free)
                val fresh = withContext(Dispatchers.IO) {
                    val created = mutableListOf<BridgeItem>()
                    try {
                        var total = staged.sumOf { it.bytes }
                        for (uri in uris) {
                            require(uri.scheme == "content") { "Yalnız seçilmiş sistem belge URI’si" }
                            var name = "Secilen-dosya"
                            app.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                                if (cursor.moveToFirst()) name = cursor.getString(0) ?: name
                            }
                            BridgeRules.name(name)
                            val id = BridgeRules.token(16); val target = File(root, id)
                            try {
                                require(root.usableSpace > 16L * 1024 * 1024)
                                val (size, hash) = target.outputStream().use { out ->
                                    requireNotNull(app.contentResolver.openInputStream(uri)).use { input ->
                                        BridgeRules.copy(input, out, minOf(BridgeRules.MAX_FILE, BridgeRules.BUDGET - total))
                                    }
                                }
                                total += size; created += BridgeItem(id, name, size, hash)
                            } catch (error: Exception) { target.delete(); throw error }
                        }
                        created
                    } catch (error: Exception) { created.forEach { File(root, it.id).delete() }; throw error }
                }
                if (generation != epoch) { withContext(Dispatchers.IO) { fresh.forEach { File(root, it.id).delete() } }; return@work }
                staged = staged + fresh; message = "${fresh.size} seçilmiş dosya hazırlandı. Henüz bir cihaza gönderilmedi."
            } finally { completed() }
        }
    }
    fun publish(item: BridgeItem) = work {
        val h = host ?: return@work
        withContext(Dispatchers.IO) { h.offer(File(root, item.id).inputStream(), item.name) }
        message = "${item.name} eşleşen cihazların paylaşım masasında. Karşı cihaz ayrıca Al demeden indirilmez."
    }
    fun propose(item: BridgeItem) = work {
        val c = client?.takeIf { connected } ?: return@work
        val id = withContext(Dispatchers.IO) { c.propose(item) }
        if (c !== client) return@work
        uploads = uploads + (item.id to id)
        message = "${item.name} için alıcı onayı istendi. Baytlar henüz gönderilmedi."
    }
    fun sendApproved(item: BridgeItem) = work {
        val c = client ?: return@work; val id = uploads[item.id] ?: return@work
        val status = withContext(Dispatchers.IO) { c.uploadStatus(id) }
        if (c !== client) return@work
        if (status != "approved") { message = "Alıcı durumu: $status. Onaysız aktarım yapılmadı."; return@work }
        val result = withContext(Dispatchers.IO) { c.upload(id, File(root, item.id)) }
        if (c === client) { message = if (result == "ready") "Alıcı dosyanın SHA-256 özetini doğruladı. Kalıcı kaydetmeyi kendi ekranında seçer." else "Alıcı tamamlanma bildirmedi."; uploads = uploads - item.id }
    }
    fun receive(item: BridgeItem) = work {
        val c = client ?: return@work
        require(downloaded.size + staged.size < BridgeRules.MAX_ITEMS &&
            downloaded.values.sumOf { it.length() } + staged.sumOf { it.bytes } + item.bytes <= BridgeRules.BUDGET)
        val target = File(root, "received-${BridgeRules.token(16)}")
        withContext(Dispatchers.IO) { c.receive(item, target) }
        if (c === client) { downloaded = downloaded + (item.id to target); message = "Dosya özeti doğrulandı. Kalıcı konumu ‘Kaydet’ ile sistemde seç; dosya çalıştırılmaz/açılmaz." } else target.delete()
    }
    fun save(uri: Uri) = work {
        val (item, file) = pendingExport ?: return@work
        pendingExport = null
        withContext(Dispatchers.IO) {
            require(uri.scheme == "content")
            BridgeRules.verify(file, item.bytes, item.sha256)
            requireNotNull(app.contentResolver.openOutputStream(uri, "w")).use { output -> file.inputStream().use { BridgeRules.copy(it, output, BridgeRules.MAX_FILE) } }
        }
        message = "${item.name} sistemde seçtiğin konuma yazıldı. Hiçbir dosya otomatik açılmadı/kurulmadı."
    }
    fun report(text: String) { message = text }
    fun stop() {
        epoch++
        app.stopService(Intent(app, BridgeMirrorService::class.java))
        val h = host; val c = client
        host = null; client = null; connected = false; remote = null; pairCode = ""; invitation = ""
        pairs = emptyList(); peers = emptyList(); incoming = emptyList(); uploads = emptyMap()
        val privateFiles = root.listFiles()?.toList() ?: emptyList()
        staged = emptyList(); downloaded = emptyMap(); pendingExport = null
        if (BridgeRuntime.host === h) BridgeRuntime.host = null
        viewModelScope.launch(Dispatchers.IO) { h?.close(); privateFiles.forEach { it.delete() }; try { c?.disconnect() } catch (_:Exception) { c?.forget() } }
        message = "Oturum kapalı. Eşleşme anahtarları yalnız bellekteydi; yeni bağlantı için yeni davet gerekir."
    }
    override fun onCleared() {
        client?.forget(); host?.close()
        if (BridgeRuntime.host === host) BridgeRuntime.host = null
        app.stopService(Intent(app, BridgeMirrorService::class.java)); root.deleteRecursively(); super.onCleared()
    }
}
