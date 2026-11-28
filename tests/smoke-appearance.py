#!/usr/bin/env python3
"""Real Welcome callbacks -> settings -> XSettings/xfdesktop, disposable CI only.

Native ARM64 is not a physical Pi. Two synthetic solid-colour images exercise
real xfdesktop pixels; no personal files, wallpaper, role or system package is
changed by this script. The runner installs prerequisites separately.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from support import ROOT


def child(directory):
    if (os.getuid() == 0 or directory.parent != Path(tempfile.gettempdir())
            or not directory.name.startswith('oguzdows-appearance-ci-')
            or Path.home().resolve() != directory / 'home'
            or not os.environ.get('DBUS_SESSION_BUS_ADDRESS')):
        raise ValueError('Only a disposable non-root CI home/session is accepted.')
    import gi
    gi.require_version('Gtk', '3.0'); gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gtk
    from PIL import Image
    import desktop_preferences as preferences
    import desktop_state as state
    import profiles
    import wallpapers
    import welcome
    from resource_policy import policy

    processes = []
    app = None
    report = {'scope': 'private-nonroot-native-Xfce-Welcome-theme-wallpaper-and-root-pixels',
              'architecture': subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip(),
              'source_revision': os.environ.get('OGUZDOWS_SOURCE_REVISION', ''),
              'runtime_sha256': {name: hashlib.sha256((ROOT / 'system/usr/lib/oguzdows' / name).read_bytes()).hexdigest()
                                 for name in ('desktop_preferences.py', 'desktop_runtime.py', 'desktop_material.py', 'wallpapers.py', 'profiles.py')},
              'locale_probe_sha256': hashlib.sha256((ROOT / 'scripts/pi_session_smoke.py').read_bytes()).hexdigest(),
              'synthetic_image_fixture': True, 'physical_pi': False, 'physical_gpu': False,
              'performance_measurement': False, 'settings_backend_mocked': False,
              'errors': []}

    def save_report():
        (directory / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def pump(seconds=.03):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for _ in range(80):
                if not Gtk.events_pending(): break
                Gtk.main_iteration_do(False)
            time.sleep(.008)

    def until(predicate, message, seconds=30):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate(): return
            pump()
        raise AssertionError(message)

    def start(label, argv):
        with (directory / (label + '.log')).open('w') as log:
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process

    def read(channel, key, kind='string'):
        return profiles.read_property(channel, key, kind, profiles.run)

    def backdrop_keys():
        result = profiles.run(['xfconf-query', '-c', 'xfce4-desktop', '-l'])
        return sorted(line.strip() for line in result.stdout.splitlines() if line.strip().endswith('/last-image'))

    screen = Gdk.Screen.get_default()
    root = Gdk.get_default_root_window()
    def pixel():
        Gdk.Display.get_default().sync()
        # Test windows live on the left; sample the fixture background on the right.
        frame = Gdk.pixbuf_get_from_window(root, screen.get_width() - 40, screen.get_height() // 2, 4, 4)
        assert frame is not None
        return tuple(frame.get_pixels()[:3])

    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read('/usr/share/dbus-1/services/org.xfce.Xfconf.service')
        command = shlex.split(config['D-BUS Service']['Exec'])
        assert len(command) == 1 and Path(command[0]).name == 'xfconfd'
        for label, argv in [('xfconf', command), ('wm', ['xfwm4', '--compositor=off']),
                            ('xsettings', ['xfsettingsd', '--no-daemon']), ('desktop', ['xfdesktop'])]:
            process = start(label, argv)
            pump(.5)
            assert process.poll() is None, label + ' exited'
        sys.path.insert(0, str(ROOT / 'scripts'))
        from pi_session_smoke import xfconf_locale_check
        report['xfconf_locale'] = xfconf_locale_check(Path.home())
        save_report()
        # Only the resource policy and image catalogue are fixtures. No native
        # settings/apply/callback, session guard or busy guard is stubbed.
        preferences.current_policy = lambda: policy(524288)
        entries = []
        for name, rgb in [('fixture-red', (160, 30, 40)), ('fixture-blue', (30, 60, 160))]:
            path = Path.home() / (name + '.png')
            Image.new('RGB', (320, 180), rgb).save(path)
            entries.append(dict(id=name, name='TEST ONLY ' + name, path=str(path), preview=str(path)))
        wallpapers.catalog = lambda: entries
        welcome.is_live = lambda: False
        app = welcome.Welcome(); app.register(None); app.activate()
        app.window.move(20, 20); app.window.resize(570, 580)
        pump(.5)
        app.navigate('styles')
        app.profile_reload.set_active(False)  # Config transaction, not a panel process/restart test.
        report['profile_themes'] = {}
        for identifier in (*profiles.PROFILES, 'oguzdows'):
            app.profile_buttons[identifier].emit('clicked')
            assert app.profile_choice.get_active_id() == identifier
            app.profile_apply.emit('clicked')
            until(lambda: not app.profile_busy, 'Welcome profile worker did not finish: ' + identifier, 50)
            message = app.profile_status.get_text()
            assert 'kaydedildi' in message, message
            assert profiles.selection()[0] == identifier
            theme = read('xsettings', '/Net/ThemeName')
            assert theme and 'User-' in theme, theme
            assert read('xfwm4', '/general/theme') == theme
            until(lambda: Gtk.Settings.get_default().get_property('gtk-theme-name') == theme,
                  'Profile theme did not reach real GtkSettings: ' + identifier)
            assert read('xfce4-panel', '/panels', 'int-array') == (['1', '90'] if identifier in profiles.DOCK_PROFILES else ['1'])
            report['profile_themes'][identifier] = theme
            save_report()
        report['profile_panel_restart_tested'] = False
        app.navigate('appearance')
        for mode in ('dark', 'light'):
            app.theme_buttons[mode].emit('clicked')
            until(lambda: not app.theme_busy, 'Welcome theme worker did not finish', 50)
            message = app.theme_status.get_text()
            assert 'uygulandı' in message, message
            theme = read('xsettings', '/Net/ThemeName')
            assert theme and 'User-' in theme
            assert read('xfwm4', '/general/theme') == theme
            until(lambda: Gtk.Settings.get_default().get_property('gtk-theme-name') == theme,
                  'Real GtkSettings did not reload XSettings theme')
            assert state.load()['appearance'] == mode
            assert Path(os.environ['XDG_DATA_HOME'], 'themes', theme, 'gtk-3.0/gtk.css').is_file()
            report[mode + '_theme'] = theme
        report['welcome_theme_callbacks_and_GTK_reload'] = True
        save_report()
        app.navigate('wallpapers')
        for index, (entry, rgb) in enumerate(zip(entries, ((160, 30, 40), (30, 60, 160)))):
            app.wallpaper_buttons[index].emit('clicked')
            until(lambda: not app.theme_busy, 'Welcome wallpaper worker did not finish', 50)
            message = app.wallpaper_status.get_text()
            assert 'seçimin kaydedildi' in message, message
            app.window.hide(); pump(.2)
            until(lambda: pixel() == rgb, 'xfconf accepted but visible xfdesktop pixels did not change; ' + repr(pixel()))
            assert state.load()['wallpaper'] == entry['id']
            report[entry['id'] + '_root_rgb'] = pixel()
            save_report()
            app.window.show(); pump(.1)
        report['welcome_wallpaper_callbacks_and_real_pixels'] = True
        save_report()
        # Reproduce stale connector state: keep a disconnected connector's
        # last-image while an active connector has only native defaults.
        live_keys = backdrop_keys()
        assert live_keys, 'No live xfdesktop backdrop key'
        stale = '/backdrop/screen0/monitorDisconnected-CI/workspace0/last-image'
        profiles.set_property('xfce4-desktop', stale, 'string', entries[1]['path'], profiles.run)
        for key in live_keys:
            profiles.set_property('xfce4-desktop', key, 'string', None, profiles.run)
        pump(.5)
        app.wallpaper_buttons[0].emit('clicked')
        until(lambda: not app.theme_busy, 'Stale connector operation did not finish', 50)
        assert 'seçimin kaydedildi' in app.wallpaper_status.get_text(), app.wallpaper_status.get_text()
        app.window.hide(); pump(.2)
        until(lambda: pixel() == (160, 30, 40), 'Stale connector silently swallowed wallpaper change; ' + repr(pixel()))
        report['stale_connector_does_not_swallow_change'] = True
        # Only the primary enumerator fails here; GDK helper / X connection,
        # callbacks, xfconf and visible pixels remain real. This is NOT proof
        # of a physical legacy server without the RandR extension.
        native_run = wallpapers.run
        def missing_randr(command):
            if command[0] == 'xrandr':
                return subprocess.CompletedProcess(command, 1, '', 'TEST ONLY RandR unavailable')
            return native_run(command)
        app.window.show(); pump(.1)
        with patch.object(wallpapers, 'run', side_effect=missing_randr):
            app.wallpaper_buttons[1].emit('clicked')
            until(lambda: not app.theme_busy, 'GDK display fallback did not finish', 50)
            assert 'seçimin kaydedildi' in app.wallpaper_status.get_text(), app.wallpaper_status.get_text()
        app.window.hide(); pump(.2)
        until(lambda: pixel() == (30, 60, 160), 'Real GDK metadata fallback did not change xfdesktop pixels')
        report['randr_failure_injected'] = True
        report['fallback_real_gdk_helper_and_pixels'] = True
        report['native_property_count'] = len(backdrop_keys())
        report['shared_revision'] = state.load()['revision']
        save_report()
        print('::notice title=Real appearance transaction::' + json.dumps(report, ensure_ascii=True), flush=True)
    except Exception as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
        save_report()
        print('::notice title=Appearance failure context::' + json.dumps(report, ensure_ascii=True), flush=True)
        raise
    finally:
        if app and app.window:
            app.window.destroy(); app.quit()
        for process in reversed(processes):
            if process.poll() is None:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
            process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--output', type=Path, default=Path('test-results/appearance'))
    args = parser.parse_args()
    if os.environ.get('CI') != 'true':
        parser.error('Only a disposable CI / private Xvfb display is accepted.')
    if args.child:
        child(args.child.resolve()); return
    if not os.environ.get('XAUTHORITY'):
        parser.error('A private xvfb-run Xauthority is required.')
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='oguzdows-appearance-ci-') as temporary:
        directory = Path(temporary); home = directory / 'home'
        shutil.copytree(ROOT / 'system/etc/skel', home)
        for path in ('state', 'data', 'runtime', 'cache'):
            (directory / path).mkdir(mode=0o700)
        authority = directory / 'Xauthority'
        shutil.copy2(os.environ['XAUTHORITY'], authority); authority.chmod(0o600)
        # Use the copied personal skel and real dconf/session transport, not a
        # memory GSettings backend, global GTK_THEME override or a host bus.
        env = {key: value for key, value in os.environ.items() if key not in (
            'GSETTINGS_BACKEND', 'GTK_THEME', 'DBUS_SESSION_BUS_ADDRESS', 'WAYLAND_DISPLAY')}
        env.update(LANG='tr_TR.UTF-8', LANGUAGE='tr:en', LC_ALL='tr_TR.UTF-8',
                   HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                   XDG_STATE_HOME=str(directory / 'state'), XDG_DATA_HOME=str(directory / 'data'),
                   XDG_CACHE_HOME=str(directory / 'cache'), XDG_RUNTIME_DIR=str(directory / 'runtime'),
                   XAUTHORITY=str(authority), XDG_CURRENT_DESKTOP='XFCE', GDK_BACKEND='x11',
                   XDG_SESSION_TYPE='x11', NO_AT_BRIDGE='1', GIO_USE_VFS='local',
                   OGUZDOWS_SOURCE_REVISION=os.environ.get('OGUZDOWS_SOURCE_REVISION', os.environ.get('GITHUB_SHA', 'unrecorded')))
        command = ['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()), '--child', str(directory)]
        if os.getuid() == 0:
            for path in [directory, *directory.rglob('*')]: os.chown(path, 65534, 65534, follow_symlinks=False)
            command = ['setpriv', '--reuid=65534', '--regid=65534', '--clear-groups', *command]
        try:
            with (args.output / 'runner.log').open('w') as log:
                subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
        except subprocess.CalledProcessError:
            print((args.output / 'runner.log').read_text(errors='replace')[-7000:], file=sys.stderr)
            raise
        finally:
            for name in ('xfconf.log', 'wm.log', 'xsettings.log', 'desktop.log', 'result.json'):
                if (directory / name).is_file(): shutil.copyfile(directory / name, args.output / name)
        print((args.output / 'runner.log').read_text(errors='replace')[-7000:], flush=True)


if __name__ == '__main__':
    main()
