"""Gerçek arşiv envanteri / manifest; RAM tasarrufunu boot kanıtı diye sunmaz."""
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import load

inventory = load('initramfs_inventory_tests', 'scripts/initramfs-report.py')
optimizer = load('initramfs_inventory_optimizer', 'pc/initramfs-firmware.py')


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def staged(root):
    stage = root / 'main'
    stage.mkdir()
    put(stage, 'init', b'#!/bin/sh\n')
    (stage / 'scripts').mkdir()
    config = put(root, 'kernel-config', b'CONFIG_FW_LOADER_COMPRESS=y\nCONFIG_FW_LOADER_COMPRESS_XZ=y\n')
    path = put(stage, 'usr/lib/firmware/amdgpu/main.bin', b'GPU firmware\x00' * 10000)
    path.with_name('alias.bin').symlink_to(path.name)
    put(stage, 'usr/lib/modules/fixture/kernel/drivers/ata/ata_piix.ko', b'module fixture' * 500)
    report = optimizer.optimize(stage, 'fixture', config)
    put(stage, inventory.MANIFEST, json.dumps(report).encode())
    return stage, report


class InitramfsReportTests(unittest.TestCase):
    def test_manifest_payload_hash_aliases_and_category_sizes_match_extracted_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unpacked = root / 'unpacked'
            unpacked.mkdir()
            stage, original = staged(unpacked)
            # kernel-config, kullanılan dış kernel yapılandırmasıdır; arşiv kökü değil.
            (unpacked / 'kernel-config').unlink()
            report, manifests = inventory.inspect_tree(unpacked)
            self.assertEqual(manifests, [original])
            self.assertEqual(report['firmware'][0]['payloads_verified'], 1)
            self.assertEqual(report['firmware'][0]['converted_files'], 1)
            expected = (stage / 'usr/lib/firmware/amdgpu/main.bin.xz').stat().st_size
            self.assertEqual(report['category_bytes']['firmware'], expected)
            self.assertEqual(report['category_bytes']['modules'], len(b'module fixture' * 500))
            self.assertEqual(report['regular_file_bytes'], sum(report['category_bytes'].values()))
            self.assertNotIn('converted', report['firmware'][0])

    def test_no_early_archive_uses_the_tools_flat_output_without_a_synthetic_main_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, _original = staged(root)
            (root / 'kernel-config').unlink()
            for path in stage.iterdir():
                shutil.move(path, root / path.name)
            stage.rmdir()
            report, _manifests = inventory.inspect_tree(root)
            self.assertEqual(report['extraction_layout'], 'flat')
            self.assertEqual(report['firmware'][0]['payloads_verified'], 1)
            self.assertEqual(report['category_bytes']['modules'], len(b'module fixture' * 500))

    def test_split_early_compressed_members_and_main_manifest_are_verified_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage, _original = staged(root)
            (root / 'kernel-config').unlink()
            early = root / 'early/usr/lib'
            early.mkdir(parents=True)
            shutil.move(stage / 'usr/lib/firmware', early / 'firmware')
            report, _manifests = inventory.inspect_tree(root)
            self.assertEqual(report['firmware'][0]['payloads_verified'], 1)
            self.assertTrue(any(item['path'].startswith('early/') for item in report['largest_files']))

    def test_corrupted_payload_lost_alias_and_reintroduced_raw_firmware_are_errors(self):
        for change in ('corrupt', 'alias', 'raw'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stage, _original = staged(root)
                (root / 'kernel-config').unlink()
                gpu = stage / 'usr/lib/firmware/amdgpu'
                if change == 'corrupt':
                    (gpu / 'main.bin.xz').write_bytes(b'corrupted')
                elif change == 'alias':
                    (gpu / 'alias.bin.xz').unlink()
                else:
                    (gpu / 'main.bin').write_bytes(b'raw reinjected by a late hook')
                with self.assertRaises(ValueError):
                    inventory.inspect_tree(root)

    def test_member_paths_do_not_read_outside_a_private_extracted_root(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'escape').symlink_to(outside)
            for relative in ('/etc/shadow', '../../etc/shadow', 'escape/secret'):
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    inventory.member(root, relative)
        with patch.object(inventory.subprocess, 'run') as child, self.assertRaises(ValueError):
            inventory.record(Path('/dev/null'), Path('/unused'))
        child.assert_not_called()

    @unittest.skipUnless(shutil.which('cpio') and shutil.which('unmkinitramfs'), 'Gerçek cpio / initramfs-tools yok; host CI iki tabanda çalıştırır.')
    def test_real_cpio_gzip_round_trip_preserves_payload_and_archive_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unpacked = root / 'source'
            unpacked.mkdir()
            stage, _original = staged(unpacked)
            names = ['.'] + [str(path.relative_to(stage)) for path in sorted(stage.rglob('*'))]
            cpio = subprocess.run(['cpio', '--null', '--quiet', '-o', '-H', 'newc', '--reproducible'],
                                  cwd=stage, input=('\0'.join(names) + '\0').encode(),
                                  capture_output=True, check=True)
            image = put(root, 'initrd.img-fixture', gzip.compress(cpio.stdout, mtime=0))
            before = image.read_bytes()
            report = inventory.record(image, root / 'evidence', root)
            self.assertEqual(report['archive_sha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual(report['archive_bytes'], len(before))
            self.assertEqual(report['firmware'][0]['payloads_verified'], 1)
            self.assertEqual(image.read_bytes(), before)
            self.assertTrue((root / 'evidence/initrd.img-fixture-inventory.json').is_file())
            self.assertTrue((root / 'evidence/initrd.img-fixture-firmware.json').is_file())
            self.assertFalse(list(root.glob('oguzdows-initrd-report-*')))


if __name__ == '__main__':
    unittest.main()
