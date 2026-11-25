"""Narrow removal contracts: simulated plans / fake libflatpak; no packages touched."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import ROOT, load

core = load('store_remove_maintenance', 'system/usr/lib/oguzdows/maintenance.py')
service = load('store_remove_service', 'system/usr/lib/oguzdows/store_service.py')
PC = {'arch': 'amd64', 'suite': 'trixie'}


def installed(version='1.0', essential=False, priority='optional'):
    return NS(installed=NS(version=version, priority=priority), essential=essential)


class SystemRemovalTests(unittest.TestCase):
    def test_only_catalogued_app_requests_get_explicit_remove_not_purge_or_autoremove(self):
        args = core.apt_command('remove-app:gimp', PC, True)
        self.assertEqual(args[-2:], ['remove', 'gimp'])
        self.assertIn('--simulate', args)
        self.assertNotIn('--no-remove', args)
        self.assertIn('--no-remove', core.apt_command('app:gimp', PC, True))
        self.assertIn('APT::Get::AutomaticRemove=false', args)
        for word in ('purge', 'autoremove', '--force-yes', '--allow-remove-essential'):
            self.assertNotIn(word, args)
        for request in ('remove-app:libc6', 'remove-app:firefox*', 'remove-app:--system', 'remove:app:gimp'):
            with self.assertRaises(core.MaintenanceError):
                core.apt_command(request, PC, True)

    def test_reverse_dependency_or_essential_or_install_plan_is_rejected_whole(self):
        cache = {'gimp': installed(), 'xfce4': installed(), 'libc6': installed()}
        result = core.removal_plan('Remv gimp [1.0]\n', ['gimp'], cache)
        self.assertEqual(result[0]['operation'], 'remove')
        for text in ('Remv gimp [1.0]\nRemv xfce4 [1.0]\n', 'Remv libc6 [1.0]\n',
                     'Remv gimp [2.0]\n', 'Remv gimp unknown\n', 'Inst other (2 Debian:stable [amd64])\n',
                     'Conf other (2 Debian:stable [amd64])\n'):
            with self.subTest(text=text), self.assertRaises(core.MaintenanceError):
                core.removal_plan(text, ['gimp'], cache)
        for package in (installed(essential=True), installed(priority='required'), installed(priority='important')):
            with self.assertRaises(core.MaintenanceError):
                core.removal_plan('Remv gimp [1.0]\n', ['gimp'], {'gimp': package})

    def test_removal_is_bound_to_recomputed_plan_and_wrong_token_never_applies(self):
        cache = {'gimp': installed()}
        execute = Mock(return_value='Remv gimp [1.0]\n')
        plan = core.make_plan('remove-app:gimp', PC, execute, cache)
        self.assertEqual(plan['intent'], 'remove')
        self.assertEqual(len(plan['token']), 64)
        execute.reset_mock()
        with self.assertRaisesRegex(core.MaintenanceError, 'değişti'):
            core.apply_plan('remove-app:gimp', 'a' * 64, PC, execute, cache)
        self.assertEqual(execute.call_count, 1)
        self.assertIn('--simulate', execute.call_args.args[0])
        execute.reset_mock()
        core.apply_plan('remove-app:gimp', plan['token'], PC, execute, cache)
        self.assertEqual(execute.call_count, 2)
        self.assertNotIn('--simulate', execute.call_args.args[0])
        self.assertEqual(execute.call_args.args[0][-2:], ['remove', 'gimp'])

    def test_service_still_uses_the_same_locked_polkit_helper_and_scoped_verb(self):
        execute = Mock(return_value=json.dumps({'changes': [], 'token': 'a' * 64}))
        plan = service.apt_request('plan', 'gimp', execute=execute, remove=True)
        self.assertEqual(plan['intent'], 'remove')
        execute.assert_called_once_with([*service.HELPER, 'plan', 'remove-app:gimp'], timeout=None)
        for identifier in ('@updates', 'libc6', '--purge'):
            with self.assertRaises(ValueError):
                service.apt_request('plan', identifier, remove=True)
        source = (ROOT / 'system/usr/local/sbin/oguzdows-maintenance').read_text()
        self.assertIn("startswith(('app:', 'remove-app:'))", source)
        self.assertIn('fcntl.flock', source)
        self.assertIn("args[0] in ('apply', 'pardus-enable') and is_live()", source)
        with patch.object(service, 'apt_request', return_value={'intent': 'remove'}) as request:
            service.dispatch(['remove-plan', 'gimp', 'system'])
            request.assert_called_once_with('plan', 'gimp', '', remove=True)


class UserFlatpakRemovalTests(unittest.TestCase):
    def api(self, *, extra=False, origin='flathub'):
        ref = 'app/org.gimp.GIMP/x86_64/stable'
        state = {'applied': False, 'uninstall': None, 'remote_read': False}
        op = NS(get_ref=lambda: 'runtime/other/x86_64/stable' if extra else ref,
                get_operation_type=lambda: 2, get_remote=lambda: '', get_commit=lambda: '',
                get_download_size=lambda: 0, get_installed_size=lambda: 500)
        class Transaction:
            def set_no_interaction(self, value):
                self.no_interaction = value
            def connect(self, name, callback):
                if name == 'ready': self.ready = callback
            def add_uninstall(self, value):
                state['uninstall'] = value
            def get_operations(self):
                return [op]
            def run(self, _cancel):
                if not self.ready(self):
                    raise RuntimeError('Stopped before mutation')
                state['applied'] = True
        transaction = Transaction()
        installation = NS(list_installed_refs=lambda _: [NS(format_ref=lambda: ref, get_origin=lambda: origin)])
        api = NS(Installation=NS(new_user=lambda _: installation),
                 Transaction=NS(new_for_installation=lambda *_: transaction),
                 TransactionOperationType=NS(UNINSTALL=2), get_default_arch=lambda: 'x86_64')
        return api, state

    def test_user_app_only_offline_preview_then_exact_approval_preserves_runtime_and_data(self):
        api, state = self.api()
        plan = service.flatpak_transaction('gimp', 'plan', api=api, remove=True)
        self.assertEqual(plan['intent'], 'remove')
        self.assertEqual(state['uninstall'], 'app/org.gimp.GIMP/x86_64/stable')
        self.assertFalse(state['applied'])
        service.flatpak_transaction('gimp', 'apply', plan['token'], api=api, remove=True)
        self.assertTrue(state['applied'])
        self.assertIn('verileri', plan['note'])

    def test_other_origin_extra_operations_updates_or_changed_token_never_uninstall(self):
        for parameters in ({'extra': True}, {'origin': 'untrusted'}):
            api, state = self.api(**parameters)
            with self.assertRaises(ValueError):
                service.flatpak_transaction('gimp', 'plan', api=api, remove=True)
            self.assertFalse(state['applied'])
        api, state = self.api()
        with self.assertRaises(ValueError):
            service.flatpak_transaction('@updates', 'plan', api=api, remove=True)
        with self.assertRaises(ValueError):
            service.flatpak_transaction('gimp', 'apply', 'f' * 64, api=api, remove=True)
        self.assertFalse(state['applied'])


class CurrentMetadataTests(unittest.TestCase):
    def test_catalogue_surfaces_actual_local_versions_and_featured_not_fake_ratings(self):
        def execute(argv):
            if argv[0].endswith('dpkg-query'):
                return 'firefox-esr\tinstalled\n'
            if '--default-arch' in argv:
                return 'x86_64'
            return ''
        result = service.catalogue(execute, PC, {'firefox': {'version': 'TEST 2', 'installed_version': 'TEST 1', 'update_available': True}})
        app = result['apps'][0]
        self.assertTrue(app['installed'])
        self.assertTrue(app['update_available'])
        self.assertEqual(app['version'], 'TEST 2')
        self.assertTrue(any(app['featured'] for app in result['apps']))
        self.assertNotIn('rating', app)
        self.assertTrue(result['checked_at'])


if __name__ == '__main__':
    unittest.main()
