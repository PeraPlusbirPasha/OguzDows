# Atölye ve modern yerel arayüzler

Bu belge **[v1.2 ile yayımlanan](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.2) ortak PC / Raspberry Pi araçlarını** anlatır. Dört yeni imajın ürün kimliği **1.2**, gerçek kaynağı **`dc92fe9e47d8cdc599094281780e274cc49d1470`**; [sürüm notları / mimari, RAM, kurulum ve test sınırları](releases/v1.2.md). Yayımlanmış v1.1 / `29f7738` ve önceki `85dc974` PC/Pi dosyaları bu araçları içermez ve kendiliğinden güncellenmez. Güncel imajlar ayrıca yeniden derlendi; [bağımsız yayın denetimi](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45994504674) 17 dosyanın gerçek byte hash'lerini doğruladı. PR / kullanıcı-QEMU / Xvfb tek başına fiziksel PC/Pi/GPU veya performans kanıtı değildir.

## Nereden açılır?

- **Başlat → Atölye**, Rehber → uygulamalar veya Masaüstü Merkezi → Yerel araçlar.
- `oguzdows-workbench` bütün araçları açar; örneğin
  `oguzdows-workbench --tool checksum` doğrudan dosya doğrulamaya gider.
- Başlat aramasında **`> hesap`**, **`> not`**, **`> renk`** yazıp Enter'a basın.
  Bu bir terminal değildir: yalnız 19 sabit, gözden geçirilmiş yerel eylem vardır.
- `oguzdows-workbench --list-tools` GTK/Pillow, işçi, ağ veya dosya taraması
  başlatmadan 16 araçlık JSON envanteri verir.

## Gerçekten yeni 23 işlev

Aşağıdaki sayım yeni kullanıcı işlevleridir. Eski tema değiştirme, normal uygulama
arama/sabitleme, Mağaza kur/kaldır, haber görselleri ve tek tıklamalı okuyucu
**tekrar sayılmaz**. Geri alma, kopyalama, dar ekran ve klavye kısayolları da ayrı
özellik diye şişirilmez. Kurulum onarımı bu sayıya dahil değildir.

| # | Yeni işlev | Kullanılabilir davranış / sınama |
|---|---|---|
| 1 | **Günüm** | Kalıcı görev oluştur/düzenle/tamamla/sil; öncelik, son tarih, açık/tamamlanan/geciken filtreleri. |
| 2 | **Defter** | Kalıcı yerel notlar; arama, açık kaydet, kaydetmeden ayrılma uyarısı ve yeni TXT dosyası. |
| 3 | **Metin rafı** | Elle eklenen aranabilir parçalar; yalnız kullanıcı düğmeye basınca panoya kopyalar. Pano izleyicisi değildir. |
| 4 | **Yerlerim** | Seçilen klasörlere kişisel yer imleri; doğrulanmış klasörü dosya yöneticisinde açar. |
| 5 | **Dosya bul** | Seçilen görünür ağaçta dosya adı arar; indeks/daemon, gizli dizin veya symlink takibi yok. |
| 6 | **Toplu adlandır** | Gerçek önizleme → onay → üzerine yazmasız uygulama; inode denetimli, diskte kayıtlı son işlem geri alma. |
| 7 | **Dosya doğrula** | SHA-256/SHA-512'yi bloklarla hesaplar; beklenen özetle eşleştirir, okuma sırasında değişmiş girdiyi reddeder. İmza doğrulaması değildir. |
| 8 | **Görsel hazırla** | Oranı koruyan küçültme, JPEG/PNG/WebP çıktı ve metadata taşımama; özgün görseli değiştirmez. |
| 9 | **Metin karşılaştır** | Gerçek unified diff; son satırdaki eksik newline bilgisini korur, `.diff` dışa aktarır. |
| 10 | **JSON masası** | Ayrıştır/doğrula, biçimlendir/küçült; yinelenen anahtar, NaN/Infinity ve aşırı derinliği reddeder. |
| 11 | **Hesap** | Ondalık aritmetik, parantez, sqrt/abs, sınırlı üs; oturumluk geçmiş. Python/shell çalıştırmaz. |
| 12 | **Birimler** | Beş kategori; SI ve ikili veri birimleri ayrı, sıcaklıkta mutlak sıfır denetimi. |
| 13 | **Renk stüdyosu** | WCAG sRGB kontrastı/AA/AAA, RGB, kalıcı renk ekle/seç/kaldır ve CSS palet çıktısı. |
| 14 | **Dünya saatleri** | Gerçek tzdata/yaz saati ile 12 şehir; ağ/GPS yok, gizli pencerede veya başka sayfada zamanlayıcı yok. |
| 15 | **Metin işle** | Türkçe I/ı/İ/i dönüşümleri, satır sıralama/tekilleştirme/boşluk temizleme ve karakter/sözcük/satır sayıları. |
| 16 | **Başlangıç yöneticisi** | Var olan oturum girdilerini yalnız kullanıcı gölgelemesiyle etkinleştir/devre dışı bırak; özgün ayarı geri al. Sistem Exec ve kişisel sonraki düzenlemeler korunur. |
| 17 | **Mağaza istek listesi** | Uygulamayı kurmadan listeye ekle/çıkar; kalıcı, yerel liste filtresi. |
| 18 | **Mağaza yerel teşhisi** | Eksik motor/eklenti/API/dil dosyası, taban/mimari ve devre dışı/çakışan Flathub durumunu çevrimdışı raporla; açık kopyalama. |
| 19 | **APT / Flatpak karşılaştırması** | Aynı gözden geçirilmiş uygulamanın kapsamını, yerel aday sürüm/boyutunu ve runtime farkını birlikte gösterir. Bilinmeyen Flatpak boyutu uydurulmaz. |
| 20 | **Çevrimdışı okuma listem** | Kaynak/önbellek değişse bile saklanan en fazla 40 RSS metni/özeti; haber kaydet/çıkar. Tam site kopyası değildir. |
| 21 | **Okundu / okunmamış takibi** | Yerel geçmiş ve okunmamış filtresi; 1000 kayıt sınırı, geçmişi ayrıca onayla temizleme. Kaydedilen haberler silinmez. |
| 22 | **Haberi TXT dışa aktarma** | Seçili RSS metni, yayıncı ve kaynak bağlantısını yeni özel dosyaya, işçide aktarır. Var olan dosyayı ezmez. |
| 23 | **Sabit komut paleti** | Başlat'ta `>` araması / `oguzdows-hub --commands`; 16 araç + Mağaza kaynakları/Masaüstü Merkezi/İzleyici. Serbest komut kabul etmez. |

Atölye çekirdeği: `tests/test_workbench.py`. Gerçek GTK ve geçici gerçek dosya
akışları: `tests/smoke-workbench.py`. Yerel C Mağaza/Haber/Başlat derlemelerinin
kendi ayrı `--test` hedefleri vardır. Paket fixture'ları gerçek APT kurulum
kanıtı yerine geçmez; kurulum testi aşağıda ayrıca tanımlıdır.

## Ortak tasarım, daha az yük

- Atölye: geniş ekranda sol gezinme + araç kartları, dar ekranda araç seçici;
  araç sayfası yalnız açılınca kurulur. Ctrl+K araç arar, Ctrl+S kaydeder,
  Escape durdurulabilir okuma/hesap isteğini durdurur.
- Ortak `modern.css` ve olay tabanlı `ui_theme`: Rehber, Masaüstü Merkezi,
  Güncelleyici, İmece, Uyumluluk, Cihaz Merkezi, gerçek oturum seçici,
  kurucu başlatıcısı, hafif karşılama, Rıfkı/anlatım ve GNOME merkezi denetimi.
  C karşılığı Mağaza, Haber, Başlat ve İzleyici'de aynı tasarım kurallarını kullanır.
- Açık/koyu yüzey hiyerarşisi, ince kenarlar, erişilebilir odak, okunabilir metin ve
  optimize simge basış/yükselme tepkisi. Sürekli dekoratif animasyon, webview,
  per-tile blur veya yeni çizim servisi yoktur.
- HighContrast seçimi ezilmez. Azaltılmış hareket/düşük kaynak kuralları, normal
  kare maximized/tiled/fullscreen geometri, dosya alanlarının opaklığı ve daha
  önceki gerçek uygulama tema/PrintScreen onarımları korunur.
- Masaüstü Merkezi genişte yan menü, dar pencerede üst geçiş kullanır.
  Bir üçüncü taraf uygulamanın bütün iç sayfalarının yeniden yazıldığı iddia edilmez.

### Açık kaynak bütçeleri

| İş | Uygulanan sınır |
|---|---|
| Açılış / kapalı uygulama | Yeni autostart/systemd servisi, indeksleyici, ağ isteği, clipboard dinleyicisi yok. |
| Atölye | En fazla **1 işçi / 1 istek**. GTK yalnız ana iş parçacığında güncellenir. Yazma sırasında kapatma/çakışan düzenleme engellenir. |
| Araç sayfaları | Eski sayfa yok edilir; Pillow yalnız görsel aracı kullanıldığında yüklenir. Koleksiyon Unicode arama anahtarları işçide hazırlanır. |
| Kitaplık | Toplam **4 MiB JSON**, koleksiyon başına **500** kayıt; atomik 0600 yazım ve süreçler arası kilit. |
| Dosya arama | **20.000 girdi / 200 sonuç / 8 saniye / 12 derinlik**; başka aygıta geçmez, iptal edilebilir. |
| Adlandırma | En fazla **200 dosya**; tüm girdi taraması ayrıca **20.000 / 8 saniye**. NOREPLACE ve kilitli geri alma günlüğü. |
| Özet | Sabit **256 KiB okuma bloğu**, ilerleme bildirimleri en fazla 4/sn. |
| Görseller | **32 MiB girdi / 8 megapiksel / 1 kare**; hedef 16–4096 piksel. Büyük dosya için dış görsel düzenleyici kullanın. |
| Metin / JSON | Araç girdisi **131.072 karakter**, diff en fazla **1500 newline**, JSON **40 katman**. |
| Hesap | **256 karakter / 64 AST düğümü / 28 basamak**, tam sayı üs −12…12. eval/exec yok. |
| Saatler | Açık/görünür sayfada **dakikada bir**; gizlenince veya sayfadan ayrılınca kaldırılır. |
| Haber kitaplığı | **2 MiB / 40 saklanan haber / 1000 okundu**; seri, birleştirilen arka plan atomik yazımları. |
| İstek listesi | **64 KiB**; çıkarılan anahtar gerçekten kaldırılır. Bozuk dosya sessizce sıfırlanmaz. |

Sınırlar bir fiziksel donanım hız garantisi değildir. Özellikle 512 MiB / Pi Zero
üzerinde başka ağır uygulamalarla aynı anda görsel işleme rahatlığı vaat edilmez.

## Flatpak / GNOME Yazılımlar kurulum onarımı

### Düzeltilen somut kaynak sorunları

1. Eksik Flatpak motoru veya GI köprüsü için kurulabilir, bütünlüğü
   doğrulanan bir **sabit bileşen demeti** yoktu. Artık gerçek imzalı APT adayı/bağımlılığı çözülür.
2. GNOME Software'in tek başına var olması hazır olduğu anlamına gelmez:
   Flatpak eklentisi, PackageKit, ISO639 verisi ve başlatıcı bağımlılıkları birlikte
   tamamlanır. Eksik eklenti varken gelişmiş merkez onarım yoluna yönlendirilir.
3. Resmî ama **devre dışı Flathub** kaydı yanlışlıkla hazır sayılabiliyordu. Açık
   onayla yalnız bu kullanıcıdaki o kayıt etkinleştirilir ve tekrar okunur.
   Boş CLI seçenek sütunu da yanlışlıkla bozuk kaynak diye reddedilmez.
4. Pi/generic ARM üretim katmanı GNOME merkezinin Python başlatıcı/yaşam döngüsü
   dosyaları ve varsayılan-kapalı autostart/şema ayarlarını artık kaldırmaz.
5. Pi/ARM'de yalnız Mağaza'nın imzalı liste yenilemesi için ayrı, dar
   `store-refresh` kapısı vardır. Genel PC güncelleyicisi, Pardus veya sürücü
   kapsamı ARM'e gelişi güzel açılmaz.

**Kullanıcının bildirdiği özgün hata günlüğü/mimarisi verilmedi.** Bu kaynak
kusurlarının düzeltilmesi ve temiz container'da başarılı kurulum, belirli bir
cihazdaki bütün ağ/depo/kilit sorunlarının uzaktan giderildiği iddiası değildir.

### Kullanım

1. Güncel kaynaktan üretilmiş sistemde **Mağaza → Kaynaklar → Yerel bileşen
   teşhisi / raporu…**. Bu adım çevrimdışıdır ve paket kurmaz.
2. Aday paket yoksa **Paket listelerini yenile…**: yalnız mevcut depolardan,
   açık onay ve yönetici doğrulamasıyla listeleri yeniler; yeni depo eklemez.
3. **Flatpak bileşenlerini kur / tamamla…** veya
   **GNOME Yazılımlar’ı kur / tamamla…** seçin. Önce gerçek planı okuyun,
   sonra o planı ve yönetici isteğini ayrıca onaylayın.
4. Uygun 64 bit mimaride **Flathub’u ekle / doğrula…**. Önceden resmî/imzalı
   ama kapalı kaynak varsa etkinleştirir; aksi halde resmî HTTPS tanımını ister.
5. **Gelişmiş paket merkezi · GNOME Software** isteğe bağlıdır. Arayüzü kapatmak
   devam eden işlemi zorla öldürmez; tam çıkış ayrı kullanıcı onayıdır.

Demetler:

- `flatpak-support`: `flatpak`, `gir1.2-flatpak-1.0`, `xdg-desktop-portal`,
  `xdg-desktop-portal-gtk`, `ca-certificates`.
- `software-center`: `gnome-software`, `gnome-software-plugin-flatpak`,
  `packagekit`, `iso-codes`, `flatpak`, `gir1.2-flatpak-1.0`, `python3-xlib`.

Serbest root paket/komutu, farklı dağıtım deposu, `--no-gpg-verify`, otomatik yeni
remote, purge/autoremove veya kilit dosyası silme yoktur. Planın özeti değişirse
uygulama reddedilir. Kalıcı APT kurulumu canlı USB'de bilerek kapalıdır.

**Flathub uygulamaları x86_64/aarch64 ile sınırlıdır.** i386/armhf'de motorun veya
GNOME Yazılımlar'ın kurulabilmesi güncel 64 bit Flathub uygulamalarını çalıştırma
sözü değildir; bu cihazlar imzalı sistem paketlerini kullanır.

## Veriler, izin ve geri alma

- Atölye: `$XDG_DATA_HOME/oguzdows/workbench/library.json`.
  Varsayılan `~/.local/share/...`. Kitaplık **şifreli kasa değildir**.
- Adlandırma: aynı dizindeki `rename.json`; kaynak dosyalar değil yalnız geri
  alma planıdır. Önceki plan varken yenisi üzerine yazılmaz. Geri alma dosya
  değiştiyse/çakışıyorsa reddedilir. Başka uygulamayla eşzamanlı adlandırmayın.
- Başlangıç: yalnız `$XDG_CONFIG_HOME/autostart/*.desktop`; özgün kayıtlar
  Atölye'nin `startup/` altında tutulur. Yeni Exec üretilmez, sistem dosyası
  değiştirilmez, çalışan süreç kapatılmaz. Sonraki oturumda geçerlidir.
- Haber: `$XDG_DATA_HOME/oguzdows/news/library.ini`; yalnız RSS metni/özeti,
  metadata ve yerel okundu anahtarları. Saklanan görseller kalıcı arşiv garantisi
  taşımaz; görüntü önbelleği temizlenebilir.
- İstek listesi: `$XDG_CONFIG_HOME/oguzdows/store/wishlist.ini`.
- TXT/JSON/diff/CSS/görsel dışa aktarma **yeni dosya** ister; var olan dosyanın
  veya symlink hedefinin üzerine yazılmaz. Bir diff/özet dosyası özgün veriyi
  güvenli, doğru veya zararsız ilan etmez.

Dosya bozuksa veya başka kullanıcıya aitse özgün veri korunur. Elle müdahaleden
önce uygulamayı kapatın ve ilgili kişisel dosyayı yedekleyin; yapılandırmanın
silinmesi genel bir "onarım" adımı değildir.

## Doğrulama ve mimari sınırları

- Yerel Python: tüm birim testleri; GTK'sız çalışabilen çekirdek gerçek geçici
  dosya, Pillow, renameat2, kilit ve geri alma testleri içerir.
- PC: Bookworm/Trixie gerçek GTK3, üretim ve fixture C derlemeleri; 1024×768 açık
  ve 360×800 koyu Atölye eylemleri; eski geometri/tema/PrintScreen testleri.
- ARM64: **ARM64 runner**, gerçek Debian Bookworm/Trixie Python/GTK/C kütüphaneleri;
  aynı masaüstü/kompakt gerçek dosya eylemleri ve gerçek imzalı bileşen kurulumu.
- i386 / armhf: kendi 32 bit Python/C/GTK ABI'sinde çekirdek ve başsız native
  sürüm testleri. Kullanıcı-QEMU sonuçları GPU/oturum veya gerçek kart testi değildir.
  Debian armhf / Cortex-A7 sınaması **ARMv6 / Raspbian / fiziksel Pi Zero** sınaması değildir.
- Yeni araçlar PC ve Pi/generic ARM üretim katmanlarında tutulur. Çıktı
  sözleşmeleri kaynak hash'lerini denetler; eski imajlar yeniymiş gibi sunulmaz.

`.github/workflows/portable.yml` ve `tests/smoke-store-bootstrap.py`, yalnız tek
kullanımlık GitHub container'larında iki gerçek bileşen demetini kurar; yanlış
plan özeti reddini, kurulum sonrasında boş planı ve GI/ISO639 dosyalarını sınar.
Normal kullanıcı sistemi ve canlı USB bu betiği çalıştıramaz. Bu test, interaktif
Polkit parolası veya Flathub'dan uygulama indirme kanıtı değildir.

Atölye GTK raporundaki 800 ms boşta CPU örneği **busy-loop korumasıdır**;
`peak_rss_kib` test sürecinin bütün eylem/ekran görüntüsü zirvesidir, masaüstü
RAM'i veya soğuk açılış tüketimi değildir. Bu geliştirmeye eski ISO'nun RAM
rakamları atanmaz. Fiziksel Pi/GPU/Wayland ve bütün Flathub uygulamaları için
uyumluluk veya hız garantisi verilmez.
