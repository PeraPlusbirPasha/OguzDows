#!/usr/bin/env python3
"""Kısa ömürlü, tüm mimariler için sınırlı LZ4 zram ayarı; daemon değildir."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

from resource_policy import current_policy

MARKER = '# OğuzDows: yönetilen LZ4 zram / resources.conf'
STOCK = 'ALGO=lz4\nPERCENT=50\nPRIORITY=100\n'


def write_changed(path, content, mode=0o644):
    if path.is_symlink():
        raise ValueError('Bellek ayar dosyası bir bağlantı; değiştirilmedi: ' + str(path))
    if path.is_file() and path.read_text() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.oguzdows-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def managed_config(text):
    # Kullanıcının elle düzenlediği başka zram ayarlarını ezme. Önceki Pi ve
    # ortak varsayılan da yalnızca bilinen, tam biçimdeyse devralınır.
    body = '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip() + '\n'
    return body == STOCK or bool((text.startswith(MARKER + '\n') or text.startswith('# OğuzDows Pi: /etc/oguzdows/pi.conf dosyasından üretilir.\n')) and re.fullmatch(r'ALGO=lz4\nSIZE=[1-9][0-9]{0,4}\nPRIORITY=100\n', body))


def apply(root=Path('/')):
    settings = current_policy(root)
    path = root / 'etc/default/zramswap'
    previous = path.read_text() if path.is_file() and not path.is_symlink() else ''
    managed = not path.exists() and not path.is_symlink() or managed_config(previous)
    if managed:
        write_changed(path, MARKER + '\n' + f"ALGO=lz4\nSIZE={settings['zram_mb']}\nPRIORITY=100\n")
        for name, value in (('swappiness', settings['swappiness']), ('page-cluster', settings['page_cluster'])):
            target = root / 'proc/sys/vm' / name
            if target.exists() and not target.is_symlink():
                target.write_text(str(value) + '\n')
    settings['zram_config_managed'] = managed
    settings['note'] = ('Sınırlı LZ4; mevcut disk swap ayarlarına dokunulmadı.' if managed else
                        'Özel zramswap ayarı korundu; otomatik zram / VM ayarı uygulanmadı.')
    write_changed(root / 'run/oguzdows/resources.json', json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and os.geteuid() != 0:
        parser.error('Uygulamak için yönetici yetkisi gerekli.')
    result = apply() if args.apply else current_policy()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
