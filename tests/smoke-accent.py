#!/usr/bin/env python3
"""Real xfconf -> native event observer -> short Python worker -> GTK/Xfwm.

Only disposable non-root CI home/Xvfb/session bus. No package changes, user
session, personal wallpaper, network or physical GPU claim.
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


def child(directory):
    home = Path(os.environ.get('HOME', '/')).resolve()
    if (os.getuid() == 0 or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith('oguzdows-accent-ci-') or home != directory / 'home'
            or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise ValueError('Yalnız tek kullanımlık normal kullanıcı CI evi.')
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    from PIL import Image
    from Xlib import X, display
    import accent
    import desktop_preferences as preferences
    import desktop_state as state
    import profiles

    def pump(seconds=.03):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for _ in range(50):
                if not Gtk.events_pending(): break
                Gtk.main_iteration_do(False)
            time.sleep(.008)

    def until(predicate, message, seconds=18):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate(): return
            pump()
        raise AssertionError(message)

    def stop(process):
        if process is not None:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            process.wait(timeout=8)

    def property_value(channel, key, kind='string'):
        return profiles.read_property(channel, key, kind, profiles.run)

    prop = '/backdrop/screen0/monitor0/workspace0/last-image'
    images = []
    for name, color in (('sea', '#3078ac'), ('forest', '#318142'), ('sunset', '#bb6038')):
        path = home / (name + '.png'); Image.new('RGB', (320, 180), color).save(path); images.append(path)
    colors = [accent.extract(path) for path in images]
    assert len(set(colors)) == 3
    processes = []; observer = window = connection = None
    report = {'scope': 'private-normal-user-real-xfconf-GTK-Xfwm-native-observer', 'physical_gpu_verified': False}
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read('/usr/share/dbus-1/services/org.xfce.Xfconf.service')
        command = shlex.split(config['D-BUS Service']['Exec'])
        assert len(command) == 1 and Path(command[0]).name == 'xfconfd'
        for label, args in (('xfconf', command), ('xfwm', ['/usr/bin/xfwm4', '--compositor=off']),
                            ('xsettings', ['/usr/bin/xfsettingsd', '--no-daemon'])):
            with (directory / (label + '.log')).open('w') as log:
                processes.append(subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
            pump(.5)
            assert processes[-1].poll() is None, label + ' exited'
        profiles.apply('windows11', manage_compositor=False)
        profiles.set_property('xfce4-desktop', prop, 'string', str(images[0]), profiles.run)
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'wallpaper'})
        with (directory / 'observer.log').open('w') as log:
            observer = subprocess.Popen(['/usr/lib/oguzdows/oguzdows-accent-watch'], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        until(lambda: state.load()['accent'] == colors[0], 'Initial wallpaper did not reach shared accent')
        assert observer.poll() is None
        subprocess.run(['/usr/lib/oguzdows/oguzdows-accent-watch'], check=True, timeout=6)
        assert observer.poll() is None
        report['singleton_remote_activation'] = True
        window = Gtk.Window(title='OğuzDows · gerçek otomatik vurgu')
        window.set_default_size(420, 220); window.move(50, 70)
        window.set_titlebar(Gtk.HeaderBar(title='GTK3 / Xfwm', show_close_button=True))
        button = Gtk.Button(label='Gerçek önerilen işlem / seçim rengi')
        button.get_style_context().add_class('suggested-action'); window.add(button); window.show_all()

        def native_accent_matches(expected):
            found, color = button.get_style_context().lookup_color('theme_selected_bg_color')
            expected_rgba = Gdk.RGBA(); expected_rgba.parse(expected)
            return found and max(abs(a-b) for a, b in zip((color.red, color.green, color.blue),
                                                         (expected_rgba.red, expected_rgba.green, expected_rgba.blue))) < .015

        until(lambda: native_accent_matches(colors[0]), 'GTK did not reload initial accent')
        profiles.set_property('xfce4-desktop', prop, 'string', str(images[1]), profiles.run)
        until(lambda: state.load()['accent'] == colors[1] and native_accent_matches(colors[1]), 'External xfconf wallpaper change did not reach GTK')
        theme = property_value('xsettings', '/Net/ThemeName')
        assert theme.startswith('OguzDowsElevenUser-'), theme
        assert property_value('xfwm4', '/general/theme') == theme
        report['external_wallpaper_updates_GTK_and_Xfwm'] = True
        report['windows_theme'] = theme
        # A lock held over the event must not be deleted/bypassed by the worker.
        with state.locked():
            profiles.set_property('xfce4-desktop', prop, 'string', str(images[2]), profiles.run)
            pump(2)
            assert state.load()['accent'] == colors[1]
        until(lambda: state.load()['accent'] == colors[2], 'Native observer did not retry a busy appearance transaction')
        report['lock_preserved_then_event_retried'] = True
        preferences.update_and_apply({}, resources={'compositing': False}, profile='mac')
        until(lambda: property_value('xsettings', '/Net/ThemeName').startswith('OguzDowsMacUser-'), 'Mac identity lost on common accent apply')
        assert property_value('xsettings', '/Gtk/DecorationLayout') == 'close,minimize,maximize:'
        report['mac_theme'] = property_value('xfwm4', '/general/theme')
        report['mac_left_controls'] = True
        # A real third-party GTK file manager, not a themed imitation.
        with (directory / 'thunar.log').open('w') as log:
            processes.append(subprocess.Popen(['/usr/bin/thunar', str(home)], stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        connection = display.Display(); root = connection.screen().root
        def thunar_window():
            clients = root.get_full_property(connection.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
            for xid in clients.value if clients is not None else ():
                client = connection.create_resource_object('window', int(xid))
                if any('thunar' in part.lower() for part in client.get_wm_class() or ()):
                    return client
            return None
        until(lambda: thunar_window() is not None, 'Real Thunar window did not open')
        client = thunar_window()
        extents = client.get_full_property(connection.intern_atom('_NET_FRAME_EXTENTS'), X.AnyPropertyType)
        assert extents is not None and extents.value[0] == extents.value[1] == extents.value[3] == 1, list(extents.value) if extents else None
        report['thunar_real_SSD_frame_extents'] = list(map(int, extents.value))
        pump(.3)
        capture = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), 0, 0, 1024, 768)
        assert capture is not None; capture.savev(str(directory / 'thunar-mac-accent.png'), 'png', [], [])
        preferences.update_and_apply({'accent_source': 'theme', 'accent': '#8b458f'}, resources={'compositing': False})
        until(lambda: observer.poll() == 0, 'Manual colour did not stop native observer')
        profiles.set_property('xfce4-desktop', prop, 'string', str(images[0]), profiles.run); pump(.8)
        assert state.load()['accent'] == '#8b458f'
        report['manual_colour_stops_observer_and_survives_wallpaper'] = True
        report['palettes'] = colors
    finally:
        if window: window.destroy()
        stop(observer)
        for process in reversed(processes): stop(process)
        if connection: connection.close()
        (directory / 'accent.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Native automatic wallpaper accent::' + json.dumps(report, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path); parser.add_argument('--child', type=Path)
    args = parser.parse_args()
    if os.environ.get('CI') != 'true': parser.error('Yalnız CI / özel Xvfb ekranı.')
    if args.child: child(args.child); return
    if args.output is None or not os.environ.get('XAUTHORITY'): parser.error('--output ve özel xvfb-run Xauthority gerekli.')
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-accent-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'
        shutil.copytree(ROOT / 'system/etc/skel', home); (directory / 'runtime').mkdir(mode=0o700)
        authority = directory / 'Xauthority'; shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        env = {key: value for key, value in os.environ.items() if key != 'DBUS_SESSION_BUS_ADDRESS'}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_STATE_HOME=str(home / '.local/state'),
                   XDG_CACHE_HOME=str(home / '.cache'), XDG_DATA_HOME=str(home / '.local/share'),
                   XDG_RUNTIME_DIR=str(directory / 'runtime'), XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE',
                   XDG_SESSION_TYPE='x11', GSETTINGS_BACKEND='memory', NO_AT_BRIDGE='1', GIO_USE_VFS='local')
        command = ['/usr/bin/dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()), '--child', str(directory)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['/usr/bin/setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try: subprocess.run(command, env=env, check=True, timeout=110)
        finally:
            for path in directory.iterdir():
                if path.is_file() and path.suffix in ('.log', '.json', '.png'): shutil.copy2(path, output / path.name)


if __name__ == '__main__':
    main()
