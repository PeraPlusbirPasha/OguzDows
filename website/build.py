#!/usr/bin/env python3
"""Dependency-free, deterministic public site. Never rebuild/relabel a release.

Only the fixed public-site outputs below are written under docs/. Existing
release records, guides, screenshots and product files are never rewritten.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
CONFIG = json.loads((SOURCE / 'site.json').read_text())
BASE = CONFIG['base_url']
REPO = CONFIG['repository']
RELEASE = json.loads((ROOT / 'docs/releases/v2.0-release.json').read_text())
TAG = 'v2.0'
RELEASE_URL = REPO + '/releases/tag/' + TAG
FILES = RELEASE['files']
GUIDE = REPO + '/blob/' + CONFIG['source_branch'] + '/'
APK = 'OguzDows-Mobile-2.0-Akinci-debug.apk'
WEB = 'OguzDows-Web-2.0-Akinci.tar.gz'
PAGES = {
    '': ('OğuzDows 2.0 Akıncı — Türkçe Linux, PC, Raspberry Pi ve launcher',
         'OğuzDows 2.0 Akıncı: Türkçe Xfce masaüstü, PC ve Raspberry Pi imajları, native telefon launcher’ı. Ücretsiz indirmeler, kurulum ve OğuzKöprü rehberi.'),
    'indir/': ('OğuzDows 2.0 indir — PC ISO, Raspberry Pi imajı ve launcher APK',
               'Cihazına uygun OğuzDows 2.0 Akıncı paketini seç. amd64/i386 ISO, Pi armhf/arm64 imajları ve debug launcher APK; özgün SHA-256 ve kurulum rehberleri.'),
    'pc/': ('PC için Türkçe Linux — OğuzDows 2.0 Akıncı ve Xfce',
            'Intel ve AMD bilgisayarlar için Türkçe Xfce masaüstü. OğuzDows 2.0 PC ISO, işlemci seçimi, RAM ölçümleri, canlı USB ve güvenli kurulum bilgileri.'),
    'raspberry-pi/': ('Raspberry Pi için Türkçe masaüstü — OğuzDows armhf ve arm64',
                     'OğuzDows 2.0 Raspberry Pi imajları: ARMv6 armhf ve ARM64, model/RAM seçimi ve ilk hesap. Deneysel port ve açık Zero siyah ekran sınırları.'),
    'telefon/': ('Türkçe telefon launcher’ı — OğuzDows Mobile 2.0 Akıncı',
                 'OğuzDows Mobile 2.0: native HOME, uygulamalar, widget, rehber ve yerel Rıfkı. Debug launcher APK, boş emülatör kurulumu ve açık ROM/SIM sınırları.'),
    'oguzkopru/': ('OğuzKöprü — PC, telefon ve Raspberry Pi arasında yerel bağlantı',
                   'OğuzKöprü/1 ile seçili dosyaları ve izinli salt ekranı yerel ağda paylaş. TLS, iki ekranda kod doğrulama ve dosya bazında alıcı onayı.'),
    'sss/': ('OğuzDows hakkında sık sorulan sorular — Ücretsiz indirme ve kurulum',
             'OğuzDows nedir, hangi dosyayı indirmeliyim, launcher ROM mu? PC/Pi/telefon, ücretsiz indirme, güvenlik, AI ve deneysel cihaz sorularına açık yanıtlar.'),
}


def url(path=''):
    return BASE + path


def route(path=''):
    return urlsplit(BASE).path + path


def link(href, text, cls=''):
    return f'<a href="{escape(href, quote=True)}"' + (f' class="{cls}"' if cls else '') + f'>{text}</a>'


def download(name, text, cls='button primary'):
    return link(FILES[name]['url'], text, cls)


def doc(path, text):
    return link(GUIDE + path, text)


def icon(name):
    shapes = {
        'pc': '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/>',
        'pi': '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 1v3m4-3v3m4-3v3M8 20v3m4-3v3m4-3v3M1 8h3m-3 4h3m-3 4h3m16-8h3m-3 4h3m-3 4h3"/><rect x="8" y="8" width="8" height="8" rx="1"/>',
        'phone': '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 5h4m-3 14h2"/>',
        'bridge': '<rect x="1" y="5" width="7" height="13" rx="2"/><rect x="16" y="5" width="7" height="13" rx="2"/><path d="M8 9h8m-3-3 3 3-3 3M16 15H8m3-3-3 3 3 3"/>',
        'arrow': '<path d="M5 12h14m-6-6 6 6-6 6"/>',
        'check': '<path d="m5 12 4 4L19 6"/>',
        'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 1v2m0 18v2M1 12h2m18 0h2M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
        'news': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h10M7 17h10m-4-6h4m-4 3h4"/><rect x="7" y="11" width="3" height="3"/>',
        'tools': '<path d="M14 6a4 4 0 0 0-5 5l-6 6 4 4 6-6a4 4 0 0 0 5-5l-3 3-4-4Z"/>',
        'cat': '<path d="M5 10 4 3l6 4h4l6-4-1 7a8 8 0 1 1-14 0Z"/><path d="M8 13h.01M16 13h.01m-6 4 2 1 2-1M2 15h4m12 0h4"/>',
        'shield': '<path d="m12 2 8 3v6c0 5-8 11-8 11S4 16 4 11V5Z"/><path d="m8 11 3 3 5-5"/>',
    }
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{shapes[name]}</svg>'


def callout(title, text, kind='note'):
    return f'<aside class="callout {kind}"><strong>{title}</strong><p>{text}</p></aside>'


def page_intro(kicker, title, lead):
    return f'<section class="page-intro wrap"><p class="eyebrow">{kicker}</p><h1>{title}</h1><p class="lead">{lead}</p></section>'


def action_row(*items):
    return '<div class="actions">' + ''.join(items) + '</div>'


def home():
    features = [
        ('sun', 'Tercihin gerçekten yansısın.', 'Koyu/açık görünüm yalnız Ayarlar’da kalmaz; desteklenen açık uygulamalara da iletilir. PrintScreen gerçek ekran görüntüsü aracını açar.'),
        ('news', 'Haber, Mağaza, gündelik hayat.', 'Resimli, tıklanabilir Haber; önce plan ve izin gösteren Mağaza. Flatpak ve GNOME Yazılımlar bileşenleri için mimariye uygun onarım akışı.'),
        ('tools', '16 araç, tek Atölye.', 'Notlar, dosya bulma, toplu yeniden adlandırma, checksum, resim, hesaplama ve daha fazlası. İhtiyaç olduğunda açılır; yeni bir arka plan indeksleyicisi değil.'),
        ('phone', 'Masaüstü karakteri, cep düzeni.', 'Native HOME, uygulama arama ve başlatma, kalıcı kısayollar, widget’lar, dokunmatik düzenler ve gerçek sistem Ayarları bağlantıları.'),
        ('cat', 'Rıfkı, bildiğin gibi.', 'Dokunmaya ve bağlama tepki veren yerel kedi rehber. Bulut model, mikrofon ve wake-word bu sürümde etkin değil; gizli AI faturası yok.'),
        ('bridge', 'Bağlantıda da söz sende.', 'OğuzKöprü ile seçili dosyalar ve salt ekran. İki ekranda kod doğrulama, yerel izin ve alıcı kabulü; uzaktan kontrol veya gizli eşitleme yok.'),
    ]
    cards = ''.join(f'<article class="feature"><span class="feature-icon">{icon(i)}</span><h3>{t}</h3><p>{d}</p></article>' for i, t, d in features)
    return f'''
<section class="hero wrap">
  <div class="hero-copy"><p class="eyebrow"><span class="live-dot"></span> 2.0 AKINCI · ŞİMDİ YAYINDA</p>
    <h1>OğuzDows.<br>Türkçe. Hafif.<br><em>Birbirine bağlı.</em></h1>
    <p class="lead">PC’de ve Raspberry Pi’de Türkçe bir Linux masaüstü. Telefonda native launcher. Hepsi <strong>Akıncı</strong>, hepsi senin onayınla.</p>
    {action_row(link(route('indir/'), '2.0’ı ücretsiz indir ' + icon('arrow'), 'button primary'), link(REPO, 'Kaynağı incele ↗', 'button secondary'))}
    <p class="fine-print">PC ISO · Pi imajı · Debug launcher APK<br>Telefon paketi ROM değildir. Pi portları deneyseldir.</p>
  </div>
  <figure class="hero-visual">
    <div class="visual-poster"><img src="{route('assets/bogaz-sabahi.jpg')}" width="480" height="270" alt="Boğaz Sabahı: OğuzDows’un AI üretimi kültür duvar kâğıdı" fetchpriority="high"><div class="poster-shade"></div><div class="poster-copy"><span class="overline">KÖKLERİNDEN GÜÇ ALIR.</span><strong>Özgürce<br>üretir.</strong><span class="poster-version">OĞUZDOWS 2.0 / AKINCI</span></div></div>
    <div class="phone-preview"><img src="{route('assets/oguzdows-mobile-v2.jpg')}" width="234" height="519" alt="2.0 native launcher’ın kabul edilen API35 emülatöründen gerçek ekranı"><span>Gerçek native HOME · API35 emülatör</span></div>
    <div class="connected-label">{icon('bridge')} <span>PC <b>·</b> Pi <b>·</b> Telefon<br><small>Birlikte, senin onayınla.</small></span></div>
    <figcaption>Arka görsel AI duvar kâğıdıdır, masaüstü ekranı değil. Telefon görseli gerçek emülatör kaydıdır; fiziksel cihaz testi değildir.</figcaption>
  </figure>
</section>
<section class="proof-strip wrap" aria-label="Yayın kanıtı">
  <div><strong>4 mimari</strong><span>amd64 · i386 · armhf · arm64</span></div><div><strong>24 + 20</strong><span>Native emülatör + JVM vakası</span></div><div><strong>26 dosya</strong><span>Ayrı runner’da tekrar indirildi / hash’lendi</span></div>{link(RELEASE_URL, 'Kanıtları gör ↗', 'text-link')}
</section>
<section class="section wrap"><div class="section-heading"><div><p class="eyebrow">AYNI KİMLİK, FARKLI CİHAZLAR</p><h2>Sen nerede üretiyorsan.</h2></div><p>Doğru mimariyi seç. Eski dosyaların adı değişmedi; dört imaj ve launcher 2.0 için yeniden derlendi.</p></div>
  <div class="platform-grid">
    <article class="platform-card"><span class="platform-icon">{icon('pc')}</span><span class="tag">PC</span><h3>Tanıdık, ama sana ait.</h3><p>Intel/AMD bilgisayarlar için Debian tabanlı Türkçe Xfce. Gerçek tema senkronu, native panel ve Atölye.</p>{link(route('pc/'), 'PC sürümünü keşfet ' + icon('arrow'), 'card-link')}</article>
    <article class="platform-card"><span class="platform-icon">{icon('pi')}</span><span class="tag">RASPBERRY PI · DENEYSEL</span><h3>Küçük kart, kendi yolu.</h3><p>ARMv6 armhf ve ARM64 için ayrı SD/USB imajları. Model, RAM ve ilk hesap rehberiyle.</p>{link(route('raspberry-pi/'), 'Pi için doğru imaj ' + icon('arrow'), 'card-link')}</article>
    <article class="platform-card"><span class="platform-icon">{icon('phone')}</span><span class="tag">TELEFON · DEBUG LAUNCHER</span><h3>Akıncı cebinde.</h3><p>Gerçek native HOME, kısayollar, widget’lar, rehber ve hareketli Rıfkı. Önce boş emülatörde dene.</p>{link(route('telefon/'), 'Launcher’ı tanı ' + icon('arrow'), 'card-link')}</article>
  </div>
</section>
<section class="section feature-section"><div class="wrap"><div class="section-heading"><div><p class="eyebrow">GÖRÜNÜŞÜN ÖTESİNDE</p><h2>Gündelik işler, kendi dilinde.</h2></div><p>Gösterişli bir kapaktan fazlası. Önceki sürümün 23 işlevi korunur; 2.0’da ikinci kez “yeni” diye sayılmaz.</p></div><div class="feature-grid">{cards}</div></div></section>
<section class="section wrap bridge-section"><div class="bridge-art" aria-label="PC, Pi ve telefon arasındaki onaylı bağlantı şeması"><span>{icon('pc')}PC</span><i></i><span class="bridge-center">{icon('shield')}OğuzKöprü / 1</span><i></i><span>{icon('phone')}Telefon / Pi</span></div><div><p class="eyebrow">AYNI AĞ, AYNI MASA</p><h2>Bağlanır.<br>Kontrolü devralmaz.</h2><p>Seçtiğin dosyayı sürükle. Kodu iki ekranda karşılaştır. Alıcı onaylasın. İstersen yalnız görüntüyü paylaş; uzaktan SMS, klavye veya yükleme yetkisi verme.</p>{link(route('oguzkopru/'), 'Bağlantı nasıl çalışır? ' + icon('arrow'), 'text-link')}</div></section>
<section class="section wrap"><div class="community-banner"><div><p class="eyebrow">BİRAZ ANADOLU. BİRAZ MERAK. BOLCA EMEK.</p><h2>Bir sonraki adımda sen de ol.</h2><p>Bir yıldızla görünür kıl, bir hata kaydıyla iyileştir. Denediğin donanımı ve kişisel veriden arındırılmış sonucu paylaş.</p></div><div class="actions vertical">{link(REPO, 'GitHub’da destekle ↗', 'button primary')}{link(REPO + '/issues', 'Hata / öneri bildir', 'button secondary')}</div></div></section>
'''


def file_card(name, title, subtitle, warning, icon_name):
    item = FILES[name]
    mib = item['size'] / 1024**2
    return f'''<article class="download-card"><div class="download-card-top">{icon(icon_name)}<span class="tag">{subtitle}</span></div><h2>{title}</h2><p>{warning}</p><p class="file-name">{name}</p><span class="file-size">{mib:,.1f} MiB · {item['size']:,} bayt</span>{action_row(download(name, 'Paketi indir ' + icon('arrow')), download(name + '.sha256', 'SHA-256 dosyası', 'button secondary'))}<details class="checksum"><summary>SHA-256 özetini göster</summary><code>{item['sha256']}</code><button type="button" class="copy-button" data-copy="{item['sha256']}" data-label="SHA-256 özeti">Özeti kopyala</button></details></article>'''


def downloads():
    cards = [
        file_card('OguzDows-amd64.iso', '64 bit bilgisayar', 'PC · AMD64', 'Intel ve AMD 64 bit x86. BIOS + 64 bit UEFI; canlı/kurucu 1 GiB+, günlük 2 GiB+, modern web için 4 GiB+ önerilir.', 'pc'),
        file_card('OguzDows-i386.iso', 'Gerçek 32 bit bilgisayar', 'PC · I386', 'i686/PAE; tarayıcı için SSE2. Yalnız BIOS. Canlı/kurucu 1 GiB+, günlük 2 GiB+ önerilir. Az RAM, tek başına 32 bit seçme nedeni değildir.', 'pc'),
        file_card('OguzDows-rpi-armhf.img.xz', 'Pi için armhf', 'RASPBERRY PI · DENEYSEL', 'Eski Zero/Pi 1 dahil ARMv6 kullanıcı alanı. 512 MB mini deneysel; 1 GB light. Pi 5 için değil. Zero siyah ekran bildirimi açık.', 'pi'),
        file_card('OguzDows-rpi-arm64.img.xz', 'Pi için arm64', 'RASPBERRY PI · DENEYSEL', 'Pi 4/400/5; uygun Zero 2/Pi 2 rev1.2/Pi 3 için alternatif. Günlük 2 GB+, modern web için 4 GB+ önerilir. Eski Zero/Pi 1’de açılmaz.', 'pi'),
        file_card(APK, 'Native telefon launcher’ı', '2.0.0-AKINCI · KOD 20', 'Debug imzalı normal uygulama; ROM/OTA/GSI değil. MinAPI29, kabul API35/x86_64/4 GiB emülatör. Önce boş emülatörde; günlük telefonun Telefon/SMS rollerini değiştirme.', 'phone'),
    ]
    return page_intro('RESMÎ 2.0 YAYINI · ÜCRETSİZ İNDİRME', 'Cihazına uygun<br><em>Akıncı’yı seç.</em>', 'Önce işlemci mimarisi, sonra RAM. İndirmeler doğrudan doğrulanmış GitHub Release dosyalarına gider; site büyük imajları yeniden barındırmaz.') + f'''
<div class="wrap">{callout('Önce yedek, sonra deneme.', 'USB/SD/hedef diske imaj yazmak verileri siler. Fiziksel PC/Pi/telefon kabulü yoktur. Pi imajı PC ISO’su veya evrensel ARM/telefon ROM’u değildir.', 'warning')}
<div class="download-grid">{''.join(cards)}</div>
<section class="section prose"><h2>İndir → doğrula → dene</h2><ol class="steps"><li><strong>Doğru paketi seç.</strong> {link(route('pc/'), 'PC mimarisi')}, {link(route('raspberry-pi/'), 'Pi modeli')} veya {link(route('telefon/'), 'boş telefon emülatörü')} rehberini oku.</li><li><strong>Paket ile checksum’unu aynı klasöre indir.</strong> Tek paket için ona ait <code>.sha256</code> dosyasını kullan.</li><li><strong>Özeti doğrula.</strong> Linux’ta aşağıdaki komutu çalıştır. Sonuç <code>OK</code> olmalı; uyuşmazsa dosyayı kullanma.</li></ol><pre><code>sha256sum -c OguzDows-amd64.iso.sha256
# Launcher için:
sha256sum -c {APK}.sha256</code></pre><p>PowerShell: <code>Get-FileHash .\\{APK} -Algorithm SHA256</code>. Sonucu gösterilen özetle birebir karşılaştır. Checksum, imzalı ISO veya kötü amaçlı yazılım taraması iddiası değildir.</p></section>
<section class="section prose"><h2>Rehberler, kanıtlar ve tasarım arşivi</h2><p>{download('SHA256SUMS', 'Birleşik SHA256SUMS', '')} dört imaj + üç APK + web, toplam sekiz dosyayı kapsar. Tümünü indirmediysen eksik dosya uyarılarını başarı sanma.</p><ul class="resource-list"><li>{download('release-manifest.json', 'Kaynak, dosya boyutları ve hash manifesti', '')}</li><li>{download('test-evidence.tar.gz', '26 JSON + 1 gerçek paylaşım JPEG’i: ham test kanıtları', '')}</li><li>{download('BAGLANTI-REHBERI.md', 'PC–Pi–telefon bağlantı rehberi', '')}</li><li>{link(RELEASE_URL, 'Tam sürüm notları ve diğer dosyalar ↗')}</li></ul><p><strong>Yalnız geliştirici/test için:</strong> instrumentation ve etkisiz fixture APK’ları günlük uygulama değildir. Tam yayında ayrıca bulunurlar.</p><p><strong>Tarayıcı tasarım laboratuvarı:</strong> {download(WEB, 'statik web arşivi', '')} · {download(WEB + '.sha256', 'SHA-256', '')}. Bu ayrı tasarım/yerel veri arşivi; APK, ROM, SIM veya etkin AI sunucusu değildir.</p></section>
</div>'''


def pc():
    return page_intro('PC · DEBIAN TABANLI TÜRKÇE XFCE', 'Bilgisayarında<br><em>kendi karakteri.</em>', 'OğuzDows 2.0 Akıncı, Intel ve AMD bilgisayarlar için Türkçe bir Linux masaüstü sunar. Hafif Xfce, native araçlar ve açık kurulum adımlarıyla.') + f'''
<div class="wrap content-layout"><article class="prose"><h2>Hangi PC ISO’sunu indirmeliyim?</h2><p><strong>amd64</strong>, yalnız AMD değil, Intel ve AMD’nin 64 bit x86 işlemcileri içindir. Tabanı Debian trixie; BIOS ve 64 bit UEFI akışları vardır. <strong>i386</strong> gerçek 32 bit i686/PAE bilgisayarlar içindir; Debian bookworm ve yalnız BIOS kullanır. Tarayıcı için SSE2 gerekir.</p><p>Düşük RAM tek başına 32 bit imaj seçme gerekçesi değildir. Apple Silicon/genel ARM bilgisayarlar için bu PC ISO’ları uygun değildir; Pi dosyasını da genel ARM ISO’su sanma.</p><h2>Canlı USB ile başla</h2><ol><li>ISO’yu ve ona ait checksum’u {link(route('indir/'), 'indirme sayfasından')} al, özeti doğrula.</li><li>Yedeğini aldıktan sonra 4 GB+ USB’ye imaj olarak yaz. Doğru aygıtı seçtiğinden emin ol.</li><li>Önce canlı ortamda görüntü, ağ ve sesi dene. Secure Boot kapalı olmalı; 32 bit UEFI desteklenmez.</li><li>Kuruluma karar verirsen hedef diskte en az 12 GiB alan ve kişisel hesap gerekir. Disk yazma verileri silebilir.</li></ol><p>Canlı PC hesabı <code>oguz / oguz</code>; parolasız yönetici yetkisi yalnız canlı ortama aittir. Kurulu PC kişisel hesap oluşturur ve canlı hesabı temizler. Yeni ISO mevcut kurulumunu kendiliğinden yükseltmez.</p><h2>Gündelik kullanımda neler var?</h2><p>Altı geri alınabilir Xfce düzeni, gerçek uygulama koyu/açık senkronu, PrintScreen, optimize Thunar kenar/geometrisi, native görev çubuğu ve Dock. Resimli Haber’de makaleyi açabilir; Mağaza’da plan ve izinleri kurulumdan önce inceleyebilirsin. Atölye 16 yerel araç sunar.</p><p>Flatpak/GNOME Yazılımlar bileşen onarımı uygun mimaride mevcut imzalı APT kaynaklarını kullanır. Sistem işlemi Polkit ve son kullanıcı onayı ister; Flathub ayrıca izinlidir. Bu, bütün Flathub uygulamalarının veya her donanımın desteklendiği anlamına gelmez. Altı tarz, gerçek GNOME/Plasma oturumu değildir.</p><h2>RAM: ölçümü, koşuluyla oku</h2><div class="table-scroll"><table><caption>2.0 ISO’larından tam Xfce; en yüksek kullanım, decimal MB</caption><thead><tr><th scope="col">İmaj</th><th scope="col">512 MiB VM</th><th scope="col">1024 MiB VM</th><th scope="col">2048 MiB VM</th></tr></thead><tbody><tr><th scope="row">amd64</th><td>297.1</td><td>490.2</td><td>501.7</td></tr><tr><th scope="row">i386</th><td>195.6</td><td>407.1</td><td>479.8</td></tr></tbody></table></div><p>Ağsız QEMU/TCG, 2 sanal CPU/std VGA; 120 saniye yerleşme ve 5 saniye aralıklı 6 örnek. <code>MemTotal − MemAvailable</code>; Rıfkı/Mağaza/Haber/compositor kapalı. Bu fiziksel performans veya modern tarayıcı konforu ölçümü değildir. Canlı/kurucu 1 GiB+, günlük 2 GiB+, modern web/ofis için 4 GiB+ önerilir.</p>{callout('Sınırlar açık.', 'Gerçek ISO içeriğinden hedef disk/çekirdek/systemd ve Xfce kabulü geçti. Tam Calamares GUI/LUKS, fiziksel PC ve her sürücü/firmware kabulü yapılmış sayılmaz. 512 MiB’de boşta açılması rahat kurulum/tarayıcı garantisi değildir.')}<p>{doc('docs/TEKNIK-REHBER.md', 'Teknik rehber ve eski donanım teşhisi ↗')} · {link(RELEASE_URL, 'Yöntem ve tam sürüm kanıtı ↗')}</p></article><aside class="side-card"><span class="platform-icon">{icon('pc')}</span><h2>Önce dene,<br>sonra karar ver.</h2><p>64 bit bilgisayarlar için genellikle amd64. Mimarini doğrulamadan dosya seçme.</p>{link(route('indir/'), 'PC paketlerini gör ' + icon('arrow'), 'button primary')}<hr><p class="small">ISO’nun iç sürümü 2.0; kaynak <code>5a44de0</code>. Eski 1.2 dosyası yeniden adlandırılmadı.</p></aside></div>'''


def pi():
    return page_intro('RASPBERRY PI · DENEYSEL PORT', 'Küçük kartında<br><em>Türkçe bir masa.</em>', 'OğuzDows 2.0, Pi için ayrı armhf ve arm64 SD/USB imajları sunar. Mimari, kart modeli ve RAM farklarını saklamadan.') + f'''
<div class="wrap">{callout('Önemli: Zero siyah ekran bildirimi açık.', 'İlk nesil Zero/Zero W’de hesap ekranı sonrası siyahlık giderilmiş sayılmaz. Yeni imajlar fiziksel kartlarda doğrulanmadı; ARM kullanıcı-QEMU/Xvfb başarısı gerçek LightDM/PAM/GPU/SD veya 512 MB performans kabulü değildir.', 'warning')}</div>
<div class="wrap content-layout"><article class="prose"><h2>Kartına göre imaj seç</h2><div class="table-scroll"><table><caption>Temel mimari rehberi; hiçbir satır fiziksel kart kabulü iddiası değildir</caption><thead><tr><th scope="col">Model</th><th scope="col">İmaj / öneri</th></tr></thead><tbody><tr><th scope="row">Zero / Zero W / Pi 1</th><td>armhf, ARMv6. 512 MB mini deneysel; 256 MB günlük masaüstü için önerilmez.</td></tr><tr><th scope="row">Pi 2 rev1.0 / 1.1</th><td>armhf, ARMv7; 1 GB light.</td></tr><tr><th scope="row">Zero 2 / Pi 2 rev1.2 / Pi 3</th><td>Az RAM’de armhf; 64 bit uygulama gerektiğinde arm64 alternatifi. 512 MB mini, 1 GB light.</td></tr><tr><th scope="row">Pi 4 / 400 / 5</th><td>arm64; günlük 2 GB+, modern web/ofis için 4 GB+ önerilir. Pi 5 armhf hedefi değildir.</td></tr></tbody></table></div><p>armhf Raspbian bookworm, ARMv6 uyumlu kullanıcı alanı; arm64 Debian/Raspberry Pi bookworm tabanlıdır. Eski Zero/Pi 1/erken Pi 2’de arm64 açılmaz. Pi 5’in özel <code>2712</code> çekirdeği korunur. Teknik <code>VERSION_ID=12</code> tabandır; ayrı ürün alanı <code>OGUZDOWS_VERSION_ID=2.0</code> olur.</p><h2>İlk açılışa hazırlan</h2><ol><li>Doğru <code>.img.xz</code> ve checksum’u indirip sıkıştırılmış dosyanın özetini doğrula.</li><li>Raspberry Pi Imager’da özel imaj seç; 16 GB+ SD/USB’ye yaz. Tercihen 32 GB A1/A2 kart kullan. Yazma hedefi siler.</li><li><strong>Imager kullanıcı/SSH özelleştirmelerini uygulama.</strong> Portun kendi Türkçe ilk hesap adımını kullan.</li><li>Bölüm büyütülürken gücü kesme. Uygun güç kaynağı ve soğutma kullan.</li></ol><p>Pi’de ortak <code>oguz/oguz</code>, otomatik giriş veya parolasız sudo yoktur. SSH varsayılan kapalıdır. Pi imajı PC ISO’su veya evrensel ARM/telefon ROM’u değildir; diğer SBC’lere/telefonlara yazma.</p><h2>Düşük RAM’de dürüst beklenti</h2><p>armhf’de eski ARMv6’ya modern Firefox dayatılmaz; NetSurf temel web içindir ve güncel JavaScript sitelerinde tam uyumluluk sunmaz. arm64’te 1 GiB ve altında NetSurf, daha yüksek RAM’de kurulu Firefox seçilir. Büyük ofis belgeleri, çok sekme ve yüksek çözünürlüklü video için garanti yoktur.</p><p>Türkçe Xfce, native Mağaza/Haber, Atölye ve OğuzKöprü ortak kaynakla gelir. Pi’ye özgü çekirdek/firmware/ilk hesap yolu korunur; PC Calamares/GRUB akışı karta taşınmaz. İsteğe bağlı Flatpak altyapısı arm64 tarifindedir; armhf’de bütün masaüstü/Flathub uygulamaları varmış gibi davranılmaz.</p><h2>Ne doğrulandı?</h2><p>ARM1176/Cortex-A53 kullanıcı-QEMU + host Xvfb’de 13 özellik grubu, 69 varlık hash’i, hedef Python/GTK/ELF, root olmayan tam Xfce ve süreç temizliği kapıları geçti. Bunlar fiziksel Pi boot/GPU/performans ölçümü değildir.</p><p>{doc('raspberrypi/README.md', 'Ayrıntılı model, profil ve kurulum rehberi ↗')} · {doc('docs/PI-ZERO-OTURUM.md', 'Zero oturum teşhisi ↗')}</p></article><aside class="side-card"><span class="platform-icon">{icon('pi')}</span><h2>Tek dosya,<br>her karta değil.</h2><p>Model ve revizyonu kontrol et. SD kartını yazmadan önce mutlaka yedekle.</p>{link(route('indir/'), 'Pi imajlarını gör ' + icon('arrow'), 'button primary')}<hr><p class="small">Compute Module/500, taşıyıcı kart, eMMC/USB ve firmware varyantları ayrıca test ister.</p></aside></div>'''


def phone():
    return page_intro('TELEFON · NATIVE HOME / DEBUG APK', 'Akıncı,<br><em>cebine göre.</em>', 'Kotlin/Compose native launcher: uygulamalar, kısayollar, gerçek widget’lar ve hareketli yerel Rıfkı. Masaüstü karakteri, dokunmatik düzenlerle.') + f'''
<div class="wrap">{callout('Launcher APK’sı, ROM değil.', 'Normal debug imzalı uygulamadır; cihazın işletim sistemini, global SystemUI’ını veya güvenli PIN/biyometrik kilidini değiştirmez. Önce boş emülatörde dene; günlük fiziksel telefonun varsayılan Telefon/SMS rollerini bu deneysel paketle değiştirme.', 'warning')}</div>
<div class="wrap content-layout"><article class="prose"><h2>Gerçekte neler yapar?</h2><p>Gerçek HOME rolüyle açılan native ana ekran, profil farkındalıklı uygulama envanteri, arama/başlatma, iki kalıcı kısayol sayfası ve AppWidgetHost. Altı masaüstü kimliğinin dokunmatik düzenleri, duvar kâğıdına uyumlu Aero görünümü, kendi kaydırma panelleri, medya sesi ve uygulama parlaklığı vardır.</p><p>Ayarlar gerçek sistem sayfalarına bağlanır. Sistem rehberine izinle erişim ve kişi ekleme, Java Telefon/SMS/Mağaza modülleri korunur. HOME, Telefon, SMS ve yardımcı rolleri birbirinden ayrıdır; biri diğerine yetki vermez. Ücretli çağrı/SMS ve kişi/kurulum işlemleri son yerel kullanıcı onayına bağlıdır.</p><h2>İlk deneme: boş emülatör</h2><p>MinAPI29; gerçek kabul API35 / Google APIs / x86_64 / Pixel6 QEMU, 4 GiB RAM / 256 MiB heap ortamındadır. 4–6 GB telefon hedefi fiziksel RAM/FPS/pil ölçümü değildir.</p><ol><li>Günlük verisi ve SIM’i olmayan, tek kullanımlık bir emülatör hazırla.</li><li>APK’yı ve SHA-256 dosyasını indir, özeti kontrol et.</li><li>Aşağıdaki komutla kur; HOME rolünü sistem seçicisinden ayrıca seç.</li><li>Rehber, arama/SMS ve ekran paylaşımı izinlerini yalnız denemek istediğin iş için ver.</li></ol><pre><code>adb install -t {APK}</code></pre><p>Root/flash veya bootloader açma gerekmez. Debug anahtarı koşular arasında değişebilir; güncelleyemediğinde eski veriyi silerek zorlamadan önce yedek ve imza kontrolü yap. Test APK’sı ile fixture paketi günlük uygulama değildir.</p><h2>Telefon ve bağlantı sınırı</h2><p>Gerçek emülatör Telecom/SMS provider, sanal çağrı ve SMS, sistem yükleyicisi ve F-Droid doğrulama akışları sınandı. Bu fiziksel SIM, operatör, acil arama, MMS/RCS veya bütün OEM/izin/rol matrisinin kabulü değildir. GMS/Play/Integrity/bankacılık/DRM veya tüm APK uyumluluğu garanti edilmez.</p><p>OğuzKöprü ekran paylaşımı her başlangıçta taze MediaProjection sistem seçimi ve foreground bildirim gerektirir. İptal, kilit ve erişim kaybında durur. Salt görüntü aktarır; uzaktan çağrı/SMS/yükleyici veya giriş yetkisi yoktur.</p><h2>Rıfkı: yerel ve açık sözlü</h2><p>Kedi hareket, dokunma ve bağlama tepki verir; bu sürümde üretken bulut model, mikrofon, ASR/TTS veya wake-word etkin değildir. Web tasarım yüzeyi, gerçek native launcher ya da etkin model sunucusu yerine gösterilmez.</p>{callout('Kabul ve açık kararlılık kaydı.', '24 native + 20 JVM vaka geçti. Kabulde ürün ANR/çökmesi yoktu; 2205 ms HWUI beklemesi ve aynı kaynaklı ayrı koşuda launcher otomasyon hatası kaydı vardır. Kalıcı ANR çözümü veya fiziksel kararlılık iddia edilmez.')}<p>{doc('mobile/INSTALL.md', 'Ayrıntılı emülatör kurulumu ↗')} · {doc('mobile/VERIFICATION.md', 'Kabul ve başarısızlık geçmişi ↗')}</p></article><aside class="side-card native-card"><img src="{route('assets/oguzdows-mobile-v2.jpg')}" width="234" height="519" alt="Kabul edilmiş 2.0 native HOME ekranı, gerçek API35 emülatörü"><p class="small">Gerçek native emülatör thumbnail’i. Fiziksel telefon veya web tasarım maketi değil.</p>{download(APK, 'Debug launcher indir ' + icon('arrow'))}{download(APK + '.sha256', 'SHA-256 dosyası', 'text-link')}</aside></div>'''


def bridge():
    return page_intro('OĞUZKÖPRÜ / 1 · ONAYLI YEREL BAĞLANTI', 'Aynı ağ.<br><em>Aynı masa.</em>', 'PC, Raspberry Pi ve telefon arasında seçilmiş dosyalar ile izinli salt ekran. İnternet rölesi, gizli eşitleme ve uzaktan kontrol olmadan.') + f'''
<div class="wrap content-layout"><article class="prose"><h2>İlk eşleştirme</h2><ol class="steps"><li><strong>Aynı güvenilir yerel ağa bağlan.</strong> PC/Pi menüsünden OğuzKöprü’yü; telefonda Dosyalar / OğuzKöprü’yü aç. Her iki tarafta 2.0 paketlerini kullan.</li><li><strong>Bir masa aç ve daveti aktar.</strong> Hesap oluşturma veya gizli ağ keşfi yoktur. Davet ve onay pencereleri 120 saniyedir.</li><li><strong>İki ekrandaki sekiz haneli kodu birebir karşılaştır.</strong> Uyuşmuyorsa onaylama. Eşleşmeyi yerel olarak sen onaylarsın.</li><li><strong>Dosyayı seç veya sürükle.</strong> Alıcı her dosyayı ayrıca kabul eder. Seçili özel kopya ve SHA-256 doğrulaması kullanılır; dosya kendiliğinden açılmaz/çalıştırılmaz.</li></ol><h2>Ölçülü sınırlar</h2><dl class="limits-grid"><div><dt>Dosya başına</dt><dd>128 MiB</dd></div><div><dt>Kuyruk</dt><dd>256 MiB / 8 öğe</dd></div><div><dt>Eş sayısı</dt><dd>2</dd></div><div><dt>Oturum</dt><dd>15 dakika</dd></div></dl><p>Ürün sürümü 2.0; köprü protokolü hâlâ 1’dir. Özel IPv4, sertifika-pinned TLS≥1.2 ve yerel onay kullanılır. İnternet portu açma/yönlendirme veya bulut hesabı gerekmez; güvenmediğin bir ağda masayı açma.</p><h2>Ekran paylaşımı: yalnız görüntü</h2><p>Telefon kaynağında her başlangıçta gerçek MediaProjection sistem seçimi ve son sistem onayı gerekir; foreground bildirim görünür. İptal, kilit ve erişim kaybında paylaşım durur. PC/Pi kaynağında doğrulanabilen kilitsiz X11 gerekir; bilinmeyen kilit veya Wayland reddedilir.</p><p>Telefon en çok 2 fps, PC/Pi en çok 1 fps; en çok 1280 piksel / 512 KiB JPEG. Bu video konferans, akıcı oyun yayını veya performans garantisi değildir.</p>{callout('Köprü ne yapmaz?', 'Ses/mikrofon iletmez. Uzaktan fare-klavye, rehber/SMS/Telecom/yükleyici yetkisi vermez. Otomatik kurulum veya Huawei protokol uyumluluğu iddia etmez. Eski 1.2 imajına kendiliğinden eklenmez.')}<h2>Gerçek denetim, doğru kapsam</h2><p>Kabulde dört gerçek dosya iki yönde taşındı; bağımsız aynı hash makbuzları karşılaştırıldı. Native TLS, gerçek MediaProjection iptal/taze izin/foreground/JPEG/durdurma sınandı. ARM host/GTK ve kullanıcı-QEMU testleri fiziksel cihaz/GPU/SD performansı sayılmaz.</p><p>{download('BAGLANTI-REHBERI.md', 'Yayınla gelen aynı bağlantı rehberini indir ↗', '')} · {link(RELEASE_URL, 'Sürüm ve güvenlik sınırları ↗')}</p></article><aside class="side-card"><span class="platform-icon">{icon('shield')}</span><h2>Önce kod.<br>Sonra onay.</h2><p>Uzak bir eş, telefonunun veya bilgisayarının yetkilisi olmaz. Son karar her zaman yerel cihazdadır.</p>{link(route('indir/'), '2.0 paketlerini gör ' + icon('arrow'), 'button primary')}</aside></div>'''


FAQ = [
    ('OğuzDows nedir?', 'OğuzDows; PC ve Raspberry Pi’de Türkçe Xfce masaüstü, telefonda ayrı native launcher sunan bir projedir. 2.0 sürümünün adı Akıncı’dır. PC/Pi dosyaları farklı mimarilere aittir; telefon APK’sı işletim sistemi imajı değildir.'),
    ('OğuzDows ücretsiz mi?', 'Bu sitedeki 2.0 dosyaları GitHub Releases üzerinden ücretsiz indirilir, indirmek için GitHub hesabı gerekmez. Bu, mobil operatör/çağrı/SMS, internet erişimi veya üçüncü taraf uygulama ve hizmetlerin ücretsiz olduğu anlamına gelmez.'),
    ('Bir Windows sürümü mü?', 'Hayır. PC masaüstü Debian ve Xfce tabanlıdır; tanıdık düzenler gerçek Windows değildir. Bütün EXE/APK, oyun, sürücü ve donanımların çalışacağı garanti edilmez. Üçüncü taraf bileşenlerin köken ve lisansları korunur.'),
    ('64 bit bilgisayarımda az RAM var; i386 mi seçmeliyim?', 'Yalnız RAM yüzünden 32 bit seçme. Önce işlemci mimarisini doğrula. amd64, Intel ve AMD 64 bit x86 içindir; i386 gerçek i686/PAE bilgisayarlar içindir. Canlı/kurucu 1 GiB+, günlük 2 GiB+, modern web için 4 GiB+ önerilir.'),
    ('Pi Zero’da sorunsuz çalışır mı?', 'Garanti verilmiyor. armhf eski ARMv6 için hazırlanır, ancak ilk Zero/Zero W’de hesap sonrası siyah ekran bildirimi açıktır. Fiziksel Pi boot/LightDM/PAM/GPU/SD ve 512 MB performans kabulü yoktur; 256 MB günlük masaüstü için önerilmez.'),
    ('Telefon APK’sı ROM mu; bootloader açmam gerekir mi?', 'Hayır. Normal debug imzalı launcher uygulamasıdır; root, flash veya bootloader açma gerekmez. SystemUI ve güvenli sistem kilidinin yerini alamaz. Önce boş emülatörde dene; günlük telefonun varsayılan Telefon/SMS uygulamasını bu deneysel paketle değiştirme.'),
    ('Gerçek telefon/SIM veya bankacılık kabulü var mı?', 'Hayır. API35 x86_64 emülatörde native HOME, widget, Telecom/SMS provider, sistem yükleyicisi, TLS ve MediaProjection akışları sınandı. Fiziksel SIM/acil çağrı, her OEM, GMS/Play/Integrity/bankacılık/DRM garantisi yoktur.'),
    ('Rıfkı bulut AI mı; mikrofonu dinler mi?', '2.0’da Rıfkı yerel ve kural tabanlıdır. Üretken bulut model, mikrofon, ASR/TTS ve wake-word etkin değildir; bu site de model sunucusu çalıştırmaz. Sesli/bulut yardımcı yol haritası bitmiş sayılmaz.'),
    ('Eski sürümüm kendiliğinden 2.0’a yükselir mi?', 'Hayır. Yeni imaj mevcut kurulumları veya eski 1.2 dosyalarını değiştirmez. Önce yedek al, sürüm notlarını oku. Önceki 1.0.0, 1.1 ve 1.2 yayınları korunur; eski imajlar 2.0 diye yeniden adlandırılmadı.'),
    ('Site çerez, reklam veya analiz sayacı kullanıyor mu?', 'Bu statik site reklam, analiz SDK’sı, üçüncü taraf font, form veya çerez eklemez; tarayıcıdan otomatik API/model isteği göndermez. GitHub Pages ve GitHub indirmelerinin kendi standart barındırma/erişim günlükleri bu iddiaya dahil değildir.'),
    ('Nasıl destek olurum?', 'GitHub’da projeye yıldız verebilir; gerçek donanım sonuçlarını model, mimari, sürüm ve kişisel veriden arındırılmış hata çıktısıyla issue olarak paylaşabilirsin. Siteyi ilgili bir toplulukta kendi isteğinle paylaş; sahte yorum, satın alınmış bağlantı veya spam yok.'),
]


def faq():
    answers = ''.join(f'<details class="faq-item"><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q, a in FAQ)
    return page_intro('KISA SORU, AÇIK YANIT', 'Merak ettiklerin.<br><em>Süslemeden.</em>', 'Bir paketi indirmeden önce ne olduğunu, ne olmadığını ve hangi testin neyi kanıtladığını bil.') + f'<section class="wrap faq-list">{answers}<p class="prose">Aradığın yanıt burada yok mu? {link(REPO + "/issues", "GitHub’da sor / hata bildir ↗")}</p></section>'


def nav(current):
    entries = [('indir/', 'İndir'), ('pc/', 'PC'), ('raspberry-pi/', 'Raspberry Pi'), ('telefon/', 'Telefon'), ('oguzkopru/', 'OğuzKöprü'), ('sss/', 'SSS')]
    links = ''.join(f'<a href="{route(path)}"' + (' aria-current="page"' if current == path else '') + f'>{title}</a>' for path, title in entries)
    return f'''<header class="site-header"><div class="wrap header-inner"><a href="{route()}" class="brand" aria-label="OğuzDows ana sayfa"><img src="{route('web/logo.svg')}" width="36" height="36" alt=""><span>OğuzDows<small>2.0 · AKINCI</small></span></a><nav aria-label="Ana menü" class="desktop-nav">{links}</nav><details class="mobile-menu"><summary>Menü <span aria-hidden="true">+</span></summary><nav aria-label="Mobil menü">{links}</nav></details>{link(REPO, 'GitHub ↗', 'github-link')}</div></header>'''


def footer():
    share = 'OğuzDows 2.0 Akıncı: Türkçe PC/Pi masaüstü + native debug launcher. Onaylı yerel OğuzKöprü. Ücretsiz indirmeler ve açık test sınırları: ' + BASE
    return f'''<footer class="site-footer"><div class="wrap footer-grid"><div><a class="brand" href="{route()}"><img src="{route('web/logo.svg')}" width="32" height="32" alt=""><span>OğuzDows<small>KÖKLERİNDEN GÜÇ ALIR.</small></span></a><p>Biraz Anadolu. Biraz merak.<br>Bolca emek.</p></div><nav aria-label="Kaynaklar"><strong>Keşfet</strong>{link(route('indir/'), 'İndirmeler')}{link(RELEASE_URL, '2.0 sürüm notları ↗')}{link(REPO, 'Kaynak kodu ↗')}{link(REPO + '/issues', 'Hata / öneri ↗')}</nav><nav aria-label="Rehberler"><strong>Birlikte çalışır</strong>{link(route('pc/'), 'PC kurulumu')}{link(route('raspberry-pi/'), 'Raspberry Pi')}{link(route('telefon/'), 'Native launcher')}{link(route('oguzkopru/'), 'OğuzKöprü')}</nav><div><strong>Görünür kıl.</strong><p>İlgili bir toplulukta, kendi sesinle paylaş. Otomatik gönderi veya takip yok.</p><button class="copy-button" type="button" data-copy="{escape(share, quote=True)}" data-label="Tanıtım metni">Tanıtım metnini kopyala</button><span class="copy-status" role="status" aria-live="polite"></span></div></div><div class="wrap footer-bottom"><p>Debian / Raspberry Pi kaynakları ve üçüncü taraf lisansları korunur. Telefon APK’sı ROM değildir. Pi portları deneyseldir.</p><p>Statik, hafif, reklamsız. {link(route('sss/'), 'Sınırlar ve gizlilik')}</p></div></footer>'''


def structured_data(path, title, description):
    nodes = [
        {'@type': 'Organization', '@id': BASE + '#proje', 'name': 'OğuzDows', 'url': BASE,
         'logo': url('web/logo.svg'), 'sameAs': [REPO]},
        {'@type': 'WebSite', '@id': BASE + '#website', 'url': BASE, 'name': 'OğuzDows', 'inLanguage': 'tr-TR',
         'publisher': {'@id': BASE + '#proje'}},
        {'@type': 'WebPage', '@id': url(path) + '#page', 'url': url(path), 'name': title, 'description': description,
         'inLanguage': 'tr-TR', 'isPartOf': {'@id': BASE + '#website'}},
    ]
    if path:
        label = dict([('indir/', 'İndir'), ('pc/', 'PC'), ('raspberry-pi/', 'Raspberry Pi'), ('telefon/', 'Telefon'), ('oguzkopru/', 'OğuzKöprü'), ('sss/', 'SSS')])[path]
        nodes.append({'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'OğuzDows', 'item': BASE},
            {'@type': 'ListItem', 'position': 2, 'name': label, 'item': url(path)}]})
    if path in ('', 'pc/', 'indir/'):
        nodes.append({'@type': 'SoftwareApplication', '@id': BASE + '#masaustu', 'name': 'OğuzDows 2.0 Akıncı',
                      'applicationCategory': 'DesktopEnhancementApplication', 'operatingSystem': 'Debian Linux / Raspberry Pi OS',
                      'softwareVersion': '2.0', 'url': url('pc/'), 'downloadUrl': FILES['OguzDows-amd64.iso']['url'],
                      'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'TRY', 'url': url('indir/')}})
    if path == 'telefon/':
        nodes.append({'@type': 'SoftwareApplication', '@id': BASE + '#launcher', 'name': 'OğuzDows Mobile 2.0 Akıncı debug launcher',
                      'applicationCategory': 'UtilitiesApplication', 'operatingSystem': 'Android 10+', 'softwareVersion': '2.0.0-akinci',
                      'description': 'Debug launcher APK; ROM değildir. Kabul API35 x86_64 emülatör; fiziksel telefon/SIM kabulü yoktur.',
                      'downloadUrl': FILES[APK]['url'], 'url': url(path),
                      'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'TRY', 'url': url('indir/')}})
    # No invented ratings, reviews, license, download counts or social accounts.
    return json.dumps({'@context': 'https://schema.org', '@graph': nodes}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')


def document(path, title, description, body, *, not_found=False):
    canonical = url(path)
    ld = '' if not_found else structured_data(path, title, description)
    ld_hash = base64.b64encode(hashlib.sha256(ld.encode()).digest()).decode()
    csp = f"default-src 'none'; img-src 'self' data:; style-src 'self'; script-src 'self' 'sha256-{ld_hash}'; font-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    verification = CONFIG.get('google_site_verification', '')
    verification_tag = f'<meta name="google-site-verification" content="{escape(verification, quote=True)}">' if verification else ''
    canonical_tag = '' if not_found else f'<link rel="canonical" href="{canonical}">'
    return f'''<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}"><title>{escape(title)}</title><meta name="description" content="{escape(description, quote=True)}"><meta name="robots" content="{'noindex,follow' if not_found else 'index,follow,max-image-preview:large'}">{canonical_tag}{verification_tag}<meta name="theme-color" content="#f7f5f0"><meta name="color-scheme" content="light"><meta property="og:type" content="website"><meta property="og:site_name" content="OğuzDows"><meta property="og:locale" content="tr_TR"><meta property="og:title" content="{escape(title, quote=True)}"><meta property="og:description" content="{escape(description, quote=True)}"><meta property="og:url" content="{canonical}"><meta property="og:image" content="{url('web/oguzdows-akinci.jpg')}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="OğuzDows 2.0 Akıncı — PC, Raspberry Pi ve native launcher"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{escape(title, quote=True)}"><meta name="twitter:description" content="{escape(description, quote=True)}"><meta name="twitter:image" content="{url('web/oguzdows-akinci.jpg')}"><link rel="icon" type="image/svg+xml" href="{route('web/logo.svg')}"><link rel="stylesheet" href="{route('web/site.css')}"><script src="{route('web/site.js')}" defer></script>{'<script type="application/ld+json">' + ld + '</script>' if ld else ''}</head><body><a class="skip-link" href="#icerik">İçeriğe geç</a>{nav(path)}<main id="icerik">{body}</main>{footer()}</body></html>
'''


def outputs():
    parsed = urlsplit(BASE)
    if (parsed.scheme != 'https' or not parsed.hostname or not BASE.endswith('/')
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or not RELEASE['published'] or RELEASE['tag'] != TAG or RELEASE['asset_count'] != 26
            or RELEASE['source_revision'] != '5a44de0dde676d901a32be40d631d481e213439d'):
        raise ValueError('Canonical URL and actual public 2.0 release must be valid.')
    verification = CONFIG.get('google_site_verification', '')
    if verification and not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', verification):
        raise ValueError('Only an actual Search Console HTML-tag verification value is accepted.')
    bodies = {'': home, 'indir/': downloads, 'pc/': pc, 'raspberry-pi/': pi, 'telefon/': phone, 'oguzkopru/': bridge, 'sss/': faq}
    result = {}
    for path, (title, description) in PAGES.items():
        result[path + 'index.html'] = document(path, title, description, bodies[path]()).encode()
    result['404.html'] = document('', 'Sayfa bulunamadı — OğuzDows', 'Bu sayfa bulunamadı. OğuzDows 2.0 Akıncı indirmelerine veya ana sayfaya dön.',
                                 page_intro('404 · BİR YOL AYRIMI', 'Bu sayfa yok.<br><em>Akıncı burada.</em>', 'Aradığın adres değişmiş veya yanlış yazılmış olabilir.') +
                                 '<div class="wrap section">' + action_row(link(route(), 'Ana sayfaya dön', 'button primary'), link(route('indir/'), 'İndirmeler', 'button secondary')) + '</div>', not_found=True).encode()
    # Project Pages robots.txt is below an origin subpath. It is informative,
    # not falsely described as control over the owner's origin-root robots.txt.
    result['robots.txt'] = ('# Project Pages: crawler directives apply only when this file is at the origin root.\n'
                            'User-agent: *\nAllow: /\nSitemap: ' + url('sitemap.xml') + '\n').encode()
    result['sitemap.xml'] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                             ''.join('  <url><loc>' + xml_escape(url(path)) + '</loc></url>\n' for path in PAGES) + '</urlset>\n').encode()
    result['.nojekyll'] = b''
    for name in ('site.css', 'site.js', 'logo.svg', 'oguzdows-akinci.jpg'):
        result['web/' + name] = (SOURCE / 'assets' / name).read_bytes()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if generated public outputs are stale; write nothing.')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs')
    args = parser.parse_args()
    expected = outputs()
    stale = []
    for name, content in expected.items():
        target = args.output / name
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                stale.append(name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    if stale:
        print('Stale website outputs: ' + ', '.join(stale), file=sys.stderr)
        raise SystemExit(1)
    print(f'{len(PAGES)} crawlable pages / {len(expected)} fixed outputs; ' + ('all current, no writes.' if args.check else 'generated without dependencies.'))


if __name__ == '__main__':
    main()
