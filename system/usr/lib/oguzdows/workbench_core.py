"""Atölye'nin çevrimdışı araçları. GTK, ağ, indeksleyici veya servis başlatmaz.

Büyük işler yalnızca açık kullanıcı isteğinde, tek işçide çalıştırılır. Hiçbir
metin komut olarak yorumlanmaz. Dosya araçları seçim / önizleme / onay ister.
"""
from __future__ import annotations

import ast
import configparser
import ctypes
import difflib
import errno
import fcntl
import hashlib
import io
import json
import math
import os
import re
import stat
import time
import unicodedata
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

MAX_STATE = 4 * 1024 * 1024
MAX_TEXT = 128 * 1024
KINDS = ('tasks', 'notes', 'snippets', 'folders', 'palettes')
TOOLS = (
    ('tasks', 'Günüm', 'Öncelikli, tarihli görev panosu', 'view-list-symbolic'),
    ('notes', 'Defter', 'Yerel notlar ve metin dışa aktarma', 'accessories-text-editor-symbolic'),
    ('snippets', 'Metin rafı', 'Elle kaydedilen, aranabilir metin parçaları', 'edit-paste-symbolic'),
    ('folders', 'Yerlerim', 'Kendi seçtiğin klasörlere hızlı erişim', 'folder-favorites-symbolic'),
    ('find', 'Dosya bul', 'Seçili klasörde sınırlı, indekssiz arama', 'system-search-symbolic'),
    ('rename', 'Toplu adlandır', 'Önizleme, çakışma denetimi ve geri alma', 'edit-find-replace-symbolic'),
    ('checksum', 'Dosya doğrula', 'Akış halinde SHA-256 / SHA-512 denetimi', 'security-high-symbolic'),
    ('image', 'Görsel hazırla', 'Boyutlandır, biçim değiştir, metadata taşıma', 'image-x-generic-symbolic'),
    ('diff', 'Metin karşılaştır', 'İki metnin satır farklarını incele', 'view-dual-symbolic'),
    ('json', 'JSON masası', 'Doğrula, düzenle veya küçült', 'text-x-script-symbolic'),
    ('calculator', 'Hesap', 'Komut çalıştırmayan ifade hesaplayıcı', 'accessories-calculator-symbolic'),
    ('units', 'Birimler', 'Uzunluk, kütle, sıcaklık, veri ve zaman', 'applications-science-symbolic'),
    ('colors', 'Renk stüdyosu', 'Paletler ve WCAG metin kontrastı', 'applications-graphics-symbolic'),
    ('clocks', 'Dünya saatleri', 'Saat dilimleri, ağ ve konum izni olmadan', 'preferences-system-time-symbolic'),
    ('text', 'Metin işle', 'Türkçe harfler, satırlar ve metin istatistiği', 'format-text-bold-symbolic'),
    ('startup', 'Başlangıç', 'Kullanıcı oturum başlangıçlarını geri alınabilir yönet', 'system-run-symbolic'),
)


def normalized(text):
    text = text.translate(str.maketrans({'ı': 'i', 'İ': 'i'})).casefold()
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.combining(ch))


def _bounded(text, maximum, name='Metin'):
    if not isinstance(text, str) or len(text) > maximum or '\0' in text:
        raise ValueError(name + ' boyutu / biçimi geçersiz.')
    return text


def _regular(path, maximum=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or maximum is not None and info.st_size > maximum:
            raise ValueError('Boyut sınırında normal bir dosya seçin; bağlantı / aygıt okunmaz.')
        return os.fdopen(fd, 'rb'), info
    except BaseException:
        os.close(fd)
        raise


def _read_limited(stream, maximum):
    data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Dosya okunurken boyut sınırını aştı; özgün dosya korunuyor.')
    return data


def _directory(path, create=False):
    path = Path(path).absolute()
    # Our state / explicitly chosen root must not be silently redirected.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Bağlantı yönlendirmesi yerine gerçek klasörü seçin.')
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    return path, fd


def _lock_at(directory, name='.lock'):
    info = os.fstat(directory)
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('Kayıt klasörü bu kullanıcıya ait, başkalarınca yazılamayan gerçek klasör olmalı.')
    lock = os.open(name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Kişisel kayıt kilidi güvenli değil.')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except BaseException:
        os.close(lock)
        raise


def _atomic_at(directory, name, data):
    temporary = '.' + name + '-' + uuid.uuid4().hex
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


class Library:
    """Bounded private JSON; atomic replacement + advisory lock, no daemon.

    Notes/snippets are NOT encrypted. No automatic clipboard collection.
    Opening an empty library does not create files or scan the home directory.
    """
    def __init__(self, root=None):
        base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        self.root = Path(root) if root is not None else base / 'oguzdows/workbench'

    def read(self):
        try:
            stream, info = _regular(self.root / 'library.json', MAX_STATE)
        except FileNotFoundError:
            return {'schema': 1, **{kind: [] for kind in KINDS}}
        with stream:
            if info.st_uid != os.getuid():
                raise ValueError('Kitaplık bu kullanıcıya ait değil.')
            payload = stream.read(MAX_STATE + 1)
            if len(payload) > MAX_STATE:
                raise ValueError('Kitaplık okunurken boyut sınırını aştı; özgün dosya korunuyor.')
            value = json.loads(payload)
        if not isinstance(value, dict) or value.get('schema') != 1:
            raise ValueError('Kitaplık biçimi tanınmadı; özgün dosya korunuyor.')
        for kind in KINDS:
            rows = value.get(kind)
            if not isinstance(rows, list) or len(rows) > 500:
                raise ValueError('Kitaplık kayıt sınırı / biçimi geçersiz.')
            seen = set()
            for row in rows:
                self.validate(kind, row)
                if row['id'] in seen:
                    raise ValueError('Yinelenen kayıt kimliği; kitaplık değiştirilmedi.')
                seen.add(row['id'])
        return value

    @staticmethod
    def validate(kind, row):
        if kind not in KINDS or not isinstance(row, dict) or not re.fullmatch(r'[a-f0-9]{32}', str(row.get('id', ''))):
            raise ValueError('Geçersiz kayıt / koleksiyon.')
        if not _bounded(row.get('title'), 160).strip():
            raise ValueError('Bir başlık yazın.')
        _bounded(row.get('body', ''), 65536)
        _bounded(row.get('updated', ''), 40)
        if kind == 'tasks':
            if row.get('priority') not in ('high', 'normal', 'low') or type(row.get('done')) is not bool:
                raise ValueError('Görev önceliği / durumu geçersiz.')
            due = row.get('due', '')
            if not isinstance(due, str) or due and date.fromisoformat(due).isoformat() != due:
                raise ValueError('Son tarih YYYY-AA-GG biçiminde olmalı.')
        if kind == 'folders' and (not Path(row.get('body', '')).is_absolute() or '\n' in row['body']):
            raise ValueError('Mutlak bir klasör yolu seçin.')
        if kind == 'palettes':
            color_info(row.get('body', ''), '#ffffff')

    def update(self, kind, *, identifier='', delete=False, **fields):
        if kind not in KINDS:
            raise ValueError('Koleksiyon tanınmadı.')
        _, directory = _directory(self.root, create=True)
        lock = None
        try:
            lock = _lock_at(directory)
            value = self.read()
            rows = value[kind]
            old = next((row for row in rows if row['id'] == identifier), None)
            if identifier and old is None:
                raise ValueError('Kayıt değişmiş / kaldırılmış; yeniden açın.')
            if delete:
                if old is None:
                    raise ValueError('Silmek için bir kayıt seçin.')
                rows.remove(old)
                result = old
            else:
                result = {**(old or {}), **fields, 'id': identifier or uuid.uuid4().hex,
                          'updated': datetime.now(timezone.utc).isoformat(timespec='seconds')}
                self.validate(kind, result)
                if old is None:
                    if len(rows) >= 500:
                        raise ValueError('Bu koleksiyonda en fazla 500 kayıt saklanır.')
                    rows.append(result)
                else:
                    rows[rows.index(old)] = result
            data = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
            if len(data) > MAX_STATE:
                raise ValueError('4 MiB kitaplık sınırı doldu. Önce bazı notları dışa aktarın.')
            _atomic_at(directory, 'library.json', data)
            return result
        finally:
            if lock is not None: os.close(lock)
            os.close(directory)


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise ValueError('İşlem iptal edildi; kaynaklar değiştirilmedi.')


def find_files(root, query, cancel=None, *, max_entries=20000, max_results=200, seconds=8):
    query = normalized(_bounded(query.strip(), 100))
    if not query:
        raise ValueError('Dosya adının bir bölümünü yazın.')
    path, directory = _directory(root)
    device = os.fstat(directory).st_dev
    started = time.monotonic()
    rows, stack, visited, limited = [], [(directory, '', 0)], 0, False
    try:
        while stack:
            check_cancel(cancel)
            fd, relative, depth = stack.pop()
            try:
                with os.scandir(fd) as entries:
                    for entry in entries:
                        check_cancel(cancel)
                        visited += 1
                        if visited > max_entries or time.monotonic() - started > seconds:
                            limited = True
                            break
                        if entry.name.startswith('.') or entry.is_symlink():
                            continue
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if info.st_dev != device:
                                continue
                            name = relative + entry.name
                            if stat.S_ISDIR(info.st_mode) and depth < 12 and len(stack) < 128:
                                child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                                stack.append((child, name + '/', depth + 1))
                            elif stat.S_ISREG(info.st_mode) and query in normalized(entry.name):
                                rows.append({'path': str(path / name), 'relative': name, 'bytes': info.st_size})
                                if len(rows) >= max_results:
                                    limited = True
                                    break
                        except (OSError, ValueError):
                            continue
            finally:
                os.close(fd)
            if limited:
                break
        return {'files': sorted(rows, key=lambda row: normalized(row['relative'])), 'visited': visited, 'limited': limited}
    finally:
        for fd, _, _ in stack:
            os.close(fd)


def file_checksum(path, algorithm='sha256', expected='', cancel=None, progress=None):
    if algorithm not in ('sha256', 'sha512'):
        raise ValueError('SHA-256 veya SHA-512 seçin.')
    digest = hashlib.new(algorithm)
    expected = expected.strip().lower()
    if expected and not re.fullmatch('[0-9a-f]{' + str(digest.digest_size * 2) + '}', expected):
        raise ValueError('Beklenen özetin uzunluğu / onaltılık biçimi geçersiz.')
    stream, before = _regular(path)
    total = 0
    with stream:
        while True:
            check_cancel(cancel)
            block = stream.read(256 * 1024)
            if not block:
                break
            digest.update(block)
            total += len(block)
            if progress:
                progress(total, before.st_size)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('Dosya okunurken değişti; bu özet doğrulanmış sayılmaz.')
    value = digest.hexdigest()
    return {'algorithm': algorithm, 'digest': value, 'bytes': total, 'matches': value == expected if expected else None}


def export_text(directory, name, text):
    _bounded(text, 1024 * 1024)
    safe_name(name)
    _, fd = _directory(directory)
    created = False
    try:
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        created = True
        with os.fdopen(out, 'w', encoding='utf-8') as stream:
            stream.write(text)
        return str(Path(directory) / name)
    except BaseException:
        if created:
            os.unlink(name, dir_fd=fd)
        raise
    finally:
        os.close(fd)


def safe_name(name):
    if (not isinstance(name, str) or not name or name in ('.', '..') or name.startswith('.')
            or any(ord(ch) < 32 or ch in '/\\\0' for ch in name) or len(os.fsencode(name)) > 240):
        raise ValueError('Görünür, kısa ve klasör ayırıcı içermeyen bir dosya adı kullanın.')
    return name


def _stamp(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def rename_preview(root, prefix='', find='', replace='', start=1, cancel=None, *, max_entries=20000, seconds=8):
    for value in (prefix, find, replace):
        _bounded(value, 80)
        if any(ord(ch) < 32 or ch in '/\\' for ch in value):
            raise ValueError('Adlandırma metni klasör ayırıcı / kontrol karakteri içeremez.')
    if type(start) is not int or not 0 <= start <= 99999:
        raise ValueError('Başlangıç numarası 0–99999 olmalı.')
    path, fd = _directory(root)
    try:
        info = os.fstat(fd)
        rows = []
        started, visited = time.monotonic(), 0
        with os.scandir(fd) as entries:
            for entry in entries:
                check_cancel(cancel)
                visited += 1
                if visited > max_entries or time.monotonic() - started > seconds:
                    raise ValueError('Önizleme tarama sınırı: en fazla 20.000 girdi / 8 saniye. Daha küçük klasör seçin.')
                if entry.name.startswith('.') or entry.is_symlink():
                    continue
                source = entry.stat(follow_symlinks=False)
                if stat.S_ISREG(source.st_mode):
                    rows.append((entry.name, source))
                if len(rows) > 200:
                    raise ValueError('Tek adlandırmada en fazla 200 görünür dosya; daha küçük bir klasör seçin.')
        rows.sort(key=lambda row: row[0])
        changes, targets = [], set()
        for index, (name, source) in enumerate(rows):
            changed = name.replace(find, replace) if find else name
            # {n} is the sole template; never format/eval arbitrary expressions.
            target = safe_name(prefix.replace('{n}', str(start + index).zfill(3)) + changed)
            if name == target:
                continue
            if target in targets:
                raise ValueError('Birden çok dosya aynı hedefi istiyor: ' + target)
            try:
                os.stat(target, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('Hedef zaten var; üzerine yazılmaz: ' + target)
            targets.add(target)
            changes.append({'before': name, 'after': target, 'stamp': _stamp(source)})
        if not changes:
            raise ValueError('Adı değişecek dosya yok; bir önek veya bul/değiştir kuralı yazın.')
        return {'schema': 1, 'directory': str(path), 'identity': [info.st_dev, info.st_ino], 'changes': changes}
    finally:
        os.close(fd)


def _rename_no_replace(fd, before, after):
    # libc abstracts the syscall number on i386/amd64/armhf/aarch64. No ISA or
    # syscall-number assumptions, no unsafe os.rename overwrite fallback.
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, 'renameat2', None)
    if function is None:
        raise ValueError('Güvenli renameat2 bu sistemde yok; hiçbir dosyanın üzerine yazılmaz.')
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(fd, os.fsencode(before), fd, os.fsencode(after), 1):  # RENAME_NOREPLACE
        number = ctypes.get_errno()
        if number in (errno.ENOSYS, errno.EINVAL):
            raise ValueError('Bu çekirdek / dosya sistemi üzerine yazmasız adlandırmayı desteklemiyor.')
        raise OSError(number, os.strerror(number), after)


def rename_apply(plan, journal_root, *, undo=False):
    if (not isinstance(plan, dict) or plan.get('schema') != 1 or not isinstance(plan.get('changes'), list)
            or not 1 <= len(plan['changes']) <= 200):
        raise ValueError('Geçersiz adlandırma planı.')
    _, directory = _directory(plan['directory'])
    journal = lock = None
    moved = []
    try:
        _, journal = _directory(journal_root, create=True)
        lock = _lock_at(journal)
        info = os.fstat(directory)
        if [info.st_dev, info.st_ino] != plan['identity']:
            raise ValueError('Klasör önizlemeden sonra değişmiş; plan yenilenmeli.')
        changes = list(reversed(plan['changes'])) if undo else plan['changes']
        actionable = []
        for row in changes:
            before, after = (row['after'], row['before']) if undo else (row['before'], row['after'])
            safe_name(before); safe_name(after)
            try:
                source = os.stat(before, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                if undo and _stamp(os.stat(after, dir_fd=directory, follow_symlinks=False)) == row['stamp']:
                    continue  # A crash or rollback may have left this row unchanged.
                raise ValueError('Kaynak artık yok; dosyalar otomatik birleştirilmez.')
            if not stat.S_ISREG(source.st_mode) or _stamp(source) != row['stamp']:
                raise ValueError('Dosya değişmiş; yeni içeriği korumak için işlem reddedildi: ' + before)
            try:
                os.stat(after, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('Hedef artık var; üzerine yazılmaz: ' + after)
            actionable.append((before, after, row['stamp']))
        if not undo:
            previous = Path(journal_root) / 'rename.json'
            if previous.exists():
                raise ValueError('Önce son adlandırmayı geri alın veya yeni önizleme için geçmişini bırakın.')
            _atomic_at(journal, 'rename.json', json.dumps(plan, ensure_ascii=False).encode())
        for before, after, stamp in actionable:
            if _stamp(os.stat(before, dir_fd=directory, follow_symlinks=False)) != stamp:
                raise ValueError('İşlem sırasında dosya değişti; kalanlar taşınmadı.')
            _rename_no_replace(directory, before, after)
            moved.append((before, after))
        if undo:
            os.unlink('rename.json', dir_fd=journal)
        return len(moved)
    except BaseException:
        # Best effort, still NOREPLACE; keep journal if another writer conflicts.
        for before, after in reversed(moved):
            try:
                _rename_no_replace(directory, after, before)
            except (OSError, ValueError):
                break
        raise
    finally:
        if lock is not None: os.close(lock)
        if journal is not None: os.close(journal)
        os.close(directory)


def rename_history(journal_root, *, forget=False):
    _, directory = _directory(journal_root)
    lock = None
    try:
        lock = _lock_at(directory)
        stream, info = _regular(Path(journal_root) / 'rename.json', 256 * 1024)
        with stream:
            if info.st_uid != os.getuid(): raise ValueError('Geri alma kaydı bu kullanıcıya ait değil.')
            value = json.loads(_read_limited(stream, 256 * 1024))
        if forget:
            os.unlink('rename.json', dir_fd=directory)  # Only our fixed journal; never renamed files.
        return value
    finally:
        if lock is not None: os.close(lock)
        os.close(directory)


def prepare_image(source, destination, name, width=1600, height=1600, format_name='JPEG', cancel=None):
    from PIL import Image, ImageOps
    if format_name not in ('JPEG', 'PNG', 'WEBP') or not 16 <= width <= 4096 or not 16 <= height <= 4096:
        raise ValueError('JPEG / PNG / WebP ve 16–4096 piksel sınırı kullanın.')
    safe_name(name)
    check_cancel(cancel)
    stream, _ = _regular(source, 32 * 1024 * 1024)
    with stream, Image.open(stream) as original:
        if original.width * original.height > 8_000_000 or getattr(original, 'n_frames', 1) != 1:
            raise ValueError('Düşük RAM güvenliği: en fazla 8 megapiksel, tek kare görsel seçin.')
        picture = ImageOps.exif_transpose(original)
        picture.thumbnail((width, height), Image.Resampling.LANCZOS)
        image = picture.convert('RGBA' if format_name == 'PNG' else 'RGB')
        if format_name != 'PNG' and 'A' in picture.getbands():
            image.paste((255, 255, 255), (0, 0, image.width, image.height))
            image.paste(picture, mask=picture.getchannel('A'))
        image.info.clear()  # No GPS, EXIF, comments, ICC/XMP copied to output.
        check_cancel(cancel)
        _, directory = _directory(destination)
        created = False
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            created = True
            with os.fdopen(fd, 'wb') as output:
                image.save(output, format=format_name, **({'quality': 86} if format_name in ('JPEG', 'WEBP') else {}))
            return {'path': str(Path(destination) / name), 'width': image.width, 'height': image.height}
        except BaseException:
            if created:
                os.unlink(name, dir_fd=directory)
            raise
        finally:
            image.close()
            picture.close()
            os.close(directory)


def text_diff(left, right):
    for value in (left, right):
        _bounded(value, MAX_TEXT)
        if value.count('\n') > 1500:
            raise ValueError('Karşılaştırma başına en fazla 1500 satır / 128 KiB metin.')
    result = ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n'
                     for line in difflib.unified_diff(left.splitlines(True), right.splitlines(True), fromfile='Önce', tofile='Sonra'))
    if len(result) > 512 * 1024:
        raise ValueError('Fark çıktısı sınırı aştı; daha küçük parçalar seçin.')
    return result or 'Metinler aynı.'


def format_json(text, compact=False):
    _bounded(text, MAX_TEXT)
    depth, string, escape = 0, False, False
    for ch in text:
        if string:
            if escape: escape = False
            elif ch == '\\': escape = True
            elif ch == '"': string = False
        elif ch == '"': string = True
        elif ch in '[{':
            depth += 1
            if depth > 40:
                raise ValueError('JSON en fazla 40 katman içerebilir.')
        elif ch in ']}': depth -= 1
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Yinelenen JSON anahtarı: ' + key[:100])
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('JSON sonlu sayılar içermeli: ' + value)
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)
    # Overflow such as 1e999 is also refused, rather than exporting Infinity.
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=None if compact else 2,
                      separators=(',', ':') if compact else None)


def calculate(expression):
    _bounded(expression, 256)
    tree = ast.parse(expression.strip(), mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError('İfade çok karmaşık; en fazla 64 sözdizimi düğümü.')
    def solve(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = Decimal(ast.get_source_segment(expression.strip(), node).replace('_', ''))
        elif isinstance(node, ast.Name) and node.id in ('pi', 'e'):
            result = Decimal(str(math.pi if node.id == 'pi' else math.e))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            result = solve(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = solve(node.left), solve(node.right)
            if isinstance(node.op, ast.Add): result = left + right
            elif isinstance(node.op, ast.Sub): result = left - right
            elif isinstance(node.op, ast.Mult): result = left * right
            elif isinstance(node.op, ast.Div): result = left / right
            elif isinstance(node.op, ast.FloorDiv): result = left // right
            elif isinstance(node.op, ast.Mod): result = left % right
            elif isinstance(node.op, ast.Pow) and right == right.to_integral_value() and abs(right) <= 12: result = left ** int(right)
            else: raise ValueError('İşlem desteklenmiyor; üs tam sayı ve −12…12 olmalı.')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords and len(node.args) == 1:
            value = solve(node.args[0])
            if node.func.id == 'sqrt': result = value.sqrt()
            elif node.func.id == 'abs': result = abs(value)
            else: raise ValueError('Yalnız sqrt(x) ve abs(x) kullanılabilir.')
        else:
            raise ValueError('Yalnızca sayılar ve aritmetik; dosya / Python / shell çalıştırılmaz.')
        if not result.is_finite() or abs(result) > Decimal('1e100'):
            raise ValueError('Sayı güvenli hesap sınırının dışında.')
        return result
    with localcontext() as context:
        context.prec = 28
        try:
            return str(solve(tree.body).normalize())
        except (ArithmeticError, InvalidOperation) as error:
            raise ValueError('Tanımsız hesap veya sıfıra bölme.') from error


UNITS = {
    'Uzunluk': {'mm': '.001', 'cm': '.01', 'm': '1', 'km': '1000', 'in': '.0254', 'ft': '.3048', 'mi': '1609.344'},
    'Kütle': {'mg': '.000001', 'g': '.001', 'kg': '1', 'ton': '1000', 'lb': '.45359237', 'oz': '.028349523125'},
    'Veri': {'B': '1', 'kB': '1000', 'MB': '1000000', 'GB': '1000000000', 'KiB': '1024', 'MiB': '1048576', 'GiB': '1073741824'},
    'Zaman': {'s': '1', 'dk': '60', 'saat': '3600', 'gün': '86400', 'hafta': '604800'},
    'Sıcaklık': {'°C': '1', '°F': '1', 'K': '1'},
}


def convert_unit(value, category, source, target):
    try:
        number = Decimal(_bounded(value, 100).strip().replace(',', '.'))
        units = UNITS[category]
        if not number.is_finite() or abs(number) > Decimal('1e100') or source not in units or target not in units:
            raise ValueError('Sayı / birim geçersiz.')
        if category == 'Sıcaklık':
            celsius = (number - 32) * Decimal(5) / 9 if source == '°F' else number - Decimal('273.15') if source == 'K' else number
            if celsius < Decimal('-273.15'):
                raise ValueError('Mutlak sıfırın altında sıcaklık olamaz.')
            result = celsius * 9 / 5 + 32 if target == '°F' else celsius + Decimal('273.15') if target == 'K' else celsius
        else:
            result = number * Decimal(units[source]) / Decimal(units[target])
        return str(result.normalize())
    except (KeyError, InvalidOperation) as error:
        raise ValueError('Geçerli bir sayı, kategori ve birim seçin.') from error


def color_info(foreground, background):
    def rgb(value):
        if not isinstance(value, str) or not re.fullmatch(r'#[a-fA-F0-9]{6}', value):
            raise ValueError('Renk #RRGGBB biçiminde olmalı.')
        return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
    def luminance(values):
        channels = [channel / 255 for channel in values]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    first, second = rgb(foreground), rgb(background)
    left, right = sorted((luminance(first), luminance(second)))
    ratio = (right + .05) / (left + .05)
    return {'rgb': first, 'ratio': ratio, 'aa': ratio >= 4.5, 'aaa': ratio >= 7, 'large_aa': ratio >= 3}


ZONES = ('Europe/Istanbul', 'Europe/London', 'Europe/Berlin', 'America/New_York', 'America/Los_Angeles',
         'America/Sao_Paulo', 'Africa/Cairo', 'Asia/Dubai', 'Asia/Kolkata', 'Asia/Tokyo', 'Australia/Sydney', 'Pacific/Auckland')


def world_times(zones=ZONES, now=None):
    if len(zones) > 12 or any(zone not in ZONES for zone in zones):
        raise ValueError('Listelenen en fazla 12 saat dilimini seçin.')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Karşılaştırma saati saat dilimi içermeli.')
    return [{'zone': zone, 'time': now.astimezone(ZoneInfo(zone)).strftime('%H:%M'),
             'date': now.astimezone(ZoneInfo(zone)).strftime('%Y-%m-%d'),
             'offset': now.astimezone(ZoneInfo(zone)).strftime('%z')} for zone in zones]


def transform_text(text, operation):
    _bounded(text, MAX_TEXT)
    if operation == 'Türkçe BÜYÜK': result = text.translate(str.maketrans({'i': 'İ', 'ı': 'I'})).upper()
    elif operation == 'Türkçe küçük': result = text.translate(str.maketrans({'I': 'ı', 'İ': 'i'})).lower()
    elif operation == 'Satırları sırala': result = '\n'.join(sorted(text.splitlines(), key=normalized))
    elif operation == 'Tekrarlı satırları kaldır': result = '\n'.join(dict.fromkeys(text.splitlines()))
    elif operation == 'Kenar boşluklarını temizle': result = '\n'.join(line.strip() for line in text.splitlines()).strip()
    else: raise ValueError('Metin işlemi tanınmadı.')
    return {'text': result, 'characters': len(result), 'words': len(result.split()), 'lines': len(result.splitlines())}


def _desktop(path, *, owner=None):
    stream, info = _regular(path, 65536)
    with stream:
        if owner is not None and info.st_uid != owner: raise ValueError('Kişisel başlangıç dosyası bu hesaba ait değil.')
        text = _read_limited(stream, 65536).decode('utf-8')
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read_string(text)
    section = parser['Desktop Entry']
    if section.get('Type', 'Application') != 'Application':
        raise ValueError('Uygulama başlangıcı değil.')
    return parser, text


def startup_entries(user_directory=None, system_directories=(Path('/etc/xdg/autostart'),), *, cancel=None):
    user = Path(user_directory) if user_directory is not None else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
    found = {}
    started = time.monotonic()
    for directory in (*system_directories, user):
        directory = Path(directory)
        if directory.is_symlink(): continue
        try:
            names = []
            with os.scandir(directory) as entries:
                for number, entry in enumerate(entries):
                    check_cancel(cancel)
                    if number >= 4096 or time.monotonic() - started > 8:
                        raise ValueError('Başlangıç taraması sınırı aşıldı; klasörü kendi ayar aracınızla denetleyin.')
                    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop', entry.name):
                        if len(names) >= 256: raise ValueError('Bir klasörde en fazla 256 başlangıç kaydı listelenir.')
                        names.append(directory / entry.name)
        except FileNotFoundError:
            continue
        for path in sorted(names):
            check_cancel(cancel)
            try:
                parser, _ = _desktop(path)
                section = parser['Desktop Entry']
                prior = found.get(path.name, {})
                found[path.name] = {'id': path.name, 'name': section.get('Name[tr]', section.get('Name', prior.get('name', path.stem)))[:160],
                                    'command': section.get('Exec', prior.get('command', ''))[:300],
                                    'enabled': section.get('Hidden', 'false').lower() != 'true' and section.get('X-GNOME-Autostart-enabled', 'true').lower() != 'false',
                                    'scope': 'Kullanıcı' if directory == user else 'Sistem',
                                    'only': section.get('OnlyShowIn', prior.get('only', ''))[:100]}
            except (OSError, ValueError, configparser.Error, KeyError):
                continue
    return sorted(found.values(), key=lambda row: normalized(row['name']))


def toggle_startup(identifier, enabled, user_directory=None, journal_root=None, *, system_directories=(Path('/etc/xdg/autostart'),)):
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop', identifier) or type(enabled) is not bool:
        raise ValueError('Sabit bir başlangıç kaydı seçin.')
    user = Path(user_directory) if user_directory is not None else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
    _, directory = _directory(user, create=True)
    journal_root = Path(journal_root) if journal_root is not None else Library().root / 'startup'
    journal = lock = None
    try:
        _, journal = _directory(journal_root, create=True)
        lock = _lock_at(journal)
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError('Başlangıç klasörü bu hesabın özel / salt kendince yazılabilir klasörü olmalı.')
        try:
            parser, original = _desktop(user / identifier, owner=os.getuid())
        except FileNotFoundError:
            # A Hidden-only override cannot later be enabled by setting false:
            # it shadows the vendor Exec as well. Copy the complete existing
            # desktop entry, never synthesize an incomplete autostart command.
            parser = None
            for system in reversed(system_directories):
                try:
                    parser, _ = _desktop(Path(system) / identifier)
                    break
                except FileNotFoundError:
                    continue
            if parser is None:
                raise ValueError('Başlangıç girdisi artık yok; listeyi yenileyin. Yeni komut eklenmez.')
            original = None
        if enabled and not parser['Desktop Entry'].get('Exec', '').strip():
            raise ValueError('Bu kayıt yalnızca gizleme işaretidir, çalıştırma komutu yok. Uygulamanın kendi başlangıç ayarını kullanın.')
        record_name = identifier + '.json'
        try:
            stream, _ = _regular(journal_root / record_name, 256 * 1024)
        except FileNotFoundError:
            record = {'original': original}
        else:
            with stream:
                record = json.loads(_read_limited(stream, 256 * 1024))
            if (hashlib.sha256((original or '').encode()).hexdigest() != record['after']
                    and original != record['original']):
                raise ValueError('Kişisel başlangıç dosyası dışarıdan değişmiş; üzerine yazılmadı.')
        parser['Desktop Entry']['Hidden'] = 'false' if enabled else 'true'
        if 'X-GNOME-Autostart-enabled' in parser['Desktop Entry']:
            parser['Desktop Entry']['X-GNOME-Autostart-enabled'] = 'true' if enabled else 'false'
        output = io.StringIO(); parser.write(output, space_around_delimiters=False)
        text = output.getvalue()
        record['after'] = hashlib.sha256(text.encode()).hexdigest()
        _atomic_at(journal, record_name, json.dumps(record).encode())
        _atomic_at(directory, identifier, text.encode())
        return 'Sonraki oturum için kaydedildi; çalışan uygulama durdurulmadı.'
    finally:
        if lock is not None: os.close(lock)
        if journal is not None: os.close(journal)
        os.close(directory)


def restore_startup(identifier, user_directory=None, journal_root=None):
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.desktop', identifier):
        raise ValueError('Başlangıç kimliği geçersiz.')
    user = Path(user_directory) if user_directory is not None else Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
    journal_root = Path(journal_root) if journal_root is not None else Library().root / 'startup'
    _, journal = _directory(journal_root)
    lock = directory = None
    try:
        lock = _lock_at(journal)
        stream, info = _regular(journal_root / (identifier + '.json'), 256 * 1024)
        with stream:
            if info.st_uid != os.getuid(): raise ValueError('Geri alma kaydı bu hesaba ait değil.')
            record = json.loads(_read_limited(stream, 256 * 1024))
        try:
            _, current = _desktop(user / identifier, owner=os.getuid())
        except FileNotFoundError:
            current = None
        # A failed write / interrupted restore may already equal the original.
        # Forget only that journal; do not get stuck or overwrite personal edits.
        if current != record['original']:
            if current is None or hashlib.sha256(current.encode()).hexdigest() != record['after']:
                raise ValueError('Dosya sonradan değişmiş; kişisel değişiklik korunuyor.')
            _, directory = _directory(user)
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or info.st_mode & 0o022: raise ValueError('Kişisel başlangıç klasörü güvenli değil.')
            if record['original'] is None:
                os.unlink(identifier, dir_fd=directory)
            else:
                _atomic_at(directory, identifier, record['original'].encode())
        os.unlink(identifier + '.json', dir_fd=journal)
    finally:
        if directory is not None: os.close(directory)
        if lock is not None: os.close(lock)
        os.close(journal)
    return 'Bu aracın değişikliği geri alındı; sonraki oturumda geçerli.'
