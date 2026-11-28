# OğuzDows Mobile 0.4 · bağlı launcher’ı dene

**`0.4.0-connected` APK’sı hazır.** Kotlin + Jetpack Compose HOME, altı mobil düzen ailesi, gerçek sistem Ayarları/rehberi, tam ekran paneller, kilit eşlikçisi ve OğuzKöprü. Telefon/SMS/Mağaza/widget tabanı korunarak **15 seçimde 24/24 native vaka ve 20/20 JVM** aynı kaynakta geçti. Bu bir **debug uygulamasıdır**; telefon ROM’u, OTA, GSI veya ISO değildir.

## 1. İndir

### [0.4 APK + testler + raporlar paketini indir](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46087817657/artifacts/15240450965)

- [Başarılı derleme ve tam kabul](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46087817657) · tam kaynak **`7244164364105a00838b4a68f5815c352554a36b`**.
- Artifact: `oguzdows-mobile-emulator-46087817657`. GitHub oturumu gerekebilir. **14 gün saklanır**; kalıcı mobil Release yayımlanmadı.
- ZIP’i açıp `SHA256SUMS` bulunan `package/` klasörüne gir. Raporlar ve tam çözünürlüklü native emülatör görüntüleri de pakettedir.

| Dosya | Kullanımı |
| --- | --- |
| **`OguzDows-Mobile-0.4.0-connected-debug.apk`** | Kurulacak ana launcher; **24.418.460 bayt** |
| `OguzDows-Mobile-0.4.0-connected-tests.apk` | Otomatik instrumentation testleri; günlük uygulama değil |
| `OguzDows-inert-install-fixture.apk` | Kurulum/widget testlerinin etkisiz örneği; elle kurmana gerek yok |
| `SHA256SUMS`, `APK-SIGNATURE.txt`, `BUILD.txt` | Hash’ler, CI imza denetimi ve APK’nın tam kaynak commit’i |

GitHub CLI ile:

```sh
gh run download 46087817657 --repo PeraPlusbirPasha/OguzDows \
  --name oguzdows-mobile-emulator-46087817657 --dir oguzdows-mobile-0.4
```

**Bu çalışma alanındaki sınır:** CI paketi hazırlayıp yükledi, ayrı `acceptance.py` kapısı ve `apksigner verify` geçti. Sandbox’ın artifact/iş-logu depolama yönlendirmesi ise `EOF` verdi; **APK ve yeni tam görseller burada açılamadı, bağımsız yerel APK hash/imza doğrulaması yapılamadı**. Hash/boyut CI kaydı, ZIP digest’i GitHub API gözlemidir. [Paket kökeni](android/evidence/package-7244164.json). İndirdiğin kendi kopyanı doğrula.

## 2. Doğrula

Ana APK’nın beklenen SHA-256 değeri:

```text
7213f4a94782d8a01c96af9d4aef0ab2e493cb80df4edc8b002c559b54cbe95d
```

`SHA256SUMS` bulunan klasörde Linux/WSL:

```sh
sha256sum -c SHA256SUMS
```

Windows PowerShell:

```powershell
Get-FileHash .\OguzDows-Mobile-0.4.0-connected-debug.apk -Algorithm SHA256
```

Değer farklıysa kurma. İmza **debug imzasıdır**, üretim imzası veya malware taraması değildir. Koşuların test anahtarları değişebilir; eski debug kuruluma güncelleme garantisi yoktur. İmza uyuşmazlığını aşmak için günlük telefon verilerini silme; temiz bir emülatör kullan.

## 3. Boş emülatöre kur ve ana ekran yap

Android Studio AVD Manager’da **Pixel 6 · API 35 · Google APIs · x86_64 · 4 GB RAM** oluştur ve başlat. Doğrulanan konuk budur; Play Store imajı değildir. ARM konuk, başka API ve OEM’ler ayrıca sınanmalıdır.

Fiziksel telefonlarını adb’den ayır. Komutlar yalnız `emulator-5554` içindir; `adb devices` başka `emulator-*` numarası gösterirse onu kullan. **QEMU çıktısı `1` değilse devam etme.**

```sh
adb devices
adb -s emulator-5554 shell getprop ro.kernel.qemu
# Çıktı 1 olmalı.
adb -s emulator-5554 install -t OguzDows-Mobile-0.4.0-connected-debug.apk
adb -s emulator-5554 shell am start -n org.oguzdows.mobile/.LauncherActivity
```

1. **Ana ekran yap** → sistem seçiminde OğuzDows’u onayla. Alternatif: sistem **Ayarlar → Uygulamalar → Varsayılan uygulamalar → Ana ekran**.
2. **Home** hareketi native OğuzDows’a dönmeli. Ana ekran WebView değildir; günlük araçların bir kısmı çevrimdışı paketlenmiş modül arayüzüdür.
3. Telefon ve SMS, HOME’dan **ayrı rollerdir**. Yalnız boş emülatörde ilgili rol/izin düğmelerini kullan. Alıcı/metin ve ücretli işlem son onayı ayrıca gerekir; rol seçmek arama/mesaj başlatmaz.
4. Rehber, yeni kişi ve ekran paylaşımının izinleri de ayrıdır. Sistem sorusunu okuyup açıkça seç; izin verilmediyse başarı taklidi yapılmaz. Ekran paylaşımı her başlangıçta yeniden sistem onayı ister.

Bootloader açma, flash veya root gerekmez. Çıkmak için **Varsayılan uygulamalar → Ana ekran** bölümünde stok launcher’ı seçebilirsin; bu seçim verileri silmez.

## 4. Neleri dene?

- **Altı mobil masaüstü ailesi:** OğuzDows, Plasma, GNOME/Ubuntu, Xfce, Windows 11 esintisi ve macOS iskelesi. Seçim/kalıcılık gerçek HOME yeniden yaratma testini geçti; bu işletim sistemlerini telefonda çalıştırmak değildir.
- **Uygulamalar/masaüstün/widget:** gerçek kurulu uygulamayı Türkçe adı/paket adıyla bul ve aç. İki kısayol sayfası, varsayılan 12/en çok 16 giriş, açık ekle/kaldır/öne-sona taşı; dört duvar kâğıdı. Üçüncü sayfada gerçek AppWidgetHost ve sistem bağlama/yapılandırma, en çok iki sabit boyutlu alan.
- **Tam ekran yüzeyler:** aşağı hareketle denetim, yukarı hareketle uygulama çekmecesi. Gerçek medya sesi, yalnız OğuzDows pencere parlaklığı; **telefonun kendi Ayarlar ekranı** ve ilgili sistem panelleri. Başka üreticinin uygulamaları zorla temalanmaz.
- **Sistem rehberi:** okuma izniyle gerçek kişileri gör. Yeni yerel kişi için ayrı yazma izni ve son kayıt onayı; iptal kişi eklemez. Telefon/SMS seçimi taslaktır, kendiliğinden arama/gönderim değildir. Web laboratuvarının elle oluşturulan kişi listesi bundan ayrıdır.
- **Nazar kilit eşlikçisi:** markalı kilit/karşılama yüzeyi. **Sistem PIN/parmak izi kilidinin yerine geçmez; sistem bildirim perdesini veya keyguard’ı cihaz genelinde devre dışı bırakmaz.** Bunlar cihaz özel ROM/SystemUI çalışmasıdır.
- **OğuzKöprü:** telefonda Dosyalar/OğuzKöprü, güncel dalın PC/ARM kaynaklarında `oguzdows-bridge`. Aynı yerel ağ, iki ekranda kod karşılaştırma, karşı taraf/dosya onayı ve pinned TLS. Seçili dosyayı masaya bırak; alım hash’i doğrulanır, otomatik açılmaz/çalıştırılmaz. Her başlatmada sistem izniyle salt görüntü, foreground bildirim ve durdurma; ses/uzaktan dokunma yoktur. [Adım adım eşleştirme, süre/boyut sınırları ve X11/Wayland koşulları](CONNECTED.md).
- **Rıfkı:** sevme/baş eğme, sağ/sol konum, saat/pil/şarj/görüşme tepkisi ve açıkça onaylanan tipli UI önerileri. **Şimdilik yerel kural tabanlıdır; konuşan bulut AI/ASR/TTS/mikrofon/wake-word bağlı değil.**
- **Telefon/SMS/Mağaza:** gerçek Telecom/SmsManager/sağlayıcı ve imzalı F-Droid korunur. Kabulte 5.057 uygulama / 5.016 uygun paket gözlendi; tüm APK’lerin çalıştığı anlamına gelmez. Canlı Aegis incelemesi kurmadan iptal; ayrı etkisiz fixture ise gerçek sistem kurulumu ile sınandı. İncelemede Vazgeç veya diyalogda sistem Geri, çağırana döner; son yükleyici onayı atlanmaz.

## Kabul, görüntüler ve açık sınırlar

**Geçen:** 24 native vaka / 15 seçim, 20 JVM, iki bağımsız dört-dosya TLS makbuzu, taze MediaProjection izni/iptal/FGS/gerçek JPEG/durdurma ve paket/imza. Lint **0 hata / 47 uyarı / 1 bilgi**. [Ayrıntılı sonuçlar ve başarısız geçmiş](VERIFICATION.md) · [tekrar üretim](android/README.md).

**Görseller:** güncel tam native PNG’ler ve **11.662 bayt gerçek fixture paylaşım JPEG’i** artifact’tadır. Yeni küçük native görüntünün altı checks parçasından yalnız dördü kotaya sığdı; eksik görüntü oluşturulmadı. README’deki küçük native JPEG açıkça **tarihsel 0.3**’tür, 0.4 görüntüsü değildir. Web ekranları ayrıca web önizlemesi olarak etiketlidir.

**Performans:** bu başarılı koşuda Android ürün ANR/çökmesi görülmedi, fakat **2060 ms HWUI ana iş parçacığı beklemesi** örneklendi. Önceki aralıklı ANR’ın kalıcı giderildiği veya fiziksel telefon akıcılığı/pil/RAM/FPS kabulü iddia edilmez.

**Henüz değil:** fiziksel PC/telefon/ARM drag-drop/yansıtma matrisi; gerçek SIM/operatör/acil çağrı, MMS/RCS, çoklu SIM/çağrı ve bütün rol/izin/lock/süreç ölümü matrisi; GMS/Play lisansı/sertifikası, Integrity/banka/DRM/tüm APK uyumluluğu; üretim imzası ve cihaz işletim sistemi imajı. Salt görüntü yansıtması uzaktan kontrol değildir.

**Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı bu deneysel paketle değiştirme.** ROM için tam marka/model/kod adı/yazılım ve stok geri dönüş yolu incelenmeden flash komutu hazırlanmaz. GNOME Software/Flatpak, APK/GMS motoru değildir.

Önceki kabul edilmiş [0.3 paketi](android/evidence/package-fb6cad5.json) ve [0.2 paketi](android/evidence/package-023a89c.json) tarihsel olarak korunur; buradaki indirme **0.4 bağlı launcher** içindir. Yayımlanmış PC/Pi v1.2 imajları değiştirilmedi/yeniden yayımlanmadı; PR birleştirilmedi, mobil Release açılmadı.
