#!/usr/bin/env python3
"""Zero'da NetSurf; modern web motoru / daemon zorunluluğu yoktur."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_support import armv6, is_pi
from resource_policy import current_policy

PROGRAMS = {'netsurf': '/usr/bin/netsurf-gtk', 'firefox': '/usr/bin/firefox-esr'}


def choose(legacy, low_memory_pi, available, requested='auto'):
    if requested not in ('auto', *PROGRAMS):
        raise ValueError('Tarayıcı tercihi auto, netsurf veya firefox olmalı.')
    if requested == 'firefox' and legacy:
        raise ValueError('Bu Firefox sürümünün ARMv6 desteği doğrulanmadı; Zero için NetSurf seçin.')
    order = (['netsurf'] if legacy else ['netsurf', 'firefox'] if low_memory_pi else ['firefox', 'netsurf'])
    if requested != 'auto':
        order = [requested]
    for name in order:
        if name in available:
            return PROGRAMS[name]
    raise ValueError('Uygun tarayıcı bulunamadı. NetSurf (netsurf-gtk) temel haber / siteler içindir; JavaScript çalıştırmaz.')


def preference():
    path = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'oguzdows/browser.conf'
    if not path.is_file():
        return 'auto'
    if path.stat().st_size > 4096:
        raise ValueError('Tarayıcı tercih dosyası çok büyük.')
    selected = 'auto'
    for line in path.read_text().splitlines():
        key, sep, value = line.partition('#')[0].partition('=')
        if sep and key.strip() == 'browser':
            selected = value.strip()
    return selected


def main():
    if len(sys.argv) > 2:
        raise SystemExit('Bir seferde tek adres açılabilir.')
    url = sys.argv[1] if len(sys.argv) == 2 else 'file:///usr/share/oguzdows/start.html'
    if not url.startswith(('https://', 'http://', 'file:///')) or any(char in url for char in '\x00\r\n'):
        raise SystemExit('Yalnızca http, https veya yerel dosya adresi açılabilir.')
    try:
        available = {name for name, path in PROGRAMS.items() if os.access(path, os.X_OK)}
        program = choose(armv6(), is_pi() and current_policy()['memory_kib'] <= 1048576, available, preference())
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    os.execv(program, [program, url])


if __name__ == '__main__':
    main()
