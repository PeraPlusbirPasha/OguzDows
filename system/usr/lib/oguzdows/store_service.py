#!/usr/bin/env python3
"""Derlenen mağaza için kısa ömürlü JSON arka ucu; daemon / shell / otomatik ağ yok.

APT mevcut dar Polkit yardımcısından geçer. Flatpak yalnızca kullanıcı kurulumu,
resmî imza denetimli Flathub ve yeniden çözümlenip onay özeti karşılaştırılan
libflatpak işlemleri kullanır. Pencereyi açmak indirme / kurulum başlatmaz.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app_catalog
import store_core

HELPER = ['/usr/bin/pkexec', '/usr/local/sbin/oguzdows-maintenance']
FLATPAK = '/usr/bin/flatpak'


def command(arguments, timeout=30):
    result = subprocess.run(arguments, capture_output=True, text=True, errors='replace',
                            stdin=subprocess.DEVNULL, timeout=timeout, check=False,
                            env={**os.environ, 'LC_ALL': 'C.UTF-8'})
    if len(result.stdout) > 2 * 1024 * 1024:
        raise ValueError('Mağaza yanıtı boyut sınırını aştı.')
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:] or result.stdout[-2500:] or 'İşlem tamamlanamadı.')
    return result.stdout.strip()


def image_info():
    try:
        value = json.loads(Path('/usr/share/oguzdows/build-info.json').read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def flatpak_arch(execute=command):
    try:
        return execute([FLATPAK, '--default-arch'])
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return ''


def dpkg_installed(execute=command):
    output = execute(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\t${db:Status-Status}\n'])
    return {line.split('\t')[0].split(':')[0] for line in output.splitlines() if line.endswith('\tinstalled')}


def installed_flatpaks(execute=command):
    try:
        return set(execute([FLATPAK, '--user', 'list', '--app', '--columns=application']).splitlines())
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return set()


def remote_ready(execute=command):
    try:
        return store_core.official_remote(execute([FLATPAK, '--user', 'remotes', '--columns=name,url,options']))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return False


def catalogue(execute=command, info=None):
    info = image_info() if info is None else info
    installed = dpkg_installed(execute)
    flatpaks = installed_flatpaks(execute)
    pc_supported = info.get('platform') != 'raspberrypi' and (info.get('arch'), info.get('suite')) in (('amd64', 'trixie'), ('i386', 'bookworm'))
    pi_supported = info.get('platform') == 'raspberrypi' and info.get('arch') in ('armhf', 'arm64') and info.get('suite') == 'bookworm'
    arm_supported = (info.get('platform') == 'arm' and info.get('arch') == 'arm64' and info.get('suite') == 'trixie'
                     and info.get('device_profile') in ('arm64-uefi', 'pinephone', 'pinephone-pro', 'rockpro64'))
    supported = pc_supported or pi_supported or arm_supported
    architecture = flatpak_arch(execute)
    return {'apps': [{**item, 'packages': list(item['packages']),
                      'installed': all(name in installed for name in item['packages']),
                      'flatpak_installed': item['flatpak'] in flatpaks} for item in app_catalog.APPS],
            'categories': list(app_catalog.CATEGORIES), 'supports_apt': supported, 'supports_updates': pc_supported,
            'supports_advanced': Path('/usr/lib/oguzdows/store.py').is_file(),
            'arch': info.get('arch', 'bilinmiyor'), 'flatpak_arch': architecture,
            'supports_user_flatpak': architecture in ('x86_64', 'aarch64'),
            'remote_ready': remote_ready(execute),
            'message': 'Yerel katalog hazır. Henüz ağ isteği veya paket işlemi yapılmadı.'}


def target(identifier, source):
    if source not in ('system', 'flatpak'):
        raise ValueError('Bilinmeyen uygulama kaynağı.')
    if identifier.startswith('flatpak:'):
        if source != 'flatpak':
            raise ValueError('Flathub arama sonucu sistem paketi değildir.')
        return app_catalog.flatpak_id(identifier[8:])
    item = app_catalog.get(identifier)
    if source == 'flatpak':
        return app_catalog.flatpak_id(item['flatpak'])
    return item['id']


def system_desktop(identifier, directory=Path('/usr/share/applications')):
    app_catalog.get(identifier)
    for name in app_catalog.DESKTOP_IDS.get(identifier, ()):
        path = directory / name
        try:
            details = path.lstat()
            if (stat.S_ISREG(details.st_mode) and details.st_uid == 0 and not details.st_mode & 0o022
                    and path.resolve().parent == directory.resolve()):
                return path
        except OSError:
            pass
    return None


def launch_state(identifier, source, execute=command):
    name = target(identifier, source)
    if source == 'system':
        packages = dpkg_installed(execute)
        installed = all(package in packages for package in app_catalog.packages(name))
        desktop = system_desktop(name) if installed else None
        return {'installed': installed, 'can_launch': desktop is not None, 'source': source}
    arch = flatpak_arch(execute)
    if arch not in ('x86_64', 'aarch64'):
        return {'installed': False, 'can_launch': False, 'source': source}
    try:
        ref = execute([FLATPAK, '--user', 'info', '--show-ref', name])
    except (OSError, RuntimeError, subprocess.SubprocessError):
        ref = ''
    installed = ref == 'app/' + name + '/' + arch + '/stable'
    return {'installed': installed, 'can_launch': installed, 'source': source}


def launch(identifier, source, execute=command, api=None):
    if os.geteuid() == 0:
        raise ValueError('Uygulama root olarak başlatılmaz. Kendi masaüstü hesabınızı kullanın.')
    state = launch_state(identifier, source, execute)
    if not state['installed'] or not state['can_launch']:
        raise ValueError('Bu kaynakta çalıştırılabilir kurulu uygulama bulunamadı. Önce kurulum durumunu yenileyin.')
    if api is None:
        from gi.repository import Gio as api
    name = target(identifier, source)
    if source == 'system':
        path = system_desktop(name)
        if path is None:
            raise ValueError('Sistem masaüstü kısayolu artık yok / değişmiş.')
        application = api.DesktopAppInfo.new_from_filename(str(path))
    else:
        # Gio argv'yi ayrıştırıp başlatır; /bin/sh yok. Uygulama kimliği target()
        # ile doğrulanır. --user sabittir; sistem Flatpak'ı / pkexec çağrılmaz.
        arch = flatpak_arch(execute)
        if arch not in ('x86_64', 'aarch64'):
            raise ValueError('Kullanıcı Flatpak mimarisi değişti.')
        application = api.AppInfo.create_from_commandline(
            FLATPAK + ' run --user --arch=' + arch + ' --branch=stable ' + name,
            None, api.AppInfoCreateFlags.NONE)
    if application is None or not application.launch([], None):
        raise ValueError('Masaüstü başlatma isteğini kabul etmedi.')
    return {'message': 'Başlatma isteği gönderildi. Uygulama penceresini kontrol edin; çalışma / uyumluluk başarısı varsayılmaz.', 'source': source}


def detail(identifier, source, execute=command):
    name = target(identifier, source)
    state = launch_state(identifier, source, execute)
    if source == 'flatpak':
        if flatpak_arch(execute) not in ('x86_64', 'aarch64'):
            raise ValueError('Bu mimaride kullanıcı Flathub uygulamaları sunulmuyor.')
        ready = remote_ready(execute)
        if not ready and state['installed']:
            return {**state, 'detail': 'Bu hesapta kurulu. Flathub metadata kaynağı hazır değil; kurulu uygulama Aç ile başlatılabilir.',
                    'message': 'Yerel kurulum durumu okundu. Kaynak eklenmedi.'}
        if not ready:
            raise ValueError('Önce Kaynaklar bölümünden Flathub’u açık onayla ekleyin.')
        ref = 'app/' + name + '/' + flatpak_arch(execute) + '/stable'
        try:
            text = execute([FLATPAK, '--user', 'remote-info', '--log', 'flathub', ref], timeout=90)
            permissions = execute([FLATPAK, '--user', 'remote-info', '--show-metadata', 'flathub', ref], timeout=90)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            if not state['installed']:
                raise
            return {**state, 'detail': 'Kaynak metadata bilgisi alınamadı: ' + str(error)[:2500],
                    'message': 'Metadata hatası. Kurulu uygulamayı Aç ile başlatabilirsin; yeni kurulum yapılmadı.'}
        return {**state, 'detail': text[:12000] + '\n\nİzin bildirimi (özgün metadata):\n' + permissions[:16000],
                'message': 'İmzalı kaynak metadata bilgisi; kurulum yapılmadı. İzinleri ve geliştirici kimliğini inceleyin.'}
    import apt
    cache = apt.Cache()
    lines = []
    for package in app_catalog.packages(name):
        if package not in cache or cache[package].candidate is None:
            lines.append(package + ': bu taban / mimari için aday bulunamadı.')
            continue
        value = cache[package].candidate
        origins = ', '.join(origin.origin + '/' + origin.codename + (' · imzalı' if origin.trusted else ' · GÜVENİLMEYEN') for origin in value.origins)
        lines.append(package + '\nSürüm: ' + value.version + '\nKaynak: ' + origins
                     + '\nLisans / telif: kurulum sonrası /usr/share/doc/' + package + '/copyright\n'
                     + value.description[:4500])
    return {**state, 'detail': '\n\n'.join(lines), 'message': 'Yerel paket listesi okundu. Aday ve imzalı köken kurulum planında yeniden doğrulanır.'}


def apt_request(operation, identifier, token='', execute=command):
    request = 'upgrade' if identifier == '@updates' else 'app:' + app_catalog.get(identifier)['id']
    arguments = [*HELPER, operation, request]
    if operation == 'apply':
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise ValueError('Geçerli plan onayı gerekli.')
        arguments.append(token)
    result = json.loads(execute(arguments, timeout=None))
    if not isinstance(result, dict) or 'error' in result:
        raise RuntimeError(result.get('error', 'Paket yardımcısından geçersiz yanıt.') if isinstance(result, dict) else 'Geçersiz yanıt.')
    result['source'] = 'system'
    result['detail'] = result.get('detail', result.get('message', ''))
    return result


def search(query, execute=command):
    query = query.strip()
    if not 2 <= len(query) <= 100 or any(ord(char) < 32 for char in query) or query.startswith('-'):
        raise ValueError('Arama için 2–100 karakterlik bir uygulama adı yazın.')
    if not remote_ready(execute):
        raise ValueError('Önce Kaynaklar bölümünden Flathub’u ekleyin. Yerel katalog ağ olmadan aranabilir.')
    output = execute([FLATPAK, '--user', 'search', '--columns=application,name,description,remotes', query], timeout=120)
    apps = []
    for line in output.splitlines():
        columns = line.split('\t')
        if len(columns) != 4 or 'flathub' not in columns[3].split(','):
            continue
        try:
            identifier = app_catalog.flatpak_id(columns[0])
        except ValueError:
            continue
        apps.append({'id': 'flatpak:' + identifier, 'name': columns[1][:120], 'summary': columns[2][:350],
                     'category': 'Flathub', 'flatpak': identifier, 'icon': identifier, 'fallback_icon': 'oguzdows-app-flathub',
                     'packages': [], 'installed': False, 'flatpak_installed': False})
        if len(apps) == 80:
            break
    return {'apps': apps, 'message': str(len(apps)) + ' Flathub sonucu. Bir uygulamanın listelenmesi güvenlik onayı değildir.'}


def plan_digest(operations):
    canonical = sorted(operations, key=lambda row: (row['ref'], row['operation'], row['remote']))
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def flatpak_transaction(identifier, operation, token='', api=None):
    if operation not in ('plan', 'apply') or token and not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Geçersiz Flatpak işlemi / planı.')
    if operation == 'apply' and not token:
        raise ValueError('Kurulumdan önce planı açıkça onaylayın.')
    if os.geteuid() == 0 and api is None:
        raise ValueError('Flatpak mağazası root olarak çalıştırılmaz. Kendi masaüstü hesabınızı kullanın.')
    if api is None:
        import gi
        gi.require_version('Flatpak', '1.0')
        from gi.repository import Flatpak as api
    installation = api.Installation.new_user(None)
    remote = installation.get_remote_by_name('flathub', None)
    if remote.get_url().rstrip('/') != store_core.FLATHUB_URL.rstrip('/') or not remote.get_gpg_verify() or remote.get_disabled():
        raise ValueError('Resmî, etkin ve GPG denetimli Flathub kullanıcı kaynağı gerekli.')
    transaction = api.Transaction.new_for_installation(installation, None)
    transaction.set_no_interaction(True)
    transaction.connect('add-new-remote', lambda *_: False)
    # Hiçbir ek depo sessizce eklenemez. Yeni anahtar veya sistem kurulumu yok.
    if identifier == '@updates':
        for ref in installation.list_installed_refs(None):
            if ref.get_origin() == 'flathub':
                transaction.add_update(ref.format_ref(), None, None)
    else:
        application = target(identifier, 'flatpak')
        arch = api.get_default_arch()
        if arch not in ('x86_64', 'aarch64'):
            raise ValueError('Bu mimaride Flatpak uygulama kapsamı sunulmuyor.')
        ref = 'app/' + application + '/' + arch + '/stable'
        if any(installed.format_ref() == ref for installed in installation.list_installed_refs(None)):
            transaction.add_update(ref, None, None)
        else:
            transaction.add_install('flathub', ref, None)
    captured = None
    refused = None
    def ready(resolved):
        nonlocal captured, refused
        operations = []
        for item in resolved.get_operations():
            if item.get_remote() not in ('flathub', None, ''):
                refused = 'İşlem başka bir kaynaktan bağımlılık istiyor; otomatik depo eklenmedi.'
                return False
            operations.append({'ref': item.get_ref(), 'operation': int(item.get_operation_type()),
                               'remote': item.get_remote() or '', 'commit': item.get_commit() or '',
                               'download_bytes': item.get_download_size(), 'installed_bytes': item.get_installed_size()})
        captured = {'source': 'flatpak', 'token': plan_digest(operations), 'changes': operations,
                    'detail': '\n'.join(row['ref'] + '\n  commit: ' + row['commit'] + '\n  indirme: ' + str(row['download_bytes']) + ' bayt' for row in operations)
                              or 'Güncellenecek / kurulacak kullanıcı Flatpak paketi yok.',
                    'note': 'Yalnızca bu hesaba, yönetici parolası olmadan. Runtime ve bağımlılıklar dahildir. Uygulama izinlerini ayrıntı sayfasında inceleyin.'}
        if operation == 'apply' and token != captured['token']:
            refused = 'Flatpak planı / commit değişti. Yeni planı görüntüleyip yeniden onaylayın.'
        return operation == 'apply' and refused is None
    transaction.connect('ready', ready)
    try:
        transaction.run(None)
    except Exception:
        # Önizlemede ready=False bilinçli iptaldir; paket değiştirilmez. Diğer
        # bütün hatalar (apply dahil) aşağıda / çağıranda görünür kalır.
        if operation != 'plan' or captured is None:
            if refused:
                raise ValueError(refused)
            raise
    if refused:
        raise ValueError(refused)
    if captured is None:
        raise ValueError('Flatpak işlem planı alınamadı; başarı varsayılmadı.')
    if operation == 'apply':
        return {'message': 'Kullanıcı Flatpak işlemi tamamlandı.', 'detail': captured['detail'], 'source': 'flatpak'}
    return captured


def dispatch(arguments):
    if arguments == ['catalog']:
        return catalogue()
    if arguments == ['setup']:
        if os.geteuid() == 0:
            raise ValueError('Kaynak kurulumu için kendi masaüstü hesabınızı kullanın.')
        store_core.setup_flathub()
        return {'message': 'Flathub yalnızca bu hesaba eklendi. Hiçbir uygulama kurulmadı.'}
    if len(arguments) == 2 and arguments[0] == 'search':
        return search(arguments[1])
    if len(arguments) == 3 and arguments[0] == 'detail':
        return detail(arguments[1], arguments[2])
    if len(arguments) == 3 and arguments[0] == 'launch':
        return launch(arguments[1], arguments[2])
    if len(arguments) in (3, 4) and arguments[0] in ('plan', 'apply'):
        operation, identifier, source = arguments[:3]
        if (operation == 'plan' and len(arguments) != 3) or (operation == 'apply' and len(arguments) != 4):
            raise ValueError('Geçersiz işlem argümanları.')
        token = arguments[3] if len(arguments) == 4 else ''
        if source == 'system':
            return apt_request(operation, identifier, token)
        if source == 'flatpak':
            return flatpak_transaction(identifier, operation, token)
    raise ValueError('İzin verilmeyen mağaza işlemi.')


def main():
    try:
        result = dispatch(sys.argv[1:])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        # Hata GTK'ye düz metin gider; traceback veya serbest komut çalıştırılmaz.
        print(json.dumps({'error': str(error)[:5000]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
