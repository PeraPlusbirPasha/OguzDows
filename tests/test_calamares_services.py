"""Calamares 3.2/3.3 servis işi sözleşmesi. Gerçek systemctl çağrılmaz."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml

from support import ROOT, load

config = load('calamares_service_configure', 'scripts/configure.py')
SERVICES = ['NetworkManager.service', 'lightdm.service', 'bluetooth.service', 'zramswap.service', 'oguzdows-resource-tune.service']


def staged(arch, directory):
    output = Path(directory)
    config.configure(arch, output)
    return yaml.safe_load((output / 'includes.chroot/etc/calamares/modules/services-systemd.conf').read_text())


class CalamaresServiceContractTests(unittest.TestCase):
    def test_suite_formats_differ_but_intended_services_and_nonfatal_policy_are_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            old = staged('i386', directory)
            self.assertEqual(set(old), {'services', 'disable'})
            self.assertEqual([name + '.service' for name in old['services']], SERVICES)
            self.assertEqual(old['disable'], [])
        with tempfile.TemporaryDirectory() as directory:
            new = staged('amd64', directory)
            self.assertEqual(set(new), {'units'})
            self.assertEqual(new['units'], [{'name': name, 'action': 'enable', 'mandatory': False} for name in SERVICES])
        # Önceki ortak dosya bookworm içindir; trixie'de aynen kullanılmaz.
        self.assertEqual(yaml.safe_load((ROOT / 'installer/modules/services-systemd.conf').read_text()), old)
        self.assertNotEqual(new, old)

    def test_actually_installed_calamares_job_consumes_staged_configuration(self):
        if os.environ.get('OGUZDOWS_TEST_TARGET') == 'raspberrypi':
            self.skipTest('Pi Calamares kullanmaz; gerçek PC işi bookworm/trixie CI içinde zorunludur.')
        try:
            package = subprocess.run(['dpkg-query', '-L', 'calamares'], check=False,
                                     capture_output=True, text=True, timeout=10)
            candidates = [Path(line) for line in package.stdout.splitlines()
                          if line.endswith('/services-systemd/main.py') and Path(line).is_file()]
        except (OSError, subprocess.SubprocessError):
            candidates = []
        if not candidates:
            if os.environ.get('GITHUB_ACTIONS') == 'true':
                self.fail('CI Calamares paketi kurmalı; gerçek services-systemd işi bulunamadı.')
            self.skipTest('Yerelde Calamares yok; iki tabanlı CI gerçek modülü sınar.')
        release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                       if '=' in line and not line.startswith('#'))
        suite = release.get('VERSION_CODENAME', '').strip('"')
        arch = {'bookworm': 'i386', 'trixie': 'amd64'}.get(suite)
        if not arch:
            if os.environ.get('GITHUB_ACTIONS') == 'true':
                self.fail('Bilinmeyen Calamares tabanı; uyumluluk açıkça gözden geçirilmeli: ' + suite)
            self.skipTest('Bu sözleşme bookworm/trixie içindir.')
        with tempfile.TemporaryDirectory() as directory:
            settings = staged(arch, directory)
            call = Mock(return_value=0)
            fake = SimpleNamespace(job=SimpleNamespace(configuration=settings), utils=SimpleNamespace(
                gettext_path=lambda: '/nonexistent/oguzdows-locales', gettext_languages=lambda: ['tr'],
                target_env_call=call, warning=Mock(), error=Mock()))
            # Kaynak gerçekten kurulu paketten gelir; yalnızca yetkili çalıştırıcı sahte.
            with patch.dict('sys.modules', {'libcalamares': fake}), patch('sys.dont_write_bytecode', True):
                module = load('installed_calamares_services_contract', candidates[0])
                self.assertIsNone(module.run())
            self.assertEqual([entry.args[0] for entry in call.call_args_list],
                             [['systemctl', 'enable', name] for name in SERVICES])

    def test_native_service_requirement_fails_in_pc_ci_and_skips_only_in_explicit_pi_scope(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'OGUZDOWS_TEST_TARGET': 'pc'}), \
                patch('subprocess.run', return_value=SimpleNamespace(stdout='')):
            with self.assertRaisesRegex(AssertionError, 'CI Calamares paketi kurmalı'):
                self.test_actually_installed_calamares_job_consumes_staged_configuration()
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'OGUZDOWS_TEST_TARGET': 'raspberrypi'}), \
                patch('subprocess.run') as command:
            with self.assertRaisesRegex(unittest.SkipTest, 'Pi Calamares kullanmaz'):
                self.test_actually_installed_calamares_job_consumes_staged_configuration()
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
