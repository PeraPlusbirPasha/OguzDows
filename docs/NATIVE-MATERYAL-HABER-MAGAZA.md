# Native materyal, Haber ve Mağaza · geliştirme kaynağı

Bu çalışma **GTK3/C + kısa ömürlü Python işçileri + Xfce/Picom** mimarisini korur. GNOME/Mutter ve Plasma/KWin kendi kabuklarını, widget/panel düzenlerini ve mevcut geri alma sözleşmesini korur. Web maketi, Electron, webview, yeni daemon veya arka planda otomatik indirme yoktur. Yayımlanmış v1.1 dosyaları değiştirilmez. Yeni geliştirme ISO’larının kesin kaynak ve test sonucu PR/Actions kaydından takip edilmelidir; eski ISO’ya bu değişiklikler mal edilmez.

## Kısa teknik tanı

- Haber ve Mağaza ortak `modern.css` katmanını kullanmıyordu. Rehber/merkez ile ayrı sabit CSS, ağır dikdörtgen uygulama kartları ve farklı boşluklar tek ürün hissini bozuyordu.
- Rehber, Haber, Mağaza ve monitör `GtkStack` geçişlerini koşulsuz `NONE` yapıyordu. Başlat hover kodu her karede ikonun piksel boyutunu değiştiriyor, görüntüyle beraber yerleşim hesabını da tetikliyordu.
- RSS HTTPS işleyicisi `HTTPSHandler._check_hostname` alanını kullanıyordu. Bu alan CPython 3.12/3.13’te yoktur; Trixie/Python 3.13’te gerçek bağlantı yolu `AttributeError` verebilirdi. SSLContext zaten hostname ve CA doğrulamasını yapar. Eski parametre kaldırıldı; DNS sabitleme, SSRF/özel ağ, yönlendirme, boyut ve TLS sınırları gevşetilmedi.
- Haber ilk açılışta bilerek HTTP yapmıyordu fakat boş önbelleğe kullanılabilir içerik sunmuyordu. Kategori ve hata sonrası belirgin mod ayrımı eksikti.
- Mağaza kurulumu/güncellemeyi planlıyordu; kaldırma yolu yoktu. Yerel aday sürümler ve güncellenebilir durum keşifte görünmüyordu. Kısa bir metadata sorgusu bile bütün içerik alanını kilitliyordu.

Bunlar koddan doğrulanan nedenlerdir. Fiziksel makinedeki tüm kasmanın kaynağı veya belirli GPU’da FPS kazancı ölçülmüş değildir.

## Modüller

| Katman | Tam uygulama |
|---|---|
| Ortak native tema | `system/usr/share/oguzdows/ui/modern.css` |
| C tema / kaynak / materyal / sayfa geçişi | `native/ui.c`, `native/ui.h` |
| Python GTK eşdeğeri; olay tabanlı tercih yenileme | `system/usr/lib/oguzdows/ui_theme.py` |
| Haber arayüzü | `native/news.c` |
| RSS/Atom, güvenli aktarım, önbellek ve örnek akış | `system/usr/lib/oguzdows/news_core.py`, `news_service.py` |
| Yayıncı manifesti | `system/usr/share/oguzdows/news-sources.json` |
| Mağaza arayüzü | `native/store.c` |
| Katalog, yerel sürümler ve işlemler | `app_catalog.py`, `store_service.py` (`system/usr/lib/oguzdows/`) |
| Dar APT planı / kaldırma doğrulaması | `system/usr/lib/oguzdows/maintenance.py`, `system/usr/local/sbin/oguzdows-maintenance` |
| Pencere ölçek/opacity animasyonu | Mevcut `system/usr/share/oguzdows/compositor/{motion,full,snap,full-snap}.conf`; Picom 12+ |

### Materyal ve hareket

- Tek tip ölçü ailesi, 1px alpha kenarlar, küçük köşe yarıçapları, sakin satırlar, tek editoryal öne çıkan alan. Kart başına çoklu gölge/blur yoktur. Başlık, menü, arama, onay penceresi ve içerik aynı temel kontrolleri kullanır.
- C ve Python GTK pencereleri `desktop.json` değişimini dosya olayıyla izler. Açık/koyu/vurgu ve azaltılmış hareket açık pencerede güncellenir. Yüksek kontrast teması seçilirse uygulama materyal sınıfı çekilir; kullanıcı erişilebilirlik teması ezilmez.
- Uygun cihaz + GTK animasyon ayarı + azaltılmamış hareket: **200ms native crossfade**. GTK3’ün native easing’i kullanılır; web `transform` veya her sayfada özel bir yay/yerleşim döngüsü taklit edilmez. Başlat ikonunun mikro hareketi `-gtk-icon-transform` ile çizim katmanındadır; sabit piksel boyutu korunur. CSS renk geçişleri 160–180ms, tek ve sınırlıdır.
- Pencere aç/kapat, ölçek/opacity ve desteklenen yay hareketi mevcut tek-kompozitör motoruna aittir. Uygulama ikinci bir pencere animasyonu başlatmaz. Eski Picom’da fade/statik fallback korunur. Yerel GTK popover/menüler kabuğun/GTK’nın geçişlerini kullanır; her menüde bulanık arka plan yeniden üretilmez.
- **Gerçek cam için:** Masaüstü Merkezi → Aero → gerçek blur’ü açıkça seç. Yalnız >2GiB, izinli DRM sürücüsü, normal kaynak profili, nomodeset olmaması ve **canlı sahipliği doğrulanmış kendi Picom’u + `blur_configured`** halinde uygulama kökü ARGB olur. PID başlangıç zamanı ve X11 CM sahibi doğrulanır. Haber okuma yüzeyi ve başlık/kapatma kontrolleri opaktır. Vurgu/tint ve ince yansıma okunabilirliği korur.
- GTK3’te `backdrop-filter`/evrensel saturation shader yoktur. Gerçek blur Picom/GLX’tedir; tint saturation shader diye sunulmaz. GNOME CSD, Wayland ve bilinmeyen/harici compositor’da uygulama içi cam **opak fallback** kullanır; GNOME/Plasma kabuk camı mevcut native arka uçlarında kalır. Düşük RAM, bilinmeyen GPU, mini/light, azaltılmış hareket ve kurulum korumaları kaldırılmaz.

### Haber kullanımı ve veri sözleşmesi

1. Açılış yerel kaynağı okur; arka planda otomatik HTTP yoktur.
2. **Yenile** yalnız seçili HTTPS RSS/Atom kaynağına gider. Resim, reklam, JavaScript veya tam makale kazıma yoktur. İşçi süre/boyut sınırına tabidir ve iptal edilebilir. Yükleme sırasında eski metin okunabilir.
3. Başarılı indirme → `mode: live`; sonraki çevrimdışı açılış → `cache`. Yayıncının tarihi değiştirilmez; son başarılı indirme zamanı ayrıca görünür.
4. Ağ/TLS/XML hatası → görünür uyarı + eski önbellek. Önbellek yok/bozuksa **ÖRNEK AKIŞ · Gerçek haber değildir**. Altı yerel kullanım ipucu, istek anındaki dakikaya göre sıralanır; haber olayı, kaynak bağlantısı veya yayın tarihi uydurulmaz. Örnekler TRT/BBC/DW’ye atfedilmez ve yayıncı önbelleğine yazılmaz.
5. Gündem, Dünya, Bilim ve teknoloji, Kültür, Spor, Rehber kategorileri ve arama indirilmiş metni **yerel** filtreler. Reader görünümü, Kaynakta aç ve 12–26pt yazı tercihi korunur. Aynı metin yeniden geldiyse liste yeniden kurulmaz, açık okuma görünümü sıfırlanmaz.
6. HTTPS kaynak ekleme/kaldırma devam eder. Özel ağ/DNS rebinding/HTTP downgrade/entity/DTD/markup/boyut kısıtları değişmez.

`Reader.cached()` / `refresh()` katı doğrulama API’sidir. Sunum için yeni `Reader.stream(identifier, network=False)` kullanılır; `mode`, `example`, `warning`, `note`, `categories` alanlarını döndürür. Hata metni açıkça görünür; örnek veri gerçek haber diye gösterilemez.

### Mağaza kullanımı ve işlem güvenliği

- **Keşfet:** editoryal seçki + kompakt uygulama satırları; kategori/işlev/isim araması. Üreticinin hayalî ekran görüntüsü, puan veya indirme sayısı eklenmez. Flathub araması açık ve ayrı eylemdir; arama sonucu bu hesaptaki kurulu durumunu da okur.
- **Yerel kataloğa dön / listeyi yenile:** dpkg ve bir defa Python-APT önbelleği okunur; güncel yerel aday sürüm, kurulu sürüm ve yükseltilebilirlik sunulur. Bu işlem depo listelerini ağdan yenilemez. Güncel imzalı listeler için mevcut Güncelleyici kullanılır. Metadata yoksa sürüm uydurulmaz.
- **Ayrıntı:** kaynak/kapsam, gerçek paket sürümleri/kökeni veya Flatpak izinleri. Yükle / Güncellemeyi denetle / Aç / Kaldır eylemleri sonuç sonrasında yeniden okunan kurulum durumuna göre güncellenir.
- Metadata, plan ve işlem sırasında okuma/kaydırma/yerel filtreler donmaz. Çakışan işlem düğmeleri kapalıdır. Gerçek paket işlemi X/`--quit` ile yarıda kesilmez; shell/root GUI/killall eklenmez.
- **Sistem kaldırması** yalnız `remove-app:<katalog-kimliği>` ister. Aynı Polkit yardımcısı, canlı USB yasağı, OğuzDows/APT kilitleri, mimari ve taban denetimi kullanılır. Önce gerçek APT simülasyonu, sonra açık plan onayı ve aynı digest’in tekrar doğrulanması gerekir. Başka bir paket de kaldırılacaksa veya Essential/required/important/tutulan paket etkilenirse bütün istek reddedilir. Kurulum/güncellemedeki `--no-remove` aynen kalır. `purge`, `autoremove`, serbest paket adı veya temel sistem kaldırma izni yoktur. Yeniden planlama ve uygulama boyunca dpkg frontend kilidi tutulur. Onaydan sonra ikinci bir APT çözümlemesiyle kaldırma kümesinin genişlememesi için yalnız planın kesin paketleri `dpkg --remove` ile aktarılır; dpkg backend kilidi, bağımlılık ve Essential denetimi açık kalır.
- **Kullanıcı Flatpak kaldırması** sadece bu hesapta Flathub’dan kurulu seçili `app/<id>/<arch>/stable` ref’idir. Önizleme mutasyondan önce durur; apply aynı operasyon digest’ini ister. Runtime/başka ref kaldırması reddedilir; `--delete-data` yoktur. Kaynak çevrimdışı/kaldırılmışken kurulu uygulama yerel planla kaldırılabilir. Sistem Flatpak kapsamı yönetilmez.
- Varsayılan onay cevabı **Vazgeç**. Kişisel dosyalar ve uygulama ayarları korunur. Bir bağımlılık mağazanın dar sınırını aşıyorsa kullanıcıya açıklanır; zorla kaldırılmaz.

## Derleme ve doğrulama

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' -v
sh scripts/build-news.sh /tmp/oguzdows-news
sh scripts/build-native.sh /tmp/oguzdows-store
sh scripts/build-desktop.sh hub /tmp/oguzdows-hub
sh scripts/build-desktop.sh monitor /tmp/oguzdows-monitor
# Native geliştirme/test ikilileri --test ile repo içindeki CSS ve fixture işçisini kullanır.
sh scripts/build-news.sh /tmp/news-test --test
xvfb-run -a dbus-run-session -- /tmp/news-test --smoke-test test-results/news
sh scripts/build-native.sh /tmp/store-test --test
xvfb-run -a dbus-run-session -- /tmp/store-test --smoke-test test-results/store
xvfb-run -a dbus-run-session -- python3 tests/smoke-material.py --output test-results/material
# Ayrı, açık ağ deneyi; masaüstü açılışına bağlı değildir:
python3 tests/smoke-news-live.py --output test-results/news-live.json
```

Hedeflerde `build-essential pkg-config libgtk-3-dev libjson-glib-dev libx11-dev` gerekir; Python GTK testleri GI/Xvfb/DBus gerektirir. Üretim ikilileri hedef mimarinin ABI’sinde mevcut ISO/Pi/ARM derleme yollarıyla derlenir; uyumsuz x86 ikilisi ARM’e kopyalanmaz.

Yalnız tek kullanımlık amd64/trixie GitHub container’ında `tests/smoke-store-transaction.py`, gerçek yardımcı üzerinden Geany yükleme/kaldırma, tutulan paket, frontend kilidi, yanlış token, bağımlılık ve kişisel dosya koruma kapılarını sınar. Normal host/USB’de açıkça reddedilir. Bu test Polkit parola arayüzünü veya fiziksel kurulumu kanıtlamaz.

Yeni testler Python 3.13 HTTPS sözleşmesini, canlı→önbellek→dürüst örnek geçişini, kategori/arama/reader/iptal yollarını, dar APT ve libflatpak kaldırma digest’ini, varsayılan iptal ve fixture yükle/kaldır düğme bağlantılarını kapsar. Gerçek GTK CSS/parser/geçiş ve 360px ekran kontrolleri iki hedef tabanda CI’dadır. Ayrı canlı RSS probu her yayıncı sonucunu ve Python sürümünü raporlar; tüm kaynaklar erişilebilir varsayılmaz.

**Kanıt sınırı:** fixture GTK yükle/kaldır işlemi gerçek paket kurulumu değildir; ayrı gerçek container testi bundan ayrıdır. Xvfb/simüle kaynak uygunluğu fiziksel GPU/FPS değildir. ISO hedef kapıları exact kaynak revizyonu, kernel/systemd, BIOS/UEFI (uygun mimaride) ve 512/1024/2048MiB tam Xfce boşta ölçümünü ayrıca doğrular; fiziksel cihaz, Wayland ve tam Calamares GUI/encrypted-root kurulumu yerine geçmez.
