> **OğuzDows 2.0 “Akıncı” yayında.** PC, Raspberry Pi ve native launcher, aynı kimlikte. **[Web sitesi →](https://peraplusbirpasha.github.io/OguzDows/)** · **[Ücretsiz indir →](https://peraplusbirpasha.github.io/OguzDows/indir/)** · [Sürüm notları ve 26 dosyalı yayın](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0) · [Doğrulanmış yayın kaydı](docs/releases/v2.0-release.json).

<p align="center">
  <img src="docs/assets/oguzdows-banner.svg" width="100%" alt="OğuzDows 2.0 · Akıncı — PC, Raspberry Pi ve native launcher. Köklerinden güç alır. Özgürce üretir.">
</p>

<h1 align="center">OğuzDows 2.0 · Akıncı</h1>

<p align="center">
  <b>Türkçe. Hafif. Birbirine bağlı.</b><br>
  PC’de ve Raspberry Pi’de Debian tabanlı Xfce; telefonda ayrı native Aero launcher.<br>
  Kendine özgü bir masaüstü, hareketli yerel Rıfkı ve onaylı OğuzKöprü bağlantısı.
</p>

<p align="center">
  <a href="https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0"><kbd>2.0 · Akıncı</kbd></a>
  &nbsp; <kbd>PC · Pi · launcher APK</kbd> &nbsp; <kbd>Xfce</kbd> &nbsp; <kbd>Türkçe</kbd>
</p>

<p align="center">
  <a href="https://peraplusbirpasha.github.io/OguzDows/"><b>Web sitesi ↗</b></a> &nbsp; · &nbsp;
  <a href="#indir"><b>↓ İndir</b></a> &nbsp; · &nbsp;
  <a href="#ozellikler">Neler var?</a> &nbsp; · &nbsp;
  <a href="#manzaralar">Manzaralar</a> &nbsp; · &nbsp;
  <a href="#performans">RAM ölçümleri</a> &nbsp; · &nbsp;
  <a href="docs/TEKNIK-REHBER.md">Teknik rehber</a> &nbsp; · &nbsp;
  <a href="https://github.com/PeraPlusbirPasha/OguzDows/issues">Sorun bildir</a>
</p>

---

## 2.0 · Akıncı — aynı ağ, aynı masa

**[OğuzDows 2.0 · Akıncı](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0)**: yeniden derlenmiş **amd64/i386 ISO + Pi armhf/arm64 IMG.XZ + gerçek native launcher APK’sı**, aynı **`5a44de0`** kaynağı. İmajların iç ürün sürümü **2.0**, APK **`2.0.0-akinci` / kod20**. Eski imaj/APK yeniden etiketlenmedi; telefon paketi **debug uygulamasıdır, ROM/OTA/GSI değildir**.

**OğuzKöprü/1** PC, telefon ve ARM’ı seçilmiş dosyalar ve izinli **salt ekran** için bağlar: pinned TLS, iki ekranda kod, dosya bazında alıcı onayı. Gizli eşitleme, uzaktan SMS/kurulum veya fare-klavye yetkisi yoktur. Köprü, yeni PC/Pi imajlarına ve APK’ya dahildir; **[bağlantı rehberi →](docs/AKINCI-BAGLANTI.md)**.

**Masaüstü:** modern GTK/C-GTK, gerçek uygulama koyu/açık senkronu ve **PrintScreen**, optimize Thunar/kenarlar, native görev çubuğu/Dock. Atölye’nin **16 aracı** ve önceki sürümdeki toplam **23 ek işlev**, resimli/tıklanabilir Haber, imzalı APT ile Flatpak/GNOME Yazılımlar bileşen onarımı korunur. [Kullanım →](docs/ATOLYE-VE-MAGAZA-YENILEME.md)

**Telefon:** Kotlin/Compose HOME, gerçek uygulama arama/başlatma, kalıcı kısayollar ve gerçek widget; altı dokunmatik düzen, Ayarlar, medya sesi/paneller, sistem rehberi, Telefon/SMS/Mağaza ve hareketli yerel Rıfkı. [**Launcher APK’sı ve boş emülatöre kurulum →**](mobile/INSTALL.md) · [Gerçek yeni native ekran →](docs/assets/oguzdows-mobile-v2.jpg). Bulut AI/ses/wake-word etkin değildir; SystemUI/güvenli kilit cihaz genelinde değişmez.

[PC](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092345482), [Pi](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092347693) ve [mobil](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348) kabulü aynı kaynakta geçti: **24/24 native +20/20 JVM**, gerçek çift yönlü dört-dosya TLS/MediaProjection; ayrıca **16 başarılı host/ABI işi**. Kamuya açılmadan önce [ayrı salt-okunur denetim](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46100003996) 26 yayın dosyasını yeniden indirip hash’ledi, APK sürüm/imzalarını ve 27 ham kanıt dosyasını doğruladı. **[Sürüm notları, ölçümler ve açık sınırlar →](docs/releases/v2.0.md)**

> **Pi portları deneyseldir. Zero/Zero W hesap sonrası siyah ekran bildirimi hâlâ açıktır.** Mobil kabulde ANR/çökme yok, fakat **2205 ms HWUI beklemesi** ve aynı kaynaklı başka koşuda launcher otomasyon hatası kaydı vardır; kalıcı çözüm veya fiziksel pil/FPS/kararlılık iddia edilmez. [Pi teşhis](docs/PI-ZERO-OTURUM.md) · [Mobil geçmiş](mobile/VERIFICATION.md).

**Tarih korunur:** [1.2 · Ay Yıldız](docs/releases/v1.2.md) (`dc92fe9`, 17 dosya) ve [1.1](docs/releases/v1.1.md)/[1.0.0](docs/releases/v1.0.0.md) değişmez. 23 işlev 2.0’da ikinci kez “yeni” sayılmaz. Altı hafif Xfce tarzı gerçek GNOME/Plasma oturumu diye sunulmaz; fiziksel cihaz/ROM/AI yol haritası tamamlanmış sayılmaz.

<a id="indir"></a>

## Cihazına uygun paketle başla

**Güncel yayın: [OğuzDows 2.0 · Akıncı — PC + Pi + launcher APK](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0)**

İndirmeler herkese açıktır; GitHub hesabı gerekmez. **Önce CPU mimarisi, sonra RAM seçilir.** `amd64` Intel ve AMD 64 bit PC’ler içindir; düşük RAM tek başına 32 bit imaj seçme gerekçesi değildir.

| Cihazın | Paket | RAM / önemli koşul | Bütünlük dosyası |
| :--- | :--- | :--- | :--- |
| **64 bit PC** · Intel/AMD · ASUS X553M dahil | **[amd64 ISO ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-amd64.iso)** | Canlı/kurucu **1 GiB+**, günlük **2 GiB+**, modern web/ofis **4 GiB+ önerilir**; BIOS / 64 bit UEFI | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-amd64.iso.sha256) |
| **32 bit PC** · i686/PAE, tarayıcı için SSE2 | **[i386 ISO ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-i386.iso)** | Canlı/kurucu **1 GiB+**, günlük **2 GiB+ önerilir**; yalnız BIOS | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-i386.iso.sha256) |
| **Pi Zero/1/2**, düşük RAM’li **Zero 2/3** | **[Pi armhf IMG.XZ ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-rpi-armhf.img.xz)** | 512 MB deneysel **mini**, 1 GB **light**; NetSurf temel web. **Zero siyah ekran sorunu açık; Pi 5 için değil** | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-rpi-armhf.img.xz.sha256) |
| **Pi 4/400/5**; 64 bit uygulama isteyen **Zero 2/3 / Pi 2 rev 1.2** | **[Pi arm64 IMG.XZ ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-rpi-arm64.img.xz)** | Günlük **2 GB+**, modern web/ofis **4 GB+ önerilir**. Eski Zero/Pi 1/erken Pi 2 için değil | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-rpi-arm64.img.xz.sha256) |
| **Boş API35 x86_64 telefon emülatörü** | **[Launcher APK ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Mobile-2.0-Akinci-debug.apk)** | MinAPI29, kabul API35/Google APIs/4 GiB QEMU; debug imzalı uygulama, **ROM değildir**. [Kurulum](mobile/INSTALL.md) | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Mobile-2.0-Akinci-debug.apk.sha256) |
| **Tarayıcı tasarım laboratuvarı** | [Statik web arşivi ↗](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Web-2.0-Akinci.tar.gz) | Ayrı yerel tasarım yüzeyi; SIM/native widget/etkin model sunucusu yok | [SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Web-2.0-Akinci.tar.gz.sha256) |

**Pi dosyaları PC ISO’su değildir; fiziksel kart doğrulaması yoktur.** Pi 1’in 256 MB modelleri günlük masaüstü için önerilmez. Telefonlara/diğer ARM kartlarına bu imajları yazmayın. [Tam model/revizyon ve kapasite tablosu →](docs/releases/v2.0.md)

**APK için:** önce [boş emülatör kılavuzunu](mobile/INSTALL.md) izle; günlük fiziksel telefonunun varsayılan Telefon/SMS uygulamasını değiştirme. HOME ve diğer roller/izinler ayrıdır; ücretli/kişi/ekran işlemleri son yerel onay ister.

### İndir → doğrula → dene

1. **İmajı ve ona ait SHA-256 dosyasını** aynı klasöre indir. Örneğin:
   ```sh
   sha256sum -c OguzDows-amd64.iso.sha256
   # Pi için, sıkıştırılmış dosya üzerinde:
   sha256sum -c OguzDows-rpi-armhf.img.xz.sha256
   ```
   Sonuç `OK` olmalı. Dört imaj + üç APK + web dosyasının tamamı varsa [SHA256SUMS](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/SHA256SUMS) içindeki 8 girdiyi denetle; yalnız birini indirdiysen ayrı checksum’u kullan. SHA-256 bir bütünlük denetimidir; ayrıca imzalı yayın iddiası yoktur.
2. **PC:** ISO’yu güvendiğin bir imaj aracıyla **4 GB+ USB’ye** yaz. USB’den aç, **OğuzDows’u dene** ile donanımı kontrol et; hazır olunca **OğuzDows’u kur**.
3. **Pi:** `.img.xz` dosyasını Raspberry Pi Imager → **özel imaj** ile **16 GB+ SD/USB’ye** yaz; tercihen 32 GB A1/A2 kart kullan. **Imager kullanıcı/SSH özelleştirmelerini uygulama**; ilk açılışta portun kendi Türkçe kişisel hesap adımını tamamla. [Pi kurulum rehberi →](raspberrypi/README.md)

> [!IMPORTANT]
> **Önce yedek al; yazılan aygıtın içeriği silinir.** PC’de Secure Boot kapalı olmalıdır; 32 bit UEFI desteklenmez. Canlı PC hesabı `oguz` / `oguz`; parolasız yönetici yetkisi yalnız canlı ortam içindir. Kurulu PC’de kişisel hesap belirlenir ve canlı hesap temizlenir. **Pi’de ortak hesap/otomatik giriş/parolasız sudo yoktur; SSH varsayılan kapalıdır.** Yeni imaj mevcut kurulumu kendiliğinden yükseltmez.

[Kaynak / dosya manifesti](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/release-manifest.json) · [Ham test raporları](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/test-evidence.tar.gz) · [Önceki v1.2](docs/releases/v1.2.md) · [Önceki v1.1](docs/releases/v1.1.md) · [v1.1 yayını](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.1) · [Korunan önceki v1.0.0](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v1.0.0)

<a id="ozellikler"></a>

## Tanıdık hissettirir. Kendi karakterini taşır.

| Gündelik kolaylık | OğuzDows dokunuşu |
| :--- | :--- |
| **🇹🇷 Baştan sona Türkçe**<br>Türkçe Q klavye, İstanbul saat dilimi, anlaşılır karşılama ve OğuzDows kimliği taşıyan kurulum ekranları. | **🪶 Hafif Xfce masaüstü**<br>Opak ve okunaklı panel/başlıklar; varsayılan kapalı görsel efektler. Mağaza ve güncelleyici için otomatik başlayan süreç yok. |
| **🔧 OğuzDows Güncelleyici**<br>Önce paket/sürüm planını gör, sonra açık onay ve yönetici doğrulamasıyla ilerle. Donanımla eşleşen firmware önerilerini incele. | **📦 Uygulamalar, sen isteyince**<br>Yerel C/GTK mağaza: önce plan/izin, sonra koşullu kurulum ve ayrı Aç. Uygun mimaride kullanıcı Flatpak/Flathub; gelişmiş GNOME Yazılımlar seçeneği. Snap yok; otomatik indirme kapalı. |
| **🎨 Altı farklı tarz**<br>OğuzDows/XP, KDE, GNOME/Ubuntu, Klasik Xfce, elementary esintili Mac ve ortalı Windows 11: aynı hafif masaüstünde geri alınabilir düzenler; bağımsız açık/koyu tema. | **🐾 Rıfkı yanında**<br>İsteğe bağlı, hafif Van kedisi rehber; çevrimdışı Türkçe yazılı yardım ve yerel konuşma kayıtları. Mikrofon veya ağ üzerinden sohbet yok. |

**İnce dokunuşlar:** yerel hareketli **tespih imleci**, **nazar boncuğu pil göstergesi**, ay-yıldızlı açılış animasyonu, güvenli görüntü / düşük bellek önyükleme seçenekleri ve **20 kültür duvar kâğıdı**. Hafif C/GTK Haber, otomatik ağ isteği olmadan RSS/Atom özetlerini ve çevrimdışı önbelleği gösterir.

**Kurulumda sürpriz değil, açık sonuç:** kurucu başarı, iptal, hata ve doğrulanamayan sonucu ayırır; sonuç ekranı kendiliğinden kaybolmaz. Yeniden başlatma ayrıca onay ister. Ek sürücü uyarısı, temel kurulum başarısı gibi sunulmaz.

### Biraz da bizden

| Araç | Ne yapar? |
| :--- | :--- |
| **🍵 Çay Molası** | Kısa bir nefes için istek üzerine açılan mola aracı. |
| **⌨️ Türkçe Hızlı Yazım** | `I/ı` ve `İ/i` dahil Türkçe yazım alıştırmaları. |
| **🎒 Heybe** | Senin seçtiğin klasörlerden yerel yedek arşivi oluşturur. |
| **🤝 İmece** | Seçtiğin dosyaları paylaşmaya hazır yerel bir ZIP’e koyar. |

Bu araçlar kendiliğinden dosya yüklemez, paylaşmaz veya kaynak silmez. Heybe/İmece arşivleri **şifreli değildir**; özel içeriklerini kontrol et.

<a id="manzaralar"></a>

## Masaüstünde Türkiye’den izler

<table>
  <tr>
    <td width="33%" align="center"><a href="system/usr/share/backgrounds/oguzdows/bogaz-sabahi.jpg"><img src="docs/assets/bogaz-sabahi.jpg" width="100%" alt="Boğaz Sabahı duvar kâğıdı önizlemesi"></a><br><b>Boğaz Sabahı</b></td>
    <td width="33%" align="center"><a href="system/usr/share/backgrounds/oguzdows/kackar-sisi.jpg"><img src="docs/assets/kackar-sisi.jpg" width="100%" alt="Kaçkar Sisi duvar kâğıdı önizlemesi"></a><br><b>Kaçkar Sisi</b></td>
    <td width="33%" align="center"><a href="system/usr/share/backgrounds/oguzdows/kapadokya-isigi.jpg"><img src="docs/assets/kapadokya-isigi.jpg" width="100%" alt="Kapadokya Işığı duvar kâğıdı önizlemesi"></a><br><b>Kapadokya Işığı</b></td>
  </tr>
  <tr>
    <td align="center"><a href="system/usr/share/backgrounds/oguzdows/oludeniz-kiyisi.jpg"><img src="docs/assets/oludeniz-kiyisi.jpg" width="100%" alt="Ölüdeniz Kıyısı duvar kâğıdı önizlemesi"></a><br><b>Ölüdeniz Kıyısı</b></td>
    <td align="center"><a href="system/usr/share/backgrounds/oguzdows/tuz-golu-aksami.jpg"><img src="docs/assets/tuz-golu-aksami.jpg" width="100%" alt="Tuz Gölü Akşamı duvar kâğıdı önizlemesi"></a><br><b>Tuz Gölü Akşamı</b></td>
    <td align="center"><a href="system/usr/share/backgrounds/oguzdows/ani-kisi.jpg"><img src="docs/assets/ani-kisi.jpg" width="100%" alt="Ani Kışı duvar kâğıdı önizlemesi"></a><br><b>Ani Kışı</b></td>
  </tr>
</table>

Bu altı önizleme, **20 kültür görselli** galeriden bir seçkidir. Her manzaranın sağ altında **OğuzDows logosu** bulunur. 1920×1080 yerel görseller; ağdan indirme veya sürekli çalışan slayt servisi yoktur. Özel duvar kâğıdın korunur.

<sub>Bu altı önizleme yapay zekâ üretimidir; galerinin tamamı 16 AI görsel + 4 özgün çizimdir. Bunlar gerçek kamera fotoğrafı veya birebir coğrafi belge değildir. Bu galeri masaüstü ekran görüntüsü değil, paketlenen duvar kâğıtlarının önizlemesidir. [Görsel ve ses kaynakları →](artwork/README.md)</sub>

<a id="performans"></a>

## Hafiflik, yalnızca bir sıfat değil

**2.0 / `5a44de0` ISO’larından** hazırlanan özel disklerde gerçek tam Xfce ölçümü; yeni dosyalar, yeni ölçümler:

| İmaj · en yüksek kullanım (decimal MB) | 512 MiB VM | 1024 MiB VM | 2048 MiB VM |
| --- | ---: | ---: | ---: |
| **amd64** | **297.1** | **490.2** | **501.7** |
| **i386** | **195.6** | **407.1** | **479.8** |

Ağsız QEMU/TCG · 2 sanal CPU/std VGA · **120 saniye yerleşme + 5 saniye aralıklı 6 örnek**, `MemTotal − MemAvailable`. Rehber/Rıfkı/Mağaza/Haber/compositor kapalı; 512/1024 MiB’de OOM yokluğu ve kullanılabilir RAM payı zorunlu. Fiziksel PC/Pi/telefon veya gerçek GNOME/Plasma için ölçüm değildir. **512 MiB boşta açılış, canlı kurucu veya modern tarayıcı konforu demek değildir.** [2.0 yöntem ve ham kanıt →](docs/releases/v2.0.md)

<details>
<summary>Tarihsel 1.2 ölçümleri — 2.0 sayıları değildir</summary>

**Yayımlanmış v1.2**, `dc92fe9` ISO içeriğinden hazırlanan özel test diskinde gerçek **tam Xfce oturumu** ile ölçüldü; eski sürüm sayıları kullanılmaz.

| İmaj · en yüksek kullanım (decimal MB) | 512 MiB VM | 1024 MiB VM | 2048 MiB VM |
| :--- | ---: | ---: | ---: |
| **amd64** | **290.0 MB** | **474.8 MB** | **507.2 MB** |
| **i386** | **191.9 MB** | **413.7 MB** | **471.5 MB** |

**Koşullar:** ağsız QEMU/TCG · 2 sanal CPU/std VGA · 120 saniye yerleşme + 5 saniye aralıklı 6 örnek. `MemTotal − MemAvailable`, RSS toplamı değil. Rehber/Rıfkı/Mağaza/Haber ve compositor kapalı; 512/1024 MiB'de OOM yokluğu ve `max(32 MiB, MemTotal/10)` kullanılabilir pay kapıları geçti.

**512 MiB'de boşta Xfce'nin açılması, kurucu/tarayıcı/ofisin rahat çalışacağı anlamına gelmez.** Fiziksel PC, Pi ve gerçek KDE/GNOME bu RAM ölçümünün kapsamında değildir. [1.2 ölçüm/test sınırları](docs/releases/v1.2.md) · [Tarihsel 1.1](docs/V1.1-TEST-KANITI.md) · [v1.0.0](docs/MASAUSTU-TEST-KANITI.md)

</details>

### Donanım için kısa rehber

| | Beklenti |
| :--- | :--- |
| **İşlemci** | amd64 için 64 bit x86; i386 için i686/PAE, tarayıcı için SSE2. |
| **Bellek** | Günlük kullanım için **en az 2 GiB önerilir**. Canlı ortam/kurucu en az 1 GiB kontrolü yapar; tarayıcı/ofis ek bellek ister. |
| **Disk** | Kurulumda en az **12 GiB boş alan** kontrol edilir; uygulama ve dosyaların için ek yer ayır. |
| **Önyükleme** | amd64 BIOS + 64 bit UEFI; i386 BIOS. **Secure Boot kapalı** olmalı. |
| **Eski aygıtlar** | Eski görüntü/ağ firmware’leri ve lisans onaylı çevrimdışı ek sürücü akışı. Her donanım için uyumluluk garantisi yoktur. |

Siyah ekranda **güvenli görüntü**, az bellekte **düşük bellek** açılışını dene. Donanım merkeziyle sürücü durumunu incele; rastgele depolardan sistem/çekirdek paketi karıştırma. [Sürücü ve kurulum ayrıntıları →](docs/TEKNIK-REHBER.md#eski-cihazlar-ve-sürücüler)

## Senin sistemin, senin kararın

- **Onay önce gelir.** Kurulum, ek sürücü, güncelleme ve isteğe bağlı depo işlemlerinde açık kullanıcı/yönetici onayı gerekir. Heybe/İmece dosyalarını otomatik göndermez.
- **Pardus kanalı varsayılan kapalıdır.** Yalnızca uygun amd64/trixie tabanında, sabit anahtar ve güncel imza/mimari/tarih/pin denetimleriyle dar uygulama listesi değerlendirilir. Genel sistem deposu karıştırılmaz.
- **KDE/GNOME tarzı ≠ gerçek KDE/GNOME.** Altı tarz Xfce görünümüdür. Gerçek masaüstleri amd64 / ARM64’te ayrıca, daha yüksek kaynak beklentisi ve onaylı paket planıyla sunulur; gerçek giriş oturumları henüz doğrulanmadı.
- **Sınırlar saklanmaz.** İmzalı APT ile Flatpak/GNOME Software bileşen kurulumu ayrı CI kaplarında geçti; etkileşimli Polkit, Flathub uygulaması indirme/çalıştırma, şifreli tam kurulum ve fiziksel aygıt kapsamı ayrı kalır. i386/eski ARM için Flathub kapsamı varsayılmaz.
- **Rıfkı bilinçli olarak hafiftir.** Pencere takip eden ağır animasyonlar kaldırıldı. Konuşmalar yapay zekâ ile hazırlanmış yerel kayıtlardır; panel rehberleri yerel kayıtlara bağlıdır; değişken hata / haber metni otomatik seslendirilmez.

[Masaüstü ve bakım rehberi →](docs/MASAUSTU-VE-BAKIM.md)

## Raspberry Pi için ayrı bir yol

Zero–5 ailesi için ayrı `armhf` / `arm64` SD/USB imajı akışı bulunur. PC ISO’su Pi’ye yazılmaz; Pi’de ilk açılışta kişisel hesap oluşturulur, ortak canlı parola veya parolasız sudo yoktur.

**v2.0 Akıncı yayını hem armhf hem arm64 dosyasını içerir; Pi portları deneyseldir.** ARM1176/Cortex-A53 kullanıcı-QEMU + host Xvfb’de root olmayan tam Xfce, native Haber ve armhf NetSurf yerel sayfası geçti. Fiziksel Pi açılışı/LightDM/PAM/GPU/performance doğrulaması değildir; **Zero hesap sonrası siyahlık bildirimi açıktır**. Resmî Pi OS/pi-gen kaynak/ABI/paket/varlık kapıları ve kaynak kilidi korunur; sonraki portlar için kanıtlar saklanır. [Mimari karşılaştırma ve portlama verisi →](docs/ARM-MIMARI-VE-PORTLAMA.md) · [Pi rehberi →](raspberrypi/README.md)

## Yeni bir sayfa, yeni bir ana sürüm

```text
v1.0.0  ·  Ay Yıldız — yayımlandı
   ↓
v1.1    ·  Ara güncelleme — PC + Pi yayımlandı
   ↓
v1.2    ·  23 yeni işlev / modern arayüz — PC + Pi yayımlandı
   ↓
v2.0    ·  Akıncı — PC + Pi + native launcher APK / OğuzKöprü
   ↓
v3.0    ·  Sonraki ana yayın
```

Bundan sonraki yeni ana yayınlar **v2.0, v3.0, …** olarak ilerler. Bu bir sürümleme düzenidir; takvim veya henüz tamamlanmamış özellikler için söz değildir. **Mevcut v1.0.0 etiketi ve ISO’ları yeniden adlandırılmaz.** Her yeni yayın kendi kaynak commit’i, ISO’ları, SHA-256 dosyaları, Türkçe sürüm notları ve test kanıtlarıyla paylaşılır.

[Yayın ve sürümleme politikası →](docs/SURUM-POLITIKASI.md) · [Tüm yayınlar →](https://github.com/PeraPlusbirPasha/OguzDows/releases)

## Merak edenler ve katkı verenler için

```sh
# ISO üretmeden, çevrimdışı yapılandırmayı incele:
python3 scripts/configure.py --arch amd64 --output /tmp/oguzdows-config

# Test bağımlılıkları hazırken yerel kontroller:
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Tam ISO derlemesi root, ağ ve yeterli disk alanı gerektirir. Hazırlık adımları, test ortamı, kaynak düzeni ve temizlik kuralları **[teknik rehberde](docs/TEKNIK-REHBER.md)**. Çalışan bir ISO/Pi işi yeni bir iş geldi diye iptal edilmez.

| Yol gösterici | İçerik |
| :--- | :--- |
| [Web sitesi ve ücretsiz görünürlük](docs/WEB-VE-GORUNURLUK.md) | GitHub Pages, sayfa/SEO altyapısı, Search Console adımları ve ücretsiz tanıtım planı. |
| [Teknik rehber](docs/TEKNIK-REHBER.md) | Derleme, kurulum güvenliği, eski sürücüler, Rıfkı ve geliştirici testleri. |
| [Masaüstü ve bakım](docs/MASAUSTU-VE-BAKIM.md) | Mağaza, güncelleyici, tarzlar, kültür araçları ve depo güveni. |
| [2.0 Akıncı indirme ve test kanıtı](docs/releases/v2.0.md) | Aynı kaynaklı dört imaj + native APK/web, onaylı bağlantı, düşük RAM/ABI ve 26 dosyalı yayın denetimi. |
| [Mobil kurulum ve geçmiş](mobile/INSTALL.md) | Debug APK, gerçek emülatör kabulü ve açık fiziksel SIM/ROM/AI sınırları. |
| [Tarihsel 1.2](docs/releases/v1.2.md) | Önceki dört imaj, 23 işlev ve değişmeyen yayın kanıtı. |
| [Tarihsel 1.1 kanıtı](docs/V1.1-TEST-KANITI.md) | Önceki imajların değişmeyen kaynak, ölçüm ve test sınırları. |
| [Kurulum karşılaştırması](docs/KURULUM-KARSILASTIRMA.md) | Kali/Linux Mint kaynak incelemesi ve kurulum kontrollerinin gerekçeleri. |
| [Raspberry Pi](raspberrypi/README.md) | ARM hedefleri, ilk hesap, güvenlik ve fiziksel test sınırları. |

Bir sorun bildirirken cihaz modelini, ISO mimarisini/sürümünü ve kişisel bilgileri ayıklanmış hata çıktısını ekle. Donanım raporun **kendiliğinden gönderilmez**.

---

<sub>OğuzDows PC tabanı amd64 için Debian trixie, i386 için Debian bookworm’dur. Xfce, Calamares, GNOME Software, Flatpak ve diğer üçüncü taraf bileşenlerin köken, telif ve lisans bilgileri korunur. Ürün kimliği, bu bilgileri gizlemek anlamına gelmez.</sub>

<p align="center"><b>Biraz Anadolu. Biraz merak. Bolca emek.</b><br><sub>OğuzDows 2.0 · Akıncı</sub></p>
