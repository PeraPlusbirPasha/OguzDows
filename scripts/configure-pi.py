#!/usr/bin/env python3
"""Raspberry Pi imaj aşamasını çevrimdışı ve root gerektirmeden hazırla."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "raspberrypi/pi-gen.lock.json").read_text())
SPEC = importlib.util.spec_from_file_location('pi_shared_source_identity', ROOT / 'scripts/configure.py')
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)
# Canlı USB hesabı, Calamares ve PCI ek sürücü kurucusu kalıcı Pi'ye taşınmaz.
PC_ONLY = (
    "etc/default/grub", "etc/default/grub.d",
    # lsb_release -cs, Pi araçlarına ürün kod adı değil gerçek tabanı söylemeli.
    "etc/lsb-release",
    "etc/systemd/system/oguzdows-live-setup.service",
    "usr/lib/oguzdows/live-setup.sh", "usr/lib/oguzdows/finish-install.sh",
    "usr/lib/oguzdows/prepare-install.py", "usr/lib/oguzdows/cache-drivers.py",
    "usr/lib/oguzdows/target_system.py", "usr/lib/oguzdows/install_launcher.py", "usr/lib/oguzdows/run-installer.py", "usr/lib/oguzdows/install-target-driver.py",
    "usr/lib/oguzdows/driver_transfer.py",
    "usr/local/bin/oguzdows-install", "usr/local/sbin/oguzdows-installer",
    "usr/local/sbin/oguzdows-driver-helper", "usr/share/applications/oguzdows-install.desktop",
    "usr/share/polkit-1/actions/org.oguzdows.install.policy",
    "usr/share/polkit-1/actions/org.oguzdows.drivers.policy",
    # PC güncelleyici / Pardus / gelişmiş GNOME merkezi taşınmaz. Yerel C
    # mağazası yalnızca app: demetlerini Pi imzalı tabanında ayrıca doğrular.
    "usr/lib/oguzdows/updater.py",
    "usr/lib/oguzdows/store.py", "usr/lib/oguzdows/store_lifecycle.py", "usr/lib/oguzdows/memory_probe.py",
    "usr/local/bin/oguzdows-update",
    "usr/local/bin/oguzdows-memory-report",
    "usr/share/applications/oguzdows-update.desktop",
    "usr/local/share/applications/org.gnome.Software.desktop",
    "etc/apt/sources.list.d/oguzdows-pardus.sources", "etc/apt/preferences.d/oguzdows-pardus",
    "usr/share/keyrings/oguzdows-pardus.asc",
    "usr/share/glib-2.0/schemas/90_oguzdows-store.gschema.override",
    "etc/xdg/autostart/org.gnome.Software.desktop",
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def packages_for(arch='armhf') -> list[str]:
    packages = []
    for name in ("common", "raspberrypi"):
        for line in (ROOT / "packages" / (name + ".list")).read_text().splitlines():
            package = line.partition("#")[0].strip()
            # ARMv6 uyumlu ortak armhf imajında zorunlu ağır web motoru yok.
            # NetSurf aynı web özelliğini temel / JavaScript'siz kapsamda sağlar.
            if arch == 'armhf' and package in ('firefox-esr', 'firefox-esr-l10n-tr'):
                continue
            if package and package not in packages:
                packages.append(package)
    if arch == 'arm64':
        packages.extend(['flatpak', 'gir1.2-flatpak-1.0', 'xdg-desktop-portal', 'xdg-desktop-portal-gtk'])
    return packages


def configure(arch: str, output: Path) -> None:
    if arch not in ("armhf", "arm64"):
        raise ValueError("Pi mimarisi armhf veya arm64 olmalı.")
    # Stale veya başka mimari dosyaları sessizce karıştırma.
    output.mkdir(parents=True, exist_ok=False)
    stage = output / "stage-oguzdows"
    shutil.copytree(ROOT / "raspberrypi/stage", stage)
    overlay = stage / "00-desktop/files/overlay"
    shutil.copytree(ROOT / "system", overlay,
                    ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]", "rifki_pet.py", "rifki_scene.py", "rifki_motion.py", "rig", "envelopes.json", "intro-full.wav", "hello.wav", "help.wav", "disk.wav", "talk-blink.png"))
    for name in PC_ONLY:
        path = overlay / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    SHARED.install_desktop_assets(overlay, LOCK['suite'])
    shutil.copytree(ROOT / "raspberrypi/system", overlay, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.py[cod]"))
    shutil.copytree(ROOT / "boot", overlay / "usr/share/plymouth/themes/oguzdows")
    shutil.copytree(ROOT / "assets", overlay / "usr/share/oguzdows/assets")
    documentation = overlay / "usr/share/doc/oguzdows"
    documentation.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/MASAUSTU-VE-BAKIM.md", documentation / "masaustu-ve-bakim.md")
    shutil.copy2(ROOT / "docs/PI-ZERO-OTURUM.md", documentation / "PI-ZERO-OTURUM.md")
    shutil.copy2(ROOT / "docs/ELEMENTARY-HABER.md", documentation / "ELEMENTARY-HABER.md")
    shutil.copy2(ROOT / "docs/NATIVE-MATERYAL-HABER-MAGAZA.md", documentation / "NATIVE-MATERYAL-HABER-MAGAZA.md")
    shutil.copy2(ROOT / "docs/CIHAZLAR-VE-UYUMLULUK.md", documentation / "cihazlar-ve-uyumluluk.md")
    shutil.copy2(ROOT / "scripts/render-assets.py", overlay / "usr/lib/oguzdows/render-assets.py")
    shutil.copytree(ROOT / 'native', overlay / 'usr/share/oguzdows/native')
    (overlay / 'usr/share/oguzdows/scripts').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'scripts/build-native.sh', overlay / 'usr/share/oguzdows/scripts/build-native.sh')
    shutil.copy2(ROOT / 'scripts/build-news.sh', overlay / 'usr/share/oguzdows/scripts/build-news.sh')
    shutil.copy2(ROOT / 'scripts/build-desktop.sh', overlay / 'usr/share/oguzdows/scripts/build-desktop.sh')
    (overlay / 'usr/share/oguzdows/scripts/build-desktop.sh').chmod(0o755)
    (overlay / 'usr/share/oguzdows/scripts/build-news.sh').chmod(0o755)
    (overlay / 'usr/share/oguzdows/scripts/build-native.sh').chmod(0o755)
    shutil.copy2(ROOT / "scripts/verify-pi.py", overlay / "usr/lib/oguzdows/verify-pi.py")
    shutil.copy2(ROOT / "scripts/pi_contract.py", overlay / "usr/lib/oguzdows/pi_contract.py")
    write(overlay / "etc/locale.gen", "tr_TR.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\n")
    write(overlay / "etc/default/locale", 'LANG=tr_TR.UTF-8\nLANGUAGE="tr:en"\n')
    write(overlay / "etc/timezone", "Europe/Istanbul\n")
    info = {"platform": "raspberrypi", "arch": arch, "suite": LOCK["suite"],
            "pi_gen_commit": LOCK[arch]["commit"], "status": "physical-boot-unverified",
            **SHARED.source_identity()}
    for name in ("etc/oguzdows/pi-image.json", "usr/share/oguzdows/build-info.json"):
        write(overlay / name, json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    write(overlay / "usr/share/oguzdows/pi-gen.lock.json", json.dumps(LOCK, indent=2) + "\n")
    # Her sürümde tüm ortak paketler / ürün varlıkları için hedef mimari kapısı.
    contract = json.loads((ROOT / 'raspberrypi/feature-contract.json').read_text())
    if arch == 'armhf':
        contract['features']['web-office-media']['packages'] = [
            package for package in contract['features']['web-office-media']['packages']
            if package not in ('firefox-esr', 'firefox-esr-l10n-tr')]
    contract.update(arch=arch, suite=LOCK['suite'], required_packages=packages_for(arch),
                    source_revision=info['source_revision'], pi_gen_commit=info['pi_gen_commit'])
    contract['asset_hashes'] = {
        'usr/share/backgrounds/oguzdows/' + entry['file']: entry['packaged_sha256']
        for entry in json.loads((ROOT / 'artwork/landscapes.json').read_text())}
    contract['asset_hashes'].update({
        'usr/share/oguzdows/rifki/' + entry['file']: entry['sha256']
        for entry in json.loads((ROOT / 'artwork/rifki-narration.json').read_text())['clips']})
    write(overlay / 'usr/share/oguzdows/pi-contract.json', json.dumps(contract, ensure_ascii=False, indent=2) + '\n')
    shutil.copy2(ROOT / 'scripts/pi-runtime-smoke.py', stage / '00-desktop/files/pi-runtime-smoke.py')
    shutil.copy2(ROOT / 'scripts/pi_contract.py', stage / '00-desktop/files/pi_contract.py')
    shutil.copy2(ROOT / 'scripts/pi_session_smoke.py', stage / '00-desktop/files/pi_session_smoke.py')
    # Sadece güvenli tarayıcı varsayılanları; sandbox/çoklu süreç izolasyonu kapatılmaz.
    policy_path = overlay / "usr/lib/firefox-esr/distribution/policies.json"
    policies = json.loads(policy_path.read_text())
    policies["policies"].setdefault("Preferences", {}).update({
        "browser.cache.disk.enable": {"Value": False, "Status": "default"},
        "browser.sessionstore.interval": {"Value": 60000, "Status": "default"},
    })
    # Pi paketi distribution'ı /etc altına bağlı bir symlink olarak getirebilir.
    # Host cp -a ile bu bağlantının üstüne dizin kopyalama / hostta takip yok.
    # Politika hedef chroot içinde, mevcut anahtarlar korunarak birleştirilir.
    write(overlay / 'usr/share/oguzdows/firefox-policies.json', json.dumps(policies, ensure_ascii=False, indent=2) + '\n')
    policy_path.unlink()
    policy_path.parent.rmdir()
    policy_path.parent.parent.rmdir()  # Beklenmeyen ek Firefox dosyasını sessizce silme.
    for name in ("Masaüstü", "İndirilenler", "Şablonlar", "Ortak", "Belgeler", "Müzik", "Resimler", "Videolar"):
        (overlay / "etc/skel" / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(overlay / "usr/share/applications/oguzdows-welcome.desktop",
                 overlay / "etc/skel/Masaüstü/oguzdows-welcome.desktop")
    for directory in ("usr/local/bin", "usr/lib/oguzdows"):
        for path in (overlay / directory).iterdir():
            if path.is_file() and path.suffix in ("", ".py", ".sh"):
                path.chmod(0o755)
    (overlay / "etc/skel/Masaüstü/oguzdows-welcome.desktop").chmod(0o755)
    write(stage / "00-desktop/00-packages-nr", "\n".join(packages_for(arch)) + "\n")
    write(stage / "EXPORT_IMAGE", 'IMG_SUFFIX=""\n')
    # FIRST_USER_PASS bilerek yok. Resmî rename aşaması ayrı SKIP ile devre dışı;
    # kilitli derleme hesabı silinir, Türkçe yerel kurulum servisi gerçek hesabı açar.
    write(output / "config", f'''IMG_NAME=OguzDows-rpi-{arch}
IMG_FILENAME=OguzDows-rpi-{arch}
ARCHIVE_FILENAME=OguzDows-rpi-{arch}
RELEASE=bookworm
TARGET_HOSTNAME=oguzdows
FIRST_USER_NAME=oguz-build
FIRST_USER_PASS=""
DISABLE_FIRST_BOOT_USER_RENAME=0
ENABLE_SSH=0
USE_QEMU=0
LOCALE_DEFAULT=tr_TR.UTF-8
KEYBOARD_KEYMAP=tr
KEYBOARD_LAYOUT=Turkish
TIMEZONE_DEFAULT=Europe/Istanbul
WPA_COUNTRY=TR
DEPLOY_COMPRESSION=xz
COMPRESSION_LEVEL=6
PI_GEN_RELEASE="OğuzDows Raspberry Pi"
PI_GEN_REPO={LOCK['repository']}
GIT_HASH={LOCK[arch]['commit']}
STAGE_LIST="${{BASE_DIR}}/stage0 ${{BASE_DIR}}/stage1 ${{BASE_DIR}}/stage2 ${{BASE_DIR}}/stage-oguzdows"
''')
    shutil.copy2(ROOT / "raspberrypi/pi-gen.lock.json", output / "pi-gen.lock.json")
    shutil.copy2(ROOT / "raspberrypi/export-check.sh", output / "export-check.sh")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("armhf", "arm64"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    configure(args.arch, args.output.resolve())
    print(f"OğuzDows Pi {args.arch} yapılandırması: {args.output}")


if __name__ == "__main__":
    main()
