#!/usr/bin/env python3
"""Gerçek GNOME Shell / KWin + Plasma; özel normal kullanıcı Xvfb oturumu.

Host yazılım GPU'su / simüle full kaynak bütçesi. Fiziksel açılış, GPU hızı,
Wayland, ARM veya pil ölçümü değildir. Kullanıcının mevcut kabuğuna bağlanmaz.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from support import ROOT


def child(directory, desktop):
    home = Path(os.environ.get('HOME', '/')).resolve()
    if (os.getuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            or directory.parent != Path(tempfile.gettempdir()) or not directory.name.startswith('oguzdows-shell-ci-')
            or home != directory / 'home' or home.is_symlink()):
        raise ValueError('Yalnız tek kullanımlık normal kullanıcı / CI evi.')
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gio, GLib, Gtk
    import desktop_preferences as preferences
    import desktop_runtime as runtime
    from resource_policy import policy

    processes = []
    qt = None
    report = {'scope': 'private-nonroot-real-shell-X11-software-GPU', 'desktop': desktop,
              'physical_device_verified': False, 'wayland_verified': False,
              'performance_benchmark': False, 'resource_budget_simulated': True}

    def pump(seconds=.3):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            while GLib.MainContext.default().iteration(False): pass
            if qt: qt.processEvents()
            time.sleep(.01)

    def wait(predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for process in processes:
                if process.poll() is not None: raise AssertionError('Özel kabuk erken kapandı: ' + str(process.returncode))
            try:
                value = predicate()
                if value: return value
            except (RuntimeError, IndexError):
                pass
            pump(.12)
        raise AssertionError('Yerel kabuk API yanıtı / geçişi süre sınırında tamamlanmadı')

    def start(argv, name):
        with (directory / (name + '.log')).open('w') as log:
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)

    def owner(name):
        return runtime.dbus('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                            'NameHasOwner', '(s)', (name,))[0]

    def shell_state():
        value = runtime.dbus('org.gnome.Shell', '/org/oguzdows/Desktop', 'org.oguzdows.Desktop', 'GetState')[0]
        return json.loads(value)

    window = Gtk.Window(title='OğuzDows · gerçek kabuk test yüzeyi')
    window.set_default_size(320, 240); window.add(Gtk.Label(label='Native GTK · özel normal kullanıcı'))
    try:
        if desktop == 'gnome':
            import desktop_gnome as gnome
            shell = Gio.Settings.new('org.gnome.shell')
            shell.set_strv('enabled-extensions', [gnome.UUID]); shell.set_boolean('disable-user-extensions', False)
            Gio.Settings.sync()
            version = subprocess.run(['/usr/bin/gnome-shell', '--version'], text=True, capture_output=True, check=True, timeout=5).stdout.strip()
            start(['/usr/bin/gnome-shell', '--x11'], 'gnome-shell')
            wait(lambda: owner('org.gnome.Shell'))
            wait(shell_state)
            report['shell'] = version
        else:
            import desktop_plasma as plasma
            import desktop_decoration as decoration
            backend = plasma.PlasmaSettings()
            report['kconfig_major'] = backend.major
            assert decoration.available(backend.major), 'Hedef ABI Aurorae kütüphanesi bulunamadı'
            start(['/usr/bin/kwin_x11'], 'kwin')
            wait(lambda: owner('org.kde.KWin'))
            start(['/usr/bin/plasmashell'], 'plasmashell')
            wait(lambda: owner('org.kde.plasmashell'))
            wait(lambda: plasma.wallpaper_state())
            code = 'var ps=panels(), ids=[]; for(var i=0;i<ps.length;++i) ids.push(ps[i].id); print(JSON.stringify(ids));'
            panel_ids = runtime.dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', '(s)', (code,))[0]
            if backend.major == 6:
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtGui import QPalette
                role = QPalette.ColorRole.Window
            else:
                from PyQt5.QtWidgets import QApplication
                from PyQt5.QtGui import QPalette
                role = QPalette.Window
            os.environ['KDE_SESSION_VERSION'] = str(backend.major)
            os.environ['KDE_FULL_SESSION'] = 'true'
            qt = QApplication(['oguzdows-private-palette-test'])
            pump(.8)
            before_color = qt.palette().color(role).name()
        # Kaynak kararı burada açıkça simüledir; gerçek Shell / efekt yüklenmesi
        # ve API sonuçları aşağıda ayrıca sınanır, dosya yazımı başarı sayılmaz.
        result = preferences.update_and_apply({'appearance': 'dark', 'effects': 'aero',
            'blur': True, 'motion': 'spring', 'snap_animation': True, 'accent': '#74c8d5'}, policy(8388608))
        report['apply_notes'] = result['notes']
        if desktop == 'gnome':
            actual = wait(lambda: (value if (value := shell_state()).get('blur_attached') and value.get('spring_enabled') else False))
            report['extension_state'] = actual
            assert gnome.status()['extension_active'] is True
            # Sadece sabit köprü API'si; Shell Eval / unsafe-mode YOK.
            runtime.dbus('org.gnome.Shell', '/org/oguzdows/Desktop', 'org.oguzdows.Desktop', 'Open', '(s)', ('hide-overview',))
        else:
            assert result.get('blur_active') is True, result
            assert result.get('spring_active') is True, result
            assert backend.read('decoration-library') == 'org.kde.kwin.aurorae'
            expected_rgb = tuple(map(int, backend.read('palette:Window:BackgroundNormal').split(',')))
            expected = '#' + ''.join(f'{value:02x}' for value in expected_rgb)
            wait(lambda: qt.palette().color(role).name() == expected)
            after_color = qt.palette().color(role).name()
            assert before_color != after_color, (before_color, after_color)
            report['live_qt_palette'] = {'before': before_color, 'after': after_color, 'matches_kconfig': True}
            after_ids = runtime.dbus('org.kde.plasmashell', '/PlasmaShell', 'org.kde.PlasmaShell', 'evaluateScript', '(s)', (code,))[0]
            assert json.loads(panel_ids) == json.loads(after_ids)
            report['panel_ids_preserved'] = json.loads(after_ids)
            report['real_kwin_effects_loaded'] = ['blur', 'oguzdows-aero']
            report['aurorae_selected'] = backend.read('decoration-theme')
        pump(1)
        window.show_all(); window.present(); pump(1)
        for direction in ('left', 'right', 'maximize', 'restore'):
            window.present(); pump(.2)
            runtime.snap(direction); pump(.6)
            rectangle = window.get_window().get_frame_extents()
            assert rectangle.width > 0 and rectangle.height > 0
            if direction in ('left', 'right'):
                assert rectangle.width < 1024 * .65, (direction, rectangle.width)
            report.setdefault('snap_frame_rectangles', {})[direction] = [rectangle.x, rectangle.y, rectangle.width, rectangle.height]
        window.iconify(); pump(.5); window.deiconify(); window.present(); pump(.7)
        root = Gdk.get_default_root_window()
        capture = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
        assert capture is not None
        capture.savev(str(directory / (desktop + '.png')), 'png', [], [])
        window.destroy(); pump(.6)
        low = preferences.update_and_apply({}, policy(524288))
        if desktop == 'gnome':
            wait(lambda: not shell_state()['blur_attached'] and not shell_state()['spring_enabled'])
            report['low_budget_disables_blur_and_spring'] = True
            # Kilit/greeter gerekmeden, kapat/aç temizliği gerçek Shell içinde.
            gnome.extension_enabled(False); pump(.5)
            gnome.extension_enabled(True); wait(shell_state)
            report['extension_disable_enable_clean'] = True
        else:
            assert low.get('blur_active') is False and low.get('spring_active') is False, low
            assert backend.read('decoration-library') != 'org.kde.kwin.aurorae'
            report['low_budget_disables_blur_spring_and_restores_decoration'] = True
        preferences.restore(); pump(.5)
        report['journal_restore_executed'] = True
        for path in directory.glob('*.log'):
            text = path.read_text(errors='replace')
            # İsteğe bağlı sistem servisi eksikleri bir script başarısı değildir;
            # kendimize ait runtime JS / QML hatası da sessizce yutulmaz.
            bad = [line for line in text.splitlines() if ('oguzdows' in line.lower() or 'aurorae' in line.lower())
                   and any(word in line for word in ('TypeError', 'ReferenceError', 'SyntaxError', 'Error loading', 'is not a function'))]
            assert not bad, bad[-12:]
        (directory / 'shell.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print('::notice title=Gerçek yerel kabuk kontrolü::' + json.dumps(report, ensure_ascii=False).replace('%', '%25'), flush=True)
    except Exception:
        for path in directory.glob('*.log'):
            text = path.read_text(errors='replace')[-2500:]
            print('::error title=' + path.stem + ' runtime::' + text.replace('%', '%25').replace('\n', '%0A'), flush=True)
        raise
    finally:
        window.destroy()
        if qt: qt.quit()
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', choices=('gnome', 'kde'), required=True)
    parser.add_argument('--output', type=Path); parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Yalnız özel CI / Xvfb.')
    if args.child: child(args.child, args.desktop); return
    if args.output is None or not os.environ.get('XAUTHORITY'): parser.error('--output ve özel Xauthority gerekli.')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-shell-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'; home.mkdir(mode=0o700)
        (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key not in ('DBUS_SESSION_BUS_ADDRESS', 'SESSION_MANAGER', 'WAYLAND_DISPLAY')}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
            XDG_DATA_HOME=str(home / '.local/share'), XDG_STATE_HOME=str(home / '.local/state'),
            XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), GSETTINGS_BACKEND='dconf',
            XDG_CURRENT_DESKTOP='GNOME' if args.desktop == 'gnome' else 'KDE', XDG_SESSION_TYPE='x11',
            GDK_BACKEND='x11', LIBGL_ALWAYS_SOFTWARE='1', NO_AT_BRIDGE='1',
            QT_QPA_PLATFORM='xcb', QT_QPA_PLATFORMTHEME='kde', QT_QUICK_BACKEND='software',
            KWIN_COMPOSE='O2', KWIN_X11_NO_SYNC_TO_VBLANK='1')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(ROOT / 'tests/smoke-shells.py'), '--desktop', args.desktop, '--child', str(directory)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try: subprocess.run(command, env=env, check=True, timeout=150)
        finally:
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.png', '.json', '.log'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
