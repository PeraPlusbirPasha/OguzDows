# OğuzDows 2.0 · Akıncı native Aero launcher

**`2.0.0-akinci` / versionCode20 tam emülatör kabulünü geçti:** [`5a44de0` / 46092350348](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348), **24/24 native / 15 seçim ve 20/20 JVM**, lint **0 hata / 47 uyarı / 1 bilgi**. Bağımsız dört-dosya TLS ve gerçek MediaProjection/iptal/taze izin/JPEG/durdurma, paket ve `apksigner` geçti. [**Kalıcı 2.0 APK ve kurulum**](../INSTALL.md) · [SDK](evidence/sdk-5a44de0.json) · [cihaz](evidence/emulator-5a44de0.json) · [kabul](evidence/acceptance-5a44de0.json) · [paket](evidence/package-5a44de0.json) · [PC/Pi/telefon bağlantısı](../../docs/AKINCI-BAGLANTI.md). Yayın taslağının imaj/yeniden indirme denetimi ayrı kapıdır. Fiziksel cihaz/SIM/GMS kabulü değildir.

**Önceki 0.4 kabulü tarihsel kalır:** [`7244164`](evidence/acceptance-7244164.json); eski APK/source/hash 2.0 diye yeniden etiketlenmez.

**Kotlin + Jetpack Compose ana ekranı.** MAIN/HOME/LAUNCHER artık `LauncherActivity`’dir; native ana ekran WebView değildir. Kabul edilmiş Java Telefon/SMS/Mağaza servisleri ve çevrimdışı paketli günlük araçlar korunur. Bu, normal kullanıcı yetkili uygulamadır; web sitesinden SIM’e uzaktan erişim değildir.

**Tarihsel 0.3 kabulü korunur:** [`fb6cad5` / 17 native ve 13 JVM](evidence/emulator-fb6cad5.json), [eski SDK](evidence/sdk-fb6cad5.json) ve [eski paket](evidence/package-fb6cad5.json). 0.2’nin [`023a89c` / 12-vaka kabulü](evidence/emulator-023a89c.json) de silinmez. Güncel 24-vaka kapısı, 0.3’ün 17 vakasını koruyup 4 bağlı kabuk ve 3 köprü vakası ekler; farklı koşuların başarıları toplanmaz.

> APK, ROM/OTA/GSI/ISO değildir. Bootloader açma, flash veya root gerekmez. Fiziksel SIM/operatör, acil arama, MMS/RCS, GMS/Play Integrity/bankacılık/DRM ve her uygulamanın uyumluluğu doğrulanmış değildir. Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı bu deneysel paketle değiştirme.

## Gerçek platform yolları

### 0.4 bağlı kabuk

Altı gerçek masaüstü profil kimliği mobil ızgara/raf/dock ailelerine uyarlanır; PC pencere yöneticilerini çalıştırmaz. Tam ekran kontrol/çekmece yüzeyleri, kendi penceresinde immersive görünüm ve gerçek sistem Ayarları bağlantıları vardır. Duvar kâğıdı vurgu rengi native/Java/paketli modüllere uygulanır; üçüncü taraf uygulamalar zorlanmaz.

Kişiler artık gerçek sistem sağlayıcısından, ayrı READ/WRITE izinleriyle okunur/eklenir. En çok 1000 satır taranır, yeni yerel kayıt son onaydan sonra eklenir, mevcut kişi silinmez/değiştirilmez. Telefon/SMS seçimi yalnız taslak hazırlar. Nazarın açtığı markalı kilit yüzeyi sistem PIN/biometrik kilidinin yerine geçmez.

OğuzKöprü: native SAF/drag-drop ve Python/GTK PC/ARM eşleri, yerel IPv4, davette sabitlenmiş TLS, iki ekranda kod karşılaştırma ve alıcı dosya onayı. 15 dakika, 2 eş, 8 öğe/kuyruk, 128 MiB/dosya ve 256 MiB/kuyruk. Gerçek MediaProjection her başlangıçta sistem izni/foreground bildirim/durdurma gerektirir; salt görüntü, ses/uzaktan dokunma yoktur. PC/ARM X11 yakalaması gerçek açık/kilitsiz oturum doğrulamasında açılır; bilinmeyen durum/Wayland reddedilir. Oturum özel kopyaları kapanışta temizlenir; cihazlar birbirinin rehber/SMS/kurulum yetkisini alamaz. Ayrıntılı protokol ve sınırlar [CONNECTED.md](../CONNECTED.md) içindedir.

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
- İncelemede **Vazgeç** veya görünür diyalogda **sistem Geri**, `RESULT_CANCELED` ile incelemeyi bitirip çağırana döner; ikinci Geri gerektirmez. Üç zorunlu iptal/örnek yıkımı/özgün HomeActivity odağı/kurulmama ve ardından tek gerçek son kurulum aynı koşuda geçti. Yalnız sade inceleme Activity’si yazılım çizimidir; HOME/Compose/WebView hızlandırması korunur.
- Kaynak izni kapalıysa ayar açılır; dönüşte otomatik yükleme yoktur. Başarı için sistem `RESULT_OK` **ve** yüklü sürüm/ilk imzacı eşleşmesi gerekir. İmza/hash, malware taraması veya güvenilir geliştirici sertifikası değildir; tam imza/politika denetimini sistem yapar. Özel önbellekte en çok üç kopya, yeni incelemede 24 saatlik temizlik uygulanır.
- **Google Play ayrı kaynaktır:** mevcut lisanslı Play açılabilir; yoksa durum açıklanır. GMS/Play APK’leri paketlenmez veya sessizce kurulmaz. GNOME Software/Flatpak, APK çalışma zamanı veya GMS sağlamaz.

### Ana ekran, denetim ve Rıfkı

- **Gerçek native HOME:** `LauncherActivity` → `NativeLauncherScreen`; saat, nazar kimliği, arama, sabit dock, iki kısayol sayfası + ayrı widget alanı. Ayarlar, Koleksiyon ve gerçek sistem anlık görüntülü Cihazım ayrı native panellerdir. Telefon/diğer günlük araçlar `HomeActivity` modül konağına; Mağaza doğrudan mevcut native ekrana gider. Modüllerin ana ekran düğmesi ve launcher’dan açılan modülde sistem Geri, web ana ekranı yerine native HOME’a döner.
- **Gerçek kurulu uygulamalar:** `LauncherApps` / `UserManager` ile erişilebilir profillerdeki başlatılabilir aktiviteler; kullanıcı seri numarası + component anahtarı, Türkçe arama/filtre, gerçek badged simge, `startMainActivity` ve sistem uygulama bilgisi. Liste en çok 1000 giriş, simge LRU’su 3 MiB; ikon çözme/sıralama arka planda, görünürken paket callback’i. Özel uygulama verileri okunmaz; `QUERY_ALL_PACKAGES` yoktur. Eski bağımsız yüklü uygulamalar ekranının 250 sınırı bu çekmece değildir.
- **Kalıcı düzen:** varsayılan 12, en çok 16 kısayol; + ile sabitle, basılı tut/düzenle ile öne/sona taşı veya sabitlemeyi kaldır. İki sayfa, 4 duvar kâğıdı, hafif görünüm, Rıfkı tarafı ve widget ID’leri özel tercihlerde. Seri IO yazımı; bozuk kısayol kaydı sessizce ezilmez, açık onayla yalnız kısayollar sıfırlanır. Serbest piksel sürükleme veya sınırsız masaüstü yoktur.
- **Gerçek AppWidgetHost:** yalnız cihazdaki sağlayıcıyı ara/seç → platform bağlama izni → gerekiyorsa sağlayıcının yapılandırma aktivitesi → bağlanmış ID kaydı → gerçek RemoteViews. En çok iki sabit boyutlu alan; kaldırma gerçek host ID’sini siler. Dinleme yalnız görünür yaşam döngüsünde. İptal/yapılandırma yolları vardır; tüm sağlayıcı/iş profili/yeniden boyutlandırma matrisi kabul edilmiş sayılmaz.
- 20 OğuzDows girişi, 16 Atölye aracı ve Haber gibi günlük modüller korunur; hepsinin Compose’a taşındığı iddia edilmez. Native kabuk, bu modüllerin origin sınırını veya ücretli işlem onaylarını gevşetmez.
- Medya sesi `AudioManager`, parlaklık yalnız uygulama penceresi, pil/saat sistemden. Wi-Fi/Bluetooth/uçak/DND gerçek sistem paneline gider; sahte açık/kapalı veya modem bağlantısı gösterilmez. Tema kendi web/yerel ekranlarına uygulanır, üçüncü taraf uygulamalar zorla değiştirilmez.
- Nazar güç simgesidir; normal uygulama cihazı kapatmış, yeniden başlatmış veya güvenlik kilidi koymuş gibi davranmaz. Fiziksel güç/kilit yolu ve pil ayarı kullanılır.
- Rıfkı yerel, kural tabanlı rehberdir: pil/şarj/saat/görüşmeye göre bağlam, sevme/baş eğme ve sağ/sol konum etkileşimi, yalnız dokunularak uygulanabilen tipli öneriler. Sonsuz animasyon veya her koşulda yaşayan/sesli AI değildir. Kullanıcı isterse `ROLE_ASSISTANT` sistem seçimini açabilir. `VoiceInteractionService`/session/recognition bileşenleri sistem imza izniyle korunur. **Mikrofon/hotword/ekran bağlamı veya üretken model yoktur**; tanıma servisi dinlemeden kullanılamıyor cevabı verir. Yardımcı rolünün OEM uçtan uca testi ayrıca gereklidir.

## Güvenlik sınırı

Paketlenmiş origin: `https://appassets.androidplatform.net`. AndroidX `WebViewAssetLoader` ve ana çerçeve + tam origin bağlı `WebMessageListener`; uzak sayfa köprüye alınmaz. WebView uzak ağ isteklerini engeller; CSP, dosya erişimi ve izin kısıtları vardır. `addJavascriptInterface`, serbest shell/root/exec, genel dosya erişimi, mikrofon veya çağrı günlüğü izni yoktur. Rehber okuma/yazma ayrı native izin/onay yollarıdır. Ağ yalnız native imzalı depo istemcisi ve açıkça eşleşmiş kısa ömürlü yerel TLS oturumundadır; WebView uzak ağ açamaz.

SMS ve gerçek rehber sistem sağlayıcısında, gönderim günlüğü uygulama özel alanında, notlar ve yalnız web laboratuvarının elle oluşturulmuş kişileri WebView’in yerel alanındadır. Sistem rehberi alıcı listesi bellektedir; bunlar **uygulama düzeyinde şifreli kasa değildir**. Sistem bildirimlerinin davranışı/rol geri alma/OEM farkları ayrıca sınanmalıdır. Otomatik veri gönderimi, analitik ve ücretli işlem tekrarı yoktur.

## Tekrar üretim

Node 22, **JDK 21** (uygulama kaynak/bytecode Java/Kotlin 17), Android SDK Platform/Build Tools 35.0.0. AGP 8.7.3, Kotlin/Compose derleyicisi 2.0.21, Compose BOM 2024.12.01, lifecycle 2.8.7; Gradle **8.9 wrapper ve dağıtım hash’i sabittir**. SDK/Google Maven erişimi ve kendi ortamındaki SDK lisansları gerekir. `ANDROID_HOME`/gerekirse Git dışı `local.properties` kullanın; anahtar ve SDK dosyalarını Git’e koymayın.

```sh
cd mobile/preview
npm ci
npm test
npm run test:native             # kaynak/manifest sözleşmeleri, cihaz testi değil
npm run build
python3 ../scripts/sync-shell-assets.py  # mevcut 4 görseli birebir kopyala; indirme yok
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
python3 mobile/scripts/acceptance.py  # 20 JVM / 24 native / bağımsız hash’ler / gerçek JPEG / ANR kapısı
python3 mobile/scripts/package-mobile.py  # yalnız tam kabulden sonra APK / web / sürüm / imza makbuzu
```

Sürücü yalnız tek `emulator-*` ve `ro.kernel.qemu=1` hedefini kabul eder. APK/test APK’sını yükler, gerçek HOME/Telefon/SMS rollerini seçer, yalnız bu harcanabilir emülatörde izin/kaynak ayarını yapar, sanal GSM/SMS enjekte eder. **Rol uygunluğu atlanmaz.** 8 Telefon/SMS/köprü/yükleyici + 5 launcher + 4 bağlı kabuk/rehber/kilit + 3 TLS/çift yönlü aktarım/gerçek MediaProjection + 3 depo güvenliği + 1 canlı depo testi: 15 seçimde tam **24 gerçek vaka** zorunludur. Launcher kabulü: gerçek HOME/inventory/Koleksiyon/Cihazım, kurulu fixture’ı arama/başlatma/HOME, kısayol taşıma/yeni ViewModel’de disk/bozuk kayıt, gerçek ses/ortak Phone rengi/Rıfkı, gerçek widget bağlama/RemoteViews/host yeniden yaratma/kaldırma. Embed AndroidView’da sahte Compose etiketi yerine sağlayıcının gerçek RemoteViews içeriği okunur. Boş/atlanmış test sonucu başarı kabul edilmez. Canlı test gerçek imzalı kataloğu ve Aegis APK’sını indirip inceler ve **kurmadan iptal eder**; ayrıca etkisiz fixture sistem yükleyicisiyle kurulur.

Headless CI, 4–6 GB ürün hedefinin alt sınırında **4 GiB AVD / 256 MiB uygulama heap’i**, SwiftShader/GL ve kapalı Vulkan kullanır; fiziksel GPU/pil/RAM performans testi değildir. Kotlin derleyicisi derleme JVM’inde çalışır; AVD yanında ikinci 2 GiB daemon bırakılmaz. Sanal SIM’in tam `READY`/`LOADED` değeri beklenir; `NOT_READY` kabul edilmez, hat uydurulmaz veya mesaj onayı atlanmaz.

**Açık performans sınırı:** kabul edilen 5a44de0 koşusunda ürün ANR/çökmesi yok, fakat **2205 ms HWUI `nSetStopped` beklemesi** var. Aynı kaynaklı manuel 46092349811 launcher otomasyonunda stale/menü hatalarıyla reddedildi; kalıcı kararlılık veya eski ANR’ın giderildiği iddia edilmez. Yeni 234×519 native thumbnail altı eksiksiz checks parçasından yerelde doğrulandı; APK/tam JPEG burada bağımsız hash’lenmedi. [Güncel ve tarihsel sonuçlar](../VERIFICATION.md).

[46065058564](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46065058564) koşusu, **ürün APK’sı kurulmadan önce** emülatörün stok **Pixel Launcher**’ında ANR penceresini yakaladı; sıfır ürün testiyle başarısız olarak korunur. Yalnız bu tanınmış stok uygulama penceresi, yalnız QEMU hazırlığında gerçek “Close app” düğmesinden kapatılabilir; paket varlığı doğrulanan stok launcher durdurulur ve ürün gerçek HOME rolünü alır. Yapılırsa `stock_boot_recovery` kanıtına yazılır. OğuzDows veya başka bir ANR bu istisnaya girmez; gerçek DropBox/main-thread/UI kimliği kaydedilir, eksik kabul başarısızdır ve paketlenmez. Bu hazırlık APK kodunda yoktur, fiziksel telefonlarda çalıştırılmaz. Başarılı `fb6cad5` koşusunda bu kurtarma istisnası kullanılmadı (`stock_boot_recovery` kaydı yok).

[Test iş akışı](../../.github/workflows/mobile-emulator.yml), yalnız bu daldaki manuel/PR koşularında çalışır. Geçerse APK/test/fixture, `APK-SIGNATURE.txt`, `SHA256SUMS` ve kaynak SHA’sı paketlenir. Hiçbir ürün ANR’ı kapatılıp başarıya çevrilmez; eksik kabulde dağıtım paketi oluşmaz. Raporlar, kısa API’den okunabilir derleme/cihaz bildirimleri ve ekran görüntüleri `test-results/mobile/` içinde; Actions artifact saklama süresi **14 gündür**. 2.0’ın kalıcı birleşik Release dosyaları bu geçici artifact’tan ayrıdır; yalnız tam kabul edilen kaynak seçilir. Farklı koşuların debug anahtarı değişebilir; mevcut kuruluma güncelleme garantisi yoktur.

## Sonraki kabul kapıları

API 29–34 ve OEM/gerçek SIM; rol/izin reddi ve geri alma; birden fazla SIM/çağrı, DTMF/ses rotaları/lock screen/bildirim; MMS/RCS; bozuk belge/işlem kesintisi/süreç ölümü; split/update/downgrade/signer zinciri; büyük font/ekran okuyucu; gerçek bellek/termal/pil ölçümleri. Yardımcı rolü ve üretken model de ayrı test kapısıdır. Tamamlanmayan 6 Atölye aracı, İmece/Heybe ve cihaz ROM’u [özellik eşlemesinde](../feature-parity.json) açık kalır. Eski PC/Pi v1.x yayınları değiştirilmez; yeni 2.0 imajları ayrı kaynak kimliğiyle yeniden derlenir.
