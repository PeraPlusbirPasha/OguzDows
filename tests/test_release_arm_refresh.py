"""ARM-only draft transfer/audit negatives; synthetic files, NOT image acceptance."""
from datetime import datetime, timezone
import copy
import hashlib
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
    def locale_fixture(self, *, reproduced=True):
        # Structural input ONLY. No GNU catalogue, settings or ARM runs here.
        return {'schema': 1, 'environment': {'LANG': 'tr_TR.UTF-8', 'LANGUAGE': 'tr:en', 'LC_ALL': 'tr_TR.UTF-8'},
                'raw_turkish_header': 'Değer, 2 ögeden oluşan dizidir:',
                'unfixed_reader_error_reproduced': reproduced,
                'unfixed_reader_header': 'Değer, 4 ögeden oluşan dizidir:' if reproduced else 'Value is an array with 4 items:',
                'runners': ['profiles', 'desktop_runtime', 'wallpapers'], 'typed_arrays': ['int-array', 'double-array'],
                **dict.fromkeys(arm.LOCALE_TRUE, True), 'settings_backend_mocked': False}

    def native_fixture(self):
        # Synthetic structural receipt, NEVER saved as production acceptance.
        report = {'source_revision': REVISION, 'architecture': 'arm64',
                  'scope': 'private-nonroot-native-Xfce-Welcome-theme-wallpaper-and-root-pixels',
                  'runtime_sha256': {name: arm.base.sha256(ROOT / 'system/usr/lib/oguzdows' / name) for name in arm.NATIVE_RUNTIME},
                  'locale_probe_sha256': arm.base.sha256(ROOT / 'scripts/pi_session_smoke.py'),
                  'errors': [], 'synthetic_image_fixture': True,
                  **dict.fromkeys(('physical_pi', 'physical_gpu', 'performance_measurement', 'settings_backend_mocked'), False),
                  **dict.fromkeys(('welcome_theme_callbacks_and_GTK_reload', 'welcome_wallpaper_callbacks_and_real_pixels',
                                   'stale_connector_does_not_swallow_change', 'randr_failure_injected', 'fallback_real_gdk_helper_and_pixels'), True),
                  'profile_themes': dict.fromkeys(('oguzdows', 'kde', 'gnome', 'xfce', 'windows11', 'mac'), 'TEST ONLY'),
                  'fixture-red_root_rgb': [160, 30, 40], 'fixture-blue_root_rgb': [30, 60, 160],
                  'dark_theme': 'TEST ONLY dark', 'light_theme': 'TEST ONLY light'}
        return {'schema': 1, 'scope': 'native-ARM64-Turkish-Xfce-Welcome-and-real-pixels-not-physical-Pi',
                'acceptance': {'source_revision': REVISION, 'conclusion': 'success', 'run_id': 123,
                               'results': [{'suite': suite, 'conclusion': 'success', 'job_id': index,
                                            'report': {**report, 'xfconf_locale': self.locale_fixture(reproduced=suite == 'bookworm')}}
                                           for index, suite in enumerate(('bookworm', 'trixie'), start=1)]}}

    def fixture(self, root):
        inputs = all_tests.AllReleaseAssetsTests().fixture(root)
        for arch in arm.base.PI_ARCHES:
            proof = inputs / 'evidence' / ('OguzDows-Pi-gunluk-' + arch)
            path = proof / 'pi-runtime-report.json'
            report = json.loads(path.read_text())
            report.update(feature_presence={'asset_hashes': 75}, full_session={'appearance': {
                'settings_backend_mocked': False, 'xfconf_locale': self.locale_fixture()}})
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
        native = root / 'native-fixture.json'
        native.write_text(json.dumps(self.native_fixture()))
        with patch.object(arm, 'source_contract', return_value=contract), \
                patch.object(arm, 'native_evidence', return_value=native), \
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
            self.assertEqual(manifest['tag'], 'v2.0-arm2')
            self.assertEqual(manifest['product_version'], '2.0')
            self.assertEqual(manifest['source_revision'], REVISION)
            self.assertNotEqual(manifest['source_revision'], manifest['previous_release']['source_revision'])
            self.assertFalse(manifest['pc_rebuilt'])
            self.assertFalse(manifest['mobile_rebuilt'])
            self.assertFalse(manifest['previous_release']['assets_modified'])
            self.assertEqual(manifest['supersedes_arm_release']['tag'], 'v2.0-arm1')
            self.assertFalse(manifest['supersedes_arm_release']['assets_modified'])
            self.assertIn('native-arm64-xfconf-locale.json', manifest['evidence_files'])
            self.assertEqual(set(manifest['evidence_files']), arm.EVIDENCE)
            self.assertEqual(len(manifest['evidence_files']), 13)
            for arch in arm.base.PI_ARCHES:
                name = f'OguzDows-rpi-{arch}.img.xz'
                self.assertEqual((root / 'output' / name).stat().st_ino, (inputs / ('rpi-' + arch) / name).stat().st_ino)
            self.assertEqual(len((root / 'output/SHA256SUMS').read_text().splitlines()), 2)
            self.assertNotIn('release-manifest.json', manifest['files'])

    def test_publisher_allowlist_cannot_hide_recipe_source_lock_or_target_smoke_changes(self):
        arm.validate_changes(['docs/index.html', 'docs/releases/v2.0-arm1.md', 'website/build.py',
                              '.github/workflows/main.yml', 'scripts/release-arm-refresh.py', 'scripts/release-draft-read.py',
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
                self.assertEqual(contract['xfconf_locale_runtime_schema'], 1)
                self.assertEqual(contract['source_revision'], REVISION)
                self.assertEqual(len(contract['asset_hashes']), 75)
                self.assertEqual(contract['asset_hashes']['usr/lib/oguzdows/wallpapers.py'],
                                 arm.base.sha256(ROOT / 'system/usr/lib/oguzdows/wallpapers.py'))

    def test_native_evidence_requires_both_suites_exact_runtime_bytes_and_real_turkish_callbacks(self):
        good = self.native_fixture()
        arm.validate_native_evidence(good, REVISION)
        for broken in ('source', 'suite', 'job', 'profiles-hash', 'probe-hash', 'settings-mock',
                       'callback', 'pixels', 'errors', 'old-English-only-evidence'):
            bad = copy.deepcopy(good)
            acceptance = bad['acceptance']
            report = acceptance['results'][0]['report']
            if broken == 'source': acceptance['source_revision'] = 'c' * 40
            if broken == 'suite': acceptance['results'].pop()
            if broken == 'job': acceptance['results'][0]['conclusion'] = 'failure'
            if broken == 'profiles-hash': report['runtime_sha256']['profiles.py'] = 'd' * 64
            if broken == 'probe-hash': report['locale_probe_sha256'] = 'e' * 64
            if broken == 'settings-mock': report['settings_backend_mocked'] = True
            if broken == 'callback': report['welcome_theme_callbacks_and_GTK_reload'] = False
            if broken == 'pixels': report['fixture-blue_root_rgb'] = [0, 0, 0]
            if broken == 'errors': report['errors'] = ['TEST ONLY failure']
            if broken == 'old-English-only-evidence': report.pop('xfconf_locale')
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                arm.validate_native_evidence(bad, REVISION)

    def test_locale_gate_rejects_missing_translated_header_mocked_or_missing_rollback_evidence(self):
        good = self.locale_fixture()
        arm.validate_locale(good, reproduced=True)
        arm.validate_locale(self.locale_fixture(reproduced=False), reproduced=False)
        for change in ({'schema': True}, {'environment': {'LANGUAGE': 'C'}}, {'raw_turkish_header': 'Value is an array with 2 items:'},
                       {'typed_arrays': ['int-array']}, {'runners': ['profiles']}, {'typed_backup': False},
                       {'persistence_failure_rollback': False}, {'compare_rollback': False}, {'settings_backend_mocked': True},
                       {'unfixed_reader_error_reproduced': False}, {'unfixed_reader_header': 'Value is an array with 4 items:'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                arm.validate_locale({**good, **change}, reproduced=True)
        with self.assertRaises(ValueError):
            arm.validate_locale(self.locale_fixture(reproduced=False), reproduced=True)

    def test_manifest_rejects_old_tag_source_missing_arch_or_inflated_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            self.prepare(root)
            good = arm.base.read_json(root / 'output/release-manifest.json')
            for change in ({'tag': 'v2.0'}, {'tag': 'v2.0-arm1'}, {'product_version': '2.0-arm2'}, {'source_revision': 'c' * 40},
                           {'pc_rebuilt': True}, {'mobile_rebuilt': True}, {'physical_boot': True},
                           {'images_repacked_by_publisher': True}, {'images_built_in_source_run': False},
                           {'files': {}}, {'files': None}, {'evidence_files': {}}, {'image_identity': {}},
                           {'publisher_revision': None}, {'schema': True}, {'previous_release': {}}, {'supersedes_arm_release': {}}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    arm.validate_manifest({**good, **change}, repository=REPOSITORY, run_id=123, release_id=456, revision=REVISION)

    def test_independent_audit_rehashes_all_downloads_and_repeats_inspection_without_release_writes(self):
        for use_grant in (False, True):
            with self.subTest(use_grant=use_grant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                expected = self.prepare(root)
                output = root / 'output'
                manifest = arm.base.read_json(output / 'release-manifest.json')
                release = {'id': 456, 'draft': True, 'prerelease': False, 'tag_name': arm.TAG, 'target_commitish': REVISION,
                           'body': 'TEST ONLY ARM notes', 'assets': [dict(id=index, name=name, state='uploaded',
                               size=row['size'], digest='sha256:' + row['sha256'],
                               url=f'https://api.github.com/repos/{REPOSITORY}/releases/assets/{index}',
                               browser_download_url=f'https://github.com/{REPOSITORY}/releases/download/{arm.TAG}/{name}')
                               for index, (name, row) in enumerate(expected.items(), start=1)]}
                def command(*args):
                    if args[:3] == ('gh', 'release', 'download'):
                        shutil.copytree(output, Path(args[-1]))
                    return ''
                with patch.object(arm.base, 'command', side_effect=command) as called, \
                        patch.object(arm.base, 'api', return_value=release) as api, \
                        patch.object(arm.draft_read, 'download', side_effect=lambda _grant, dest: shutil.copytree(output, dest)) as get, \
                        patch.object(arm, 'inspect', return_value=manifest['image_identity']) as inspect, \
                        patch.object(arm, 'native_evidence', return_value=root / 'native-fixture.json'), \
                        patch.object(arm.base, 'prepare_pi', wraps=arm.base.prepare_pi) as validate, patch('sys.stdout', io.StringIO()) as stdout:
                    arm.audit_release(release, root / 'audit', repository=REPOSITORY, run_id=123,
                                      release_id=456, revision=REVISION, notes='TEST ONLY ARM notes', artifacts={},
                                      read_grant={'release': release} if use_grant else None)
                validate.assert_called_once()
                inspect.assert_called_once()
                self.assertTrue(inspect.call_args.kwargs['audit'])
                if use_grant:
                    get.assert_called_once()
                    api.assert_not_called()  # no private-draft API, let alone a write token
                else:
                    api.assert_called_once()
                    get.assert_not_called()
                line, = [line for line in stdout.getvalue().splitlines() if line.startswith('::notice title=ARM release bağımsız')]
                summary = json.loads(line.split('::', 2)[2])
                self.assertEqual(summary['live_draft_metadata_rechecked_inside_audit'], not use_grant)
                self.assertEqual(summary['publication_collector_must_recheck_live_metadata'], use_grant)
                self.assertEqual(summary['draft_snapshot_sha256'], arm.draft_read.snapshot_hash(release))
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
        self.assertEqual(jobs['arm-release-audit']['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(jobs['arm-release-audit']['needs'], 'arm-release-audit-access')
        grant_job = jobs['arm-release-audit-access']
        self.assertEqual(grant_job['permissions'], {'contents': 'write', 'actions': 'read'})
        grant_script = '\n'.join(step.get('run', '') for step in grant_job['steps'])
        self.assertIn('--create-read-grant', grant_script)
        self.assertNotIn('--audit', grant_script)
        upload, = [step for step in grant_job['steps'] if step.get('uses') == 'actions/upload-artifact@v4']
        self.assertEqual(upload['with']['retention-days'], 1)
        audit_script = '\n'.join(step.get('run', '') for step in jobs['arm-release-audit']['steps'])
        self.assertIn('release-arm-refresh.py --audit --read-grant', audit_script)
        for job in ('arm-release', 'arm-release-audit', 'arm-release-audit-access'):
            text = '\n'.join(step.get('run', '') for step in jobs[job]['steps'])
            self.assertNotIn('build-pi.sh', text)
            self.assertNotIn('--clobber', text)
            self.assertNotIn('gh release edit', text)


class DraftReadTests(unittest.TestCase):
    NOW = 1_800_000_000
    CONTENT = b'SYNTHETIC TEST ONLY, not an image'

    def url(self, *, until=1800, host='release-assets.githubusercontent.com', permission='r'):
        expiry = datetime.fromtimestamp(self.NOW + until, timezone.utc).isoformat().replace('+00:00', 'Z')
        return f'https://{host}/github-production-release-asset/123/test?sp={permission}&se={expiry}&sig=synthetic-test-only'

    def release(self):
        return {'id': 456, 'draft': True, 'prerelease': False, 'tag_name': arm.TAG, 'target_commitish': REVISION,
                'body': 'SYNTHETIC TEST ONLY', 'assets': [{'id': 789, 'name': 'test.txt', 'state': 'uploaded',
                    'size': len(self.CONTENT), 'digest': 'sha256:' + hashlib.sha256(self.CONTENT).hexdigest(),
                    'url': f'https://api.github.com/repos/{REPOSITORY}/releases/assets/789',
                    'browser_download_url': f'https://github.com/{REPOSITORY}/releases/download/{arm.TAG}/test.txt'}]}

    def test_grant_is_short_lived_get_only_no_bearer_token_and_tampering_or_expiry_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'grant.json'
            with patch.object(arm.draft_read.time, 'time', return_value=self.NOW), \
                    patch.object(arm.draft_read, 'asset_read_url', return_value=self.url()):
                grant = arm.draft_read.create_grant(self.release(), path, repository=REPOSITORY, names={'test.txt'})
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(arm.draft_read.load_grant(path, repository=REPOSITORY, names={'test.txt'}), grant)
                self.assertNotIn('Authorization', path.read_text())
                bad = json.loads(path.read_text())
                bad['release']['assets'][0]['size'] += 1
                path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError, 'hash'):
                    arm.draft_read.load_grant(path, repository=REPOSITORY, names={'test.txt'})
                path.write_text(json.dumps(grant))
                with self.assertRaises(ValueError):
                    arm.draft_read.load_grant(path, repository='wrong/repository', names={'test.txt'})
                with self.assertRaises(ValueError):
                    arm.draft_read.load_grant(path, repository=REPOSITORY, names={'../escape'})
            with patch.object(arm.draft_read.time, 'time', return_value=self.NOW + 4000), self.assertRaises(ValueError):
                arm.draft_read.load_grant(path, repository=REPOSITORY, names={'test.txt'})

    def test_private_draft_untagged_routes_are_allowed_but_not_mistaken_for_published_tag_urls(self):
        release = self.release()
        published_hash = arm.draft_read.snapshot_hash(release)
        item = release['assets'][0]
        item['browser_download_url'] = item['browser_download_url'].replace('/' + arm.TAG + '/', '/untagged-8a82a6f2d62045573d67/')
        arm.draft_read.validate_snapshot(release, repository=REPOSITORY, names={'test.txt'})
        self.assertEqual(arm.draft_read.snapshot_hash(release), published_hash)
        for route in ('untagged-wrong', 'v2.0', 'other-tag', 'untagged-8a82a6f2d62045573d67/escape'):
            bad = self.release()
            bad['assets'][0]['browser_download_url'] = item['browser_download_url'].replace('untagged-8a82a6f2d62045573d67', route)
            with self.subTest(route=route), self.assertRaises(ValueError):
                arm.draft_read.validate_snapshot(bad, repository=REPOSITORY, names={'test.txt'})
        release['draft'] = False
        with self.assertRaises(ValueError):
            arm.draft_read.validate_snapshot(release, repository=REPOSITORY, names={'test.txt'})

    def test_only_github_asset_origin_read_permission_and_short_future_expiry_are_allowed(self):
        self.assertEqual(arm.draft_read.signed_url_expiry(self.url(), self.NOW), self.NOW + 1800)
        for url in (self.url(host='evil.example'), self.url(host='release-assets.githubusercontent.com.evil.example'),
                    self.url(host='user@release-assets.githubusercontent.com'), self.url(host='release-assets.githubusercontent.com:443'),
                    self.url(permission='rw'), self.url(until=-1), self.url(until=9999),
                    self.url().replace('https:', 'http:'), self.url() + '#fragment', self.url() + '&se=broken'):
            with self.subTest(kind=url.split('?')[0]), self.assertRaises(ValueError) as error:
                arm.draft_read.signed_url_expiry(url, self.NOW)
            self.assertNotIn(url, str(error.exception))

    def test_snapshot_rejects_duplicates_escaping_names_and_foreign_authenticated_api_requests(self):
        for kind in ('duplicate', 'escape', 'api', 'digest', 'size'):
            release = self.release()
            item = release['assets'][0]
            if kind == 'duplicate': release['assets'].append(dict(item))
            if kind == 'escape': item['name'] = '../test.txt'
            if kind == 'api': item['url'] = 'https://evil.example/steal-token'
            if kind == 'digest': item['digest'] = 'sha256:wrong'
            if kind == 'size': item['size'] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                arm.draft_read.validate_snapshot(release, repository=REPOSITORY, names={'test.txt'})

    def test_get_download_has_no_authorization_and_checks_exact_size_hash_and_hides_errors(self):
        for kind in ('valid', 'short', 'long', 'hash', 'network'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                grant = {'release': self.release(), 'urls': {'test.txt': self.url()}}
                content = self.CONTENT
                if kind == 'short': content = content[:-1]
                if kind == 'long': content += b'x'
                if kind == 'hash': content = b'x' * len(content)
                response = io.BytesIO(content)
                response.status = 200
                with patch.object(arm.draft_read.time, 'time', return_value=self.NOW), \
                        patch.object(arm.draft_read.urllib.request, 'build_opener') as build, patch('sys.stdout', io.StringIO()):
                    build.return_value.open.return_value = response
                    if kind == 'network': build.return_value.open.side_effect = OSError(self.url())
                    destination = Path(directory) / 'download'
                    if kind == 'valid':
                        arm.draft_read.download(grant, destination)
                        self.assertEqual((destination / 'test.txt').read_bytes(), self.CONTENT)
                    else:
                        with self.assertRaises(ValueError) as error:
                            arm.draft_read.download(grant, destination)
                        self.assertNotIn(self.url(), str(error.exception))
                        self.assertFalse((destination / 'test.txt').exists())
                    request = build.return_value.open.call_args.args[0]
                    self.assertEqual(request.get_method(), 'GET')
                    self.assertFalse(request.has_header('Authorization'))
                response.close()


if __name__ == '__main__':
    unittest.main()
