"""Açık cihaz sözleşmeleri; bir mimari bütün kartlar için boot desteği değildir."""
from __future__ import annotations

import json
import platform
from pathlib import Path

from pi_support import is_pi, model

PROFILES = {
    'pc-amd64': {'name': 'PC · 64 bit', 'arch': 'amd64', 'suite': 'trixie', 'boot': 'BIOS / x86_64 UEFI', 'tier': 'PC imajı', 'phone': False, 'physical_verified': False},
    'pc-i386': {'name': 'PC · 32 bit PAE', 'arch': 'i386', 'suite': 'bookworm', 'boot': 'BIOS · i686 / PAE', 'tier': 'PC imajı', 'phone': False, 'physical_verified': False},
    'rpi-armhf': {'name': 'Pi Zero / 1 / 2 / 3 / 4 · 32 bit', 'arch': 'armhf', 'suite': 'bookworm', 'boot': 'Pi firmware + ARMv6 / v7 çekirdekleri ve kart DTB’leri; Pi 5 bu imajın hedefi değil', 'tier': 'Ayrı pi-gen imaj tarifi; fiziksel test bekliyor', 'phone': False, 'physical_verified': False},
    'rpi-arm64': {'name': 'Pi Zero 2 / 3 / 4 / 5 · 64 bit', 'arch': 'arm64', 'suite': 'bookworm', 'boot': 'Pi firmware + kernel8 / kernel_2712 + kart DTB’leri; ilk Zero / Pi 1 çalışmaz', 'tier': 'Ayrı pi-gen imaj tarifi; fiziksel test bekliyor', 'phone': False, 'physical_verified': False},
    'arm64-uefi': {'name': 'ARM64 · UEFI bilgisayar', 'arch': 'arm64', 'suite': 'trixie', 'boot': 'Cihaz üreticisinin çalışan ARM64 UEFI / ACPI ve kendi kurulu Linux çekirdeği', 'tier': 'Deneysel masaüstü katmanı; önyüklenebilir imaj değildir', 'phone': False, 'physical_verified': False},
    'pinephone': {'name': 'PinePhone · Allwinner A64', 'arch': 'arm64', 'suite': 'trixie', 'boot': 'Kart özel U-Boot + sun50i-a64-pinephone DTB + ekran / modem / güç sürücüleri', 'tier': 'Deneysel telefon katmanı; fiziksel test bekliyor', 'phone': True, 'physical_verified': False},
    'pinephone-pro': {'name': 'PinePhone Pro · RK3399S', 'arch': 'arm64', 'suite': 'trixie', 'boot': 'Kart özel Tow-Boot / U-Boot + rk3399-pinephone-pro DTB + güç / ekran sürücüleri', 'tier': 'Deneysel telefon katmanı; fiziksel test bekliyor', 'phone': True, 'physical_verified': False},
    'rockpro64': {'name': 'ROCKPro64 · RK3399', 'arch': 'arm64', 'suite': 'trixie', 'boot': 'Kart özel U-Boot + rk3399-rockpro64 DTB + çalışan cihaz Linux’u', 'tier': 'Deneysel SBC katmanı; fiziksel test bekliyor', 'phone': False, 'physical_verified': False},
}
OVERLAY_PROFILES = ('arm64-uefi', 'pinephone', 'pinephone-pro', 'rockpro64')


def get(identifier):
    if identifier not in PROFILES:
        raise ValueError('Cihaz profili tanınmıyor. Rastgele çekirdek / DTB veya telefon imajı seçilmez.')
    return {'id': identifier, **PROFILES[identifier]}


def read_json(path):
    try:
        if path.stat().st_size > 8192:
            return {}
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def current(root=Path('/'), machine=None):
    declared = read_json(root / 'etc/oguzdows/device.json')
    identifier = declared.get('profile')
    if identifier in PROFILES:
        return get(identifier)
    info = read_json(root / 'usr/share/oguzdows/build-info.json')
    if is_pi(root):
        return get('rpi-arm64' if info.get('arch') == 'arm64' else 'rpi-armhf')
    board = model(root).lower()
    if 'pinephone-pro' in board or 'pinephone pro' in board:
        return get('pinephone-pro')
    if 'pinephone' in board:
        return get('pinephone')
    if 'rockpro64' in board:
        return get('rockpro64')
    machine = platform.machine() if machine is None else machine
    if machine in ('x86_64', 'i386', 'i486', 'i586', 'i686'):
        return get('pc-amd64' if machine == 'x86_64' else 'pc-i386')
    return {'id': 'unknown', 'name': model(root) or 'Tanınmayan ARM / cihaz', 'arch': machine,
            'suite': '', 'boot': 'Cihaz özgü çekirdek, firmware, DTB ve boot yolu gerekli.',
            'tier': 'Destek doğrulanmadı; genel Pi imajını bu cihaza yazmayın', 'phone': False, 'physical_verified': False}


def summary(root=Path('/'), machine=None):
    item = current(root, machine)
    return (item['name'] + '\nMimari: ' + item['arch'] + '\nDüzey: ' + item['tier']
            + '\nÖnyükleme: ' + item['boot']
            + '\n\nAPK, yalnızca hazırlanmış Waydroid / binder / çalışan Wayland ve yeterli bellekte denenebilir.'
            + '\nTelefon görüşmesi, modem, kamera, askıya alma, GPU ve pil ömrü bu katmanla doğrulanmış sayılmaz.'
            + '\nTek imaj her ARM cihazında çalışmaz. Kilitli Android / iPhone’a otomatik flaşlama veya kilit açma yapılmaz.')
