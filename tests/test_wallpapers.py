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
    def __init__(self, properties, values=(), *, monitors=None, workspaces='4', display_info=None):
        self.properties = properties
        self.values = dict(values)
        self.calls = []
        self.monitors = ('Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767\n'
                         'HDMI-1 connected primary 1920x1080+0+0 (normal)\n') if monitors is None else monitors
        self.workspaces = workspaces
        self.display_info = display_info

    def __call__(self, command):
        self.calls.append(command)
        if command[-1] == '-l':
            return subprocess.CompletedProcess(command, 0, '\n'.join(self.properties) + '\n')
        if command[0] == 'xrandr':
            return subprocess.CompletedProcess(command, 0, self.monitors)
        if command[-1] == '--display-info':
            return subprocess.CompletedProcess(command, int(self.display_info is None), json.dumps(self.display_info))
        if command[command.index('-c') + 1] == 'xfwm4':
            assert command[-1] == '/general/workspace_count'
            return subprocess.CompletedProcess(command, int(self.workspaces is None), (self.workspaces or '') + '\n')
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

    def test_stale_connector_and_absent_live_last_image_do_not_swallow_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            stale = '/backdrop/screen0/monitorHDMI-0/workspace0/last-image'
            live = '/backdrop/screen0/monitorHDMI-1/workspace0/last-image'
            style = live.removesuffix('last-image') + 'image-style'
            native = NativeWallpaperFixture([stale, style], {stale: '/previous/old-port.jpg', style: '0'})
            with patch.object(wallpapers, 'run', side_effect=native):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
            self.assertEqual(native.values.get(live), str(image))
            self.assertEqual(native.values[style], '5')
            self.assertIn(['xrandr', '--query'], native.calls)
            self.assertEqual((root / 'marker').read_text(), 'new\n')

    def test_all_live_monitors_and_more_than_four_workspaces_are_targeted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            monitors = ('Screen 1: minimum 8 x 8, current 3840 x 1080, maximum 32767 x 32767\n'
                        'HDMI-1 connected primary 1920x1080+0+0 (normal)\n'
                        'DP-1 connected 1920x1080+1920+0 (normal)\n'
                        'DP-2 connected (normal left inverted right x axis y axis)\n'
                        'HDMI-2 disconnected (normal)\n')
            native = NativeWallpaperFixture([], monitors=monitors, workspaces='6')
            with patch.object(wallpapers, 'run', side_effect=native):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
            images = {key: value for key, value in native.values.items() if key.endswith('/last-image')}
            self.assertEqual(images, {f'/backdrop/screen1/monitor{monitor}/workspace{workspace}/last-image': str(image)
                                      for monitor in ('HDMI-1', 'DP-1') for workspace in range(6)})

    def test_missing_last_image_is_recovered_from_other_native_backdrop_properties(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            # Older GDK / numeric monitor identifiers must remain usable too.
            prefix = '/backdrop/screen0/monitor0/workspace5/'
            native = NativeWallpaperFixture([prefix + 'image-style'], {prefix + 'image-style': '0'})
            with patch.object(wallpapers, 'run', side_effect=native):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
            self.assertEqual(native.values.get(prefix + 'last-image'), str(image))
            self.assertEqual(native.values[prefix + 'image-style'], '5')

    def test_no_active_monitor_never_falls_back_to_an_invented_monitor_zero(self):
        for monitors in ('', 'Screen 0: current 1920 x 1080\nHDMI-1 disconnected\n',
                         'Screen 0: current 1920 x 1080\nHDMI-1 connected (normal)\n'):
            with self.subTest(monitors=monitors), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); image = root / 'new.png'; image.touch()
                stale = '/backdrop/screen0/monitorOld/workspace0/last-image'
                native = NativeWallpaperFixture([stale], {stale: '/personal/keep.jpg'}, monitors=monitors)
                with patch.object(wallpapers, 'run', side_effect=native), self.assertRaisesRegex(RuntimeError, 'monitör'):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
                self.assertFalse(any('-s' in command or '--reset' in command for command in native.calls))
                self.assertEqual(native.values, {stale: '/personal/keep.jpg'})
                self.assertFalse((root / 'marker').exists())

    def test_randr_unavailable_uses_real_display_metadata_not_gpu_or_guessed_monitor_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            native = NativeWallpaperFixture([], monitors='', display_info={'screen': 2, 'monitors': ['0', 'Legacy-1']})
            def run(command):
                if command[0] == 'xrandr':
                    raise FileNotFoundError('CI no RandR utility')
                return native(command)
            with patch.object(wallpapers, 'run', side_effect=run):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
            images = {key: value for key, value in native.values.items() if key.endswith('/last-image')}
            self.assertEqual(images, {f'/backdrop/screen2/monitor{name}/workspace{workspace}/last-image': str(image)
                                      for name in ('0', 'Legacy-1') for workspace in range(4)})
            helper, = [command for command in native.calls if command[-1] == '--display-info']
            self.assertEqual(helper[-3:], ['-I', str(Path(wallpapers.__file__).resolve()), '--display-info'])

    def test_invalid_display_helper_reply_never_changes_native_keys(self):
        for reply in ({}, {'screen': True, 'monitors': ['0']}, {'screen': -1, 'monitors': ['0']},
                      {'screen': 0, 'monitors': []}, {'screen': 0, 'monitors': ['bad/monitor']},
                      {'screen': 0, 'monitors': ['bad\nmonitor']}, {'screen': 0, 'monitors': ['bad\0monitor']},
                      {'screen': 0, 'monitors': [1]}, {'screen': 0, 'monitors': ['a'] * 129},
                      {'screen': 0, 'monitors': ['0'], 'extra': True}):
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); image = root / 'new.png'; image.touch()
                native = NativeWallpaperFixture([], monitors='', display_info=reply)
                with patch.object(wallpapers, 'run', side_effect=native), self.assertRaisesRegex(RuntimeError, 'monitör'):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
                self.assertEqual(native.values, {})
                self.assertFalse((root / 'marker').exists())

    def test_workspace_and_target_bounds_are_checked_before_any_write(self):
        for count in ('0', '-1', 'not-a-number', '129'):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); image = root / 'new.png'; image.touch()
                native = NativeWallpaperFixture([], workspaces=count)
                with patch.object(wallpapers, 'run', side_effect=native), self.assertRaises(ValueError):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
                self.assertFalse(any('-s' in command for command in native.calls))
                self.assertFalse((root / 'marker').exists())

    def test_absent_workspace_count_keeps_xfce_default_and_readback_rollback(self):
        import profiles
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            native = NativeWallpaperFixture([], workspaces=None)
            with patch.object(wallpapers, 'run', side_effect=native), patch.object(profiles, 'atomic_text', side_effect=OSError('CI commit failure')):
                with self.assertRaises(OSError):
                    wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], root / 'marker')
            paths = {command[command.index('-p') + 1] for command in native.calls if '-s' in command and command[-1] == str(image)}
            self.assertEqual(paths, {f'/backdrop/screen0/monitorHDMI-1/workspace{workspace}/last-image' for workspace in range(4)})
            self.assertEqual(native.values, {})
            self.assertFalse((root / 'marker').exists())

    def test_deferred_rollback_restores_custom_native_path_not_a_guessed_catalog_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); image = root / 'new.png'; image.touch()
            prop = '/backdrop/screen0/monitorHDMI-1/workspace0/last-image'
            style = prop.removesuffix('last-image') + 'image-style'
            values = {prop: '/home/user/My personal wallpaper.jpg', style: '3'}
            marker = root / 'state'; marker.write_text('personal-old-marker\n')
            native = NativeWallpaperFixture([prop], values)
            undo = []
            with patch.object(wallpapers, 'run', side_effect=native):
                wallpapers.apply_xfce('new', [{'id': 'new', 'path': str(image)}], marker, undo=undo)
                self.assertEqual(native.values[prop], str(image)); self.assertEqual(native.values[style], '5')
                undo[0]()
            self.assertEqual(native.values, {prop: '/home/user/My personal wallpaper.jpg', style: '3'})
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
