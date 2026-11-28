"""EXE / APK incelemesi ve koşullu başlatma planı. İçe aktarmada işlem yok.

Bu araç antivirüs / sandbox değildir. Hiçbir dosya inceleme veya MIME eşleşmesi
nedeniyle otomatik çalıştırılmaz. Dosya onaydan sonra özel dizine hash ile
kopyalanır; özgün dosyanın değişmesi reddedilir. root olarak çalıştırma yoktur.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import stat
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

WINE = '/usr/bin/wine'
WAYDROID = '/usr/bin/waydroid'
MAX_EXE = 2 * 1024**3
MAX_APK = 512 * 1024**2
MACHINES = {0x14c: 'x86', 0x8664: 'x86_64', 0xaa64: 'arm64'}


def open_regular(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Yalnızca normal, yerel bir dosya seçin. Bağlantı / aygıt / boru çalıştırılmaz.')
        return os.fdopen(descriptor, 'rb'), info
    except Exception:
        os.close(descriptor)
        raise


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def digest(stream, maximum):
    stream.seek(0)
    value = hashlib.sha256()
    size = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            return value.hexdigest()
        size += len(block)
        if size > maximum:
            raise ValueError('Dosya boyut sınırını aşıyor; işlem yapılmadı.')
        value.update(block)


def pe_info(stream, size):
    stream.seek(0)
    header = stream.read(64)
    if len(header) < 64 or header[:2] != b'MZ':
        raise ValueError('Dosya geçerli Windows PE başlığı taşımıyor.')
    offset = struct.unpack_from('<I', header, 60)[0]
    if not 64 <= offset <= min(1024 * 1024, size - 24):
        raise ValueError('Windows başlık konumu geçersiz.')
    stream.seek(offset)
    header = stream.read(24)
    if len(header) != 24 or header[:4] != b'PE\0\0':
        raise ValueError('Eski DOS / bilinmeyen MZ dosyası otomatik çalıştırılmaz.')
    machine, sections, _timestamp, _symbols, _count, optional_size, flags = struct.unpack('<HHIIIHH', header[4:])
    if machine not in MACHINES or not 1 <= sections <= 96 or flags & 0x2000 or not 96 <= optional_size <= 4096:
        raise ValueError('PE mimarisi / bölüm yapısı desteklenmiyor veya dosya DLL türünde.')
    if offset + 24 + optional_size + sections * 40 > size:
        raise ValueError('Windows bölüm tablosu eksik.')
    magic = stream.read(2)
    if magic not in (b'\x0b\x01', b'\x0b\x02') or (machine == 0x14c) != (magic == b'\x0b\x01'):
        raise ValueError('Windows mimarisi ve PE türü eşleşmiyor.')
    return {'kind': 'exe', 'architecture': MACHINES[machine], 'abis': [],
            'note': 'PE başlığı ve SHA-256 okundu; dijital imza / zararlı yazılım doğrulaması yapılmadı.'}


def apk_info(stream, size):
    # ZipFile büyük bir merkez dizini belleğe almadan ÖNCE EOCD sınırlandırılır.
    stream.seek(max(0, size - 65557))
    tail = stream.read(65557)
    index = tail.rfind(b'PK\x05\x06')
    if index < 0 or index + 22 > len(tail):
        raise ValueError('APK ZIP dizini bulunamadı.')
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, comment = struct.unpack('<4s4H2IH', tail[index:index + 22])
    end_offset = max(0, size - 65557) + index
    if (disk or cd_disk or disk_count != count or not 1 <= count <= 10000
            or cd_size > 8 * 1024**2 or cd_offset + cd_size > end_offset
            or index + 22 + comment != len(tail)):
        raise ValueError('APK arşivi bölünmüş / ZIP64 / çok büyük veya geçersiz.')
    stream.seek(0)
    with zipfile.ZipFile(stream) as archive:
        entries = archive.infolist()
        if len(entries) != count:
            raise ValueError('APK dosya sayısı tutarsız.')
        names, abis, total = set(), set(), 0
        for entry in entries:
            name = entry.filename
            parts = name.rstrip('/').split('/')
            mode = entry.external_attr >> 16
            if (name in names or name.startswith('/') or '\\' in name or '\x00' in name
                    or any(part in ('', '.', '..') for part in parts) or stat.S_ISLNK(mode)
                    or entry.flag_bits & 1 or entry.file_size > MAX_APK):
                raise ValueError('APK içinde güvenli olmayan / belirsiz arşiv girdisi var.')
            total += entry.file_size
            if total > 2 * 1024**3 or entry.file_size > max(1, entry.compress_size) * 1000:
                raise ValueError('APK açılmış boyut / sıkıştırma sınırını aşıyor.')
            names.add(name)
            if len(parts) >= 3 and parts[0] == 'lib' and name.endswith('.so'):
                abis.add(parts[1])
        if 'AndroidManifest.xml' not in names:
            raise ValueError('AndroidManifest.xml yok; bu dosya bir APK değil.')
    return {'kind': 'apk', 'architecture': ', '.join(sorted(abis)) or 'Evrensel / Java (yerel ABI bildirilmedi)',
            'abis': sorted(abis),
            'note': 'APK açılmadan arşiv listesi okundu. Android imzası / geliştirici / zararlı yazılım doğrulanmadı. Android sürümü uyumu ayrıca gerekir.'}


def inspect(path):
    path = Path(path).absolute()
    if path.suffix.lower() not in ('.exe', '.apk'):
        raise ValueError('Yalnızca .exe veya .apk dosyası seçin.')
    maximum = MAX_APK if path.suffix.lower() == '.apk' else MAX_EXE
    stream, before = open_regular(path)
    with stream:
        if not 0 < before.st_size <= maximum:
            raise ValueError('Dosya boş veya desteklenen boyut sınırının dışında.')
        result = apk_info(stream, before.st_size) if path.suffix.lower() == '.apk' else pe_info(stream, before.st_size)
        checksum = digest(stream, maximum)
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError('Dosya inceleme sırasında değişti. Yeniden seçin.')
    return {**result, 'path': str(path), 'name': path.name, 'size': before.st_size,
            'identity': identity(before), 'sha256': checksum}


def read(path):
    try:
        return path.read_text(errors='replace')
    except OSError:
        return ''


def capabilities(root=Path('/'), machine=None, environ=None):
    machine = platform.machine() if machine is None else machine
    environ = os.environ if environ is None else environ
    memory = re.search(r'^MemTotal:\s+(\d+)', read(root / 'proc/meminfo'), re.MULTILINE)
    memory_kib = int(memory[1]) if memory else 0
    display = environ.get('WAYLAND_DISPLAY', '')
    runtime = Path(environ.get('XDG_RUNTIME_DIR', '/nonexistent'))
    socket = Path(display) if display.startswith('/') else runtime / display
    try:
        wayland = bool(display) and stat.S_ISSOCK(socket.stat().st_mode) and socket.stat().st_uid == os.getuid()
    except OSError:
        wayland = False
    return {'machine': machine, 'memory_kib': memory_kib,
            'wine': (root / WINE.lstrip('/')).is_file(),
            'wine32': any((root / path).is_file() for path in ('usr/lib/i386-linux-gnu/wine/i386-windows/ntdll.dll', 'usr/lib/wine/i386-windows/ntdll.dll')),
            'waydroid': (root / WAYDROID.lstrip('/')).is_file(), 'wayland': wayland,
            'binder': any((root / path).exists() for path in ('dev/binder', 'dev/binderfs/binder', 'dev/anbox-binder'))}


def availability(receipt, caps, execute=None):
    reasons = []
    kind, architecture = receipt['kind'], receipt['architecture']
    if kind == 'exe':
        if caps['machine'] not in ('x86_64', 'i386', 'i486', 'i586', 'i686'):
            reasons.append('Bu sürüm ARM üzerinde Windows / x86 emülasyonu kurmaz.')
        if architecture not in ('x86', 'x86_64') or architecture == 'x86_64' and caps['machine'] != 'x86_64':
            reasons.append('EXE mimarisi bu PC ile eşleşmiyor.')
        if not caps['wine']:
            reasons.append('Wine kurulu değil. Mağaza → Windows Uyumluluğu planını ayrıca onaylayabilirsin.')
        if architecture == 'x86' and not caps['wine32']:
            reasons.append('32-bit Wine çalışma alanı bulunamadı. 32-bit / çoklu mimari paketleri otomatik eklenmez.')
    elif kind == 'apk':
        if caps['machine'] not in ('aarch64', 'x86_64'):
            reasons.append('Bu mimaride Android uyumluluğu sunulmuyor; Pi Zero / ARMv6 için uygun değil.')
        if not caps['waydroid']:
            reasons.append('Waydroid kurulu / hazırlanmış değil. Rastgele APK veya işletim sistemi deposu eklenmedi.')
        if not caps['wayland']:
            reasons.append('Çalışan bir Wayland oturumu gerekli; Xfce X11 tek başına yeterli değil.')
        if not caps['binder']:
            reasons.append('Çekirdekte Android binder aygıtı görünmüyor; modül / çekirdek zorlanmaz.')
        if caps['memory_kib'] < 1536 * 1024:
            reasons.append('Waydroid için en az 2 GB sınıfı cihaz ve boş bellek gerekir; 4 GB önerilir.')
        expected = 'arm64-v8a' if caps['machine'] == 'aarch64' else 'x86_64'
        if receipt['abis'] and expected not in receipt['abis']:
            reasons.append('APK yerel kütüphaneleri bu cihazın 64-bit ABI’siyle eşleşmiyor. Çeviri katmanı varsayılmadı.')
        if not reasons and execute is not None:
            output = execute([WAYDROID, 'status'])
            output = re.sub(r'\x1b\[[0-9;]*m', '', output)
            if not all(re.search(r'^' + key + r':\s*RUNNING\s*$', output, re.MULTILINE | re.IGNORECASE) for key in ('Session', 'Container')):
                reasons.append('Waydroid oturumu ve kapsayıcısı çalışır durumda olmalı. Önce Waydroid’i kendi arayüzünden hazırla.')
    else:
        reasons.append('Desteklenmeyen dosya türü.')
    return reasons


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError('Özel çalışma dizini güvenli / bu kullanıcıya ait değil.')
    path.chmod(0o700)
    return path


def stage(receipt, directory):
    """Onaylanan baytları sabitle. Değişen kaynak / bağlantı / FIFO reddedilir."""
    if os.geteuid() == 0:
        raise ValueError('EXE / APK root olarak çalıştırılmaz. Masaüstü hesabını kullan.')
    maximum = MAX_EXE if receipt['kind'] == 'exe' else MAX_APK
    directory = private_directory(Path(directory))
    stream, before = open_regular(receipt['path'])
    temporary = None
    try:
        with stream:
            if tuple(receipt['identity']) != identity(before):
                raise ValueError('Dosya onaydan sonra değişti. Yeniden incele.')
            descriptor, name = tempfile.mkstemp(prefix=receipt['sha256'][:16] + '-', suffix='.' + receipt['kind'], dir=directory)
            temporary = Path(name)
            checksum, total = hashlib.sha256(), 0
            with os.fdopen(descriptor, 'wb') as output:
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > maximum:
                        raise ValueError('Dosya büyüdü; işlem durduruldu.')
                    checksum.update(block)
                    output.write(block)
            if checksum.hexdigest() != receipt['sha256'] or identity(os.fstat(stream.fileno())) != identity(before):
                raise ValueError('Onaylanan dosya içeriği değişti; hiçbir şey çalıştırılmadı.')
        return temporary
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def launch_plan(receipt, staged, data_directory, caps, execute=None):
    if os.geteuid() == 0:
        raise ValueError('Uyumluluk araçları yönetici olarak başlatılmaz.')
    reasons = availability(receipt, caps, execute)
    if reasons:
        raise ValueError('\n'.join(reasons))
    if receipt['kind'] == 'apk':
        return [WAYDROID, 'app', 'install', str(staged)], {}, None
    prefix = private_directory(Path(data_directory) / 'wine' / receipt['sha256'][:24])
    # Bu dizin yalnızca düzenleme izolasyonudur. Wine ev dosyalarına / ağa
    # erişebilir; prefix bir güvenlik sandbox'ı olarak sunulmaz.
    environment = {'WINEPREFIX': str(prefix), 'WINEDEBUG': '-all'}
    if receipt['architecture'] == 'x86_64':
        environment['WINEARCH'] = 'win64'
    elif caps['machine'] != 'x86_64':
        environment['WINEARCH'] = 'win32'
    return [WINE, str(staged)], environment, str(prefix)


def runtime_status(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, errors='replace', timeout=10, check=False,
                            stdin=subprocess.DEVNULL, env={**os.environ, 'LC_ALL': 'C.UTF-8'})
    if result.returncode:
        raise ValueError('Waydroid durumu alınamadı: ' + result.stderr[-1500:])
    return result.stdout[:8192]
