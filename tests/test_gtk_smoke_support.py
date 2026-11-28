"""Optional GI binding warm-up never exempts application image / pet imports."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import support


class GtkSmokeSupportTests(unittest.TestCase):
    def fixture(self):
        window = Mock()
        window.get_size.return_value = (64, 48)
        gtk = Mock()
        gtk.Window.return_value = window
        gtk.events_pending.return_value = False
        gdk = Mock()
        return gtk, gdk, window

    def test_toolkit_cairo_is_measured_before_product_without_exempting_pillow_or_rig(self):
        gtk, gdk, window = self.fixture()
        modules = {}
        def render(*_args):
            modules.update(cairo=object(), PIL=object(), rifki_pet=object())
        window.get_window.return_value.process_updates.side_effect = render
        with patch.object(support, 'sys', SimpleNamespace(modules=modules)):
            self.assertEqual(support.native_gtk_imports(gtk, gdk), frozenset({'cairo'}))
        window.destroy.assert_called_once()
        gdk.pixbuf_get_from_window.assert_called_once_with(window.get_window.return_value, 0, 0, 64, 48)

    def test_no_cairo_exemption_when_the_toolkit_did_not_load_it(self):
        gtk, gdk, window = self.fixture()
        with patch.object(support, 'sys', SimpleNamespace(modules={'PIL': object()})):
            self.assertEqual(support.native_gtk_imports(gtk, gdk), frozenset())
        window.destroy.assert_called_once()

    def test_failed_native_capture_remains_fatal_and_closes_only_its_fixture(self):
        gtk, gdk, window = self.fixture()
        gdk.pixbuf_get_from_window.return_value = None
        with self.assertRaises(AssertionError):
            support.native_gtk_imports(gtk, gdk)
        window.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()
