# OğuzDows tanıtım sitesi

Ücretsiz statik GitHub Pages sitesi. Native launcher/mobil tasarım laboratuvarı veya OS imajı değildir. Kaynak değiştirilmeden 2.0 yayın dosyalarına bağlanır.

- [Canlı adres](https://peraplusbirpasha.github.io/OguzDows/)
- [SEO, Google Search Console, ücretsiz tanıtım ve dal sınırları](../docs/WEB-VE-GORUNURLUK.md)

## Derle ve önizle

```sh
python3 website/build.py
python3 website/build.py --check
python3 website/serve.py --host 0.0.0.0 --port 4174
```

Önizleme: `http://127.0.0.1:4174/OguzDows/`. Tarayıcıdaki asset/link’ler origin-relative olduğundan paylaşımlı preview host’unda da çalışır; canonical/OG/sitemap üretim adresini kullanır. Önizleme sunucusu indekslenmez.

Sayfa içerikleri ve ortak şablon: `build.py`. Görünüm: `assets/site.css`. JS yalnız kopyalama/menü kolaylığıdır; site JS olmadan da çalışır. `site.json` canonical ve gerçek Search Console etiketi ayarını tutar; henüz Google sahiplik doğrulaması yapılmış değildir.

Üretilen 15 sabit dosya `docs/` altına commit edilir. `.nojekyll` ile bir paket yöneticisi/ücretli build gerekmeden sunulur. Üretim indirme/hash kaynakları `docs/releases/v2.0-release.json` içinden okunur. Başka rehber, tarihsel yayın veya native ürün dosyası yeniden yazılmaz.

## Test

```sh
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -p 'test_website.py' -v
# Önizleme açıkken; var olan mobile/preview test bağımlılıklarıyla:
node --test website/tests/browser.test.mjs
```

Pillow yalnız görsel testleri ve isteğe bağlı `make-social.py` yeniden üretimi içindir; site oluşturucusunun bağımlılığı değildir. Tarayıcı araçları test içindir, ziyaretçiye indirilmez. CI yalnız okuyabilir; Pages ayarı, release, etiket veya ürün derlemesine yazamaz.

## Görsel köken

- `logo.svg`: mevcut `assets/oguzdows.svg` proje geometrisinin aynısı; ayrı, yeni marka/lisans iddiası yok.
- `oguzdows-akinci.jpg`: özgün tipografik 1200×630 paylaşım kartı; OS ekranı veya AI görseli değil. DejaVu Sans sistem fontuyla rasterize edilir, font dosyası dağıtılmaz.
- Hero arka planı: mevcut `docs/assets/bogaz-sabahi.jpg`, açıklanmış AI duvar kâğıdı.
- Telefon: mevcut `docs/assets/oguzdows-mobile-v2.jpg`, gerçek kabul edilen 2.0 native emülatör kaydı; fiziksel telefon veya web UI görüntüsü değil.

Üçüncü taraf font/CDN, reklam, analitik, gizli form, API/model çağrısı, çerez veya kayıt hesabı eklenmez. Hosting sağlayıcısının standart erişim günlükleri bu kapsama dahil değildir.
