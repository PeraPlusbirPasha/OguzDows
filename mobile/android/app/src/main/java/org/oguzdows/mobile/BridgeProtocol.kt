package org.oguzdows.mobile

import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.security.SecureRandom

/** No contacts, SMS, input injection, shell or installer capabilities in the device-link protocol. */
object BridgeRules {
    const val MAX_FILE = 128L * 1024 * 1024
    const val BUDGET = 256L * 1024 * 1024
    const val MAX_ITEMS = 8
    const val TTL = 15 * 60 * 1000L
    const val MAX_FRAME = 512 * 1024
    fun token(bytes: Int = 32): String = ByteArray(bytes).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it.toInt() and 255) }
    fun sha(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
    fun hash(value: String) = value.matches(Regex("[a-f0-9]{64}"))
    fun id(value: String) = value.matches(Regex("[a-f0-9]{32}"))
    fun name(value: String): String {
        require(value.isNotBlank() && value.length <= 160 && value != "." && value != ".." && value.none { it=='/' || it=='\\' } && value.codePoints().noneMatch {
            Character.getType(it) in setOf(Character.CONTROL.toInt(), Character.FORMAT.toInt(), Character.SURROGATE.toInt(), Character.PRIVATE_USE.toInt(), Character.UNASSIGNED.toInt())
        }) { "Dosya adında yol/kontrol karakteri olamaz." }
        return value
    }
    fun localAddress(value: String): Boolean {
        val parts=value.split('.')
        if(parts.size!=4 || parts.any{it.isEmpty() || it.length>3 || it.any{c->c !in '0'..'9'} || (it.length>1 && it[0]=='0')})return false
        val n=parts.map{it.toIntOrNull() ?: return false}
        if(n.any{it !in 0..255})return false
        return n[0]==10 || n[0]==127 || (n[0]==172 && n[1] in 16..31) || (n[0]==192 && n[1]==168) || (n[0]==169 && n[1]==254)
    }
    fun copy(input: InputStream, output: OutputStream, limit: Long): Pair<Long,String> {
        val digest=MessageDigest.getInstance("SHA-256"); val buffer=ByteArray(65536);var count=0L
        while(true){val n=input.read(buffer);if(n<0)break;if(n==0)continue;count+=n;require(count<=limit){"Dosya boyut sınırı"};digest.update(buffer,0,n);output.write(buffer,0,n)}
        return count to digest.digest().joinToString(""){"%02x".format(it.toInt() and 255)}
    }
    fun verify(file:File,size:Long,hash:String) {
        require(size in 0..MAX_FILE && BridgeRules.hash(hash) && file.length()==size)
        val actual=file.inputStream().use { copy(it,object : OutputStream() { override fun write(value: Int) {}
            override fun write(bytes: ByteArray, offset: Int, length: Int) {} },MAX_FILE).second }
        require(MessageDigest.isEqual(actual.toByteArray(),hash.toByteArray())){"Dosya özeti eşleşmedi"}
    }
}
