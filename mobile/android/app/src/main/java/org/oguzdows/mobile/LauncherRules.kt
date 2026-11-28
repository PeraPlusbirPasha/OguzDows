package org.oguzdows.mobile

import java.text.Normalizer
import java.util.Locale

/** Pure, bounded launcher/character logic. No Android API, model, paid action or remote instruction. */
object LauncherRules {
    const val MAX_PINS = 16
    val destinations = listOf(
        ShellDestination("phone", "Telefon", "arama numara çevir", "phone", 0xFFD9ECDD),
        ShellDestination("messages", "Mesajlar", "sms mesaj yaz", "message", 0xFFF3E4C5),
        ShellDestination("contacts", "Kişiler", "rehber kişi", "contacts", 0xFFD9E8F4),
        ShellDestination("store", "Mağaza", "uygulama indir apk", "store", 0xFFD7EADD),
        ShellDestination("browser", "Tarayıcı", "internet web", "globe", 0xFFD5E4F3),
        ShellDestination("media", "Müzik", "medya mp3 ses", "music", 0xFFF4DDCE),
        ShellDestination("gallery", "Galeri", "resim fotoğraf", "image", 0xFFEEDCE6),
        ShellDestination("settings", "Ayarlar", "tema görünüm duvar kağıdı", "settings", 0xFFE0E5E5),
        ShellDestination("workbench", "Atölye", "araç hesap json", "tools", 0xFFF2DDC9),
        ShellDestination("notes", "Defter", "not yaz", "notes", 0xFFDFEBD6),
        ShellDestination("tasks", "Günüm", "görev yapılacak", "tasks", 0xFFE4DFF0),
        ShellDestination("calendar", "Takvim", "ajanda tarih", "calendar", 0xFFEEDDE4),
        ShellDestination("clock", "Saat", "kronometre sayaç zaman", "clock", 0xFFE2DFF0),
        ShellDestination("calculator", "Hesap", "hesap makinesi", "calculator", 0xFFECE5CF),
        ShellDestination("news", "Haber", "okuma haberler", "news", 0xFFDDE7ED),
        ShellDestination("culture", "Koleksiyon", "kültür duvar kağıdı", "image", 0xFFEDDCE1),
        ShellDestination("files", "Dosyalar", "belge hash dosya", "folder", 0xFFF1E3C7),
        ShellDestination("google", "Google", "gmail youtube haritalar", "globe", 0xFFE9EAE5),
        ShellDestination("monitor", "Cihazım", "pil sistem kaynak", "monitor", 0xFFE1DEF0),
        ShellDestination("rifki", "Rıfkı", "asistan yardımcı kedi", "rifki", 0xFFD9EADD),
    )
    val defaultPins = destinations.take(12).map { "internal:${it.id}" }
    fun normalize(value: String): String = Normalizer.normalize(
        value.take(2000).replace('ı', 'i').replace('İ', 'i').lowercase(Locale.ROOT), Normalizer.Form.NFD
    ).replace(Regex("\\p{M}+"), "")
    fun internalRoute(key: String): String? = key.removePrefix("internal:")
        .takeIf { key.startsWith("internal:") && destinations.any { d -> d.id == it } }
    fun validPin(key: String): Boolean = internalRoute(key) != null ||
        (key.length <= 300 && Regex("app:[0-9]{1,18}:[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+").matches(key))
    fun sanitizePins(values: List<String>): List<String> = values.filter(::validPin).distinct().take(MAX_PINS)
    fun pin(values: List<String>, key: String): List<String> = sanitizePins(values + key)
    fun move(values: List<String>, key: String, delta: Int): List<String> {
        val out = sanitizePins(values).toMutableList()
        val from = out.indexOf(key)
        if (from < 0 || delta !in -1..1) return out
        val to = (from + delta).coerceIn(0, out.lastIndex)
        if (to != from) { out.removeAt(from); out.add(to, key) }
        return out
    }
}

data class ShellDestination(val id: String, val label: String, val keywords: String, val glyph: String, val color: Long)

enum class ShellSuggestion { PHONE, MESSAGES, STORE, TOOLS, DARK, LIGHT, CONTROLS, APPS }
data class RifkiContext(val hour: Int, val battery: Int?, val charging: Boolean, val inCall: Boolean = false)
data class RifkiReaction(val mood: String, val line: String)
data class RifkiAnswer(val text: String, val suggestion: ShellSuggestion? = null, val label: String = "")

object RifkiBehavior {
    fun reaction(c: RifkiContext): RifkiReaction = when {
        c.inCall -> RifkiReaction("Ciddi", "Görüşmen var. Ben sessizce burada bekliyorum.")
        c.battery != null && c.battery in 0..15 && !c.charging -> RifkiReaction("Dikkatli", "Benim dokuz canım var; pilin o kadar cömert değil.")
        c.charging -> RifkiReaction("Keyifli", "Telefon besleniyor. Benim mama işi ne oldu?")
        c.hour in 0..6 || c.hour >= 23 -> RifkiReaction("Uykulu", "Bu saatte ben bile pencereden indim. Hâlâ buradayım.")
        else -> RifkiReaction("Meraklı", "Burası senin masaüstün. Ben de evin kedisiyim.")
    }
    fun answer(input: String): RifkiAnswer {
        val q = LauncherRules.normalize(input).trim()
        return when {
            q.isEmpty() -> RifkiAnswer("Bir şey söyle; kulaklar bende. Şimdilik yalnız yerel rehberim.")
            listOf("gonder", "mesaj", "sms").any(q::contains) -> RifkiAnswer("Mesajlar’ı açabilirim. Alıcı, metin ve son gönderim onayı sende; ben kendiliğimden SMS göndermem.", ShellSuggestion.MESSAGES, "Mesajlar’ı aç")
            listOf("telefon", "ara ", "arama").any(q::contains) -> RifkiAnswer("Tuş takımını açarım; numarayı ve arama onayını sen seçersin. Gizlice arama işi bana göre değil.", ShellSuggestion.PHONE, "Telefon’u aç")
            listOf("gece", "koyu", "karanlik").any(q::contains) -> RifkiAnswer("Gece mavisi yakışır. Hazırsan kendi ekranlarımızı koyulaştıralım.", ShellSuggestion.DARK, "Gece görünümüne geç")
            listOf("aydinlik", "acik tema").any(q::contains) -> RifkiAnswer("Perdeleri açalım. Yalnız OğuzDows’un kendi görünümü değişecek.", ShellSuggestion.LIGHT, "Aydınlık görünüme geç")
            listOf("ses", "parlaklik", "denetim", "pil").any(q::contains) -> RifkiAnswer("Ses gerçek medya kanalı, parlaklık kendi penceremiz. Anahtarları sana getireyim.", ShellSuggestion.CONTROLS, "Denetim merkezini aç")
            listOf("yukle", "magaza", "apk").any(q::contains) -> RifkiAnswer("Mağaza’ya bakalım. Kaynak imzası ve APK özeti denetlenir; son kurulum onayı sistemde ve sende.", ShellSuggestion.STORE, "İmzalı Mağaza’yı aç")
            listOf("uygulama", "cekmece").any(q::contains) -> RifkiAnswer("Gerçek kurulu uygulamalarını topladım. Kısayolu sabitlemek için yanındaki artıya dokun.", ShellSuggestion.APPS, "Uygulamaları göster")
            listOf("atolye", "arac", "hesap", "not").any(q::contains) -> RifkiAnswer("Alet çantası bende; işi seçmek sende. Atölye’yi açalım mı?", ShellSuggestion.TOOLS, "Atölye’yi aç")
            else -> RifkiAnswer("Şimdilik kural tabanlı yerel rehberim; bulut sohbeti, ses ve mikrofon bağlı değil. Tema, uygulamalar, Telefon, Mesajlar veya Mağaza için yardımcı olabilirim.")
        }
    }
}
