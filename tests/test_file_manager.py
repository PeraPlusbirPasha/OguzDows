"""One-shot preview budget, typed xfconf and personal-setting preservation."""
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load
from xfconf_fixture import Xfconf

files = load('file_manager_test', 'system/usr/lib/oguzdows/file_manager.py')
state = load('file_manager_state_test', 'system/usr/lib/oguzdows/desktop_state.py')
resources = load('file_manager_resources_test', 'system/usr/lib/oguzdows/resource_policy.py')


class FileManagerTests(unittest.TestCase):
    def test_physical_budget_wins_over_full_override_on_pc_pi_and_arm(self):
        for memory, mode, limit in ((0, 'NEVER', 8), (512, 'NEVER', 8), (1024, 'ONLY_LOCAL', 16),
                                    (2048, 'ONLY_LOCAL', 16), (4096, 'ONLY_LOCAL', 32)):
            for requested in resources.PROFILES:
                policy = resources.policy(memory * 1024, requested=requested)
                value = files.targets(policy)
                expected_mini = requested == 'mini' or memory <= 768
                self.assertTrue(value['thumbnails'].endswith('NEVER' if expected_mini else mode))
                self.assertEqual(value['max-bytes'], str((8 if expected_mini else limit) * 1024**2))
                self.assertEqual(value['frames'], 'false')
        self.assertTrue(files.targets(resources.policy(8 * 1024**2, legacy=True))['thumbnails'].endswith('NEVER'))

    def test_absent_settings_change_once_then_follow_budget_and_restore_exactly(self):
        backend = Xfconf()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            api = files.ThunarSettings(backend)
            self.assertEqual(len(files.apply(resources.policy(524288), directory, api)['changed']), 3)
            self.assertEqual(backend.values['thunar', '/misc-thumbnail-mode'], 'THUNAR_THUMBNAIL_MODE_NEVER')
            first_calls = len(backend.calls)
            self.assertFalse(files.apply(resources.policy(524288), directory, api)['changed'])
            self.assertTrue(all(len(command) == 5 for command in backend.calls[first_calls:]), 'No repeat writes / background worker')
            files.apply(resources.policy(4194304), directory, api)
            self.assertEqual(backend.values['thunar', '/misc-thumbnail-mode'], 'THUNAR_THUMBNAIL_MODE_ONLY_LOCAL')
            self.assertEqual(backend.types['thunar', '/misc-thumbnail-max-file-size'], 'uint64')
            self.assertEqual(files.restore(directory, api), [])
            self.assertEqual(backend.values, {})

    def test_personal_preferences_before_and_after_apply_are_never_overwritten(self):
        for personal in (None, 'THUNAR_THUMBNAIL_MODE_ALWAYS'):
            backend = Xfconf()
            if personal is not None:
                backend.values['thunar', '/misc-thumbnail-mode'] = personal
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); api = files.ThunarSettings(backend)
                files.apply(resources.policy(524288), directory, api)
                backend.values['thunar', '/misc-thumbnail-mode'] = 'THUNAR_THUMBNAIL_MODE_ALWAYS'
                backend.values['thunar', '/misc-thumbnail-max-file-size'] = '0'
                before = copy.deepcopy(backend.values)
                result = files.apply(resources.policy(4194304), directory, api)
                self.assertIn('thumbnails', result['preserved'])
                self.assertIn('max-bytes', result['preserved'])
                self.assertEqual(backend.values['thunar', '/misc-thumbnail-mode'], before['thunar', '/misc-thumbnail-mode'])
                files.restore(directory, api)
                self.assertEqual(backend.values, {key: value for key, value in before.items() if key[1] != '/misc-thumbnail-draw-frames'})

    def test_explicit_desktop_restore_blocks_session_reapplication(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            state.atomic_json(directory / 'xfce-applied.json', {'restored': True})
            backend = Xfconf()
            self.assertTrue(files.apply(resources.policy(524288), directory, files.ThunarSettings(backend))['restored'])
            self.assertEqual(backend.calls, [])
            self.assertFalse((directory / 'thunar-performance-settings.json').exists())

    def test_invalid_and_unbounded_values_are_rejected_before_execution(self):
        api = files.ThunarSettings(Xfconf())
        for key, value in (('other', None), ('thumbnails', 'ALWAYS; touch /tmp/no'), ('frames', True),
                           ('frames', '1'), ('max-bytes', '-1'), ('max-bytes', str(2**64)), ('max-bytes', '1e9')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                api.write(key, value)
        self.assertEqual(api.execute.calls, [])
        for value in ('0', '33554432', str(2**64 - 1)):
            api.validate('max-bytes', value)

    def test_failed_partial_write_rolls_back_exact_values_and_ownership(self):
        backend = Xfconf(); api = files.ThunarSettings(backend)
        original = api.write
        failed = False
        def write(key, value):
            nonlocal failed
            original(key, value)
            if key == 'max-bytes' and value is not None and not failed:
                failed = True
                raise OSError('simulated failure after actual fixture write')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch.object(api, 'write', side_effect=write), self.assertRaises(OSError):
                files.apply(resources.policy(524288), directory, api)
            self.assertTrue(failed)
            self.assertEqual(backend.values, {})
            self.assertEqual(state.read_json(directory / 'thunar-performance-settings.json'), {})

    def test_installed_entry_can_import_its_fixed_peers_in_isolated_mode(self):
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'system/usr/lib/oguzdows/file_manager.py'), '--help'],
                                capture_output=True, text=True, check=False, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--session', result.stdout)

    def test_session_uses_fixed_isolated_helper_not_polling_or_cache_deletion(self):
        session = (ROOT / 'system/usr/lib/oguzdows/session.sh').read_text()
        self.assertIn('/usr/bin/python3 -I /usr/lib/oguzdows/file_manager.py --session', session)
        source = (ROOT / 'system/usr/lib/oguzdows/file_manager.py').read_text()
        for unwanted in ('rglob(', 'unlink(', 'while True', 'sleep(', 'Popen(', 'shutil.rmtree'):
            self.assertNotIn(unwanted, source)


if __name__ == '__main__':
    unittest.main()
