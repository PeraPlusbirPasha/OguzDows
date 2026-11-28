#!/usr/bin/env python3
"""Dört özgün kültür çizimi; çevrimdışı geliştirme aracı, oturum servisi değil.

Fotoğraf / AI görüntüsü değildir. 1920×1080 tasarımlar Pillow vektör
primitiflerinden 2x örneklenir; markalama prepare-landscapes.py'de yapılır.
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H, S = 1920, 1080, 2
NAMES = ('vapur', 'safranbolu', 'pamukkale-teraslari', 'anadolu-gecesi')


class Canvas:
    def __init__(self, top, bottom):
        def rgb(color):
            return tuple(bytes.fromhex(color.lstrip('#')))
        a, b = rgb(top), rgb(bottom)
        line = Image.new('RGB', (1, H * S))
        line.putdata([tuple(round(x + (y - x) * n / (H * S - 1)) for x, y in zip(a, b)) for n in range(H * S)])
        self.image = line.resize((W * S, H * S))
        self.draw = ImageDraw.Draw(self.image)

    def polygon(self, points, fill):
        self.draw.polygon([(round(x * S), round(y * S)) for x, y in points], fill=fill)

    def ellipse(self, box, fill):
        self.draw.ellipse(tuple(round(x * S) for x in box), fill=fill)

    def rectangle(self, box, fill):
        self.draw.rectangle(tuple(round(x * S) for x in box), fill=fill)

    def line(self, points, fill, width=2):
        self.draw.line([(round(x * S), round(y * S)) for x, y in points], fill=fill, width=width * S, joint='curve')

    def wave(self, base, height, frequency, color, phase=0):
        points = [(x, base + math.sin(x / frequency + phase) * height) for x in range(-20, W + 21, 12)]
        self.polygon(points + [(W + 20, H), (-20, H)], color)

    def finish(self):
        return self.image.resize((W, H), Image.Resampling.LANCZOS)


def vapur():
    art = Canvas('#ddccc4', '#ffd9b1')
    art.ellipse((1390, 150, 1600, 360), '#f9e9c8')
    art.wave(510, 28, 300, '#a6b7bc')
    # Uzak kent, sade ve özgün geometrik siluet.
    for x, y, width in ((1010, 482, 82), (1100, 455, 100), (1230, 470, 90), (1380, 460, 130), (1540, 488, 120), (1710, 450, 110)):
        art.rectangle((x, y, x + width, 540), '#839ca8')
        art.ellipse((x, y - 23, x + width, y + 25), '#839ca8')
    art.wave(560, 7, 160, '#427e92')
    art.wave(720, 12, 240, '#34758c', 1)
    art.wave(920, 18, 340, '#23667e', 2)
    # Vapur; çizim gerçek bir şirkete / gemiye ait değildir.
    art.polygon([(1030, 705), (1750, 705), (1665, 825), (1130, 825)], '#193f56')
    art.polygon([(1050, 705), (1740, 705), (1715, 742), (1075, 742)], '#f8f1df')
    art.rectangle((1150, 568, 1630, 704), '#f8f1df')
    art.rectangle((1210, 528, 1510, 568), '#f8f1df')
    for x in range(1180, 1620, 49):
        art.rectangle((x, 588, x + 26, 625), '#23495e')
        art.rectangle((x, 650, x + 26, 679), '#23495e')
    art.rectangle((1370, 461, 1414, 527), '#28465a')
    art.rectangle((1370, 455, 1414, 473), '#be4350')
    art.line([(1508, 445), (1508, 568)], '#31546a', 3)
    art.polygon([(1510, 448), (1550, 458), (1510, 470)], '#c55053')
    for y, width in ((840, 560), (875, 460), (914, 330)):
        art.line([(1110, y), (1110 + width, y)], '#82b1ba', 3)
    for x, y in ((960, 260), (1120, 310), (1750, 220)):
        art.line([(x - 18, y + 5), (x, y), (x + 18, y + 5)], '#526779', 3)
    return art.finish()


def house(art, x, y, scale):
    def p(a, b):
        return x + a * scale, y + b * scale
    art.polygon([p(-68, 0), p(68, 0), p(68, 156), p(-68, 156)], '#f4e9ce')
    art.polygon([p(-84, 0), p(0, -56), p(85, 0)], '#9b4d41')
    for offset in (-64, 0, 64):
        art.line([p(offset, 6), p(offset, 150)], '#6a554b', max(1, round(5 * scale)))
    art.line([p(-64, 68), p(64, 68)], '#6a554b', max(1, round(5 * scale)))
    for dx, dy in ((-42, 20), (22, 20), (-42, 90), (22, 90)):
        a, b = p(dx, dy), p(dx + 22, dy + 32)
        art.rectangle((*a, *b), '#4f6868')
    a, b = p(-12, 102), p(12, 156)
    art.rectangle((*a, *b), '#796451')


def safranbolu():
    art = Canvas('#b7cdd4', '#e4d7b9')
    art.ellipse((1400, 180, 1560, 340), '#f8edcd')
    art.wave(530, 50, 340, '#a4b9b2', 1)
    art.wave(650, 60, 390, '#7f9b94', 2)
    for x, y, s in ((1320, 570, .7), (1510, 530, .85), (1740, 570, .8)):
        house(art, x, y, s)
    art.wave(760, 70, 450, '#687f73', 1)
    for x, y, s in ((1010, 700, .9), (1240, 735, 1.15), (1515, 710, 1.05), (1780, 760, 1.25)):
        house(art, x, y, s)
    art.polygon([(1410, 1080), (1590, 1080), (1400, 860), (1350, 830), (1360, 890)], '#c5b18e')
    art.wave(990, 35, 240, '#596e5c', 3)
    for x, y in ((860, 850), (1880, 870), (1670, 650)):
        art.line([(x, y), (x, y + 110)], '#675b45', 7)
        art.ellipse((x - 33, y - 77, x + 33, y + 20), '#64765c')
        art.ellipse((x - 38, y - 39, x + 38, y + 45), '#6f8060')
    return art.finish()


def pamukkale():
    art = Canvas('#a7cfd7', '#dce9e1')
    art.wave(490, 26, 360, '#baccc5', 1)
    # Organik teras konturları; gerçek yerin haritası değildir.
    for level in range(8):
        y = 560 + level * 75
        points = [(x, y + math.sin(x / 185 + level * .73) * (25 + level * 7) + math.cos(x / 407 + level) * 13)
                  for x in range(-20, W + 21, 8)]
        art.polygon(points + [(W + 20, H), (-20, H)], '#f1eee1')
        inner = [(x, yy + 15 + level * 2) for x, yy in points]
        art.polygon(inner + [(W + 20, H), (-20, H)], ('#9dcfcf', '#8bc8c9', '#78bfc5', '#65b2bd')[min(level // 2, 3)])
        art.line(points, '#fffaf0', 4)
    return art.finish()


def night():
    art = Canvas('#101e36', '#365968')
    rng = random.Random(1101)
    for _ in range(125):
        x, y = rng.randrange(20, 1900), rng.randrange(35, 650)
        r = rng.choice((.6, .9, 1.3))
        art.ellipse((x-r, y-r, x+r, y+r), rng.choice(('#88a0b2', '#a8b8be', '#d3d9d1')))
    art.ellipse((1440, 160, 1560, 280), '#f4e6bd')
    art.ellipse((1458, 149, 1570, 261), '#1c3049')
    art.wave(730, 70, 430, '#294955', 1)
    art.wave(840, 65, 390, '#203c48', 2)
    for x, y, width in ((1320, 790, 120), (1440, 820, 110), (1550, 770, 130), (1660, 835, 120)):
        art.rectangle((x, y, x + width, y + 105), '#192e3b')
        art.polygon([(x - 10, y), (x + width / 2, y - 47), (x + width + 10, y)], '#152b37')
        for dx in (25, 75):
            art.rectangle((x + dx, y + 24, x + dx + 15, y + 47), '#d3a96b')
    art.wave(980, 28, 220, '#142d38', 2)
    art.line([(1810, 810), (1810, 990)], '#142d38', 9)
    art.polygon([(1770, 915), (1810, 690), (1850, 915)], '#142d38')
    # Küçük, sabit yumuşak ışık: çalışma zamanı animasyonu yoktur.
    glow = Image.new('RGBA', art.image.size)
    draw = ImageDraw.Draw(glow)
    draw.ellipse((1400*S, 790*S, 1700*S, 970*S), fill=(242, 184, 102, 18))
    art.image = Image.alpha_composite(art.image.convert('RGBA'), glow.filter(ImageFilter.GaussianBlur(40*S))).convert('RGB')
    return art.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, painter in zip(NAMES, (vapur, safranbolu, pamukkale, night)):
        painter().save(args.output / (name + '.png'), optimize=True)


if __name__ == '__main__':
    main()
