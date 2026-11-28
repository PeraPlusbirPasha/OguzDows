#!/usr/bin/env python3
"""Pi ürün adını değiştir; paket araçlarının taban ID/sürüm/kod adını bozma."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

PRODUCT_KEYS = ('NAME', 'PRETTY_NAME', 'HOME_URL', 'SUPPORT_URL', 'BUG_REPORT_URL', 'LOGO')


def read_release(path):
    if path.stat().st_size > 16384:
        raise ValueError('os-release boyut sınırını aşıyor.')
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch('[A-Z_][A-Z0-9_]*', key) or key in values:
            raise ValueError('os-release anahtarı geçersiz / tekrarlı.')
        words = shlex.split(value)
        if len(words) != 1:
            raise ValueError('os-release değeri geçersiz.')
        values[key] = words[0]
    return values


def render(base, product, expected):
    for key, wanted in (('ID', expected['os_id']), ('VERSION_ID', expected['base_version_id']),
                        ('VERSION_CODENAME', expected['suite'])):
        if base.get(key) != wanted:
            raise ValueError('Pi taban kimliği sözleşmeyle eşleşmiyor: ' + key)
    result = dict(base)
    for key in PRODUCT_KEYS:
        if key in product:
            result[key] = product[key]
    result['OGUZDOWS_VERSION_ID'] = product['VERSION_ID']
    result['OGUZDOWS_CODENAME'] = product['VERSION_CODENAME']
    # Hiçbir değer shell olarak çalıştırılmaz; bu dosyayı source eden araçlar
    # için de dolar / ters tırnaklar literal yazılır.
    lines = []
    for key, value in result.items():
        if any(character in value for character in ('\n', '\r', '\x00')):
            raise ValueError('os-release değeri tek satır olmalı.')
        quoted = json.dumps(value, ensure_ascii=False).replace('$', '\\$').replace('`', '\\`')
        lines.append(key + '=' + quoted)
    return '\n'.join(lines) + '\n'


def apply(root=Path('/')):
    contract = json.loads((root / 'usr/share/oguzdows/pi-contract.json').read_text())
    expected = {**contract['architectures'][contract['arch']], 'suite': contract['suite']}
    base = read_release(root / 'usr/lib/os-release.upstream')
    product = read_release(root / 'usr/share/oguzdows/os-release')
    content = render(base, product, expected)
    destination = root / 'usr/lib/os-release'
    if destination.read_text() == content:
        return False
    descriptor, name = tempfile.mkstemp(prefix='.oguzdows-identity-', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0 or not Path('/etc/oguzdows/pi-image.json').is_file():
        print('Bu araç yalnızca Pi imajının yapılandırma chroot’u içindir.', file=sys.stderr)
        return 2
    try:
        apply()
    except (OSError, ValueError, KeyError) as error:
        print('Pi ürün / taban kimliği uygulanamadı: ' + str(error), file=sys.stderr)
        return 1
    print('OğuzDows ürün adı uygulandı; Pi OS teknik ID / sürüm / taban kod adı korundu.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
