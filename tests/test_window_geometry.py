"""Native XShape assets and single-owner geometry, no display required here."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from support import ROOT, load
import desktop_material as material

renderer = load('window_geometry_assets_test', 'scripts/render-assets.py')
smoke = load('window_geometry_smoke_contract', 'tests/smoke-window-geometry.py')


class WindowGeometryTests(unittest.TestCase):
    def test_every_theme_has_complete_opaque_active_inactive_title_and_one_pixel_rails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in smoke.THEMES:
                renderer.window_theme(root, name, light=name != 'OguzDows' and not name.endswith('Dark'), xp='XP' in name)
                folder = root / 'usr/share/themes' / name / 'xfwm4'
                for mode in ('active', 'inactive'):
                    for part in ('title-1', 'title-2', 'title-3', 'title-4', 'title-5',
                                 'left', 'right', 'bottom', 'bottom-left', 'bottom-right'):
                        with self.subTest(theme=name, mode=mode, part=part), Image.open(folder / f'{part}-{mode}.png') as image:
                            self.assertEqual(image.getchannel('A').getextrema(), (255, 255), 'Xfwm includes ONLY alpha == 255 in its mask')
                            if not part.startswith('title-'):
                                self.assertEqual(image.size, (1, 1), 'No fake client padding to hide broken geometry')
                    for corner in ('top-left', 'top-right'):
                        with Image.open(folder / f'{corner}-{mode}.png') as image:
                            self.assertEqual(image.size, (10, 32))
                            self.assertEqual(image.getpixel((0 if corner == 'top-left' else 9, 0))[3], 0)
                            self.assertEqual(image.crop((0, 31, 10, 32)).getchannel('A').getextrema(), (255, 255))

    def test_generated_material_rekeys_old_cache_without_mutating_or_collecting_it(self):
        import os
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'XDG_DATA_HOME': temporary}):
            with patch.object(material, 'MARKER', 'oguzdows-generated-material-v4\n'):
                old = material.install('#3187ac', False, renderer.window_theme)
            old_folder = Path(temporary) / 'themes' / old
            before = {str(path.relative_to(old_folder)): path.read_bytes() for path in old_folder.rglob('*') if path.is_file()}
            new = material.install('#3187ac', False, renderer.window_theme)
            self.assertNotEqual(old, new)
            self.assertEqual(before, {str(path.relative_to(old_folder)): path.read_bytes() for path in old_folder.rglob('*') if path.is_file()})
            self.assertTrue((Path(temporary) / 'themes' / new / 'xfwm4/themerc').is_file())

    def test_modern_picom_uses_real_corner_rules_not_ignored_legacy_exclusion(self):
        for name in ('full', 'full-snap', 'motion', 'snap'):
            source = (ROOT / 'system/usr/share/oguzdows/compositor' / (name + '.conf')).read_text()
            self.assertIn('rules = (', source)
            self.assertNotIn('rounded-corners-exclude =', source)
            for ignored in ('active-opacity =', 'inactive-opacity =', 'inactive-dim ='):
                self.assertNotIn(ignored, source)
            self.assertIn('corner-radius = 0;', source)
            self.assertIn("window_type != 'normal' || bounding_shaped || override_redirect || fullscreen || _GTK_FRAME_EXTENTS@:c", source)
            for state in ('VERT', 'HORZ'):
                self.assertIn('_NET_WM_STATE_MAXIMIZED_' + state, source)
            self.assertIn('use-damage = true;', source)
            self.assertIn('frame-opacity = 1.0;', source)

    def test_old_picom_excludes_all_native_shape_csd_and_popup_owners(self):
        paths = [ROOT / 'system/usr/share/oguzdows/picom.conf']
        paths += [ROOT / 'system/usr/share/oguzdows/compositor' / (name + '.conf')
                  for name in ('blur', 'blur-still', 'blur9', 'blur9-still', 'still')]
        for path in paths:
            with self.subTest(path=path):
                line = next(line for line in path.read_text().splitlines() if line.startswith('rounded-corners-exclude ='))
                for match in ("window_type != 'normal'", 'bounding_shaped', 'override_redirect',
                              '_GTK_FRAME_EXTENTS@:c', '_NET_WM_STATE_MAXIMIZED_VERT', '_NET_WM_STATE_MAXIMIZED_HORZ'):
                    self.assertIn(match, line)

    def test_application_priority_css_honors_all_square_geometry_states(self):
        source = (ROOT / 'system/usr/share/oguzdows/ui/modern.css').read_text()
        geometry = (ROOT / 'system/usr/share/oguzdows/ui/window-geometry.css').read_text()
        for state in ('maximized', 'fullscreen', 'solid-csd', 'tiled', 'tiled-left', 'tiled-right', 'tiled-top', 'tiled-bottom'):
            self.assertIn('.oguzdows-modern.' + state + ' decoration', source)
            self.assertIn('.oguzdows-modern.' + state + ' headerbar', source)
            self.assertIn('.' + state + ' decoration', geometry)
        self.assertIn('margin: 6px;', geometry)
        self.assertIn('border-radius: 0; box-shadow: none; margin: 0;', geometry)
        for path in (ROOT / '.github/workflows/main.yml', ROOT / '.github/workflows/raspberrypi.yml'):
            self.assertIn('python3 tests/smoke-window-geometry.py', path.read_text())

    def test_installed_picom_version_accepts_major_only_and_package_suffixes(self):
        for version, major in (('v9.1', 9), ('v10', 10), ('v12.5', 12),
                               ('v12.5-dirty', 12), ('picom v12.5+git123', 12)):
            with self.subTest(version=version):
                self.assertEqual(smoke.picom_major(version), major)
        for version in ('', 'unknown', 'libGL 3.2 (picom unknown)'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                smoke.picom_major(version)

    def test_exact_mask_union_detects_one_pixel_holes_and_overlaps(self):
        for intervals, start, end, expected in (([(0, 4), (4, 10)], 0, 10, True),
                                                ([(0, 4), (5, 10)], 0, 10, False),
                                                ([(0, 4), (3, 10), (20, 30)], 0, 10, True),
                                                ([(5, 10)], 0, 10, False),
                                                ([(0, 9)], 0, 10, False), ([], 0, 10, False),
                                                ([(0, 10)], 3, 8, True), ([], 0, 0, True)):
            self.assertIs(smoke.coverage(intervals, start, end), expected)


if __name__ == '__main__':
    unittest.main()
