"""Haber metni / XML sınırları / offline / kaynak güvenliği; gerçek ağ değildir."""
import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT, load

core = load('news_core_test', 'system/usr/lib/oguzdows/news_core.py')
service = load('news_service_test', 'system/usr/lib/oguzdows/news_service.py')

RSS = b'''<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><item><title><![CDATA[TEST &amp; News]]></title><link>https://example.org/one</link>
<description><![CDATA[<p>TEST summary</p><img src="https://example.invalid/track"><script>NEVER RUN</script>]]></description>
<pubDate>2000-01-01</pubDate></item>
<item><title>TEST two</title><link>/two</link><content:encoded><![CDATA[<p>Paragraph A</p><p>Paragraph B</p>]]></content:encoded></item>
<item><title>Duplicate link</title><link>https://example.org/one</link></item></channel></rss>'''
BASE = 'https://example.org/rss'


class NewsTests(unittest.TestCase):
    def reader(self, temporary):
        root = Path(temporary)
        sources = root / 'sources.json'
        sources.write_text(json.dumps([{'id': 'test', 'name': 'TEST only', 'url': BASE}]))
        return core.Reader(sources, root / 'config/news', root / 'cache/news')

    def test_rss_text_only_links_deduplication_attribution_and_paragraphs(self):
        items = core.parse(RSS, BASE)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['title'], 'TEST & News')
        self.assertEqual(items[0]['body'], 'TEST summary')
        self.assertNotIn('NEVER RUN', items[0]['body'])
        self.assertNotIn('track', json.dumps(items))
        self.assertEqual(items[1]['url'], 'https://example.org/two')
        self.assertEqual(items[1]['body'], 'Paragraph A\n\nParagraph B')
        self.assertEqual(items[0]['published'], '2000-01-01')

    def test_atom_namespace_xhtml_and_unsafe_links_never_become_executables(self):
        data = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom</title>
        <link rel="alternate" href="https://example.org/atom"/><summary>TEST</summary><updated>2000</updated></entry>
        <entry><title>XHTML</title><link href="javascript:alert(1)"/>
        <content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Hello</p><p>Second</p><script>NEVER SHOW</script></div></content></entry></feed>'''
        items = core.parse(data, BASE)
        self.assertEqual(items[0]['url'], 'https://example.org/atom')
        self.assertEqual(items[0]['published'], '2000')
        self.assertEqual(items[1]['url'], '')
        self.assertEqual(items[1]['body'], 'Hello\n\nSecond')
        self.assertNotIn('NEVER SHOW', items[1]['body'])
        self.assertNotIn('<', items[1]['body'])

    def test_rdf_and_link_only_feeds_honestly_report_publisher_summary_limit(self):
        data = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><item><title>TEST</title><link>https://example.org/one</link></item></rdf:RDF>'
        self.assertIn('yalnızca', core.parse(data, BASE)[0]['body'])

    def test_malformed_empty_html_dtd_entity_deep_and_huge_feeds_are_rejected(self):
        bad = [b'', b'<rss>', b'<html>not rss</html>', b'<rss/>', b'x' * (core.MAX_FEED_BYTES + 1),
               b'<!DOCTYPE rss [<!ENTITY x "EXPAND">]><rss><channel><item><title>&x;</title></item></channel></rss>',
               '<!DOCTYPE rss><rss/>'.encode('utf-16'),
               b'<rss>' + b'<a>' * 60 + b'</a>' * 60 + b'</rss>',
               b'<rss>' + b'<a/>' * 12001 + b'</rss>']
        for data in bad:
            with self.subTest(length=len(data)), self.assertRaises(core.NewsError):
                core.parse(data, BASE)

    def test_item_body_title_and_date_limits_apply_before_ui(self):
        data = ('<rss>' + ''.join(f'<item><title>{i}'+ 'T' * 300 + '</title><description>' + 'A' * 10000 + '</description><pubDate>' + 'D' * 110 + '</pubDate></item>' for i in range(65)) + '</rss>').encode()
        self.assertLess(len(data), core.MAX_FEED_BYTES)
        items = core.parse(data, BASE)
        self.assertEqual(len(items), 60)
        self.assertEqual(len(items[0]['title']), 240)
        self.assertEqual(len(items[0]['body']), 8192)
        self.assertEqual(len(items[0]['published']), 100)

    def test_cold_start_source_selection_and_add_do_not_make_a_network_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            with patch.object(core.urllib.request, 'build_opener', side_effect=AssertionError('Açılışta ağ yok')):
                self.assertEqual(reader.cached()['items'], [])
                self.assertFalse(reader.cached('test')['network_refresh_requested'])
                data = reader.add('https://example.com/news.xml', 'Kendi kaynağım')
                self.assertEqual(data['items'], [])
                self.assertTrue(data['selected'].startswith('rss-'))
                self.assertEqual(len(data['sources']), 2)
            self.assertFalse(reader.cache.exists())

    def test_successful_refresh_is_atomic_private_and_readable_offline_after_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            download = Mock(return_value=RSS)
            data = reader.refresh('test', download)
            download.assert_called_once_with(BASE)
            self.assertTrue(data['network_refresh_requested'])
            cache = reader.cache / 'test.json'
            original = cache.read_bytes()
            self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(reader.cache.stat().st_mode), 0o700)
            for result in (b'<rss>', b'<html>maintenance</html>', b''):
                with self.assertRaises(core.NewsError):
                    reader.refresh('test', lambda _url: result)
                self.assertEqual(cache.read_bytes(), original)
                self.assertEqual(reader.cached()['items'], data['items'])
            self.assertFalse(list(reader.cache.glob('.haber-*')))

    def test_sources_are_capped_not_arbitrary_files_shells_or_plain_http(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            for address in ('file:///etc/passwd', 'http://example.org/rss', 'https://user:pass@example.org/rss',
                            'https://localhost/rss', 'https://127.0.0.1/rss', 'https://[::1]/rss',
                            'https://192.168.1.1/rss', 'https://example.org:999999/', 'https://example.org/\nBad', '--refresh', None):
                with self.subTest(url=address), self.assertRaises(core.NewsError):
                    reader.add(address, 'No')
            reader.add('https://example.com/rss', 'Test')
            with self.assertRaises(core.NewsError):
                reader.add('https://example.com/rss', 'Duplicate')
            for i in range(14):
                reader.add(f'https://example.com/{i}', str(i))
            with self.assertRaises(core.NewsError):
                reader.add('https://example.com/too-many', 'Limit')
            self.assertEqual(len(reader.sources()), 16)
            for identifier in ('../../anything', '--remove', 'missing'):
                with self.assertRaises(core.NewsError):
                    reader.cached(identifier)

    def test_private_destinations_including_dns_resolution_and_redirect_downgrade_are_denied(self):
        public = Mock(return_value=[(2, 1, 6, '', ('1.1.1.1', 443))])
        self.assertEqual(core.public_destination(BASE, public), BASE)
        for ip in ('127.0.0.1', '169.254.169.254', '10.1.2.3', '::1', 'fd00::1', '0.0.0.0'):
            resolver = Mock(return_value=[(2, 1, 6, '', (ip, 443))])
            with self.subTest(ip=ip), self.assertRaises(core.NewsError):
                core.public_destination(BASE, resolver)
        redirect = core.Redirects()
        request = core.urllib.request.Request(BASE)
        for destination in ('http://example.org/downgrade', 'https://127.0.0.1/private', 'file:///etc/passwd'):
            with self.subTest(destination=destination), self.assertRaises(core.NewsError):
                redirect.redirect_request(request, None, 302, '', {}, destination)

    def test_download_enforces_timeout_size_identity_encoding_and_system_tls(self):
        class Response(io.BytesIO):
            headers = {}
        for headers, payload, good in (({}, RSS, True), ({'Content-Length': str(core.MAX_FEED_BYTES + 1)}, b'', False),
                                       ({'Content-Encoding': 'gzip'}, b'compressed', False), ({}, b'x' * (core.MAX_FEED_BYTES + 1), False)):
            response = Response(payload)
            response.headers = headers
            opener = Mock(open=Mock(return_value=response))
            with self.subTest(headers=headers), patch.object(core, 'public_destination', side_effect=lambda value: value), patch.object(core.urllib.request, 'build_opener', return_value=opener) as build:
                if good:
                    self.assertEqual(core.fetch(BASE), RSS)
                else:
                    with self.assertRaises(core.NewsError):
                        core.fetch(BASE)
                self.assertEqual(opener.open.call_args.kwargs['timeout'], 12)
                self.assertEqual(opener.open.call_args.args[0].headers['Accept-encoding'], 'identity')
                https = build.call_args.args[1]
                self.assertTrue(https._context.check_hostname)
                self.assertEqual(https._context.verify_mode, core.ssl.CERT_REQUIRED)

    def test_connection_pins_the_verified_address_but_keeps_tls_hostname(self):
        address = (core.socket.AF_INET, core.socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))
        raw = Mock(); context = Mock()
        connection = core.DirectHTTPSConnection('example.org', timeout=12, context=context)
        with patch.object(core.socket, 'getaddrinfo', return_value=[address]) as resolve, patch.object(core.socket, 'socket', return_value=raw):
            connection.connect()
        resolve.assert_called_once_with('example.org', 443, type=core.socket.SOCK_STREAM)
        raw.connect.assert_called_once_with(('1.1.1.1', 443))
        raw.settimeout.assert_called_once_with(12)
        context.wrap_socket.assert_called_once_with(raw, server_hostname='example.org')
        connection.sock = None  # Fixture Mock, no actual network socket.
        # Değişen DNS ikinci bağlantıda özel IP verirse socket bile açılmaz.
        with patch.object(core.socket, 'getaddrinfo', return_value=[(*address[:4], ('127.0.0.1', 443))]), patch.object(core.socket, 'socket') as sock, self.assertRaises(core.NewsError):
            connection.connect()
        sock.assert_not_called()
        connection.set_tunnel('example.org')
        with self.assertRaises(core.NewsError):
            connection.connect()

    def test_environment_proxies_cannot_bypass_private_address_or_tls_checks(self):
        with patch.object(core, 'public_destination', side_effect=lambda value: value), patch.object(core.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = OSError('TEST only, no network')
            with self.assertRaises(core.NewsError):
                core.fetch(BASE)
            handlers = build.call_args.args
            self.assertIsInstance(handlers[1], core.DirectHTTPSHandler)
            self.assertEqual(handlers[2].proxies, {})

    def test_custom_remove_preserves_default_sources_and_other_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            data = reader.add('https://example.com/rss', 'Personal')
            added = data['selected']
            reader.refresh(added, lambda _url: RSS)
            sentinel = reader.cache / 'keep.txt'; sentinel.write_text('Unrelated')
            self.assertEqual(reader.remove(added)['selected'], 'test')
            self.assertFalse((reader.cache / (added + '.json')).exists())
            self.assertEqual(sentinel.read_text(), 'Unrelated')
            with self.assertRaises(core.NewsError):
                reader.remove('test')

    def test_symlink_fifo_corrupt_oversized_and_foreign_cache_are_rejected(self):
        for damage in ('symlink', 'fifo', 'json', 'large', 'foreign', 'bad-link'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory() as temporary:
                reader = self.reader(temporary)
                reader.refresh('test', lambda _url: RSS)
                path = reader.cache / 'test.json'; data = json.loads(path.read_text()); path.unlink()
                if damage == 'symlink': path.symlink_to(reader.source_file)
                elif damage == 'fifo': os.mkfifo(path)
                elif damage == 'json': path.write_text('broken')
                elif damage == 'large': path.write_bytes(b'x' * (core.MAX_CACHE_BYTES + 1))
                else:
                    if damage == 'foreign': data['source_url'] = 'https://example.com/other'
                    else: data['items'][0]['url'] = 'javascript:alert(1)'
                    path.write_text(json.dumps(data))
                with self.assertRaises(core.NewsError):
                    reader.cached()
                if damage in ('symlink', 'fifo'):
                    with self.assertRaises(core.NewsError):
                        reader.refresh('test', lambda _url: RSS)

    def test_private_directory_and_atomic_write_failures_preserve_old_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            reader.refresh('test', lambda _url: RSS)
            path = reader.cache / 'test.json'; before = path.read_bytes()
            with patch.object(core.os, 'fsync', side_effect=OSError('Full')):
                with self.assertRaises(OSError): reader.refresh('test', lambda _url: RSS)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(list(reader.cache.glob('.haber-*')))
            with self.assertRaises(core.NewsError): core.atomic_json(path, {'big': 'X' * core.MAX_CACHE_BYTES})
            link = Path(temporary) / 'linked'; link.symlink_to(reader.cache, target_is_directory=True)
            with self.assertRaises(core.NewsError): core.private_directory(link)

    def test_text_cannot_use_markup_or_bidi_to_impersonate_ui(self):
        self.assertEqual(core.plain('<script>alert(1)</script><p>OK <b>bold</b></p>\u202eFake\x00'), 'OK bold\n\nFake')
        self.assertEqual(core.plain('A' * 100, 20), 'A' * 20)

    def test_service_argv_and_root_do_not_start_an_arbitrary_task(self):
        for args in ([], ['run', 'command'], ['refresh', 'test', 'extra'], ['cached', '../escape']):
            with self.subTest(args=args), patch.object(service.os, 'geteuid', return_value=0), patch.object(service, 'Reader') as reader, patch('sys.argv', ['news', *args]), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(service.main(), 1)
                reader.assert_not_called()
                self.assertIn('yönetici', json.loads(output.getvalue())['error'])
        for args in (['list'], ['cached', 'test'], ['refresh', 'test'], ['add', BASE, 'Test'], ['remove', 'test']):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as temporary:
                reader = self.reader(temporary)
                with patch.object(service.os, 'geteuid', return_value=1000), patch.object(service, 'Reader', return_value=reader), patch('sys.argv', ['news', *args]), patch.object(reader, 'refresh', return_value={'items': [], 'test': True}), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertIn(service.main(), (0, 1))
                    self.assertIsInstance(json.loads(output.getvalue()), dict)

    def test_https_handler_works_without_removed_python313_private_attribute(self):
        context = core.ssl.create_default_context()
        handler = core.DirectHTTPSHandler(context=context)
        if hasattr(handler, '_check_hostname'):
            del handler._check_hostname  # CPython 3.12 / 3.13 contract.
        handler.do_open = Mock(return_value='TLS response')
        request = core.urllib.request.Request(BASE)
        self.assertEqual(handler.https_open(request), 'TLS response')
        handler.do_open.assert_called_once_with(core.DirectHTTPSConnection, request, context=context)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, core.ssl.CERT_REQUIRED)

    def test_stream_first_launch_is_populated_but_never_disguises_demo_as_news(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            download = Mock(side_effect=AssertionError('No implicit HTTP'))
            result = reader.stream(download=download)
            download.assert_not_called()
            self.assertEqual(result['mode'], 'example')
            self.assertFalse(result['network_refresh_requested'])
            self.assertIn('Gerçek haber değildir', result['note'])
            self.assertEqual(len(result['items']), 6)
            for item in result['items']:
                self.assertTrue(item['example'])
                self.assertTrue(item['title'].startswith('ÖRNEK'))
                self.assertEqual(item['url'], '')
                self.assertEqual(item['published'], '')
                self.assertIn('yerel örnek', item['publisher'])
            self.assertFalse(reader.cache.exists())
            self.assertEqual(reader.cached()['items'], [])  # Not saved as publisher data.

    def test_stream_failure_uses_stale_cache_or_labelled_demo_and_exposes_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = self.reader(temporary)
            fail = Mock(side_effect=core.NewsError('TEST TLS failure'))
            result = reader.stream('test', network=True, download=fail)
            self.assertEqual(result['mode'], 'example')
            self.assertIn('TEST TLS failure', result['warning'])
            live = reader.stream('test', network=True, download=lambda _address: RSS)
            self.assertEqual(live['mode'], 'live')
            self.assertFalse(live['example'])
            before = (reader.cache / 'test.json').read_bytes()
            result = reader.stream('test', network=True, download=fail)
            self.assertEqual(result['mode'], 'cache')
            self.assertEqual(result['items'], live['items'])
            self.assertEqual(result['cached_at'], live['cached_at'])
            self.assertIn('TEST TLS failure', result['warning'])
            self.assertEqual((reader.cache / 'test.json').read_bytes(), before)
            (reader.cache / 'test.json').write_text('damaged')
            result = reader.stream('test')
            self.assertEqual(result['mode'], 'example')
            self.assertTrue(result['warning'])
            self.assertEqual((reader.cache / 'test.json').read_text(), 'damaged')

    def test_categories_and_demo_rotation_are_local_bounded_and_date_honest(self):
        data = RSS.replace(b'<pubDate>', b'<category>Technology</category><pubDate>')
        self.assertEqual(core.parse(data, BASE)[0]['category'], 'Bilim ve teknoloji')
        before = core.example_items(datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc))
        after = core.example_items(datetime(2026, 11, 17, 10, 1, tzinfo=timezone.utc))
        self.assertNotEqual(before[0]['id'], after[0]['id'])
        self.assertEqual({item['id'] for item in before}, {item['id'] for item in after})
        self.assertTrue(all(item['category'] in core.CATEGORIES for item in before))
        self.assertTrue(all(not item['published'] for item in after))

    def test_native_ui_is_not_a_browser_and_never_auto_refreshes(self):
        source = (ROOT / 'native/news.c').read_text()
        self.assertNotIn('webkit', source.lower())
        self.assertNotIn('system(', source)
        activate = source.split('static void activate(', 1)[1].split('#ifdef OGUZDOWS_NEWS_TEST', 1)[0]
        self.assertIn('run_service("list", NULL, NULL)', activate)
        self.assertNotIn('run_service("refresh"', activate)
        self.assertIn('g_subprocess_force_exit(worker)', source)
        self.assertIn('g_timeout_add_seconds(24', source)
        self.assertIn('CLAMP(points + change, 12, 26)', source)
        self.assertIn('gtk_text_buffer_set_text', source)
        self.assertNotIn('gtk_label_set_markup', source)
        self.assertTrue((ROOT / 'system/usr/share/applications/oguzdows-news.desktop').is_file())


if __name__ == '__main__':
    unittest.main()
