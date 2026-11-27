# OğuzDows 0.4 · Bağlı kabuk (geliştirme dalı)

**Durum:** Kaynak eklendi; yeni native derleme ve 24 cihaz vakasının sonucu henüz
alınmadı. Bu belge 0.4'ün kabul edildiği veya fiziksel cihazlarda denendiği anlamına
gelmez. Önceden kabul edilmiş 0.3 APK bağlantısı [INSTALL.md](INSTALL.md) içindedir.

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
çizer; fiziksel GPU/RAM/pil/gerçek SIM/ARM performansı kanıtı değildir. Sonuç ve APK
ancak yeni CI raporu incelendikten sonra teslim edilir. Henüz ROM/ISO/OTA veya yeni
public Release hazırlanmaz.
