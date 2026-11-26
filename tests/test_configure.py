import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from support import ROOT, load

config = load("oguzdows_config", "scripts/configure.py")


class ConfigurationTests(unittest.TestCase):
    def test_both_architectures_stage_without_root_or_network(self):
        for arch, suite in (("amd64", "trixie"), ("i386", "bookworm")):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "config"
                config.configure(arch, output)
                overlay = output / "includes.chroot"
                self.assertEqual(json.loads((output / "oguzdows/boot.json").read_text())["suite"], suite)
                packages = (output / "package-lists/oguzdows.list.chroot").read_text().splitlines()
                self.assertEqual(len(packages), len(set(packages)))
                self.assertIn("xserver-xorg-video-all", packages)
                self.assertIn("firmware-brcm80211", packages)
                self.assertIn("amd64-microcode", packages)
                self.assertIn("xfce4-power-manager-plugins", packages)
                self.assertIn("plymouth-label", packages)
                for package in ("atmel-firmware", "firmware-zd1211", "firmware-bnx2", "firmware-bnx2x", "dkms", "build-essential", "python3-yaml"):
                    self.assertIn(package, packages)
                # --no-install-recommends ile de gerçek mağaza açılabilmeli;
                # Software 48 dil verisi yoksa SIGTRAP ile duruyor.
                for package in ('gnome-software', 'gnome-software-plugin-flatpak', 'iso-codes', 'flatpak'):
                    self.assertIn(package, packages)
                self.assertIn("linux-headers-" + ("amd64" if arch == "amd64" else "686-pae"), packages)
                self.assertNotIn("firmware-ipw2x00", packages)  # yalnızca onay sonrası yerel arşivden
                self.assertTrue((overlay / "etc/skel/İndirilenler").is_dir())
                self.assertNotIn("broadcom-sta-dkms", packages)
                self.assertNotIn("plank", packages)
                self.assertFalse(any(p.startswith("calamares-settings-") for p in packages))
                self.assertEqual("firmware-intel-graphics" in packages, arch == "amd64")
                self.assertEqual("grub-efi-amd64-bin" in packages, arch == "amd64")
                self.assertIn("firmware-libertas", packages)
                self.assertEqual("firmware-mediatek" in packages, arch == "amd64")
                for name in ("oguzdows-welcome.desktop", "oguzdows-install.desktop"):
                    launcher = overlay / "etc/skel/Masaüstü" / name
                    self.assertTrue(launcher.is_file())
                    self.assertTrue(os.access(launcher, os.X_OK))
                self.assertTrue((overlay / 'usr/lib/oguzdows/install_launcher.py').is_file())
                for name in ('rifki_pet.py','rifki_scene.py','rifki_motion.py'):
                    self.assertFalse((overlay / 'usr/lib/oguzdows' / name).exists())
                for name in ('rig','envelopes.json','intro-full.wav'):
                    self.assertFalse((overlay / 'usr/share/oguzdows/rifki' / name).exists())
                self.assertEqual((overlay / "usr/share/doc/oguzdows/ATOLYE-VE-MAGAZA-YENILEME.md").read_bytes(),
                                 (ROOT / "docs/ATOLYE-VE-MAGAZA-YENILEME.md").read_bytes())
                self.assertFalse(list(overlay.rglob("__pycache__")))
                for path in (overlay / "usr/lib/oguzdows").glob("*.py"):
                    self.assertTrue(os.access(path, os.X_OK))
                initrd_hook = overlay / 'etc/initramfs-tools/hooks/oguzdows-firmware'
                initrd_helper = overlay / 'usr/lib/oguzdows/initramfs_firmware.py'
                self.assertEqual(initrd_hook.is_file(), arch == 'amd64')
                self.assertEqual(initrd_helper.is_file(), arch == 'amd64')
                if arch == 'amd64':
                    self.assertTrue(os.access(initrd_hook, os.X_OK))
                    self.assertEqual(initrd_helper.read_bytes(), (ROOT / 'pc/initramfs-firmware.py').read_bytes())
                self.assertFalse((ROOT / 'system/etc/initramfs-tools').exists(), 'PC hook ortak Pi / ARM katmanına sızmamalı.')
                for hook in (output / "hooks/live").iterdir():
                    self.assertTrue(os.access(hook, os.X_OK))
                settings = yaml.safe_load((overlay / "etc/calamares/settings.conf").read_text())
                self.assertEqual(settings["branding"], "oguzdows")
                self.assertIn("tr_TR.UTF-8", (overlay / "etc/default/locale").read_text())
                self.assertIn("Europe/Istanbul", (overlay / "etc/timezone").read_text())

    def test_boot_args_are_shared_with_build_script(self):
        result = subprocess.run(["python3", str(ROOT / "scripts/configure.py"), "--print-boot-args"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), config.BOOT_ARGS)
        self.assertIn("--print-boot-args", (ROOT / "build.sh").read_text())

    def test_help_and_bad_architecture_do_not_require_build_tools(self):
        for args, code in ((["--help"], 0), (["arm64"], 2), (["amd64", "i386"], 2)):
            with self.subTest(args=args):
                result = subprocess.run(["bash", str(ROOT / "build.sh"), *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, code)

    def test_configure_only_calls_live_build_correctly_and_never_deletes_existing_work(self):
        for arch in ("amd64", "i386"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                repo = Path(directory) / "repo"
                shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".cache", "__pycache__", "build-amd64", "build-i386", "preview"))
                bin_dir = Path(directory) / "bin"
                bin_dir.mkdir()
                lb = bin_dir / "lb"
                lb.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$LB_CALLS"\n[ "$1" = config ]\n')
                lb.chmod(0o755)
                log = Path(directory) / "calls"
                env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "LB_CALLS": str(log)}
                cmd = ["bash", str(repo / "build.sh"), arch, "--configure-only"]
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = log.read_text().splitlines()
                self.assertEqual(args[0], "config")
                def option(name):
                    return args[args.index(name) + 1]
                self.assertEqual(option("--distribution"), "trixie" if arch == "amd64" else "bookworm")
                self.assertEqual(option("--linux-flavours"), "amd64" if arch == "amd64" else "686-pae")
                self.assertEqual(option("--bootloaders"), "syslinux,grub-efi" if arch == "amd64" else "syslinux")
                self.assertEqual(option("--bootappend-live"), config.BOOT_ARGS)
                self.assertEqual(option("--uefi-secure-boot"), "disable")
                sentinel = repo / f"build-{arch}/keep-me.txt"
                sentinel.write_text("önceki derleme")
                again = subprocess.run(cmd, capture_output=True, text=True, env=env)
                self.assertNotEqual(again.returncode, 0)
                self.assertEqual(sentinel.read_text(), "önceki derleme")
                self.assertFalse(list(repo.glob("*.iso")))


if __name__ == "__main__":
    unittest.main()
