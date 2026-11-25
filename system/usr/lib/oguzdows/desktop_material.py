"""Versioned per-accent Xfwm / GTK themes, preserving each layout's identity.

Immutable colour-keyed themes make GTK and Xfwm reload immediately. Only
owned generated directories are collected; wallpaper files / user pins and
personal themes are never copied, edited or removed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import tempfile
from pathlib import Path

from desktop_state import private_directory
from profiles import atomic_text, theme, PROFILES

MARKER = 'oguzdows-generated-material-v3\n'
PREFIX = 'OguzDowsAeroGlassUser-'


def foreground(accent):
    components = [int(accent[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in components]
    luminance = sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    return '#11202f' if luminance > .179 else '#ffffff'


def css(accent, dark, parent, glass):
    text = '#edf2fa' if dark else '#1d293b'
    base = 24 if dark else 246
    tint = [round(int(accent[i:i + 2], 16) * .12 + base * .88) for i in (1, 3, 5)]
    rgb = ', '.join(map(str, tint))
    panel_alpha, surface_alpha = ('.84', '.93') if glass else ('1', '1')
    selected_text = foreground(accent)
    return f'''@import url("/usr/share/themes/{parent}/gtk-3.0/gtk.css");
@import url("/usr/share/oguzdows/ui/window-geometry.css");
@define-color theme_selected_bg_color {accent};
@define-color selected_bg_color {accent};
@define-color theme_selected_fg_color {selected_text};
@define-color selected_fg_color {selected_text};
@define-color oguzdows_glass_tint rgb({rgb});
/* Background alpha only. No widget / text / whole-window opacity rule. */
window.background, dialog.background {{ background-image: none; background-color: rgba({rgb}, {surface_alpha}); color: {text}; }}
headerbar, headerbar:backdrop, .titlebar {{ background-image: none; background-color: rgba({rgb}, {surface_alpha}); color: {text}; border-bottom: 1px solid alpha({accent}, .28); }}
headerbar label:backdrop {{ color: {text}; }}
selection, treeview:selected, iconview:selected, flowboxchild:selected,
.view:selected, .view:selected:focus, row:selected {{ background-color: {accent}; color: {selected_text}; }}
button.suggested-action, button.suggested-action:hover,
check:checked, radio:checked, switch:checked {{ background-image: none; background-color: {accent}; border-color: {accent}; color: {selected_text}; }}
entry:focus, button:focus, spinbutton:focus {{ border-color: {accent}; }}
progressbar progress, scale highlight {{ background-image: none; background-color: {accent}; }}
notebook > header > tabs > tab:checked {{ border-bottom: 2px solid {accent}; }}
.xfce4-panel.background {{ background-image: none; background-color: rgba({rgb}, {panel_alpha}); color: {text}; border: 1px solid alpha({text}, .18); }}
.xfce4-panel button, .xfce4-panel label {{ color: {text}; }}
.xfce4-panel button:checked {{ background-color: alpha({accent}, .18); }}
menu, .menu, popover.background {{ background-image: none; background-color: rgba({rgb}, {surface_alpha}); color: {text}; border: 1px solid alpha({text}, .18); }}
menuitem:hover {{ background-color: {accent}; color: {selected_text}; }}
/* Thunar uses real GTK nodes; file/text panes stay opaque and readable. */
.thunar .standard-view, .thunar .view, .thunar textview text {{ background-color: {'#202731' if dark else '#ffffff'}; }}
.thunar .view:selected, .thunar .view:selected:focus {{ background-color: {accent}; color: {selected_text}; }}
.thunar .sidebar {{ background-color: rgb({rgb}); }}
'''


def install(accent, dark, renderer=None, *, identifier='oguzdows', glass=True, base_theme=None):
    if not re.fullmatch(r'#[a-fA-F0-9]{6}', accent) or type(dark) is not bool or type(glass) is not bool or identifier not in PROFILES:
        raise ValueError('Materyal rengi / türü geçersiz.')
    accent = accent.lower()
    parent = base_theme or ('OguzDowsAeroGlassDark' if dark else 'OguzDowsAeroGlass')
    allowed = {theme(key, mode) for key in PROFILES for mode in ('light', 'dark')}
    allowed.update(('OguzDowsAero', 'OguzDowsAeroDark', 'OguzDowsAeroGlass', 'OguzDowsAeroGlassDark'))
    if parent not in allowed:
        raise ValueError('Materyalin ana teması izin listesinde değil.')
    prefix = (theme(identifier, 'dark' if dark else 'light') + 'User-') if identifier in ('mac', 'windows11') or not glass else PREFIX
    base = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'themes'
    key = hashlib.sha256((MARKER + accent + str(dark) + str(glass) + parent + identifier).encode()).hexdigest()[:16]
    name = prefix + key
    target = private_directory(base / name)
    marker = target / '.oguzdows-owned'
    if marker.is_symlink():
        raise ValueError('Materyal kimliği bağlantı olamaz.')
    if marker.is_file() and marker.read_text() == MARKER:
        if (target / 'xfwm4/themerc').is_file() and (target / 'gtk-3.0/gtk.css').is_file():
            return name
    # Never merge into a foreign directory, even if it happens to use our name.
    if any(target.iterdir()):
        raise ValueError('Materyal hedefi bize ait değil veya yarım kalmış; kişisel dosya üzerine yazılmadı.')
    if renderer is None:
        source = Path(__file__).with_name('render-assets.py')
        if not source.is_file():
            source = Path('/usr/lib/oguzdows/render-assets.py')  # fixed installed helper, never a user-supplied script
        if not source.is_file():
            raise RuntimeError('İmajın çevrimdışı materyal üreticisi kurulu değil.')
        spec = importlib.util.spec_from_file_location('_oguzdows_material_renderer', source)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        renderer = module.window_theme
    # Publish only a fully rendered theme. An interrupted render never becomes
    # a selected theme. A failed preference transaction can still reselect its
    # exact previous immutable theme, not a mutated directory of old colours.
    with tempfile.TemporaryDirectory(prefix='.oguzdows-material-', dir=base) as temporary:
        root = Path(temporary)
        renderer(root, name, light=not dark, xp=identifier == 'oguzdows' and not glass, accent=accent, glass=glass)
        built = root / 'usr/share/themes' / name
        gtk = private_directory(built / 'gtk-3.0')
        atomic_text(gtk / 'gtk.css', css(accent, dark, parent, glass))
        gtk2 = private_directory(built / 'gtk-2.0')
        gtk2_parent = theme(identifier, 'dark' if dark else 'light')
        atomic_text(gtk2 / 'gtkrc', f'include "/usr/share/themes/{gtk2_parent}/gtk-2.0/gtkrc"\n'
                    f'gtk-color-scheme = "selected_bg_color:{accent}\\nselected_fg_color:{foreground(accent)}"\n')
        atomic_text(built / 'index.theme', f'[Desktop Entry]\nName=OğuzDows · {identifier} · {accent}\n'
                    f'[X-GNOME-Metatheme]\nGtkTheme={name}\nIconTheme=OguzDows\n')
        atomic_text(built / '.oguzdows-owned', MARKER)
        target.rmdir()  # our empty, verified target only; no personal contents
        built.replace(target)
        target.chmod(0o700)
    # Do not collect theme history on apply: the previous theme may be the
    # first-change backup / another logged-in display's rollback target. Tiny
    # palette themes are immutable; explicit cleanup is safer than broken undo.
    return name
