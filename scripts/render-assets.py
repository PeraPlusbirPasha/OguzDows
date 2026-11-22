#!/usr/bin/env python3
"""OğuzDows görsellerini Pillow ile çevrimdışı üretir; uzak tema indirmez."""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
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


def window_theme(root: Path, name='OguzDows', light=False, xp=False) -> None:
    base = f'usr/share/themes/{name}/xfwm4/'
    active_bg = '#245ca5' if xp and light else ('#183352' if xp else ('#e9edf2' if light else '#1c202a'))
    mac, gnome = name.startswith('OguzDowsMac'), name.startswith('OguzDowsGnome')
    inactive_bg = '#385d88' if xp and light else ('#1b3048' if xp else ('#dce3ed' if light else '#191c24'))
    active_text = '#1e2a3a' if light and not xp else PAPER
    inactive_text = '#334155' if light and not xp else '#e1e6ef'
    if mac:
        active_bg, inactive_bg = ('#eef0f4', '#e1e5ec') if light else ('#292c33', '#24272e')
    elif gnome:
        active_bg, inactive_bg = ('#f0edf3', '#e2dfe9') if light else ('#322f3d', '#292733')

    def tile(size, color):
        image = Image.new('RGBA', size, color)
        if xp or mac:
            # Reflet çizime gömülüdür; çalışma anında blur / animasyon yoktur.
            rgb = ImageColor.getrgb(color)
            draw = ImageDraw.Draw(image)
            for y in range(size[1]):
                shine = (1 - y / max(1, size[1] - 1)) * (.16 if xp else .05)
                draw.line((0, y, size[0], y), fill=tuple(round(c + (255 - c) * shine) for c in rgb) + (255,))
        return image

    for state in ("active", "inactive"):
        bg = active_bg if state == "active" else inactive_bg
        edge = RED if state == "active" else "#363b49"
        for part in ("title-1", "title-2", "title-3", "title-4", "title-5", "top-left", "top-right"):
            image = tile((5, 32), bg)
            ImageDraw.Draw(image).line((0, 0, 5, 0), fill=edge)
            save(image, root, base + f"{part}-{state}.png")
        for part, size in (("left", (3, 1)), ("right", (3, 1)), ("bottom", (1, 3)), ("bottom-left", (3, 3)), ("bottom-right", (3, 3))):
            save(Image.new("RGBA", size, bg), root, base + f"{part}-{state}.png")
    for state in ("active", "inactive", "prelight", "pressed"):
        color = inactive_text if state == "inactive" else active_text
        for button in ("close", "hide", "maximize", "maximize-toggled", "menu"):
            # Eski GPU'da da bütün düğme döşemesi tamamen opaktır.
            image = tile((28 * 3, 32 * 3), inactive_bg if state == "inactive" else active_bg)
            draw = ImageDraw.Draw(image)
            if mac and button in ("close", "hide", "maximize", "maximize-toggled"):
                fill = {"close": "#f16e68", "hide": "#f4cf72", "maximize": "#81c79a", "maximize-toggled": "#81c79a"}[button]
                draw.ellipse((12, 21, 72, 81), fill=fill, outline="#68717d", width=2)
                color = "#20252d"
            elif button == "close" or state in ("prelight", "pressed"):
                fill = ("#9f293e" if state == "inactive" else RED) if button == "close" else "#37424b"
                draw.rounded_rectangle((6, 12, 78, 84), radius=15, fill=fill)
            if button == "close":
                draw.line((30, 36, 54, 60), fill=color if mac else PAPER, width=4)
                draw.line((54, 36, 30, 60), fill=color if mac else PAPER, width=4)
            elif button == "hide":
                draw.line((27, 57, 57, 57), fill=color, width=4)
            elif button.startswith("maximize"):
                draw.rectangle((28, 34, 56, 62), outline=color, width=3)
                if button.endswith("toggled"):
                    draw.line((34, 28, 62, 28, 62, 56), fill=color, width=3)
            else:
                for y in (36, 48, 60):
                    draw.line((27, y, 57, y), fill=TURQUOISE if state != "inactive" else color, width=3)
            save(image.resize((28, 32), Image.Resampling.LANCZOS), root, base + f"{button}-{state}.png")
    path = root / base / "themerc"
    path.write_text(f"""active_text_color={active_text}
inactive_text_color={inactive_text}
active_text_shadow_color={active_bg}
inactive_text_shadow_color={inactive_bg}
button_offset=3
button_spacing=1
full_width_title=true
title_horizontal_offset=8
title_vertical_offset=0
shadow_delta_height=2
shadow_delta_width=2
shadow_delta_x=0
shadow_delta_y=2
""")


def render_store_icons(root: Path) -> None:
    """Kurulmamış uygulamada da çevrimdışı rozet; üçüncü taraf logosu taklidi değil."""
    relative = 'usr/share/oguzdows/store-icons.json'
    manifest = root / relative
    if not manifest.is_file():
        manifest = Path(__file__).resolve().parents[1] / 'system' / relative
    for item in json.loads(manifest.read_text()):
        for size in (48, 64):
            n = size * 3
            image = Image.new('RGBA', (n, n))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((2, 2, n - 3, n - 3), radius=n * .23, fill=item['color'])
            draw.rounded_rectangle((n * .12, n * .10, n * .88, n * .88), radius=n * .17, outline='#ffffff50', width=2)
            words = item['badge']
            draw.text((n * .5, n * .47), words, fill='#ffffff', anchor='mm',
                      font=font(round(n * (.32 if len(words) < 3 else .24)), True))
            draw.line((n * .35, n * .78, n * .65, n * .78), fill='#ffffffb0', width=max(2, n // 50))
            save(image.resize((size, size), Image.Resampling.LANCZOS), root,
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
    window_theme(root)
    window_theme(root, 'OguzDowsLight', light=True)
    window_theme(root, 'OguzDowsXP', light=True, xp=True)
    window_theme(root, 'OguzDowsXPDark', xp=True)
    for name, light in (('OguzDowsMac', True), ('OguzDowsMacDark', False), ('OguzDowsGnome', True), ('OguzDowsGnomeDark', False)):
        window_theme(root, name, light=light)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Üretilen dosyaların kök dizini")
    args = parser.parse_args()
    render(args.root.resolve())


if __name__ == "__main__":
    main()
