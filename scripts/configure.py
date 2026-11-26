#!/usr/bin/env python3
"""Depodaki dosyalardan incelenebilir bir live-build yapılandırması üretir.

Bu adım paket kurmaz, root gerektirmez ve ağa çıkmaz.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURES = {
    "amd64": {"suite": "trixie", "flavour": "amd64", "uefi": True},
    "i386": {"suite": "bookworm", "flavour": "686-pae", "uefi": False},
}
BOOT_ARGS = (
    "boot=live components quiet splash loglevel=3 "
    "hostname=oguzdows username=oguz user-fullname=OguzDows locales=tr_TR.UTF-8 "
    "keyboard-layouts=tr timezone=Europe/Istanbul"
)


def packages_for(arch: str) -> list[str]:
    suite = ARCHITECTURES[arch]["suite"]
    packages: list[str] = []
    for name in ("common", "pc", str(suite), arch):
        for line in (ROOT / "packages" / f"{name}.list").read_text().splitlines():
            package = line.partition("#")[0].strip()
            if package and package not in packages:
                packages.append(package)
    return packages


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def source_identity():
    revision = os.environ.get('GITHUB_SHA', 'unknown')
    dirty = None
    try:
        result = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=5, check=False)
        if result.returncode == 0:
            revision = result.stdout.strip()
            status = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=normal'],
                                    capture_output=True, text=True, timeout=5, check=False)
            dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        pass
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', revision):
        revision = 'unknown'
    return {'source_revision': revision, 'source_dirty': dirty}


def install_desktop_assets(overlay, suite):
    runpy.run_path(str(ROOT / 'scripts/install-desktop-assets.py'))['install'](overlay, suite)


def configure(arch: str, output: Path) -> None:
    info = ARCHITECTURES[arch]
    overlay = output / "includes.chroot"
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "system", overlay, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]", "rifki_pet.py", "rifki_scene.py", "rifki_motion.py", "rig", "envelopes.json", "intro-full.wav", "hello.wav", "help.wav", "disk.wav", "talk-blink.png"))
    install_desktop_assets(overlay, info['suite'])
    shutil.copytree(ROOT / "installer" / "modules", overlay / "etc/calamares/modules", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]"))
    # Bookworm Calamares 3.2 ile trixie 3.3 bazı anahtarları farklı okur.
    # Ortak masaüstü tercihlerini değil yalnızca sürüme özel kurucu biçimini değiştir.
    overrides = ROOT / "installer/overrides" / info["suite"]
    if overrides.is_dir():
        shutil.copytree(overrides, overlay / "etc/calamares/modules", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]"))
    shutil.copy2(ROOT / "installer/settings.conf", overlay / "etc/calamares/settings.conf")
    branding = overlay / "usr/share/calamares/branding/oguzdows"
    shutil.copytree(ROOT / "installer/branding", branding, dirs_exist_ok=True)
    plymouth = overlay / "usr/share/plymouth/themes/oguzdows"
    shutil.copytree(ROOT / "boot", plymouth, dirs_exist_ok=True)
    shutil.copytree(ROOT / "assets", overlay / "usr/share/oguzdows/assets", dirs_exist_ok=True)
    documentation = overlay / "usr/share/doc/oguzdows"
    documentation.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/MASAUSTU-VE-BAKIM.md", documentation / "masaustu-ve-bakim.md")
    shutil.copy2(ROOT / "docs/PI-ZERO-OTURUM.md", documentation / "PI-ZERO-OTURUM.md")
    shutil.copy2(ROOT / "docs/ELEMENTARY-HABER.md", documentation / "ELEMENTARY-HABER.md")
    shutil.copy2(ROOT / "docs/NATIVE-MATERYAL-HABER-MAGAZA.md", documentation / "NATIVE-MATERYAL-HABER-MAGAZA.md")
    shutil.copy2(ROOT / "docs/ATOLYE-VE-MAGAZA-YENILEME.md", documentation / "ATOLYE-VE-MAGAZA-YENILEME.md")
    shutil.copy2(ROOT / 'docs/MODLAR-VE-OTOMATIK-RENK.md', documentation / 'MODLAR-VE-OTOMATIK-RENK.md')
    shutil.copy2(ROOT / "docs/CIHAZLAR-VE-UYUMLULUK.md", documentation / "cihazlar-ve-uyumluluk.md")
    shutil.copy2(ROOT / "scripts/render-assets.py", overlay / "usr/lib/oguzdows/render-assets.py")
    if arch == 'amd64':
        # Trixie / 64 bit erken açılış: tüm sürücüler korunur; yalnızca geçici
        # initramfs GPU firmware kopyası kernel tarafından istenince açılır.
        # Pi / diğer ARM katmanları ve çalışan i386 yolu değiştirilmez.
        shutil.copytree(ROOT / 'pc/initramfs-tools', overlay / 'etc/initramfs-tools', dirs_exist_ok=True)
        (overlay / 'etc/initramfs-tools/hooks/oguzdows-firmware').chmod(0o755)
        shutil.copy2(ROOT / 'pc/initramfs-firmware.py', overlay / 'usr/lib/oguzdows/initramfs_firmware.py')
    shutil.copytree(ROOT / 'native', overlay / 'usr/share/oguzdows/native', dirs_exist_ok=True)
    (overlay / 'usr/share/oguzdows/scripts').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'scripts/build-native.sh', overlay / 'usr/share/oguzdows/scripts/build-native.sh')
    shutil.copy2(ROOT / 'scripts/build-news.sh', overlay / 'usr/share/oguzdows/scripts/build-news.sh')
    shutil.copy2(ROOT / 'scripts/build-desktop.sh', overlay / 'usr/share/oguzdows/scripts/build-desktop.sh')
    (overlay / 'usr/share/oguzdows/scripts/build-desktop.sh').chmod(0o755)
    shutil.copy2(ROOT / 'scripts/build-panel.sh', overlay / 'usr/share/oguzdows/scripts/build-panel.sh')
    (overlay / 'usr/share/oguzdows/scripts/build-panel.sh').chmod(0o755)
    (overlay / 'usr/share/oguzdows/scripts/build-news.sh').chmod(0o755)
    (overlay / 'usr/share/oguzdows/scripts/build-native.sh').chmod(0o755)

    # Paketlerin önerilen ayar paketlerinden marka/config taşınmasına izin verme.
    write(output / "package-lists/oguzdows.list.chroot", "\n".join(packages_for(arch)) + "\n")
    write(overlay / "usr/share/oguzdows/build-info.json", json.dumps({"arch": arch, **info, **source_identity()}, indent=2) + "\n")
    write(overlay / "etc/locale.gen", "tr_TR.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n")
    write(overlay / "etc/default/locale", 'LANG=tr_TR.UTF-8\nLANGUAGE="tr:en"\n')
    write(overlay / "etc/timezone", "Europe/Istanbul\n")
    write(overlay / "etc/hostname", "oguzdows\n")
    # squashfs yolu, hook tarafından gerçek canlı ortamda saptanır.
    write(overlay / "etc/calamares/modules/unpackfs.conf", """---
unpack:
  - source: /run/live/medium/live/filesystem.squashfs
    sourcefs: squashfs
    destination: ""
""")

    hooks = output / "hooks/live"
    shutil.copytree(ROOT / "hooks", hooks, dirs_exist_ok=True)
    for hook in hooks.iterdir():
        hook.chmod(0o755)
    for directory in ("usr/local/bin", "usr/local/sbin", "usr/lib/oguzdows"):
        for script in (overlay / directory).iterdir():
            if script.is_file() and script.suffix in ("", ".py", ".sh"):
                script.chmod(0o755)
    # xdg-user-dirs, var olmayan ön tanımlı yolları HOME'a çevirmesin.
    for directory in ("Masaüstü", "İndirilenler", "Şablonlar", "Ortak", "Belgeler", "Müzik", "Resimler", "Videolar"):
        (overlay / "etc/skel" / directory).mkdir(parents=True, exist_ok=True)
    desktop = overlay / "etc/skel/Masaüstü"
    for name in ("oguzdows-install.desktop", "oguzdows-welcome.desktop"):
        target = desktop / name
        shutil.copy2(overlay / "usr/share/applications" / name, target)
        target.chmod(0o755)

    # Binary hook, hazır çekirdek dosyalarını bulur; menülerde sabit sürüm numarası yoktur.
    binary_config = output / "oguzdows"
    binary_config.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "scripts/configure-boot.py", binary_config / "configure-boot.py")
    write(binary_config / "boot.json", json.dumps({"arch": arch, "boot_args": BOOT_ARGS, **info}) + "\n")
    splash = (ROOT / "assets/boot-background.svg").read_text()
    # live-build sürümleri arasındaki splash dosyası konumu farklarını da karşıla.
    for directory in ("bootloaders", "bootloaders/syslinux_common", "bootloaders/grub-pc"):
        write(output / directory / "splash.svg", splash)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=ARCHITECTURES, default="amd64")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--print-boot-args", action="store_true")
    args = parser.parse_args()
    if args.print_boot_args:
        print(BOOT_ARGS)
    elif args.output:
        configure(args.arch, args.output.resolve())
        print(f"OğuzDows {args.arch}: {args.output}")
    else:
        parser.error("--output veya --print-boot-args belirtin")


if __name__ == "__main__":
    main()
