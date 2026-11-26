#!/usr/bin/env python3
"""Install missing / stock screenshot bindings once; keep personal commands.

Invoked by Xfce session startup, never by an appearance change. A user's
Flameshot/other binding always wins. No reset of the keyboard channel.
"""
from __future__ import annotations

import argparse
import os
import subprocess

BINDINGS = {'Print': ('fullscreen', ('xfce4-screenshooter', 'xfce4-screenshooter -f')),
            '<Shift>Print': ('region', ('xfce4-screenshooter -r',)),
            '<Alt>Print': ('window', ('xfce4-screenshooter -w',)),
            '<Shift><Super>s': ('region', ())}


def execute(argv):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          check=False, timeout=5)


def install(run=execute):
    changed, preserved = [], []
    for key, (mode, stock) in BINDINGS.items():
        base = ['xfconf-query', '-c', 'xfce4-keyboard-shortcuts', '-p', '/commands/custom/' + key]
        found = run(base)
        target = '/usr/local/bin/oguzdows-screenshot --' + mode
        current = found.stdout.strip() if found.returncode == 0 else None
        if current == target:
            continue
        if current is not None and current not in stock:
            preserved.append(key)
            continue
        argv = [*base, *(['-n'] if current is None else []), '-t', 'string', '-s', target]
        if run(argv).returncode or run(base).stdout.strip() != target:
            raise RuntimeError('Ekran yakalama kısayolu yazılamadı: ' + key)
        changed.append(key)
    return {'changed': changed, 'personal_bindings_preserved': preserved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', action='store_true', required=True)
    parser.parse_args()
    if os.getuid() == 0 or not os.environ.get('DISPLAY') or 'XFCE' not in os.environ.get('XDG_CURRENT_DESKTOP', '').upper().split(':'):
        raise ValueError('Kısayollar yalnız normal kullanıcının Xfce oturumunda tamamlanır.')
    import json
    print(json.dumps(install(), ensure_ascii=False))


if __name__ == '__main__':
    main()
