#!/usr/bin/env python3
"""OğuzDows görsellerini Pillow ile çevrimdışı üretir; uzak tema indirmez."""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import wave
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

INK = "#131620"
PAPER = "#fff9ef"
RED = "#c93246"
TURQUOISE = "#3fc5c1"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        "/usr/share/fonts/truetype/inter/Inter-SemiBold.otf" if bold else "/usr/share/fonts/truetype/inter/Inter-Regular.otf",
        "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf" if bold else "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    raise RuntimeError("Türkçe karakterleri destekleyen bir sistem yazı tipi bulunamadı.")


def save(image: Image.Image, root: Path, target: str) -> None:
    path = root / target.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def star(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    return [
        (cx + math.cos(i * math.pi / 5) * radius * (0.4 if i % 2 else 1),
         cy + math.sin(i * math.pi / 5) * radius * (0.4 if i % 2 else 1))
        for i in range(10)
    ]


def emblem(size: int, tile: bool = False) -> Image.Image:
    # 3x örnekleme; küçük panel ikonlarında da temiz kenarlar.
    scale = size * 3
    image = Image.new("RGBA", (scale, scale))
    draw = ImageDraw.Draw(image)
    if tile:
        draw.rounded_rectangle((0, 0, scale - 1, scale - 1), radius=scale / 4, fill=RED)
    mask = Image.new("L", image.size)
    md = ImageDraw.Draw(mask)
    md.ellipse((scale * .15, scale * .23, scale * .69, scale * .77), fill=255)
    md.ellipse((scale * .30, scale * .28, scale * .74, scale * .72), fill=0)
    image.alpha_composite(Image.composite(Image.new("RGBA", image.size, PAPER), Image.new("RGBA", image.size), mask))
    draw = ImageDraw.Draw(image)
    draw.polygon(star(scale * .73, scale * .50, scale * .135), fill=PAPER)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def text_image(text: str, size: int, color: str, bold: bool = False) -> Image.Image:
    face = font(size, bold)
    box = face.getbbox(text)
    image = Image.new("RGBA", (box[2] - box[0] + 4, box[3] - box[1] + 8))
    ImageDraw.Draw(image).text((2 - box[0], 4 - box[1]), text, font=face, fill=color)
    return image


def kilim(draw: ImageDraw.ImageDraw, width: int, y: int, unit: int, color: str) -> None:
    for x in range(-unit, width + unit, unit * 2):
        draw.line([(x, y), (x + unit, y - unit), (x + unit * 2, y), (x + unit, y + unit), (x, y)], fill=color, width=2)
        r = max(2, unit // 4)
        draw.polygon([(x + unit - r, y), (x + unit, y - r), (x + unit + r, y), (x + unit, y + r)], fill=TURQUOISE)


def render_wallpapers(root: Path) -> None:
    # Eski çizimler emekli edildi. JPEG'ler bir kez, prepare-landscapes.py ile
    # sağ altta markalanır; her derlemede tekrar logo / JPEG kaybı eklenmez.
    entries = []
    gallery = (
        ("bogaz-sabahi", "Boğaz · Sabah Işığı"),
        ("kackar-sisi", "Kaçkar · Sis Denizinde"),
        ("kapadokya-isigi", "Kapadokya · Gün Doğumu"),
        ("oludeniz-kiyisi", "Ölüdeniz · Turkuaz Kıyı"),
        ("tuz-golu-aksami", "Tuz Gölü · Akşam Aynası"),
        ("ani-kisi", "Ani · Kış Sessizliği"),
        ('istanbul-kedisi', 'İstanbul Kedisi · Kıyıda'),
        ('van-kedisi', 'Van Kedisi · Mavi ve Kehribar'),
        ('cay-simit', 'Çay ve Simit · Bir Mola'),
        ('halay', 'Halay · Yan Yana'),
        ('horon', 'Horon · Yayla Sevinci'),
        ('zeybek', 'Zeybek · Ege Rüzgârı'),
        ('kilim', 'Kilim · Anadolu İzi'),
        ('ebru', 'Ebru · Suyun Hafızası'),
        ('lale', 'Lale · Sade Bahar'),
        ('nazar', 'Nazar · Mavi Cam'),
        ('vapur', 'Vapur · Kıyı Çizgileri'),
        ('safranbolu', 'Safranbolu · Ahşap ve Taş'),
        ('pamukkale-teraslari', 'Pamukkale · Turkuaz Katlar'),
        ('anadolu-gecesi', 'Anadolu Gecesi · Ev Işıkları'),
    )
    for identifier, name in gallery:
        relative = "usr/share/backgrounds/oguzdows/" + identifier + ".jpg"
        source = root / relative
        if not source.is_file():
            source = Path(__file__).resolve().parents[1] / "system" / relative
        target_image = root / relative
        target_image.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target_image.resolve():
            shutil.copyfile(source, target_image)
        with Image.open(source) as image:
            if image.size != (1920, 1080):
                raise ValueError("Paketlenen manzara boyutu yanlış: " + identifier)
            preview = "/usr/share/oguzdows/wallpaper-previews/" + identifier + ".jpg"
            save(image.resize((320, 180), Image.Resampling.LANCZOS), root, preview)
            if identifier == 'bogaz-sabahi':
                # Pi / eski ayarlar bu yolu kullanır; içerik yeni manzaradır.
                save(image.copy(), root, "/usr/share/backgrounds/oguzdows/wallpaper.png")
        entries.append({"id": identifier, "name": name, "path": "/" + relative,
                        "preview": preview, "origin": "Original illustration" if identifier in ("vapur", "safranbolu", "pamukkale-teraslari", "anadolu-gecesi") else "AI-generated", "logo": "bottom-right"})
    target = root / "usr/share/oguzdows/wallpapers.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def boot_background(width: int, height: int) -> Image.Image:
    # BIOS menü metnini SYSLINUX çizer; başlık/fontlar resme gömülür.
    image = Image.new("RGBA", (640, 480), INK)
    draw = ImageDraw.Draw(image)
    draw.polygon([(480, 0), (640, 0), (640, 160)], fill="#241b29")
    image.alpha_composite(emblem(84), (278, 26))
    title = text_image("OğuzDows", 42, PAPER, True)
    image.alpha_composite(title, ((640 - title.width) // 2, 117))
    subtitle = text_image("KÖKLERİNDEN GÜÇ ALIR.", 11, TURQUOISE, True)
    image.alpha_composite(subtitle, ((640 - subtitle.width) // 2, 171))
    draw = ImageDraw.Draw(image)
    draw.line((280, 200, 360, 200), fill=RED, width=2)
    kilim(draw, 640, 462, 12, "#672c3b")
    return image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)


def window_theme(root: Path, name='OguzDows', light=False, xp=False, accent=None, glass=None) -> None:
    """One contiguous 32px title baseline, 1px frame and shaped top corners.

    GTK owns CSD geometry, Xfwm owns SSD assets; Picom optionally clips outer
    SSD corners once. No painted rectangular button patch across a corner.
    """
    base = f'usr/share/themes/{name}/xfwm4/'
    mac = name.startswith('OguzDowsMac')
    eleven = name.startswith('OguzDowsEleven')
    glass = name.startswith('OguzDowsAeroGlass') if glass is None else glass
    accent = accent or ('#2469ad' if mac else '#276bc1' if eleven else RED)
    active_bg = '#245ca5' if xp and light else '#183352' if xp else '#e9edf2' if light else '#1c202a'
    if mac:
        active_bg = '#eef0f4' if light else '#292c33'
    elif eleven:
        active_bg = '#edf2f9' if light else '#202d40'
    elif name.startswith('OguzDowsGnome'):
        active_bg = '#f0edf3' if light else '#322f3d'
    elif name.startswith('OguzDowsAero'):
        active_bg = '#c6dbef' if light else '#204568'
    rgb = ImageColor.getrgb(accent)
    if not xp:
        weight = .10 if light else .16
        active_bg = '#' + ''.join(f'{round(c * weight + b * (1-weight)):02x}' for c, b in zip(rgb, ImageColor.getrgb(active_bg)))
    inactive_bg = '#e4e7ed' if light else '#252b34'
    active_text = '#1d293b' if light and not xp else PAPER
    inactive_text = '#536074' if light and not xp else '#c1c8d2'

    def tile(size, color):
        # Vertical gradients share the same endpoints across title / buttons.
        image = Image.new('RGBA', size, color)
        draw = ImageDraw.Draw(image)
        components = ImageColor.getrgb(color)
        for y in range(size[1]):
            shine = (1 - y / max(1, size[1] - 1)) * (.10 if glass else .035 if mac else 0)
            draw.line((0, y, size[0], y), fill=tuple(round(c + (255 - c) * shine) for c in components) + (255,))
        return image

    for state in ('active', 'inactive'):
        bg = active_bg if state == 'active' else inactive_bg
        edge = (*ImageColor.getrgb(accent), 190) if state == 'active' else ((70, 83, 102, 110) if light else (180, 193, 213, 90))
        for part in ('title-1', 'title-2', 'title-3', 'title-4', 'title-5'):
            image = tile((32 if part == 'title-3' else 5, 32), bg)
            ImageDraw.Draw(image).line((0, 0, image.width, 0), fill=edge)
            if glass:
                # Alpha only on decorative strips, behind no title glyphs.
                for y in (1, 2, 29, 30, 31):
                    for x in range(image.width):
                        red, green, blue, _alpha = image.getpixel((x, y))
                        image.putpixel((x, y), (red, green, blue, 220))
            save(image, root, base + f'{part}-{state}.png')
        for part in ('top-left', 'top-right'):
            scale, radius = 4, 10
            image = tile((radius * scale, 32 * scale), bg)
            mask = Image.new('L', (radius * scale * 2, 64 * scale), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, radius * scale * 2 - 1, 64 * scale - 1), radius=radius * scale, fill=255)
            outline = Image.new('RGBA', mask.size)
            ImageDraw.Draw(outline).rounded_rectangle((0, 0, radius * scale * 2 - 1, 64 * scale - 1), radius=radius * scale, outline=edge, width=scale)
            image.alpha_composite(outline.crop((0, 0, radius * scale, 32 * scale)))
            image.putalpha(mask.crop((0, 0, radius * scale, 32 * scale)))
            if part == 'top-right': image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            save(image.resize((radius, 32), Image.Resampling.LANCZOS), root, base + f'{part}-{state}.png')
        for part, size in (('left', (1, 1)), ('right', (1, 1)), ('bottom', (1, 1)), ('bottom-left', (1, 1)), ('bottom-right', (1, 1))):
            # SSD fallback is square at the 1px bottom rail. Picom radius=10
            # clips all four outer corners; do not fake 10px of client padding.
            save(Image.new('RGBA', size, edge), root, base + f'{part}-{state}.png')
    for state in ('active', 'inactive', 'prelight', 'pressed'):
        for button in ('close', 'hide', 'maximize', 'maximize-toggled', 'menu'):
            color = inactive_text if state == 'inactive' else active_text
            width = 26 if mac else 44 if eleven else 28
            image = tile((width * 3, 96), inactive_bg if state == 'inactive' else active_bg)
            draw = ImageDraw.Draw(image)
            cx = width * 1.5
            if mac and button != 'menu':
                fill = {'close': '#ed6a5f', 'hide': '#f5bf4f', 'maximize': '#61c454', 'maximize-toggled': '#61c454'}[button]
                draw.ellipse((cx - 18, 30, cx + 18, 66), fill=fill, outline='#82645b', width=2)
                color = '#352c2b'
            elif state in ('prelight', 'pressed') or (xp and button == 'close'):
                fill = '#c62b3d' if button == 'close' else ('#d4dfec' if light else '#405067')
                draw.rectangle((0, 3, width * 3, 95), fill=fill)
                if button == 'close': color = PAPER
            # Traffic lights display glyphs only under hover / keyboard press.
            glyph = not mac or button == 'menu' or state in ('prelight', 'pressed')
            if glyph and button == 'close':
                draw.line((cx - 12, 36, cx + 12, 60), fill=color, width=3)
                draw.line((cx + 12, 36, cx - 12, 60), fill=color, width=3)
            elif glyph and button == 'hide':
                draw.line((cx - 14, 49, cx + 14, 49), fill=color, width=3)
            elif glyph and button.startswith('maximize'):
                draw.rectangle((cx - 13, 35, cx + 13, 61), outline=color, width=3)
                if button.endswith('toggled'): draw.line((cx - 7, 29, cx + 19, 29, cx + 19, 55), fill=color, width=3)
            elif button == 'menu':
                for y in (36, 48, 60): draw.line((cx - 13, y, cx + 13, y), fill=color, width=3)
            save(image.resize((width, 32), Image.Resampling.LANCZOS), root, base + f'{button}-{state}.png')
    (root / base / 'themerc').write_text(f'''active_text_color={active_text}
inactive_text_color={inactive_text}
active_text_shadow_color={active_bg}
inactive_text_shadow_color={inactive_bg}
button_offset=0
button_spacing=0
full_width_title=true
title_horizontal_offset=8
title_vertical_offset=0
shadow_delta_height=0
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=0
''')


def own_app_icon(identifier: str, size: int) -> Image.Image:
    """Özgün, farklı siluetli ve saydam kenarlı ikonlar; tek tip kare rozet yok.

    Mantıksal 256 px çizimler düşük boyutta da okunur; gölgeler/statik parıltı
    PNG'ye gömülüdür. Panelde SVG işçisi veya animasyon çalışmaz.
    """
    image = Image.new('RGBA', (256, 256))
    d = ImageDraw.Draw(image)
    white, ink = '#fffdf7', '#243952'
    if identifier == 'store':
        d.rounded_rectangle((43, 76, 213, 223), radius=30, fill='#147f92')
        d.polygon([(43, 97), (213, 97), (203, 215), (54, 215)], fill='#24b7bd')
        d.arc((86, 28, 172, 136), 180, 359, fill='#156879', width=15)
        d.arc((88, 27, 169, 132), 180, 359, fill='#b8f0e3', width=7)
        d.ellipse((83, 101, 98, 116), fill=ink); d.ellipse((163, 101, 178, 116), fill=ink)
        d.line((105, 162, 122, 179, 155, 143), fill=white, width=12, joint='curve')
        d.line((61, 88, 196, 88), fill='#b8f5e4', width=4)
    elif identifier == 'news':
        d.rounded_rectangle((32, 44, 204, 217), radius=13, fill='#b9ceda')
        d.rounded_rectangle((43, 31, 220, 206), radius=14, fill='#f5f7ee')
        d.rounded_rectangle((57, 48, 205, 82), radius=5, fill='#2d74ad')
        d.rectangle((59, 99, 121, 151), fill='#57b2b5')
        d.polygon([(61, 149), (82, 120), (96, 135), (114, 112), (121, 149)], fill='#286986')
        for y in (103, 121, 139): d.line((137, y, 202, y), fill='#5c7183', width=7)
        for y in (171, 188): d.line((59, y, 202, y), fill='#7d929e', width=6)
        d.arc((24, 178, 57, 217), 0, 180, fill='#7193a7', width=6)
    elif identifier == 'welcome':
        d.polygon([(29, 56), (119, 68), (128, 219), (32, 201)], fill='#238f9d')
        d.polygon([(128, 68), (224, 52), (224, 199), (128, 219)], fill='#176e83')
        d.polygon([(40, 43), (124, 59), (124, 202), (40, 187)], fill='#f6f1d9')
        d.polygon([(132, 59), (213, 43), (213, 187), (132, 202)], fill=white)
        for y in (87, 108, 129): d.line((52, y, 105, y+8), fill='#b5b5a8', width=5)
        d.ellipse((146, 100, 234, 188), fill='#eab455', outline='#9c7139', width=4)
        d.polygon([(190, 111), (205, 151), (173, 173)], fill='#df6551')
        d.polygon([(173, 173), (185, 133), (205, 151)], fill=white)
    elif identifier == 'update':
        d.arc((35, 34, 220, 220), 205, 356, fill='#2bbab1', width=29)
        d.polygon([(222, 61), (224, 146), (160, 103)], fill='#2bbab1')
        d.arc((35, 34, 220, 220), 26, 178, fill='#2779ba', width=29)
        d.polygon([(33, 195), (30, 111), (96, 151)], fill='#2779ba')
        d.ellipse((103, 103, 153, 153), fill='#b9eadf')
    elif identifier in ('device', 'drivers'):
        d.rounded_rectangle((26, 35, 220, 170), radius=16, fill='#344e6f')
        d.rounded_rectangle((38, 47, 208, 151), radius=7, fill='#64b9ca')
        d.polygon([(49, 133), (111, 65), (201, 137)], fill='#2e81a0')
        d.polygon([(110, 173), (140, 173), (150, 202), (97, 202)], fill='#8097ac')
        d.rounded_rectangle((78, 201, 167, 215), radius=6, fill='#a6b9c7')
        if identifier == 'device':
            d.rounded_rectangle((154, 140, 231, 218), radius=12, fill='#225d63', outline='#a5ddc4', width=5)
            d.rounded_rectangle((172, 158, 213, 199), radius=5, fill='#55be9f')
            for i in range(4):
                v = 165+i*15; d.line((v, 133, v, 145), fill='#8eb2a2', width=5); d.line((v, 215, v, 229), fill='#8eb2a2', width=5)
        else:
            d.ellipse((156, 128, 230, 202), fill='#e8b667')
            d.polygon([(166, 157), (197, 185), (137, 234), (118, 214)], fill='#f2ce87')
            d.polygon([(190, 125), (232, 161), (208, 165), (183, 144)], fill=(0, 0, 0, 0))
            d.ellipse((127, 213, 139, 225), fill='#795d3d')
    elif identifier == 'compatibility':
        d.rounded_rectangle((31, 83, 129, 210), radius=21, fill='#5989d2')
        d.ellipse((74, 55, 125, 108), fill='#5989d2')
        d.rounded_rectangle((126, 44, 225, 175), radius=21, fill='#62ba99')
        d.ellipse((103, 103, 154, 155), fill='#62ba99')
        d.line((61, 152, 78, 169, 105, 133), fill=white, width=9, joint='curve')
        d.line((165, 82, 196, 82), fill='#def6d7', width=8)
        d.line((180, 67, 180, 98), fill='#def6d7', width=8)
    elif identifier == 'imece':
        d.ellipse((29, 191, 227, 229), fill='#b7d5d8', outline='#5d99a1', width=5)
        d.ellipse((51, 194, 204, 216), fill='#eaf1df')
        d.polygon([(72, 57), (183, 57), (163, 122), (175, 195), (80, 195), (92, 122)], fill='#b1d7d5')
        d.polygon([(84, 81), (172, 81), (152, 125), (165, 187), (90, 187), (103, 125)], fill='#ac5034')
        d.polygon([(95, 93), (165, 93), (151, 125), (158, 165), (96, 165), (103, 125)], fill='#cc7040')
        d.arc((109, 16, 141, 68), 110, 266, fill='#83b5ba', width=7)
        d.line((86, 64, 97, 93), fill='#f5f5dc', width=6)
    elif identifier == 'install':
        d.rounded_rectangle((28, 146, 228, 223), radius=22, fill='#5f8194')
        d.rounded_rectangle((35, 151, 221, 198), radius=15, fill='#a9c3cb')
        d.ellipse((186, 202, 197, 213), fill='#9aedd8')
        d.line((54, 210, 154, 210), fill='#2f5369', width=5)
        d.rounded_rectangle((105, 29, 151, 132), radius=9, fill='#1eae9e')
        d.polygon([(70, 111), (186, 111), (128, 174)], fill='#1eae9e')
        d.line((118, 43, 118, 111), fill='#9ce9d8', width=7)
    elif identifier == 'rifki':
        d.polygon([(43, 111), (38, 29), (104, 70)], fill='#ba8b60')
        d.polygon([(153, 70), (218, 29), (213, 118)], fill='#ae7b52')
        d.polygon([(54, 80), (53, 46), (86, 68)], fill='#ecc1a1')
        d.polygon([(174, 68), (204, 46), (202, 87)], fill='#ecc1a1')
        d.ellipse((37, 57, 219, 226), fill='#d5ac7b')
        d.polygon([(109, 60), (128, 57), (147, 60), (137, 109), (119, 109)], fill='#a87351')
        d.ellipse((69, 121, 103, 151), fill=ink); d.ellipse((155, 121, 189, 151), fill=ink)
        d.ellipse((77, 125, 87, 135), fill='#cceae0'); d.ellipse((162, 125, 172, 135), fill='#cceae0')
        d.ellipse((87, 155, 169, 212), fill='#f7e7c7')
        d.polygon([(114, 165), (142, 165), (128, 180)], fill='#a8675f')
        d.line((128, 180, 128, 189), fill='#735144', width=4)
        for y in (168, 185):
            d.line((20, y-8, 84, y), fill='#735b4e', width=4); d.line((172, y, 236, y-8), fill='#735b4e', width=4)
    elif identifier == 'desktops':
        d.rounded_rectangle((28, 34, 198, 174), radius=17, fill='#698cbd')
        d.rounded_rectangle((57, 76, 232, 218), radius=17, fill='#f3f0e3', outline='#477b98', width=6)
        d.rounded_rectangle((63, 81, 226, 112), radius=9, fill='#4eb3b2')
        for x in (79, 96, 113): d.ellipse((x, 91, x+8, 99), fill='#f8f2d7')
        d.rounded_rectangle((75, 130, 118, 201), radius=6, fill='#b9d9d8')
        d.rounded_rectangle((132, 130, 211, 159), radius=5, fill='#c2d7e8')
        d.rounded_rectangle((132, 170, 211, 201), radius=5, fill='#dce8ed')
    elif identifier == 'wallpapers':
        d.rounded_rectangle((29, 43, 227, 214), radius=22, fill='#e6ddc6', outline='#b9ab8c', width=5)
        d.rounded_rectangle((42, 56, 214, 200), radius=13, fill='#85c9d7')
        d.ellipse((156, 72, 192, 108), fill='#ffe5a2')
        d.polygon([(43, 169), (98, 92), (160, 179), (185, 140), (214, 178), (214, 200), (43, 200)], fill='#367e8e')
        d.polygon([(77, 121), (98, 92), (121, 124), (100, 115)], fill='#ecf0df')
        d.polygon([(43, 185), (108, 152), (162, 181), (214, 167), (214, 200), (43, 200)], fill='#68b59b')
    elif identifier == 'browser':
        d.ellipse((29, 29, 227, 227), fill='#318db8')
        d.arc((61, 29, 195, 227), 80, 280, fill='#a2ded4', width=10)
        d.arc((61, 29, 195, 227), 260, 460, fill='#a2ded4', width=10)
        d.arc((29, 75, 227, 179), 0, 360, fill='#95d5d4', width=9)
        d.line((34, 128, 222, 128), fill='#9ee4dd', width=8)
        d.polygon([(166, 137), (239, 108), (207, 181), (195, 150)], fill='#f9b978', outline='#f8dfae')
    elif identifier == 'files':
        d.rounded_rectangle((26, 57, 126, 127), radius=14, fill='#2c92af')
        d.rounded_rectangle((26, 79, 229, 215), radius=20, fill='#2689a9')
        d.rounded_rectangle((42, 85, 213, 163), radius=10, fill='#e6f2e7')
        d.polygon([(25, 116), (232, 116), (216, 214), (41, 214)], fill='#63bec9')
        d.line((44, 130, 215, 130), fill='#a8e5db', width=5)
    elif identifier == 'terminal':
        d.rounded_rectangle((25, 42, 231, 207), radius=27, fill='#31475d')
        d.rounded_rectangle((34, 51, 222, 197), radius=21, fill='#21374b')
        d.polygon([(62, 201), (62, 232), (99, 201)], fill='#31475d')
        d.line((64, 90, 95, 118, 64, 146), fill='#8be2ce', width=11, joint='curve')
        d.line((118, 150, 171, 150), fill='#f2eedb', width=10)
        d.line((51, 61, 201, 61), fill='#65879b', width=3)
    else:
        raise ValueError('Özgün simge kimliği bilinmiyor: ' + identifier)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def editorial_cover(topic: int, width=320, height=180) -> Image.Image:
    """Original category illustrations, NEVER publisher / current-news photos."""
    palettes = (('#3a689a', '#203e63'), ('#328f98', '#215570'), ('#6559a0', '#303c6f'),
                ('#b16d67', '#633c6c'), ('#407d74', '#18434f'), ('#2a91a3', '#28597d'))
    top, bottom = (ImageColor.getrgb(value) for value in palettes[topic % len(palettes)])
    image = Image.new('RGB', (640, 360)); d = ImageDraw.Draw(image)
    for y in range(360):
        d.line((0, y, 640, y), fill=tuple(round(a + (b-a)*y/359) for a, b in zip(top, bottom)))
    d.ellipse((400, -170, 850, 280), fill=tuple(min(255, v+16) for v in top))
    d.polygon(((0, 280), (150, 200), (390, 300), (640, 240), (640, 360), (0, 360)), fill=bottom)
    pale, teal, gold = '#e3f0e7', '#75d2c5', '#f3c77f'
    if topic == 0:  # skyline, abstract editorial scene
        for x, h in ((88, 120), (166, 190), (250, 154), (342, 222), (438, 145), (522, 180)):
            d.rounded_rectangle((x, 306-h, x+62, 306), radius=6, fill=teal if x % 3 else pale)
            for y in range(326-h, 284, 24): d.line((x+14, y, x+46, y), fill=bottom, width=6)
        d.ellipse((466, 42, 528, 104), fill=gold)
    elif topic == 1:  # globe
        d.ellipse((206, 64, 442, 300), fill=teal, outline=pale, width=7)
        d.ellipse((256, 64, 392, 300), outline=pale, width=6)
        d.arc((206, 114, 442, 246), 0, 360, fill=pale, width=6)
        d.line((210, 182, 439, 182), fill=pale, width=6)
        d.arc((161, 32, 490, 327), 30, 179, fill=gold, width=9)
    elif topic == 2:  # science / orbit, not a rocket photograph
        for angle in (0, 60, 120):
            orbit = Image.new('RGBA', (640, 360)); od = ImageDraw.Draw(orbit)
            od.ellipse((152, 123, 488, 237), outline=teal, width=7)
            orbit = orbit.rotate(angle, resample=Image.Resampling.BICUBIC)
            image.paste(orbit, (0, 0), orbit)
        d = ImageDraw.Draw(image); d.ellipse((293, 153, 347, 207), fill=gold)
        d.ellipse((477, 165, 503, 191), fill=pale)
    elif topic == 3:  # culture, open book and sun
        d.polygon(((128, 110), (316, 134), (316, 288), (128, 264)), fill=pale)
        d.polygon(((328, 134), (512, 110), (512, 264), (328, 288)), fill='#b7d8d8')
        for y in (164, 190, 216):
            d.line((157, y, 281, y+14), fill=top, width=6); d.line((362, y+14, 482, y), fill=top, width=6)
        d.ellipse((284, 44, 356, 116), fill=gold)
    elif topic == 4:  # playing field
        d.rounded_rectangle((106, 82, 534, 306), radius=18, outline=pale, width=7)
        d.ellipse((258, 130, 382, 254), outline=pale, width=6); d.line((320, 85, 320, 304), fill=pale, width=6)
        d.rectangle((106, 143, 179, 246), outline=teal, width=6); d.rectangle((461, 143, 534, 246), outline=teal, width=6)
        d.ellipse((367, 186, 403, 222), fill=gold)
    else:  # guide / compass
        d.ellipse((218, 66, 434, 282), fill=pale)
        d.ellipse((235, 83, 417, 265), outline=top, width=6)
        d.polygon(((344, 103), (350, 189), (289, 244), (296, 160)), fill=teal)
        d.polygon(((344, 103), (350, 189), (296, 160)), fill='#d27766')
        for x, y in ((326, 88), (326, 246), (246, 169), (405, 169)): d.ellipse((x-4, y-4, x+4, y+4), fill=bottom)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def store_art(topic: str) -> Image.Image:
    """Static transparent editorial art. No remote images / frame clock."""
    image = Image.new('RGBA', (480, 380)); d = ImageDraw.Draw(image)
    d.ellipse((35, 291, 438, 357), fill='#061c2f30')
    d.rounded_rectangle((70, 57, 377, 281), radius=23, fill='#71cdd1')
    d.rounded_rectangle((84, 67, 363, 262), radius=17, fill='#e9f2e6')
    d.rounded_rectangle((84, 67, 363, 106), radius=13, fill='#b8dfe0')
    for x, color in ((105, '#f39883'), (125, '#f7cf87'), (145, '#6cbbad')): d.ellipse((x, 81, x+9, 90), fill=color)
    if topic == 'create':
        d.ellipse((159, 133, 277, 251), fill='#6892cd')
        d.polygon(((119, 253), (192, 125), (266, 253)), fill='#78c5b0')
        d.rounded_rectangle((272, 147, 331, 237), radius=14, fill='#e8a2b0')
        pencil = Image.new('RGBA', (480, 380)); pd = ImageDraw.Draw(pencil)
        pd.rounded_rectangle((342, 70, 378, 303), radius=9, fill='#f6cf86')
        pd.rectangle((351, 97, 358, 280), fill='#fff0bf'); pd.polygon(((342, 297), (378, 297), (360, 339)), fill='#ffebd5')
        pd.polygon(((354, 325), (366, 325), (360, 339)), fill='#365275')
        pencil = pencil.rotate(-23, resample=Image.Resampling.BICUBIC); image.alpha_composite(pencil)
    elif topic == 'media':
        d.ellipse((147, 124, 309, 286), fill='#385f96')
        d.ellipse((165, 142, 291, 268), fill='#193b69'); d.polygon(((213, 166), (213, 245), (264, 207)), fill='#d3eee0')
        for i, h in enumerate((42, 68, 108, 78, 45)):
            x = 318 + i*21; d.rounded_rectangle((x, 297-h, x+12, 297), radius=6, fill='#f5d296' if i%2 else '#8ed3c9')
    else:
        for y, color in ((134, '#5c9aab'), (165, '#b3ced0'), (196, '#b3ced0')): d.rounded_rectangle((110, y, 247, y+10), radius=4, fill=color)
        d.rounded_rectangle((278, 182, 433, 317), radius=19, fill='#5b9bad')
        for i, h in enumerate((34, 66, 92)):
            x = 297+i*39; d.rounded_rectangle((x, 295-h, x+22, 296), radius=5, fill='#d7f0da')
        d.ellipse((34, 209, 132, 307), fill='#f3cf88'); d.line((62, 258, 82, 278, 108, 239), fill='#547366', width=10, joint='curve')
    return image.resize((240, 190), Image.Resampling.LANCZOS)


def layout_preview(identifier):
    """Build-time illustration of actual panel placement, not a live screenshot."""
    image = Image.new('RGBA', (480, 284), '#89bfc6'); d = ImageDraw.Draw(image)
    d.polygon(((0, 220), (178, 12), (480, 184), (480, 284), (0, 284)), fill='#6484b3')
    d.polygon(((0, 284), (249, 83), (480, 167), (480, 284)), fill='#6177a1')
    d.ellipse((323, -67, 573, 183), fill='#a3d1d0')
    top = identifier in ('mac', 'gnome', 'xfce')
    dark = identifier == 'kde'; panel = '#29394d' if dark or identifier == 'gnome' else '#eff3f6'
    y = 0 if top else 254
    d.rectangle((0, y, 480, y+30), fill=panel)
    d.rounded_rectangle((102, 64, 384, 229), radius=12, fill='#ebeff4')
    d.rounded_rectangle((102, 64, 384, 93), radius=12, fill='#d7e0ea')
    d.rectangle((102, 80, 384, 94), fill='#d7e0ea')
    for x, color in zip((116, 130, 144) if identifier == 'mac' else (332, 348, 364), ('#ed8d86', '#e7c478', '#83bda5')):
        d.ellipse((x, 74, x+7, 81), fill=color)
    d.rounded_rectangle((116, 108, 169, 213), radius=5, fill='#c6d8df')
    for row in range(3):
        d.rounded_rectangle((185, 110+row*34, 365, 133+row*34), radius=5, fill='#f9fbfb')
        d.ellipse((197, 117+row*34, 207, 127+row*34), fill=('#69aeba', '#879bcc', '#d3b68a')[row])
    icons = ('browser', 'files', 'store', 'terminal')
    if identifier == 'mac':
        d.rounded_rectangle((160, 241, 319, 280), radius=12, fill='#edf4f2e8')
        for i, icon in enumerate(icons): image.alpha_composite(own_app_icon(icon, 32), (170+i*34, 243))
    elif identifier == 'gnome':
        d.rectangle((0, 30, 42, 284), fill='#29394d')
        for i, icon in enumerate(icons): image.alpha_composite(own_app_icon(icon, 32), (5, 78+i*42))
    else:
        start = 153 if identifier == 'windows11' else 20
        for i, icon in enumerate(icons): image.alpha_composite(own_app_icon(icon, 26), (start+i*35, y+2))
    d.rounded_rectangle((419, y+11, 464, y+16), radius=2, fill='#8796a8')
    return image.resize((240, 142), Image.Resampling.LANCZOS)


def render_editorial_assets(root: Path) -> None:
    for identifier in ('oguzdows', 'kde', 'gnome', 'xfce', 'windows11', 'mac'):
        save(layout_preview(identifier), root, f'usr/share/oguzdows/ui/layout-{identifier}.png')
    for topic in range(6):
        save(editorial_cover(topic), root, f'usr/share/oguzdows/ui/news-cover-{topic}.png')
    for topic in ('create', 'media', 'work'):
        save(store_art(topic), root, f'usr/share/oguzdows/ui/store-{topic}.png')


def store_badge(identifier, color, size):
    """Pictorial offline fallback, not initials or a counterfeit vendor logo."""
    image = Image.new('RGBA', (192, 192)); d = ImageDraw.Draw(image)
    d.rounded_rectangle((8, 8, 184, 184), radius=44, fill=color)
    d.arc((18, 17, 175, 176), 192, 282, fill='#ffffff70', width=4)
    white, light = '#f4f6e9', '#bee4de'
    if identifier in ('firefox', 'transmission', 'remmina', 'filezilla'):
        d.ellipse((47, 46, 145, 144), outline=white, width=8)
        d.ellipse((72, 46, 120, 144), outline=light, width=6); d.line((50, 95, 142, 95), fill=white, width=6)
        if identifier != 'firefox': d.polygon(((132, 109), (163, 109), (147, 141)), fill='#f6ce8b')
    elif identifier == 'thunderbird':
        d.rounded_rectangle((37, 55, 155, 140), radius=14, fill=white)
        d.line((43, 65, 96, 105, 149, 65), fill=color, width=9, joint='curve')
    elif identifier in ('libreoffice', 'evince', 'xournalpp'):
        d.rounded_rectangle((52, 32, 143, 160), radius=9, fill=white)
        d.polygon(((117, 32), (143, 58), (117, 58)), fill=light)
        for y in (84, 105, 126): d.line((69, y, 124, y), fill=color, width=7)
        if identifier == 'xournalpp': d.line((87, 155, 147, 77), fill='#f6cc84', width=14)
    elif identifier in ('gimp', 'krita', 'inkscape', 'blender'):
        d.ellipse((39, 40, 151, 152), fill=white)
        for x, y, fill in ((67, 67, '#de9083'), (110, 62, '#e6c582'), (129, 102, '#79bfc0'), (68, 123, '#8a9fd6')): d.ellipse((x-12, y-12, x+12, y+12), fill=fill)
        d.line((76, 153, 126, 91), fill='#3f5875', width=14); d.ellipse((114, 77, 137, 102), fill='#f7d7a4')
    elif identifier in ('vlc', 'audacity', 'kdenlive', 'obs', 'handbrake'):
        d.rounded_rectangle((35, 48, 157, 147), radius=18, fill=white)
        if identifier == 'audacity':
            for x, h in ((60, 25), (82, 56), (104, 78), (126, 40)): d.line((x, 97-h//2, x, 97+h//2), fill=color, width=10)
        else: d.polygon(((80, 71), (80, 126), (124, 99)), fill=color)
    elif identifier in ('geany', 'builder', 'gitg'):
        d.line((72, 64, 42, 96, 72, 128), fill=white, width=13, joint='curve')
        d.line((120, 64, 150, 96, 120, 128), fill=white, width=13, joint='curve'); d.line((108, 49, 85, 146), fill=light, width=11)
    elif identifier in ('supertuxkart', 'supertux', 'aisleriot'):
        d.rounded_rectangle((34, 62, 158, 139), radius=30, fill=white)
        d.line((69, 78, 69, 122), fill=color, width=10); d.line((47, 100, 91, 100), fill=color, width=10)
        d.ellipse((115, 82, 130, 97), fill=color); d.ellipse((133, 105, 148, 120), fill=color)
    else:
        d.rounded_rectangle((50, 77, 142, 153), radius=15, fill=white)
        d.arc((64, 37, 128, 115), 180, 360, fill=light, width=12)
        d.ellipse((87, 101, 105, 119), fill=color); d.rectangle((92, 112, 100, 134), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def render_desktop_assets(root: Path) -> None:
    vectors = Path(__file__).resolve().parents[1] / 'system/usr/share/icons/hicolor/scalable'
    if vectors.is_dir() and vectors.resolve() != (root / 'usr/share/icons/hicolor/scalable').resolve():
        shutil.copytree(vectors, root / 'usr/share/icons/hicolor/scalable', dirs_exist_ok=True)
    # Kısa, özgün onay sesi: yalnız açık feedback tercihiyle paplay tarafından
    # çalınır. Boot / kurulum / normal hover sırasında ses veya işçi yoktur.
    target = root / 'usr/share/oguzdows/ui/confirm.wav'
    target.parent.mkdir(parents=True, exist_ok=True)
    render_editorial_assets(root)
    rate, duration = 16000, .085
    with wave.open(str(target), 'wb') as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(rate)
        frames = [round(1700 * math.sin(math.pi * n / (rate * duration))**2 * math.sin(2 * math.pi * 880 * n / rate)) for n in range(round(rate * duration))]
        sound.writeframes(struct.pack('<' + 'h' * len(frames), *frames))


def render_own_app_icons(root: Path) -> None:
    relative = 'usr/share/oguzdows/own-app-icons.json'
    source = root / relative
    if not source.is_file():
        source = Path(__file__).resolve().parents[1] / 'system' / relative
    manifest = json.loads(source.read_text())
    for identifier in manifest['icons']:
        for size in manifest['sizes']:
            save(own_app_icon(identifier, size), root,
                 f'usr/share/icons/hicolor/{size}x{size}/apps/oguzdows-{identifier}.png')


def render_store_icons(root: Path) -> None:
    """Kurulmamış uygulamada da çevrimdışı rozet; üçüncü taraf logosu taklidi değil."""
    relative = 'usr/share/oguzdows/store-icons.json'
    manifest = root / relative
    if not manifest.is_file():
        manifest = Path(__file__).resolve().parents[1] / 'system' / relative
    for item in json.loads(manifest.read_text()):
        for size in (48, 64):
            save(store_badge(item['id'], item['color'], size), root,
                 f"usr/share/icons/hicolor/{size}x{size}/apps/oguzdows-app-{item['id']}.png")


def nazar(level: int, size: int = 48, charging: bool = False) -> Image.Image:
    """Mavi cam boncuk aşağıdan yukarı açılır; güç politikası değişmez."""
    level = max(0, min(100, level))
    n = size * 3
    image = Image.new("RGBA", (n, n))
    for y in range(n):
        for x in range(n):
            r = math.hypot(x - n * .47, y - n * .5) / (n * .43)
            if r > 1:
                continue
            if y < n * (1 - level / 100):
                color = (48, 57, 74, 255)
            else:
                color = (9, 64, 178) if r > .70 else ((245, 242, 216) if r > .46 else ((52, 179, 227) if r > .23 else (9, 22, 39)))
                glow = 1 - .30 * r + .12 * (1 - y / n)
                color = tuple(min(255, round(channel * glow)) for channel in color) + (255,)
            image.putpixel((x, y), color)
    draw = ImageDraw.Draw(image)
    if level:
        draw.arc((n*.1, n*.12, n*.8, n*.88), 195, 250, fill=(200, 237, 255, 220), width=max(1, n//30))
    if charging:
        draw.polygon([(n*.79,n*.08),(n*.64,n*.43),(n*.77,n*.43),(n*.68,n*.70),(n*.96,n*.33),(n*.82,n*.33),(n*.94,n*.08)], fill="#ffda71", outline="#3e331d", width=max(1,n//48))
    elif level <= 10:
        draw.ellipse((n*.65,n*.64,n*.97,n*.96), fill="#d63c53")
        draw.line((n*.81,n*.69,n*.81,n*.83), fill="white", width=max(2,n//24))
        draw.ellipse((n*.79,n*.87,n*.83,n*.91), fill="white")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def power_fallback(size: int, missing: bool) -> Image.Image:
    # Yeni ikon tabanlarında kaldırılan durumlar boş pil gibi gösterilmez.
    n = size * 3
    image = Image.new("RGBA", (n, n))
    draw = ImageDraw.Draw(image)
    color = "#d6e1ed"
    line = max(2, n // 18)
    if missing:
        draw.rounded_rectangle((n*.23,n*.17,n*.76,n*.91), radius=n*.06, outline=color, width=line)
        draw.rectangle((n*.39,n*.08,n*.60,n*.18), fill=color)
        draw.text((n*.50,n*.53), "?", font=font(round(n*.43), True), fill=color, anchor="mm")
    else:
        for x in (.35, .64):
            draw.line((n*x,n*.10,n*x,n*.38), fill=color, width=line)
        draw.rounded_rectangle((n*.23,n*.32,n*.77,n*.66), radius=n*.12, outline=color, width=line)
        draw.line([(n*.50,n*.66),(n*.50,n*.87),(n*.76,n*.87)], fill=color, width=line)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def render_nazar(root: Path) -> None:
    sizes = (16, 24, 32, 48)
    base = root / "usr/share/icons/OguzDows"
    base.mkdir(parents=True, exist_ok=True)
    directories = [f"{size}x{size}/status" for size in sizes]
    index = "[Icon Theme]\nName=OguzDows\nComment=Nazar boncuğu pil göstergeleri\nInherits=Adwaita,hicolor\nDirectories=" + ",".join(directories) + "\n"
    for size, directory in zip(sizes, directories):
        index += f"\n[{directory}]\nSize={size}\nContext=Status\nType=Fixed\n"
        for level in range(0, 101, 10):
            # Xfce son dilimde 100 adını kullanır; tam dolu durumu ayrı ikondur.
            shown = min(level, 95)
            for suffix, charging in (("", False), ("-charging", True)):
                image = nazar(shown, size, charging)
                for name in (f"battery-level-{level}{suffix}-symbolic", f"battery-level-{level}{suffix}", f"xfpm-primary-{level:03}{suffix}"):
                    save(image, root, f"usr/share/icons/OguzDows/{directory}/{name}.png")
        for name, level in (("empty", 0), ("caution", 10), ("low", 20), ("good", 60), ("full", 95), ("full-charged", 100)):
            for suffix in ("", "-symbolic"):
                save(nazar(level, size), root, f"usr/share/icons/OguzDows/{directory}/battery-{name}{suffix}.png")
                save(nazar(level, size, True), root, f"usr/share/icons/OguzDows/{directory}/battery-{name}-charging{suffix}.png")
        for name in ("battery-level-100-charged-symbolic", "battery-level-100-charged", "xfpm-primary-charged"):
            save(nazar(100, size), root, f"usr/share/icons/OguzDows/{directory}/{name}.png")
        for name, missing in (("battery-missing", True), ("ac-adapter", False)):
            for suffix in ("", "-symbolic"):
                save(power_fallback(size, missing), root, f"usr/share/icons/OguzDows/{directory}/{name}{suffix}.png")
    (base / "index.theme").write_text(index, encoding="utf-8")


def cursor_frame(size: int, phase: int, role: str = 'pointer') -> Image.Image:
    """Tespih tanesi vurgusu döner; nişangâh / tıklama noktası sabittir."""
    n = 96
    image = Image.new('RGBA', (n, n))
    draw = ImageDraw.Draw(image)
    # Boncuklar ilmek üzerinde ilerler, ilmek hafifçe sallanır; ok / hotspot
    # yerinde kalır. Sadece renk yanıp sönmesi değil, gerçek küçük konum farkı.
    sway = 3 * math.sin(phase * 2 * math.pi / 10)
    points = [(64 + sway + 20 * math.cos((i + phase / 10) * 2 * math.pi / 10),
               48 + 26 * math.sin((i + phase / 10) * 2 * math.pi / 10)) for i in range(10)]
    draw.line(points + [points[0]], fill='#30241e', width=5)
    for index, (x, y) in enumerate(points):
        radius = 7 if role != 'busy' else 8
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill='#e6ae55' if index == phase % 10 else '#97512f', outline='#fff1d5', width=2)
        draw.ellipse((x-3, y-4, x, y-1), fill='#ffe6af')
    draw.line([(64 + sway, 75), (64 + sway, 84), (56 + sway, 92)], fill='#503326', width=4)
    draw.line([(64 + sway, 84), (68 + sway, 92)], fill='#e6ae55', width=3)
    if role == 'text':
        draw.line([(17, 9), (33, 9), (25, 9), (25, 67), (17, 67), (33, 67)], fill='#17202b', width=9)
        draw.line([(17, 9), (33, 9), (25, 9), (25, 67), (17, 67), (33, 67)], fill=PAPER, width=4)
    elif role == 'link':
        draw.rounded_rectangle((12, 26, 43, 65), radius=8, fill=PAPER, outline='#17202b', width=3)
        draw.rounded_rectangle((13, 4, 24, 48), radius=5, fill=PAPER, outline='#17202b', width=3)
        draw.line((28, 30, 28, 47), fill='#17202b', width=3)
        draw.line((36, 34, 36, 47), fill='#17202b', width=3)
    elif role != 'busy':
        draw.polygon([(7, 4), (7, 66), (22, 51), (34, 76), (45, 71), (33, 47), (54, 47)], fill=PAPER, outline='#17202b', width=4)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def xcursor_bytes(frames):
    """Xcursor v1: TOC + 36 bayt image başlığı + premultiplied ARGB32."""
    chunks, table = [], []
    position = 16 + len(frames) * 12
    for image, nominal, hotspot, delay in frames:
        width, height = image.size
        chunk = struct.pack('<9I', 36, 0xfffd0002, nominal, 1, width, height, *hotspot, delay)
        for r, g, b, a in struct.iter_unpack('4B', image.convert('RGBA').tobytes()):
            chunk += struct.pack('<I', (a << 24) | ((r*a//255) << 16) | ((g*a//255) << 8) | (b*a//255))
        table.append(struct.pack('<3I', 0xfffd0002, nominal, position))
        chunks.append(chunk)
        position += len(chunk)
    return struct.pack('<4I', 0x72756358, 16, 0x00010000, len(frames)) + b''.join(table + chunks)


def render_cursor(root: Path) -> None:
    base = root / 'usr/share/icons/OguzDowsTespih'
    cursors = base / 'cursors'
    cursors.mkdir(parents=True, exist_ok=True)
    (base / 'index.theme').write_text('[Icon Theme]\nName=OğuzDows Tespih\nComment=Yerel hareketli tespih; sürekli uygulama gerektirmez\nInherits=Adwaita\n', encoding='utf-8')
    for name, role, animated in (('left_ptr', 'pointer', True), ('hand2', 'link', True),
                                  ('watch', 'busy', True), ('left_ptr_watch', 'pointer', True),
                                  ('xterm', 'text', False)):
        frames = []
        for size in (24, 32, 48):
            hotspot = (max(1, round(size * .07)), max(1, round(size * .04)))
            if role == 'text':
                hotspot = (round(size * 25/96), round(size * 38/96))
            elif role == 'link':
                hotspot = (round(size * 18/96), round(size * 4/96))
            elif role == 'busy':
                hotspot = (size // 2, size // 2)
            frames.extend((cursor_frame(size, frame, role), size, hotspot, 120)
                          for frame in range(10 if animated else 1))
        (cursors / name).write_bytes(xcursor_bytes(frames))
    for alias, name in {'default': 'left_ptr', 'arrow': 'left_ptr', 'top_left_arrow': 'left_ptr',
                         'pointer': 'hand2', 'hand': 'hand2', 'pointing_hand': 'hand2',
                         'wait': 'watch', 'progress': 'left_ptr_watch', 'text': 'xterm'}.items():
        path = cursors / alias
        if path.is_symlink() or path.is_file():
            path.unlink()
        path.symlink_to(name)


def render(root: Path) -> None:
    geometry = Path(__file__).resolve().parents[1] / 'system/usr/share/oguzdows/ui/window-geometry.css'
    target_geometry = root / 'usr/share/oguzdows/ui/window-geometry.css'
    if geometry.is_file() and geometry.resolve() != target_geometry.resolve():
        target_geometry.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(geometry, target_geometry)
    render_wallpapers(root)
    render_nazar(root)
    render_cursor(root)
    source = Path(__file__).resolve().parents[1] / "system/usr/share/oguzdows/rifki"
    target = root / "usr/share/oguzdows/rifki"
    if source.is_dir() and source.resolve() != target.resolve():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("rig", "envelopes.json", "intro-full.wav", "hello.wav", "help.wav", "disk.wav", "talk-blink.png"))
    for size in (24, 32, 48, 64, 128, 256):
        save(emblem(size, tile=True), root, f"usr/share/icons/hicolor/{size}x{size}/apps/oguzdows.png")
    brand = "usr/share/oguzdows/brand/"
    save(emblem(128, tile=True), root, brand + "oguzdows.png")
    for name, size in (("boot-bios", (640, 480)), ("boot-efi", (800, 600))):
        save(boot_background(*size), root, brand + name + ".png")
    plymouth = "usr/share/plymouth/themes/oguzdows/"
    for name, image in {
        "emblem": emblem(128),
        "wordmark": text_image("OğuzDows", 48, PAPER, True),
        "tagline": text_image("Köklerinden güç alır.", 15, "#aeb9c8"),
        "track": Image.new("RGBA", (280, 4), "#343948"),
        "fill": Image.new("RGBA", (280, 4), RED),
        "dot": Image.new("RGBA", (4, 4), TURQUOISE),
    }.items():
        save(image, root, plymouth + name + ".png")
    installer = "usr/share/calamares/branding/oguzdows/"
    save(emblem(160, tile=True), root, installer + "logo.png")
    save(boot_background(640, 480).crop((80, 20, 560, 210)), root, installer + "welcome.png")
    render_store_icons(root)
    render_own_app_icons(root)
    render_desktop_assets(root)
    window_theme(root)
    window_theme(root, 'OguzDowsLight', light=True)
    window_theme(root, 'OguzDowsXP', light=True, xp=True)
    window_theme(root, 'OguzDowsXPDark', xp=True)
    for name, light in (('OguzDowsMac', True), ('OguzDowsMacDark', False), ('OguzDowsGnome', True), ('OguzDowsGnomeDark', False),
                        ('OguzDowsEleven', True), ('OguzDowsElevenDark', False),
                        ('OguzDowsAero', True), ('OguzDowsAeroDark', False),
                        ('OguzDowsAeroGlass', True), ('OguzDowsAeroGlassDark', False)):
        window_theme(root, name, light=light)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Üretilen dosyaların kök dizini")
    args = parser.parse_args()
    render(args.root.resolve())


if __name__ == "__main__":
    main()
