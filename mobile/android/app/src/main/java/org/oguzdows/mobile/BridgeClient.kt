package org.oguzdows.mobile

import android.util.Base64
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.Proxy
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

/** A pasted LAN invitation is used only here. Never in WebView, browser URLs, logs or preferences. */
data class BridgeInvitation(val host: String, val port: Int, val pin: String, val secret: String) {
    fun encode(): String = "oguzkopru1:" + Base64.encodeToString(JSONObject().put("host", host).put("port", port)
        .put("pin", pin).put("secret", secret).toString().toByteArray(Charsets.UTF_8), Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    companion object {
        fun parse(raw: String): BridgeInvitation {
            val text = raw.trim()
            require(text.length <= 1200 && text.startsWith("oguzkopru1:")) { "OğuzKöprü daveti gerekli." }
            val encoded = text.removePrefix("oguzkopru1:")
            require(encoded.matches(Regex("[A-Za-z0-9_-]+")))
            val json = JSONObject(Base64.decode(encoded, Base64.URL_SAFE or Base64.NO_WRAP).toString(Charsets.UTF_8))
            require(json.keys().asSequence().toSet() == setOf("host", "port", "pin", "secret") && json.get("port") is Int)
            val value = BridgeInvitation(json.getString("host"), json.getInt("port"), json.getString("pin"), json.getString("secret"))
            require(BridgeRules.localAddress(value.host) && value.port in 1024..65535 && BridgeRules.hash(value.pin) && BridgeRules.hash(value.secret))
            return value
        }
    }
}
data class BridgeRemoteState(val name: String, val files: List<BridgeItem>, val mirror: Boolean)

class BridgeClient(val invitation: BridgeInvitation) {
    @Volatile private var bearer: String? = null
    private var pending: JSONObject? = null
    @Volatile private var closed = false
    private val active = mutableSetOf<HttpsURLConnection>()
    private val tls = SSLContext.getInstance("TLS").apply {
        init(null, arrayOf(object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) { throw java.security.cert.CertificateException("Client trust not supported") }
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                if (chain.isEmpty() || !MessageDigest.isEqual(BridgeRules.sha(chain[0].encoded).toByteArray(), invitation.pin.toByteArray()))
                    throw java.security.cert.CertificateException("Sertifika parmak izi eşleşmedi")
            }
        }), SecureRandom())
    }

    private fun request(method: String, path: String, value: JSONObject? = null, source: File? = null,
                        target: File? = null, limit: Long = 65536): ByteArray {
        check(!closed) { "Oturum kapalı" }
        require(path.matches(Regex("/v1/[A-Za-z0-9/-]+")))
        val connection = URL("https://${invitation.host}:${invitation.port}$path").openConnection(Proxy.NO_PROXY) as HttpsURLConnection
        connection.sslSocketFactory = tls.socketFactory
        connection.hostnameVerifier = javax.net.ssl.HostnameVerifier { host, session ->
            host == invitation.host && session.peerCertificates.isNotEmpty() &&
                BridgeRules.sha(session.peerCertificates[0].encoded) == invitation.pin
        }
        connection.instanceFollowRedirects = false
        connection.connectTimeout = 15000; connection.readTimeout = 15000
        connection.requestMethod = method
        connection.setRequestProperty("Connection", "close")
        bearer?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
        var created = false
        synchronized(active) { check(!closed); active.add(connection) }
        try {
            if (method == "POST" || method == "PUT") {
                val body = value?.toString()?.toByteArray(Charsets.UTF_8) ?: ByteArray(0)
                val length = source?.length() ?: body.size.toLong()
                require(length in 0..BridgeRules.MAX_FILE)
                connection.doOutput = true
                connection.setFixedLengthStreamingMode(length)
                connection.setRequestProperty("Content-Type", if (source != null) "application/octet-stream" else "application/json")
                connection.outputStream.use { output ->
                    if (source != null) source.inputStream().use { BridgeRules.copy(it, output, length) }
                    else output.write(body)
                }
            }
            val status = connection.responseCode
            if (status !in 200..299) throw BridgeDenied(status)
            val length = connection.getHeaderField("Content-Length")?.toLongOrNull() ?: throw IllegalArgumentException("Yanıt boyutu eksik")
            require(length in 0..limit) { "Yanıt boyut sınırı" }
            connection.inputStream.use { input ->
                if (target != null) {
                    check(target.createNewFile()) { "Hedef dosya zaten var" }; created = true
                    target.outputStream().use { output -> require(BridgeRules.copy(input, output, limit).first == length) }
                    return ByteArray(0)
                }
                val output = ByteArrayOutputStream()
                require(BridgeRules.copy(input, output, limit).first == length)
                return output.toByteArray()
            }
        } catch (error: Exception) { if (created) target?.delete(); throw error }
        finally { synchronized(active) { active.remove(connection) }; connection.disconnect() }
    }

    fun pair(name: String): JSONObject {
        require(bearer == null)
        BridgeRules.name(name)
        val nonce = BridgeRules.token()
        val reply = JSONObject(request("POST", "/v1/pair", JSONObject().put("name", name.take(80)).put("secret", invitation.secret).put("nonce", nonce)).toString(Charsets.UTF_8))
        val id = reply.getString("id"); require(BridgeRules.id(id))
        require(reply.getString("code") == BridgeRules.sha((id + nonce).toByteArray()).take(8).uppercase(java.util.Locale.ROOT))
        pending = JSONObject().put("id", id).put("nonce", nonce)
        return reply
    }
    fun pollPair(): String {
        val reply = JSONObject(request("POST", "/v1/pair/status", requireNotNull(pending)).toString(Charsets.UTF_8))
        val status = reply.getString("status")
        require(status in listOf("pending", "approved", "rejected"))
        if (status == "approved") { val token = reply.getString("token"); require(BridgeRules.hash(token)); bearer = token; pending = null }
        return status
    }
    fun state(): BridgeRemoteState {
        val value = JSONObject(request("GET", "/v1/state").toString(Charsets.UTF_8))
        require(value.getInt("version") == 1)
        val name = BridgeRules.name(value.getString("name")).take(80)
        val array = value.getJSONArray("files"); require(array.length() <= BridgeRules.MAX_ITEMS)
        val files = (0 until array.length()).map { i ->
            val f = array.getJSONObject(i); val id = f.getString("id"); val size = f.getLong("bytes"); val hash = f.getString("sha256")
            require(BridgeRules.id(id) && size in 0..BridgeRules.MAX_FILE && BridgeRules.hash(hash))
            BridgeItem(id, BridgeRules.name(f.getString("name")), size, hash)
        }
        require(files.map { it.id }.distinct().size == files.size)
        return BridgeRemoteState(name, files, value.getBoolean("mirror"))
    }
    fun receive(item: BridgeItem, target: File) {
        require(BridgeRules.id(item.id))
        check(!target.exists()) { "Hedef zaten var" }
        require(target.parentFile!!.usableSpace > item.bytes + 16L * 1024 * 1024)
        var downloaded = false
        try { request("GET", "/v1/files/${item.id}", target = target, limit = BridgeRules.MAX_FILE); downloaded = true; BridgeRules.verify(target, item.bytes, item.sha256) }
        catch (error: Exception) { if(downloaded) target.delete(); throw error }
    }
    fun propose(item: BridgeItem): String {
        val reply = JSONObject(request("POST", "/v1/inbox", item.json()).toString(Charsets.UTF_8))
        return reply.getString("id").also { require(BridgeRules.id(it)) }
    }
    fun uploadStatus(id: String): String {
        require(BridgeRules.id(id))
        return JSONObject(request("GET", "/v1/inbox/$id").toString(Charsets.UTF_8)).getString("status")
    }
    fun upload(id: String, source: File): String {
        require(BridgeRules.id(id))
        return JSONObject(request("PUT", "/v1/inbox/$id", source = source).toString(Charsets.UTF_8)).getString("status")
    }
    fun frame(): ByteArray = request("GET", "/v1/frame", limit = BridgeRules.MAX_FRAME.toLong())
    fun disconnect() { try { if(bearer != null) request("POST", "/v1/bye") } finally { forget() } }
    fun forget() {
        closed = true; bearer = null; pending = null
        synchronized(active) { active.forEach { it.disconnect() }; active.clear() }
    }
}
