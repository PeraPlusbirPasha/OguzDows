#!/usr/bin/env python3
"""Real GTK3 + open libadwaita color sync, Print key, Start and Thunar.

Only a disposable non-root CI home, private Xvfb and session bus. No network,
package changes, host settings, physical-GPU or latency/performance claim.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from support import ROOT


def private_child(directory):
    if (os.getuid() == 0 or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')
            or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith('oguzdows-polish-ci-')
            or Path.home().resolve() != directory / 'home' or (directory / 'home').is_symlink()):
        raise ValueError('Yalnız tek kullanımlık normal kullanıcı CI evi.')


def adwaita_probe(directory):
    private_child(directory)
    import gi
    gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')
    from gi.repository import Adw, GLib, Gtk
    Adw.init()
    manager = Adw.StyleManager.get_default()
    window = Adw.Window(title='TEST · standard libadwaita client')
    window.set_default_size(380, 220)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    content.append(Adw.HeaderBar())
    content.append(Gtk.Label(label='Standard libadwaita · no OğuzDows CSS'))
    window.set_content(content); window.present()
    def report(*_args):
        path = directory / 'adwaita.json'
        temporary = directory / 'adwaita.tmp'
        temporary.write_text(json.dumps({'dark': manager.get_dark(),
                                        'system_supports_color_schemes': manager.get_system_supports_color_schemes()}))
        temporary.replace(path)
    manager.connect('notify::dark', report)
    manager.connect('notify::system-supports-color-schemes', report)
    report()
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(100, lambda: (loop.quit(), False)[1])
    loop.run()


def child(directory, hub):
    private_child(directory)
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    import desktop_preferences as preferences
    import desktop_shortcuts as shortcuts
    import desktop_state as state
    import profiles
    from resource_policy import policy

    processes = []
    connection = display.Display()
    root = connection.screen().root
    report = {'scope': 'private-nonroot-Xvfb-real-Xfce-GTK3-libadwaita',
              'physical_gpu_verified': False, 'performance_benchmark': False}
    sample = None

    def pump(seconds=.03):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for _ in range(60):
                if not Gtk.events_pending(): break
                Gtk.main_iteration_do(False)
            time.sleep(.008)

    def until(predicate, message, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate(): return
            pump()
        raise AssertionError(message)

    def start(label, argv):
        with (directory / (label + '.log')).open('w') as log:
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process); return process

    def stop(process):
        if process is None: return
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        process.wait(timeout=8)

    def clients():
        prop = root.get_full_property(connection.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
        return [connection.create_resource_object('window', int(xid)) for xid in prop.value] if prop is not None else []

    def owned_window(pid):
        for window in clients():
            value = window.get_full_property(connection.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
            if value is not None and len(value.value) == 1 and int(value.value[0]) == pid:
                return window
        return None

    def screenshot(name):
        pump(.15)
        image = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, 1024, 768)
        assert image is not None
        image.savev(str(directory / name), 'png', [], [])

    def key(name):
        code = connection.keysym_to_keycode(XK.string_to_keysym(name))
        assert code
        xtest.fake_input(connection, X.KeyPress, code)
        xtest.fake_input(connection, X.KeyRelease, code)
        connection.sync()

    def adwaita_dark(expected):
        path = directory / 'adwaita.json'
        return path.is_file() and json.loads(path.read_text())['dark'] is expected

    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read('/usr/share/dbus-1/services/org.xfce.Xfconf.service')
        daemon = shlex.split(config['D-BUS Service']['Exec'])
        assert len(daemon) == 1 and Path(daemon[0]).name == 'xfconfd'
        start('xfconf', daemon); pump(.3)
        start('xfwm', ['/usr/bin/xfwm4', '--compositor=off']); pump(.4)
        start('xsettings', ['/usr/bin/xfsettingsd', '--no-daemon']); pump(.4)
        assert all(process.poll() is None for process in processes)
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'theme'})
        sample = Gtk.Window(title='TEST · already open standard GTK3 application')
        sample.set_default_size(470, 300); sample.move(30, 40)
        data = Gtk.ListStore(str)
        for text in ('Ordinary GTK3 client · no custom application theme', 'Açık / koyu changes an already open application', 'PrintScreen opens the native capture dialog'):
            data.append([text])
        tree = Gtk.TreeView(model=data); tree.append_column(Gtk.TreeViewColumn('Application content', Gtk.CellRendererText(), text=0))
        sample.add(tree); sample.show_all()
        adwaita = start('adwaita', [sys.executable, str(Path(__file__).resolve()), '--adwaita-probe', str(directory)])
        until(lambda: (directory / 'adwaita.json').is_file(), 'Standard libadwaita client did not start')
        dark_theme = ''
        for mode in ('dark', 'light', 'dark'):
            preferences.update_and_apply({'appearance': mode, 'effects': 'off', 'accent_source': 'theme'},
                                         resources=policy(1048576), profile='windows11' if not dark_theme else None)
            expected = mode == 'dark'
            until(lambda: ('Dark' in Gtk.Settings.get_default().get_property('gtk-theme-name')) is expected,
                  'Already open standard GTK3 application did not change theme')
            until(lambda: adwaita_dark(expected), 'Already open libadwaita application did not follow the standard color preference')
            found, base = tree.get_style_context().lookup_color('theme_base_color')
            assert found and (max(base.red, base.green, base.blue) < .4 if expected else min(base.red, base.green, base.blue) > .7), (mode, base)
            dark_theme = Gtk.Settings.get_default().get_property('gtk-theme-name')
            screenshot('application-theme-' + mode + '.png')
        assert adwaita.poll() is None
        report['already_open_standard_gtk3_dark_light_dark'] = True
        report['already_open_standard_libadwaita_dark_light_dark'] = True
        report['color_scheme_transport'] = json.loads((directory / 'adwaita.json').read_text())
        thunar = start('thunar', ['/usr/bin/thunar', str(Path.home())])
        until(lambda: owned_window(thunar.pid) is not None, 'Real Thunar did not open')
        screenshot('thunar-dark.png')
        report['real_thunar_opened'] = True
        # A real Print key goes through xfsettingsd, xfconf and the installed
        # production wrapper, not a stubbed command or an auto-written image.
        profiles.set_property('xfce4-keyboard-shortcuts', '/commands/custom/override', 'bool', 'true', profiles.run)
        profiles.set_property('xfce4-keyboard-shortcuts', '/commands/custom/Print', 'string', 'xfce4-screenshooter -f', profiles.run)
        profiles.set_property('xfce4-keyboard-shortcuts', '/commands/custom/<Shift>Print', 'string', 'true', profiles.run)
        migrated = shortcuts.install()
        assert 'Print' in migrated['changed'] and '<Shift>Print' in migrated['personal_bindings_preserved'], migrated
        assert not shortcuts.install()['changed']
        pump(.4); key('Print')
        def screenshot_dialog():
            for window in clients():
                value = window.get_wm_class()
                if value and any('screenshooter' in part.lower() for part in value): return window
            return None
        until(lambda: screenshot_dialog() is not None, 'Print did not open the real native screenshot capture dialog')
        screenshot('printscreen-native-dialog.png')
        capture_window = screenshot_dialog()
        pid = capture_window.get_full_property(connection.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
        assert pid is not None
        capture_pid = int(pid.value[0])
        assert b'xfce4-screenshooter' in Path(f'/proc/{capture_pid}/cmdline').read_bytes()
        # Normal close through the WM, preserving the no-save/no-upload default
        # of this disposable test. Product saving is left to the user's dialog.
        capture_window.set_input_focus(X.RevertToParent, X.CurrentTime); connection.sync(); key('Escape')
        until(lambda: screenshot_dialog() is None, 'Screenshot dialog did not close with Escape')
        report['real_Print_key_to_native_capture_dialog'] = True
        report['custom_shortcut_preserved_and_migration_idempotent'] = True
        # Toggle is also exercised with a real window manager / work area.
        hub_process = start('hub-toggle', [str(hub), '--toggle'])
        until(lambda: owned_window(hub_process.pid) is not None, 'Start did not open')
        screenshot('hub-dark.png')
        subprocess.run([str(hub), '--toggle'], check=True, timeout=8)
        hub_process.wait(timeout=8); assert hub_process.returncode == 0
        report['real_start_toggle'] = True
        hub_process = start('hub-escape', [str(hub), '--toggle'])
        until(lambda: owned_window(hub_process.pid) is not None, 'Start did not reopen')
        surface = owned_window(hub_process.pid)
        surface.set_input_focus(X.RevertToParent, X.CurrentTime); connection.sync(); key('Escape')
        hub_process.wait(timeout=8); assert hub_process.returncode == 0
        report['real_start_escape'] = True
    finally:
        if sample: sample.destroy()
        for process in reversed(processes): stop(process)
        connection.close()
        (directory / 'desktop-polish.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Application themes PrintScreen and Start::' + json.dumps(report, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--hub', type=Path)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--adwaita-probe', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Only a disposable CI Xvfb session.')
    if args.adwaita_probe: adwaita_probe(args.adwaita_probe); return
    if args.child:
        if args.hub is None: parser.error('--hub required')
        child(args.child, args.hub); return
    if args.output is None or args.hub is None or not os.environ.get('XAUTHORITY'):
        parser.error('--output, --hub and private xvfb-run Xauthority required')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-polish-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'
        shutil.copytree(ROOT / 'system/etc/skel', home)
        (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key not in ('DBUS_SESSION_BUS_ADDRESS', 'GTK_THEME')}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CACHE_HOME=str(home / '.cache'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='dconf', NO_AT_BRIDGE='1', GIO_USE_VFS='local',
                   GSK_RENDERER='cairo', LC_ALL='C.UTF-8')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                   '--child', str(directory), '--hub', str(args.hub.resolve())]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try: subprocess.run(command, env=env, check=True, timeout=100)
        finally:
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.log', '.json', '.png'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
