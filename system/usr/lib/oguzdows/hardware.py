"""GUI ve yetkili sürücü yardımcısının paylaştığı salt-okunur donanım mantığı."""
from __future__ import annotations

import datetime
import os
import platform
import subprocess
from pathlib import Path

from pi_support import current_policy, is_pi, model as pi_model, peripheral_summary
from resource_policy import policy as resource_budget

# Broadcom STA'nın desteklediği PCI kimlikleri. Diğer Broadcom aygıtları için
# b43 / brcmsmac / brcmfmac yerleşik sürücüleri korunur.
BROADCOM_STA_IDS = frozenset({
    "4311", "4312", "4313", "4315", "4329", "432a", "432b", "432c", "4727",
    "432d", "4353", "4357", "4358", "4359", "4365", "43a0", "43b1",
})


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def is_live(cmdline: str | None = None) -> bool:
    return "boot=live" in (read_text(Path("/proc/cmdline")) if cmdline is None else cmdline).split()


def memory_kib(meminfo: str | None = None) -> int:
    text = read_text(Path("/proc/meminfo")) if meminfo is None else meminfo
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            try:
                return max(0, int(line.split()[1]))
            except (ValueError, IndexError):
                return 0
    return 0


def light_profile(cmdline: str, memory: int) -> bool:
    args = cmdline.split()
    requested = next((arg.partition("=")[2] for arg in args if arg.startswith("oguzdows.profile=")), "auto")
    if requested not in ("auto", "mini", "light", "full"):
        requested = "auto"
    return not resource_budget(memory, requested=requested, nomodeset="nomodeset" in args)["compositing"]


INTEL_LEGACY_IDS = frozenset({"1043", "4220", "4221", "4223", "4224"})


def matching_pci(vendor_id: str, ids: frozenset[str], sysfs: Path = Path("/sys/bus/pci/devices")) -> list[Path]:
    devices = []
    for path in sorted(sysfs.glob("*")):
        vendor = read_text(path / "vendor").strip().lower()
        device = read_text(path / "device").strip().lower().removeprefix("0x")
        device_class = read_text(path / "class").strip().lower()
        if vendor == "0x" + vendor_id and device in ids and device_class.startswith("0x02"):
            devices.append(path)
    return devices


def supported_broadcom(sysfs: Path = Path("/sys/bus/pci/devices")) -> list[str]:
    return ["14e4:" + read_text(path / "device").strip().lower().removeprefix("0x")
            for path in matching_pci("14e4", BROADCOM_STA_IDS, sysfs)]


def supported_intel_legacy(sysfs: Path = Path("/sys/bus/pci/devices")) -> list[str]:
    return ["8086:" + read_text(path / "device").strip().lower().removeprefix("0x")
            for path in matching_pci("8086", INTEL_LEGACY_IDS, sysfs)]


def driver_summary(sysfs: Path = Path("/sys/bus/pci/devices")) -> str:
    lines = []
    for path in sorted(sysfs.glob("*")):
        kind = read_text(path / "class").strip().lower()
        if not kind.startswith(("0x02", "0x03")):
            continue
        identity = ":".join(read_text(path / key).strip().lower().removeprefix("0x") for key in ("vendor", "device"))
        driver = (path / "driver").resolve().name if (path / "driver").is_symlink() else "SÜRÜCÜ BAĞLI DEĞİL"
        category = "Ağ" if kind.startswith("0x02") else "Görüntü"
        lines.append(f"{category} · {identity} · {path.name} → {driver}")
    return "\n".join(lines) or "PCI ağ/görüntü aygıtı bulunamadı (USB aygıtlarını da kontrol et)."


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=12,
                                env={**os.environ, "LC_ALL": "C", "LANG": "C"}, check=False)
    except FileNotFoundError:
        return "Bu tanılama aracı kurulu değil."
    except subprocess.TimeoutExpired:
        return "Donanım sorgusu zaman aşımına uğradı."
    except OSError:
        return "Donanım bilgisi okunamadı."
    return (result.stdout.strip() or "Aygıt bilgisi alınamadı.")[:60000]


def report() -> str:
    memory = memory_kib()
    cmdline = read_text(Path("/proc/cmdline"))
    sections = [
        "OğuzDows · Donanım ve Sürücüler",
        datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        f"Mimari: {platform.machine()}   Çekirdek: {platform.release()}",
        f"Bellek: {memory // 1024} MiB",
        "Oturum: " + ("Canlı OğuzDows" if is_live(cmdline) else "Kurulu OğuzDows"),
        "Profil: " + ("Hafif / efektler kapalı" if light_profile(cmdline, memory) else "Standart"),
        "\nAğ / görüntü sürücüsü durumu\n" + driver_summary(),
        "\nPCI aygıtları ve kullanılan çekirdek sürücüleri\n" + command_output(["/usr/bin/lspci", "-nnk"]),
        "\nUSB aygıtları\n" + command_output(["/usr/bin/lsusb"]),
        "\nKablosuz anahtarları\n" + command_output(["/usr/sbin/rfkill", "list"]),
        "\nISO / sistemde kurulu firmware paketleri\n" + command_output(["/usr/bin/dpkg-query", "-W", "-f=${binary:Package} ${Version}\\n", "firmware-*", "atmel-firmware"]),
        "\nAğ aygıtları\n" + command_output(["/usr/bin/nmcli", "-f", "DEVICE,TYPE,STATE", "device"]),
        "\nNot: Bu rapor yerel olarak üretilir; hiçbir yere gönderilmez.",
    ]
    if is_pi():
        settings = current_policy()
        sections[5] = "Profil: " + settings["profile"] + f" · LZ4 zram {settings['zram_mb']} MiB"
        sections[6:6] = ["\nRaspberry Pi kartı\n" + (pi_model() or "Model okunamadı"),
                         "\nPlatform / SDIO / DRM / ağ sürücüleri\n" + peripheral_summary(),
                         "\nPi sıcaklık, besleme ve throttling bayrakları\n" + command_output(["/usr/bin/vcgencmd", "measure_temp"])
                         + "\n" + command_output(["/usr/bin/vcgencmd", "get_throttled"])]
    return "\n".join(sections) + "\n"
