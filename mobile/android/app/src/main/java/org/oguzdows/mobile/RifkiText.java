package org.oguzdows.mobile;

import java.util.Locale;

/** Honest deterministic fallback, NOT an LLM. No side effects. */
final class RifkiText {
    static String reply(String input) {
        String q = input.substring(0, Math.min(2000, input.length())).toLowerCase(Locale.forLanguageTag("tr-TR")).replace('ı', 'i');
        if (q.contains("apk")) return "APK incelemesi özel kopyanın özetini ve paket bilgilerini gösterir. Bu, güven veya zararlı yazılım doğrulaması değildir. Kurulumu yalnız sistem yükleyicisi, kaynak izni ve son onayınla yapabilir.";
        if (q.contains("google") || q.contains("play")) return "Google web kısayollarını başlatıcıda bulabilirsin. Kurulu uygulamalar sistem listesinden açılır. Play Store/GMS lisans ve sertifika koşulludur; bunları dağıtmıyorum.";
        if (q.contains("not")) return "Başlatıcıdaki Defter notunu yalnız bu cihazın özel uygulama alanına, Kaydet düğmesine bastığında yazar. Şifreli kasa veya bulut eşitlemesi değildir.";
        if (q.contains("tema") || q.contains("koyu")) return "Başlatıcının Gece mavisi / Gün ışığı düğmesi yalnız kendi görünümünü değiştirir. Başka uygulamaların ayarına erişmem.";
        if (q.contains("pil") || q.contains("nazar")) return "Nazar boncuğu güç seçeneklerini açar ve gerçek pil düzeyini sistemden okur. Bu normal uygulama cihazı kapatamaz veya yeniden başlatamaz.";
        return "Bu, sınırlı ve kural tabanlı yerel rehberdir. Üretken model burada bağlı değil. Not, APK, Google, görünüm ve pil hakkında yardımcı olabilirim; bilmediğim yanıtı uydurmam. Ses veya ekran bağlamı okumam.";
    }
    private RifkiText() {}
}
