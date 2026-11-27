# Yerel başlangıç iskeleti · OğuzDows Mobile

**Durum: kaynak yazıldı; Android SDK ile derlenmedi, APK üretilmedi, emülatör/fiziksel telefon testi yapılmadı.** Bu tam işletim sistemi veya web tasarımının eksiksiz native portu değildir. PC/Pi ürün sürümü 1.2 ile aynı yayın numarası olarak sunulmaz.

## Kaynaktaki yollar

- `HomeActivity`: normal HOME/LAUNCHER adayı; varsayılan ana ekranı yalnız sistem ayarından kullanıcı seçer. Gerçek başlatılabilir uygulamaları sorgulama/açma (en çok 250), basit açık/koyu başlatıcı ve Defter.
- Günlük sistem akışları: numara doğrulayan `ACTION_DIAL` (arama onayı sistemde), alıcı/2000 karakter taslak ile `ACTION_SENDTO` / `smsto:` (gönderim sistemde); kişiler/takvim/kamera/müzik/galeri/tarayıcı için standart uygulama intent’leri. Çağrı veya SMS okuma/gönderme izni yoktur. Uygun uygulama bulunmazsa hata gösterilir; başarı uydurulmaz.
- Ses/Wi-Fi için `Settings.Panel.ACTION_VOLUME` / `ACTION_WIFI`, Bluetooth/ekran ayarlarına açık geçiş. Genel ayarları arka planda değiştirmez; `WRITE_SETTINGS` veya kök yetki istemez. Webdeki kaydırmalı panelin tam native görsel portu değildir.
- Nazar vektör simgesi ve sistemden gerçek pil okuma. Normal uygulama cihazı kapatamaz/yeniden başlatamaz; pil ayarına devreder. SystemUI/ROM güç katmanı ayrı iştir.
- APK: SAF belge seçimi, yalnız `content:` URI, `.apk`, en çok 32 MiB özel kopya, SHA-256, paket/minSdk/ABI/izin/sertifika özeti; açık inceleme sonrası aynı özel kopyayı FileProvider üzerinden sistem yükleyicisine aktarır. **Sessiz kurulum veya başarı simülasyonu yoktur.**
- Kaynak izni kapalıysa sistemin “bu kaynaktan” sayfası açılır; dönüşte otomatik kurulum yapılmaz. Kullanıcı dosyayı tekrar seçip inceler. XAPK/APKS/split paketler yoktur. Sistem yükleyicisi son imza/politika/onay denetimini yapar; inceleme tek başına doğrulanmış imza veya malware taraması değildir.
- Google web bağlantıları; kurulu Google uygulamaları normal listeden açılır. GMS/Play APK’leri, kapalı firmware veya Google hesabı toplama yoktur.
- `RifkiVoiceService` / `RifkiSessionService`: sistem imza izniyle korunan, açık `RoleManager.ROLE_ASSISTANT` seçimi için metin oturumu. Diğer yardımcılar silinmez. Varsayılan seçilmedikçe sistemin bu rolü üstlenmesi istenmez.
- AOSP yardımcı metadata’sının zorunlu tanıma adresi için `RifkiRecognitionService` bulunur; **ses açmaz**, yalnız kullanılamıyor/izin yok hatası döndürür. Üç servis de mevcut `BIND_VOICE_INTERACTION` imza izniyle sistem bağlantısına kısıtlıdır. Sesli tanıma tamamlandı sayılmaz.
- Rıfkı yerel rehberi kural tabanlıdır, genel AI değildir. Native üretken model köprüsü **henüz bağlanmadı**. Webdeki opsiyonel API desteği native işlev olarak sunulmaz.
- Mikrofon/hotword, internet, kişi, konum, SMS, tüm dosyalar veya ekran yakalama izni yoktur. Yardımcı ekran bağlamı ve screenshot verisi kapatılır. Servis platform tarafından yardımcı rolü seçildiğinde bağlı tutulabilir; sürekli inference/dinleme yoktur.

## Derleme ön koşulları

Kendi geliştirme ortamında **JDK 17**, Android SDK Platform 35 ve Gradle 8.9 kullanın. API 35 bu başlangıç projesinin sabit derleme hedefidir; en güncel platform veya güvenlik yaması iddiası değildir. Minimum API 29’dur. Gerçek ROM temeli, cihazın desteklenen/güvenlik bakımı yapılan dalına göre ayrıca seçilmelidir.

```sh
cd mobile/android
# Android Studio ile bu dizini açabilir veya kurulu Gradle 8.9 ile:
gradle :app:assembleDebug
```

SDK ve Google Maven erişimi gerekir. Bu depoya Gradle wrapper JAR’ı, SDK, imzalama anahtarı veya APK ikilisi eklenmedi; henüz var olmayan `./gradlew` komutu kullanılmaz. `local.properties` / `ANDROID_HOME` yalnız kendi ortamında ayarlanır. Başarılı komut çıktısı gözlenmeden APK hazır diye raporlanmamalıdır.

Build başarılı olduktan sonra önce emülatörde, kullanıcının seçimiyle normal uygulama olarak deneyin. **Bootloader açmak, ROM flaşlamak veya root vermek gerekmez ve bu aşamanın parçası değildir.** HOME ve varsayılan yardımcı rollerini sistemde kullanıcı seçmeli; desteklemediklerinde hata/kurtarma akışı test edilmelidir.

## Tamamlanması gerekenler

- SDK derlemesi, lint, test APK’sı, emülatör ve gerçek OEM rol/intent testleri.
- Activity/servis yaşam döngüsü, büyük font/ekran okuyucu, yavaş/bozuk belge sağlayıcıları, I/O iptali, ANR ve süreç ölümü.
- Kaynak-kopya/hash/API/ABI/signature/update/downgrade/iptal/başarısız yükleme testleri; 32 MiB sınırının üretim tasarımı ve split session desteği.
- Webdeki 10 araç ve geri kalan 6 yerel işlev, Mağaza/Haber/koleksiyon, görsel tasarım ve erişilebilirliğin gerçek native portu.
- İmzalı/şifreli veri dışa aktarımı gerekiyorsa ayrı tasarım; mevcut notlar uygulama alanında düz veridir, şifreli kasa değildir.
- Varsayılan yardımcı rolünde sistem bağlamının kapalı kaldığının ve mikrofon çalışmadığının gerçek cihaz kanıtı.
- Native Rıfkı için açık sağlayıcı/izin/saklama politikası; kullanıcı kimlik doğrulamalı sunucu veya cihaz özel yerel model.

Kaynak sözleşmesi testleri [`../tests/test_native_contract.py`](../tests/test_native_contract.py) içindedir; bunlar yalnız statik izin/path/rol/sınır kontrolleridir, derleme veya çalışma kanıtı değildir. [Ürün tasarımı ve ROM kabul kapıları →](../DESIGN.md)
