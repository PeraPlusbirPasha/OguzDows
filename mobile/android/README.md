# OğuzDows Mobile · yerel Telefon, SMS ve Mağaza

**Sürüm: `0.2.0-emulator` · normal, kullanıcı yetkili test APK’sı.** Zengin OğuzDows arayüzü APK içinde çevrimdışı paketlenir; Telefon/SMS, cihaz ayarları ve paket yükleme işlemleri dar bir yerel adaptöre bağlanır. Bu bir web sitesinden SIM’e uzaktan erişim değildir.

**Gözlenen kabul:** [`023a89c` koşusunda](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) **12/12 gerçek emülatör testi ve 6/6 Java testi geçti**; lint **0 hata / 37 uyarı**. Paketleme, `apksigner verify` ve artifact yüklemesi başarılıdır. [**APK’yı indir ve emülatöre kur**](../INSTALL.md) · [SDK kaydı](evidence/sdk-023a89c.json) · [Sanal radyo/kurulum kaydı](evidence/emulator-023a89c.json) · [Paket kökeni ve indirme sınırı](evidence/package-023a89c.json). İlk başarısız koşular silinmeden [doğrulama kaydında](../VERIFICATION.md) saklanır. Bu başarı, fiziksel operatör veya GMS testi değildir.

> APK, ROM/OTA/GSI/ISO değildir. Bootloader açma, flash veya root gerekmez. Fiziksel SIM/operatör, acil arama, MMS/RCS, GMS/Play Integrity/bankacılık/DRM ve her uygulamanın uyumluluğu doğrulanmış değildir. Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı bu deneysel paketle değiştirme.

## Gerçek platform yolları

### Telefon ve mesajlaşma

- **Telefon:** kullanıcının seçtiği `ROLE_DIALER`, `CALL_PHONE`, yerel alıcı/ücret onayı → `TelecomManager.placeCall`. Yanıtla/reddet/bitir, mikrofon, ses rotası, bekletme, DTMF ve hesap seçimi `InCallService` / `Call.Callback` durumlarına bağlıdır. İstek kabul edildi diye görüşme bağlandı denmez. Karşı taraf/operatörün desteklemediği yetenekler tamamlandı sayılmaz.
- **Acil arama:** platformun numara denetimi ve 112/911 için ayrı uyarı; yalnız ön yüklü sistem arayıcısını açma yolu. Otomatik acil çağrı yoktur ve testlerde acil numara kullanılmaz.
- **Düz SMS:** kullanıcı seçili `ROLE_SMS`, izinler, geçerli varsayılan abonelik ve ikinci yerel alıcı/metin/parça/ücret onayı → `SmsManager`. En çok 2000 karakter/30 parça; onaylar arasında 5 saniye; otomatik yeniden gönderme yoktur.
- **Doğru durum:** ilk cevap `queued`. Kalıcı parça günlüğü ve gerçek gönderim/teslim `PendingIntent` geri bildirimleri sistem SMS sağlayıcısını günceller. Teslim PDU’su gelmeden “teslim edildi” denmez; kısmi başarısızlık gizlenmez. Gelen SMS, korumalı `SMS_DELIVER` alıcısından sağlayıcıya yazılır. Arayüz en çok 50 sağlayıcı mesajını okur.
- Gelen intent/hızlı yanıt yalnız taslak oluşturur; rol/izin kararı veya yeniden yükleme mesajı/aramayı kendiliğinden başlatmaz. MMS bildirimi ayrıca sayılır; **MMS indirme/gönderme ve RCS uygulanmadı**. SMS rolü seçilmeden bu sınır açıkça gösterilir.

### Mağaza ve paketler

- **İmzalı canlı F-Droid:** birincil `https://f-droid.org/repo`, yalnız ağ hatasında resmî FAU aynası. İndirme açık kullanıcı onayından sonra başlar. Sabitlenmiş X.509 SHA-256: `43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab`; değişmez upstream kökeni [store-trust.json](store-trust.json).
- JAR tamamen okunup imza ve depo sertifikası doğrulanmadan JSON içe alınmaz. SQLite işlemi; geri alınmış/çok eski/gelecek zaman damgası, API/ABI/eski hedef API, `KnownVuln`, boyut ve hash sınırları. Başarısız eşitleme önceki doğrulanmış kataloğu silmez.
- Canlı arama en çok **80 eşleşme** gösterir. Güncelleme filtresi bu eşleşmelerde görünür yüklü sürümle karşılaştırır; tüm cihazı tarayan veya arka planda güncelleyen bir servis değildir. API/ABI uygunluğu çalışma garantisi değildir.
- Simgeler: gerçekten yüklüyse paket simgesi; 24 tanınan paket için lisanslı yerel marka vektörü; diğerleri için renkli harf simgesi. Harf, uygulamanın resmî simgesi gibi sunulmaz. Gizli simge CDN isteği yoktur; satırlar geri kullanılır, harf simgesi önbelleği 1.5 MiB ile sınırlıdır. [Vektör lisans/hash kaydı](native-icons.json).
- **APK inceleme:** SAF ile seçilen tek `.apk` veya imzalı katalogdan indirilen dosya → en çok **256 MiB özel kopya** → SHA-256/paket/sürüm/API/ABI/ilk 40 izin/ilk imzacı özeti → açık inceleme → FileProvider üzerinden aynı kopya → **sistemin son kurulum onayı**. Split APK/APKS/XAPK desteklenmez.
- Kaynak izni kapalıysa ayar açılır; dönüşte otomatik yükleme yoktur. Başarı için sistem `RESULT_OK` **ve** yüklü sürüm/ilk imzacı eşleşmesi gerekir. İmza/hash, malware taraması veya güvenilir geliştirici sertifikası değildir; tam imza/politika denetimini sistem yapar. Özel önbellekte en çok üç kopya, yeni incelemede 24 saatlik temizlik uygulanır.
- **Google Play ayrı kaynaktır:** mevcut lisanslı Play açılabilir; yoksa durum açıklanır. GMS/Play APK’leri paketlenmez veya sessizce kurulmaz. GNOME Software/Flatpak, APK çalışma zamanı veya GMS sağlamaz.

### Ana ekran, denetim ve Rıfkı

- 20 yerel arayüz girişi, üç kaydırılabilir ana sayfa, 16 Atölye aracı ve Haber/kültür sayfaları aynı paketlenmiş arayüzü kullanır. Gerçek yüklü/başlatılabilir uygulamalar ayrıca listelenir (en çok 250). Diğer uygulamaların özel verileri okunmaz; `QUERY_ALL_PACKAGES` yoktur.
- Medya sesi `AudioManager`, parlaklık yalnız uygulama penceresi, pil/saat sistemden. Wi-Fi/Bluetooth/uçak/DND gerçek sistem paneline gider; sahte açık/kapalı veya modem bağlantısı gösterilmez. Tema kendi web/yerel ekranlarına uygulanır, üçüncü taraf uygulamalar zorla değiştirilmez.
- Nazar güç simgesidir; normal uygulama cihazı kapatmış, yeniden başlatmış veya güvenlik kilidi koymuş gibi davranmaz. Fiziksel güç/kilit yolu ve pil ayarı kullanılır.
- Rıfkı yerel, kural tabanlı rehberdir. Kullanıcı isterse `ROLE_ASSISTANT` sistem seçimini açabilir. `VoiceInteractionService`/session/recognition bileşenleri sistem imza izniyle korunur. **Mikrofon/hotword/ekran bağlamı veya üretken model yoktur**; tanıma servisi dinlemeden kullanılamıyor cevabı verir. Yardımcı rolünün OEM uçtan uca testi ayrıca gereklidir.

## Güvenlik sınırı

Paketlenmiş origin: `https://appassets.androidplatform.net`. AndroidX `WebViewAssetLoader` ve ana çerçeve + tam origin bağlı `WebMessageListener`; uzak sayfa köprüye alınmaz. WebView uzak ağ isteklerini engeller; CSP, dosya erişimi ve izin kısıtları vardır. `addJavascriptInterface`, serbest shell/root/exec, genel dosya erişimi, mikrofon, sistem rehberi veya çağrı günlüğü izni yoktur. Sabit depoya ağ erişimi yalnız yerel istemcidedir.

SMS sistem sağlayıcısında, gönderim günlüğü uygulama özel alanında, arayüz not/kişileri WebView’in yerel alanındadır; bunlar **uygulama düzeyinde şifreli kasa değildir**. Sistem bildirimlerinin davranışı/rol geri alma/OEM farkları ayrıca sınanmalıdır. Otomatik veri gönderimi, analitik ve ücretli işlem tekrarı yoktur.

## Tekrar üretim

Node 22, **JDK 21** (uygulama kaynak/bytecode Java 17), Android SDK Platform/Build Tools 35.0.0. Gradle **8.9 wrapper ve dağıtım hash’i sabittir**. SDK/Google Maven erişimi ve kendi ortamındaki SDK lisansları gerekir. `ANDROID_HOME`/gerekirse Git dışı `local.properties` kullanın; anahtar ve SDK dosyalarını Git’e koymayın.

```sh
cd mobile/preview
npm ci
npm test
npm run test:native             # kaynak/manifest sözleşmeleri, cihaz testi değil
npm run build
cd ../android
./gradlew --no-daemon :fixture:assembleDebug
python3 ../scripts/generate-test-fixtures.py
./gradlew --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest :app:testDebugUnitTest :app:lintDebug
python3 ../scripts/report-build.py
```

Çıktılar `app/build/outputs/apk/{debug,androidTest/debug}/` altındadır. Derleme tek başına kabul testini geçirmiş dağıtım değildir. Fixture üreticisi yalnız test anahtarı üretir, imzalı/bozulmuş/imzasız indeks örnekleri ve etkisiz kurulum APK’sını test varlıklarına kopyalar, geçici özel anahtarı siler. Üretim F-Droid güven kökü değiştirilmez.

### Yalnız harcanabilir emülatörde test

Android Studio AVD Manager’da **API 35 / Google APIs / x86_64 / Pixel 6** oluşturup başlatın; bu **Play Store imajı değildir**. KVM gerekir; ARM ana bilgisayarda farklı imaj/konuk mimarisi ayrıca doğrulanmalıdır. Başka adb cihazlarını kapatın ve repo kökünden:

```sh
python3 mobile/scripts/emulator-smoke.py
```

Sürücü yalnız tek `emulator-*` ve `ro.kernel.qemu=1` hedefini kabul eder. APK/test APK’sını yükler, gerçek Telefon/SMS rollerini seçer, yalnız bu harcanabilir emülatörde izin/kaynak ayarını yapar, sanal GSM/SMS enjekte eder. **Rol uygunluğu atlanmaz.** 8 yerel cihaz + 3 depo güvenliği + 1 canlı depo testi; tam **12 gerçek test** zorunludur. Boş/atlanmış test sonucu başarı kabul edilmez. Canlı test gerçek imzalı kataloğu ve Aegis APK’sını indirip inceler ve **kurmadan iptal eder**; ayrıca etkisiz fixture sistem yükleyicisiyle kurulur.

[Test iş akışı](../../.github/workflows/mobile-emulator.yml), yalnız bu daldaki manuel/PR koşularında çalışır. Geçerse APK/test/fixture, `APK-SIGNATURE.txt`, `SHA256SUMS` ve kaynak SHA’sı paketlenir. Raporlar, kısa API’den okunabilir derleme/cihaz bildirimleri ve ekran görüntüleri `test-results/mobile/` içinde; Actions artifact saklama süresi **14 gündür**. Bu bir mobil Release yayını değildir. Farklı koşuların debug anahtarı değişebilir; mevcut kuruluma güncelleme garantisi yoktur.

## Sonraki kabul kapıları

API 29–34 ve OEM/gerçek SIM; rol/izin reddi ve geri alma; birden fazla SIM/çağrı, DTMF/ses rotaları/lock screen/bildirim; MMS/RCS; bozuk belge/işlem kesintisi/süreç ölümü; split/update/downgrade/signer zinciri; büyük font/ekran okuyucu; gerçek bellek/termal/pil ölçümleri. Yardımcı rolü ve üretken model de ayrı test kapısıdır. Tamamlanmayan 6 Atölye aracı, İmece/Heybe ve cihaz ROM’u [özellik eşlemesinde](../feature-parity.json) açık kalır. PC/Pi v1.2 ve mevcut yayınlar değiştirilmez.
