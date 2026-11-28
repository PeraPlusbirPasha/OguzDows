package org.oguzdows.mobile

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.spec.ECGenParameterSpec
import java.math.BigInteger
import java.util.Date
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import javax.net.ssl.X509KeyManager
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket
import javax.security.auth.x500.X500Principal

/** Bounded native TLS server. The certificate is pinned out of band, not trusted globally. */
class BridgeServer(@Suppress("UNUSED_PARAMETER") context: Context, private val host: BridgeHost) : AutoCloseable {
    private val alias = "oguzkopru-${BridgeRules.token(16)}"
    private val keys = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private val workers = Executors.newFixedThreadPool(4)
    private val slots = Semaphore(4)
    private val active = mutableSetOf<SSLSocket>()
    private var listener: SSLServerSocket? = null
    @Volatile private var closed = false
    @Volatile internal var lastTlsFailure: String? = null
        private set
    var pin: String = ""
        private set
    val port: Int get() = listener?.localPort ?: 0

    fun start() {
        check(listener == null && !closed)
        try {
            val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
            generator.initialize(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                // Conscrypt signs an already computed TLS digest with NONEwithECDSA.
                // DIGEST_NONE is required for an AndroidKeyStore TLS key (AOSP KeyGenParameterSpec).
                // This grants only this ephemeral signing key, never decryption/device credentials.
                .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
                .setCertificateSubject(X500Principal("CN=OguzDows local session"))
                .setCertificateSerialNumber(BigInteger(128, java.security.SecureRandom()).abs().add(BigInteger.ONE))
                .setCertificateNotBefore(Date(System.currentTimeMillis() - 60000))
                .setCertificateNotAfter(Date(System.currentTimeMillis() + 2L * 86400000)).build())
            generator.generateKeyPair()
            pin = BridgeRules.sha(keys.getCertificate(alias).encoded)
            // Select THIS session's key explicitly, even if a crash left another app-owned alias.
            val manager = object : X509KeyManager {
                override fun getClientAliases(keyType: String?, issuers: Array<out java.security.Principal>?) = null
                override fun chooseClientAlias(keyType: Array<out String>?, issuers: Array<out java.security.Principal>?, socket: java.net.Socket?) = null
                override fun getServerAliases(keyType: String?, issuers: Array<out java.security.Principal>?) = if(keyType == "EC") arrayOf(alias) else null
                override fun chooseServerAlias(keyType: String?, issuers: Array<out java.security.Principal>?, socket: java.net.Socket?) = if(keyType == "EC") alias else null
                override fun getCertificateChain(requested: String?) = if(requested == alias) arrayOf(keys.getCertificate(alias) as java.security.cert.X509Certificate) else null
                override fun getPrivateKey(requested: String?) = if(requested == alias) keys.getKey(alias, null) as java.security.PrivateKey else null
            }
            val tls = SSLContext.getInstance("TLS").apply { init(arrayOf(manager), null, null) }
            listener = (tls.serverSocketFactory.createServerSocket() as SSLServerSocket).apply {
                enabledProtocols = supportedProtocols.filter { it == "TLSv1.3" || it == "TLSv1.2" }.toTypedArray()
                soTimeout = 500
                bind(InetSocketAddress("0.0.0.0", 0), 4)
            }
            Thread(::accept, "oguzkopru-listen").apply { isDaemon = true; start() }
        } catch (error: Exception) { close(); throw error }
    }

    private fun accept() {
        while (!closed) {
            try {
                host.live()
                val socket = listener?.accept() as? SSLSocket ?: break
                if (!slots.tryAcquire()) { socket.close(); continue }
                synchronized(active) { active.add(socket) }
                try { workers.execute { handle(socket) } }
                catch (_: java.util.concurrent.RejectedExecutionException) {
                    synchronized(active) { active.remove(socket) }; socket.close(); slots.release()
                }
            } catch (_: SocketTimeoutException) { /* TTL is checked at most 500 ms later. */ }
            catch (_: BridgeDenied) { host.close(); break }
            catch (_: java.io.IOException) { if (!closed) host.close(); break }
        }
    }

    private fun line(input: BufferedInputStream): String {
        val bytes = ByteArrayOutputStream()
        while (bytes.size() <= 2048) {
            val b = input.read()
            if (b < 0) throw BridgeDenied(400)
            bytes.write(b)
            if (b == 10) {
                val value = bytes.toByteArray()
                if (value.size < 2 || value[value.size - 2] != 13.toByte() || value.any { it < 0 }) throw BridgeDenied(400)
                return value.toString(Charsets.US_ASCII).removeSuffix("\r\n")
            }
        }
        throw BridgeDenied(413)
    }

    private fun handle(socket: SSLSocket) {
        try {
            socket.soTimeout = 15000
            try { socket.startHandshake(); lastTlsFailure = null }
            catch (error: Exception) {
                // Only pre-HTTP provider diagnostics; never headers, invitation, bearer or file paths.
                lastTlsFailure = generateSequence(error as Throwable?) { it.cause }.take(4)
                    .joinToString(" <- ") { it.javaClass.simpleName + ": " + (it.message ?: "").take(180) }
                throw error
            }
            val input = BufferedInputStream(socket.inputStream, 65536)
            val request = line(input)
            val match = Regex("(GET|POST|PUT) (/v1/[A-Za-z0-9/-]+) HTTP/1\\.[01]").matchEntire(request) ?: throw BridgeDenied(400)
            val headers = linkedMapOf<String, String>()
            var count = request.length
            while (true) {
                val row = line(input); count += row.length + 2
                if (count > 8192) throw BridgeDenied(413)
                if (row.isEmpty()) break
                val split = row.indexOf(':')
                if (split < 1) throw BridgeDenied(400)
                val key = row.substring(0, split).lowercase(java.util.Locale.ROOT)
                if (!key.matches(Regex("[a-z0-9-]+")) || headers.containsKey(key)) throw BridgeDenied(400)
                headers[key] = row.substring(split + 1).trim()
            }
            val length = headers["content-length"] ?: "0"
            if (headers.containsKey("origin") || headers.containsKey("transfer-encoding") || !length.matches(Regex("[0-9]{1,10}"))) throw BridgeDenied(400)
            if (length.toLong() > BridgeRules.MAX_FILE) throw BridgeDenied(413)
            val reply = host.route(match.groupValues[1], match.groupValues[2], headers, input)
            val size = reply.file?.length() ?: reply.bytes.size.toLong()
            val output = socket.outputStream
            output.write(("HTTP/1.1 ${reply.status} Response\r\nContent-Type: ${reply.mime}\r\nContent-Length: $size\r\n" +
                "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n").toByteArray(Charsets.US_ASCII))
            if (reply.file != null) reply.file.inputStream().use { source ->
                val buffer = ByteArray(65536)
                while (true) {
                    host.ensureAuthorized(headers["authorization"] ?: "")
                    val n = source.read(buffer); if (n < 0) break
                    output.write(buffer, 0, n)
                }
            } else output.write(reply.bytes)
            output.flush()
        } catch (error: Exception) {
            val status = (error as? BridgeDenied)?.status ?: 400
            try { socket.outputStream.write("HTTP/1.1 $status Blocked\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII)) }
            catch (_: Exception) { /* No secret/path/body is written to logs. */ }
        } finally {
            synchronized(active) { active.remove(socket) }; try { socket.close() } catch (_: Exception) { }; slots.release()
        }
    }

    override fun close() {
        if (closed) return
        closed = true
        try { listener?.close() } catch (_: Exception) { }
        synchronized(active) { active.forEach { try { it.close() } catch (_: Exception) { } }; active.clear() }
        workers.shutdownNow()
        try { keys.deleteEntry(alias) } catch (_: Exception) { }
    }
}
