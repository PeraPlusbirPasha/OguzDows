"""Shared native material contract; resource decisions do not require GTK imports."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import ROOT, load

ui = load('material_theme_test', 'system/usr/lib/oguzdows/ui_theme.py')


class MaterialPolicyTests(unittest.TestCase):
    def test_motion_requires_gtk_resource_and_explicit_non_reduced_preference(self):
        for animations in (True, False):
            for eligible in (True, False):
                for motion in ('reduced', 'smooth', 'spring'):
                    with self.subTest(animations=animations, eligible=eligible, motion=motion):
                        self.assertEqual(ui.motion_allowed({'motion': motion}, {'animations': eligible}, animations),
                                         animations and eligible and motion != 'reduced')

    def test_alpha_requires_live_owned_blur_not_merely_requested_preference(self):
        screen = NS(is_composited=lambda: True)
        preferences = {'effects': 'aero', 'blur': True}
        resources = {'compositing': True}
        state = NS(read_json=Mock(return_value={'engine': 'picom', 'blur_configured': True}))
        connection = NS(owner=Mock(return_value=42), close=Mock())
        effects = NS(owned_state=Mock(return_value={'owner': 42}), X11=Mock(return_value=connection))
        with patch.dict('sys.modules', {'desktop_state': state, 'effects': effects}), patch.dict('os.environ', {'XDG_SESSION_TYPE': 'x11'}):
            self.assertTrue(ui.blur_confirmed(screen, preferences, resources))
            connection.close.assert_called_once()
            connection.owner.return_value = 43
            self.assertFalse(ui.blur_confirmed(screen, preferences, resources))
            effects.owned_state.return_value = None
            self.assertFalse(ui.blur_confirmed(screen, preferences, resources))
            for prefs, budget in (({'effects': 'off', 'blur': True}, resources),
                                  ({'effects': 'aero', 'blur': False}, resources), (preferences, {'compositing': False})):
                self.assertFalse(ui.blur_confirmed(screen, prefs, budget))
            with patch.dict('os.environ', {'XDG_SESSION_TYPE': 'wayland'}):
                self.assertFalse(ui.blur_confirmed(screen, preferences, resources))

    def test_all_native_apps_share_theme_and_bounded_stack_helper_not_per_frame_layout(self):
        for path in ('native/news.c', 'native/store.c', 'native/hub.c', 'native/monitor.c'):
            source = (ROOT / path).read_text()
            self.assertIn('og_ui_setup(window)', source, path)
            self.assertNotIn('gtk_css_provider_load_from_data', source, path)
        for path in ('native/news.c', 'native/store.c', 'native/monitor.c'):
            self.assertIn('og_ui_stack_setup(', (ROOT / path).read_text())
        source = (ROOT / 'native/ui.c').read_text()
        self.assertNotIn('gtk_widget_add_tick_callback', source)
        self.assertNotIn('32 + (int)round', source)
        self.assertIn('XGetSelectionOwner', source)
        self.assertIn('started', source)
        self.assertIn('nomodeset', source)
        css = ui.CSS.read_text()
        self.assertIn('border: 1px solid rgba(', css)
        self.assertIn('-gtk-icon-transform: scale(', css)
        self.assertIn('.reduced-motion', css)
        self.assertNotIn('backdrop-filter:', css)
        self.assertNotIn('box-shadow: 0 10px', css)


if __name__ == '__main__':
    unittest.main()
