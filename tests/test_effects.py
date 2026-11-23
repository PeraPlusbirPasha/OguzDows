"""Kaynak / kompozitör sahipliği sınırları; fiziksel GPU veya animasyon testi değil."""
import fcntl
import json
import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT, load

effects = load('window_effects_test', 'system/usr/lib/oguzdows/effects.py')
policy = load('window_policy_test', 'system/usr/lib/oguzdows/resource_policy.py')
profiles = load('window_profiles_test', 'system/usr/lib/oguzdows/profiles.py')


class EffectTests(unittest.TestCase):
    def test_low_ram_legacy_unknown_gpu_and_nomodeset_cannot_enable_transitions(self):
        for resources in [policy.policy(memory, requested='full') for memory in (0, 524288, 1048576, 2097152)] + [policy.policy(8388608, **extra) for extra in ({'legacy': True}, {'nomodeset': True}, {'graphics': False})]:
            with self.subTest(resources=resources), tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'spawn') as spawn, patch.object(effects, 'xfwm') as xfwm, patch.object(effects, 'stop_owned') as stop:
                x11 = Mock(owner=Mock(return_value=0))
                result = effects.reconcile('aero', resources, directory=Path(temporary), connect=lambda: x11)
                self.assertFalse(result['transitions'])
                self.assertEqual(result['engine'], 'none')
                spawn.assert_not_called(); stop.assert_called_once(); xfwm.assert_called_once_with(False)
                x11.close.assert_called_once()
                values = {key: value for _ch, key, _kind, value in profiles.settings('mac', effects='aero', resources=resources)}
                self.assertEqual(values['/Gtk/EnableAnimations'], 'false')
                self.assertEqual(values['/general/use_compositing'], 'false')
                self.assertEqual(values['/panels/panel-90/background-rgba'][-1], '1')

    def test_eligible_aero_disables_xfwm_before_single_fixed_config_spawn(self):
        calls = []
        x11 = Mock(owner=Mock(return_value=0))
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'owned_state', return_value=None), patch.object(effects, 'stop_owned'), patch.object(effects, 'xfwm', side_effect=lambda value: calls.append(('xfwm', value))), patch.object(effects.Path, 'is_file', return_value=True), patch.object(effects.os, 'access', return_value=True), patch.object(effects, 'wait_owner', side_effect=[0, 77]), patch.object(effects, 'spawn', side_effect=lambda directory: calls.append(('spawn', directory)) or 12345), patch.object(effects, 'identity', return_value='123'):
            directory = Path(temporary)
            result = effects.reconcile('aero', policy.policy(8388608), directory=directory, connect=lambda: x11)
            self.assertTrue(result['transitions'])
            self.assertEqual(result['engine'], 'picom')
            self.assertEqual(calls, [('xfwm', False), ('spawn', directory)])
            self.assertEqual(json.loads((directory / 'picom.json').read_text()), {'pid': 12345, 'started': '123', 'owner': 77})
            self.assertFalse(json.loads((directory / 'status.json').read_text())['physical_gpu_verified'])

    def test_an_existing_compositor_is_not_replaced_or_competed_with(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'owned_state', return_value=None), patch.object(effects, 'stop_owned'), patch.object(effects, 'xfwm') as xfwm, patch.object(effects, 'wait_owner', return_value=42), patch.object(effects, 'spawn') as spawn:
            x11 = Mock(owner=Mock(return_value=42))
            result = effects.reconcile('aero', policy.policy(8388608), directory=Path(temporary), connect=lambda: x11)
            self.assertEqual(result['engine'], 'external')
            self.assertFalse(result['transitions'])
            spawn.assert_not_called(); xfwm.assert_not_called()

    def test_existing_owned_engine_is_reused_and_failure_falls_back_without_a_restart_loop(self):
        for current in ({'pid': 12345, 'started': '123', 'owner': 77}, None):
            with self.subTest(current=current), tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'owned_state', return_value=current), patch.object(effects, 'stop_owned') as stop, patch.object(effects, 'xfwm') as xfwm, patch.object(effects, 'wait_owner', return_value=0), patch.object(effects.Path, 'is_file', return_value=True), patch.object(effects.os, 'access', return_value=True), patch.object(effects, 'spawn', side_effect=OSError('Unavailable')) as spawn:
                x11 = Mock(owner=Mock(return_value=77 if current else 0))
                result = effects.reconcile('aero', policy.policy(8388608), directory=Path(temporary), connect=lambda: x11)
                if current:
                    self.assertTrue(result['transitions']); spawn.assert_not_called(); stop.assert_not_called(); xfwm.assert_not_called()
                else:
                    self.assertFalse(result['transitions']); self.assertEqual(result['engine'], 'xfwm4')
                    self.assertEqual(xfwm.call_args_list[0].args, (False,)); self.assertEqual(xfwm.call_args_list[-1].args, (True,))
                    spawn.assert_called_once()

    def test_glass_reuses_xfwm_selection_instead_of_switching_it_off(self):
        for owner, requested, expected in ((0, 'glass', True), (77, 'glass', True), (77, 'off', False)):
            with self.subTest(owner=owner, requested=requested), tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'stop_owned'), patch.object(effects, 'xfwm') as xfwm, patch.object(effects, 'spawn') as spawn:
                x11 = Mock(owner=Mock(return_value=owner), wm_owner=Mock(return_value=77))
                result = effects.reconcile(requested, policy.policy(8388608), directory=Path(temporary), connect=lambda: x11)
                self.assertEqual(result['engine'], 'xfwm4' if expected else 'none')
                xfwm.assert_called_once_with(expected); spawn.assert_not_called()

    def test_off_and_low_budget_preserve_a_foreign_compositor_and_its_preference(self):
        for requested in ('off', 'glass', 'aero'):
            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(effects, 'stop_owned'), patch.object(effects, 'xfwm') as xfwm, patch.object(effects, 'spawn') as spawn:
                x11 = Mock(owner=Mock(return_value=42), wm_owner=Mock(return_value=77))
                result = effects.reconcile(requested, policy.policy(524288), directory=Path(temporary), connect=lambda: x11)
                self.assertEqual(result['engine'], 'external')
                self.assertFalse(result['transitions']); xfwm.assert_not_called(); spawn.assert_not_called()

    def test_no_saved_user_choice_leaves_a_personal_compositor_unchanged(self):
        with patch.object(effects, 'read_state', return_value=''), patch.object(effects, 'state_directory') as directory, patch.object(effects, 'xfwm') as xfwm:
            self.assertEqual(effects.reconcile()['engine'], 'unchanged')
            directory.assert_not_called(); xfwm.assert_not_called()

    def test_two_displays_do_not_share_process_ownership_or_a_blocking_lock(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'XDG_STATE_HOME': temporary, 'DISPLAY': ':91'}):
            first = effects.state_directory()
            with patch.dict(os.environ, {'DISPLAY': ':92'}):
                second = effects.state_directory()
            self.assertNotEqual(first, second)
            self.assertEqual(first.stat().st_mode & 0o777, 0o700)
            with (first / '.lock').open('w') as lock, patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                connect = Mock()
                with self.assertRaisesRegex(ValueError, 'Başka bir efekt'):
                    effects.reconcile('aero', policy.policy(8388608), directory=first, connect=connect)
                connect.assert_not_called()

    def test_fifo_lock_or_log_is_rejected_without_waiting_for_a_peer(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            os.mkfifo(directory / 'picom.log')
            with self.assertRaises((OSError, ValueError)):
                effects.spawn(directory)
            os.mkfifo(directory / '.lock')
            with patch.dict(os.environ, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), self.assertRaises((OSError, ValueError)):
                effects.reconcile('off', policy.policy(524288), directory=directory)

    def test_other_desktop_wayland_no_display_and_root_never_start_a_compositor(self):
        for uid, env in ((0, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE'}), (1000, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'KDE'}), (1000, {'DISPLAY': ':999', 'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'wayland'}), (1000, {'XDG_CURRENT_DESKTOP': 'XFCE'})):
            with self.subTest(uid=uid, env=env), patch.dict(os.environ, env, clear=True), patch.object(effects.os, 'getuid', return_value=uid), patch.object(effects, 'spawn') as spawn, patch.object(effects, 'state_directory') as directory:
                result = effects.reconcile('aero', policy.policy(8388608))
                self.assertFalse(result['transitions']); spawn.assert_not_called(); directory.assert_not_called()

    def test_pid_identity_checks_uid_fixed_argv_zombie_and_starttime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); process = root / '12345'; process.mkdir()
            fields = ['S'] + ['0'] * 18 + ['98765'] + ['0'] * 10
            (process / 'stat').write_text('12345 (picom) ' + ' '.join(fields))
            (process / 'cmdline').write_bytes(b'/usr/bin/picom\0--config\0/usr/share/oguzdows/picom.conf\0')
            self.assertEqual(effects.identity(12345, root), '98765')
            for args in (b'/usr/bin/picom\0--config\0/home/user/custom.conf\0', b'/usr/bin/python3\0somebody.py\0'):
                (process / 'cmdline').write_bytes(args)
                self.assertIsNone(effects.identity(12345, root))
            self.assertIsNone(effects.identity(None, root)); self.assertIsNone(effects.identity(1, root))
            with patch.object(effects.os, 'getuid', return_value=process.stat().st_uid + 1):
                self.assertIsNone(effects.identity(12345, root))

    def test_stale_pid_symlink_fifo_and_nonobject_state_cannot_target_any_process(self):
        for data in ({'pid': 99999, 'started': 'wrong', 'owner': 77}, [], None, {'pid': os.getpid()}, 'link', 'fifo'):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); path = directory / 'picom.json'
                if data == 'link': path.symlink_to('/proc/self/stat')
                elif data == 'fifo': os.mkfifo(path)
                else: path.write_text(json.dumps(data))
                with patch.object(effects, 'identity', return_value='other'), patch.object(effects.os, 'kill') as kill:
                    effects.stop_owned(directory)
                    kill.assert_not_called()
                self.assertFalse(path.exists())

    def test_stop_only_signals_the_validated_owned_pid_with_sigterm(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(effects, 'owned_state', return_value={'pid': 12345, 'started': 'old', 'owner': 77}), patch.object(effects, 'identity', return_value=None), patch.object(effects.os, 'kill') as kill, patch.object(effects.os, 'waitpid', side_effect=ChildProcessError):
            effects.stop_owned(Path(temporary))
            kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_spawn_uses_absolute_argv_and_log_not_shell_daemon_or_user_config(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(effects.os, 'posix_spawn', return_value=12345) as spawn:
            self.assertEqual(effects.spawn(Path(temporary)), 12345)
            self.assertEqual(spawn.call_args.args[:2], ('/usr/bin/picom', ['/usr/bin/picom', '--config', '/usr/share/oguzdows/picom.conf']))
            self.assertTrue(spawn.call_args.kwargs['setsid'])
            self.assertEqual((Path(temporary) / 'picom.log').stat().st_mode & 0o777, 0o600)

    def test_config_keeps_reading_opaque_and_excludes_dock_from_fading(self):
        config = (ROOT / 'system/usr/share/oguzdows/picom.conf').read_text()
        for value in ('active-opacity = 1.0', 'inactive-opacity = 1.0', 'frame-opacity = 1.0', 'use-damage = true', 'fading = true', 'fade-delta = 10', "window_type = 'dock'", "window_type = 'desktop'", 'backend = "xrender"'):
            self.assertIn(value, config)
        self.assertNotIn('blur-method =', config); self.assertNotIn('experimental-backends', config)
        css = (ROOT / 'system/usr/share/themes/OguzDows/gtk-3.0/dock.css').read_text()
        self.assertNotIn('@keyframes', css); self.assertIn('border-radius: 12px', css)


if __name__ == '__main__':
    unittest.main()
