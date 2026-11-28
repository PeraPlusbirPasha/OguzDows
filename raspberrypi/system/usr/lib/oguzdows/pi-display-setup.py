#!/usr/bin/env python3
"""İmaj aşamasında LightDM ana dosyasının drop-in'i ezmesini önler.

Bu bir GPU / HDMI düzeltmesi iddiası değildir. LightDM lightdm.conf'u conf.d
sonrasında okur; yalnızca imajın varsayılan oturum / greeter anahtarları yönetilir.
Kurulu kullanıcının oturumu veya .dmrc dosyası değiştirilmez.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

VALUES = {'user-session': 'oguzdows', 'greeter-session': 'lightdm-gtk-greeter'}


def render(text):
    lines = text.splitlines()
    section = ''
    has_default = False
    found = set()
    output = []
    for line in [*lines, '[__end__]']:
        match = re.fullmatch(r'\s*\[([^\]]+)\]\s*(?:[#;].*)?', line)
        if match:
            if section == 'Seat:*':
                output.extend(key + '=' + value for key, value in VALUES.items() if key not in found)
            section = match[1]
            if section == '__end__':
                break
            if section == 'Seat:*':
                has_default = True
                found = set()
        key = line.partition('=')[0].strip()
        if (section.startswith('Seat:') or section == 'SeatDefaults') and key in VALUES and '=' in line:
            line = key + '=' + VALUES[key]
            found.add(key)
        output.append(line)
    if not has_default:
        output.extend(['', '[Seat:*]', *(key + '=' + value for key, value in VALUES.items())])
    return '\n'.join(output) + '\n'


def apply(root=Path('/')):
    path = root / 'etc/lightdm/lightdm.conf'
    if path.is_symlink():
        raise ValueError('LightDM ana dosyası bağlantı; imaj yapılandırması reddedildi.')
    original = path.read_text() if path.exists() else ''
    result = render(original)
    if result != original:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix='.oguzdows-lightdm-', dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(result)
            temporary.chmod(0o644)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return result


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Bu yapılandırma yalnızca hedef imajın root derleme aşaması içindir.')
    apply()
