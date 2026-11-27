# Mobil deneyim · gerçek doğrulama kaydı

Dört düzey ayrıdır: **tarayıcı**, **SDK/Java/lint**, **sanal radyo/sağlayıcı/yükleyici emülatörü**, **gerçek SIM/cihaz/ROM**. Bir düzeyin başarısı diğerine aktarılmaz. Bu kayıt, başarısız kabul koşularını da saklar; hazırlanmış test kodu geçmiş test sayılmaz.

## Son tam kontrol

| Kontrol                | Gözlenen sonuç                | Sınır                                                                       |
| ---------------------- | ----------------------------- | --------------------------------------------------------------------------- |
| `npm run build`        | Başarılı                      | TypeScript + Vite 6.4.6, 1594 modül                                         |
| `npm test`             | **30 geçti, 0 atlama**        | 12 temel mantık + 8 günlük deneyim/varlık/durum + 10 API testi                    |
| `npm run test:native`  | **13 geçti, 0 atlama**         | Yalnız manifest/XML/izin/köprü/rol/depoya güven/simge/kaynak sözleşmeleri                |
| `npm run test:browser` | **31 senaryo geçti**          | 15 mevcut + 16 günlük deneyim; iki kapsayıcıyla Node raporu 33/33           |
| `npm run format:check` | Başarılı                      | TSX/MJS/CSS/config/test kaynakları                                          |
| `npm audit`            | **0 raporlanan açık**         | Bu lockfile ve sorgu anı; genel güvenlik sertifikası değil                  |
| Başlangıç JS           | **99241 gzip bayt**           | Hedef ≤112640 bayt (110 KiB), geçildi                                       |
| Günlük uygulamalar JS  | **12082 gzip bayt**            | Ayrı, dinamik yüklenen modül; yukarıdaki ilk paket değildir                 |
| CSS                    | **16460 gzip bayt**           | İki stil kaynağının üretim dosyası                                          |
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

## Native SDK ve ilk gerçek emülatör koşusu

| Kanıt | Gözlenen sonuç | Anlamı |
| --- | --- | --- |
| [SDK koşusu `7e7dad7`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46043838494) | Ana APK **6,992,378 bayt** + test APK’sı derlendi; **6/6 Java**, 0 atlama; lint **0 hata / 37 uyarı** | [API’den alınan SDK kaydı](android/evidence/sdk-7e7dad7.json); tek başına cihaz kabulü değil |
| [İlk sanal radyo koşusu `384e905`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46044480983) | **BAŞARISIZ: 5/12 test geçti**, 7 geçmedi | [Ham kısa emülatör kaydı](android/evidence/emulator-384e905.json); dağıtım paketi hazırlanmadı |
| Sistem sesi/parlaklık/tema | 1 gerçek emülatör testi geçti | AudioManager ve pencere özellikleri; pil ömrü/ekran ışık şiddeti ölçümü değil |
| Gelen sanal çağrı | 1 gerçek emülatör testi geçti | OğuzDows InCallService/UI’da yanıtla, mikrofon sustur/aç ve bitir; gerçek SIM/operatör değil |
| Depo güvenliği | **3 gerçek Android testi geçti** | Ayrı test anahtarlı JAR, yanlış pin/bozuk/imzasız ret; SQLite sürüm seçimi/rollback; izinsiz uç reddi |
| Kalan kabul | UI/JS hazır olma/ön plan ve sistem düğmesi seçici hataları düzeltme aşamasında | SMS gönderim/alım, giden çağrı, kurulum ve canlı inceleme bu başarısız koşuda geçti sayılmaz |

İlk emülatör çalıştırıcı commit’i, kendi runtime bağımlılıklarını içermeyen upstream geliştirme revizyonuydu; aynı adım 0 saniyede durdu. Yayınlanmış, bağımlılıkları içeren **v2.34.0 / `1dcd0090116d15e7c562f8db72807de5e036a4ed`** pin’iyle gerçek API35 Google APIs / x86_64 Pixel6 emülatörü başladı. Bu imaj Play Store/GMS sertifikası veya fiziksel ürün desteği değildir.

Kabul düzeneği 8 cihaz metodu + 3 depo güvenliği + 1 canlı depo testini, 10 instrumentation seçiminde **tam 12 test** olarak zorunlu tutar. Sıfır/eksik test başarı olamaz. Sürücü yalnız tek `emulator-*` ve `ro.kernel.qemu=1` hedefinde çalışır; rol uygunluğunu atlamadan Telefon/SMS rollerini seçer, yalnız sanal modem fixture’ları kullanır. Gerçek SIM/acil numara denenmez. Canlı test resmî pinned kataloğu ve Aegis APK’sını indirip inceler ve **kurmadan iptal eder**; ayrı etkisiz fixture APK, gerçek sistem yükleyicisi onayıyla kurulmalıdır. Bunlar test tasarımıdır; yalnız geçmiş adımlar yukarıda başarı olarak yazılır.

İş akışı yalnız bütün yerel testler geçince APK/test/fixture paketini, `APK-SIGNATURE.txt`, `SHA256SUMS` ve `BUILD.txt` kaynak SHA’sını hazırlar. Mevcut rapor/ekran/log dosyaları hata halinde de Actions artifact’ına alınır (**14 gün**). `test-results/mobile/build.json` SDK’yı, `emulator/evidence.json` cihazı ayrı kaydeder; kısa bildirimler GitHub checks API’den de okunur. APK’lar/SDK/özel test anahtarları Git’e eklenmez. Kaynak, şema veya lint uyarıları azaltılmadan üretim güvenlik/performans onayı iddia edilmez.

## API ve native kaynak sınırı

API testleri: kapalı varsayılan; HTTPS/sunucu-loopback uç kısıtı; gönderim başlığı/onayı ve rol/sayı/uzunluk doğrulaması; sunucuda sabit sistem promptu; model araçlarının olmaması; gövde/yanıt sınırı; anahtar/hata sızdırmama; IP hız sınırı; yabancı Origin reddi ve iki inference eşzamanlılık kapısı. Gerçek sağlayıcı, model kalitesi, veri saklama ve üretim oturum doğrulaması test edilmedi.

13 kaynak sözleşmesi; açık manifest izinleri/rol bileşenleri, origin/ana çerçeve/CSP, ücretli işlem onayı ve doğruluk, APK özel kopyası/yükleyici, depo güven kökü/imza/hash/rollback, yardımcı mikrofonunun kapalı kalması, gerçekten bağlı native Telefon/Mesaj rotaları, emülatör güvenlik kilitleri ve 24 vektörün path/lisans/hash eşleşmesini denetler. Bunlar **statik kaynak sözleşmeleridir**, çalışan cihaz kanıtı değildir. Gerçek SDK sonucu ve yalnız geçen emülatör adımları üstte ayrıca belirtilir.

AOSP yardımcı metadata’sının zorunlu `recognitionService` alanı kaynak incelemesiyle eklenmişti; tanıma iskeleti mikrofon açmadan hata döndürür. Üç yardımcı servisi `BIND_VOICE_INTERACTION` imza izniyle kısıtlıdır. İncelenen AOSP 15 kaynakları:

- [VoiceInteractionServiceInfo](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionServiceInfo.java)
- [VoiceInteractionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionService.java)
- [RecognitionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/speech/RecognitionService.java)

## Özellikle yapılmayanlar

- Tam emülatör kabulü ve doğrulanmış dağıtım APK’sı henüz yok; ilk koşu başarısızdır. AOSP/GSI/boot/vendor/ROM üretimi, unlock/flash/root yapılmadı.
- GMS/Play dağıtımı, lisans/sertifika, CTS/VTS, Play Integrity, banka veya DRM uygulaması testi.
- Fiziksel SIM/operatör/VoLTE/VoWiFi/acil çağrı, sistem rehberi/takvim erişimi, gerçek kamera/radyo/GPU/ses kalitesi veya pil ölçümü. Sanal gelen çağrı ve ses API testi fiziksel donanım kanıtı değildir.
- Canlı üretken model, mikrofon, ASR/hotword veya ekran bağlamı okuma.
- Gerçek pil ömrü/RAM/FPS/termal ölçümü veya tüm masaüstü özelliklerinin native tamamlandığı iddiası.
- Mevcut PC/Pi dosyaları, yayımlanmış imajlar veya PR/release işlemlerine müdahale.

Kapsam: [özellik eşlemesi](feature-parity.json) · [kaynak/lisans atıfları](ASSETS.md) · [çalıştırma ve tekrar üretim](README.md). Ekran görüntüleri çalışan web önizlemesidir, fiziksel telefon fotoğrafı veya ROM testi değildir.
