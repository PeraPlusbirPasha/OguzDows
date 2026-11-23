# elementary esintili düzen, özgün simgeler ve hafif Haber

Bu bölüm **79c6942 imajlarından sonraki kaynak değişikliklerini** anlatır. v1.0.0 etiketi / yayın dosyaları değişmez. Kaynak testi, gerçek host GTK, ARM kullanıcı-QEMU, tam sistem VM ve fiziksel cihaz sonuçları aynı şey değildir.

## Görünüm

- **macOS esintisi · Xfce:** elementary referansındaki ince, opak üst panel ve içeriğine oturan ortalı alt iskele. Sol pencere düğmeleri / bağımsız açık-koyu tema korunur. Aero seçimi bu düzenin Mac temasını başka bir temaya çevirmez.
- **Windows 11 esintisi · Xfce:** Başlat + dört sabit başlatıcı + açık uygulama grubu aynı doğal genişlikli alt paneldedir. Saat / tepsi / ses / güç ayrı ince üst şerittedir; asimetrik sağ alan merkez grubunu sola itemez. Ortalanan yalnızca yüzde 76 genişliğinde boş bir panel değildir. Ek açık pencerelerde panel içeriği büyür; görevler kaldırılmaz.
- **Ubuntu / GNOME esintisi · Xfce:** sol iskele de sabit büyük boş alan yerine doğal boyut ister. Bunlar gerçek Plasma/GNOME oturumu veya Apple/Microsoft işletim sistemi değildir; gerçek KDE/GNOME kurulum / giriş seçimi ayrı kalır.
- İskele düğmeleri, karşılayıcı ve mağaza yan menüsü yuvarlatıldı; kabartmalı kare çerçeve yoktur. Üst panel, içerik, yazı ve kapatma kontrolleri **opak** kalır. Kişisel panel / ilk ayarların tipli yedeği ve geri alma akışı korunur.

Panel kapısı gerçek Xfce 4.18 / 4.20 üzerinde **1024×768, 1280×900 ve 1920×1080** için tanımlıdır. Yalnızca panel pencere sınırını değil ekran görüntüsündeki görünür simge/düğme şeridini ölçer: merkez hatası en çok 12px. Üç ayrı uygulama sınıfıyla görev grubu büyümeli, yine ortada kalmalıdır. Bu yeni kapının sonucu olmadan “bütün ekranlarda merkezleme doğrulandı” denmez.

## 15 ayrı özgün uygulama simgesi

Mağaza, Haber, Rehber, Güncelleyici, Cihaz, Uyumluluk, İmece, Kurucu, Rıfkı, Masaüstleri, Sürücüler, Manzaralar, Tarayıcı, Dosyalar ve Terminal için ayrı çizim vardır. Her araçta aynı bayrak / monogram tekrarlanmaz. Köşeler saydamdır; renkli çanta, gazete, kitap, çay, kedi, klasör gibi farklı siluetler kullanılır.

Köken / ad listesi: `system/usr/share/oguzdows/own-app-icons.json`. Çizim kaynağı `scripts/render-assets.py:own_app_icon`; **16/24/32/48/64/96/128/256px**, toplam 120 PNG imaj derlemesinde çevrimdışı üretilir. Yerelde tam renderer çalıştı: **315.915 bayt** özgün uygulama simgesi. Uygulama masaüstü dosyası, pencere simgesi ve dört iskele kısayolu aynı hicolor adlarını kullanır. Üçüncü taraf uygulamaların logoları oldukları iddia edilmez; mağazadaki uygulama rozetleri ayrı kalır. Üretici / elementary simgeleri kopyalanmaz.

## Kaynak bütçeli geçiş

Rehber → Tarzlar → **Aero esintisi** seçilirse ve **>2 GiB / full / tanınan DRM / ARMv6 değil / nomodeset değil** koşulları birlikte sağlanırsa tek Picom **XRender** motoru kullanılır. Yaklaşık 90–120ms açma/kapatma/haritalama solması ve hafif gölge; sürekli hareket / GLX / blur yoktur. İskele camı yalnız arka planda 0,94 alfadır; bütün pencereyi veya yazıları soldurmaz. **Gala'nın spring / zoom / çalışma alanı animasyonlarıyla tam eşdeğerlik iddia edilmez.**

`effects.py` tek seferlik karar verip çıkar; sürekli Python denetleyicisi yoktur. Kendi Picom'u UID / sabit argv / PID doğum zamanı / X11 CM seçim kimliğiyle izlenir. Her X ekranının sahipliği ayrıdır; başka kompozitör başlatılmaz / öldürülmez. Tekrarlanan hafif cam seçimi mevcut Xfwm kompozitörünü yanlışlıkla kapatmaz. Açılışta kayıtlı kullanıcı tercihi yoksa kişisel kompozitör ayarı korunur. Motor açılamazsa uygun durumda Xfwm, aksi halde statik görünüm kalır; yeniden başlatma döngüsü yoktur.

512MiB / 1GiB / 2GiB, Zero / ARMv6, güvenli grafik veya bilinmeyen DRM durumunda aynı uygulamalar, simgeler ve düzen korunur; kompozitör / GTK animasyonları açılmaz. Bu politika **ölçülmüş hızlanma veya yeni RAM tasarrufu sonucu değildir**.

## OğuzDows Haber

Başlat → **OğuzDows Haber** veya Rehber → Uygulamalar → Haber. `native/news.c` içinden mimariye uygun **C / GTK3** ikilisi derlenir; webview / Electron / tarayıcı motoru yoktur. Python stdlib işçisi tek JSON isteğini bitirince çıkar; kapalı uygulamanın yenileme servisi yoktur.

1. Açılışta yalnızca kaynak listesi ve yerel önbellek okunur, **ağa bağlanılmaz**.
2. Kaynak seçip **Yenile**: yalnız seçili HTTPS RSS / Atom / RDF akışı istenir. Görsel, reklam, JavaScript veya bütün site indirilmez. Yayıncının akışta sunduğu metin / özet gösterilir; tam makale garantisi verilmez.
3. Haber aç → **A− / A+** ile 12–26pt. Boyut kullanıcı hesabında saklanır; çevrimdışı metin okunabilir. **Kaynakta aç** yalnız açık tıklamayla kullanıcının tarayıcısını çağırır, komut çalıştırmaz.
4. Kendi HTTPS kaynağını ekleyebilirsin; eklemek indirme yapmaz. Yalnız kişisel kaynak kaldırılır. Varsayılanlar TRT Manşet / Bilim-Teknoloji, BBC Türkçe ve DW'dir; canlı erişimleri bu sandbox'ta doğrulanmadı. Yayıncı erişimi / RSS yapısı değişirse hata gösterilir ve eski önbellek korunur.
5. **Durdur**, 24 saniyelik ön yüz süre sınırı veya pencereyi kapatma kısa ömürlü ağ işçisini sonlandırır. Kullanıcı onayı olmadan otomatik tekrar deneme yapılmaz.

Akış / önbellek en çok 1MiB, kaynak başına 60 haber, gövde 8192 karakter, toplam 16 kaynak, en çok 3 yönlendirme. DTD/entity, aşırı XML derinliği / düğüm sayısı, yerel/özel IP ve HTTPS→HTTP düşüşü reddedilir. Bağlantı doğrulanan genel IP'ye sabitlenir; TLS SNI / sertifika / hostname denetimi asıl alan adında kalır. Ortam proxy'si kullanılmaz: indirme doğrudan HTTPS ister. Bu, her ağda erişim veya haber içeriğinin doğruluğu garantisi değildir. Dizinler 0700, atomik JSON önbelleği 0600'dür; sembolik bağ / FIFO / normal olmayan dosyalar reddedilir. Yazı tercihi `~/.config/oguzdows/news/reader.ini`, önbellek `~/.cache/oguzdows/news/` altındadır.

**Dinle / Durdur**, aynı seçilmiş voice-01 ile yerel kullanım rehberidir; değişken haber metnini seslendiren TTS değildir. Yeni kayıt 47,68sn; seçili toplam **11 kayıt / 18.407.898 bayt / 25 metin eşlemesi**. Önceki on WAV byte-byte korunmuştur. Yapay zekâ üretimidir, insan stüdyo kaydı değildir.

## PC / Pi / diğer ARM'e taşıma ve kanıt

PC hook, iki pi-gen tarifi ve dört deneysel ARM64 katmanı aynı news kaynaklarını, simge renderer'ını ve efekt kararını alır. Hazır x86 ikilisi ARM'e kopyalanmaz; hedef derleyici / ABI varsayılanıyla, `-march=native` / zorunlu NEON olmadan derlenir. Pi sözleşmesi artık **11 özellik grubu / 31 galeri-ses hash'i / 11 seçili kayıt** ister. 15 simgenin 64px üretimi, Picom / config ve haber dosyaları da varlık kapısındadır. ARM hedef kapısı native Haber ELF/sürümünü ve ayrı non-root oturumda gerçek C istemcisi + üretim işçisiyle **ağsız TEST önbelleğini** zorunlu kılar. Bu bir canlı haber, piksel, performans veya fiziksel boot testi değildir.

Yerelde **444 test / 7 bağımlılık atlaması, 25,265sn**, ResourceWarning ölümcül; 18 haber, 15 efekt ve 4 simge testi dahildir. Tam renderer, Python / kabuk lint, workflow eşliği geçti. **GTK geliştirme araçları / Xvfb / QEMU burada yok; C derleme ve yeni gerçek grafik kapıları CI sonucu bekler.** PC / Pi görüntüleri veya fiziksel Zero başarısı bu sayıya dahil değildir.

`79c6942` önceki imajları dört mimaride tamamlandı: [kaynak kimlikli makine kaydı](releases/v1.1-79c6942-images.json). Yeni Haber / simge / geçiş kodu bu imajların içinde değildir. Zero'nun hesap ekranı sonrası fiziksel siyahlığının nedeni [günlüklerle ayrıca doğrulanmalıdır](PI-ZERO-OTURUM.md).
