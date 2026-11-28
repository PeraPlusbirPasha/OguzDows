#!/usr/bin/env python3
"""Hazır ISO ağacına OğuzDows BIOS/UEFI menülerini yazar."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    bios_title: str
    arguments: str
    help: str


def entries(boot_args: str) -> list[Entry]:
    args = boot_args.split()
    no_splash = [arg for arg in args if arg != "splash"]
    verbose = [arg for arg in args if arg not in ("quiet", "splash") and not arg.startswith("loglevel=")]
    return [
        Entry("oguzdows", "OğuzDows'u başlat", "OguzDows'u baslat", boot_args, "Dene, kesfet veya OguzDows'u bilgisayarina kur."),
        Entry("oguzdows-safe", "OğuzDows · Güvenli görüntü", "OguzDows - guvenli goruntu", " ".join(no_splash + ["nomodeset", "plymouth.enable=0", "oguzdows.profile=light"]), "Siyah ekran veren eski ekran kartlari icin. 3B efektler kapali."),
        Entry("oguzdows-light", "OğuzDows · Düşük bellek", "OguzDows - dusuk bellek", " ".join(no_splash + ["plymouth.enable=0", "oguzdows.profile=light"]), "Masaustu efektleri kapali. Sistem RAM'e kopyalanmaz."),
        Entry("oguzdows-verbose", "OğuzDows · Açılış günlüğü", "OguzDows - acilis gunlugu", " ".join(verbose + ["loglevel=6", "systemd.show_status=true", "plymouth.enable=0"]), "Sorun tespiti icin ayrintili acilis iletileri."),
    ]


def kernel_pair(binary: Path) -> tuple[str, str]:
    live = binary / "live"
    if (live / "vmlinuz").is_file() and (live / "initrd.img").is_file():
        return "/live/vmlinuz", "/live/initrd.img"
    pairs = []
    for kernel in sorted(live.glob("vmlinuz-*")):
        initrd = live / kernel.name.replace("vmlinuz-", "initrd.img-", 1)
        if kernel.is_file() and initrd.is_file():
            pairs.append((f"/live/{kernel.name}", f"/live/{initrd.name}"))
    if len(pairs) != 1:
        raise RuntimeError("ISO ağacında tek, eşleşen bir OğuzDows çekirdeği/initrd çifti bulunamadı.")
    return pairs[0]


def bios_menu(items: list[Entry], kernel: str, initrd: str) -> str:
    menu = """UI vesamenu.c32
DEFAULT oguzdows
PROMPT 0
TIMEOUT 80
MENU TITLE OGUZDOWS / AY YILDIZ
MENU BACKGROUND splash.png
MENU WIDTH 70
MENU HSHIFT 5
MENU VSHIFT 14
MENU ROWS 6
MENU HELPMSGROW 22
MENU TIMEOUTROW 25
MENU TABMSGROW 26
MENU CMDLINEROW 26
MENU TABMSG ENTER: baslat   |   TAB: secenekleri duzenle
MENU AUTOBOOT OguzDows # saniye icinde baslatilacak.
MENU COLOR border * #00000000 #00000000 none
MENU COLOR title * #ff70d1ca #00000000 none
MENU COLOR unsel * #ffe8e9ef #00000000 none
MENU COLOR sel * #ffffffff #ff8d293d none
MENU COLOR hotkey * #ff70d1ca #00000000 none
MENU COLOR hotsel * #ffffffff #ff8d293d none
MENU COLOR help * #ffacb8cb #00000000 none
MENU COLOR tabmsg * #ffacb8cb #00000000 none
MENU COLOR timeout_msg * #ffacb8cb #00000000 none
MENU COLOR timeout * #ff70d1ca #00000000 none
"""
    for item in items:
        menu += f"""
LABEL {item.key}
  MENU LABEL {item.bios_title}
  LINUX {kernel}
  INITRD {initrd}
  APPEND {item.arguments}
  TEXT HELP
  {item.help}
  ENDTEXT
"""
    # Klasik BIOS yazı tipi UTF-8 desteklemez; metinler bilinçli olarak ASCII'dir.
    menu.encode("ascii")
    return menu


def grub_menu(items: list[Entry], kernel: str, initrd: str) -> str:
    menu = f"""# OğuzDows · Akıncı
set default=0
set timeout=8
if [ -z "$iso_path" ]; then
    search --no-floppy --set=root --file {kernel}
else
    set oguzdows_iso="findiso=$iso_path"
fi
insmod all_video
insmod gfxterm
insmod png
loadfont /boot/grub/unicode.pf2
set gfxmode=800x600,auto
terminal_output gfxterm
set theme=/boot/grub/oguzdows-theme.txt
export theme
set menu_color_normal=light-gray/black
set menu_color_highlight=white/red
"""
    for item in items:
        menu += f"""
menuentry \"{item.title}\" --id {item.key} {{
    linux {kernel} {item.arguments} $oguzdows_iso
    initrd {initrd}
}}
"""
    return menu


GRUB_THEME = """desktop-image: "splash.png"
title-text: ""
terminal-font: "Unifont Regular 16"
+ boot_menu {
  left = 10%
  top = 44%
  width = 80%
  height = 32%
  item_font = "Unifont Regular 16"
  item_color = "#d9dce5"
  selected_item_color = "#70d1ca"
  item_height = 32
  item_padding = 4
  item_spacing = 4
  icon_width = 0
  icon_height = 0
}
+ label {
  left = 8%
  top = 83%
  width = 84%
  height = 24
  text = "ENTER: başlat   ·   E: seçenekleri düzenle"
  color = "#acb8cb"
  align = "center"
}
+ progress_bar {
  id = "__timeout__"
  left = 20%
  top = 89%
  width = 60%
  height = 18
  text = "OğuzDows %d saniye içinde başlatılacak"
  text_color = "#ffffff"
  fg_color = "#8d293d"
  bg_color = "#252936"
  border_color = "#252936"
}
"""


def configure(binary: Path, root: Path, config: dict) -> None:
    kernel, initrd = kernel_pair(binary)
    items = entries(config["boot_args"])
    bios = binary / "isolinux"
    if not (bios / "vesamenu.c32").is_file():
        raise RuntimeError("SYSLINUX menü modülü bulunamadı; varsayılan menüyle ISO üretilmeyecek.")
    # Ulaşılmayan varsayılan menüleri de ISO'da bırakma.
    for directory in (bios, binary / "boot/grub"):
        if directory.exists():
            for pattern in ("*.cfg", "*.svg"):
                for old in directory.glob(pattern):
                    old.unlink()
            shutil.rmtree(directory / "live-theme", ignore_errors=True)
    (bios / "isolinux.cfg").write_text(bios_menu(items, kernel, initrd), encoding="ascii")
    (bios / "syslinux.cfg").write_text("INCLUDE isolinux.cfg\n", encoding="ascii")
    brand = root / "usr/share/oguzdows/brand"
    shutil.copy2(brand / "boot-bios.png", bios / "splash.png")
    if config["uefi"]:
        grub = binary / "boot/grub"
        grub.mkdir(parents=True, exist_ok=True)
        (grub / "grub.cfg").write_text(grub_menu(items, kernel, initrd), encoding="utf-8")
        (grub / "loopback.cfg").write_text("source /boot/grub/grub.cfg\n", encoding="ascii")
        (grub / "oguzdows-theme.txt").write_text(GRUB_THEME, encoding="utf-8")
        shutil.copy2(brand / "boot-efi.png", grub / "splash.png")
        shutil.copy2(root / "usr/share/grub/unicode.pf2", grub / "unicode.pf2")
    disk = binary / ".disk"
    disk.mkdir(exist_ok=True)
    (disk / "info").write_text(f"OğuzDows · Akıncı · {config['arch']}\n", encoding="utf-8")
    defines = binary / "README.diskdefines"
    if defines.exists():
        defines.write_text(f"#define DISKNAME OğuzDows\n#define ARCH {config['arch']}\n", encoding="utf-8")
    readme = binary / "README.html"
    if readme.exists():
        readme.write_text('<!doctype html><meta charset="utf-8"><title>OğuzDows</title><h1>OğuzDows · Akıncı</h1><p>Başlangıç için masaüstündeki OğuzDows Rehberi’ni açın.</p>\n', encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    configure(args.binary.resolve(), args.root.resolve(), json.loads(args.config.read_text()))


if __name__ == "__main__":
    main()
