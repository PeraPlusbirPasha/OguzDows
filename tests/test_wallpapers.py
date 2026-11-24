import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import load

wallpapers = load("wallpapers", "system/usr/lib/oguzdows/wallpapers.py")


class WallpaperTests(unittest.TestCase):
    def test_invalid_catalog_and_unknown_selection_are_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "wallpapers.json"
            self.assertEqual(wallpapers.catalog(manifest), [])
            manifest.write_text("bad json")
            self.assertEqual(wallpapers.catalog(manifest), [])
            manifest.write_text(json.dumps([{}, {"id": "x", "name": "x", "path": "x", "preview": "x"}]))
            self.assertEqual(len(wallpapers.catalog(manifest)), 1)
            with patch.object(wallpapers, "run") as run, self.assertRaises(ValueError):
                wallpapers.apply("unknown", items=[], state=root / "state")
            run.assert_not_called()

    def test_apply_uses_detected_monitors_and_persists_only_after_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "istanbul.png"
            image.touch()
            prop = "/backdrop/screen0/monitorHDMI-1/workspace0/last-image"
            calls = []
            def run(command):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, prop + "\n" if command[-1] == "-l" else "", "")
            items = [{"id": "istanbul", "path": str(image)}]
            with patch.object(wallpapers, "run", side_effect=run):
                wallpapers.apply("istanbul", items, root / "state")
            self.assertEqual((root / "state").read_text(), "istanbul\n")
            self.assertIn(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(image)], calls)
            self.assertFalse(any("monitor0" in " ".join(call) for call in calls))

    def test_deferred_rollback_restores_custom_native_path_not_a_guessed_catalog_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            prop = '/backdrop/screen0/monitorHDMI-1/workspace0/last-image'
            style = prop.removesuffix('last-image') + 'image-style'
            values = {prop: '/home/user/My personal wallpaper.jpg', style: '3'}
            marker = root / 'state'; marker.write_text('personal-old-marker\n')
            def run(command):
                if command[-1] == '-l': return subprocess.CompletedProcess(command, 0, prop + '\n')
                key = command[command.index('-p') + 1]
                if '--reset' in command: values.pop(key, None)
                elif '-s' in command: values[key] = command[command.index('-s') + 1]
                return subprocess.CompletedProcess(command, int(key not in values), values.get(key, '') + '\n')
            undo = []
            with patch.object(wallpapers, 'run', side_effect=run):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker, undo=undo)
                self.assertEqual(values[prop], str(image)); self.assertEqual(values[style], '5')
                undo[0]()
            self.assertEqual(values, {prop: '/home/user/My personal wallpaper.jpg', style: '3'})
            self.assertEqual(marker.read_text(), 'personal-old-marker\n')

    def test_initialize_migrates_retired_ids_once_without_resetting_valid_or_custom_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'wallpaper'
            with patch.object(wallpapers, 'state_path', return_value=state), patch.object(wallpapers, 'apply') as apply:
                wallpapers.initialize()
                apply.assert_called_once_with('bogaz-sabahi')
                for old, new in wallpapers.LEGACY.items():
                    apply.reset_mock()
                    state.write_text(old + '\n')
                    wallpapers.initialize()
                    apply.assert_called_once_with(new)
                for selected in ('bogaz-sabahi', 'ani-kisi', 'kendi-gorselim'):
                    apply.reset_mock()
                    state.write_text(selected + '\n')
                    wallpapers.initialize()
                    apply.assert_not_called()

    def test_failed_desktop_change_does_not_record_a_false_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "wallpaper.png"
            image.touch()
            with patch.object(wallpapers, "run", return_value=subprocess.CompletedProcess([], 1, "", "")), self.assertRaises(RuntimeError):
                wallpapers.apply("a", [{"id": "a", "path": str(image)}], root / "state")
            self.assertFalse((root / "state").exists())


if __name__ == "__main__":
    unittest.main()
