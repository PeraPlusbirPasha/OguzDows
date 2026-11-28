#!/usr/bin/env python3
"""Geçici CI kökünde root olmayan TAM Xfce oturumu; LightDM/PAM/GPU testi değil.

Yalnızca /run/oguzdows-ci.* altında özel Xauthority ve D-Bus ile çalışır.
İmajın gerçek Xsession girişini kullanır; --version yanıtını açılış saymaz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

PROCESSES = ('xfwm4', 'xfce4-panel', 'xfdesktop')


def private_home(home):
    home = Path(home)
    if (not str(home).startswith('/run/oguzdows-ci.') or home.name != 'home'
            or home.is_symlink() or not home.is_dir()):
        raise ValueError('Oturum testi yalnızca kendine ait geçici CI evinde çalışır.')
    return home


def owned_processes(home, uid=None):
    uid = os.getuid() if uid is None else uid
    result = {}
    expected = ('HOME=' + str(home)).encode()
    for directory in Path('/proc').glob('[0-9]*'):
        try:
            if int(directory.name) in (os.getpid(), os.getppid()) or directory.stat().st_uid != uid:
                continue
            if expected not in (directory / 'environ').read_bytes().split(b'\x00'):
                continue
            args = (directory / 'cmdline').read_bytes().decode(errors='replace').split('\x00')
            result[int(directory.name)] = {Path(arg).name for arg in args if arg}
        except (OSError, ValueError):
            continue
    return result



def news_fixture_check(prefix, home, log):
    """Gerçek hedef C istemcisi + üretim JSON işçisi; ağsız RSS fixture'ı.

    Süreç / offline önbellek denetimi; pencere pikseli, haber ağı ve performans
    ölçümü değildir. Yalnızca bu geçici evdeki veriye ve çocuğa dokunur.
    """
    sys.path.insert(0, '/usr/lib/oguzdows')
    from news_core import Reader
    reader = Reader()
    selected = reader.sources()[0]['id']
    payload = b'<rss><channel><item><title>TEST ONLY - offline news</title><description>TEST fixture, not real news.</description><link>https://example.org/test</link></item></channel></rss>'
    reader.refresh(selected, download=lambda _url: payload)
    cache = reader.cache / (selected + '.json')
    before = cache.read_bytes()
    process = subprocess.Popen([*prefix, '/usr/lib/oguzdows/oguzdows-news-native'],
                               env={**os.environ, 'G_MESSAGES_DEBUG': 'OguzDows-Haber'},
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic() + 60
        stable = 0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError('Hedef C Haber istemcisi erken kapandı: ' + str(process.returncode))
            processes = owned_processes(home)
            names = set().union(*processes.values()) if processes else set()
            log.flush()
            response = 'cached-view-ready: 1 items' in Path(log.name).read_text(errors='replace')[-64000:]
            ready = response and 'oguzdows-news-native' in names and 'news_service.py' not in names
            stable = stable + 1 if ready else 0
            if stable >= 3:
                break
            time.sleep(1)
        if stable < 3 or cache.read_bytes() != before:
            raise ValueError('C Haber / kısa ömürlü işçi / salt-okunur offline önbellek denetimi başarısız.')
        return {'native_process_alive': True, 'worker_exited': True, 'cached_fixture_preserved': True,
                'network_tested': False, 'performance_measurement': False, 'window_pixels_verified': False}
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def xfconf_locale_check(home):
    """Real CLI/catalogue/typed-array regression in an already private session.

    Shared by native ARM64 Welcome CI and installed target-user QEMU CI.
    Only the metadata persistence error is deliberately injected; the Xfconf
    service, CLI, gettext catalogues, writes, readback and rollback are real.
    """
    home = Path(home)
    if (os.getuid() == 0 or home.resolve() != Path.home().resolve()
            or not (str(home).startswith('/run/oguzdows-ci.')
                    or str(home).startswith('/tmp/oguzdows-appearance-ci-'))
            or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            or os.environ.get('LANGUAGE') != 'tr:en' or os.environ.get('LC_ALL') != 'tr_TR.UTF-8'):
        raise ValueError('Türkçe Xfconf regresyonu özel normal kullanıcı / tr_TR.UTF-8 / LANGUAGE=tr:en gerektirir.')
    import profiles
    import desktop_runtime
    import wallpapers

    channel = 'oguzdows-ci-locale'
    row = ('xfce4-panel', '/panels/panel-1/background-rgba', 'double-array')
    original = profiles.read_property(*row, profiles.run)
    panel_keys = ('/panels', '/panels/panel-1/plugin-ids')
    panels = {key: profiles.read_property('xfce4-panel', key, 'int-array', profiles.run) for key in panel_keys}
    directory = home.parent / 'xfconf-locale-profiles'
    header = None
    try:
        for module in (profiles, desktop_runtime, wallpapers):
            for kind, values in (('int-array', ['17', '23']), ('int-array', ['17']),
                                 ('double-array', ['0.125', '0.25', '0.5', '1'])):
                profiles.set_property(channel, '/array', kind, values, module.run)
                if profiles.read_property(channel, '/array', kind, module.run) != values:
                    raise ValueError('Türkçe oturumda tür güvenli dizi geri okunamadı: ' + module.__name__)
                # Control deliberately bypasses the fixed subprocess runners.
                # It MUST be translated, otherwise this locale test has no coverage.
                raw = subprocess.run(['xfconf-query', '-c', channel, '-p', '/array'],
                                     env={**os.environ, 'LC_ALL': 'C.UTF-8'},
                                     check=True, capture_output=True, text=True, timeout=12)
                if raw.stdout.splitlines()[0] != f'Değer, {len(values)} ögeden oluşan dizidir:':
                    raise ValueError('Gerçek Türkçe Xfconf katalog başlığı etkin değil: ' + repr(raw.stdout))
                if len(values) == 2:
                    header = raw.stdout.splitlines()[0]
            text = 'İstanbul, Kaçkar — ışık'
            profiles.set_property(channel, '/utf8', 'string', text, module.run)
            if profiles.read_property(channel, '/utf8', 'string', module.run) != text:
                raise ValueError('Türkçe UTF-8 Xfconf değeri korunmadı.')

        def unfixed_runner(command):
            return subprocess.run(command, env={**os.environ, 'LC_ALL': 'C.UTF-8'},
                                  capture_output=True, text=True, check=False, timeout=12)
        try:
            profiles.read_property(channel, '/array', 'double-array', unfixed_runner)
        except ValueError as error:
            if str(error) != 'Xfce dizi ayarı güvenle okunamadı: /array':
                raise
        else:
            raise ValueError('Düzeltme öncesi gerçek Türkçe dizi hatası yeniden üretilemedi.')

        target = ['0.125', '0.25', '0.5', '1']
        if target == original:
            target = ['0.5', '0.25', '0.125', '1']
        undo = []
        profiles.transaction([(*row, target)], directory, profiles.run, {}, undo=undo)
        if profiles.read_property(*row, profiles.run) != target or len(undo) != 1:
            raise ValueError('Gerçek dizi işlemi / geri okuması başarısız.')
        backup = profiles.validate_backup(json.loads((directory / 'before-first-change.json').read_text()))
        if [*row, original] not in backup:
            raise ValueError('Türkçe oturumda tür güvenli ilk yedek korunmadı.')
        undo[0]()
        if profiles.read_property(*row, profiles.run) != original:
            raise ValueError('Gerçek dizi işleminin karşılaştırmalı geri alması başarısız.')
        # Missing metadata parent injects a persistence failure AFTER a real
        # array write/readback, not a mocked successful/failed settings backend.
        try:
            profiles.transaction([(*row, target)], directory, profiles.run,
                                 {'missing-parent/selection': 'TEST ONLY rollback\n'})
        except FileNotFoundError:
            pass
        else:
            raise ValueError('Kasıtlı kayıt hatası tetiklenmedi.')
        if profiles.read_property(*row, profiles.run) != original:
            raise ValueError('Kayıt hatasından sonra gerçek dizi geri alınmadı.')
        if any(profiles.read_property('xfce4-panel', key, 'int-array', profiles.run) != value for key, value in panels.items()):
            raise ValueError('Tema işlemi kişisel panel / eklenti dizilerini değiştirdi.')
        return {'schema': 1, 'environment': {key: os.environ[key] for key in ('LANG', 'LANGUAGE', 'LC_ALL')},
                'raw_turkish_header': header, 'unfixed_reader_error_reproduced': True,
                'runners': ['profiles', 'desktop_runtime', 'wallpapers'],
                'typed_arrays': ['int-array', 'double-array'], 'single_item_array': True,
                'utf8_value_roundtrip': True, 'array_read_write_readback': True,
                'typed_backup': True, 'compare_rollback': True, 'persistence_failure_rollback': True,
                'personal_panel_arrays_unchanged': True, 'persistence_failure_injected': True,
                'settings_backend_mocked': False}
    finally:
        profiles.set_property(*row, original, profiles.run)
        result = profiles.run(['xfconf-query', '-c', channel, '-p', '/', '--reset', '--recursive'])
        if result.returncode:
            raise ValueError('Özel Xfconf test kanalı temizlenemedi.')


def appearance_check(home):
    """Installed target code -> real XSettings and packaged wallpaper pixels.

    No backend or resource-policy mocks. This is the temporary target ARM
    user/QEMU session, not a physical Pi or the Welcome UI callback test.
    """
    private_home(home)
    if os.geteuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise ValueError('Görünüm testi özel normal kullanıcı oturumunu gerektirir.')
    sys.path.insert(0, '/usr/lib/oguzdows')
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    import desktop_preferences as preferences
    import desktop_state as state
    import profiles
    import wallpapers

    def pump():
        for _ in range(100):
            if not Gtk.events_pending(): break
            Gtk.main_iteration_do(False)
        time.sleep(.04)

    # First-login migration must finish; never remove its lock or race it by
    # resetting user configuration. The native accent observer stays enabled.
    deadline = time.monotonic() + 120
    while any(names & {'session.sh', 'wallpapers.py', '--effects-session'}
              for names in owned_processes(home).values()):
        if time.monotonic() >= deadline:
            raise ValueError('İlk giriş görünüm işçisi tamamlanmadı.')
        pump()

    locale_report = xfconf_locale_check(home)

    def apply(changes):
        deadline = time.monotonic() + 90
        while True:
            try:
                return preferences.update_and_apply(changes)
            except RuntimeError as error:
                if (str(error) not in ('Başka bir masaüstü işlemi devam ediyor.', 'Başka bir görünüm işlemi devam ediyor.')
                        or time.monotonic() >= deadline):
                    raise
                pump()

    themes = {}
    for mode in ('dark', 'light'):
        apply({'appearance': mode})
        theme = profiles.read_property('xsettings', '/Net/ThemeName', 'string', profiles.run)
        if not theme or 'User-' not in theme or profiles.read_property('xfwm4', '/general/theme', 'string', profiles.run) != theme:
            raise ValueError('Hedef GTK / Xfwm tema ayarı eşleşmedi.')
        deadline = time.monotonic() + 25
        while Gtk.Settings.get_default().get_property('gtk-theme-name') != theme:
            if time.monotonic() >= deadline:
                raise ValueError('Hedef GTK3 açık/koyu temayı yeniden yüklemedi.')
            pump()
        if state.load()['appearance'] != mode:
            raise ValueError('Hedef tema tercihi kaydedilmedi.')
        themes[mode] = theme

    screen = Gdk.Screen.get_default()
    root = Gdk.get_default_root_window()
    # Choose an uncovered patch; a recoloured Welcome window is NOT evidence
    # that xfdesktop changed. EWMH frame extents include normal decorations.
    rectangles = [window.get_frame_extents() for window in (screen.get_window_stack() or [])
                  if window.is_viewable() and window.get_type_hint() != Gdk.WindowTypeHint.DESKTOP]
    point = next(((x, y) for x in range(4, screen.get_width() - 4, max(1, screen.get_width() // 32))
                  for y in range(4, screen.get_height() - 4, max(1, screen.get_height() // 32))
                  if not any(x + 4 > r.x and x < r.x + r.width and y + 4 > r.y and y < r.y + r.height
                             for r in rectangles)), None)
    if point is None:
        raise ValueError('Duvar kâğıdı pikselleri için örtülmemiş masaüstü alanı yok.')

    def signature():
        Gdk.Display.get_default().sync()
        # Fail rather than count a popup/notification repaint as wallpaper.
        x, y = point
        if any(window.is_viewable() and window.get_type_hint() != Gdk.WindowTypeHint.DESKTOP
               and (r := window.get_frame_extents()).x < x + 4 and r.x + r.width > x
               and r.y < y + 4 and r.y + r.height > y for window in (screen.get_window_stack() or [])):
            raise ValueError('Test edilen masaüstü alanını başka bir pencere örttü.')
        frame = Gdk.pixbuf_get_from_window(root, *point, 4, 4)
        if frame is None:
            raise ValueError('Hedef masaüstü pikselleri okunamadı.')
        return hashlib.sha256(frame.get_pixels()).hexdigest()

    entries = wallpapers.catalog()
    if len(entries) < 2:
        raise ValueError('En az iki gerçek paketlenmiş duvar kâğıdı gerekli.')
    images, signatures = [], []
    previous = signature()
    for entry in (entries[1], entries[0]):
        apply({'wallpaper': entry['id']})
        deadline = time.monotonic() + 40
        stable, last = 0, None
        while True:
            for _ in range(5): pump()
            value = signature()
            stable = stable + 1 if value != previous and value == last else 0
            last = value
            if stable >= 3:
                break
            if time.monotonic() >= deadline:
                raise ValueError('Xfconf yazıldı ama hedef xfdesktop pikselleri değişmedi / kararlı olmadı.')
        previous = value
        if state.load()['wallpaper'] != entry['id']:
            raise ValueError('Hedef duvar kâğıdı tercihi kaydedilmedi.')
        properties = wallpapers.xfce_properties()
        if not properties or any(profiles.read_property('xfce4-desktop', key, 'string', profiles.run) != entry['path'] for key in properties):
            raise ValueError('Hedef duvar kâğıdı ayarları geri okunarak doğrulanamadı.')
        images.append(entry['id']); signatures.append(value)
    return {'schema': 1, 'scope': 'target-user-QEMU-real-Xfce-appearance',
            'xfconf_locale': locale_report,
            'gtk3_dark_light_reloaded': True, 'gtk_themes': themes, 'wallpaper_ids': images,
            'wallpaper_pixel_sha256': signatures, 'wallpaper_pixels_changed': True,
            'settings_backend_mocked': False, 'packaged_wallpapers': True,
            'welcome_callbacks_tested': False, 'gtk4_portal_tested': False,
            'physical_device': False, 'performance_measurement': False}


def session_child(output, cpu):
    home = private_home(os.environ.get('HOME', ''))
    if os.geteuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS') or not os.environ.get('DISPLAY'):
        raise ValueError('Root olmayan kullanıcı, özel X ve D-Bus oturumu gerekli.')
    report = {'scope': 'non-root-Xfce-on-host-Xvfb', 'uid': os.getuid(),
              'lightdm_pam': False, 'physical_boot': False, 'performance_measurement': False,
              'errors': []}
    prefix = ['/tmp/oguzdows-qemu-static', '-cpu', cpu]
    process = None
    browser = None
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('Gdk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gdk, GdkX11, Gtk
        if not Gtk.init_check()[0]:
            raise ValueError('Kullanıcı özel Xauthority ile ekran açamadı.')
        with (home.parent / 'xfce.log').open('w') as log:
            process = subprocess.Popen([*prefix, '/usr/bin/python3', '-I', '/usr/lib/oguzdows/session_start.py'],
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 180
            stable = 0
            found = set()
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ValueError('Gerçek Xfce oturumu erken kapandı: ' + str(process.returncode))
                for _ in range(100):
                    if not Gtk.events_pending():
                        break
                    Gtk.main_iteration_do(False)
                processes = owned_processes(home)
                found = set().union(*processes.values()) if processes else set()
                wm = GdkX11.X11Screen.get_window_manager_name(Gdk.Screen.get_default())
                ready = all(name in found for name in PROCESSES) and wm.lower() == 'xfwm4'
                stable = stable + 1 if ready else 0
                if stable >= 5:
                    break
                time.sleep(1)
            if stable < 5:
                raise ValueError('WM + panel + masaüstü 180 saniyede birlikte hazır olmadı: ' + repr(sorted(found)))
            report.update({name: True for name in PROCESSES})
            report['x11_window_manager'] = wm
            report['stable_samples'] = stable
            # Gerçek non-root Xfconf / oturum kaydı da gerekli.
            query = subprocess.run([*prefix, '/usr/bin/xfconf-query', '-c', 'xfce4-panel', '-p', '/panels'],
                                   check=True, capture_output=True, text=True, timeout=30)
            report['panel_configuration'] = query.stdout.strip()[:500]
            startup = json.loads((home / '.local/state/oguzdows/session/startup.json').read_text())
            if startup.get('uid') != os.getuid():
                raise ValueError('Ürün giriş işçisi kullanıcı kimliği uyuşmuyor.')
            report['startup_profile'] = startup['profile']
            report['appearance'] = appearance_check(home)
            report['news'] = news_fixture_check(prefix, home, log)
            if cpu == 'arm1176':
                # armhf imajında varsayılan başlatıcı gerçekten NetSurf'ü
                # açabilmeli. Ağ / haber sitesi uyumluluğu ölçülmez.
                browser = subprocess.Popen([*prefix, '/usr/bin/python3', '-I', '/usr/lib/oguzdows/browser.py'],
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                for _ in range(8):
                    time.sleep(1)
                    if browser.poll() is not None:
                        raise ValueError('ARMv6 NetSurf varsayılanı erken kapandı: ' + str(browser.returncode))
                names = set().union(*owned_processes(home).values())
                if 'netsurf-gtk' not in names:
                    raise ValueError('ARMv6 web başlatıcısı NetSurf sürecini oluşturmadı.')
                report['browser'] = {'program': 'netsurf-gtk', 'local_start_page_alive': True,
                                     'network_tested': False, 'modern_sites_verified': False}
    except Exception as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        if browser is not None:
            if browser.poll() is None:
                browser.terminate()
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=10)
        if process is not None:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        # Xfce bazı alt bileşenleri daemonlaştırır. Yalnızca bu özel HOME'a
        # ait aynı UID süreçleri temizle; pkill / killall / host D-Bus yok.
        for pid, names in owned_processes(home).items():
            if names & {'dbus-daemon', 'dbus-run-session'}:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 1 if report['errors'] else 0


def run_nonroot_session(cpu):
    root = Path(os.environ['XDG_RUNTIME_DIR'])
    if os.geteuid() != 0 or not str(root).startswith('/run/oguzdows-ci.') or not root.is_dir():
        raise ValueError('Oturum CI hazırlığı yalnızca geçici hedef chroot içindir.')
    directory = root / 'nonroot'
    home = directory / 'home'
    directory.mkdir(mode=0o700)
    shutil.copytree('/etc/skel', home)
    (directory / 'runtime').mkdir(mode=0o700)
    shutil.copy2(os.environ['XAUTHORITY'], directory / 'Xauthority')
    for path in [directory, *directory.rglob('*')]:
        os.chown(path, 65534, 65534, follow_symlinks=False)
    root.chmod(0o711)  # Yalnızca geçiş; root raporu / evinin içeriği okunamaz.
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
           'LANG': 'tr_TR.UTF-8', 'LANGUAGE': 'tr:en', 'LC_ALL': 'tr_TR.UTF-8',
           'HOME': str(home), 'USER': 'nobody', 'LOGNAME': 'nobody',
           'DISPLAY': os.environ['DISPLAY'], 'XAUTHORITY': str(directory / 'Xauthority'),
           'XDG_RUNTIME_DIR': str(directory / 'runtime'),
           'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11', 'GDK_BACKEND': 'x11',
           'GSETTINGS_BACKEND': 'memory', 'NO_AT_BRIDGE': '1', 'QEMU_CPU': cpu,
           'DBUS_SYSTEM_BUS_ADDRESS': 'unix:path=' + str(directory / 'no-system-bus')}
    prefix = ['/tmp/oguzdows-qemu-static', '-cpu', cpu]
    command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups',
               '/usr/bin/dbus-run-session', '--', *prefix, '/usr/bin/python3', str(Path(__file__).resolve()),
               '--cpu', cpu, '--output', str(directory / 'session.json')]
    try:
        with (directory / 'runner.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=480)
        result = json.loads((directory / 'session.json').read_text())
        if result.get('errors') or result.get('uid') != 65534 or any(result.get(name) is not True for name in PROCESSES):
            raise ValueError('Root olmayan oturum kapısı başarısız: ' + str(result))
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logs = '\n'.join(path.read_text(errors='replace')[-3500:] for path in
                         (directory / 'runner.log', directory / 'xfce.log', directory / 'session.json') if path.is_file())
        raise ValueError('Root olmayan tam Xfce oturumu başarısız: ' + str(error) + '\n' + logs) from error
    finally:
        # timeout'ta dbus-run-session'ın çocuğu kalmış olsa da başka kullanıcının
        # sürecini öldürme. Yalnızca bu testin tam HOME + UID eşleşmesi.
        for pid in owned_processes(home, uid=65534):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        root.chmod(0o700)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', choices=('arm1176', 'cortex-a53'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(session_child(args.output, args.cpu))
