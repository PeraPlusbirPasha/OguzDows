"""Kurulu uygulamaya açık başlatma isteği; gerçek program / paket çalışmaz."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from PIL import Image
from support import ROOT, load

service = load('launch_store_service', 'system/usr/lib/oguzdows/store_service.py')
assets = load('launch_store_assets', 'scripts/render-assets.py')


class LaunchTests(unittest.TestCase):
    def api(self):
        application = Mock()
        application.launch_uris_as_manager.return_value = True
        return NS(DesktopAppInfo=NS(new_from_filename=Mock(return_value=application)),
                  AppInfo=NS(create_from_commandline=Mock(return_value=application)),
                  AppInfoCreateFlags=NS(NONE=0)), application

    def execute(self, command, **_kwargs):
        self.commands.append(command)
        if '--default-arch' in command:
            return self.arch
        if '--show-ref' in command:
            return 'app/org.gimp.GIMP/' + self.arch + '/stable' if self.installed else ''
        if command[0].endswith('dpkg-query'):
            return 'gimp\tinstalled\n' if self.installed else ''
        return ''

    def setUp(self):
        self.commands, self.arch, self.installed = [], 'aarch64', True
        self.uid = patch.object(service.os, 'geteuid', return_value=1000).start()
        launch_application = service.launch_application
        flags_api = NS(SpawnFlags=NS(SEARCH_PATH=4, STDOUT_TO_DEV_NULL=8, STDERR_TO_DEV_NULL=16))
        patch.object(service, 'launch_application', side_effect=lambda app: launch_application(app, flags_api)).start()
        self.addCleanup(patch.stopall)

    def test_user_launch_is_explicit_user_scope_exact_installed_stable_ref_and_no_admin(self):
        api, app = self.api()
        result = service.launch('gimp', 'flatpak', self.execute, api)
        api.AppInfo.create_from_commandline.assert_called_once_with(
            '/usr/bin/flatpak run --user --arch=aarch64 --branch=stable org.gimp.GIMP', None, 0)
        app.launch_uris_as_manager.assert_called_once_with(
            uris=[], launch_context=None, spawn_flags=28, user_setup=None, user_setup_data=None, pid_callback=None, pid_callback_data=None)
        self.assertIn('isteği gönderildi', result['message'])
        app.launch.assert_not_called()
        self.assertFalse(any('pkexec' in ' '.join(command) for command in self.commands))
        self.assertFalse(any('install' in command or 'update' in command for command in self.commands))
        api.DesktopAppInfo.new_from_filename.assert_not_called()

    def test_missing_app_or_unsupported_arch_is_not_executed(self):
        for arch, installed in (('arm', True), ('i386', True), ('aarch64', False)):
            self.arch, self.installed = arch, installed
            api, app = self.api()
            with self.assertRaises(ValueError):
                service.launch('gimp', 'flatpak', self.execute, api)
            app.launch_uris_as_manager.assert_not_called()
            api.AppInfo.create_from_commandline.assert_not_called()

    def test_different_branch_or_system_scope_install_does_not_count_as_user_install(self):
        execute = Mock(side_effect=['x86_64', 'app/org.gimp.GIMP/x86_64/beta'])
        self.assertFalse(service.launch_state('gimp', 'flatpak', execute)['can_launch'])
        self.assertEqual(execute.call_args_list[1].args[0], ['/usr/bin/flatpak', '--user', 'info', '--show-ref', 'org.gimp.GIMP'])

    def test_root_or_invalid_identifier_cannot_launch_or_inject_options(self):
        api, app = self.api()
        with patch.object(service.os, 'geteuid', return_value=0), self.assertRaises(ValueError):
            service.launch('gimp', 'flatpak', self.execute, api)
        for identifier, source in (('flatpak:--system', 'flatpak'), ('flatpak:org.example.App;id', 'flatpak'),
                                   ('../../shell', 'system'), ('gimp', 'sudo')):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                service.launch(identifier, source, self.execute, api)
        app.launch_uris_as_manager.assert_not_called()
        self.assertFalse(self.commands)

    def test_system_launch_uses_only_fixed_packaged_desktop_not_user_override(self):
        api, app = self.api()
        with patch.object(service, 'system_desktop', return_value=Path('/usr/share/applications/gimp.desktop')):
            service.launch('gimp', 'system', self.execute, api)
        api.DesktopAppInfo.new_from_filename.assert_called_once_with('/usr/share/applications/gimp.desktop')
        api.AppInfo.create_from_commandline.assert_not_called()
        app.launch_uris_as_manager.assert_called_once_with(
            uris=[], launch_context=None, spawn_flags=28, user_setup=None, user_setup_data=None, pid_callback=None, pid_callback_data=None)
        with patch.object(service, 'system_desktop', return_value=None), self.assertRaises(ValueError):
            service.launch('gimp', 'system', self.execute, api)

    def test_packaged_launcher_links_writable_and_user_owned_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            desktop = root / 'gimp.desktop'
            desktop.write_text('[Desktop Entry]\nExec=/bin/false\n')
            # Test hesabı root olabilir; kullanıcıya yazılabilir dosya her durumda reddedilir.
            desktop.chmod(0o666)
            self.assertIsNone(service.system_desktop('gimp', root))
            desktop.unlink()
            desktop.symlink_to('/usr/share/applications/gimp.desktop')
            self.assertIsNone(service.system_desktop('gimp', root))
            desktop.unlink()
            desktop.write_text('[Desktop Entry]\nExec=/bin/false\n')
            with patch.object(Path, 'lstat', return_value=NS(st_mode=stat.S_IFREG | 0o644, st_uid=1001)):
                self.assertIsNone(service.system_desktop('gimp', root))
            with patch.object(Path, 'lstat', return_value=NS(st_mode=stat.S_IFREG | 0o644, st_uid=0)):
                self.assertEqual(service.system_desktop('gimp', root), desktop)

    def test_local_launch_remains_available_if_flatpak_remote_was_removed(self):
        result = service.detail('gimp', 'flatpak', self.execute)
        self.assertTrue(result['can_launch'])
        self.assertTrue(result['installed'])
        self.assertIn('hazır değil', result['detail'])
        self.assertFalse(any('remote-info' in command for command in self.commands))

    def test_launch_failure_is_not_reported_as_success(self):
        api, app = self.api()
        app.launch_uris_as_manager.return_value = False
        with self.assertRaisesRegex(ValueError, 'kabul etmedi'):
            service.launch('gimp', 'flatpak', self.execute, api)

    def test_unavailable_gio_launcher_is_an_error_without_falling_back_to_shell(self):
        api, app = self.api()
        api.DesktopAppInfo.new_from_filename.return_value = None
        with patch.object(service, 'system_desktop', return_value=Path('/usr/share/applications/gimp.desktop')):
            with self.assertRaisesRegex(ValueError, 'kabul etmedi'):
                service.launch('gimp', 'system', self.execute, api)
        app.launch.assert_not_called()
        app.launch_uris_as_manager.assert_not_called()

    def test_real_gio_smoke_refuses_non_ci_and_root_worker_before_any_application(self):
        cases = [({'CI': 'false'}, [], 'tek kullanımlık CI')]
        if os.getuid() == 0:
            cases.append(({'CI': 'true'}, ['--worker', '/does-not-exist'], 'gerçek yönetici olmayan'))
        for extra, arguments, expected in cases:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'must-not-exist'
                result = subprocess.run([sys.executable, '-I', str(ROOT / 'tests/smoke-store-launch.py'), '--output', str(output), *arguments],
                                        env={**extra, 'PATH': os.environ.get('PATH', '')}, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertFalse(output.exists())

    def test_private_launch_environment_is_set_after_switching_user_not_overwritten_by_runuser(self):
        smoke = load('gio_launch_private_environment', 'tests/smoke-store-launch.py')
        home, directory = Path('/private/test-home'), Path('/private/test-root')
        arguments = smoke.worker_command(NS(pw_name='nobody'), home, directory)
        self.assertEqual(arguments[:5], ['runuser', '-u', 'nobody', '--', '/usr/bin/env'])
        dbus_index = arguments.index('dbus-run-session')
        values = dict(value.split('=', 1) for value in arguments[5:dbus_index])
        self.assertEqual(values['HOME'], str(home))
        self.assertEqual(values['XDG_RUNTIME_DIR'], str(home / 'runtime'))
        self.assertEqual(values['USER'], 'nobody')
        self.assertEqual(arguments[-2:], ['--worker', str(directory)])
        self.assertNotIn('/bin/sh', arguments)
        self.assertNotIn('/bin/bash', arguments)

    def test_catalogue_declares_unsupported_passwordless_install_honestly(self):
        for arch, expected in (('arm', False), ('i386', False), ('aarch64', True), ('x86_64', True)):
            self.arch = arch
            result = service.catalogue(self.execute, {'arch': 'armhf', 'platform': 'raspberrypi', 'suite': 'bookworm'})
            self.assertEqual(result['supports_user_flatpak'], expected)
            self.assertTrue(result['supports_apt'])

    def test_each_curated_app_has_a_small_distinct_offline_icon_even_when_not_installed(self):
        manifest = json.loads((ROOT / 'system/usr/share/oguzdows/store-icons.json').read_text())
        self.assertEqual({item['id'] for item in manifest}, set(service.app_catalog.BY_ID) | {'flathub'})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets.render_store_icons(root)
            hashes = set()
            for item in service.app_catalog.APPS:
                path = root / ('usr/share/icons/hicolor/64x64/apps/' + item['fallback_icon'] + '.png')
                self.assertLess(path.stat().st_size, 12000)
                with Image.open(path) as image:
                    self.assertEqual(image.size, (64, 64))
                    hashes.add(image.tobytes())
            self.assertEqual(len(hashes), len(service.app_catalog.APPS))


if __name__ == '__main__':
    unittest.main()
