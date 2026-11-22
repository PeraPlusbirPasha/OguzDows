#!/usr/bin/env python3
"""Yalnızca --test ile derlenmiş C arayüzü: ağ / APT / Polkit çağırmaz."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system/usr/lib/oguzdows'))
import app_catalog

if sys.argv[1:] == ['catalog']:
    result = {'apps': [{**item, 'installed': index < 3, 'flatpak_installed': False}
                       for index, item in enumerate(app_catalog.APPS)],
              'supports_apt': True, 'remote_ready': False, 'flatpak_arch': 'x86_64', 'supports_user_flatpak': True,
              'message': 'GTK kontrolü: örnek durum verisi. Paket / ağ işlemi yapılmadı.'}
elif len(sys.argv) == 4 and sys.argv[1] == 'detail':
    app_catalog.get(sys.argv[2])
    assert sys.argv[3] == 'system'
    result = {'installed': True, 'can_launch': True, 'source': 'system', 'detail': 'GTK test ayrıntısı.\nGerçek paket / kaynak sorgusu değildir.\nKurulum yapılmaz.',
              'message': 'Arayüz ayrıntı sayfası açıldı.'}
elif len(sys.argv) == 4 and sys.argv[1] == 'launch':
    app_catalog.get(sys.argv[2])
    assert sys.argv[3] == 'system'
    result = {'message': 'GTK test başlatma isteği; gerçek uygulama çalıştırılmadı.'}
else:
    raise SystemExit('Bu test işçisi kurulum, indirme veya plan başlatamaz.')
print(json.dumps(result, ensure_ascii=False))
