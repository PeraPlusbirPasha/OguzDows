"""Ortak tercih / kurtarma işlemleri. Hiçbir test gerçek masaüstüne yazmaz."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT  # sys.path: ortak, yan etkisiz modüller
import desktop_state as state


class Backend:
    name = 'test'
    keys = {'theme', 'motion', 'uuid'}

    def __init__(self, values=None):
        self.values = dict(values or {})
        self.calls = []

    def validate(self, key, value):
        if key not in self.keys or value is not None and not isinstance(value, (str, bool)):
            raise ValueError('not allowed')

    def read(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.calls.append((key, value))
        self.values[key] = value


class DesktopStateTests(unittest.TestCase):
    def test_upgrade_migrates_only_previous_style_and_never_enables_new_effects(self):
        import profiles
        with tempfile.TemporaryDirectory() as temporary, patch.object(profiles, 'selection', return_value=('mac', 'dark')), patch.object(profiles, 'effect_selection', return_value='aero'):
            value = state.load(Path(temporary) / 'missing')
            self.assertEqual(value['appearance'], 'dark'); self.assertEqual(value['effects'], 'aero')
            self.assertFalse(value['blur']); self.assertFalse(value['snap_animation'])
            self.assertEqual(value['motion'], 'smooth'); self.assertEqual(value['revision'], 0)

    def test_strict_schema_types_colors_ids_and_revisions(self):
        bad = ({'schema': True}, {'schema': 2}, {'revision': True}, {'revision': 2**53},
               {'revision': -1}, {'blur': 1}, {'feedback': 'yes'}, {'snap_animation': []},
               {'accent': '#f00; color:red'}, {'accent': '#123456\n'}, {'appearance': 'auto'},
               {'effects': 'shell --run'}, {'motion': 'loop'}, {'accent_source': 'execute'},
               {'wallpaper': '../secret'}, {'wallpaper': 'x' * 81})
        for change in bad:
            with self.subTest(change=change), self.assertRaises(ValueError):
                state.validate({**state.DEFAULTS, **change})
        with self.assertRaises(ValueError): state.validate({**state.DEFAULTS, 'command': 'x'})
        with self.assertRaises(ValueError): state.validate({})
        self.assertEqual(state.merged(state.DEFAULTS, {'accent': '#AABBCC'})['accent'], '#aabbcc')
        with self.assertRaises(ValueError): state.merged(state.DEFAULTS, {'revision': 900})
        self.assertEqual(state.merged(state.DEFAULTS, {})['revision'], 1)

    def test_private_atomic_json_and_failed_write_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'private/config.json'
            state.atomic_json(path, state.DEFAULTS)
            original = path.read_bytes()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(ValueError): state.atomic_json(path, {'x': 'a' * state.LIMIT})
            with patch.object(Path, 'replace', side_effect=OSError('disk')), self.assertRaises(OSError):
                state.atomic_json(path, {'new': True})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_symlink_fifo_directory_large_and_foreign_owned_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'value').write_text('{}')
            (root / 'link').symlink_to(root / 'value')
            os.mkfifo(root / 'fifo')
            (root / 'large').write_text(' ' * (state.LIMIT + 1))
            for name in ('link', 'fifo', 'large', '.'):
                with self.subTest(name=name), self.assertRaises((OSError, ValueError)):
                    state.read_json(root / name)
            with patch.object(state.os, 'getuid', return_value=os.getuid() + 1), self.assertRaises(ValueError):
                state.read_json(root / 'value')
            with self.assertRaises(ValueError): state.atomic_json(root / 'link', {})
            with self.assertRaises(ValueError): state.private_directory(root / 'link')
            self.assertEqual(state.read_json(root / 'missing', {'x': 1}), {'x': 1})

    def test_nonblocking_private_lock_and_fifo_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with state.locked(root):
                with self.assertRaises(RuntimeError):
                    with state.locked(root): pass
            self.assertEqual((root / '.lock').stat().st_mode & 0o777, 0o600)
            (root / '.lock').unlink(); os.mkfifo(root / '.lock')
            with self.assertRaises((OSError, ValueError)):
                with state.locked(root): pass

    def test_journal_is_written_before_backend_and_restore_is_compare_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); backend = Backend({'theme': 'personal', 'uuid': False})
            journal = state.Journal(backend, root)
            original = backend.write
            def write(key, value):
                disk = json.loads(journal.path.read_text())
                self.assertEqual(disk[key]['applied'], value)
                original(key, value)
            backend.write = write
            journal.apply({'theme': 'glass', 'uuid': True})
            backend.write = original
            backend.values['motion'] = 'external'
            backend.values['theme'] = 'custom-after-oguzdows'
            skipped = state.Journal(backend, root).restore()
            self.assertEqual(skipped, ['theme'])
            self.assertEqual(backend.values['theme'], 'custom-after-oguzdows')
            self.assertFalse(backend.values['uuid'])
            self.assertEqual(backend.values['motion'], 'external')
            self.assertEqual(json.loads(journal.path.read_text()), {})

    def test_external_change_becomes_new_restore_base_and_other_tokens_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = Backend({'theme': 'first', 'motion': 'smooth'})
            journal = state.Journal(backend, Path(temporary))
            journal.apply({'theme': 'glass'}); backend.values['theme'] = 'personal-new'
            journal.apply({'theme': 'glass-dark', 'motion': 'spring'})
            journal.restore()
            self.assertEqual(backend.values, {'theme': 'personal-new', 'motion': 'smooth'})

    def test_failed_backend_rolls_back_prior_writes_and_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = Backend({'theme': 'before', 'motion': 'smooth'})
            journal = state.Journal(backend, Path(temporary)); before = copy.deepcopy(backend.values)
            original = backend.write
            def write(key, value):
                if key == 'motion' and value == 'spring': raise RuntimeError('unwritable')
                original(key, value)
            backend.write = write
            with self.assertRaisesRegex(RuntimeError, 'unwritable'):
                journal.apply({'theme': 'glass', 'motion': 'spring'})
            self.assertEqual(backend.values, before)
            self.assertEqual(json.loads(journal.path.read_text()), {})

    def test_silent_backend_noop_is_not_success_and_other_tokens_roll_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = Backend({'theme': 'before', 'motion': 'smooth'})
            journal = state.Journal(backend, Path(temporary)); original = backend.write
            backend.write = lambda key, value: original(key, value) if key != 'motion' else None
            with self.assertRaisesRegex(RuntimeError, 'doğrulanamadı'):
                journal.apply({'theme': 'glass', 'motion': 'spring'})
            self.assertEqual(backend.values, {'theme': 'before', 'motion': 'smooth'})

    def test_untrusted_journal_cannot_target_arbitrary_backend_or_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            backend = Backend(); root = Path(temporary)
            for data in ([], {'execute': {'before': None, 'applied': 'rm'}}, {'theme': {'before': [], 'applied': 'x'}}, {'theme': {'before': None}}):
                state.atomic_json(root / 'test-settings.json', data)
                with self.subTest(data=data), self.assertRaises(ValueError): state.Journal(backend, root)
            (root / 'test-settings.json').unlink()
            journal = state.Journal(backend, root)
            with self.assertRaises(ValueError): journal.apply({'execute': 'anything'})
            self.assertEqual(backend.calls, [])

    def test_imports_have_no_shell_or_auto_session_switch(self):
        source = (ROOT / 'system/usr/lib/oguzdows/desktop_state.py').read_text()
        for bad in ('subprocess.', 'os.system(', 'exec(', 'eval(', 'logout', 'systemctl'):
            self.assertNotIn(bad, source)


if __name__ == '__main__':
    unittest.main()
