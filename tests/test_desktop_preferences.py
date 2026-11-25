"""Paylaşılan tercihlerin oturum sınırı; arka uçlar burada açıkça taklittir."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT
import desktop_gnome as gnome
import desktop_preferences as preferences
import desktop_runtime as runtime
import desktop_state as state
import aero
import effects
import profiles
from resource_policy import policy


class FakeGnome:
    name = 'gnome'
    keys = set(gnome.KEYS)
    def __init__(self): self.values = {}; self.calls = []
    def supports(self, key): return key != 'native-accent'
    def validate(self, key, value):
        if key not in self.keys: raise ValueError(key)
    def read(self, key): return self.values.get(key)
    def write(self, key, value): self.calls.append((key, value)); self.values[key] = value


class SharedPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        environment = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config'),
            'XDG_STATE_HOME': str(self.root / 'state'), 'XDG_CURRENT_DESKTOP': 'GNOME', 'DISPLAY': ':97'})
        environment.start(); self.addCleanup(environment.stop)
        self.backend = FakeGnome()
        for target, replacement in ((runtime, 'normal_session'), (runtime, 'installation_busy')):
            mocked = patch.object(target, replacement, return_value=False); mocked.start(); self.addCleanup(mocked.stop)
        for mocked in (patch.object(gnome, 'GnomeSettings', return_value=self.backend),
                       patch.object(gnome, 'status', return_value={'extension_active': False})):
            mocked.start(); self.addCleanup(mocked.stop)

    def test_update_is_native_gnome_only_and_revision_receipt_is_private(self):
        with patch.object(profiles, 'set_shared') as xfce:
            result = preferences.update_and_apply({'appearance': 'dark', 'effects': 'aero', 'blur': True}, policy(8388608))
            xfce.assert_not_called()
        self.assertEqual(result['revision'], 1); self.assertFalse(result['physical_gpu_verified'])
        self.assertEqual(self.backend.values['gtk-theme'], 'OguzDows')
        self.assertTrue(self.backend.values['extension-enabled'])
        self.assertTrue(self.backend.values['glass-enabled'])
        saved = state.load(); self.assertEqual(saved['appearance'], 'dark')
        self.assertEqual(state.config_path().stat().st_mode & 0o777, 0o600)
        receipt = state.state_directory() / 'gnome-applied.json'
        self.assertEqual(json.loads(receipt.read_text()), {'revision': 1, 'compositing': True})
        self.assertFalse((state.state_directory() / 'kde-settings.json').exists())

    def test_invalid_preference_or_installation_busy_never_writes_native_settings(self):
        with self.assertRaises(ValueError): preferences.update_and_apply({'blur': 'true'}, policy(8388608))
        self.assertEqual(self.backend.calls, [])
        with patch.object(runtime, 'installation_busy', return_value=True), self.assertRaisesRegex(RuntimeError, 'Kurucu'):
            preferences.update_and_apply({'blur': True}, policy(8388608))
        self.assertEqual(self.backend.calls, []); self.assertFalse(state.config_path().exists())

    def test_missing_shared_settings_does_not_touch_a_new_session(self):
        with patch.object(runtime, 'normal_session') as guard, patch.object(preferences, 'apply_current') as apply:
            result = preferences.session(policy(8388608))
            self.assertIn('korunuyor', result['message']); guard.assert_not_called(); apply.assert_not_called()

    def test_same_revision_keeps_external_changes_but_budget_is_rechecked(self):
        preferences.update_and_apply({'effects': 'aero', 'blur': True}, policy(8388608))
        self.backend.values['gtk-theme'] = 'a-personal-theme'; before = len(self.backend.calls)
        preferences.session(policy(8388608)); self.assertEqual(len(self.backend.calls), before)
        preferences.session(policy(524288)); self.assertFalse(self.backend.values['glass-enabled'])
        self.assertFalse(self.backend.values['animations'])
        self.assertGreater(len(self.backend.calls), before)

    def test_compare_restore_preserves_personal_key_and_does_not_reapply_same_revision(self):
        self.backend.values.update({'gtk-theme': 'before-theme', 'extension-enabled': False})
        preferences.update_and_apply({'appearance': 'dark', 'effects': 'aero', 'blur': True}, policy(8388608))
        self.backend.values['gtk-theme'] = 'after-theme'
        result = preferences.restore()
        self.assertIn('gtk-theme', result['preserved_external_changes'])
        self.assertEqual(self.backend.values['gtk-theme'], 'after-theme')
        self.assertFalse(self.backend.values['extension-enabled'])
        calls = len(self.backend.calls); preferences.session(policy(8388608))
        self.assertEqual(len(self.backend.calls), calls)
        preferences.update_and_apply({'appearance': 'light'}, policy(8388608))
        self.assertEqual(self.backend.values['gtk-theme'], 'OguzDowsLight')

    def test_persistence_failures_restore_exact_native_values_receipts_and_revision(self):
        atomic = state.atomic_json
        for stage in ('receipt', 'preferences', 'after-replace'):
            with self.subTest(stage=stage):
                preferences.update_and_apply({'appearance': 'light'}, policy(8388608))
                self.backend.values['gtk-theme'] = 'PersonalBeforeFailedApply'
                old_config = state.read_json(state.config_path())
                receipt = state.state_directory() / 'gnome-applied.json'
                old_receipt = state.read_json(receipt)
                journal = state.state_directory() / 'gnome-settings.json'
                old_journal = state.read_json(journal)
                old_native = dict(self.backend.values)
                failed = False
                def write(path, value):
                    nonlocal failed
                    target = receipt if stage == 'receipt' else state.config_path()
                    if not failed and Path(path) == target and value.get('revision') == old_config['revision'] + 1:
                        failed = True
                        if stage == 'after-replace': atomic(path, value)
                        raise OSError('CI storage unavailable')
                    atomic(path, value)
                with patch.object(state, 'atomic_json', side_effect=write), self.assertRaisesRegex(OSError, 'CI storage'):
                    preferences.update_and_apply({'appearance': 'dark', 'blur': True}, policy(8388608))
                self.assertTrue(failed)
                self.assertEqual(self.backend.values, old_native)
                self.assertEqual(state.read_json(state.config_path()), old_config)
                self.assertEqual(state.read_json(receipt), old_receipt)
                self.assertEqual(state.read_json(journal), old_journal)

    def test_failed_first_shared_save_keeps_personal_theme_and_absent_files_absent(self):
        self.backend.values.update({'gtk-theme': 'PreExistingPersonalTheme', 'extension-enabled': False})
        atomic = state.atomic_json
        def fail_config(path, value):
            if Path(path) == state.config_path(): raise OSError('CI first save unavailable')
            atomic(path, value)
        with patch.object(state, 'atomic_json', side_effect=fail_config), self.assertRaises(OSError):
            preferences.update_and_apply({'appearance': 'dark'}, policy(8388608))
        self.assertEqual(self.backend.read('gtk-theme'), 'PreExistingPersonalTheme')
        self.assertFalse(self.backend.read('extension-enabled'))
        self.assertFalse(state.config_path().exists())
        self.assertFalse((state.state_directory() / 'gnome-applied.json').exists())
        self.assertEqual(state.read_json(state.state_directory() / 'gnome-settings.json'), {})

    def test_deferred_xfce_undo_restores_native_surface_and_only_changed_markers(self):
        from xfconf_fixture import Xfconf
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); backend = Xfconf(profiles.settings('oguzdows'))
            profiles.apply('windows11', directory, backend)
            backend.values['xsettings', '/Net/ThemeName'] = 'PersonalBeforeApply'
            before = dict(backend.values)
            markers = {name: (directory / name).read_text() if (directory / name).exists() else None
                       for name in ('selected', 'appearance', 'effects', 'layout-v2')}
            undo = []
            profiles.set_shared({**state.DEFAULTS, 'appearance': 'dark'}, directory, backend, policy(8388608), undo=undo)
            self.assertNotEqual(before, backend.values); self.assertEqual(len(undo), 1)
            undo[0]()
            self.assertEqual(backend.values, before)
            self.assertEqual(markers, {name: (directory / name).read_text() if (directory / name).exists() else None for name in markers})

    def test_deferred_xfce_rollback_preserves_intervening_external_changes(self):
        from xfconf_fixture import Xfconf
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); backend = Xfconf(profiles.settings('oguzdows'))
            profiles.apply('windows11', directory, backend)
            before = dict(backend.values)
            marker = directory / 'appearance'; marker.write_text('light\n\n')
            undo = []
            profiles.set_shared({**state.DEFAULTS, 'appearance': 'dark'}, directory, backend, policy(8388608), undo=undo)
            backend.values['xsettings', '/Net/ThemeName'] = 'ExternalAfterApply'
            (directory / 'effects').write_text('external-after-apply\n')
            undo[0]()
            before['xsettings', '/Net/ThemeName'] = 'ExternalAfterApply'
            self.assertEqual(backend.values, before)
            self.assertEqual(marker.read_text(), 'light\n\n')
            self.assertEqual((directory / 'effects').read_text(), 'external-after-apply\n')

    def test_current_protocol_status_is_honest_about_unsaved_applications(self):
        result = preferences.status()
        self.assertEqual(result['desktop'], 'gnome')
        self.assertIn('Kaydedip', result['session_note'])
        self.assertNotIn('physical_gpu_verified', result)

    def test_xfce_glass_is_selected_only_after_capability_and_rolls_surface_back_on_engine_failure(self):
        prefs = {**state.DEFAULTS, 'effects': 'aero', 'blur': True, 'motion': 'spring'}
        for accelerated, running in ((False, False), (True, True), (True, False)):
            with self.subTest(accelerated=accelerated, running=running), patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'XFCE'}), patch.object(profiles, 'selection', return_value=('windows11', 'light')), patch.object(profiles, 'set_shared') as shared, patch.object(aero, 'probe', return_value={'major': 12, 'accelerated': accelerated}), patch('desktop_material.install', return_value='OguzDowsAeroGlassUser-0123456789ab') as material, patch.object(effects, 'reconcile', return_value={'engine': 'picom' if running else 'xfwm4', 'blur_configured': running, 'message': 'test'}) as reconcile:
                preferences.apply_current(prefs, self.root, policy(8388608))
                self.assertEqual(shared.call_args_list[0].args[0]['blur'], accelerated)
                self.assertEqual(material.call_count, 2 if accelerated and not running else 1)
                self.assertEqual(material.call_args_list[0].kwargs['identifier'], 'windows11')
                self.assertEqual(material.call_args_list[0].kwargs['glass'], accelerated)
                self.assertEqual(shared.call_count, 2 if accelerated and not running else 1)
                if accelerated and not running:
                    self.assertTrue(shared.call_args.kwargs['surface_only'])
                    self.assertFalse(shared.call_args.args[0]['blur'])
                self.assertEqual(reconcile.call_args.kwargs['capability']['accelerated'], accelerated)

    def test_shared_apply_releases_picom_before_enabling_xfwm(self):
        from xfconf_fixture import Xfconf
        backend = Xfconf(profiles.settings('oguzdows'))
        backend.values['xfwm4', '/general/use_compositing'] = 'false'
        owner = {'value': 88}; events = []
        owned = {'pid': 32145, 'started': 'old', 'owner': 88}
        x11 = Mock(owner=lambda: owner['value'], wm_owner=lambda: 77)
        directory = self.root / 'effects'; directory.mkdir()
        surface, reconcile = profiles.set_shared, effects.reconcile
        def native(command):
            if '-s' in command and command[2:5] == ['xfwm4', '-p', '/general/use_compositing']:
                enabled = command[command.index('-s') + 1] == 'true'
                if enabled and owner['value'] == 88:
                    raise RuntimeError('Fixture: Picom hâlâ seçim sahibiyken Xfwm başlatıldı')
            return backend(command)
        def stop(_directory):
            events.append('stop-picom'); owner['value'] = 0
        def xfwm(enabled):
            events.append('xfwm:' + str(enabled).lower())
            native(['xfconf-query', '-c', 'xfwm4', '-p', '/general/use_compositing', '-t', 'bool', '-s', str(enabled).lower()])
            owner['value'] = 77 if enabled else 0
        with patch('desktop_material.install', return_value='OguzDowsXPUser-test'), patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'XFCE', 'XDG_SESSION_TYPE': 'x11'}), patch.object(effects.os, 'getuid', return_value=1000), patch.object(profiles, 'state_directory', return_value=self.root / 'profiles'), patch.object(profiles, 'set_shared', side_effect=lambda prefs, **kwargs: surface(prefs, directory=self.root / 'profiles', execute=native, **kwargs)), patch.object(effects, 'reconcile', side_effect=lambda effect, resources, **kwargs: reconcile(effect, resources, directory=directory, connect=lambda: x11, **kwargs)), patch.object(effects, 'owned_state', side_effect=lambda _directory: owned if owner['value'] == 88 else None), patch.object(effects, 'stop_owned', side_effect=stop), patch.object(effects, 'xfwm', side_effect=xfwm), patch.object(effects, 'wait_owner', side_effect=lambda *_args: owner['value']):
            result = preferences.apply_current({**state.DEFAULTS, 'effects': 'glass'}, self.root, policy(8388608))
        self.assertEqual(events, ['stop-picom', 'xfwm:true'])
        self.assertEqual(result['engine'], 'xfwm4')
        self.assertEqual(owner['value'], 77)

    def test_shared_surface_never_rewrites_a_personal_compositor_preference(self):
        from xfconf_fixture import Xfconf
        for effect in ('off', 'glass', 'aero'):
            for memory in (524288, 8388608):
                for before in ('false', 'true'):
                    with self.subTest(effect=effect, memory=memory, before=before), tempfile.TemporaryDirectory() as temporary:
                        backend = Xfconf(profiles.settings('oguzdows'))
                        backend.values['xfwm4', '/general/use_compositing'] = before
                        profiles.set_shared({**state.DEFAULTS, 'effects': effect}, Path(temporary), backend, policy(memory))
                        self.assertEqual(backend.values['xfwm4', '/general/use_compositing'], before)
                        self.assertFalse(any(command[2:5] == ['xfwm4', '-p', '/general/use_compositing'] and '-s' in command
                                             for command in backend.calls))

    def test_layout_apply_can_leave_compositor_ownership_to_the_runtime(self):
        from xfconf_fixture import Xfconf
        for identifier in profiles.PROFILES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); backend = Xfconf(profiles.settings('oguzdows'))
                backend.values['xfwm4', '/general/use_compositing'] = 'true'
                profiles.apply(identifier, directory, backend, manage_compositor=False)
                self.assertEqual(backend.values['xfwm4', '/general/use_compositing'], 'true')
                self.assertFalse(any(command[2:5] == ['xfwm4', '-p', '/general/use_compositing'] and '-s' in command
                                     for command in backend.calls))
        source = (ROOT / 'system/usr/lib/oguzdows/welcome.py').read_text()
        self.assertIn('desktop_preferences.update_and_apply({}, profile=identifier)', source)

    def test_all_six_xfce_layouts_keep_arrays_shortcuts_and_controls_in_shared_surface_changes(self):
        from test_profile_layouts import Xfconf
        for identifier in profiles.PROFILES:
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); backend = Xfconf(profiles.settings('oguzdows'))
                profiles.apply(identifier, directory, backend)
                before = {key: value for key, value in backend.values.items() if key[1].endswith(('plugin-ids', '/position')) or key[1] in ('/panels', '/general/button_layout', '/Gtk/CursorThemeName')}
                profiles.set_shared({**state.DEFAULTS, 'effects': 'aero', 'blur': True, 'appearance': 'dark', 'motion': 'reduced'}, directory, backend, policy(8388608))
                self.assertEqual(before, {key: backend.values[key] for key in before})
                self.assertEqual(backend.values['xsettings', '/Gtk/EnableAnimations'], 'false')
                self.assertEqual(backend.values['xfce4-panel', '/panels/panel-1/enter-opacity'], '100')
                self.assertEqual(backend.values['xfce4-panel', '/panels/panel-1/leave-opacity'], '100')

    def test_session_hooks_have_one_ordered_xfce_effect_entry_and_never_logout_or_replace_shell(self):
        autostart = ROOT / 'system/etc/xdg/autostart'
        self.assertIn('Hidden=true', (autostart / 'oguzdows-effects.desktop').read_text())
        script = (ROOT / 'system/usr/lib/oguzdows/session.sh').read_text()
        self.assertLess(script.index('wallpapers.py'), script.index('desktop_center.py'))
        self.assertEqual(script.count('--effects-session'), 1)
        native = (autostart / 'oguzdows-native-desktop.desktop').read_text()
        self.assertIn('OnlyShowIn=GNOME;KDE;', native)
        self.assertNotIn('OnlyShowIn=XFCE', native)
        text = (ROOT / 'system/usr/lib/oguzdows/desktop_preferences.py').read_text()
        for forbidden in ('killall', '--replace', 'gnome-session-quit', 'xfce4-session-logout', 'systemctl'):
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
