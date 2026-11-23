"""Zero giriş değişiklikleri: gerçek başlatıcı, tipli politika ve kanıt sınırları."""
import configparser
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load
from xfconf_fixture import Xfconf

start = load('session_start_test', 'system/usr/lib/oguzdows/session_start.py')
policy = load('session_policy_test', 'system/usr/lib/oguzdows/resource_policy.py')
display = load('pi_display_test', 'raspberrypi/system/usr/lib/oguzdows/pi-display-setup.py')
browser = load('new_browser_test', 'system/usr/lib/oguzdows/browser.py')
sessions = load('real_sessions_test', 'system/usr/lib/oguzdows/desktop_sessions.py')
maintenance = load('desktop_maintenance_test', 'system/usr/lib/oguzdows/maintenance.py')
profiles = load('aero_profiles_test', 'system/usr/lib/oguzdows/profiles.py')
smoke = load('nonroot_smoke_test', 'scripts/pi_session_smoke.py')


class StartTests(unittest.TestCase):
    def test_session_entry_has_valid_single_executable_tryexec_and_no_shell_arguments(self):
        entry = configparser.ConfigParser(interpolation=None)
        entry.read(ROOT / 'system/usr/share/xsessions/oguzdows.desktop')
        self.assertEqual(entry['Desktop Entry']['TryExec'], '/usr/bin/startxfce4')
        self.assertEqual(entry['Desktop Entry']['Exec'], '/usr/bin/python3 -I /usr/lib/oguzdows/session_start.py')

    def test_low_ram_environment_bounds_software_workers_but_preserves_user_choice(self):
        for memory, threads in ((524288, '1'), (1048576, '2')):
            value = start.environment(policy.policy(memory), {'WAYLAND_DISPLAY': 'wayland-0', 'KEEP': 'unchanged'})
            self.assertEqual(value['LP_NUM_THREADS'], threads)
            self.assertEqual(value['MALLOC_ARENA_MAX'], '2')
            self.assertEqual(value['GDK_BACKEND'], 'x11')
            self.assertNotIn('WAYLAND_DISPLAY', value)
            self.assertEqual(value['KEEP'], 'unchanged')
            for forbidden in ('LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER'):
                self.assertNotIn(forbidden, value)
        value = start.environment(policy.policy(524288, legacy=True), {'LP_NUM_THREADS': '3'})
        self.assertEqual(value['LP_NUM_THREADS'], '3')
        self.assertEqual(value['GSK_RENDERER'], 'cairo')
        self.assertNotIn('LP_NUM_THREADS', start.environment(policy.policy(8388608), {}))

    def test_startup_record_is_private_bounded_and_never_serializes_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            resources = policy.policy(524288, legacy=True)
            start.log_start(resources, {'PASSWORD': 'secret', 'DBUS_SESSION_BUS_ADDRESS': 'secret', 'GDK_BACKEND': 'x11'}, root)
            record = json.loads((root / 'startup.json').read_text())
            self.assertNotIn('secret', json.dumps(record))
            self.assertEqual(record['uid'], os.getuid())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((root / 'startup.json').stat().st_mode), 0o600)
            (root / 'startup.json').unlink()
            other = Path(temporary) / 'keep'
            other.write_text('keep')
            (root / 'startup.json').symlink_to(other)
            with self.assertRaises(OSError):
                start.log_start(resources, {}, root)
            self.assertEqual(other.read_text(), 'keep')

    def test_main_execs_xfce_after_one_shot_policy_and_refuses_arguments(self):
        with patch('sys.argv', ['session']), patch.object(start, 'current_policy', return_value=policy.policy(524288)), \
                patch.object(start, 'log_start'), patch('profiles.session') as prepare, patch.object(os, 'execve') as execute:
            start.main()
            prepare.assert_called_once()
            self.assertEqual(execute.call_args.args[0:2], ('/usr/bin/startxfce4', ['/usr/bin/startxfce4']))
        with patch('sys.argv', ['session', 'arbitrary-command']), self.assertRaises(SystemExit):
            start.main()

    def test_no_gpu_candidate_means_no_compositor_even_with_sufficient_ram(self):
        self.assertFalse(policy.policy(8388608, graphics=False)['compositing'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'proc').mkdir()
            (root / 'proc/meminfo').write_text('MemTotal: 8388608 kB\n')
            self.assertFalse(policy.current_policy(root)['compositing'])
            driver = root / 'sys/class/drm/card0/device/driver'
            driver.parent.mkdir(parents=True)
            (root / 'vc4').mkdir()
            driver.symlink_to(root / 'vc4')
            self.assertTrue(policy.current_policy(root)['compositing'])

    def test_nonroot_smoke_rejects_real_homes_and_root_before_starting_any_process(self):
        for path in ('/home/user', '/run/user/1000', '/', '/tmp/home'):
            with self.assertRaises(ValueError):
                smoke.private_home(path)
        with patch.object(subprocess, 'Popen') as execute, self.assertRaises(ValueError):
            smoke.session_child(Path('/should-not-write'), 'arm1176')
        execute.assert_not_called()


class DisplayTests(unittest.TestCase):
    def test_main_file_cannot_silently_override_dropin_and_other_keys_survive(self):
        source = '# personal comment\n[Seat:*]\nuser-session=LXDE-pi\ngreeter-session=pi-greeter\nxserver-command=X -nolisten tcp\n[LightDM]\nlog-directory=/keep\n'
        text = display.render(source)
        self.assertEqual(display.render(text), text)
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
        self.assertEqual(parser['Seat:*']['user-session'], 'oguzdows')
        self.assertEqual(parser['Seat:*']['greeter-session'], 'lightdm-gtk-greeter')
        self.assertEqual(parser['Seat:*']['xserver-command'], 'X -nolisten tcp')
        self.assertEqual(parser['LightDM']['log-directory'], '/keep')
        self.assertIn('# personal comment', text)
        self.assertNotIn('autologin-user=', text)
        for source in ('', '# no seat\n[LightDM]\n', '[SeatDefaults]\nuser-session=LXDE-pi\n[Seat:seat0]\nuser-session=LXDE-pi\n'):
            text = display.render(source)
            self.assertIn('[Seat:*]', text)
            self.assertNotIn('LXDE-pi', text)
            self.assertEqual(display.render(text), text)

    def test_build_display_setup_is_atomic_and_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            display.apply(root)
            path = root / 'etc/lightdm/lightdm.conf'
            before = path.read_text(), path.stat().st_mtime_ns
            display.apply(root)
            self.assertEqual((path.read_text(), path.stat().st_mtime_ns), before)
            self.assertFalse(list(path.parent.glob('.oguzdows-*')))
            path.unlink()
            path.symlink_to(root / 'other')
            with self.assertRaises(ValueError):
                display.apply(root)


class BrowserTests(unittest.TestCase):
    def test_netsurf_is_usable_without_firefox_and_legacy_never_falls_back_to_it(self):
        self.assertEqual(browser.choose(True, True, {'netsurf'}), '/usr/bin/netsurf-gtk')
        self.assertEqual(browser.choose(False, False, {'netsurf'}), '/usr/bin/netsurf-gtk')
        self.assertEqual(browser.choose(False, True, {'netsurf', 'firefox'}), '/usr/bin/netsurf-gtk')
        self.assertEqual(browser.choose(False, False, {'netsurf', 'firefox'}), '/usr/bin/firefox-esr')
        for available in (set(), {'firefox'}):
            with self.assertRaises(ValueError):
                browser.choose(True, True, available)
        for requested in ('firefox', '$(touch never)', '--no-sandbox'):
            with self.assertRaises(ValueError):
                browser.choose(True, True, {'netsurf', 'firefox'}, requested)

    def test_invalid_uri_is_not_passed_as_command_line_flags(self):
        for url in ('--private-window', 'javascript:alert(1)', 'https://example.org/\n--no-sandbox'):
            with patch('sys.argv', ['browser', url]), patch.object(os, 'execv') as execute, self.assertRaises(SystemExit):
                browser.main()
            execute.assert_not_called()


class RealDesktopTests(unittest.TestCase):
    def test_only_real_installed_xsessions_are_listed_not_theme_choices_or_wayland(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(sessions.installed(root, executable=lambda _path: True), {})
            for name in ('oguzdows', 'plasma', 'gnome-xorg'):
                (root / (name + '.desktop')).write_text('[Desktop Entry]\nType=Application\nExec=/fixed/session\n')
            self.assertEqual(set(sessions.installed(root, executable=lambda _path: True)), {'xfce', 'kde', 'gnome'})
            self.assertEqual(sessions.installed(root, executable=lambda _path: False), {})
            (root / 'plasma.desktop').write_text('[Desktop Entry]\nType=Application\nExec=/fixed/session\nHidden=true\n')
            self.assertNotIn('kde', sessions.installed(root, executable=lambda _path: True))

    def test_select_updates_accountsservice_and_dmrc_without_running_any_desktop_exec(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / '.dmrc').write_text('[Desktop]\nSession=oguzdows\nLanguage=tr_TR.UTF-8\n[Keep]\nvalue=yes\n')
            called = []
            result = sessions.select('kde', {'kde': {'session': 'plasma'}}, home, called.append)
            self.assertEqual(result, 'plasma')
            self.assertEqual(called, ['plasma'])
            self.assertIn('Language = tr_TR.UTF-8', (home / '.dmrc').read_text())
            self.assertIn('value = yes', (home / '.dmrc').read_text())
            self.assertEqual(stat.S_IMODE((home / '.dmrc').stat().st_mode), 0o600)
            before = (home / '.dmrc').read_bytes()
            def fail(_):
                raise RuntimeError('denied')
            with self.assertRaises(RuntimeError):
                sessions.select('gnome', {'gnome': {'session': 'gnome'}}, home, fail)
            self.assertEqual((home / '.dmrc').read_bytes(), before)
            self.assertFalse(list(home.glob('.oguzdows-*')))
            for identifier, choices in (('mac', {}), ('kde', {}), ('kde', {'kde': {'session': '../shell'}})):
                with self.assertRaises(ValueError):
                    sessions.select(identifier, choices, home, called.append)

    def test_zero_and_low_ram_cannot_install_heavy_desktops_but_arm64_uses_native_suite(self):
        for memory in (0, 524288, 1048576):
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.desktop_resources(memory)
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.desktop_resources(8388608, legacy=True)
        maintenance.desktop_resources(4 * 1048576)
        for arch in ('armhf', 'i386'):
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.request_packages('desktop:kde', {'arch': arch, 'suite': 'bookworm'})
        for arch, suite in (('amd64', 'trixie'), ('arm64', 'bookworm'), ('arm64', 'trixie')):
            info = {'arch': arch, 'suite': suite}
            gnome = maintenance.request_packages('desktop:gnome', info)
            kde = maintenance.request_packages('desktop:kde', info)
            self.assertIn('gnome-session', gnome)
            self.assertIn('kwin-x11', kde)
            self.assertEqual('gnome-session-xsession' in gnome, suite == 'trixie')
            self.assertIn('plasma-workspace', kde)
            self.assertNotIn('plasma-workspace-x11', kde)

    def test_new_desktop_identity_does_not_widen_general_pi_maintenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'build.json'
            file.write_text(json.dumps({'platform': 'raspberrypi', 'arch': 'arm64', 'suite': 'bookworm'}))
            self.assertEqual(maintenance.build_desktop_info(file)['arch'], 'arm64')
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.build_info(file)
            file.write_text(json.dumps({'platform': 'raspberrypi', 'arch': 'armhf', 'suite': 'bookworm'}))
            with self.assertRaises(maintenance.MaintenanceError):
                maintenance.build_desktop_info(file)


class AeroTests(unittest.TestCase):
    def test_windows11_changes_geometry_icons_and_theme_not_merely_a_name(self):
        values = {path: value for _ch, path, _kind, value in profiles.settings('windows11')}
        self.assertEqual(values['/panels/panel-90/position'], 'p=10;x=0;y=0')
        self.assertEqual(values['/panels/panel-90/length'], '1')
        self.assertEqual(values['/panels/panel-90/length-adjust'], 'true')
        self.assertEqual(values['/panels/panel-1/position'], 'p=9;x=0;y=0')
        self.assertIn('1', values['/panels/panel-90/plugin-ids'])
        self.assertNotIn('3', values['/panels/panel-90/plugin-ids'])
        self.assertNotIn('7', values['/panels/panel-90/plugin-ids'])
        self.assertEqual(values['/plugins/plugin-2/show-labels'], 'false')
        self.assertEqual(values['/plugins/plugin-1/show-button-title'], 'false')
        self.assertEqual(values['/Net/ThemeName'], 'OguzDowsEleven')

    def test_aero_static_theme_remains_on_zero_and_opaque_controls_on_full(self):
        for memory in (524288, 1048576, 8388608):
            values = {path: value for _ch, path, _kind, value in profiles.settings('windows11', 'dark', 'aero', policy.policy(memory))}
            self.assertEqual(values['/Net/ThemeName'], 'OguzDowsAeroDark')
            self.assertEqual(values['/general/frame_opacity'], '100')
            self.assertEqual(values['/general/inactive_opacity'], '100')
            self.assertEqual(values['/general/popup_opacity'], '100')
            self.assertEqual(values['/general/use_compositing'], 'false', 'Aero tek Picom kompozitörü kullanır')
            self.assertEqual(values['/Gtk/EnableAnimations'], str(memory > 2097152).lower())
        with self.assertRaises(ValueError):
            profiles.settings('windows11', 'invalid', 'aero')

    def test_effect_and_appearance_changes_keep_layout_and_restore_typed_backup(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = dict(xfconf.values)
            profiles.apply('windows11', root, xfconf)
            position = xfconf.values['xfce4-panel', '/panels/panel-1/position']
            profiles.set_effects('aero', root, xfconf, policy.policy(524288))
            profiles.set_appearance('dark', root, xfconf)
            self.assertEqual(xfconf.values['xsettings', '/Net/ThemeName'], 'OguzDowsAeroDark')
            self.assertEqual(xfconf.values['xfce4-panel', '/panels/panel-1/position'], position)
            profiles.set_effects('off', root, xfconf)
            self.assertEqual(xfconf.values['xsettings', '/Net/ThemeName'], 'OguzDowsElevenDark')
            profiles.restore(root, xfconf)
            self.assertEqual(xfconf.values, original)


if __name__ == '__main__':
    unittest.main()
