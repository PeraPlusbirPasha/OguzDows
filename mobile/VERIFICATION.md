# Mobil deneyim · gerçek doğrulama kaydı

Dört düzey ayrıdır: **tarayıcı**, **SDK/Java/lint**, **sanal radyo/sağlayıcı/yükleyici emülatörü**, **gerçek SIM/cihaz/ROM**. Bir düzeyin başarısı diğerine aktarılmaz. Bu kayıt, başarısız kabul koşularını da saklar; hazırlanmış test kodu geçmiş test sayılmaz.

## Son tam kontrol

| Kontrol                | Gözlenen sonuç                | Sınır                                                                       |
| ---------------------- | ----------------------------- | --------------------------------------------------------------------------- |
| `npm run build`        | Başarılı                      | TypeScript + Vite 6.4.6, 1594 modül                                         |
| `npm test`             | **31 geçti, 0 atlama**        | 13 temel mantık/kanıt + 8 günlük deneyim/varlık/durum + 10 API testi                    |
| `npm run test:native`  | **13 geçti, 0 atlama**         | Yalnız manifest/XML/izin/köprü/rol/depoya güven/simge/kaynak sözleşmeleri                |
| `npm run test:browser` | **31 senaryo geçti**          | 15 mevcut + 16 günlük deneyim; iki kapsayıcıyla Node raporu 33/33           |
| `npm run format:check` | Başarılı                      | TSX/MJS/CSS/config/test kaynakları                                          |
| `npm audit`            | **0 raporlanan açık**         | Bu lockfile ve sorgu anı; genel güvenlik sertifikası değil                  |
| Başlangıç JS           | **99247 gzip bayt**           | Hedef ≤112640 bayt (110 KiB), geçildi                                       |
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

## Tam native kabul: `023a89c`

[Başarılı koşu **46048445728**](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) / [iş **140673465222**](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728/job/140673465222), tam kaynak **`023a89c9f22bdcd27eabecf8437b05addcab03e9`**. SDK35 / Google APIs / x86_64 / Pixel6 QEMU. **10 instrumentation seçiminde 12/12 gerçek test**, 0 boş/atlanmış kabul; **6/6 Java**, lint **0 hata / 37 uyarı**. SDK, cihaz ve paket kaydı birbirinden ayrıdır:

- [SDK derleme kaydı](android/evidence/sdk-023a89c.json): APK boyutları/hash’leri, Java sonuçları ve lint uyarı sınıfları. `emulator_passed: null` yalnız SDK kaydının kapsamıdır, kabul başarısızlığı değil.
- [Emülatör kaydı](android/evidence/emulator-023a89c.json): tek tek geçen cihaz testleri, imaj fingerprint’i ve canlı kaynak kanıtı.
- [Paket kökeni](android/evidence/package-023a89c.json): başarılı paket/imza adımı, artifact ID/digest’i ve yerel indirme sınırı.

| Gerçek Android testi | Geçen vaka | Gözlenen kapsam / sınır |
| --- | ---: | --- |
| Paketlenmiş köprü ve yalıtım | 1 | Rol durumu/istek reddi, origin/main-frame ve alt çerçeve sınırı; soğuk `ACTION_DIAL` yalnız taslak oluşturur |
| Ücretli eylem onayı | 1 | Çağrı/SMS son yerel onayında iptal → çağrı ve sağlayıcıya giden SMS yok |
| Sistem denetimi ve tema | 1 | AudioManager medya sesi, uygulama pencere parlaklığı, native tema tercihi; fiziksel ses/ışık/pil ölçümü değil |
| Gelen SMS | 1 | Sanal modem PDU’su → korumalı alıcı → gerçek sağlayıcı → zengin gelen kutusu |
| Giden SMS | 1 | Önce `queued`, ardından gerçek sanal radyo sent callback’i ve sağlayıcı `SENT`; **operatör teslim raporu yok** |
| Giden çağrı | 1 | Telecom ve OğuzDows InCallService; gerçek `DIALING`/`CONNECTING`/`ACTIVE` durumlarından biri ve bitirme. Fiziksel karşı tarafla bağlantı kanıtı değil |
| Gelen çağrı | 1 | Sanal modem → `RINGING`, kendi UI’da yanıtla → `ACTIVE`, mikrofon sustur/aç ve bitir |
| APK iptal/kurulum | 1 | Özel kopya incelemesi, iptal, gerçek sistem yükleyicisi onayı, etkisiz fixture’ın yüklü sürüm/imzacı doğrulaması |
| Depo güvenliği | 3 | Ayrı anahtarlı imzalı/bozuk/imzasız JAR ve yanlış pin; SQLite seçim/rollback; izinsiz uç reddi |
| Canlı F-Droid | 1 | **5.057 uygulama / 5.016 API-ABI uygun paket**; Aegis code82, **6.869.856 bayt**, SHA-256 doğrulamalı indir/incele/**kurmadan iptal** |
| **Toplam** | **12** | Yalnız bu API35/QEMU kapsamı; tüm servis/uygulama/OEM kabulü değil |

Aegis inceleme hash’i: `0eecec45de0da3ff1358004b51e2960d9178551643a6ed44f6496ea9ec999c19`. Katalog sayıları koşu anının gözlemidir; uygun paket seçimi her uygulamanın çalışacağını garanti etmez. Canlı üçüncü taraf APK’sı kurulmadı; gerçek sistem kurulumu ayrı etkisiz fixture üzerindedir.

### Hazırlanan APK ve indirme

**[APK/test/rapor artifact’ı](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728/artifacts/15222979423)** · [kurulum ve hash kontrolü](INSTALL.md). Ana dosya: `OguzDows-Mobile-0.2.0-emulator-debug.apk`, **6.993.130 bayt**; SHA-256:

```text
175c471a87d9c6020d29a8a8cbca7a3903eb05e939c0c5fd32c26790917c2f04
```

Yalnız tam kabulden sonra paketleme adımı çalıştı; **`apksigner verify` başarılı**, APK/test/fixture, `APK-SIGNATURE.txt`, `SHA256SUMS`, `BUILD.txt` ve raporlar artifact’a yüklendi. Bu **debug/test dağıtımıdır**, üretim imzası veya mobil Release değil. Saklama süresi **14 gün**; tekrar üretim komutları [Android kılavuzunda](android/README.md).

**Yerel doğrulama sınırı:** `gh run download` GitHub’ın blob depolama alanına yönlenince sandbox ağ izinleri nedeniyle `EOF` verdi. APK baytları çalışma alanına alınamadı; burada bağımsız APK hash/imza doğrulaması veya artifact açma yapılmadı. Yukarıdaki hash ve boyut CI bildiriminden, artifact digest’i GitHub API’den alınmıştır. İndiren kullanıcı kendi kopyasını `SHA256SUMS` ile doğrulamalıdır. Ağ sınırını aşmak için APK/SDK/anahtar Git’e eklenmedi veya yeni bir Release açılmadı.

### Korunan başarısız koşular ve düzeltmeler

| Koşu / kaynak | Gözlenen sonuç | Paket |
| --- | --- | --- |
| [46044480983 / `384e905`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46044480983) | **5/12 geçti, başarısız**; beş JS callback hatası, kurulum düğmesi ve belirsiz canlı inceleme hatası | Hazırlanmadı; [kayıt](android/evidence/emulator-384e905.json) |
| [46046215253 / `be00308`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46046215253) | **10/12 geçti, başarısız**; dotless `ı` içeren çağrı düğmesi seçimi ve iki ayrı snapshot arasında çağrının kaldırılması yarışı | Hazırlanmadı; [kayıt](android/evidence/emulator-be00308.json) |
| [46047473237 / `a2eafe4`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46047473237) | **11/12 geçti, başarısız**; soğuk intent action/data’sını değiştirmek AndroidX ActivityScenario kapanış takibini bozdu | Hazırlanmadı; [kayıt](android/evidence/emulator-a2eafe4.json) |
| [46048445728 / `023a89c`](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) | **12/12 geçti**; tüm kapılar ve paketleme başarılı | Yukarıdaki debug artifact |

Test düzeltmeleri: odaklanmış/yüklenmiş WebView bekleme; navigasyon/yerel onay sırasında JS dönüşünü beklememe; ön planda JS sorgulama; Türkçe `iIıİ` düğme seçimi; çağrı durumunu tek snapshot üzerinden okuma; görünür Activity’den yükleyici başlatma; anlamlı canlı kaynak assertion’ları. Ürün düzeltmeleri: React dinleyicisi → `ui.ready` el sıkışmasıyla kaybolmayan soğuk başlangıç taslağı; intent action/data’sını değiştirmeden ayrı, kaydedilen tüketim durumu; eksik/geçersiz imzacı özetinde kurulum/başarı kapısını kapatma. İzin, ücretli onay veya 12 vaka kapısı gevşetilmedi.

İlk çalıştırıcı revizyonu kendi runtime bağımlılıklarını içermediği için emülatör başlamamıştı. Paketlenmiş **v2.34.0 / `1dcd0090116d15e7c562f8db72807de5e036a4ed`** ile gerçek emülatör çalıştı. Google APIs imajı, Play Store/GMS sertifikası veya fiziksel ürün desteği değildir.

Kabul sürücüsü yalnız tek `emulator-*` ve `ro.kernel.qemu=1` hedefinde çalışır; rol uygunluğunu atlamadan Telefon/SMS rollerini seçer, yalnız bu harcanabilir hedefte izin/kaynak ayarlarını yapar. Gerçek SIM/acil numara kullanılmaz. Rol/izin reddi ve geri alma matrisi bu olumlu koşuya dahil değildir. `test-results/mobile/build.json`, `emulator/evidence.json`, log/ekran/rapor dosyaları hata halinde de artifact’a alınır; kısa bildirimler GitHub checks API’den okunur. Kalıcı özetler Git’teki yukarıdaki JSON’lardır, büyük üretilmiş dosyalar değildir.

## API ve native kaynak sınırı

API testleri: kapalı varsayılan; HTTPS/sunucu-loopback uç kısıtı; gönderim başlığı/onayı ve rol/sayı/uzunluk doğrulaması; sunucuda sabit sistem promptu; model araçlarının olmaması; gövde/yanıt sınırı; anahtar/hata sızdırmama; IP hız sınırı; yabancı Origin reddi ve iki inference eşzamanlılık kapısı. Gerçek sağlayıcı, model kalitesi, veri saklama ve üretim oturum doğrulaması test edilmedi.

13 kaynak sözleşmesi; açık manifest izinleri/rol bileşenleri, origin/ana çerçeve/CSP, ücretli işlem onayı ve doğruluk, APK özel kopyası/yükleyici, depo güven kökü/imza/hash/rollback, yardımcı mikrofonunun kapalı kalması, gerçekten bağlı native Telefon/Mesaj rotaları, emülatör güvenlik kilitleri ve 24 vektörün path/lisans/hash eşleşmesini denetler. Bunlar **statik kaynak sözleşmeleridir**, çalışan cihaz kanıtı değildir. Gerçek SDK sonucu ve yalnız geçen emülatör adımları üstte ayrıca belirtilir.

AOSP yardımcı metadata’sının zorunlu `recognitionService` alanı kaynak incelemesiyle eklenmişti; tanıma iskeleti mikrofon açmadan hata döndürür. Üç yardımcı servisi `BIND_VOICE_INTERACTION` imza izniyle kısıtlıdır. İncelenen AOSP 15 kaynakları:

- [VoiceInteractionServiceInfo](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionServiceInfo.java)
- [VoiceInteractionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionService.java)
- [RecognitionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/speech/RecognitionService.java)

## Özellikle yapılmayanlar

- API35/QEMU kabulünün ötesinde fiziksel ürün/üretim dağıtım kabulü yoktur. AOSP/GSI/boot/vendor/ROM üretimi, unlock/flash/root yapılmadı; artifact yerel olarak indirilemedi.
- GMS/Play dağıtımı, lisans/sertifika, CTS/VTS, Play Integrity, banka veya DRM uygulaması testi.
- Fiziksel SIM/operatör/VoLTE/VoWiFi/acil çağrı, sistem rehberi/takvim erişimi, gerçek kamera/radyo/GPU/ses kalitesi veya pil ölçümü. Sanal gelen çağrı ve ses API testi fiziksel donanım kanıtı değildir.
- Canlı üretken model, mikrofon, ASR/hotword veya ekran bağlamı okuma.
- Gerçek pil ömrü/RAM/FPS/termal ölçümü veya tüm masaüstü özelliklerinin native tamamlandığı iddiası.
- Mevcut PC/Pi dosyaları, yayımlanmış imajlar veya PR/release işlemlerine müdahale.

Kapsam: [özellik eşlemesi](feature-parity.json) · [kaynak/lisans atıfları](ASSETS.md) · [çalıştırma ve tekrar üretim](README.md). Ekran görüntüleri çalışan web önizlemesidir, fiziksel telefon fotoğrafı veya ROM testi değildir.
