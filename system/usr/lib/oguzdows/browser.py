#!/usr/bin/env python3
"""ARMv6'da modern tarayıcı talimatlarını zorlamadan web uygulamasını açar."""
import os
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_support import armv6


def main():
    if len(sys.argv) > 2:
        raise SystemExit('Bir seferde tek adres açılabilir.')
    url = sys.argv[1] if len(sys.argv) == 2 else 'file:///usr/share/oguzdows/start.html'
    # Masaüstü URI alanını komut satırı seçeneği olarak yorumlatma.
    if not url.startswith(('https://', 'http://', 'file:///')):
        raise SystemExit('Yalnızca http, https veya yerel dosya adresi açılabilir.')
    program = '/usr/bin/netsurf-gtk' if armv6() else '/usr/bin/firefox-esr'
    os.execv(program, [program, url])


if __name__ == '__main__':
    main()
