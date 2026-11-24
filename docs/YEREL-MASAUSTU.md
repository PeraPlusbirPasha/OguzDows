# Yerel Aero, ortak görünüm ve canlı performans

[← Proje](../README.md) · [Bakım rehberi](MASAUSTU-VE-BAKIM.md) · [Makine okunur test kaydı](evidence/native-desktop-39e5f9a.json)

> **Geliştirme kaynağıdır; yayımlanmış v1.1 imajlarının özelliği diye sunulmaz.** v1.1’in dört imajı, `29f7738` ürün kaynağı ve [yayın kanıtları](releases/v1.1.md) değişmedi. Aşağıdaki gerçek kabuk sonuçları `39e5f9a1d729e8d510526ba504f49ec268fe4b9c` içindir; yeni ISO/IMG, fiziksel cihaz veya Wayland doğrulaması değildir.

## Kullanım

Yeni kaynağın paketlendiği bir sistemde, **normal masaüstü hesabından**:

```sh
oguzdows-desktop           # Masaüstü Merkezi: Aero ve görünüm / yerel araçlar
oguzdows-hub               # Yerel C/GTK Başlat: arama, sabitleme, yerel ayarlar
oguzdows-monitor           # Yerel C/GTK/Cairo CPU, RAM ve ağ grafikleri
oguzdows-desktop --status  # Salt-okunur tercih / kaynak / oturum durumu
```

Rehber’in **Görünüm** sayfası aynı tercih bileşenini kullanır. Açık/koyu, efekt düzeyi, hareket, blur, deneysel Snap animasyonu ve vurgu rengi ayrı seçimlerdir. **Yeni blur, yay ve Snap animasyonu kendiliğinden açılmaz.**

1. Önce **Aero** düzeyini seç. Gerçek blur için ayrıca blur kutusunu açıkça işaretle. Kapalı / hafif cam düzeyinde işaretli gelişmiş seçenekler zorla etkinleşmez.
2. **Azaltılmış** hareket animasyonu kapatır; **Kısa / yerel** hafif geçişleri, **Yay** desteklenen kompozitör API’sini ister. Yetenek / kaynak kapısı başarısızsa hafif veya statik sonuç kullanılır; kayıtlı istek ile çalışan efekt aynı şey değildir.
3. Vurgu rengini seç veya **seçili galeri görselinden** renk çıkar. İkincisi açık uygulama işlemi sırasında tek küçük örnekleme yapar; duvar kâğıdını sürekli tarayan süreç yoktur. Galeri seçimi Rehber → **Manzaralar** üzerinden aynı ortak tercihe kaydolur.
4. **Ortak tercihleri uygula** yalnız etkin masaüstünün kendi ayar arka ucunu kullanır. Diğer kabukların panel / widget düzenleri değiştirilmez. Aynı tercih, diğer desteklenen oturuma normal girişte uygulanabilir; açık uygulamalar oturumlar arasında taşınmaz, otomatik çıkış yapılmaz.

Ortak dosya `~/.config/oguzdows/desktop.json`, Başlat sabitlemeleri `~/.config/oguzdows/pins.ini` içindedir. Yerel ayar aracında yapılan bütün değişiklikler ortak dosyaya geri aktarılmaz; bu çift yönlü, sürekli bir eşitleme servisi değildir. Daha önce kurulmuş v1.1 sistemi Git deposundaki dosyaları kendiliğinden edinmez.

## Her kabuk kendi kimliğini korur

| Etkin masaüstü | Yerel entegrasyon | Kasıtlı sınır |
| --- | --- | --- |
| **Xfce / X11** | Tipli xfconf; kendi paneli, eklentileri ve Xfwm. Uygun kaynakta tek sahipli Picom. Picom 9 için ayrı kernel-blur reçeteleri, 12+ için geometri / yay reçeteleri. | GLX blur için hızlandırılmış doğrudan çizim ayrıca doğrulanır. Mac esintili düzenin kendi teması korunur. Başka kompozitör değiştirilmez. |
| **GNOME Shell 43/44; 45–48** | Sürümüne uygun eski / ESM yükleyici; GSettings; Shell açılır menülerinde blur; yerel Clutter geçişleri ve pencere yerleştirme. | Üst çubuk, Etkinlikler ve GNOME’un kendi pencere yaşam döngüsü korunur. Bütün uygulama çerçevelerine blur vaat edilmez. Yeni kurulan uzantı için normal yeniden giriş gerekebilir. |
| **Plasma / KWin 5 ve 6** | KConfig 5/6, canlı Qt paleti bildirimi, Plasma yüzeyleri, yerel KWin scripted effect ve kurulu Aurorae üzerinde üretilen cam kenarlar. | Plasmoidler / paneller yeniden kurulmaz. Aurorae yoksa kişisel dekorasyon korunur. CSD uygulamalar kendi blur bölgesini bildirmelidir. |

Gövde yazıları, başlık metni, simgeler ve kapatma kontrolleri bütün pencereye alfa uygulanarak soldurulmaz; cam yalnız uygun arka plan / çerçeve yüzeylerinde kullanılır. GTK4/libadwaita ve kendi temasını kullanan üçüncü taraf uygulamaların tüm renkleri zorlanmaz. GNOME’da **43.9 ve 48.7**, KWin’de **5 ve 6** gerçek özel kabuk testinden geçti; bu, aradaki her GNOME sürümünün ayrı ayrı test edildiği anlamına gelmez.

Masaüstü Merkezi → **Yerel araçlar**, etkin kabuğun görünüm, ekran, klavye kısayolu, pencere yönetimi, panel / widget ve bildirim araçlarını çağırır. Eksik GNOME aracı yerine Xfce paneli başlatılmaz. GNOME uzantısı, Plasma plasmoidi ve Xfce panel eklentisi birbirinin sürecine yüklenmez. Modern Başlat da mevcut panelin / bildirim hizmetinin yerini zorla almaz.

### Snap ve kısayollar

```sh
oguzdows-desktop --snap left
oguzdows-desktop --snap right
oguzdows-desktop --snap maximize
oguzdows-desktop --snap restore
oguzdows-desktop --snap minimize
```

Bunlar sabit işlemlerdir; serbest JavaScript veya kabuk komutu kabul edilmez. GNOME’da uzantının yerel pencere API’si, KWin 5/6’da sabit Snap köprüsü, Xfce’de EWMH kullanılır. KWin köprüsü `oguzdows-snap-v1` adını ve `OguzDows Snap …` eylemlerini kullanır; **varsayılan tuş atamaz**. İstersen komutları kendi masaüstünün kısayol düzenleyicisine ekle; mevcut kişisel bağlar otomatik ezilmez.

Yinelenen sol / sağ / büyüt / geri al işlemleri toggle gibi tersine dönmez. GNOME ve KWin testinde asıl çerçeve en çok 2px toleransla geri geldi. **Snap işlemi** ile **Snap animasyonu** ayrıdır: animasyon ayrıca açık yay / destekli API ister; Xfce/Picom geometri animasyonu elle sürüklemeyi de etkileyebildiğinden deneysel ve varsayılan kapalıdır.

## Kaynak koruması

- **≤2 GiB, ARMv6, güvenli grafik / nomodeset veya tanınmayan grafik sürücüsü:** yeni blur / yay kapalı, statik görünüm. Aynı uygulamalar ve masaüstü düzeni kalır; ağır bir kabuk kendiliğinden kurulmaz.
- Xfce’de gerçek blur için kaynak politikasına ek olarak tek seferlik, süre sınırlı `glxinfo -B` denetimi gerekir. `llvmpipe` / `softpipe` / yazılım rasterizer veya bilinmeyen sonuç hızlandırılmış GPU sayılmaz. Picom 9–11’de yay API’si varmış gibi davranılmaz; 12+ gerekir.
- **Azaltılmış hareket** önceliklidir. GNOME’un etkin animasyon ayarı ve yerel kabuk kısıtları dikkate alınır. Wayland’ın zorunlu kompozitörü kapatılmaz.
- Kendi motoru açılamazsa sınırlı, sabit bir hafif fallback denenir; sonsuz yeniden başlatma döngüsü veya kalıcı Python efekt denetleyicisi yoktur. Aynı çalışan Picom reçetesi tekrar kullanılır.

Bu kapılar **ölçülmüş FPS / pil / RAM kazancı değildir**. Yayınlanmış v1.1 boşta Xfce RAM sayıları yeni GNOME / Plasma / blur açık oturumlara mal edilmez.

## Geri alma ve hata durumu

**Masaüstü Merkezi → Bu masaüstünün önceki ayarlarını geri al…** veya `oguzdows-desktop --restore`:

- **GNOME / Plasma:** `~/.local/state/oguzdows/desktop/` altında izinli anahtar başına ilk değer ve son uygulanan değer tutulur. Yalnız hâlâ bizim son değerimiz duran anahtar geri alınır; sonradan kişisel araçla değişenler korunup kullanıcıya bildirilir. Duvar kâğıdı da bu arka uçların günlüğündedir. Eksik geri alma sessiz başarı sayılmaz; kurtarma satırları korunur.
- **Xfce:** `~/.local/state/oguzdows/profiles/before-first-change.json` içindeki ilk **tipli görünüm / panel yedeği** kullanılır. Bu açık tam profil geri alma, sonradan değişmiş yönetilen görünüm anahtarlarını da eskiye döndürebilir; GNOME/Plasma karşılaştırmalı geri almasıyla aynı değildir. Duvar kâğıdı bu profil yedeğinin parçası değildir; galeri veya Xfce’nin yerel aracıyla ayrıca seçilir. Paneli hemen yenilemek ayrı onaylı işlemdir, açık uygulamalar kapanmaz.

Başarısız bir **tercih uygulamasının geri sarılması**, yukarıdaki açık profil sıfırlamasından ayrıdır. Yeni kaynakta:

- Native ayarlar önce uygulanıp geri okunur; ortak tercih dosyası en son görünür olur. Son JSON kaydı başarısızsa varsayılan tema tahmini değil, işlemin tam önceki değerleri geri alınır.
- Xfce duvar kâğıdı / görüntü stili bütün yönetilen monitörlerde doğrulanır. İlk uygulamanın kısmi hatası ve seçim dosyası hatası da geri sarılır. Sonradan haricen değişen anahtarlar ezilmez; bir geri alma arızası diğer bağımsız anahtarların denenmesini engellemez.
- Picom geri sarması PID doğum zamanı / kullanıcı / sabit argv / X11 seçim sahipliğini denetler. Yalnız işlemin kendi motoru durdurulur; önceki çalışan **izinli reçete** gerekirse kaynak kapısından geçirilerek yeniden açılır. Eski PID’nin aynı kalması vaat edilmez. Motor durmazsa sahiplik kaydı korunur, ikinci motor açılmaz; başka kompozitörün süreci öldürülmez.
- Ortak kilit eşzamanlı uygulamayı reddeder. Kurucu / sürücü işlemi sırasında yeni görünüm işi başlatılmaz. Arka plan işçisi başlatılamasa veya zaman aşımına uğrasa bile ayar düğmeleri kalıcı kilitli bırakılmaz.

İşlem eksik geri alma uyarısı verirse günlüğü silerek veya başka kullanıcının süreçlerini öldürerek düzeltmeye çalışmayın. Mesajı ve `oguzdows-desktop --status` çıktısını, kişisel yolları ayıklayarak hata kaydına ekleyin. Bu araç bir disk / önyükleme onarıcısı değildir.

## Canlı grafikler ve Başlat

**Performans** C/GTK/Cairo’dur; HTML/WebView veya rastgele çizilmiş demo verisi yoktur:

- CPU: `/proc/stat` sayaç farkı; RAM: `/proc/meminfo` kullanılabilir bellek hariç kullanım; ağ: `/proc/net/dev`, loopback hariç alım / gönderim farkı ve geçen gerçek süre.
- Sabit **90 örnek** halka, normalde **1 saniye**, ≤2 GiB’de **2 saniye** aralık. İlk fark veya geçersiz sayaç sıfır yük gibi uydurulmaz. Ağda iki çizgi ve otomatik ölçek vardır.
- Gizli / küçültülmüş pencerede, tam örtülme bildirildiğinde, duraklatmada ve performans dışı sayfada zamanlayıcı durur. Süreç listesi yalnız **Yenile** ile okunur; RSS toplamı fiziksel RAM toplamı diye sunulmaz. Süreç öldürme / root işlemi yoktur.

**Başlat** gerçek `GAppInfo` kataloğunu, Türkçe karakterleri kapsayan aramayı ve kullanıcı sabitlemelerini kullanır. Bir uygulama seçilirse `Exec` metni elle kabuğa verilmez; Gio başlatma API’si kullanılır. Ağ / pil durumu mevcut servislerden alınır; eksik donanım servisleri otomatik başlatılmaz. Ses sorgusu kısa ömürlü ve süre sınırlıdır. Başarılı başlatmada kısa sesli geri bildirim ayrıca opt-in’dir. Bunlar yeni sürekli açılış servisleri değildir.

## Doğrulama kaydı — kaynak `39e5f9a`

| Katman | Doğrulanan | Sonuç / kaynak |
| --- | --- | --- |
| **Kaynak / birim / varlık** | Python, Node/vm API sözleşmeleri, tipli ayarlar / rollback, native sayaç fixture’ları, görsel / şema sözleşmeleri. | **532 test, 8 bağımlılık/ortam atlaması; başarılı**, ResourceWarning ölümcül. Bu satır gerçek kompozitör kanıtı değildir. |
| **Gerçek GTK ve ayar API’leri** | Hedef tabanda derlenmiş C Başlat / Performans; 360×800 ve 1024×768; gerçek GSettings / KConfig; sahte son dosya hatasından geri alma ve işçi yaşam döngüsü. | [Masaüstü CI 45426010752](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45426010752), bookworm / trixie **2/2 başarılı**. Başlat smoke’u uygulama çalıştırmaz. |
| **Gerçek GNOME Shell** | **43.9 ve 48.7** uzantı yükleme; menü blur efekti; yerel kritik sönümlü geçişler; yinelenen Snap / tam çerçeve geri dönüşü; düşük bütçe ve disable/enable temizliği. | Aynı masaüstü CI, GNOME **2/2 başarılı**. Geçiş sayacı 43.9’da **27**, 48.7’de **28**; yalnız gerçek callback bağlanması, FPS ölçümü değil. |
| **Gerçek Plasma / KWin** | **5 ve 6** blur / özel efekt / Aurorae; canlı Qt paleti; panel kimliği korunması; açılış ve Snap geçiş callback’leri; yinelenen Snap / tam çerçeve geri dönüşü. | Aynı masaüstü CI, KDE **2/2 başarılı**. `transition-attached`, `transition-completed`, `snap-transition-attached` üçünün de zorunlu kontrolü geçti. |
| **Gerçek Picom / ARGB pikselleri** | Picom **9.1’de 3**, **12.5’te 7** sabit reçete; parser / GLX shader / seçim sahipliği ve ARGB test yüzeyinin arka plan bulanıklığı. | Aynı masaüstü CI. Örnek standart sapma: bulanıksız **89,5**; 9.1 blur **1,5**, 12.5 blur **0,696**. Bu özel desen ölçümü, masaüstü FPS / görsel kalite puanı değildir. |
| **Gerçek Xfce / XRender / geri alma** | **4.18.2 ve 4.20.4**, üç çözünürlükte altı düzen; ilk tipli yedeğin geri okunması ve geri alma sonrası gerçek panel geometrisi. Picom reçetesi + xfconf’un sahte JSON hatasından ve gerçek kısmi duvar kâğıdı yazısının enjekte hatadan geri dönüşü. | [PC doğrulama 45426010919](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45426010919), iki taban / iki firmware kontrolü **başarılı**; ISO üretimi **atlandı**. Duvar kâğıdı testi gerçek xfconfd kullanır ama xfdesktop render testi değildir. |
| **Pi yapılandırması** | Mevcut kaynak / güvenlik / paket sözleşmeleri. | [Pi 45426010713](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45426010713) **başarılı**; yeni SD/USB imajı üretimi **atlandı**. |

### Bu CI’ın ispatlamadığı şeyler

Gerçek kabuklar **özel, non-root X11/Xvfb, yazılım Mesa GPU, boş özel sistem D-Bus’u ve taklit kaynak bütçesiyle** çalışır. Logind / giriş yöneticisi / fiziksel GPU hizmetleri yoktur. Yazılım GPU’da yerel animasyon kodunu sınamak için **yalnız testte** KWin `KWIN_EFFECTS_FORCE_ANIMATIONS`, GNOME 48 yerel `--force-animations`, GNOME 43 ise ayrı ve bir kez çalışan özel fixture uzantısı kullanır. Bunlar üretim paketine bir GPU koruması bypass’ı olarak eklenmez. Picom reçeteleri test tarafından doğrudan açılır; üretim GLX denetimi bu ortamı hâlâ `accelerated: false` görür. Picom 9’un vsync istisnası da yalnız özel testtedir.

**Wayland, fiziksel PC/Pi, çoklu gerçek ekran / HiDPI, gerçek GPU’da akıcılık / FPS / pil / bellek farkı ve gerçek giriş oturumu hâlâ ayrı doğrulama ister.** GNOME / KWin’de efektin bağlanması, bütün uygulamalarda aynı görsel sonucu veya Gala/Aero ile birebir eşdeğerliği kanıtlamaz. Pi Zero / Zero W’nin hesap sonrası siyah ekran bildirimi [hâlâ açıktır](PI-ZERO-OTURUM.md).

Ham PNG / JSON / günlükler ilgili CI artefaktlarındadır; masaüstü iş akışının saklama süresi **14 gün**dür. Kalıcı küçük özet, tam kaynak ve iş kimlikleri [bu kanıt kaydında](evidence/native-desktop-39e5f9a.json) tutulur. [Yayımlanmış v1.1 kanıtı](V1.1-TEST-KANITI.md) bunlardan ayrı kalır.
