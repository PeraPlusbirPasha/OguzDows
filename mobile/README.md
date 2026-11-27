# OğuzDows Mobile

**Cebinde, senden bir dünya.**

**Sıradaki ürün planı:** [Canlı Aero kabuk + konuşan Rıfkı mimarisi ve MVP → v1.0 yol haritası](ROADMAP.md). Kullanıcının seçimi: bulut ağırlıklı AI, uyandırma kelimesi, kabuk + sistem yardımcı yüzeyi ve 4–6 GB RAM hedefi. Bu bir geliştirme planıdır; aşağıdaki APK’ya mikrofon/model/bildirim erişimi eklenmiş değildir.

OğuzDows’un Türkçe kimliği, nazar boncuğu güç simgesi, Rıfkı’sı, kültür koleksiyonu ve araçlarını birleştiren **zengin mobil arayüz + yerel Telefon/SMS/Mağaza test APK’sı**. Tarayıcı önizlemesi ve telefondaki yerel servis yolu ayrı tutulur.

> **Emülatör APK’sı hazır; telefon ROM’u/ISO’su değildir.** [`023a89c` koşusunda](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) **12/12 gerçek emülatör testi + 6 Java testi geçti**; lint 0 hata / 37 uyarı. Paket yalnız tam kabulden sonra hazırlandı. [**APK indirme, SHA-256 ve emülatöre kurulum**](INSTALL.md) · [Kanıt ve kalan kapılar](VERIFICATION.md). Fiziksel SIM/cihaz, GMS, MMS/RCS ve canlı üretken model doğrulanmış değildir. PC/Pi v1.2 dosyaları ve yayınları değiştirilmez.

Ana APK **6.993.130 bayt**, debug imzalıdır. [Actions paketi](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728/artifacts/15222979423) 14 gün saklanır; kalıcı mobil Release değildir. Sandbox artifact depolama alanından indiremediği için burada yerel APK kopyası/bağımsız hash doğrulaması yoktur; CI kanıtı ve kendi indirmeni doğrulama adımları [kurulum kılavuzunda](INSTALL.md).

![OğuzDows Mobile tasarım laboratuvarı](screenshots/home-desktop.webp)

## Deneyebildiklerin

- **Ana ekran:** Boğaz duvar kâğıdı, pastel yerel simgeler, yatay kaydırılan **üç gerçek ana sayfa**, 20 uygulamalık çekmece, Türkçe arama, dokunma/basış geri bildirimi. Dar ekranda telefon çerçevesi kaybolur; arayüz ekranı doldurur.
- **Nazar boncuğu güç menüsü:** webde açıkça etiketli tasarım kilidi/önizleme kapatma; APK’da gerçek pil/ekran ayarı ve fiziksel güç/kilit yolu açıklaması. Cihaz kapatılmış veya güvenlik kilidi konmuş gibi gösterilmez. APK saat/pili sistemden okur; webdeki saat/pil/hava örnektir.
- **Rıfkı:** mevcut kedi karakteri korunur. Yerel rehber sabit, onaylı arayüz eylemleri önerir; keyfî komut çalıştırmaz. İsteğe bağlı üretken model için sunucu köprüsü vardır; varsayılan kapalıdır ve canlı modelle denenmemiştir.
- **Atölye:** 16 aracın tamamı görünür; **10 araç etkileşimlidir**, diğer 6’sı yerel entegrasyon gerektirdiğini açıkça gösterir. Görev/not/metin rafı, SHA-256, JSON, hesap, birimler, renk kontrastı, dünya saatleri ve Türkçe metin işlemleri. Masaüstüyle tam eşdeğerlik iddiası yok; [sınırlar](feature-parity.json).
- **Mağaza:** 24 kartlık seçki ve istek listesine ek olarak APK’da **canlı, imzası sabitlenmiş F-Droid kataloğu**; API/ABI filtresi, görünür yüklü sürüm karşılaştırması, gerçek boyut/sürüm/SHA-256, onaylı indirme ve sistem yükleyicisi. Canlı sonuçlar web seçkisiyle karıştırılmaz. Play ayrı kaynaktır; GNOME Software/Flatpak, APK veya GMS sağlamaz.
- **APK inceleme:** webde en çok 32 MiB ZIP başlangıcı/SHA-256; kurulum yok. APK’da en çok **256 MiB özel kopya**, paket/API/ABI/izin/ilk imzacı incelemesi ve ayrı sistem onayıyla kurulum. İptal/başarısızlık kuruldu sayılmaz. Hash veya sertifika özeti malware taraması değildir.
- **Google seçenekleri:** Google/Gmail/Haritalar/YouTube/Drive/Çeviri için açıkça etiketli dış web bağlantıları. Hesap/parola bu önizlemeye girilmez. GMS/Play Store ROM’a paketlenmez.
- **Haber & okuma:** üç özgün, çevrimdışı örnek metin; okuma listesi, okundu filtresi, TXT indirme. Canlı haber sunuluyormuş gibi gösterilmez.
- **Kişiselleştirme:** gerçek ortak açık/koyu tema, üç vurgu, dört kültür duvar kâğıdı, kompakt düzen, hafif/azaltılmış hareket. Sistem `prefers-reduced-motion` tercihi de izlenir.
- **Dosyalar/kamera seçimi:** yalnız açıkça seçilen dosya okunur. Fotoğraf seçimi/kamera önerisi tarayıcının sistem seçicisine bağlıdır; sürekli kamera veya mikrofon yoktur.

## Günlük mobil deneyim

- **Arama gerçekten arar:** ana ekrandaki arama, uygulama adları/takma adları, kişiler, 16384 karakterlik not, görevler, Atölye araçları ve mağazada eşleşme bulur. Türkçe `I/İ/ı/i` desteklenir; basit hesap ifadesi de çözümlenir. Yazarken ağa sorgu gönderilmez.
- **Telefon:** tam ekran tuş takımı, elle/yapıştırarak numara, kişi seçimi. **APK’da OğuzDows içinde** varsayılan Telefon rolü + izin + yerel alıcı/ücret onayı → Telecom ve kendi görüşme ekranı. Yanıtla/reddet/bitir/mikrofon/hoparlör/beklet/DTMF, servis durumuna bağlıdır. Web yalnız güvenli `tel:` aktarımı yapar; bağlı görüşme taklidi yoktur. Acil çağrı ayrı sistem yoludur, testlerde denenmez.
- **Mesajlar ve Kişiler:** APK’da açık SMS rolü/izin/hat ve ikinci gönderim onayı; sistem sağlayıcısından gelen/giden geçmişi ve gerçek parça geri bildirimleri. `queued`, gönderildi ve teslim raporu ayrı durumlardır. **MMS/RCS yoktur**; rol seçilmeden uyarılır. Web yalnız kalıcı taslak + güvenli `sms:` geçişidir. 60 elle oluşturulmuş kişi/favori/düzenle/onaylı sil; sistem rehberi okunmaz.
- **Denetim merkezi:** **üstten aşağı kaydır** veya durum çubuğuna dokun. Webde ses gerçek önizleme oynatıcısını, parlaklık arayüz karartmasını etkiler. APK’da ses **gerçek sistem medya kanalı**, parlaklık uygulama penceresidir; radyo/DND ayrı sistem panellerine gider. Başka uygulamaların teması veya sistemin açık/kapalı durumu uydurulmaz. Hafif/azaltılmış hareket tercihleri korunur.
- **Çeşitlilik:** Telefon, Mesajlar, Kişiler, Takvim, Saat, Müzik, Tarayıcı, Galeri, Hesap, Defter ve Günüm ile birlikte **20 uygulama girişi**. Takvimde en çok 80 yerel plan; Saat’te sayfalar arasında korunan kronometre/sayaç başlangıcı; Müzik’te 32 MiB’a kadar kendi ses dosyan; Galeri’de seçili 6 geçici fotoğrafı aç/indir/kaldır. Sistem alarmı/bildirim, kalıcı fotoğraf kitaplığı ve arka plan müzik servisi henüz yoktur.
- **Mağaza:** **24 uygulama / 8 kategori**, arama, kategori filtreleri, yerel marka SVG’leri ve istek listesi. Firefox, Signal, VLC, Organic Maps, Telegram, WhatsApp, Spotify, Bitwarden, Proton Mail, Nextcloud, Joplin, Obsidian, DuckDuckGo, Brave, KDE Connect, Wikipedia, AntennaPod, Element X, Aegis, Thunderbird, F-Droid, NewPipe, OsmAnd, Collabora Office. Katalog açık kaynak ve diğer lisanslı uygulamaları karıştırır; hepsi açık kaynak denmez. F-Droid/NewPipe için Play bağlantısı uydurulmaz.
- **Hareketler:** ana ekranda sola/sağa kaydır veya sayfa noktalarına dokun; aşağıdan yukarı çekerek çekmeceyi aç. Uygulama içi normal kaydırma/slider hareketi üst paneli yanlışlıkla açmaz. Yeni sayfa, simge ve panel geçişleri kısa; hafif profil ve sistem/uygulama azaltılmış hareket tercihi hepsini kapatır. Yalnız açıkça başlatılmış müzikte plak dönüşü vardır.

Telefon/SMS web bağlantıları uygun işleyicisi olmayan masaüstü tarayıcısında uygulama açmayabilir; tarayıcıdan SIM erişimi yoktur. Yerel APK, çevrimdışı paketlenmiş aynı arayüzü origin/ana çerçeve kısıtlı platform adaptörüne bağlar. Ayrıntılar ve yalnız harcanabilir emülatörde tekrar üretim: [Android modülü](android/README.md).

## Ekranlar

| Ana ekran                                       | Rıfkı                                                      | Atölye                                             | Gece mavisi                                           |
| ----------------------------------------------- | ---------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------- |
| ![Mobil ana ekran](screenshots/home-phone.webp) | ![Rıfkı yerel rehber ekranı](screenshots/rifki-phone.webp) | ![Atölye araçları](screenshots/atelier-phone.webp) | ![Koyu görünüm ayarları](screenshots/dark-phone.webp) |

| Telefon                                                    | Denetim merkezi                                                      | Mağaza                                                      | Uygulamalar                                            |
| ---------------------------------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------ |
| ![Tam ekran numara çevirme](screenshots/phone-dialer.webp) | ![Kaydırmalı ses ve görünüm paneli](screenshots/controls-phone.webp) | ![Yerel marka simgeli mağaza](screenshots/store-phone.webp) | ![20 uygulamalık çekmece](screenshots/apps-phone.webp) |

Bunlar çalışan web önizlemesinden alınmıştır; fiziksel cihaz veya ROM görüntüsü değildir.

## Çalıştır

Node.js 22 ve npm ile:

```sh
cd mobile/preview
npm ci
npm run dev
```

Sunucu `0.0.0.0:5173` üzerinde dinler; Arena `.e2b.app` önizleme hostlarını kabul eder. Kullanıcının tarayıcısındaki API istekleri **yalnız göreli `/api/rifki/...`** yolunu kullanır, `localhost`a bağlanmaz.

```sh
npm run build          # TypeScript + üretim dosyaları
npm test               # sınır/hesap/kayıt/yerel rehber + model köprüsü testleri
npm run test:native    # yalnız manifest/kaynak sözleşmeleri; SDK derlemesi değil
npm run test:browser   # çalışan önizleme üzerinde gerçek Chromium akışları
npm run format:check
npm audit
```

Tarayıcı testleri için `npm run dev` ayrı terminalde çalışmalıdır. İsterseniz `MOBILE_BASE_URL` ile test sunucusunu, `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` ile sistem Chromium yolunu belirtin. Varsayılan CI tarayıcısı npm’de sabitlenen Sparticuz Chromium’dur; gereken NSS kitaplıkları yalnız test önbelleğine açılır. Tarayıcı güvenlik denetimini kapatan bayraklar kullanılmaz. Test tarayıcısının `--no-sandbox` ihtiyacı CI ortamına özgüdür; telefon güvenlik politikası değildir.

Üretim çıktısı `mobile/preview/dist/` içindedir ve Git dışında tutulur. `npm run preview`, aynı opsiyonel API köprüsüyle yerel üretim önizlemesi sunar; kimlik doğrulamalı bir üretim servisi değildir. Salt statik barındırmada yerel arayüz çalışır; sunucu API’si ayrıca uygulanmadıkça üretken model bağlı görünmez.

## Rıfkı: rehber başka, üretken model başka

**Varsayılan:** kural tabanlı, sınırlı yerel rehber. Mesajlar ağa gönderilmez; mikrofon, bildirim, Google hesabı veya ekran okunmaz. Sohbet yalnız bellektedir; not/görevler gibi kalıcı depoya yazılmaz.

**Opsiyonel gerçek model köprüsü:** OpenAI uyumlu bir sunucu veya yerel inference servisi. `.env.example` dosyasını `mobile/preview/.env` olarak kopyalayıp sunucu ortamında ayarlayın; dosya Git dışında tutulur. `.env` değişince sunucuyu yeniden başlatın.

- `RIFKI_ENABLED=true`, `RIFKI_API_BASE`, `RIFKI_MODEL`; gerekirse sunucuda `RIFKI_API_KEY`.
- Anahtarı **asla** `VITE_*` değişkenine, arayüze, belgeye veya sohbete koymayın.
- API base HTTPS olmalı; yalnız sunucunun yerel model bağlantısı için loopback HTTP kabul edilir. URL/anahtar kullanıcı arayüzünden alınmaz.
- Rıfkı → **Model** → bağlı sağlayıcıyı gör → gönderimi onayla → **yeni** model sohbeti aç. Eski yerel konuşma otomatik gönderilmez.
- Modelin araç/shell/dosya/kurulum yetkisi yoktur. Yanıt yalnız metin olarak çizilir; HTML olarak çalıştırılmaz.
- En çok 12 mesaj / mesaj başına 2000 / toplam 12000 karakter, 24 KiB istek, 64 KiB upstream yanıt, 600 token istek bütçesi, 20 s timeout; en çok 2 inference / süreç ve IP başına 8/dakika. Bu proxy-arkası IP sınırı kullanıcı kimlik doğrulaması değildir.
- Sağlayıcı hatası, anahtar veya cevap gövdesi loglanmaz/istemciye sızdırılmaz; bu kod sohbet kaydı tutmaz. **Sağlayıcının kendi veri saklama politikası bunun dışındadır.**

**Ücretli/uzak modeli herkese açık önizlemede açmadan önce** kullanıcı kimlik doğrulaması, proxy body/time limitleri, kullanıcı bazlı kota, TLS, kötüye kullanım kontrolü, sağlayıcı veri saklama sözleşmesi ve güvenlik incelemesi gerekir. Bu geliştirme köprüsünü doğrudan ücretli, anonim üretim servisi olarak kullanmayın. Bu oturumda gerçek inference çalıştırılmadı; köprü sözleşmeleri sahte upstream ile sınanır.

## Yerel APK ve varsayılan yardımcı

[`android/`](android/README.md), paketlenmiş zengin WebView arayüzünü AndroidX origin-bağlı mesaj köprüsüyle yerel platform servislerine bağlar. Görüşme, canlı Mağaza, yüklü uygulamalar ve APK inceleme/yükleme ekranları platform görünümleridir. HOME/Telefon/SMS/yardımcı rolleri kullanıcı seçimine bağlıdır; başka uygulamalar kaldırılmaz. Rıfkı’nın sistem yardımcı oturumu metin tabanlı, çevrimdışı rehberdir; mikrofon/hotword/ekran bağlamı ve native üretken model bağlı değildir. APK bir işletim sistemi imajının yerine sunulmaz.

## Veriler ve sıfırlama

- Önizleme tercihleri/notlar/görevler/listeler, kişiler, SMS taslağı, takvim planları ve sayaç/kronometre başlangıcı: yalnız bu origin’in `localStorage` alanındaki `oguzdows.mobile.preview.v1`. **Şifreli değildir.** Paylaşılan tarayıcıda sır saklamayın.
- Bozuk/sürümü tanınmayan kayıt sessizce ezilmez; yazma durur, uyarı çıkar. Depolama engellenirse çalışma bellekte sürer, kalıcı kayıt iddia edilmez.
- Ayarlar → **Yalnız bu önizlemenin verilerini temizle** ikinci onay ister. APK’da da yalnız arayüzün yerel kaydı silinir; sistem SMS geçmişi, rol/izinler ve depo/yükleyici verisi bu düğmeyle silinmez. Diğer origin/dosya/masaüstü ayarlarına dokunmaz.
- APK/hash girdileri ve seçilen fotoğraf sunucuya gönderilmez. Sohbete bir dosyanın içeriğini kendiniz yazmanız ayrı bir açık gönderimdir.

## Gerçek cihaz sürümüne geçiş

[Ürün/sistem tasarımı](DESIGN.md) · [23 özellik ve platform eşlemesi](feature-parity.json) · [Yerel APK ve tekrar üretim](android/README.md) · [Test kapsamı](VERIFICATION.md)

İlk ROM için **tam marka/model, kod adı ve mevcut yazılım sürümü** gerekir. ARM64 olmak tek başına telefon desteği değildir. Bootloader politikası, kernel/vendor ağaçları, modem/kamera/GPU sürücüleri, AVB/şifreleme, imzalı OTA ve geri dönüş yolu incelenmeden imaj veya flash komutu verilmeyecek. Google paketlerinin lisans/sertifika kapıları ve gerçek donanım testleri ayrıca geçilmeli.

### Varlıklar

Rıfkı ve duvar kâğıtları mevcut depo koleksiyonundan küçük WebP türevleridir; 24 yerel mağaza marka simgesinin kaynağı, lisansı, değişiklik ve hash kayıtları dahil [varlık atıfları](ASSETS.md). Font Manrope (SIL OFL), simgeler Lucide (ISC); bağımlılıklar lockfile’da sabittir. Ekran görüntüleri çalışan tarayıcıdan alınır; fiziksel telefon fotoğrafı veya cihaz testi değildir. Google/Android adları ilgili sahiplerine aittir; resmî ortaklık/sertifika iddia edilmez.
