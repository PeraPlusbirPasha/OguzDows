"""Proje vitrini: yerel bağlantılar, küçük görseller ve dürüst yayın kimliği."""
import hashlib
import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from PIL import Image

from support import ROOT, load

LANDSCAPES = ('bogaz-sabahi', 'kackar-sisi', 'kapadokya-isigi',
              'oludeniz-kiyisi', 'tuz-golu-aksami', 'ani-kisi')


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ('href', 'src') and value:
                self.links.append(value)
            elif name in ('id', 'name') and value:
                self.anchors.add(value)


class ReadmeTests(unittest.TestCase):
    def test_local_markdown_html_images_and_explicit_navigation_anchors_resolve(self):
        for name in ('README.md', 'docs/TEKNIK-REHBER.md', 'docs/SURUM-POLITIKASI.md', 'docs/assets/README.md',
                     'docs/releases/v1.1.md', 'docs/releases/v1.2.md', 'docs/releases/v2.0.md',
                     'docs/releases/v2.0-arm1.md', 'docs/releases/v2.0-arm2.md',
                     'docs/ARM-GORUNUM-TESHIS.md', 'docs/WEB-VE-GORUNURLUK.md',
                     'docs/AKINCI-BAGLANTI.md', 'mobile/INSTALL.md', 'raspberrypi/README.md', 'docs/ELEMENTARY-HABER.md',
                     'docs/V1.1-TEST-KANITI.md', 'docs/V1.1-GELISTIRME.md', 'docs/YEREL-MASAUSTU.md',
                     'docs/ATOLYE-VE-MAGAZA-YENILEME.md', 'docs/MASAUSTU-GORSEL-YENILEME.md',
                     'docs/NATIVE-MATERYAL-HABER-MAGAZA.md'):
            path = ROOT / name
            text = re.sub(r'```.*?```', '', path.read_text(), flags=re.DOTALL)
            html = References()
            html.feed(text)
            links = html.links + re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', text)
            self.assertTrue(links)
            for link in links:
                with self.subTest(document=name, link=link):
                    target = urlsplit(link)
                    if target.scheme or target.netloc:
                        self.assertEqual(target.scheme, 'https')
                        continue
                    if not target.path:
                        self.assertIn(unquote(target.fragment), html.anchors)
                        continue
                    destination = (path.parent / unquote(target.path)).resolve()
                    self.assertTrue(destination.is_relative_to(ROOT))
                    self.assertTrue(destination.is_file(), destination)

    def test_current_downloads_preserve_v20_pc_mobile_and_use_only_a_published_pi_overlay(self):
        text = (ROOT / 'README.md').read_text()
        links = re.findall(r'https://github\.com/PeraPlusbirPasha/OguzDows/releases/download/([^/]+)/([^\s)"<>]+)', text)
        # Exact platform/tag mapping; historical receipts stay pinned. An ARM
        # supplement never relabels PC/APK bytes or replaces the old checksum list.
        expected = {('v2.0', name) for name in (
            'OguzDows-amd64.iso', 'OguzDows-amd64.iso.sha256',
            'OguzDows-i386.iso', 'OguzDows-i386.iso.sha256',
            'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-armhf.img.xz.sha256',
            'OguzDows-rpi-arm64.img.xz', 'OguzDows-rpi-arm64.img.xz.sha256',
            'OguzDows-Mobile-2.0-Akinci-debug.apk', 'OguzDows-Mobile-2.0-Akinci-debug.apk.sha256',
            'OguzDows-Web-2.0-Akinci.tar.gz', 'OguzDows-Web-2.0-Akinci.tar.gz.sha256',
            'SHA256SUMS', 'release-manifest.json', 'test-evidence.tar.gz')}
        # The newest actual public receipt chooses the Pi overlay, not a draft
        # label; the arm1 assertions below remain the immutable historical test.
        tag = 'v2.0-arm2' if (ROOT / 'docs/releases/v2.0-arm2-release.json').is_file() else 'v2.0-arm1'
        path = ROOT / ('docs/releases/' + tag + '-release.json')
        if path.is_file():
            receipt = json.loads(path.read_text())
            self.assertIs(receipt['published'], True)
            self.assertEqual(receipt['tag'], tag)
            pi_files = {f'OguzDows-rpi-{arch}.img.xz{suffix}' for arch in ('armhf', 'arm64') for suffix in ('', '.sha256')}
            expected -= {('v2.0', name) for name in pi_files}
            expected |= {(tag, name) for name in pi_files | {'SHA256SUMS', 'release-manifest.json', 'test-evidence.tar.gz'}}
            self.assertIn('docs/releases/' + tag + '-release.json', text)
            self.assertIn('75 birebir kaynak/varlık', text)
            self.assertIn('otomatik güncellenmez', text)
        self.assertEqual(set(links), expected)
        self.assertIn('mobile/INSTALL.md', text)
        self.assertIn('docs/AKINCI-BAGLANTI.md', text)
        self.assertIn('<h1 align="center">OğuzDows 2.0 · Akıncı</h1>', text)
        self.assertIn('https://peraplusbirpasha.github.io/OguzDows/', text[:2200])
        self.assertIn('https://peraplusbirpasha.github.io/OguzDows/indir/', text[:2200])
        self.assertIn('debug uygulamasıdır, ROM/OTA/GSI değildir', text)
        self.assertIn('releases/tag/v1.0.0', text)
        self.assertIn('docs/releases/v1.1.md', text)
        self.assertIn('releases/tag/v1.1', text)
        self.assertIn('docs/releases/v1.2.md', text)
        for warning in ('Zero/Zero W', 'siyah ekran', '1 GiB', '2 GiB', '4 GiB', '512 MB',
                        'fiziksel kart doğrulaması yoktur', '32 bit UEFI', 'Secure Boot', '16 GB'):
            self.assertIn(warning, text)
        for tag in ('v1.0.0', 'v1.1', 'v1.2', 'v2.0', 'v3.0'):
            self.assertIn(tag, text)
            self.assertIn(tag, (ROOT / 'docs/SURUM-POLITIKASI.md').read_text())
        self.assertIn('yeniden adlandırılmaz', text)
        self.assertIn('gerçek kamera fotoğrafı', text)
        self.assertIn('masaüstü ekran görüntüsü değil', text)
        self.assertIn('Debian trixie', text)
        self.assertIn('Debian bookworm', text)

    def test_arm_receipt_never_claims_rebuilt_pc_mobile_historical_mutation_or_physical_acceptance(self):
        path = ROOT / 'docs/releases/v2.0-arm1-release.json'
        if not path.is_file():
            self.assertNotIn('/releases/download/v2.0-arm1/', (ROOT / 'README.md').read_text())
            return  # Source scaffolding only: no publication is inferred from this branch.
        record = json.loads(path.read_text())
        original = json.loads((ROOT / 'docs/releases/v2.0-release.json').read_text())
        source = 'c5063ee8b558cb6c8af8301143cf3ce02106e2aa'
        self.assertEqual(record['source_revision'], source)
        self.assertEqual(record['tag_target'], source)
        self.assertEqual(record['release_id'], 461532378)
        self.assertEqual(record['tag'], 'v2.0-arm1')
        self.assertEqual(record['product_version'], '2.0')
        self.assertIs(record['published'], True)
        self.assertIs(record['prerelease'], False)
        self.assertIs(record['latest_at_publication'], False)
        for name in ('pc_rebuilt', 'mobile_rebuilt', 'historical_v2_assets_modified',
                     'physical_boot_verified', 'pi_performance_measured', 'images_repacked_by_publisher'):
            self.assertIs(record[name], False)
        expected = {f'OguzDows-rpi-{arch}.{suffix}' for arch in ('armhf', 'arm64')
                    for suffix in ('img.xz', 'img.xz.sha256', 'packages.txt')}
        expected |= {'SHA256SUMS', 'pi-gen.lock.json', 'INDIRME-REHBERI.md', 'release-manifest.json', 'test-evidence.tar.gz'}
        self.assertEqual(record['asset_count'], 11)
        self.assertEqual(set(record['files']), expected)
        for name, item in record['files'].items():
            self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(item['size'], 0)
            self.assertEqual(item['state'], 'uploaded')
            self.assertEqual(item['url'], 'https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0-arm1/' + name)
            if name.endswith('.img.xz'):
                self.assertGreater(item['size'], 100_000_000)
                self.assertNotEqual(item['sha256'], original['files'][name]['sha256'])
        source_run = record['source_run']
        self.assertEqual(source_run['id'], 46142709227)
        self.assertEqual(source_run['source_revision'], source)
        self.assertEqual(source_run['conclusion'], 'success')
        self.assertEqual(len(source_run['jobs']), 3)
        self.assertTrue(all(job['conclusion'] == 'success' for job in source_run['jobs']))
        self.assertEqual(set(record['target_runtime_reports']), {'armhf', 'arm64'})
        for arch, report in record['target_runtime_reports'].items():
            self.assertEqual(report['arch'], arch)
            self.assertEqual(report['feature_presence']['asset_hashes'], 75)
            self.assertEqual(len(report['feature_presence']['groups']), 13)
            self.assertEqual(report['errors'], [])
            self.assertEqual(report['full_session']['uid'], 65534)
            appearance = report['full_session']['appearance']
            self.assertEqual(appearance['schema'], 1)
            for name in ('gtk3_dark_light_reloaded', 'packaged_wallpapers', 'wallpaper_pixels_changed'):
                self.assertIs(appearance[name], True)
            for name in ('settings_backend_mocked', 'physical_device', 'performance_measurement',
                         'welcome_callbacks_tested', 'gtk4_portal_tested'):
                self.assertIs(appearance[name], False)
            self.assertEqual(len(set(appearance['wallpaper_pixel_sha256'])), 2)
        audit = record['release_download_audit']
        self.assertEqual(audit['conclusion'], 'success')
        self.assertEqual(audit['evidence_file_count'], 13)
        self.assertIs(audit['release_modified'], False)
        self.assertNotEqual(audit['run_id'], record['release_transfer']['run_id'])
        self.assertEqual(audit['download_access'], 'asset-scoped-signed-GET')
        self.assertIs(audit['live_draft_metadata_rechecked_inside_audit'], False)
        self.assertIs(audit['publication_collector_must_recheck_live_metadata'], True)
        access = record['draft_read_access_and_live_metadata_recheck']
        self.assertEqual(access['audit_job_permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertEqual(access['helper_permissions'], {'contents': 'write', 'actions': 'read'})
        self.assertIs(access['helper_only_GETs_no_Release_mutation'], True)
        self.assertIs(access['bearer_token_exported_to_auditor'], False)
        self.assertIs(access['live_metadata_rechecked_after_audit_by_collector'], True)
        self.assertRegex(access['live_release_snapshot_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(access['live_release_snapshot_sha256'], audit['draft_snapshot_sha256'])
        self.assertIs(access['earlier_rejected_attempt']['accepted'], False)
        for name in ('all_release_assets_redownloaded_and_hashed', 'both_images_reinspected_read_only',
                     'expected_75_source_asset_contracts_matched'):
            self.assertIs(audit[name], True)
        self.assertEqual(set(record['image_identity']), {'armhf', 'arm64'})
        for arch, identity in record['image_identity'].items():
            self.assertEqual(identity['build']['arch'], arch)
            self.assertEqual(identity['build']['source_revision'], source)
            self.assertIs(identity['build']['source_dirty'], False)
            self.assertIs(identity['existing_pi_verifier_passed'], True)
            self.assertIs(identity['embedded_runtime_matches_raw_artifact'], True)
        self.assertEqual(len(record['public_download_checks']), 11)
        self.assertTrue(all(item['unauthenticated'] and item['status'] in (200, 302, 307)
                            and not item['full_bytes_downloaded_by_this_head_check'] for item in record['public_download_checks']))
        for tag, count in (('v2.0', 26), ('v1.2', 17), ('v1.1', 17), ('v1.0.0', 8)):
            before = record['previous_releases_preserved'][tag]
            self.assertEqual(before['asset_count'], count)
            self.assertIs(before['tag_body_asset_ids_sizes_hashes_unchanged'], True)
        self.assertIs(record['full_product_bytes_hashed_in_GitHub_runner'], True)
        self.assertIs(record['full_product_bytes_downloaded_or_independently_hashed_in_local_sandbox'], False)
        rejected = record['newer_mobile_ci_not_accepted']
        self.assertTrue({140967180202, 140971721566, 140974464222, 140977645533} <= {item['job_id'] for item in rejected})
        for item in rejected:
            self.assertEqual(item['conclusion'], 'failure')
            self.assertIs(item['accepted'], False)
            self.assertIs(item['replaces_original_apk_acceptance'], False)
            self.assertIs(item['root_cause_confirmed'], False)

    def test_current_arm2_receipt_binds_the_new_turkish_fix_native_evidence_and_independent_image_audit(self):
        path = ROOT / 'docs/releases/v2.0-arm2-release.json'
        if not path.is_file():
            self.assertNotIn('/releases/download/v2.0-arm2/', (ROOT / 'README.md').read_text())
            return  # Preparing a new draft is not publication acceptance.
        record = json.loads(path.read_text())
        arm1 = json.loads((ROOT / 'docs/releases/v2.0-arm1-release.json').read_text())
        original = json.loads((ROOT / 'docs/releases/v2.0-release.json').read_text())
        native_path = ROOT / 'docs/evidence/arm-xfconf-locale.json'
        native = json.loads(native_path.read_text())
        validator = load('readme_arm2_acceptance', 'scripts/release-arm-refresh.py')
        source = '6ec8f55054e8eddde7fb0e74d62c4332a2cd7e35'
        self.assertEqual(record['source_revision'], source)
        self.assertEqual(record['tag_target'], source)
        self.assertEqual(record['release_id'], 461704890)
        self.assertEqual(record['tag'], 'v2.0-arm2')
        self.assertEqual(record['product_version'], '2.0')
        self.assertIs(record['published'], True)
        self.assertIs(record['prerelease'], False)
        self.assertIs(record['latest_at_publication'], False)
        self.assertEqual(record['xfconf_locale_runtime_schema'], 1)
        for key in ('pc_rebuilt', 'mobile_rebuilt', 'historical_v2_assets_modified', 'historical_arm1_assets_modified',
                    'images_repacked_by_publisher', 'physical_boot_verified', 'pi_performance_measured'):
            self.assertIs(record[key], False)
        self.assertEqual(record['native_locale_evidence'], {
            'path': 'docs/evidence/arm-xfconf-locale.json', 'sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
            'run_id': 46165804788, 'source_revision': source, 'conclusion': 'success'})
        validator.validate_native_evidence(native, source)
        self.assertIs(native['acceptance']['results'][0]['report']['xfconf_locale']['unfixed_reader_error_reproduced'], True)
        self.assertEqual(record['asset_count'], 11)
        self.assertEqual(set(record['files']), set(arm1['files']))
        for name, item in record['files'].items():
            self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(item['size'], 0)
            self.assertEqual(item['state'], 'uploaded')
            self.assertEqual(item['url'], 'https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v2.0-arm2/' + name)
            if name.endswith('.img.xz'):
                self.assertGreater(item['size'], 100_000_000)
                self.assertNotIn(item['sha256'], (arm1['files'][name]['sha256'], original['files'][name]['sha256']))
        run = record['source_run']
        self.assertEqual(run['id'], 46165807516)
        self.assertEqual(run['source_revision'], source)
        self.assertEqual(run['conclusion'], 'success')
        self.assertEqual(len(run['jobs']), 3)
        self.assertTrue(all(job['conclusion'] == 'success' for job in run['jobs']))
        self.assertEqual(set(record['target_runtime_reports']), {'armhf', 'arm64'})
        relay = record['target_runtime_json_byte_relay']
        self.assertEqual(relay['conclusion'], 'success')
        self.assertEqual(relay['permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertIs(relay['artifact_code_executed'], False)
        self.assertLessEqual(sum(item['parts'] for item in relay['reports'].values()), 10)
        rejected_relays = record['target_runtime_json_byte_relay_rejected']
        self.assertEqual({item['id'] for item in rejected_relays}, {46171886371, 46172114390})
        self.assertTrue(all(item['accepted'] is False for item in rejected_relays))
        for arch, report in record['target_runtime_reports'].items():
            self.assertEqual(report['source_revision'], source)
            self.assertEqual(report['feature_presence']['asset_hashes'], 75)
            self.assertEqual(len(report['feature_presence']['groups']), 13)
            self.assertEqual(report['errors'], [])
            session = report['full_session']
            self.assertEqual(session['uid'], 65534)
            self.assertGreaterEqual(session['stable_samples'], 5)
            self.assertEqual(session['errors'], [])
            appearance = session['appearance']
            for key in ('gtk3_dark_light_reloaded', 'packaged_wallpapers', 'wallpaper_pixels_changed'):
                self.assertIs(appearance[key], True)
            for key in ('settings_backend_mocked', 'physical_device', 'performance_measurement',
                        'welcome_callbacks_tested', 'gtk4_portal_tested'):
                self.assertIs(appearance[key], False)
            validator.validate_locale(appearance['xfconf_locale'], reproduced=True)
            self.assertEqual(len(set(appearance['wallpaper_pixel_sha256'])), 2)
            raw = relay['reports']['OguzDows-Pi-gunluk-' + arch]
            artifact = run['artifacts']['OguzDows-Pi-gunluk-' + arch]
            self.assertEqual(raw['encoding'], 'zlib-base64')
            self.assertEqual(raw['source_run'], run['id'])
            self.assertEqual(raw['source_revision'], source)
            self.assertEqual(raw['artifact_id'], artifact['id'])
            self.assertEqual(raw['artifact_digest'], artifact['digest'])
            self.assertRegex(raw['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(raw['bytes'], 0)
            identity = record['image_identity'][arch]
            self.assertEqual(identity['build']['arch'], arch)
            self.assertEqual(identity['build']['source_revision'], source)
            self.assertIs(identity['build']['source_dirty'], False)
            self.assertIs(identity['existing_pi_verifier_passed'], True)
            self.assertIs(identity['embedded_runtime_matches_raw_artifact'], True)
        audit = record['release_download_audit']
        self.assertEqual(audit['conclusion'], 'success')
        self.assertEqual(audit['evidence_file_count'], 13)
        self.assertIs(audit['release_modified'], False)
        self.assertNotEqual(audit['run_id'], record['release_transfer']['run_id'])
        self.assertEqual(record['publisher_revision'], audit['publisher_revision'])
        self.assertNotEqual(record['publisher_revision'], source)
        for key in ('all_release_assets_redownloaded_and_hashed', 'both_images_reinspected_read_only',
                    'expected_75_source_asset_contracts_matched', 'turkish_xfconf_runtime_gate_matched',
                    'native_ARM64_Turkish_Welcome_evidence_matched'):
            self.assertIs(audit[key], True)
        access = record['draft_read_access_and_live_metadata_recheck']
        self.assertEqual(access['audit_job_permissions'], {'contents': 'read', 'actions': 'read'})
        self.assertIs(access['helper_only_GETs_no_Release_mutation'], True)
        self.assertIs(access['bearer_token_exported_to_auditor'], False)
        self.assertIs(access['live_metadata_rechecked_after_audit_by_collector'], True)
        self.assertEqual(access['live_release_snapshot_sha256'], audit['draft_snapshot_sha256'])
        self.assertEqual(len(record['public_download_checks']), 11)
        self.assertTrue(all(item['unauthenticated'] and item['status'] in (200, 302, 307)
                            and not item['full_bytes_downloaded_by_this_head_check'] for item in record['public_download_checks']))
        self.assertIs(record['public_release_tag_check']['original_v2_remains_latest'], True)
        for tag, count in (('v2.0-arm1', 11), ('v2.0', 26), ('v1.2', 17), ('v1.1', 17), ('v1.0.0', 8)):
            preserved = record['previous_releases_preserved'][tag]
            self.assertEqual(preserved['asset_count'], count)
            self.assertIs(preserved['tag_body_asset_ids_sizes_hashes_unchanged'], True)
        for document in ('README.md', 'raspberrypi/README.md', 'docs/ARM-GORUNUM-TESHIS.md', 'docs/TEKNIK-REHBER.md'):
            text = (ROOT / document).read_text()
            self.assertIn('/releases/tag/v2.0-arm2', text)
            self.assertNotIn('/releases/download/v2.0-arm1/', text)
        self.assertIn('Xfce dizi ayarı güvenle okunamadı', (ROOT / 'README.md').read_text())

    def test_published_v11_record_keeps_real_image_hashes_source_and_test_limits(self):
        record = json.loads((ROOT / 'docs/releases/v1.1-release.json').read_text())
        revision = '29f7738534cd00bd87887f530355ef45e01eb28c'
        self.assertEqual(record['source_revision'], revision)
        self.assertEqual(record['tag_target'], revision)
        self.assertEqual(record['release_id'], 455583593)
        self.assertEqual(record['tag'], 'v1.1')
        self.assertTrue(record['published'])
        self.assertTrue(record['latest'])
        self.assertFalse(record['images_rebuilt_or_repacked'])
        self.assertEqual(record['asset_count'], 17)
        self.assertEqual(len(record['files']), 17)
        for name in ('OguzDows-amd64.iso', 'OguzDows-i386.iso', 'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-arm64.img.xz'):
            self.assertIn(name, record['files'])
            self.assertGreater(record['files'][name]['size'], 900_000_000)
        for name, data in record['files'].items():
            self.assertRegex(data['sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(data['state'], 'uploaded')
            self.assertEqual(data['url'], 'https://github.com/PeraPlusbirPasha/OguzDows/releases/download/v1.1/' + name)
        self.assertEqual(set(record['image_identity']), {'amd64', 'i386', 'rpi-armhf', 'rpi-arm64'})
        for identity in record['image_identity'].values():
            self.assertEqual(identity['build']['source_revision'], revision)
            self.assertEqual(identity['version'], '1.1')
        self.assertTrue(record['release_download_audit']['all_17_release_assets_redownloaded_and_hashed'])
        self.assertEqual(record['release_download_audit']['raw_json_evidence_count'], 21)
        self.assertFalse(record['release_download_audit']['release_modified'])
        self.assertFalse(record['physical_boot_verified'])
        self.assertFalse(record['pi_performance_measured'])
        self.assertIn('black screen', record['known_issue'])
        self.assertTrue(record['v1_0_0_preserved']['unchanged'])
        self.assertEqual(record['v1_0_0_preserved']['asset_count'], 8)

    def test_banner_is_static_and_all_six_gallery_previews_are_small_local_derivatives(self):
        banner = ROOT / 'docs/assets/oguzdows-banner.svg'
        root = ET.parse(banner).getroot()
        self.assertEqual(root.attrib['viewBox'], '0 0 1600 560')
        self.assertLess(banner.stat().st_size, 20_000)
        banner_text = ' '.join(root.itertext())
        self.assertIn('OğuzDows 2.0 · Akıncı', banner_text)
        self.assertIn('AKINCI · 2.0', banner_text)
        self.assertNotIn('AY YILDIZ · 1.0', banner_text)
        for element in root.iter():
            self.assertNotIn(element.tag.rsplit('}', 1)[-1], ('script', 'foreignObject', 'image'))
            for name, value in element.attrib.items():
                self.assertFalse(name.lower().startswith('on'))
                if name.rsplit('}', 1)[-1] == 'href':
                    self.assertTrue(value.startswith('#'))
        total = 0
        for name in LANDSCAPES:
            path = ROOT / 'docs/assets' / (name + '.jpg')
            total += path.stat().st_size
            with self.subTest(image=name), Image.open(path) as image:
                self.assertEqual(image.size, (480, 270))
                self.assertEqual(image.format, 'JPEG')
            self.assertTrue((ROOT / 'system/usr/share/backgrounds/oguzdows' / (name + '.jpg')).is_file())
        self.assertLess(total, 200_000)

    def test_detailed_installer_and_legacy_device_safeguards_are_kept_in_technical_guide(self):
        guide = (ROOT / 'docs/TEKNIK-REHBER.md').read_text()
        for preserved in ('mbr-before-active-', 'quit-at-end: false',
                          'EFI/BOOT/BOOTX64.EFI', '--no-download --no-remove',
                          'No bootable device', 'broadcom-sta-dkms'):
            self.assertIn(preserved, guide)
        self.assertIn('../README.md', guide)
        self.assertIn('MASAUSTU-TEST-KANITI.md', guide)
        self.assertNotIn('](docs/', guide)


if __name__ == '__main__':
    unittest.main()
