"""Proje vitrini: yerel bağlantılar, küçük görseller ve dürüst yayın kimliği."""
import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from PIL import Image

from support import ROOT

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
                     'docs/releases/v1.1.md', 'raspberrypi/README.md', 'docs/ELEMENTARY-HABER.md',
                     'docs/V1.1-TEST-KANITI.md', 'docs/V1.1-GELISTIRME.md'):
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

    def test_downloads_point_to_all_four_v11_images_and_preserve_v100_history(self):
        text = (ROOT / 'README.md').read_text()
        links = re.findall(r'https://github\.com/PeraPlusbirPasha/OguzDows/releases/download/([^/]+)/([^\s)"<>]+)', text)
        self.assertEqual(set(links), {('v1.1', name) for name in (
            'OguzDows-amd64.iso', 'OguzDows-amd64.iso.sha256',
            'OguzDows-i386.iso', 'OguzDows-i386.iso.sha256',
            'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-armhf.img.xz.sha256',
            'OguzDows-rpi-arm64.img.xz', 'OguzDows-rpi-arm64.img.xz.sha256',
            'SHA256SUMS', 'release-manifest.json', 'test-evidence.tar.gz')})
        self.assertIn('releases/tag/v1.0.0', text)
        self.assertIn('docs/releases/v1.1.md', text)
        for warning in ('Zero/Zero W', 'siyah ekran', '1 GiB', '2 GiB', '4 GiB', '512 MB',
                        'fiziksel kart doğrulaması yoktur', '32 bit UEFI', 'Secure Boot', '16 GB'):
            self.assertIn(warning, text)
        for tag in ('v1.0.0', 'v1.1', 'v2.0', 'v3.0'):
            self.assertIn(tag, text)
            self.assertIn(tag, (ROOT / 'docs/SURUM-POLITIKASI.md').read_text())
        self.assertIn('yeniden adlandırılmaz', text)
        self.assertIn('gerçek kamera fotoğrafı', text)
        self.assertIn('masaüstü ekran görüntüsü değil', text)
        self.assertIn('Debian trixie', text)
        self.assertIn('Debian bookworm', text)

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
