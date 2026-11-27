# OğuzDows Mobile 0.2.0 · emülatör kurulumu

**APK hazır; API 35 emülatör kabulü 12/12 geçti.** Bu, OğuzDows içinden yerel Telefon/SMS ve imzalı Mağaza akışını kullanan **debug test uygulamasıdır**. Telefon ROM’u, OTA, GSI veya ISO değildir.

## 1. Paketi indir

### [APK + testler + raporlar paketini indir](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728/artifacts/15222979423)

- [Başarılı derleme ve kabul koşusu](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46048445728) · kaynak **`023a89c9f22bdcd27eabecf8437b05addcab03e9`**.
- Artifact: `oguzdows-mobile-emulator-46048445728`. GitHub oturumu gerekebilir. **Saklama süresi 14 gün**; kalıcı mobil Release yayımlanmadı.
- ZIP’i açıp `SHA256SUMS` bulunan klasöre gir. Genellikle `test-results/mobile/package/` altındadır. Raporlar/ekran görüntüleri de aynı artifact’tadır.

| Dosya | Kullanımı |
| --- | --- |
| **`OguzDows-Mobile-0.2.0-emulator-debug.apk`** | Denemek için kurulacak ana uygulama; **6.993.130 bayt** |
| `OguzDows-Mobile-0.2.0-emulator-tests.apk` | Otomatik instrumentation testleri; günlük kullanım uygulaması değil |
| `OguzDows-inert-install-fixture.apk` | Kurulum testinin etkisiz örnek uygulaması; ayrıca kurmana gerek yok |
| `SHA256SUMS`, `APK-SIGNATURE.txt`, `BUILD.txt` | Hash’ler, CI imza denetimi ve tam kaynak commit’i |

İstersen kendi bilgisayarında GitHub CLI ile indirebilirsin:

```sh
gh run download 46048445728 --repo PeraPlusbirPasha/OguzDows \
  --name oguzdows-mobile-emulator-46048445728 --dir oguzdows-mobile-0.2.0
```

**Bu çalışma alanındaki indirme sınırı:** CI paketi hazırladı ve artifact’a yükledi; ancak sandbox, GitHub’ın artifact depolama alanına yönlenen indirmeye erişemedi (`EOF`). APK bu çalışma alanına kopyalanamadı ve burada bağımsız hash/imza doğrulaması yapılmadı. Aşağıdaki hash, başarılı CI derleme kaydıdır; ZIP’in digest’i ve paket kökeni [kanıt kaydında](android/evidence/package-023a89c.json). İndirdikten sonra kendi kopyanı doğrula.

## 2. İndirilen kopyayı doğrula

Ana APK için beklenen SHA-256:

```text
175c471a87d9c6020d29a8a8cbca7a3903eb05e939c0c5fd32c26790917c2f04
```

`SHA256SUMS` bulunan klasörde Linux/WSL:

```sh
sha256sum -c SHA256SUMS
```

Windows PowerShell’de ana dosya için:

```powershell
Get-FileHash .\OguzDows-Mobile-0.2.0-emulator-debug.apk -Algorithm SHA256
```

Sonucu yukarıdaki değerle karşılaştır. Farklıysa kurma. CI’de `apksigner verify --verbose --print-certs` adımı başarılıdır; bu bir **debug imzasıdır**, üretim imzası veya malware taraması değildir. Koşular arasında debug anahtarı değişebilir; eski test kurulumuna güncelleme garantisi yoktur.

## 3. Yalnız boş bir emülatöre kur

Android Studio AVD Manager’da **Pixel 6 · API 35 · Google APIs · x86_64** oluştur ve başlat. Doğrulanan imaj budur; Play Store imajı değildir. İlk kabul, x86_64 konuk/KVM ortamındadır; ARM konuk, başka API ve OEM’ler ayrıca sınanmalıdır.

Fiziksel telefonlarını adb’den ayır. Aşağıdaki komutlar yalnız `emulator-5554` içindir; `adb devices` başka bir `emulator-*` numarası gösterirse onu kullan. **QEMU çıktısı `1` değilse devam etme.**

```sh
adb devices
adb -s emulator-5554 shell getprop ro.kernel.qemu
# Yukarıdaki çıktı 1 olmalı.
adb -s emulator-5554 install -t OguzDows-Mobile-0.2.0-emulator-debug.apk
adb -s emulator-5554 shell am start -n org.oguzdows.mobile/.HomeActivity
```

Uygulama normal kullanıcı yetkileriyle çalışır; bootloader açma, flash veya root gerekmez. Yalnız emülatörde, uygulamanın Telefon/SMS rolü ve gerekli izin düğmelerini kullan. Rol seçimi ücretli işlem başlatmaz; çağrı/SMS için ayrıca alıcı ve işlem onayı vardır. Ana ekran rolü isteğe bağlıdır.

- **Telefon:** OğuzDows içinde tuş takımı ve kendi görüşme ekranı. Giden sanal arama Telecom’a ulaşır; gelen sanal aramada yanıtla/sustur/aç/bitir doğrulandı.
- **Mesajlar:** gelen SMS gerçek sistem sağlayıcısı üzerinden listelenir. Giden SMS önce `queued`, gerçek sanal radyo geri bildirimi gelince gönderildi olur. **Operatör teslim raporu test edilmedi**; teslim edildi varsayılmaz.
- **Mağaza:** canlı kaynağı açıkça eşitle. Doğrulanan koşuda **5.057 uygulama / 5.016 API-ABI uygun paket** görüldü; bu sayı zamanla değişir ve her uygulamanın çalıştığı anlamına gelmez. Aegis indirme/hash/inceleme **kurmadan iptal** edildi. Ayrı etkisiz test APK’sı gerçek sistem yükleyicisi onayıyla kuruldu.
- **Denetim:** medya sesi sistem kanalına, parlaklık OğuzDows penceresine uygulanır. Üç sayfa, 20 uygulama girişi, 24 seçki simgesi, nazar güç simgesi ve Rıfkı korunur.

Tam otomatik tekrar üretim ve sanal modem fixture’ları için [yerel modül kılavuzu](android/README.md). Test sürücüsünü günlük telefonunda çalıştırma; yalnız harcanabilir QEMU hedefini kabul eder.

## 4. Kabul edilen ve açık kalan sınır

**Geçen:** 12 gerçek emülatör testi, 6 Java testi, 13 kaynak sözleşmesi; yerel web testleri 31/31 ve tarayıcı raporu 33/33. Lint 0 hata / **37 uyarı**. [Ayrıntılı kanıt](VERIFICATION.md).

**Henüz değil:** fiziksel SIM/operatör/acil çağrı, MMS/RCS, çoklu SIM/çağrı ve tüm izin/lock-screen/süreç ölümü matrisi, GMS/Play lisansı/sertifikası, Play Integrity/banka/DRM veya bütün APK’lerle uyumluluk; üretim imzası ve cihaz işletim sistemi imajı. Rıfkı yerel rehberdir, mikrofon ve canlı üretken model kapalıdır. GNOME Software/Flatpak Android APK/GMS motoru yerine geçmez.

**Günlük fiziksel telefonunda varsayılan Telefon/SMS uygulamanı bu deneysel paketle değiştirme.** İlk ROM adımı için telefonun **tam marka/modeli, mümkünse kod adı ve Ayarlar → Telefon hakkında bölümündeki yazılım sürümü** gerekir. Bootloader bilinmiyorsa şimdilik işlem yapma; destek ve stok geri dönüş yolu incelenmeden flash komutu/imajı hazırlanmaz.

PC/Pi v1.2 imajları değiştirilmedi. PR birleştirilmedi, mobil Release veya fiziksel flash yapılmadı.
