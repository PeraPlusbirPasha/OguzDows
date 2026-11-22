import ast
import json
import unittest
import xml.etree.ElementTree as ET

import yaml

from support import ROOT


class ContractsTests(unittest.TestCase):
    def test_xml_json_and_installer_yaml_are_valid(self):
        for directory in ("system", "assets"):
            for path in (ROOT / directory).rglob("*"):
                if path.suffix in (".xml", ".svg", ".policy", ".menu"):
                    with self.subTest(path=path):
                        ET.parse(path)
                elif path.suffix == ".json":
                    json.loads(path.read_text())
        for path in (ROOT / "installer").rglob("*"):
            if path.suffix in (".conf", ".desc"):
                with self.subTest(path=path):
                    self.assertIsInstance(yaml.safe_load(path.read_text()), dict)

    def test_user_facing_product_files_are_branded(self):
        for directory in ("system", "installer", "boot", "assets"):
            for path in (ROOT / directory).rglob("*"):
                if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".png", ".jpg", ".wav"}:
                    continue
                text = path.read_text().replace('DEBIAN_FRONTEND', 'PACKAGE_FRONTEND').lower()
                # İmzalı APT Origin alanı ve açık depo kökeni teknik gerçektir;
                # bunları markalamak imza / taban sürümü denetimini bozar.
                provenance = {'system/usr/lib/oguzdows/maintenance.py', 'system/usr/lib/oguzdows/updater.py'}
                technical = str(path.relative_to(ROOT)) in provenance or '/usr/share/doc/oguzdows/' in str(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    if not technical:
                        self.assertNotIn('debian', text)
                    self.assertNotIn("whitesur", text)
                    # Kullanıcı açıkça macOS esintili düzen istedi. Ürün kimliği
                    # macOS olamaz; dürüst esinti / kurulmaz açıklaması olabilir.
                    if 'macos' in text:
                        self.assertIn('xfce', text)
                        self.assertTrue('esinti' in text or 'kurulmaz' in text)

    def test_live_admin_account_is_bounded_to_live_boot(self):
        unit = (ROOT / "system/etc/systemd/system/oguzdows-live-setup.service").read_text()
        script = (ROOT / "system/usr/lib/oguzdows/live-setup.sh").read_text()
        self.assertIn("ConditionKernelCommandLine=boot=live", unit)
        self.assertLess(script.index("*' boot=live '*"), script.index("useradd"))
        cleanup = (ROOT / "system/usr/lib/oguzdows/finish-install.sh").read_text()
        for name in ("oguzdows-live-setup.service", "/etc/sudoers.d/oguzdows-live", "99-oguzdows-live.conf", "oguzdows-install.desktop"):
            self.assertIn(name, cleanup)
        self.assertNotIn("rm -rf", cleanup)
        self.assertNotIn("NOPASSWD", (ROOT / "installer/modules/users.conf").read_text())

    def test_install_sequence_cleans_live_user_before_creating_real_user(self):
        settings = yaml.safe_load((ROOT / "installer/settings.conf").read_text())
        sequence = settings["sequence"][1]["exec"]
        self.assertLess(sequence.index("unpackfs"), sequence.index("removeuser"))
        self.assertLess(sequence.index("removeuser"), sequence.index("users"))
        self.assertLess(sequence.index("shellprocess@cleanup"), sequence.index("users"))
        self.assertLess(sequence.index("grubcfg"), sequence.index("bootloader"))
        self.assertLess(sequence.index("initramfscfg"), sequence.index("initramfs"))
        self.assertLess(sequence.index("initramfs"), sequence.index("bootloader"))
        self.assertEqual(sequence[-2:], ["umount", "oguzdowsresult@result-complete"])
        cleanup = yaml.safe_load((ROOT / "installer/modules/cleanup.conf").read_text())
        self.assertFalse(cleanup["dontChroot"])
        users = yaml.safe_load((ROOT / "installer/modules/users.conf").read_text())
        self.assertFalse(users["doAutologin"])
        self.assertFalse(users["setRootPassword"])
        partition = yaml.safe_load((ROOT / "installer/modules/partition.conf").read_text())
        self.assertEqual(partition["initialPartitioningChoice"], "none")

    def test_installer_keeps_its_result_page_visible_without_automatic_reboot(self):
        settings = yaml.safe_load((ROOT / "installer/settings.conf").read_text())
        self.assertFalse(settings["quit-at-end"])
        self.assertEqual(settings["sequence"][-1], {"show": ["finished"]})
        finished = yaml.safe_load((ROOT / "installer/modules/finished.conf").read_text())
        self.assertEqual(finished["restartNowMode"], "user-unchecked")

    def test_no_silent_network_theme_download_or_global_driver_blacklist(self):
        for path in (ROOT / "hooks").iterdir():
            text = path.read_text()
            self.assertNotIn("git clone", text)
            self.assertNotIn("curl ", text)
            self.assertNotIn("apt-get", text)
        for path in (ROOT / "system").rglob("*"):
            if path.is_file() and path.suffix not in {".pyc", ".png", ".jpg", ".wav"}:
                text = path.read_text()
                self.assertNotIn("blacklist brcmfmac", text)
                self.assertNotIn("blacklist b43", text)

    def test_privileged_actions_require_explicit_admin_authentication(self):
        for path in (ROOT / "system/usr/share/polkit-1/actions").glob("*.policy"):
            tree = ET.parse(path)
            self.assertEqual(tree.findtext(".//allow_active"), "auth_admin")
            self.assertEqual(tree.findtext(".//allow_any"), "no")
            self.assertEqual(tree.findtext(".//allow_inactive"), "no")
            executable = tree.find(".//annotate[@key='org.freedesktop.policykit.exec.path']").text
            self.assertTrue((ROOT / "system" / executable.lstrip("/")).is_file())
        for path in list((ROOT / "system/usr/lib/oguzdows").glob("*.py")) + [ROOT / "system/usr/local/sbin/oguzdows-driver-helper"]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "shell":
                            self.assertIsNot(getattr(keyword.value, "value", None), True)

    def test_plymouth_uses_real_progress_and_keeps_password_prompts(self):
        script = (ROOT / "boot/oguzdows.script").read_text()
        for callback in ("SetBootProgressFunction", "SetRefreshFunction", "SetDisplayPasswordFunction", "SetDisplayQuestionFunction", "SetDisplayNormalFunction"):
            self.assertIn(callback, script)
        refresh = script.split("fun refresh_callback()", 1)[1].split("Plymouth.SetRefreshFunction", 1)[0]
        self.assertNotIn("Scale(", refresh)
        self.assertNotIn("Image(", refresh)
        self.assertNotIn("progress = 20", script)
        self.assertIn("global.last_progress", script)

    def test_firefox_homepage_is_local_and_user_changeable(self):
        policies = json.loads((ROOT / "system/usr/lib/firefox-esr/distribution/policies.json").read_text())["policies"]
        url = policies["Homepage"]["URL"]
        self.assertTrue(url.startswith("file:///usr/share/oguzdows/"))
        self.assertTrue((ROOT / "system" / url.removeprefix("file:///")).is_file())
        self.assertFalse(policies["Homepage"]["Locked"])
        self.assertTrue(policies["DisableTelemetry"])

    def test_application_menu_and_login_session_use_product_identity(self):
        menu_path = ROOT / "system/etc/xdg/menus/oguzdows-applications.menu"
        menu = ET.parse(menu_path)
        self.assertEqual(menu.findtext("Name"), "OğuzDows")
        self.assertIsNone(menu.find("DefaultMergeDirs"))
        for entry in menu.findall(".//Directory"):
            self.assertTrue((ROOT / "system/usr/share/desktop-directories" / entry.text).is_file())
        rc = (ROOT / "system/etc/skel/.config/xfce4/panel/whiskermenu-1.rc").read_text()
        self.assertIn("button-title=Başlat", rc)
        self.assertIn("button-icon=oguzdows", rc)
        self.assertIn("custom-menu-file=/etc/xdg/menus/oguzdows-applications.menu", rc)
        live = (ROOT / "system/usr/lib/oguzdows/live-setup.sh").read_text()
        self.assertIn("usermod -c 'OğuzDows Canlı Oturum' oguz", live)
        self.assertIn("user-session=oguzdows", live)
        self.assertTrue((ROOT / "system/usr/share/xsessions/oguzdows.desktop").is_file())

    def test_safe_install_preserves_only_compatibility_flags_without_overwriting_crypto_args(self):
        cleanup = (ROOT / "system/usr/lib/oguzdows/finish-install.sh").read_text()
        self.assertIn("60-oguzdows-compat.cfg", cleanup)
        self.assertIn('${GRUB_CMDLINE_LINUX_DEFAULT}%s plymouth.enable=0', cleanup)
        self.assertIn("COMPAT_ARGS=' nomodeset'", cleanup)
        self.assertNotIn("GRUB_CMDLINE_LINUX_DEFAULT", (ROOT / "system/etc/default/grub.d/50-oguzdows.cfg").read_text())

    def test_titlebars_panel_and_notifications_do_not_fade(self):
        base = ROOT / "system/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml"
        for name, keys in (("xfwm4", ("inactive_opacity", "frame_opacity", "popup_opacity", "move_opacity", "resize_opacity")), ("xfce4-panel", ("enter-opacity", "leave-opacity"))):
            tree = ET.parse(base / (name + ".xml"))
            for key in keys:
                self.assertEqual(tree.find(f".//property[@name='{key}']").get("value"), "100")
        tree = ET.parse(base / "xfce4-notifyd.xml")
        self.assertEqual(tree.find("property[@name='initial-opacity']").get("value"), "1.0")
        self.assertEqual(tree.find("property[@name='do-fadeout']").get("value"), "false")
        css = (ROOT / "system/usr/share/themes/OguzDows/gtk-3.0/gtk.css").read_text()
        self.assertIn("button.titlebutton.close:backdrop", css)
        self.assertTrue((ROOT / "system/usr/share/themes/OguzDows/xfce-notify-4.0/gtk.css").is_file())

    def test_live_installer_uses_system_configuration_and_exposes_errors(self):
        script = (ROOT / "system/usr/local/sbin/oguzdows-installer").read_text()
        self.assertIn("/usr/bin/python3 -I /usr/lib/oguzdows/run-installer.py", script)
        runner = (ROOT / "system/usr/lib/oguzdows/run-installer.py").read_text()
        self.assertIn("['/usr/bin/calamares', '-D', '6']", runner)
        self.assertNotIn("--config /etc/calamares/settings.conf", script)
        self.assertIn("flock -n", script)
        self.assertIn("installer.log", script)
        self.assertIn("/usr/lib/oguzdows/install_launcher.py", (ROOT / "system/usr/local/bin/oguzdows-install").read_text())
        settings = yaml.safe_load((ROOT / "installer/settings.conf").read_text())
        sequence = settings["sequence"][1]["exec"]
        self.assertLess(sequence.index("oguzdowsdrivers@drivers"), sequence.index("initramfs"))
        self.assertLess(sequence.index("shellprocess@cleanup"), sequence.index("oguzdowsdrivers@drivers"))
        defaults = yaml.safe_load((ROOT / "installer/modules/selected-drivers.conf").read_text())
        self.assertEqual(defaults["actions"], [])
        workflow = yaml.safe_load((ROOT / ".github/workflows/main.yml").read_text())
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])

    def test_wallpaper_selection_is_not_reset_on_every_login(self):
        script = (ROOT / "system/usr/lib/oguzdows/session.sh").read_text()
        self.assertIn("wallpapers.py --initialize", script)
        self.assertNotIn("/last-image", script)
        self.assertTrue((ROOT / "system/usr/share/applications/oguzdows-wallpapers.desktop").is_file())

    def test_workflow_mirror_is_kept_in_sync(self):
        self.assertEqual((ROOT / "build.yml").read_text(), (ROOT / ".github/workflows/main.yml").read_text())


if __name__ == "__main__":
    unittest.main()
