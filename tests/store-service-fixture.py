#!/usr/bin/env python3
"""Yalnızca --test ile derlenmiş C arayüzü: ağ / APT / Polkit çağırmaz."""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system/usr/lib/oguzdows'))
import app_catalog

state = Path(os.environ.get('OGUZDOWS_STORE_FIXTURE_STATE', '/nonexistent/fixture-not-enabled'))
removed = state.is_file()

if sys.argv[1:] == ['catalog']:
    result = {'apps': [{**item, 'installed': index < 3, 'flatpak_installed': False, 'version': 'TEST 1.0',
                        'featured': item['id'] in app_catalog.FEATURED, 'update_available': index == 0}
                       for index, item in enumerate(app_catalog.APPS)],
              'supports_apt': True, 'remote_ready': False, 'flatpak_arch': 'x86_64', 'supports_user_flatpak': True,
              'message': 'GTK kontrolü: örnek durum verisi. Paket / ağ işlemi yapılmadı.'}
elif len(sys.argv) == 4 and sys.argv[1] == 'detail':
    app_catalog.get(sys.argv[2])
    assert sys.argv[3] == 'system'
    result = {'installed': not removed, 'can_launch': not removed, 'source': 'system', 'detail': 'GTK test ayrıntısı.\nGerçek paket / kaynak sorgusu değildir.\nKurulum yapılmaz.',
              'message': 'Arayüz ayrıntı sayfası açıldı.'}
elif len(sys.argv) == 4 and sys.argv[1] == 'launch':
    app_catalog.get(sys.argv[2])
    assert sys.argv[3] == 'system'
    result = {'message': 'GTK test başlatma isteği; gerçek uygulama çalıştırılmadı.'}
elif len(sys.argv) in (4, 5) and sys.argv[1] in ('plan', 'apply', 'remove-plan', 'remove-apply'):
    assert os.environ.get('OGUZDOWS_STORE_FIXTURE_STATE'), 'No private native test state'
    app_catalog.get(sys.argv[2])
    assert sys.argv[3] == 'system'
    removing = sys.argv[1].startswith('remove-')
    if sys.argv[1].endswith('plan'):
        result = {'source': 'system', 'intent': 'remove' if removing else 'install', 'token': 'b' * 64,
                  'changes': [{'package': 'TEST-only', 'operation': 'remove' if removing else 'install'}],
                  'detail': 'FIXTURE ONLY · No APT / Flatpak / Polkit is called.',
                  'note': 'Fake plan for GTK action wiring, not a real package transaction.'}
    else:
        assert sys.argv[4] == 'b' * 64
        if removing:
            state.write_text('fixture removal, not real APT')
        else:
            state.unlink(missing_ok=True)
        result = {'source': 'system', 'message': 'TEST fixture action complete · no real packages changed.'}
else:
    raise SystemExit('Bu test işçisi kurulum, indirme veya plan başlatamaz.')
print(json.dumps(result, ensure_ascii=False))
