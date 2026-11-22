import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from support import ROOT, load
from xfconf_fixture import Xfconf

model = load('welcome_v11_model', 'system/usr/lib/oguzdows/welcome_model.py')
profiles = load('welcome_v11_profiles', 'system/usr/lib/oguzdows/profiles.py')
assets = load('welcome_v11_assets', 'scripts/render-assets.py')
speech = load('welcome_v11_speech', 'system/usr/lib/oguzdows/rifki_speech.py')


class WelcomeModelTests(unittest.TestCase):
    def test_live_installed_and_pi_are_different_first_runs(self):
        live = model.context(live=True)
        installed = model.context()
        pi = model.context(live=True, pi=True)
        self.assertTrue(live.offers_installer)
        self.assertFalse(installed.offers_installer)
        self.assertFalse(pi.offers_installer)
        self.assertEqual(len({x.state_name for x in (live, installed, pi)}), 3)
        self.assertIn('Kurulum bitti', installed.subtitle)
        smoke = (ROOT / 'tests/smoke-iso-target.py').read_text()
        self.assertIn(installed.state_name, smoke)

    def test_bounded_previous_next_never_leaves_install_result(self):
        self.assertEqual(model.PAGE_IDS[0], 'welcome')
        self.assertIsNone(model.adjacent('welcome', -1))
        for index, name in enumerate(model.PAGE_IDS[1:], 1):
            self.assertEqual(model.adjacent(name, -1), model.PAGE_IDS[index - 1])
        self.assertIsNone(model.adjacent(model.PAGE_IDS[-1], 1))
        self.assertIsNone(model.adjacent('install-result', 1))
        with self.assertRaises(ValueError):
            model.adjacent('welcome', 10)
        for session in (model.context(), model.context(live=True), model.context(pi=True)):
            for page in model.PAGE_IDS:
                self.assertTrue(model.page_text(page, session))
        self.assertNotIn('üstten', model.page_text('welcome', model.context()))


class AppearanceTests(unittest.TestCase):
    def execute(self, command):
        return self.xfconf(command)

    def setUp(self):
        self.xfconf = Xfconf(profiles.settings('oguzdows'))
        self.calls = self.xfconf.calls

    def test_oguzdows_is_original_xp_inspired_bottom_panel(self):
        settings = {(channel, key): value for channel, key, _type, value in profiles.settings('oguzdows')}
        self.assertEqual(settings['xfce4-panel', '/panels/panel-1/position'], 'p=10;x=0;y=0')
        self.assertEqual(settings['xfce4-panel', '/plugins/plugin-1/button-title'], 'Başlat')
        self.assertEqual(settings['xsettings', '/Net/ThemeName'], 'OguzDowsXP')
        self.assertEqual(settings['xfwm4', '/general/theme'], 'OguzDowsXP')
        self.assertEqual(profiles.theme('oguzdows', 'dark'), 'OguzDowsXPDark')
        self.assertEqual(profiles.theme('gnome', 'light'), 'OguzDowsGnome')
        for value in ('', 'auto', '../OguzDows'):
            with self.assertRaises(ValueError):
                profiles.settings('oguzdows', value)

    def test_theme_only_changes_three_theme_keys_not_layout_or_cursor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.set_appearance('dark', root, self.execute)
            mutations = [call for call in self.calls if len(call) != 5]
            self.assertEqual(len(mutations), 3)
            self.assertEqual({call[4] for call in mutations}, {'/Net/ThemeName', '/Gtk/ApplicationPreferDarkTheme', '/general/theme'})
            self.assertEqual(profiles.selection(root), ('oguzdows', 'dark'))
            self.assertEqual(stat.S_IMODE((root / 'before-first-change.json').stat().st_mode), 0o600)
            self.calls.clear()
            profiles.apply('mac', root, self.execute)
            self.assertEqual(profiles.selection(root), ('mac', 'dark'))
            self.assertIn('OguzDowsMacDark', [call[-1] for call in self.calls])
            backup = json.loads((root / 'before-first-change.json').read_text())
            self.assertEqual(len(backup), len(profiles.settings('oguzdows')))
            profiles.restore(root, self.execute)
            self.assertFalse((root / 'appearance').exists())
            self.assertFalse((root / 'selected').exists())

    def test_failed_metadata_write_restores_settings_and_previous_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('xfce', root, self.execute)
            self.calls.clear()
            before = dict(self.xfconf.values)
            original = profiles.atomic_text
            def fail(path, text):
                if text == 'dark\n':
                    raise OSError('Disk dolu')
                original(path, text)
            with patch.object(profiles, 'atomic_text', side_effect=fail):
                with self.assertRaises(OSError):
                    profiles.set_appearance('dark', root, self.execute)
            self.assertEqual(profiles.selection(root), ('xfce', 'light'))
            self.assertEqual(self.xfconf.values, before)

    def test_all_eight_generated_decorations_have_opaque_visible_close_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name, light, xp in (('OguzDows', False, False), ('OguzDowsLight', True, False),
                                    ('OguzDowsXP', True, True), ('OguzDowsXPDark', False, True),
                                    ('OguzDowsMac', True, False), ('OguzDowsMacDark', False, False),
                                    ('OguzDowsGnome', True, False), ('OguzDowsGnomeDark', False, False)):
                root = Path(temporary)
                assets.window_theme(root, name, light, xp)
                theme = root / 'usr/share/themes' / name
                self.assertTrue((ROOT / 'system/usr/share/themes' / name / 'index.theme').is_file())
                for state in ('active', 'inactive', 'pressed', 'prelight'):
                    with Image.open(theme / 'xfwm4' / ('close-' + state + '.png')) as image:
                        self.assertEqual(image.getchannel('A').getextrema(), (255, 255))
                        self.assertGreater(len(set(image.getdata())), 3)
                self.assertIn('active_text_color=', (theme / 'xfwm4/themerc').read_text())


class SpeechCacheTests(unittest.TestCase):
    def test_manifest_cached_once_and_untrusted_shapes_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / 'speech.json'
            for value in ([], 'wrong', 1):
                manifest.write_text(json.dumps(value))
                self.assertEqual(speech.load_manifest(root), {})
            manifest.write_text(' ' * 65537)
            self.assertEqual(speech.load_manifest(root), {})
            manifest.write_text('{}')
            with patch.object(speech, 'load_manifest', wraps=speech.load_manifest) as read:
                with patch.dict('os.environ', {'XDG_CONFIG_HOME': str(root / 'config')}):
                    speaker = speech.Speaker(lambda *args: None, assets=root)
                    speaker.speak('unknown')
                    speaker.speak('another')
                    self.assertEqual(read.call_count, 1)
                    speaker.close()


if __name__ == '__main__':
    unittest.main()
