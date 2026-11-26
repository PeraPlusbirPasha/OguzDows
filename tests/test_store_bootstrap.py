"""Store engine repair: fixed bundles, actual disabled-remote reproduction, no installs."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import ROOT, load

core = load('bootstrap_store_core', 'system/usr/lib/oguzdows/store_core.py')
service = load('bootstrap_store_service', 'system/usr/lib/oguzdows/store_service.py')
maintenance = load('bootstrap_store_maintenance', 'system/usr/lib/oguzdows/maintenance.py')

READY = 'flathub\thttps://dl.flathub.org/repo/\tuser'
DISABLED = 'flathub\thttps://dl.flathub.org/repo/\tdisabled,user'
PC = {'arch': 'amd64', 'suite': 'trixie'}
PI = {'platform': 'raspberrypi', 'arch': 'armhf', 'suite': 'bookworm'}


class RemoteRepairTests(unittest.TestCase):
    def test_enabled_remote_with_empty_cli_options_is_not_misclassified(self):
        for suffix in ('', '\t', '\t\n'):
            self.assertEqual(core.remote_state('flathub\thttps://dl.flathub.org/repo/' + suffix), 'ready')

    def test_disabled_signed_official_remote_is_not_ready_reproduction(self):
        self.assertFalse(core.official_remote(DISABLED))
        self.assertEqual(core.remote_state(DISABLED), 'disabled')
        self.assertFalse(service.remote_ready(Mock(return_value=DISABLED)))

    def test_explicit_setup_enables_only_known_signed_user_remote_and_rechecks(self):
        execute = Mock(side_effect=['aarch64', DISABLED, '', READY])
        core.setup_flathub(execute)
        self.assertEqual(execute.call_args_list[2].args[0], ['/usr/bin/flatpak', '--user', 'remote-modify', '--enable', 'flathub'])
        self.assertEqual(execute.call_args_list[1].args, execute.call_args_list[3].args)
        self.assertFalse(any('--system' in call.args[0] or '--no-gpg-verify' in call.args[0] for call in execute.call_args_list))

    def test_failed_enable_cannot_report_success(self):
        execute = Mock(side_effect=['x86_64', DISABLED, '', DISABLED])
        with self.assertRaisesRegex(ValueError, 'doğrulanamadı'): core.setup_flathub(execute)

    def test_untrusted_conflicting_or_duplicate_remote_never_gets_mutation(self):
        for listing in (DISABLED.replace('user', 'no-gpg-verify,user'), READY.replace('https://', 'http://'),
                        READY.replace('dl.flathub.org', 'evil.example'), READY + '\n' + READY, 'flathub'):
            execute = Mock(side_effect=['x86_64', listing])
            with self.subTest(listing=listing), self.assertRaises(ValueError): core.setup_flathub(execute)
            self.assertEqual(execute.call_count, 2)

    def test_missing_engine_has_actionable_message_and_old_arch_is_not_faked(self):
        execute = Mock(side_effect=FileNotFoundError())
        with self.assertRaisesRegex(ValueError, 'bileşenlerini kur'): core.setup_flathub(execute)
        for architecture in ('arm', 'armhf', 'i386'):
            execute = Mock(return_value=architecture)
            with self.assertRaises(ValueError): core.setup_flathub(execute)
            self.assertEqual(execute.call_count, 1)


class BootstrapBundleTests(unittest.TestCase):
    def test_both_engines_are_fixed_catalogue_bundles_not_arbitrary_root_install(self):
        flatpak = maintenance.request_packages('app:flatpak-support', PC)
        software = maintenance.request_packages('app:software-center', PC)
        self.assertIn('flatpak', flatpak)
        self.assertIn('gir1.2-flatpak-1.0', flatpak)
        self.assertIn('xdg-desktop-portal-gtk', flatpak)
        self.assertTrue({'gnome-software', 'gnome-software-plugin-flatpak', 'packagekit', 'iso-codes'} <= set(software))
        for info in (PC, PI, {**PI, 'arch': 'arm64'}, {'arch': 'i386', 'suite': 'bookworm'},
                     {'platform': 'arm', 'arch': 'arm64', 'suite': 'trixie', 'device_profile': 'pinephone'}):
            self.assertEqual(maintenance.request_packages('app:software-center', info), software)
        for request in ('app:flatpak;id', 'app:gnome-shell', 'app:packagekit', 'app:--allow-unauthenticated'):
            with self.assertRaises(ValueError): maintenance.request_packages(request, PC)
        for identifier in ('flatpak-support', 'software-center'):
            command = maintenance.apt_command('app:' + identifier, PC, True)
            self.assertIn('--simulate', command)
            self.assertIn('--no-remove', command)
            with self.assertRaisesRegex(ValueError, 'altyapısı'):
                maintenance.apt_command('remove-app:' + identifier, PC)

    def test_engine_plans_still_require_exact_digest_approved_arch_and_signed_origin(self):
        text = 'Inst flatpak (1.0 Debian:13/trixie [amd64])\nConf flatpak (1.0 Debian:13/trixie [amd64])\n'
        cache = {'flatpak': NS(candidate=NS(version='1.0', architecture='amd64', origins=[NS(origin='Debian', codename='trixie', trusted=True)]))}
        execute = Mock(return_value=text)
        plan = maintenance.make_plan('app:flatpak-support', PC, execute, cache)
        with self.assertRaises(ValueError): maintenance.apply_plan('app:flatpak-support', 'a' * 64, PC, execute, cache)
        self.assertFalse(any('--assume-yes' in call.args[0] for call in execute.call_args_list))
        for key, value in (('architecture', 'arm64'), ('version', '2.0')):
            old = getattr(cache['flatpak'].candidate, key)
            setattr(cache['flatpak'].candidate, key, value)
            with self.assertRaises(ValueError): maintenance.make_plan('app:flatpak-support', PC, execute, cache)
            setattr(cache['flatpak'].candidate, key, old)
        cache['flatpak'].candidate.origins[0].trusted = False
        with self.assertRaises(ValueError): maintenance.make_plan('app:flatpak-support', PC, execute, cache)
        self.assertEqual(len(plan['token']), 64)

    def test_refresh_has_its_own_store_scope_not_a_general_arm_maintenance_unlock(self):
        source = (ROOT / 'system/usr/local/sbin/oguzdows-maintenance').read_text()
        self.assertIn("args[0] == 'store-refresh'", source)
        self.assertIn("core.build_store_info() if app_request else core.build_info()", source)
        self.assertIn("args[0] in ('apply', 'pardus-enable') and is_live()", source)
        helper = Mock(return_value=json.dumps({'message': 'yenilendi'}))
        with patch.object(service, 'command', helper): service.dispatch(['refresh'])
        helper.assert_called_once_with([*service.HELPER, 'store-refresh'], timeout=None)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'build.json'; path.write_text(json.dumps(PI))
            self.assertEqual(maintenance.build_store_info(path), PI)
            with self.assertRaises(ValueError): maintenance.build_info(path)

    def test_advanced_wrapper_is_no_longer_removed_from_pi_or_generic_arm(self):
        configure = load('bootstrap_configure_pi', 'scripts/configure-pi.py')
        for name in ('usr/lib/oguzdows/store.py', 'usr/lib/oguzdows/store_lifecycle.py',
                     'etc/xdg/autostart/org.gnome.Software.desktop', 'usr/share/glib-2.0/schemas/90_oguzdows-store.gschema.override'):
            self.assertNotIn(name, configure.PC_ONLY)
        self.assertIn('Hidden=true', (ROOT / 'system/etc/xdg/autostart/org.gnome.Software.desktop').read_text())
        entry = (ROOT / 'system/usr/share/applications/oguzdows-software.desktop').read_text()
        self.assertIn('Exec=/usr/local/bin/oguzdows-store --advanced', entry)
        self.assertIn('NoDisplay=true', entry)
        native = (ROOT / 'native/store.c').read_text()
        self.assertNotIn('sudo apt install gnome-software', native)
        self.assertIn('run_service(BUNDLE_PLAN, "plan", id, "system", NULL)', native)
        self.assertIn('BUNDLE_APPLY', native)

    def test_offline_health_reports_missing_engines_disabled_remote_and_does_not_install(self):
        calls = []
        def execute(arguments):
            calls.append(arguments)
            if arguments[0].endswith('dpkg-query'): return 'flatpak\tinstalled\n'
            if '--default-arch' in arguments: return 'x86_64'
            if 'remotes' in arguments: return DISABLED
            return ''
        with tempfile.TemporaryDirectory() as temporary:
            result = service.store_health(execute, PC, Path(temporary))
        self.assertIn('gnome-software', result['detail'])
        self.assertIn('devre dışı', result['detail'])
        self.assertIn('ISO639 dil verisi: EKSİK', result['detail'])
        self.assertFalse(any(word in args for args in calls for word in ('install', 'update', 'remote-add', 'remote-modify')))

    def test_comparison_reads_local_metadata_only_and_does_not_invent_flatpak_size(self):
        calls = []
        def execute(args):
            calls.append(args)
            if '--default-arch' in args: return 'aarch64'
            return ''
        result = service.compare_sources('gimp', execute, {'gimp': {'version': '3.0', 'metadata_known': True,
                                        'download_bytes': 123, 'installed_bytes': 456}})
        self.assertIn('123 bayt', result['detail'])
        self.assertIn('456 bayt', result['detail'])
        self.assertIn('tahmin edilmez', result['detail'])
        self.assertIn('yalnız bu hesap', result['detail'])
        self.assertFalse(any('remote-info' in args or 'search' in args for args in calls))
        with self.assertRaises(ValueError): service.compare_sources('arbitrary-package', execute, {})


if __name__ == '__main__':
    unittest.main()
