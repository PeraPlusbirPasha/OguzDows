#!/usr/bin/env python3
"""C GTK testi için sabit JSON; ağ / gerçek yayıncı / paket işlemi DEĞİLDİR."""
import json
import sys
import time
from pathlib import Path

args = sys.argv[1:]
if args == ['cached', 'test']:
    time.sleep(60)  # Only the native test's cancellation / deadline path.
    raise SystemExit(3)
if args == ['refresh', 'test']:
    print(json.dumps({'error': 'Test bağlantı hatası; eski haberler ve önbellek korunur.'}, ensure_ascii=False))
    raise SystemExit(1)
if args == ['cached', 'example']:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system/usr/lib/oguzdows'))
    from news_core import example_items
    print(json.dumps({'sources': [{'id': 'test', 'name': 'TEST source'}], 'selected': 'test',
                      'source': 'TEST source', 'items': example_items(), 'mode': 'example',
                      'note': 'ÖRNEK AKIŞ · Gerçek haber değildir.', 'warning': 'TEST network unavailable'}, ensure_ascii=False))
    raise SystemExit(0)
if args != ['list']:
    print(json.dumps({'error': 'Test işçisi beklenmeyen işlem aldı.'}))
    raise SystemExit(2)
print(json.dumps({'sources': [{'id': 'test', 'name': 'Yalnızca test · Türkçe RSS', 'custom': False,
                             'url': 'https://example.org/rss'}], 'selected': 'test',
                  'source': 'Yalnızca test', 'cached_at': '2000-01-01T10:00:00Z',
                  'network_refresh_requested': False,
                  'items': [{'id': 'a' * 32, 'title': 'TEST · Çevrimdışı okunabilir Türkçe metin',
                             'body': 'TEST VERİSİ · Gerçek haber değildir.\n\nÇay, İmece, ışık, çevrimdışı okuma. <b>Bu metin markup olarak yorumlanmaz.</b>\n\n' + 'Okunabilir örnek paragraf. ' * 40,
                             'url': 'https://example.org/test', 'published': '2000-01-01', 'category': 'Gündem'},
                            {'id': 'b' * 32, 'title': 'TEST · Büyük yazı ve kaynak atfı',
                             'body': 'TEST VERİSİ · Resim / JavaScript indirilmez.',
                             'url': '', 'published': '', 'category': 'Bilim ve teknoloji'}]}, ensure_ascii=False))
