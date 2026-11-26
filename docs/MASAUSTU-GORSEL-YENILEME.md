# Masaüstü görsel yenileme · uygulama teması, Başlat, PrintScreen, Mağaza ve Haber

Bu belge **geliştirme dalındaki kaynak değişikliklerini** anlatır. Önceki v1.1, `00ec2b1` veya `775b0a7` imajları kendiliğinden güncellenmez. Son Thunar/çerçeve ve kaynak-bütçesi düzeltmeleri için yeni **amd64/i386 PC ISO** ve **armhf/arm64 Raspberry Pi IMG** derlemeleri istenir; indirme ve doğrulama sonuçları ilgili kaynak commit'i / CI çalışmasıyla raporlanır. PR birleştirme, etiket veya Release yayımlama bu işlemin parçası değildir. Önceki RAM/boot ölçümleri yeni değişikliklerin performans kanıtı değildir.

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

Panel, tepsi, ses, güç, saat ve Whisker düğmelerinin kabartmalı kare çerçeveleri ortak GTK temasında kaldırılır. Xfce'nin dış süreçteki eklenti sarmalayıcısı (`XfcePanelWindowWrapper`) ana panelle aynı CSS sınıflarını kullandığı için, her ses/güç eklentisine ayrı panel kenarı çizmeyen, yalnız bu sarmalayıcıya ait bir geometri kuralı da bulunur; uygulama pencereleri etkilenmez. Tepsi simgeleri **20px**, tek sıra ve kare hücre zorlaması olmadan; saat 9pt, tek dijital düzendedir. Yeni hesap iskeleti ile mevcut hesaplara açık profil uygulaması aynı tipli değerleri kullanır. Kişisel paneli yalnız görünüm değiştirerek sıfırlama yoktur.

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

Okuyucuda başlık, kaynak, görsel ve seçilip kopyalanabilen düz metin aynı dikey kaydırıcıdadır. Büyük yazı veya kısa pencere alt kontrolleri ekran dışına itmez; HTML/markup yorumlanmaz.

Resim düğmesi açıksa **Yenile**, yalnız yayıncının RSS `media:thumbnail`, image `media:content` veya raster `enclosure` alanlarını kullanır. HTML içindeki takip `img` etiketleri kazınmaz. Soğuk açılış / kaynak seçimi / kaynak ekleme **ağ isteği başlatmaz**. Düğme kapatılınca sonraki yenileme yalnız metindir; önceden kaydedilen resimler çevrimdışı kalabilir.

- En fazla **6 görsel**, görsel başına **256KiB**, en fazla **6 megapiksel** durağan JPEG/PNG/WebP; SVG, animasyon ve aşırı büyük raster reddedilir.
- Görsel indirmeleri için **6 saniyelik hedef bütçe**, bağlantı başına en fazla 2 saniye. Tüm kısa ömürlü işçi ön yüzde 24 saniye sonunda sonlandırılır; DNS/ağ gecikmesine rağmen sonsuz bekleme servisi yoktur.
- Akışla aynı genel-HTTPS/DNS sabitleme/TLS sertifika denetimi/yönlendirme sınırı. Yerel/özel IP, ortam proxy'si ve HTTPS→HTTP düşüşü reddedilir.
- Pillow işçide **320×180 JPEG** üretir, EXIF taşımaz; native istemci tür/boyut/kullanıcı/yol sınırını tekrar denetler. GTK, ağdan gelen tam çözünürlüklü dosyayı veya HTML'yi çözümlemez.
- Özel önbellek `~/.cache/oguzdows/news/thumbnails/`, dizin 0700/dosya 0600; en fazla 64 normalleştirilmiş görsel. İlgisiz dosya/bağ silinmez. İndirme/çözümleme hatası okunabilir metni kaybettirmez.

Görsel yoksa altı özgün kategori çiziminden biri kullanılır; bunlar **haber fotoğrafı değildir**, arayüzde açıkça belirtilir. Tarihli canlı haber yerine geçen üretilmiş sahte fotoğraf veya ağsız örneği gerçek güncel haber gibi sunma yoktur.

Rıfkı'nın seçilmiş eski ses kaydı değiştirilmez. Haber anlatım penceresinde kaydın görsel desteği öncesinden olduğu ve güncel resim düğmesinin davranışı ayrıca yazılır.

## Kenarlar ve dosya yöneticisi

### Gerçek çerçeve boşluklarının nedeni

Xfwm 4.18'in [`xfwmPixmapDrawFromGdkPixbuf`](https://github.com/xfce-mirror/xfwm4/blob/xfwm4-4.18.0/src/mypixmap.c) işlevi, PNG'den ürettiği ikili pencere maskesine **yalnız alfa == 255** olan pikselleri katar. Önceki 190/110/90 alfa değerli 1px çerçeve çizgileri ve cam başlığın 220 alfa şeritleri bu maskede boşluğa dönüşebilirdi; sorun yalnız gölge rengi değildi. Yeni üretici kenar rengini önceden karıştırır ve bütün yapısal çizgileri / başlık satırlarını opak tutar. Sadece gerçek üst köşe dışı saydamdır. Alt kenar bütün arka uçlarda kesintisiz 1px kalır; içerikten 10px keserek yuvarlak köşe taklidi yapılmaz.

Picom 12 [`rules` kullanıldığında eski `*-exclude` listelerini okumaz](https://github.com/yshui/picom/blob/v12.5/src/config_libconfig.c). Yeni 12+ reçetelerinde CSD, XShape ile zaten şekillendirilmiş çerçeve, açılır menü, diyalog, override-redirect, tam ekran ve iki eksende büyütülmüş pencere istisnaları gerçek `corner-radius = 0` kuralındadır. Eski 9/11 reçeteleri kendi destekledikleri listeyi kullanır. Böylece aynı köşeyi iki motor kesmez. Büyütülmüş / tam ekran yüzeylerde ek arka plan blur'u ve SSD gölgesi de atlanır.

GTK CSD gölgesi **2px/4px, alfa .12** ve dengeli 6px görünmez yeniden boyutlandırma tutamacıyla sınırlıdır. Büyütülmüş, döşenmiş, tam ekran ve kompozitörsüz `solid-csd` durumları kare köşeye ve sıfır gölge marjına döner. Mağaza / Haber / Masaüstü Merkezi'nin uygulama öncelikli CSS'i de bu durumlara uyar; genel 10px uygulama yarıçapı tema kuralını ezmez. Kişiye özel değişmez materyaller **v5** anahtarıyla yeniden üretilir; eski geri-alma temaları silinmez veya yerinde değiştirilmez.

Thunar'ın gerçek `GtkScrolledWindow.standard-view` içindeki simge/liste/kompakt bölgeleri düz ve opaktır; içe kabartma ve gereksiz köşe kesimi kaldırılır, aktif/pasif seçim vurgusu korunur. GTK dosya seçicisi, Nemo ve Caja'nın opak dosya/metin bölgeleri de korunur. Tüm pencereye opaklık veya büyüyen dosya simgesi uygulanmaz. Bunlar tarayıcı CSS `backdrop-filter` hilesi değildir. Fiziksel GPU/driver kaynaklı her çizim sorununun çözüldüğü iddia edilmez.

### PC, Pi ve ortak ARM katmanında tek seferlik performans bütçesi

`file_manager.py --session`, yalnız Xfce oturumunda Thunar için aşağıdaki varsayılanları uygular. Dizin taramaz, görsel çözümlemez, önbellek / kullanıcı dosyası silmez ve arka planda kalmaz.

| Fiziksel kaynak / profil | Küçük resim varsayılanı | Tek dosya boyut sınırı |
|---|---|---:|
| ≤768MiB, eski Pi CPU'su, bilinmeyen RAM veya `mini` | Kapalı | 8MiB |
| 768MiB–2GiB | Yalnız yerel dosyalar | 16MiB |
| >2GiB | Yalnız yerel dosyalar | 32MiB |

Küçük resimlerin ek siyah çerçevesi kapalıdır. Önceden seçilmiş kişisel Thunar ayarları veya sonradan kullanıcı tarafından değiştirilmiş değerler **ezilmez**. Yalnız eksik ya da hâlâ bize ait değerler bütçe değişince güncellenir; tipli günlük, kısmi hata geri alması ve Masaüstü Merkezi'nin geri-alma işlemiyle entegredir. Kullanıcı önizlemeleri Thunar tercihlerinden yeniden açabilir.

Mevcut ≤2GiB / eski CPU / `nomodeset` / doğrulanmamış grafik koruması, isteğe bağlı efekt onayı, sınırlı LZ4 zram, kişisel swap koruması, azaltılmış hareket ve olay tabanlı native panel çizimi korunur. Bu ortak dosyalar iki PC, iki Pi ve desteklenen ARM64 katmanlarının tamamına kopyalanır; ARM64 katmanı fiziksel cihaz imajı / GPU doğrulaması sayılmaz.

## Doğrulama

- `test_desktop_appearance.py`: INI/portal geri alma, güvensiz kişisel dosyaları koruma, sabit ekran yakalama argv'si, idempotent kısayol geçişi ve küçük tepsi tipleri.
- `test_news_images.py`: metadata/HTML ayrımı, gerçek raster normalleştirme, boyut/piksel/tür/zaman/önbellek sınırları, çevrimdışı ve yalnız metin yolu; canlı ağ kullanılmaz.
- `test_window_geometry.py`: 14 tema / iki odak durumunda bütün başlık ve 1px rayların tam alfa maskesi, değişmez v5 tema önbelleği, eski/yeni Picom istisnaları, uygulama öncelikli kare CSD durumları ve kesintisiz maske birleşimi.
- `test_file_manager.py`: fiziksel RAM üst sınırı, tipli `uint64`, tekrarsız uygulama, kişisel tercihi koruma, kısmi yazı hatasını tam geri alma, açık geri-alma kararını koruma ve gerçek `python3 -I` girişinin yüklenmesi.
- `smoke-window-geometry.py`: özel normal kullanıcıda gerçek Thunar'ın aktif/pasif XShape kenarlarının **tamamı**, 14 statik + 4 üretilmiş tema, kompozitörsüz / gerçek üretim Xrender, simge/liste/kompakt görünüm ve bağlam menüsü; gerçek GTK ölçeği 1×/2× PC kapısında çalıştırılır. Native öncelikli CSD stillerinin piksel probe'u ile gerçek büyütme / tam ekran işlemleri ayrı ayrı kaydedilir. Döşenmiş sınıfların probe'u fiziksel pencere döşeme testi değildir. Pi doğrulama işi de aynı kontrolü host üzerinde 1× çalıştırır; bu ARM GPU testi değildir.
- PC imaj kapısı yeni politika / CSS / üretici dahil kurulu kaynak baytlarını SHA-256 ile karşılaştırır. Pi'nin ARM CPU / GUI kapısı ve salt okunur export doğrulaması 31 görsel/ses dosyasına ek **19 masaüstü kaynak dosyasını** hash ile denetler; imajdan host üzerinde Python kodu çalıştırılmaz.
- Mevcut native Store/Haber/Başlat, azaltılmış hareket, kurulum/onay ve paket kapıları korunur. Haber fixture'ı gerçek normalleştirilmiş yerel JPEG ve dürüst kategori çizimi içerir.
- `smoke-desktop-polish.py`: özel normal kullanıcıda gerçek xfsettingsd/xfwm; zaten açık sıradan GTK3 ve libadwaita istemcilerinde koyu→açık→koyu, gerçek Thunar, XTest Print tuşundan native ekran yakalama diyaloğuna giden yol, gerçek Başlat toggle/Escape. Çıktı JSON/PNG'ler CI artifact'ındadır. Bu testin varlığı tek başına başarılı çalıştırma sonucu değildir.

CI/Xvfb görüntüleri fiziksel GPU/FPS, pil tüketimi, tam kurulum veya Pi'de fiziksel ekran testi değildir. Sonuçlar kaynak commit'i ve CI çalışmasıyla birlikte raporlanmalıdır.
