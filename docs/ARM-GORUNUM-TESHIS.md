# ARM: tema ve duvar kâğıdı teşhisi

## Durum ve yayın sınırı

Düzeltme, ayrı **[2.0 Akıncı · ARM düzeltmesi 1](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0-arm1)**
armhf/arm64 imajlarında yayımlandı; imaj kaynağı **`c5063ee8b558cb6c8af8301143cf3ce02106e2aa`**.
[Yeni ARM yayın kaydı](releases/v2.0-arm1-release.json), gerçek indirme
boyutlarını, SHA-256’ları, kaynak koşusunu ve bağımsız denetimi bağlar.
**Mevcut SD/USB kartlar otomatik güncellenmez; fiziksel Pi düzelmiş sayılmaz.**

Özgün **v2.0 / `5a44de0dde676d901a32be40d631d481e213439d`** armhf/arm64
dosyaları değiştirilmedi; bu düzeltmeler o eski dosyalarda yoktur.
Etiket, SHA-256 listesi ve [özgün 2.0 yayın kaydı](releases/v2.0-release.json)
korunur. PC ISO ve mobil APK da özgün 2.0’da kalır.

### Doğrulanan duvar kâğıdı hatası

Xfce'nin `xfce4-desktop` kanalında eski HDMI/monitör kayıtları kalabilir.
Önceki uygulama, **herhangi bir `last-image` anahtarı bulunca** yalnız bu
kayıtlara yazıyordu. Etkin monitörün `last-image` değeri henüz yoksa, eski
bağlantıya yazılan değer geri okunabiliyor ve karşılayıcı “uygulandı” diyordu;
oysa ekrandaki `xfdesktop` görüntüsü değişmiyordu.

Bu durum Bookworm ve Trixie üzerinde **iki ayrı yerel ARM64 Xfce testinde**
yeniden üretildi. Normal açık/koyu geçişi ve normal galeri seçimi bu testlerde
çalışıyordu; eski monitör senaryosu ekrandaki piksel denetiminde başarısızdı.
Bu sonuç, bildirilen bütün ARM/tema sorunlarının tek nedeninin bu olduğunu
göstermez. Cihaz modeli, kullanılan imaj ve oturum bilgisi ayrıca gerekir.

### Kaynakta değişenler

- Saklı kayıtlar tek başına etkin monitör kanıtı sayılmaz. RandR üzerinden
  **şu anda görüntü veren çıkışlar** her uygulamada hedeflere eklenir.
- Etkin monitörde sadece `image-style`/renk ayarı bulunması da ele alınır.
  Önceden kayıtlı sayısal GDK monitör kimlikleri korunur.
- Gerçek X ekranı numarası ve Xfwm çalışma alanı sayısı kullanılır;
  yalnız `screen0` ve ilk dört çalışma alanı varsayılmaz.
- RandR aracı/yanıtı yoksa kısa ömürlü, salt okunur GDK yardımcısı kendi X11
  bağlantısından monitörleri sorgular. UI işçisinden GTK'nın paylaşılan ekranına
  dokunulmaz. **GPU hızlandırması veya çalışan bir kompozitör şart değildir.**
- Her iki tespit yolu da başarısızsa `monitor0` uydurulmaz ve eski bağlantıya
  yazılmış bir değer başarı diye sunulmaz. Açık hata döner.
- Sınırlı hedef sayısı, tipli yazma/geri okuma, seçim kaydının en son yazılması
  ve kısmi hata durumunda tam işlem-öncesi değerlere karşılaştırmalı geri alma
  korunur. Kişisel ayar dizini silinmez, kilit zorla kaldırılmaz.
- Yeni Pi yapılandırmaları, görünüm arka uçları ve karşılayıcı dahil altı ek
  kaynak dosyasının gerçek baytlarını imaj sözleşmesinde hash ile bağlar.
  Doğru adlı ama eski `wallpapers.py` dosyası export denetiminden geçemez.

## Testin kanıtladığı ve kanıtlamadığı

`tests/smoke-appearance.py`, özel Xvfb ekranı ve D-Bus üzerinde, kopyalanmış
ürün iskeletiyle **root olmayan kullanıcıda gerçek Karşılayıcı düğmelerini**
tetikler. Native ayar arka ucu, kurulum/meşgul kapısı, Xfconf, GTK3/XSettings,
Xfwm tema üretimi ve `xfdesktop` sahte değildir.

- Altı tarzın tema/yerleşim **yapılandırması** ve açık/koyu GTK3 tema yüklemesi
  denetlenir. Bu özel test paneli yeniden başlatmaz; görünür Dock/yerel panel
  eklentisinin davranış testi değildir.
- İki sentetik düz renk görsel kullanılır. Seçim JSON'u veya xfconf geri okuması
  tek başına yeterli sayılmaz: gerçek masaüstünden alınan RGB pikselleri
  kırmızı `(160, 30, 40)` ve mavi `(30, 60, 160)` değerleriyle karşılaştırılır.
- Eski monitör anahtarlarıyla aynı piksel kontrolü tekrarlanır.
- RandR başarısızlığı özellikle enjekte edilerek **gerçek GDK yardımcısı ve
  gerçek masaüstü pikselleri** ayrıca sınanır. Bu, fiziksel bir eski X sunucuda
  RandR uzantısının gerçekten bulunmadığına ilişkin donanım kanıtı değildir.
- 512 MiB kaynak politikası bir fixture'dır; runner RAM'i 512 MiB değildir.
  Bu testten Pi Zero performansı, GPU/HDMI/KMS, LightDM/PAM, SD veya fiziksel
  açılış başarısı çıkarılamaz. ARM64 sonucu ARMv6 GUI sonucu diye sunulmaz.
- `scripts/smoke-portable.sh` içindeki 32-bit görünüm testleri açıkça taklit
  edilmiş ayar arka uçlarıyla doğrulama/geri alma testleridir; ARM masaüstü
  pikselleri veya gerçek kart testi değildir.

Yeni kaynak için kabul koşulu, her iki ARM64 tabanda testin gerçekten geçmesi
ve kök birim testlerinin yeşil kalmasıdır. Çalıştırma kimlikleri ve JSON
sonuçları [görünüm test kaydında](evidence/arm-appearance.json) tutulur;
önceki sürümün kabul kayıtları yeniden yazılmaz.

## Yeni imajların ayrı hedef görünüm kabulü

[İki mimarili gerçek derleme 46142709227](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46142709227)
ve **[bağımsız yeniden indirme / iç imaj denetimi 46149729927](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46149729927)**
başarıyla tamamlandı. Temiz armhf ve arm64 imajlarında **75 birebir kaynak/varlık
hash’i**, minimum CPU/ABI ve normal kullanıcı tam Xfce kapısı zorunludur.
Kurulu üretim kodu, taklit edilmemiş ayar arka ucu ve gerçek kaynak politikasıyla
açık/koyu GTK3’ü yeniden yükler; iki gerçek paketlenmiş duvar kâğıdının seçim
kaydı/xfconf geri okumasını ve örtülmemiş kararlı masaüstü piksellerinin değişmesini
sınar. Aktarım ve ayrı salt-okunur runner bu raporu imajın gömülü raporuyla ve
beklenen kaynak sözleşmesiyle karşılaştırdı.

Bu hedef kullanıcı-QEMU + host Xvfb testidir. Yukarıdaki native ARM64
**Welcome düğmeleri / altı profil** testinden ayrı tutulur; GTK4/portal,
fiziksel kernel/firmware/LightDM/PAM/GPU/HDMI/SD, tüm uygulamalar veya Pi
performansı kabulü değildir. **İlk Zero/Zero W siyah ekran bildirimi açıktır.**

## Cihazında kolay ve güvenli teşhis

İşlemleri **açık grafik masaüstündeki normal kullanıcı terminalinde**, `sudo`
kullanmadan yap. SSH/TTY, root veya başka bir kullanıcının ortamı aynı oturum
sayılmaz. Önce cihaz/VM modelini ve indirdiğin imajın dosya adını belirt.
`uname -m` tek başına kullanıcı alanının 32/64-bit olduğunu kanıtlamaz;
64-bit çekirdek üzerinde armhf kullanıcı alanı olabilir.

### 1. Salt okunur durum

```sh
printf 'Mimari: '; dpkg --print-architecture
printf 'Masaüstü: %s · Oturum: %s\n' "$XDG_CURRENT_DESKTOP" "$XDG_SESSION_TYPE"
oguzdows-desktop --status
```

Pi modelini bilmiyorsan, mevcut dosyayı salt okuyabilirsin:

```sh
if [ -r /proc/device-tree/model ]; then
    tr -d '\000' < /proc/device-tree/model
    printf '\n'
fi
```

Bunlar paket kurmaz, ağ isteği yapmaz, ayar değiştirmez veya raporu bir yere
göndermez. Paylaşmadan önce çıktıyı gözden geçir; parola, tam ortam dökümü,
SSH anahtarı, D-Bus adresi veya kişisel dosyalar istenmez.

### 2. Temayı doğrudan aynı arka uçtan dene

Aşağıdaki komut **salt okunur değildir**: aynı kullanıcı için koyu temayı
uygulamayı dener. Hata oluşursa gerçek hata metni terminalde görünür.

```sh
oguzdows-desktop --apply --appearance dark
```

İstersen daha sonra aynı yoldan `--appearance light` ile açık temayı seç.
Sonuç hata verirse metni aynen, cihaz/imaj/oturum bilgileriyle bildir.
“Başarılı” yanıtına rağmen görünüm değişmezse bunu da ayrıca belirt;
config dosyasına yazılmış olması ekrandaki sonuç için tek başına kanıt değildir.

### 3. Karşılayıcıdaki seçim ile uygulama farkı

- **Tarz kartı** önce seçer; ardından **“Seçili tarzı uygula”** gerekir.
- Yeni panel düzenini o anda yüklemek için **“Uygularken panelleri de şimdi
  yenile”** seçeneği açık olmalıdır. Bu onay yoksa panel bir sonraki girişte
  yüklenir; tema ve duvar kâğıdı bundan ayrı denetlenir.
- Açık/koyu düğmesi ve galeri görseli doğrudan işlemi başlatır. Alttaki durum
  satırında “uygulanamadı/değiştirilemedi” varsa bu metin teşhis için önemlidir.
- `mini`/`light`, düşük RAM veya eski GPU ağır blur/yay efektlerini kapatabilir;
  **temanın ve statik duvar kâğıdının çalışmamasının normal açıklaması değildir.**

Teşhis için `.config` silme, `chmod -R 777`, zorla kilit silme, rastgele
`chown -R`, bütün xfconf kanallarını sıfırlama veya oturumu root başlatma
önerilmez. Önce gerçek hata saptanmalı, sonra cihaza uygun yeni imaj/ayrı
güncelleme yolu değerlendirilmelidir. Bu işlem kendiliğinden cihaz yazmaz.
