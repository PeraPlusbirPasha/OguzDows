"""Pinned Akıncı publication receipts; offline regressions, NOT another device/byte audit."""
import hashlib
import json
import unittest

from support import ROOT

SOURCE = '5a44de0dde676d901a32be40d631d481e213439d'
PREFIX = 'https://github.com/PeraPlusbirPasha/OguzDows/'
PRODUCTS = {
    'OguzDows-Mobile-2.0-Akinci-debug.apk': (24434944, '305015d09e57dcc18b854c3624754ed1723b2cfb2b9c3493c2b0cc6661820e82'),
    'OguzDows-Mobile-2.0-Akinci-tests.apk': (1087315, '7ef313a2ca2ea7197fe58280f4e5488c97cecd78a606378684ff3334db49184e'),
    'OguzDows-inert-install-fixture.apk': (11512, '487efbf4bcf8f552ad9c4644cabe6ff71761c29104d58f02cd7fd7617bf65ebe'),
    'OguzDows-Web-2.0-Akinci.tar.gz': (548075, '7c58f6449ce9bfcc55cd076d092e5bf561b2cdf19f9ab2b94bc8cd85e4e40237'),
}

IMAGES = {
    'OguzDows-amd64.iso': (1776648192, '88441467802343a7666c8f2db5e3c44bfb8a9dbebdca378a12fa69ad032b1d49'),
    'OguzDows-i386.iso': (1456766976, 'dfc0ab08e8c09e2d18ec0e83a8ab3bd5c07466bcce14f66c0f7156cc53e33276'),
    'OguzDows-rpi-armhf.img.xz': (984103864, '68e6816a3948cfb1115458c435673b8c45eff4fa7f4d24fb2be7e6684d1c7886'),
    'OguzDows-rpi-arm64.img.xz': (943580480, '6509d17f7dbe3bbf44b6e55d265d3da6f6c8019924305cd63c60efc95462106d'),
}


def read(name):
    return json.loads((ROOT / 'docs/releases' / name).read_text())


class ReleaseV20Tests(unittest.TestCase):
    def record(self):
        return read('v2.0-release.json')

    def test_four_images_and_real_launcher_have_one_source_not_the_publisher_revision(self):
        record = self.record()
        self.assertTrue(record['published'])
        self.assertTrue(record['latest_at_publication'])
        self.assertFalse(record['prerelease'])
        self.assertEqual(record['tag'], 'v2.0')
        self.assertEqual(record['release_id'], 461210500)
        self.assertEqual(record['url'], PREFIX + 'releases/tag/v2.0')
        self.assertEqual(record['source_revision'], SOURCE)
        self.assertEqual(record['tag_target'], SOURCE)
        self.assertNotEqual(record['publisher_revision'], SOURCE)
        self.assertTrue(record['images_and_apks_rebuilt_for_2_0_product_version'])
        self.assertFalse(record['images_or_apks_repacked_or_rebuilt_during_release_transfer'])
        identities = record['image_identity']
        self.assertEqual(set(identities), {'amd64', 'i386', 'rpi-armhf', 'rpi-arm64'})
        for identity in identities.values():
            self.assertEqual(identity['version'], '2.0')
            self.assertEqual(identity['build']['source_revision'], SOURCE)
        self.assertIsNone(identities['amd64']['build']['source_dirty'])
        self.assertIsNone(identities['i386']['build']['source_dirty'])

    def test_exact_asset_inventory_and_accepted_apk_web_bytes_are_pinned(self):
        record = self.record()
        names = {'APK-SIGNATURE.txt', 'BAGLANTI-REHBERI.md', 'INDIRME-REHBERI.md', 'MOBILE-BUILD.txt',
                 'SHA256SUMS', 'desktop-idle-amd64.json', 'desktop-idle-i386.json', 'pi-gen.lock.json',
                 'release-manifest.json', 'test-evidence.tar.gz', *PRODUCTS}
        images = ['OguzDows-amd64.iso', 'OguzDows-i386.iso', 'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-arm64.img.xz']
        names.update(images)
        names.update(name + '.sha256' for name in images)
        names.update(name + '.sha256' for name in ('OguzDows-Mobile-2.0-Akinci-debug.apk', 'OguzDows-Web-2.0-Akinci.tar.gz'))
        names.update('OguzDows-rpi-' + arch + '.packages.txt' for arch in ('armhf', 'arm64'))
        self.assertEqual(record['asset_count'], 26)
        self.assertEqual(set(record['files']), names)
        for name, item in record['files'].items():
            self.assertEqual(item['state'], 'uploaded')
            self.assertGreater(item['size'], 0)
            self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(item['url'], PREFIX + 'releases/download/v2.0/' + name)
        for name, (size, digest) in {**IMAGES, **PRODUCTS}.items():
            self.assertEqual((record['files'][name]['size'], record['files'][name]['sha256']), (size, digest))
        guide = ROOT / 'docs/AKINCI-BAGLANTI.md'
        self.assertEqual(record['files']['BAGLANTI-REHBERI.md']['sha256'], hashlib.sha256(guide.read_bytes()).hexdigest())
        self.assertEqual(record['files']['INDIRME-REHBERI.md']['sha256'], hashlib.sha256((ROOT / 'docs/releases/v2.0.md').read_bytes()).hexdigest())

    def test_distinct_successful_runner_redownloaded_all_bytes_before_publication(self):
        record = self.record()
        transfer, audit = record['release_transfer'], record['release_download_audit']
        self.assertNotEqual(transfer['run_id'], audit['run_id'])
        self.assertNotEqual(transfer['job_id'], audit['job_id'])
        self.assertEqual(transfer['conclusion'], 'success')
        self.assertEqual(audit['conclusion'], 'success')
        self.assertTrue(audit['all_release_assets_redownloaded_and_hashed'])
        self.assertEqual(audit['asset_count'], 26)
        self.assertEqual(audit['evidence_file_count'], 27)
        self.assertEqual(audit['evidence_json_count'], 26)
        self.assertTrue(audit['draft'])
        self.assertFalse(audit['release_modified'])
        self.assertEqual(audit['source_revision'], SOURCE)
        self.assertEqual(audit['publisher_revision'], record['publisher_revision'])
        self.assertEqual(audit['mobile_source_run_id'], 46092350348)
        self.assertTrue(record['full_product_bytes_hashed_in_GitHub_runner'])
        self.assertFalse(record['full_product_bytes_downloaded_or_independently_hashed_in_local_sandbox'])
        self.assertTrue(record['independent_audit_rechecked_apk_package_version_certificate_and_full_native_capture_gate'])
        public = record['public_release_latest_and_tag_checks']
        self.assertTrue(public['all_checks_passed'])
        self.assertTrue(public['unauthenticated'])
        self.assertEqual(len(record['public_download_checks']), 26)
        self.assertEqual({item['name'] for item in record['public_download_checks']}, set(record['files']))
        for item in record['public_download_checks']:
            self.assertIn(item['status'], (200, 302, 307))
            self.assertTrue(item['unauthenticated'])
            self.assertFalse(item['full_bytes_downloaded_by_this_head_check'])

    def test_real_build_and_native_acceptance_are_separate_from_static_browser_design(self):
        record = self.record()
        self.assertEqual(record['image_build_verification'], read('v2.0-build.json'))
        build = record['image_build_verification']
        self.assertEqual(build['source_revision'], SOURCE)
        for kind, run_id in (('pc', 46092345482), ('pi', 46092347693)):
            run = record['source_runs'][kind]['run']
            self.assertEqual(run['id'], run_id)
            self.assertEqual(run['head_sha'], SOURCE)
            self.assertEqual(run['status'], 'completed')
            self.assertEqual(run['conclusion'], 'success')
        self.assertEqual(record['source_runs']['mobile']['id'], 46092350348)
        self.assertEqual(record['source_runs']['mobile']['source_revision'], SOURCE)
        self.assertEqual(record['source_runs']['mobile']['conclusion'], 'success')
        self.assertFalse(build['physical_pc_or_pi_boot_verified'])
        self.assertFalse(build['full_image_bytes_downloaded_or_independently_hashed_by_this_metadata_collector'])
        self.assertFalse(record['physical_pc_pi_phone_or_real_SIM_verified'])
        self.assertFalse(record['pi_performance_measured'])
        package = json.loads((ROOT / 'mobile/android/evidence/package-5a44de0.json').read_text())
        accepted = json.loads((ROOT / 'mobile/android/evidence/acceptance-5a44de0.json').read_text())
        self.assertEqual(record['mobile'], package)
        self.assertEqual(package['source_sha'], SOURCE)
        self.assertEqual(package['version_code'], 20)
        self.assertEqual(package['version'], '2.0.0-akinci')
        self.assertFalse(package['production_signing'])
        self.assertTrue(accepted['passed'])
        self.assertEqual((accepted['native_cases'], accepted['jvm_cases']), (24, 20))
        self.assertFalse(package['physical_devices_tested'])
        thumbnail = ROOT / 'docs/assets/oguzdows-mobile-v2.jpg'
        self.assertEqual(hashlib.sha256(thumbnail.read_bytes()).hexdigest(), '2f532a28e17c2df84030c0169a44878479b4e6df51cf9ed4d4b6e7699bff6876')

    def test_original_instrumentation_metadata_is_not_fabricated_from_primary_version(self):
        report = self.record()['read_only_original_apk_diagnostics']
        self.assertEqual(report, read('v2.0-apk-diagnostics.json'))
        self.assertEqual(report['source_revision'], SOURCE)
        self.assertEqual(report['mobile_source_run_id'], 46092350348)
        self.assertFalse(report['artifacts_or_release_modified'])
        self.assertFalse(report['APKs_installed_or_executed_by_diagnostic'])
        self.assertFalse(report['full_APK_bytes_downloaded_or_hashed_in_local_sandbox'])
        self.assertEqual(report['diagnostic_run']['conclusion'], 'success')
        identities = {item['file']: item for item in report['identities']}
        self.assertEqual(set(identities), set(PRODUCTS) - {'OguzDows-Web-2.0-Akinci.tar.gz'})
        test = identities['OguzDows-Mobile-2.0-Akinci-tests.apk']
        self.assertIn("versionCode='' versionName=''", test['package_lines'][0])
        xml = '\n'.join(line for block in test['instrumentation_xml'] for line in block)
        self.assertIn('androidx.test.runner.AndroidJUnitRunner', xml)
        self.assertIn('android:targetPackage(0x01010021)="org.oguzdows.mobile"', xml)
        for name, item in identities.items():
            self.assertEqual((item['bytes'], item['sha256']), PRODUCTS[name])
            self.assertEqual(item['certificate_sha256'], '5f87f6817823b618c7ff26ed57e56f5e71305b689e5d7b50331883b767ee7811')

    def test_failed_transfers_are_preserved_and_native_gates_not_waived(self):
        record = self.record()
        self.assertEqual({item['run_id'] for item in record['rejected_transfer_attempts']}, {46098202189, 46098735703})
        for item in record['rejected_transfer_attempts']:
            self.assertEqual(item['conclusion'], 'failure')
            self.assertTrue(item['no_release_assets_from_this_failed_attempt'])
            self.assertFalse(item['native_or_image_acceptance_relaxed'])
        rules = record['release_packaging_regressions']
        self.assertEqual(rules['count'], 47)
        self.assertTrue(all(value is True for key, value in rules.items() if key != 'count'))
        notes = (ROOT / 'docs/releases/v2.0.md').read_text()
        for required in ('46098202189', '46098735703', '46099111876', '46092349811', '2205 ms', 'siyah ekran', 'ROM/OTA/GSI', 'wake-word'):
            self.assertIn(required, notes)

    def test_previous_releases_unchanged_and_pr_is_not_merged(self):
        record = self.record()
        expected = {'v1.2': (460537352, 'dc92fe9e47d8cdc599094281780e274cc49d1470', 17),
                    'v1.1': (455583593, '29f7738534cd00bd87887f530355ef45e01eb28c', 17),
                    'v1.0.0': (452038375, 'bcd03315873f186ee25f9296afc44356defd0763', 8)}
        self.assertEqual(set(record['previous_releases_preserved']), set(expected))
        for tag, values in expected.items():
            old = record['previous_releases_preserved'][tag]
            self.assertEqual((old['release_id'], old['source_revision'], old['asset_count']), values)
            self.assertTrue(old['tag_body_asset_ids_sizes_hashes_unchanged'])
        self.assertEqual(record['pull_request']['state'], 'OPEN')
        self.assertTrue(record['pull_request']['isDraft'])
        self.assertIsNone(record['pull_request']['mergedAt'])
        self.assertEqual(record['pull_request']['headRefName'], 'arena/2d796713-o-uzdows')


if __name__ == '__main__':
    unittest.main()
