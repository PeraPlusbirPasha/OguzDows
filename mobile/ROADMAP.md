# OğuzDows Mobile · canlı kabuk ve Rıfkı yol haritası

> **Yol haritası; ilk native kabuk dilimi uygulandı.** `0.3.0-launcher`, gerçek HOME/uygulama çekmecesi/kalıcı kısayollar/AppWidgetHost/yerel Rıfkı ile [17/17 emülatör kabulünü geçti](VERIFICATION.md). [APK’yı indir ve dene](INSTALL.md). Bu, bütün yol haritasının tamamlandığı anlamına gelmez: bulut, ses/wake-word, arayan profilleri, bildirimler ve fiziksel performans/ölçek/süreç ölümü kapıları açık. Bu belge mikrofon/model/izinleri etkinleştirmez; mevcut mimari [DESIGN.md](DESIGN.md) içindedir.

**Ürün cümlesi:** Masaüstünün küçültülmüş ekranı değil; cebinde yaşayan OğuzDows. **Rıfkı evin kedisi; root kullanıcısı değil.** Lafını esirgemeyebilir, fakat gönderilmemiş mesaja “gönderdim”, istenmiş çağrıya “bağlandım” diyemez.

## 1. Netleşen ürün sözleşmesi

| Konu | Kullanıcının seçimi | Mimari sonucu |
| --- | --- | --- |
| Üretken sohbet | **Bulut ağırlıklı** | Ağ/sağlayıcıdan bağımsız yerel kabuk; kimlik doğrulamalı model geçidi; anahtar APK’da değil |
| Ses | **Uyandırma kelimesi de olsun** | Yerel keyword algılama + bas-konuş yedeği; donanımsal sürekli dinleme ayrı fizibilite kapısı |
| Görünürlük | **Kabuk + sistem yardımcı çağrısı** | Ana ekranda canlı karakter; başka uygulamadan kullanıcı çağırınca yardımcı oturumu; sürekli yüzen overlay yok |
| Donanım | **4–6 GB RAM / orta segment** | Ağır yerel LLM yok; uyarlanabilir cam katmanı ve sınırlı animasyon/bellek |
| İlk doğrulama | **Emülatörle geliştirmeye devam** | Var olan Telefon/SMS/Mağaza kabul kapıları korunur; gerçek cihaz kanıtı ayrıca gerekir |

Bu aşamanın ürünü normal yetkili bir **Launcher + varsayılan yardımcı + isteğe bağlı Telefon/SMS entegrasyonu**dur. “AI OS”, bunun ürün dilidir; kernel, SystemUI, kilit ekranı veya tüm uygulamalar üzerinde sınırsız denetim değildir. Cihaza özel ROM, ayrı cihaz/vendor/bootloader projesidir.

### Eldeki temeli koru

- `HomeActivity` içinde çevrimdışı paketlenmiş zengin UI, origin/ana çerçeve kısıtlı köprü var.
- `CallController` / `OguzInCallService`, SMS sağlayıcısı/gerçek geri bildirim ve imzalı F-Droid/APK inceleme yolları var. Önceki 12/12 taban korunarak 5 native launcher testi eklendi; API35/4GiB QEMU’da 17/17 kabul kanıtı mevcut.
- `RifkiVoiceService`, `RifkiSessionService`, `RifkiRecognitionService` henüz **metin/kural tabanlı iskelet**; ses kaydı, wake-word ve native bulut sohbeti yok.
- Mevcut web model köprüsü varsayılan kapalı bir geliştirme köprüsü; üretim kimlik doğrulamalı mobil servis değil.
- Gerçek widget host’u ilk dilimde uygulandı: platform bağlama, gerçek RemoteViews, yeni host’a dönüş ve kaldırma fixture’ı geçti. Tüm sağlayıcı/iş profili/ölçek/süreç ölümü matrisi açık; sistem rehberi profilleri ve bildirim dinleyicisi henüz uygulanmadı.

**Karar:** Güvenlik/telefon/depo kodunu baştan yazma. Kotlin adaptörleriyle sar; ana kabuğu kademeli olarak Compose’a taşı. Web önizlemesini tasarım ve davranış referansı olarak koru; geçişte taşınmamış Atölye/Haber modülleri eski yerel köprü sınırını koruyan paketlenmiş UI’da kalabilir. WebView’in uzak içerik yasağı bu geçiş için kaldırılmaz.

**Test göçü:** Korunan şey yalnız “12” sayısı veya WebView’e özgü JS seçiciler değil, 12 kabul senaryosunun gerçek davranışıdır. Bir yüzey Compose’a taşındığında o senaryonun UI seçicileri Compose test tag/UiAutomator ile yenilenir; aynı rol/izin/iptal/Telecom/SMS/kurulum doğrulamaları gerçek emülatörde sürer. Taşınan yüzey eski JS testini çalıştırmadı diye sıfır/atlanmış test başarı kabul edilmez; eski ve yeni akış karşılaştırıldıktan sonra kapı güncellenir. Mikrofon/AI/widget için ayrıca yeni testler eklenir.

## 2. Mimari: karakter, karar ve yetki birbirinden ayrı

```text
Telefon / SMS / pil / saat / açık izinli bildirim olayları
                 │
                 ▼
       Yerel bağlam deposu / StateFlow
          ├─ CallerProfileResolver ──► Güvenli görüşme UI’sı
          └─ RifkiBehaviorReducer ──► Kedi pozu, ruh hali, yerel replik

Dokunma / yazı / açık ses oturumu
                 │
                 ▼
      Rıfkı oturum düzenleyicisi
          ├─ Ses: ASR / TTS adaptörleri
          └─ HTTPS model geçidi ──► Bulut sağlayıcıları
                 │                  (metin + eylem önerisi)
                 ▼
       Yerel ActionPolicy / yetenek kataloğu
          ├─ Reddet / belirsizliği sor / kilidi açtır
          ├─ Gerekli rol-izin ve kullanıcı onayı
          └─ Yerel executor ──► Gerçek platform callback’i
                                      │
                                      └─► UI ve Rıfkı sonuç bildirimi
```

**LLM’den doğrudan Telecom, SmsManager, paket yükleyicisi veya bildirim eylemine bağlantı yoktur.** Bulut “Ali’ye SMS taslağı oluştur” önerebilir; alıcı çözümü, mesaj önizlemesi, son gönderim onayı ve gerçek sent durumu cihazdadır.

### Mantıksal modüller

| Modül | Sorumluluk | İçermemesi gereken |
| --- | --- | --- |
| `app` | Manifest, rol girişleri, servis/Activity bağlama, DI | Büyük iş kuralları |
| `shell-ui` | Ana ekran, çekmece, arama, widget host, kontrol merkezi, kendi modül kartları | Telecom/LLM çağrıları |
| `design-system` | Aero yüzeyleri, tema/token, basış geri bildirimi, erişilebilirlik, kalite profili | Cihaz yetkileri |
| `domain` | Tipli eylemler, izin/onay politikası, doğrulanmış işlem durumu | Android View veya sağlayıcı SDK’sı |
| `platform` | Mevcut Java Telefon/SMS/Store adaptörleri; LauncherApps, widget ve bildirim entegrasyonu | Karakter prompt’u |
| `rifki-core` | Davranış reducer’ı, bağlam filtresi, konuşma oturumu, niyet önerileri | Doğrudan sistem işlemi |
| `rifki-voice` | Keyword, mikrofon oturumu, ASR/TTS, audio focus ve iptal | Sürekli buluta ses akışı |
| `data` | Room profil/düzen kayıtları, DataStore tercihleri, kontrollü önbellek | Varsayılan ham ses/sohbet arşivi |
| Ayrı backend | Kimlik, kota/maliyet, sağlayıcı anahtarları, model/ASR/TTS geçidi | Telefone doğrudan komut yürütme |

MVP’de bunlar paket/sorumluluk sınırları olabilir; ihtiyaç oldukça Gradle modüllerine ayrılır. Her kutu için ayrı süreç/servis açılmaz.

### Süreç ve olay modeli

- **Ana süreç:** HOME/Compose UI, görüşme/SMS/Store’un tek doğruluk kaynağı, policy/executor ve `VoiceInteractionSessionService` yüzeyi. UI gerçek state’i `StateFlow` üzerinden gözler; tek seferlik etkiler yaşam döngüsüne bağlıdır.
- **İnce `:assistant` süreci:** sistemin seçili tuttuğu `VoiceInteractionService`, küçük etkinlik/keyword koordinatörü. Sürekli bir Compose sahnesi, WebView, kişi veritabanı veya ağ sohbeti yüklemez. Ağır oturum/görünüm ana süreçte yalnız gerektiğinde açılır; bu ayrım AOSP’nin servis/session önerisini izler.
- Süreçler arası iletişim **uygulama içi tipli Binder sözleşmesi**dir; dışa açık genel komut broadcast’i yoktur. `StateFlow` kendiliğinden süreçler arası çalışmaz. İşlem yürütme ve veritabanı yazımı tek taraftadır; onay nonce’u/bağlam sürümü/istek kimliği kontrol edilir.
- Asistan ana süreci sürekli bağlı tutmaz. Konuşma/eylem sırasında gereken snapshot alınır. Olay kaybında modelden durum uydurulmaz; güncel platform snapshot’ı sorgulanır.
- `WorkManager`, yalnız uygun ertelenebilir işlere kullanılır. Mikrofon, wake-word ve canlı çağrı akışı periyodik worker değildir.

### Eylem kapısı

İlk beyaz liste: `OpenApp`, `OpenPanel`, `SetOwnTheme`, `DraftSms`, `RequestCall`, `OpenSystemSetting`, `ReviewApk`, `ShowNotificationSummary`. Model serbest URI, shell komutu, rastgele dosya yolu veya doğrudan `PendingIntent` alamaz. Uygulama/alıcı referansları yerel katalogda çözülür; modelin uydurduğu paket veya kişi kabul edilmez.

| Eylem sınıfı | Kural |
| --- | --- |
| Kullanıcının istediği düşük riskli UI eylemi | Açık kullanıcı isteği + geçerli oturum; örneğin Rıfkı “gece modunu aç” isteğinde kendi temamızı değiştirir |
| Belirsiz kişi/uygulama | Seçim sor; “Ali” için rastgele ilk kişiyi seçme |
| Çağrı, SMS, bildirim yanıtı, veri paylaşımı | Alıcı/içerik/ücret önizlemesi ve **cihaz üzerinde son kullanıcı onayı** |
| APK yükleme/silme | İnceleme ve sistemin kullanıcı onayı; sessiz işlem yok |
| Kilitli cihazda özel/veri etkileyen işlem | Kilidi açtır; bildirim/kişi içeriğini seslendirme veya gösterme |
| Sistemce kapalı/izin yok | Gerçek ayar/rol akışını öner; başarı veya yetki uydurma |

Rıfkı’nın kendi başına yaptığı ruh hali yorumu, kullanıcı eylem isteği sayılmaz. Modelin “bunu zaten onayladı” demesi de onay değildir. Bildirim, kişi adı ve SMS metni güvenilmeyen veridir; içlerindeki talimat policy’yi geçemez. Ücretli eylem otomatik yeniden denenmez; belirsiz sonuç “bilinmiyor/yeniden kontrol ediliyor” olarak kalır.

## 3. Aero: cam hissi, pil yakmayan çizim

### Yerleşim

- **Ana ekran:** duvar kâğıdı, serbest duran uygulama simgeleri, ince cam raflar, gerçek widget alanları. Masaüstü görev çubuğunun kalın kare kutuları telefona taşınmaz.
- **Alt erişim bölgesi:** başparmakla arama, çekmece, Telefon/Mesajlar ve Rıfkı çağrısı. Esas eylemler en az 48 dp dokunma alanında; görünen yüzey daha ince olabilir.
- **Üstten kontrol merkezi:** tek cam düzlem; sistem medya sesi, kendi pencere parlaklığı ve desteklenen sistem ayar panelleri.
- **Uygulama modülleri:** telefonda alt sayfa/tam ekran; geniş ekranda iki sütun veya kendi uygulamamızın panelleri. Diğer uygulamaları keyfî serbest pencereler halinde yönetme iddiası yok.
- **Rıfkı:** ana ekranda küçük bir “tünek”; dokununca kısa tepki, sürükleyince güvenli alana yerleşme, çağrılınca alt yardımcı sahnesi. Başka uygulamaların üstünde kalıcı kedi yok. Başkasının güvenlik ekranını örten veya global hareketi kaçıran overlay yok.
- 8–12 dp gibi kontrollü köşe token’ları, ince ışık kenarı, hafif gölge, okunaklı dolgu ve kısa basış tepkisi. Koyu/açık tema bütün **kendi** web/yerel/Compose ekranlarında tek tercihi izler. Başka üreticinin uygulaması zorla temalanmaz.

### Üç kalite profili

1. **Hafif:** yarı saydam renk, sabit ışık kenarı; blur/refraction ve sürekli karakter hareketi yok.
2. **Dengeli — varsayılan:** duvar kâğıdından boyut/tema değişince üretilen düşük çözünürlüklü ön-bulanık doku + saydam yüzeyler. Her kart arka planı yeniden bulanıklaştırmaz.
3. **Aero+:** destekli/ölçülmüş cihazda yalnız sınırlı kendi UI bölgesinde gerçek zamanlı efekt. Global ekran/başka uygulama bulanıklaştırması değildir; API/donanım/ısı/pil tasarrufuna göre geri düşer.

Camın ışık kırılması ilk sürümde görsel olarak taklit edilir; her pikselde fiziksel refraction shader’ı çalıştırılmaz. Hareketler çoğunlukla transform/opacity; iç içe offscreen katmanlar, her satırda blur ve sonsuz 60 FPS kedi animasyonu yok. Widget güncellemeleri görünürlük yaşam döngüsüne bağlıdır. Azaltılmış hareket tercihinde aynı bilgi statik poz ve metinle verilir.

### Başlangıç performans hedefleri — henüz ölçüm sonucu değil

Referans **4 GB ARM64 / 60 Hz** fiziksel cihaz belirlendikten sonra release derlemede:

- Ana ekran/çekmece kritik akışlarında 16,7 ms kare bütçesi; kontrollü senaryolarda jank oranı için ilk hedef <%3.
- Soğuk ilk çizim için ilk hedef ≤1,2 s; ağ/AI bu yolu bloklamaz.
- Isınmış boşta kabuk + asistan koordinatörünün toplam PSS’i için ilk hedef ≤150 MiB. Aktif ses/oturum ayrıca ölçülür; WebView geçiş sürecinin maliyeti ayrı raporlanır.
- Uygulama simgesi ve karakter dokuları sınırlı LRU; ağır yüzeyler kapanınca bırakılır. Düşük bellek/pil tasarrufu gerçek sistem sinyaliyle kaliteyi düşürür.
- Macrobenchmark, JankStats, Baseline Profiles ve Perfetto ile doğrula; emülatör sonucu pil/termal/gerçek cihaz FPS kanıtı değildir.

## 4. Rıfkı: yerel sinir sistemi, bulutta sohbet

### 4.1 Üç ayrı durum ekseni

**Ruh hali:** `Keyifli / Uykulu / Meraklı / Ciddi / Huysuz / Endişeli`.

**İşlev:** `Dingin / Dinliyor / Düşünüyor / Konuşuyor / OnayBekliyor / Çevrimdışı / Hata`.

**Görsel eylem:** göz kırp, kulak çevir, esne, başını eğ, kısa adım at, tüneğe dön, konuşma ağız şekli.

Böylece `Uykulu + Dinliyor` mümkün olur; ruh hali mikrofon durumunu gizlemez. Mikrofon/bağlantı/işlem durumu pozdan bağımsız yazı ve belirgin göstergeyle görünür. Öncelik: **çağrı ve güvenlik > ses oturumu > açık kullanıcı işi > ortam yorumu**. Gelen/aktif çağrı, TTS ve ASR’yi durdurur; görüşme sesi kaydedilmez.

`RifkiBehaviorReducer(Context, UserPreferences, Event) -> Mood + Pose + OptionalSuggestion` saf ve test edilebilir bir fonksiyondur. Saat/pil/şarj, kullanıcının atadığı arayan profili, izinli bildirim sayısı ve son etkileşim buraya gelir. Aynı olay için sürekli ağ model çağrısı yapılmaz. Bulut kesilince kedi ve yerel aksiyonlar çalışır; yerel replikler üretken sohbetmiş gibi gösterilmez.

### 4.2 Karakter ve bağlam

| Olay | Görsel / davranış | Örnek replik | Sınır |
| --- | --- | --- | --- |
| Pil eşik altına iner | Kulak aşağı, kuyruğu toplar | “Benim dokuz canım var; pilin o kadar cömert değil. Tasarruf ayarını açalım mı?” | Gerçek pil verisi; eşik geçişi/histerezis ve bekleme süresi, her yüzde değişiminde konuşma yok |
| Gece geç saat | Esneme, daha yavaş kısa hareket | “Bu saatte ben bile pencereden indim. Gece görünümü?” | Sessiz saatlerde otomatik ses yok; mizah kapatılabilir |
| Bildirim yoğunluğu | Bir bakış, ardından sakinleşir | “Kapı önü kalabalık. Bildirim özetine bakalım mı?” | İzin varsa sayı/yerel gruplama; içerik otomatik buluta gitmez |
| Yakın/VIP çağrısı | Dikkatli, sıcak poz | “İç halkadan biri. Açıyor muyuz?” | Yalnız yerel profil; kendi başına yanıtlama yok |
| İş çağrısı | Dik oturuş, sade UI | “Kuyruk toplandı. İş modu.” | Gelen çağrıda varsayılan sessiz yazılı tepki; zilin üstüne konuşmaz |
| Ağ/model yok | Meraklı baş eğme | “Bulut tarafı yanıt vermiyor. Uygulamayı yine açarım; sohbet için bağlantı lazım.” | Gerçek hata/erişim durumu; uydurma cevap veya başarı yok |

Kişilik: hafif ukala, kısa, sıcak; küçümseyen, panik yaratan veya kullanıcının ilişkileri hakkında hüküm veren dil yok. Acil/sağlık/finans bağlamında şaka geri çekilir. “Tepki sıklığı”, “sessiz kedi” ve “mizah dozu” ayarlanabilir. Arka plandayken veya ekran kapalıyken gereksiz yorum/animasyon/ağ isteği üretilmez.

**Görsel teknoloji kararı:** İlk rig, mevcut Rıfkı kimliğini koruyan küçük 2D sprite/vector atlası ve Compose dönüşümleri. Ölçüm bütçesini geçerse Rive state machine’e geçilebilir; zorunlu ağır 3D yok. İlk ağız hareketi ses genliğine bağlı birkaç şekildir; sağlayıcı viseme sunarsa daha sonra eşleme eklenir. Lip-sync için ekran sürekli yeniden yerleşmez.

### 4.3 Ses ve model hattı

```text
Yerel “Hey Rıfkı” algılama veya bas-konuş
   → görünen yardımcı oturumu + duyulur/görsel etkinleşme işareti
   → sınırlı ses yakalama / konuşma sonu / iptal
   → bulut ASR (yalnız etkinleşme sonrası, açık veri izniyle)
   → ekranda transkript
   → LLM: kısa yanıt + şemalı eylem önerisi
   → yerel policy / gerekiyorsa alıcı seçimi ve son onay
   → bulut TTS / yerel kullanılabilir ses yedeği
   → platformdan doğrulanmış sonuç
```

- Wake-word öncesindeki ortam sesi buluta gönderilmez. Yerel algılama tamponu sınırlı ve geçicidir; varsayılan ses/transkript arşivi tutulmaz.
- Mikrofon, etkinleşme ve aktarım durumları ayrı gösterilir. Fiziksel mikrofon gizlilik anahtarı, izin iptali ve başka uygulamanın mikrofonu kullanması doğru hata/geri düşüş üretir.
- Önce ayrı ASR → metin modeli → TTS hattı: hata, izin ve maliyet izlenebilir olsun. Gerçek zamanlı speech-to-speech daha sonra, aynı eylem kapısından geçerek eklenebilir.
- Gelen çağrı/audio focus kaybı oturumu ve TTS’yi iptal eder. Uzun cevap varsayılan değil; ayrıntı istenirse genişler. Replik seslendirilecek diye özel bildirim veya kişi adı kilit ekranında okunmaz.
- Yerel TTS yedeği yalnız uygun, yüklenmiş ve çevrimdışı çalıştığı doğrulanan motor/ses varsa kullanılır; Android TTS’nin her cihazda çevrimdışı olduğu varsayılmaz. Yoksa metinle sürer.

### 4.4 Uyandırma kelimesi: üç dürüst destek düzeyi

1. **Her durumda temel yol:** metin ve kullanıcı başlatmalı bas-konuş / sistem yardımcı çağrısı. Yardımcı hareketinin/düğmesinin tam şekli OEM’e bağlıdır.
2. **Standart APK için hedef:** OğuzDows görünürken yerel yazılım keyword algılama; uygun cihazda, kullanıcı görünürken başlatılmış ve sistemce izin verilen mikrofon foreground hizmetiyle isteğe bağlı arka plan modu. Bildirim/gizlilik göstergesi ve tek hareketle kapatma şarttır. Android sürümü, while-in-use mikrofon/FGS kuralları, pil ve OEM davranışı ayrı test edilir; boot’tan gizlice başlatılmaz.
3. **Donanımsal düşük güçlü sürekli mod:** DSP/enrollment/ayrıcalıklı API/OEM desteği varsa ayrı ürün entegrasyonu. **Varsayılan yardımcı olmak tek başına bu yetkiyi vermez.** API35 kaynağındaki hotword girişlerinin bir kısmı `@SystemApi`/özel izin/donanım koşulludur; standart APK’da reflection/hidden API hilesi kullanılmaz.

`WakeWordEngine` bir adaptördür. Türkçe “Hey Rıfkı” doğruluğu, ARM64 paket boyutu, lisans/SDK veri davranışı ve pil testini geçen motor seçilir. Porcupine veya sherpa-onnx tabanlı keyword spotting fizibilite adaylarıdır; hiçbiri bu belgeyle lisanslanmış, entegre edilmiş veya Türkçe marka kelimesinde doğrulanmış sayılmaz. Motor seçimini ilk teknik denemede kapat; başarısızsa yazılım modu etiketini daralt, sahte always-on anahtarı gösterme.

### 4.5 Bulut geçidi ve veri sınırı

- Mevcut Node tabanını esas alan ayrı **TypeScript/Fastify** geçidi; sağlayıcılar `ChatProvider`, `AsrProvider`, `TtsProvider` adaptörlerinin arkasında. Metin tarafında şemalı yanıt destekleyen OpenAI-uyumlu uç seçilebilir; bütün ses API’lerinin aynı sözleşmeyi desteklediği varsayılmaz.
- Sağlayıcı anahtarı yalnız sunucu secret deposunda. Mobilde hesap/oturum için kısa ömürlü yetki, güvenli token saklama, kullanıcı bazlı hız ve harcama kotası. Vite geliştirme proxy’si üretim güvenlik katmanı değildir; CORS veya IP sınırı kimlik doğrulama yerine geçmez.
- Süre/mesaj/ses boyutu/yanıt token/eşzamanlılık sınırı, streaming iptali, zaman aşımı ve geri basınç uygulanır. Ücretli işlem retry’siyle sohbet retry’si birbirinden ayrıdır.
- Buluta varsayılan veri: kullanıcının bu oturumda bilerek söylediği/yazdığı içerik ve izinli en küçük bağlam. Tüm rehber, SMS kutusu, ekran, pano veya ham bildirim havuzu gönderilmez. Önceki yerel sohbet kendiliğinden taşınmaz.
- Arayan profili yorumu için yerelde `VIP/İş/Bilinmeyen` etiketi yeterlidir; numara ve gerçek isim gerekmez. Bildirim özetinde uygulama bazlı izin ve seçili içerik paylaşımı vardır; banka/OTP/hassas kaynaklar varsayılan dışarıdadır. Maskeleme, yanlış içeriği paylaşmanın tek savunması değildir.
- Profil ve kalıcı tercih cihazda; sohbet varsayılan oturum belleğinde. Ham ses ve mesaj gövdeleri ürün loglarına yazılmaz. Sağlayıcının saklama/eğitim politikası ayrıca seçilip kullanıcıya açıklanır; bu uygulamanın log tutmaması sağlayıcıda saklanmama garantisi değildir. KVKK/veri aktarımı ve gerekli hukuki inceleme yayın kapısıdır.

## 5. Arayana göre deneyim: değişen atmosfer, değişmeyen güvenlik

### Profil verisi

Kullanıcı belirli numara/kişiye `Yakın/VIP`, `İş`, `Genel`, `Kendi kuralımla engelli` atar. Sistem rehberi isteğe bağlı izin/seçiciyle bağlanır; elle tanımlama her zaman çalışır. Numara ülke bağlamı ile normalize edilir; belirsiz numara yanlış kişiyle eşleştirilmez. Gizli numara ayrı durumdur. Profil listesi yerelde kalır; buluta numara karması yollamak anonimleştirme sayılmaz.

Renk, vurgu, kedi pozu, kilit ekranı görünürlüğü, hazır **taslaklar** ve isteğe bağlı zil tercihi profilde tutulur. Yaşa/cinsiyete/isme bakarak ilişki veya risk çıkarımı yapılmaz. Kullanıcının bilinmeyen numarası otomatik “spam” değildir. Eşleşen numara da kimlik doğrulaması değildir; caller-ID taklit edilebilir.

| Profil | Görsel | Rıfkı | Hızlı aksiyon |
| --- | --- | --- | --- |
| Yakın/VIP | Sıcak amber kenar, kullanıcı izin verdiyse fotoğraf | Dikkatli/samimi | Yanıtla, sessize al, “Birazdan ararım” **taslağı** |
| İş/resmî | Sade petrol mavisi, daha az hareket | Dik oturuş, kısa ve ölçülü | Yanıtla, reddet; kullanıcı tetiklerse uygun hızlı yanıt taslağı |
| Genel/kayıtlı | Olağan tema | Nötr, kısa bakış | Standart çağrı kontrolleri |
| Bilinmeyen/gizli | Nötr yüksek kontrast; açık etiket | “Tanımıyorum; hemen hüküm vermiyorum.” | Yanıtla/reddet; çağrı sonrası kişi/profil oluşturma |
| Kullanıcının açık engel kuralı | Sade durum kaydı | Gösterişsiz, sessiz | Kuralı gör/düzenle; AI kendi başına engellemez |

Kontrollerin konumu profil değişince oynamaz; renk tek bilgi kanalı değildir. İsim/fotoğraf/özel replik kilitliyken kullanıcı tercihine göre gizlenir. Arayan profilinden otomatik mesaj gönderme, konuşma kaydetme veya arama yanıtlama çıkarılmaz.

### Gelen çağrı sırası

1. Telecom → mevcut `InCallService` callback’i: gerçek çağrı kaydı ve durum.
2. Yerel `CallerProfileResolver` → profil + kilit durumu + erişilebilirlik tercihi.
3. Native görüşme UI’sı hemen çizilir; profil geç gelirse güvenli nötr UI görünür. **Ağ/LLM/ASR hiçbir zaman çalma veya yanıtla düğmesinin ön koşulu değildir.**
4. Rıfkı’nın kısa sessiz pozu/metni yerelden seçilir. Varsayılan olarak çağrı zilinin üstüne konuşmaz; aktif çağrıda ses/mikrofon oturumu durur.
5. Kullanıcı yanıtla/bitir/yanıt taslağı seçer. Sonuç gerçek callback/sağlayıcıyla güncellenir.

**Zil kararı:** mevcut manifest `IN_CALL_SERVICE_RINGING=false`; sistemin zil sorumluluğu korunur. MVP’de mevcut kişi/sistem zil ayarını bozma. OğuzDows’un kendisinin profile özel zil çalması, ancak DND/sessiz/titreşim/AudioFocus/Bluetooth ve çift zil/eksik zil regresyonları geçince ayrı aşamada açılır; sessiz modu aşma izni değildir.

**İsteğe bağlı tarama:** `ROLE_CALL_SCREENING` ve `CallScreeningService`, kullanıcı açık engel kuralı isterse ayrıca eklenebilir. Platformun **5 saniyelik cevap sınırı** nedeniyle karar yerel ve hızlıdır; bulut modeli beklenmez. Servise hangi çağrıların ulaştığı izin/rehber/platform koşulludur. Çağrının kişiselleştirilmesi için screening rolü zorunlu değildir.

## 6. Platform yetenekleri ve izin stratejisi

| İhtiyaç | Resmî entegrasyon | Ürün sınırı |
| --- | --- | --- |
| Gerçek launcher | `ROLE_HOME`, `LauncherApps`, paket/değişim callback’leri | Uygulama + kullanıcı profili kimliğiyle anahtarla; tüm paketleri görme varsayımı yok |
| Gerçek widget | `AppWidgetHost` / `AppWidgetManager`, kullanıcı bağlama/ayar onayı | RemoteViews yaşam döngüsü; launcher içi sahte kart gerçek widget sayılmaz |
| Başka uygulamadan Rıfkı | `ROLE_ASSISTANT`, `VoiceInteractionService` / session | Ekran/AssistStructure/screenshot toplama kapalı kalır; kalıcı overlay gerekmez |
| Sesli girdi | `RECORD_AUDIO`, gerektiği ve izinli olduğu yerde mikrofon FGS tipi | Ön plan/arka plan ve gizlilik kısıtlarını dolanma yok |
| Çağrı | `ROLE_DIALER`, gerekli runtime izinleri, Telecom/InCallService | Acil çağrı sistem yolu; tüm VoIP uygulamalarının çağrılarını ele geçirme iddiası yok |
| Düz SMS | `ROLE_SMS`, gerçek izin/abonelik, SmsManager ve sağlayıcı | MMS/RCS ayrı; hiçbir üçüncü taraf mesaj veritabanına sınırsız erişim vermez |
| Kişi profili | Elle profil; gerekirse isteğe bağlı rehber izni/seçici | Bütün rehberi otomatik sunucuya yükleme yok |
| Bildirim merkezi | Kullanıcı açarsa `NotificationListenerService` | OS/OEM/iş profili ve gizlilik sınırları; bütün içeriklerin daima görünmesi beklenmez |
| Bildirime yanıt | Yalnız uygulamanın sunduğu geçerli RemoteInput/action | Kullanıcı seçimi ve alıcı/içerik onayı; her uygulamada aynı yetenek yok |
| Sistem kontrolleri | AudioManager, kendi pencere parlaklığı, resmî ayar panelleri | Gizli Wi-Fi/uçak modu anahtarı, root veya WRITE_SECURE_SETTINGS yok |
| Kurulum/mağaza | Mevcut imzalı depo, özel APK kopyası, sistem yükleyicisi | Google Play/GMS ayrı kaynak/lisans; bütün uygulamalarla uyumluluk vaadi yok |

İzinler ilk açılışta topluca istenmez: özellik kullanıldığında gerekçe → sistem onayı → reddedilirse çalışan sınırlı mod. Bildirim gövdesi erişimi ve buluta özet gönderme ayrı tercihlerdir. Başlangıçta yalnız yerel sayı/uygulama grupları yeterlidir. NLS ile diğer uygulamaların bildirimleri kendi merkezimizde gruplanabilir; kaynak uygulamanın sistem bildirim yapısını sınırsız değiştiremeyiz. Erişilebilirlik servisi, başka uygulamayı gizlice kumanda etmek için kestirme yol yapılmaz.

Normal launcher; SystemUI/Recents/Quickstep, OEM kilit ekranı, DND istisnaları veya bütün üçüncü taraf uygulama temalarını tam değiştiremez. Bildirim/banka/OTP/iş profili içeriği sistemce kısıtlanabilir. Bu durumlar “telefonu bozan izin hatası” değil, ürünün açık yetki sınırıdır.

## 7. Önerilen teknoloji yığını

| Katman | Seçim |
| --- | --- |
| Ana uygulama | Kotlin + Jetpack Compose; Java platform koduna kademeli adaptör |
| UI durumu | ViewModel, Coroutines, StateFlow; tek yönlü veri akışı; kontrollü efektler |
| Tasarım | Kendi Aero token’ları/Surface bileşenleri; Material 3 erişilebilir bileşen altyapısı, hazır kurumsal görünüm değil |
| Kayıt | Room: yerleşim/profil; DataStore: ayar; Keystore destekli token güvenliği. “DataStore = şifreli kasa” varsayılmaz |
| DI / sözleşme | Hilt, Kotlin serialization, tipli eylem şemaları; özel Binder yalnız süreç sınırında |
| Ağ | OkHttp streaming/cancellation; HTTPS model geçidi; yerel sistem işlemleri için ağ bağımlılığı yok |
| Karakter | Önce hafif 2D atlas/vektör + Compose; bütçe geçerse Rive |
| Ses | Yerel `WakeWordEngine`; bulut ASR/TTS adaptörleri; doğrulanmış yerel TTS/metin yedeği |
| Backend | Node ekosistemi üzerinde TypeScript/Fastify; kimlik doğrulama, kullanıcı kotası, maliyet ve sağlayıcı adaptörleri |
| Test | JUnit, Compose UI, UiAutomator, mevcut sanal modem testleri; Macrobenchmark/JankStats/Perfetto, Baseline Profiles |
| Build | Gradle Kotlin DSL + sürüm kataloğu; uyumlu kararlı Kotlin/Compose/AGP sürümleri sabitlenir; mevcut Java17/JDK21 ayrımı korunur |

İlk destek alt sınırı mevcut **API29** kalabilir; ilk doğrulanmış emülatör matrisi **API35**. Yayına çıkarken target/compile SDK ve dağıtım politikası o tarihteki güncel gereksinimlere göre ayrıca yükseltilir/test edilir; API35’in sürekli yeterli olduğu iddia edilmez. Her cihaz aynı wake-word/bildirim/widget yeteneğine sahip kabul edilmez.

## 8. MVP’den tam launcher sürümüne

Aşağıdaki süreler küçük deneyimli ekip için **kaba iş tahmini**, teslim tarihi değil: iki Android geliştirici, yarı zamanlı backend ve tasarım desteği varsayılır. Donanım/sağlayıcı/lisans belirsizlikleri süreyi değiştirebilir. Aşamaların çıkış kanıtı takvimden önemlidir.

| Aşama | Üretilen şey | Çıkış kapısı | Kaba süre |
| --- | --- | --- | --- |
| **0 — Teknik sözleşme** | Referans 4 GB/6 GB cihaz, API matrisi, tehdit/veri haritası, bulut sağlayıcı maliyeti, Türkçe keyword denemesi | Mikrofon/assistant yaşam döngüsü, foreground/hotword yetenek etiketi ve motor lisansı net; baz performans ölçümü | 3–5 iş günü |
| **1 — v0.3 Native kabuk** | Compose HOME, gerçek uygulama çekmecesi/arama, düzen kalıcılığı, gerçek widget host, cam kalite profili | HOME/uygulama başlatma/widget ekle-sil/ölçek/geri/proses ölümü testleri; mevcut Telefon/SMS/Mağaza testleri korunur | 2–3 hafta |
| **2 — v0.4 Rıfkı MVP** | Canlı 2D karakter, yerel reducer, bulut metin + ASR/TTS, bas-konuş, ilk beyaz liste eylemleri ve açık onay | Gerçek sağlayıcıyla onaylı test, iptal/çevrimdışı/kota; model arama/SMS’yi atlayamaz; çağrı gelince ses susar | 2–3 hafta |
| **3 — Ses/yardımcı beta** | Sistem yardımcı yüzeyi, izinli yazılım wake-word modu, açık destek seviyesi | Ekran açık/kapalı, Doze/pil tasarrufu/rol değişimi/mikrofon iptali/başka ses uygulaması; yanlış uyanma ve pil ölçümü | 1–3 hafta |
| **4 — v0.5 Arayan profilleri** | Yerel profil editörü, VIP/iş/bilinmeyen UI, Rıfkı tepkileri, hızlı yanıt taslakları | Kilit ekranı gizliliği, numara normalizasyonu, fiziksel SIM gelen/giden çağrı, tüm profil/izin ret yolları | 1–2 hafta |
| **5 — v0.6 Günlük merkez** | Opt-in bildirim merkezi, uygulama bazlı izin/özet, Atölye/Heybe/İmece portlarının öncelikli tamamlanması | Hassas içerik aktarım testi, izin geri alma ve adversarial bildirim; eksik modüller açık etiketli | 2–3 hafta |
| **6 — v1.0 Launcher** | Gerçek cihaz regresyonu, performans/erişilebilirlik, imzalı güncelleme/geri dönüş, mağaza yayın hazırlığı | Çoklu SIM/lock-screen/ses rotası/proses ölümü/bozuk belge; kullanıcı mahremiyeti ve yayın politikaları; üretim imzalama | 2–4 hafta |

### “İlk çalışan MVP” için bitti tanımı

Kabuğu ana ekran seçebiliyor, kurulu uygulamayı açabiliyor, widget yerleştirip düzeni yeniden başlatmada koruyabiliyorum. Rıfkı’ya dokunup/yazıp/bas-konuşla gerçekten bulut yanıtı alabiliyorum; görsel tepki/ses/iptal çalışıyor. “Ali’ye geç kalacağım yaz” yalnız taslak oluşturuyor; göndermek için alıcı/içerik ve son onay görüyorum. Ağ kapalıyken ana ekran, Telefon/SMS ve yerel araçlar bozulmuyor. Wake-word ancak doğrulanmış destek düzeyiyle beta olarak sunuluyor. **Bu MVP, donanımsal global always-on veya tam ROM değildir.**

### İlk sprintte açılacak somut işler

1. Mevcut 12 cihaz kabulünü dokunulmaz regresyon tabanı yap; yeni testler ekle, eski kapıyı küçültme.
2. Native `LauncherRepository`: LauncherApps + kullanıcı profili + simge önbelleği/değişim callback’i.
3. `ShellAction` / `ActionPolicy`: kullanıcı isteği, kilit, rol/izin, alıcı belirsizliği ve onay testleri.
4. Tek gerçek veri kaynağına bağlı `ContextSnapshot` + saf `RifkiBehaviorReducer`; saat/pil/çağrı fixture’ları.
5. Compose `HomeScreen` + `GlassSurface` hafif/dengeli; gerçek cihaz başlangıç/kaydırma ölçümü.
6. Gerçek `AppWidgetHost` bağlama/konfigürasyon/geri yükleme ve yaşam döngüsü denemesi.
7. Mevcut `CallController` / SMS / Store için Kotlin adaptörleri; ücretli eylem semantiğini değiştirme.
8. Bulut geçidi için kimlik/kota/iptal ve sahte/gerçek sağlayıcı test ayrımı; anahtar sızdırmama.
9. Rıfkı metin → ASR/TTS oturum prototipi; gerçek mikrofon/sağlayıcı testi için ayrı açık izin.
10. `RifkiVoiceService` hafif süreç ve `RifkiSessionService` görünümü; Türkçe wake-word fizibilitesi ve başarısızlıkta bas-konuş geri dönüşü.

### Üretim kapıları

- Mevcut testlere ek izin reddi/geri alma, varsayılan rol değişimi, süreç ölümü, bozuk veri, kilit, büyük font/ekran okuyucu, tüm kalite profilleri.
- Gerçek SIM/operatör/çoklu SIM, çağrı/ses rotası/DTMF, SMS parça başarısızlığı; MMS eksikse günlük eksiksiz SMS uygulaması diye yayınlamama. RCS için operatör/platform koşulları ayrıca incelenir.
- Keyword için farklı Türkçe telaffuzlar, TV/müzik, yanlış kabul/kaçırma, mikrofon gizlilik anahtarı ve pil testi. Ölçülmeyen cihazda “her zaman dinler” etiketi yok.
- Bildirim içi prompt injection, modelin uydurduğu kişi/uygulama, tekrarlanan ücretli komut ve kilit ekranı veri sızıntısı testleri.
- Backend kimlik/kota/abuse, sağlayıcı KVKK/saklama sözleşmesi; crash loglarında ses/mesaj/anahtar olmaması.
- Üretim imza anahtarı Git/chat dışında; debug APK’dan güncelleme garantisi verilmez. Google Play dağıtımı için SMS/Call Log, asistan, mikrofon FGS ve full-screen intent politikaları ayrıca değerlendirilir.
- Sürekli çalışan mikrofon/asistanın pil/RAM/termal etkisi gerçek cihazda ölçülür. Laboratuvar hedefleri ölçüm sonucu diye sunulmaz.

## 9. “Tam kapasite”nin sınırı

**v1.0 hedefi:** karakterli, yerel performanslı, gerçek servislerle konuşan, günlük kullanılabilir OğuzDows launcher/yardımcı kabuğu. Her Android uygulamasını veya Google servisini yeniden uygulamak değildir. GMS/Play lisans/sertifika, Play Integrity, banka/DRM ve başka uygulamaların özel verileri kendi güven alanlarında kalır. GNOME Software/Flatpak Android çalışma zamanı yerine geçmez.

Cihaza özel “OğuzDows OS” istenirse sonraki ayrı akış: tam model/kod adı → dağıtılabilir kernel/vendor/device ağaçları → bootloader/geri dönüş → SELinux/AVB/şifreleme/OTA → donanım ve CTS/VTS/uygun lisans kapıları. Evrensel telefon ISO’su veya kullanıcıdan habersiz flash yok. PC/Pi yayınları ve PR birleştirme işlemi bu yol haritasından bağımsızdır.

## Teknik kaynak notları

Aşağıdaki sabitlenmiş **AOSP 15 / API35** kaynakları bu plandaki kritik sınırları doğrulamak için incelendi. Bunlar gelecek API/OEM veya Google Play politika incelemesinin yerine geçmez.

- [VoiceInteractionService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/VoiceInteractionService.java): seçili servisin hafif kalması, session’ın ağır iş/UI’yı taşıması, hotword girişlerinin özel API/izin/donanım koşulları.
- [AlwaysOnHotwordDetector](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/voice/AlwaysOnHotwordDetector.java): donanım/enrollment ve kullanılabilirlik durumları.
- [InCallService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/telecomm/java/android/telecom/InCallService.java): varsayılan Telefon rolü, görüşme UI’sı ve zil sorumluluğu.
- [CallScreeningService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/telecomm/java/android/telecom/CallScreeningService.java): 5 saniyelik karar süresi ve hangi çağrıların servisle paylaşıldığı.
- [NotificationListenerService](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/service/notification/NotificationListenerService.java): kullanıcı erişimi, düşük RAM/iş profili sınırları.
- [AppWidgetHost](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/appwidget/AppWidgetHost.java): gerçek widget barındırma ve görünürlük yaşam döngüsü.
