"""Hafif RSS/Atom okuyucu: yalnızca metin, sınırlı ağ/önbellek, içe aktarımda I/O yok.

Tarayıcı motoru, JavaScript, resim, otomatik yenileme veya tam makale kazıyıcısı
DEĞİLDİR. Yayıncının RSS içinde sunduğu metin korunur; kaynak atfı silinmez.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

MAX_FEED_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 1024 * 1024
MAX_ITEMS = 60
MAX_BODY = 8192
MAX_SOURCES = 16
CATEGORIES = ('Tümü', 'Gündem', 'Dünya', 'Bilim ve teknoloji', 'Kültür', 'Spor', 'Rehber')
SOURCES = Path('/usr/share/oguzdows/news-sources.json')
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')


class NewsError(ValueError):
    pass


def url(value, *, feed=False):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048 or any(ord(char) < 33 for char in value):
        raise NewsError('Geçerli bir web adresi gerekli.')
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise NewsError('Adres biçimi okunamadı.') from error
    if (parsed.scheme not in (('https',) if feed else ('http', 'https')) or not parsed.hostname
            or parsed.username is not None or parsed.password is not None or port == 0):
        raise NewsError('Kaynak HTTPS olmalı; dosya, parola içeren adres veya komut kabul edilmez.')
    if parsed.hostname.lower() == 'localhost' or parsed.hostname.lower().endswith(('.localhost', '.local', '.internal')):
        raise NewsError('Yerel / özel ağ hedefi haber kaynağı olamaz.')
    try:
        address = ipaddress.ip_address(parsed.hostname.strip('[]'))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise NewsError('Yerel / özel ağ hedefi haber kaynağı olamaz.')
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))


def public_addresses(host, port, resolver=None):
    addresses = (socket.getaddrinfo if resolver is None else resolver)(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise NewsError('Kaynak özel / yerel ağa yönleniyor; istek yapılmadı.')
    return addresses


def public_destination(value, resolver=None):
    value = url(value, feed=True)
    parsed = urllib.parse.urlsplit(value)
    public_addresses(parsed.hostname, parsed.port or 443, resolver)
    return value


class DirectHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        if self._tunnel_host:
            raise NewsError('Haber indirmesi doğrudan HTTPS kullanır; proxy tüneli açılmaz.')
        # Ön denetimden sonra HTTPConnection'ın yeniden DNS çözmesine izin
        # verme. Her yönlendirme / bağlantı genel IP'ye sabitlenir, TLS SNI ve
        # sertifika / hostname denetimi ise asıl alan adında kalır.
        addresses = public_addresses(self.host, self.port)
        last_error = None
        for family, kind, protocol, _canonical, address in addresses:
            connection = socket.socket(family, kind, protocol)
            try:
                connection.settimeout(self.timeout)
                if self.source_address:
                    connection.bind(self.source_address)
                connection.connect(address)
                self.sock = self._context.wrap_socket(connection, server_hostname=self.host)
                return
            except OSError as error:
                last_error = error
                connection.close()
        raise last_error or NewsError('Genel HTTPS adresine bağlanılamadı.')


class DirectHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        # Python 3.12+ removed _check_hostname / HTTPSConnection's keyword.
        # The SSLContext already enforces CERT_REQUIRED and check_hostname.
        return self.do_open(DirectHTTPSConnection, request, context=self._context)


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirects = 0

    def redirect_request(self, request, response, code, message, headers, new_url):
        self.redirects += 1
        if self.redirects > 3:
            raise NewsError('Kaynak çok fazla yönlendirme yapıyor.')
        return super().redirect_request(request, response, code, message, headers, public_destination(new_url))


def fetch(value):
    value = public_destination(value)
    # Sistem CA/hostname denetimi; CERT_NONE, HTTP downgrade ve gzip bombası yok.
    opener = urllib.request.build_opener(Redirects(), DirectHTTPSHandler(context=ssl.create_default_context()),
                                         urllib.request.ProxyHandler({}))
    request = urllib.request.Request(value, headers={'User-Agent': 'OguzDows-Haber/1.1 RSS-reader',
                                                    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml',
                                                    'Accept-Encoding': 'identity'})
    try:
        with opener.open(request, timeout=12) as response:
            if response.headers.get('Content-Encoding', 'identity').lower() not in ('identity', ''):
                raise NewsError('Sıkıştırılmış akış bu hafif okuyucuda açılmadı.')
            length = response.headers.get('Content-Length', '')
            if length.isdecimal() and int(length) > MAX_FEED_BYTES:
                raise NewsError('RSS akışı 1 MiB sınırından büyük.')
            data = bytearray()
            while True:
                chunk = response.read(min(32768, MAX_FEED_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_FEED_BYTES:
                    raise NewsError('RSS akışı 1 MiB sınırından büyük.')
            return bytes(data)
    except urllib.error.HTTPError as error:
        error.close()
        raise NewsError('Kaynak HTTP ' + str(error.code) + ' yanıtı verdi; eski önbellek korunur.') from error
    except (urllib.error.URLError, OSError) as error:
        raise NewsError('Kaynağa ulaşılamadı / TLS doğrulanamadı. Eski önbellek korunur. ' + str(error)[:300]) from error


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.rsplit(':', 1)[-1]  # Atom XHTML namespace önekleri de yalnız metin.
        if tag in ('script', 'style', 'iframe', 'object', 'svg', 'template', 'head'):
            self.hidden += 1
        elif not self.hidden and tag in ('p', 'br', 'div', 'li', 'h1', 'h2', 'h3', 'blockquote'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.rsplit(':', 1)[-1]
        if tag in ('script', 'style', 'iframe', 'object', 'svg', 'template', 'head'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'blockquote'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value, limit=MAX_BODY):
    parser = Text()
    parser.feed(str(value)[:65536])
    lines = [' '.join(line.split()) for line in ''.join(parser.parts).splitlines()]
    value = '\n\n'.join(line for line in lines if line)
    # Kontrol / bidi override karakterleri kaynağı veya arayüzü taklit etmesin.
    value = ''.join(char for char in value if char in '\n\t' or ord(char) >= 32 and char not in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069')
    return value[:limit]


class SafeTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.depth = self.nodes = 0

    def doctype(self, *_args):
        raise NewsError('DTD / entity içeren RSS açılmadı.')

    def start(self, tag, attrs):
        self.depth += 1
        self.nodes += 1
        if self.depth > 48 or self.nodes > 12000 or len(attrs) > 64:
            raise NewsError('RSS yapısı hafif okuyucunun sınırını aşıyor.')
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)


def local(tag):
    return tag.rsplit('}', 1)[-1].lower()


def child_text(element, names):
    for name in names:
        for child in element:
            if local(child.tag) == name:
                # Atom XHTML de çalıştırılmaz; aynı HTML→metin süzgecinden geçer.
                return (child.text or '') + ''.join(ET.tostring(part, encoding='unicode') for part in child)
    return ''


def parse(data, base_url):
    if not isinstance(data, bytes) or not data or len(data) > MAX_FEED_BYTES:
        raise NewsError('RSS boş veya 1 MiB sınırından büyük.')
    base_url = url(base_url, feed=True)
    try:
        root = ET.fromstring(data, parser=ET.XMLParser(target=SafeTree()))
    except (ET.ParseError, LookupError, UnicodeError) as error:
        raise NewsError('RSS / Atom XML okunamadı; eski önbellek korundu.') from error
    if local(root.tag) not in ('rss', 'rdf', 'feed'):
        raise NewsError('Bu belge RSS / Atom akışı değil.')
    items, seen = [], set()
    for element in root.iter():
        if local(element.tag) not in ('item', 'entry'):
            continue
        title = plain(child_text(element, ('title',)), 240)
        body = plain(child_text(element, ('encoded', 'content', 'description', 'summary')))
        raw_link = child_text(element, ('link',)).strip()
        if not raw_link:
            raw_link = next((child.get('href', '') for child in element if local(child.tag) == 'link'
                             and child.get('rel', 'alternate') == 'alternate'), '')
        try:
            link = url(urllib.parse.urljoin(base_url, raw_link)) if raw_link else ''
        except NewsError:
            link = ''  # Geçersiz link çalıştırılmaz; varsa salt metin yine okunur.
        if not title or not (body or link):
            continue
        identity = hashlib.sha256((link or title + body).encode()).hexdigest()[:32]
        if identity in seen:
            continue
        seen.add(identity)
        items.append({'id': identity, 'title': title, 'body': body or 'Yayıncı bu akışta yalnızca başlık / bağlantı sunuyor. Tamamı için Kaynakta aç düğmesini kullanın.',
                      'url': link, 'published': plain(child_text(element, ('pubdate', 'published', 'updated', 'date')), 100),
                      'category': category(child_text(element, ('category', 'subject')))})
        if len(items) == MAX_ITEMS:
            break
    if not items:
        raise NewsError('Akışta okunabilir haber bulunamadı; eski önbellek korundu.')
    return items



def category(value, default='Gündem'):
    value = plain(value, 120).casefold()
    if any(word in value for word in ('bilim', 'teknoloji', 'science', 'technology')):
        return 'Bilim ve teknoloji'
    if any(word in value for word in ('dünya', 'world', 'international')):
        return 'Dünya'
    if any(word in value for word in ('kültür', 'sanat', 'culture', 'arts')):
        return 'Kültür'
    if any(word in value for word in ('spor', 'sport')):
        return 'Spor'
    return default


def example_items(now=None):
    """Useful generated demo, NEVER represented as current publisher news.

    No invented events, source attribution, publication date or article links.
    It is produced on demand, not by an idle timer; never written to RSS cache.
    """
    now = now or datetime.now(timezone.utc)
    rows = (
        ('Bilim ve teknoloji', 'RSS ile reklamsız okumayı dene',
         'Yenile, yalnızca seçili yayıncının HTTPS RSS / Atom akışını getirir. Resim, reklam veya JavaScript indirilmez. Yayıncı yalnız özet sunuyorsa Kaynakta aç ile asıl metne geçebilirsin.'),
        ('Gündem', 'Bağlantı yokken de okumaya devam et',
         'Başarılı bir yenilemeden sonra indirilen metinler kendi hesabının önbelleğinde kalır. Bir sonraki bağlantı hatasında son haberler korunur; yeniymiş gibi tarihlenmez.'),
        ('Dünya', 'Haberin kaynağını ve tarihini karşılaştır',
         'Bir iddiayı farklı yayıncılardan kontrol et. Bu örnek başlık, gerçek bir dünya haberi değildir. Gerçek yayıncıyı üstteki kaynak menüsünden seçip Yenile’ye bas.'),
        ('Kültür', 'Kendi okuma listeni oluştur',
         'Artı düğmesiyle güvendiğin yayıncının HTTPS RSS / Atom adresini ekleyebilirsin. Kaynak eklemek tek başına ağ isteği başlatmaz; kişisel kaynaklar ayrıca kaldırılabilir.'),
        ('Spor', 'Kategoriler arasında hafifçe dolaş',
         'Kategori ve arama filtreleri indirilen metinde yerel olarak çalışır. Yeni indirme başlatmaz. Bu spor kategorisi girdisi yalnızca arayüzü denemek içindir; maç sonucu ya da güncel haber değildir.'),
        ('Rehber', 'Cam görünümünde kontrol sende',
         'Masaüstü Merkezi’nde görünüm ve azaltılmış hareket tercihini seç. Düşük RAM, nomodeset veya doğrulanamayan GPU’da okunaklı opak yüzeyler korunur. Bu bir OğuzDows kullanım ipucudur, haber değildir.'),
    )
    offset = (now.hour * 60 + now.minute) % len(rows)
    return [{'id': hashlib.sha256(('example:' + title).encode()).hexdigest()[:32],
             'title': 'ÖRNEK · ' + title, 'body': 'ÖRNEK AKIŞ · Gerçek haber değildir.\n\n' + body,
             'url': '', 'published': '', 'category': group, 'example': True,
             'publisher': 'OğuzDows · yerel örnek akış'}
            for group, title, body in rows[offset:] + rows[:offset]]


def read_json(path, limit=MAX_CACHE_BYTES):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise NewsError('Önbellek / kaynak dosyası normal ve sınırlı olmalı.')
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise NewsError('Yerel haber verisi okuma sınırını aşıyor.')
        return json.loads(data.decode('utf-8'))
    except (OSError, ValueError, UnicodeError) as error:
        raise NewsError('Yerel haber verisi okunamadı / normal ve sınırlı dosya gerekli.') from error


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise NewsError('Haber veri dizini sembolik bağ olamaz.')
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise NewsError('Haber veri dizini bu kullanıcıya ait olmalı.')
    path.chmod(0o700)
    return path


def atomic_json(path, data):
    directory = private_directory(path.parent)
    if path.is_symlink() or path.exists() and not path.is_file():
        raise NewsError('Haber dosyası normal dosya olmalı; sembolik bağ / özel dosya olamaz.')
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
    if len(text.encode()) > MAX_CACHE_BYTES:
        raise NewsError('Haber önbelleği 1 MiB sınırını aşıyor.')
    descriptor, name = tempfile.mkstemp(prefix='.haber-', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Reader:
    def __init__(self, source_file=SOURCES, config=None, cache=None):
        self.source_file = Path(source_file)
        self.config = Path(config) if config is not None else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'oguzdows/news'
        self.cache = Path(cache) if cache is not None else Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'oguzdows/news'

    def sources(self):
        defaults = read_json(self.source_file, 32768)
        custom_file = self.config / 'sources.json'
        custom = read_json(custom_file, 32768) if custom_file.exists() or custom_file.is_symlink() else []
        if not isinstance(defaults, list) or not isinstance(custom, list) or not 1 <= len(defaults) + len(custom) <= MAX_SOURCES:
            raise NewsError('Kaynak listesi sınırlı bir dizi olmalı (en fazla 16).')
        result, seen = [], set()
        for source, personal in [(item, False) for item in defaults] + [(item, True) for item in custom]:
            if (not isinstance(source, dict) or not isinstance(source.get('id'), str)
                    or not IDENTIFIER.fullmatch(source['id']) or source['id'] in seen
                    or not isinstance(source.get('name'), str) or not 1 <= len(source['name']) <= 80):
                raise NewsError('Kaynak kimliği / adı geçersiz.')
            seen.add(source['id'])
            result.append({'id': source['id'], 'name': plain(source['name'], 80),
                           'url': url(source.get('url'), feed=True), 'custom': personal,
                           'category': category(source.get('category', source['name']))})
        return result

    def selected(self, identifier):
        sources = self.sources()
        if identifier is None:
            identifier = sources[0]['id']
        source = next((item for item in sources if item['id'] == identifier), None)
        if source is None:
            raise NewsError('Kaynak listesinde bulunmayan kimlik.')
        return sources, source

    def cached(self, identifier=None):
        sources, source = self.selected(identifier)
        path = self.cache / (source['id'] + '.json')
        result = {'sources': sources, 'selected': source['id'], 'source': source['name'], 'items': [],
                  'cached_at': '', 'network_refresh_requested': False,
                  'note': 'Yayıncının RSS metni / özeti. Resim, reklam, webview veya JavaScript yüklenmez.'}
        if path.exists() or path.is_symlink():
            data = read_json(path)
            if (not isinstance(data, dict) or data.get('source_url') != source['url']
                    or not isinstance(data.get('items'), list) or len(data['items']) > MAX_ITEMS
                    or not isinstance(data.get('cached_at'), str) or len(data['cached_at']) > 64):
                raise NewsError('Haber önbelleği bu kaynağa ait değil / biçimi bozuk.')
            for item in data['items']:
                if (not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ('id', 'title', 'body', 'url', 'published'))
                        or not re.fullmatch('[a-f0-9]{32}', item['id']) or len(item['title']) > 240
                        or len(item['body']) > MAX_BODY or len(item['published']) > 100
                        or 'category' in item and item['category'] not in CATEGORIES[1:]
                        or item['url'] and url(item['url']) != item['url']):
                    raise NewsError('Önbellekte geçersiz haber kaydı var.')
            result.update(items=data['items'], cached_at=data['cached_at'])
        return result

    def refresh(self, identifier, download=fetch):
        _sources, source = self.selected(identifier)
        items = parse(download(source['url']), source['url'])
        for item in items:
            if item['category'] == 'Gündem':
                item['category'] = source['category']
        atomic_json(self.cache / (source['id'] + '.json'), {'source_url': source['url'], 'items': items,
                    'cached_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        result = self.cached(identifier)
        result['network_refresh_requested'] = True
        return result

    def stream(self, identifier=None, *, network=False, download=fetch):
        """Presentation contract: live -> stale cache -> clearly labelled demo.

        cached()/refresh() stay strict for callers that need validation errors.
        A damaged local file is reported and not silently overwritten offline.
        No fallback is ever attributed to TRT / BBC / DW or saved as real RSS.
        """
        _sources, source = self.selected(identifier)
        warning = ''
        try:
            result = self.refresh(source['id'], download) if network else self.cached(source['id'])
        except (NewsError, OSError) as error:
            warning = str(error)[:700]
            try:
                result = self.cached(source['id'])
            except (NewsError, OSError) as cache_error:
                warning += ' · Önbellek: ' + str(cache_error)[:300]
                result = {'sources': _sources, 'selected': source['id'], 'source': source['name'],
                          'items': [], 'cached_at': ''}
        example = not result['items']
        if example:
            result['items'] = example_items()
        result.update(mode='example' if example else 'live' if network and not warning else 'cache',
                      categories=list(CATEGORIES), network_refresh_requested=network,
                      warning=warning, example=example,
                      note=('ÖRNEK AKIŞ · Gerçek haber değildir. Henüz indirilen haber yok. '
                            'Yayıncıdan güncel başlıklar için Yenile’ye bas.' if example else
                            'Yayıncının RSS metni / özeti. Tarih yayıncıya aittir; son başarılı indirme aşağıdadır.'))
        return result

    def add(self, address, name):
        address = url(address, feed=True)
        name = plain(name, 80)
        sources = self.sources()
        if not name or len(sources) >= MAX_SOURCES or any(item['url'] == address for item in sources):
            raise NewsError('Ad boş, kaynak zaten var veya 16 kaynak sınırı dolu.')
        identifier = 'rss-' + hashlib.sha256(address.encode()).hexdigest()[:20]
        custom = [{key: item[key] for key in ('id', 'name', 'url')} for item in sources if item['custom']]
        custom.append({'id': identifier, 'name': name, 'url': address})
        atomic_json(self.config / 'sources.json', custom)
        return self.cached(identifier)  # Eklemek otomatik ağ isteği değildir.

    def remove(self, identifier):
        sources, source = self.selected(identifier)
        if not source['custom']:
            raise NewsError('Yerleşik kaynak silinmez; başka kaynak seçebilir veya kendi RSS adresini ekleyebilirsin.')
        custom = [{key: item[key] for key in ('id', 'name', 'url')} for item in sources if item['custom'] and item['id'] != identifier]
        atomic_json(self.config / 'sources.json', custom)
        path = self.cache / (identifier + '.json')
        if path.is_symlink() or path.exists() and not stat.S_ISREG(path.stat().st_mode):
            raise NewsError('Beklenmeyen önbellek dosyası silinmedi.')
        path.unlink(missing_ok=True)
        return self.cached()
