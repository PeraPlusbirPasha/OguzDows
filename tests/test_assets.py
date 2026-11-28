import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from support import ROOT, load

renderer = load("oguzdows_assets", "scripts/render-assets.py")


class AssetTests(unittest.TestCase):
    def test_all_theme_assets_render_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            renderer.render(root)
            wallpaper = root / "usr/share/backgrounds/oguzdows/wallpaper.png"
            bios = root / "usr/share/oguzdows/brand/boot-bios.png"
            efi = root / "usr/share/oguzdows/brand/boot-efi.png"
            for path, expected in ((wallpaper, (1920, 1080)), (bios, (640, 480)), (efi, (800, 600))):
                with Image.open(path) as image:
                    self.assertEqual(image.size, expected)
            for name in re.findall(r'Image\("([^"/]+\.png)"\)', (ROOT / "boot/oguzdows.script").read_text()):
                self.assertTrue((root / "usr/share/plymouth/themes/oguzdows" / name).is_file(), name)
            self.assertTrue((root / "usr/share/calamares/branding/oguzdows/logo.png").is_file())
            self.assertTrue((root / "usr/share/calamares/branding/oguzdows/welcome.png").is_file())
            for name in ("battery-missing-symbolic", "ac-adapter-symbolic"):
                with Image.open(root / f"usr/share/icons/OguzDows/24x24/status/{name}.png") as fallback:
                    self.assertEqual(fallback.size, (24, 24))
                    self.assertNotEqual(fallback.tobytes(), renderer.nazar(0, 24).tobytes())
            theme = root / "usr/share/themes/OguzDows/xfwm4"
            for part in ("title-1", "title-5", "left", "right", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"):
                for state in ("active", "inactive"):
                    self.assertTrue((theme / f"{part}-{state}.png").is_file())
            for button in ("close", "hide", "maximize", "maximize-toggled", "menu"):
                for state in ("active", "inactive", "prelight", "pressed"):
                    self.assertTrue((theme / f"{button}-{state}.png").is_file())
            manifest = json.loads((root / "usr/share/oguzdows/wallpapers.json").read_text())
            self.assertTrue({'bogaz-sabahi', 'kackar-sisi', 'kapadokya-isigi', 'oludeniz-kiyisi', 'tuz-golu-aksami', 'ani-kisi', 'halay', 'cay-simit', 'istanbul-kedisi'} <= {item['id'] for item in manifest})
            self.assertEqual(len(manifest), 20)
            self.assertEqual(sum(item.get('origin') == 'AI-generated' for item in manifest), 16)
            self.assertEqual(sum(item.get('origin') == 'Original illustration' for item in manifest), 4)
            self.assertTrue(all(item.get('logo') == 'bottom-right' for item in manifest))
            for retired in ('istanbul', 'kapadokya', 'pamukkale', 'kackar', 'anadolu'):
                self.assertFalse((wallpaper.parent / (retired + '.png')).exists())
            pixels = set()
            for item in manifest:
                with Image.open(root / item["path"].lstrip("/")) as image:
                    self.assertEqual(image.size, (1920, 1080))
                    pixels.add(hashlib.sha256(image.tobytes()).hexdigest())
                with Image.open(root / item["preview"].lstrip("/")) as preview:
                    self.assertEqual(preview.size, (320, 180))
            self.assertEqual(len(pixels), 20)
            with Image.open(wallpaper) as default, Image.open(wallpaper.parent / 'bogaz-sabahi.jpg') as scenery:
                self.assertEqual(default.tobytes(), scenery.tobytes())
            for state in ("active", "inactive"):
                with Image.open(theme / f"close-{state}.png") as close:
                    self.assertEqual(close.getchannel("A").getextrema(), (255, 255))
            for name in ('OguzDowsAero', 'OguzDowsAeroDark', 'OguzDowsEleven', 'OguzDowsElevenDark'):
                for part in ('title-1-active', 'close-active', 'close-inactive'):
                    with Image.open(root / f'usr/share/themes/{name}/xfwm4/{part}.png') as image:
                        if part.startswith('title-'):
                            self.assertEqual(image.crop((0, 1, image.width, image.height)).getchannel('A').getextrema(), (255, 255))
                            self.assertEqual(image.getpixel((0, 0))[3], 255)  # Xfwm mask requires exact opacity
                        else:
                            self.assertEqual(image.getchannel('A').getextrema(), (255, 255))
            original = bios.read_bytes()
            renderer.render(root)
            self.assertEqual(bios.read_bytes(), original)

    def test_nazar_reveals_monotonically_and_keeps_charging_distinct(self):
        blue_counts = []
        for percentage in range(0, 101, 10):
            image = renderer.nazar(percentage)
            blue_counts.append(sum(b > 110 and b > r * 1.5 and a > 100 for r, g, b, a in image.getdata()))
        self.assertEqual(blue_counts, sorted(blue_counts))
        self.assertGreater(blue_counts[-1], blue_counts[0])
        self.assertNotEqual(renderer.nazar(50).tobytes(), renderer.nazar(50, charging=True).tobytes())
        self.assertEqual(renderer.nazar(100).getpixel((0, 0))[3], 0)

    def test_mark_has_transparent_background_and_native_small_icons(self):
        mark = renderer.emblem(128)
        self.assertEqual(mark.size, (128, 128))
        self.assertEqual(mark.getpixel((0, 0))[3], 0)
        self.assertEqual(renderer.emblem(24, tile=True).size, (24, 24))
        self.assertGreater(renderer.text_image("OğuzDows · İstanbul", 20, "white").width, 100)


if __name__ == "__main__":
    unittest.main()
