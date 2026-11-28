# Yayın ve sürümleme politikası

[← Proje vitrini](../README.md) · [Yayınlar](https://github.com/PeraPlusbirPasha/OguzDows/releases)

## Ana yayın adları

- İlk yayımlanmış PC sürümü **v1.0.0 · OğuzDows 1.0 Ay Yıldız** olarak kalır. Kaynak etiketi, ISO adları veya dosya içeriği yalnızca yeni bir adlandırma düzenine geçmek için değiştirilmez.
- Bundan sonraki yeni ana yayınlar **v2.0**, **v3.0**, … olarak adlandırılır. Sırf README, sürümleme belgesi veya GitHub görünümü değişti diye yeni ana sürüm yayımlanmaz.
- Yayın aracı hem yeni `v2.0` biçimini hem mevcut `v1.0.0` biçimini kabul eder. Bir etiket biçiminin kabul edilmesi o sürümün yayımlandığı anlamına gelmez.
- Bu düzen bir yayın takvimi, otomatik yükseltme sistemi veya henüz tamamlanmamış özellik taahhüdü değildir. Yeni bir ISO mevcut kurulumları kendiliğinden değiştirmez.

## 2.0 · Akıncı — güncel ana yayın

**[v2.0 · OğuzDows 2.0 “Akıncı”](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0) yayımlandı ve son sürüm olarak doğrulandı.** Kullanıcı isteğiyle **amd64/i386 PC ISO + Pi armhf/arm64 IMG.XZ + gerçek native launcher APK** aynı **`5a44de0dde676d901a32be40d631d481e213439d`** kaynağından yeniden derlendi. İmajların iç ürün sürümü **2.0**, ana APK **`2.0.0-akinci` / versionCode20**; eski 1.2 imajları veya 0.4 APK yeniden etiketlenmedi. APK debug imzalı normal uygulamadır, ROM/OTA/GSI değildir; statik web tasarım arşivi ayrıca etiketlidir. [Sürüm notları / indirmeler](releases/v2.0.md) · [Yayın kaydı](releases/v2.0-release.json).

Başarılı [PC 46092345482](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092345482), [Pi 46092347693](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092347693) ve [mobil 46092350348](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348) kabulünden sonra [46099334688 aktarımı](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46099334688) özgün dosyaları mevcut taslağa taşıdı. Ayrı salt-okunur **[46100003996 denetimi](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46100003996)**, kamuya açılmadan önce **26 dosyanın tamamını** yeniden indirip boyut/SHA-256, **26 JSON + 1 gerçek MediaProjection JPEG’i** ve APK paket/sürüm/sertifika/kabul kapılarını doğruladı; release'e yazmadı. SHA256SUMS dört imaj + üç APK + web olmak üzere sekiz girdidir. Yayından sonra herkese açık latest/etiket ve 26 indirme ucu kontrol edildi.

**Ürün kaynağı ile yayımlayıcı ayrı kimliktir:** aktarım/yayın aracının `11339644aab61ebd3df6dc7d911753a6cbf19346` commit'i derlenmiş kaynak veya etiket hedefi değildir. Sonraki belge/kanıt testleri de bu imajları değiştirmez. v1.2/v1.1/v1.0.0 etiket/gövde/dosya kimlikleri, boyutları ve hash'leri korunmuş olarak doğrulandı. Özgün 2.0 yayımı sırasında PR açık/taslaktı; bu tarihsel yayın kaydı sonraki kaynak/site birleştirmesiyle geriye dönük değiştirilmez. Cihaza flash veya ücretli AI etkinleştirilmedi.

**OğuzKöprü/1**, PC/Pi/telefon arasında yalnız yerel izinli dosya ve salt ekran bağlantısıdır; uzaktan SMS/Telecom/yükleyici yetkisi veya bulut eşitleme değildir. Fiziksel PC/Pi/telefon/SIM, Pi performansı ve Zero siyah ekranı için tamamlanmamış testler tamamlanmış sayılmaz. Bulut üretken Rıfkı, ses/wake-word ve telefon ROM'u bu yayında tamamlanmadı. İlk iki reddedilmiş aktarım ve meşru test-APK manifest farkına ilişkin bağımsız teşhis [2.0 notlarında](releases/v2.0.md) saklanır; native kabul kapıları gevşetilmedi.

## 2.0 Akıncı · yalnız ARM düzeltmesi 1

**[v2.0-arm1](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0-arm1)**, ürün sürümü **2.0** kalacak şekilde yalnız Raspberry Pi armhf/arm64 imajlarını yeniler. Etiket hedefi/imaj kaynağı **`c5063ee8b558cb6c8af8301143cf3ce02106e2aa`**; PC ISO, mobil APK, özgün v2.0’ın 26 dosyası ve eski v1.2/v1.1/v1.0.0 yayınları değişmez. `v2.0-arm1` sonraki ana sürüm değildir ve özgün v2.0’ın Latest işaretini devralmaz. [Notlar](releases/v2.0-arm1.md) · [Gerçek yayın kaydı](releases/v2.0-arm1-release.json).

[İki mimari derleme 46142709227](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46142709227) sonrası [aktarım 46147922509](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46147922509) özgün yeni imaj baytlarını ayrı taslağa taşıdı. **[Bağımsız salt-okunur denetim 46149729927](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46149729927)**, 11 yayın dosyasının tamamını yeniden indirip hash’ledi; 13 JSON ham kanıtı, iki salt-okunur MBR/FAT/ext4 imaj kimliğini, temiz kaynağı, 75 birebir kaynak/varlık sözleşmesini ve gerçek hedef GTK3/Xfce tema/duvar kâğıdı/piksel raporunu tekrar doğruladı. İmajlar aktarım sırasında yeniden paketlenmedi.

Yeni Pi indirmeleri yalnız kendi `.sha256` / iki girdili ARM `SHA256SUMS` listesiyle eşleştirilir. Özgün 2.0’ın sekiz girdili listesi yeni ARM baytlarını kapsamaz. Web sitesi her platformu kendi doğrulanmış yayın kaydına bağlar; PC/APK için eski kaynak kimliği yeni ARM kaynağı diye sunulmaz. Kaynak/site değişiklikleri [PR #2](https://github.com/PeraPlusbirPasha/OguzDows/pull/2) üzerinden main’e alınır; eski etiket taşınmaz.

Hedef kullanıcı-QEMU/host Xvfb görünüm kapısı, ayrı native ARM64 Welcome testi veya fiziksel Pi kabulüyle karıştırılmaz. Zero siyah ekranı ve fiziksel boot/LightDM/PAM/GPU/SD/performans sınırları korunur. Yeni mobil kabul iddiası yoktur; daha yeni CI’deki ANR/launcher UI-odak başarısızlıkları giderildi sayılmaz. Mevcut SD kartlar otomatik yükselmez; flash, ücretli servis veya bulut AI açılmaz.

## 1.2 ara güncellemesi

**[v1.2 · OğuzDows 1.2](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.2) yayımlandı.** Dört imajın iç ürün sürümü **1.2**, kaynak commit'i ve etiket hedefi **`dc92fe9e47d8cdc599094281780e274cc49d1470`**. Kullanıcı isteğiyle amd64/i386 PC ve armhf/arm64 Pi bu ortak kaynaktan yeniden derlendi; eski 1.1 imajları yeniden adlandırılmadı. Atölye/23 yeni işlev ve Mağaza onarımı bu yeni dosyalardadır. [Sürüm notları / indirme / testler](releases/v1.2.md) · [Yayın kaydı](releases/v1.2-release.json).

[PC](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45984535667) ve [Pi](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45984521207) başarıyla tamamlandı. [Yayın aktarımı](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45993701545) dört özgün checksum'u ve salt-okunur iç kaynak/sürüm kimliklerini, [ayrı denetim](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45994504674) 17 dosyanın tamamını yeniden indirip hash'ledi ve 21 JSON'u karşılaştırdı; denetim release'e yazmadı. Yayımlama açık kullanıcı isteğidir; PR birleştirilmedi.

Bu yeni ara yayın ana sürümlerin v2.0 / v3.0 adlandırmasını değiştirmez. v1.0.0 / v1.1 etiketleri, yayın gövdeleri ve dosya kimlik/boyut/hash'leri ayrıca değişmemiş olarak doğrulandı. Pi fiziksel boot/GPU/RAM performansı ve Zero siyahlık sınırları görünür kalır.

## 1.1 ara güncellemesi

**[v1.1 · OğuzDows 1.1](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.1)**, v1.0.0 üzerine geliştirilen ara güncellemedir; sonraki ana sürümlerin v2.0 / v3.0 adlandırmasını değiştirmez. **amd64/i386 PC ISO’ları ve armhf/arm64 Raspberry Pi SD/USB imajları** aynı `29f7738534cd00bd87887f530355ef45e01eb28c` kaynağına bağlıdır. v1.0.0 etiketi/ISO’ları/sekiz yayın dosyası korunur. [1.1 sürüm notları ve CPU/RAM indirme tablosu](releases/v1.1.md) · [Test kanıtı](V1.1-TEST-KANITI.md).

Yayın aktarımı **45201307283**, mevcut başarılı PC **45170572813** ve Pi **45170576727** çıktılarını kullanır; yeni imaj derlemez. Özgün SHA-256’lar yeniden hesaplanır; ISO/squashfs ve Pi MBR/FAT/ext4 iç kaynak/sürüm kimlikleri salt okunur denetlenir, Pi boot/hesap/özellik doğrulayıcısı yeniden çalıştırılır. Ham raporlar ve kaynak kilidi yayın dosyalarıdır. Yükleme sonrası salt-okunur **45203390800** denetimi 17 dosyanın tamamını yeniden indirip hash’ledi, arşivdeki 21 JSON’un hash/boyutunu doğruladı; yayına yazmadı. v1.1 Latest/etiket/oturumsuz indirme uçları ayrıca kontrol edildi. Yalnız belge/test/yayın aracını içeren sonraki commit, imaj kaynağı veya etiket hedefi değildir.

**Pi portları deneyseldir:** ARM kullanıcı-QEMU/Xvfb, fiziksel kart/LightDM/PAM/GPU/RAM performansı kanıtı değildir. İlk nesil Zero/Zero W’de hesap sonrası siyahlık bildirimi açıktır. Bu sınırlar sürüm notları ve indirme tablosunda görünür kalır.

## Her yayında aynı kimlik

Her yeni yayında ürün içindeki sürüm bilgisi, açık kaynak commit kimliği, yayın etiketi, sürüm notları ve ISO’lar birbiriyle uyumlu olmalıdır. Daha eski ISO’lar yeni ürün değişikliklerini içeriyormuş gibi yeniden etiketlenmez.

ARM gibi ayrı kapsamlı düzeltme etiketi ürün sürümünü değiştirmeden kullanılabilir; hangi mimarinin gerçekten yeniden derlendiği açıkça belirtilir ve eski etiket/dosyalar korunur.

Sonraki değişiklikler yalnızca belge, test veya yayın aracıyla sınırlıysa mevcut ISO’nun yeniden derlenmediği açıkça belirtilir. Kaynak çalışma ağacının temizliği belirlenemediğinde `source_dirty: null`, temiz (`false`) olarak sunulmaz.

## Yayın kontrol listesi

1. Kaynak değişikliklerini çalışma dalında tamamla, birim/kontrat ve ilgili gerçek ortam testlerini çalıştır.
2. PC için başarılı amd64/i386 derlemelerini ve mimariye uygun hedef OS açılış testlerini kullan. Yayımlanan ISO’nun içeriği/kaynak commit’i eşleşmeli.
3. Boşta RAM iddiası varsa tam grafik oturumunu ölç; yöntem, örnekler, koşullar ve hedefi tutturamayan sonuçlar dahil sınırlamaları açıkça paylaş. Bileşen RSS’i veya GRUB menüsü tam masaüstü kanıtı değildir.
4. Yayın **taslağı** oluştur. Hedef commit’i açıkça seç; varsayılan dalın en son commit’ine sessizce etiket koyma.
5. ISO’ları özgün `.iso.sha256`, Pi imajlarını `.img.xz.sha256` dosyalarıyla doğrula. Seçilen bütün mimariler, ayrı checksum’lar, birleşik `SHA256SUMS`, kaynak/dosya manifesti ve ham test kanıtlarını ekle. Pi paket envanterleri ve `pi-gen.lock.json` korunur. Sıkıştırılmış Pi imajı ISO diye sunulmaz.
6. Türkçe sürüm notlarında yeni özellikleri, imajın gerçek kaynak kimliğini, test sonuçlarını ve bilinen sınırları belirt. CPU mimarisi, RAM önerisi, depolama/önyükleme koşulları ve deneysel cihazları ayrı indirme tablosunda açıkla. Yapay zekâ görsel/ses kökenini gizleme.
7. Ayrı salt-okunur koşuda eksiksiz dosya listesinin **tamamını yeniden indir**; boyut/SHA-256 ve ham kanıtları doğrula. Mobil paket varsa gerçek ana APK paket/sürüm/sertifikasını, test runner/hedef paketini ve tam native/izin/iptal/yakalama kabulünü ayrıca denetle; debug imzayı üretim imzası diye sunma. Yalnız başarılı denetimden sonra taslağı yayımla. Sonrasında herkese açık son sürüm/etiket/indirme uçlarını tekrar kontrol et.
8. README’deki güncel sürüm, ISO, checksum ve test bağlantılarını yeni yayına taşı. Önceki sürümlerin yayınlarını ve kanıtlarını koru.

**Süren bir derleme, yeni yayın işi geldi diye iptal edilmez veya yeniden başlatılmaz.** Artefakt aktarımı ISO’yu yeniden paketlemez; yalnızca gerekli başarılı çıktıları taşır. `pc-release` işi isteğe bağlı `pi_evidence_run` ile aynı kaynaklı iki Pi imajını da kapsar; kendiliğinden yeni release/etiket oluşturmaz, dosya ezmez ve taslağı herkese açmaz; son yayın ayrı bir karardır.

## v1.0.0 kaydı

- [Yayımlanmış sürüm](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.0.0)
- [Türkçe sürüm notları](releases/v1.0.0.md)
- [Kaynak, SHA-256 ve ölçüm kanıtı](MASAUSTU-TEST-KANITI.md)

Bu belgede fiziksel PC/Raspberry Pi, Secure Boot, gerçek KDE/GNOME oturumu, şifreli tam kurulum veya gerçek yetkili paket kurulumları için tamamlanmamış testler tamamlanmış sayılmaz.
