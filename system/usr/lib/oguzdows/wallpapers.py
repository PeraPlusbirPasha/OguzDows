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


def apply_xfce(identifier: str, items=None, state: Path | None = None) -> None:
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
    applied = 0
    for prop in sorted(properties):
        command = ["xfconf-query", "-c", "xfce4-desktop", "-p", prop]
        result = run([*command, "-s", item["path"]])
        if result.returncode:
            result = run([*command, "-n", "-t", "string", "-s", item["path"]])
        if result.returncode == 0:
            applied += 1
        style = ["xfconf-query", "-c", "xfce4-desktop", "-p", prop.removesuffix("last-image") + "image-style"]
        if run([*style, "-s", "5"]).returncode:
            run([*style, "-n", "-t", "int", "-s", "5"])
    if not applied:
        raise RuntimeError("Masaüstü ayarı değiştirilemedi. Xfce oturumunda yeniden dene.")
    path = state or state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(identifier + "\n", encoding="utf-8")
    temporary.replace(path)


def initialize():
    # Sadece ilk giriş / emekliye ayrılan çizimden geçiş. Geçerli seçim veya
    # kullanıcının Xfce'den seçtiği başka görsel her girişte zorlanmaz.
    path = state_path()
    selected = path.read_text().strip() if path.exists() else None
    if selected is None or selected in LEGACY:
        apply(LEGACY.get(selected, DEFAULT))


if __name__ == "__main__":
    if sys.argv[1:] != ["--initialize"]:
        raise SystemExit("Kullanım: wallpapers.py --initialize")
    try:
        initialize()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"OğuzDows duvar kâğıdı: {error}", file=sys.stderr)
