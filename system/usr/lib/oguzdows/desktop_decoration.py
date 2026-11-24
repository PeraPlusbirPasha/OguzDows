"""Özgün Aurorae SVG çerçevesi; KWin'in gerçek dekorasyon blur bölgesi.

QML / C++ eklentisi derlemeyiz: kurulu Aurorae'nin mask-* -> blurRegion
sözleşmesini kullanırız. İstemci tarafı başlık çizen uygulamalara uygulanmaz.
Yazı şeridi ve bütün düğme yüzeyleri opak; yalnız dekoratif kenarlar camdır.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from desktop_state import private_directory
from profiles import atomic_text


def available(major, root=Path('/usr/lib')):
    relative = f'qt{6 if major == 6 else 5}/plugins/org.kde.kdecoration*/org.kde.kwin.aurorae.so'
    return any(path.is_file() for pattern in (relative, '*/' + relative) for path in root.glob(pattern))


def colors(accent, dark):
    if not isinstance(accent, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', accent) or type(dark) is not bool:
        raise ValueError('Aurorae materyal rengi geçersiz.')
    rgb = [int(accent[i:i + 2], 16) for i in (1, 3, 5)]
    base = 20 if dark else 248
    return '#' + ''.join(f'{round(base * .84 + value * .16):02x}' for value in rgb)


def decoration_svg(accent, dark):
    base = colors(accent, dark)
    # 16 px iki katlı gölge, 6 px yan cam, 34 px başlık. KWin kendi
    # DecorationShadow katmanını padding'den çıkarır; ikinci compositor yok.
    pieces = []
    parts = [('topleft', 0, 0, 22, 50), ('top', 22, 0, 64, 50), ('topright', 86, 0, 22, 50),
             ('left', 0, 50, 22, 32), ('center', 22, 50, 64, 32), ('right', 86, 50, 22, 32),
             ('bottomleft', 0, 82, 22, 22), ('bottom', 22, 82, 64, 22), ('bottomright', 86, 82, 22, 22)]
    for prefix in ('decoration', 'decoration-inactive'):
        for part, x, y, w, h in parts:
            inner_left = 16 if 'left' in part else 0
            inner_right = 16 if 'right' in part else 0
            inner_top = 16 if 'top' in part else 0
            inner_bottom = 16 if 'bottom' in part else 0
            cx, cy, cw, ch = x + inner_left, y + inner_top, w - inner_left - inner_right, h - inner_top - inner_bottom
            shapes = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#071323" fill-opacity=".035"/>',
                      f'<rect x="{x + inner_left / 2}" y="{y + inner_top / 2}" width="{w - (inner_left + inner_right) / 2}" height="{h - (inner_top + inner_bottom) / 2}" fill="#071323" fill-opacity=".07"/>',
                      f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" fill="{base}" fill-opacity=".82"/>',
                      f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" fill="url(#streak)"/>']
            if 'top' in part:
                # 6 px camın altında başlık metni için opak 28 px şerit.
                shapes += [f'<rect x="{cx}" y="{cy + 6}" width="{cw}" height="28" fill="{base}"/>',
                           f'<path d="M{cx},{cy + 1}h{cw}" stroke="#fff" stroke-opacity=".72"/>']
            pieces.append(f'<g id="{prefix}-{part}">' + ''.join(shapes) + '</g>')
    # Aurorae supportsMask=true olduğunda bu FrameSvg maskesini KDecoration
    # blurRegion'a iletir. KWin bunu dekorasyon - içerik alanıyla kesiştirir.
    for part, x, y, w, h in parts:
        pieces.append(f'<rect id="mask-{part}" x="{x + 128}" y="{y}" width="{w}" height="{h}" fill="#000"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="104" viewBox="0 0 256 104">'
            '<defs><linearGradient id="streak" x1="0" y1="0" x2="1" y2="1">'
            '<stop stop-color="#fff" stop-opacity=".32"/><stop offset=".38" stop-color="#fff" stop-opacity=".03"/>'
            '<stop offset=".42" stop-color="#fff" stop-opacity=".23"/><stop offset=".59" stop-color="#fff" stop-opacity="0"/>'
            '</linearGradient></defs>' + ''.join(pieces) + '</svg>\n')


def button_svg(action, accent, dark):
    base, ink = colors(accent, dark), '#f5f8fd' if dark else '#172b40'
    glyphs = {'close': 'M10 10L18 18M18 10L10 18', 'minimize': 'M9 18H19',
              'maximize': 'M9 10H19V20H9Z', 'restore': 'M9 12H17V20H9ZM12 9H20V17',
              'alldesktops': 'M10 10H18V18H10Z', 'keepabove': 'M9 17L14 12L19 17',
              'keepbelow': 'M9 12L14 17L19 12', 'shade': 'M9 10H19M9 17L14 12L19 17',
              'help': 'M11 11C11 7 20 8 17 12L14 15M14 18V19'}
    if action not in glyphs:
        raise ValueError('Bilinmeyen Aurorae düğmesi.')
    pieces = []
    for index, state in enumerate(('active', 'inactive', 'hover', 'pressed', 'deactivated', 'hover-inactive', 'pressed-inactive')):
        fill = '#b92541' if action == 'close' else base
        line = '#ffffff' if action == 'close' else ink
        border = accent if 'hover' in state or state == 'pressed' else base
        pieces.append(f'<g id="{state}" transform="translate({index * 32},0)">'
                      f'<rect width="28" height="28" rx="5" fill="{fill}"/>'
                      f'<rect x=".5" y=".5" width="27" height="27" rx="5" fill="none" stroke="{border}"/>'
                      f'<path d="{glyphs[action]}" fill="none" stroke="{line}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></g>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="224" height="28">' + ''.join(pieces) + '</svg>\n'


def install(name, accent, dark):
    if not re.fullmatch(r'oguzdows-glass-[a-f0-9]{12}', name):
        raise ValueError('Yalnız ürüne ait Aurorae adı yazılabilir.')
    colors(accent, dark)
    root = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    directory = private_directory(root / 'aurorae/themes' / name)
    atomic_text(directory / 'decoration.svg', decoration_svg(accent, dark))
    for action in ('close', 'minimize', 'maximize', 'restore', 'alldesktops', 'keepabove', 'keepbelow', 'shade', 'help'):
        atomic_text(directory / (action + '.svg'), button_svg(action, accent, dark))
    ink = '#f5f8fd' if dark else '#172b40'
    atomic_text(directory / (name + 'rc'), f'[General]\nActiveTextColor={ink}\nInactiveTextColor={ink}\n'
                'UseTextShadow=false\nTitleAlignment=Left\nAnimation=0\nShadow=true\n'
                '[Layout]\nBorderLeft=6\nBorderRight=6\nBorderBottom=6\nBorderTop=6\n'
                'TitleHeight=26\nTitleEdgeTop=6\nTitleEdgeBottom=2\nTitleEdgeLeft=6\nTitleEdgeRight=6\n'
                'TitleEdgeTopMaximized=6\nTitleEdgeBottomMaximized=2\nTitleEdgeLeftMaximized=4\nTitleEdgeRightMaximized=4\n'
                'TitleBorderLeft=8\nTitleBorderRight=8\nButtonWidth=28\nButtonHeight=26\nButtonSpacing=2\n'
                'PaddingLeft=16\nPaddingRight=16\nPaddingTop=16\nPaddingBottom=16\n')
    atomic_text(directory / 'metadata.desktop', f'[Desktop Entry]\nName=OğuzDows Glass\nX-KDE-PluginInfo-Name={name}\n'
                'X-KDE-PluginInfo-Version=1\nX-KDE-PluginInfo-License=GPL-3.0-or-later\n')
    return '__aurorae__svg__' + name
