# ARM / Raspberry Pi OS mimari karşılaştırması ve sürüm kapıları

Bu belge **v1.1 geliştirme çalışmasıdır**. Özellik kaldırarak küçük imaj üretme hedefi yoktur: ortak Xfce / Başlat, açık-koyu temalar, karşılayıcı / Rıfkı / doğal kayıtlar, kültür araçları / galeri, yerel mağaza, cihaz merkezi ve dosya inceleme korunur. CPU, boot yolu ve uygulama motoru sınırlamaları ise gizlenmez.

**Karşılaştırmanın kapsamı:** resmî kaynak ağaçları, paket listeleri, boot / export betikleri ve bizim tarifimiz. Yayımlanmış Raspberry Pi OS binary imajları indirip boot ederek RAM / hız karşılaştırması yapılmadı. Bu sandbox'ta fiziksel Pi yoktur. “Pi OS'tan yüzde X hızlı” veya “her ARM cihazına otomatik port” iddiası yoktur.

## 1. Gerçek hatadan elde edilen kanıt

[`f6d12f0` Pi çalışması 44800915275](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44800915275) **başarısız tamamlandı**; iki mimari de aynı noktada durdu:

```text
Firefox politikası birleştirildi; paket bağlantısı ve diğer ayarlar korundu.
... End .../00-desktop/01-run.sh
... Begin .../00-desktop/02-run.sh
OğuzDows minimum ARM CPU / Python / GTK: başarılı
XDG_RUNTIME_DIR "/run/user/1001" not available
xfce4-session: Cannot open display: .
```

- Önceki Firefox çakışması giderilmiş: hesap / hizmet yapılandırması, görsel üretimi ve hedef mimaride C mağazası derlemesi dahil `01-run.sh` iki mimaride tamamlandı.
- Minimum CPU ile Python / GTK **içe aktarımı** geçti; bu, GTK penceresi veya tam Pi masaüstü boot testi değildir.
- Hata Xfce'nin kaldırılmasını gerektirmiyor. `xfce4-session --version` bile bu sürümde GTK ekran bağlantısını başlatıyor; başsız chroot'ta geçerli ekran ve kullanıcı çalışma dizini yoktu.
- Günlük toplama / artefakt yükleme iki mimaride de başarılı oldu. Günlük ZIP'i bu sandbox'ın izinli ağ uçları dışında kalan Azure adresine yönlendiği için yerel indirmesi EOF verdi. Yukarıdaki hata, doğrudan job/check annotations API'sindeki gerçek günlük kuyruğundan alındı.

Yeni kapı host **Xvfb** ekranını yalnızca X soketi ve özel Xauthority ile hedefe açar; TCP dinlemez / `-ac` kullanmaz. Hedefte `env -i`, özel HOME/XDG dizinleri ve yeni **D-Bus oturumu** kullanılır. Hostun `/run/user/1001` veya oturum veri yolu miras alınmaz. `xvfb-run`'ın POSIX shell sınırında dışa aktarılmış Bash işlevleri kaybolduğundan, çocuk süreç hash'i denetlenen resmî `scripts/common` içinden `on_chroot` işlevini yeniden alır. Bu sınır gerçek `/bin/sh → bash` regresyonuyla sınanır.

Xvfb / xauth **build host araçlarıdır**; hedef uygulama listesinden özellik çıkarmak veya hedefe yeni boşta daemon eklemek için kullanılmaz. QEMU / test dosyaları ve soket bağlantısı hata halinde de temizlenir. Asıl hata kodu saklanır; başarılı testten sonra temizliğin bozulması da build'i başarısız yapar. Bash `EXIT` kapanışında yalnızca `return` bunu sağlamadığından açık `exit` ve gerçek stage betiğiyle hata enjeksiyon testi vardır. `QEMU_CPU`, hedef çocuk işlemlere de minimum CPU'yu taşır. Resmî `on_chroot` işlevinin `mount | grep -q` kontrolleri, yeni `pipefail` ayarı yüzünden SIGPIPE'ı “bağlı değil” sanmasın diye kendi upstream kabuk davranışı içinde çağrılır.

### Host kapısının yakaladığı Türkçe CLI çıktısı hatası

`fea3915` için [44814981635](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44814981635) ve [Pi PR 44814919820](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44814919820), yerel mağazanın gerçek C/GTK derleme ve pencere smokundan sonra yeni sürüm yanıtı denetiminde **başarısız** oldu. İmaj işleri bu host kapısı nedeniyle otomatik atlandı; işler iptal edilmedi veya yeniden başlatılmadı. Aynı kaynağın [PC PR 44814919805](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44814919805) kontrolü başarılıydı.

C programı GTK'ye girmeden `--version` döndürdüğü için locale hâlâ `C` idi: `LANG=C.UTF-8` tek başına C programında `setlocale` çağırmaz. Gerçek GLib ile tekrar üretimde çıktı `O?uzDows Ma?aza ? GTK`; açık `setlocale(LC_ALL, "")` sonrasında `OğuzDows Mağaza · GTK` oldu. Başsız yol artık locale'i kendisi başlatır; sürüm testi gevşetilmez. İki regresyon üretim C fast-path'ini gerçek GLib'e bağlayarak eski/yeni davranışı karşılaştırır ve bozuk sürüm metninin reddedilip sınırlı ayrıntıyla raporlandığını sınar. Bu mikrotestte yalnızca üç GTK sürüm getter'ı sabittir; tam GTK frontend / ARM derleme veya fiziksel ekran testi diye sunulmaz. Hedef GUI kontrolü hata halinde artık iki gerçek sürüm satırını da rapora koyar.

**Gerçek CI takibi:** düzeltme kaynağı **`469cbc310497627ac94c1363a277dac19e0a8875`** için [Pi PR 44815856038](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44815856038) ve [PC PR 44815855973](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44815855973) başarılı. Host raporu GTK **3.24.41**, `xfce4-session 4.18.3 (Xfce 4.18)` ve doğru **`OğuzDows Mağaza · GTK 3.24.41`** çıktısını kaydetti; `scope=host-gui-only`, fiziksel/GPU/performans bayrakları false. Aynı ürün kaynağı için [Pi 44816162831](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44816162831) bir kez başlatıldı: **başarısız tamamlandı**. Host ve **arm64 imaj işi başarılı**; armhf, Raspbian ayna yönlendiricisinin seçtiği `archive-bm.raspbian.org` üzerinden `libvorbis0a_1.3.7-1_armhf.deb` indirilirken APT 100 ile durdu. Bu bir CPU uyumsuzluğu kanıtı değildir. ARM64 minimum Cortex-A53 kullanıcı-QEMU/GTK ve export kapısını geçti; imaj arşivi bu sandbox’ta yeniden indirilip hash doğrulanmadı. Fiziksel boot / GPU / performans sonucu değildir. Sonraki yalnızca belge güncellemesini ürünün derleme kaynağıyla karıştırmayın.

## 2. İncelenen resmî kaynaklar

Tam tar arşivleri indirildi, mevcut kilitteki SHA-256 ile doğrulandı; iki ağaçta 12 kritik dosya ayrıca karşılaştırıldı. Kilitler sessizce güncellenmedi.

| Kaynak | İncelenen commit |
|---|---|
| [pi-gen · bookworm / armhf](https://github.com/RPi-Distro/pi-gen/tree/8b71acc79287392a63985ba383c496d5419426b4) | `8b71acc79287392a63985ba383c496d5419426b4` |
| [pi-gen · bookworm-arm64](https://github.com/RPi-Distro/pi-gen/tree/3a7eeb9bd49278375b8871b284c1aacf54a31b34) | `3a7eeb9bd49278375b8871b284c1aacf54a31b34` |
| [raspi-config · bookworm](https://github.com/RPi-Distro/raspi-config/blob/aabbd96212484856e324eff82d519a5ff243cd9b/raspi-config) | `aabbd96212484856e324eff82d519a5ff243cd9b` |
| [raspberrypi-sys-mods · ilk boot](https://github.com/RPi-Distro/raspberrypi-sys-mods/blob/5c66bcd45eadb55af2419805700e2fdb30d52584/usr/lib/raspberrypi-sys-mods/firstboot) | `5c66bcd45eadb55af2419805700e2fdb30d52584` |

Son iki kaynak karşılaştırma referansıdır; kurulan APT paketinin birebir aynı Git commit'inden üretildiği varsayılmaz. APT güvenlik / firmware güncellemeleri nedeniyle her build'de gerçek paket sürümleri ayrıca raporlanır.

## 3. Mimari farklar ve korunan yapı

| Konu | Resmî yapı / fark | OğuzDows uyarlaması |
|---|---|---|
| 32-bit taban | ARMv6 için Raspbian armhf; sıradan ARMv7 Debian armhf ile eşdeğer değil | Aynı stage0 / kaynaklar; minimum `arm1176`; ELF32 ARM hard-float denetimi. Zero / Pi 1 yolu korunur. |
| 64-bit taban | Debian arm64 + Raspberry Pi paketleri | Aynı stage0 / kaynaklar; minimum `cortex-a53`; ELF64 AArch64 denetimi. x86 PC ikilisi kopyalanmaz. |
| Çekirdek ailesi | armhf: v6/v7/v7l/v8; arm64: v8 + **2712** | Kilitli model DTB / kernel / initramfs listeleri ve resmî export korunur. Bütün kartlara `kernel8.img` zorlanmaz. |
| Host / hedef sayfa boyutu | Resmî build guard yalnızca **armhf host için 4 KiB** ister | Aynı koşul korunur; arm64 build hostu gereksiz yere 4 KiB ile sınırlanmaz. Hedef Pi 5 `2712` / 16 KiB desteği kaldırılmaz. |
| GPU / kamera / ekran / ses | VC4/V3D KMS, kamera/DSI otomatik algılama, `dtparam=audio=on`, firmware sınırlarında `arm_boost` | Boot dosyaları baştan yazılmaz. Bu varsayılanların export'ta kaybolması hata olur. Yazılımsal renderer veya `nomodeset` bütün kartlara zorlanmaz. |
| İlk boot / depolama | sys-mods `firstboot`, PARTUUID düzeltmesi, `resize2fs_once` | Resmî zincir ve export bölümleri korunur; yalnızca ortak build hesabı yerine kişisel Türkçe hesap kurulur. `gpio/spi/i2c/video/render/cdrom/users/games` dahil mevcut resmî gruplar korunur. |
| Masaüstü | pi-gen'in LXDE/labwc masaüstü aşamaları | Aynı hafif OğuzDows **Xfce** ortamı ayrı son aşamadır. İkinci masaüstü oturumu veya ağır Rıfkı motoru arka planda eklenmez. |
| Tarayıcı | Modern Firefox paketinin ARMv7/NEON kısıtları olabilir | armhf tarifinde zorunlu modern motor yoktur: NetSurf GTK temel tarayıcıdır; Firefox / dil paketi zorunlu listede değildir. arm64 tarifinde Firefox korunur; düşük RAM'li Pi'de varsayılan NetSurf olur. Modern JavaScript desteği eski Zero için varmış gibi gösterilmez. Sandbox / çoklu süreç izolasyonu kapatılmaz. |
| Paket kimliği | Paket araçları gerçek taban / kod adını bekler | Görünür NAME / PRETTY_NAME **OğuzDows**; teknik `ID`, `VERSION_ID`, `VERSION_CODENAME` üretici tabanından korunur. Ürün sürümü `OGUZDOWS_VERSION_ID` ve build metadata'sındadır. |

### Kimlik hatası neden önemlidir?

Ortak PC overlay'indeki `lsb-release` dosyası Pi'ye `ayyildiz / 1.1` tabanını bildiriyordu; `os-release` içindeki teknik taban alanları da ürün sürümüyle değişiyordu. Örneğin incelenen `raspi-config` beta kanal seçimi `lsb_release -c` kullanır. Ürün kod adını taban paket serisi sanmamalıdır.

Pi overlay'i artık PC `lsb-release` dosyasını kopyalamaz. `pi-identity.py`, gerçek upstream dosyadan ID / sürüm / kod adını doğrular; yalnızca ürünün görünür alanlarını değiştirir. `lsb_release -sc` hedef testinde **bookworm** olmalıdır. Essential dosya için diversion `--no-rename` ile yapılır; orijinal içerik korunur. Bu teknik kökeni korumaktır, ürün arayüzüne başka dağıtım markası yerleştirmek değildir.

## 4. Özellik kaybetmeden hafiflik

- **NetworkManager sırası düzeltildi.** Eski gerçek günlükte `disable wait-online` sonrasında `enable NetworkManager` bu servisi `Also=` üzerinden yeniden açıyordu. Şimdi bekleyici en son kapatılır; NetworkManager / Wi-Fi / Bluetooth devre dışı bırakılmaz veya maskelenmez. Export'ta geri açılması derlemeyi durdurur.
- Mevcut **mini / light / full**, LZ4 zram ve SD swap politikası korunur. Yalnızca mini/light efekt varsayılanlarını azaltır; uygulamalar / temalar / ses kayıtları çıkarılmaz. Voltaj, zorunlu governor / overclock ve termal koruma değiştirilmez.
- Yerel mağaza hedef mimaride `-O2` ve sertleştirme bayraklarıyla derlenir; `-march=native`, körlemesine NEON veya Pi 5'e özgü kullanıcı alanı bütün modellere uygulanmaz. Yeni `--version` pencere / işçi / D-Bus açmadan ABI ve GTK sürümü raporlar.
- Galeri / anlatım hash kontrolleri **yalnızca build / export sırasında** çalışır. Oturum açılışına dosya taraması, hash döngüsü veya yeni boşta servis eklenmez. Kayıtlar doğal yerel pakette kalır; çalışma zamanında sentez yoktur.
- Altı bilinen günlük + üç yapı raporu ayrı okunabilir alana alınır; rootfs'in izinleri gevşetilmez veya özyinelemeli taranmaz. Günlükler dosya başına son 2 MiB ile sınırlıdır; JSON raporu kesilerek geçerli veri gibi sunulmaz.

Bunlar gereksiz açılış beklemesi / hatalı uyarlama / CI I/O düzeltmeleridir. Fiziksel açılış süresi, RAM, güç ve uygulama performansında ölçülmüş kazanç henüz yoktur. Eski PC VM RAM sonuçları Pi sonucu sayılmaz.

## 5. Her sürümde tekrar kullanılacak veri

- `raspberrypi/upstream-contract.json`: incelenmiş kaynak commit + arşiv hash'leri, 12 kritik dosyanın hash'i ve bilinçli uyarlamalar. `audit-pi-upstream.py` bunu **uzun paket kurulumundan önce** denetler. Kaynak kilidi değişirse yeni inceleme zorunludur; hash'leri körlemesine güncelleyerek kapı aşılmaz.
- `raspberrypi/feature-contract.json`: **9 ortak yetenek grubu**, minimum CPU / ELF / taban kimliği. `configure-pi.py` ortak listeyi taşır; armhf'de belgelenen Firefox / dil paketi istisnası yerine NetSurf korunur; iki mimarinin tam istenen paket listesi, **20 JPEG + seçilmiş 10 WAV hash'i**, Python çekirdek modülleri ve kaynak commit'ini hedef sözleşmeye koyar.
- `pi-runtime-smoke.py`: hedef ARM'de minimum CPU ile Python / ürün modülleri, gerçek GTK pencere / Türkçe yazı, Xfce sürümü, yerel C mağaza ABI / sürümü, tüm istenen paketlerin gerçek sürüm ve mimarileri, launcher / tema / galeri / doğal kayıt varlığı. **Hash / varlık kontrolü gerçek APT işlemi, ses dinleme veya uygulamaların işlevsel testi değildir.**
- `verify-pi.py`: export öncesi ve salt okunur son imajda bu raporun doğru kaynak / CPU / mimariye ait olduğunu, dosyaların / hash'lerin kaybolmadığını, KMS / kernel / ilk-boot ve hesap güvenliğinin korunduğunu tekrar denetler. Host-only raporu ARM başarısı diye kabul etmez; imajdan host üzerinde kod çalıştırmaz.
- `pi_contract.py`: runtime ve export için ortak, sınırlı veri okuyucusu. Kök dışına taşan bağlantılar, FIFO / özel dosyalar, aşırı büyük / tekrarlı anahtarlı JSON reddedilir; kök içindeki göreli Python paket bağlantısı korunur. Export, yalnızca eski rapordaki sayılara güvenmez: gerçek galeri / önizleme / ses eşlemeleri ve ELF başlıklarını tekrar karşılaştırır. Host verifier yalnızca kendi yanındaki incelenmiş modülü yükler, imajdakini değil.

Tam build'in `OguzDows-Pi-gunluk-*` artefaktına üretilen **`pi-upstream-audit.json`**, **`pi-apt-adaptation.json`**, **`pi-runtime-report.json`**, `collection.json` ve mevcut günlükler alınır; erken hata nedeniyle oluşmayan raporlar açıkça **missing** kaydedilir. Başarılı hedef raporu imajda `/usr/share/oguzdows/pi-build-report.json` olarak da kalır. API erişimi için kısa sonuç kontrol notuna yazılır. Raporda fiziksel boot / GPU hızlandırma / performans / gerçek ses / paket işlemleri **false** olarak ayrı işaretlenir; yapılmayan test başarıya çevrilmez. CI artefaktlarının saklaması **7 gündür**, kalıcı Release arşivi değildir. İleride ARM yayını yapılırken bu raporlar, kaynak sözleşmesi ve imaj hash'i o sürümün kalıcı yayın kanıtıyla birlikte arşivlenmelidir.

Bu değişikliğin yerel kontrolü: **323 test / 6 bağımlılık atlaması, 17,500 sn** (`ResourceWarning` ölümcül); pyflakes / shellcheck / workflow eşliği / diff ve iki gerçek kaynakta **12 dosya/mimari** audit geçti. Bu sandbox'ta GI / Xvfb / GTK geliştirme paketleri yoktur: tam yerel C/GTK mağaza derlemesi ve gerçek grafik kapısı burada çalıştırılmış sayılmaz; yukarıdaki dar C/GLib mikrotesti ayrı tutulur. Tam CI / ARM imaj sonucu ayrıca kaydedilir.

### Sonraki sürüm kontrol sırası

1. Ürün sürümü / ortak özellik değişikliği → iki Pi yapılandırması + yerel/host regresyonu; özellik / varlık sayısını düşürerek test geçirme yok.
2. Taban / pi-gen kilidi değişiyorsa iki resmî kaynağı yeniden karşılaştır; APT mimarisi, kernel/DTB/initramfs, KMS, ilk-boot ve paket aracı kimliğini gözden geçir.
3. Ayrı armhf + arm64 tam build; minimum CPU / ABI / GTK ve export raporlarını kaynak commit'iyle sakla. Eski işler iptal edilmez veya yeniden başlatılmaz.
4. Aynı fiziksel kart / güç / soğutma / SD-SSD üzerinde resmî Pi OS ve OğuzDows'u ayrı ayrı ölç: oturum türü, açık uygulamalar, 120 sn yerleşme, en az 6 örnek; `MemTotal − MemAvailable`, CPU / zram / sıcaklık / throttling, `systemd-analyze`, GPU renderer ve çevre birimleri. Cache drop / zorla servis öldürme ile sayı küçültme yok. İmaj hash'i ve gerçek paket sürümlerini kaydet.
5. Diğer ARM / telefonlar için kullanıcı alanı sözleşmesi yeniden kullanılabilir; Pi kernel / DTB / firmware'i kopyalanamaz. UEFI/U-Boot, ekran/güç/modem ve fiziksel cihaz kapıları ayrıca gereklidir. Deneysel ARM64 katmanları hâlâ boot imajı değildir.

Bu süreç yeni sürüm portunu tekrarlanabilir ve denetlenebilir hale getirir; her sürümün her donanımda kendiliğinden çalışacağına garanti vermez. [Pi kullanım / fiziksel test listesi](../raspberrypi/README.md) · [1.1 test kanıtı](V1.1-TEST-KANITI.md)


## 6. armhf ayna onarımı ve ortak düşük RAM katmanı

`44816162831` armhf hatasında CPU / GTK değil, paket indirme aynası ulaşılamazdı. `prepare-pi-apt.py` hash’i doğrulanmış stage0 APT şablonuna sınırlı bir uyarlama uygular: debootstrap’tan **sonra**, ilk APT update’inden önce retries=3, 30 sn timeout, imzasız kaynakları reddetme ve yalnızca armhf’de `mirror+file:/etc/apt/mirrors/oguzdows-raspbian.list`. Aynı Raspbian arşivi `archive.raspbian.org` öncelik 1, resmî yönlendirici `raspbian.raspberrypi.com` öncelik 2’dir. Sürüm / ARMv6 ABI / anahtar / paket veya boot dosyaları değiştirilmez; arm64 şablonu byte-byte korunur. Bu işlem debootstrap ağı için çözüm değildir. `pi-apt-adaptation.json` kaynak before/after ve ayar hash’lerini üçüncü yapı raporu olarak saklar.

Gerçek yerel APT, ağsız sentetik dosya deposunda ikinci aynaya geçiş / bozuk paketi hash ile reddetme testini geçti. Testteki `trusted=yes` üretimde kullanılmaz ve bu bir imza testi değildir. Güncel Raspbian ağı, yeni armhf imajı ve fiziksel Zero sonucu ayrı gereklidir.

PC/Pi/diğer ARM aynı kaynak kararını kullanır: 512 MiB → mini / en fazla 384 MiB LZ4 sanal kapasite; 1 GiB → light / 512 MiB; özel swap korunur. Efekt tercihi low-RAM, ARMv6 ve nomodeset korumasını aşamaz. Mac/GNOME iki-panel yerleşimleri ve mağaza simgeleri tüm katmanlara taşınır, 9 özellik grubu azaltılmaz; modül listesi 8’den 10’a çıkar. Karşılayıcı 2/7 sayfayla açılır, kalan sayfalar ilk ziyarette kurulur. Bunlar ölçülmüş Pi performansı değildir. PC’nin yeni 512/1024 MiB QEMU tam-Xfce kapısı da Pi Zero CPU / SD / GPU kanıtı yerine kullanılamaz.


## 7. Zero giriş katmanları ve tabana özgü gerçek oturum paketi

Kullanıcı ilk nesil Zero / Zero W'de doğru **armhf** kartla hesap ekranından sonra siyah ekran bildirdi. Yanlış imaj / RAM / HDMI teşhisi konulmadı; günlükler beklenir. LightDM main-config önceliği ile gerçek Xsession girişi ayrı incelenir: Xfce autostart'ı login girişinin yerine sayılmaz. Yeni wrapper düşük kaynak politikasını WM öncesinde bir kez uygular; ardından `exec` eder. Konsol recovery yönergesi yalnızca başarısız LightDM servisini kapsar. Ayrıntı ve salt-okunur komutlar: [Pi Zero oturumu](PI-ZERO-OTURUM.md).

Yeni hedef kapısı, yalnızca root GTK / `--version` yerine özel UID/HOME/Xauthority/D-Bus ile gerçek wrapper → Xfce WM + panel + masaüstü ve armhf'de yerel NetSurf başlangıcını ister. **User-QEMU / host Xvfb raporu LightDM/PAM, 512 MiB fiziksel RAM, GPU veya gerçek kart boot kanıtı değildir.** Eski yeşil Pi raporları bu yeni kapıyı geçmiş sayılmaz.

`46677f5` [PC host 45083549051](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45083549051) gerçek trixie APT simülasyonu, sonraki tabandan varsayılan `plasma-workspace-x11` paketini reddetti. Bookworm/trixie için `plasma-workspace` + `kwin-x11` gerekir; GNOME X11 paket ayrımı da tabana göre ele alınır. [Plasma 6.3.6 upstream startkde](https://github.com/KDE/plasma-workspace/blob/63e4bad2fe4bfc2b8c42f6347f61d2418cc7143c/startkde/CMakeLists.txt) `startplasma-x11` hedefini ve [login-sessions](https://github.com/KDE/plasma-workspace/tree/63e4bad2fe4bfc2b8c42f6347f61d2418cc7143c/login-sessions) X11 girdisini tanımlar; bu upstream kaynak incelemesi kurulu Debian paket sürümünün birebir aynı Git commit'i olduğunun kanıtı değildir. Her iki tabanın gerçek APT planı / güvenilir aday denetimi CI'da zorunludur. Kurulum planı, gerçek APT kurulum→oturum açma veya ARM performans testi diye sunulmaz.
