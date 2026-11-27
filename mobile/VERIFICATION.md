# Mobil deneyim · gerçek doğrulama kaydı

Bu kayıt **tarayıcıdaki çalışan arayüz ve kaynak sözleşmeleri** içindir. Native SDK derlemesi, emülatör, fiziksel telefon, ROM, Google sertifikası veya gerçek üretken model kanıtı değildir.

## Son tam kontrol

| Kontrol                | Gözlenen sonuç                | Sınır                                                                       |
| ---------------------- | ----------------------------- | --------------------------------------------------------------------------- |
| `npm run build`        | Başarılı                      | TypeScript + Vite 6.4.6, 1588 modül                                         |
| `npm test`             | **29 geçti, 0 atlama**        | 12 temel mantık + 7 günlük deneyim/varlık + 10 API testi                    |
| `npm run test:native`  | **9 geçti, 0 atlama**         | Yalnız manifest/XML/izin/path/rol/intent/kaynak sözleşmeleri                |
| `npm run test:browser` | **31 senaryo geçti**          | 15 mevcut + 16 günlük deneyim; iki kapsayıcıyla Node raporu 33/33           |
| `npm run format:check` | Başarılı                      | TSX/MJS/CSS/config/test kaynakları                                          |
| `npm audit`            | **0 raporlanan açık**         | Bu lockfile ve sorgu anı; genel güvenlik sertifikası değil                  |
| Başlangıç JS           | **95917 gzip bayt**           | Hedef ≤112640 bayt (110 KiB), geçildi                                       |
| Günlük uygulamalar JS  | **9724 gzip bayt**            | Ayrı, dinamik yüklenen modül; yukarıdaki ilk paket değildir                 |
| CSS                    | **16070 gzip bayt**           | İki stil kaynağının üretim dosyası                                          |
| Mağaza simgeleri       | **24 / 24 yerel SVG**         | Tarayıcıda her birinin gerçek yüklenmesi, manifest SHA-256/lisans kontrolü  |
| Önceki çalışma         | **633 dosyanın içeriği aynı** | Mobil işe başlamadan kaydedilen SHA-256 tabanı; PC/Pi yayını değiştirilmedi |

Ortam: Node 22.22.3, npm 10.9.8, Python 3.11.2, sabitlenen Sparticuz Chromium 133 / Playwright Core. Chromium bir test koşucusudur, telefon emülatörü değildir. Tarayıcının web güvenliği/CORS denetimi kapatılmadı; CI için `--no-sandbox` gerekir. NSS destek kitaplıkları yalnız test önbelleğine açılır.

## Günlük deneyimde geçen 16 senaryo

1. **20 uygulama girişi:** Türkçe ad/takma ad araması; `rehber` → Kişiler, `hesap makinesi` → çalışan Hesap.
2. **Üç gerçek ana sayfa:** yatay dokunma hareketi ve sayfa düğmeleri gerçekten sayfa/uygulama değiştirir.
3. **Rıfkı’nın açık eylemi:** Telefon/Mesajlar/denetim merkezi gibi sabit yollar ancak önerilen düğmeye basılınca açılır; mesaj/arama yapılmaz.
4. **Birleşik arama:** uygulamalar, araçlar, notun 5000. karakterinden sonraki Türkçe eşleşme, basit aritmetik, ayar ve mağaza sonucu; otomatik web/model gönderimi yok.
5. **Telefon:** tuş takımı, elle numara, sil, normalleştirilmiş `tel:` ve Mesajlar’a geçiş; geçersiz/servis kodunda arama bağlantısı yok. Çağrı bağlandığı iddia edilmez.
6. **Kişiler:** ekle, favori, yeniden yükle, Türkçe ara, numara çevir, mesaj taslağı aç; silme iptal/ikinci onay akışları.
7. **SMS taslağı:** alıcı ve Türkçe/özel karakterli metin yeniden yüklemede korunur; `sms:` gövdesi güvenli kodlanır, gönderildi sayılmaz.
8. **Hareketler:** üst kenardan dokunma ve fare sürüklemesi panel açar; yukarı tutamaç kapatır; uygulama içi normal kaydırma panel açmaz; yukarı ana ekran hareketi çekmece açar.
9. **Gerçek önizleme sesi:** seçilmiş WAV gerçek HTML audio öğesine yüklenir; panel sesi `.volume`, sessiz ayarı `.muted` değerini değiştirir. Parlaklık gerçek UI karartma katmanına uygulanır; tercihler yeniden yüklemede kalır. Bu sistem ses/pil/donanım ölçümü değildir.
10. **Mağaza:** 24 yerel marka görselinin hepsi yüklenir; sekiz kategori filtrelenir; F-Droid için hayalî Play bağlantısı sunulmaz.
11. **Takvim:** ay ileri/geri, seçili gün ve yerel plan ekle/yeniden yükle/sil.
12. **Saat:** kronometre başlangıcı ve sayaç son tarihi sayfalar arasında korunur; duraklat/iptal çalışır. Sistem alarmı veya bildirim testi değildir.
13. **Tarayıcı:** script/dosya/güvensiz URL reddi; güvenli HTTPS adresi veya açık dış arama bağlantısı; iframe/otomatik sorgu yok.
14. **Galeri:** seçilen gerçek PNG baytları açılır, aynı baytlar indirilir ve yalnız geçici önizleme kaldırılır; dosya yüklemesi yok.
15. **Dar ekran/erişilebilirlik:** 14 yeni rota 320×640’ta yatay taşmaz. 390×844’te Telefon, Mesajlar, Kişiler, Takvim, Mağaza, Arama ve denetim merkezi için Axe kritik/ciddi ihlal raporlamaz; kontrast kuralı açıktır.
16. **Azaltılmış hareket:** yeni sayfa/simge/panel/plak animasyonları hem sistem reduced-motion hem hafif profil tercihini izler.

Yeni senaryolarda yakalanmamış tarayıcı/React hatası veya üçüncü tarafa otomatik ağ isteği görülmedi. SMS/call bağlantıları **güvenli URI ve arayüz düzeyinde** sınanır; gerçek telefon işleyicisi, operatör veya mesaj teslimi test edilmedi. “Sesi dene” sentetik, yalnız kullanıcı tıklamasıyla kısa önizleme sesidir; fiziksel hoparlör/ses kalitesi ölçümü değildir.

## Korunan 15 önceki senaryo

Masaüstü laboratuvarı/başlangıçta harici istek olmaması; 390px tam ekran ana sayfa; nazar güç menüsü ve modal odak/Escape/kilit; ortak tema kalıcılığı; duvar kâğıdı kalıcılığı; görev/not kaydı; 16 Atölye girişi ve kod çalıştırmayan hesap; yerel Rıfkı ve onaylı eylem; **sahte taşıma** ile model gönderim izni/eski yerel konuşmanın taşınmaması; gerçek APK bayt hash’i/uzantı reddi; istek listesi/resmî kaynak/Google HTTPS bağlantıları; örnek okuma listesi/okundu/TXT; dar ekran/azaltılmış hareket/Ayarlar Axe; bozuk kaydın iptalde korunması ve yalnız açık sıfırlama; depolama reddinde açık uyarı ve çalışan oturum.

Axe sonuçları tüm temalarda, her OEM’de, gerçek ekran okuyucuda veya tam WCAG sertifikasyonu anlamına gelmez. Yeni panelde testte yakalanan düşük kontrast giderildi; metinleri yarı saydamlaştırmayan, transform odaklı panel animasyonu kullanıldı. Yeni durum alanları eski v1 kayıtlara veri silmeden varsayılan ekler; not/görevler korunur.

## API ve native kaynak sınırı

API testleri: kapalı varsayılan; HTTPS/sunucu-loopback uç kısıtı; gönderim başlığı/onayı ve rol/sayı/uzunluk doğrulaması; sunucuda sabit sistem promptu; model araçlarının olmaması; gövde/yanıt sınırı; anahtar/hata sızdırmama; IP hız sınırı; yabancı Origin reddi ve iki inference eşzamanlılık kapısı. Gerçek sağlayıcı, model kalitesi, veri saklama ve üretim oturum doğrulaması test edilmedi.

Native kontratlara normal numara doğrulama, `ACTION_DIAL`, `ACTION_SENDTO` / `smsto:`, sistem ses/Wi-Fi paneli ve günlük uygulama intent’leri eklendi. Doğrudan `ACTION_CALL`, `SmsManager` veya sistem ayarına yazma yok; yalnız mevcut `REQUEST_INSTALL_PACKAGES` özel izni istenir. Bu kod **SDK ile derlenmedi**; doğru intent metninin varlığı OEM’de çalışma kanıtı değildir.

AOSP yardımcı metadata’sının zorunlu `recognitionService` alanı kaynak incelemesiyle eklenmişti; tanıma iskeleti mikrofon açmadan hata döndürür. Üç yardımcı servisi `BIND_VOICE_INTERACTION` imza izniyle kısıtlıdır. İncelenen AOSP 15 kaynakları:

- [VoiceInteractionServiceInfo](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionServiceInfo.java)
- [VoiceInteractionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionService.java)
- [RecognitionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/speech/RecognitionService.java)

## Özellikle yapılmayanlar

- SDK/Gradle derlemesi, native APK çalıştırma/kurma; AOSP/GSI/boot/vendor/ROM üretimi, unlock/flash/root.
- GMS/Play dağıtımı, lisans/sertifika, CTS/VTS, Play Integrity, banka veya DRM uygulaması testi.
- Gerçek SIM/modem/arama/SMS/acil çağrı, sistem rehberi/bildirim/takvim erişimi, donanım kamera/radyo/GPU veya sistem ses kontrolü.
- Canlı üretken model, mikrofon, ASR/hotword veya ekran bağlamı okuma.
- Gerçek pil ömrü/RAM/FPS/termal ölçümü veya tüm masaüstü özelliklerinin native tamamlandığı iddiası.
- Mevcut PC/Pi dosyaları, yayımlanmış imajlar veya PR/release işlemlerine müdahale.

Kapsam: [özellik eşlemesi](feature-parity.json) · [kaynak/lisans atıfları](ASSETS.md) · [çalıştırma ve tekrar üretim](README.md). Ekran görüntüleri çalışan web önizlemesidir, fiziksel telefon fotoğrafı veya ROM testi değildir.
