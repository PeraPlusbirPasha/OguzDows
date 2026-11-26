"""Publisher thumbnail metadata, raster/DNS/cache limits; never a live network."""
import io
import json
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from support import ROOT, load

core = load('news_images_test_core', 'system/usr/lib/oguzdows/news_core.py')
BASE = 'https://example.org/rss'
RSS = b'''<rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
<item><title>TEST media</title><description>TEST summary</description><link>/article</link>
<media:thumbnail url="/photo.png"/></item></channel></rss>'''


def raster(size=(640, 360), mode='RGB', kind='PNG'):
    output = io.BytesIO(); Image.new(mode, size, '#438899').save(output, kind); return output.getvalue()


class ThumbnailTests(unittest.TestCase):
    def test_only_explicit_publisher_raster_metadata_not_html_trackers_or_video(self):
        self.assertEqual(core.parse(RSS, BASE)[0]['image_url'], 'https://example.org/photo.png')
        for metadata, expected in ((b'<enclosure type="image/jpeg" url="https://cdn.example.org/photo.jpg"/>', 'https://cdn.example.org/photo.jpg'),
                                   (b'<media:content medium="image" url="/full.webp"/>', 'https://example.org/full.webp'),
                                   (b'<media:content type="video/mp4" url="/video.mp4"/>', None),
                                   (b'<enclosure type="image/png" url="http://example.org/insecure.png"/>', None),
                                   (b'<media:thumbnail url="https://127.0.0.1/private.png"/>', None),
                                   (b'<media:thumbnail url="file:///etc/passwd"/>', None)):
            data = RSS.replace(b'<media:thumbnail url="/photo.png"/>', metadata)
            self.assertEqual(core.parse(data, BASE)[0].get('image_url'), expected)
        data = RSS.replace(b'<media:thumbnail url="/photo.png"/>', b'').replace(b'TEST summary', b'&lt;img src="https://example.org/track"&gt;Text')
        self.assertNotIn('image_url', core.parse(data, BASE)[0])
        self.assertNotIn('track', json.dumps(core.parse(data, BASE)))

    def test_normalized_jpeg_is_fixed_size_and_metadata_is_not_copied(self):
        for mode in ('RGB', 'RGBA'):
            data = core.thumbnail(raster(mode=mode))
            self.assertLessEqual(len(data), core.MAX_THUMBNAIL_BYTES)
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual(image.format, 'JPEG'); self.assertEqual(image.size, (320, 180))
                self.assertEqual(image.mode, 'RGB'); self.assertEqual(dict(image.getexif()), {})

    def test_bad_tiny_svg_animated_large_bytes_and_decompression_bombs_are_rejected(self):
        output = io.BytesIO()
        Image.new('RGB', (100, 100)).save(output, 'GIF', save_all=True, append_images=[Image.new('RGB', (100, 100), 'red')], duration=20, loop=0)
        def chunk(kind, data): return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
        oversized_pixels = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 4000, 4000, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'')) + chunk(b'IEND', b'')
        for data in (b'bad', b'<svg/>', b'x' * (core.MAX_IMAGE_BYTES + 1), raster((1, 1)), output.getvalue(), oversized_pixels):
            with self.subTest(size=len(data)), self.assertRaises(core.NewsError): core.thumbnail(data)

    def test_images_use_the_same_verified_https_dns_and_redirect_transport(self):
        with patch.object(core, 'fetch', return_value=b'JPEG') as fetch:
            self.assertEqual(core.fetch_image('https://example.org/a.jpg', timeout=1.5), b'JPEG')
            fetch.assert_called_once_with('https://example.org/a.jpg', maximum=262144,
                                          accept='image/jpeg, image/png, image/webp', timeout=1.5)

    def test_at_most_six_thumbnails_per_explicit_refresh_then_cached_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            items = [{'image_url': f'https://example.org/photo{i}.png'} for i in range(12)]
            download = Mock(return_value=raster())
            core.cache_thumbnails(cache, items, download, clock=lambda: 0)
            self.assertEqual(download.call_count, 6)
            self.assertEqual(sum('thumbnail' in item for item in items), 6)
            for item in items[:6]:
                path = Path(core.thumbnail_path(cache, item['thumbnail']))
                self.assertTrue(path.is_file()); self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            download.reset_mock(); core.cache_thumbnails(cache, items[:6], download, clock=lambda: 0)
            download.assert_not_called()

    def test_wall_time_budget_and_errors_do_not_discard_readable_articles(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            items = [{'image_url': 'https://example.org/one.png', 'title': 'Keep text'}]
            download = Mock(side_effect=core.NewsError('TEST TLS image failure'))
            core.cache_thumbnails(cache, items, download)
            self.assertEqual(items[0]['title'], 'Keep text'); self.assertNotIn('thumbnail', items[0])
            clock = Mock(side_effect=[0, 1, 2, 7])
            core.cache_thumbnails(cache, items, Mock(return_value=raster()), clock)
            self.assertNotIn('thumbnail', items[0]); self.assertFalse((cache / 'thumbnails').exists())

    def test_cache_paths_are_hash_only_normal_owned_jpegs_and_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary); folder = cache / 'thumbnails'; folder.mkdir()
            foreign = cache / 'personal.jpg'; foreign.write_bytes(core.thumbnail(raster()))
            name = core.thumbnail_name('https://example.org/one.png')
            target = folder / name; target.symlink_to(foreign)
            self.assertEqual(core.thumbnail_path(cache, name), '')
            for value in ('../personal.jpg', str(foreign), 'x.jpg', None): self.assertEqual(core.thumbnail_path(cache, value), '')
            target.unlink(); os.mkfifo(target)
            self.assertEqual(core.thumbnail_path(cache, name), '')
            target.unlink(); target.write_bytes(b'not jpeg')
            self.assertEqual(core.thumbnail_path(cache, name), '')
            target.unlink(); folder.rmdir(); folder.symlink_to(cache, target_is_directory=True)
            self.assertEqual(core.thumbnail_path(cache, name), '')
            self.assertTrue(foreign.is_file())

    def test_image_cache_has_a_hard_count_budget_and_keeps_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary); folder = cache / 'thumbnails'; folder.mkdir()
            data = core.thumbnail(raster())
            for index in range(70): (folder / (f'{index:064x}.jpg')).write_bytes(data)
            keep = folder / 'my-picture.jpg'; keep.write_bytes(b'Personal')
            core.cache_thumbnails(cache, [{'image_url': 'https://example.org/new.png'}], lambda *_args, **_kwargs: raster())
            self.assertEqual(len([p for p in folder.iterdir() if len(p.name) == 68]), 64)
            self.assertEqual(keep.read_bytes(), b'Personal')

    def test_reader_text_only_and_cold_launch_never_download_images_and_offline_cache_keeps_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'sources.json'
            source.write_text(json.dumps([{'id': 'test', 'name': 'TEST', 'url': BASE}]))
            reader = core.Reader(source, root / 'config', root / 'cache')
            download = Mock(return_value=raster())
            data = reader.refresh('test', lambda _url: RSS, images=False, image_download=download)
            download.assert_not_called(); self.assertNotIn('image_path', data['items'][0])
            data = reader.refresh('test', lambda _url: RSS, image_download=download)
            self.assertEqual(download.call_count, 1)
            self.assertTrue(Path(data['items'][0]['image_path']).is_file())
            with patch.object(core.urllib.request, 'build_opener', side_effect=AssertionError('No cold-start HTTP')):
                self.assertEqual(reader.cached()['items'], data['items'])
            path = reader.cache / 'test.json'; document = json.loads(path.read_text())
            self.assertNotIn('image_path', document['items'][0])
            document['items'][0]['thumbnail'] = '../escape.jpg'; path.write_text(json.dumps(document))
            with self.assertRaises(core.NewsError): reader.cached()

    def test_native_single_click_reader_validates_rasters_and_has_a_text_only_switch(self):
        source = (ROOT / 'native/news.c').read_text()
        for marker in ('gtk_list_box_set_activate_on_single_click', 'image_size(', 'O_NOFOLLOW', 'cached_picture(', 'text-only', 'haber fotoğrafı değildir'):
            self.assertIn(marker, source)
        self.assertIn('Haberi oku', source)
        self.assertNotIn('soup_session', source)


if __name__ == '__main__':
    unittest.main()
