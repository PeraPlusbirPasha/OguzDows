import copy
import ctypes.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import ROOT, load

catalog = load('native_store_catalog_test', 'system/usr/lib/oguzdows/app_catalog.py')
service = load('native_store_service_test', 'system/usr/lib/oguzdows/store_service.py')
maintenance = load('native_store_apt_test', 'system/usr/lib/oguzdows/maintenance.py')
PC = {'arch': 'amd64', 'suite': 'trixie'}


class CatalogTests(unittest.TestCase):
    def test_fixed_catalog_is_unique_and_has_valid_flatpak_ids(self):
        self.assertEqual(len(catalog.APPS), 29)
        self.assertEqual(len(catalog.BY_ID), len(catalog.APPS))
        for item in catalog.APPS:
            self.assertIn(item['category'], catalog.CATEGORIES)
            self.assertTrue(item['packages'])
            self.assertEqual(maintenance.request_packages('app:' + item['id'], PC), list(item['packages']))
            if item['flatpak']:
                self.assertEqual(catalog.flatpak_id(item['flatpak']), item['flatpak'])
        for identifier in ('bash', 'libc6', '../firefox', '--assume-yes', 'wine;id'):
            with self.assertRaises(ValueError):
                maintenance.request_packages('app:' + identifier, PC)
        for identifier in ('--system', '/tmp/x', 'org/name/App', 'org..Name', 'org.example.App\n--no-gpg-verify'):
            with self.assertRaises(ValueError):
                catalog.flatpak_id(identifier)

    def test_opening_catalogue_has_no_network_or_package_action(self):
        calls = []
        def execute(command):
            calls.append(command)
            if command[0].endswith('dpkg-query'):
                return 'firefox-esr\tinstalled\nvlc:amd64\tconfig-files\n'
            if '--default-arch' in command:
                return 'x86_64'
            return ''
        result = service.catalogue(execute, PC)
        self.assertTrue(result['supports_apt'])
        self.assertTrue(result['apps'][0]['installed'])
        self.assertFalse(result['apps'][12]['installed'])
        self.assertTrue(all(command[0] in ('/usr/bin/dpkg-query', '/usr/bin/flatpak') for command in calls))
        self.assertFalse(any(word in command for command in calls for word in ('install', 'update', 'remote-add', 'search')))
        self.assertTrue(service.catalogue(execute, {'arch': 'arm64', 'platform': 'raspberrypi', 'suite': 'bookworm'})['supports_apt'])
        self.assertFalse(service.catalogue(execute, {'arch': 'arm64', 'platform': 'unknown', 'suite': 'unknown'})['supports_apt'])

    def test_command_is_argv_not_shell_and_large_or_failed_output_is_not_success(self):
        with patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'ok', '')) as run:
            self.assertEqual(service.command(['/fixed', "query'; whoami"]), 'ok')
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual(run.call_args.args[0], ['/fixed', "query'; whoami"])
        with patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'x' * (2 * 1024 * 1024 + 1), '')):
            with self.assertRaises(ValueError):
                service.command(['/fixed'])
        with patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'denied')):
            with self.assertRaises(RuntimeError):
                service.command(['/fixed'])

    def test_search_requires_explicit_valid_query_and_only_returns_flathub_ids(self):
        execute = Mock()
        for query in ('x', '--system', 'test\ncommand', 'a' * 101):
            with self.assertRaises(ValueError):
                service.search(query, execute)
        execute.assert_not_called()
        execute.side_effect = ['flathub\thttps://dl.flathub.org/repo/\tuser',
                               'org.example.App\tÖrnek\tAçıklama\tflathub\n'
                               '--system\tSahte\tBozuk\tflathub\n'
                               'org.example.Other\tBaşka\tBaşka kaynak\tuntrusted\n', 'org.example.App\n']
        result = service.search('örnek', execute)
        self.assertEqual(len(result['apps']), 1)
        self.assertEqual(result['apps'][0]['id'], 'flatpak:org.example.App')
        self.assertEqual(execute.call_args_list[-2].args[0][-1], 'örnek')
        self.assertTrue(result['apps'][0]['flatpak_installed'])

    def test_apt_only_calls_existing_helper_and_requires_plan_token(self):
        execute = Mock(return_value=json.dumps({'changes': [], 'token': 'a' * 64}))
        service.apt_request('plan', 'gimp', execute=execute)
        self.assertEqual(execute.call_args.args[0], [*service.HELPER, 'plan', 'app:gimp'])
        service.apt_request('apply', 'gimp', 'a' * 64, execute)
        self.assertEqual(execute.call_args.args[0], [*service.HELPER, 'apply', 'app:gimp', 'a' * 64])
        execute.reset_mock()
        with self.assertRaises(ValueError):
            service.apt_request('apply', 'gimp', '--force', execute)
        execute.assert_not_called()
        with self.assertRaises(ValueError):
            service.dispatch(['remove', 'libc6', 'system'])


class NativeVersionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc') and ctypes.util.find_library('glib-2.0'), 'C derleyicisi / GLib çalışma kütüphanesi yok')
    def test_headless_version_initializes_utf8_before_gtk_locale_setup(self):
        # Üretim C fast-path'i derlenir; GLib gerçektir, yalnızca üç GTK sürüm
        # getter'ı sabittir. Bu tam GTK frontend derlemesi / ekran testi değildir.
        source = (ROOT / 'native/store.c').read_text()
        branch = source.split('int main(int argc, char **argv) {', 1)[1].split('    application =', 1)[0]
        header = '''#include <locale.h>
#include <string.h>
extern void g_print(const char *, ...);
static unsigned int gtk_get_major_version(void) { return 3; }
static unsigned int gtk_get_minor_version(void) { return 24; }
static unsigned int gtk_get_micro_version(void) { return 0; }
int main(int argc, char **argv) {
'''
        glib = ctypes.util.find_library('glib-2.0')
        library = glib if '/' in glib else '-l:' + glib
        with tempfile.TemporaryDirectory() as temporary:
            for label, code, correct in (('product', branch, True), ('old-c-locale', branch.replace('setlocale(LC_ALL, "");', ''), False)):
                binary = Path(temporary) / label
                result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-x', 'c', '-', '-o', str(binary), library],
                                        input=header + code + 'return 99; }\n', capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                # DISPLAY / DBUS_SESSION_BUS_ADDRESS yok; C programı LANG'i kendi başlatmalı.
                result = subprocess.run([str(binary), '--version'], env={'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8'},
                                        capture_output=True, text=True, encoding='utf-8', timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual('OğuzDows Mağaza · GTK 3.24.0' in result.stdout, correct, result.stdout)


class FlatpakTransactionTests(unittest.TestCase):
    def api(self, commit='1' * 64, remote='flathub', signed=True):
        operation = NS(get_ref=lambda: 'app/org.gimp.GIMP/x86_64/stable', get_operation_type=lambda: 0,
                       get_remote=lambda: remote, get_commit=lambda: commit,
                       get_download_size=lambda: 100, get_installed_size=lambda: 500)
        installation = NS(get_remote_by_name=lambda *_: NS(get_url=lambda: 'https://dl.flathub.org/repo/',
                          get_gpg_verify=lambda: signed, get_disabled=lambda: False), list_installed_refs=lambda *_: [])
        class Transaction:
            def __init__(self):
                self.callbacks = {}
                self.changed = False
                self.install = None
            def set_no_interaction(self, value):
                self.no_interaction = value
            def connect(self, name, callback):
                self.callbacks[name] = callback
            def add_install(self, *args):
                self.install = args
            def get_operations(self):
                return [operation]
            def run(self, _cancellable):
                if not self.callbacks['ready'](self):
                    raise RuntimeError('Aborted at ready')
                self.changed = True
        transaction = Transaction()
        api = NS(Installation=NS(new_user=lambda *_: installation),
                 Transaction=NS(new_for_installation=lambda *_: transaction), get_default_arch=lambda: 'x86_64')
        return api, transaction

    def test_plan_resolves_real_operations_but_aborts_before_install_and_apply_matches(self):
        api, transaction = self.api()
        plan = service.flatpak_transaction('gimp', 'plan', api=api)
        self.assertFalse(transaction.changed)
        self.assertEqual(transaction.install, ('flathub', 'app/org.gimp.GIMP/x86_64/stable', None))
        self.assertEqual(len(plan['token']), 64)
        self.assertFalse(transaction.callbacks['add-new-remote'](None, None))
        result = service.flatpak_transaction('gimp', 'apply', plan['token'], api)
        self.assertTrue(transaction.changed)
        self.assertIn('tamamlandı', result['message'])

    def test_changed_commit_untrusted_remote_or_missing_token_cannot_apply(self):
        api, transaction = self.api()
        plan = service.flatpak_transaction('gimp', 'plan', api=api)
        changed, transaction = self.api(commit='2' * 64)
        with self.assertRaisesRegex(ValueError, 'değişti'):
            service.flatpak_transaction('gimp', 'apply', plan['token'], changed)
        self.assertFalse(transaction.changed)
        for fields in ({'remote': 'other'}, {'signed': False}):
            api, transaction = self.api(**fields)
            with self.assertRaises(ValueError):
                service.flatpak_transaction('gimp', 'plan', api=api)
            self.assertFalse(transaction.changed)
        for token in ('', 'bad', '--no-gpg-verify'):
            api, transaction = self.api()
            with self.assertRaises(ValueError):
                service.flatpak_transaction('gimp', 'apply', token, api)
            self.assertFalse(transaction.changed)

    def test_digest_is_order_independent_but_binds_commit_and_remote(self):
        operations = [{'ref': 'b', 'operation': 0, 'remote': 'flathub', 'commit': '1'},
                      {'ref': 'a', 'operation': 0, 'remote': 'flathub', 'commit': '2'}]
        token = service.plan_digest(operations)
        self.assertEqual(token, service.plan_digest(list(reversed(operations))))
        for field in ('remote', 'commit', 'ref'):
            changed = copy.deepcopy(operations)
            changed[0][field] = 'other'
            self.assertNotEqual(token, service.plan_digest(changed))

    def test_native_launcher_and_c_frontend_do_not_cancel_or_shell_execute(self):
        launcher = (ROOT / 'system/usr/local/bin/oguzdows-store').read_text()
        self.assertIn('exec /usr/lib/oguzdows/oguzdows-store-native', launcher)
        source = (ROOT / 'native/store.c').read_text()
        for forbidden in ('system(', 'popen(', 'g_spawn_command_line', 'g_subprocess_force_exit', 'g_cancellable_cancel'):
            self.assertNotIn(forbidden, source)
        self.assertIn('g_subprocess_communicate_utf8_async', source)
        self.assertIn('GTK_RESPONSE_CANCEL', source)
        self.assertIn('if (busy)', source)
        self.assertIn('STORE_SERVICE "/usr/lib/oguzdows/store_service.py"', source)
        self.assertIn('g_assert_cmpint(width, <=, workarea.width)', source)
        self.assertIn('g_assert_cmpint(height, <=, workarea.height)', source)
        self.assertIn('store-native-source-confirmation.png', source)
        self.assertIn('assert_feature_background();', source)
        self.assertIn('gtk_overlay_add_overlay(GTK_OVERLAY(overlay), art)', source)
        self.assertIn('GtkWidget *hero = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0)', source)


if __name__ == '__main__':
    unittest.main()
