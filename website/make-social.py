#!/usr/bin/env python3
"""Optional artwork regeneration with Pillow; not needed to build/serve the site.

Original typographic promotional card, NOT a product screenshot or AI image.
Uses the project's existing crescent/star geometry and system DejaVu Sans.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = 2
image = Image.new('RGB', (1200 * SCALE, 630 * SCALE), '#f7f5f0')
draw = ImageDraw.Draw(image)
FONT = Path('/usr/share/fonts/truetype/dejavu')


def text(x, y, value, size, color='#172936', bold=False):
    font = ImageFont.truetype(str(FONT / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')), size * SCALE)
    draw.text((x * SCALE, y * SCALE), value, font=font, fill=color)


def box(bounds, color, radius=0):
    draw.rounded_rectangle(tuple(x * SCALE for x in bounds), radius=radius * SCALE, fill=color)


box((60, 53, 93, 58), '#b82e43', 2)
text(107, 39, 'OĞUZDOWS 2.0 · AKINCI', 17, '#126b66', True)
text(55, 109, 'OğuzDows', 77, bold=True)
text(60, 238, 'Türkçe. Hafif.', 51)
text(60, 309, 'Birbirine bağlı.', 51, '#126b66')
text(63, 459, 'PC ISO   /   Raspberry Pi   /   Native launcher', 20)
box((61, 520, 392, 566), '#b82e43', 23)
text(83, 531, 'ÜCRETSİZ İNDİR · 2.0 AKINCI', 16, '#ffffff', True)
# Existing logo geometry rendered at twice the resolution for a crisp raster.
ox, oy, unit = 866, 210, 1.25

def point(x, y): return ((ox + x * unit) * SCALE, (oy + y * unit) * SCALE)

def ellipse(bounds, fill):
    a, b = point(bounds[0], bounds[1]), point(bounds[2], bounds[3])
    draw.ellipse((*a, *b), fill=fill)

box((822, 167, 1111, 456), '#e7eadd', 144)
box((ox, oy, ox + 160 * unit, oy + 160 * unit), '#b82e43', 44)
ellipse((25, 37, 111, 123), '#fff9ef')
ellipse((48, 45, 118, 115), '#b82e43')
star = [(138.4,80),(123.8,85.1),(123.5,100.5),(114.1,88.2),(99.3,92.7),(108.2,80),(99.3,67.3),(114.1,71.8),(123.5,59.5),(123.8,74.9)]
draw.polygon([point(x,y) for x,y in star], fill='#fff9ef')
text(853, 485, 'Köklerinden güç alır.', 15, '#52616b')
image = image.resize((1200, 630), Image.Resampling.LANCZOS)
image.save(ROOT / 'assets/oguzdows-akinci.jpg', quality=90, optimize=True, progressive=True)
print('Saved original 1200×630 social artwork; no screenshot/device/AI claim.')
