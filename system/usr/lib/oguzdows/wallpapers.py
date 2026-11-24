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
    return subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)


def apply(identifier: str, items=None, state: Path | None = None) -> None:
    import desktop_runtime
    if items is None and state is None and desktop_runtime.current() in ('gnome', 'kde'):
        from desktop_preferences import update_and_apply
        update_and_apply({'wallpaper': identifier})
        return
    apply_xfce(identifier, items, state)


def apply_xfce(identifier: str, items=None, state: Path | None = None, undo=None) -> None:
    entries = catalog() if items is None else items
    item = next((entry for entry in entries if entry["id"] == identifier), None)
    if item is None or not Path(item["path"]).is_file():
        raise ValueError("Duvar kâğıdı bulunamadı.")
    listing = run(["xfconf-query", "-c", "xfce4-desktop", "-l"])
    properties = {line.strip() for line in listing.stdout.splitlines()
                  if re.fullmatch(r"/backdrop/[^\s]+/last-image", line.strip())}
    if not properties:
        monitors = run(["xrandr", "--query"])
        names = [match.group(1) for match in re.finditer(r"^(\S+) connected", monitors.stdout, re.MULTILINE)] or ["0"]
        properties = {f"/backdrop/screen0/monitor{monitor}/workspace{workspace}/last-image"
                      for monitor in names for workspace in range(4)}
    from profiles import atomic_text, marker_text
    path = state or state_path()
    old_marker = marker_text(path.parent, path.name)
    if len(properties) > 128:
        raise ValueError('Duvar kâğıdı ekran / çalışma alanı sınırını aşıyor.')
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
    if sys.argv[1:] != ["--initialize"]:
        raise SystemExit("Kullanım: wallpapers.py --initialize")
    try:
        initialize()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"OğuzDows duvar kâğıdı: {error}", file=sys.stderr)
