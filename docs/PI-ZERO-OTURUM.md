# Pi Zero · hesap ekranından sonra siyah ekran

## Doğrulanmış bildirim ve henüz bilinmeyenler

Kullanıcının cihazı **ilk nesil Pi Zero / Zero W (ARMv6)**; yazılan imaj **armhf**.
Hesap oluşturma / giriş ekranı görülüyor, sonrasında masaüstü siyah kalıyor.
Bu bilgi yanlış mimari veya hiç HDMI sinyali yok varsayımına indirgenmez.
Ekranın tam olarak Türkçe metin hesabından mı, grafik greeter girişinden mi sonra
karardığı ve LightDM / Xorg / kullanıcı günlükleri henüz doğrulanmadı.
**Kesin kök neden, başarılı fiziksel düzeltme veya Pi RAM tasarruf miktarı ilan edilmez.**

Önceki yeşil Pi derlemesi root GTK penceresi + Xfce sürüm yanıtını sınadı;
normal kullanıcının LightDM → masaüstü girişini veya gerçek GPU'yu kanıtlamadı.
Başarılı PC `440cf74` / 45069328093 512 MiB VM ölçümü de Pi sonucu değildir.

## Bu yeni kaynakta yapılanlar

1. LightDM `conf.d` dosyalarını **ana `lightdm.conf` öncesinde** okur. Yalnızca
   drop-in'e `user-session=oguzdows` yazmak ana dosyanın eski LXDE / greeter
   seçimini önlemiyordu. İmaj aşamasında yalnızca oturum / greeter anahtarları
   ana dosyada da ayarlanır; diğer satırlar / yorumlar korunur. Gerçek
   `lightdm --show-config` derleme çıktısına eklenir; export ana dosyayı da
   denetler. Bu yapılandırma açığı **kullanıcının kartındaki kesin neden olarak
   gösterilmez**. Kurulu kullanıcının mevcut `.dmrc` dosyası topluca silinmez.
2. Gerçek Xsession girdisi `session_start.py` kullanır. Düşük RAM efekt politikası
   pencere yöneticisinden **önce** uygulanır; sonrasında `exec startxfce4` olur,
   kalıcı Python denetleyicisi kalmaz. X11 masaüstü ortamı açıktır. `mini/light`
   için LLVM yazılım fallback işçileri 1/2, glibc arena üst sınırı 2'dir;
   kullanıcının açık ortam tercihi korunur, GPU sürücüsü zorla değiştirilmez.
   ARMv6'da GTK4 Cairo tercihi GL/Vulkan renderer yükünü önlemeyi hedefler.
3. `~/.local/state/oguzdows/session/startup.json` yalnızca UID / profil / dört
   izinli ortam anahtarı yazar (0700 dizin / 0600 dosya). Parola ve tam ortam
   kaydedilmez; bu dosya **başlangıç isteğidir, başarı işareti değildir**.
4. `mini/light` otomatik girişinde tam rehber / donanım taraması yerine küçük
   statik GTK karşılama vardır. Tam rehber, sesli paneller, Rıfkı ve bütün
   araçlar istek üzerine aynı düğmeden / Başlat menüsünden açılır. Canlı PC'de
   hafif kurucuya doğrudan düğme korunur. Kapanınca worker kalmaz; bu küçük
   pencere de bir sonraki otomatik başlangıçta tekrarlanmaz. Manuel rehber
   çağrıları normal tam arayüzü açar. Otomatik tam rehber tercihi kapatılmışsa
   hafif pencere de açılmaz. Canlı / kurulu / Pi işaretleri ayrıdır.
5. LightDM servisi başarısız olup systemd hata durumuna gelirse, hesap
   tamamlanmış cihazda konsolda Türkçe teşhis yönergesi gösterilir. Bu, çalışan
   LightDM altındaki her Xfce / GPU siyahlığını yakalayan watchdog değildir.
   Otomatik root giriş, reboot, sürücü silme veya KMS kapatma yapılmaz.
6. armhf ürün sözleşmesinde **NetSurf GTK** zorunludur; Firefox ve dil paketi
   zorunlu listeden çıkarılır. Office / VLC, ağ / Bluetooth, eski sürücüler,
   mağaza, kültür araçları / duvar kâğıtları / sesler korunur. Web bağlantısı
   `oguzdows-browser.desktop` üzerinden açılır; sahte Firefox kısayolu yoktur.
   NetSurf temel HTML / haber içindir; **JavaScript, modern web uygulamaları,
   video platformları veya bütün sitelerle uyumluluk vaat edilmez**. arm64'te
   1 GiB ve altındaki Pi'de NetSurf, daha güçlü kartta kurulu Firefox seçilir.
   Tarayıcı sandbox'ı kapatılmaz. İsteğe bağlı kullanıcı tercihi
   `~/.config/oguzdows/browser.conf` içinde `browser=auto|netsurf|firefox` olur;
   seçenek / shell kabul edilmez, ARMv6 Firefox isteği reddedilir.

## Yeni test kapısı ve sınırı

`pi_session_smoke.py`, derleme chroot'unda UID 65534 / ayrı, geçici ev / ayrı
Xauthority / özel D-Bus ile **gerçek ürün session_start → startxfce4** girişini
çalıştırır. `xfwm4 + xfce4-panel + xfdesktop`, X11 WM adı ve gerçek kullanıcı
Xfconf'u beş ardışık örnekte gerekir. armhf'de varsayılan web başlatıcısı
NetSurf'ü yerel başlangıç sayfasıyla açmalı ve erken çökmemelidir. Rapor olmadan
export başarılı sayılmaz. Yalnızca teste ait HOME / UID / süreç grubu temizlenir;
test hesabı veya Xvfb imaja eklenmez. Önceki sürüm kapıları da korunur.

Bu test **ARM kullanıcı emülasyonu + host Xvfb**'dir. LightDM/PAM/logind, gerçek
Pi firmware/kernel/GPU, 512 MiB fiziksel bellek, kamera, ses, Wi-Fi / SD veya haber
sitesi TLS / JavaScript uyumluluğu kanıtı değildir. Yeni kodun fiziksel Zero'da
sınanması ve aşağıdaki günlüklerle doğrulanması gerekir.

## Mevcut kartta salt okunur teşhis

Siyah ekran sırasında **Ctrl+Alt+F2** ile metin ekranına geçin, kendi hesabınızla
giriş yapın. Aşağıdaki komutlar servis / disk / sürücü ayarı değiştirmez:

```sh
systemctl --no-pager -l status lightdm
journalctl -b -u lightdm --no-pager -n 60
journalctl -b -u oguzdows-pi-firstboot --no-pager -n 40
tail -n 60 ~/.xsession-errors
cat ~/.local/state/oguzdows/session/startup.json
```

Son dosya yalnızca yeni kaynakla vardır; yokluğu eski imajda beklenir. Günlükler
izin nedeniyle görünmüyorsa aynı salt-okunur `journalctl` komutunu kendi yönetici
parolanızla `sudo` kullanarak çalıştırabilirsiniz. **Parolanızı, parola özetini,
`/etc/shadow` veya hesap hazırlama dosyasını paylaşmayın.** Kullanıcı adı,
SSID ve kişisel yolları ayıklayın. Bu Pi'nin journal'ı uçucudur; yeniden
başlatmadan önce ilgili çıktıyı kaydedin.

TTY de görünmüyorsa bu, aynı tür oturum arızası diye varsayılmaz. Boot bölümünde
`cmdline.txt` tek satır ve root PARTUUID korunarak yalnızca `quiet splash`
kaldırılıp `plymouth.enable=0 systemd.show_status=1` eklenebilir. KMS'yi bütün
modellere `nomodeset` ile zorlamayın; `gpu_mem`, CMA veya çözünürlük tahminleri
fiziksel günlük olmadan genel düzeltme diye dağıtılmaz.

## Görünüm, gerçek oturum ve Aero

Altı kart **Xfce düzenidir**. Windows 11 ortalı kısa / simgeli çubuk; macOS üst
çubuk + alt iskele; Ubuntu üst çubuk + sol iskeledir. Bunlar Windows / macOS
kurmaz. Panel yenile kutusu açıkken Uygula, yeni yerleşimi de yeniler; kişisel
panellerin tipli yedeği / geri alma ve açık uygulamalar korunur.

Gerçek Plasma / GNOME **ayrı** kurulum planı ve kurulu X11 oturumu seçimiyle
sunulur. Kendi imzalı tabanından sabit demet / önizleme / onay / Polkit geçerlidir.
amd64 / ARM64 ve en az 2 GiB sınıfı cihaz koşulu hem UI'da hem root arka uçta
kontrol edilir; 4 GiB ve çalışan 3B sürücü önerilir. Zero / armhf / i386 / 512 MiB /
1 GiB'ye ağır oturum kurulumu önerilmez / bu araçla açılmaz. Güncel paket
kullanılabilirliği ve gerçek ARM oturum performansı ayrıca sınanmalıdır.
Varsayılan Xfce / LightDM kaldırılmaz. `.dmrc` ve varsa AccountsService kişinin
kendi XSession tercihidir; otomatik çıkış yapılmaz. Normal çıkıştan sonra giriş
menüsünde oturumu doğrulayın; gerektiğinde OğuzDows / Xfce'ye dönün.

Aero esintisi **opak statik yansımalı başlık** sağlar. >2 GiB, ARMv6 olmayan,
nomodeset olmayan ve tanınan DRM sürücülü full profilde, açık istekle alt çubuk /
iskelede hafif alfa ve çerçeve gölgesi olabilir. Bilinen DRM sürücüsü tek başına
hız ölçümü değildir. Blur / sürekli animasyon / picom daemon yoktur. Zero'da
aynı statik renk / yansıma kalır, compositor açılmaz. Üst çubuk, içerik, yazılar
ve kapatma düğmeleri her bütçede okunaklı ve opaktır. Fiziksel GPU / RAM kazancı
ayrıca ölçülmelidir.
