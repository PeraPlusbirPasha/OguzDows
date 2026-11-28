"""Public static site / SEO regressions, never search-rank or device acceptance."""
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from PIL import Image
from support import ROOT, load

site = load('oguzdows_public_website', 'website/build.py')


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.ids = set()
        self.jsonld = []
        self.in_jsonld = False
        self.feed(text)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        self.elements.append((tag, attrs))
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.in_jsonld = True

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld.append(json.loads(data))

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_jsonld = False


class WebsiteTests(unittest.TestCase):
    def documents(self):
        for route in site.PAGES:
            name = route + 'index.html'
            text = (ROOT / 'docs' / name).read_text()
            yield route, name, text, Document(text)

    def test_generated_pages_are_reproducible_and_do_not_touch_frozen_release_records(self):
        frozen = [ROOT / 'docs/releases/v2.0.md', ROOT / 'docs/releases/v2.0-release.json', ROOT / 'docs/AKINCI-BAGLANTI.md']
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
        outputs = site.outputs()
        self.assertEqual(len(outputs), 15)
        for name, content in outputs.items():
            self.assertNotIn('..', Path(name).parts)
            self.assertFalse(Path(name).is_absolute())
            self.assertEqual((ROOT / 'docs' / name).read_bytes(), content, name)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen})
        self.assertEqual(site.RELEASE['source_revision'], '5a44de0dde676d901a32be40d631d481e213439d')
        self.assertTrue(site.RELEASE['published'])

    def arm_fixture(self):
        # Synthetic metadata only; no production receipt is created here.
        names = site.ARM_NAMES | {'SHA256SUMS', 'pi-gen.lock.json', 'INDIRME-REHBERI.md', 'test-evidence.tar.gz', 'release-manifest.json'}
        return {'published': True, 'prerelease': False, 'tag': site.ARM_TAG, 'product_version': '2.0',
                'source_revision': 'a' * 40, 'tag_target': 'a' * 40, 'asset_count': 11,
                'pc_rebuilt': False, 'mobile_rebuilt': False, 'historical_v2_assets_modified': False,
                'release_download_audit': {'conclusion': 'success', 'all_release_assets_redownloaded_and_hashed': True,
                                           'both_images_reinspected_read_only': True, 'expected_75_source_asset_contracts_matched': True},
                'files': {name: {'size': 123, 'sha256': 'b' * 64, 'state': 'uploaded',
                                 'url': site.REPO + '/releases/download/' + site.ARM_TAG + '/' + name} for name in names}}

    def test_arm_overlay_is_per_artifact_and_never_rewrites_original_pc_mobile_or_shared_checksums(self):
        original = copy.deepcopy(site.RELEASE)
        refresh = self.arm_fixture()
        combined = site.validated_files(original, refresh)
        self.assertEqual(original, site.RELEASE)
        for name in combined:
            self.assertEqual(combined[name], refresh['files'][name] if name in site.ARM_NAMES else original['files'][name])
        self.assertEqual(site.validated_files(original, None), original['files'])
        for changes in ({'published': False}, {'tag': 'v2.0'}, {'product_version': '2.1'}, {'prerelease': True},
                        {'source_revision': original['source_revision'], 'tag_target': original['source_revision']},
                        {'pc_rebuilt': True}, {'mobile_rebuilt': True}, {'historical_v2_assets_modified': True},
                        {'release_download_audit': {}}, {'files': {}}, {'asset_count': 10}, {'tag_target': 'c' * 40}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                site.validated_files(original, {**refresh, **changes})
        for change in ({'url': site.REPO + '/releases/download/v2.0/OguzDows-rpi-armhf.img.xz'},
                       {'size': 0}, {'sha256': 'broken'}, {'state': 'pending'},
                       {'sha256': original['files']['OguzDows-rpi-armhf.img.xz']['sha256']}):
            bad = copy.deepcopy(refresh)
            bad['files']['OguzDows-rpi-armhf.img.xz'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                site.validated_files(original, bad)

    def test_arm_receipt_renders_new_pi_links_and_separate_evidence_without_relabelling_other_platforms(self):
        refresh = self.arm_fixture()
        files = site.validated_files(site.RELEASE, refresh)
        with patch.object(site, 'ARM_RELEASE', refresh), patch.object(site, 'FILES', files):
            outputs = site.outputs()
        self.assertEqual(len(outputs), 15)
        downloads = outputs['indir/index.html'].decode()
        pi = outputs['raspberry-pi/index.html'].decode()
        for arch in ('armhf', 'arm64'):
            for suffix in ('img.xz', 'img.xz.sha256'):
                name = f'OguzDows-rpi-{arch}.{suffix}'
                self.assertIn(refresh['files'][name]['url'], downloads)
                self.assertNotIn(site.RELEASE['files'][name]['url'], downloads)
        for name in ('OguzDows-amd64.iso', 'OguzDows-i386.iso', site.APK, site.WEB,
                     'SHA256SUMS', 'release-manifest.json', 'test-evidence.tar.gz'):
            self.assertIn(site.RELEASE['files'][name]['url'], downloads)
        for name in ('SHA256SUMS', 'release-manifest.json', 'test-evidence.tar.gz'):
            self.assertIn(refresh['files'][name]['url'], downloads)
            self.assertIn(refresh['files'][name]['url'], pi)
        for text in ('75 kaynak/varlık', '13 JSON', 'otomatik güncellenmez', 'Fiziksel Pi kabulü değildir'):
            self.assertIn(text, downloads)
        self.assertIn('<code>' + refresh['source_revision'][:7] + '</code>', downloads)
        self.assertNotIn('69 varlık', pi)
        graph = Document(pi).jsonld[0]['@graph']
        application, = [node for node in graph if node['@type'] == 'SoftwareApplication']
        self.assertEqual(application['downloadUrl'], refresh['files']['OguzDows-rpi-arm64.img.xz']['url'])
        for path in site.PAGES:
            self.assertLess(len(outputs[path + 'index.html']), 32_000)
        # An absent receipt must not announce a completed build or expose draft URLs.
        with patch.object(site, 'ARM_RELEASE', None), patch.object(site, 'FILES', site.RELEASE['files']):
            fallback = site.outputs()
        self.assertNotIn('/releases/download/v2.0-arm1/', fallback['indir/index.html'].decode())
        self.assertIn('69 varlık', fallback['raspberry-pi/index.html'].decode())

    def test_every_page_is_server_rendered_turkish_unique_and_canonical(self):
        titles, descriptions = set(), set()
        for route, _, text, html in self.documents():
            with self.subTest(route=route):
                self.assertIn(('html', {'lang': 'tr'}), html.elements)
                self.assertEqual(sum(tag == 'h1' for tag, _ in html.elements), 1)
                title = re.search(r'<title>(.*?)</title>', text)[1]
                self.assertNotIn(title, titles); titles.add(title)
                descriptions_on_page = [a['content'] for t, a in html.elements if t == 'meta' and a.get('name') == 'description']
                self.assertEqual(len(descriptions_on_page), 1)
                description = descriptions_on_page[0]
                self.assertTrue(90 <= len(description) <= 200)
                self.assertNotIn(description, descriptions); descriptions.add(description)
                self.assertEqual([a['href'] for t, a in html.elements if t == 'link' and a.get('rel') == 'canonical'], [site.BASE + route])
                self.assertEqual([a['content'] for t, a in html.elements if t == 'meta' and a.get('name') == 'robots'], ['index,follow,max-image-preview:large'])
                self.assertIn('id="icerik"', text)
                self.assertNotIn('<div id="root"></div>', text)
                self.assertGreater(len(re.sub(r'<[^>]+>', '', text)), 1500)
        self.assertEqual(len(titles), 7)

    def test_all_local_links_images_styles_and_explicit_anchors_resolve_under_pages_subpath(self):
        prefix = urlsplit(site.BASE).path
        origin = urlsplit(site.BASE).netloc
        for route, _, _, html in self.documents():
            for tag, attrs in html.elements:
                for attr in ('href', 'src'):
                    if attr not in attrs:
                        continue
                    value = attrs[attr]
                    with self.subTest(route=route, target=value):
                        parsed = urlsplit(value)
                        if not parsed.path and parsed.fragment:
                            self.assertIn(parsed.fragment, html.ids)
                            continue
                        if parsed.netloc and parsed.netloc != origin:
                            self.assertEqual(parsed.scheme, 'https')
                            self.assertEqual(parsed.netloc, 'github.com')
                            self.assertEqual(tag, 'a')  # No automatic third-party resource request.
                            continue
                        self.assertTrue(parsed.path.startswith(prefix), value)
                        local = ROOT / 'docs' / unquote(parsed.path[len(prefix):])
                        if parsed.path.endswith('/'):
                            local = local / 'index.html'
                        self.assertTrue(local.resolve().is_relative_to((ROOT / 'docs').resolve()))
                        self.assertTrue(local.is_file(), local)
                        if attr == 'src' or tag == 'link' and attrs.get('rel') in ('stylesheet', 'icon'):
                            self.assertFalse(parsed.netloc, 'Browser resources must use origin-relative URLs.')

    def test_sitemap_lists_exactly_seven_canonical_urls_and_no_invented_lastmod(self):
        tree = ET.parse(ROOT / 'docs/sitemap.xml')
        locs = [e.text for e in tree.findall('.//{*}loc')]
        self.assertEqual(set(locs), {site.BASE + path for path in site.PAGES})
        self.assertEqual(len(locs), 7)
        self.assertFalse(tree.findall('.//{*}lastmod'))
        robots = (ROOT / 'docs/robots.txt').read_text()
        self.assertIn('Sitemap: ' + site.BASE + 'sitemap.xml', robots)
        self.assertIn('origin root', robots)  # A project subpath is NOT an origin robots controller.
        not_found = (ROOT / 'docs/404.html').read_text()
        self.assertIn('noindex,follow', not_found)
        self.assertNotIn('rel="canonical"', not_found)
        self.assertTrue((ROOT / 'docs/.nojekyll').is_file())

    def test_social_metadata_and_visible_truthful_structured_data_without_fake_reviews(self):
        for route, _, _, html in self.documents():
            meta = {a.get('property', a.get('name')): a.get('content') for t, a in html.elements if t == 'meta'}
            self.assertEqual(meta['og:url'], site.BASE + route)
            self.assertEqual(meta['og:image'], site.BASE + 'web/oguzdows-akinci.jpg')
            self.assertEqual(meta['twitter:card'], 'summary_large_image')
            self.assertEqual(len(html.jsonld), 1)
            graph = html.jsonld[0]
            self.assertEqual(graph['@context'], 'https://schema.org')
            text = json.dumps(graph)
            for invented in ('aggregateRating', 'reviewCount', 'ratingValue', 'SearchAction', 'license', 'FAQPage'):
                self.assertNotIn(invented, text)
            nodes = graph['@graph']
            self.assertTrue(any(item['@type'] == 'WebPage' and item['url'] == site.BASE + route for item in nodes))
            for item in nodes:
                if item['@type'] == 'SoftwareApplication':
                    self.assertEqual(item['offers']['price'], '0')
                    self.assertIn(item['downloadUrl'], {f['url'] for f in site.FILES.values()})
        with Image.open(ROOT / 'docs/web/oguzdows-akinci.jpg') as image:
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.format, 'JPEG')

    def test_download_urls_hashes_sizes_and_platform_limits_come_from_published_receipt(self):
        text = (ROOT / 'docs/indir/index.html').read_text()
        for name in ('OguzDows-amd64.iso', 'OguzDows-i386.iso', 'OguzDows-rpi-armhf.img.xz', 'OguzDows-rpi-arm64.img.xz', site.APK):
            self.assertIn(site.FILES[name]['url'], text)
            self.assertIn(site.FILES[name + '.sha256']['url'], text)
            self.assertIn(site.FILES[name]['sha256'], text)
            self.assertIn(f"{site.FILES[name]['size']:,}", text)
        self.assertIn('ROM/OTA/GSI değil', text)
        self.assertIn('Zero siyah ekran', text)
        self.assertIn('Fiziksel PC/Pi/telefon kabulü yoktur', text)
        self.assertIn('statik web arşivi', text)
        phone = (ROOT / 'docs/telefon/index.html').read_text()
        for limitation in ('2205 ms', 'boş emülatör', 'debug', 'wake-word', 'SystemUI', 'fiziksel', 'GMS'):
            self.assertIn(limitation, phone)
        pi = (ROOT / 'docs/raspberry-pi/index.html').read_text()
        self.assertIn('Zero siyah ekran bildirimi açık', pi)
        self.assertIn('fiziksel Pi boot/GPU/performans ölçümü değildir', pi)

    def test_small_static_assets_and_no_analytics_cookie_remote_fonts_or_api(self):
        assets = ROOT / 'docs/web'
        self.assertLess((assets / 'site.css').stat().st_size, 48_000)
        self.assertLess((assets / 'site.js').stat().st_size, 3_000)
        self.assertLess((assets / 'oguzdows-akinci.jpg').stat().st_size, 120_000)
        for _, _, text, _ in self.documents():
            self.assertLess(len(text.encode()), 32_000)
        script = (assets / 'site.js').read_text()
        for unwanted in ('fetch(', 'XMLHttpRequest', 'document.cookie', 'localStorage', 'sendBeacon', 'eval(', 'https://'):
            self.assertNotIn(unwanted, script)
        self.assertIn('prefers-reduced-motion', (assets / 'site.css').read_text())
        self.assertIn('clipboard.writeText', script)
        self.assertIn('elle kopyalayabilirsin', script)
        self.assertIn('Escape', script)

    def test_google_verification_is_not_fabricated_and_configuration_is_bounded(self):
        self.assertEqual(site.CONFIG['google_site_verification'], '')
        for _, _, text, _ in self.documents():
            self.assertNotIn('name="google-site-verification"', text)
        with patch.dict(site.CONFIG, google_site_verification='"><script>alert(1)</script>'):
            with self.assertRaises(ValueError): site.outputs()
        with patch.object(site, 'BASE', 'http://untrusted.example/'):
            with self.assertRaises(ValueError): site.outputs()


if __name__ == '__main__':
    unittest.main()
