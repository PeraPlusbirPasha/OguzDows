# Rıfkı ve manzara kaynakları

## Paketlenen hafif sürüm

`rifki/portrait.png` ve `rifki/expression.png` bu proje için üretilmiş yapay zekâ görselleridir. Aynı Van kedisinin temel pozu ve kapalı göz / açık ağız ifadesinden hazırlanmış 384×384 PNG kaynakları `system/usr/share/oguzdows/rifki/` altındadır. Karşılamada tek sabit resim; istenince açılan Rıfkı penceresinde en fazla üç küçük, önceden ölçeklenen resim kullanılır. Varsayılan animasyon döngüsü, Cairo çizim geri çağrısı veya pencere katmanı yoktur. İsteğe bağlı ağız geçişi yalnızca konuşma sırasında 2 Hz'dir; azaltılmış hareket profilinde ve kurulumda kapalıdır.

Türkçe WAV'lar yapay zekâ ile hazırlanmış, doğal konuşma tınılı **yerel kayıtlardır; gerçek bir insanın stüdyo kaydı değildir.** Eski temel yardım, ayar, kurulum aşaması ve sonuç kayıtları korunur. 1.1'in **10 yeni açıklaması**, kullanıcının iki seslik dinleme önizlemesinde açıkça seçtiği sesle hazırlandı. Canlı / kurulu karşılama, tasarım ve açık/koyu, uygulamalar, destek, 20 görsellik galeri, Pi donanımı, yerel mağaza, EXE/APK ve İmece'yi kapsar. Eski altı-görsel / üst-sekme anlatımları eşlemeden ve kaynak paketinden çıkarıldı.

`speech.json` **24 farklı tam metin özetini** yerel WAV'a eşler; bazı paneller aynı açıklamayı paylaşır. Kurulum sonuçları yalnızca sabit bir izin listesinden kayıt seçer. Başarılı olmayan veya henüz tamamlanmamış kurulum için başarı kaydı seçilmez. `rifki-narration.json` yeni on kaydın tam metnini, SHA-256'sını, örnek / kanal / süre bilgisini ve açık ses seçimi kökenini kaydeder. `scripts/prepare-narration.py`, önceden üretilmiş 24 kHz / mono / 16 bit PCM dosyalarını doğrulayıp çevrimdışı paketler; ses üretmez veya indirmez. On yeni dosya toplam **16.119.180 bayttır**, en uzunu 49,44 saniyedir. Tasarım kaydı aynı seçilmiş sesle Windows 11 / macOS / Ubuntu esintileri ile ayrı gerçek oturum ve Aero ayrımını anlatacak şekilde yenilenmiştir; eski beş-kart metin eşlemesi emekli edilmiştir.

Çalışma zamanında eSpeak NG, sentez, genlik taraması, model indirme, mikrofon veya ağ erişimi yoktur. Manifest her pencere açılışında bir kez okunur; ses yalnızca oynatma sırasında ayrı oynatıcıdan akar. Karşılayıcının yedi sayfasında otomatik anlatım tek tercihle kapatılır; diğer araçlarda Dinle / Durdur / ses anahtarı vardır. Kurucunun D-Bus busy sinyali sesi keser; sonradan otomatik devam etmez. Değişken hata / hedef / donanım ayrıntıları yazılıdır; yanlış bir genel başarı kaydına veya robotik sese düşülmez. Yeni mesajda kayıt bulunmasa bile önceki ses kesilir.

## Önceki hareketli sürüm — yalnızca geliştirici kaynakları

`perch.png`, `leap.png`, `play.png`, `tea.png`, `teapot.png` ve `tea-glass.png` önceki katmanlı animasyon için üretilmiş poz / obje kaynaklarıdır. `scripts/prepare-rifki.py`, `scripts/preview-rifki.py`, `rifki_scene.py` ve hareket testleri bu kaynakları geliştirme / tarihsel önizleme amacıyla korur. Tam 3B model veya gerçek hayvan videosu değildir.

Bu çizici, pencere takipçisi, hareket planlayıcısı ve `rig/` dokuları **PC veya Pi imajına kopyalanmaz**. Eski `envelopes.json`, artık kullanılmayan tanıtım kayıtları ve dördüncü animasyon karesi de imajdan dışlanır. Önceki video / WebP demosu hafif sürümün çalışma zamanı veya performans gösterimi değildir.

## Türkiye manzaraları

Önceki altı çizim emekli edildi; altı manzaranın da içeriği yenilendi. Boğaz, Kaçkar, Kapadokya, Ölüdeniz, Tuz Gölü ve Ani esintili bu görseller bu proje için yapay zekâyla üretildi. **Gerçek kamera fotoğrafları veya birebir coğrafi belge değildir.** Ticari stok arama önizlemeleri kullanılmadı.

Paketlenen 1920×1080 JPEG dosyaları `system/usr/share/backgrounds/oguzdows/` altındadır; her birinin sağ alt köşesine proje ay-yıldızı ve OğuzDows yazısı eklenmiştir. Ayrı 320×180 önizlemeler yalnızca galeri açılınca yüklenir. Eski `wallpaper.png` uyumluluk yolu yeni Boğaz manzarasından üretilir; eski çizim tekrar paketlenmez.

`landscapes.json`, logosuz özgün kaynağın boyut/SHA-256'sını ve paketlenen logolu JPEG'in SHA-256'sını kaydeder. `scripts/prepare-landscapes.py` logosuz özgün kaynaklarla bir kez çalıştırılan geliştirme aracıdır; derleme sırasında JPEG'e tekrar logo basılmaz. GTK galerisi, yerel belge ve README yapay zekâ kökenini açıkça belirtir.

## Yerel tespih imleci

`scripts/render-assets.py` özgün, küçük boncuk/tane-vurgusu karelerini ve Xcursor v1 dosyalarını çevrimdışı üretir. 24/32/48 px; normal/bağlantı/bekleme için 10 kare, yazı için sabit kare; diğer roller Adwaita'dan miras alınır. Ayrı runtime çizici, masaüstü katmanı veya tıklama izleme servisi yoktur. Format/boyut/hotspot/alpha testleri ve CI içinde gerçek libXcursor okuyucusu kullanılır.

## 1.1 kültür koleksiyonu — toplam 20

İlk altı manzara korunur. **İstanbul Kedisi, Van Kedisi, Çay ve Simit, Halay, Horon, Zeybek, Kilim, Ebru, Lale, Nazar** bu proje için üretilmiş 10 yeni yapay zekâ görselidir. Kültürel esintili görseller birebir belgesel / etnografik doğruluk veya bir insan fotoğrafı iddiası taşımaz. Gerçek bir dans grubunun ya da stok fotoğraf sanatçısının eseri gibi sunulmaz.

**Vapur, Safranbolu, Pamukkale Terasları, Anadolu Gecesi** ise `scripts/draw-culture-wallpapers.py` içindeki özgün, deterministik Pillow çizimleridir; yapay zekâ görüntüsü veya kamera fotoğrafı olarak etiketlenmez. Çizim kaynağı sürüm kontrolündedir. 10 model görseli sınırı nedeniyle bu dört eserin tasarımı kodla yapılmıştır.

Toplam **16 AI görsel + 4 özgün çizim**, 1920×1080 JPEG. Paketlenmiş yirmi dosya toplamı yaklaşık 11,3 MB; çalışma zamanında yalnızca kullanıcı seçtiği masaüstü ve galeriye girdiğinde 320×180 önizlemeler yüklenir. Ham geliştirme PNG'leri ve araç önbellekleri imaja / Git'e girmez. Hepsi bir kez sağ altta ay-yıldız / OğuzDows işaretiyle markalanır; SHA-256 ve köken kayıtları `landscapes.json` içinde tutulur. Bir logo lisans / telif yükümlülüğünü ortadan kaldırmaz.

## Özgün OğuzDows uygulama simgeleri

`own-app-icons.json` ürün tarafında `system/usr/share/oguzdows/` altındadır; 15 ayrı çizimin köken / ad listesi ve sekiz boyutu tutulur. Kaynak `scripts/render-assets.py:own_app_icon` olup derlemede 16–256px toplam 120 saydam kenarlı PNG üretir. Tekrarlanan bayraklar yerine çanta, gazete, çay, kedi, klasör ve ayrı siluetler vardır; elementary/Apple/Microsoft veya üçüncü taraf üretici logoları kopyalanmaz. Tam renderer yerelde 315.915 bayt üretti; bu dosya boyutu çalışma RAM'i veya fiziksel GPU başarısı değildir. Mağazadaki üçüncü taraf uygulama rozetleri ayrı kalır.

Haber için seçili voice-01 ile 47,68sn yerel kullanım kaydı eklendi. Toplam 11 seçili WAV / 18.407.898 bayt / 25 metin eşlemesi; önceki on WAV'ın SHA-256'ları byte-byte korunur. Köken / PCM / tam metin `rifki-narration.json` içindedir; bu AI sesi insan stüdyo kaydı veya makale TTS'si değildir.
