#!/usr/bin/env python3
"""Yeni manzara kaynaklarını bir kez boyutlandır / sağ altta markala.

Düzenleme aracıdır, oturumda çalışmaz. Girdi özgün ve logosuz olmalı. Paketlenen
JPEG'ler build sırasında tekrar sıkıştırılmaz; kaynak SHA-256 özeti kaydedilir.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('oguzdows_art', ROOT / 'scripts/render-assets.py')
art = importlib.util.module_from_spec(spec)
spec.loader.exec_module(art)
NAMES = ('bogaz-sabahi', 'kackar-sisi', 'kapadokya-isigi', 'oludeniz-kiyisi', 'tuz-golu-aksami', 'ani-kisi')


def brand(image):
    image = ImageOps.fit(image.convert('RGB'), (1920, 1080), method=Image.Resampling.LANCZOS).convert('RGBA')
    badge = Image.new('RGBA', (284, 72))
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle((0, 0, 283, 71), radius=18, fill=(19, 22, 32, 190))
    badge.alpha_composite(art.emblem(52), (10, 10))
    draw = ImageDraw.Draw(badge)
    draw.text((72, 21), 'OğuzDows', font=art.font(31, True), fill=art.PAPER)
    image.alpha_composite(badge, (1920 - 284 - 36, 1080 - 72 - 32))
    return image.convert('RGB')


def prepare(source, target, names=NAMES, origins=None):
    target.mkdir(parents=True, exist_ok=True)
    records = []
    for name in names:
        original = source / (name + '.png')
        if not original.is_file():
            original = source / (name + '.jpg')
        output = target / (name + '.jpg')
        if original.resolve() == output.resolve():
            raise ValueError('Özgün kaynakla çıktı aynı olamaz; logo iki kez eklenmez.')
        with Image.open(original) as image:
            source_size = image.size
            brand(image).save(output, quality=94, subsampling=0, optimize=True)
        records.append({'file': output.name, 'source_size': source_size,
                        'source_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                        'packaged_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                        'origin': (origins or {}).get(name, 'AI-generated; not a camera photograph'), 'logo': 'bottom-right'})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--names', nargs='+', default=NAMES)
    parser.add_argument('--append', action='store_true', help='Var olan diğer kayıtları koru')
    parser.add_argument('--target', type=Path, default=ROOT / 'system/usr/share/backgrounds/oguzdows')
    args = parser.parse_args()
    if any(not name or any(char not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for char in name) for name in args.names):
        raise ValueError('Güvenli görsel kimlikleri gerekli.')
    manifest = ROOT / 'artwork/landscapes.json'
    previous = json.loads(manifest.read_text()) if manifest.is_file() else []
    replaced = {name + '.jpg' for name in args.names}
    retained = [row for row in previous if row['file'] not in replaced]
    if retained and not args.append:
        raise ValueError('Diğer görselleri silmemek için --append seçeneğini kullanın.')
    records = retained + prepare(args.source, args.target, args.names)
    manifest.write_text(json.dumps(records, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
