"""PC / ARM ortak kaynak kararı; içe aktarımda servis, ağ veya ayar değişmez.

mini / light bir özellik listesi DEĞİLDİR: yalnızca efekt ve zram bütçesidir.
512 MiB'de modern web, video kurgu veya Android için yeterlilik sözü verilmez.
"""
from __future__ import annotations

import json
from pathlib import Path

PROFILES = ('auto', 'mini', 'light', 'full')


def text(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace').replace('\x00', '').strip()
    except OSError:
        return ''


def policy(memory_kib, legacy=False, requested='auto', nomodeset=False, graphics=True):
    if requested not in PROFILES:
        raise ValueError('Profil auto, mini, light veya full olmalı.')
    memory_kib = max(0, int(memory_kib))
    automatic = 'mini' if legacy or 0 < memory_kib <= 786432 else 'light' if memory_kib <= 2097152 else 'full'
    # Bilinmeyen RAM de güvenli tarafta kalır. full, düşük RAM / nomodeset
    # korumasını aşarak kompozitörü açma yetkisi değildir.
    profile = automatic if requested == 'auto' else requested
    effects = bool(memory_kib > 2097152 and not legacy and not nomodeset and profile == 'full' and graphics)
    usable_mb = max(1, memory_kib // 1024) if memory_kib else 512
    zram_mb = min(usable_mb, max(64, min(384 if profile == 'mini' else 1024,
                                      usable_mb * (75 if profile == 'mini' else 50) // 100)))
    return {'profile': profile, 'memory_kib': memory_kib, 'compositing': effects,
            # Uygunluk; kendiliğinden açılmaz. Aero ayrıca açık tercih ister.
            'animations': effects, 'zram_mb': zram_mb, 'algorithm': 'lz4',
            'swappiness': 100, 'page_cluster': 0,
            'thumbnail_pixels': 160 if automatic == 'mini' else 224,
            'legacy_cpu': bool(legacy), 'graphics_candidate': bool(graphics)}


def current_policy(root=Path('/')):
    memory = 0
    for line in text(root / 'proc/meminfo').splitlines():
        if line.startswith('MemTotal:'):
            try:
                memory = max(0, int(line.split()[1]))
            except (ValueError, IndexError):
                pass
    requested = 'auto'
    # Pi'nin mevcut profil dosyası geriye uyumlu ve yalnızca Pi'de geçerlidir.
    board = text(root / 'sys/firmware/devicetree/base/model') or text(root / 'proc/device-tree/model')
    pi = (root / 'etc/oguzdows/pi-image.json').is_file() or board.startswith('Raspberry Pi')
    for name in ('etc/oguzdows/resources.conf', *(['etc/oguzdows/pi.conf'] if pi else [])):
        for line in text(root / name).splitlines():
            key, sep, value = line.partition('#')[0].strip().partition('=')
            if sep and key.strip() == 'profile':
                requested = value.strip()
    args = text(root / 'proc/cmdline').split()
    for arg in args:
        if arg.startswith('oguzdows.profile='):
            requested = arg.partition('=')[2]
    if requested not in PROFILES:
        requested = 'auto'
    legacy = board.startswith(('Raspberry Pi Zero', 'Raspberry Pi 1 ', 'Raspberry Pi Model ',
                               'Raspberry Pi Compute Module Rev')) and not board.startswith('Raspberry Pi Zero 2')
    # RAM tek başına GPU kanıtı değildir. Bilinen DRM sürücüsü yoksa statik kal.
    drivers = {path.resolve().name for path in (root / 'sys/class/drm').glob('card[0-9]*/device/driver') if path.is_symlink()}
    graphics = bool(drivers & {'vc4', 'v3d', 'i915', 'xe', 'amdgpu', 'radeon', 'nouveau',
                               'nvidia', 'virtio_gpu', 'panfrost', 'lima', 'msm', 'etnaviv'})
    return policy(memory, legacy, requested, 'nomodeset' in args, graphics)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='store_true')
    args = parser.parse_args()
    value = current_policy()
    print(value['profile'] if args.profile else json.dumps(value, ensure_ascii=False))
