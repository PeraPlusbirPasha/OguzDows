# OğuzDows 0.4 · Bağlı kabuk (geliştirme dalı)

**Durum:** 0.4 geliştirme dalıdır, henüz kabul edilmiş mobil paket değildir.
İlk native derleme/20 JVM testi geçti; genişletilmiş cihaz kabulü arayüz/TLS
hataları buldu ve paketleme durdu. Düzeltmeler yeniden emülatörde sınanıyor.
Bu belge fiziksel cihaz/ARM kabulü anlamına gelmez. Önceden kabul edilmiş
0.3 APK bağlantısı [INSTALL.md](INSTALL.md) içindedir.

## Eklenen yollar

- Masaüstündeki aynı altı profil kimliği: OğuzDows, Plasma, GNOME/Ubuntu, Xfce,
  Windows 11 esintisi, macOS iskelesi. Dokunmatik ızgara/raf/dock geometrisi ve
  kalıcı seçim; bu sistemleri çalıştırma veya tüm PC pencere yöneticisini taşıma değildir.
- Ana ekran içinden aşağı/yukarı hareketle tam ekran kontrol/uygulama yüzeyleri.
  Gerçek medya sesi, pencere parlaklığı, sistem Ayarları ve doğrudan ekran,
  bildirim, varsayılan uygulama, güvenlik bağlantıları.
- Duvar kâğıdına bağlı native/Java/web vurgu renkleri ve kapatılabilir hafif cam.
  Sürekli canlı arkaplan blur'u yok; hafif görünüm camı sadeleştirir.
- Gerçek sistem rehberi: izinli okuma, sağlayıcı değişikliğine canlı tepki, yeni
  yerel kişi kaydı için ayrı izin ve son kayıt onayı. Telefon/SMS alıcıları sistem
  rehberinden bellekte okunur; eski tasarım laboratuvarının yerel kişi listesi
  native rehber sayılmaz. Buluta rehber gönderilmez veya yeni eşitleme hesabı açılmaz.
- Nazar ile OğuzDows kilit/karşılama yüzeyi. **Güvenli PIN/parmak izi kilidinin
  yerine geçmez, kendi PIN'ini toplamaz, ekranı cihaz genelinde kilitlemez.** Fiziksel
  güç tuşu sonrası sistemin kilidi geçerlidir. Gerçek kimlik doğrulamayı sistem yapar.

## OğuzKöprü/1 · PC, telefon, ARM

PC/ARM'da `oguzdows-bridge` veya uygulama menüsündeki **OğuzKöprü**, telefonda
**Dosyalar / OğuzKöprü** açılır. Güncel dalın PC kaynakları gerekir; yayımlanmış
eski v1.2 imajına bu kodun kendiliğinden gelmiş olduğu iddia edilmez. PC için
Python 3, GTK 3/GI, OpenSSL ve iproute2 ortak paket listesine dahildir.

1. Aynı Wi-Fi/Ethernet ağında bir cihazda **Masa aç** seç.
2. Yerel IPv4 arayüzünü seçip iki dakikalık daveti güvenilir özel kanaldan diğer
   cihaza aktar. Otomatik keşif, hesap, internet rölesi ve genel URL işleyicisi yok.
3. Diğer cihazda daveti yapıştır. **Her iki ekranda sekiz haneli kodu karşılaştır**;
   masa sahibi izin verir, istemci de kodun aynı olduğunu onaylar. İsim tek başına
   kimlik kanıtı değildir.
4. Sistemden seçilmiş dosyayı/yerel belgeyi masaya bırak. Telefon kartları basılı
   tutularak masaya/cihaza sürüklenebilir; aynı iş için erişilebilir düğmeler de vardır.
   Masaya konan dosya bu oturumun **tüm onaylı cihazlarına** görünür. İstemciden
   gönderim için alıcının **dosya bazında Kabul** seçimi ayrıca gerekir.
5. Alınan dosyanın gerçek SHA-256 özeti kontrol edilir. Kalıcı yeri sistem seçicisiyle
   seç; hiçbir dosya otomatik açılmaz, arşivden çıkarılmaz veya APK olarak kurulmaz.

### Ekran yansıtma

- **Telefon → PC/ARM/telefon:** Masa sahibi onaylı cihaz için ekran paylaşımını
  seçer. Her başlangıçta telefonun gerçek MediaProjection seçim/onay ekranı açılır;
  bir uygulama/tüm ekran seçimini sistem sunar. Durdurma bildirimi ve foreground
  service kullanılır. Ses, mikrofon ve uzaktan dokunma/klavye aktarılmaz. Bildirim
  izni paylaşımın kullanılacağı anda istenir. Kilitlenince, izin/cihaz erişimi geri
  alınınca veya durdurulunca biter. Güvenli/DRM pencereleri siyah kalabilir;
  OğuzKöprü'nün davet penceresi de güvenli tutulur.
- **PC/ARM → telefon/PC/ARM:** Yalnız açıkça onaylanan X11 masaüstü, her kareden
  önce sistemin `Active=yes`, `LockedHint=no` doğrulamasıyla. Durum bilinmiyorsa
  veya Wayland ise yayın açılmaz. Tam Wayland portalı bu sürümde uygulanmış değildir.
- Salt görüntü: telefondan en çok 2 kare/sn, PC'den en çok 1 kare/sn; uzun kenar
  1280 px, kare 512 KiB sınırı. Oyun/videosu akıcılığı veya Huawei ürünüyle protokol
  uyumluluğu iddia edilmez. Eski kare bağlantı yokken canlıymış gibi gösterilmez.

### İzinler ve sınırlar

- Üçüncü taraf APK, sistem bildirim perdesini veya güvenli keyguard'ı cihaz genelinde
  devre dışı bırakamaz. Kendi penceresi immersive olabilir; güvenli sistem kenarı
  ve acil/sistem çıkışları korunur. Gerçek değiştirme cihaz/ROM/SystemUI çalışmasıdır;
  donanım ve bootloader hâlâ belirlenmemiştir.
- Rehber izinleri, ekran izni, Phone/SMS rolleri ve ücretli işlem son onayı birbirinden
  ayrıdır. Sistem, açıkça seçilen bir role bazı izinleri kendisi verebilir; uygulama
  izinleri sessizce zorlamaz. Mikrofon, tüm dosyalar, Accessibility, overlay,
  device-admin, root, WRITE_SECURE_SETTINGS veya uzaktan SMS yetkisi eklenmez.
- Oturum 15 dakika, en çok 2 onaylı cihaz; kuyruk başına 8 dosya/256 MiB,
  dosya başına 128 MiB. Native hazırlama ve paylaşım özel kopyaları ayrı sınırlı
  kuyruklardır. Hiçbir dosya yolu karşı cihazın isteğiyle yerel diske çevrilmez.
- TLS sertifikası davetteki SHA-256 parmak izine **her bağlantıda, sır/dosya
  gönderilmeden önce** sabitlenir. Kimlik/bearer yalnız bellektedir. 4 TLS işçisi,
  15 sn soket zaman aşımı, boyut/başlık/deneme kotaları ve anında yerel erişim kesme
  vardır. Bağımsız güvenlik denetimi yapılmış sayılmaz; yalnız güvenilir yerel ağda dene.
- Telefon yüzeyinden çıkışta oturum kapanır; yalnız sistemden onaylı ekran paylaşımı
  bildirimle sürebilir. Sistem seçicisi için en çok 60 saniyelik istisna vardır.
  Normal kapanış özel geçici kopyaları siler; bir süreç çökmesinden kalan telefon
  kopyaları bir sonraki OğuzKöprü açılışında temizlenir. Kullanıcının ayrıca kaydettiği
  dosyalar silinmez. PC süreç çökmesi sonrası özel geçici dizin temizliği OS'nin
  geçici dosya politikasına kalabilir.

## Doğrulama kapısı

Mevcut 17 emülatör vakası korunur; 4 bağlı kabuk/rehber/kilit, 3 TLS/çift yönlü
Python–native protokolü/gerçek ekran izni vakası eklenir: **hedef 24 vaka / 15 seçim**.
Python protokol testleri gerçek loopback TLS soketleri kullanır, cihaz testi değildir.
Emülatör, CPU tabanlı SwiftShader'da aynı yaklaşık 411dp arayüzü 720×1600/280dpi ile
çizer; fiziksel GPU/RAM/pil/gerçek SIM/ARM performansı kanıtı değildir.

Paketleme ayrıca bağımsız `mobile/scripts/acceptance.py` kapısından geçer: üç JVM
sınıfında 20 vaka, 15 benzersiz native seçimde 24 vaka; her iki uygulamadan dört
aktarılmış dosyanın aynı gerçek SHA-256 özetleri; taze MediaProjection onayı,
iptal/durdurma kontrolü ve cihazdan çekilmiş JPEG ile birebir hash/boyut eşleşmesi
zorunludur. Eksik bildirim, eski commit, boş/atlanmış test, ürün ANR/çökmesi veya
fiziksel başarı iddiası kabul edilmez. Kuralların sentetik rapor testleri native
başarı kanıtı yerine geçmez. Davet/sır dosyaları raporlara alınmaz.

### Gözlenmiş sonuçlar (kabul ile karıştırılmamalı)

- [`6780523` / 46074610850](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46074610850):
  **20/20 JVM**, lint 0 hata/47 uyarı/1 bilgi; eski telefon/SMS/yükleyici/depo
  tabanının 12 vakası geçti. Launcher 5, bağlı kabuk 4 ve köprü 3 vakasında hata
  oluştu. **0.4 kabul edilmedi, dağıtım paketi hazırlanmadı.**
  [SDK](android/evidence/sdk-6780523.json) ve [başarısız cihaz kaydı](android/evidence/emulator-6780523.json).
- [`2da79b2` / 46076879137](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46076879137):
  [20 JVM/SDK tekrar geçti](android/evidence/sdk-2da79b2.json). Native/Python arasında
  dört dosyanın iki yönlü TLS/özetleri ve native instrumentation `OK (1 test)`
  gözlendi; sürücünün son işaretçiyi süreç çıkışından sonra okumaması kabulü bozdu.
  Gerçek arayüz tanısı, ilk kullanım **Viewing full screen / Got it** sistem
  öğreticisini gösterdi. Test yalnız `android:id/immersive_cling_title` ve
  `immersive_cling_description` birlikteyse bu öğreticinin kendi düğmesine basar;
  güvenlik/izin/MediaProjection/ANR pencerelerini böyle kapatmaz.
  [Kısmi başarısız kayıt](android/evidence/emulator-2da79b2-partial.json); nihai özet
  checks bildirim kotasında görünmediği için toplam cihaz başarısı çıkarılmaz.
  Yeni sürücüde zorunlu makbuzlar görsel tanı parçalarından önce yazılır.
- [`18034bb` masaüstü / 46076502634](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46076502634):
  Debian bookworm/trixie üzerinde **1024×768 ve 360×800: dört gerçek GTK köprü
  koşusu geçti**. Gerçek düğme/dosya/loopback TLS/GDK kareleri sınandı. Üretimin
  bilinmeyen kilit durumunu reddetmesi ayrıca doğrulandı; ardından **yalnız özel
  Xvfb test sürecinde** açık-oturum/onay koşulu test verisiyle sağlandı. Gerçek
  logind/telefon/ARM/Wi-Fi kanıtı değildir. [Özgün CI makbuzları](../docs/evidence/bridge-gtk-18034bb.json).
- Yerel tekrar: Python köprü **19/19** (takılı gerçek TLS el sıkışmasında anlık durdurma dahil); masaüstü birimleri **102/102**; Pi yapılandırma
  ve doğrulama kuralları **35/35**; mobil kaynak/kabul kuralları **29/29** (9'u açıkça
  sentetik rapor/orkestrasyon testi); JS mantık/API **31/31**, Chromium **33/33** (31 akış ve 2
  kapsayıcı). Bunlar derlenmiş APK'nın 24 cihaz vakası yerine kullanılamaz.

Sonuç ve APK ancak yeni CI raporu incelendikten sonra teslim edilir. Henüz
ROM/ISO/OTA veya yeni public Release hazırlanmaz.
