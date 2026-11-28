# OğuzDows 2.0 · Akıncı — aynı ağ, aynı masa

PC, Raspberry Pi ve telefon farklı işletim sistemi paketleri kullanır; **OğuzKöprü/1** aynı onaylı yerel dosya/ekran protokolünü konuşur. Hesap, gizli keşif, internet rölesi veya otomatik eşleştirme yoktur. Mevcut 1.x imajlar kendiliğinden 2.0’a yükselmez.

## Önce doğru paketi seç

[Tüm 2.0 Akıncı indirmeleri](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0)

- **64 bit Intel/AMD PC:** `OguzDows-amd64.iso`; amd64 iki işlemci markasını da kapsar.
- **Gerçek 32 bit x86 PC:** `OguzDows-i386.iso`, i686/PAE/SSE2 ve BIOS. 32 bit UEFI/Secure Boot yoktur.
- **Pi Zero/1/2/3/4:** `OguzDows-rpi-armhf.img.xz`; ARMv6 kullanıcı alanı, deneysel port. Pi 5 için uygun değildir.
- **Zero 2 W / Pi 2 rev1.2 / Pi 3/4/5:** `OguzDows-rpi-arm64.img.xz`, deneysel port.
- **Telefon/emülatör:** [OguzDows-Mobile-2.0-Akinci-debug.apk](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Mobile-2.0-Akinci-debug.apk). API29+ normal launcher uygulaması; doğrulama API35 x86_64 QEMU üzerindedir. **Telefon ROM’u/OTA/GSI değildir.** Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı deneysel paketle değiştirme.
- **Tarayıcı laboratuvarı:** `OguzDows-Web-2.0-Akinci.tar.gz`, ayrı tasarım/yerel veri yüzeyi. SIM, sistem widget’ı, uzaktan dosya yetkisi veya ekran kontrolü vermez. Statik içerikte üretken model sunucusu yoktur.

Önce yayın `SHA256SUMS` ve manifestindeki boyut/hash’i doğrula. APK **debug imzalıdır**; kurulum izinleri sistemde açıkça seçilir. Derlemeler arasında debug anahtarı değişebilir; imza uyuşmazlığını gidermek için günlük verini silme, boş emülatör kullan. PC/Pi kurulumunda yedek al; yanlış diske yazma. Pi en az 12 GiB kullanılabilir medya (16 GB kart önerilir); canlı PC kurulumunda 1 GiB+, günlük kullanımda 2 GiB+, web/ofis için 4 GiB+ önerilir. Telefon hedefi 4–6 GB; ölçülmüş fiziksel pil/FPS garantisi değildir.

## 1. İki cihazı hazırla

1. Aynı güvenilir Wi-Fi/Ethernet ağına bağla. Misafir/AP yalıtımı veya güvenlik duvarı bağlantıyı engelleyebilir; güvenlik duvarını tümden kapatma.
2. PC/Pi’de uygulama menüsünden **OğuzKöprü**, telefonda **Dosyalar / OğuzKöprü** aç. Yalnız 2.0 güncel imajlarında bu sürümün köprü kodu vardır; eski 1.2 imajına gelmiş gibi gösterilmez.
3. Bir cihazda **15 dakikalık masa aç** seç, doğru özel yerel IPv4 arayüzünü seçip iki dakikalık daveti göster. `127.0.0.1` yalnız aynı cihazdır; gerçek cihazlarda davet için yerel ağ adresini kullan.
4. Daveti güvenilir özel kanaldan diğer cihaza aktar; herkese açık sohbet/ekran görüntüsü/loga koyma. Kopyalama/yapıştırma manuel ve isteğe bağlıdır.

## 2. İki ekranda doğrula

1. Diğer cihazda daveti yapıştırıp eşleşme iste.
2. **Sekiz haneli kod her iki ekranda birebir aynı olmalı.** İsim tek başına kimlik değildir.
3. Masa sahibi izin verir; istemci de kodun aynı olduğunu onaylar. Kod farklıysa reddet/oturumu kapat, daveti yenile.
4. Davetteki sertifika SHA-256 parmak izi her TLS bağlantısında, sır veya dosya yollanmadan önce denetlenir. Genel internete port açma, yönlendiricide port forward yapma.

## 3. Dosya bırak ve al

- PC’de dosyayı masaya bırak veya sistem seçicisini kullan. Telefonda sistemden belge seç; kartı uzun basıp cihaza/masaya sürükle. Erişilebilir düğmeler aynı işi yapar.
- Masa sahibinin sunduğu dosya bu oturumun tüm onaylı eşlerine görünür. İstemciden gönderim için alıcının **dosya bazında Kabul** seçimi ayrıca gerekir.
- Alım gerçek SHA-256 ile doğrulanır. Kalıcı kaydı ayrıca seç; dosya/APK otomatik açılmaz, arşivden çıkarılmaz veya kurulmaz.
- En çok 2 onaylı eş, 8 öğe/kuyruk, 128 MiB/dosya ve 256 MiB/kuyruk. Normal kapanış özel kopyaları siler; ayrıca kaydettiğin dosya silinmez.

## 4. İzinli ekran paylaşımı

- **Telefon kaynaksa:** onaylı eş için Ekranımı paylaş → açıklamayı oku → her başlangıçta gerçek sistem uygulama/tüm ekran seçimini ve son onayı ver. Foreground bildirimindeki veya uygulamadaki **Durdur** ile bitir. İptal paylaşım başlatmaz; kilit/izin/erişim kaybında durur.
- **PC/Pi kaynaksa:** yalnız açık/kilitsiz olduğu gerçek sistemden doğrulanabilen X11 oturumunda açık onayla açılır. Durum bilinmiyorsa veya Wayland ise başlamaz; tam Wayland portalı henüz yoktur.
- **Salt görüntü:** telefon en çok 2 kare/sn, PC en çok 1 kare/sn, 1280 px uzun kenar/512 KiB JPEG. Oyun/video akıcılığı, ses/mikrofon/fare/klavye veya uzaktan SMS/kurulum aktarılmaz. DRM/güvenli pencereler siyah olabilir; eski kare canlı diye tutulmaz.

## Sınırlar ve gizlilik

HOME/yardımcı/Telefon/SMS rolleri, rehber okuma/yazma ve ekran izni ayrıdır. Kilit eşlikçisi güvenli PIN/biyometriyi veya sistem bildirim perdesini cihaz genelinde değiştirmez. Root/Accessibility/overlay/device-admin/sessiz izin verme yoktur. Rıfkı bu sürümde yerel kural tabanlıdır; bulut, mikrofon, TTS/ASR ve wake-word etkinleştirilmez.

Dosya baytları ve ekranlar yalnız seçilmiş onaylı yerel eşe gider; uzaktaki eş telefonun Telekom/SMS/yükleyici yetkisini alamaz. Telefon yüzeyinden çıkışta oturum kapanır; yalnız sistem onaylı ekran paylaşımı bildirimle sürebilir. Sistem seçicileri için sınırlı süre istisnası vardır. PC/Pi süreç çökmesi sonrası geçici dizin temizliği OS politikasına kalabilir.

Emülatör/loopback/ARM kullanıcı-QEMU ve host GTK sonuçları **fiziksel PC/telefon/Pi, GPU/pil/RAM/FPS veya modem kabulü değildir**. Pi Zero/Zero W hesap ekranından sonra bildirilen siyah ekran fiziksel olarak çözülmüş sayılmaz. Tam güncel test sonuçları ve bilinen sorunlar yayın notları/manifestte ayrı gösterilir; başarısız kabul paketi yayımlanmaz.
