"""İsteğe bağlı X11 Aero yetenek kapısı; kaynak uygunluğu GPU kanıtı değildir."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

BASE = Path('/usr/share/oguzdows/picom.conf')
ROOT = BASE.parent / 'compositor'
CONFIGS = {BASE, *(ROOT / (name + '.conf') for name in ('blur', 'blur-still', 'still', 'motion', 'full', 'snap', 'full-snap'))}


def probe():
    """Tek seferlik, süre sınırlı gerçek GLX raporu. Bilinmeyen = statik fallback."""
    def command(argv):
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=4, check=False, env={**os.environ, 'LC_ALL': 'C'})
    try:
        version = command(['/usr/bin/picom', '--version'])
        match = re.search(r'v?(\d+)\.(\d+)', version.stdout)
        major = int(match[1]) if match and version.returncode == 0 else 0
        info = command(['/usr/bin/glxinfo', '-B'])
        report = info.stdout.lower()
        software = any(name in report for name in ('llvmpipe', 'softpipe', 'swrast', 'software rasterizer'))
        accelerated = ('accelerated: yes' in report and 'direct rendering: yes' in report
                       and not software and info.returncode == 0
                       and os.environ.get('LIBGL_ALWAYS_SOFTWARE', '').lower() not in ('1', 'true'))
        return {'major': major, 'accelerated': accelerated}
    except (OSError, subprocess.SubprocessError):
        return {'major': 0, 'accelerated': False}


def plan(preferences, resources, capability=None):
    result = {'config': BASE, 'blur_configured': False, 'spring_configured': False,
              'snap_configured': False, 'note': ''}
    if not resources['compositing'] or preferences['effects'] != 'aero':
        return result
    blur = preferences['blur']
    spring = preferences['motion'] == 'spring'
    reduced = preferences['motion'] == 'reduced'
    if not blur and not spring and not reduced:
        return result  # Eski Aero yükseltmede yeni GPU işi açmaz.
    if reduced and not blur:
        return dict(result, config=ROOT / 'still.conf')
    capability = probe() if capability is None else capability
    if not capability['accelerated'] or capability['major'] < 9:
        return dict(result, config=ROOT / 'still.conf' if reduced else BASE,
                    note='Hızlandırılmış GLX doğrulanamadı; gerçek blur / yay açılmadı, hafif fallback korundu.')
    if spring and capability['major'] < 12:
        spring = False
        result['note'] = 'Picom 9–11 geometri / yay API’si sunmaz; blur desteklenir, pencere yayı için Picom 12+ gerekir.'
    snap = spring and preferences['snap_animation']
    name = ('full-snap' if blur else 'snap') if snap else 'full' if blur and spring else 'blur' if blur else 'motion' if spring else 'still' if reduced else None
    if name:
        result['config'] = ROOT / ('blur-still.conf' if name == 'blur' and reduced else name + '.conf')
        result.update(blur_configured=blur, spring_configured=spring, snap_configured=snap)
    return result
