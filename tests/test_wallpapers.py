import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import load

wallpapers = load("wallpapers", "system/usr/lib/oguzdows/wallpapers.py")


class NativeWallpaperFixture:
    """CLI sözleşmesi taklidi; gerçek Xfce oturum kanıtı değildir."""
    def __init__(self, properties, values=()):
        self.properties = properties
        self.values = dict(values)
        self.calls = []

    def __call__(self, command):
        self.calls.append(command)
        if command[-1] == '-l':
            return subprocess.CompletedProcess(command, 0, '\n'.join(self.properties) + '\n')
        if command[0] == 'xrandr':
            return subprocess.CompletedProcess(command, 0, 'HDMI-1 connected primary\n')
        key = command[command.index('-p') + 1]
        if '--reset' in command:
            self.values.pop(key, None)
        elif '-s' in command:
            self.values[key] = command[command.index('-s') + 1]
        return subprocess.CompletedProcess(command, int(key not in self.values), self.values.get(key, '') + '\n')


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
            native = NativeWallpaperFixture([prop])
            items = [{"id": "istanbul", "path": str(image)}]
            with patch.object(wallpapers, "run", side_effect=native):
                wallpapers.apply("istanbul", items, root / "state")
            self.assertEqual((root / "state").read_text(), "istanbul\n")
            self.assertIn(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(image)], native.calls)
            self.assertFalse(any("monitor0" in " ".join(call) for call in native.calls))

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

    def test_initial_partial_native_and_marker_failures_restore_every_changed_monitor(self):
        import profiles
        atomic = profiles.atomic_text
        for stage in ('path', 'style', 'readback', 'marker', 'after-marker'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); image = root / 'new.png'; image.touch()
                props = [f'/backdrop/screen0/monitor{name}/workspace0/last-image' for name in ('DP-1', 'HDMI-1')]
                values = {prop: '/home/user/personal.jpg' for prop in props}
                values.update({prop.removesuffix('last-image') + 'image-style': '3' for prop in props})
                native = NativeWallpaperFixture(props, values)
                marker = root / 'state'; marker.write_text('previous\n\n')
                failed = False
                target = props[1] if stage != 'style' else props[1].removesuffix('last-image') + 'image-style'
                def run(command):
                    nonlocal failed
                    if stage in ('path', 'style', 'readback') and '-s' in command and command[command.index('-p') + 1] == target and command[-1] in (str(image), '5'):
                        failed = True
                        if stage == 'readback': return subprocess.CompletedProcess(command, 0, '')  # Kabul edildi ama yazılmadı.
                        native(command)  # Önce kısmen yazdı, sonra hata bildirdi.
                        raise OSError('CI partial native write failure')
                    return native(command)
                def write(path, text):
                    nonlocal failed
                    if stage in ('marker', 'after-marker') and text == 'new\n':
                        failed = True
                        if stage == 'after-marker': atomic(path, text)
                        raise OSError('CI marker commit failure')
                    atomic(path, text)
                with patch.object(wallpapers, 'run', side_effect=run), patch.object(profiles, 'atomic_text', side_effect=write), self.assertRaises((OSError, RuntimeError)):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker)
                self.assertTrue(failed)
                self.assertEqual(native.values, values)
                self.assertEqual(marker.read_text(), 'previous\n\n')

    def test_deferred_rollback_resets_previously_absent_values_and_preserves_external_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            prop = '/backdrop/screen0/monitorHDMI-1/workspace0/last-image'
            style = prop.removesuffix('last-image') + 'image-style'
            native = NativeWallpaperFixture([prop]); marker = root / 'state'; undo = []
            with patch.object(wallpapers, 'run', side_effect=native):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker, undo=undo)
                native.values[prop] = '/home/user/external-after.jpg'
                marker.write_text('external-after\n')
                undo[0]()
            self.assertEqual(native.values, {prop: '/home/user/external-after.jpg'})
            self.assertNotIn(style, native.values)
            self.assertEqual(marker.read_text(), 'external-after\n')

    def test_rollback_readback_failure_reports_error_but_continues_other_restorations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            prop = '/backdrop/screen0/monitorHDMI-1/workspace0/last-image'
            style = prop.removesuffix('last-image') + 'image-style'
            native = NativeWallpaperFixture([prop], {prop: '/home/user/personal.jpg', style: '3'})
            marker = root / 'state'; marker.write_text('previous\n'); undo = []
            def run(command):
                if '-s' in command and command[command.index('-p') + 1] == style and command[-1] == '3':
                    return subprocess.CompletedProcess(command, 0, '')  # Geri alma yazısı düşürüldü.
                return native(command)
            with patch.object(wallpapers, 'run', side_effect=run):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker, undo=undo)
                with self.assertRaisesRegex(RuntimeError, 'geri okunarak'):
                    undo[0]()
            self.assertEqual(native.values[prop], '/home/user/personal.jpg')
            self.assertEqual(native.values[style], '5')
            self.assertEqual(marker.read_text(), 'previous\n')

    def test_unsafe_marker_is_rejected_before_native_writes(self):
        for kind in ('symlink', 'fifo', 'oversize'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); image = root / 'new.png'; image.touch(); marker = root / 'state'
                if kind == 'symlink': marker.symlink_to(image)
                elif kind == 'fifo': os.mkfifo(marker)
                else: marker.write_text('x' * 4097)
                native = NativeWallpaperFixture(['/backdrop/screen0/monitor0/workspace0/last-image'])
                with patch.object(wallpapers, 'run', side_effect=native), self.assertRaises(ValueError):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker)
                self.assertFalse(any('-s' in command for command in native.calls))
                self.assertEqual(image.read_bytes(), b'')

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
