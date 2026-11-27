"""Dört imajın yeniden derlenmeden, kaynak/hash doğrulamalı yayın aktarımı."""
import contextlib
import copy
import hashlib
import io
import json
import lzma
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from support import ROOT, load
import test_release_assets as pc_tests
from test_release_assets import REPOSITORY, BRANCH

release = load('all_release_assets_test', 'scripts/release-assets.py')
REVISION = '29f7738534cd00bd87887f530355ef45e01eb28c'


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')


class AllReleaseAssetsTests(unittest.TestCase):
    def fixture(self, root):
        inputs = pc_tests.ReleaseAssetsTests().fixture(root)
        for arch in release.ARCHES:
            proof = inputs / 'evidence' / ('OguzDows-ISO-hedef-test-' + arch)
            result = json.loads((proof / 'target-os-result.json').read_text())
            result.update(source_revision=REVISION, build={'arch': arch, 'source_revision': REVISION, 'source_dirty': None})
            write_json(proof / 'target-os-result.json', result)
            memory = json.loads((proof / 'desktop-idle.json').read_text())
            memory['build']['source_revision'] = REVISION
            write_json(proof / 'desktop-idle.json', memory)
            for ram in (512, 1024):
                measurement = copy.deepcopy(memory)
                measurement['vm_ram_mib'] = ram
                for sample in measurement['samples']:
                    sample['total_bytes'] = ram * 1024**2
                    sample['available_bytes'] = sample['total_bytes'] - sample['used_bytes']
                measurement['low_ram_budget'] = {
                    'passed': True, 'fail_reasons': [],
                    'minimum_available_bytes': max(32 * 1024**2, (ram * 1024**2 + 9) // 10),
                    'observed_min_available_bytes': ram * 1024**2 - 450_000_000}
                write_json(proof / f'ram-{ram}/low-ram-idle.json', measurement)
        lock = json.loads((ROOT / 'raspberrypi/pi-gen.lock.json').read_text())
        upstream = json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text())
        for arch in release.PI_ARCHES:
            directory = inputs / ('rpi-' + arch)
            directory.mkdir()
            name = f'OguzDows-rpi-{arch}.img.xz'
            content = lzma.compress(b'Unchanged synthetic image; not a boot test. ' + arch.encode())
            (directory / name).write_bytes(content)
            (directory / (name + '.sha256')).write_text(hashlib.sha256(content).hexdigest() + '  ' + name + '\n')
            (directory / f'OguzDows-rpi-{arch}.packages.txt').write_text('synthetic-package\t1\n')
            write_json(directory / 'raspberrypi/pi-gen.lock.json', lock)
            proof = inputs / 'evidence' / ('OguzDows-Pi-gunluk-' + arch)
            runtime = {'arch': arch, 'source_revision': REVISION, 'pi_gen_commit': lock[arch]['commit'],
                       'scope': 'ARM-qemu-user-with-host-Xvfb', 'errors': [],
                       'physical_boot': False, 'hardware_gpu': False, 'performance_measurement': False,
                       'real_package_transactions': False, 'real_audio_playback': False}
            audit = {'arch': arch, 'pi_gen_commit': lock[arch]['commit'], 'errors': [], 'physical_boot': False,
                     'archive_sha256': lock[arch]['archive_sha256'], 'files': upstream['architectures'][arch]['files']}
            apt = {'arch': arch, 'pi_gen_commit': lock[arch]['commit'], 'signature_checks_disabled': False,
                   'before_sha256': upstream['architectures'][arch]['files']['stage0/00-configure-apt/files/sources.list'],
                   'apt_config_sha256': release.sha256(ROOT / 'raspberrypi/apt/80oguzdows-resilience'),
                   'mirror_list_sha256': release.sha256(ROOT / 'raspberrypi/apt/raspbian.mirrors')}
            records = []
            for name, value in [('pi-runtime-report', runtime), ('pi-upstream-audit', audit), ('pi-apt-adaptation', apt)]:
                path = proof / (name + '.json')
                write_json(path, value)
                records.append({'file': path.name, 'status': 'copied', 'truncated': False, 'copied_bytes': path.stat().st_size})
            write_json(proof / 'collection.json', {'arch': arch, 'recursive_rootfs_scan': False,
                                                   'source_permissions_changed': False, 'logs': records})
        return inputs

    def identities(self, inputs):
        result = {arch: {'build': release.read_json(inputs / 'evidence' / ('OguzDows-ISO-hedef-test-' + arch)
                                                  / 'target-os-result.json')['build'], 'version': '1.1'}
                  for arch in release.ARCHES}
        result.update({'rpi-' + arch: {'build': {'source_revision': REVISION, 'arch': arch}, 'version': '1.1'}
                       for arch in release.PI_ARCHES})
        return result

    def prepare(self, root, *, identities=None):
        with patch.object(release, 'inspect_images', return_value=identities or self.identities(root / 'input')) as inspect:
            result = release.prepare(root / 'input', root / 'output', repository=REPOSITORY, run_id=123,
                                     pi_run_id=789, release_id=456, revision=REVISION,
                                     publisher_revision='b' * 40, tag='v1.1')
            inspect.assert_called_once()
            return result

    def test_four_images_original_checksums_packages_locks_and_raw_evidence_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = self.fixture(root)
            files = self.prepare(root)
            self.assertEqual(len(files), 17)
            manifest = release.read_json(root / 'output/release-manifest.json')
            self.assertEqual(manifest['format'], 2)
            self.assertEqual(manifest['source_revision'], REVISION)
            self.assertEqual(manifest['pi_source_run_id'], 789)
            self.assertEqual(manifest['source_run_id'], 123)
            self.assertFalse(manifest['images_rebuilt'])
            self.assertNotIn('release-manifest.json', manifest['files'])
            self.assertEqual(len((root / 'output/SHA256SUMS').read_text().splitlines()), 4)
            for arch in release.PI_ARCHES:
                name = f'OguzDows-rpi-{arch}.img.xz'
                original = inputs / ('rpi-' + arch) / name
                self.assertEqual((root / 'output' / name).stat().st_ino, original.stat().st_ino)
                self.assertEqual((root / 'output' / (name + '.sha256')).read_bytes(), original.with_name(name + '.sha256').read_bytes())
            with tarfile.open(root / 'output/test-evidence.tar.gz', 'r:gz') as archive:
                self.assertEqual(len(archive.getnames()), 21)
                self.assertTrue(all(member.isfile() and '/' not in member.name for member in archive.getmembers()))
                with archive.extractfile('pi-runtime-report-armhf.json') as stream:
                    self.assertEqual(stream.read(), (inputs / 'evidence/OguzDows-Pi-gunluk-armhf/pi-runtime-report.json').read_bytes())
            self.assertEqual((root / 'output/INDIRME-REHBERI.md').read_bytes(), (ROOT / 'docs/releases/v1.1.md').read_bytes())

    def test_host_evidence_is_version_scoped_and_old_published_evidence_is_not_reused(self):
        self.assertEqual(release.host_evidence('v1.1', REVISION), ROOT / 'docs/releases/v1.1-elementary-host.json')
        with tempfile.TemporaryDirectory() as directory, patch.object(release, 'ROOT', Path(directory)):
            root = Path(directory)
            old = root / 'docs/releases/v1.1-elementary-host.json'
            write_json(old, {'source_revision': REVISION, 'conclusion': 'success'})
            with self.assertRaises(ValueError):
                release.host_evidence('v1.2', REVISION)
            current = root / 'docs/releases/v1.2-host.json'
            write_json(current, {'source_revision': REVISION, 'conclusion': 'success'})
            self.assertEqual(release.host_evidence('v1.2', REVISION), current)
            for changed in ({'source_revision': 'c' * 40}, {'conclusion': 'failure'}):
                write_json(current, {'source_revision': REVISION, 'conclusion': 'success', **changed})
                with self.assertRaises(ValueError):
                    release.host_evidence('v1.2', REVISION)
            for tag in ('../v1.2', '1.2', 'v1.2/../../x'):
                with self.assertRaises(ValueError):
                    release.host_evidence(tag, REVISION)
            self.assertEqual(release.read_json(old), {'source_revision': REVISION, 'conclusion': 'success'})

    def test_pi_checksum_lock_source_arch_and_unperformed_physical_claim_fail_closed(self):
        cases = [('rpi-armhf/OguzDows-rpi-armhf.img.xz.sha256', None, None),
                 ('rpi-armhf/raspberrypi/pi-gen.lock.json', 'suite', 'wrong'),
                 ('evidence/OguzDows-Pi-gunluk-armhf/pi-runtime-report.json', 'source_revision', 'c' * 40),
                 ('evidence/OguzDows-Pi-gunluk-armhf/pi-runtime-report.json', 'arch', 'arm64'),
                 ('evidence/OguzDows-Pi-gunluk-armhf/pi-runtime-report.json', 'physical_boot', True),
                 ('evidence/OguzDows-Pi-gunluk-armhf/pi-upstream-audit.json', 'files', {}),
                 ('evidence/OguzDows-Pi-gunluk-armhf/pi-apt-adaptation.json', 'signature_checks_disabled', True),
                 ('evidence/OguzDows-Pi-gunluk-armhf/collection.json', 'logs', [])]
        for name, field, value in cases:
            with self.subTest(name=name, field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.fixture(root) / name
                if field:
                    data = release.read_json(path)
                    data[field] = value
                    write_json(path, data)
                else:
                    path.write_text('0' * 64 + '  OguzDows-rpi-armhf.img.xz\n')
                with self.assertRaises(ValueError), patch.object(release, 'inspect_images') as inspect:
                    release.prepare(root / 'input', root / 'output', repository=REPOSITORY, run_id=123,
                                    pi_run_id=789, release_id=456, revision=REVISION, publisher_revision='b' * 40, tag='v1.1')
                inspect.assert_not_called()

    def test_low_ram_budget_is_recomputed_not_merely_trusted(self):
        for field, value in [('vm_ram_mib', 1024), ('low_ram_budget', {'passed': True}),
                             ('samples', []), ('target_met', False)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.fixture(root) / 'evidence/OguzDows-ISO-hedef-test-amd64/ram-512/low-ram-idle.json'
                data = release.read_json(path)
                data[field] = value
                with self.assertRaises(ValueError):
                    release.validate_memory(data, 'amd64', REVISION, 512)
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory)) / 'evidence/OguzDows-ISO-hedef-test-amd64/ram-512/low-ram-idle.json'
            data = release.read_json(path)
            data['low_ram_budget']['observed_min_available_bytes'] += 1
            with self.assertRaisesRegex(ValueError, 'yeniden hesaplama'):
                release.validate_memory(data, 'amd64', REVISION, 512)

    def test_actual_iso_identity_cannot_disagree_with_boot_report_or_be_missing(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                inputs = self.fixture(root)
                identities = self.identities(inputs)
                if missing:
                    del identities['rpi-arm64']
                else:
                    identities['amd64']['build'] = {'source_revision': 'c' * 40}
                with self.assertRaises(ValueError):
                    self.prepare(root, identities=identities)

    def test_embedded_identity_rejects_wrong_version_source_cpu_and_dirty_unknown_is_not_clean(self):
        build = {'arch': 'amd64', 'source_revision': REVISION, 'source_dirty': None}
        lsb = 'DISTRIB_ID=OguzDows\nDISTRIB_RELEASE=1.1\n'
        release.validate_identity(build, lsb, 'amd64', REVISION, '1.1')
        for changed in [{'arch': 'i386'}, {'source_revision': 'd' * 40}, {'source_dirty': True}, {'source_dirty': 0}]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                release.validate_identity({**build, **changed}, lsb, 'amd64', REVISION, '1.1')
        with self.assertRaises(ValueError):
            release.validate_identity(build, lsb.replace('1.1', '1.0'), 'amd64', REVISION, '1.1')
        with self.assertRaises(ValueError):
            release.validate_identity({'arch': 'amd64', 'source_revision': REVISION}, lsb, 'amd64', REVISION, '1.1')

    def test_release_1_2_refuses_to_relabel_old_1_1_pc_and_pi_images(self):
        for arch in (*release.ARCHES, *release.PI_ARCHES):
            pi = arch in release.PI_ARCHES
            build = {'arch': arch, 'source_revision': REVISION, 'source_dirty': None}
            old = ('NAME="OğuzDows"\nID=raspbian\nVERSION_ID="12"\nOGUZDOWS_VERSION_ID="1.1"\n' if pi
                   else 'DISTRIB_ID=OguzDows\nDISTRIB_RELEASE=1.1\n')
            with self.subTest(arch=arch), self.assertRaises(ValueError):
                release.validate_identity(build, old, arch, REVISION, '1.2', pi=pi)
            release.validate_identity(build, old.replace('1.1', '1.2'), arch, REVISION, '1.2', pi=pi)

    def test_pi_product_version_is_separate_from_technical_bookworm_12(self):
        build = {'arch': 'armhf', 'source_revision': REVISION, 'source_dirty': None}
        text = 'NAME="OğuzDows"\nID=raspbian\nVERSION_ID="12"\nOGUZDOWS_VERSION_ID="1.1"\n'
        release.validate_identity(build, text, 'armhf', REVISION, '1.1', pi=True)
        with self.assertRaises(ValueError):
            release.validate_identity(build, text.replace('OGUZDOWS_VERSION_ID="1.1"', 'OGUZDOWS_VERSION_ID="1.0"'),
                                      'armhf', REVISION, '1.1', pi=True)
        with self.assertRaises(ValueError):
            release.validate_identity(build, text.replace('OGUZDOWS_VERSION_ID="1.1"', ''), 'armhf', REVISION, '1.1', pi=True)

    def test_release_notes_cover_four_downloads_hardware_capacity_and_known_zero_issue(self):
        notes = (ROOT / 'docs/releases/v1.1.md').read_text()
        for name in ('OguzDows-amd64.iso', 'OguzDows-i386.iso', 'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-arm64.img.xz'):
            self.assertIn('/releases/download/v1.1/' + name + ')', notes)
            self.assertIn('/releases/download/v1.1/' + name + '.sha256)', notes)
        for needed in (REVISION, 'actions/runs/45170572813', 'actions/runs/45170576727',
                       '1 GiB', '2 GiB', '4 GiB', '512 MB', '12 GiB', '16 GB', 'Zero 2 W',
                       'i686/PAE', 'SSE2', 'ARMv6', 'Pi 5', '32 bit UEFI', 'Secure Boot',
                       'siyah ekran bildirimi çözülmüş değildir', 'LightDM/PAM', 'test-evidence.tar.gz',
                       'v1.0.0', '191,4', '271,5', 'yapay zekâ', 'fiziksel boot testi değildir'):
            self.assertIn(needed, notes)
        self.assertIsNotNone(release.TAG.fullmatch('v1.1'))

    def test_inspect_pc_uses_data_readers_only_and_cleans_squash_copy(self):
        build = {'arch': 'amd64', 'source_revision': REVISION, 'source_dirty': None}
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with patch.object(release, 'command', side_effect=['', json.dumps(build), 'DISTRIB_ID=OguzDows\nDISTRIB_RELEASE=1.1\n']) as command:
                result = release.inspect_pc(work / 'test.iso', 'amd64', REVISION, '1.1', work)
            self.assertEqual(result['build'], build)
            self.assertEqual(command.call_args_list[0].args[0], 'xorriso')
            self.assertEqual(command.call_args_list[1].args[:2], ('unsquashfs', '-cat'))
            self.assertFalse((work / 'amd64.squashfs').exists())

    def pi_inspection(self, root, *, runtime_mismatch=False, failed_unmount=False):
        image = root / 'image.img.xz'
        image.write_bytes(lzma.compress(b'not an actual disk'))
        runtime = {'source_revision': REVISION, 'errors': []}
        lock = release.read_json(ROOT / 'raspberrypi/pi-gen.lock.json')
        build = {'arch': 'armhf', 'source_revision': REVISION, 'source_dirty': None}
        def command(*args):
            if args[0] == 'sfdisk':
                return json.dumps({'partitiontable': {}})
            if args[:2] == ('sudo', 'losetup') and '--find' in args:
                return '/dev/loop42\n'
            if args[:2] == ('sudo', 'mount') and args[-1].endswith('/root'):
                mounted = Path(args[-1])
                write_json(mounted / 'usr/share/oguzdows/build-info.json', build)
                write_json(mounted / 'usr/share/oguzdows/pi-build-report.json', {} if runtime_mismatch else runtime)
                write_json(mounted / 'usr/share/oguzdows/pi-gen.lock.json', lock)
                write_json(mounted / 'etc/oguzdows/pi-image.json', build)
                (mounted / 'usr/lib').mkdir(parents=True, exist_ok=True)
                (mounted / 'usr/lib/os-release').write_text('NAME="OğuzDows"\nID=raspbian\nVERSION_ID=12\nOGUZDOWS_VERSION_ID="1.1"\n')
                (mounted / 'boot/firmware').mkdir(parents=True)
            if args[:2] == ('sudo', 'umount') and failed_unmount:
                raise subprocess.CalledProcessError(1, args, stderr='synthetic unmount failure')
            return ''
        with patch.object(release, 'command', side_effect=command) as called, patch.object(release, 'validate_partitions'):
            if failed_unmount:
                with patch.object(release.shutil, 'rmtree') as remove, self.assertRaises(subprocess.CalledProcessError):
                    release.inspect_pi(image, 'armhf', REVISION, '1.1', root, runtime)
                remove.assert_not_called()
            elif runtime_mismatch:
                with self.assertRaisesRegex(ValueError, 'imaj içi rapor'):
                    release.inspect_pi(image, 'armhf', REVISION, '1.1', root, runtime)
            else:
                result = release.inspect_pi(image, 'armhf', REVISION, '1.1', root, runtime)
                self.assertTrue(result['embedded_runtime_matches_raw_artifact'])
                self.assertEqual(result['uncompressed_bytes'], len(b'not an actual disk'))
            return called

    def test_pi_readonly_inspection_checks_embedded_report_and_existing_host_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            called = self.pi_inspection(Path(directory))
            mounts = [call.args for call in called.call_args_list if call.args[:2] == ('sudo', 'mount')]
            self.assertEqual(mounts[0][3], 'ro,noload,nodev,nosuid,noexec')
            self.assertEqual(mounts[1][3], 'ro,nodev,nosuid,noexec')
            self.assertTrue(any('scripts/verify-pi.py' in ' '.join(call.args) for call in called.call_args_list))
            self.assertFalse(any(call.args[0] == 'chroot' for call in called.call_args_list))
        with tempfile.TemporaryDirectory() as directory:
            self.pi_inspection(Path(directory), runtime_mismatch=True)

    def test_unmount_failure_never_recursively_removes_a_mounted_root(self):
        with tempfile.TemporaryDirectory() as directory:
            self.pi_inspection(Path(directory), failed_unmount=True)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(release, 'inspect_pc', return_value={}), \
                    patch.object(release, 'inspect_pi', side_effect=RuntimeError('mount not released')), \
                    patch.object(release.shutil, 'rmtree') as remove, self.assertRaises(RuntimeError):
                release.inspect_images(Path(directory) / 'input', REVISION, 'v1.1', {'armhf': {}})
            remove.assert_not_called()

    def test_mbr_alignment_overlap_and_out_of_image_boundaries_are_rejected(self):
        table = {'label': 'dos', 'sectorsize': 512, 'partitions': [
            {'start': 16384, 'size': 16384, 'type': 'c'}, {'start': 32768, 'size': 16384, 'type': '83'}]}
        release.validate_partitions(table, 49152 * 512)
        for changed in [{'label': 'gpt'}, {'sectorsize': 4096}, {'partitions': table['partitions'][:1]}]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                release.validate_partitions({**table, **changed}, 49152 * 512)
        for index, field, value in [(0, 'start', 1), (0, 'size', 32769), (1, 'size', 16385), (1, 'type', 'ef')]:
            data = copy.deepcopy(table)
            data['partitions'][index][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                release.validate_partitions(data, 49152 * 512)

    def test_evidence_bundle_is_flat_original_and_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'report.json'
            original.write_bytes(b'{"original": true}\n')
            for name in ('one.tar.gz', 'two.tar.gz'):
                release.deterministic_bundle({'report.json': original}, root / name)
            self.assertEqual((root / 'one.tar.gz').read_bytes(), (root / 'two.tar.gz').read_bytes())
            with self.assertRaises(ValueError):
                release.deterministic_bundle({'../escape.json': original}, root / 'unsafe.tar.gz')

    def test_pi_readme_only_exception_does_not_allow_recipe_lock_or_other_product_edits(self):
        release.validate_changes(['raspberrypi/README.md', 'scripts/release-assets.py', 'tests/test_release_all_assets.py'])
        for name in ('raspberrypi/pi-gen.lock.json', 'raspberrypi/stage/00-desktop/01-run.sh',
                     'raspberrypi/evil.md', 'scripts/verify-pi.py', 'packages/raspberrypi.list'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.validate_changes([name])

    def test_pi_run_and_artifact_must_be_successful_unexpired_unique_same_source(self):
        run = {'id': 789, 'status': 'completed', 'conclusion': 'success', 'repository': {'full_name': REPOSITORY},
               'head_repository': {'full_name': REPOSITORY}, 'head_branch': BRANCH,
               'path': '.github/workflows/raspberrypi.yml', 'head_sha': REVISION}
        self.assertEqual(release.validate_run(run, 789, REPOSITORY, BRANCH, pi=True), REVISION)
        with self.assertRaises(ValueError):
            release.validate_run(run, 789, REPOSITORY, BRANCH)
        for change in ({'status': 'in_progress'}, {'head_branch': 'main'}, {'conclusion': 'failure'}, {'path': '.github/workflows/unrelated.yml'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                release.validate_run({**run, **change}, 789, REPOSITORY, BRANCH, pi=True)
        artifact = {'id': 1, 'name': 'image', 'size_in_bytes': 20, 'digest': 'sha256:' + 'a' * 64,
                    'expired': False, 'workflow_run': {'id': 789, 'head_sha': REVISION}}
        release.validate_artifacts({'artifacts': [artifact]}, ['image'], 789, REVISION)
        for change in ({'expired': True}, {'digest': None}, {'workflow_run': {'id': 123, 'head_sha': REVISION}},
                       {'workflow_run': {'id': 789, 'head_sha': 'b' * 40}}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                release.validate_artifacts({'artifacts': [{**artifact, **change}]}, ['image'], 789, REVISION)
        with self.assertRaises(ValueError):
            release.validate_artifacts({'artifacts': [artifact, artifact]}, ['image'], 789, REVISION)

    def audit_fixture(self, root, *, corrupt=False, changed_remote=False):
        self.fixture(root)
        expected = self.prepare(root)
        draft = {'id': 456, 'draft': True, 'tag_name': 'v1.1', 'target_commitish': REVISION,
                 'body': (ROOT / 'docs/releases/v1.1.md').read_text(),
                 'assets': [{'name': name, 'size': data['size'], 'digest': 'sha256:' + data['sha256'], 'state': 'uploaded'}
                            for name, data in expected.items()]}
        def command(*args):
            if args[:3] == ('gh', 'release', 'download'):
                target = Path(args[args.index('--dir') + 1])
                target.mkdir(parents=True)
                pattern = args[args.index('--pattern') + 1]
                files = list((root / 'output').iterdir()) if pattern == '*' else [root / 'output' / pattern]
                for path in files:
                    (target / path.name).write_bytes(path.read_bytes())
                if pattern == '*' and corrupt:
                    (target / 'OguzDows-rpi-armhf.img.xz').write_bytes(b'corrupted transfer')
            elif args[:3] != ('git', 'merge-base', '--is-ancestor'):
                raise AssertionError('Beklenmeyen/yazma komutu: ' + repr(args))
            return ''
        current = copy.deepcopy(draft)
        if changed_remote:
            current['assets'][0]['digest'] = 'sha256:' + 'f' * 64
        output = io.StringIO()
        with patch.object(release, 'command', side_effect=command) as called, patch.object(release, 'api', return_value=current), \
                contextlib.redirect_stdout(output):
            result = release.audit_release(draft, root / 'audit', repository=REPOSITORY, run_id=123, pi_run_id=789,
                                           release_id=456, revision=REVISION, tag='v1.1', notes=draft['body'])
        return result, called, output.getvalue()

    def test_audit_redownloads_and_hashes_all_seventeen_assets_without_writing_release(self):
        with tempfile.TemporaryDirectory() as directory:
            result, called, output = self.audit_fixture(Path(directory))
            self.assertEqual(len(result), 17)
            self.assertEqual(sum(call.args[:3] == ('gh', 'release', 'download') for call in called.call_args_list), 2)
            self.assertNotIn('upload', str(called.call_args_list))
            notices = output.splitlines()
            self.assertEqual(len(notices), 8)  # GitHub'ın 10 notice/adım sınırının altında.
            self.assertTrue(all(len(line.split('::', 2)[-1]) <= 3500 for line in notices))
            decoded = [json.loads(line.split('::', 2)[-1]) for line in notices if 'Release doğrulanmış dosyalar' in line]
            self.assertEqual({row['name'] for batch in decoded for row in batch}, set(result))
            self.assertIn('"all_release_assets_redownloaded_and_hashed": true', output)

    def test_audit_rejects_corrupted_download_or_concurrent_remote_change(self):
        for options in ({'corrupt': True}, {'changed_remote': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                self.audit_fixture(Path(directory), **options)

    def test_ci_pi_input_is_optional_and_does_not_add_build_or_publish_permissions_elsewhere(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        on = workflow.get('on', workflow.get(True))
        self.assertEqual(on['workflow_dispatch']['inputs']['pi_evidence_run']['default'], '')
        job = workflow['jobs']['release']
        self.assertIn('${{ inputs.pi_evidence_run }}', str(job))
        self.assertIn('--pi-run', str(job))
        self.assertNotIn('build-pi.sh', str(job))
        self.assertNotIn('bash build.sh', str(job))
        self.assertEqual(job['permissions'], {'contents': 'write', 'actions': 'read'})
        source = (ROOT / 'scripts/release-assets.py').read_text()
        for forbidden in ("command('gh', 'release', 'edit'", "command('gh', 'release', 'create'", "'--clobber'", "command('gh', 'run', 'cancel'"):
            self.assertNotIn(forbidden, source)
        self.assertEqual((ROOT / 'build.yml').read_bytes(), (ROOT / '.github/workflows/main.yml').read_bytes())


if __name__ == '__main__':
    unittest.main()
