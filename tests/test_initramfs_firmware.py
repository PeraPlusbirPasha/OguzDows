"""Geçici initramfs firmware kopyası; bu testler sistem firmware'ine dokunmaz."""
import hashlib
import lzma
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load

firmware = load('pc_initramfs_firmware', 'pc/initramfs-firmware.py')


def put(root, relative, data=b'unchanged'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def fixture(root):
    put(root, 'init')
    (root / 'scripts').mkdir()
    config = put(root, 'boot/config-fixture', b'CONFIG_FW_LOADER_COMPRESS=y\nCONFIG_FW_LOADER_COMPRESS_XZ=y\n')
    (root / 'lib').symlink_to('usr/lib')
    return config


class InitramfsFirmwareTests(unittest.TestCase):
    def test_graphics_remain_byte_identical_on_demand_and_unrelated_features_stay_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = fixture(root)
            raw = b'GPU firmware payload\x00\xff' * 16000
            paths = [put(root, f'usr/lib/firmware/{driver}/device.bin', raw) for driver in sorted(firmware.GRAPHICS)]
            untouched = [put(root, name, raw) for name in (
                'usr/lib/firmware/intel-ucode/06-8e-0a', 'usr/lib/firmware/amd-ucode/microcode_amd.bin',
                'usr/lib/firmware/brcm/wifi.bin', 'usr/lib/firmware/rtl_nic/network.fw',
                'usr/lib/firmware/regulatory.db', 'usr/lib/modules/fixture/kernel/drivers/ata/ata_piix.ko',
                'usr/lib/modules/fixture/kernel/drivers/gpu/drm/i915/i915.ko',
                'scripts/local-top/cryptroot', 'usr/share/plymouth/themes/oguzdows/logo.png')]
            details = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in untouched}
            paths[0].chmod(0o640)
            os.utime(paths[0], ns=(123000000000, 456000000000))
            report = firmware.optimize(root, 'fixture', config)
            self.assertTrue(report['kernel_support_verified'])
            self.assertEqual(len(report['converted']), len(paths))
            self.assertGreater(report['saved_unpacked_bytes'], len(raw) * len(paths) * .90)
            self.assertEqual(report['firmware_regular_bytes_after'],
                             report['firmware_regular_bytes_before'] - report['saved_unpacked_bytes'])
            for path in paths:
                self.assertFalse(path.exists())
                encoded = path.with_name(path.name + '.xz')
                encoded_bytes = encoded.read_bytes()
                decoder = lzma.LZMADecompressor()
                self.assertEqual(decoder.decompress(encoded_bytes), raw)
                self.assertEqual(decoder.check, lzma.CHECK_CRC32)
                item = next(item for item in report['converted'] if root / item['path'] == path)
                self.assertEqual(item['sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(item['raw_bytes'], len(raw))
                self.assertEqual(item['compressed_bytes'], len(encoded_bytes))
            self.assertEqual(paths[0].with_name(paths[0].name + '.xz').stat().st_mode & 0o777, 0o640)
            self.assertEqual(paths[0].with_name(paths[0].name + '.xz').stat().st_mtime_ns, 456000000000)
            for path in untouched:
                self.assertEqual((path.stat().st_mtime_ns, path.read_bytes()), details[path])
            again = firmware.optimize(root, 'fixture', config)
            self.assertEqual(again['converted'], [])
            self.assertEqual(again['saved_unpacked_bytes'], 0)
            self.assertFalse(list(root.rglob('.oguzdows-fw-*')))

    def test_relative_absolute_chained_and_directory_aliases_keep_kernel_xz_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = fixture(root)
            raw = b'GPU\x00' * 20000
            path = put(root, 'usr/lib/firmware/amdgpu/main.bin', raw)
            gpu = path.parent
            (gpu / 'alias.bin').symlink_to('main.bin')
            (gpu / 'chain.bin').symlink_to('alias.bin')
            (gpu / 'absolute.bin').symlink_to('/lib/firmware/amdgpu/main.bin')
            outside = root / 'usr/lib/firmware/radeon'
            outside.mkdir()
            (outside / 'cross.bin').symlink_to('../amdgpu/chain.bin')
            (gpu.parent / 'directory-alias').symlink_to('amdgpu')
            report = firmware.optimize(root, 'fixture', config)
            self.assertEqual(report['renamed_aliases'], 4)
            for name in ('amdgpu/main.bin', 'amdgpu/alias.bin', 'amdgpu/chain.bin',
                         'amdgpu/absolute.bin', 'radeon/cross.bin', 'directory-alias/alias.bin'):
                logical = gpu.parent / name
                self.assertFalse(logical.exists())
                # Aynı mantıksal firmware isteği; .xz son ekini çekirdek seçer.
                with lzma.open(str(logical) + '.xz') as stream:
                    self.assertEqual(stream.read(), raw)
            self.assertTrue((gpu.parent / 'directory-alias').is_symlink())
            self.assertEqual(len(report['converted'][0]['aliases']), 4)

    def test_unknown_or_disabled_kernel_support_cannot_remove_a_firmware_file(self):
        for config_text in (b'', b'# CONFIG_FW_LOADER_COMPRESS_XZ is not set\n',
                            b'CONFIG_FW_LOADER_COMPRESS_XZ=y\n', b'CONFIG_FW_LOADER_COMPRESS=y\n'):
            with self.subTest(config=config_text), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = fixture(root)
                config.write_bytes(config_text)
                path = put(root, 'usr/lib/firmware/amdgpu/main.bin', b'A' * 100000)
                with patch.object(firmware, 'compress_copy') as compressor:
                    report = firmware.optimize(root, 'fixture', config)
                compressor.assert_not_called()
                self.assertFalse(report['kernel_support_verified'])
                self.assertIn('skip_reason', report)
                self.assertEqual(path.read_bytes(), b'A' * 100000)

    def test_existing_encoded_variants_including_aliases_are_never_overwritten(self):
        for suffix in ('.xz', '.zst'):
            for alias_conflict in (False, True):
                with self.subTest(suffix=suffix, alias=alias_conflict), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    config = fixture(root)
                    source = put(root, 'usr/lib/firmware/amdgpu/main.bin', b'A' * 100000)
                    alias = source.with_name('alias.bin')
                    alias.symlink_to(source.name)
                    conflict = alias if alias_conflict else source
                    encoded = put(root, str(conflict.relative_to(root)) + suffix, b'existing-variant')
                    with patch.object(firmware, 'compress_copy') as compressor:
                        report = firmware.optimize(root, 'fixture', config)
                    compressor.assert_not_called()
                    self.assertEqual(report['converted'], [])
                    self.assertTrue(alias.is_symlink())
                    self.assertEqual(encoded.read_bytes(), b'existing-variant')
                    self.assertEqual(source.read_bytes(), b'A' * 100000)

    def test_already_compressed_small_incompressible_and_hardlinked_payloads_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = fixture(root)
            paths = [put(root, name, payload) for name, payload in (
                ('usr/lib/firmware/amdgpu/small.bin', b'A' * 100),
                ('usr/lib/firmware/amdgpu/already.bin.xz', b'compressed' * 1000),
                ('usr/lib/firmware/amdgpu/already.bin.zst', b'compressed' * 1000),
                ('usr/lib/firmware/amdgpu/random.bin', os.urandom(16000)),
                ('usr/lib/firmware/amdgpu/hardlink.bin', b'A' * 100000))]
            os.link(paths[-1], paths[-1].with_name('same-inode.bin'))
            before = {path: path.read_bytes() for path in paths}
            report = firmware.optimize(root, 'fixture', config)
            self.assertEqual(report['converted'], [])
            for path in paths:
                self.assertEqual(path.read_bytes(), before[path])
            self.assertFalse(list(root.rglob('.oguzdows-fw-*')))

    def test_bad_compression_keeps_original_and_cleans_only_owned_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = put(root, 'firmware.bin', b'A' * 100000)
            unrelated = put(root, '.oguzdows-fw-unrelated', b'do not remove')
            with patch.object(firmware, 'digest', return_value=('wrong', 100000)):
                with self.assertRaisesRegex(ValueError, 'eşleşmedi'):
                    firmware.compress_copy(path)
            self.assertEqual(path.read_bytes(), b'A' * 100000)
            self.assertFalse(path.with_name('firmware.bin.xz').exists())
            self.assertEqual(list(root.glob('.oguzdows-fw-*')), [unrelated])

    def test_real_root_relative_roots_invalid_version_and_escaped_links_are_rejected(self):
        for root in (Path('/'), Path('relative')):
            with self.subTest(root=root), self.assertRaises(ValueError):
                firmware.optimize(root, 'fixture', Path('/nonexistent'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                firmware.optimize(root, 'fixture', Path('/nonexistent'))
            config = fixture(root)
            source = put(root, 'usr/lib/firmware/amdgpu/main.bin', b'A' * 100000)
            with self.assertRaises(ValueError):
                firmware.optimize(root, '../bad-version', config)
            (source.parent / 'unsafe.bin').symlink_to('../../../../../../outside')
            with self.assertRaisesRegex(ValueError, 'dışına'):
                firmware.optimize(root, 'fixture', config)
            self.assertEqual(source.read_bytes(), b'A' * 100000)
            self.assertFalse(source.with_name('main.bin.xz').exists())

    def test_hook_prerequisites_and_non_amd64_exit_without_reading_host_or_copying_modules(self):
        hook = ROOT / 'pc/initramfs-tools/hooks/oguzdows-firmware'
        for args, env in ((['prereqs'], {}), ([], {'DPKG_ARCH': 'armhf'}),
                          ([], {'DPKG_ARCH': 'i386'}), ([], {'DPKG_ARCH': 'arm64'})):
            with self.subTest(args=args, env=env):
                child = subprocess.run(['/bin/sh', str(hook), *args], env=env, capture_output=True, text=True)
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertEqual(child.stdout, '')
        text = hook.read_text()
        self.assertLess(text.index('apply_add_modules\n'), text.index('exec /usr/bin/python3 -I'))
        self.assertNotIn('MODULES=dep', text)
        self.assertNotIn('rm ', text)


if __name__ == '__main__':
    unittest.main()
