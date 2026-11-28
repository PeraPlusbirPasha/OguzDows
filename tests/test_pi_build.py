"""Pi imajı oluşmadan önce: paket symlink'i / politika birleşimi / dar günlük toplama."""
import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from support import ROOT, load

config = load('pi_overlay_regression_config', 'scripts/configure-pi.py')
policy = load('pi_browser_policy', 'raspberrypi/system/usr/lib/oguzdows/pi-firefox-policy.py')
logs = load('pi_collect_logs', 'scripts/collect-pi-logs.py')


def write(root, relative, data):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data)
    return target


class PiOverlayTests(unittest.TestCase):
    def test_real_cp_preserves_absolute_package_link_for_both_architectures(self):
        for arch in ('armhf', 'arm64'):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                configuration = root / 'configuration'
                config.configure(arch, configuration)
                stage = configuration / 'stage-oguzdows/00-desktop'
                overlay = stage / 'files/overlay'
                self.assertFalse((overlay / 'usr/lib/firefox-esr').exists(), 'Boş distribution dizini bile cp -a ile paket bağlantısını bozar.')
                desired = json.loads((overlay / 'usr/share/oguzdows/firefox-policies.json').read_text())['policies']
                self.assertFalse(desired['Homepage']['Locked'])
                self.assertFalse(desired['Preferences']['browser.cache.disk.enable']['Value'])
                self.assertEqual(desired['Preferences']['browser.sessionstore.interval']['Value'], 60000)
                target = root / 'target rootfs'
                link = target / 'usr/lib/firefox-esr/distribution'
                link.parent.mkdir(parents=True)
                link.symlink_to('/etc/firefox/policies', target_is_directory=True)
                protected = target / 'etc/chatscripts'
                protected.mkdir(parents=True, mode=0o700)
                captured = root / 'chroot-script.txt'
                # Gerçek cp / üretim 01-run.sh; hesap, mount, servis veya chroot çalıştırılmaz.
                result = subprocess.run(['bash', '-c',
                    'on_chroot() { cat > "$CAPTURED"; }; export -f on_chroot; bash ./01-run.sh'],
                    cwd=stage, env={**os.environ, 'ROOTFS_DIR': str(target), 'CAPTURED': str(captured)},
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(os.readlink(link), '/etc/firefox/policies')
                self.assertEqual(stat.S_IMODE(protected.stat().st_mode), 0o700)
                self.assertTrue((target / 'usr/share/oguzdows/firefox-policies.json').is_file())
                self.assertIn('python3 /usr/lib/oguzdows/pi-firefox-policy.py', captured.read_text())

    def test_policy_merges_nested_vendor_defaults_keeps_links_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = {'policies': {'VendorOnly': True, 'Homepage': {'Extra': 'koru'},
                                    'Preferences': {'vendor.preference': {'Value': 7, 'Status': 'default'}}}}
            source = write(root, 'source.json', json.dumps({'policies': {'Homepage': {'URL': 'file:///local', 'Locked': False},
                          'Preferences': {'browser.cache.disk.enable': {'Value': False, 'Status': 'default'}}}}))
            destination = write(root, 'etc/firefox/policies/policies.json', json.dumps(existing))
            destination.chmod(0o640)
            sibling = write(destination.parent, 'extension.json', 'korunan paket verisi')
            link = root / 'usr/lib/firefox-esr/distribution'
            link.parent.mkdir(parents=True)
            link.symlink_to(os.path.relpath(destination.parent, link.parent), target_is_directory=True)
            self.assertTrue(policy.apply(source, link))
            merged = json.loads(destination.read_text())['policies']
            self.assertTrue(merged['VendorOnly'])
            self.assertEqual(merged['Homepage']['Extra'], 'koru')
            self.assertEqual(merged['Homepage']['URL'], 'file:///local')
            self.assertEqual(merged['Preferences']['vendor.preference']['Value'], 7)
            self.assertFalse(merged['Preferences']['browser.cache.disk.enable']['Value'])
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o640)
            self.assertTrue(link.is_symlink())
            self.assertEqual(sibling.read_text(), 'korunan paket verisi')
            before = destination.stat().st_mtime_ns
            self.assertFalse(policy.apply(source, link))
            self.assertEqual(destination.stat().st_mtime_ns, before)
            self.assertFalse(list(destination.parent.glob('.oguzdows-policy-*')))

    def test_missing_target_is_created_but_bad_policy_never_overwrites_existing_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write(root, 'source.json', '{"policies": {"DisableTelemetry": true}}')
            target = root / 'distribution'
            self.assertTrue(policy.apply(source, target))
            path = target / 'policies.json'
            for bad in ('{', '[]', '{"policies": []}'):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    policy.apply(source, target)
                self.assertEqual(path.read_text(), bad)
            path.write_text('{"policies": {"keep": true}}')
            source.write_text('{"policies": []}')
            with self.assertRaises(ValueError):
                policy.apply(source, target)
            self.assertTrue(json.loads(path.read_text())['policies']['keep'])

    def test_individual_policy_link_is_preserved_and_interrupted_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write(root, 'source.json', '{"policies": {"DisableTelemetry": true}}')
            destination = write(root, 'etc/firefox/policies.json', '{"policies": {"vendor": true}}')
            distribution = root / 'distribution'
            distribution.mkdir()
            link = distribution / 'policies.json'
            link.symlink_to(destination)  # Mutlak bağlantı da geçici test kökü içinde.
            self.assertTrue(policy.apply(source, distribution))
            self.assertTrue(link.is_symlink())
            self.assertTrue(json.loads(destination.read_text())['policies']['vendor'])
            previous = destination.read_bytes()
            source.write_text('{"policies": {"DisableTelemetry": false}}')
            with patch.object(policy.json, 'dump', side_effect=OSError('Test: disk dolu')):
                with self.assertRaises(OSError):
                    policy.apply(source, distribution)
            self.assertEqual(destination.read_bytes(), previous)
            self.assertTrue(link.is_symlink())
            self.assertFalse(list(destination.parent.glob('.oguzdows-policy-*')))

    def test_oversized_policy_is_rejected_before_creating_a_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write(root, 'source.json', '{"policies": {"large": "' + 'x' * 512 + '"}}')
            with patch.object(policy, 'MAX_BYTES', 128):
                with self.assertRaises(ValueError):
                    policy.apply(source, root / 'distribution')
            self.assertFalse((root / 'distribution').exists())

    def test_policy_entrypoint_is_not_a_host_configuration_command(self):
        with patch.object(policy.os, 'geteuid', return_value=1000), patch('sys.argv', ['pi-firefox-policy']), patch.object(policy, 'apply') as apply, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(policy.main(), 2)
            apply.assert_not_called()
        with patch.object(policy.os, 'geteuid', return_value=0), patch.object(policy.Path, 'is_file', return_value=False), patch('sys.argv', ['pi-firefox-policy']), patch.object(policy, 'apply') as apply, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(policy.main(), 2)
            apply.assert_not_called()


class PiLogTests(unittest.TestCase):
    def test_only_known_logs_are_copied_bounded_without_walking_or_chmodding_rootfs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build-rpi-arm64'
            original = write(build, 'build.log', '0' * 128 + '\nkesin hata\n')
            original.chmod(0o600)
            protected = build / 'pi-gen/work/OguzDows-rpi-arm64/stage-oguzdows/rootfs/etc/chatscripts'
            protected.mkdir(parents=True)
            protected.chmod(0)
            try:
                with patch.object(logs, 'MAX_BYTES', 32), patch.object(Path, 'rglob', side_effect=AssertionError('Rootfs taranamaz')), patch.object(Path, 'glob', side_effect=AssertionError('Rootfs glob taraması yok')), patch.object(os, 'walk', side_effect=AssertionError('Rootfs dolaşılamaz')):
                    report = logs.collect('arm64', build, root / 'collected')
                self.assertFalse(report['recursive_rootfs_scan'])
                self.assertFalse(report['source_permissions_changed'])
                self.assertEqual((root / 'collected/build.log').read_bytes(), original.read_bytes()[-32:])
                self.assertTrue(report['logs'][0]['truncated'])
                self.assertEqual(stat.S_IMODE(original.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(protected.stat().st_mode), 0)
                self.assertEqual(stat.S_IMODE((root / 'collected/build.log').stat().st_mode), 0o644)
            finally:
                protected.chmod(0o700)

    def test_outside_links_and_fifos_are_rejected_without_reading_or_blocking(self):
        for kind in ('link', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                build = root / 'build'
                build.mkdir()
                private = write(root, 'private.txt', 'BU VERİ GÜNLÜK DEĞİL')
                if kind == 'link':
                    (build / 'build.log').symlink_to(private)
                else:
                    os.mkfifo(build / 'build.log')
                report = logs.collect('armhf', build, root / 'out')
                self.assertEqual(report['logs'][0]['status'], 'error')
                self.assertFalse((root / 'out/build.log').exists())
                self.assertEqual(private.read_text(), 'BU VERİ GÜNLÜK DEĞİL')
                self.assertNotIn('BU VERİ GÜNLÜK DEĞİL', (root / 'out/collection.json').read_text())

    def test_missing_logs_are_reported_and_existing_or_in_tree_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build'
            build.mkdir()
            report = logs.collect('armhf', build, root / 'empty')
            self.assertTrue(all(row['status'] == 'missing' for row in report['logs']))
            sentinel = write(root, 'keep/me', 'dokunma')
            for output in (root / 'keep', build / 'new-output'):
                with self.assertRaises(ValueError):
                    logs.collect('armhf', build, output)
            self.assertFalse((build / 'new-output').exists())
            self.assertEqual(sentinel.read_text(), 'dokunma')
            with self.assertRaises(ValueError):
                logs.collect('../../outside', build, root / 'bad')
            self.assertFalse((root / 'bad').exists())

    def test_structured_porting_reports_are_copied_complete_or_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build = root / 'build'
            source = write(build, 'pi-runtime-report.json', '{"errors": []}')
            with patch.object(logs, 'MAX_BYTES', 32):
                report = logs.collect('armhf', build, root / 'out')
                row = next(row for row in report['logs'] if row['file'] == 'pi-runtime-report.json')
                self.assertEqual(row['status'], 'copied')
                self.assertFalse(row['truncated'])
                self.assertEqual(json.loads((root / 'out/pi-runtime-report.json').read_text()), {'errors': []})
                source.write_text('x' * 64)
                report = logs.collect('armhf', build, root / 'too-large')
                row = next(row for row in report['logs'] if row['file'] == 'pi-runtime-report.json')
                self.assertEqual(row['status'], 'error')
                self.assertFalse((root / 'too-large/pi-runtime-report.json').exists())

    def test_workflow_uploads_only_the_flat_collection_even_after_a_build_failure(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/raspberrypi.yml').read_text())
        steps = workflow['jobs']['image']['steps']
        collector = next(step for step in steps if 'collect-pi-logs.py' in step.get('run', ''))
        artifact = next(step for step in steps if step.get('with', {}).get('name', '').startswith('OguzDows-Pi-gunluk-'))
        self.assertEqual(collector['if'], 'always()')
        self.assertEqual(artifact['if'], 'always()')
        self.assertEqual(artifact['with']['path'], 'test-results/pi-build-${{ matrix.arch }}')
        self.assertNotIn('work/**', str(artifact))
        self.assertNotIn('chmod -R', collector['run'])


if __name__ == '__main__':
    unittest.main()
