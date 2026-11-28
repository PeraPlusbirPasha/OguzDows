"""ARM-only draft transfer/audit negatives; synthetic files, NOT image acceptance."""
import io
import json
import lzma
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

from support import ROOT, load
import test_release_all_assets as all_tests
from test_release_all_assets import REVISION, REPOSITORY

arm = load('arm_refresh_release_test', 'scripts/release-arm-refresh.py')


class ArmRefreshTests(unittest.TestCase):
    def fixture(self, root):
        inputs = all_tests.AllReleaseAssetsTests().fixture(root)
        for arch in arm.base.PI_ARCHES:
            proof = inputs / 'evidence' / ('OguzDows-Pi-gunluk-' + arch)
            path = proof / 'pi-runtime-report.json'
            report = json.loads(path.read_text())
            report.update(feature_presence={'asset_hashes': 75}, full_session={'appearance': {'settings_backend_mocked': False}})
            path.write_text(json.dumps(report) + '\n')
            collection = json.loads((proof / 'collection.json').read_text())
            collection['logs'][0]['copied_bytes'] = path.stat().st_size
            (proof / 'collection.json').write_text(json.dumps(collection))
        return inputs

    def prepare(self, root):
        # Only mount/contract inspection is replaced here. Real checksum,
        # lock, upstream, APT and collector validation still executes.
        contract = {'schema': 1, 'appearance_runtime_schema': 1, 'asset_hashes': {'test-only': 'a' * 64}}
        def identity(_image, arch, revision, version, _work, _report, *, expected_contract):
            self.assertEqual(expected_contract, contract)
            self.assertEqual(version, '2.0')
            return {'version': version, 'build': {'arch': arch, 'source_revision': revision, 'source_dirty': False},
                    'uncompressed_bytes': 100, 'uncompressed_sha256': 'a' * 64}
        with patch.object(arm, 'source_contract', return_value=contract), \
                patch.object(arm.base, 'inspect_pi', side_effect=identity), patch('sys.stdout', io.StringIO()):
            return arm.prepare(root / 'input', root / 'output', repository=REPOSITORY, run_id=123,
                               release_id=456, revision=REVISION, publisher_revision='b' * 40,
                               notes='TEST ONLY ARM notes', artifacts={})

    def test_new_11_asset_release_has_two_new_sources_not_fabricated_pc_mobile_or_old_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = self.fixture(root)
            expected = self.prepare(root)
            self.assertEqual(set(expected), arm.NAMES)
            self.assertEqual(len(expected), 11)
            manifest = arm.base.read_json(root / 'output/release-manifest.json')
            self.assertEqual(manifest['tag'], 'v2.0-arm1')
            self.assertEqual(manifest['product_version'], '2.0')
            self.assertEqual(manifest['source_revision'], REVISION)
            self.assertNotEqual(manifest['source_revision'], manifest['previous_release']['source_revision'])
            self.assertFalse(manifest['pc_rebuilt'])
            self.assertFalse(manifest['mobile_rebuilt'])
            self.assertFalse(manifest['previous_release']['assets_modified'])
            self.assertEqual(set(manifest['evidence_files']), arm.EVIDENCE)
            self.assertEqual(len(manifest['evidence_files']), 13)
            for arch in arm.base.PI_ARCHES:
                name = f'OguzDows-rpi-{arch}.img.xz'
                self.assertEqual((root / 'output' / name).stat().st_ino, (inputs / ('rpi-' + arch) / name).stat().st_ino)
            self.assertEqual(len((root / 'output/SHA256SUMS').read_text().splitlines()), 2)
            self.assertNotIn('release-manifest.json', manifest['files'])

    def test_publisher_allowlist_cannot_hide_recipe_source_lock_or_target_smoke_changes(self):
        arm.validate_changes(['docs/index.html', 'docs/releases/v2.0-arm1.md', 'website/build.py',
                              '.github/workflows/main.yml', 'scripts/release-arm-refresh.py',
                              'scripts/release-assets.py', 'tests/test_release_arm_refresh.py', 'README.md'])
        for path in ('system/usr/lib/oguzdows/wallpapers.py', 'scripts/configure-pi.py',
                     'scripts/verify-pi.py', 'scripts/pi_session_smoke.py', 'scripts/pi-runtime-smoke.py',
                     'raspberrypi/feature-contract.json', 'raspberrypi/pi-gen.lock.json',
                     'packages/raspberrypi.list', 'build-pi.sh'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                arm.validate_changes([path])

    def test_source_contract_recreates_75_exact_current_asset_hashes_for_both_arches(self):
        for arch in arm.base.PI_ARCHES:
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                contract = arm.source_contract(arch, REVISION, Path(directory) / 'config')
                self.assertEqual(contract['appearance_runtime_schema'], 1)
                self.assertEqual(contract['source_revision'], REVISION)
                self.assertEqual(len(contract['asset_hashes']), 75)
                self.assertEqual(contract['asset_hashes']['usr/lib/oguzdows/wallpapers.py'],
                                 arm.base.sha256(ROOT / 'system/usr/lib/oguzdows/wallpapers.py'))

    def test_manifest_rejects_old_tag_source_missing_arch_or_inflated_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.prepare(root)
            good = arm.base.read_json(root / 'output/release-manifest.json')
            for change in ({'tag': 'v2.0'}, {'product_version': '2.0-arm1'}, {'source_revision': 'c' * 40},
                           {'pc_rebuilt': True}, {'mobile_rebuilt': True}, {'physical_boot': True},
                           {'images_repacked_by_publisher': True}, {'images_built_in_source_run': False},
                           {'files': {}}, {'files': None}, {'evidence_files': {}}, {'image_identity': {}},
                           {'publisher_revision': None}, {'schema': True}, {'previous_release': {}}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    arm.validate_manifest({**good, **change}, repository=REPOSITORY, run_id=123, release_id=456, revision=REVISION)

    def test_independent_audit_rehashes_all_downloads_and_repeats_inspection_without_release_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            expected = self.prepare(root)
            output = root / 'output'
            manifest = arm.base.read_json(output / 'release-manifest.json')
            release = {'id': 456, 'draft': True, 'tag_name': arm.TAG, 'target_commitish': REVISION,
                       'body': 'TEST ONLY ARM notes', 'assets': [dict(name=name, state='uploaded', size=row['size'], digest='sha256:' + row['sha256'])
                                                              for name, row in expected.items()]}
            def command(*args):
                if args[:3] == ('gh', 'release', 'download'):
                    shutil.copytree(output, Path(args[-1]))
                return ''
            with patch.object(arm.base, 'command', side_effect=command) as called, \
                    patch.object(arm.base, 'api', return_value=release), \
                    patch.object(arm, 'inspect', return_value=manifest['image_identity']) as inspect, \
                    patch.object(arm.base, 'prepare_pi', wraps=arm.base.prepare_pi) as validate, patch('sys.stdout', io.StringIO()):
                arm.audit_release(release, root / 'audit', repository=REPOSITORY, run_id=123,
                                  release_id=456, revision=REVISION, notes='TEST ONLY ARM notes', artifacts={})
            validate.assert_called_once()
            inspect.assert_called_once()
            self.assertTrue(inspect.call_args.kwargs['audit'])
            for call in called.call_args_list:
                self.assertNotIn('upload', call.args)
                self.assertNotIn('edit', call.args)
                self.assertNotIn('delete', call.args)
            self.assertEqual(arm.base.inventory(output), expected)

    def test_archive_rejects_mismatched_hash_missing_duplicate_symlink_or_escaping_member(self):
        for kind in ('hash', 'missing', 'duplicate', 'symlink', 'escape'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original = root / 'original.json'
                original.write_text('{"test-only":true}\n')
                record = {'size': original.stat().st_size, 'sha256': arm.base.sha256(original)}
                expected = {name: dict(record) for name in arm.EVIDENCE}
                archive = root / 'evidence.tar.gz'
                names = sorted(arm.EVIDENCE)
                if kind == 'missing': names.pop()
                if kind == 'duplicate': names.append(names[0])
                if kind == 'escape': names[0] = '../escape.json'
                with tarfile.open(archive, 'w:gz') as output:
                    for index, name in enumerate(names):
                        info = tarfile.TarInfo(name)
                        if kind == 'symlink' and index == 0:
                            info.type, info.linkname = tarfile.SYMTYPE, '/etc/shadow'
                            output.addfile(info)
                        else:
                            content = original.read_bytes()
                            info.size = len(content)
                            output.addfile(info, io.BytesIO(content))
                if kind == 'hash': expected[sorted(arm.EVIDENCE)[0]]['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    arm.unpack_evidence(archive, root / 'unpack', expected)
                self.assertFalse((root / 'escape.json').exists())

    def test_readonly_image_inspector_requires_the_exact_source_contract_not_only_self_reported_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'not-a-disk.img.xz'
            image.write_bytes(lzma.compress(b'TEST ONLY, no real partitions'))
            build = {'arch': 'armhf', 'source_revision': REVISION, 'source_dirty': False}
            def command(*args):
                if args[0] == 'sfdisk': return json.dumps({'partitiontable': {}})
                if args[:2] == ('sudo', 'losetup') and '--find' in args: return '/dev/loop42\n'
                if args[:2] == ('sudo', 'mount') and args[-1].endswith('/root'):
                    mounted = Path(args[-1])
                    path = mounted / 'usr/share/oguzdows'
                    path.mkdir(parents=True)
                    (path / 'build-info.json').write_text(json.dumps(build))
                    (path / 'pi-contract.json').write_text('{"appearance_runtime_schema":0}')
                    (mounted / 'boot/firmware').mkdir(parents=True)
                return ''
            with patch.object(arm.base, 'command', side_effect=command) as called, \
                    patch.object(arm.base, 'validate_partitions'), self.assertRaisesRegex(ValueError, 'kaynak baytlarıyla'):
                arm.base.inspect_pi(image, 'armhf', REVISION, '2.0', root, {}, expected_contract={'appearance_runtime_schema': 1})
            self.assertTrue(any(call.args[:2] == ('sudo', 'umount') for call in called.call_args_list))
            self.assertFalse(any(call.args[0] == 'chroot' for call in called.call_args_list))

    def test_dispatch_skips_all_pc_builds_and_audit_has_read_only_contents_permission(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        jobs = workflow['jobs']
        for name in ('verify', 'installed-boot', 'build'):
            self.assertIn("target != 'arm-release'", jobs[name]['if'])
        self.assertEqual(jobs['arm-release']['permissions']['contents'], 'write')
        self.assertEqual(jobs['arm-release-audit']['permissions']['contents'], 'read')
        audit_script = '\n'.join(step.get('run', '') for step in jobs['arm-release-audit']['steps'])
        self.assertIn('release-arm-refresh.py --audit', audit_script)
        for job in ('arm-release', 'arm-release-audit'):
            text = '\n'.join(step.get('run', '') for step in jobs[job]['steps'])
            self.assertNotIn('build-pi.sh', text)
            self.assertNotIn('--clobber', text)
            self.assertNotIn('gh release edit', text)


if __name__ == '__main__':
    unittest.main()
