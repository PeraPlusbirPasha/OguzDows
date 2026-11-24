#!/usr/bin/env python3
"""Ortak overlay'e doğru GNOME JS ABI'sini derleme zamanında yerleştir.

Root / ağ / GNOME kurulumu gerekmez. Kurulu Shell sürümü çalışma anında
zorlanmaz; metadata bilinmeyen sürümün uzantıyı yüklemesini engeller.
"""
import argparse
import json
import shutil
from pathlib import Path

UUID = 'oguzdows-glass@oguzdows.local'


def install(root, suite):
    source = Path(root) / 'usr/share/oguzdows/gnome'
    if suite == 'bookworm':
        loader, versions = 'legacy', ['43', '44']
    elif suite == 'trixie':
        loader, versions = 'modern', ['45', '46', '47', '48']
    else:
        raise ValueError('Bu tabanın GNOME ABI desteği tanımlı değil.')
    target = Path(root) / 'usr/share/gnome-shell/extensions' / UUID
    target.mkdir(parents=True, exist_ok=True)
    javascript = (source / (loader + '.js')).read_text()
    if javascript.count('// @OGUZDOWS_CORE@') != 1:
        raise ValueError('GNOME yükleyici şablonu geçersiz.')
    (target / 'extension.js').write_text(javascript.replace('// @OGUZDOWS_CORE@', (source / 'core.js').read_text()))
    for name in ('stylesheet.css', 'reflection.svg'):
        shutil.copy2(source / name, target / name)
    (target / 'metadata.json').write_text(json.dumps({'uuid': UUID, 'name': 'OğuzDows Glass',
        'description': 'Opt-in native Shell blur and bounded spring transitions; native Activities retained',
        'shell-version': versions, 'settings-schema': 'org.oguzdows.desktop', 'version': 1}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--suite', choices=('bookworm', 'trixie'), required=True)
    args = parser.parse_args()
    install(args.root, args.suite)
