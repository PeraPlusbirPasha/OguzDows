"""OğuzDows bakım sözleşmesi: sabit işlemler, imzalı adaylar, önce plan/onay.

Modül içe aktarılırken ağ, APT veya yetkili işlem çalıştırmaz.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import app_catalog

ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8',
       'LANG': 'C.UTF-8', 'HOME': '/root', 'DEBIAN_FRONTEND': 'noninteractive'}
APT = ['/usr/bin/apt-get', '-o', 'Dpkg::Lock::Timeout=60', '-o', 'Acquire::Retries=1',
       '-o', 'Acquire::http::Timeout=30', '-o', 'Acquire::https::Timeout=30',
       '-o', 'APT::Get::AllowUnauthenticated=false', '-o', 'Acquire::AllowInsecureRepositories=false',
       '-o', 'Acquire::AllowDowngradeToInsecureRepositories=false',
       '-o', 'APT::Update::Error-Mode=any', '-o', 'APT::Get::AutomaticRemove=false',
       '-o', 'Dpkg::Options::=--force-confdef', '-o', 'Dpkg::Options::=--force-confold']
PARDUS_APPS = ('pardus-image-writer', 'pardus-night-light', 'pardus-pen')
DESKTOPS = {
    'kde': ('plasma-desktop', 'plasma-workspace', 'kwin-x11', 'dolphin', 'konsole', 'systemsettings',
            'breeze', 'kwin-common', 'plasma-pa', 'plasma-nm', 'powerdevil', 'kde-config-gtk-style', 'kde-cli-tools'),
    'gnome': ('gnome-session', 'gnome-session-xsession', 'gnome-shell', 'gnome-control-center', 'nautilus',
              'gnome-terminal', 'gnome-tweaks', 'gnome-shell-extension-prefs'),
}
DRIVERS = {
    'intel-wifi': ('firmware-iwlwifi',), 'realtek': ('firmware-realtek',),
    'atheros': ('firmware-atheros',), 'broadcom-open': ('firmware-brcm80211',),
    'amd-graphics': ('firmware-amd-graphics',), 'libertas': ('firmware-libertas',),
    'intel-graphics': ('firmware-intel-graphics',), 'mediatek': ('firmware-mediatek',),
    'nvidia-firmware': ('firmware-nvidia-graphics',),
}
VENDORS = {'8086': 'intel-wifi', '10ec': 'realtek', '0bda': 'realtek', '168c': 'atheros',
           '0cf3': 'atheros', '14e4': 'broadcom-open', '0a5c': 'broadcom-open',
           '1002': 'amd-graphics', '11ab': 'libertas', '14c3': 'mediatek', '148f': 'mediatek',
           '10de': 'nvidia-firmware'}
CHANNEL = Path('/etc/apt/sources.list.d/oguzdows-pardus.sources')
PREFERENCES = Path('/etc/apt/preferences.d/oguzdows-pardus')
PARDUS_KEY = Path('/usr/share/keyrings/oguzdows-pardus.asc')
# Resmî arşiv-anahtarlık kaynağı, d28a52a8 commit'i; testing anahtarı alınmaz.
PARDUS_KEY_SHA256 = '7e0f0db2d7ef3aea57bb41469286061a050a184fbfd6f6fee8fb946d78af686e'
PARDUS_FINGERPRINT = '88561F1612B981756C6C9E94026440E60FE45435'
PARDUS_INRELEASE = 'https://depo.pardus.org.tr/pardus/dists/yirmibes/InRelease'


class MaintenanceError(ValueError):
    pass


def build_info(path=Path('/usr/share/oguzdows/build-info.json')):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise MaintenanceError('OğuzDows taban kimliği okunamadı; depo / paket işlemi yapılmadı.')
    if (not isinstance(data, dict) or data.get('platform') == 'raspberrypi'
            or (data.get('arch'), data.get('suite')) not in (('amd64', 'trixie'), ('i386', 'bookworm'))):
        raise MaintenanceError('Bu bakım sürümü yalnızca doğrulanan OğuzDows PC tabanları içindir.')
    return data


def build_desktop_info(path=Path('/usr/share/oguzdows/build-info.json')):
    """Sadece sabit desktop: demetleri için ayrı PC / ARM64 sözleşmesi."""
    data = build_store_info(path)
    if data['arch'] not in ('amd64', 'arm64'):
        raise MaintenanceError('Gerçek Plasma / GNOME amd64 veya ARM64 gerektirir; Zero / armhf için hafif Xfce düzenleri korunur.')
    return data


def desktop_resources(memory_kib, legacy=False):
    # MemTotal, 2 GiB kartta ayrılan GPU / firmware belleğinden daha küçüktür.
    if legacy or memory_kib < 1792000:
        raise MaintenanceError('Gerçek Plasma / GNOME için en az 2 GiB sınıfı cihaz gerekir; 4 GiB ve çalışan 3B sürücü önerilir. 512 MiB / 1 GiB ve Zero için hafif düzeni seçin.')


def build_store_info(path=Path('/usr/share/oguzdows/build-info.json')):
    """Yalnızca sabit mağaza app: istekleri için ayrı ARM tabanı sözleşmesi.

    Genel bakım / sürücü / depo işlemlerinin PC sınırı genişletilmez;
    gerçek masaüstü işlemi ayrıca build_desktop_info ile daraltılır.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        raise MaintenanceError('Mağaza için imaj kimliği okunamadı.')
    if isinstance(data, dict):
        if data.get('platform') == 'raspberrypi' and data.get('arch') in ('armhf', 'arm64') and data.get('suite') == 'bookworm':
            return data
        if (data.get('platform') == 'arm' and data.get('arch') == 'arm64' and data.get('suite') == 'trixie'
                and data.get('device_profile') in ('arm64-uefi', 'pinephone', 'pinephone-pro', 'rockpro64')):
            return data
    return build_info(path)


def driver_suggestions(sysfs=Path('/sys/bus'), suite='trixie'):
    found = {}
    for bus in ('pci', 'usb'):
        for device in sorted((sysfs / bus / 'devices').glob('*')):
            try:
                vendor = (device / ('vendor' if bus == 'pci' else 'idVendor')).read_text().strip().lower().removeprefix('0x')
                kind = (device / 'class').read_text().strip().lower() if bus == 'pci' else ''
            except OSError:
                continue
            # PCI'de yalnızca kablosuz ağ / görüntü; USB'de bilinen firmware üreticileri.
            if bus == 'pci' and not kind.startswith(('0x0280', '0x03')):
                continue
            choice = 'intel-graphics' if vendor == '8086' and kind.startswith('0x03') else VENDORS.get(vendor)
            if choice is None:
                continue
            packages = DRIVERS[choice]
            if suite == 'bookworm' and choice in ('intel-graphics', 'mediatek', 'nvidia-firmware'):
                packages = ('firmware-misc-nonfree',)
            entry = found.setdefault(choice, {'id': choice, 'packages': list(packages), 'devices': [], 'unbound': False})
            entry['devices'].append(device.name)
            entry['unbound'] |= not (device / 'driver').is_symlink()
    return list(found.values())


def request_packages(request, info, suggestions=None):
    if request == 'upgrade':
        return None
    if request.startswith(('app:', 'remove-app:')):
        identifier = request.partition(':')[2]
        if info.get('arch') not in ('amd64', 'i386') and identifier == 'wine':
            raise MaintenanceError('Windows Wine demeti yalnızca x86 PC içindir. ARM emülasyonu varsayılmadı.')
        try:
            return app_catalog.packages(identifier)
        except ValueError as error:
            raise MaintenanceError(str(error)) from error
    if request.startswith('desktop:') and request[8:] in DESKTOPS:
        if info['arch'] not in ('amd64', 'arm64'):
            raise MaintenanceError('Gerçek KDE/GNOME için amd64 veya ARM64 gerekir; armhf / Zero için Xfce düzenleri kullanılır.')
        packages = list(DESKTOPS[request[8:]])
        if info['suite'] == 'bookworm':
            # GNOME 43 X11 dosyası gnome-session içindedir; ayrı paket yeni tabandadır.
            packages = [name for name in packages if name != 'gnome-session-xsession']
        # Bookworm / trixie startplasma-x11 ve Xsession girdisini zaten
        # plasma-workspace sağlar. Daha yeni bir tabanın paket ayrımını taşıma.
        return packages
    if request.startswith('driver:'):
        choice = request[7:]
        found = driver_suggestions(suite=info['suite']) if suggestions is None else suggestions
        match = next((item for item in found if item['id'] == choice), None)
        if match:
            return match['packages']
        raise MaintenanceError('Bu bilgisayarda seçilen firmware ile eşleşen aygıt yok; sürücüler zorlanmadı.')
    if request.startswith('pardus:') and request[7:] in PARDUS_APPS:
        if info['arch'] != 'amd64' or info['suite'] != 'trixie':
            raise MaintenanceError('Pardus 25 uygulama kanalı yalnızca amd64 / trixie ile eşleştirildi.')
        return [request[7:]]
    raise MaintenanceError('İzin verilmeyen bakım isteği. Serbest paket / komut kabul edilmez.')


def apt_command(request, info, simulate=False, suggestions=None):
    packages = request_packages(request, info, suggestions)
    command = [*APT, '--simulate' if simulate else '--assume-yes']
    if request.startswith('remove-app:'):
        # No purge, autoremove, wildcard, arbitrary package or force flag.
        return [*command, 'remove', *packages]
    command.append('--no-remove')
    if packages is None:
        return [*command, '--with-new-pkgs', 'upgrade']
    return [*command, '--no-install-recommends', 'install', *packages]


def parse_plan(text):
    if any(line.startswith('Remv ') for line in text.splitlines()):
        raise MaintenanceError('İşlem paket kaldırmak istiyor. Otomatik işlem reddedildi; sistem korunuyor.')
    changes = []
    for line in text.splitlines():
        if line.startswith('Inst '):
            # APT bazı ara bağımlılık durumlarını kapanış parantezinden sonra
            # [] / [paket:amd64 ] ile gösterir. Bu tanı eki paket / sürümün
            # parçası değildir; gerçek aday ve imzalı köken yine denetlenir.
            match = re.fullmatch(r'Inst ([a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?) (?:\[[^\]]+\] )?\(([^\s()]+) .+\)(?: \[[^\]\r\n]*\])*', line)
            if not match:
                raise MaintenanceError('APT planındaki paket / sürüm biçimi tanınmadı; işlem yapılmadı.\nTeknik satır: ' + line[:350])
            changes.append({'package': match[1], 'version': match[2], 'detail': line})
    return changes



def removal_plan(text, packages, cache):
    """Only explicitly catalogued app packages may go; never dependencies.

    APT itself resolves reverse dependencies. If that resolution includes ANY
    extra removal or install the whole plan is refused. Personal app data and
    package configuration are retained (remove, not purge / autoremove).
    """
    allowed = set(packages)
    changes = []
    for line in text.splitlines():
        if line.startswith(('Inst ', 'Conf ')):
            raise MaintenanceError('Kaldırma planı başka paket kurmak / yapılandırmak istiyor; reddedildi.')
        if not line.startswith('Remv '):
            continue
        match = re.fullmatch(r'Remv ([a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?) \[([^\]\s]+)\](?:.*)', line)
        if not match:
            raise MaintenanceError('APT kaldırma satırı doğrulanamadı; paketler korunuyor.')
        name, version = match[1], match[2]
        base = name.split(':')[0]
        if base not in allowed or name not in cache:
            raise MaintenanceError('Kaldırma başka bir paketi de etkiliyor: ' + name + '. Dar mağaza planı reddedildi.')
        package = cache[name]
        installed = package.installed
        if (installed is None or installed.version != version or package.essential
                or installed.priority in ('required', 'important')):
            raise MaintenanceError('Temel / önemli paket ya da değişmiş kurulum durumu kaldırılamaz: ' + name)
        changes.append({'package': name, 'version': version, 'operation': 'remove', 'detail': line})
    return changes


def verify_origins(changes, cache, request, info):
    allowed_suites = {info['suite'], info['suite'] + '-security', info['suite'] + '-updates'}
    for change in changes:
        name = change['package']
        candidate = cache[name].candidate
        if candidate is None or candidate.version != change['version']:
            raise MaintenanceError('Plan sürümü ile doğrulanan paket adayı eşleşmiyor: ' + name)
        if candidate.architecture not in ('all', info['arch']):
            raise MaintenanceError('Bu mimari için doğrulanmayan paket: ' + name)
        trusted = [origin for origin in candidate.origins if origin.trusted]
        debian = any(origin.origin == 'Debian' and origin.codename in allowed_suites for origin in trusted)
        # Pi uygulamaları kendi imzası doğrulanmış mevcut pi-gen kaynaklarını
        # kullanır. Başka dağıtım kaynağı eklenmez; PC kuralı değişmez.
        pi = (info.get('platform') == 'raspberrypi' and request.startswith(('app:', 'desktop:'))
              and info['suite'] == 'bookworm' and info['arch'] in ('armhf', 'arm64')
              and any(origin.origin in ('Raspbian', 'Raspberry Pi Foundation')
                      and origin.codename in allowed_suites for origin in trusted))
        pardus = (info['arch'] == 'amd64' and info['suite'] == 'trixie'
                  and name.split(':')[0] in PARDUS_APPS
                  and any(origin.origin == 'Pardus' and origin.codename == 'yirmibes' for origin in trusted))
        if not debian and not pi and not (pardus and (request == 'upgrade' or request.startswith('pardus:'))):
            raise MaintenanceError('Paketin imzalı kaynağı / taban sürümü izinli değil: ' + name
                                   + '. Ubuntu/Kali/Pardus temel sistem paketleri karıştırılmadı.')


def make_plan(request, info, execute, cache, suggestions=None):
    command = apt_command(request, info, True, suggestions)
    text = execute(command)
    removing = request.startswith('remove-app:')
    changes = removal_plan(text, request_packages(request, info, suggestions), cache) if removing else parse_plan(text)
    if not removing:
        verify_origins(changes, cache, request, info)
    # APT'nin tuttuğu paketleri de kullanıcıya göster; plan değişirse yeniden onay.
    digest = hashlib.sha256((request + '\n' + text).encode()).hexdigest()
    return {'request': request, 'token': digest, 'changes': changes, 'detail': text,
            'intent': 'remove' if removing else 'install',
            'note': ('Yalnız seçili uygulamanın katalog paketleri kaldırılır. Bağımlılıklar, kişisel dosyalar ve yapılandırma korunur. Başka paketin kaldırılması istenirse işlem reddedilir.'
                     if removing else 'Paket kaldırma ve dağıtım yükseltmesi kapalıdır. Tutulan paketler zorlanmaz.')}


def apply_plan(request, token, info, execute, cache, suggestions=None):
    if not re.fullmatch(r'[0-9a-f]{64}', token or ''):
        raise MaintenanceError('Geçerli önizleme / onay yok.')
    plan = make_plan(request, info, execute, cache, suggestions)
    if plan['token'] != token:
        raise MaintenanceError('Paket planı değişti. Yeniden denetleyip yeni planı onaylayın.')
    if plan['changes']:
        execute(apt_command(request, info, False, suggestions))
    return {'message': 'İşlem tamamlandı. Çekirdek / firmware güncellendiyse yeniden başlatın.',
            'changed': len(plan['changes'])}


def pardus_source(enabled=False):
    return ('# OğuzDows: yalnızca seçili Pardus uygulamaları; temel paketler pin ile engellenir.\n'
            'Types: deb\nURIs: https://depo.pardus.org.tr/pardus\nSuites: yirmibes\n'
            'Components: main\nArchitectures: amd64\n'
            'Signed-By: /usr/share/keyrings/oguzdows-pardus.asc\n'
            'Check-Valid-Until: yes\nValid-Until-Max: 7776000\n'
            'Enabled: ' + ('yes' if enabled else 'no') + '\n')


def pardus_preferences():
    return ('# Önce dar uygulama listesi; bağımlılıklar temel dağıtımdan çözülür.\n'
            'Package: ' + ' '.join(PARDUS_APPS) + '\nPin: release o=Pardus,n=yirmibes\nPin-Priority: 100\n\n'
            'Package: *\nPin: release o=Pardus\nPin-Priority: -1\n\n'
            'Package: *\nPin: origin "depo.pardus.org.tr"\nPin-Priority: -1\n')


def channel_controls(info, key=PARDUS_KEY, preferences=PREFERENCES):
    if info['arch'] != 'amd64' or info['suite'] != 'trixie':
        raise MaintenanceError('Bu taban için Pardus kanalı desteklenmiyor; temel kaynaklar korunuyor.')
    if key.is_symlink() or not key.is_file() or hashlib.sha256(key.read_bytes()).hexdigest() != PARDUS_KEY_SHA256:
        raise MaintenanceError('Sabitlenen Pardus imza anahtarı eksik / değişmiş; kanal etkinleştirilmedi.')
    if preferences.is_symlink() or not preferences.is_file() or preferences.read_text() != pardus_preferences():
        raise MaintenanceError('Pardus paket sınırlandırma dosyası eksik / değişmiş; kanal etkinleştirilmedi.')


def validate_pardus_release(signed_text, now=None):
    # İmza doğrulaması gpgv ile ÖNCE yapılır. Bu fonksiyon yalnızca imzalı
    # metnin beklenen sürüm / mimari / tazelik sözleşmesini değerlendirir.
    values = dict(re.findall(r'^(Origin|Suite|Codename|Architectures|Date): (.+)$', signed_text, re.MULTILINE))
    if (values.get('Origin') != 'Pardus' or values.get('Suite') != 'yirmibes'
            or values.get('Codename') != 'yirmibes' or 'amd64' not in values.get('Architectures', '').split()):
        raise MaintenanceError('İmzalı Pardus deposu beklenen 25 / amd64 kanalı değil.')
    try:
        stamp = parsedate_to_datetime(values['Date'])
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
    except (KeyError, ValueError, TypeError, OverflowError):
        raise MaintenanceError('Depo tarihi doğrulanamadı.')
    if not -86400 <= age <= 90 * 86400:
        raise MaintenanceError('Depo tarihi eski / gelecekte; sistem saatini ve Pardus kanalını kontrol edin.')


def atomic_channel(enabled, info, path=CHANNEL, key=PARDUS_KEY, preferences=PREFERENCES, verify_release=None):
    if path.is_symlink():
        raise MaintenanceError('Depo dosyası beklenmeyen bir bağlantı; değiştirilmedi.')
    if enabled:
        channel_controls(info, key, preferences)
        if verify_release is None:
            raise MaintenanceError('Güncel depo imzası denetlenmeden Pardus kanalı açılamaz.')
        validate_pardus_release(verify_release())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.sources.new')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(pardus_source(enabled))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return {'message': 'Pardus uygulama kanalı ' + ('açıldı; önce paket listesini yenileyin.' if enabled else 'kapatıldı. Kurulu uygulamalar silinmedi.')}


def memory_report(text=None):
    if text is None:
        text = Path('/proc/meminfo').read_text()
    fields = {line.split(':')[0]: int(line.split()[1]) for line in text.splitlines()
              if line.startswith(('MemTotal:', 'MemAvailable:', 'SwapTotal:', 'SwapFree:'))}
    if not {'MemTotal', 'MemAvailable'} <= fields.keys() or not 0 <= fields['MemAvailable'] <= fields['MemTotal']:
        raise MaintenanceError('MemAvailable bilgisi okunamadı; bellek kullanımı tahmin edilmedi.')
    used = (fields['MemTotal'] - fields['MemAvailable']) * 1024
    return {'used_bytes': used, 'used_mb': round(used / 1_000_000, 1),
            'total_bytes': fields['MemTotal'] * 1024, 'available_bytes': fields['MemAvailable'] * 1024,
            'used_mib': round(used / 1048576, 1), 'target_bytes': 600_000_000,
            'within_target': used <= 600_000_000,
            'method': 'MemTotal − MemAvailable; önbellek boşaltılmadı, zram RAM kazancı diye sayılmadı.',
            'machine': platform.machine(), 'measurement': 'anlık; boşta olduğunuzu tek başına kanıtlamaz'}
