"""Özgün ikonların bayrak / tek kare olmaması ve tüm tariflere taşınması."""
import configparser
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from support import ROOT, load

assets = load('own_icons_assets', 'scripts/render-assets.py')
profiles = load('own_icons_profiles', 'system/usr/lib/oguzdows/profiles.py')


class OwnIconTests(unittest.TestCase):
    def test_all_own_launchers_use_their_own_declared_icon_not_the_product_flag(self):
        manifest = json.loads((ROOT / 'system/usr/share/oguzdows/own-app-icons.json').read_text())
        self.assertEqual(len(manifest['icons']), 15)
        for identifier in manifest['icons']:
            config = configparser.ConfigParser(interpolation=None)
            config.read(ROOT / f'system/usr/share/applications/oguzdows-{identifier}.desktop')
            self.assertEqual(config['Desktop Entry']['Icon'], 'oguzdows-' + identifier)
        self.assertIn('oguzdows', (ROOT / 'system/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml').read_text())
        self.assertTrue((ROOT / 'assets/oguzdows.svg').is_file(), 'Ürün / boot markası korunmalı')

    def test_every_size_is_nonempty_unique_transparent_at_corners_and_offline(self):
        manifest = json.loads((ROOT / 'system/usr/share/oguzdows/own-app-icons.json').read_text())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets.render_own_app_icons(root)
            for size in manifest['sizes']:
                hashes = set()
                for identifier in manifest['icons']:
                    path = root / f'usr/share/icons/hicolor/{size}x{size}/apps/oguzdows-{identifier}.png'
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (size, size))
                        alpha = image.getchannel('A')
                        self.assertEqual(alpha.getpixel((0, 0)), 0)
                        self.assertEqual(alpha.getpixel((size - 1, size - 1)), 0)
                        self.assertGreater(alpha.getextrema()[1], 240)
                        opaque = sum(value > 240 for value in alpha.getdata())
                        self.assertLess(opaque, size * size * .68, identifier)
                        self.assertGreater(opaque, size * size * .10, identifier)
                        self.assertGreater(len(set(image.getdata())), 3)
                    hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(len(hashes), len(manifest['icons']))

    def test_windows11_center_cluster_contains_neither_tray_clock_nor_expanding_spacer(self):
        values = {key: value for _ch, key, _kind, value in profiles.settings('windows11')}
        self.assertEqual(values['/panels'], ['1'])
        self.assertEqual(values['/panels/panel-1/position'], 'p=10;x=0;y=0')
        self.assertEqual(values['/panels/panel-1/length'], '100')
        self.assertEqual(values['/panels/panel-1/plugin-ids'], ['95', '3', '4', '5', '6', '7'])
        self.assertEqual(values['/plugins/plugin-95'], 'oguzdows-tasks')
        self.assertEqual(values['/plugins/plugin-95/style'], 'windows11')
        self.assertEqual(values['/plugins/plugin-3/expand'], 'false')
        self.assertIsNone(values['/panels/panel-90/position'])
        self.assertGreater(float(values['/panels/panel-1/background-rgba'][0]), .9)
        dark = {key: value for _ch, key, _kind, value in profiles.settings('windows11', appearance='dark')}
        self.assertLess(float(dark['/panels/panel-1/background-rgba'][0]), .2)

    def test_mac_and_ubuntu_docks_shrink_to_contents_not_a_large_fixed_blank_strip(self):
        for identifier in ('mac', 'gnome'):
            values = {key: value for _ch, key, _kind, value in profiles.settings(identifier)}
            self.assertEqual(values['/panels/panel-90/length'], '1')
            self.assertEqual(values['/panels/panel-90/length-adjust'], 'true')
            self.assertNotIn('3', values['/panels/panel-90/plugin-ids'])
            self.assertEqual(values['/panels/panel-90/icon-size'], '36')
        for appearance, expected in (('light', 'OguzDowsMac'), ('dark', 'OguzDowsMacDark')):
            for eligible in (False, True):
                values = {key: value for _ch, key, _kind, value in profiles.settings('mac', appearance, effects='aero', resources={'compositing': eligible})}
                self.assertEqual(values['/Net/ThemeName'], expected)
                self.assertEqual(values['/general/button_layout'], 'CHM|')
                self.assertEqual(values['/Gtk/EnableAnimations'], str(eligible).lower())


if __name__ == '__main__':
    unittest.main()
