# OğuzDows 2.0 · Akıncı — launcher’ı kur

> **Yayın hazırlığı:** aşağıdaki APK tam kabulü geçti; kalıcı indirme bağlantısı 2.0 taslağının bütünlük denetimi ve yayımlanmasından sonra açılır. Bu satır yayımlama tamamlanınca kaldırılır.

**Gerçek APK sürümü `2.0.0-akinci`, versionCode `20`.** Kotlin/Compose HOME, Aero/cam, altı mobil düzen, gerçek sistem Ayarları/rehberi, Telefon/SMS/Mağaza/widget ve OğuzKöprü aynı pakette. **Debug imzalı normal uygulamadır; telefon ROM’u, OTA, GSI veya ISO değildir.**

## 1. Kalıcı yayın dosyasını indir

### [OguzDows-Mobile-2.0-Akinci-debug.apk](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Mobile-2.0-Akinci-debug.apk)

[Tüm PC / Pi / APK dosyaları](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0) · [APK SHA-256](https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0/OguzDows-Mobile-2.0-Akinci-debug.apk.sha256) · [PC–telefon–ARM bağlantı rehberi](../docs/AKINCI-BAGLANTI.md)

| Dosya | Ne için? |
| --- | --- |
| **`OguzDows-Mobile-2.0-Akinci-debug.apk`** | Ana launcher, **24.434.944 bayt** |
| `OguzDows-Mobile-2.0-Akinci-tests.apk` | Instrumentation testleri; günlük uygulama değildir |
| `OguzDows-inert-install-fixture.apk` | Kurulum/widget testlerinin etkisiz örneği; elle kurmana gerek yok |
| `APK-SIGNATURE.txt`, `MOBILE-BUILD.txt`, `SHA256SUMS`, `release-manifest.json` | İmzacı özeti, gerçek kaynak SHA’sı, boyutlar/hash’ler ve test kökeni |
| `OguzDows-Web-2.0-Akinci.tar.gz` | Ayrı statik tarayıcı tasarım laboratuvarı; APK/ROM veya etkin AI sunucusu değildir |

Kaynak **`5a44de0dde676d901a32be40d631d481e213439d`**. [Tam kabul koşusu 46092350348](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348): **15/15 seçimde 24/24 native vaka + 20/20 JVM**, lint **0 hata / 47 uyarı / 1 bilgi**; iki bağımsız dört-dosya TLS makbuzu, gerçek MediaProjection/iptal/durdurma ve `apksigner` geçti. [SDK](android/evidence/sdk-5a44de0.json) · [Emülatör](android/evidence/emulator-5a44de0.json) · [Kabul](android/evidence/acceptance-5a44de0.json) · [Paket](android/evidence/package-5a44de0.json).

Release kalıcıdır; tanısal [Actions artifact’ı](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348/artifacts/15241623587) ise 14 günlük, GitHub oturumu gerektirebilen ayrı dağıtımdır. Artifact ZIP hash’i APK hash’i değildir.

## 2. İndirdiğin kopyayı doğrula

Ana APK’nın SHA-256 değeri:

```text
305015d09e57dcc18b854c3624754ed1723b2cfb2b9c3493c2b0cc6661820e82
```

APK ile ona ait `.sha256` dosyasını aynı klasöre indir:

```sh
sha256sum -c OguzDows-Mobile-2.0-Akinci-debug.apk.sha256
```

Windows PowerShell:

```powershell
Get-FileHash .\OguzDows-Mobile-2.0-Akinci-debug.apk -Algorithm SHA256
```

Değer farklıysa kurma. Hash malware taraması değildir; debug imzası üretim imzası/Play sertifikası değildir. Koşular arasında test anahtarı değişebilir: eski debug kuruluma güncelleme garantisi yoktur. İmza uyuşmazlığı için günlük telefon verilerini silme; temiz emülatör kullan.

## 3. Boş emülatöre kur ve ana ekran yap

Android Studio AVD Manager’da **Pixel 6 · API 35 · Google APIs · x86_64 · 4 GB RAM** oluştur. Bu Play Store imajı değildir. APK’nın asgari API’si 29’dur; kabul matrisi yalnız API35/x86_64’tür. Başka API/ARM/OEM’ler ayrıca sınanmalıdır.

Fiziksel telefonlarını adb’den ayır. `adb devices` başka bir `emulator-*` numarası gösterirse aşağıdaki numarayı değiştir. **QEMU çıktısı `1` değilse devam etme.**

```sh
adb devices
adb -s emulator-5554 shell getprop ro.kernel.qemu
# Çıktı 1 olmalı.
adb -s emulator-5554 install -t OguzDows-Mobile-2.0-Akinci-debug.apk
adb -s emulator-5554 shell am start -n org.oguzdows.mobile/.LauncherActivity
```

1. **Ana ekran yap** → sistem seçiminde OğuzDows’u onayla. Alternatif: Ayarlar → Uygulamalar → Varsayılan uygulamalar → Ana ekran.
2. HOME hareketi gerçek native OğuzDows’a dönmeli; ana ekran WebView değildir. Günlük araçların bir kısmı çevrimdışı paketli modüldür.
3. Telefon/SMS, HOME’dan **ayrı rollerdir**. Yalnız boş emülatörde seç; alıcı/metin/ücret için son yerel onay ayrıca gerekir. Rol seçimi arama/mesaj başlatmaz.
4. Rehber okuma/yazma ve her yeni ekran paylaşımının sistem izni ayrıdır. İptal edilen işlem yapılmış sayılmaz.
5. Çıkmak için Varsayılan uygulamalar → Ana ekran’da stok launcher’ı seç. Root, bootloader açma veya flash gerekmez.

## 4. PC / Pi / telefon bağla

Yeni **2.0 PC/Pi imajlarında OğuzKöprü kurulu gelir**; eski 1.2 imajlarına kendiliğinden eklenmez. Aynı güvenilir yerel ağda bir cihazda masa aç, diğerine daveti aktar; iki ekranda sekiz haneli kodu birebir karşılaştırıp onayla. Seçili dosyayı sürükle veya erişilebilir düğmeyi kullan; istemci gönderiminde alıcının dosya bazında kabulü gerekir.

Dosya başına 128 MiB, kuyrukta 256 MiB / 8 öğe, 2 eş ve 15 dakika. Gerçek dosya SHA-256’sı denetlenir; otomatik açma/kurma yoktur. Telefon ekranı için her başlangıçta gerçek MediaProjection izni ve foreground bildirim; PC/Pi kaynağı için doğrulanabilen kilitsiz X11. **Salt görüntüdür; ses/mikrofon/uzaktan fare-klavye/SMS/kurulum yetkisi yoktur.** [Adım adım eşleştirme ve güvenlik](../docs/AKINCI-BAGLANTI.md).

## Ne tamamlandı, ne tamamlanmadı?

- **Var:** gerçek kurulu uygulama arama/başlatma, kalıcı iki kısayol sayfası, en çok iki gerçek AppWidgetHost alanı; medya sesi, kendi pencere parlaklığı ve gerçek Ayarlar bağlantıları; gerçek sistem rehberi, açık onayla kişi ekleme ve Telefon/SMS taslakları; altı mobil düzen/duvar kâğıdı vurgu rengi; yerel, dokunmaya/bağlama tepki veren Rıfkı; native Telefon/SMS ve imzalı F-Droid.
- **Sistem yerine geçmez:** kendi immersive penceresi ve nazar kilit eşlikçisi; SystemUI/bildirim perdesi/güvenli PIN-biyometri cihaz genelinde kaldırılmaz. Üçüncü taraf uygulamalar zorla temalanmaz.
- **AI sınırı:** bulut üretken model, mikrofon/ASR/TTS ve wake-word bağlı değildir. Ücretli hizmet etkinleştirilmedi.
- **Açık performans/otomasyon sınırı:** kabul edilen koşuda ürün ANR/çökmesi yok, fakat **2205 ms HWUI ana iş parçacığı beklemesi** gözlendi. Aynı kaynaklı paralel manuel **46092349811** koşusu launcher otomasyonunda `StaleObjectException` / menü aramasında `NullPointerException` ile reddedildi; paketlenmedi. Önceki **46091903486** da launcher odak/eksik düğme nedeniyle reddedildi. Bu geçmiş saklanır; tüm koşulların kararlı olduğu veya eski ANR’ın kalıcı giderildiği iddia edilmez.
- **Fiziksel kabul yok:** gerçek SIM/operatör/acil arama, MMS/RCS, çoklu SIM/çağrı, tüm rol/izin/süreç ölümü matrisi, GMS/Integrity/bankacılık/DRM/tüm APK uyumluluğu, gerçek pil/RAM/FPS ve PC–telefon–Pi Wi-Fi matrisi açık kalır. 4–6 GB bir ürün hedefidir, ölçülmüş garanti değildir.

**Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı bu deneysel paketle değiştirme.** ROM için cihaz modeli/kod adı ve stok geri dönüş yolu bilinmeden flash hazırlanmaz.

Bu sandbox APK/tam MediaProjection JPEG’ini bağımsız indirip çalıştırmadı veya hash’lemedi; bunlar CI makbuzları ve yayının ayrı runner byte denetimiyle ayrılır. Yeni **234×519 native thumbnail** ise eksiksiz altı checks parçasından alınıp yerelde JPEG olarak doğrulandı; fiziksel telefon ekranı veya paylaşım karesi değildir. [Doğrulama/geçmiş](VERIFICATION.md).

Önceki [0.4](android/evidence/package-7244164.json), [0.3](android/evidence/package-fb6cad5.json) ve [0.2](android/evidence/package-023a89c.json) kabul kayıtları değişmez; eski APK hash’leri 2.0’a taşınmaz. Eski PC/Pi v1.x yayınları korunur. PR birleştirilmez; cihazlara flash atılmaz.
