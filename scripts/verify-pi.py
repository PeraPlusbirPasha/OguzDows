#!/usr/bin/env python3
"""Bağlanmış Pi kökünü ve boot dosyalarını denetler; bu bir kart açılış testi değildir."""
from __future__ import annotations

import argparse
import configparser
import re
import sys
from pathlib import Path


# Yalnızca bu betiğin yanındaki kaynak; --root altından kod içe aktarılmaz.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pi_contract import checked_path, elf_info, feature_presence, read_bytes, read_json


def read(root: Path, name: str) -> str:
    return read_bytes(root, name, allow_empty=True).decode('utf-8', errors='replace')


def validate_features(root: Path, arch: str) -> None:
    """Yalnızca veri / ELF başlığı oku; bağlı imajdan hiçbir kod çalıştırma."""
    contract = read_json(root, 'usr/share/oguzdows/pi-contract.json')
    report = read_json(root, 'usr/share/oguzdows/pi-build-report.json')
    info = read_json(root, 'etc/oguzdows/pi-image.json')
    if (not isinstance(contract, dict) or not isinstance(report, dict)
            or type(contract.get('schema')) is not int or contract['schema'] != 1
            or type(report.get('schema')) is not int or report['schema'] != 1):
        raise ValueError('Pi sözleşme / hedef rapor şeması geçersiz.')
    expected = contract['architectures'][arch]
    if not isinstance(report.get('gui'), dict) or not all(isinstance(report['gui'].get(key), str) for key in ('xfce_version', 'native_store_version', 'native_news_version')):
        raise ValueError('Pi hedef GUI sürüm raporu eksik / geçersiz.')
    if (contract['arch'] != arch or contract['pi_gen_commit'] != info['pi_gen_commit']
            or contract['source_revision'] != info['source_revision']
            or contract['suite'] != info['suite'] or report.get('python_modules') != contract['python_modules']
            or report.get('arch') != arch or report.get('errors') != []
            or report.get('minimum_cpu') != expected['cpu']
            or report.get('scope') != 'ARM-qemu-user-with-host-Xvfb'
            or report.get('source_revision') != contract['source_revision']
            or report.get('pi_gen_commit') != contract['pi_gen_commit']
            or report.get('suite') != contract['suite']
            or report.get('gui', {}).get('gtk_window') is not True
            or 'xfce4-session' not in report.get('gui', {}).get('xfce_version', '')
            or 'OğuzDows' not in report.get('gui', {}).get('native_store_version', '')
            or 'OğuzDows Haber · GTK ' not in report.get('gui', {}).get('native_news_version', '')):
        raise ValueError('Pi hedef ABI / gerçek GTK / kaynak raporu eksik veya başarısız.')
    session = report.get('full_session', {})
    if (not isinstance(session, dict) or session.get('uid') != 65534
            or session.get('scope') != 'non-root-Xfce-on-host-Xvfb'
            or str(session.get('x11_window_manager', '')).lower() != 'xfwm4'
            or session.get('errors') != [] or type(session.get('stable_samples')) is not int
            or session['stable_samples'] < 5
            or any(session.get(name) is not True for name in ('xfwm4', 'xfce4-panel', 'xfdesktop'))
            or any(session.get(name) is not False for name in ('lightdm_pam', 'physical_boot', 'performance_measurement'))):
        raise ValueError('Pi root olmayan TAM Xfce oturum raporu eksik / başarısız; --version yeterli değildir.')
    # Old published contracts remain readable. New ARM-refresh contracts
    # explicitly require actual target appearance operations, not file counts.
    if 'appearance_runtime_schema' in contract:
        appearance = session.get('appearance', {})
        if (type(contract['appearance_runtime_schema']) is not int or contract['appearance_runtime_schema'] != 1
                or not isinstance(appearance, dict) or type(appearance.get('schema')) is not int or appearance['schema'] != 1
                or appearance.get('scope') != 'target-user-QEMU-real-Xfce-appearance'
                or any(appearance.get(key) is not True for key in ('gtk3_dark_light_reloaded', 'wallpaper_pixels_changed', 'packaged_wallpapers'))
                or any(appearance.get(key) is not False for key in ('settings_backend_mocked', 'welcome_callbacks_tested',
                           'gtk4_portal_tested', 'physical_device', 'performance_measurement'))
                or not isinstance(appearance.get('gtk_themes'), dict) or set(appearance['gtk_themes']) != {'dark', 'light'}
                or any(not isinstance(value, str) or not re.fullmatch(r'OguzDows[A-Za-z0-9]*User-[0-9a-f]{16}', value)
                       for value in appearance['gtk_themes'].values())
                or appearance['gtk_themes']['dark'] == appearance['gtk_themes']['light']
                or not isinstance(appearance.get('wallpaper_ids'), list) or len(appearance['wallpaper_ids']) != 2
                or any(not isinstance(value, str) or not re.fullmatch('[a-z0-9-]{1,80}', value) for value in appearance['wallpaper_ids'])
                or len(set(appearance['wallpaper_ids'])) != 2
                or not isinstance(appearance.get('wallpaper_pixel_sha256'), list) or len(appearance['wallpaper_pixel_sha256']) != 2
                or any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in appearance['wallpaper_pixel_sha256'])
                or len(set(appearance['wallpaper_pixel_sha256'])) != 2):
            raise ValueError('Pi gerçek hedef tema / duvar kâğıdı görünüm işlemi kanıtı eksik veya başarısız.')
    # arm1 contracts did not promise Turkish gettext/typed-array coverage.
    # Require it explicitly for new builds without rewriting historical proof.
    if 'xfconf_locale_runtime_schema' in contract:
        appearance = session.get('appearance', {})
        locale = appearance.get('xfconf_locale') if isinstance(appearance, dict) else None
        if (type(contract['xfconf_locale_runtime_schema']) is not int or contract['xfconf_locale_runtime_schema'] != 1
                or not isinstance(locale, dict) or type(locale.get('schema')) is not int or locale['schema'] != 1
                or locale.get('environment') != {'LANG': 'tr_TR.UTF-8', 'LANGUAGE': 'tr:en', 'LC_ALL': 'tr_TR.UTF-8'}
                or locale.get('raw_turkish_header') != 'Değer, 2 ögeden oluşan dizidir:'
                or locale.get('runners') != ['profiles', 'desktop_runtime', 'wallpapers']
                or locale.get('typed_arrays') != ['int-array', 'double-array']
                or any(locale.get(key) is not True for key in ('single_item_array', 'utf8_value_roundtrip',
                           'array_read_write_readback', 'typed_backup', 'compare_rollback', 'persistence_failure_rollback',
                           'personal_panel_arrays_unchanged', 'persistence_failure_injected', 'unfixed_reader_error_reproduced'))
                or locale.get('settings_backend_mocked') is not False):
            raise ValueError('Pi Türkçe Xfconf dizi / yedek / geri alma kanıtı eksik veya başarısız.')
    if session.get('news') != {'native_process_alive': True, 'worker_exited': True, 'cached_fixture_preserved': True,
                              'network_tested': False, 'performance_measurement': False, 'window_pixels_verified': False}:
        raise ValueError('Pi C Haber / offline fixture / kısa ömürlü işçi testi eksik veya başarısız.')
    if arch == 'armhf' and session.get('browser') != {'program': 'netsurf-gtk', 'local_start_page_alive': True,
                                                   'network_tested': False, 'modern_sites_verified': False}:
        raise ValueError('Pi ARMv6 NetSurf yerel başlangıç testi eksik / başarısız.')
    if any(report.get(key) is not False for key in ('physical_boot', 'hardware_gpu', 'performance_measurement', 'real_package_transactions', 'real_audio_playback')):
        raise ValueError('Pi yapı raporu yapılmayan fiziksel / işlem testini başarı sayamaz.')
    if not isinstance(report.get('packages'), dict) or set(report['packages']) != set(contract['required_packages']):
        raise ValueError('Ortak paket özellikleri hedef raporundan eksilmiş.')
    if any(not isinstance(value, dict) or value.get('architecture') not in (arch, 'all')
           or not isinstance(value.get('version'), str) or not value['version'] for value in report['packages'].values()):
        raise ValueError('Ortak paket sürümü / yerel mimari raporu eksik.')
    if report.get('feature_presence') != feature_presence(root, contract):
        raise ValueError('Pi özellik / doğal kayıt / galeri raporu export ile eşleşmedi.')
    abi = {'/' + name: elf_info(checked_path(root, name), expected)
           for name in ('usr/bin/python3', 'usr/lib/oguzdows/oguzdows-store-native', 'usr/lib/oguzdows/oguzdows-news-native')}
    if report.get('abi') != abi:
        raise ValueError('Pi hedef ABI raporu export içindeki Python / mağazayla eşleşmedi.')
    release = dict(line.split('=', 1) for line in read(root, 'usr/lib/os-release').splitlines() if '=' in line and not line.startswith('#'))
    for key, value in (('ID', expected['os_id']), ('VERSION_ID', expected['base_version_id']), ('VERSION_CODENAME', contract['suite'])):
        if release.get(key, '').strip('"') != value:
            raise ValueError('Pi OS teknik taban kimliği ürün sürümüyle bozulmuş: ' + key)


def validate(root: Path, arch: str, pre_export: bool = False) -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    info = read_json(root, "etc/oguzdows/pi-image.json")
    lock = read_json(root, "usr/share/oguzdows/pi-gen.lock.json")
    require(info["arch"] == arch and info["platform"] == "raspberrypi", "Yanlış Pi mimarisi / platformu.")
    require(info["pi_gen_commit"] == lock[arch]["commit"], "pi-gen kaynak kimliği uyuşmuyor.")
    files = ["boot/firmware/config.txt", "boot/firmware/cmdline.txt", "boot/firmware/start.elf",
             "boot/firmware/start4.elf", "boot/firmware/fixup.dat", "boot/firmware/bootcode.bin",
             "boot/firmware/overlays/vc4-kms-v3d.dtbo", "usr/share/xsessions/oguzdows.desktop",
             "usr/share/backgrounds/oguzdows/wallpaper.png", "usr/share/oguzdows/wallpapers.json",
             "usr/share/themes/OguzDows/xfwm4/themerc", "usr/lib/oguzdows/pi-firstboot.py",
             "etc/systemd/system/lightdm.service.d/10-oguzdows-firstboot.conf",
             "etc/systemd/system/ssh.service.d/10-oguzdows-firstboot.conf",
             "usr/lib/raspberrypi-sys-mods/firstboot", "etc/init.d/resize2fs_once",
             "usr/share/oguzdows/pi-contract.json", "usr/share/oguzdows/pi-build-report.json"]
    for filename in lock[arch]["kernels"] + lock[arch]["dtbs"] + ([] if pre_export else lock[arch]["initramfs"]):
        files.append("boot/firmware/" + filename)
    for filename in files:
        try:
            checked_path(root, filename)
        except (OSError, ValueError) as error:
            raise ValueError("Eksik / boş / hedef dışı Pi dosyası: " + filename) from error
    config = read(root, "boot/firmware/config.txt")
    settings = {line.partition('#')[0].strip() for line in config.splitlines()}
    require({'dtoverlay=vc4-kms-v3d', 'auto_initramfs=1', 'camera_auto_detect=1', 'display_auto_detect=1',
             'dtparam=audio=on', 'disable_fw_kms_setup=1', 'arm_boost=1'}.issubset(settings),
            "Resmî KMS / initramfs / kamera / ekran / ses varsayılanı eksik.")
    require(("arm_64bit=1" in settings) == (arch == "arm64"), "Yanlış firmware bit modu.")
    require(not re.search(r'(?m)^\s*kernel\s*=', config), "Bütün Pi modellerine tek kernel zorlanmış.")
    require(not re.search(r"(?m)^\s*(over_voltage\w*|force_turbo|arm_freq)\s*=", config), "Zorunlu overclock bulundu.")
    cmdline = read(root, "boot/firmware/cmdline.txt")
    args = cmdline.split()
    require(len(cmdline.strip().splitlines()) == 1, "cmdline.txt tek satır olmalı.")
    require(any(re.fullmatch(r"root=PARTUUID=[0-9a-fA-F]{8}-02", arg) for arg in args), "Kök PARTUUID çözülmedi.")
    require("ROOTDEV" not in cmdline and "BOOTDEV" not in read(root, "etc/fstab"), "Bölüm yer tutucusu kaldı.")
    require("boot=live" not in args and not any("username=oguz" == arg for arg in args), "Canlı PC hesabı taşındı.")
    require('init=/usr/lib/raspberrypi-sys-mods/firstboot' in args, "Resmî ilk açılış / bölüm büyütme zinciri kaybolmuş.")
    require("OğuzDows" in read(root, "usr/lib/os-release"), "Ürün kimliği eksik.")
    for filename in ("etc/systemd/system/oguzdows-live-setup.service", "usr/local/sbin/oguzdows-installer",
                     "etc/calamares", "var/lib/oguzdows/firstboot.done", "var/lib/oguzdows/firstboot.pending.json"):
        require(not (root / filename).exists(), "Dağıtıma taşınmaması gereken dosya: " + filename)
    require(not any(1000 <= int(line.split(":")[2]) < 60000 for line in read(root, "etc/passwd").splitlines()),
            "İmajda önceden oluşturulmuş normal kullanıcı var.")
    shadow = {line.split(":")[0]: line.split(":")[1] for line in read(root, "etc/shadow").splitlines()}
    require(shadow.get("root", "").startswith(("!", "*")), "Root hesabı kilitli değil.")
    for filename in [root / "etc/sudoers", *(root / "etc/sudoers.d").glob("*")]:
        if filename.is_file():
            require(not any("NOPASSWD" in line.partition("#")[0] for line in read(root, filename.relative_to(root).as_posix()).splitlines()),
                    "Kalıcı imajda parolasız sudo kuralı var: " + filename.name)
    for filename in (root / "etc/lightdm").rglob("*.conf"):
        require(not any(re.match(r"\s*autologin-user\s*=\s*\S", line.partition("#")[0])
                        for line in read(root, filename.relative_to(root).as_posix()).splitlines()), "Kalıcı imajda otomatik giriş açık.")
    for service in ("oguzdows-pi-firstboot", "oguzdows-pi-tune", "zramswap"):
        require((root / f"etc/systemd/system/multi-user.target.wants/{service}.service").is_symlink(),
                "Servis etkinleştirilmemiş: " + service)
    require((root / "etc/systemd/system/display-manager.service").is_symlink()
            and (root / "etc/systemd/system/display-manager.service").readlink().name == "lightdm.service", "LightDM varsayılan değil.")
    require(not (root / "etc/systemd/system/multi-user.target.wants/ssh.service").is_symlink(), "SSH varsayılan olarak açık.")
    require((root / "etc/systemd/system/dphys-swapfile.service").is_symlink()
            and (root / "etc/systemd/system/dphys-swapfile.service").readlink() == Path("/dev/null"), "SD swap devre dışı değil.")
    require(not list((root / "etc/ssh").glob("ssh_host_*_key*")), "Kopyalanmış SSH sunucu anahtarı var.")
    require(not (root / 'etc/systemd/system/network-online.target.wants/NetworkManager-wait-online.service').is_symlink(),
            'NetworkManager enable sonrasında ağ bekleyici geri açılmış.')
    if not pre_export:
        require(not read(root, "etc/machine-id").strip(), "Makine kimliği sıfırlanmamış.")
    # Ana lightdm.conf drop-in'den sonra okunur. Yanlış LXDE / greeter
    # seçimini yalnızca paket varlığı kapısından geçirip dağıtma.
    display = configparser.ConfigParser(interpolation=None)
    display.read_string(read(root, 'etc/lightdm/lightdm.conf'))
    require(display.get('Seat:*', 'user-session', fallback='') == 'oguzdows'
            and display.get('Seat:*', 'greeter-session', fallback='') == 'lightdm-gtk-greeter',
            'LightDM ana dosyası ürün oturumunu / greeter seçimini ezebilir.')
    require('session_start.py' in read(root, 'usr/share/xsessions/oguzdows.desktop'), 'Ürün oturum giriş işçisi kullanılmıyor.')
    validate_features(root, arch)
    print(f"OğuzDows Pi {arch}: dosya / boot / hesap güvenliği / özellik varlığı doğrulandı ({'export öncesi' if pre_export else 'son imaj'}).")
    print("Bu sonuç fiziksel Pi açılışı, çevre birimi veya performans doğrulaması değildir.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--arch", choices=("armhf", "arm64"), required=True)
    parser.add_argument("--pre-export", action="store_true")
    args = parser.parse_args()
    validate(args.root.resolve(), args.arch, args.pre_export)


if __name__ == "__main__":
    main()
