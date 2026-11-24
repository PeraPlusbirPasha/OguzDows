"""Seçilen renkten statik Xfwm/GTK döşemeleri; duvar kâğıdı izleyicisi yok."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
from pathlib import Path

from desktop_state import private_directory
from profiles import atomic_text

MARKER = 'oguzdows-generated-material-v1\n'
PREFIX = 'OguzDowsAeroGlassUser-'


def install(accent, dark, renderer=None):
    if not re.fullmatch(r'#[a-fA-F0-9]{6}', accent) or type(dark) is not bool:
        raise ValueError('Materyal rengi / türü geçersiz.')
    base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'themes'
    key = hashlib.sha256((accent.lower() + str(dark)).encode()).hexdigest()[:12]
    name = PREFIX + key
    target = private_directory(base / name)
    if (target / '.oguzdows-owned').is_symlink():
        raise ValueError('Materyal kimliği bağlantı olamaz.')
    if (target / '.oguzdows-owned').is_file() and (target / '.oguzdows-owned').read_text() == MARKER:
        if (target / 'xfwm4/themerc').is_file() and (target / 'gtk-3.0/gtk.css').is_file():
            return name
    if renderer is None:
        source = Path(__file__).with_name('render-assets.py')
        if not source.is_file():
            raise RuntimeError('İmajın çevrimdışı materyal üreticisi kurulu değil.')
        spec = importlib.util.spec_from_file_location('_oguzdows_material_renderer', source)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        renderer = module.window_theme
    # Var olan çevrimdışı üretecin kök sözleşmesiyle geçici, yalnız bize ait
    # dizinde üret; başka kullanıcının teması / dosyası içeri alınmaz.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='.oguzdows-material-', dir=base) as temporary:
        root = Path(temporary)
        renderer(root, name, light=not dark, accent=accent)
        shutil.copytree(root / 'usr/share/themes' / name / 'xfwm4', target / 'xfwm4', dirs_exist_ok=True)
    gtk = private_directory(target / 'gtk-3.0')
    parent = 'OguzDowsAeroGlassDark' if dark else 'OguzDowsAeroGlass'
    atomic_text(gtk / 'gtk.css', f'@import url("/usr/share/themes/{parent}/gtk-3.0/gtk.css");\n'
        f'@define-color theme_selected_bg_color {accent};\n@define-color selected_bg_color {accent};\n')
    atomic_text(target / 'index.theme', f'[Desktop Entry]\nName=OğuzDows kişisel cam\n'
        f'[X-GNOME-Metatheme]\nGtkTheme={name}\nIconTheme=OguzDows\n')
    atomic_text(target / '.oguzdows-owned', MARKER)
    # Tüm renk geçmişini sonsuz büyütme. Yalnız geçerli özgün işaretçimizi
    # taşıyan, bağı olmayan kendi altı eski temamızı tut; yabancıya dokunma.
    candidates = []
    for directory in base.glob(PREFIX + '*'):
        marker = directory / '.oguzdows-owned'
        if (directory != target and not directory.is_symlink() and marker.is_file()
                and not marker.is_symlink() and marker.stat().st_size == len(MARKER)
                and marker.read_text() == MARKER):
            candidates.append(directory)
    for directory in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)[5:]:
        shutil.rmtree(directory)
    return name
