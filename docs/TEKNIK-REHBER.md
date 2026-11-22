# OğuzDows · Teknik rehber

[← Proje vitrini](../README.md) · [İndir](https://github.com/PeraPlusbirPasha/OguzDows/releases/latest)

**Köklerinden güç alır. Özgürce üretir.**

Türkçe, Xfce tabanlı bir canlı masaüstü ve kurulum ISO’su. Ay-yıldız amblemi, Anadolu kilim geometrisi, al kırmızısı ve turkuaz vurgular; açılış menüsünden masaüstüne kadar aynı OğuzDows kimliğini taşır. Görseller ve pencere teması yerel olarak üretilir; derleme sırasında uzak tema depoları indirilmez.

> Bu depo ISO **derleme tarifini** içerir. Yeni üretilen her imaj ayrıca sınanır; sanal makine kanıtları bütün fiziksel donanımlar için garanti değildir. Gerçek diske kurmadan önce sanal makinede deneyin ve verilerinizi yedekleyin.

## İndir · OğuzDows 1.0 Ay Yıldız

**[v1.0.0 yayını ve Türkçe sürüm notları](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.0.0)** herkese açıktır; Actions oturumu gerekmez.

- **[64 bit PC · amd64 ISO · 1,74 GB](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.0.0/OguzDows-amd64.iso)** — BIOS + 64 bit UEFI; ASUS X553M için bu imajı seçin.
- **[32 bit PC · i386 ISO · 1,41 GB](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.0.0/OguzDows-i386.iso)** — i686/PAE, BIOS; tarayıcı için SSE2 gerekir.

Release dosyaları iki ISO, her birinin `.iso.sha256` dosyası, **[SHA256SUMS](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.0.0/SHA256SUMS)**, iki ham Xfce RAM raporu ve kaynak/dosya manifestini içerir. ISO ile eşleşen checksum dosyasını aynı dizine indirin; örneğin `sha256sum -c OguzDows-amd64.iso.sha256` ile doğrulayın. Secure Boot kapalı olmalıdır. Bu PC yayını Raspberry Pi imajı içermez.

## Neler var?

- **OğuzDows önyükleme menüsü:** normal açılış, güvenli görüntü, düşük bellek ve açılış günlüğü. `amd64` imajı BIOS ve 64 bit UEFI; `i386` imajı klasik BIOS içindir. Normal seçenek 8 saniye sonra başlar.
- **Animasyonlu Plymouth açılışı:** ay-yıldız, OğuzDows yazısı, gerçek önyükleme ilerlemesi ve turkuaz nefes animasyonu. Disk şifresi ve etkileşimli sorular için giriş alanı korunur. Güvenli/düşük bellek açılışında grafik açılış ekranı devre dışıdır.
- **İlk karşılama:** “OğuzDows’u dene”, “OğuzDows’u kur”, “Donanımını tanı”. İlk oturumda açılır; tekrar gösterilmesi seçilebilir. Kurulu sistemde kurulum seçeneği pasiftir. Rehber uygulamalar menüsünden yeniden açılabilir.
- **Türkçe masaüstü:** Q klavye, İstanbul saat dilimi, Türkçe uygulamalar menüsü, kendi pencere/GTK teması, giriş ekranı, duvar kâğıdı ve yerel tarayıcı başlangıç sayfası.
- **OğuzDows kurucusu:** bağımsız Calamares ayarları, Türkçe karşılama, kendi görselleri ve OğuzDows GRUB kimliği. Disk silme seçeneği önceden seçilmez; işlem öncesi onay gerekir.
- **Hafif varsayılan:** Xfce birleştirme efektleri ve GTK animasyonları varsayılan kapalıdır; LZ4 zram korunur. Güncelleyici/mağaza/İmece için açılış daemonu yoktur. **600 MB boşta hedefi**, yerleşmiş tam grafik oturumu ölçümüyle değerlendirilir; her cihazda garanti değildir. Gerçek KDE/GNOME bu hedefin dışındadır.

Kendi ekranlarımızdaki ürün adı OğuzDows’tur. Paket deposu adresleri, derleme araçlarının zorunlu seçenekleri, paket/donanım meta verileri ve üçüncü tarafların lisans, telif ve yasal “hakkında” içerikleri değiştirilmez. Markalama, bunları silmek veya köken bilgilerini yanıltıcı biçimde gizlemek anlamına gelmez.

## Görünüm ve Türkiye duvar kâğıtları

- Pencere başlıkları, kapatma **X** düğmesi, üst panel ve bildirimler opaktır. Odak başka pencereye geçince başlık/düğme solmaz; bildirimlerin solma animasyonu varsayılan kapalıdır. Birleştirme kapalı eski GPU profilinde de okunaklılık hedeflenir.
- Rehber → **Manzaralar** veya menü → **Türkiye Duvar Kâğıtları**: **Boğaz Sabahı, Kaçkar Sisi, Kapadokya Işığı, Ölüdeniz Kıyısı, Tuz Gölü Akşamı, Ani Kışı**. Önceki çizimler kaldırıldı; altı manzaranın tamamı yenilendi. Her birinin sağ altında ay-yıldız + **OğuzDows logosu** var.
- Foto-gerçekçi görseller **yapay zekâ üretimidir; gerçek kamera fotoğrafları veya birebir coğrafi belge değildir**. 1920×1080 JPEG ve ayrı küçük önizlemeler paketlenir. Ağ indirmesi, slayt/arka plan servisi yoktur. Kaynak/çıktı özetleri `artwork/landscapes.json` içindedir.
- Eski çizim seçimleri bir defa yeni karşılıklarına geçirilir; yeni seçim her girişte sıfırlanmaz. Eski `wallpaper.png` yolu yeni Boğaz manzarasını içerir. Kalıcılıksız canlı USB seçimleri yeniden başlatmada silinir.
- **Yerel hareketli tespih imleci:** 24/32/48 px Xcursor; sabit tıklama noktasıyla dönen tane vurgusu. Ayrı Python süreci veya masaüstü katmanı yoktur. Global tıklama tepkisi iddia edilmez; diğer roller Adwaita'dan miras alınır.

## Güncelleyici, mağaza ve kişisel masaüstü

- **OğuzDows Güncelleyici:** liste yenile → paket/sürüm planı → açık onay + yönetici doğrulaması. Plan değişirse yeniden onay; paket kaldırma/dağıtım yükseltmesi yok. Uygun imzalı taban ve mimari denetlenir. Donanımla eşleşen firmware önerisi ve kurulu paket durumu; eski lisanslı sürücü rehberi korunur. Günlük: `/var/log/oguzdows/updater.log`.
- **GNOME Yazılımlar + Flatpak/Flathub:** PC imajında mağaza ve eklentisi bulunur; Flathub ilk açılışta kullanıcı onayıyla hesabına eklenir. Otomatik başlangıç/indirme kapalıdır; Xfce'de son mağaza penceresi kapanınca **İşlemler bitti · Tamamen kapat** kontrolü gösterilir. Tam çıkış açık onay ister; pencere gizlenince indirme/kurulum kendiliğinden iptal edilmez. Flatpak güncellemeleri mağazanın Güncellemeler sayfasından yönetilir. **Snap yoktur.** i386/eskimiş ARM'da Flathub kapsamı varsayılmaz; i386 APT mağazasını kullanabilir.
- **Kontrollü Pardus 25:** varsayılan kapalı; yalnızca amd64/trixie. Sabit üretim anahtarı + güncel gerçek `gpgv` imza kontrolü, taban/mimari/tarih ve APT pinleri gerekir. Yalnızca Image Writer, Night Light, Pen; diğer Pardus paketleri −1. Temel sistem/çekirdek deposu eklenmez; uyumsuz bağımlılıklar zorlanmaz.
- Rehber → **Tarzlar:** **OğuzDows, KDE tarzı, GNOME tarzı, Klasik Xfce, Mac esintisi**. Hepsi hafif Xfce görünümüdür; ilk ayarlar yedeklenir ve geri alınabilir. **Gerçek KDE/GNOME** amd64'te ayrı, onaylı paket planından kurulabilir; daha fazla RAM/disk/grafik kaynağı ister, giriş ekranından seçilir.
- **Dört çevrimdışı araç:** **Çay Molası**, **Türkçe Hızlı Yazım** (I/ı, İ/i), **Heybe** seçilmiş klasör yedeği, **İmece** seçilmiş dosyaların yerel paylaşım ZIP'i. Kendiliğinden çalışmaz/göndermez; kaynak silmez. Arşivlerde şifreleme yoktur; özel içerik kullanıcı tarafından kontrol edilmelidir.

Kullanım, anahtarın açık kökeni, sınırlar ve tam oturum **600 MB ölçüm protokolü**: **[Masaüstü ve bakım rehberi](MASAUSTU-VE-BAKIM.md)**. Ölçüm: `oguzdows-memory-report --idle-confirmed --output "$HOME/oguzdows-bosta-ram.json"` (120 sn yerleşme + 6 örnek). Bileşen RSS'i, tam masaüstü RAM sonucu gibi sunulmaz. Pi'nin ARM kaynak/hesap/boot korumaları ayrı kalır; 1.1’de yerel mağazanın sabit uygulama demetleri Pi’ye eklenir, genel PC bakım / sürücü / Pardus işlemleri taşınmaz.

**Ölçülmüş PC imajı (`bcd0331`):** 2 GiB RAM / 2 vCPU / ağsız QEMU'da tam Xfce oturumunun en yüksek kullanımı **amd64 459,0 MB, i386 518,8 MB**; iki ölçüm de 600 MB koşulunu geçti. Bu, fiziksel PC/Pi veya gerçek KDE/GNOME garantisi değildir. ISO bağlantıları, altı gerçek örneğin kanıtı ve test sınırları: **[Masaüstü test kanıtı](MASAUSTU-TEST-KANITI.md)**.

## Eski cihazlar ve sürücüler

| İmaj | Hedef | Açılış |
| --- | --- | --- |
| `amd64` | 64 bit x86 işlemciler | BIOS + 64 bit UEFI |
| `i386` | i686 / PAE destekli 32 bit işlemciler; tarayıcı için SSE2 gerekir | BIOS |

- Intel, AMD/ATI, Nouveau, VESA/fbdev ve standart Xorg sürücüleri; Intel/AMD mikro kodları; Intel, Realtek, Atheros, Broadcom, **Atmel, ZD1211, Libertas** kablosuz firmware'i ve eski Broadcom Ethernet firmware'i ISO’ya kurulur. Eski giriş aygıtları için evdev de bulunur. Paketler taban sürümüne göre ayrılır; firmware, aygıtın çekirdek sürücüsünün yerine geçmez.
- **Siyah ekran:** açılışta “OğuzDows - güvenli görüntü” seçeneğini deneyin. `nomodeset`, grafik açılışını kapatma ve hafif profil uygular; ACPI/APIC veya bütün Wi-Fi sürücülerini topluca kapatmaz. Bu seçenekle kurulum yapılırsa uyumluluk parametreleri hedefte `/etc/default/grub.d/60-oguzdows-compat.cfg` dosyasında korunur; kurucu canlı ortama ait `boot=live` parametresini taşımaz.
- **Az RAM:** “OğuzDows - düşük bellek” seçeneği efektleri kapatır, sistemi RAM’e kopyalamaz. Canlı sistem/kurucu için en az 1 GiB RAM ve kurulum için 12 GiB boş alan kontrol edilir; günlük kullanım için **en az 2 GiB RAM önerilir**. Tarayıcı ve ofis uygulamaları daha fazla bellek isteyebilir.
- **Donanım merkezi:** PCI/USB kimlikleri, ağ/görüntü kartının gerçekten bağlandığı sürücü, **SÜRÜCÜ BAĞLI DEĞİL** uyarısı, kurulu firmware envanteri, ağ durumu ve kablosuz anahtarları gösterilir. Gri ek sürücü düğmesi, o ek paketle eşleşen kart bulunmadığı anlamına gelir; bütün sürücülerin eksik olduğu anlamına gelmez. Raporu yalnızca siz kaydedersiniz; otomatik yükleme yoktur. Sorun bildirirken laptop modeliyle birlikte bu raporu ekleyin.
- **Çevrimdışı ek sürücüler:** `broadcom-sta-dkms` ve Intel 2100/2200/2915 için `firmware-ipw2x00` paketlerinin **özgün .deb arşivleri ve lisansları**, derleme sırasında imzalı sistem deposundan `/usr/share/oguzdows/offline-drivers/` içine alınır. Paket hash'leri tekrar doğrulanır. Intel lisansı derleme sırasında kabul edilmez; bu iki paket varsayılan olarak kurulmaz veya etkinleştirilmez. Donanım eşleşmesi, özgün lisansı okuma/kabul kutusu ve yönetici onayı gerekir. Hiçbir rastgele internet arşivi veya Windows sürücüsü eklenmez.
- **İnternet olmadan STA:** DKMS, derleyici ve ISO çekirdeğiyle **tam eşleşen başlıklar** imajda hazırdır. Ek kurulum `--no-download --no-remove` ile yapılır; APT arşiv önbelleği açıkça gömülü paket dizinine yönlendirilir. Böylece aynı sürüm paket dizininde de bulunduğunda APT yerel arşivi atlayıp indirme istemez. Çekirdeği sonradan değiştirdiyseniz Broadcom için eşleşen başlıkların internetten indirileceği ayrıca bildirilir. Eksik/bozuk Intel arşivi sessizce internetten indirilmez. Çekirdek, başlık veya lisans hazırlığı başarısızsa ISO derlemesi durur.
- **Canlı oturum ve disk kurulumu:** sürücü kurulduğunda modül yükleme denenir; çalışan bağlantının sürücüsü zorla sökülmez. Raporu yenileyip ağı kontrol edin. Canlıda onaylanan sürücüler, kurucu tarafından hedef sisteme de **çevrimdışı** kurulur; yeniden lisans onayı varsayılmaz, aynı oturumdaki açık seçim taşınır. Seçim yapılmadıysa hedefte ek sürücü kurulmaz. Kurulu sistemde yeniden başlatın; kalıcılıksız canlı USB’yi yeniden başlatmak değişiklikleri siler.
- **Hedefe aktarım:** PCI eşleşmesi canlı ortamda denetlenir; hedef chroot içinde donanımın yeniden görünmesi şart koşulmaz. Hedef çalışanı yalnızca root tarafından yazılmış aynı oturumun lisans/aygıt onayını kabul eder. Hedef çekirdek başlıklarını denetler; canlı bağlantıya `modprobe` / modül sökme işlemi uygulamaz. Uyumsuz / artık bulunmayan kartta ek paket atlanır. Ek paket hatası temel sistemi ve GRUB kurulumunu kesmez; sonuç ekranında **ek sürücü uyarısı** ve hedefte `/var/log/oguzdows/driver-transfer.json`, `drivers-target.log` bırakılır. Bu uyarı Wi-Fi sürücüsünün çalıştığı iddiası değildir.
- Günlük: `/var/log/oguzdows/drivers.log` (yönetici erişimi). STA’yı geri almak için kurulu sistemde `sudo apt-get purge broadcom-sta-dkms` çalıştırıp yeniden başlatabilirsiniz. Donanım modeli bilinmeden her eski karta kapalı sürücü zorlanmaz; b43 ailesinin ayrı edinilen firmware'i veya artık desteklenmeyen NVIDIA/ATI sürümleri için genel uyumluluk sözü verilmez.

**Sınırlar:** her eski aygıt için garanti yoktur. PAE’siz işlemciler, 32 bit UEFI, Secure Boot ve artık güncel çekirdeklerle çalışmayan eski kapalı NVIDIA/ATI sürücüleri bu profilin kapsamında değildir. UEFI kurulumda Secure Boot kapalı olmalıdır. Wi-Fi, askıya alma, ses ve 3B hızlandırma gerçek cihazda ayrıca sınanmalıdır.

## Raspberry Pi Zero–5 · ARM portu

Aynı Türkçe Xfce ortamının Pi için ayrı **SD/USB imajı** akışı vardır; x86 ISO'ları değişmeden korunur:

| İmaj | Hedef |
| --- | --- |
| `armhf` | ARMv6 uyumlu kullanıcı alanı: Zero/Zero W, Pi 1/2/3/4; 512 MB için mini profil |
| `arm64` | Zero 2 W, Pi 2 rev 1.2, Pi 3/4/**5**; Pi 5'e özel `2712` çekirdeği |

```sh
# Sadece yapılandırma; root/ağ/imaj üretimi yok:
./build-pi.sh armhf --configure-only
# Gerekli araçları kurduktan sonra tam SD/USB imajı:
sudo ./build-pi.sh arm64
```

Pi imajında ortak `oguz/oguz` hesabı, parolasız sudo, Calamares veya PC STA sürücüsü **yoktur**. İlk açılış Türkçe hesap ekranıdır; RAM'e göre mini/light/full profili, sınırlı LZ4 zram, SD swap kapatma ve platform/SDIO/DRM donanım raporu eklenir. Kimlik, görünüm, duvar kâğıdı galerisi ve ortak uygulamalar korunur. **ARMv6'da varsayılan Netsurf temel tarayıcıdır (JavaScript yok); 512 MB'da modern web/ofis için Pi 5 performansı vaat edilmez.**

**Fiziksel Pi açılışı/çevre birimleri/performans henüz doğrulanmış değildir.** İmaj matrisi, araçlar, SD'ye yazma, güvenli ilk açılış, kaynak pinleri, kurtarma ve test sınırları: **[Raspberry Pi rehberi](../raspberrypi/README.md)**. Pi derlemeleri ayrı `.github/workflows/raspberrypi.yml` akışındadır; sürmekte olan PC/Pi işleri iptal edilmez.

## ISO derleme

Root erişimi, internet bağlantısı ve yeterli disk alanı olan x86_64 bir `live-build` ortamı kullanın. İki mimarinin çalışma alanları ayrıdır; en az 20 GiB boş alan ayırmanız önerilir.

```sh
sudo apt-get update
sudo apt-get install -y live-build debootstrap squashfs-tools xorriso \
  syslinux syslinux-utils isolinux grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools python3 ca-certificates

sudo ./build.sh amd64
# veya 32 bit imaj:
sudo ./build.sh i386
```

Çıktılar:

```text
OguzDows-amd64.iso
OguzDows-amd64.iso.sha256
OguzDows-i386.iso
OguzDows-i386.iso.sha256
```

Derleme sonunda ISO içindeki BIOS/UEFI seçimleri, çekirdek/initrd yolları, ürün kimliği ve istenmeyen varsayılan menü artıkları denetlenir. Bu kontrol bir açılış testi değildir. `sha256sum -c OguzDows-amd64.iso.sha256` ile imaj bütünlüğünü kontrol edebilirsiniz.

### Yalnızca yapılandırmayı inceleme

`live-build` kuruluysa root veya paket indirmesi olmadan:

```sh
./build.sh amd64 --configure-only
```

`live-build` bile gerektirmeyen, tamamen çevrimdışı hazırlama:

```sh
python3 scripts/configure.py --arch i386 --output /tmp/oguzdows-i386-config
```

Bu komutlar **ISO oluşturmaz**. Gerçek derlemeyi daha sonra temiz bir çalışma alanında başlatın.

### Önceki derlemeyi temizleme

Betik mevcut `build-amd64/` veya `build-i386/` dizinini otomatik silmez. İlgili dizinde önce `sudo lb clean --purge` çalıştırın. Altında bağlı chroot/dosya sistemi kalmadığını doğruladıktan sonra çalışma dizinini kendiniz kaldırın. Bağlı chroot üzerinde `rm -rf` kullanmayın. Başarısız derlemenin ayrıntıları ilgili çalışma dizinindeki `build.log` dosyasındadır.

## PC ISO: güvenlik ve kurulum davranışı

Aşağıdaki canlı hesap yalnızca x86 PC ISO içindir; Raspberry Pi hesap kurulumu yukarıdaki ayrı rehberdedir.

Canlı oturum: **`oguz` / `oguz`**, otomatik giriş ve parolasız yönetici yetkisi **yalnızca canlı ortamda**. `oguz` adı kurucuda canlı kullanıcı için ayrılmıştır.

Kurulum sırasında hedefteki canlı kullanıcı kaldırılır; canlı oturum servisi, otomatik giriş ayarları ve parolasız sudo kuralı temizlenir. Yeni kullanıcı ve parolası kurucuda belirlenir; kurulu sistem her açılışta bir canlı kullanıcı oluşturmaz. `root` hesabı kilitlidir; yönetim yeni kullanıcının `sudo` yetkisiyle yapılır. Kurucu ve ek sürücü işlemleri açık yönetici onayı isteyen, sabit görevli PolicyKit yardımcıları kullanır.

Canlı oturumdaki değişiklikler, kalıcılık ayrıca ayarlanmadıkça yeniden başlatmada kaybolur. Donanım sürücülerini kalıcı kullanmak için kurulu sistemde işlem yapın.

## Rıfkı, nazar boncuğu ve açık kurulum sonucu

- **Hafif Rıfkı:** küçük, foto-gerçekçi Van kedisi resmi ve çevrimdışı Türkçe yardım. Karşılama ekranı artık Rıfkı penceresini kendiliğinden açmaz. **Rıfkı’ya sor** veya uygulamalar menüsünden istenince açılır; kapatılabilir. Boştayken kediye ait animasyon zamanlayıcısı yoktur. Galeri küçük resimleri de yalnızca ilgili sekme açılınca yüklenir.
- **Performans önceliği:** pencere takibi / zıplama, kuyruk deformasyonu, tüy topu, çay, saydam masaüstü katmanı ve kare başına Pillow çizimi kaldırıldı. Eski `pet` / `auto` tercihleri bu yolları yeniden etkinleştirmez. İsteğe bağlı ağız hareketi **varsayılan kapalıdır**; açılırsa yalnızca kayıt çalarken saniyede iki küçük PNG arasında geçiş yapar. Azaltılmış hareket profilinde, pencere gizliyken ve kurulum sırasında çalışmaz. “Selam ver” tek seferlik göz kırpabilir; sürekli göz kırpma döngüsü yoktur.
- **Doğal Türkçe kayıtlar, robotik yedek yok:** eSpeak NG / çalışma zamanı sentezi / ses genliği taraması yoktur. 1.1’de kullanıcının açıkça seçtiği sesle **10 yeni kayıt**, korunan temel yardım / aşama / sonuç kayıtları ve **24 tam metin eşlemesi** vardır. Bunlar yapay zekâ konuşma kayıtlarıdır, gerçek bir ses sanatçısının stüdyo kaydı değildir. Mikrofon, ağ, model indirme veya kişisel ses önbelleği kullanılmaz. Yeni kayıtlar toplam 15,6 MB / 24 kHz mono PCM; oynatıcı ses çalarken çalışır. Ses arızası kurulumu durdurmaz.
- **Panel anlatımı:** canlı / kurulu karşılayıcı için ayrı giriş, yedi sayfanın her birinde doğal kullanım açıklaması; Pi donanımı için ayrı kayıt vardır. Açık/koyu ve tasarım aynı kısa açıklamayı paylaşır. Tek otomatik sayfa tercihi yardımcıyla eşlenir; **Bu paneli anlat**, **Son mesajı dinle**, **Sesi durdur** korunur. Güncelleyici, yerel Mağaza, İmece, Uyumluluk ve Cihaz Merkezi de istek üzerine Dinle / Durdur / ses anahtarı sunar. Kurulumda açık tekrar düğmesi bile sesi başlatmaz; odak / sayfa değişiminde kesilir. Değişken hedef / hata / dosya / donanım raporu birebir okunmaz; ayrıntılar yazılı kalır, yanlış başarı kaydı seçilmez. Köken ve hash: `artwork/rifki-narration.json`.
- **Kurucu kediden bağımsız:** masaüstü / menüdeki kurulum kısayolu doğrudan küçük `install_launcher.py` penceresini açar; Rıfkı, galeri, rig, Pillow veya ses motoru yüklemez. Sabit PolicyKit yardımcısı, aynı kurucu kilidi, günlük ve aynı kanıtlı sonuç protokolü korunur. Açık rehber, başlatıcının D-Bus durum bildirimiyle Rıfkı'nın sesini ve hareketini durdurur; bunun için boştayken disk tarayan zamanlayıcı yoktur. Rehberdeki Kur düğmesi de açık Rıfkı'yı duraklatır. Calamares'in kendi slaytında kedi sabittir.
- Kurulum, disk, açılış, ağ, sürücüler, pil ve duvar kâğıdı konularında yazılı sorular / yardım düğmeleri çalışır. Bu **çevrimdışı, konu sınırlı bir rehberdir**, genel amaçlı sohbet modeli değildir. Mikrofon açmaz, mesaj göndermez, yazılan komutları çalıştırmaz; disk seçmez / biçimlendirmez. Sistem eylemleri sabit düğmelerdir; kurucu ve sürücüler mevcut yönetici onayını kullanır.
- **Nazar boncuğu pil göstergesi:** mevcut Xfce güç eklentisinin ikonlarını değiştirir, güç yönetimini değiştirmez. Boncuk aşağıdan yukarı açılır. Xfce'nin yerel **10 puanlık seviye adımları** kullanılır; kesin yüzde mevcut araç ipucundadır. Tam dolu durumunda tamamı, şarj olurken şimşek, düşük pilde uyarı görünür. Pil yoksa / bilgi alınamıyorsa ayrı eksik-pil / fiş simgeleri kullanılır; belirsiz durum boş pil gibi gösterilmez. Kritik pil eylemleri ve uyku ayarları aynı kalır.
- **Yirmi markalı kültür görseli:** ilk altı manzara korunur; kedi, çay–simit, halk oyunları ve kültür desenleriyle 20’ye tamamlanır. 16 AI görsel + 4 özgün kod çizimi; doğrulanmış kamera fotoğrafı / yer veya kültür belgesi değildir. Her biri 1920×1080 JPEG ve sağ altta OğuzDows işaretlidir; 320×180 küçük önizlemeler toplam yaklaşık 200 kB ve tembel yüklenir. Ağ gerekmez.

### Kurulum sonucu artık kaybolmaz

`quit-at-end: false` sayesinde Calamares'in son sayfası kendiliğinden kapanmaz; yeniden başlatma kutusu varsayılan olarak işaretli değildir. Her deneme için yeni bir rastgele oturum kimliği oluşturulur. Sadece **umount sonrasındaki son iş**, aynı oturuma ait başarı kaydını oluşturabilir. İşlem çıkış kodu `0` veya önceki denemenin kaydı tek başına başarı değildir. Sonuçlar **başarı / başlatılmadı-iptal / tamamlanamadı / doğrulanamadı** olarak ayrı gösterilir. Rehber kendiliğinden ilk seçim ekranına dönmez; kullanıcı sonuç sayfasını kapatır. Yeniden başlatma ancak doğrulanmış sonuçtan sonra, ayrıca onayla istenir.

Durum: `/run/oguzdows-installer/status.json` (yalnızca root yazar, parola içermez). Ayrıntılı günlük: `/var/log/oguzdows/installer.log`. Rıfkı'nın **salt-okunur açılış raporu** diskleri, mevcut oturumun BIOS/UEFI kipini ve sürüm bilgisini gösterir; mevcut diski veya firmware'i onarmaz. Başarılı kurulum kaydı, fiziksel cihazda diskten açılışın ayrıca doğrulandığı anlamına gelmez.

## Testler

```sh
sudo apt-get install -y python3-pil python3-yaml fonts-dejavu-core shellcheck
python3 -m unittest discover -s tests -p 'test_*.py' -v
shellcheck build.sh hooks/* system/usr/lib/oguzdows/*.sh \
  system/usr/local/bin/* system/usr/local/sbin/oguzdows-installer

# Yalnızca görselleri önizleme dizinine üret; sisteme kurmaz:
python3 scripts/render-assets.py --root preview
```

Testler iki mimarinin paket ayrımını, ilk açılış/kurulum temizliğini, dar yetkili sürücü yardımcısını, gerçek ilerleme geri çağrılarını, BIOS/UEFI menülerini, XML/YAML/JSON dosyalarını ve yerel tema üretimini kontrol eder. APT/dpkg-deb varsa gerçek küçük .deb dosyaları ve izole bir paket diziniyle aynı sürümün depoda da bulunması durumu sınanır: yanlış önbellek hatası yeniden üretilir, doğru gömülü önbellek doğrulanır ve eksik bağımlılıkların sessizce indirilmediği gösterilir. Bu testler yalnızca simülasyon yapar; ağa veya sistem paket veritabanına erişmez. `--configure-only` akışı sahte bir `lb` ile sınanır; testler gerçek disklere veya paket yöneticisine yazmaz.

GitHub Actions iki taban sürümünde **gerçek GTK penceresini Xvfb ile açar**; küçük ekran, donanım, 20 logolu kültür görseli, altı Xfce tarzı, hafif Rıfkı ve görünür kurucu sonuç yollarını kontrol eder. Yeni bakım/mağaza/İmece pencereleri, onay iptali, gerçek xfconf profil uygulaması ve yerel libXcursor okuyucusu ayrıca sınanır. Paket kurmayan gerçek APT/Python-APT planları ve isteğe bağlı güncel Pardus imzası raporlanır. Ayrı süreçlerde karşılama / Rıfkı / hafif başlatıcı için açılış süresini, boşta CPU zamanını, en yüksek RSS'i ve olay döngüsü gecikmesini JSON'a yazar; kurulumda D-Bus üzerinden duraklatma / devam etmeyi sınar. Bu ölçümde yetkili kurucu işçisi güvenli bir bekleyiciyle değiştirilir; gerçek kurulum yükü veya fiziksel bilgisayarda akıcılık kanıtı değildir. Ayrıca **gerçek Calamares'i** kendi markalama/ayarlarıyla açıp bütün modüllerin yüklenmesini ve pencerenin görünmesini doğrular; hiçbir kurulum düğmesine basmaz veya disk kurmaz. Ekran görüntüleri, JSON ölçümleri ve kurucu açılış günlüğü artefakt olarak saklanır. PR’larda testler, `main` güncellemesinde veya elle `target=pc` çalıştırmada testlerden sonra iki ISO derlemesi çalışır. `target=pc-tests` yalnızca PC doğrulamalarını çalıştırır; ISO üretmez. `target=pc-diagnostics` ve `evidence_run=<çalışma numarası>` ise yalnızca tamamlanmış çalışmanın küçük hedef-OS raporlarını kontrol notlarına taşır; yeniden derlemez veya eski işi yeniden başlatmaz. Yeni bir çalıştırma **sürmekte olan ISO işini iptal etmez**. `.github/workflows/main.yml` etkin iş akışıdır; kökteki `build.yml` eş kopyasıdır.

Kurucu, standart `/etc/calamares/settings.conf` yapılandırmasını kullanır; bu dosya `--config` seçeneğine verilmez. Başlatıcı yalnızca canlı ortamda çalışır, tek kurucu kilidi alır ve gerçek squashfs kaynağını saptar. Kurucu açılamazsa masaüstünde hata gösterilir; yönetici günlüğü: `/var/log/oguzdows/installer.log`. Kurucunun açılması, gerçek diske başarılı kurulum yapıldığının kanıtı değildir.

### PC kurulumu sonrası “No bootable device” kontrolü

Diskte sistem dosyalarının bulunması, firmware'in diski açabildiğini tek başına göstermez. Kurucu önyükleyiciden önce hedefi, sonra diskteki sonucu ayrıca denetler:

- **BIOS + MBR:** GRUB bir bölüme değil seçilen diskin tamamına kurulmalıdır. Calamares otomatik bölümlemede aktif bayrağını zaten ister; bu ek kontrol özellikle elle bölümleme veya eksik sonuç içindir, fiziksel cihazdaki hatanın sebebini tek başına kanıtlamaz. Hiçbir aktif bölüm yoksa, doğrulanmış `/boot` (yoksa `/`) bölümünün MBR aktif bayrağı tamamlanır. Bazı eski BIOS'lar bu bayrak olmadan diski atlar. Yalnızca **bir bayt** değiştirilir; disk kimliği, bölüm başlangıç/boyutları ve dosya sistemleri korunur. Önceki 512 baytın özel izinli yedeği hedefte `/var/log/oguzdows/mbr-before-active-*.bin` altında saklanır. Var olan aktif bölüm tercihi ve koruyucu/hibrit GPT MBR'ı değiştirilmez; diskte tahminî bir bölüm seçilmez.
- **UEFI:** görünür OğuzDows adı korunur; firmware dizini/kimliği eski aygıtlarla uyum için ASCII `OguzDows` kullanır. FAT EFI bölümünün gerçekten bağlı olduğu, üretici yükleyicisi ve mevcut fallback mekanizmasının `EFI/BOOT/BOOTX64.EFI` dosyası doğrulanır. Boş/eksik dosya veya bağlanmamış ESP ile başarı bildirilmez. Secure Boot/32 bit UEFI desteği eklenmez.
- Önyükleyici hedefi seçilmemişse veya diskte gerçek GRUB menüsü yoksa kurulum sessizce başarılı sayılmaz. Diskler yeniden bölümlenmez; tema, masaüstü, sürücü, uygulama ve performans tercihleri bu düzeltmeyle değiştirilmez.

**Daha önce kurulmuş PC:** yeni kaynak/ISO, mevcut diski uzaktan veya otomatik onarmaz. Sorunun yalnızca aktif bayrak mı, eksik GRUB mu, UEFI kaydı mı olduğunu görmeden `/dev/sda` gibi tahminî bir aygıta yazmayın ve yeniden biçimlendirmeyin. Canlı USB terminalinde aşağıdaki salt-okunur çıktıları ve cihaz modelini paylaşarak mevcut kurulumu koruyan onarımı belirleyebilirsiniz:

```sh
if [ -d /sys/firmware/efi ]; then echo UEFI; else echo BIOS; fi
lsblk -o NAME,SIZE,TYPE,FSTYPE,PTTYPE,MOUNTPOINTS
sudo fdisk -l
```

İlk CI testi yalnızca kendisinin oluşturduğu geçici loop disklerde gerçek GRUB kurar; QEMU/SeaBIOS ve temiz NVRAM'li OVMF ile **firmware → GRUB** açılışını sınar. Bu test tek başına işletim sistemi açılışını kanıtlamaz.

ISO derlemesinden sonraki ayrı `smoke-iso-target.py` kontrolü ise **üretilen ISO'nun squashfs'inden** kendi özel disk dosyasına hedef sistem hazırlar; üretimdeki zorunlu canlı-paket temizliğini, gerçek initramfs ve GRUB üretimini çalıştırır. ISO takılı olmadan QEMU'da hedef çekirdek / initramfs / systemd açılışını sınar. amd64 BIOS+UEFI, i386 BIOS gerektirir. `--graphical-idle` ile özel test diskindeki geçici hesapta tam Xfce oturumu da açılır ve gerçek yerleşmiş RAM `desktop-idle.json` olarak raporlanır; 600 MB aşımı veya sakin olmayan ölçüm açık uyarıdır, başarı diye etiketlenmez. Bu test hesabı/otomatik giriş yayımlanan ISO’ya eklenmez. Bu kontrol geçmeden ISO artefaktı yayımlanmaz. Test **Calamares GUI bölümleme/kullanıcı akışını çalıştırmaz**, LUKS veya fiziksel bilgisayar doğrulaması değildir.

**Kali / Linux Mint kaynak karşılaştırması ve sınırlar:** [ayrıntılı inceleme](KURULUM-KARSILASTIRMA.md). Kritik canlı paketler artık `try_remove` ile geçiştirilmez; temiz hedef durumu, `update-initramfs` yönlendirmesi, gerçekten yenilenen ve çekirdekle eşleşen initramfs ile mevcut dosyalara işaret eden GRUB menüsü zorunlu doğrulanır. İsteğe bağlı sürücü uyarıları ayrı kalır. PC ISO kaynak commit kimliği `build-info.json` ve kurucu günlüğüne yazılır.

### Yayın öncesi elle kontrol

- [ ] `amd64`: BIOS ve OVMF/UEFI ile menü → animasyon → Türkçe masaüstü.
- [ ] `i386`: PAE/SSE2 destekli CPU ile BIOS açılışı.
- [ ] Güvenli görüntü ve düşük bellek seçenekleri; ağ, ses ve uyku/uyanma.
- [ ] Karşılama ekranındaki üç işlem; kapatınca tekrar açılmama ve “yeniden göster” tercihi.
- [ ] Boş **sanal diske** çevrimdışı kurulum; yeniden başlatınca OğuzDows GRUB adı.
- [ ] Kurulu sistemde canlı `oguz` kullanıcısı, parolasız sudo ve zorunlu otomatik giriş kalmaması.
- [ ] Şifreli kurulum seçilirse soğuk açılışta parola istemi ve kilit açma.
- [ ] Hedef eski fiziksel cihazlarda görüntü/Wi-Fi/USB/firmware doğrulaması.

Klasik BIOS menüsünde ROM yazı tipi sınırlaması nedeniyle seçim metinleri Türkçenin ASCII karşılıklarıdır; resimdeki OğuzDows başlığı, UEFI, karşılama ve masaüstü Türkçe karakterlidir.

## Kaynak düzeni

- `build.sh`: x86 mimari seçimi ve ISO derleme akışı.
- `build-pi.sh`, `raspberrypi/`: ayrı Pi imajı, kilitli pi-gen, ilk hesap ve donanım politikası.
- `scripts/configure-pi.py`, `scripts/verify-pi.py`: çevrimdışı Pi aşaması ve güvenlik/boot kontrolü.
- `packages/`: ortak masaüstü, PC'ye özgü, taban sürümüne ve mimariye özel paketler.
- `system/`: canlı/kurulu sisteme eklenen dosyalar, karşılama ve sürücü merkezi.
- `installer/`: OğuzDows Calamares ayarları ve markalama.
- `boot/`: Plymouth teması ve animasyonu.
- `assets/`, `scripts/render-assets.py`: vektör kimliği ve çevrimdışı görsel üretimi.
- `scripts/configure-boot.py`, `scripts/verify-iso.py`: ISO menüsü oluşturma ve doğrulama.
- `hooks/`: markalama, görseller, servisler ve son ISO menüsü kancaları.
- `tests/`: izole birim/kontrat testleri ve gerçek GTK smoke testi.
