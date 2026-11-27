# OğuzDows Mobile · ürün, mimari ve kabul kapıları

Bu belge mevcut APK/tarayıcı mimarisini anlatır. **Gelecek sürümün** Kotlin/Compose Aero kabuğu, bulut ağırlıklı Rıfkı, koşullu wake-word, sistem yardımcı yüzeyi ve arayan profilleri için [yeni yol haritası](ROADMAP.md) geçerlidir. Oradaki yeni yetenekler burada uygulanmış sayılmaz.

## 1. Ürün ve kapsam

**OğuzDows Mobile — “Cebinde, senden bir dünya.”** Türkçe kimlik, nazar boncuğu güç simgesi, Rıfkı kedi rehberi, kültür koleksiyonu, Atölye, Mağaza ve Haber aynı dokunmatik deneyimde buluşur.

Günlük UI’da ürün adı OğuzDows’tur. **Android/AOSP teknik kimliği, izin ekranları, güvenlik uyarıları, gerçek sürüm bilgisi ve üçüncü taraf lisansları gizlenmez.** PC/Pi’nin Debian/ISO kimliği telefona taklit edilmez.

Üç farklı çıktı birbirine karıştırılmaz:

1. **Tarayıcı laboratuvarı:** etkileşimli ve yerel verili tasarım; SIM/APK kurulum yetkisi yok.
2. **`0.2.0-emulator` APK:** aynı zengin arayüz + gerçek platform servisleri; derleme/çalışma kanıtı [VERIFICATION.md](VERIFICATION.md) içinde. Normal uygulama ve kullanıcı seçili roller; root/platform imzası değil.
3. **Cihaz özel işletim sistemi:** henüz yok. Boot/vendor/ROM/OTA/GSI ve tüm uygulamalarla uyumluluk bir APK üretildi diye tamamlanmış sayılmaz. Evrensel telefon ISO’su vaat edilmez.

Kullanıcının seçtiği ilk kabul hedefi **emülatörde, telefonun içinde OğuzDows’tan arama/SMS**’tir; eşleştirilmiş telefona webden uzaktan kumanda değildir. Fiziksel model/kod adı ve bootloader politikası henüz bilinmiyor.

## 2. Görsel dil ve etkileşim

- Deniz yeşili/bakır/mürdüm vurgu, sıcak açık yüzeyler ve gece mavisi; ortak konfor/kompakt ve azaltılmış hareket tercihleri.
- Nazar boncuğu güç/pil kimliğidir; erişilebilir metin ve yüzde bulunur. Webde pil/saat örnektir; APK sistem değerlerini okur. Normal uygulama kilit/kapatma başarısı uydurmaz; fiziksel menü/pil ayarını açıklar.
- Rıfkı mevcut bir gözü mavi/bir gözü kehribar kedidir; başka şirketin asistanı, gizli çalışan model veya insan operatör gibi sunulmaz.
- 20 arayüz girişi; üç gerçek ana sayfa, yatay kaydırma/noktalar, yukarı çekmece, yalnız üst kenardan aşağı denetim merkezi. Formlar/slider/normal sayfa kaydırması hareket çalmaz. Düğme/klavye karşılığı ve modal odak/Escape vardır.
- Küçük ekranda çerçeve/yan sütunlar kaybolur; APK’da tüm boyutlarda laboratuvar çerçevesi kaldırılır. Insets/cutout/IME platformdan uygulanır.
- Basış geri bildirimi transform/renk ve yerel ripple ile sınırlıdır. Sürekli kedi/duvar kâğıdı animasyonu yok; hafif profil, uygulama ve sistem `prefers-reduced-motion` geçişleri kapatır. Yerel eylemler en az 48 dp hedefler; gerçek büyük font/ekran okuyucu doğrulaması ayrı kapıdır.
- Kendi arayüzünün açık/koyu tercihi yerel Mağaza, APK inceleme, uygulama listesi ve Rıfkı oturumunda da okunur. Başka üreticinin uygulamasının teması zorla değiştirilmez.

## 3. Yüzey ve yetki haritası

| Yüzey | Tarayıcı | Yerel APK |
| --- | --- | --- |
| Telefon | Güvenli `tel:` aktarımı, bağlı çağrı taklidi yok | Kullanıcı seçili Telefon rolü + izin + yerel ücret onayı → Telecom/InCallService ve OğuzDows görüşme UI’sı |
| Mesajlar | Kalıcı taslak + güvenli `sms:` aktarımı | Kullanıcı seçili SMS rolü + izin/abonelik + ikinci onay → SmsManager; sistem sağlayıcısından geçmiş/gerçek geri bildirim |
| Mağaza | 24 yerel marka kartı, istek listesi, resmî kaynak/Play bağlantıları | Ayrıca imzalı canlı F-Droid kataloğu, API/ABI seçimi, hash doğrulaması, görünür sürüm karşılaştırması, onaylı sistem yükleyicisi |
| Denetim | Gerçek HTML medya sesi ve UI karartması; radyo örnek | AudioManager medya sesi, uygulama pencere parlaklığı; gerçek radyo/DND sistem panelleri |
| Uygulamalar | 20 ürün içi giriş | Ayrıca gerçekten yüklü ve başlatılabilir uygulamaların en çok 250’si |
| Kişiler/takvim | Elle oluşturulan 60 kişi / 80 yerel plan | Aynı arayüz verisi; sistem rehber/takvim izni yok |
| Haber/kültür | Görsel seçki, üç özgün çevrimdışı metin, okundu/kaydet/TXT | Aynı paketlenmiş içerik; canlı haber/konum bilgisi değil |
| Dosyalar | Yalnız açık seçilen dosya/görsel | Ayrıca APK için SAF/private-copy akışı; genel depolama izni yok |
| Güç | Açıkça etiketli tasarım kilidi/kapatma | Fiziksel güç/kilit ve pil ayarı; kapatılmış/kilitlenmiş gibi gösterilmez |

## 4. Yerel güvenlik mimarisi

```text
Çevrimdışı paketlenmiş OğuzDows arayüzü
 https://appassets.androidplatform.net
          │ tam origin + ana çerçeve bağlı, sınırlandırılmış mesajlar
          ▼
 HomeActivity / AndroidX WebMessageListener
   ├─ açık rol/izin isteği (eski ücretli eylem otomatik tekrarlanmaz)
   ├─ Telecom → sistemin bağladığı InCallService → yerel görüşme ekranı
   ├─ SmsManager / korumalı SMS_DELIVER / kalıcı parça günlüğü → sistem SMS sağlayıcısı
   ├─ kullanıcı onaylı, sabit kaynaklı imzalı depo istemcisi → SQLite katalog
   ├─ özel APK incelemesi → salt okunur FileProvider → sistem yükleyicisi
   └─ sınırlı ses/parlaklık/ayar ve yüklü uygulama yolları
```

WebView uzak istekleri engeller; CSP, main-frame kontrolü, kapalı dosya erişimi ve izin reddi kullanır. Harici HTTPS site köprüden ayrılmış sistem tarayıcısında ayrı onayla açılır. `addJavascriptInterface`, serbest shell/root/exec veya uzak sayfaya yerel köprü yoktur. İstek ≤16 KiB / kimlik ≤80 karakter; istemcide en çok 12 bekleyen istek ve 180 s süre sınırı. Ücretli eylem otomatik yeniden denenmez.

İzinler açık manifestte tutulur. Mikrofon, sistem rehberi, çağrı günlüğü, tüm dosyalar, sessiz paket yükleme, `WRITE_SETTINGS`/`WRITE_SECURE_SETTINGS` ve platform/root yetkisi yoktur. Ağ izni sabit depoya açık kullanıcı onaylı native erişim içindir; arayüzden model veya analitik bağlantısı açmaz.

### Telefon/SMS doğruluğu

Numara isteğe bağlı `+` ve 3–20 rakamla sınırlıdır; USSD/servis kodu, URI parametresi ve kontrol karakteri reddedilir. Rol/izin onayından, gelen intent’ten veya sayfa yenilenmesinden otomatik çağrı/SMS çıkmaz. Acil numaralar ayrı ön yüklü sistem arayıcısı yoluna gider; emülatörde acil numara denenmez.

Çağrı `requested`, sonra gerçek Telecom durumu; JavaScript zamanlayıcısıyla bağlı gösterilmez. SMS ilk sonucu `queued`; en çok 2000 karakter/30 parça ve 5 saniyelik onay aralığı. Kalıcı parça günlüğü gerçek gönderim/teslim PDU geri bildirimlerini toplar. Kısmi başarısızlık gizlenmez; rapor yoksa teslim doğrulanmadı denir. En çok 50 sağlayıcı mesajı okunur; MMS bildirimi ayrı tutulur, **MMS/RCS uygulanmış değildir**. Deneysel SMS rolünün günlük telefonda mevcut eksiksiz mesajlaşmayı etkileyebileceği seçilmeden önce açıklanır.

## 5. Mağaza: güçlü kaynak, ayrı güven alanları

**F-Droid:** sabit birincil/resmî ayna, TLS + ayrı pinned X.509 JAR imzası, EOF/digest doğrulaması, sınırlı JSON akış ayrıştırma ve atomik SQLite import. Rollback/eski/gelecek timestamp, API/ABI/eski hedef API, `KnownVuln`, dosya boyutu/hash denetimleri vardır. Güven kökü ve değişmez upstream revizyon [android/store-trust.json](android/store-trust.json) içindedir. Keyfi depo/TOFU güveni yoktur; başarısız eşitleme eski doğrulanmış kataloğu korur.

Canlı arama en çok 80 satır; güncelleme filtresi yalnız bu eşleşmelerde görünür yüklü sürümleri karşılaştırır. Bu tüm cihaz için arka plan güncelleyici değildir. 24 web kartı canlı sürüm sonucu sayılmaz. Gerçek kurulu paket simgesi → lisanslı yerel 24 vektör → dürüst harf simgesi; gizli ikon CDN ağı yoktur.

**APK:** tek dosya ≤256 MiB özel kopya; SHA-256, paket/sürüm/minSdk/target/ABI, ilk 40 izin ve ilk imzacı özeti. İmzalı katalogdan geliyorsa paket/sürüm/hash de bağlanır. Kullanıcı incelemesi, kaynak izni ve ayrı sistem yükleyicisi onayı korunur. Ayardan dönüşte otomatik kurulum yoktur. Başarı, sistemin `RESULT_OK` sonucu **ve** yüklü sürüm/ilk imzacı eşleşmesiyle işaretlenir. XAPK/APKS/split ve tam imzacı rotasyon zinciri bu sürümün kabul edilmiş kapsamı değildir. Malware taraması/güvenilir geliştirici sertifikası iddiası yoktur.

**Google:** mevcut lisanslı Play/Google uygulamaları açılabilir, resmî web seçenekleri ayrıdır. GMS/Play dağıtımı AOSP ile aynı hak değildir; lisans/sertifika olmadan paketlenmez. CTS tek başına GMS dağıtım hakkı vermez. Play Integrity, bankacılık/e-Devlet/anti-cheat/DRM/Widevine/satın alma/yedekleme veya bütün uygulamaların çalışması garanti edilmez; kimlik/imza taklidi yapılmaz. microG bu çalışmada uygulanmadı. Google parolası OğuzDows formuyla toplanmaz.

**GNOME Software/Flatpak/APT:** PC’de anlamlıdır; Android APK çalışma zamanı, uygulama ekosistemi veya Google servisleri yerine geçmez. Telefona Debian deposu eklemek çözüm diye sunulmaz.

## 6. Rıfkı: rehber ve model farklıdır

Varsayılan Rıfkı deterministik, ağsız yerel rehberdir; yalnız sabit UI eylemini düğmeyle önerir. Genel AI cevabı/typing simülasyonu, gizli komut, gönderildi/kuruldu uydurması yoktur. Sohbet bellektedir; kişiler, pano, ekran, konum veya başka uygulama bağlamı toplanmaz.

Web geliştirme ortamında ayrıca varsayılan kapalı, **sunucuda** yapılandırılan OpenAI-uyumlu metin köprüsü bulunur. Anahtar tarayıcıya/`VITE_*`/Git’e konmaz. Sağlayıcı ve yeni gönderim onayı gösterilir; eski yerel konuşma otomatik taşınmaz. Modelin shell/araç/dosya/kurulum yetkisi yoktur. Gövde/token/süre/eşzamanlılık/hız sınırları vardır; halka açık ücretli üretim için ayrıca kimlik doğrulama, kota, TLS, kötüye kullanım ve sağlayıcı saklama politikası incelemesi gerekir. Canlı inference bu çalışmada doğrulanmadı.

APK bu uzak modeli bağlamaz; `/api/rifki/status` kapalı cevap verir. Kullanıcı isterse `ROLE_ASSISTANT` seçer. Sistem imza izniyle korunan VoiceInteractionService/session ve zorunlu recognition adresi vardır; ses açmadan kullanılamıyor cevabı verir. Ekran/assist/screenshot bağlamı kapatılmıştır; mikrofon/hotword izni yoktur. Seçili yardımcı servisini platform bağlı tutabilir; bu sürekli inference/dinleme değildir. ASR/TTS ve yardımcı rolünün OEM uçtan uca kabulü ayrı iştir.

## 7. Özellik mirası ve kaynak bütçesi

[feature-parity.json](feature-parity.json), **16 Atölye + 7 Mağaza/Haber/palet işlevini**, kimlik ve günlük telefon yollarını ayrı gösterir. 10 Atölye aracı etkileşimli/çoğunlukla kısmi; diğer 6 tamamlanmış sayılmaz. 20 kültür görseli/11 anlatım, İmece/Heybe, dosya ağacında bul/yeniden adlandır/diff, sistem yedek/OTA ve altı masaüstü düzeninin tam mobil portu henüz yoktur.

PrintScreen karşılığı platformun ekran görüntüsü kısayoludur; normal uygulama arka planda ekran yakalamaz. Programatik MediaProjection olursa her oturum sistem onayı gerekir. EXE/Wine, DKMS/GRUB/Calamares, PC ISO/Pi IMG ve GNOME/Plasma/Xfce oturumları mobil yetenek gibi listelenmez.

Tek React kökü, açılınca oluşturulan sayfalar, dinamik günlük uygulama modülü, yerel font/WebP/vektörler. Dünya saatleri/duvar saati görünürken seyrek güncellenir; gizli feed/analitik/pano/mikrofon taraması yoktur. Web hash’i bir dosya ≤32 MiB; medya ≤32 MiB, geçici altı fotoğraf ≤8 MiB/adet. Kronometre/sayaç zaman damgasıyla kalır; sistem alarmı/arka plan ses garantisi yoktur. Başlangıç JS gzip bütçesi ≤110 KiB; ölçüm [doğrulama kaydında](VERIFICATION.md), telefon RAM/pil/FPS garantisi değildir.

Yerel işçiler sınırlıdır. Katalog ≤48 MiB JAR / ≤256 MiB JSON, ≥384 MiB boş alan, ≤20 bin uygulama ve paket grubu, ≤2000 sürüm/grup; açık arama ≤80 sonuç. APK özel önbelleği ≤3 kopya, yeni seçimde 24 saatlik temizlik, 64 KiB I/O bloğu, ≤100 bin arşiv girdisi. Mağaza satırları geri kullanılır; harf simgesi önbelleği ≤1.5 MiB. Bu sınırlar ANR/pil/termal kanıtı değildir; kötü belge/ağ, iptal, düşük alan ve süreç ölümü ayrıca ölçülmelidir.

## 8. Kanıt ve ilk ROM kapıları

Kaynak sözleşmesi, SDK derlemesi, emülatör sanal radyo/kurulum testi ve gerçek SIM/cihaz kanıtı ayrı tutulur. CI harcanabilir QEMU emülatörü dışında fixture araması/SMS çalıştırmaz; gerçek rol uygunluğunu atlamaz. 8 cihaz + 3 depo güvenliği + 1 canlı kaynak testi geçmeden dağıtım paketi hazırlanmaz. Canlı Aegis APK incelemesi **kurmadan iptal**, ayrı etkisiz fixture ise sistem onayıyla gerçek kurulumdur. Bunlar GMS/operatör onayı değildir.

**Gözlenen emülatör kilometre taşı:** [`023a89c` / koşu 46048445728](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) tam **12/12** kabulü ve paket kapısını geçti. Soğuk başlangıçtaki intent, React taslak dinleyicisi hazır olduğunu bildirdikten sonra yalnız bir kez teslim edilir; framework action/data bilgisi değiştirilmeden tüketim durumu ayrıca tutulur. 5/12, 10/12 ve 11/12 kalan önceki başarısız koşular [kanıt kaydında](VERIFICATION.md) korunur. [İndirme/kurulum](INSTALL.md); bu çalışma alanına artifact indirmesi ağ sınırı nedeniyle tamamlanmadığından yerel APK hash/imza doğrulaması iddia edilmez.

Son telefon imajı için:

1. Tam marka/model/kod adı, SoC/ABI, mevcut yazılım/vendor dalı ve bootloader politikası.
2. Kullanıcının yedeği, garanti/DRM etkileri ve doğrulanmış stok geri dönüş yolu; otomatik unlock/flash/relock yok.
3. Dağıtılabilir device/kernel/vendor ağaçları ve firmware lisansları; GSI/Treble uygunluğu ayrıca incelenir.
4. SELinux enforcing, şifreleme, AVB/Verified Boot, güvenli imza anahtarları, OTA/anti-rollback/kurtarma. Anahtarlar Git/chat’e konmaz.
5. Tam donanımda boot/dokunma/ekran/GPU/kamera/ses/SIM/arama/SMS/acil arama/Wi-Fi/Bluetooth/GPS/NFC/biyometri.
6. Uyku/uyanma, şarj/termal, düşük bellek, ölçülmüş pil/RAM/FPS, büyük font/ekran okuyucu ve rol/izin geri alma.
7. API/OEM/çoklu SIM/çoklu çağrı/lock-screen/bildirim/DTMF, bozuk belge, kurulum iptal/hata/update/signature/split/process-death testleri.
8. CTS/VTS/CDD ve uygulanacaksa GMS lisans/sertifika; Rıfkı sağlayıcı/gizlilik/onay/saklama ve yetki sınırı incelemesi.

Bu kapılar geçilmeden hiçbir telefon “destekleniyor” listesine eklenmez. PC/Pi v1.2 kanıtları mobil boot/modem/ROM kanıtı olarak kullanılmaz; mevcut yayınlar ve PR birleştirme yetkisi bu çalışmadan bağımsızdır.
