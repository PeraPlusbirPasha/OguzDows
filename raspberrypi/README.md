# OğuzDows · Raspberry Pi portu

Aynı Ay Yıldız kimliği, Türkçe Xfce/X11 masaüstü, net pencere/panel düğmeleri, Plymouth animasyonu, Pi'ye özel karşılayıcı, doğal yerel Rıfkı rehberi, cihaz merkezi, yerel C/GTK mağaza ve **20 kültür duvar kâğıdı**; Pi'ye özgü çekirdek, boot firmware'i ve güvenli ilk açılış ile. Galeri 16 AI görsel ve 4 özgün çizimden oluşur; yirmi gerçek fotoğraf iddiası değildir.

**[v1.1 yayını](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.1)** iki mimarinin kalıcı indirmesini içerir: **[armhf](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/OguzDows-rpi-armhf.img.xz)** · [armhf SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/OguzDows-rpi-armhf.img.xz.sha256) · **[arm64](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/OguzDows-rpi-arm64.img.xz)** · [arm64 SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/OguzDows-rpi-arm64.img.xz.sha256). Ürün kaynağı `29f7738534cd00bd87887f530355ef45e01eb28c`; `--configure-only` çıktısı imaj değildir. **[PC/Pi model, CPU, RAM ve depolama indirme rehberi](../docs/releases/v1.1.md).**

> **Deneysel port:** fiziksel kartlar bu yeni imajla doğrulanmadı. İlk nesil Zero/Zero W’de doğru armhf ile hesap ekranı sonrası siyah ekran bildirimi hâlâ açıktır; giderildiği iddia edilmez. ARM kullanıcı-QEMU/Xvfb başarısı LightDM/PAM veya fiziksel boot kanıtı değildir. [Teşhis](../docs/PI-ZERO-OTURUM.md).

**Bu bir PC ISO'su değildir.** Doğrudan SD/USB'ye yazılan, değişiklikleri kalıcı tutan iki `.img.xz` tarifi vardır. ARMv6 ile ARM64 aynı dosya gibi ele alınmaz. Yapılandırmanın/testlerin geçmesi, bütün kartların açıldığı veya ölçülmüş yüksek performans elde edildiği anlamına gelmez. Fiziksel kart testleri aşağıdaki tabloda henüz yapılmamıştır.

## İmaj seçimi

| Kart / işlemci | İmaj | Otomatik profil | Bu imajla fiziksel test |
| --- | --- | --- | --- |
| Zero / Zero W / Zero WH · ARM1176, ARMv6, 512 MB | **armhf** | mini | Yapılmadı; hesap sonrası siyahlık bildirimi açık |
| Pi 1 A/A+/B/B+ · ARMv6, 256–512 MB | **armhf** | mini | Yapılmadı; 256 MB günlük masaüstü önerilmez |
| Pi 2 B rev 1.0/1.1 · Cortex-A7, ARMv7 | **armhf** | light | Yapılmadı |
| Pi 2 B rev 1.2 · Cortex-A53 | armhf veya arm64 | light | Yapılmadı |
| Zero 2 W · Cortex-A53, 512 MB | RAM tasarrufu için **armhf**; arm64 alternatifi | mini | Yapılmadı |
| Pi 3 A+ · 512 MB / 3 B / 3 B+ · 1 GB | armhf veya arm64 | mini / light | Yapılmadı |
| Pi 4 / 400 · Cortex-A72 | **arm64**; az RAM'de armhf alternatifi | ≤2 GiB light, daha fazlası full | Yapılmadı |
| Pi 5 · Cortex-A76 | **arm64** | RAM'e göre light / full | Yapılmadı |

- **armhf**: Raspbian tabanlı, ARMv6 uyumlu kullanıcı alanı; resmî `v6`, `v7`, `v7l`, `v8` Pi çekirdekleri. Sıradan ARMv7 tabanlı bir armhf kök sistemi eski Zero'ya kopyalanmaz. **Pi 5 bu imajın hedefi değildir.** 32 bit uygulamaların adres alanı sınırı vardır.
- **arm64**: ARMv8 kullanıcı alanı; resmî `v8` ve Pi 5'e özgü **`2712`** çekirdekleri. Pi 5'in özel çekirdeği/16 KiB sayfa optimizasyonu korunur; bütün kartlara tek `kernel8.img` zorlanmaz. Eski Zero / Pi 1 / erken Pi 2'de açılmaz.
- Compute Module türevleri ve Pi 500 gibi aynı SoC ailesindeki ek modellerin firmware desteği üreticiden gelir; taşıyıcı kart, eMMC/rpiboot, ekran ve çevre birimleri ayrıca doğrulanmalıdır. Bu tabloda doğrulanmış yeni kartlar gibi sunulmazlar.

### “Aynı özellikler” ve donanım sınırları

Ortak masaüstü/uygulama listesi iki PC imajıyla paylaşılır: LibreOffice Writer/Calc/Impress, VLC, dosya yöneticisi, ağ/Bluetooth/ses, temalar ve galeri korunur. Web başlatıcısı armhf'de NetSurf GTK, arm64'te kaynak bütçesine göre NetSurf / kurulu Türkçe Firefox ESR kullanır; armhf için Firefox zorunlu değildir. Pi'ye GPIO/I2C/SPI kitaplıkları ve kamera komut satırı araçları da eklenir. Kamera/HAT arabirimleri kullanıcı istemeden zorla etkinleştirilmez.

Yerel mağaza Pi rootfs'i içinde kendi mimarisine derlenir; PC ikili dosyası kopyalanmaz. Sabit uygulama demetleri yalnızca cihazın mevcut imzalı kaynaklarından planlanır. Genel Pi sistem / çekirdek güncellemeleri kendi paket yöneticisinde kalır; PC güncelleyicisi veya başka dağıtımın temel depoları taşınmaz. İsteğe bağlı kullanıcı Flatpak / Flathub altyapısı yalnızca arm64 tarifindedir; eski Zero / armhf için bu kaynak veya APK çalıştırma vaadi yoktur. Gerçek APT / Flatpak işlemi ve fiziksel kart doğrulaması henüz tamamlanmadı.

**512 MB + tek ARMv6 çekirdeğinde güncel web/ofis, Pi 5 hızında çalışamaz.** Modern Firefox'un ARMv7/NEON gereksinimlerini ARMv6'ya dayatmamak için varsayılan tarayıcı başlatıcısı eski Zero/Pi 1'de **Netsurf GTK** seçer. Bu tarayıcı temel web içindir; **JavaScript ve modern sitelerle tam uyumluluk yoktur**. **armhf imajında Firefox ve Türkçe dil paketi artık zorunlu değildir / yüklenmez; NetSurf kullanılır.** arm64’te 1 GiB ve altı Pi’de NetSurf, daha yüksek RAM’de kurulu Firefox seçilir. Menü / web bağlantıları ortak `oguzdows-browser` MIME başlatıcısından geçer. NetSurf için JavaScript kullanan siteler yerine sade haber, HTML / mobil veya yazdırma sayfaları tercih edin. ARMv6’da Firefox isteği açıkça reddedilir. Ofis ve video uygulamalarının özellikle 512 MB'da büyük dosya/çoklu sekme/yüksek çözünürlük performansı garanti edilmez. Modern web/ofis için **Pi 4/5 ve en az 2 GB, tercihen 4 GB RAM** önerilir.

PC'ye özgü Calamares, BIOS/UEFI/GRUB menüsü, Intel/AMD mikro kodları ve Broadcom STA/Intel 2100 PCI ek paket kurucuları Pi'ye taşınmaz. Pi Wi-Fi'ı **brcmfmac/SDIO + doğru kart firmware'i** kullanır; STA kurulmaz, açık sürücüler kara listeye alınmaz. Pi'de kurulumun karşılığı imajı yazma ve ilk açılışta hesap oluşturmadır. Rehberde sahte/çalışmayan PC kurucu düğmesi yerine masaüstü ayarları bulunur.

## SD / USB'ye yazma ve ilk açılış

1. Yukarıdaki v1.1 yayınından kartınıza uygun `OguzDows-rpi-armhf.img.xz` veya `OguzDows-rpi-arm64.img.xz` ile SHA-256 dosyasını indirin. Release dosyası `.img.xz` biçimindedir; ayrıca Actions ZIP’i indirmeniz gerekmez.
2. Aynı dizinde `sha256sum -c OguzDows-rpi-armhf.img.xz.sha256` (veya arm64) çalıştırın.
3. Raspberry Pi Imager'da **özel imaj kullan** ile `.img.xz` dosyasını seçin. Hedefin tüm verileri silinir; doğru SD/USB'yi seçtiğinizi iki kez kontrol edin. En az **16 GB**, tercihen kaliteli **32 GB A1/A2** kart kullanın. Pi 4/5'te desteklenen USB 3 SSD, SD'ye göre daha iyi uygulama deneyimi sağlayabilir.
4. **Imager'ın kullanıcı/SSH/ileri özelleştirme seçeneklerini uygulamayın.** Bu port kendi hesap adımını kullanır. Mevcut imaj dosyası için Imager'ın kimlik özelleştirme uyumluluğu test edilmemiştir.
5. Monitör/klavye bağlayıp üreticinin uygun güç kaynağıyla açın. Eski Zero'da mini-HDMI ve USB OTG/hub gerekebilir. Ağ için internet zorunlu değildir. Kartta yerleşik Wi-Fi/Ethernet yoksa uygun adaptör gerekir.
6. Resmî ilk açılış/bölüm büyütme mekanizması korunur; ilk açılış daha uzun sürebilir ve yeniden başlatabilir. Gücü kesmeyin. Ardından **Türkçe yerel hesap ekranında** kullanıcı adı ve en az 10 karakterli parola belirleyin. Parola yazılırken görünmez.
7. OğuzDows giriş ekranında hesabınızla giriş yapın. Otomatik giriş yoktur; `sudo` kendi parolanızı ister. SD/USB'deki ayarlar ve dosyalar kalıcıdır. Başka diske Calamares kurulumu gerekmez.

**Pi için `oguz/oguz` hesabı yoktur.** `root` kilitlidir, SSH varsayılan olarak kapalıdır ve parolasız yönetici kuralı yoktur. İlk hesap tamamlanmadan hem LightDM hem SSH başlatılması engellenir. Parola/özet komut satırına, günlüğe veya kalıcı durum dosyasına yazılmaz. Kesintide yarım kalan hesap aynı adla güvenle tamamlanabilir. İlk kurulum tekrar soruluyorsa başka bir hesabı devralmak yerine yerel hata gösterilir.

### Ekransız hesap hazırlama (isteğe bağlı)

Güvendiğiniz bir bilgisayarda `openssl passwd -6` ile **etkileşimli** olarak güçlü parolanızın SHA-512 özetini üretin (parolayı komut argümanına yazmayın). FAT boot bölümünün köküne **`oguzdows-userconf.txt`** adlı tek satırlık dosyayı yerleştirin:

```text
kullaniciadi:$6$...ürettiğiniz_tam_özet...
```

Bu örnek yer tutucudur; olduğu gibi çalışmaz. Yalnızca geçerli SHA-512 / yescrypt özetleri kabul edilir; açık metin parola, çoklu hesap, symlink veya kod çalıştırılmaz. Dosya hesap açıldıktan sonra kaldırılır. **FAT/flash üzerinde fiziksel güvenli silme garantisi yoktur**; özeti de hassas kabul edin ve ilk kullanımda parolanızı değiştirin.

Bu dosya **ağı veya SSH'yi kendiliğinden açmaz**. Ağ için kablolu/USB Ethernet veya önceden güvenle hazırlanmış NetworkManager profili gerekir. Kurulumdan sonra yerelde `sudo systemctl enable --now ssh` ile açıkça etkinleştirebilirsiniz. Tamamen ekransız ilk kurulum gerekiyorsa resmî `ssh` boot işaret dosyası mekanizması ayrıca kullanılabilir; bunun ilk açılış sıralaması ve Wi-Fi profili gerçek kartta ayrıca test edilmelidir. SSH için de hesap tamamlanma engeli geçerlidir; root girişi kapalı kalır. İnternete parola ile SSH açmak yerine anahtar ve güvenlik duvarı kullanın.

## Otomatik performans profilleri

`/etc/oguzdows/pi.conf` yalnızca veri olarak okunur; shell olarak çalıştırılmaz:

```ini
profile=auto
```

| Profil | Seçim | Efektler | LZ4 zram |
| --- | --- | --- | --- |
| mini | ARMv6 veya kullanılabilir RAM ≤768 MiB | Compositor ve GTK animasyonları kapalı | RAM'in %75'i, en fazla 384 MiB |
| light | RAM ≤2 GiB | Compositor ve GTK animasyonları kapalı | RAM'in %50'si, en fazla 1 GiB |
| full | Daha fazla RAM | Ortak masaüstü varsayılanları; kullanıcının tercihi korunur | RAM'in %50'si, en fazla 1 GiB |

`MemTotal` GPU/kernel için ayrılan belleği dışladığından etiketteki RAM'den az görünebilir. Zram boyutu sanal sıkıştırılmamış kapasitedir, bedava gerçek RAM değildir; doldukça RAM/CPU kullanır. Disk swap servisi maskelidir; aşırı yükte yine bellek yetersizliği olabilir. Loglar SD'yi yormamak için en fazla 32 MiB uçucu journal'dadır. `journalctl` kayıtları yeniden açılışta kaybolur; sorun raporunu önceden kaydedin. Firefox disk önbelleği varsayılanı kapalı ve oturum kayıt aralığı 60 saniyedir; sandbox kapatılmaz.

`mini`, `light` veya `full` seçip yeniden başlatarak bütçeyi değiştirebilirsiniz. PC / diğer ARM ile ortak karar `/etc/oguzdows/resources.conf`, Pi’ye özel üst seçim `pi.conf`, son öncelik tam `oguzdows.profile=` kernel argümanıdır. Dosyalar shell olarak çalıştırılmaz. Bilinen yönetilen `/etc/default/zramswap` otomatik üretilir; elle özelleştirilmiş zram dosyası ve mevcut disk swap ayarları ortak işçi tarafından ezilmez (Pi imajının SD swap varsayılanı ayrı olarak kapalı kalır). **full seçimi dahi 2 GiB ve altında, ARMv6 veya `nomodeset` ile kompozitörü açmaz.** Efekt tercihi Karşılayıcı → Görünüm’dedir; varsayılan kapalı, yalnızca iskele / alt çubuk arka planında hafif alfa vardır. Başlıklar ve düğmeler daima opaktır. Bu bütçeler 512 MiB fiziksel Pi performansı kanıtı değildir.

**CPU frekansı/voltajı, termal kısıtlama ve fan korumaları değiştirilmez; zorunlu performance governor/overclock yoktur.** Resmî `arm_boost`, DRM/KMS ve model bazlı çekirdek seçimi korunur. Pi 5'te soğutucu/fan, yeterli güç ve hızlı depolama yazılım ayarlarından daha belirleyici olabilir. Ölçülmüş FPS/açılış süresi iddiası yoktur.

### Görüntü / açılış kurtarma

Pi firmware'i PC GRUB menüsü sunmaz. Boot bölümündeki `cmdline.txt` **tek satır** kalmalıdır; mevcut `root=PARTUUID=...`, `rootwait` ve ilk açılış `init=...` değerlerini silmeyin.

- Az efekt için satırın sonuna `oguzdows.profile=light` ekleyin (veya `mini`).
- Günlükleri görmek için `quiet splash` sözcüklerini kaldırıp `plymouth.enable=0 systemd.show_status=1` ekleyin.
- Ek ekran/firmware ayarları `/boot/firmware/oguzdows-config.txt` dosyasına yazılabilir. Varsayılan KMS bütün kartlara körlemesine `nomodeset` ile kapatılmaz; ekran/HDMI sorunu kart ve bağlantıya göre teşhis edilmelidir.
- Üretici EEPROM/USB boot yeteneği özellikle Pi 4/5 USB/SSD açılışını etkiler. Bu tarif EEPROM'a kontrolsüz `rpi-update` veya overclock uygulamaz.

## Kaynaktan derleme

İzole, root/mount/loop erişimi olan Linux makinesi/VM kullanın; **yalnızca armhf derleme hostu için 4 KiB sayfa koşulu vardır**. arm64 gereksiz yere bu koşulla kısıtlanmaz; hedef Pi 5 `2712` / 16 KiB çekirdeği korunur. x86_64 üzerinde QEMU kullanıcı emülasyonu mümkündür; bu Pi donanım emülasyonu değildir. 30 GiB boş disk önerilir (betik en az 20 GiB kontrol eder). Her mimari ayrı çalışma dizini kullanır. Pi 5'in 16 KiB host kernel'inde armhf için önce 4 KiB host gerekir.

```sh
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  quilt parted coreutils qemu-user-static debootstrap zerofree zip dosfstools \
  e2fsprogs libcap2-bin rsync grep udev xz-utils curl xxd file kmod bc gpg pigz \
  arch-test binfmt-support ca-certificates fdisk git python3 xvfb xauth
# Yalnızca bu izole derleme makinesinde; hedef Pi / günlük bilgisayar için değil:
sudo scripts/prepare-pi-binfmt.sh armhf
sudo scripts/prepare-pi-binfmt.sh arm64

sudo ./build-pi.sh armhf
sudo ./build-pi.sh arm64
```

`prepare-pi-binfmt.sh` yalnızca kurulu QEMU paketinin sistem tanımını kullanır. Yeni hostlarda `systemd` / `binfmt.d`, eski paketlerde `binfmt-support` kaydı seçilir; `update-binfmts` veri tabanında görünmeme tek başına QEMU yok demek değildir. Host yürütmesine ek olarak yeni, boş ve özel bir chroot içinde `arch-test` çalıştırılır; böylece yalnızca hostta çalışan ama debootstrap içinde kaybolan bir yorumlayıcı hazır sayılmaz. Bu betik hedef imaja eklenmez; **hedef Pi'de veya başka build işleriyle paylaşılan makinede çalıştırmayın**. Bu kapının geçmesi fiziksel ARM / Pi boot kanıtı değildir.

Tam derleme Raspberry Pi OS/Raspbian paket sunucularına erişim ister. Ağ kısıtlı geliştirme ortamında sadece yapılandırma ve testler çalışabilir; GitHub Actions bu yüzden ayrı tam imaj işleri sunar.

```sh
# Root, ağ veya pi-gen indirmesi yok:
./build-pi.sh armhf --configure-only
# veya istediğiniz yeni bir dizine:
python3 scripts/configure-pi.py --arch arm64 --output /tmp/oguzdows-pi-config
```

`--configure-only` **imaj üretmez**. Daha sonra tam derleme için temiz/yeni çalışma alanı kullanın. Betik mevcut `build-rpi-armhf/` / `build-rpi-arm64/` dizinlerini otomatik silmez; bağlı dosya sistemi kalmadığını `findmnt`/`losetup` ile doğrulamadan çalışma alanını silmeyin. Kök depoyu veya `.git` dizinini taşımayın/silmeyin.

Çıktılar:

```text
OguzDows-rpi-armhf.img.xz
OguzDows-rpi-armhf.img.xz.sha256
OguzDows-rpi-armhf.packages.txt
OguzDows-rpi-arm64.img.xz
OguzDows-rpi-arm64.img.xz.sha256
OguzDows-rpi-arm64.packages.txt
```

Resmî `RPi-Distro/pi-gen` kaynakları `pi-gen.lock.json` içinde **tam commit + arşiv SHA-256** ile sabittir; hash doğrulanmadan açılmaz. `bookworm` / `bookworm-arm64` dalları X11/Xfce uyumu ve ARMv6 ayrımı için seçilmiştir. Depoların imzalı güncel paketleri kullanılır; bit düzeyinde aynı çıktı garantisi verilmez. Taban sürümünün güvenlik desteği ve firmware pinleri düzenli güncellenmelidir. Yasal/provenance dosyaları ve özgün paket lisansları korunur.

Önemli ayrıntı: pi-gen'de **`USE_QEMU=1` çapraz derleme anahtarı değildir**; QEMU hedef imajı davranışını değiştirir ve normal Pi yeniden boyutlandırmasını kapatır. Bu port gerçek Pi imajı için **`USE_QEMU=0`** kullanır; çapraz çalıştırmayı host QEMU/binfmt sağlar. Resmî ilk kullanıcı yeniden adlandırma aşaması atlanır; onun yerine OğuzDows'un kendi kilitli hesap akışı kullanılır.

## Doğrulama ve testlerin anlamı

`29f7738` [Pi ortak host CI](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45169809200) ve [armhf+arm64 imaj çalışması 45170576727](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45170576727) **başarılı tamamlandı**. İmajlar birer kez başlatıldı; iptal/yeniden başlatma yoktur. ARM1176/Cortex-A53 hedef ELF/GTK, root olmayan tam Xfce/beş kararlı örnek, native C Haber/çıkan üretim işçisi/ağsız TEST önbelleği ve armhf NetSurf yerel sayfası geçti. 115/121 ortak paket, 11 özellik grubu, 31 görsel/ses hash’i, 20 duvar kâğıdı, 11 kayıt/25 eşleme doğrulandı. **LightDM/PAM, fiziksel Pi kernel/GPU/SD, ses çıkışı, canlı haber veya Pi RAM/hız ölçümü değildir.**

Yayın aktarımı [45201307283](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45201307283), mevcut sıkıştırılmış dosya SHA-256’sını yeniden hesaplar; ham imajı salt okunur açıp iç kaynak/sürüm/lock/rapor eşleşmesini ve mevcut Pi boot/hesap/özellik denetimini tekrar kontrol eder. İmaj yeniden derlenmez. [Yükleme sonrası 45203390800](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45203390800) 17 release dosyasını yeniden indirip hash’lerini ve 21 JSON kanıtını ayrıca doğruladı; release’e yazmadı. [Yayın manifesti](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/release-manifest.json) · [Özgün runtime/upstream/APT/collection JSON’ları](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/test-evidence.tar.gz) · [Host kanıtı](../docs/releases/v1.1-elementary-host.json).

Ortak kaynak native C/GTK Haber okuyucusu, 15 ayrı simge ve doğal boyutlu iskele/bütçeli geçişleri içerir. ARMv6’da kompozitör açılmaz; aynı uygulamalar ve statik düzen korunur. [Uygulama / sınırlar](../docs/ELEMENTARY-HABER.md).

### Önceki imajların tarihsel kaydı

`79c6942` / [45084959200](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45084959200) önceki iki imajı, non-root tam Xfce ve armhf NetSurf yerel sayfasıyla başarıyla tamamladı. Bu kullanıcı-QEMU / host Xvfb kanıtıdır; fiziksel Zero siyahlığının çözüldüğü anlamına gelmez. Yeni Haber / simge / Picom kodu bu imajlarda yoktur.

- Birim/kontrat testleri: iki mimari, PC paket ayrımı, ARMv6/Zero 2 ayrımı, zram sınırları, komut enjeksiyonu reddi, ilk açılışta kesinti/yeniden deneme ve hesap güvenliği.
- Xvfb üzerindeki gerçek GTK penceresi Pi sayfa dalını **host üzerinde** açar; sahte kurucu/PC STA düğmesi olmadığını ve galeriyi denetler. Bu ARM veya kart ekran testi değildir.
- Tam derlemede kullanıcı alanı **QEMU ARM1176 (ARMv6)** veya **Cortex-A53 (ARMv8)** altında `/bin/true`, Python / ürün modülleri, gerçek GTK pencere / Türkçe metin, Xfce ve yerel C mağaza sürümü / ELF ABI ile denetlenir. Xvfb yalnızca hosttadır; hedefe özel XDG / D-Bus oturumu verilir. Bu sürüm özel non-root tam Xfce (WM + panel + masaüstü + kararlı örnekler), native Haber ve armhf'de yerel NetSurf başlangıcı kapılarını da geçti. Eski başarılı imajın sürüm testi bu yeni kapı yerine kullanılamaz. LightDM/PAM, gerçek firmware/GPU/512 MiB fiziksel RAM, tarayıcı/ofis yükü veya gerçek ses testi değildir.
- **11 ortak özellik grubu**, ortak paketlerin gerçek sürüm / yerel mimarileri, **20 görsel + 11 seçilmiş doğal kayıt hash'i** ve resmî boot / taban kimliği build ve export'ta tekrar denetlenir. Minimum kaynak profili özellik kaldırmaz. Teknik paket tabanı / kod adı korunur; görünen ürün OğuzDows'tur.
- Export öncesi ve son ham imajın **salt okunur loop** kontrolünde MBR/FAT/ext4, hizalama, model DTB/çekirdek/initramfs zinciri, çözülmüş PARTUUID, marka ve hesap güvenliği denetlenir. SSH anahtarları/machine-id, ortak kullanıcı ve parolasız sudo bulunması derlemeyi durdurur.
- Bu kontroller **Pi'nin firmware'den gerçekten açıldığını, VC4/V3D donanım hızlandırmasını, Wi-Fi/Bluetooth/kamera/HAT işlevlerini veya performansı kanıtlamaz.** Bunlar fiziksel test ister.

### Derleme test oturumunun güvenli kapanışı

İlk 1.2 hazırlık denemesinde (`5a31de8`, [45977169487](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/45977169487)) iki mimarinin hedef ARM / GTK / root olmayan Xfce kapıları geçti; ancak sonraki `stage-oguzdows` unmount işlemi `/run` ve `/dev` meşgul kaldığı için **iki Pi imajı da başarısız oldu ve yayımlanmadı**. Başarılı uygulama testi, tamamlanmış bir SD imajı sayılmaz.

`02-run.sh` artık özel test oturumunun root GTK/D-Bus ve ayrışmış non-root Xfce çocuklarını **geçici çalışma dizinini silmeden ve mount'ları ayırmadan önce** bekler/sonlandırır. Yalnız hostta çalışan `scripts/pi-ci-cleanup.py`, tam chroot kökü **ve** rastgele özel `HOME` yolu **ve** test UID'si eşleşmesini ister; pidfd ile PID yeniden kullanımını önler. Önce SIGTERM, yalnız kalan sahipli süreçlere sınırlı SIGKILL uygular. Başka HOME/UID ile aynı chroot'ta kalan bir süreç başarıyı engeller; genel `pkill`, `killall`, lazy/force unmount veya bağlı rootfs silme yoktur. Temizlik tamamlanmazsa çalışma dizini/emülatör korunur ve asıl hata kodu gizlenmez. Bu yardımcı **üretilen sisteme kurulmaz**.

Sahte `/proc` birim testlerine ek olarak ayrı zorunlu host CI adımı gerçek geçici chroot/root+non-root süreçleri ve Linux pidfd sinyallerini sınar; aynı `HOME` değerine sahip host sürecinin ve sahip olunmayan chroot sürecinin öldürülmediğini denetler. Bu yalnızca **derleme/test yaşam döngüsü regresyonudur**, fiziksel Pi açılış veya performans kanıtı değildir.

`.github/workflows/raspberrypi.yml` PC ISO işlerinden ayrıdır. PR'da test, `main` güncellemesi veya elle çalıştırmada seçilen iki/tek imaj derlenir. Yeni workflow henüz varsayılan dala eklenmediyse GitHub doğrudan dispatch'i kaydetmez; mevcut `main.yml` girişinden **`target=raspberrypi`** seçilerek aynı daldaki Pi workflow'u çağrılır. Bu seçim PC ISO işlerini başlatmaz:

```sh
gh workflow run main.yml --ref CALISTIGINIZ_DAL -f target=raspberrypi -f architecture=both
# architecture: both, armhf veya arm64
```

**Süren işler yeni bir çalıştırmayla iptal edilmez.** Artefaktlar imaj + SHA-256 + paket envanteri + kaynak kilidini taşır. Her build'de bilinen altı günlükten dosya başına son **2 MiB** ve üç JSON kanıtı (`pi-upstream-audit.json`, `pi-apt-adaptation.json`, `pi-runtime-report.json`) `OguzDows-Pi-gunluk-*` artefaktına alınır; eksik / kesilmiş / reddedilen dosyalar `collection.json` içindedir. JSON kanıtı kesilip geçerli rapor gibi sunulmaz. `upload-artifact` rootfs’i taramaz; günlük toplamak için rootfs’te `chmod -R` / `chown -R` yapılmaz.

[Önceki tam imaj çalışması 44791241701](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44791241701) Firefox paket yolu çakışmasıyla durdu. `f6d12f0` için [44800915275](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44800915275) bu hatayı ve günlük yükleme sorununu iki mimaride geçti; fakat minimum CPU Python/GTK içe aktarımı sonrasında başsız Xfce sürüm sorgusu ekran bulamadığı için **başarısız** oldu. Yeni özel Xvfb/XDG/D-Bus kapısı, taban kimliği ve ağ bekleme sırası resmî kaynaklarla karşılaştırılarak düzeltildi. Sonraki `469cbc3` [44816162831](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/44816162831) koşusunda host ve **arm64 imaj işi başarılı**, armhf ulaşılamayan Raspbian paket aynası nedeniyle APT 100 ile başarısız oldu. ARM64 kullanıcı-QEMU/GTK sonucu fiziksel boot veya performans değildir; imaj baytları bu sandbox’ta ayrıca indirilip hash doğrulanmadı. **Fiziksel boot ve ölçülmüş ARM hızlanması henüz yoktur.** Detaylı hata kanıtı, 12 dosya/mimari kaynak denetimi ve sonraki sürümlere taşınan sözleşmeler: **[ARM mimari / portlama kaydı](../docs/ARM-MIMARI-VE-PORTLAMA.md)**.

### Fiziksel yayın kontrol listesi

Her kart için ayrı kaydedin; henüz tamamlandığı iddia edilmez:

- [ ] Kart modeli/revizyonu, RAM, güç kaynağı, soğutma, SD/SSD ve imaj SHA-256.
- [ ] Zero/Zero W ARMv6; Pi 2 ARMv7; Zero 2/3; Pi 4; Pi 5 `2712` çekirdeği.
- [ ] Soğuk açılış, ilk bölüm büyütme/yeniden açılış, Türkçe hesap ekranı ve parola doğrulaması.
- [ ] İkinci açılışta kullanıcı/dosyalar/duvar kâğıdı korunması; ortak parola/NOPASSWD/autologin bulunmaması.
- [ ] HDMI/DSI, klavye/fare, Wi-Fi/ülke kodu, Ethernet/USB ağ, Bluetooth, HDMI/analog/USB ses.
- [ ] `glxinfo -B` gerçek VC4/V3D renderer; yazılımsal llvmpipe kullanılıyorsa raporlama.
- [ ] `vcgencmd measure_temp`, `get_throttled`, fan/termal davranış; düşük voltaj sorunu olmaması.
- [ ] Boşta RAM, zram, açılış süresi ve örnek web/ofis/video yükü; tüm kartlarda aynı ölçüm yöntemi.
- [ ] Ekransız dosya, açıkça etkinleştirilmiş SSH ve başarısız/yarım ilk kurulumda erişim engeli.
- [ ] SD ve desteklenen USB/SSD açılışı; ani güç kesintisi sonrası hesap kurulumu kurtarma.

Donanım merkezindeki rapor model, platform/SDIO/DRM bağlanmış sürücüleri, Pi sıcaklık/throttling bayraklarını ve kaynak profilini içerir; otomatik olarak dışarı gönderilmez. Sorun bildirirken raporla beraber güç/ekran/SD ayrıntılarını ekleyin. Raporu paylaşmadan önce kişisel bilgileri gözden geçirin.


## Hesap sonrası grafik giriş / oturum takibi

[Pi Zero oturum notu](../docs/PI-ZERO-OTURUM.md): ilk nesil ARMv6 / armhf kullanıcı
bildirimi izleniyor; mevcut siyah ekranın fiziksel kök nedeni henüz doğrulanmadı.
Yeni imaj yapısı LightDM ana dosyasının drop-in seçimini ezmesini önler,
`lightdm --show-config` çıktısını derlemeye yazar. Giriş politikası Xfce'den önce
uygulanır; mini/light girişinde tam rehber taraması ertelenir. LightDM servisi
başarısız olursa hesap tamamlanmış cihazda salt-okunur teşhis yönergesi konsolda
gösterilir; GPU / HDMI veya kullanıcı oturumundaki her siyahlığı yakalama garantisi değildir.

Yeni `pi_session_smoke.py` root olmayan UID 65534 / ayrı ev / Xauthority /
özel D-Bus ile **xfwm4 + xfce4-panel + xfdesktop** süreçlerini ve X11 WM'yi birlikte
beş örnekte doğrular, armhf’de gerçek NetSurf başlatıcısını yerel sayfayla açar.
Test kullanıcısı / daemon dağıtılmaz. LightDM/PAM, GPU, SD veya fiziksel 512 MiB
ölçümü değildir; eski başarılı imajın `--version` kapısı bu yeni kanıt yerine geçmez.
Paylaşılan yeni hafif başlangıç / oturum seçici / CSS, `b30dbf9` host CI'ında
[başarılıdır](../docs/releases/v1.1-development-sessions.json); bu raporda ARM
hedef oturumu veya yeni IMG açılışı sınanmış değildir.
