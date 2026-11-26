"""GTK3 / GTK4 / portal choice, exact key ownership and rollback without GI."""
import configparser
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT
import desktop_appearance as appearance
import desktop_state as state
import desktop_shortcuts as shortcuts
import screenshot


class Value:
    def __init__(self, value): self.value = value
    def unpack(self): return self.value


class Settings:
    def __init__(self): self.value = None; self.calls = []
    def get_user_value(self, _key): return Value(self.value) if self.value is not None else None
    def set_string(self, key, value): self.calls.append((key, value)); self.value = value; return True
    def reset(self, key): self.calls.append((key, None)); self.value = None
    def sync(self): pass


class AppearanceTests(unittest.TestCase):
    def test_edits_only_settings_key_preserving_comments_and_unrelated_sections(self):
        text = '# personal\n[Settings]\ngtk-font-name=Personal 12\n# leave me\n[Other]\nvalue=100%\n'
        result = appearance.edit_key(text, 'gtk-theme-name', 'OguzDowsElevenDarkUser-test')
        self.assertIn('gtk-theme-name=OguzDowsElevenDarkUser-test\n[Other]', result)
        self.assertIn('gtk-font-name=Personal 12\n# leave me\n', result)
        self.assertTrue(result.endswith('[Other]\nvalue=100%\n'))
        self.assertEqual(appearance.edit_key(result, 'gtk-theme-name', None), text)
        result = appearance.edit_key('[Other]\nvalue=yes', 'gtk-theme-name', 'Theme')
        parser = configparser.ConfigParser(); parser.read_string(result)
        self.assertEqual(parser['Settings']['gtk-theme-name'], 'Theme')
        self.assertEqual(parser['Other']['value'], 'yes')

    def test_live_portal_and_both_gtk_generations_have_one_reversible_choice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); backend = appearance.AppearanceSettings(root, Settings())
            gtk3 = root / 'gtk-3.0/settings.ini'; gtk3.parent.mkdir()
            original = '[Settings]\ngtk-theme-name=Personal\ngtk-application-prefer-dark-theme=false\ngtk-font-name=Keep 11\n'
            gtk3.write_text(original)
            journal = state.Journal(backend, root / 'journal')
            values, notes = backend.changes({'appearance': 'dark'}, 'OguzDowsElevenDarkUser-test')
            self.assertEqual(notes, [])
            journal.apply(values)
            self.assertEqual(backend.read('gtk3-theme'), 'OguzDowsElevenDarkUser-test')
            self.assertEqual(backend.read('gtk3-dark'), '1')
            self.assertFalse((root / 'gtk-4.0/settings.ini').exists())
            self.assertNotIn('gtk4-dark', values)  # unsupported by libadwaita; use portal instead
            self.assertEqual(backend.read('color-scheme'), 'prefer-dark')
            self.assertEqual(stat.S_IMODE(gtk3.stat().st_mode), 0o600)
            values, _ = backend.changes({'appearance': 'light'}, 'OguzDowsElevenUser-test')
            journal.apply(values)
            self.assertEqual(backend.read('color-scheme'), 'prefer-light')
            backend.write('gtk3-theme', 'UserAfterApply')
            preserved = journal.restore()
            self.assertEqual(preserved, ['gtk3-theme'])
            self.assertEqual(backend.read('gtk3-theme'), 'UserAfterApply')
            self.assertEqual(backend.read('gtk3-dark'), '0')
            self.assertIsNone(backend.read('color-scheme'))
            self.assertIn('gtk-font-name=Keep 11', gtk3.read_text())
            self.assertFalse((root / 'gtk-4.0/settings.ini').exists())

    def test_write_failure_rolls_back_files_and_portal_not_a_guessed_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); settings = Settings(); settings.value = 'prefer-light'
            backend = appearance.AppearanceSettings(root, settings)
            values, _ = backend.changes({'appearance': 'dark'}, 'OguzDowsDark')
            write = backend.write
            def fail(key, value):
                if key == 'color-scheme' and value == 'prefer-dark': raise OSError('Test full disk')
                write(key, value)
            with patch.object(backend, 'write', side_effect=fail), self.assertRaises(OSError):
                state.Journal(backend, root / 'journal').apply(values)
            self.assertEqual(settings.value, 'prefer-light')
            for key in appearance.FILES:
                self.assertIsNone(backend.read(key))
            self.assertEqual(state.read_json(root / 'journal/xfce-appearance-settings.json'), {})

    def test_deferred_rollback_after_shared_file_commit_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); backend = appearance.AppearanceSettings(root, Settings())
            backend.write('gtk3-theme', 'PersonalBefore')
            journal = state.Journal(backend, root / 'journal')
            undo = []; values, _ = backend.changes({'appearance': 'dark'}, 'Dark')
            journal.apply(values, undo=undo)
            self.assertEqual(len(undo), 1); undo[0]()
            self.assertEqual(backend.read('gtk3-theme'), 'PersonalBefore')
            self.assertIsNone(backend.read('color-scheme'))
            self.assertIsNone(backend.read('gtk3-dark'))

    def test_symlink_fifo_invalid_and_oversized_personal_config_are_not_overwritten(self):
        for kind in ('symlink', 'fifo', 'invalid', 'huge', 'directory-link'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); folder = root / 'gtk-3.0'; folder.mkdir()
                target = root / 'personal'; target.write_text('[Settings]\ngtk-theme-name=Preserve\n')
                path = folder / 'settings.ini'
                if kind == 'symlink': path.symlink_to(target)
                elif kind == 'fifo': os.mkfifo(path)
                elif kind == 'invalid': path.write_text('not an INI')
                elif kind == 'huge': path.write_text('x' * (appearance.LIMIT + 1))
                else: folder.rmdir(); folder.symlink_to(root, target_is_directory=True)
                backend = appearance.AppearanceSettings(root, Settings())
                values, notes = backend.changes({'appearance': 'dark'}, 'Dark')
                self.assertNotIn('gtk3-theme', values); self.assertNotIn('gtk3-dark', values)
                self.assertTrue(notes)
                self.assertEqual(target.read_text(), '[Settings]\ngtk-theme-name=Preserve\n')

    def test_only_allowlisted_settings_and_single_line_theme_names_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = appearance.AppearanceSettings(Path(temporary), Settings())
            for key, value in (('anything', 'a'), ('gtk3-theme', 'dark\nrun=x'), ('gtk3-dark', 'yes'), ('color-scheme', 'auto')):
                with self.subTest(key=key), self.assertRaises(ValueError): backend.write(key, value)

    def test_default_panel_and_profiles_agree_on_small_signed_tray_icons(self):
        import xml.etree.ElementTree as ET
        import profiles
        xml = ET.parse(ROOT / 'system/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml').getroot()
        for path, kind, value in (('icon-size', 'int', '20'), ('single-row', 'bool', 'true'),
                                  ('square-icons', 'bool', 'false'), ('symbolic-icons', 'bool', 'true')):
            node = xml.find('./property[@name="plugins"]/property[@name="plugin-4"]/property[@name="' + path + '"]')
            self.assertEqual((node.get('type'), node.get('value')), (kind, value))
            for identifier in profiles.PROFILES:
                rows = {(channel, key): (typ, val) for channel, key, typ, val in profiles.settings(identifier, resources={'compositing': False})}
                self.assertEqual(rows['xfce4-panel', '/plugins/plugin-4/' + path], (kind, value))
        source = (ROOT / 'native/hub.c').read_text()
        for marker in ('public_recent(', 'gtk_recent_info_get_private_hint', 'g_application_hold(application)', 'g_application_release(G_APPLICATION(data))'):
            self.assertIn(marker, source)


class ScreenshotTests(unittest.TestCase):
    def test_capture_package_wrapper_and_xfce_session_migration_are_included(self):
        self.assertIn('\nxfce4-screenshooter\n', (ROOT / 'packages/common.list').read_text())
        wrapper = ROOT / 'system/usr/local/bin/oguzdows-screenshot'
        self.assertTrue(wrapper.stat().st_mode & 0o111)
        self.assertIn('screenshot.py "$@"', wrapper.read_text())
        self.assertIn('desktop_shortcuts.py --session', (ROOT / 'system/usr/lib/oguzdows/session.sh').read_text())
        for package in ('gsettings-desktop-schemas', 'xdg-desktop-portal-gtk', 'dconf-gsettings-backend'):
            self.assertIn('\n' + package + '\n', (ROOT / 'packages/common.list').read_text())

    def test_shortcut_migration_is_idempotent_and_personal_bindings_win(self):
        from types import SimpleNamespace as Result
        values = {'Print': 'flameshot gui', '<Alt>Print': 'xfce4-screenshooter -w'}
        calls = []
        def run(argv):
            calls.append(argv)
            key = argv[4].rsplit('/', 1)[-1]
            if '-s' in argv: values[key] = argv[-1]
            return Result(returncode=0 if key in values else 1, stdout=values.get(key, '') + '\n')
        result = shortcuts.install(run)
        self.assertEqual(result['personal_bindings_preserved'], ['Print'])
        self.assertEqual(values['Print'], 'flameshot gui')
        self.assertEqual(values['<Shift>Print'], '/usr/local/bin/oguzdows-screenshot --region')
        self.assertEqual(values['<Alt>Print'], '/usr/local/bin/oguzdows-screenshot --window')
        self.assertFalse(any('--reset' in argv for argv in calls))
        calls.clear(); shortcuts.install(run)
        self.assertFalse(any('-s' in argv for argv in calls))

    def test_modes_are_fixed_argv_no_shell_or_upload_and_missing_tool_is_explained(self):
        with tempfile.TemporaryDirectory() as temporary:
            tool = Path(temporary) / 'capture'
            with self.assertRaisesRegex(ValueError, 'xfce4-screenshooter'): screenshot.command('fullscreen', tool)
            tool.write_text('# test only'); tool.chmod(0o700)
            for mode, argument in screenshot.MODES.items():
                self.assertEqual(screenshot.command(mode, tool), [str(tool), argument])
            with self.assertRaises(ValueError): screenshot.command('--upload', tool)


if __name__ == '__main__':
    unittest.main()
