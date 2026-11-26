import ast
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from support import ROOT, load

config = load("oguzdows_pi_config", "scripts/configure-pi.py")
pi = load("pi_support", "system/usr/lib/oguzdows/pi_support.py")
tune = load("oguzdows_pi_tune", "raspberrypi/system/usr/lib/oguzdows/pi-tune.py")
first = load("oguzdows_pi_firstboot", "raspberrypi/system/usr/lib/oguzdows/pi-firstboot.py")
verify = load("oguzdows_pi_verify", "scripts/verify-pi.py")


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


class PiConfigurationTests(unittest.TestCase):
    def test_separate_images_preserve_the_desktop_without_pc_boot_or_accounts(self):
        for arch in ("armhf", "arm64"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "config"
                config.configure(arch, output)
                stage = output / "stage-oguzdows"
                overlay = stage / "00-desktop/files/overlay"
                info = json.loads((overlay / "etc/oguzdows/pi-image.json").read_text())
                self.assertEqual(info["arch"], arch)
                self.assertEqual(info["pi_gen_commit"], config.LOCK[arch]["commit"])
                packages = (stage / "00-desktop/00-packages-nr").read_text().splitlines()
                self.assertEqual(len(packages), len(set(packages)))
                for package in ("xfce4", "libreoffice-writer", "vlc", "netsurf-gtk", "plymouth", "firmware-brcm80211", "zram-tools", "python3-rpi-lgpio"):
                    self.assertIn(package, packages)
                self.assertIn('firefox-esr', packages) if arch == 'arm64' else self.assertNotIn('firefox-esr', packages)
                for package in ("intel-microcode", "amd64-microcode", "grub-pc-bin", "calamares", "broadcom-sta-dkms", "dkms", "firmware-amd-graphics", "xserver-xorg-video-all"):
                    self.assertNotIn(package, packages)
                for name in config.PC_ONLY:
                    self.assertFalse((overlay / name).exists(), name)
                for name in ('rifki_pet.py','rifki_scene.py','rifki_motion.py'):
                    self.assertFalse((overlay / 'usr/lib/oguzdows' / name).exists())
                self.assertFalse((overlay / 'usr/share/oguzdows/rifki/rig').exists())
                self.assertTrue((overlay / "etc/skel/Masaüstü/oguzdows-welcome.desktop").is_file())
                self.assertFalse((overlay / "etc/skel/Masaüstü/oguzdows-install.desktop").exists())
                self.assertTrue((overlay / "usr/share/plymouth/themes/oguzdows/oguzdows.script").is_file())
                self.assertTrue((overlay / "usr/share/themes/OguzDows/gtk-3.0/gtk.css").is_file())
                start = (overlay / "usr/share/oguzdows/start.html").read_text()
                self.assertIn("Raspberry Pi", start)
                self.assertIn("JavaScript yoktur", start)
                self.assertNotIn("Canlı oturumdan kurulumu", start)
                self.assertNotIn("açılış menüsündeki güvenli görüntüyü", start)
                self.assertFalse(list(overlay.rglob("__pycache__")))
                for path in (stage / "prerun.sh", stage / "00-desktop/01-run.sh", overlay / "usr/lib/oguzdows/pi-firstboot.py", overlay / "usr/local/bin/oguzdows-browser"):
                    self.assertTrue(os.access(path, os.X_OK), str(path))
                result = subprocess.run(["bash", "-c", 'BASE_DIR=/pi-gen; source "$1"; printf "%s\\n" "$USE_QEMU" "$FIRST_USER_PASS" "$ENABLE_SSH" "$STAGE_LIST"', "bash", str(output / "config")], capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.splitlines(), ["0", "", "0", "/pi-gen/stage0 /pi-gen/stage1 /pi-gen/stage2 /pi-gen/stage-oguzdows"])
                with self.assertRaises(FileExistsError):
                    config.configure(arch, output)

    def test_sources_are_commit_and_archive_hash_locked(self):
        for arch in ("armhf", "arm64"):
            info = config.LOCK[arch]
            self.assertRegex(info["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(info["archive_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(len(info["kernels"]), len(info["initramfs"]))
        self.assertIn("kernel.img", config.LOCK["armhf"]["kernels"])
        self.assertIn("kernel_2712.img", config.LOCK["arm64"]["kernels"])
        self.assertNotIn("kernel.img", config.LOCK["arm64"]["kernels"])
        builder = (ROOT / "build-pi.sh").read_text()
        self.assertIn("sha256sum --check --strict", builder)
        self.assertIn("export-image/01-user-rename/SKIP", builder)
        self.assertIn("stage2/SKIP_IMAGES", builder)
        self.assertIn("verify-pi-image.sh", builder)

    def test_help_and_bad_arguments_are_unprivileged(self):
        for args, status in ((["--help"], 0), ([], 2), (["amd64"], 2), (["arm64", "--wrong"], 2), (["arm64", "armhf", "other"], 2)):
            result = subprocess.run(["bash", str(ROOT / "build-pi.sh"), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, status, result.stderr)

    def test_configure_only_never_downloads_or_overwrites_previous_work(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".cache", "__pycache__", "build-amd64", "build-i386", "build-rpi-armhf", "build-rpi-arm64", "preview", "test-results"))
            tools = Path(directory) / "bin"
            tools.mkdir()
            for name in ("curl", "debootstrap", "mount", "sudo"):
                target = tools / name
                target.write_text('#!/bin/sh\necho "Yasak araç çağrıldı" >&2\nexit 73\n')
                target.chmod(0o755)
            env = {**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"]}
            cmd = ["bash", str(repo / "build-pi.sh"), "armhf", "--configure-only"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            sentinel = write(repo, "build-rpi-armhf/keep-me", "önceki çalışma")
            again = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(sentinel.read_text(), "önceki çalışma")
            self.assertFalse(list(repo.rglob("*.img*")))

    def test_cpu_smoke_covers_armv6_and_baseline_armv8_without_claiming_boot(self):
        smoke = (ROOT / "raspberrypi/stage/00-desktop/02-run.sh").read_text()
        self.assertIn("cpu=arm1176", smoke)
        self.assertIn("cpu=cortex-a53", smoke)
        self.assertIn('"${ROOTFS_DIR}/tmp/oguzdows-qemu-static"', smoke)
        target = (ROOT / 'scripts/pi-runtime-smoke.py').read_text()
        self.assertIn('gi.require_version', target)
        self.assertIn("'/usr/bin/xfce4-session', '--version'", target)
        self.assertIn('xvfb-run', smoke)
        self.assertIn('pi-build-report.json', smoke)

    def test_binfmt_preparation_uses_packaged_definitions_and_checks_an_empty_chroot(self):
        script = ROOT / 'scripts/prepare-pi-binfmt.sh'
        for args, status in ((['--help'], 0), ([], 2), (['amd64'], 2), (['arm64', 'extra'], 2), (['arm; id'], 2)):
            result = subprocess.run(['bash', str(script), *args], capture_output=True, text=True)
            self.assertEqual(result.returncode, status, result.stderr)
        if os.geteuid() != 0:
            result = subprocess.run(['bash', str(script), 'arm64'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('root gerektirir', result.stderr)
        source = script.read_text()
        self.assertIn('/usr/lib/binfmt.d/qemu-$cpu-static.conf', source)
        self.assertIn('/usr/lib/systemd/systemd-binfmt "$config"', source)
        self.assertIn('arch-test -c "$probe" "$arch"', source)
        self.assertIn('trap cleanup EXIT', source)
        for forbidden in ('curl ', 'wget ', 'docker ', 'update-binfmts --remove', 'systemctl restart'):
            self.assertNotIn(forbidden, source)

    def test_firstboot_gates_local_and_remote_login_and_never_enables_autologin(self):
        base = ROOT / "raspberrypi/system/etc/systemd/system"
        for service in ("lightdm", "ssh"):
            unit = (base / f"{service}.service.d/10-oguzdows-firstboot.conf").read_text()
            self.assertIn("Requires=oguzdows-pi-firstboot.service", unit)
            self.assertIn("ExecStartPre=/usr/bin/test -f /var/lib/oguzdows/firstboot.done", unit)
        setup = (ROOT / "raspberrypi/stage/00-desktop/files/configure-system.sh").read_text()
        self.assertIn("userdel --remove oguz-build", setup)
        self.assertIn("systemctl mask dphys-swapfile.service", setup)
        self.assertIn("systemctl disable ssh.service", setup)
        self.assertNotIn("autologin-user=", setup)
        self.assertNotIn("init=/", setup)  # Resmî ilk açılış / bölüm büyütme korunur.

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze kurulu değil")
    def test_pi_units_pass_the_real_systemd_unit_parser(self):
        base = ROOT / "raspberrypi/system/etc/systemd/system"
        result = subprocess.run(["systemd-analyze", "--man=no", "verify",
                                 str(base / "oguzdows-pi-firstboot.service"),
                                 str(base / "oguzdows-pi-tune.service"),
                                 str(base / "oguzdows-pi-display-recovery.service")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pi_workflow_is_separate_non_cancelling_and_checks_images(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/raspberrypi.yml").read_text())
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertEqual(workflow["jobs"]["image"]["needs"], "verify")
        steps = str(workflow["jobs"]["image"]["steps"])
        self.assertIn("build-pi.sh", steps)
        self.assertIn("qemu-user-static", steps)
        tools = next(step['run'] for step in workflow['jobs']['image']['steps']
                     if step.get('name') == 'Yerel pi-gen ve çapraz ARM çalıştırma araçları')
        self.assertIn("scripts/ci-run.py --title 'Pi ${{ matrix.arch }} host araçları'", tools)
        self.assertIn("update-binfmts --display", tools)
        self.assertIn('bash scripts/prepare-pi-binfmt.sh "$1"', tools)
        self.assertIn(".img.xz.sha256", steps)
        verification = str(workflow["jobs"]["verify"]["steps"])
        self.assertIn("--pi", verification)
        self.assertIn("scripts/ci-run.py --title 'Pi birim ve kaynak kontrolleri'", verification)
        self.assertIn("python3 -W error::ResourceWarning -m unittest", verification)
        self.assertEqual(workflow["jobs"]["verify"]["env"]["OGUZDOWS_TEST_TARGET"], "raspberrypi")
        pc = yaml.safe_load((ROOT / ".github/workflows/main.yml").read_text())
        self.assertNotIn("OGUZDOWS_TEST_TARGET", pc["jobs"]["verify"].get("env", {}))
        self.assertNotIn("calamares", (ROOT / "packages/raspberrypi.list").read_text().lower())

    def test_registered_workflow_can_call_pi_without_rebuilding_pc_isos(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/main.yml").read_text())
        job = workflow["jobs"]["raspberrypi"]
        self.assertEqual(job["uses"], "./.github/workflows/raspberrypi.yml")
        self.assertIn("'raspberrypi'", job["if"])
        for name in ("verify", "build"):
            self.assertIn("target != 'raspberrypi'", workflow["jobs"][name]["if"])

    def test_export_chroot_receives_a_shell_script_not_a_python_elf_as_shell_input(self):
        script = 'on_chroot() { [ "$#" -eq 0 ] || return 71; cat; }; export -f on_chroot; export ARCH=armhf; bash "$1"'
        result = subprocess.run(["bash", "-c", script, "bash", str(ROOT / "raspberrypi/export-check.sh")], capture_output=True, text=True, check=True)
        self.assertIn("/usr/bin/python3 /usr/lib/oguzdows/verify-pi.py", result.stdout)
        self.assertIn('--arch "armhf" --pre-export', result.stdout)

    def test_browser_selects_netsurf_only_for_armv6_and_never_interprets_options(self):
        for legacy, expected in ((True, "/usr/bin/netsurf-gtk"), (False, "/usr/bin/firefox-esr")):
            with patch.object(pi, "armv6", return_value=legacy), patch.object(os, "execv") as execute, patch.object(os, "access", return_value=True), patch("sys.argv", ["oguzdows-browser", "https://example.org/"]):
                load("oguzdows_browser_test", "system/usr/lib/oguzdows/browser.py").main()
                execute.assert_called_once_with(expected, [expected, "https://example.org/"])
        with patch.object(os, "execv") as execute, patch("sys.argv", ["oguzdows-browser", "--private-window"]):
            with self.assertRaises(SystemExit):
                load("oguzdows_browser_test_rejected", "system/usr/lib/oguzdows/browser.py").main()
            execute.assert_not_called()

    def test_pc_and_pi_browser_launchers_share_the_same_isolated_module(self):
        common = (ROOT / 'system/usr/local/bin/oguzdows-browser').read_text()
        self.assertEqual(common, (ROOT / 'raspberrypi/system/usr/local/bin/oguzdows-browser').read_text())
        self.assertIn('/usr/bin/python3 -I /usr/lib/oguzdows/browser.py "$@"', common)

    def test_new_privileged_python_never_uses_a_shell(self):
        paths = list((ROOT / "raspberrypi/system").rglob("*")) + [ROOT / "system/usr/lib/oguzdows/browser.py"]
        for path in paths:
            if path.is_file() and path.suffix == ".py":
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.Call):
                        self.assertFalse(any(keyword.arg == "shell" and getattr(keyword.value, "value", None) is True for keyword in node.keywords))


class PiPolicyTests(unittest.TestCase):
    def test_old_zero_and_zero2_are_not_confused(self):
        for board in ("Raspberry Pi Zero Rev 1.3", "Raspberry Pi Zero W Rev 1.1", "Raspberry Pi Model B Rev 2", "Raspberry Pi 1 Model B+"):
            self.assertTrue(pi.armv6("armv7l", board))
        for board in ("Raspberry Pi Zero 2 W Rev 1.0", "Raspberry Pi 2 Model B Rev 1.1", "Raspberry Pi 3 Model B", "Raspberry Pi 5 Model B"):
            self.assertFalse(pi.armv6("aarch64", board))
        self.assertTrue(pi.armv6("armv6l", ""))

    def test_memory_profiles_and_zram_are_bounded(self):
        for memory, expected in ((450560, "mini"), (786432, "mini"), (950000, "light"), (2097152, "light"), (4000000, "full")):
            self.assertEqual(pi.policy(memory, "Raspberry Pi 4")["profile"], expected)
        self.assertEqual(pi.policy(8388608, "Raspberry Pi Zero W")["profile"], "mini")
        for memory in (1024, 65536, 450560, 1048576, 8388608):
            for profile in ("auto", "mini", "light", "full"):
                settings = pi.policy(memory, "Raspberry Pi 5", profile)
                self.assertLessEqual(settings["zram_mb"], min(1024, memory // 1024))
                self.assertEqual(settings["algorithm"], "lz4")
        with self.assertRaises(ValueError):
            pi.policy(1000000, "", "performance; rm -rf /")

    def test_profile_config_is_not_executable_and_kernel_override_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "proc/meminfo", "MemTotal: 4194304 kB\n")
            write(root, "etc/oguzdows/pi.conf", 'profile=$(touch /tmp/should-not-exist)\n')
            self.assertEqual(pi.current_policy(root)["profile"], "full")
            write(root, "proc/cmdline", "notoguzdows.profile=mini")
            self.assertEqual(pi.current_policy(root)["profile"], "full")
            write(root, "proc/cmdline", "oguzdows.profile=light")
            self.assertEqual(pi.current_policy(root)["profile"], "light")
            write(root, "sys/firmware/devicetree/base/model", "Raspberry Pi Zero W\x00")
            self.assertTrue(pi.is_pi(root))
            self.assertEqual(pi.model(root), "Raspberry Pi Zero W")

    def test_tuning_only_changes_named_files_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                tune.apply(root)
            write(root, "etc/oguzdows/pi-image.json", "{}")
            write(root, "proc/meminfo", "MemTotal: 450560 kB\n")
            write(root, "proc/sys/vm/swappiness", "60")
            write(root, "proc/sys/vm/page-cluster", "3")
            settings = tune.apply(root)
            config_path = root / "etc/default/zramswap"
            self.assertIn(f"SIZE={settings['zram_mb']}", config_path.read_text())
            self.assertNotIn("PERCENT=", config_path.read_text())
            self.assertEqual((root / "proc/sys/vm/swappiness").read_text(), "100\n")
            before = config_path.stat().st_mtime_ns
            tune.apply(root)
            self.assertEqual(config_path.stat().st_mtime_ns, before)
            self.assertFalse(list(root.rglob("*.new")))

    def test_platform_sdio_drm_and_network_are_reported_without_pci(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root, "bus/sdio/devices/mmc1:0001:1/modalias", "sdio:c00v02D0dA9A6")
            driver = root / "bus/sdio/devices/mmc1:0001:1/driver"
            driver.symlink_to("/sys/bus/sdio/drivers/brcmfmac")
            write(root, "bus/platform/devices/v3d/modalias", "platform:v3d")
            (root / "class/net/wlan0/device").mkdir(parents=True)
            (root / "class/net/wlan0/device/driver").symlink_to("/sys/bus/sdio/drivers/brcmfmac")
            report = pi.peripheral_summary(root)
            self.assertIn("sdio", report)
            self.assertIn("brcmfmac", report)
            self.assertIn("v3d → SÜRÜCÜ BAĞLI DEĞİL", report)
            self.assertIn("Ağ · wlan0", report)


class PiFirstbootTests(unittest.TestCase):
    def setUp(self):
        self.sync = patch.object(first.os, "sync").start()
        self.addCleanup(patch.stopall)

    def test_username_and_password_validation_rejects_injection_or_shared_root(self):
        for name in ("root", "oguz-build", "nobody", "--root", "a:b", "a\nb", "İsim", "a" * 32, "$(id)"):
            self.assertFalse(first.valid_username(name), name)
        for name in ("oguz", "pasha", "veli_1", "pi-kullanicisi"):
            self.assertTrue(first.valid_username(name))
        for password in ("", "oguz", "0123456789\nroot:x", "0123456789:more", "\x00" * 10):
            self.assertFalse(first.valid_password(password))
        self.assertTrue(first.valid_password("Uzun bir parola 123!"))

    def test_headless_file_only_accepts_one_hashed_account(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oguzdows-userconf.txt"
            self.assertIsNone(first.read_provision(path))
            hashed = "$6$salt$" + "a" * 86
            path.write_text("pasha:" + hashed + "\n")
            self.assertEqual(first.read_provision(path), ("pasha", hashed))
            for value in ("root:" + hashed, "pasha:plaintext-password", "pasha:$1$old$weak", "pasha:" + hashed + "\nother:" + hashed, "pasha:" + hashed + ":extra", "x" * 4097):
                path.write_text(value)
                with self.subTest(value=value[:40]), self.assertRaises(ValueError):
                    first.read_provision(path)

    def test_headless_file_refuses_symlinks_and_special_files_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration"
            path.symlink_to("/etc/passwd")
            with self.assertRaises(OSError):
                first.read_provision(path)
            path.unlink()
            os.mkfifo(path)
            with self.assertRaises(ValueError):
                first.read_provision(path)

    def test_password_only_goes_to_stdin_and_success_follows_all_account_changes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(first, "lookup", return_value=None), patch.object(first.pwd, "getpwuid", side_effect=KeyError), patch.object(first.grp, "getgrnam", return_value=object()), patch.object(first, "run") as run:
            state = Path(directory) / "state"
            password = "Yerel guclu parola 123"
            first.complete("pasha", password, False, state)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual([command[0] for command in commands], ["/usr/sbin/useradd", "/usr/sbin/usermod", "/usr/sbin/usermod", "/usr/sbin/chpasswd"])
            self.assertNotIn(password, str(commands))
            self.assertEqual(run.call_args.kwargs["secret"], "pasha:" + password + "\n")
            done = state / "firstboot.done"
            self.assertEqual(json.loads(done.read_text())["username"], "pasha")
            self.assertNotIn(password, done.read_text())
            self.assertEqual(stat.S_IMODE(done.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            self.assertFalse((state / "firstboot.pending.json").exists())

    def test_power_loss_keeps_no_success_marker_and_can_resume_only_the_same_account(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(first, "lookup", return_value=None) as lookup, patch.object(first.pwd, "getpwuid", side_effect=KeyError), patch.object(first.grp, "getgrnam", return_value=object()), patch.object(first, "run", side_effect=RuntimeError("kesinti")) as run:
            state = Path(directory) / "state"
            with self.assertRaises(RuntimeError):
                first.complete("pasha", "Guclu parola 123!", False, state)
            self.assertFalse((state / "firstboot.done").exists())
            self.assertEqual(json.loads((state / "firstboot.pending.json").read_text())["username"], "pasha")
            with self.assertRaises(ValueError):
                first.complete("baska", "Guclu parola 123!", False, state)
            lookup.return_value = SimpleNamespace(pw_uid=1000, pw_dir="/home/pasha")
            run.side_effect = None
            run.reset_mock()
            first.complete("pasha", "Yeni guclu parola 123!", False, state)
            self.assertFalse(any(call.args[0][0].endswith("useradd") for call in run.call_args_list))
            self.assertTrue((state / "firstboot.done").is_file())

    def test_existing_account_or_uid_is_never_silently_hijacked(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(first, "lookup", return_value=SimpleNamespace(pw_uid=1000, pw_dir="/home/pasha")), patch.object(first, "run") as run:
            with self.assertRaises(ValueError):
                first.complete("pasha", "Guclu parola 123!", False, Path(directory))
            run.assert_not_called()
        with tempfile.TemporaryDirectory() as directory, patch.object(first, "lookup", return_value=None), patch.object(first.pwd, "getpwuid", return_value=object()), patch.object(first.grp, "getgrnam", return_value=object()), patch.object(first, "run") as run:
            with self.assertRaises(ValueError):
                first.complete("pasha", "Guclu parola 123!", False, Path(directory))
            run.assert_not_called()

    def test_command_failures_do_not_echo_password_or_captured_stderr(self):
        error = subprocess.CalledProcessError(1, ["/usr/sbin/chpasswd"], stderr="secret-password")
        with patch.object(first.subprocess, "run", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                first.run(["/usr/sbin/chpasswd"], "pasha:secret-password\n")
            self.assertNotIn("secret-password", str(caught.exception))


class PiImageValidationTests(unittest.TestCase):
    def fixture(self, directory, arch="armhf"):
        config.configure(arch, Path(directory) / "config")
        root = Path(directory) / "config/stage-oguzdows/00-desktop/files/overlay"
        # Bunlar yalnızca negatif yapısal test verileri; gerçek boot/görsel dosyaları değildir.
        for path in ["boot/firmware/start.elf", "boot/firmware/start4.elf", "boot/firmware/fixup.dat", "boot/firmware/bootcode.bin", "boot/firmware/overlays/vc4-kms-v3d.dtbo", "usr/share/backgrounds/oguzdows/wallpaper.png", "usr/share/oguzdows/wallpapers.json", "usr/share/themes/OguzDows/xfwm4/themerc", *["boot/firmware/" + name for name in config.LOCK[arch]["kernels"] + config.LOCK[arch]["dtbs"] + config.LOCK[arch]["initramfs"]]]:
            write(root, path, "test-verisi")
        write(root, "boot/firmware/config.txt", "dtoverlay=vc4-kms-v3d\nauto_initramfs=1\ncamera_auto_detect=1\ndisplay_auto_detect=1\ndtparam=audio=on\ndisable_fw_kms_setup=1\narm_boost=1\n" + ("arm_64bit=1\n" if arch == "arm64" else ""))
        write(root, "boot/firmware/cmdline.txt", "root=PARTUUID=1234abcd-02 rootwait quiet splash init=/usr/lib/raspberrypi-sys-mods/firstboot\n")
        write(root, 'usr/lib/raspberrypi-sys-mods/firstboot', 'resmî ilk açılış test verisi')
        write(root, 'etc/init.d/resize2fs_once', 'resmî büyütme test verisi')
        write(root, "etc/fstab", "PARTUUID=1234abcd-01 /boot/firmware vfat defaults 0 2\nPARTUUID=1234abcd-02 / ext4 defaults,noatime 0 1\n")
        contract = json.loads((root / 'usr/share/oguzdows/pi-contract.json').read_text())
        expected = contract['architectures'][arch]
        write(root, "usr/lib/os-release", f'NAME="OğuzDows"\nID="{expected["os_id"]}"\nVERSION_ID="12"\nVERSION_CODENAME="bookworm"\n')
        # Galeri / önizlemeler de yalnızca yapısal test verisidir, görüntülenmez.
        wallpaper_paths = ['/' + name for name in contract['asset_hashes'] if name.endswith('.jpg')]
        preview = '/usr/share/oguzdows/wallpaper-previews/test.jpg'
        write(root, preview.removeprefix('/'), 'önizleme test verisi')
        write(root, 'usr/share/oguzdows/wallpapers.json', json.dumps([{'path': name, 'preview': preview} for name in wallpaper_paths]))
        for group in contract['features'].values():
            for name in group['files']:
                if not (root / name).exists():
                    write(root, name, 'özellik varlığı test verisi')
        # Bunlar sahte ELF başlıklarıdır; hiçbir testte çalıştırılmaz.
        header = bytearray(64)
        header[:4] = b'\x7fELF'
        header[4:6] = bytes((expected['elf_class'], 1))
        struct.pack_into('<H', header, 18, expected['elf_machine'])
        if arch == 'armhf':
            struct.pack_into('<I', header, 36, 0x5000400)
        for name in ('usr/bin/python3', 'usr/lib/oguzdows/oguzdows-store-native', 'usr/lib/oguzdows/oguzdows-news-native'):
            write(root, name, '').write_bytes(header)
        report = {'schema': 1, 'arch': arch, 'minimum_cpu': expected['cpu'], 'errors': [],
                  'scope': 'ARM-qemu-user-with-host-Xvfb', 'source_revision': contract['source_revision'],
                  'pi_gen_commit': contract['pi_gen_commit'], 'suite': contract['suite'],
                  'gui': {'gtk_window': True, 'xfce_version': 'xfce4-session test', 'native_store_version': 'OğuzDows test', 'native_news_version': 'OğuzDows Haber · GTK 3.24.0'},
                  'python_modules': contract['python_modules'],
                  'abi': {'/' + name: {'bits': 32 if arch == 'armhf' else 64,
                                      'machine': expected['elf_machine'], 'hard_float': True if arch == 'armhf' else None}
                          for name in ('usr/bin/python3', 'usr/lib/oguzdows/oguzdows-store-native', 'usr/lib/oguzdows/oguzdows-news-native')},
                  'packages': {name: {'architecture': arch, 'version': 'test-verisi'} for name in contract['required_packages']},
                  'physical_boot': False, 'hardware_gpu': False, 'performance_measurement': False,
                  'real_package_transactions': False, 'real_audio_playback': False,
                  'feature_presence': {'groups': list(contract['features']), 'asset_hashes': len(contract['asset_hashes']),
                                       'wallpapers': 20, 'selected_narration': 11,
                                       'speech_contexts': len(json.loads((root / 'usr/share/oguzdows/rifki/speech.json').read_text()))}}
        write(root, 'usr/share/oguzdows/pi-build-report.json', json.dumps(report))
        write(root, 'etc/lightdm/lightdm.conf', '[Seat:*]\nuser-session=oguzdows\ngreeter-session=lightdm-gtk-greeter\n')
        report['full_session'] = {'uid': 65534, 'errors': [], 'stable_samples': 5,
                                  'scope': 'non-root-Xfce-on-host-Xvfb', 'x11_window_manager': 'Xfwm4',
                                  'xfwm4': True, 'xfce4-panel': True, 'xfdesktop': True,
                                  'lightdm_pam': False, 'physical_boot': False, 'performance_measurement': False}
        report['full_session']['news'] = {'native_process_alive': True, 'worker_exited': True, 'cached_fixture_preserved': True,
                                          'network_tested': False, 'performance_measurement': False, 'window_pixels_verified': False}
        if arch == 'armhf':
            report['full_session']['browser'] = {'program': 'netsurf-gtk', 'local_start_page_alive': True,
                                                 'network_tested': False, 'modern_sites_verified': False}
        write(root, 'usr/share/oguzdows/pi-build-report.json', json.dumps(report))
        write(root, "etc/passwd", "root:x:0:0:root:/root:/bin/bash\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n")
        write(root, "etc/shadow", "root:*:1:0:99999:7:::\n")
        write(root, "etc/sudoers", "%sudo ALL=(ALL:ALL) ALL\n")
        write(root, "etc/machine-id", "")
        units = root / "etc/systemd/system"
        (units / "multi-user.target.wants").mkdir()
        for service in ("oguzdows-pi-firstboot", "oguzdows-pi-tune", "zramswap"):
            (units / f"multi-user.target.wants/{service}.service").symlink_to(f"/lib/systemd/system/{service}.service")
        (units / "display-manager.service").symlink_to("/lib/systemd/system/lightdm.service")
        (units / "dphys-swapfile.service").symlink_to("/dev/null")
        return root

    def test_both_final_images_have_required_boot_chains_and_security(self):
        for arch in ("armhf", "arm64"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory, patch("sys.stdout", io.StringIO()):
                root = self.fixture(directory, arch)
                verify.validate(root, arch)
                with self.assertRaises(ValueError):
                    verify.validate(root, "arm64" if arch == "armhf" else "armhf")

    def test_only_pre_export_can_omit_initramfs(self):
        with tempfile.TemporaryDirectory() as directory, patch("sys.stdout", io.StringIO()):
            root = self.fixture(directory)
            (root / "boot/firmware/initramfs").unlink()
            verify.validate(root, "armhf", pre_export=True)
            with self.assertRaisesRegex(ValueError, "initramfs"):
                verify.validate(root, "armhf")

    def test_missing_pi5_kernel_or_unresolved_root_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory, "arm64")
            (root / "boot/firmware/kernel_2712.img").write_text("")
            with self.assertRaisesRegex(ValueError, "kernel_2712"):
                verify.validate(root, "arm64")
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            write(root, "boot/firmware/cmdline.txt", "root=ROOTDEV\n")
            with self.assertRaisesRegex(ValueError, "PARTUUID"):
                verify.validate(root, "armhf")

    def test_export_rejects_failed_host_only_or_inflated_runtime_receipts(self):
        with tempfile.TemporaryDirectory() as directory, patch('sys.stdout', io.StringIO()):
            root = self.fixture(directory, 'arm64')
            path = root / 'usr/share/oguzdows/pi-build-report.json'
            original = json.loads(path.read_text())
            changes = ({'scope': 'host-gui-only'}, {'physical_boot': True}, {'gui': {'gtk_window': False}},
                       {'errors': ['Hedef GTK başarısız']}, {'minimum_cpu': 'host'}, {'packages': {}},
                       {'feature_presence': {'groups': []}}, {'source_revision': 'yanlış kaynak'},
                       {'abi': {}}, {'python_modules': []}, {'schema': 2}, {'gui': None})
            for change in changes:
                with self.subTest(change=change):
                    path.write_text(json.dumps({**original, **change}))
                    with self.assertRaises(ValueError):
                        verify.validate(root, 'arm64')
            path.write_text(json.dumps(original))
            image = root / next(name for name in json.loads((root / 'usr/share/oguzdows/pi-contract.json').read_text())['asset_hashes'] if name.endswith('.jpg'))
            image.write_bytes(b'degismis')
            with self.assertRaisesRegex(ValueError, 'hash'):
                verify.validate(root, 'arm64')

    def test_export_rejects_stale_thunar_policy_theme_or_compositor_without_executing_it(self):
        with tempfile.TemporaryDirectory() as directory, patch('sys.stdout', io.StringIO()):
            root = self.fixture(directory, 'arm64')
            contract = json.loads((root / 'usr/share/oguzdows/pi-contract.json').read_text())
            for relative in ('usr/lib/oguzdows/file_manager.py', 'usr/lib/oguzdows/render-assets.py',
                             'usr/share/oguzdows/ui/window-geometry.css', 'usr/share/oguzdows/ui/modern.css',
                             'usr/share/oguzdows/compositor/full.conf'):
                with self.subTest(relative=relative):
                    self.assertIn(relative, contract['asset_hashes'])
                    path = root / relative
                    original = path.read_bytes()
                    path.write_text('stale repair bytes / never executed\n')
                    with self.assertRaisesRegex(ValueError, 'hash'):
                        verify.validate(root, 'arm64')
                    path.write_bytes(original)
            verify.validate(root, 'arm64')

    def test_export_requires_complete_nonroot_session_and_netsurf_receipts(self):
        for broken in ('missing', 'root', 'panel', 'version-only', 'samples-type', 'browser'):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                path = root / 'usr/share/oguzdows/pi-build-report.json'
                report = json.loads(path.read_text())
                if broken == 'missing': report.pop('full_session')
                if broken == 'root': report['full_session']['uid'] = 0
                if broken == 'panel': report['full_session']['xfce4-panel'] = False
                if broken == 'version-only': report['full_session']['x11_window_manager'] = ''
                if broken == 'samples-type': report['full_session']['stable_samples'] = '5'
                if broken == 'browser': report['full_session'].pop('browser')
                path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, 'oturum|NetSurf'):
                    verify.validate(root, 'armhf')

    def test_export_rechecks_catalog_and_never_imports_the_images_python_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory, 'arm64')
            module = root / 'usr/lib/oguzdows/pi_contract.py'
            original = module.read_bytes()
            module.write_text('raise RuntimeError("İMAJDAN HOSTTA KOD ÇALIŞTIRILDI")\n')
            env = {**os.environ, 'PYTHONPATH': '', 'PYTHONDONTWRITEBYTECODE': '1'}
            # Host yalnızca kendi scripts/pi_contract.py okuyucusunu kullanır.
            result = subprocess.run(['python3', str(ROOT / 'scripts/verify-pi.py'), '--root', str(root), '--arch', 'arm64'],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Hedefe kopyalanan incelenmiş verifier + okuyucu da kendi başına bulunabilmeli.
            module.write_bytes(original)
            result = subprocess.run(['python3', str(root / 'usr/lib/oguzdows/verify-pi.py'), '--root', str(root), '--arch', 'arm64'],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            write(root, 'usr/share/oguzdows/wallpapers.json', '[]')
            with self.assertRaisesRegex(ValueError, 'duvar kâğıdı'):
                verify.validate(root, 'arm64')

    def test_official_camera_resize_and_async_network_rules_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            path = root / 'boot/firmware/config.txt'
            original = path.read_text()
            for content in (original.replace('camera_auto_detect=1', 'camera_auto_detect=0'), original + 'kernel=kernel8.img\n'):
                path.write_text(content)
                with self.assertRaises(ValueError): verify.validate(root, 'armhf')
            path.write_text(original)
            commandline = root / 'boot/firmware/cmdline.txt'
            original = commandline.read_text()
            commandline.write_text(original.replace(' init=/usr/lib/raspberrypi-sys-mods/firstboot', ''))
            with self.assertRaisesRegex(ValueError, 'büyütme'):
                verify.validate(root, 'armhf')
            commandline.write_text(original)
            path = root / 'etc/systemd/system/network-online.target.wants/NetworkManager-wait-online.service'
            path.parent.mkdir(parents=True)
            path.symlink_to('/lib/systemd/system/NetworkManager-wait-online.service')
            with self.assertRaisesRegex(ValueError, 'bekleyici'):
                verify.validate(root, 'armhf')

    def test_security_regressions_are_rejected(self):
        cases = [("etc/shadow", "root:$6$password:1:0:9999:7:::\n", "Root"),
                 ("etc/passwd", "oguz:x:1000:1000:live:/home/oguz:/bin/bash\n", "normal kullanıcı"),
                 ("etc/sudoers.d/bad", "oguz ALL=(ALL) NOPASSWD: ALL\n", "parolasız sudo"),
                 ("etc/machine-id", "cloned-id", "Makine kimliği"),
                 ("etc/lightdm/lightdm.conf.d/99-unsafe.conf", "[Seat:*]\nautologin-user=oguz\n", "otomatik giriş"),
                 ("etc/ssh/ssh_host_ed25519_key", "copied-key", "SSH sunucu anahtarı"),
                 ("var/lib/oguzdows/firstboot.done", "{}", "taşınmaması")]
        for filename, content, expected in cases:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                write(root, filename, content)
                with self.assertRaisesRegex(ValueError, expected):
                    verify.validate(root, "armhf")


if __name__ == "__main__":
    unittest.main()
