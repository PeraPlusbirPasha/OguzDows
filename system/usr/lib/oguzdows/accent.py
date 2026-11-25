#!/usr/bin/env python3
"""Bounded local wallpaper palette worker; the optional observer is native C.

No HTTP, pywal shell, desktop screenshot, root service, periodic sampling or
unbounded image decode. A filename is data, never an executable / CSS string.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desktop_state as state

MAX_BYTES = 40 * 1024 * 1024
MAX_PIXELS = 25_000_000
BACKDROP = re.compile(r'/backdrop/[^\s]+/last-image')


def image_path(value):
    path = Path(value).expanduser().resolve(strict=True)
    details = path.stat()
    if not stat.S_ISREG(details.st_mode) or not 0 < details.st_size <= MAX_BYTES:
        raise ValueError('Vurgu için normal, en fazla 40 MiB yerel görsel gerekir.')
    if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise ValueError('Vurgu için JPEG / PNG / WebP gerekir; SVG veya komut açılmaz.')
    return path


def extract(value):
    from PIL import Image, ImageOps
    path = image_path(value)
    info = path.stat()
    fingerprint = hashlib.sha256((str(path) + f'\0{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}').encode()).hexdigest()
    cache = state.state_directory() / 'wallpaper-palette.json'
    old = state.read_json(cache, {})
    if (isinstance(old, dict) and old.get('fingerprint') == fingerprint
            and re.fullmatch('#[0-9a-f]{6}', old.get('accent', ''))):
        return old['accent']
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(path) as source:
            if source.width * source.height > MAX_PIXELS:
                raise ValueError('Görsel 25 megapiksel renk örnekleme sınırını aşıyor.')
            source.draft('RGB', (96, 96))
            source.thumbnail((64, 64))
            image = ImageOps.exif_transpose(source).convert('RGBA')
            background = Image.new('RGBA', image.size, '#808080')
            background.alpha_composite(image)
            sampled = background.convert('RGB').quantize(colors=12).convert('RGB')
            colors = sampled.getcolors(4096) or []
    candidates = []
    for count, (red, green, blue) in colors:
        hue, saturation, brightness = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        if .13 < brightness < .98:
            candidates.append((count * (.25 + saturation), hue, saturation, brightness))
    if candidates:
        _weight, hue, saturation, brightness = max(candidates)
        rgb = colorsys.hsv_to_rgb(hue, min(.76, max(.36, saturation)), min(.75, max(.43, brightness)))
        color = '#' + ''.join(f'{round(component * 255):02x}' for component in rgb)
    else:
        color = state.DEFAULTS['accent']
    state.atomic_json(cache, {'fingerprint': fingerprint, 'accent': color})
    return color


def current_wallpaper(changed_property=None, execute=None):
    if execute is None:
        def execute(command):
            return subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
    if changed_property is not None:
        if not BACKDROP.fullmatch(changed_property) or len(changed_property) > 1024:
            raise ValueError('Xfce duvar kâğıdı anahtarı geçersiz.')
        properties = [changed_property]
    else:
        listing = execute(['/usr/bin/xfconf-query', '-c', 'xfce4-desktop', '-l'])
        if listing.returncode:
            raise RuntimeError('Xfce duvar kâğıdı kanalı okunamadı.')
        properties = sorted(line.strip() for line in listing.stdout.splitlines() if BACKDROP.fullmatch(line.strip()))
        if len(properties) > 128:
            raise ValueError('Duvar kâğıdı ekran / çalışma alanı sınırı aşıldı.')
        # Deterministic first screen/workspace for startup; actual changes carry
        # their precise monitor/workspace key and do not rewrite other screens.
    for prop in properties:
        result = execute(['/usr/bin/xfconf-query', '-c', 'xfce4-desktop', '-p', prop])
        value = result.stdout.removesuffix('\n') if result.returncode == 0 else ''
        if value and not any(char in value for char in '\n\r\0'):
            try:
                return image_path(value)
            except (OSError, ValueError):
                if changed_property:
                    raise
    raise ValueError('Xfce’de okunabilir yerel bir duvar kâğıdı bulunamadı.')


def ensure_observer(preferences):
    if preferences['accent_source'] != 'wallpaper' or os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        return
    import desktop_runtime as runtime
    if runtime.current() != 'xfce':
        return
    binary = Path('/usr/lib/oguzdows/oguzdows-accent-watch')
    if binary.is_file() and os.access(binary, os.X_OK):
        from gi.repository import GLib
        GLib.spawn_async([str(binary)], flags=GLib.SpawnFlags.STDOUT_TO_DEV_NULL | GLib.SpawnFlags.STDERR_TO_DEV_NULL)


def sync(changed_property=None):
    import desktop_runtime as runtime
    import desktop_preferences as preferences
    runtime.normal_session()
    if runtime.current() != 'xfce':
        raise ValueError('Otomatik xfconf izleme yalnız Xfce/X11 içindir.')
    original = state.load()
    if original['accent_source'] != 'wallpaper':
        return {'changed': False, 'message': 'Otomatik renk kapalı; kullanıcı rengi korundu.'}
    path = current_wallpaper(changed_property)
    color = extract(path)
    if original['accent'] == color:
        return {'changed': False, 'accent': color, 'message': 'Duvar kâğıdı rengi zaten güncel.'}
    result = preferences.update_and_apply({'accent': color}, observed_wallpaper=path)
    return {**result, 'changed': True, 'accent': color}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--sync', action='store_true')
    actions.add_argument('--extract', type=Path)
    actions.add_argument('--enable', action='store_true')
    actions.add_argument('--disable', action='store_true')
    actions.add_argument('--session', action='store_true')
    parser.add_argument('--changed-property')
    args = parser.parse_args(argv)
    try:
        if args.extract:
            result = {'accent': extract(args.extract)}
        elif args.sync:
            result = sync(args.changed_property)
        else:
            import desktop_runtime as runtime
            import desktop_preferences as preferences
            runtime.normal_session()
            if args.session:
                ensure_observer(state.load())
                result = {'message': 'Otomatik renk izleyicisi yalnız etkin tercihte başlatılır.'}
            else:
                result = preferences.update_and_apply({'accent_source': 'wallpaper' if args.enable else 'theme'})
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 75 if isinstance(error, RuntimeError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
