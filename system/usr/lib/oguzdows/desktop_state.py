"""Ortak masaüstü tercihleri ve dar, karşılaştırmalı geri-alma günlüğü.

Root, kabuk, oturum kapatma ve sürekli izleyici yoktur. Kişisel DE ayarı bizim
son yazdığımız değerden farklıysa geri alma o ayarı EZMEZ. JSON yalnız veridir.
"""
from __future__ import annotations

import contextlib
import copy
import fcntl
import json
import os
import re
import stat
import tempfile
from pathlib import Path

DEFAULTS = {'schema': 1, 'revision': 0, 'appearance': 'light', 'effects': 'off',
            'blur': False, 'motion': 'smooth', 'snap_animation': False,
            'accent': '#36b6c5', 'accent_source': 'theme', 'feedback': False,
            'wallpaper': ''}
LIMIT = 65536


def private_directory(path):
    path = Path(path)
    # Ürüne ait dizinlerde bağ / başka kullanıcı / FIFO kabul edilmez.
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('Masaüstü veri dizini sembolik bağ olamaz.')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Masaüstü veri dizini bu kullanıcıya ait olmalı.')
    path.chmod(0o700)
    return path


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'oguzdows/desktop.json'


def state_directory():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'oguzdows/desktop'


def read_json(path, default=None):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return copy.deepcopy(default)
    with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > LIMIT:
            raise ValueError('Masaüstü kayıt dosyası normal, sınırlı bir kullanıcı dosyası olmalı.')
        text = stream.read(LIMIT + 1)
        if len(text.encode('utf-8')) > LIMIT:
            raise ValueError('Masaüstü kaydı okuma sırasında boyut sınırını aştı.')
        return json.loads(text)


def atomic_json(path, value):
    path = Path(path)
    private_directory(path.parent)
    if path.is_symlink() or path.exists() and not path.is_file():
        raise ValueError('Masaüstü kaydı bağlantı veya özel dosya olamaz.')
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if len(text.encode()) > LIMIT:
        raise ValueError('Masaüstü kaydı boyut sınırını aşıyor.')
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def locked(directory=None):
    directory = private_directory(state_directory() if directory is None else directory)
    descriptor = os.open(directory / '.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError('Masaüstü kilidi normal dosya değil.')
        os.fchmod(lock.fileno(), 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Başka bir masaüstü işlemi devam ediyor.') from error
        yield directory


def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS) or type(value.get('schema')) is not int or value['schema'] != 1:
        raise ValueError('Ortak masaüstü tercih biçimi geçersiz; dosya değiştirilmedi.')
    if type(value['revision']) is not int or not 0 <= value['revision'] < 2**53:
        raise ValueError('Tercih sürümü geçersiz.')
    for key, options in (('appearance', ('light', 'dark')), ('effects', ('off', 'glass', 'aero')),
                         ('motion', ('reduced', 'smooth', 'spring')), ('accent_source', ('theme', 'wallpaper'))):
        if value[key] not in options:
            raise ValueError('Bilinmeyen masaüstü tercihi: ' + key)
    if any(type(value[key]) is not bool for key in ('blur', 'snap_animation', 'feedback')):
        raise ValueError('Efekt anahtarları doğru / yanlış olmalı.')
    if not isinstance(value['accent'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value['accent']):
        raise ValueError('Vurgu rengi #RRGGBB biçiminde olmalı.')
    if not isinstance(value['wallpaper'], str) or not re.fullmatch(r'[a-z0-9-]{0,80}', value['wallpaper']):
        raise ValueError('Duvar kâğıdı katalog kimliği geçersiz.')
    return dict(value, accent=value['accent'].lower())


def load(path=None):
    path = config_path() if path is None else Path(path)
    value = read_json(path)
    if value is None:
        # Önceki Xfce tercihleri kaybolmaz; yükseltme ASLA blur'u otomatik açmaz.
        import profiles
        value = dict(DEFAULTS, appearance=profiles.selection()[1], effects=profiles.effect_selection())
    return validate(value)


def merged(current, changes):
    if not isinstance(changes, dict) or not set(changes) <= set(DEFAULTS) - {'schema', 'revision'}:
        raise ValueError('İzin verilmeyen ortak masaüstü ayarı.')
    return validate({**current, **changes, 'revision': current['revision'] + 1})


class Journal:
    """Arka ucun izin verdiği anahtarlar; ayar başına kalıcı write-ahead kayıt.

    backend.read() varsayılanı None, kullanıcı değerini JSON olarak döndürür.
    backend.write(key, None) yalnızca o kullanıcı override'ını sıfırlar.
    """
    def __init__(self, backend, directory):
        self.backend = backend
        self.path = Path(directory) / (backend.name + '-settings.json')
        value = read_json(self.path, {})
        if not isinstance(value, dict) or len(value) > 256:
            raise ValueError('Masaüstü geri-alma günlüğü geçersiz.')
        for key, row in value.items():
            if key not in backend.keys or not isinstance(row, dict) or set(row) != {'before', 'applied'}:
                raise ValueError('Günlük izin verilmeyen ayar içeriyor.')
            backend.validate(key, row['before'])
            backend.validate(key, row['applied'])
        self.rows = value

    def rollback(self, previous_rows, changed):
        # Kalıcı ortak tercih / oturum makbuzu yazılamazsa da aynı kesin
        # işlem-öncesi değerlere dön. Önceki tercihi tekrar uygulamak kişisel
        # yerel tema veya ilk giriş varsayılanını yanlışlıkla ezebilir.
        for key, old, target in reversed(changed):
            try:
                if self.backend.read(key) == target:
                    self.backend.write(key, old)
                    if self.backend.read(key) != old:
                        raise RuntimeError('Geri alma geri okunarak doğrulanamadı: ' + key)
            except (OSError, ValueError, RuntimeError) as error:
                # Write-ahead kayıt kurtarma için diskte kalır.
                raise RuntimeError('Ayar işlemi yarım kaldı; masaüstü merkezinden geri almayı deneyin.') from error
        self.rows = copy.deepcopy(previous_rows)
        atomic_json(self.path, self.rows)

    def apply(self, changes, undo=None):
        if not set(changes) <= self.backend.keys:
            raise ValueError('Arka uç izin vermediği bir ayara yazamaz.')
        for key, value in changes.items():
            self.backend.validate(key, value)
        previous_rows = copy.deepcopy(self.rows)
        changed = []
        try:
            for key, value in changes.items():
                old = self.backend.read(key)
                self.backend.validate(key, old)
                # Önceki uygulamadan sonra kullanıcı değiştirdiyse yeni kişisel
                # değer geri-alma tabanı olur; ilk eski değerle üzerine basma.
                before = self.rows.get(key, {}).get('before', old)
                if key in self.rows and old != self.rows[key]['applied']:
                    before = old
                self.rows[key] = {'before': before, 'applied': value}
                atomic_json(self.path, self.rows)
                changed.append((key, old, value))
                self.backend.write(key, value)
                if self.backend.read(key) != value:
                    raise RuntimeError('Masaüstü ayarı geri okunarak doğrulanamadı: ' + key)
        except Exception:
            self.rollback(previous_rows, changed)
            raise
        if undo is not None:
            undo.append(lambda: self.rollback(previous_rows, changed))

    def restore(self):
        skipped = []
        for key, row in list(self.rows.items())[::-1]:
            if self.backend.read(key) == row['applied']:
                self.backend.write(key, row['before'])
            else:
                skipped.append(key)
            del self.rows[key]
            atomic_json(self.path, self.rows)
        return skipped
