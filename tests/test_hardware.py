import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import load

hardware = load("hardware", "system/usr/lib/oguzdows/hardware.py")
helper = load("oguzdows_driver_helper", "system/usr/local/sbin/oguzdows-driver-helper")


class HardwareTests(unittest.TestCase):
    def test_live_detection_uses_whole_kernel_argument(self):
        self.assertTrue(hardware.is_live("quiet boot=live components"))
        self.assertFalse(hardware.is_live("quiet notboot=live"))
        self.assertFalse(hardware.is_live("boot=installed"))

    def test_memory_and_light_profiles(self):
        self.assertEqual(hardware.memory_kib("MemTotal: 2048000 kB\nMemFree: 10 kB\n"), 2048000)
        for text in ("", "MemTotal: invalid kB", "MemTotal:", "MemTotal: -100 kB"):
            self.assertEqual(hardware.memory_kib(text), 0)
        self.assertTrue(hardware.light_profile("quiet", 1048576))
        self.assertTrue(hardware.light_profile("nomodeset", 8388608))
        self.assertTrue(hardware.light_profile("oguzdows.profile=light", 8388608))
        self.assertFalse(hardware.light_profile("quiet", 8388608))
        self.assertTrue(hardware.light_profile("quiet", 0))  # Bilinmeyen RAM ile efekt açılmaz.

    def test_broadcom_detection_is_an_allowlist_not_a_vendor_wide_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (vendor, device, kind) in enumerate([
                ("0x14e4", "0x4353", "0x028000"),
                ("0x14e4", "0x43ba", "0x028000"),
                ("0x8086", "0x4353", "0x028000"),
                ("0x14e4", "0x4353", "0x030000"),
            ]):
                dev = root / str(index)
                dev.mkdir()
                for name, value in (("vendor", vendor), ("device", device), ("class", kind)):
                    (dev / name).write_text(value + "\n")
            self.assertEqual(hardware.supported_broadcom(root), ["14e4:4353"])
            self.assertEqual(hardware.supported_broadcom(root / "absent"), [])

    def test_intel_legacy_detection_and_unbound_device_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, vendor, device, kind in (("old-wifi", "0x8086", "0x4220", "0x028000"), ("modern-wifi", "0x8086", "0x2723", "0x028000"), ("not-network", "0x8086", "0x4220", "0x040000")):
                path = root / name
                path.mkdir()
                for key, value in (("vendor", vendor), ("device", device), ("class", kind)):
                    (path / key).write_text(value)
            (root / "modern-wifi/driver").symlink_to(root / "drivers/iwlwifi")
            self.assertEqual(hardware.supported_intel_legacy(root), ["8086:4220"])
            text = hardware.driver_summary(root)
            self.assertIn("SÜRÜCÜ BAĞLI DEĞİL", text)
            self.assertIn("iwlwifi", text)
            self.assertNotIn("not-network", text)

    def test_missing_or_stalled_diagnostic_tools_do_not_crash(self):
        for error in (FileNotFoundError(), OSError(), subprocess.TimeoutExpired("lspci", 12)):
            with patch.object(hardware.subprocess, "run", side_effect=error):
                self.assertTrue(hardware.command_output(["/usr/bin/lspci"]))

    def test_report_runs_only_local_diagnostics(self):
        with patch.object(hardware, "command_output", return_value="aygıt") as run:
            text = hardware.report()
            self.assertIn("OğuzDows", text)
            self.assertIn("hiçbir yere gönderilmez", text)
            self.assertEqual([call.args[0][0] for call in run.call_args_list], ["/usr/bin/lspci", "/usr/bin/lsusb", "/usr/sbin/rfkill", "/usr/bin/dpkg-query", "/usr/bin/nmcli"])
            self.assertIn("sürücüsü durumu", text)

    def test_privileged_helper_rejects_unknown_action_before_doing_anything(self):
        with patch.object(sys, "argv", ["helper", "arbitrary-package"]), patch.object(helper.os, "open") as opened, patch.object(helper.subprocess, "run") as run, patch("sys.stderr", io.StringIO()):
            self.assertEqual(helper.main(), 2)
            opened.assert_not_called()
            run.assert_not_called()

    def test_privileged_helper_requires_root_and_matching_hardware(self):
        with patch.object(sys, "argv", ["helper", "broadcom"]), patch.object(helper.os, "geteuid", return_value=1000), patch.object(helper.subprocess, "run") as run, patch("sys.stderr", io.StringIO()):
            self.assertEqual(helper.main(), 1)
            run.assert_not_called()
        with patch.object(sys, "argv", ["helper", "broadcom"]), patch.object(helper.os, "geteuid", return_value=0), patch.object(helper, "supported_broadcom", return_value=[]), patch.object(helper.os, "open") as opened, patch.object(helper.subprocess, "run") as run, patch("sys.stderr", io.StringIO()):
            self.assertEqual(helper.main(), 1)
            opened.assert_not_called()
            run.assert_not_called()

    def test_privileged_install_uses_exact_kernel_headers_and_handles_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                logdir = root / "logs"
                real_open = helper.os.open
                def local_open(path, flags, mode=0o777):
                    if str(path) == "/run/lock/oguzdows-drivers.lock":
                        path = root / "drivers.lock"
                    self.assertTrue(Path(path).is_relative_to(root))
                    return real_open(path, flags, mode)
                error = subprocess.CalledProcessError(100, "apt-get") if fail else None
                with patch.object(sys, "argv", ["helper", "broadcom"]), \
                     patch.object(helper.os, "geteuid", return_value=0), \
                     patch.object(helper, "supported_broadcom", return_value=["14e4:4353"]), \
                     patch.object(helper, "Path", return_value=logdir), \
                     patch.object(helper.os, "open", side_effect=local_open), \
                     patch.object(helper.subprocess, "run", side_effect=error) as run, \
                     patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
                    self.assertEqual(helper.main(), 1 if fail else 0)
                    self.assertEqual(run.call_count, 1 if fail else 4)
                    if not fail:
                        install = run.call_args_list[2].args[0]
                        self.assertEqual(install[:4], ["/usr/bin/apt-get", "install", "-y", "--no-install-recommends"])
                        self.assertEqual(install[4:], ["dkms", "linux-headers-" + helper.os.uname().release, "broadcom-sta-dkms"])
                        self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))
                self.assertEqual((logdir / "drivers.log").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
