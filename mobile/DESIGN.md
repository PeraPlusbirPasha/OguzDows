# OğuzDows Mobile · ürün ve sistem tasarımı

## 1. Ürün kararı

**Ad:** OğuzDows Mobile. **Söz:** “Cebinde, senden bir dünya.”

Günlük arayüz OğuzDows adıyla konuşur; platform adının her karta basılması gerekmez. Ancak **Android/AOSP teknik kimliği, üçüncü taraf telif/lisansları, güvenlik uyarıları, izin sayfaları ve gerçek sürüm bilgisi gizlenmez veya başka bir ürünmüş gibi sahteleştirilmez.** Teknik temel Hakkında/geliştirici/yasal sayfalarında görünür kalır. PC/Pi’nin Debian kimliğini telefonun teknik kimliği yerine geçirmek yoktur.

Bu aşamadaki çıktılar:

1. Gerçek davranışları ve sınırları görülebilen, dokunmatik/klavye uyumlu web tasarımı.
2. Bağımsız yerel HOME/varsayılan yardımcı başlangıç kaynakları; **derlenmemiştir**.
3. Özellik eşleme ve ROM’a geçiş kapıları. ROM, GSI, boot/vendor imajı veya sertifikalı cihaz yayını **yoktur**.

## 2. Görsel dil

- **Boğaz / bakır / mürdüm:** sakin deniz yeşili ana vurgu, sıcak kırık beyaz yüzeyler, mavi-gece karşılığı. Üç vurgu seçimi ortak yerel ekranlara uygulanır.
- **Türkçe, doğal, kısa:** “Günüm”, “Defter”, “Atölye”, “Koleksiyon”, “Birlikte düşünelim”. İzin ve hata dili süslü ifadelerin arkasına saklanmaz.
- **Nazar boncuğu:** güç kimliği için lacivert dış halka, krem/mavi merkez ve küçük güç çizgisi. Pil düzeyi varsa erişilebilir yüzde metni de bulunur; renk tek bilgi taşıyıcısı değildir. Webdeki 86 örnektir, yerel kaynak gerçek pil değerini okumayı hedefler.
- **Rıfkı:** mevcut bir gözü mavi/bir gözü kehribar kedi. Yeni bir küre veya başka şirketin asistanı değil, ürünün tanıdık kişiliği. Özel bilgi bilen bir kişi, insan operatör veya gizlice çalışan model gibi davranmaz.
- **Dokunma hissi:** basılı/yükselmiş geri bildirim yalnız transform ve küçük renk/gölge geçişidir. Titreşim varsayılan değildir; platform uygulamasında ayrıca kullanıcı tercihi ve donanım sınaması ister.
- **Yoğunluk:** konfor/kompakt; büyük font ve ekran okuyucu native kabul kapısıdır. Android tarafında en az 48 dp eylem hedefi, sistem font ölçeği, kenar boşluğu/cutout ve gesture inset’leri esas alınır.
- **Hareket:** açılan sayfa/panelde sınırlı 160–280 ms geçiş. Düşük kaynak, düşük güç veya azaltılmış hareket tercihinde statik. Sürekli kedi/duvar kâğıdı/arka plan animasyonu yok.

## 3. Etkileşim haritası

| Yüzey                | Davranış                                                  | Yetki sınırı                                                                                                               |
| -------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Ana ekran            | Kültür manzarası, uygulamalar, Rıfkı kartı, arama/çekmece | Webde yalnız önizleme envanteri; native gerçek launcher intent’leri                                                        |
| Hızlı ayarlar        | Wi-Fi/Bluetooth/uçak/odak/görünüm                         | Webde radyo/DND örnektir; ses gerçek önizleme medyasına, parlaklık UI karartmaya uygulanır. Native sistem paneline aktarır |
| Nazar güç menüsü     | Güç/pil kimliği, kilit ve kapatma tasarımı                | Normal başlatıcı cihazı kapatamaz. Gerçek menu SystemUI/platform imzası ve cihaz politikası gerektirir                     |
| Rıfkı                | Metin, önerilen sabit eylem, ayrı onay                    | Model bir araç çalıştıramaz. Her riskli gerçek işlem sistem arayüzüne gider                                                |
| Mağaza               | Kaynağı gör, izinleri incele, kullanıcı seçimi            | “Düğmeye basıldı” başarı değildir; sistemin kurulum sonucu okunur                                                          |
| Atölye               | 16 masaüstü aracının mobil karşılığı                      | Genel dosya/pano tarama yok; kullanıcı seçili URI ve sınırlı işler                                                         |
| Haber                | Görsel seçki, tıklanabilir okuma, kaydet/okundu/TXT       | Web özgün örnek içerik; canlı ağ verisi gibi gösterilmez                                                                   |
| Ayarlar              | Ortak tema/yoğunluk/vurgu/hareket                         | Başka uygulamaların tüm iç ekranları veya cihaz teması zorla değişmez                                                      |
| Dosyalar             | Belge seç → sınırları incele → açık eylem                 | SAF/fotoğraf seçici; MANAGE_EXTERNAL_STORAGE yok                                                                           |
| Telefon/mesaj/kamera | Platformun uygun uygulamasına devret                      | Gerçek modem, acil arama ve kamera HAL’i bir launcher tasarımıyla uygulanmış sayılmaz                                      |

Tarayıcıda telefon çerçevesi ve çevresindeki tasarım laboratuvarı büyük ekran içindir; küçük ekranda dış çerçeve/yan sütunlar gizlenir. Geri/home/çıkış kontrolleri, klavye odak görünümü, Escape ve modal odak döngüsü vardır. Uygulamalar yalnız açıldığında oluşturulur.

## 4. Rıfkı, varsayılan etkileşimli yardımcı

### Katmanlar

```text
Kullanıcı yazısı / açık UI eylemi
         │
         ├── Yerel rehber: sınırlı, deterministik, ağsız
         │       └── yalnız sabit eylem önerisi → kullanıcı düğmesi → UI değişimi
         │
         └── Üretken model: varsayılan kapalı
                 └── gönderim onayı → sunucu köprüsü → seçilen yerel/uzak model
                           └── yalnız metin; shell/cihaz/dosya araçları YOK
```

Model olmadan genel amaçlı AI varmış gibi cevap/typing simülasyonu yapılmaz. Model bağlanınca sağlayıcının görünen adı ve veri gönderim durumu değişir; eski yerel konuşma taşınmaz. Model hatası açıklanır, başarılı yanıt uydurulmaz. Rıfkı hiçbir zaman “uygulamayı kurdum/mesajı gönderdim” diyerek yapılmayan sistem işi için başarı üretmemelidir; model çıktısı güvenilmeyen metindir, eylem değildir.

### Yerel varsayılan yardımcı yolu

- `VoiceInteractionService` + `VoiceInteractionSessionService`, imza düzeyli `BIND_VOICE_INTERACTION` kapısıyla yalnız sistem tarafından bağlanır.
- `RoleManager.ROLE_ASSISTANT` **kullanıcının açık seçimiyle** istenir. Mevcut yardımcı zorla kaldırılmaz, varsayılan sessizce değiştirilmez.
- Başlangıç iskeleti metin tabanlıdır. Mikrofon/hotword izni yoktur; ekran metni ve screenshot bağlamı `setDisabledShowContext` ile kapatılır.
- Yardımcı rolü seçilirse platform hafif servis bileşenini bağlı tutabilir; bu, web önizlemesinin “servis yok” davranışıyla karıştırılmaz. Sürekli inference veya dinleme işçisi başlatılmaz.
- Sesli giriş/çıkış, çevrimdışı Türkçe ASR/TTS, konuşmayı kesme, sesli erişilebilirlik ve Bluetooth ses rotası sonraki cihaz aşamasıdır. Mevcut 11 masaüstü anlatım kaydının bulunması bunları sağlamaz.
- Native iskelette üretken köprü henüz bağlı değildir. APK/varsayılan yardımcı/emülatör testi yapılmadı; kaynak sözleşmesi gerçek çalışma kanıtı yerine geçmez.

### Gizlilik varsayılanı

Sohbet bellekte; mesajlar cihazda/sunucuda otomatik arşivlenmez. Kişiler, takvim, bildirimler, ekran, pano ve konum varsayılan bağlam değildir. Her yeni veri türü ayrı kapsam ve izin ister. Bulut sağlayıcı saklama politikası ayrıca gösterilmeli; “yerel” etiketi uzak modele takılamaz. Token/istem/yanıt hataları loglanmaz; üretimde oturum, hız/kota ve denetlenebilir gizlilik politikası gerekir.

## 5. Google ve APK desteği birbirinden farklıdır

### APK

Gerçek mobil sistemin hedefi **yerel platform PackageManager/PackageInstaller** üzerindedir; Waydroid/container değildir. ABI, minSdk/target davranışı, split APK, imza güncelleme zinciri, kaynak izni, kurumsal politika ve sistem onayı korunur. Aynı uygulamanın bütün APK’ları veya x86 ikili kodu ARM64’te çalışacak denmez.

Başlangıç iskeleti: kullanıcı belge seçer → en çok 32 MiB özel kopya/gerçek SHA-256 → paket/API/ABI/bildirilen izinler/sertifika özeti → uygun görünüyorsa açık inceleme onayı → FileProvider ile **aynı özel kopya** → gerçek sistem yükleyicisi. Kaynak izni kapalıysa kullanıcı ayara gider; dönüşte otomatik kurulum yapılmaz. APK’yi seçmek kurmaz. Sertifika özeti “güvenilir geliştirici” veya malware taraması değildir. APK imzasının nihai denetimi sistemde kalır. XAPK/APKS/split paketler bu iskelette desteklenmez; 32 MiB sınırı tasarım iskeletine aittir, hedef işletim sisteminin genel paket sınırı değildir.

Gerçek sürümde async kurulum sonucu, güncelleme/iptal/başarısızlık, paylaşımlı kullanıcı/bozuk split setleri ve dosya sağlayıcı yarışları özel test ister. Otomatik kaynak izni, sessiz root kurulum, imza atlama veya paket kimliği taklidi yoktur.

### Google

- Web kısayolları, mevcut tarayıcı ile kullanılabilir; önizlemede çalışan kısım budur.
- Cihazda zaten kurulu/başlatılabilir Google uygulamaları normal paket listesi üzerinden açılır.
- **Play Store/GMS dağıtımı** açık kaynak AOSP ile aynı şey değildir. Uygun lisans, cihaz sertifikası ve ilgili uyumluluk süreci olmadan paketlenmez. CTS geçmek tek başına GMS dağıtım hakkı vermez.
- Play Integrity, banka, e-Devlet, anti-cheat, Widevine/HD içerik, yedekleme veya satın almalar garanti edilmez; imza/cihaz taklidi önerilmez.
- microG ayrı, uygulamaya bağlı uyumluluk tercihidir; Google onaylı GMS diye sunulmaz ve bu çalışmada uygulanmadı. Signature spoofing otomatik eklenmez.
- Hesap girişini OğuzDows web formu toplamaz. Sistem AccountManager/sağlayıcının onaylı OAuth akışı veya resmî web sayfası kullanılmalıdır.

## 6. OğuzDows özellik mirası

[`feature-parity.json`](feature-parity.json) makinece okunabilir kaynaktır: **16 Atölye + 7 Mağaza/Haber/palet işlevi** ve kültür, nazar, Rıfkı, görünüm, cihaz/uyumluluk, İmece/Heybe, odak, güncelleme ve masaüstü davranışlarının durumunu ayrı gösterir.

“Yansıtmak” aynı PC ikilisini telefona kopyalamak değildir:

- APT/Flatpak/GNOME Software → kaynak/izin/kurulum şeffaflığı ve sistem paket yükleyicisi. Debian deposu telefona eklenmez.
- Xfce/GNOME/Plasma tarzları → dokunmatik düzen aileleri, launcher yoğunluğu, tablet/split-screen; gerçek masaüstü oturumları varmış gibi gösterilmez.
- PrintScreen → sistem screenshot kısayolu; programatik MediaProjection varsa her oturum sistem onayı. Arka planda ekran okuma yok.
- Başlangıç yöneticisi → platformun pil/uygulama izin sayfaları. Üçüncü taraf uygulamanın servis politikası normal launcher yetkisiyle değiştirilemez.
- Sürücü ve güncelleyici → cihaz özel vendor/kernel ve imzalı OTA. GRUB/DKMS/Calamares telefona taşınmaz.
- EXE/Wine ve PC/Pi boot imajları → bu mobil sürümün çalıştırma/kurulum özelliği değildir.
- 20 kültür görseli, 11 Rıfkı anlatımı, İmece/Heybe ve altı düzenin tamamı henüz native mobilde yoktur; webdeki dört görsel bunların tamamlanmış portu sayılmaz.

## 7. Sistem mimarisi ve yetki ayrımı

```text
Cihaz özel AOSP temeli ─ kernel + vendor HAL + firmware + güvenli boot
   ├─ Framework / SystemUI (ayrı sistem yetkisi, device-specific test)
   │    ├─ Nazar pil/güç menüsü, kilit, screenshot, hızlı ayarlar
   │    └─ telephony/camera/biometric/permission controller
   ├─ OğuzDows Home (normal app / seçilebilir HOME rolü)
   │    └─ uygulamalar, kültür, yerel araçlar, görünüm
   ├─ Rıfkı (kullanıcı seçili yardımcı rolü)
   │    ├─ metin rehberi / ayrı, açık model bağlantısı
   │    └─ hiçbir genel root veya serbest shell aracı yok
   ├─ Mağaza / kaynak incelemesi → sistem PackageInstaller
   └─ Google katmanı (ancak lisans ve cihaz sertifikası varsa)
```

Root, `priv-app` veya platform imzası normal launcher’a topluca verilmez. SystemUI değişikliği ayrı modülde, en az yetkiyle ve tam cihaz ağacı üzerinde yapılır. İzin denetçisi devre dışı bırakılmaz; SELinux enforcing, FBE, AVB, Verified Boot ve imzalı OTA hedeflenir. Güncelleme anahtarları depoya/chat’e konmaz; ayrı güvenli imzalama altyapısı gerekir. Bir prototipin varlığı bunların uygulanmış olduğunu kanıtlamaz.

## 8. Kaynak bütçesi

Önizleme: tek React kökü; 16 araç sayfası/okuyucu/sohbet yalnız açıldığında oluşturulur. Pano/ekran dinleyicisi, canlı feed, analytics, push, servis worker veya sürekli animasyon yoktur. Dünya saatleri yalnız görünürken dakikada bir yenilenir. Dosya hash’i açık istek, bir dosya, 32 MiB sınırıyla yapılır. Düşük güçte dock blur/gölge/geçişler kaldırılır. Kullanılmayan kamera akışı yoktur; sistem seçicisi kullanılır.

Ölçülebilir web hedefi: başlangıç JS gzip ≤110 KiB; kendinden sunulan fontlar ve küçük WebP’ler; başlangıçta üçüncü tarafa ağ isteği yok. Bunlar telefon RAM/FPS/pil garantisi değildir. Native model belleği modele, quantization’a ve SoC hızlandırmasına bağlıdır; cihaz seçmeden “2 GB’da LLM çalışır” veya “600 MB tüm sistem” sözü verilmez.

Native başlangıç: tek I/O işçisi, en çok 250 başlatılabilir uygulama, 32 MiB APK kopyası, cache’te en çok 3 kopya (24 saatten eski kopyalar yeni incelemede temizlenir), 64 KiB kopyalama bloğu, 10000 arşiv girdisi, 16 KiB not sınırı. Bunlar kaynak-kod sınırlarıdır; çalışma/timeout/ANR kanıtı değildir. Sonraki yerel uygulamada yavaş/kötü niyetli belge sağlayıcısı ve işlem iptali ayrıca test edilmelidir.

## 9. İlk ROM için kabul kapıları

1. **Tam marka/model/kod adı** ve mevcut yazılım/vendor sürümü; SoC/ABI tek başına yetmez.
2. Bootloader politikası, garanti/DRM etkisi, veri yedeği, çalışan stok geri dönüş yolu. Otomatik unlock/flash/relock yok.
3. Dağıtılabilir kernel/device/vendor ağaçları ve firmware lisansları. GSI/Treble uygunluğu ayrıca doğrulanır; evrensel telefon ROM’u sözü verilmez.
4. AVB/şifreleme/SELinux enforcing, imzalama anahtarları, OTA ve anti-rollback/geri kurtarma tasarımı.
5. Gerçek cihazda ekran/dokunma/GPU/kamera/ses/SIM/arama/SMS/acil arama/Wi-Fi/Bluetooth/GPS/NFC/parmak izi.
6. Uyku/uyanma, şarj/termal, düşük bellek, ölçülmüş RAM/FPS/pil, büyük font ve erişilebilirlik.
7. Native APK derlemesi, emülatör UI, sistem yükleyici ve yardımcı rolünün baştan sona sınanması. CTS/VTS/CDD kapsamı; varsa GMS lisans/sertifika.
8. Rıfkı için gerçek provider testi, açık izin, veri saklama, prompt injection/yetki sınırı ve ağ kesilmesi senaryoları.

Henüz hiçbir telefon “destekleniyor” listesine eklenmez. Başarılı web/manifest testi, fiziksel boot/modem/ROM testi değildir. PC/Pi v1.2 kanıtları da bu kapıların yerine kullanılamaz.

## 10. Günlük deneyim genişletmesi

20 yerel uygulama girişi ve üç gerçek ana ekran sayfası vardır. Uygulama çekmecesi yukarı; denetim merkezi yalnız üst kenardan aşağı kaydırmayla açılır. Yatay hareket yalnız ana ekranda sayfa değiştirir. Form alanları, kaydırıcılar ve uygulama içi normal kaydırma launcher hareketi olarak yorumlanmaz. Aynı akışların düğme/klavye karşılığı da vardır.

Birleşik arama cihazın tamamını veya başka uygulamaların verilerini taramaz: bu origin’de elle oluşturulan kişiler, notlar, görevler, uygulama/araç/katalog sabitleri içinde çalışır. Web araması ayrı, açık dış bağlantıdır. Kişi ve SMS taslağı hassas olabilir; mevcut `localStorage` şifrelenmemiştir. Bulut eşitlemesi, kişi yükleme ve SMS okuma yoktur.

Telefon `tel:`, Mesajlar `sms:` işleyicisine devreder. Sıradan numaralar (isteğe bağlı +, 3–20 rakam) dışında URI parametresi, kontrol karakteri veya USSD aktarılmaz. SMS gövdesi 2000 karakterle sınırlı ve URL-kodludur. Çağrı bağlandı/mesaj gönderildi sonucu çıkarılmaz. Native kaynak aynı sınırı `ACTION_DIAL` ve `ACTION_SENDTO` / `smsto:` ile uygular; `CALL_PHONE`, `SEND_SMS`, `WRITE_SETTINGS` yetkisi istemez. Sistem ses/Wi-Fi panelleri ve standart günlük uygulama intent’leri kullanıcıya devredilir; bu yollar derlenmedi/cihazda denenmedi.

Takvim en çok 80 yerel plan tutar. Sayaç/kronometre başlangıcı zaman damgasıyla saklanır; sayfa gizliyken interval durur, geri gelince saat farkından hesaplanır. Sayaç tamamlanınca ekran interval’i de durur. Bu bir sistem alarmı, arka plan ses servisi veya bildirim garantisi değildir. Kronometre 24 saat, sayaç 1–180 dakika; tur listesi yalnız açık ekrandadır.

Ses kaydırıcısı ve sessiz durumu gerçek HTML audio öğesine uygulanır. Müzik dosyası açık seçimle, tek dosya/32 MiB sınırıyla alınır; arka planda ağdan müzik çekilmez. Galeri en çok 6 kullanıcı seçili fotoğrafı (8 MiB/dosya) geçici object URL’lerle gösterir; sayfa kapanınca URL’ler bırakılır. Orijinal bayt indirme fotoğraf dönüşümü/EXIF temizliği değildir. Görsel karartma donanım parlaklığı değildir. Sistem radyoları/DND anahtarları halen örnektir.

24 mağaza sembolü yerel SVG’dir (toplam yaklaşık 27.6 kB); gizli hotlink/CDN bağımlılığı yoktur. Geliştirici/Play kaynak sayfaları ayrı açılır, indirme/kurulum sonucu taklit edilmez. [Simge köken/lisans manifesti](ASSETS.md) F-Droid’ın CC BY-SA istisnasını ayrıca korur. Günlük uygulama modülü dinamik yüklenir; başlangıç JS için 110 KiB gzip bütçesi korunur. Bu telefon RAM/pil/FPS ölçümü değildir.
