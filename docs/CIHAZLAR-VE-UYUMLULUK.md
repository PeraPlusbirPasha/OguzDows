# OğuzDows 1.1 · Cihazlar ve uygulama uyumluluğu

**1.1 geliştirme belgesi.** Kaynak / yapılandırma testinin geçmesi, bir telefonun veya kartın fiziksel olarak açıldığı anlamına gelmez. v1.0.0 yayımlanmış dosyaları değiştirilmez.

## Cihaz ailesi başka, mimari başka

| Profil | Kullanıcı alanı | Önyükleme yolu / düzey |
|---|---|---|
| PC amd64 | trixie / x86_64 | Mevcut BIOS / 64-bit UEFI ISO zinciri. v1.1 için yeni ISO testi gerekir. |
| PC i386 | bookworm / i686 PAE | BIOS ISO. 64-bit EXE çalıştırmaz; Flathub kapsamı varsayılmaz. |
| Pi Zero / 1 / 2 / 3 / 4 | bookworm / armhf, ARMv6 tabanı | Ayrı pi-gen tarifi: kernel.img / kernel7 / kernel7l / kernel8 ve kart DTB’leri. İlk Zero için 64-bit imaj kullanılmaz. Pi 5 bu 32-bit tarifin hedefi değildir. |
| Pi Zero 2 / 3 / 4 / 5 | bookworm / arm64 | Ayrı pi-gen tarifi: kernel8 / kernel_2712 ve kart DTB’leri. Fiziksel Pi boot / GPU / RAM doğrulaması bekliyor. |
| ARM64 UEFI | trixie / arm64 | Deneysel masaüstü katmanı. Çalışan üretici UEFI / ACPI / cihaz Linux’u önkoşuldur; kendi başına boot imajı değil. |
| PinePhone A64 | trixie / arm64 | Deneysel portlama katmanı. Cihaz özel U-Boot, DTB, ekran / güç / modem sürücüleri ayrıca gerekir. |
| PinePhone Pro | trixie / arm64 | Ayrı RK3399S / Tow-Boot veya U-Boot / DTB yolu. İlk PinePhone imajı bunun yerine geçmez. |
| ROCKPro64 | trixie / arm64 | Deneysel RK3399 kart katmanı; cihaz özel bootloader / DTB ve çalışan Linux gerekir. |
| Diğer Android / iPhone / ARM kartları | Değişir | **Destek doğrulanmadı.** SoC adı veya ARM64 olması yeterli değildir; otomatik flaşlama / bootloader kilidi açma yoktur. |

Cihaz Merkezi, bulunan / bildirilen profili ve Wine, Wayland, binder, Waydroid koşullarını gösterir. Telefon profillerinde karşılayıcının dar, ikonlu sol menüsü ve dikey kart düzeni kullanılır. Xfce’nin bütünü, modem, arama / SMS, GPS, dokunmatik, kamera, ses, askıya alma ve pil ömrü fiziksel telefonda test edilmiş sayılmaz. Dokunmatik ekran klavyesi yalnızca kullanıcı açarsa çalışır.

Deneysel katman üretimi — ağ, root veya aygıta yazma olmadan:

```sh
python3 scripts/configure-arm.py --device pinephone --output .cache/pinephone-katmani
python3 scripts/configure-arm.py --device arm64-uefi --output .cache/arm64-uefi-katmani
```

Çıktı **ROM / ISO / SD imajı değildir**: incelenebilir `overlay/`, `packages.list`, cihaz profili ve portlama notlarıdır. Cihazına uygun, zaten açılan trixie ARM64 rootfs üzerinde uzman incelemesi gerekir. Alpine / postmarketOS veya stok Android paket depoları bu sisteme karıştırılmaz. Çalışan kernel / boot / hesaplar körlemesine üzerine yazılmaz. Pi için mevcut `build-pi.sh` yolu ayrıdır.

## Mağaza ve ARM

Derlenen yerel GTK mağazası PC / Pi için kendi mimarisinde imaj aşamasında üretilir; masaüstü girişinde derleyici veya daemon çalışmaz. ARMv6 tabanlı Pi’de sistem uygulamaları kendi imzalı mevcut kaynaklarından alınır. ARM64’te kullanıcı onaylı Flathub da seçilebilir; her uygulamanın ARM sürümü veya düşük RAM’de iyi çalışacağı varsayılmaz.

Genel PC bakım / sürücü / gerçek KDE/GNOME / eski üçüncü taraf depo işlemleri ARM’e açılmaz. Mağazanın **yalnızca `app:` sabit paket demetleri** için ayrı ARM kimlik kontrolü vardır. PC: aynı sürümün imzalı Debian kökeni; Pi: aynı bookworm tabanının imzalı Debian / Raspbian / Raspberry Pi Foundation kökenleri. Yeni dağıtım kaynağı eklenmez; mimari, aday sürüm ve plan token’ı yine doğrulanır. Wine demeti ARM’e zorlanmaz. Genel sistem güncellemesi için cihazın kendi paket yöneticisi kullanılmalıdır.

## EXE: çift tık → incele → onayla

Yeni hesaplarda EXE MIME türleri **OğuzDows Uyumluluk** açıcıya bağlıdır. Eski hesabın kendi dosya ilişkilendirmeleri otomatik üzerine yazılmaz; sağ tık → Birlikte Aç ile seçilebilir. Menüden `oguzdows-open --manager` da açılır.

1. Normal, yerel `.exe` seçilir; sembolik bağlantı / aygıt / FIFO reddedilir.
2. MZ / PE, mimari, bölüm tablosu, boyut ve SHA-256 okunur. DLL veya bozuk / bilinmeyen DOS dosyası çalıştırılmaz. **Authenticode imzası veya virüs taraması yapılmaz.**
3. Uygun x86 PC ve önceden kurulu Wine gerekir. Mağaza → **Windows Uyumluluğu** yalnızca ayrı, açık onaylı paket planıdır; dosya seçmek Wine kurmaz.
4. 32-bit EXE için gerçek 32-bit Wine çalışma dosyaları aranır. Multiarch / i386 depoları otomatik açılmaz. ARM’de Box64 / x86 çevirisi veya Windows ARM desteği varsayılmaz.
5. Risk kutusu ve ikinci, varsayılanı **Vazgeç** olan onay sonrası dosya tekrar açılır, kimliği ve hash’i karşılaştırılır; özel 0700 dizine 0600 kopya alınır. Kaynak değişirse çalıştırılmaz.
6. Shell yerine sabit `/usr/bin/wine` argüman dizisi kullanılır. Her dosya özeti için ayrı kullanıcı Wine prefix’i vardır. **Prefix bir sandbox değildir; Wine ev dosyalarına / ağa erişebilir.** Güvenmediğiniz dosyaları açmayın; ayrı kullanıcı / izole VM daha güçlü ayrım sağlar.

Tek EXE kopyalanır, yanındaki DLL / veri dosyaları otomatik taşınmaz; bu nedenle bazı kurucular ayrıca hazırlanmayı gerektirir. Motorun başlaması / sıfır çıkışı, uygulamanın başarıyla kurulduğu anlamına gelmez. Sonucu uygulamanın kendi ekranından doğrulayın. Arayüz kapanışı çalışan Wine alt süreçlerini zorla öldürmez.

## APK: yalnızca hazırlanmış Android ortamında

APK’ye çift tıklamak Android servisi açmaz, sistem imajı indirmez ve root işlemi başlatmaz. ZIP merkez dizini / sayı / boyut / yol kontrolleri ve `AndroidManifest.xml` varlığı incelenir; arşiv kullanıcı dizinine çıkarılmaz. Yerel `.so` ABI’leri raporlanır. **APK imzası, geliştirici kimliği, içerdiği izinlerin tamamı veya zararlı yazılım doğrulanmış değildir.**

Koşulların hepsi gerekir:

- Uygun 64-bit cihaz ve APK’nın yerel ABI’si; 32-bit çeviri katmanı varsayılmaz.
- Cihaz çekirdeğinde binder ve çalışan, kullanıcıya ait Wayland soketi. Varsayılan Xfce X11 tek başına yeterli değildir.
- Cihaza uygun, önceden kurulu / hazırlanmış Waydroid; hem Session hem Container **RUNNING** olmalı. Araç kernel modülü yüklemez, servis açmaz, Android imajı / depo eklemez.
- En az 2 GB sınıfı fiziksel bellek, ayrıca boş kapasite; 4 GB önerilir. Bu 600 MB boşta Xfce hedefi değildir. Pi Zero / ARMv6 ve düşük bellekli cihazlar için APK desteği vaat edilmez.

Açık onay ve yeniden hash kontrolünden sonra yalnızca `/usr/bin/waydroid app install <özel-kopya.apk>` çağrılır. Motorun komut çıkışı tek başına Android Package Manager başarı kanıtı değildir; kurulu uygulamayı Android arayüzünden doğrulayın. Play Store / Google servisleri, DRM, banka / anti-cheat uygulamaları veya bütün APK’lar için uyumluluk sözü verilmez.

## Veriler ve çıkış

- Özel kopyalar / Wine prefix’leri / 0600 günlükler: `~/.local/share/oguzdows/compatibility/` (XDG_DATA_HOME değişirse ona göre).
- Kaynak dosya silinmez, hiçbir dosya kendiliğinden ağa yüklenmez. Açılan uygulamanın kendi ağ / dosya erişimi bunun dışındadır.
- EXE kopyası Wine alt süreçleri okuyabileceği için otomatik silinmez. Wine tamamen kapalıyken `inbox/` temizlenebilir. `wine/` silmek ilgili prefix içindeki kurulumu / uygulama verisini de siler; önce yedek alın.
- APK komutu sürerken pencere kapatılmaz; iş zorla öldürülmez. Kaynak / kurulum hataları başarı gibi gösterilmez.
- Testler sahte motorlar, üretilmiş küçük PE / APK örnekleri ve GTK görünümü içindir; gerçek EXE / APK veya fiziksel telefon çalıştırıldığı iddia edilmez.
