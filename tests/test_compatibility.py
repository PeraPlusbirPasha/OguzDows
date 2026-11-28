import json
import os
import socket
import stat
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT, load

core = load('compat_core_test', 'system/usr/lib/oguzdows/compat_core.py')
devices = load('devices_test', 'system/usr/lib/oguzdows/device_support.py')
arm = load('arm_config_test', 'scripts/configure-arm.py')
maintenance = load('arm_store_maintenance_test', 'system/usr/lib/oguzdows/maintenance.py')


def pe(machine=0x8664, flags=2):
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', data, 68, machine, 1, 0, 0, 0, 112, flags)
    struct.pack_into('<H', data, 88, 0x10b if machine == 0x14c else 0x20b)
    return bytes(data)


def apk(path, names=None):
    with zipfile.ZipFile(path, 'w') as archive:
        for name in names or ('AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/test.so'):
            archive.writestr(name, b'small test fixture, not an executable application')


def caps(**overrides):
    return {'machine': 'x86_64', 'memory_kib': 4 * 1024**2, 'wine': True,
            'wine32': True, 'waydroid': True, 'wayland': True, 'binder': True, **overrides}


class InspectionTests(unittest.TestCase):
    def test_pe_and_apk_are_inspected_without_running_any_process(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(core.subprocess, 'run') as run:
            root = Path(temporary)
            path = root / "test with ' spaces.exe"
            path.write_bytes(pe())
            result = core.inspect(path)
            self.assertEqual(result['architecture'], 'x86_64')
            self.assertEqual(result['kind'], 'exe')
            self.assertEqual(len(result['sha256']), 64)
            self.assertEqual(result['size'], 512)
            path = root / 'test.apk'
            apk(path)
            result = core.inspect(path)
            self.assertEqual(result['abis'], ['arm64-v8a'])
            run.assert_not_called()

    def test_symlinks_fifos_dlls_unknown_headers_and_extensions_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'a.exe'
            target.write_bytes(pe())
            link = root / 'link.exe'
            link.symlink_to(target)
            with self.assertRaises(OSError):
                core.inspect(link)
            fifo = root / 'pipe.exe'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                core.inspect(fifo)
            for value in (b'not a PE', pe(flags=0x2000), pe(machine=1)):
                target.write_bytes(value)
                with self.assertRaises(ValueError):
                    core.inspect(target)
            with self.assertRaises(ValueError):
                core.inspect(root / 'command.desktop')

    def test_apk_paths_duplicate_entries_missing_manifest_and_huge_central_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'test.apk'
            for names in (('classes.dex',), ('AndroidManifest.xml', '../escape'),
                          ('AndroidManifest.xml', '/absolute'), ('AndroidManifest.xml', 'dir\\file')):
                apk(path, names)
                with self.assertRaises(ValueError):
                    core.inspect(path)
            apk(path)
            data = bytearray(path.read_bytes())
            offset = data.rfind(b'PK\x05\x06')
            struct.pack_into('<I', data, offset + 12, 9 * 1024**2)
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                core.inspect(path)

    def test_staging_rechecks_identity_and_hash_preserves_original_and_is_private(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(core.os, 'geteuid', return_value=1000):
            root = Path(temporary)
            path = root / 'original.exe'
            path.write_bytes(pe())
            receipt = core.inspect(path)
            copy = core.stage(receipt, root / 'inbox')
            self.assertEqual(copy.read_bytes(), path.read_bytes())
            self.assertEqual(stat.S_IMODE(copy.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(copy.parent.stat().st_mode), 0o700)
            self.assertTrue(path.exists())
            changed = dict(receipt, sha256='f' * 64)
            with self.assertRaises(ValueError):
                core.stage(changed, root / 'inbox')
            self.assertEqual(list((root / 'inbox').iterdir()), [copy])
            path.write_bytes(pe(machine=0x14c))
            with self.assertRaises(ValueError):
                core.stage(receipt, root / 'inbox')

    def test_root_is_never_allowed_to_stage_or_launch(self):
        with patch.object(core.os, 'geteuid', return_value=0):
            with self.assertRaises(ValueError):
                core.stage({}, Path('/never-create'))
            with self.assertRaises(ValueError):
                core.launch_plan({}, None, None, {})


class RuntimeTests(unittest.TestCase):
    def test_windows_pc_arch_and_real_32bit_runtime_required(self):
        receipt = {'kind': 'exe', 'architecture': 'x86', 'abis': []}
        self.assertFalse(core.availability(receipt, caps()))
        for value in (caps(machine='aarch64'), caps(wine=False), caps(wine32=False)):
            self.assertTrue(core.availability(receipt, value))
        receipt['architecture'] = 'x86_64'
        self.assertTrue(core.availability(receipt, caps(machine='i686')))
        receipt['architecture'] = 'arm64'
        self.assertTrue(core.availability(receipt, caps()))

    def test_apk_requires_all_device_conditions_native_abi_and_running_session(self):
        receipt = {'kind': 'apk', 'architecture': 'arm64-v8a', 'abis': ['arm64-v8a']}
        execute = Mock(return_value='Session:\tRUNNING\nContainer:\tRUNNING\n')
        self.assertFalse(core.availability(receipt, caps(machine='aarch64'), execute))
        execute.assert_called_once_with([core.WAYDROID, 'status'])
        for value in (caps(machine='armv6l'), caps(waydroid=False), caps(wayland=False),
                      caps(binder=False), caps(memory_kib=512000), caps(machine='x86_64')):
            execute.reset_mock()
            self.assertTrue(core.availability(receipt, value, execute))
            execute.assert_not_called()
        execute.return_value = 'Session: STOPPED\nContainer: RUNNING\n'
        self.assertTrue(core.availability(receipt, caps(machine='aarch64'), execute))

    def test_caps_require_a_real_user_wayland_socket_not_just_an_env_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'proc').mkdir()
            (root / 'proc/meminfo').write_text('MemTotal: 2097152 kB\n')
            runtime = root / 'runtime'
            runtime.mkdir()
            env = {'WAYLAND_DISPLAY': 'wayland-test', 'XDG_RUNTIME_DIR': str(runtime)}
            self.assertFalse(core.capabilities(root, 'aarch64', env)['wayland'])
            server = socket.socket(socket.AF_UNIX)
            try:
                server.bind(str(runtime / 'wayland-test'))
                self.assertTrue(core.capabilities(root, 'aarch64', env)['wayland'])
            finally:
                server.close()

    def test_launch_is_fixed_argv_and_separate_prefix_not_a_shell_or_root(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(core.os, 'geteuid', return_value=1000):
            root = Path(temporary)
            path = root / "name'; touch never.exe"
            path.write_bytes(pe())
            receipt = core.inspect(path)
            command, env, cwd = core.launch_plan(receipt, path, root, caps())
            self.assertEqual(command, [core.WINE, str(path)])
            self.assertIn('/wine/', env['WINEPREFIX'])
            self.assertEqual(env['WINEARCH'], 'win64')
            self.assertEqual(cwd, env['WINEPREFIX'])
            self.assertNotIn('LD_PRELOAD', env)
            receipt.update(kind='apk', architecture='arm64-v8a', abis=['arm64-v8a'])
            execute = Mock(return_value='Session: RUNNING\nContainer: RUNNING\n')
            command, env, cwd = core.launch_plan(receipt, path, root, caps(machine='aarch64'), execute)
            self.assertEqual(command[:3], [core.WAYDROID, 'app', 'install'])

    def test_mime_and_launcher_only_point_to_confirmation_gui(self):
        entry = (ROOT / 'system/usr/share/applications/oguzdows-compatibility.desktop').read_text()
        defaults = (ROOT / 'system/etc/skel/.config/mimeapps.list').read_text()
        self.assertIn('Exec=/usr/local/bin/oguzdows-open %f', entry)
        self.assertNotIn('Exec=wine', entry)
        self.assertIn('application/vnd.android.package-archive=oguzdows-compatibility.desktop', defaults)
        source = (ROOT / 'system/usr/lib/oguzdows/compatibility.py').read_text()
        self.assertIn('set_default_response(Gtk.ResponseType.CANCEL)', source)
        self.assertIn('self.ack.get_active()', source)
        self.assertNotIn('shell=True', source)
        self.assertNotIn('.kill(', source)


class DeviceProfileTests(unittest.TestCase):
    def test_unknown_arm_and_different_pinephones_are_never_silently_a_pi(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(devices.current(root, 'aarch64')['id'], 'unknown')
            path = root / 'sys/firmware/devicetree/base/model'
            path.parent.mkdir(parents=True)
            path.write_text('Pine64 PinePhone Pro\0')
            self.assertEqual(devices.current(root, 'aarch64')['id'], 'pinephone-pro')
            path.write_text('Pine64 PinePhone\0')
            self.assertEqual(devices.current(root, 'aarch64')['id'], 'pinephone')
            self.assertTrue(all(not item['physical_verified'] for item in devices.PROFILES.values()))
            with self.assertRaises(ValueError):
                devices.get('any-android-phone')

    def test_arm_layer_is_offline_device_specific_and_not_a_flashable_image(self):
        for identifier in devices.OVERLAY_PROFILES:
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'layer'
                arm.configure(identifier, output)
                overlay = output / 'overlay'
                info = json.loads((overlay / 'usr/share/oguzdows/build-info.json').read_text())
                self.assertEqual(info['device_profile'], identifier)
                self.assertEqual(info['arch'], 'arm64')
                self.assertIn('not-boot-image', info['status'])
                self.assertFalse((overlay / 'etc/default/grub').exists())
                self.assertFalse((overlay / 'usr/local/bin/oguzdows-install').exists())
                self.assertTrue((overlay / 'usr/local/bin/oguzdows-open').is_file())
                self.assertFalse((overlay / 'etc/apt/sources.list.d/oguzdows-pardus.sources').exists())
                self.assertIn('onboard', (output / 'packages.list').read_text() if identifier.startswith('pinephone') else 'onboard')
                self.assertIn('önyüklenebilir ISO', (output / 'OKU-BENI.md').read_text())
                with self.assertRaises(FileExistsError):
                    arm.configure(identifier, output)

    def test_arm_store_identity_does_not_open_general_pc_maintenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'info.json'
            for info in ({'platform': 'raspberrypi', 'arch': 'armhf', 'suite': 'bookworm'},
                         {'platform': 'raspberrypi', 'arch': 'arm64', 'suite': 'bookworm'},
                         {'platform': 'arm', 'arch': 'arm64', 'suite': 'trixie', 'device_profile': 'pinephone'}):
                path.write_text(json.dumps(info))
                self.assertEqual(maintenance.build_store_info(path), info)
                with self.assertRaises(ValueError):
                    maintenance.build_info(path)
                self.assertEqual(maintenance.request_packages('app:geany', info), ['geany'])
                with self.assertRaises(ValueError):
                    maintenance.request_packages('app:wine', info)
            for info in ({'platform': 'arm', 'arch': 'arm64', 'suite': 'trixie', 'device_profile': 'random'},
                         {'platform': 'raspberrypi', 'arch': 'arm64', 'suite': 'forky'}):
                path.write_text(json.dumps(info))
                with self.assertRaises(ValueError):
                    maintenance.build_store_info(path)


if __name__ == '__main__':
    unittest.main()
