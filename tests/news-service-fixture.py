#!/usr/bin/env python3
"""C GTK testi için sabit JSON; ağ / gerçek yayıncı / paket işlemi DEĞİLDİR."""
import json
import sys
import time

args = sys.argv[1:]
if args == ['cached', 'test']:
    time.sleep(60)  # Only the native test's cancellation / deadline path.
    raise SystemExit(3)
if args == ['refresh', 'test']:
    print(json.dumps({'error': 'Test bağlantı hatası; eski haberler ve önbellek korunur.'}, ensure_ascii=False))
    raise SystemExit(1)
if args != ['list']:
    print(json.dumps({'error': 'Test işçisi beklenmeyen işlem aldı.'}))
    raise SystemExit(2)
print(json.dumps({'sources': [{'id': 'test', 'name': 'Yalnızca test · Türkçe RSS', 'custom': False,
                             'url': 'https://example.org/rss'}], 'selected': 'test',
                  'source': 'Yalnızca test', 'cached_at': '2000-01-01T10:00:00Z',
                  'network_refresh_requested': False,
                  'items': [{'id': 'a' * 32, 'title': 'TEST · Çevrimdışı okunabilir Türkçe metin',
                             'body': 'TEST VERİSİ · Gerçek haber değildir.\n\nÇay, İmece, ışık, çevrimdışı okuma. <b>Bu metin markup olarak yorumlanmaz.</b>\n\n' + 'Okunabilir örnek paragraf. ' * 40,
                             'url': 'https://example.org/test', 'published': '2000-01-01'},
                            {'id': 'b' * 32, 'title': 'TEST · Büyük yazı ve kaynak atfı',
                             'body': 'TEST VERİSİ · Resim / JavaScript indirilmez.',
                             'url': '', 'published': ''}]}, ensure_ascii=False))
