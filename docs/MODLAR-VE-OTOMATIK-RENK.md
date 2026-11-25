# Ayrı Windows 11 / macOS modları ve duvar kâğıdına bağlı renk

Bu modlar **OğuzDows’un Xfce/X11 düzenleridir**; Windows veya macOS kurulmaz.
Mevcut GTK3/C uygulamalar, Xfwm, Xfconf, kişisel sabitlemeler, yedekler ve
tek kompozitör koruması korunur. Yeni shell, Electron, Plank veya sürekli
Python çizim / renk tarama servisi yoktur.

## Neden önceki görünüm benziyordu?

1. Windows profili de üst panel + küçük alt iskele kullanıyordu. Artık **tek
   tam genişlikli alt görev çubuğu** vardır. Başlat / uygulamalar ayrı yerel
   C grubunda ekran merkezine yerleşir; tepsi, ses, güç ve tarih/saat sağdadır.
2. Aero, Windows 11 temasını genel Aero temasıyla değiştiriyordu. Artık Eleven
   ve Mac kimlikleri açık/koyu, cam ve opak durumda da ayrı kalır.
3. Xfwm’nin kare başlık parçaları, GTK CSD’nin kendi gölgesi ve kompozitörün
   kesmesi farklı sahiplerdi. Artık tek 32px başlık tabanı, 1px yarı saydam
   kenar, şekilli üst köşeler, tutarlı GTK CSD geometrisi ve Picom’da tek
   SSD köşe kesmesi kullanılır. Kontrollerin arkasında kare renk yamaları yoktur.
4. Renk yalnız galeri seçiminin bir dalında hesaplanıyordu. Artık galeri
   işlemi ortak tercihe bağlıdır; Xfce’nin kendi arka plan ayarı da olayla izlenir.

## Hazır ISO’da kullanım

1. Yeni ISO’dan OğuzDows / Xfce oturumunu açın. Mağaza / Haber mimarisi değişmez.
2. **Masaüstü Merkezi → Aero ve görünüm → Masaüstü düzeni** alanından:
   - **Windows 11 esintisi:** tek alt çubuk, ortalı Başlat / uygulamalar,
     sağ tepsi ve iki satırlı tarih/saat, sağda geniş Windows tarzı kontroller.
   - **macOS esintisi:** ince üst uygulama / yerler menüsü ve sağ sistem alanı;
     altta ayrı, içeriğe oturan Dock; solda kırmızı/sarı/yeşil kontroller,
     ortalı başlık. Dock ikonları fareyle 150ms içinde büyür; aktif pencere
     noktası görünür. Hareket azaltılmışsa büyüme yerine statik odak kullanılır.
3. Anında düzen değişimi için **“Düzen değişirse paneli şimdi yenile”** kutusunu
   özellikle işaretleyin. Yoksa yeni panel bileşenleri sonraki girişte yüklenir.
   Panel yenileme açık uygulamaları kapatmaz; oturum kapatma komutu verilmez.
4. **Otomatik vurgu → Her duvar kâğıdında otomatik** seçin ve uygulayın.
   Yeni tercihi olmayan temiz kurulumlarda bu kaynak varsayılandır. Eski açık
   elle renk tercihi yükseltmede zorla değiştirilmez.
5. Rehber’in Türkiye galerisinden veya **Xfce Masaüstü Ayarları** içinden başka
   JPEG / PNG / WebP seçin. Galeride aynı işlem içinde; dış değişiklikte yaklaşık
   350ms birleştirme + kısa renk işçisi süresinden sonra vurgu yenilenir.
   Etkin Xfwm kenarı, GTK seçimleri, önerilen düğmeler, odak / ilerleme / vurgu
   çizgileri, panel ve menü cam tonu değişir. Açık GTK3 uygulamalar tema adı
   değişimini alır; uygulamayı veya tüm oturumu yeniden başlatmak gerekmez.
6. Gerçek buzlu görünüm isterseniz **Aero**, **gerçek arka plan bulanıklığı**
   ve uygun donanım seçeneğini açıkça etkinleştirin. Otomatik renk seçimi kendi
   başına blur, yay veya ağır efektleri açmaz.

Üstteki macOS benzeri menü **Xfce’nin gerçek uygulama ve yerler menüsüdür**;
her uygulamanın Dosya/Düzen menüsünü dışarı taşıyan evrensel global menü diye
sunulmaz. Dock gerçek Wnck pencere olaylarıyla çalışır: tık etkinleştirir /
küçültür, çok pencereli grupta pencere listesi açılır; sağ tık ve klavye Menü
tuşu da desteklenir. Başlat’taki `pins.ini` tercihleri okunur ve değişince
olayla yenilenir; kişisel sabitleme dosyası Dock tarafından yeniden yazılmaz.

### Normal kullanıcı terminaliyle aynı işlemler

Açık Xfce/X11 oturumunda; **sudo kullanmayın**:

```sh
# Ayrı düzenler; --refresh-panels açık panel yenileme onayıdır.
oguzdows-desktop --profile windows11 --refresh-panels
oguzdows-desktop --profile mac --refresh-panels

# Her duvar kâğıdını izle / şu anki görselden bir kez eşitle.
oguzdows-accent --enable
oguzdows-accent --sync

# Uygun GPU’da isteğe bağlı buzlu yüzey. Düşük kaynakta opak kalır.
oguzdows-desktop --apply --effects aero --blur --motion smooth

# Animasyonu azalt / ağır efektleri kapat (otomatik renk korunur).
oguzdows-desktop --apply --motion reduced --effects off --no-blur

# Otomatik renk yerine elle seçili rengi koru; native izleyici de çıkar.
oguzdows-accent --disable

# Yalnız renk hesabını görmek; masaüstü ayarı değiştirilmez.
oguzdows-accent --extract "$HOME/Resimler/duvar-kagidi.jpg"

# Durum ve yedekli geri alma.
oguzdows-desktop --status
oguzdows-desktop --restore
```

## Kaynaktan mevcut OğuzDows’a kurulum

Yalnız bu kaynak sürümüyle uyumlu **mevcut OğuzDows** üzerinde, sistem yedeği
aldıktan sonra uygulayın. Düz başka dağıtıma tüm `system/` ağacını kopyalamayın.
Bu adımlar root yapılandırması / kullanıcı panel dosyalarını ezmez.

```sh
# Depo kökünde; Debian bookworm/trixie hedefinde derleme bağımlılıkları.
sudo apt-get install build-essential pkg-config libgtk-3-dev libjson-glib-dev \
  libxfce4ui-2-dev libxfce4panel-2.0-dev libxfconf-0-dev libwnck-3-dev python3-pil python3-gi

# Önce derleyin; başarısız derleme mevcut kuruluma dokunmaz.
stage="$(mktemp -d)"
sh scripts/build-panel.sh "$stage"
sh scripts/build-native.sh "$stage/usr/lib/oguzdows/oguzdows-store-native"
sh scripts/build-news.sh "$stage/usr/lib/oguzdows/oguzdows-news-native"
for component in hub monitor; do
  sh scripts/build-desktop.sh "$component" "$stage/usr/lib/oguzdows/oguzdows-$component-native"
done
# Mimariye göre /usr/lib/<triplet>/xfce4/panel/plugins yolunu korur.
sudo cp -a "$stage/usr/." /usr/

# Ürünün runtime modülleri ve kendi temaları. Kişisel ~/.config'a yazılmaz.
sudo install -m 644 system/usr/lib/oguzdows/{accent,profiles,desktop_preferences,desktop_material,desktop_state,desktop_center,desktop_ui,wallpapers,ui_theme,welcome}.py /usr/lib/oguzdows/
sudo install -m 644 scripts/render-assets.py /usr/lib/oguzdows/render-assets.py
sudo install -m 755 system/usr/local/bin/oguzdows-accent /usr/local/bin/
sudo install -m 644 system/usr/share/xfce4/panel/plugins/oguzdows-tasks.desktop /usr/share/xfce4/panel/plugins/
sudo cp -a system/usr/share/themes/. /usr/share/themes/
sudo install -m 644 system/usr/share/oguzdows/ui/{window-geometry,modern}.css /usr/share/oguzdows/ui/
sudo install -m 644 system/usr/share/oguzdows/picom.conf /usr/share/oguzdows/
sudo cp -a system/usr/share/oguzdows/compositor/. /usr/share/oguzdows/compositor/
sudo install -m 755 system/usr/lib/oguzdows/session.sh /usr/lib/oguzdows/session.sh

# Yalnız Xfwm parçalarını üretir; galeri / kişisel fotoğraflar değiştirilmez.
sudo python3 - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('assets', '/usr/lib/oguzdows/render-assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
for name in ('OguzDows', 'OguzDowsLight', 'OguzDowsXP', 'OguzDowsXPDark',
             'OguzDowsEleven', 'OguzDowsElevenDark', 'OguzDowsMac', 'OguzDowsMacDark',
             'OguzDowsAero', 'OguzDowsAeroDark', 'OguzDowsAeroGlass', 'OguzDowsAeroGlassDark'):
    light = name.endswith('Light') or name in ('OguzDowsXP','OguzDowsEleven','OguzDowsMac','OguzDowsAero','OguzDowsAeroGlass')
    assets.window_theme(Path('/'), name, light=light, xp=name.startswith('OguzDowsXP'))
PY
```

Ardından yukarıdaki **normal kullanıcı** düzen / otomatik renk komutlarını
çalıştırın. Sonraki girişte `session.sh`, otomatik kaynak açıksa native
izleyiciyi yeniden başlatır. Mevcut yedekler ve ilk değişiklik yedeği silinmez.

## Kompozitör / pencere uyumluluğu

| Oturum / sahip | Köşe / gölge | Cam / hareket |
|---|---|---|
| Xfce + Xfwm, efekt kapalı / düşük kaynak | GTK3 CSD kendi tutarlı köşesini; SSD Xfwm şekilli üst köşeyi ve 1px alt rayı kullanır. Kompozitörsüz CSD güvenli kare fallback olabilir. | Renk ve vurgu çalışır; opak, bulanıklık yok. |
| Xfce + Xfwm kompozitörü (`glass`) | GTK CSD kendi gölgesi, SSD için çift gölge yok. | Hafif panel alfa; gerçek backdrop blur yok. |
| Xfce + sahipliği doğrulanan Picom 9+ (`aero`) | SSD dış çerçeve 10px kırpılır; CSD `_GTK_FRAME_EXTENTS` ile yeniden kırpılmaz / gölgelenmez. Tam ekran ve büyütülmüş pencereler kare kalır. Panelin şekli GTK’nındır. | Hızlandırılmış GLX + açık blur onayı + >2GiB/full/uygun DRM gerekir. 9.x: desteklenen kernel blur; yeni sürümler: dual-kawase. Yay/geometri 12+ ister. |
| Yabancı kişisel kompozitör | Kapatılmaz / öldürülmez; onun ayarları son sözdür. | İkinci motor açılmaz; doğrulanamayan cam opak fallback alır. |
| GNOME / Plasma / Wayland | Mevcut yerel arka uçlar korunur. | Bu iki panel düzeni ve yeni xfconf izleyicisi yalnız Xfce/X11 içindir. |

GTK3 ARGB destekleyen başlık, menü, panel ve dekoratif çerçeveler renkli cam
alabilir. **Thunar’ın dosya listesi ve yazı alanları okunaklı / opak kalır**;
tüm pencereye `opacity=.8` uygulayarak yazıyı soldurmak yapılmaz. GTK2, Qt,
GTK4/libadwaita ve uygulamanın özel CSD çizimi aynı kuralları evrensel olarak
izlemek zorunda değildir. Kendi dekorasyonunu çizen her uygulamada eşit köşe
ve blur garantisi verilmez; bunların yerel ayarı / fallback’i korunur.

## Renk, veri ve kaynak sınırları

- Özel script 64×64 örnekten 12 renk çıkarır; baskınlık / doygunluk puanlar,
  okunabilir aralığa getirir ve seçim yazısı için koyu/açık kontrast seçer.
  Renk her fotoğrafa bağlıdır; isimden rastgele palet seçilmez.
- Yalnız yerel JPEG/PNG/WebP, en fazla 40 MiB / 25 megapiksel. SVG, URL ve
  komut açılmaz. Görsel uygun değilse önceki renk korunur; işçi hata kodu verir.
- Çok monitör / çalışma alanında son değişen anahtarın görseli ortak vurguyu
  belirler; başlangıçta sıralı ilk okunabilir ekran kullanılır. Diğer duvar
  kâğıtları yeniden yazılmaz. Aynı görselin dosya içeriği, yol değişmeden başka
  araçla düzenlenirse `oguzdows-accent --sync` kullanın.
- Native `GApplication` ekran başına tektir. 350ms debounce, aynı anda bir
  kısa Python işçisi ve yoğun işlem kilidinde sınırlı geri çekilme vardır.
  Boşta HTTP / görsel / süreç taraması yoktur. Elle kaynak seçilince izleyici çıkar.
- Renk temaları `~/.local/share/themes/*User-<hash>` altında sürümlü, değişmezdir.
  Ortak ayar `~/.config/oguzdows/desktop.json`, tipli Xfconf yedeği
  `~/.local/state/oguzdows/profiles/before-first-change.json` içindedir.
  Yedekteki veya başka oturumun temasını bozmamak için geçmiş apply sırasında
  silinmez. Kişisel temalar, sabitlemeler ve fotoğraflar temizlenmez.
- Kurucu / sürücü meşgulse renk veya düzen güvenlik kapısını aşmaz. Değişiklik
  ve kalıcılık hatasında eski tema / tipli anahtarlar karşılaştırmalı geri alınır.

## Doğrulama ve ISO üretimi

Birim testleri: ayrı panel dizileri, çakışma / yedek / rollback, fotoğraflardan
farklı renkler, cache ve sınırlar, manuel kaynak yarışı, GTK/CSD / SSD geometri
sözleşmeleri. CI her iki Debian tabanında C bileşenini `-Werror` ile derler;
gerçek Xfce panellerinde 3 çözünürlük, merkez / sağ tepsi geometrisi, native
launcher’ın gecikmeli kaydı, geri alma ve açık uygulama korunması sınanır.
Yazılım GPU’sunda Picom parser / gerçek ARGB blur testi fiziksel GPU testi değildir.

```sh
# Geliştirici: yalnız ayrı çalışma ortamında.
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'
# README'deki live-build bağımlılıkları hazır, çalışma dizini henüz yokken:
sudo ./build.sh amd64  # trixie, BIOS + UEFI
sudo ./build.sh i386   # bookworm / 686-pae, BIOS
```

Yeni ISO’lar kaynak hashleriyle ayrıca doğrulanır; önceki görevde üretilen ISO,
bu düzen / renk değişikliklerini içeriyor diye sunulmaz. QEMU hedef kernel /
initramfs / systemd / Xfce ve düşük RAM kapıları, fiziksel GPU FPS’i veya tam
Calamares GUI kurulumunun kanıtı değildir. Pi imajı, sürüm etiketi, birleştirme
ve web yayını bu isteğin parçası değildir.
