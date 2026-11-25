"""Local image palettes, observed/manual races and transactional mode surfaces."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from support import ROOT, load
from xfconf_fixture import Xfconf
import accent
import desktop_material as material
import desktop_preferences as preferences
import desktop_runtime as runtime
import desktop_state as state
import profiles

renderer = load('mode_palette_renderer_test', 'scripts/render-assets.py')


class AccentFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config'),
            'XDG_STATE_HOME': str(self.root / 'state'), 'XDG_DATA_HOME': str(self.root / 'data'),
            'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11', 'DISPLAY': ':97'})
        environment.start(); self.addCleanup(environment.stop)

    def picture(self, name, color):
        path = self.root / name
        Image.new('RGB', (80, 60), color).save(path)
        return path


class AccentTests(AccentFixture):
    def test_distinct_images_drive_different_bounded_dominant_accents(self):
        colors = [accent.extract(self.picture(name + '.png', color)) for name, color in
                  (('forest', '#226e35'), ('sea', '#267ba4'), ('sunset', '#ce6533'))]
        self.assertEqual(len(set(colors)), 3)
        for color in colors:
            self.assertRegex(color, r'^#[a-f0-9]{6}$')
            self.assertLessEqual(max(int(color[i:i+2], 16) for i in (1, 3, 5)), 192)

    def test_extraction_cache_avoids_redecode_and_content_change_invalidates(self):
        path = self.picture('palette.png', '#a84f8c')
        expected = accent.extract(path)
        with patch('PIL.Image.open', side_effect=AssertionError('cached image decoded again')):
            self.assertEqual(accent.extract(path), expected)
        Image.new('RGB', (81, 60), '#317944').save(path)
        self.assertNotEqual(accent.extract(path), expected)
        self.assertEqual((state.state_directory() / 'wallpaper-palette.json').stat().st_mode & 0o777, 0o600)

    def test_untrusted_or_oversized_input_never_becomes_shell_or_css(self):
        for value in ('https://example.org/cover.png', '$(touch nope).png'):
            with self.assertRaises((OSError, ValueError)): accent.extract(value)
        svg = self.root / 'bad.svg'; svg.write_text('<svg/>')
        with self.assertRaises(ValueError): accent.extract(svg)
        fifo = self.root / 'pipe.png'; os.mkfifo(fifo)
        with self.assertRaises(ValueError): accent.extract(fifo)
        path = self.picture('small.png', '#394e95')
        with patch.object(accent, 'MAX_BYTES', 3), self.assertRaises(ValueError): accent.extract(path)
        with patch.object(accent, 'MAX_PIXELS', 3), self.assertRaises(ValueError): accent.extract(path)
        self.assertFalse((self.root / 'nope').exists())

    def test_external_xfce_property_reads_exact_changed_monitor_not_stale_catalogue(self):
        path = self.picture('external.png', '#3e8caa')
        prop = '/backdrop/screen0/monitorHDMI-2/workspace1/last-image'
        execute = Mock(return_value=subprocess.CompletedProcess([], 0, str(path) + '\n', ''))
        self.assertEqual(accent.current_wallpaper(prop, execute), path)
        self.assertEqual(execute.call_args.args[0][-1], prop)
        for invalid in ('/general/theme', prop + '\n', prop + '/other'):
            with self.assertRaises(ValueError): accent.current_wallpaper(invalid, execute)
        self.assertEqual(execute.call_count, 1)

    def test_startup_read_is_bounded_and_skips_missing_local_images(self):
        path = self.picture('startup.jpg', '#73569b')
        rows = ['/backdrop/screen0/monitor0/workspace0/last-image', '/backdrop/screen0/monitor0/workspace1/last-image']
        def execute(command):
            output = '\n'.join(rows) if command[-1] == '-l' else '/nonexistent.png' if command[-1] == rows[0] else str(path)
            return subprocess.CompletedProcess(command, 0, output + '\n', '')
        self.assertEqual(accent.current_wallpaper(execute=execute), path)

    def test_manual_source_prevents_sampling_and_does_not_start_observer(self):
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'theme'})
        with patch.object(runtime, 'normal_session'), patch.object(accent, 'extract') as extract:
            self.assertFalse(accent.sync()['changed'])
            extract.assert_not_called()
        accent.ensure_observer({**state.DEFAULTS, 'accent_source': 'theme'})  # no gi dependency when disabled

    def test_disable_race_is_rechecked_inside_shared_transaction(self):
        path = self.picture('race.png', '#e38c44')
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'theme', 'accent': '#112244'})
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'installation_busy', return_value=False), patch.object(preferences, 'apply_current') as apply:
            result = preferences.update_and_apply({'accent': '#aa4455'}, resources={'compositing': False}, observed_wallpaper=path)
        self.assertFalse(result['changed']); apply.assert_not_called()
        self.assertEqual(state.load()['accent'], '#112244')

    def test_explicit_restore_blocks_observer_and_pending_colour_race_until_new_preferences(self):
        path = self.picture('restored.png', '#8f6632')
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'revision': 8, 'accent': '#334488'})
        state.atomic_json(state.state_directory() / 'xfce-applied.json', {'revision': 8, 'restored': True})
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'installation_busy', return_value=False), patch.object(preferences, 'apply_current') as apply:
            result = preferences.update_and_apply({'accent': '#aa4455'}, {'compositing': False}, observed_wallpaper=path)
            self.assertFalse(result['changed']); apply.assert_not_called()
            with patch.object(accent, 'extract') as extract:
                self.assertFalse(accent.sync()['changed']); extract.assert_not_called()
        accent.ensure_observer(state.load())  # no GTK import / launch on restored revision
        self.assertEqual(state.load()['revision'], 8)

    def test_observed_wallpaper_never_reapplies_a_previous_gallery_id(self):
        path = self.picture('observed.png', '#9768b4')
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'wallpaper': 'an-old-gallery-id'})
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'installation_busy', return_value=False), patch.object(preferences, 'apply_current', return_value={'message': 'fixture', 'notes': []}) as apply, patch.object(preferences, 'wallpaper_entry', side_effect=AssertionError('stale catalogue used')), patch.object(accent, 'ensure_observer'):
            preferences.update_and_apply({'accent': '#123456'}, resources={'compositing': False}, observed_wallpaper=path)
        self.assertEqual(state.load()['accent'], accent.extract(path))
        self.assertFalse(apply.call_args.kwargs['wallpaper'])
        self.assertEqual(state.load()['wallpaper'], 'an-old-gallery-id')

    def test_neutral_image_has_safe_fallback_not_invalid_palette(self):
        self.assertRegex(accent.extract(self.picture('white.png', '#ffffff')), '#[a-f0-9]{6}')
        self.assertEqual(material.foreground('#ffffff'), '#11202f')
        self.assertEqual(material.foreground('#000000'), '#ffffff')

    def test_busy_installer_does_not_write_preferences_or_native_settings(self):
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'installation_busy', return_value=True), patch.object(preferences, 'apply_current') as apply:
            with self.assertRaisesRegex(RuntimeError, 'Kurucu'):
                preferences.update_and_apply({'accent_source': 'wallpaper'}, resources={'compositing': False})
        apply.assert_not_called(); self.assertFalse(state.config_path().exists())


class ModeSurfaceTests(AccentFixture):
    def test_win_and_mac_identity_survives_opaque_glass_and_dark_variants(self):
        for identifier in ('windows11', 'mac'):
            for dark in (False, True):
                for glass in (False, True):
                    name = material.install('#3187ac', dark, renderer.window_theme, identifier=identifier,
                                            glass=glass, base_theme=profiles.theme(identifier, 'dark' if dark else 'light'))
                    self.assertTrue(name.startswith('OguzDowsMac' if identifier == 'mac' else 'OguzDowsEleven'))
                    directory = self.root / 'data/themes' / name
                    css = (directory / 'gtk-3.0/gtk.css').read_text()
                    for selector in ('treeview:selected', '.view:selected', 'button.suggested-action', 'entry:focus', 'scale highlight', 'oguzdows_glass_tint'):
                        self.assertIn(selector, css)
                    with Image.open(directory / 'xfwm4/title-3-active.png') as image:
                        self.assertEqual(image.crop((0, 4, image.width, 28)).getchannel('A').getextrema(), (255, 255))
                    with Image.open(directory / 'xfwm4/top-left-active.png') as image:
                        self.assertEqual(image.getpixel((0, 0))[3], 0)
                        self.assertEqual(image.size, (10, 32))
                    with Image.open(directory / 'xfwm4/close-active.png') as image:
                        self.assertEqual(image.width, 26 if identifier == 'mac' else 44)
                        self.assertEqual(image.getchannel('A').getextrema(), (255, 255))

    def test_accent_updates_active_frame_and_all_surface_targets_without_panel_relayout(self):
        for identifier in ('windows11', 'mac'):
            backend = Xfconf(profiles.settings('oguzdows'))
            directory = self.root / ('profiles-' + identifier)
            profiles.apply(identifier, directory, backend)
            before = {key: value for key, value in backend.values.items() if key[1].endswith(('plugin-ids', '/position')) or key[1] == '/panels'}
            for glass in (False, True):
                preferences = {**state.DEFAULTS, 'effects': 'aero' if glass else 'off', 'blur': glass, 'accent': '#7c4faa'}
                profiles.set_shared(preferences, directory, backend, {'compositing': True}, material_theme='ModeUser-verified')
                self.assertEqual(backend.values['xfwm4', '/general/theme'], 'ModeUser-verified')
                self.assertEqual(backend.values['xsettings', '/Net/ThemeName'], 'ModeUser-verified')
                self.assertEqual(before, {key: backend.values[key] for key in before})
                self.assertEqual(float(backend.values['xfce4-panel', '/panels/panel-1/background-rgba'][-1]) < 1, glass)

    def test_light_glass_retains_panel_alpha_without_enabling_backdrop_blur(self):
        for identifier in ('mac', 'windows11'):
            for budget, expected in ((True, '.94'), (False, '1')):
                directory = self.root / f'{identifier}-{budget}'
                backend = Xfconf(profiles.settings('oguzdows'))
                profiles.apply(identifier, directory, backend)
                profiles.set_shared({**state.DEFAULTS, 'effects': 'glass', 'blur': False}, directory, backend,
                                    {'compositing': budget}, material_theme='OpaqueContentUser')
                self.assertEqual(float(backend.values['xfce4-panel', '/panels/panel-1/background-rgba'][-1]), float(expected))
                self.assertEqual(backend.values['xfwm4', '/general/theme'], 'OpaqueContentUser')

    def test_new_reserved_plugin_collision_is_rejected_and_personal_slot_survives_classic_mode(self):
        backend = Xfconf(profiles.settings('oguzdows'))
        backend.values['xfce4-panel', '/plugins/plugin-95'] = 'personal-notes'
        backend.values['xfce4-panel', '/panels/panel-1/plugin-ids'].insert(2, '95')
        original = dict(backend.values)
        with self.assertRaises(ValueError): profiles.apply('windows11', self.root / 'profiles', backend)
        self.assertEqual(backend.values, original)
        profiles.apply('xfce', self.root / 'profiles', backend)
        self.assertIn('95', backend.values['xfce4-panel', '/panels/panel-1/plugin-ids'])
        self.assertEqual(backend.values['xfce4-panel', '/plugins/plugin-95'], 'personal-notes')

    def test_failed_mode_persistence_rolls_back_exact_layout_controls_and_selection(self):
        backend = Xfconf(profiles.settings('oguzdows'))
        original = dict(backend.values)
        directory = self.root / 'profiles'
        state.atomic_json(state.config_path(), {**state.DEFAULTS, 'accent_source': 'theme'})
        before = state.load()
        original_apply, atomic = profiles.apply, state.atomic_json
        def apply(identifier, **kwargs):
            return original_apply(identifier, directory, backend, **kwargs)
        def fail(path, value):
            if Path(path) == state.config_path() and value['revision'] == 1:
                raise OSError('mode save failed')
            atomic(path, value)
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'installation_busy', return_value=False), patch.object(profiles, 'apply', side_effect=apply), patch.object(preferences, 'apply_current', return_value={'message': 'fixture', 'notes': []}), patch.object(state, 'atomic_json', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'mode save failed'):
                preferences.update_and_apply({'appearance': 'dark'}, {'compositing': False}, profile='mac')
        self.assertEqual(backend.values, original)
        self.assertEqual(state.load(), before)
        self.assertFalse((directory / 'selected').exists())
        self.assertFalse((directory / 'layout-v2').exists())

    def test_dock_pins_and_native_observer_are_event_driven_not_idle_python_pollers(self):
        native = (ROOT / 'native/tasks.c').read_text()
        watcher = (ROOT / 'native/accent-watch.c').read_text()
        self.assertIn('g_file_monitor_directory', native)
        self.assertIn('pins.ini', native); self.assertNotIn('g_key_file_save', native)
        self.assertIn('g_application_new', watcher); self.assertIn('property-changed', watcher)
        self.assertIn('g_subprocess_wait_async', watcher)
        self.assertNotIn('system(', watcher); self.assertNotIn('popen(', watcher)
        self.assertIn('g_source_remove(tasks->animation)', native)
        self.assertIn('get_preferred_width = preferred_width', native)

    def test_generated_theme_cannot_import_arbitrary_css_or_overwrite_foreign_directory(self):
        with self.assertRaises(ValueError): material.install('#123456', False, renderer.window_theme, base_theme='../../personal')
        name = material.install('#123456', False, renderer.window_theme)
        marker = self.root / 'data/themes' / name / '.oguzdows-owned'; marker.write_text('foreign\n')
        with self.assertRaises(ValueError): material.install('#123456', False, renderer.window_theme)
        self.assertEqual(marker.read_text(), 'foreign\n')


if __name__ == '__main__':
    unittest.main()
