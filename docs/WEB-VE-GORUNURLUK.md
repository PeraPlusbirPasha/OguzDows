# OğuzDows 2.0 · Web sitesi ve ücretsiz görünürlük

[← README](../README.md) · [Site](https://peraplusbirpasha.github.io/OguzDows/) · [PC/APK · 2.0](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0) · [Pi · ARM düzeltmesi 2](https://github.com/PeraPlusbirPasha/OguzDows/releases/tag/v2.0-arm2)

## Ne kuruldu?

Bağımsız **statik tanıtım/indirme sitesi**, GitHub Pages’in herkese açık depo barındırması için hazırlanmıştır. Ücretli alan adı, reklam, veritabanı, AI API’si, analiz aboneliği veya sunucu satın alma yoktur. Site büyük ISO/IMG/APK dosyalarını kopyalamaz; doğrulanmış GitHub Releases dosyalarına bağlanır. Ücretsiz hizmetler sağlayıcının kota ve kullanım şartlarına tabidir; sınırsız trafik taahhüdü verilmez.

Yedi ayrı, JavaScript kapalıyken de okunabilen HTML sayfası:

| Sayfa | Amaç |
| --- | --- |
| [Ana sayfa](https://peraplusbirpasha.github.io/OguzDows/) | 2.0 Akıncı, gerçek kapsam, platformlar ve projeye katılım. |
| [İndir](https://peraplusbirpasha.github.io/OguzDows/indir/) | Dört imaj + ana launcher, özgün boyut/hash, checksum ve rehberler. |
| [PC](https://peraplusbirpasha.github.io/OguzDows/pc/) | Türkçe Linux/Xfce, mimari/RAM seçimi ve canlı USB adımları. |
| [Raspberry Pi](https://peraplusbirpasha.github.io/OguzDows/raspberry-pi/) | Model/revizyon, ARMv6/ARM64, ilk hesap ve deneysel sınırlar. |
| [Telefon](https://peraplusbirpasha.github.io/OguzDows/telefon/) | Native debug launcher, boş emülatör kurulumu; APK ≠ ROM. |
| [OğuzKöprü](https://peraplusbirpasha.github.io/OguzDows/oguzkopru/) | İzinli yerel dosya/salt ekran; eşleştirme ve limitler. |
| [SSS](https://peraplusbirpasha.github.io/OguzDows/sss/) | Gerçek sorulara görünür yanıtlar; gizlilik ve bilinen eksikler. |

Bu yeni site, 2.0 yayınının içindeki **statik mobil tasarım laboratuvarı arşivinden ayrıdır**. ROM, SIM kontrol paneli veya model sunucusu değildir. Yayın dosyaları, etiket, ürün kimliği, gömülü bağlantı rehberi ve önceki kabul kayıtları değiştirilmez.

## SEO için gerçekten yapılanlar

- Her sayfada ayrı ve açıklayıcı Türkçe başlık/açıklama, tek `h1`, `lang="tr"` ve gerçek içerik.
- Üretim adresine işaret eden tek canonical URL; yedi URL’li `sitemap.xml`. Sahte `lastmod`, arama motoru sıralaması veya indekslenme tarihi yazılmaz.
- Open Graph / sosyal paylaşım başlıkları ve **1200×630** yerel tanıtım kartı. Marka kartı özgün tipografik çizimdir, OS ekran görüntüsü değildir.
- WebSite / WebPage / Organization ve uygun sayfalarda BreadcrumbList / SoftwareApplication JSON-LD. Yalnız gerçek ürün/kapsam/ücretsiz indirme bilgisi; sahte yıldız, yorum, kullanıcı/indirme sayısı, lisans veya sosyal hesap yoktur. Rich result gösterimi taahhüt edilmez.
- Mobil düzen, klavye erişimi, atlama bağlantısı, görünür odak, azaltılmış hareket tercihi. Menü/SSS/checksum alanları native HTML ile JS kapalıyken de çalışır.
- Framework, üçüncü taraf font, otomatik API isteği, reklam/analiz çerezi ve takip SDK’sı yoktur. GitHub’ın standart barındırma/erişim günlükleri bundan ayrı kalır.
- Doğru indirme dosyaları ve açık sınırlar: debug APK, ROM olmayan telefon paketi, fiziksel kabul yokluğu, Zero siyah ekranı ve bulut AI/ses/wake-word eksikleri görünürdür.

**Google’da ilk sıra veya indekslenme garantisi yoktur.** Teknik hazırlık bulunabilirliğe yardımcı olur; yeni bir sitenin taranması, dizine alınması ve sıralaması Google’ın kararıdır. Ücretli backlink, sahte yorum, anahtar kelime doldurma ve topluluk spam’i yapılmaz. “Google’a gönderildi” ile “Google’da indekslendi” aynı şey değildir.

### Project Pages ve robots.txt ayrıntısı

Adres bir alt yoldadır: `/OguzDows/`. Standart crawler kuralları **origin kökündeki** `https://peraplusbirpasha.github.io/robots.txt` dosyasından okunur. Bu deponun `/OguzDows/robots.txt` dosyası tek başına o kökü yönetmez; bu yüzden “robots ile Google kesin açıldı” denmez. Her sayfanın `index,follow` metası ve doğrudan erişilebilir HTML’i vardır; sitemap’i aşağıdaki URL-prefix mülkü üzerinden göndermek doğru yoldur. 404 sayfası `noindex,follow` kullanır. Yerel önizleme sunucusu ayrıca `X-Robots-Tag: noindex` döndürür; bu üretim Pages başlığı değildir.

## Google için hesap sahibinin yapacağı son adım

Google hesabına giriş / mülk sahipliği kullanıcıya aittir; şifre, OAuth kodu, ödeme veya kişisel hesap erişimi istenmez. Otomatik Search Console sahipliği ya da gönderim yapılmış gibi gösterilmez.

1. [Google Search Console](https://search.google.com/search-console/) aç; **URL öneki** mülkü ekle:
   `https://peraplusbirpasha.github.io/OguzDows/`
2. **HTML etiketi** doğrulama yöntemini seç. Yalnız `content` değerini `website/site.json` içindeki `google_site_verification` alanına koy. Bu kamuya açık sahiplik etiketi bir hesap şifresi değildir; yine de gerçek değeri Google vermeden yer tutucu yayımlama.
3. `python3 website/build.py` çalıştır, mevcut çalışma dalına kaydet/push et ve PR üzerinden `main`e al. `main:/docs` Pages yayını güncellenince Search Console’da **Doğrula** de.
4. **Site Haritaları** bölümüne `sitemap.xml` ekle. Tam adres:
   `https://peraplusbirpasha.github.io/OguzDows/sitemap.xml`
5. URL Denetimi ile ana sayfa ve `/indir/` için canlı testi aç; erişilebilir/indekslenebilir durumunu görüp istersen dizine ekleme iste. Bu istek Google’ın kabul veya sıra garantisi değildir.
6. Performans raporunda gerçek gösterim/tıklama/sorguları takip et. Henüz veri yoksa kullanıcı/sıralama sayısı uydurma.

Alan adı satın almadan URL-prefix yöntemi yeterlidir. DNS tabanlı alan mülkü için `github.io` alanının sahibiymiş gibi davranılmaz. Eski “sitemap ping” uçları, toplu otomatik indeksleme spam’i veya genel sayfalarda Indexing API’ye zorlamak kullanılmaz.

## Ücretsiz ve sürdürülebilir tanıtım planı

| Zaman | Küçük, somut adım |
| --- | --- |
| Başlangıç | Depo açıklamasını 2.0’a taşı, siteyi About / Website alanına ekle ve yalnız ilgili konuları etiketle. README kapağında 1.0 yerine 2.0 Akıncı görünsün. |
| İlk paylaşım | Site altındaki **Tanıtım metnini kopyala** düğmesiyle kısa ve dürüst metni al. İlgili bir Türkçe Linux/Pi topluluğunda kurallarına uygun **bir** tanıtım paylaş; otomatik gönderi yok. |
| İlk geri bildirim | Gerçek cihaz modelini, mimariyi ve sonucu topla; issue’da kişisel bilgi/SIM numarası/log sırlarını ayıkla. Deneysel portu kararlı diye pazarlama. |
| Haftalık | Bir gerçek kullanım/kurulum ipucu veya somut geliştirme notu paylaş. Aynı reklamı tekrar tekrar göndermek yerine soruları yanıtla. |
| Aylık | Search Console’da gerçek sorgu/gösterimleri kontrol et; yanlış anlaşılmaları açıklayan özgün içerik ekle ve kırık linkleri düzelt. |

Örnek paylaşım metni (kendin uyarlayabilirsin):

> OğuzDows 2.0 Akıncı yayında: PC/Pi için Türkçe Xfce masaüstü, telefonda ayrı native debug launcher ve onaylı yerel OğuzKöprü bağlantısı. Ücretsiz indirmeler, checksum’lar ve açık test sınırları: https://peraplusbirpasha.github.io/OguzDows/ — Pi portları deneysel; launcher ROM değildir. Deneyim ve yapıcı geri bildirim bekliyoruz.

## Bakımı nasıl yapılır?

Site kaynağı `website/`; **yalnız 15 sabit web çıktısı** `docs/` içine üretilir. İmaj/kurucu/mobil uygulama derlenmez. Başka sürümün `docs/releases/` kayıtları, görselleri veya gömülü bağlantı rehberi yeniden yazılmaz.

```sh
# Python 3 standart kitaplığı yeterli; npm veya framework build'i gerekmez.
python3 website/build.py
python3 website/build.py --check
python3 website/serve.py --host 0.0.0.0 --port 4174
# Yerel adres: http://127.0.0.1:4174/OguzDows/

# Depodaki test ortamı / Pillow hazırken:
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -p 'test_website.py' -v
# Mevcut mobile/preview geliştirme test bağımlılıkları hazırken:
node --test website/tests/browser.test.mjs
```

Görünüm metinleri `website/build.py`, stiller `website/assets/site.css` içindedir. Başlık/description/canonical üretimi ve PC/APK/web download/hash değerleri değişmez `docs/releases/v2.0-release.json` makbuzuna bağlıdır. Güncel Pi imaj/checksum/envanter bağlantıları yalnız yayımlanmış, ayrı denetimi başarılı `docs/releases/v2.0-arm2-release.json` kaydıyla değiştirilir. ARM2 için gerçek Türkçe Xfconf/geri alma ve aynı kaynaklı native Welcome kanıtı da zorunludur; önceki `v2.0-arm1` imajını yeniden etiketleme reddedilir. Eski ARM1 kaydı ve sürüm notları arşiv olarak değişmez. İki yayının toplam checksum/manifest/kanıt bağlantıları birbirinden ayrıdır; eski 2.0 kaydı yeniden yazılmaz. URL veya sürüm değişirse yalnız metin değiştirip bırakma; sitemap, metadata, link ve tarayıcı testlerini de çalıştır.

Marka kartını isteğe bağlı Pillow + sistem DejaVu fontuyla yeniden üretmek için `website/make-social.py` vardır. JPEG/font/kodlayıcı sürümü çıktıyı değiştirebilir; kart yayın APK/ISO bütünlük kanıtı değildir. Hero’daki Boğaz görseli önceden açıklanmış AI duvar kâğıdı, telefon görseli gerçek kabul edilmiş 2.0 emülatör thumbnail’idir.

### Dal / main / birleştirme sınırı

Üretim için GitHub Pages kaynağı **`main` / `/docs`** seçilir. Yeni değişiklikler mevcut çalışma dalına push edilir; kullanıcı onaylı PR üzerinden `main`e birleştirilir. `main`e doğrudan push edilmez, ayrı `gh-pages` dalı açılmaz. `website/site.json` içindeki rehber kaynak dalı da `main`dir. İlk site kurulumu çalışma dalından sunulmuştu; ARM düzeltmesiyle README, indirmeler ve main güncellemesi birlikte yetkilendirildi. Pages ayarındaki kaynak dalı ile yayımlanan commit ayrıca GitHub API/deployment üzerinden doğrulanır; yerel önizleme, üretim dağıtımı sayılmaz.

### Vercel durumu

Bağlantı açıkken kişisel kapsamda proje listesi boş, takım sorgusu ise **Access denied** döndü. Yetki/plan varsayılıp tekrar yazma denenmedi; ücretli proje/alan adı kurulmadı. İleride Vercel istenirse Arena’daki bağlantının proje/takım kapsamını hesap sahibi gözden geçirmelidir. Bu kurulum Vercel’e bağımlı değildir.
