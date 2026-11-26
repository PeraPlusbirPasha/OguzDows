"""Özgün SVG / çevrimdışı cam materyal / PC-Pi-ARM ortak kaynak taşıması."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT, load
import desktop_material as material

renderer = load('desktop_assets_renderer_test', 'scripts/render-assets.py')
installer = load('desktop_assets_install_test', 'scripts/install-desktop-assets.py')


class NativeAssetTests(unittest.TestCase):
    def test_svg_icons_are_original_scalable_offline_data_not_external_or_scripts(self):
        root = ROOT / 'system/usr/share/icons/hicolor/scalable'
        files = sorted(root.glob('*/*.svg'))
        self.assertEqual(len(files), 26)
        self.assertEqual(len(list((root / 'apps').glob('*.svg'))), 19)
        for path in files:
            with self.subTest(path=path.name):
                self.assertLess(path.stat().st_size, 12000)
                source = path.read_text(); svg = ET.fromstring(source)
                self.assertIn('viewBox', svg.attrib)
                self.assertNotIn('<script', source); self.assertNotIn('<foreignObject', source)
                self.assertNotIn('href=', source); self.assertNotIn('http://', source.replace('http://www.w3.org/2000/svg', ''))
        self.assertNotEqual((root / 'apps/oguzdows-hub.svg').read_bytes(), (root / 'apps/oguzdows-store.svg').read_bytes())

    def test_glass_xfwm_edges_have_real_alpha_but_title_text_and_all_controls_remain_opaque(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for dark in (False, True):
                name = 'OguzDowsAeroGlassDark' if dark else 'OguzDowsAeroGlass'
                renderer.window_theme(root, name, light=not dark, accent='#aa6688')
                directory = root / 'usr/share/themes' / name / 'xfwm4'
                with Image.open(directory / 'title-3-active.png') as image:
                    self.assertLess(image.getchannel('A').getextrema()[0], 255)
                    self.assertEqual(image.crop((0, 4, image.width, 28)).getchannel('A').getextrema(), (255, 255))
                for action in ('close', 'hide', 'maximize', 'menu'):
                    for mode in ('active', 'inactive', 'prelight', 'pressed'):
                        with Image.open(directory / (action + '-' + mode + '.png')) as image:
                            self.assertEqual(image.getchannel('A').getextrema(), (255, 255))

    def test_tinted_material_is_cached_and_old_private_theme_does_not_escape_user_data(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'XDG_DATA_HOME': temporary}):
            render = Mock(wraps=renderer.window_theme)
            name = material.install('#36b6c5', False, render)
            self.assertTrue(name.startswith(material.PREFIX)); self.assertEqual(render.call_count, 1)
            self.assertEqual(material.install('#36b6c5', False, render), name); self.assertEqual(render.call_count, 1)
            root = Path(temporary) / 'themes' / name
            self.assertIn('#36b6c5', (root / 'gtk-3.0/gtk.css').read_text())
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / '.oguzdows-owned').read_text(), material.MARKER)
            self.assertTrue((root / 'xfwm4/close-active.png').is_file())
            for color in ('x', '#abc', '#fff;exec(x)'):
                with self.assertRaises(ValueError): material.install(color, False, render)

    def test_optional_feedback_is_short_mono_and_generated_without_remote_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); renderer.render_desktop_assets(root)
            with wave.open(str(root / 'usr/share/oguzdows/ui/confirm.wav'), 'rb') as sound:
                self.assertEqual(sound.getnchannels(), 1); self.assertEqual(sound.getframerate(), 16000)
                self.assertLessEqual(sound.getnframes(), 1600); self.assertGreater(sound.getnframes(), 1000)
            self.assertEqual(len(list((root / 'usr/share/icons/hicolor/scalable/apps').glob('*.svg'))), 19)
            for name in ('modern.css', 'window-geometry.css', 'shell.css'):
                self.assertEqual((root / 'usr/share/oguzdows/ui' / name).read_bytes(),
                                 (ROOT / 'system/usr/share/oguzdows/ui' / name).read_bytes())

    def test_editorial_art_and_layout_previews_are_offline_distinct_bounded_rasters(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); renderer.render_editorial_assets(root)
            folder = root / 'usr/share/oguzdows/ui'
            expected = ['news-cover-' + str(index) for index in range(6)]
            expected += ['store-create', 'store-media', 'store-work']
            expected += ['layout-' + key for key in ('oguzdows', 'kde', 'gnome', 'xfce', 'windows11', 'mac')]
            blobs = set()
            for name in expected:
                path = folder / (name + '.png')
                with Image.open(path) as image:
                    self.assertLessEqual(image.width, 640); self.assertLessEqual(image.height, 360)
                    self.assertIn(image.mode, ('RGB', 'RGBA'))
                self.assertLess(path.stat().st_size, 256 * 1024); blobs.add(path.read_bytes())
            self.assertEqual(len(blobs), len(expected))
        source = (ROOT / 'system/usr/lib/oguzdows/welcome.py').read_text()
        preview = source[source.index('    def style_preview('):source.index('    def styles_page(')]
        self.assertIn("'layout-' + identifier", preview)
        self.assertNotIn('Gtk.DrawingArea', preview)
        self.assertNotIn('●', preview)

    def test_build_time_installer_chooses_real_gnome_js_abi_without_enabling_extension(self):
        import shutil
        for suite, modern in (('bookworm', False), ('trixie', True)):
            with self.subTest(suite=suite), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                shutil.copytree(ROOT / 'system/usr/share/oguzdows/gnome', root / 'usr/share/oguzdows/gnome')
                installer.install(root, suite)
                target = root / 'usr/share/gnome-shell/extensions' / installer.UUID
                data = json.loads((target / 'metadata.json').read_text()); script = (target / 'extension.js').read_text()
                self.assertEqual(data['shell-version'], ['45', '46', '47', '48'] if modern else ['43', '44'])
                self.assertEqual('export default class' in script, modern)
                self.assertEqual("imports.gi" in script, not modern)
                self.assertNotIn('// @OGUZDOWS_CORE@', script)
                self.assertFalse((root / 'home').exists())
                self.assertTrue((target / 'reflection.svg').is_file())

    def test_gui_smoke_refuses_real_home_non_ci_and_root_child_before_any_gui(self):
        script = ROOT / 'tests/smoke-desktop.py'
        for env, args in (({**os.environ, 'CI': 'false'}, ['--output', '/should-not-write']),
                          ({**os.environ, 'CI': 'true', 'HOME': '/home/a-real-user'}, ['--child', '/home/a-real-user'])):
            result = subprocess.run([sys.executable, str(script), '--binaries', '/does-not-exist', *args],
                                    capture_output=True, text=True, timeout=8, check=False, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('No module named', result.stderr)

    def test_polish_smoke_refuses_real_user_home_and_tests_real_apps_not_only_own_css(self):
        script = ROOT / 'tests/smoke-desktop-polish.py'
        for env, args in (({**os.environ, 'CI': 'false'}, ['--output', '/should-not-write']),
                          ({**os.environ, 'CI': 'true'}, ['--adwaita-probe', '/home/a-real-user'])):
            result = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                                    timeout=8, check=False, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('No module named', result.stderr)
        source = script.read_text()
        for marker in ('Adw.StyleManager.get_default()', "GSETTINGS_BACKEND='dconf'", "key('Print')", 'xfsettingsd', 'thunar', "'--toggle'"):
            self.assertIn(marker, source)
        workflow = (ROOT / '.github/workflows/main.yml').read_text()
        self.assertIn('tests/smoke-desktop-polish.py', workflow)
        self.assertIn('gir1.2-adw-1', workflow)

    def test_wrappers_and_recipes_build_on_target_and_no_foreign_abi_binary_is_committed(self):
        for component in ('hub', 'monitor'):
            wrapper = ROOT / 'system/usr/local/bin' / ('oguzdows-' + component)
            self.assertIn('exec /usr/lib/oguzdows/oguzdows-' + component + '-native "$@"', wrapper.read_text())
            self.assertTrue(wrapper.stat().st_mode & 0o111)
            self.assertFalse((ROOT / 'system/usr/lib/oguzdows' / ('oguzdows-' + component + '-native')).exists())
        for script in ('configure.py', 'configure-pi.py', 'configure-arm.py'):
            source = (ROOT / 'scripts' / script).read_text()
            self.assertIn('install_desktop_assets(', source); self.assertIn('build-desktop.sh', source)
        for hook in ('hooks/0280-native-store.hook.chroot', 'raspberrypi/stage/00-desktop/files/configure-system.sh'):
            source = (ROOT / hook).read_text()
            self.assertIn('for component in monitor hub', source); self.assertIn('build-desktop.sh', source)
        workflow = (ROOT / '.github/workflows/desktop.yml').read_text()
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('gh release', workflow)


if __name__ == '__main__':
    unittest.main()
