# Masaüstü görsel yenileme · uygulama teması, Başlat, PrintScreen, Mağaza ve Haber

Bu belge **geliştirme dalındaki kaynak değişikliklerini** anlatır. Yayımlanmış v1.1 veya önceki `00ec2b1` ISO dosyaları kendiliğinden güncellenmez. Bu çalışma için yeni ISO/IMG veya yayın oluşturulmaz. Önceki RAM/boot ölçümleri bu değişikliğin performans kanıtı değildir.

## Açık/koyu tercihi gerçek uygulamalara gider

Rehber → Tarzlar veya Masaüstü Merkezi → Aero ve görünüm bölümündeki seçim tek işlem olarak şunlara uygulanır:

- **GTK3 / Xfce:** canlı XSettings tema adı; sonraki istemciler için `gtk-3.0/settings.ini` içindeki yalnız tema ve koyu tercih anahtarları. Thunar gibi normal GTK3 uygulamaları da renkli/sürümlü gerçek temayı kullanır; yalnız OğuzDows penceresine koyu CSS eklenmez.
- **GTK4 / libadwaita ve portal kullanan uygulamalar:** standart `org.gnome.desktop.interface color-scheme` tercihi ve GTK Settings portalı. Xfce portal seçimi `xfce-portals.conf` içindedir. GSettings şemaları, dconf ve GTK portal paketleri tüm hedeflerin ortak bağımlılığıdır.
- **GTK2:** mevcut gerçek GTK2 tema varyantı ve vurgu üretimi korunur. Qt5'in mevcut GTK platform tema eklentisi korunur; KDE oturumunda kendi KConfig/Qt paleti uygulanmaya devam eder.

Kişisel INI dosyasının diğer anahtarları ve yorumları saklanır. Bağ/FIFO/aşırı büyük/başka kullanıcıya ait dosya ezilmez; kullanıcıya not verilir. Değişiklikler dar günlükle geri alınır; sonradan başka uygulamayla değiştirdiğin değerler geri almada korunur. Kalıcı ortak tercih yazılamazsa yerel değişiklikler ters sırada geri sarılır.

**Sınır:** kendi temasını zorlayan uygulama, web sayfası, tarayıcı eklentisi, Flatpak'ın eksik GTK tema paketi veya her Qt/custom arayüz için evrensel piksel eşliği vaat edilmez. Uygulamaya özel koyu tercihi ayrıca gerekebilir. Global `GTK_THEME` zorlaması veya sürekli tema eşitleme servisi eklenmez.

Kurulu güncel kaynakta normal Xfce kullanıcısıyla örnek:

```sh
oguzdows-desktop --apply --appearance dark
oguzdows-desktop --apply --appearance light
```

## Çerçevesiz panel ve Windows esintili Başlat

Panel, tepsi, ses, güç, saat ve Whisker düğmelerinin kabartmalı kare çerçeveleri ortak GTK temasında kaldırılır. Tepsi simgeleri **20px**, tek sıra ve kare hücre zorlaması olmadan; saat 9pt, tek dijital düzendedir. Yeni hesap iskeleti ile mevcut hesaplara açık profil uygulaması aynı tipli değerleri kullanır. Kişisel paneli yalnız görünüm değiştirerek sıfırlama yoktur.

Windows tarzında gerçek C/GTK Başlat menüsü; arama, sabitlenenler, tüm uygulamalar, yerel son dosyalar, hızlı ayarlar ve yerel oturum/kapatma diyaloğu içerir. Uygulama düğmeleri kutusuz simge + addır. Sağ tık / klavye bağlam menüsüyle sabitleme korunur. Son dosyalarda gizli yol, özel işaretli dosya ve ağ URI'si gösterilmez. `Escape`, odak dışına tıklama ve ikinci `--toggle` isteği kapatır. Menü panel üstündeki çalışma alanına, ilgili ekranda ortalanır.

Görev simgesi basışta içeri, üzerine gelince hafif yukarı hareket eder. Yalnız önbellekteki simge sabit hücre içinde çizilir: **150ms** süren olay tabanlı geçiş; kare başına panel yerleşimi/simge yükleme yoktur. Azaltılmış hareket / düşük kaynakta timer kullanılmadan statik basış vurgusu kalır. Mac büyütmesi de aynı sınırlı çizim yolundadır.

Tarz seçicideki eski sembolik kare/dolgu önizlemeler yerine derleme sırasında üretilen altı küçük yerleşim çizimi vardır; gerçek ekran görüntüsü oldukları iddia edilmez.

## PrintScreen

`xfce4-screenshooter` bütün hedeflere eklenir. Xfce oturum başlangıcı eksik veya eski stok komutları tamamlar; kişisel Flameshot/başka komutları ezmez, klavye kanalını sıfırlamaz.

| Tuş | İşlem |
|---|---|
| PrintScreen | Tam ekran |
| Shift + PrintScreen | Alan seçimi |
| Alt + PrintScreen | Etkin pencere |
| Super + Shift + S | Alan seçimi |

Kısa ömürlü `oguzdows-screenshot` sarmalayıcısı native kaydet/kopyala diyaloğunu açar. Otomatik yükleme, sessiz dosya üzerine yazma, kabuk komutu veya kalıcı ekran servisi yoktur. Alan seçiminde Escape iptal eder. Kişisel bir PrintScreen bağın varsa Klavye → Uygulama kısayollarında bu komutu kendin seçebilirsin:

```sh
oguzdows-screenshot --fullscreen
```

Eski kuruluma yalnız bir Python dosyasını kopyalamak yeterli değildir; paket, sarmalayıcı ve oturum entegrasyonu birlikte bulunmalıdır.

## Mağaza

- Üç kullanıcı kontrollü görselli seçki; otomatik kayan carousel veya webview yok.
- Özgün çevrimdışı üret/medya/çalışma çizimleri ve uygulamaya göre resimli yedek simgeler; üçüncü tarafın resmî logosu oldukları iddia edilmez.
- Hızlı kategori düğmeleri, genişliğe göre 1/2/3 sütun, kompakt ekranda taşmayan metin ve gizlenen büyük çizim.
- Yerel katalog, gerçek kurulu durum, açık ağ araması ve kaynak/plan/ayrı onay akışı aynen korunur. Purge, autoremove veya kullanıcı verisi silme eklenmez.
- **Gelişmiş merkez** gerçek GNOME Software kuruluysa açılır; yoksa şu isteğe bağlı komut açıklanır, kendiliğinden çalıştırılmaz:

```sh
sudo apt install gnome-software gnome-software-plugin-flatpak
```

## Haber: resimler, tek tıkla okuma, gerçek kaynak

Başlığa tek tıklamak RSS metni/özetini okuyucuda açar. **Kaynakta aç ↗** yayıncının tam sayfasını kullanıcının tarayıcısına yalnız açık tıklamayla gönderir. A−/A+, kategori, arama, kaynak ekle/kaldır, iptal ve çevrimdışı okuma korunur. Pencere 720px eşiğinden geçince araç çubuğu ve küçük resim/metin yerleşimi yeniden açmadan değişir; açık haber ve seçili filtre korunur. Bu uyarlama her karede değil yalnız eşik değişiminde çalışır; akışı yeniden indirmez.

Resim düğmesi açıksa **Yenile**, yalnız yayıncının RSS `media:thumbnail`, image `media:content` veya raster `enclosure` alanlarını kullanır. HTML içindeki takip `img` etiketleri kazınmaz. Soğuk açılış / kaynak seçimi / kaynak ekleme **ağ isteği başlatmaz**. Düğme kapatılınca sonraki yenileme yalnız metindir; önceden kaydedilen resimler çevrimdışı kalabilir.

- En fazla **6 görsel**, görsel başına **256KiB**, en fazla **6 megapiksel** durağan JPEG/PNG/WebP; SVG, animasyon ve aşırı büyük raster reddedilir.
- Görsel indirmeleri için **6 saniyelik hedef bütçe**, bağlantı başına en fazla 2 saniye. Tüm kısa ömürlü işçi ön yüzde 24 saniye sonunda sonlandırılır; DNS/ağ gecikmesine rağmen sonsuz bekleme servisi yoktur.
- Akışla aynı genel-HTTPS/DNS sabitleme/TLS sertifika denetimi/yönlendirme sınırı. Yerel/özel IP, ortam proxy'si ve HTTPS→HTTP düşüşü reddedilir.
- Pillow işçide **320×180 JPEG** üretir, EXIF taşımaz; native istemci tür/boyut/kullanıcı/yol sınırını tekrar denetler. GTK, ağdan gelen tam çözünürlüklü dosyayı veya HTML'yi çözümlemez.
- Özel önbellek `~/.cache/oguzdows/news/thumbnails/`, dizin 0700/dosya 0600; en fazla 64 normalleştirilmiş görsel. İlgisiz dosya/bağ silinmez. İndirme/çözümleme hatası okunabilir metni kaybettirmez.

Görsel yoksa altı özgün kategori çiziminden biri kullanılır; bunlar **haber fotoğrafı değildir**, arayüzde açıkça belirtilir. Tarihli canlı haber yerine geçen üretilmiş sahte fotoğraf veya ağsız örneği gerçek güncel haber gibi sunma yoktur.

Rıfkı'nın seçilmiş eski ses kaydı değiştirilmez. Haber anlatım penceresinde kaydın görsel desteği öncesinden olduğu ve güncel resim düğmesinin davranışı ayrıca yazılır.

## Kenarlar ve dosya yöneticisi

GTK CSD ve Picom aynı kenarı iki kere gölgelemez. CSD gölgesi 3px/8px ve düşük alfa; SSD gölgesi daha dar/düşük alfa; gerçek blur reçeteleri daha düşük yarıçap kullanır. Bunlar tarayıcı CSS `backdrop-filter` hilesi değildir. Kompozitör yoksa opak, köşeleri bozulmayan yüzey kullanılır.

Thunar / GTK dosya seçicisinin dosya ve metin bölgeleri opaktır; seçili öğe vurgusu korunur. Tüm pencereye opaklık veya büyüyen dosya simgesi uygulanmaz. Fiziksel GPU/driver kaynaklı her çizim sorununun bu CSS ile çözüldüğü iddia edilmez.

## Doğrulama

- `test_desktop_appearance.py`: INI/portal geri alma, güvensiz kişisel dosyaları koruma, sabit ekran yakalama argv'si, idempotent kısayol geçişi ve küçük tepsi tipleri.
- `test_news_images.py`: metadata/HTML ayrımı, gerçek raster normalleştirme, boyut/piksel/tür/zaman/önbellek sınırları, çevrimdışı ve yalnız metin yolu; canlı ağ kullanılmaz.
- Mevcut native Store/Haber/Başlat, azaltılmış hareket, kurulum/onay ve paket kapıları korunur. Haber fixture'ı gerçek normalleştirilmiş yerel JPEG ve dürüst kategori çizimi içerir.
- `smoke-desktop-polish.py`: özel normal kullanıcıda gerçek xfsettingsd/xfwm; zaten açık sıradan GTK3 ve libadwaita istemcilerinde koyu→açık→koyu, gerçek Thunar, XTest Print tuşundan native ekran yakalama diyaloğuna giden yol, gerçek Başlat toggle/Escape. Çıktı JSON/PNG'ler CI artifact'ındadır. Bu testin varlığı tek başına başarılı çalıştırma sonucu değildir.

CI/Xvfb görüntüleri fiziksel GPU/FPS, pil tüketimi, tam kurulum veya Pi'de fiziksel ekran testi değildir. Sonuçlar kaynak commit'i ve CI çalışmasıyla birlikte raporlanmalıdır.
