#!/usr/bin/env python3
"""Copy four existing optimized wallpaper bytes into the native shell; no downloads or new artwork."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    output = ROOT / 'android/app/src/main/res/drawable-nodpi'
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in ('bosphorus', 'cappadocia', 'mountains', 'salt-lake'):
        source = ROOT / 'preview/public/assets' / (name + '.webp')
        destination = output / ('shell_' + name.replace('-', '_') + '.webp')
        data = source.read_bytes()
        destination.write_bytes(data)
        rows.append({'id': name, 'source': str(source.relative_to(ROOT)),
                     'native': str(destination.relative_to(ROOT)), 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'provenance': '../artwork/README.md',
                     'modification': 'Byte-identical copy of the existing optimized OğuzDows collection asset; not a real geographic photograph.'})
    (ROOT / 'android/shell-assets.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print('Four existing wallpaper assets copied byte-identically; provenance recorded.')

if __name__ == '__main__':
    main()
