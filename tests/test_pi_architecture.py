"""Pi OS mimari sözleşmesi: özellik silmeden port / ABI / başsız GTK ortamı."""
import copy
import hashlib
import json
import os
import stat
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from support import ROOT, load

config = load('pi_arch_config', 'scripts/configure-pi.py')
identity = load('pi_os_identity', 'raspberrypi/system/usr/lib/oguzdows/pi-identity.py')
runtime = load('pi_abi_runtime', 'scripts/pi-runtime-smoke.py')
upstream = load('pi_official_contract', 'scripts/audit-pi-upstream.py')
data = load('pi_contract_reader', 'scripts/pi_contract.py')


def write(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    return path


def elf(expected, hard_float=True):
    data = bytearray(64)
    data[:4] = b'\x7fELF'
    data[4:6] = bytes((expected['elf_class'], 1))
    struct.pack_into('<H', data, 18, expected['elf_machine'])
    if expected['elf_machine'] == 40:
        struct.pack_into('<I', data, 36, 0x5000400 if hard_float else 0x5000200)
    return data


class PiIdentityTests(unittest.TestCase):
    def test_current_2_0_product_version_preserves_both_pi_base_identities(self):
        product = identity.read_release(ROOT / 'system/usr/share/oguzdows/os-release')
        self.assertEqual(product['VERSION_ID'], '2.0')
        for native_id in ('raspbian', 'debian'):
            with self.subTest(native_id=native_id), tempfile.TemporaryDirectory() as directory:
                base = {'ID': native_id, 'VERSION_ID': '12', 'VERSION_CODENAME': 'bookworm'}
                expected = {'os_id': native_id, 'base_version_id': '12', 'suite': 'bookworm'}
                path = write(Path(directory), 'os-release', identity.render(base, product, expected))
                result = identity.read_release(path)
                self.assertEqual(result['OGUZDOWS_VERSION_ID'], '2.0')
                self.assertEqual(result['PRETTY_NAME'], 'OğuzDows 2.0 · Akıncı')
                for key, value in base.items():
                    self.assertEqual(result[key], value)

    def test_product_name_does_not_replace_pi_os_native_id_version_or_suite(self):
        for native_id in ('raspbian', 'debian'):
            with self.subTest(native_id=native_id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                base = {'NAME': 'Upstream', 'ID': native_id, 'ID_LIKE': 'debian', 'VERSION_ID': '12',
                        'VERSION_CODENAME': 'bookworm', 'VERSION': '12 (bookworm)', 'VENDOR_EXTRA': 'koru'}
                product = {'NAME': 'OğuzDows', 'PRETTY_NAME': 'OğuzDows 1.1', 'ID': 'oguzdows',
                           'VERSION_ID': '1.1', 'VERSION_CODENAME': 'ayyildiz'}
                expected = {'os_id': native_id, 'base_version_id': '12', 'suite': 'bookworm'}
                result = identity.read_release(write(root, 'os-release', identity.render(base, product, expected)))
                for key in ('ID', 'ID_LIKE', 'VERSION_ID', 'VERSION_CODENAME', 'VERSION', 'VENDOR_EXTRA'):
                    self.assertEqual(result[key], base[key])
                self.assertEqual(result['NAME'], 'OğuzDows')
                self.assertEqual(result['OGUZDOWS_VERSION_ID'], '1.1')

    def test_identity_apply_is_atomic_idempotent_and_rejects_an_unreviewed_base(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = 'NAME=Upstream\nID=raspbian\nVERSION_ID="12"\nVERSION_CODENAME=bookworm\n'
            write(root, 'usr/lib/os-release.upstream', base)
            target = write(root, 'usr/lib/os-release', base)
            write(root, 'usr/share/oguzdows/os-release', 'NAME="OğuzDows"\nVERSION_ID="1.1"\nVERSION_CODENAME=ayyildiz\n')
            data = {'arch': 'armhf', 'suite': 'bookworm', 'architectures': {'armhf': {'os_id': 'raspbian', 'base_version_id': '12'}}}
            write(root, 'usr/share/oguzdows/pi-contract.json', json.dumps(data))
            self.assertTrue(identity.apply(root))
            before = target.read_bytes(), target.stat().st_mtime_ns
            self.assertFalse(identity.apply(root))
            self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), before)
            write(root, 'usr/lib/os-release.upstream', base.replace('bookworm', 'trixie'))
            with self.assertRaises(ValueError):
                identity.apply(root)
            self.assertEqual(target.read_bytes(), before[0])
            self.assertFalse(list(target.parent.glob('.oguzdows-identity-*')))

    def test_identity_parser_never_sources_shell_and_new_values_are_escaped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = write(root, 'untrusted', 'NAME=$(touch /should-not-run)\n')
            with self.assertRaises(ValueError):
                identity.read_release(path)
            base = {'ID': 'raspbian', 'VERSION_ID': '12', 'VERSION_CODENAME': 'bookworm'}
            expected = {'os_id': 'raspbian', 'base_version_id': '12', 'suite': 'bookworm'}
            product = {'NAME': 'OğuzDows $HOME `touch x`', 'VERSION_ID': '1.1', 'VERSION_CODENAME': 'ayyildiz'}
            text = identity.render(base, product, expected)
            self.assertIn('\\$HOME', text)
            self.assertIn('\\`touch x\\`', text)
            with patch.object(identity.os, 'geteuid', return_value=1000), patch.object(identity, 'apply') as apply:
                with patch('sys.argv', ['pi-identity']):
                    self.assertEqual(identity.main(), 2)
                apply.assert_not_called()


class PiAbiAndFeatureTests(unittest.TestCase):
    def test_both_minimum_abis_are_checked_without_using_host_instruction_flags(self):
        contract = json.loads((ROOT / 'raspberrypi/feature-contract.json').read_text())
        for arch in ('armhf', 'arm64'):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'native'
                expected = contract['architectures'][arch]
                path.write_bytes(elf(expected))
                self.assertEqual(runtime.elf_info(path, expected)['bits'], 32 if arch == 'armhf' else 64)
                other = contract['architectures']['arm64' if arch == 'armhf' else 'armhf']
                with self.assertRaises(ValueError):
                    runtime.elf_info(path, other)
                if arch == 'armhf':
                    path.write_bytes(elf(expected, hard_float=False))
                    with self.assertRaisesRegex(ValueError, 'hard-float'):
                        runtime.elf_info(path, expected)
        source = (ROOT / 'scripts/build-native.sh').read_text()
        for flag in ('-march=native', '-mcpu=native', '-mfpu=neon'):
            self.assertNotIn(flag, source)

    def test_version_gate_stays_strict_and_retains_the_actual_failure_output(self):
        valid = 'OğuzDows Mağaza · GTK 3.24.0'
        self.assertEqual(runtime.version_output('xfce4-session test\nEk bilgi', valid)['native_store_version'], valid)
        for xfce, native in (('', valid), ('xfce4-session test', 'O?uzDows Ma?aza ? GTK'), ('xfce4-session test', '')):
            with self.subTest(xfce=xfce, native=native), self.assertRaises(ValueError) as caught:
                runtime.version_output(xfce, native)
            self.assertIn(native, str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            runtime.version_output('x' * 5000, 'y' * 5000)
        self.assertLess(len(str(caught.exception)), 700)

    def test_foreign_extra_package_is_not_confused_with_native_or_all_packages(self):
        data = 'python3\tarm64\t3.11\tinstalled\npython3\tarmhf\t3.11\tinstalled\nfonts\tall\t1.0\tinstalled\n'
        result = runtime.package_versions(data, ['python3', 'fonts'], 'armhf')
        self.assertEqual(result['python3']['architecture'], 'armhf')
        for bad in ('python3\tarm64\t3.11\tinstalled\n', 'python3\tarmhf\t3.11\tconfig-files\n', 'bozuk'):
            with self.assertRaises(ValueError):
                runtime.package_versions(bad, ['python3'], 'armhf')

    def fixture(self, root):
        hashes = {}
        for name, content in (('usr/share/backgrounds/oguzdows/test.jpg', 'fotoğraf test verisi'),
                              ('usr/share/oguzdows/rifki/panel-test.wav', 'ses test verisi')):
            path = write(root, name, content)
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        write(root, 'usr/local/bin/welcome', 'test başlatıcısı')
        write(root, 'usr/share/oguzdows/test-preview.jpg', 'test önizlemesi')
        write(root, 'usr/share/oguzdows/wallpapers.json', json.dumps([{'path': '/usr/share/backgrounds/oguzdows/test.jpg', 'preview': '/usr/share/oguzdows/test-preview.jpg'}]))
        write(root, 'usr/share/oguzdows/rifki/speech.json', json.dumps({'test': 'panel-test.wav'}))
        return {'features': {'desktop': {'packages': ['xfce4'], 'files': ['usr/local/bin/welcome']}},
                'required_packages': ['xfce4'], 'asset_hashes': hashes, 'minimum_wallpapers': 1, 'minimum_selected_narration': 1}

    def test_presence_gate_checks_hashes_launchers_narration_and_wallpapers_not_just_counts(self):
        for change in ('none', 'launcher', 'sound', 'wallpaper', 'package', 'count', 'escape'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                contract = self.fixture(root)
                if change == 'launcher': (root / 'usr/local/bin/welcome').unlink()
                if change == 'sound': write(root, 'usr/share/oguzdows/rifki/speech.json', '{}')
                if change == 'wallpaper': write(root, 'usr/share/backgrounds/oguzdows/test.jpg', 'değişmiş')
                if change == 'package': contract['required_packages'] = []
                if change == 'count': contract['minimum_wallpapers'] = 20
                if change == 'escape': contract['features']['desktop']['files'] = ['../host']
                if change == 'none':
                    result = runtime.feature_presence(root, contract)
                    self.assertEqual(result['groups'], ['desktop'])
                    self.assertEqual(result['asset_hashes'], 2)
                else:
                    with self.assertRaises(ValueError): runtime.feature_presence(root, contract)

    def test_generated_contract_keeps_every_common_package_and_selected_asset_on_both_arms(self):
        common = {line.partition('#')[0].strip() for line in (ROOT / 'packages/common.list').read_text().splitlines()} - {''}
        for arch in ('armhf', 'arm64'):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'configuration'
                config.configure(arch, output)
                overlay = output / 'stage-oguzdows/00-desktop/files/overlay'
                contract = json.loads((overlay / 'usr/share/oguzdows/pi-contract.json').read_text())
                expected = common - ({'firefox-esr', 'firefox-esr-l10n-tr'} if arch == 'armhf' else set())
                self.assertTrue(expected.issubset(contract['required_packages']))
                if arch == 'armhf':
                    self.assertTrue({'firefox-esr', 'firefox-esr-l10n-tr'}.isdisjoint(contract['required_packages']))
                    self.assertIn('netsurf-gtk', contract['required_packages'])
                self.assertEqual(len(contract['asset_hashes']), 75)  # 69 existing + 6 exact appearance runtime / callback sources
                bridge_files = contract['features']['pc-phone-arm-bridge']['files']
                self.assertEqual(len(bridge_files), 8)
                for relative in bridge_files:
                    self.assertEqual(contract['asset_hashes'][relative], hashlib.sha256((overlay / relative).read_bytes()).hexdigest())
                self.assertIn('file_manager', contract['python_modules'])
                for relative in ('usr/lib/oguzdows/file_manager.py', 'usr/lib/oguzdows/render-assets.py',
                                 'usr/lib/oguzdows/wallpapers.py', 'usr/lib/oguzdows/desktop_runtime.py',
                                 'usr/lib/oguzdows/desktop_state.py', 'usr/lib/oguzdows/profiles.py',
                                 'usr/lib/oguzdows/welcome.py', 'usr/lib/oguzdows/desktop_center.py',
                                 'usr/share/oguzdows/ui/modern.css', 'usr/share/oguzdows/ui/window-geometry.css',
                                 'usr/share/oguzdows/compositor/full.conf'):
                    self.assertEqual(contract['asset_hashes'][relative], hashlib.sha256((overlay / relative).read_bytes()).hexdigest())
                self.assertNotIn('xvfb', contract['required_packages'])
                self.assertNotIn('xauth', contract['required_packages'])
                self.assertFalse((overlay / 'etc/lsb-release').exists())
                self.assertEqual(contract['arch'], arch)
                self.assertRegex(contract['source_revision'], r'^([0-9a-f]{40}|unknown)$')
                for name in contract['asset_hashes']:
                    self.assertTrue((overlay / name).is_file(), name)
                self.assertTrue((output / 'stage-oguzdows/00-desktop/files/pi-runtime-smoke.py').is_file())
                self.assertEqual((output / 'stage-oguzdows/00-desktop/files/pi-ci-cleanup.py').read_bytes(),
                                 (ROOT / 'scripts/pi-ci-cleanup.py').read_bytes())
                self.assertFalse((overlay / 'usr/lib/oguzdows/pi-ci-cleanup.py').exists())
                reader = (ROOT / 'scripts/pi_contract.py').read_bytes()
                self.assertEqual((overlay / 'usr/lib/oguzdows/pi_contract.py').read_bytes(), reader)
                self.assertEqual((output / 'stage-oguzdows/00-desktop/files/pi_contract.py').read_bytes(), reader)
                self.assertEqual(len(contract['features']), 13)
                self.assertIn('lightweight-news', contract['features'])
                self.assertIn('original-icons-and-budgeted-transitions', contract['features'])
                self.assertIn('flatpak', contract['required_packages']) if arch == 'arm64' else self.assertNotIn('flatpak', contract['required_packages'])


class PiUpstreamTests(unittest.TestCase):
    def test_reviewed_source_lock_is_tied_to_exact_archives_and_not_a_moving_branch(self):
        lock = config.LOCK
        contract = json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text())
        self.assertEqual(contract['suite'], lock['suite'])
        for arch in ('armhf', 'arm64'):
            for key in ('branch', 'commit', 'archive_sha256'):
                self.assertEqual(contract['architectures'][arch][key], lock[arch][key])
            self.assertGreaterEqual(len(contract['architectures'][arch]['files']), 12)
        source = (ROOT / 'build-pi.sh').read_text()
        self.assertLess(source.index('audit-pi-upstream.py'), source.index('./build.sh'))
        self.assertIn('"$(getconf PAGESIZE)" != 4096', source)
        self.assertIn('[ "$ARCH" = armhf ] &&', source)

    def test_changed_boot_defaults_or_unreviewed_lock_fail_before_an_expensive_build(self):
        for arch in ('armhf', 'arm64'):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                contract = copy.deepcopy(json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text()))
                text = '\n'.join(contract['preserved_boot_settings']) + ('\narm_64bit=1\n' if arch == 'arm64' else '\n')
                path = write(root, 'stage1/00-boot-files/files/config.txt', text)
                contract['architectures'][arch]['files'] = {'stage1/00-boot-files/files/config.txt': hashlib.sha256(path.read_bytes()).hexdigest()}
                self.assertEqual(upstream.audit(arch, root, config.LOCK, contract)['errors'], [])
                path.write_text(text.replace('camera_auto_detect=1', 'camera_auto_detect=0'))
                self.assertTrue(upstream.audit(arch, root, config.LOCK, contract)['errors'])
                path.write_text(text)
                lock = copy.deepcopy(config.LOCK)
                lock[arch]['commit'] = '0' * 40
                self.assertTrue(upstream.audit(arch, root, lock, contract)['errors'])

    def test_desktop_boot_never_waits_for_network_due_to_enable_also_order(self):
        source = (ROOT / 'raspberrypi/stage/00-desktop/files/configure-system.sh').read_text()
        self.assertLess(source.index('systemctl enable NetworkManager.service'), source.index('systemctl disable NetworkManager-wait-online.service'))
        self.assertNotIn('mask NetworkManager', source)
        self.assertIn('--no-rename --divert /usr/lib/os-release.upstream', source)
        self.assertIn('python3 /usr/lib/oguzdows/pi-identity.py', source)
        firstboot = load('pi_firstboot_parity', 'raspberrypi/system/usr/lib/oguzdows/pi-firstboot.py')
        self.assertTrue({'gpio', 'spi', 'i2c', 'video', 'render', 'cdrom', 'users', 'games'}.issubset(firstboot.GROUPS))


class PiGuiEnvironmentTests(unittest.TestCase):
    def test_real_bridge_shell_resets_host_runtime_and_bus_and_only_shares_x_socket(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / 'bin'
            tools.mkdir()
            mount = write(tools, 'mount', '#!/bin/sh\nprintf "%s\\n" "$@" > "$MOUNT_CAPTURE"\n')
            mount.chmod(0o755)
            captured = root / 'chroot-script'
            write(root, 'pi-gen/scripts/common', 'on_chroot() { [[ ":$SHELLOPTS:" != *:pipefail:* ]] || return 69; cat > "$CAPTURED"; }; export -f on_chroot\n')
            env = {**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'],
                   'BASE_DIR': str(root / 'pi-gen'),
                   'ROOTFS_DIR': str(root / 'target root'), 'DISPLAY': ':199', 'ARCH': 'armhf',
                   'OGUZDOWS_PI_CI_DIR': '/run/oguzdows-ci.Test123', 'OGUZDOWS_PI_CI_CPU': 'arm1176',
                   'XDG_RUNTIME_DIR': '/run/user/1001', 'DBUS_SESSION_BUS_ADDRESS': 'host-bus-DO-NOT-INHERIT',
                   'CAPTURED': str(captured), 'MOUNT_CAPTURE': str(root / 'mount.txt')}
            # Aynı /bin/sh sınırı: xvfb-run dışa aktarılmış Bash işlevini düşürür.
            command = ['/bin/sh', '-c', 'exec bash "$1"',
                       'sh', str(ROOT / 'raspberrypi/stage/00-desktop/files/pi-gui-chroot.sh')]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            script = captured.read_text()
            for text in ('/usr/bin/env -i', 'dbus-run-session', 'DISPLAY=":199"', 'XAUTHORITY="/run/oguzdows-ci.Test123/Xauthority"', 'XDG_RUNTIME_DIR="/run/oguzdows-ci.Test123"', 'QEMU_CPU="arm1176"'):
                self.assertIn(text, script)
            self.assertNotIn('/run/user/1001', script)
            self.assertNotIn('host-bus-DO-NOT-INHERIT', script)
            self.assertEqual((root / 'mount.txt').read_text().splitlines()[0:2], ['--bind', '/tmp/.X11-unix'])
            self.assertEqual(stat.S_IMODE((root / 'target root/tmp/.X11-unix').stat().st_mode), 0o1777)
            captured.unlink()
            env['DISPLAY'] = ':99; false'
            self.assertNotEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
            self.assertFalse(captured.exists())

    def test_private_display_is_a_host_build_tool_not_a_shipping_feature_removal(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/raspberrypi.yml').read_text())
        steps = workflow['jobs']['image']['steps']
        tools = next(step['run'] for step in steps if step.get('name') == 'Yerel pi-gen ve çapraz ARM çalıştırma araçları')
        self.assertIn('xvfb xauth', tools)
        self.assertTrue(any('--host-gui' in step.get('run', '') for step in workflow['jobs']['verify']['steps']))
        smoke = (ROOT / 'raspberrypi/stage/00-desktop/02-run.sh').read_text()
        self.assertIn('trap cleanup EXIT', smoke)
        self.assertIn('-nolisten tcp', smoke)
        self.assertNotIn(' -ac', smoke)
        self.assertIn('pi-runtime-report.json', smoke)
        self.assertLess(smoke.index("on_chroot <<'EOF'"), smoke.index('install -m 0755 "$emulator"'))
        native = (ROOT / 'native/store.c').read_text().split('int main(int argc, char **argv) {', 1)[1]
        self.assertLess(native.index('"--version"'), native.index('gtk_application_new'))


class PiContractReaderTests(unittest.TestCase):
    def test_outside_links_special_files_and_oversized_or_duplicate_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / 'image'
            root.mkdir()
            secret = write(parent, 'host/secret.json', '{"secret": "HOST VERİSİ"}')
            for kind in ('leaf', 'parent', 'fifo', 'loop'):
                with self.subTest(kind=kind):
                    path = root / kind
                    if kind == 'leaf': path.symlink_to(secret)
                    elif kind == 'parent': path.symlink_to(secret.parent, target_is_directory=True)
                    elif kind == 'loop': path.symlink_to(kind)
                    else: os.mkfifo(path)
                    relative = kind + ('/secret.json' if kind == 'parent' else '')
                    with self.assertRaises(ValueError) as caught:
                        data.read_json(root, relative)
                    self.assertNotIn('HOST VERİSİ', str(caught.exception))
            path = write(root, 'report.json', '{"schema": 1, "schema": 2}')
            with self.assertRaisesRegex(ValueError, 'tekrarlı'):
                data.read_json(root, 'report.json')
            path.write_text('x' * 33)
            with self.assertRaises(ValueError): data.read_bytes(root, 'report.json', maximum=32)
            for relative in ('../host/secret.json', str(secret), 'bad\x00name'):
                with self.assertRaises(ValueError): data.checked_path(root, relative)

    def test_internal_interpreter_links_are_read_as_data_not_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = {'elf_class': 2, 'elf_machine': 183}
            target = write(root, 'usr/bin/python3.11', '')
            target.write_bytes(elf(expected))
            (target.parent / 'python3').symlink_to('python3.11')
            self.assertEqual(data.elf_info(data.checked_path(root, 'usr/bin/python3'), expected)['bits'], 64)
            target.write_bytes(elf(expected)[:52])
            with self.assertRaises(ValueError):
                data.elf_info(data.checked_path(root, 'usr/bin/python3'), expected)

    def test_nested_feature_schema_cannot_turn_corrupt_manifests_into_presence(self):
        for change in ('packages', 'duplicate', 'groups', 'gallery', 'speech', 'preview'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                contract = PiAbiAndFeatureTests().fixture(root)
                if change == 'packages': contract['required_packages'] = 'xfce4'
                if change == 'duplicate': contract['required_packages'] = ['xfce4', 'xfce4']
                if change == 'groups': contract['features'] = []
                if change == 'gallery': write(root, 'usr/share/oguzdows/wallpapers.json', '{}')
                if change == 'speech': write(root, 'usr/share/oguzdows/rifki/speech.json', '{"test": []}')
                if change == 'preview':
                    path = root / 'usr/share/oguzdows/wallpapers.json'
                    gallery = json.loads(path.read_text())
                    gallery[0]['preview'] = '/../../host'
                    path.write_text(json.dumps(gallery))
                with self.assertRaises(ValueError): data.feature_presence(root, contract)


class PiGuiLifecycleTests(unittest.TestCase):
    def run_stage(self, root, smoke_status=0, unmount_fail=False, preexisting=False, create_report=True, cleanup_status=0):
        tools = root / 'bin'
        tools.mkdir()
        work = root / 'build'
        base = work / 'pi-gen'
        base.mkdir(parents=True)
        target = work / 'rootfs'
        write(target, 'run/user/1001/keep', 'host runtime benzeri işaret; silinmez')
        (target / 'tmp').mkdir()
        (target / 'usr/share/oguzdows').mkdir(parents=True)
        stage = root / 'desktop'
        write(stage, 'files/pi-runtime-smoke.py', '# yalnızca yaşam döngüsü test girdisi')
        write(stage, 'files/pi_session_smoke.py', '# yalnızca yaşam döngüsü test girdisi')
        write(stage, 'files/pi_contract.py', '# yalnızca yaşam döngüsü test girdisi')
        # Simulated cleanup command only; real chroot/pidfd regression has its
        # own privileged test, never silently substituted for ARM boot proof.
        write(stage, 'files/pi-ci-cleanup.py', '''
import json, os, sys
from pathlib import Path
runtime = Path(sys.argv[sys.argv.index('--runtime') + 1])
Path(os.environ['CLEANUP_CAPTURE']).write_text(json.dumps({
    'argv': sys.argv[1:], 'runtime_exists': runtime.is_dir(),
    'emulator_exists': (Path(os.environ['ROOTFS_DIR']) / 'tmp/oguzdows-qemu-static').exists(),
    'mounted': Path(os.environ['MOUNTED']).exists()}))
sys.exit(int(os.environ['CLEANUP_STATUS']))
''')
        write(tools, 'xauth', '#!/bin/sh\nexit 0\n').chmod(0o755)
        # /bin/sh, tıpkı gerçek xvfb-run gibi Bash işlevlerini aktarmaz.
        write(tools, 'xvfb-run', '''#!/bin/sh
set -eu
runtime="$ROOTFS_DIR$OGUZDOWS_PI_CI_DIR"
test -s "$runtime/smoke.py"
test -s "$runtime/pi_contract.py"
test "$(stat -c %a "$runtime")" = 700
test "$(stat -c %a "$runtime/home")" = 700
if [ "$CREATE_REPORT" = 1 ]; then
    printf '{"scope":"SIMULATED-lifecycle-only"}\\n' > "$runtime/report.json"
fi
: > "$MOUNTED"
exit "$SMOKE_STATUS"
''').chmod(0o755)
        wrapper = write(root, 'wrapper.sh', '''#!/bin/bash
set -euo pipefail
command() {
    if [ "$1" = -v ] && [[ "$2" = /usr/bin/qemu-*-static ]]; then return 0; fi
    builtin command "$@"
}
install() {
    if [[ "${@: -2:1}" = /usr/bin/qemu-*-static ]]; then
        printf 'SAHTE; ÇALIŞTIRILMAZ' > "${@: -1}"
    else
        builtin command install "$@"
    fi
}
on_chroot() {
    [[ ":$SHELLOPTS:" != *:pipefail:* ]] || return 69
    cat > /dev/null
}
mountpoint() { [ -f "$MOUNTED" ]; }
umount() {
    printf '%s\\n' "$@" > "$UNMOUNT_CAPTURE"
    if [ "$UNMOUNT_FAIL" = 1 ]; then return 64; fi
    rm -f "$MOUNTED"
}
export -f command install on_chroot mountpoint umount
exec bash "$1"
''')
        mounted = root / 'mounted'
        if preexisting: mounted.touch()
        env = {**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'],
               'BASE_DIR': str(base), 'ROOTFS_DIR': str(target), 'ARCH': 'armhf',
               'MOUNTED': str(mounted), 'UNMOUNT_CAPTURE': str(root / 'umount.txt'),
               'SMOKE_STATUS': str(smoke_status), 'UNMOUNT_FAIL': '1' if unmount_fail else '0',
               'CLEANUP_STATUS': str(cleanup_status), 'CLEANUP_CAPTURE': str(root / 'process-cleanup.json'),
               'CREATE_REPORT': '1' if create_report else '0'}
        result = subprocess.run(['bash', str(wrapper), str(ROOT / 'raspberrypi/stage/00-desktop/02-run.sh')],
                                cwd=stage, env=env, text=True, capture_output=True, timeout=10)
        return result, work, target

    def test_exit_cleanup_preserves_original_failure_and_reports_without_touching_other_runtime(self):
        for smoke_status, unmount_fail, expected in ((0, False, 0), (47, False, 47), (0, True, 1), (47, True, 47)):
            with self.subTest(smoke_status=smoke_status, unmount_fail=unmount_fail), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result, work, target = self.run_stage(root, smoke_status, unmount_fail)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads((work / 'pi-runtime-report.json').read_text())['scope'], 'SIMULATED-lifecycle-only')
                self.assertEqual(bool(list((target / 'run').glob('oguzdows-ci.*'))), unmount_fail)
                self.assertEqual((target / 'tmp/oguzdows-qemu-static').exists(), unmount_fail)
                self.assertTrue((target / 'run/user/1001/keep').exists())
                captured = json.loads((root / 'process-cleanup.json').read_text())
                self.assertTrue(captured['runtime_exists'] and captured['emulator_exists'] and captured['mounted'])
                self.assertEqual(captured['argv'][0:2], ['--rootfs', str(target)])
                self.assertEqual((root / 'umount.txt').read_text().strip(), str(target / 'tmp/.X11-unix'))
                self.assertEqual((target / 'usr/share/oguzdows/pi-build-report.json').exists(), smoke_status == 0)

    def test_process_cleanup_failure_preserves_runtime_and_original_exit_code(self):
        for smoke_status, expected in ((0, 1), (47, 47)):
            with self.subTest(smoke_status=smoke_status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result, work, target = self.run_stage(root, smoke_status, cleanup_status=55)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertTrue(list((target / 'run').glob('oguzdows-ci.*')))
                self.assertTrue((target / 'tmp/oguzdows-qemu-static').exists())
                self.assertTrue((target / 'run/user/1001/keep').exists())
                self.assertIn('private runtime/emulator preserved', result.stderr)
                self.assertTrue((work / 'pi-runtime-report.json').is_file())
                self.assertTrue((root / 'process-cleanup.json').is_file())

    def test_preexisting_mount_is_not_unmounted_and_missing_failure_receipt_is_not_invented(self):
        for preexisting, expected in ((True, 1), (False, 47)):
            with self.subTest(preexisting=preexisting), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result, work, target = self.run_stage(root, 47, preexisting=preexisting, create_report=False)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual((root / 'umount.txt').exists(), not preexisting)
                self.assertFalse((work / 'pi-runtime-report.json').exists())
                self.assertFalse((target / 'usr/share/oguzdows/pi-build-report.json').exists())
                self.assertFalse(list((target / 'run').glob('oguzdows-ci.*')))
                self.assertTrue((target / 'run/user/1001/keep').exists())


if __name__ == '__main__':
    unittest.main()
