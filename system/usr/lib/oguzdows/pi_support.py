"""Pi algılama ve kaynak politikası; donanıma yazmaz, PC'de de içe aktarılabilir."""
from __future__ import annotations

import json
import platform

import resource_policy
from pathlib import Path


def text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").replace("\x00", "").strip()
    except OSError:
        return ""


def model(root: Path = Path("/")) -> str:
    return text(root / "sys/firmware/devicetree/base/model") or text(root / "proc/device-tree/model")


def is_pi(root: Path = Path("/")) -> bool:
    return (root / "etc/oguzdows/pi-image.json").is_file() or model(root).startswith("Raspberry Pi")


def armv6(machine: str | None = None, board: str | None = None) -> bool:
    machine = platform.machine() if machine is None else machine
    board = model() if board is None else board
    # 64-bit kernel üzerinde 32-bit kullanıcı alanı mümkün; kart adı da önemlidir.
    return machine.startswith("armv6") or (
        board.startswith(("Raspberry Pi Zero", "Raspberry Pi 1 ", "Raspberry Pi Model ", "Raspberry Pi Compute Module Rev"))
        and not board.startswith("Raspberry Pi Zero 2")
    )


def policy(memory_kib: int, board: str, requested: str = "auto") -> dict:
    return resource_policy.policy(memory_kib, legacy=armv6("", board), requested=requested)


def current_policy(root: Path = Path("/")) -> dict:
    return resource_policy.current_policy(root)


def peripheral_summary(root: Path = Path("/sys")) -> str:
    lines = []
    # Pi Wi-Fi SDIO'dur, VC4/V3D ise platform aygıtıdır; PCI araması yeterli değil.
    for bus in ("sdio", "platform"):
        for device in sorted((root / "bus" / bus / "devices").glob("*")):
            driver_link = device / "driver"
            driver = driver_link.resolve().name if driver_link.is_symlink() else "SÜRÜCÜ BAĞLI DEĞİL"
            identity = text(device / "modalias")
            if bus == "sdio" or any(key in (device.name + " " + driver + " " + identity).lower()
                                     for key in ("vc4", "v3d", "gpu", "hdmi", "bcm2835", "brcm", "rp1", "mmc")):
                lines.append(f"{bus} · {device.name} → {driver}")
    for interface in sorted((root / "class/net").glob("*")):
        if interface.name == "lo":
            continue
        link = interface / "device/driver"
        driver = link.resolve().name if link.is_symlink() else "SÜRÜCÜ BAĞLI DEĞİL / sanal aygıt"
        lines.append(f"Ağ · {interface.name} → {driver}")
    for card in sorted((root / "class/drm").glob("card[0-9]*")):
        if "-" in card.name:
            continue
        link = card / "device/driver"
        driver = link.resolve().name if link.is_symlink() else "SÜRÜCÜ BAĞLI DEĞİL"
        lines.append(f"DRM · {card.name} → {driver}")
    return "\n".join(lines) or "Platform / SDIO aygıtı bulunamadı."


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    settings = current_policy()
    print(settings["profile"] if args.profile else json.dumps(settings, ensure_ascii=False, indent=2))
