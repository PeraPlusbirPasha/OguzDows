"""Synthetic fail-closed Akıncı publishing regressions; never real APK/boot evidence."""
import contextlib
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from support import ROOT, load
import test_release_all_assets as all_tests
from test_release_all_assets import REVISION, REPOSITORY

release = load('mobile_release_assets_test', 'scripts/release-assets.py')
fixtures = runpy.run_path(str(ROOT / 'mobile/tests/test_acceptance.py'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')


class MobileReleaseAssetsTests(unittest.TestCase):
    def fixture(self, root):
        directory = root / 'input/mobile'
        directory.mkdir(parents=True)
        product = release.mobile_product('v2.0')
        build = fixtures['synthetic_build']()
        device, frame = fixtures['synthetic_device']()
        build['source_sha'] = device['source_sha'] = REVISION
        device['passed'] = True
        names = [product['mobile_apk'], product['mobile_tests_apk'], 'OguzDows-inert-install-fixture.apk']
        files, signatures = [], []
        for index, (item, name) in enumerate(zip(build['assembled'], names)):
            content = b'Not a real APK; synthetic integrity rule fixture: ' + str(index).encode()
            (directory / name).write_bytes(content)
            item.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
            files.append(dict(file=name, bytes=item['bytes'], sha256=item['sha256']))
            signatures.append(name + '\nSigner #1 certificate SHA-256 digest: ' + 'c' * 64 + '\n')
        (directory / 'APK-SIGNATURE.txt').write_text('\n'.join(signatures))
        (directory / 'SHA256SUMS').write_text(''.join(item['sha256'] + '  ' + item['file'] + '\n' for item in files))
        build_text = 'SOURCE_SHA=' + REVISION + '\nDEBUG synthetic release rule fixture; not installable\n'
        (directory / 'BUILD.txt').write_text(build_text)
        contents = {'web/index.html': b'<html>synthetic web fixture</html>', 'web/assets/app.js': b'/* no app */',
                    'BUILD.txt': build_text.encode(), 'ASSETS.md': b'Synthetic rule fixture.\n',
                    'BAGLANTI-REHBERI.md': (ROOT / 'docs/AKINCI-BAGLANTI.md').read_bytes()}
        web = directory / product['web_bundle']
        with tarfile.open(web, 'w:gz') as archive:
            for name, content in contents.items():
                info = tarfile.TarInfo(name); info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        package = dict(source_sha=REVISION, version=product['mobile_version_name'], version_code=20,
                       release_tag='v2.0', bridge_protocol=1, apksigner_verified=True, production_signing=False,
                       files=files, certificate_sha256={name: 'c' * 64 for name in names}, physical_devices_tested=False,
                       web_bundle=dict(file=web.name, bytes=web.stat().st_size, sha256=release.sha256(web)))
        accepted = dict(source_sha=REVISION, passed=True, native_cases=24, jvm_cases=20, interop_files=4,
                        real_capture_sha256=release.sha256(directory / names[0]),
                        physical_devices_tested=False, rom_or_gms_certification=False)
        accepted['real_capture_sha256'] = hashlib.sha256(frame).hexdigest()
        for name, value in [('build.json', build), ('evidence.json', device), ('acceptance.json', accepted),
                            ('release-package.json', package), ('product-identity.json', product)]:
            write_json(directory / name, value)
        (directory / 'connected-real-mediaprojection.jpg').write_bytes(frame)
        return directory

    def inspector(self, path, package, *, version=None, code=None):
        return dict(package=package, version_name=version or 'synthetic-test', version_code=code or 1,
                    certificate_sha256='c' * 64, signature_verified=True,
                    scope='read-only-aapt-and-apksigner-not-physical-install')

    def prepare(self, root):
        with patch.object(release, 'inspect_apk', side_effect=self.inspector):
            checksums, evidence = [], {}
            report = release.prepare_mobile(root / 'input', root / 'output', REVISION, 'v2.0', checksums, evidence)
        return report, checksums, evidence

    def test_three_apks_web_guide_raw_acceptance_and_exact_bytes_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = self.fixture(root); (root / 'output').mkdir()
            report, checksums, evidence = self.prepare(root)
            product = release.mobile_product('v2.0')
            self.assertEqual(set(release.inventory(root / 'output')), release.mobile_assets(product))
            self.assertEqual(len(checksums), 4)
            self.assertEqual(len(evidence), 6)
            self.assertFalse(report['production_signing'])
            self.assertFalse(report['physical_devices_tested'])
            self.assertEqual(report['acceptance']['native_cases'], 24)
            for name in [product['mobile_apk'], product['mobile_tests_apk'], product['web_bundle']]:
                self.assertEqual((root / 'output' / name).stat().st_ino, (directory / name).stat().st_ino)
            self.assertEqual((root / 'output/BAGLANTI-REHBERI.md').read_bytes(), (ROOT / 'docs/AKINCI-BAGLANTI.md').read_bytes())

    def test_old_wrong_source_version_missing_native_case_anr_and_capture_cannot_be_published(self):
        changes = [('build.json', lambda r: r.update(source_sha='d' * 40)),
                   ('evidence.json', lambda r: r['tests'].pop()),
                   ('evidence.json', lambda r: r.update(product_anr_detected=True)),
                   ('evidence.json', lambda r: r['screen_capture'].update(stop_tested=False)),
                   ('acceptance.json', lambda r: r.update(passed=False)),
                   ('acceptance.json', lambda r: r.update(physical_devices_tested=True)),
                   ('release-package.json', lambda r: r.update(version='0.4.0-connected')),
                   ('release-package.json', lambda r: r.update(version_code=4)),
                   ('release-package.json', lambda r: r.update(production_signing=True)),
                   ('release-package.json', lambda r: r['files'].pop()),
                   ('product-identity.json', lambda r: r.update(version='1.2'))]
        for name, mutate in changes:
            with self.subTest(name=name, mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); directory = self.fixture(root); (root / 'output').mkdir()
                path = directory / name; data = release.read_json(path); mutate(data); write_json(path, data)
                with self.assertRaises(ValueError): self.prepare(root)

    def test_modified_apk_signature_manifest_web_and_missing_real_frame_fail_closed(self):
        product = release.mobile_product('v2.0')
        for name in (product['mobile_apk'], product['web_bundle'], 'APK-SIGNATURE.txt', 'SHA256SUMS',
                     'BUILD.txt', 'connected-real-mediaprojection.jpg'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); directory = self.fixture(root); (root / 'output').mkdir()
                (directory / name).write_bytes(b'altered')
                with self.assertRaises(ValueError): self.prepare(root)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = self.fixture(root); (root / 'output').mkdir()
            (directory / 'connected-real-mediaprojection.jpg').unlink()
            with self.assertRaises(ValueError): self.prepare(root)

    def test_apk_data_readers_check_real_version_and_signer_without_installing(self):
        data = "package: name='org.oguzdows.mobile' versionCode='20' versionName='2.0.0-akinci' platformBuildVersionName='15'\n"
        signature = 'Signer #1 certificate SHA-256 digest: ' + 'c' * 64 + '\n'
        with patch.object(release, 'command', side_effect=[data, signature]) as command:
            identity = release.inspect_apk(Path('test.apk'), 'org.oguzdows.mobile', version='2.0.0-akinci', code=20)
        self.assertEqual(identity['version_code'], 20)
        self.assertEqual([call.args[:3] for call in command.call_args_list], [('aapt', 'dump', 'badging'), ('apksigner', 'verify', '--verbose')])
        for badging, signer in [(data.replace("'20'", "'4'"), signature),
                                 (data.replace('2.0.0-akinci', '0.4.0-connected'), signature),
                                 (data.replace('org.oguzdows.mobile', 'lookalike'), signature), (data, 'no verified signer')]:
            with self.subTest(badging=badging, signer=signer), patch.object(release, 'command', side_effect=[badging, signer]), self.assertRaises(ValueError):
                release.inspect_apk(Path('test.apk'), 'org.oguzdows.mobile', version='2.0.0-akinci', code=20)

    def test_web_archive_rejects_traversal_links_oversize_and_wrong_source(self):
        for name, kind, content, size in [('../escape', tarfile.REGTYPE, b'x', 1),
                                           ('web/link', tarfile.SYMTYPE, b'', 0),
                                           ('BUILD.txt', tarfile.REGTYPE, b'SOURCE_SHA=wrong\n', 17),
                                           ('web/large', tarfile.REGTYPE, b'', 16 * 1024**2 + 1)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'bad.tar.gz'
                # Header-only giant member is enough: validator must reject before reading it.
                info = tarfile.TarInfo(name); info.type = kind; info.size = size
                if size > len(content):
                    # Python 3.13 correctly refuses addfile(size>0, fileobj=None).
                    # A deliberately truncated header fixture tests our early size gate
                    # without allocating/writing 16 MiB or depending on the old writer bug.
                    with gzip.open(path, 'wb') as raw: raw.write(info.tobuf())
                else:
                    with tarfile.open(path, 'w:gz') as archive: archive.addfile(info, io.BytesIO(content))
                with self.assertRaises((ValueError, tarfile.ReadError)):
                    release.validate_web_bundle(path, REVISION, 'SOURCE_SHA=' + REVISION + '\nDEBUG\n')

    def test_akinci_refuses_partial_suite_and_old_run_path(self):
        for options in ({}, {'pi_run_id': 789}, {'mobile_run_id': 999}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                root = Path(tmp)
                release.prepare(root / 'input', root / 'output', repository=REPOSITORY, run_id=123, release_id=456,
                                revision=REVISION, publisher_revision='b' * 40, tag='v2.0', **options)
        run = dict(id=999, status='completed', conclusion='success', repository=dict(full_name=REPOSITORY),
                   head_repository=dict(full_name=REPOSITORY), head_branch='arena/test', head_sha=REVISION,
                   path='.github/workflows/mobile-emulator.yml')
        self.assertEqual(release.validate_run(run, 999, REPOSITORY, 'arena/test', mobile=True), REVISION)
        with self.assertRaises(ValueError): release.validate_run(run, 999, REPOSITORY, 'arena/test')
        for change in ({'conclusion': 'failure'}, {'head_sha': 'wrong'}, {'path': '.github/workflows/main.yml'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                release.validate_run({**run, **change}, 999, REPOSITORY, 'arena/test', mobile=True)

    def test_full_format_three_transfer_and_independent_26_file_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); all_tests.AllReleaseAssetsTests().fixture(root); self.fixture(root)
            host = root / 'host.json'; write_json(host, dict(source_revision=REVISION, conclusion='success'))
            identities = all_tests.AllReleaseAssetsTests().identities(root / 'input')
            for identity in identities.values(): identity['version'] = '2.0'
            with patch.object(release, 'inspect_images', return_value=identities), patch.object(release, 'host_evidence', return_value=host), \
                    patch.object(release, 'inspect_apk', side_effect=self.inspector):
                expected = release.prepare(root / 'input', root / 'output', repository=REPOSITORY, run_id=123, pi_run_id=789,
                                           mobile_run_id=999, release_id=456, revision=REVISION, publisher_revision='b' * 40, tag='v2.0')
            self.assertEqual(len(expected), 26)
            manifest = release.read_json(root / 'output/release-manifest.json')
            self.assertEqual(manifest['format'], 3)
            self.assertEqual(manifest['mobile_source_run_id'], 999)
            self.assertEqual(len(manifest['evidence_files']), 27)
            self.assertEqual(len((root / 'output/SHA256SUMS').read_text().splitlines()), 8)
            draft = dict(id=456, draft=True, tag_name='v2.0', target_commitish=REVISION,
                         body=(ROOT / 'docs/releases/v2.0.md').read_text(),
                         assets=[dict(name=name, size=item['size'], digest='sha256:' + item['sha256'], state='uploaded')
                                 for name, item in expected.items()])
            def command(*args):
                if args[:3] == ('gh', 'release', 'download'):
                    target = Path(args[args.index('--dir') + 1]); target.mkdir(parents=True)
                    pattern = args[args.index('--pattern') + 1]
                    files = list((root / 'output').iterdir()) if pattern == '*' else [root / 'output' / pattern]
                    for path in files: shutil.copyfile(path, target / path.name)
                elif args[:3] != ('git', 'merge-base', '--is-ancestor'):
                    raise AssertionError('Unexpected write/command: ' + repr(args))
                return ''
            output = io.StringIO()
            with patch.object(release, 'command', side_effect=command), patch.object(release, 'api', return_value=draft), \
                    patch.object(release, 'inspect_apk', side_effect=self.inspector), contextlib.redirect_stdout(output):
                audited = release.audit_release(draft, root / 'audit', repository=REPOSITORY, run_id=123, pi_run_id=789,
                                                mobile_run_id=999, release_id=456, revision=REVISION, tag='v2.0', notes=draft['body'])
            self.assertEqual(audited, expected)
            self.assertLessEqual(len(output.getvalue().splitlines()), 10)
            self.assertIn('"evidence_json_count": 26', output.getvalue())
            self.assertIn('"all_release_assets_redownloaded_and_hashed": true', output.getvalue())
            for remove in (release.mobile_product('v2.0')['mobile_apk'], 'BAGLANTI-REHBERI.md'):
                broken = copy.deepcopy(draft); broken['assets'] = [item for item in broken['assets'] if item['name'] != remove]
                with self.subTest(remove=remove), self.assertRaises(ValueError): release.check_remote(broken, expected, complete=True)

    def test_only_specific_mobile_documentation_receipts_can_change_after_build(self):
        release.validate_changes(['mobile/INSTALL.md', 'mobile/android/README.md', 'mobile/android/evidence/package-abcdef0.json'])
        for name in ('mobile/android/app/build.gradle.kts', 'mobile/preview/src/App.tsx', 'mobile/feature-parity.json',
                     'mobile/evil.md', 'mobile/android/evidence/evil.json', 'mobile/scripts/acceptance.py'):
            with self.subTest(name=name), self.assertRaises(ValueError): release.validate_changes([name])


if __name__ == '__main__':
    unittest.main()
