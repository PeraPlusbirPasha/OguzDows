"""ISO hedef OS testinin sınırları; bu birim testler VM / disk açmaz."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from support import ROOT, load

smoke = load('iso_target_smoke_contract', 'tests/smoke-iso-target.py')


class IsoTargetSmokeContractTests(unittest.TestCase):
    def test_new_native_material_news_and_store_bytes_must_match_image_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, source in smoke.NATIVE_CONTENT.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            with patch('builtins.print'):
                hashes = smoke.native_material_contract(root)
            self.assertEqual(len(hashes), 24)
            (root / 'usr/share/oguzdows/ui/modern.css').write_text('stale old theme')
            with self.assertRaisesRegex(RuntimeError, 'eşleşmiyor'):
                smoke.native_material_contract(root)

    def test_modes_and_accent_exact_hashes_and_native_target_abi_are_gated_in_iso(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, source in smoke.MODE_CONTENT.items():
                target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            header = bytearray(20); header[:4] = b'\x7fELF'; header[4] = 2; header[5] = 1; header[18:20] = (62).to_bytes(2, 'little')
            library = root / 'usr/lib/x86_64-linux-gnu/xfce4/panel/plugins/liboguzdows-tasks.so'
            library.parent.mkdir(parents=True); library.write_bytes(header)
            observer = root / 'usr/lib/oguzdows/oguzdows-accent-watch'; observer.write_bytes(header); observer.chmod(0o755)
            stat = Path.stat
            def owned(path, *, follow_symlinks=True):
                values = list(stat(path, follow_symlinks=follow_symlinks)); values[4] = values[5] = 0
                return os.stat_result(values)
            with patch.object(Path, 'stat', owned), patch('builtins.print') as printed:
                report = smoke.mode_contract(root, 'amd64')
                self.assertTrue(report['target_abi_verified'])
                self.assertEqual(len(report['content_sha256']), len(smoke.MODE_CONTENT))
                self.assertGreaterEqual(len(report['content_sha256']), 30)
                for call in printed.call_args_list: self.assertLess(len(call.args[0].encode()), 4000)
                header[4] = 1; library.write_bytes(header)
                with self.assertRaisesRegex(RuntimeError, 'ABI'): smoke.mode_contract(root, 'amd64')
                header[4] = 2; library.write_bytes(header)
                (root / 'usr/lib/oguzdows/accent.py').write_text('old worker')
                with self.assertRaisesRegex(RuntimeError, 'eşleşmiyor'): smoke.mode_contract(root, 'amd64')

    def test_final_notice_retains_boot_source_abi_and_every_ram_budget_without_duplicate_hashes(self):
        measurements = [{'vm_ram_mib': ram, 'valid_idle_measurement': True, 'target_met': True,
                         'median_used_mb': 300, 'max_used_mb': 301,
                         'low_ram_budget': {'passed': True, 'minimum_available_bytes': 50000000,
                                            'observed_min_available_bytes': 100000000, 'fail_reasons': []}}
                        for ram in (512, 1024, 2048)]
        report = {'arch': 'amd64', 'source_revision': 'a' * 40, 'modes': ['bios', 'efi'],
                  'build': {'source_revision': 'a' * 40, 'source_dirty': None},
                  'desktop_idle': measurements[2], 'low_ram': measurements[:2],
                  'desktop_contract': {'desktop_modes': {'target_abi_verified': True},
                                       'native_app_content_sha256': {'large': 'x' * 10000}}}
        text = smoke.result_summary(report)
        selected = json.loads(text)
        self.assertLess(len(text.encode()), 3500)
        self.assertEqual(selected['modes'], ['bios', 'efi'])
        self.assertEqual(selected['build'], report['build'])
        self.assertTrue(selected['desktop_modes_target_abi_verified'])
        self.assertEqual([value['vm_ram_mib'] for value in selected['low_ram']], [512, 1024])
        self.assertEqual(selected['desktop_idle'], measurements[2])
        self.assertNotIn('native_app_content_sha256', text)
        report['build']['unexpected'] = 'x' * 4000
        with self.assertRaisesRegex(RuntimeError, 'sınırını'):
            smoke.result_summary(report)

    def test_verbose_package_diagnostics_do_not_consume_the_ram_notice_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'target'; output = root / 'output'
            output.mkdir(); (target / 'var/lib/dpkg').mkdir(parents=True)
            (target / 'var/lib/dpkg/status').write_text('Package: initramfs-tools\nVersion: 1\nStatus: install ok installed\n')
            with patch('builtins.print') as printed:
                smoke.record_live_state(target, output, 'before')
            self.assertTrue((output / 'target-live-before.json').is_file())
            self.assertFalse(any(call.args[0].startswith('::notice') for call in printed.call_args_list))
        workflows = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        diagnostic = workflows['jobs']['diagnostics']['steps'][-1]['run']
        self.assertIn("'desktop_idle', 'low_ram'", diagnostic)
        self.assertNotIn('::notice title=Önceki erken açılış belleği', diagnostic)

    def test_guard_rejects_non_ci_and_non_regular_iso_before_mount_or_mkdtemp(self):
        arguments = ['smoke-iso-target', '--iso', '/dev/null', '--arch', 'amd64', '--expected-revision', 'a' * 40]
        for ci, uid in (('false', 0), ('true', 1000), ('true', 0)):
            with self.subTest(ci=ci, uid=uid), patch('sys.argv', arguments), patch.dict(os.environ, {'CI': ci}), patch.object(smoke.os, 'geteuid', return_value=uid), patch.object(smoke.tempfile, 'mkdtemp') as temp, patch.object(smoke.subprocess, 'run') as child, patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    smoke.main()
                self.assertEqual(error.exception.code, 2)
                temp.assert_not_called()
                child.assert_not_called()

    def test_vm_boot_requires_uuid_specific_os_proof_not_the_old_grub_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            serial = root / 'target-os-bios.serial.log'
            serial.write_text('OGUZDOWS-INSTALLED-BIOS-OK\n')
            process = Mock()
            process.poll.return_value = 0
            with patch.object(smoke.subprocess, 'Popen', return_value=process), self.assertRaisesRegex(RuntimeError, 'erken kapandı'):
                smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc')
            process.poll.return_value = None
            serial.write_text('OGUZDOWS-TARGET-OS-OK:abc\n')
            with patch.object(smoke.subprocess, 'Popen', return_value=process) as child, patch('builtins.print'):
                smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc')
            command = child.call_args.args[0]
            for bypass in ('-kernel', '-initrd', '-cdrom'):
                self.assertNotIn(bypass, command)
            self.assertIn('none', command)
            self.assertTrue(any('snapshot=on' in arg for arg in command))
            self.assertNotIn('OGUZDOWS-TARGET-OS-OK', str(command))
            process.terminate.assert_called_once()

    def test_graphical_idle_setup_is_confined_to_disposable_root_and_locked_test_account(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                smoke.configure_idle_test(root, 0)
            self.assertFalse(list(root.iterdir()))
            smoke.configure_idle_test(root, 1001)
            marker = root / 'home/oguz-idle-proof/.local/state/oguzdows/welcome-installed-1.1-seen'
            self.assertTrue(marker.is_file())
            script = (root / 'usr/local/sbin/oguzdows-disposable-idle').read_text()
            for argument in ('--user 1001', '--wait-for-desktop 180', '--settle-seconds 120', '--samples 6 --interval 5', '--idle-confirmed'):
                self.assertIn(argument, script)
            self.assertIn('OGUZDOWS-DESKTOP-IDLE-JSON:', script)
            self.assertIn('/dev/ttyS0', script)
            self.assertTrue((root / 'etc/systemd/system/graphical.target.wants/oguzdows-disposable-idle.service').is_symlink())
            self.assertFalse((ROOT / 'system/etc/lightdm/lightdm.conf.d/99-oguzdows-disposable-idle.conf').exists())
            self.assertFalse((ROOT / 'system/etc/systemd/system/oguzdows-disposable-idle.service').exists())

    def test_vm_graphical_report_does_not_call_an_above_target_measurement_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            measurement = {'samples': [{'graphical_xfce': True}], 'valid_idle_measurement': True,
                           'max_used_mb': 650.0, 'median_used_mb': 649.0, 'target_met': False, 'invalid_reasons': []}
            serial = root / 'target-os-bios.serial.log'
            serial.write_text('OGUZDOWS-TARGET-OS-OK:abc\nOGUZDOWS-DESKTOP-IDLE-JSON:' + json.dumps(measurement) + '\n')
            process = Mock()
            process.poll.return_value = None
            with patch.object(smoke.subprocess, 'Popen', return_value=process), patch('builtins.print') as notice:
                result = smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True)
            self.assertFalse(result['target_met'])
            self.assertIn('::warning', notice.call_args.args[0])
            self.assertEqual(json.loads((root / 'desktop-idle.json').read_text()), {**measurement, 'vm_ram_mib': 2048})
            measurement['samples'][0]['graphical_xfce'] = False
            serial.write_text('OGUZDOWS-TARGET-OS-OK:abc\nOGUZDOWS-DESKTOP-IDLE-JSON:' + json.dumps(measurement) + '\n')
            with patch.object(smoke.subprocess, 'Popen', return_value=process), self.assertRaisesRegex(RuntimeError, 'tam Xfce'):
                smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True)

    def test_low_ram_boot_records_real_vm_budget_and_rejects_oom(self):
        for ram in (512, 1024):
            with self.subTest(ram=ram), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                serial = root / 'target-os-bios.serial.log'
                measurement = {'samples': [{'graphical_xfce': True, 'total_bytes': (ram - 32) * 1024**2,
                                            'available_bytes': ram * 1024**2 // 2} for _ in range(6)],
                               'valid_idle_measurement': True, 'target_met': True}
                uart = 'OGUZDOWS-TARGET-OS-OK:abc\nOGUZDOWS-DESKTOP-IDLE-JSON:' + json.dumps(measurement) + '\n'
                serial.write_text(uart)
                process = Mock()
                process.poll.return_value = None
                with patch.object(smoke.subprocess, 'Popen', return_value=process) as spawn, patch('builtins.print'):
                    result = smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True, ram_mib=ram)
                command = spawn.call_args.args[0]
                self.assertEqual(command[command.index('-m') + 1], str(ram))
                self.assertEqual(result['vm_ram_mib'], ram)
                self.assertEqual(json.loads((root / 'low-ram-idle.json').read_text())['vm_ram_mib'], ram)
                self.assertFalse((root / 'desktop-idle.json').exists(), 'Ana 2 GiB kanıtı ile karışmamalı')
                serial.write_text('oom-kill: constraint=CONSTRAINT_NONE\n' + uart)
                with patch.object(smoke.subprocess, 'Popen', return_value=process), self.assertRaisesRegex(RuntimeError, 'OOM'):
                    smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True, ram_mib=ram)
        with patch.object(smoke.subprocess, 'Popen') as spawn, self.assertRaises(ValueError):
            smoke.boot_os(Path('/unused'), 'bios', Path('/unused'), Path('/unused'), 'abc', ram_mib=256)
        spawn.assert_not_called()

    def test_pre_userspace_kernel_panic_fails_immediately_without_waiting_for_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            serial = root / 'target-os-bios.serial.log'
            serial.write_text('gunzip\nunpack_to_rootfs\nKernel panic - not syncing: System is deadlocked on memory\n')
            process = Mock()
            process.poll.return_value = None
            with patch.object(smoke.subprocess, 'Popen', return_value=process), patch.object(smoke.time, 'sleep') as pause:
                with self.assertRaisesRegex(RuntimeError, '512 MiB erken çekirdek paniği'):
                    smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True, ram_mib=512)
            pause.assert_not_called()
            process.terminate.assert_called_once()
            self.assertFalse((root / 'low-ram-idle.json').exists())

    def test_512_failure_keeps_1024_test_and_fails_whole_gate_without_hiding_either_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = []
            success = {'vm_ram_mib': 1024, 'valid_idle_measurement': True}
            with patch.object(smoke, 'boot_os', side_effect=[RuntimeError('512 initramfs OOM'), success]) as boot:
                with self.assertRaisesRegex(RuntimeError, '512 initramfs OOM'):
                    smoke.check_low_ram(root / 'private.img', root, root, 'abc', results)
            self.assertEqual([call.kwargs['ram_mib'] for call in boot.call_args_list], [512, 1024])
            self.assertEqual(results[1], success)
            self.assertFalse(results[0]['valid_idle_measurement'])
            self.assertEqual(json.loads((root / 'ram-512/low-ram-boot-error.json').read_text())['error'], '512 initramfs OOM')
            self.assertFalse((root / 'ram-1024/low-ram-boot-error.json').exists())

    def test_low_ram_budget_needs_actual_headroom_not_just_the_600_mb_number(self):
        total = 480 * 1024**2
        threshold = (total + 9) // 10
        samples = [{'total_bytes': total, 'available_bytes': threshold} for _ in range(6)]
        measurement = {'samples': samples, 'target_met': True, 'valid_idle_measurement': True}
        budget = smoke.low_ram_budget(measurement, 512)
        self.assertTrue(budget['passed'])
        self.assertEqual(budget['minimum_available_bytes'], threshold)
        samples[-1]['available_bytes'] -= 1
        budget = smoke.low_ram_budget(measurement, 512)
        self.assertFalse(budget['passed'])
        self.assertIn('payı yetersiz', budget['fail_reasons'][0])

    def test_low_ram_budget_refuses_missing_or_other_vm_data_and_above_target_idle(self):
        base = {'samples': [{'total_bytes': 960 * 1024**2, 'available_bytes': 500 * 1024**2} for _ in range(6)],
                'target_met': True, 'valid_idle_measurement': True}
        self.assertTrue(smoke.low_ram_budget(base, 1024)['passed'])
        for change in ({'target_met': False}, {'valid_idle_measurement': False}, {'samples': []},
                       {'samples': [{'total_bytes': 10, 'available_bytes': 9}] * 6},
                       {'samples': [{'total_bytes': 960 * 1024**2, 'available_bytes': True}] * 6},
                       {'samples': [{'total_bytes': 960 * 1024**2}] * 6},
                       {'samples': base['samples'][:5]}):
            with self.subTest(change=change):
                self.assertFalse(smoke.low_ram_budget({**base, **change}, 1024)['passed'])
        self.assertFalse(smoke.low_ram_budget(base, 512)['passed'], 'Farklı RAM VM örnekleri kanıt sayılamaz.')
        with self.assertRaises(ValueError):
            smoke.low_ram_budget(base, 2048)

    def test_uart_does_not_parse_partial_graphical_json_before_the_record_is_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            serial = root / 'target-os-bios.serial.log'
            prefix = 'OGUZDOWS-TARGET-OS-OK:abc\nOGUZDOWS-DESKTOP-IDLE-JSON:'
            serial.write_text(prefix + '{"samples":')
            process = Mock()
            process.poll.return_value = None
            measurement = {'samples': [{'graphical_xfce': True}], 'target_met': False}
            def finish_uart(_delay):
                serial.write_text(prefix + json.dumps(measurement) + '\r\n')
            with patch.object(smoke.subprocess, 'Popen', return_value=process), patch.object(smoke.time, 'sleep', side_effect=finish_uart) as pause, patch('builtins.print'):
                smoke.boot_os(root / 'private.img', 'bios', root, root, 'abc', graphical_idle=True)
            pause.assert_called_once()

    def test_unknown_checkout_cleanliness_is_not_called_clean_or_confused_with_known_dirty(self):
        build = {'source_revision': 'a' * 40, 'arch': 'i386', 'source_dirty': False}
        smoke.validate_source(build, 'a' * 40, 'i386')
        build['source_dirty'] = None
        with patch('builtins.print') as notice:
            smoke.validate_source(build, 'a' * 40, 'i386')
        self.assertIn('belirlenemedi (null)', notice.call_args.args[0])
        self.assertIsNone(build['source_dirty'])
        for change in ({'source_dirty': True}, {'source_dirty': 0}, {'source_dirty': 'false'},
                       {'source_revision': 'unknown'}, {'source_revision': 'b' * 40}, {'arch': 'amd64'}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                smoke.validate_source({**build, **change}, 'a' * 40, 'i386')
        build.pop('source_dirty')
        with self.assertRaises(RuntimeError):
            smoke.validate_source(build, 'a' * 40, 'i386')

    def test_real_iso_must_contain_architecture_matching_mount_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'etc/calamares/modules/mount.conf'
            path.parent.mkdir(parents=True)
            for arch, relative in (('amd64', 'installer/overrides/trixie/mount.conf'), ('i386', 'installer/modules/mount.conf')):
                text = (ROOT / relative).read_text()
                path.write_text(text)
                self.assertEqual(smoke.iso_mount_configuration(root, arch), yaml.safe_load(text))
                self.assertEqual(path.read_text(), text)
                other = 'i386' if arch == 'amd64' else 'amd64'
                with self.assertRaisesRegex(RuntimeError, 'mount.conf'):
                    smoke.iso_mount_configuration(root, other)
            path.unlink()
            with self.assertRaises(ValueError):
                smoke.iso_mount_configuration(root, 'amd64')

    def test_ci_uuid_link_only_names_its_own_loop_and_never_overwrites_existing_devices(self):
        uuid = '12345678-1234-1234-1234-123456789abc'
        device = '/dev/loop12345p1'
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'is_block_device', return_value=True):
            base = Path(directory) / 'uuid'
            owned = smoke.expose_loop_uuid(device, uuid, base)
            self.assertEqual(os.readlink(owned[0]), device)
            self.assertIsNone(smoke.expose_loop_uuid(device, uuid, base))
            smoke.remove_owned_uuid_links([owned])
            self.assertFalse(owned[0].is_symlink())
            owned = smoke.expose_loop_uuid(device, uuid, base)
            owned[0].unlink()
            owned[0].symlink_to('/dev/loop12346p1')
            with self.assertRaisesRegex(RuntimeError, 'başka bir aygıta'):
                smoke.expose_loop_uuid(device, uuid, base)
            smoke.remove_owned_uuid_links([owned])
            self.assertEqual(os.readlink(owned[0]), '/dev/loop12346p1')
        for device_value, uuid_value in (('/dev/sda1', uuid), ('/dev/loop1', uuid), (device, '../escape')):
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory) / 'must-not-exist'
                with self.assertRaises(RuntimeError):
                    smoke.expose_loop_uuid(device_value, uuid_value, base)
                self.assertFalse(base.exists())
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'is_block_device', return_value=False):
            base = Path(directory) / 'must-not-exist'
            with self.assertRaises(RuntimeError):
                smoke.expose_loop_uuid(device, uuid, base)
            self.assertFalse(base.exists())

    def test_real_iso_package_and_diversion_evidence_is_recorded_read_only(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as result:
            root, output = Path(directory), Path(result)
            (root / 'var/lib/dpkg').mkdir(parents=True)
            (root / 'usr/sbin').mkdir(parents=True)
            status = root / 'var/lib/dpkg/status'
            status.write_text('Package: live-tools\nVersion: 1:fixture\nStatus: install ok installed\n\nPackage: unrelated\nVersion: 2\n')
            diversion = root / 'var/lib/dpkg/diversions'
            diversion.write_text('/usr/sbin/update-initramfs\n/usr/sbin/update-initramfs.orig\nlive-tools\n')
            (root / 'usr/sbin/update-initramfs').write_text('# fixture wrapper\n')
            with patch('builtins.print'):
                smoke.record_live_state(root, output, 'before')
            report = json.loads((output / 'target-live-before.json').read_text())
            self.assertEqual(report['packages'], [{'Package': 'live-tools', 'Version': '1:fixture', 'Status': 'install ok installed'}])
            self.assertIn('live-tools', report['diversions'])
            self.assertEqual((output / 'before-update-initramfs.txt').read_text(), '# fixture wrapper\n')
            self.assertEqual(status.read_text().count('Package:'), 2)
            self.assertTrue(diversion.exists())

    def test_diagnostics_relays_actual_six_samples_read_only_without_raw_process_details(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        steps = workflow['jobs']['diagnostics']['steps']
        script = next(step['run'] for step in steps if 'run' in step)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'target-evidence/amd64'
            root.mkdir(parents=True)
            target = root / 'target-os-result.json'
            initramfs = {'6.12.fixture': {'size': '190000000', 'mtime_ns': '1234'}}
            target.write_text(json.dumps({'arch': 'amd64', 'source_revision': 'a' * 40,
                                          'initramfs': initramfs, 'error': 'long failure\\%\n' * 300}))
            serial = root / 'target-os-bios.serial.log'
            serial.write_text('PRIVATE-NOT-RELAYED\n[1] Memory: 123K\n[2] Kernel panic - not syncing: memory\n')
            sample = {'used_bytes': 650_000_000, 'graphical_xfce': True, 'desktop_user': 1000,
                      'desktop_processes': ['xfce4-panel', 'xfce4-session', 'xfdesktop', 'xfwm4'],
                      'known_foreground_or_package_work': [], 'cpu_total_ticks': 1000, 'cpu_idle_ticks': 990,
                      'top_processes_rss_not_system_total': [{'name': 'PRIVATE-NOT-RELAYED'}],
                      'zram': [{'allocated_ram_bytes': 12345}]}
            measurement = {'build': {'arch': 'amd64', 'source_revision': 'a' * 40},
                           'method': 'MemTotal − MemAvailable', 'target_bytes': 600_000_000,
                           'settled_seconds': 120, 'sample_count': 6, 'sample_interval_seconds': 5,
                           'idle_confirmed_by_operator': True, 'valid_idle_measurement': True,
                           'max_used_bytes': 650_000_000, 'target_met': False, 'samples': [sample] * 6}
            path = root / 'desktop-idle.json'
            original = json.dumps(measurement).encode()
            path.write_bytes(original)
            result = subprocess.run(['bash', '-c', script], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            target_prefix = '::notice title=Önceki hedef sistem kanıtı::'
            target_note = next(line for line in result.stdout.splitlines() if line.startswith(target_prefix))
            target_data = json.loads(target_note[len(target_prefix):].replace('%25', '%'))
            self.assertEqual(target_data['initramfs'], initramfs)
            self.assertEqual(target_data['report_sha256'], hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(len(target_data['error_tail']), 1400)
            memory_prefix = 'Önceki erken açılış belleği: '
            memory_note = next(line for line in result.stdout.splitlines() if line.startswith(memory_prefix))
            self.assertEqual(json.loads(memory_note[len(memory_prefix):])['boot_memory_lines'],
                             ['[1] Memory: 123K', '[2] Kernel panic - not syncing: memory'])
            prefix = '::notice title=Önceki tam Xfce RAM örnekleri::'
            annotation = next(line for line in result.stdout.splitlines() if line.startswith(prefix))
            self.assertLess(len(annotation), 4096)
            relayed = json.loads(annotation[len(prefix):])
            self.assertFalse(relayed['target_met'])
            self.assertEqual(relayed['report_sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(len(relayed['samples']), 6)
            self.assertTrue(all(item['used_bytes'] == 650_000_000 for item in relayed['samples']))
            self.assertEqual(relayed['zram'], sample['zram'])
            self.assertNotIn('PRIVATE-NOT-RELAYED', result.stdout)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(list(Path(directory).glob('*.iso')))

    def test_iso_artifact_is_gated_by_new_real_os_check_and_failure_evidence_is_kept(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        build = workflow['jobs']['build']
        steps = build['steps']
        build_index = next(i for i, s in enumerate(steps) if 'bash build.sh' in s.get('run', ''))
        os_index = next(i for i, s in enumerate(steps) if 'tests/smoke-iso-target.py' in s.get('run', ''))
        upload_index = next(i for i, s in enumerate(steps) if s.get('with', {}).get('name') == 'OguzDows-${{ matrix.arch }}')
        self.assertLess(build_index, os_index)
        self.assertLess(os_index, upload_index)
        self.assertNotIn('continue-on-error', steps[os_index])
        self.assertNotIn('if', steps[upload_index])  # Varsayılan success() zorunlu.
        self.assertIn('--expected-revision "$GITHUB_SHA"', steps[os_index]['run'])
        evidence = next(s for s in steps if s.get('with', {}).get('name') == 'OguzDows-ISO-hedef-test-${{ matrix.arch }}')
        self.assertEqual(evidence['if'], 'always()')
        self.assertEqual(build['container']['options'], '--privileged')
        for name in ('verify', 'installed-boot', 'build'):
            self.assertIn("target != 'pc-diagnostics'", workflow['jobs'][name]['if'])
        diagnostics = workflow['jobs']['diagnostics']
        self.assertIn("target == 'pc-diagnostics'", diagnostics['if'])
        self.assertEqual(diagnostics['permissions']['actions'], 'read')
        self.assertNotIn('bash build.sh', str(diagnostics))
        self.assertTrue(any(s.get('uses', '').startswith('actions/download-artifact@') for s in diagnostics['steps']))
        checkout_index = next(i for i, s in enumerate(steps) if s.get('uses', '').startswith('actions/checkout@'))
        self.assertIn('git ca-certificates', steps[checkout_index - 1]['run'])
        self.assertEqual((ROOT / 'build.yml').read_text(), (ROOT / '.github/workflows/main.yml').read_text())


if __name__ == '__main__':
    unittest.main()
