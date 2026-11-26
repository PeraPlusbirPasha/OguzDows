#!/usr/bin/env python3
"""Bounded fixture screenshots in check annotations when artifact ZIPs cannot be read.

CI only; accepts regular images under this checkout's test-results, never a user
screen or arbitrary external path. The full PNG remains in the normal artifact.
Each small WebP is split below the annotations API's truncation threshold.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 18000
CHUNK = 3600


def preview(image, bottom=0):
    if image.width * image.height > 8_000_000:
        raise ValueError('Fixture screenshot is too large.')
    if not 0 <= bottom <= 128:
        raise ValueError('Panel strip must be at most 128px.')
    if bottom:
        image = image.crop((0, max(0, image.height - bottom), image.width, image.height))
    image = image.convert('RGB')
    image.thumbnail((900, 700), Image.Resampling.LANCZOS)
    while True:
        for quality in (80, 65, 50):
            stream = io.BytesIO()
            image.save(stream, 'WEBP', quality=quality, method=4)
            if stream.tell() <= MAX_BYTES:
                return stream.getvalue()
        image.thumbnail((max(1, image.width * 4 // 5), max(1, image.height * 4 // 5)), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--bottom', type=int, default=0, help='Only the bottom panel strip (up to 128px).')
    args = parser.parse_args()
    path = args.image.resolve()
    if os.environ.get('CI') != 'true' or not path.is_relative_to(ROOT / 'test-results'):
        parser.error('Only checkout test-results in disposable CI.')
    if not path.exists():
        print('Fixture preview unavailable; see the preceding smoke test: ' + path.name)
        return
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        parser.error('A bounded regular fixture image is required.')
    with Image.open(path) as image:
        data = preview(image, args.bottom)
    name = path.stem + (f'-bottom{args.bottom}' if args.bottom else '')
    output = path.parent / 'previews' / (name + '.webp')
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(data)
    encoded = base64.b64encode(data).decode('ascii')
    parts = [encoded[index:index + CHUNK] for index in range(0, len(encoded), CHUNK)]
    assert len(parts) <= 7  # below ten notices per step, no incomplete image
    for index, part in enumerate(parts, 1):
        print(f'::notice title=CI fixture preview {name}.png {index}/{len(parts)}::{part}', flush=True)


if __name__ == '__main__':
    main()
