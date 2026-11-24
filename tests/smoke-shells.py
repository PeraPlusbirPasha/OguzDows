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


def legacy_animation_fixture(home, major):
    """43'te force-animations CLI yok: yalnız test evinde ayrı uzantı.

    Normal Shell'in yazılım-GPU inhibitörünü bir kez dengeler; üretim
    uzantısına / kaynak bütçesine bypass koymaz, Shell Eval kullanmaz.
    """
    uuid = 'oguzdows-ci-software-animations@fixture.invalid'
    target = home / '.local/share/gnome-shell/extensions' / uuid
    target.mkdir(parents=True)
    (target / 'metadata.json').write_text(json.dumps({'uuid': uuid, 'name': 'Private CI animations fixture',
        'description': 'One-shot software GPU fixture; not a product extension', 'shell-version': [str(major)]}))
    (target / 'extension.js').write_text('''const {GLib, St} = imports.gi;
let source = 0;
let released = false;
function init() {}
function enable() {
    source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
        source = 0;
        if (!St.Settings.get().enable_animations) {
            St.Settings.get().uninhibit_animations();
            released = true;
        }
        return GLib.SOURCE_REMOVE;
    });
}
function disable() {
    if (source) { GLib.Source.remove(source); source = 0; }
    if (released) { St.Settings.get().inhibit_animations(); released = false; }
}
''')
    return uuid


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
              'system_bus': 'private-empty-bus-no-logind-no-hardware-services',
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
            except (RuntimeError, IndexError, ValueError):
                pass  # İlk masaüstü henüz yaratılmadıysa boş katalog geçicidir.
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
            version = subprocess.run(['/usr/bin/gnome-shell', '--version'], text=True, capture_output=True, check=True, timeout=5).stdout.strip()
            major = int(version.split()[-1].split('.')[0])
            enabled = [gnome.UUID]
            options = ['--force-animations'] if major >= 45 else []
            if not options: enabled.append(legacy_animation_fixture(home, major))
            report['ci_only_software_gpu_animation_override'] = 'native-cli' if options else 'separate-one-shot-fixture-extension'
            shell = Gio.Settings.new('org.gnome.shell')
            shell.set_strv('enabled-extensions', enabled); shell.set_boolean('disable-user-extensions', False)
            Gio.Settings.sync()
            start(['/usr/bin/gnome-shell', '--x11', *options], 'gnome-shell')
            wait(lambda: owner('org.gnome.Shell'))
            wait(shell_state)
            report['shell'] = version
        else:
            import desktop_plasma as plasma
            import desktop_decoration as decoration
            backend = plasma.PlasmaSettings()
            report['kconfig_major'] = backend.major
            report['ci_only_software_gpu_animation_override'] = os.environ.get('KWIN_EFFECTS_FORCE_ANIMATIONS') == '1'
            assert decoration.available(backend.major), 'Hedef ABI Aurorae kütüphanesi bulunamadı'
            if backend.major == 6:
                # Bu fixture tam startplasma oturumu değildir; KWin başlamadan
                # normalde oturumun açtığı kısayol daemon'unu açıkça hazırla.
                accelerator = runtime.binary(('kglobalacceld',))
                if not accelerator:
                    candidates = sorted(Path('/usr/lib').glob('*/libexec/kglobalacceld')) + [Path('/usr/libexec/kglobalacceld')]
                    accelerator = next((str(path) for path in candidates if path.is_file()), None)
                assert accelerator, 'Özel test için kglobalacceld kurulu değil'
                start([accelerator], 'kglobalacceld')
                wait(lambda: owner('org.kde.kglobalaccel'))
            start(['/usr/bin/kwin_x11'], 'kwin')
            wait(lambda: owner('org.kde.KWin'))
            def compositor_state():
                return runtime.dbus('org.kde.KWin', '/Compositor', 'org.freedesktop.DBus.Properties',
                                    'GetAll', '(s)', ('org.kde.kwin.Compositing',))[0]
            report['compositor_before'] = wait(lambda: (value if (value := compositor_state()).get('active') else False))
            # Normal Plasma girişinde oturum yöneticisi bunu önce hazırlar.
            # Yalnız bu özel test bus'ında açıkça başlat; kabuk başlangıç
            # yarışını üretim backend'inin NO_AUTO_START kapısına yükleme.
            runtime.dbus('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
                         'StartServiceByName', '(su)', ('org.kde.ActivityManager', 0))
            wait(lambda: owner('org.kde.ActivityManager'))
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
            report['compositor_after'] = compositor_state()
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
        def frame():
            rectangle = window.get_window().get_frame_extents()
            return [rectangle.x, rectangle.y, rectangle.width, rectangle.height]
        original_frame = frame(); last_direction = None; last_frame = None
        report['original_frame'] = original_frame
        if desktop == 'gnome': report['extension_after_open'] = shell_state()
        for direction in ('restore', 'left', 'left', 'right', 'right', 'maximize', 'maximize', 'restore', 'restore'):
            window.present(); pump(.2)
            runtime.snap(direction); pump(.6)
            rectangle = frame()
            assert min(rectangle[2:]) > 0
            if direction in ('left', 'right'):
                assert rectangle[2] < 1024 * .65, (direction, rectangle)
            if direction == last_direction:
                assert rectangle == last_frame, ('Snap idempotent değil', direction, last_frame, rectangle)
            if direction == 'restore':
                assert all(abs(a - b) <= 2 for a, b in zip(original_frame, rectangle)), ('Snap eski geometriyi geri almadı', original_frame, rectangle)
            report.setdefault('snap_frame_rectangles', {})[direction] = rectangle
            last_direction, last_frame = direction, rectangle
        report['snap_repeated_actions_idempotent_and_exact_frame_restored'] = True
        runtime.snap('minimize'); pump(.5); window.deiconify(); window.present(); pump(.7)
        if desktop == 'gnome':
            report['extension_after_window_transitions'] = shell_state()
            assert report['extension_after_window_transitions']['spring_transitions_attached'] > 0
            assert report['extension_after_window_transitions']['early_window_hook'] is True
        else:
            text = (directory / 'kwin.log').read_text(errors='replace')
            callbacks = {event: 'oguzdows-aero: ' + event in text for event in
                         ('transition-attached', 'transition-completed', 'snap-transition-attached')}
            assert all(callbacks.values()), callbacks
            report['native_kwin_transition_callbacks'] = callbacks
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
        (directory / 'shell-incomplete.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print('::error title=Eksik kabuk kontrol durumu::' + json.dumps(report, ensure_ascii=False).replace('%', '%25'), flush=True)
        for path in directory.glob('*.log'):
            text = path.read_text(errors='replace')
            own = [line for line in text.splitlines() if any(name in line.casefold() for name in ('oguzdows', 'aurorae', 'scripted effect'))]
            diagnostic = '\n'.join(own[-25:]) + '\n' + text[-2500:]
            print('::error title=' + path.stem + ' runtime::' + diagnostic.replace('%', '%25').replace('\n', '%0A'), flush=True)
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
            QT_QPA_PLATFORM='xcb', QT_QPA_PLATFORMTHEME='kde', QT_QUICK_BACKEND='software', QT_NO_GLIB='1',
            # KWin script efektleri yazılım renderer'da normalde desteklemez.
            # Yalnız özel fixture native callback/curve yolunu bu açık bayrakla
            # çalıştırır; üretim ortamına / backend'e hiçbir bypass eklenmez.
            KWIN_COMPOSE='O2', KWIN_X11_NO_SYNC_TO_VBLANK='1', KWIN_EFFECTS_FORCE_ANIMATIONS='1',
            QT_LOGGING_RULES='kwin_core.debug=true;kwin_scripting.debug=true')
        address = 'unix:path=' + str(directory / 'system-bus')
        configuration = directory / 'system-bus.conf'
        configuration.write_text('<busconfig><type>system</type><auth>EXTERNAL</auth><listen>' + address +
            '</listen><policy context="default"><allow user="*"/><allow own="*"/>'
            '<allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        env['DBUS_SYSTEM_BUS_ADDRESS'] = address
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(ROOT / 'tests/smoke-shells.py'), '--desktop', args.desktop, '--child', str(directory)]
        bus_command = ['/usr/bin/dbus-daemon', '--nofork', '--config-file=' + str(configuration)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            privilege = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups']
            command = [*privilege, *command]; bus_command = [*privilege, *bus_command]
        with (directory / 'private-system-bus.log').open('w') as log:
            system_bus = subprocess.Popen(bus_command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            while not (directory / 'system-bus').exists():
                if system_bus.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Özel test sistem bus adresi açılamadı.')
                time.sleep(.01)
            subprocess.run(command, env=env, check=True, timeout=150)
        finally:
            if system_bus.poll() is None:
                os.killpg(system_bus.pid, signal.SIGTERM); system_bus.wait(timeout=5)
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.png', '.json', '.log'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
