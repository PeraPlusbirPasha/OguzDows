#!/usr/bin/env python3
"""Türkiye galerisini listeler ve kullanıcının Xfce duvar kâğıdını değiştirir."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CATALOG = Path("/usr/share/oguzdows/wallpapers.json")
DEFAULT = 'bogaz-sabahi'
LEGACY = {'ay-yildiz': DEFAULT, 'istanbul': DEFAULT, 'kapadokya': 'kapadokya-isigi',
          'pamukkale': 'oludeniz-kiyisi', 'kackar': 'kackar-sisi', 'anadolu': 'tuz-golu-aksami'}


def catalog(path: Path = CATALOG) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in data if isinstance(item, dict) and all(isinstance(item.get(key), str) for key in ("id", "name", "path", "preview"))]
    except (OSError, ValueError, TypeError):
        return []


def state_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "oguzdows/wallpaper"


def run(command):
    return subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          timeout=10, check=False, env={**os.environ, 'LC_ALL': 'C.UTF-8'})


def display_info():
    """Read GDK's real X11 monitor names in a short, separate process.

    Fallback for legacy / software X screens without usable RandR output.
    Never access GTK's shared display from the Welcome worker thread, and
    never invent monitor0 just because display enumeration failed.
    """
    import gi
    gi.require_version('Gdk', '3.0'); gi.require_version('GdkX11', '3.0')
    from gi.repository import Gdk, GdkX11
    Gdk.set_allowed_backends('x11')
    display = Gdk.Display.open(os.environ.get('DISPLAY'))
    if display is None:
        raise RuntimeError('X11 ekranı açılamadı.')
    try:
        if not isinstance(display, GdkX11.X11Display) or not 1 <= display.get_n_monitors() <= 128:
            raise RuntimeError('X11 monitör bilgisi alınamadı.')
        return {'screen': display.get_default_screen().get_number(),
                'monitors': [re.sub(r'\s', '', display.get_monitor(index).get_model() or str(index))
                             for index in range(display.get_n_monitors())]}
    finally:
        display.close()


def xfce_properties():
    """Stored keys are history, not evidence that a monitor is still active.

    xfdesktop 4.18/4.20 may have only image-style / colour defaults for the
    current connector. Always include live RandR outputs, even if another
    (disconnected) connector already has last-image. Keep existing native
    prefixes for GDK's older numeric monitor identifiers and exact rollback.
    """
    listing = run(['xfconf-query', '-c', 'xfce4-desktop', '-l'])
    prefixes = set()
    if listing.returncode == 0:
        for line in listing.stdout.splitlines():
            match = re.fullmatch(r'(/backdrop/screen[0-9]+/monitor[^/\s]+/workspace[0-9]+/)[^/\s]+', line.strip())
            if match:
                if len(match[1]) > 1024:
                    raise ValueError('Duvar kâğıdı ayar yolunun uzunluğu geçersiz.')
                prefixes.add(match[1])
    try:
        monitors = run(['xrandr', '--query'])
    except (OSError, subprocess.SubprocessError):
        monitors = subprocess.CompletedProcess([], 1, '')
    screen = re.search(r'^Screen ([0-9]{1,3}):', monitors.stdout, re.MULTILINE)
    names = set(re.findall(r'^([^/\s]{1,255}) connected(?: primary)? [0-9]+x[0-9]+[+-][0-9]+[+-][0-9]+(?:\s|$)',
                           monitors.stdout, re.MULTILINE))
    screen_number = int(screen[1]) if screen is not None else None
    if monitors.returncode or screen_number is None or not names:
        # RandR is not a GPU requirement. Query GDK on its OWN connection in
        # a bounded helper, not from the UI worker's shared display thread.
        try:
            result = run([sys.executable, '-I', str(Path(__file__).resolve()), '--display-info'])
            if result.returncode or len(result.stdout) > 65536:
                raise ValueError('Monitor helper failed')
            value = json.loads(result.stdout)
            if (not isinstance(value, dict) or set(value) != {'screen', 'monitors'}
                    or type(value['screen']) is not int or not 0 <= value['screen'] <= 999
                    or not isinstance(value['monitors'], list) or not 1 <= len(value['monitors']) <= 128
                    or any(not isinstance(name, str) or not re.fullmatch(r'[^/\s\x00-\x1f\x7f]{1,255}', name)
                           for name in value['monitors'])):
                raise ValueError('Monitor helper reply invalid')
            screen_number, names = value['screen'], set(value['monitors'])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            raise RuntimeError('Etkin X11 monitörleri okunamadı; duvar kâğıdı değiştirilmedi.') from error
    count = run(['xfconf-query', '-c', 'xfwm4', '-p', '/general/workspace_count'])
    value = count.stdout.strip() if count.returncode == 0 else '4'  # Xfce default before the first user override.
    if not re.fullmatch(r'[0-9]{1,3}', value) or not 1 <= int(value) <= 128:
        raise ValueError('Xfce çalışma alanı sayısı güvenle okunamadı.')
    # Check the cartesian product before constructing it, not after allocating
    # unbounded targets supplied by a malformed display/configuration reply.
    if len(names) * int(value) > 128:
        raise ValueError('Duvar kâğıdı ekran / çalışma alanı sınırını aşıyor.')
    prefixes.update(f'/backdrop/screen{screen_number}/monitor{name}/workspace{workspace}/'
                    for name in names for workspace in range(int(value)))
    if len(prefixes) > 128:
        raise ValueError('Duvar kâğıdı ekran / çalışma alanı sınırını aşıyor.')
    return {prefix + 'last-image' for prefix in prefixes}


def apply(identifier: str, items=None, state: Path | None = None) -> None:
    import desktop_runtime
    if items is None and state is None and desktop_runtime.current() in ('xfce', 'gnome', 'kde'):
        from desktop_preferences import update_and_apply
        update_and_apply({'wallpaper': identifier})
        return
    apply_xfce(identifier, items, state)


def apply_xfce(identifier: str, items=None, state: Path | None = None, undo=None) -> None:
    entries = catalog() if items is None else items
    item = next((entry for entry in entries if entry["id"] == identifier), None)
    if item is None or not Path(item["path"]).is_file():
        raise ValueError("Duvar kâğıdı bulunamadı.")
    properties = xfce_properties()
    from profiles import atomic_text, marker_text
    path = state or state_path()
    old_marker = marker_text(path.parent, path.name)
    rows = []
    for prop in sorted(properties):
        for key, kind, target in ((prop, 'string', item['path']),
                (prop.removesuffix('last-image') + 'image-style', 'int', '5')):
            base = ['xfconf-query', '-c', 'xfce4-desktop', '-p', key]
            result = run(base)
            old = result.stdout.removesuffix('\n') if result.returncode == 0 else None
            if old is not None and (len(old) > 4096 or any(char in old for char in '\n\r\0')
                    or kind == 'int' and not re.fullmatch(r'-?\d+', old)):
                raise ValueError('Önceki duvar kâğıdı ayarı güvenle yedeklenemedi.')
            rows.append((base, kind, old, target))
    changed, marker_attempted = [], False
    def rollback():
        errors = []
        for base, kind, old, target in reversed(changed):
            try:
                actual = run(base)
                if actual.returncode or actual.stdout.removesuffix('\n') != target:
                    continue  # İşlemden sonra haricen değişen anahtarı koru.
                if old is None:
                    run([*base, '--reset'])
                elif run([*base, '-s', old]).returncode:
                    run([*base, '-n', '-t', kind, '-s', old])
                restored = run(base)
                if (None if restored.returncode else restored.stdout.removesuffix('\n')) != old:
                    raise RuntimeError('Duvar kâğıdı geri alma geri okunarak doğrulanamadı: ' + base[-1])
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                errors.append(str(error))
        try:
            if marker_attempted and marker_text(path.parent, path.name) == identifier + '\n':
                if old_marker is None:
                    path.unlink()
                else:
                    atomic_text(path, old_marker)
                if marker_text(path.parent, path.name) != old_marker:
                    raise RuntimeError('Duvar kâğıdı seçim kaydı geri alınamadı.')
        except (OSError, ValueError, RuntimeError) as error:
            errors.append(str(error))
        if errors:
            raise RuntimeError('Duvar kâğıdı işlemi tam geri alınamadı: ' + '; '.join(errors))
    try:
        for base, kind, old, target in rows:
            if old == target:
                continue
            changed.append((base, kind, old, target))
            result = run([*base, '-s', target])
            if result.returncode:
                result = run([*base, '-n', '-t', kind, '-s', target])
            if result.returncode:
                raise RuntimeError('Masaüstü ayarı değiştirilemedi: ' + base[-1])
            actual = run(base)
            if actual.returncode or actual.stdout.removesuffix('\n') != target:
                raise RuntimeError('Duvar kâğıdı ayarı geri okunarak doğrulanamadı: ' + base[-1])
        path.parent.mkdir(parents=True, exist_ok=True)
        marker_attempted = True
        atomic_text(path, identifier + '\n')
        if marker_text(path.parent, path.name) != identifier + '\n':
            raise RuntimeError('Duvar kâğıdı seçim kaydı doğrulanamadı.')
    except Exception as failure:
        try:
            rollback()
        except Exception as error:
            raise RuntimeError('Duvar kâğıdı işlemi başarısız; geri alma da eksik kaldı: ' + str(error)) from failure
        raise
    if undo is not None:
        undo.append(rollback)


def initialize():
    # Sadece ilk giriş / emekliye ayrılan çizimden geçiş. Geçerli seçim veya
    # kullanıcının Xfce'den seçtiği başka görsel her girişte zorlanmaz.
    from profiles import marker_text
    path = state_path()
    selected = marker_text(path.parent, path.name)
    selected = selected.strip() if selected is not None else None
    if selected is None or selected in LEGACY:
        apply(LEGACY.get(selected, DEFAULT))


if __name__ == "__main__":
    if sys.argv[1:] == ['--display-info']:
        try:
            print(json.dumps(display_info()))
        except (OSError, ValueError, RuntimeError, ImportError) as error:
            print(f'OğuzDows ekran bilgisi: {error}', file=sys.stderr)
            raise SystemExit(1)
    elif sys.argv[1:] == ['--initialize']:
        try:
            initialize()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(f"OğuzDows duvar kâğıdı: {error}", file=sys.stderr)
    else:
        raise SystemExit("Kullanım: wallpapers.py --initialize | --display-info")
