# README görselleri

Bu klasör yalnızca GitHub dokümantasyonuna aittir; buradaki görseller PC/Pi imajına eklenmez.

- `oguzdows-banner.svg`: projenin `assets/oguzdows.svg` ay-yıldız geometrisini kullanan statik vektör kapak. Haricî yazı tipi, script, `foreignObject`, takip pikseli veya ağ kaynağı yoktur. İşletim sistemi ekran görüntüsü değildir.
- `oguzdows-mobile-v2.jpg`: gerçek **2.0 Akıncı native launcher API35/x86_64 emülatör** thumbnail’i, fiziksel telefon veya web tasarımı değildir. Kaynak `5a44de0dde676d901a32be40d631d481e213439d`, [koşu 46092350348 / iş 140816933793](https://github.com/PeraPlusbirPasha/OguzDows/actions/runs/46092350348/job/140816933793). Altı checks parçası eksiksiz Base64/JPEG doğrulandı; **234×519, 12.959 bayt**, SHA-256 `2f532a28e17c2df84030c0169a44878479b4e6df51cf9ed4d4b6e7699bff6876`. MediaProjection fixture karesi veya fiziksel performans kanıtı değildir. Duvar kâğıdının kökeni [mobil varlık kaydında](../../mobile/ASSETS.md).
- Altı manzara JPEG’i: `system/usr/share/backgrounds/oguzdows/` altındaki mevcut, logolu 1920×1080 görsellerin 480×270 küçük kopyaları. README’nin yaklaşık 3 MB tam boy manzara yüklemesi yerine toplam yaklaşık 154 KB önizleme kullanmasını sağlar. Tıklama özgün görsele gider.
- Manzaralar yapay zekâ üretimidir; gerçek kamera fotoğrafı veya doğrulanmış coğrafi belge olarak sunulmaz. Ayrıntılı köken ve üretim bilgileri: [artwork/README.md](../../artwork/README.md) ve [landscapes.json](../../artwork/landscapes.json).

Önizlemeleri repo kökünden, Pillow hazırken çevrimdışı yeniden üretmek için:

```sh
python3 - <<'PY'
from pathlib import Path
from PIL import Image
source = Path('system/usr/share/backgrounds/oguzdows')
for name in ('bogaz-sabahi', 'kackar-sisi', 'kapadokya-isigi',
             'oludeniz-kiyisi', 'tuz-golu-aksami', 'ani-kisi'):
    with Image.open(source / (name + '.jpg')) as image:
        preview = image.convert('RGB').resize((480, 270), Image.Resampling.LANCZOS)
        preview.save(Path('docs/assets') / (name + '.jpg'),
                     format='JPEG', quality=83, optimize=True, progressive=True)
PY
```

Pillow/JPEG kodlayıcı sürümü ikili çıktıyı değiştirebilir; önizlemeler ISO içeriğinin hash kanıtı değildir. ISO ve özgün manzara doğrulamaları bundan ayrıdır.
