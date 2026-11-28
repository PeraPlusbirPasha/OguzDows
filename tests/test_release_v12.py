"""Pinned public 1.2 documentation evidence; offline checks, not physical tests."""
import json
import unittest

from support import ROOT

SOURCE = 'dc92fe9e47d8cdc599094281780e274cc49d1470'
IMAGES = ('OguzDows-amd64.iso', 'OguzDows-i386.iso',
          'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-arm64.img.xz')
NAMES = set(IMAGES) | {name + '.sha256' for name in IMAGES} | {
    'OguzDows-rpi-armhf.packages.txt', 'OguzDows-rpi-arm64.packages.txt', 'pi-gen.lock.json',
    'desktop-idle-amd64.json', 'desktop-idle-i386.json', 'SHA256SUMS', 'test-evidence.tar.gz',
    'INDIRME-REHBERI.md', 'release-manifest.json'}
PREFIX = 'https://github.com/PeraPlusbirPasha/OguzDows/'


class Release12Tests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT / 'docs/releases/v1.2-release.json').read_text())

    def test_published_tag_and_four_internal_versions_pin_real_rebuilt_source_not_publisher(self):
        record = self.record()
        self.assertTrue(record['published'])
        self.assertTrue(record['latest_at_publication'])
        self.assertFalse(record['prerelease'])
        self.assertEqual(record['tag'], 'v1.2')
        self.assertEqual(record['source_revision'], SOURCE)
        self.assertEqual(record['tag_target'], SOURCE)
        self.assertRegex(record['publisher_revision'], r'^[0-9a-f]{40}$')
        self.assertNotEqual(record['publisher_revision'], SOURCE)
        self.assertTrue(record['images_rebuilt_for_1_2_product_version'])
        self.assertFalse(record['images_repacked_or_rebuilt_during_release_transfer'])
        self.assertGreater(record['release_id'], 0)
        self.assertEqual(record['url'], PREFIX + 'releases/tag/v1.2')
        self.assertEqual(set(record['image_identity']), {'amd64', 'i386', 'rpi-armhf', 'rpi-arm64'})
        for arch, identity in record['image_identity'].items():
            with self.subTest(arch=arch):
                self.assertEqual(identity['version'], '1.2')
                self.assertEqual(identity['build']['source_revision'], SOURCE)
                self.assertIsNot(identity['build']['source_dirty'], True)
                self.assertIn(type(identity['build']['source_dirty']), (bool, type(None)))
                if arch.startswith('rpi-'):
                    self.assertTrue(identity['existing_pi_verifier_passed'])
                    self.assertTrue(identity['embedded_runtime_matches_raw_artifact'])
                    self.assertGreater(identity['uncompressed_bytes'], 1_000_000_000)
                    self.assertRegex(identity['uncompressed_sha256'], r'^[0-9a-f]{64}$')

    def test_exact_17_file_inventory_has_individual_hashes_original_names_and_public_urls(self):
        record = self.record()
        self.assertEqual(record['asset_count'], 17)
        self.assertEqual(set(record['files']), NAMES)
        ids = set()
        for name, data in record['files'].items():
            with self.subTest(name=name):
                self.assertGreater(data['id'], 0)
                ids.add(data['id'])
                self.assertGreater(data['size'], 0)
                self.assertRegex(data['sha256'], r'^[0-9a-f]{64}$')
                self.assertEqual(data['state'], 'uploaded')
                self.assertEqual(data['url'], PREFIX + 'releases/download/v1.2/' + name)
                if name in IMAGES:
                    self.assertGreater(data['size'], 256 * 1024**2)
                    self.assertLess(data['size'], 2 * 1024**3)
        self.assertEqual(len(ids), 17)
        self.assertEqual(len({record['files'][name]['sha256'] for name in IMAGES}), 4)

    def test_independent_audit_really_hashed_all_17_and_21_jsons_without_rebuilding_or_publishing(self):
        record = self.record()
        transfer, audit = record['release_transfer'], record['release_download_audit']
        self.assertEqual(transfer['conclusion'], 'success')
        self.assertNotEqual(transfer['run_id'], audit['run_id'])
        self.assertEqual(transfer['url'], PREFIX + 'actions/runs/' + str(transfer['run_id']))
        self.assertEqual(audit['url'], PREFIX + 'actions/runs/' + str(audit['run_id']))
        self.assertEqual(audit['release_id'], record['release_id'])
        self.assertEqual(audit['source_revision'], SOURCE)
        self.assertEqual(audit['tag'], 'v1.2')
        self.assertTrue(audit['all_release_assets_redownloaded_and_hashed'])
        self.assertFalse(audit['release_modified'])
        self.assertTrue(audit['draft'])  # It was audited BEFORE being published.
        self.assertEqual(audit['asset_count'], 17)
        self.assertEqual(audit['evidence_json_count'], 21)
        self.assertTrue(record['full_image_bytes_hashed_in_GitHub_runner'])
        self.assertFalse(record['full_image_bytes_downloaded_or_independently_hashed_in_local_sandbox'])
        self.assertFalse(record['physical_pc_or_pi_boot_verified'])
        self.assertFalse(record['pi_performance_measured'])
        self.assertIn('black screen', record['known_issue'])

    def test_public_release_latest_tag_and_all_downloads_were_checked_without_authentication(self):
        record = self.record()
        endpoints = record['public_release_latest_and_tag_checks']
        self.assertTrue(endpoints['unauthenticated'])
        self.assertTrue(endpoints['public_api_release_latest_and_tag_verified'])
        self.assertTrue(endpoints['all_checks_passed'])
        self.assertEqual(endpoints['release_id'], record['release_id'])
        self.assertEqual(endpoints['source_revision'], SOURCE)
        self.assertEqual(len(endpoints['html_pages']), 2)
        for page in endpoints['html_pages']:
            self.assertEqual(page['status'], 200)
            self.assertTrue(page['unauthenticated'])
            self.assertEqual(page['final_url'], record['url'])
        downloads = record['public_download_checks']
        self.assertEqual(len(downloads), 17)
        self.assertEqual({row['name'] for row in downloads}, NAMES)
        for row in downloads:
            self.assertTrue(row['unauthenticated'])
            self.assertIn(row['status'], (200, 302, 307))
            self.assertEqual(row['url'], record['files'][row['name']]['url'])

    def test_original_image_and_16_host_jobs_refer_to_the_same_source_not_first_failed_attempt(self):
        record = self.record()
        for platform, run_id in (('pc', 45984535667), ('pi', 45984521207)):
            run = record['source_runs'][platform]['run']
            self.assertEqual(run['id'], run_id)
            self.assertEqual(run['head_sha'], SOURCE)
            self.assertEqual(run['event'], 'workflow_dispatch')
            self.assertEqual(run['status'], 'completed')
            self.assertEqual(run['conclusion'], 'success')
            self.assertEqual(run['run_attempt'], 1)
            self.assertTrue(all(job['conclusion'] in ('success', 'skipped') for job in record['source_runs'][platform]['jobs']))
        host = json.loads((ROOT / 'docs/releases/v1.2-host.json').read_text())
        self.assertEqual(host['source_revision'], SOURCE)
        self.assertEqual(host['product_version'], '1.2')
        self.assertEqual(host['conclusion'], 'success')
        self.assertEqual(host['successful_job_count'], 16)
        self.assertEqual(host['workbench_gtk_reports'], 8)
        self.assertEqual(host['real_signed_apt_bootstrap_reports'], 3)
        self.assertEqual(host['own_32bit_abi_reports'], 2)
        self.assertTrue(host['synthetic_pr_ci_revisions_are_not_image_revision'])
        self.assertFalse(host['physical_boot_verified'])
        self.assertFalse(host['physical_gpu_verified'])
        self.assertFalse(host['flathub_application_download_tested'])
        self.assertFalse(host['interactive_polkit_tested'])
        self.assertEqual({row['run']['id'] for row in host['runs'].values()},
                         {45984418994, 45984418959, 45984418943, 45984418960})

    def test_ram_numbers_use_actual_current_512_1024_2048_vm_reports_and_notes_disclose_limits(self):
        record = self.record()
        checks = record['image_build_verification']
        self.assertTrue(checks['complete'])
        self.assertEqual(checks['source_revision'], SOURCE)
        self.assertTrue(checks['publication_byte_audit_required'])
        self.assertFalse(checks['full_image_bytes_downloaded_or_independently_hashed_by_this_metadata_collector'])
        self.assertEqual(set(checks['images']), {'amd64', 'i386', 'armhf', 'arm64'})
        notes, readme = ((ROOT / name).read_text() for name in ('docs/releases/v1.2.md', 'README.md'))
        for arch in ('amd64', 'i386'):
            rows = checks['images'][arch]['ram_vm_not_physical']
            self.assertEqual({row['vm_ram_mib'] for row in rows}, {512, 1024, 2048})
            for row in rows:
                self.assertTrue(row['valid_idle_measurement'] and row['target_met'])
                self.assertEqual(row['invalid_reasons'], [])
                self.assertIn(f"{row['median_used_mb']:.1f} / {row['max_used_mb']:.1f}", notes)
                self.assertIn(f"{row['max_used_mb']:.1f}", readme)
                if row['vm_ram_mib'] < 2048: self.assertTrue(row['low_ram_budget']['passed'])
        for arch in ('armhf', 'arm64'):
            target = checks['images'][arch]['minimum_cpu_user_qemu_not_physical_boot']
            self.assertFalse(target['physical_boot'])
            self.assertFalse(target['hardware_gpu'])
            self.assertFalse(target['performance_measurement'])
            cleanup = checks['images'][arch]['private_GUI_process_cleanup_host_report']
            self.assertTrue(cleanup['passed'])
            self.assertEqual(cleanup['remaining'], [])
        for needed in (SOURCE, '23 yeni işlev', '1 GiB', '2 GiB', '4 GiB', '512 MB',
                       '12 GiB', '16 GB', 'Zero 2 W', 'i686/PAE', 'ARMv6', 'Pi 5', 'SSE2',
                       'siyah ekran bildirimi çözülmüş değildir', 'LightDM/PAM', 'Secure Boot',
                       'source_dirty: null', 'MemTotal', '120 saniye', '21 JSON', 'test-evidence.tar.gz',
                       '701 test / 9', '10 test / 0', '45977169487'):
            self.assertIn(needed, notes)
        for name in IMAGES:
            self.assertIn('/releases/download/v1.2/' + name + ')', notes)
            self.assertIn('/releases/download/v1.2/' + name + '.sha256)', notes)
        self.assertNotIn('692 test / 8', notes)

    def test_v11_and_v100_history_and_current_guide_introductions_are_not_relabelled(self):
        record = self.record()
        expected = {'v1.1': ('29f7738534cd00bd87887f530355ef45e01eb28c', 17),
                    'v1.0.0': ('bcd03315873f186ee25f9296afc44356defd0763', 8)}
        self.assertEqual(set(record['previous_releases_preserved']), set(expected))
        for tag, (revision, count) in expected.items():
            old = record['previous_releases_preserved'][tag]
            self.assertEqual(old['source_revision'], revision)
            self.assertEqual(old['asset_count'], count)
            self.assertTrue(old['tag_body_asset_ids_sizes_hashes_unchanged'])
        historical = json.loads((ROOT / 'docs/releases/v1.1-release.json').read_text())
        self.assertEqual(historical['source_revision'], expected['v1.1'][0])
        self.assertEqual(historical['release_id'], 455583593)
        self.assertTrue(all('/download/v1.1/' in data['url'] for data in historical['files'].values()))
        pi = (ROOT / 'raspberrypi/README.md').read_text()
        intro = pi.split('> **Deneysel port:**', 1)[0]
        self.assertIn(SOURCE, intro)
        self.assertIn('/download/v1.2/', intro)
        self.assertNotIn('v1.1', intro)
        self.assertIn('v1.1 tarihsel kaydı', pi)
        self.assertIn('iki Pi imajı da başarısız oldu ve yayımlanmadı', pi)
        self.assertIn('1.2 ara güncellemesi', (ROOT / 'docs/SURUM-POLITIKASI.md').read_text())
        self.assertNotIn('1.2 ara güncellemesi · hazırlık', (ROOT / 'docs/SURUM-POLITIKASI.md').read_text())
        for name in ('ATOLYE-VE-MAGAZA-YENILEME.md', 'MASAUSTU-GORSEL-YENILEME.md',
                     'NATIVE-MATERYAL-HABER-MAGAZA.md', 'YEREL-MASAUSTU.md'):
            self.assertIn('v1.2', (ROOT / 'docs' / name).read_text()[:1800])


if __name__ == '__main__':
    unittest.main()
