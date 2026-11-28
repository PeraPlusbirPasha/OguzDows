#!/usr/bin/env python3
"""Yalnızca Pi imajının chroot'unda Firefox politikalarını birleştir.

Paketin distribution bağlantısı korunur. Mutlak bağlantıyı build hostunda
izlemek yerine bu araç on_chroot içinden çalıştırılır; tarayıcı başlatılmaz.
"""
from __future__ import annotations

import copy
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

SOURCE = Path('/usr/share/oguzdows/firefox-policies.json')
DISTRIBUTION = Path('/usr/lib/firefox-esr/distribution')
MAX_BYTES = 1024 * 1024


def read_policy(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Firefox politika dosyası boyut sınırını aşıyor: ' + str(path))
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('policies'), dict):
        raise ValueError('Firefox politikaları nesne biçiminde olmalı: ' + str(path))
    return data


def merge(existing, desired):
    result = copy.deepcopy(existing)
    for key, value in desired.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def apply(source=SOURCE, distribution=DISTRIBUTION):
    desired = read_policy(source)
    # Mutlak / göreli paket bağlantısı ancak HEDEF chroot içindeyken çözülür.
    destination = (distribution / 'policies.json').resolve()
    existing = read_policy(destination) if destination.exists() else {'policies': {}}
    result = merge(existing, desired)
    if result == existing:
        return False
    mode = stat.S_IMODE(destination.stat().st_mode) & 0o666 if destination.exists() else 0o644
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.oguzdows-policy-', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), mode)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main():
    marker = Path('/etc/oguzdows/pi-image.json')
    if len(sys.argv) != 1 or os.geteuid() != 0 or not marker.is_file():
        print('Bu araç yalnızca Pi imajının yapılandırma chroot’u içindir.', file=sys.stderr)
        return 2
    try:
        apply()
    except (OSError, ValueError) as error:
        print('Firefox politikası uygulanamadı: ' + str(error), file=sys.stderr)
        return 1
    print('Firefox politikası birleştirildi; paket bağlantısı ve diğer ayarlar korundu.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
