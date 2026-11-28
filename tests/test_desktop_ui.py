"""GTK'sız yaşam döngüsü regresyonları; widget / işçi burada açıkça taklittir."""
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from support import load

# Gerçek GTK / X11 uçtan uca denetimi ayrıca smoke-effects.py içindedir.
gi = NS(require_version=lambda *_: None)
gtk = NS(Application=object, Box=object, MessageType=NS(QUESTION=0),
         ButtonsType=NS(OK_CANCEL=0), ResponseType=NS(OK=1, CANCEL=0))
glib = NS(SOURCE_REMOVE=False)
with patch.dict(sys.modules, {'gi': gi, 'gi.repository': NS(
        Gtk=gtk, GLib=glib, Gio=object, Gdk=object, GdkPixbuf=object, Pango=object)}):
    welcome = load('welcome_appearance_unit', 'system/usr/lib/oguzdows/welcome.py')
    ui = load('desktop_ui_unit', 'system/usr/lib/oguzdows/desktop_ui.py')


class InlineThread:
    """İşçiyi testte eşzamanlı çalıştır; GTK tamamlaması yine kuyrukta kalır."""
    def __init__(self, *, target, daemon):
        self.target = target
    def start(self):
        self.target()


class AppearanceWorkerTests(unittest.TestCase):
    def setUp(self):
        self.pending = []
        dispatch = patch.object(glib, 'idle_add', side_effect=lambda *args: self.pending.append(args), create=True)
        dispatch.start(); self.addCleanup(dispatch.stop)
        self.app = welcome.Welcome.__new__(welcome.Welcome)
        for flag in ('theme_busy', 'profile_busy', 'install_busy', 'external_installing', 'driver_busy'):
            setattr(self.app, flag, False)
        self.app.window = Mock()
        self.app.theme_buttons = {'light': Mock(), 'dark': Mock()}
        self.app.wallpaper_buttons = []
        self.app.rifki = None
        for name in ('theme_status', 'profile_apply', 'profile_restore', 'profile_status', 'profile_reload', 'wallpaper_status'):
            setattr(self.app, name, Mock())
        self.app.profile_reload.get_active.return_value = False
        self.panel = ui.PreferencesPanel.__new__(ui.PreferencesPanel)
        self.panel.busy = self.panel.closed = False
        self.panel.load_error = ''
        self.panel.gate_message = None
        self.panel.allowed = lambda: not any(getattr(self.app, flag) for flag in (
            'theme_busy', 'profile_busy', 'install_busy', 'external_installing', 'driver_busy'))
        self.panel.blocked_reason = lambda: self.app.appearance_blocked_reason()
        self.panel.on_busy = self.app.material_busy_changed
        self.panel.apply_button = Mock(); self.panel.restore_button = Mock()
        messages = {'text': ''}
        self.panel.status = Mock(set_text=lambda text: messages.update(text=text), get_text=lambda: messages['text'])
        self.app.material_panel = self.panel

    def flush(self):
        while self.pending:
            callback, *args = self.pending.pop(0)
            callback(*args)

    def test_welcome_thread_start_failure_cannot_leave_theme_profile_or_wallpaper_busy(self):
        for action, flag in ((lambda: self.app.change_appearance('dark'), 'theme_busy'),
                             (lambda: self.app.change_style('oguzdows'), 'profile_busy'),
                             (lambda: self.app.reload_panels(), 'profile_busy'),
                             (lambda: self.app.apply_wallpaper({'id': 'test', 'name': 'Test'}), 'theme_busy')):
            dialog = Mock(); dialog.run.return_value = gtk.ResponseType.OK
            with self.subTest(flag=flag), self.assertLogs(level='ERROR'), patch.object(
                    welcome.desktop_runtime, 'current', return_value='xfce'), patch.object(
                    gtk, 'MessageDialog', return_value=dialog, create=True), patch.object(
                    welcome.threading.Thread, 'start', side_effect=RuntimeError('fixture thread start')):
                action()
                self.flush()
                self.assertFalse(getattr(self.app, flag))
                self.assertTrue(self.panel.allowed())
                self.assertTrue(self.panel.apply_button.set_sensitive.call_args.args[0])

    def test_unexpected_theme_error_releases_parent_gate_then_apply_can_run(self):
        with self.assertLogs(level='ERROR'), patch.object(welcome.threading, 'Thread', InlineThread), patch.object(
                welcome.desktop_preferences, 'update_and_apply', side_effect=KeyError('fixture backend shape')):
            self.app.change_appearance('dark')
            self.assertTrue(self.app.theme_busy)  # Tamamlama GTK kuyruğunda.
            self.flush()
        self.assertFalse(self.app.theme_busy)
        self.assertIn('fixture backend shape', self.app.theme_status.set_text.call_args.args[0])
        operation = Mock(return_value={'message': 'Applied'})
        with patch.object(ui.threading, 'Thread', InlineThread):
            self.panel.work(operation)
            self.flush()
        operation.assert_called_once_with()
        self.assertFalse(self.app.theme_busy or self.panel.busy)
        self.assertEqual(self.panel.status.get_text(), 'Applied')

    def test_repeated_click_does_not_misreport_its_own_pending_apply_as_a_conflict(self):
        operation = Mock(return_value={'message': 'Applied'})
        duplicate = Mock()
        with patch.object(ui.threading, 'Thread', InlineThread):
            self.panel.work(operation)
            message = self.panel.status.get_text()
            self.assertTrue(self.panel.busy and self.app.theme_busy)
            self.panel.work(duplicate)
            self.assertEqual(self.panel.status.get_text(), message)
            self.flush()
        operation.assert_called_once_with(); duplicate.assert_not_called()
        self.assertFalse(self.panel.busy or self.app.theme_busy)

    def test_real_other_operations_still_block_without_starting_another_worker(self):
        for flag in ('theme_busy', 'profile_busy', 'install_busy', 'external_installing', 'driver_busy'):
            with self.subTest(flag=flag):
                setattr(self.app, flag, True)
                operation = Mock()
                self.panel.work(operation)
                operation.assert_not_called()
                self.assertFalse(self.panel.busy)
                self.assertTrue(getattr(self.app, flag))
                self.assertEqual(self.panel.status.get_text(), self.app.appearance_blocked_reason())
                self.assertFalse(self.panel.apply_button.set_sensitive.call_args.args[0])
                setattr(self.app, flag, False)
                self.app.refresh_appearance_controls()
                self.assertTrue(self.panel.apply_button.set_sensitive.call_args.args[0])
                self.assertIsNone(self.panel.gate_message)

    def test_finishing_apply_does_not_clear_a_concurrent_external_installer(self):
        with patch.object(ui.threading, 'Thread', InlineThread):
            self.panel.work(lambda: {'message': 'Applied'})
            self.app.external_installing = True
            self.flush()
        self.assertTrue(self.app.external_installing)
        self.assertFalse(self.app.theme_busy or self.panel.busy)
        self.assertFalse(self.panel.apply_button.set_sensitive.call_args.args[0])
        self.assertIn('Kurulum', self.panel.status.get_text())

    def test_worker_releases_gate_before_reporting_and_never_updates_a_closed_window(self):
        for closed in (False, True):
            with self.subTest(closed=closed), patch.object(welcome.threading, 'Thread', InlineThread):
                self.app.theme_busy = True
                completed = Mock(side_effect=lambda *_: self.assertFalse(self.app.theme_busy))
                self.app.appearance_worker('theme_busy', lambda: 17, completed)
                self.assertTrue(self.app.theme_busy)
                if closed:
                    self.app.window = None
                self.flush()
                self.assertFalse(self.app.theme_busy)
                if closed:
                    completed.assert_not_called()
                else:
                    completed.assert_called_once_with(17, None)

    def test_legacy_effect_callback_uses_shared_apply_without_prelocking_its_own_gate(self):
        self.panel.apply = Mock(side_effect=lambda: self.assertTrue(self.panel.allowed()))
        self.app.change_effects()
        self.panel.apply.assert_called_once_with()
        self.assertFalse(self.app.theme_busy)


if __name__ == '__main__':
    unittest.main()
