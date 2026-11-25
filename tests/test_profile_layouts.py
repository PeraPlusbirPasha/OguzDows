"""İki panel / simge iskelesi için tür, geri alma ve kişisel ayar sınırları."""
import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import ROOT, load
from xfconf_fixture import Xfconf

profiles = load('new_layout_profiles', 'system/usr/lib/oguzdows/profiles.py')


class LayoutTests(unittest.TestCase):
    def test_mac_and_ubuntu_have_real_top_and_dock_arrays_not_just_button_changes(self):
        for name, position, mode in (('mac', 'p=10;x=0;y=0', '0'), ('gnome', 'p=7;x=0;y=0', '1')):
            values = {(ch, path): value for ch, path, _kind, value in profiles.settings(name)}
            self.assertEqual(values['xfce4-panel', '/panels'], ['1', '90'])
            self.assertEqual(values['xfce4-panel', '/panels/panel-1/position'], 'p=9;x=0;y=0')
            self.assertEqual(values['xfce4-panel', '/panels/panel-90/position'], position)
            self.assertEqual(values['xfce4-panel', '/panels/panel-90/mode'], mode)
            self.assertNotIn('2', values['xfce4-panel', '/panels/panel-1/plugin-ids'])
            self.assertIn('95' if name == 'mac' else '2', values['xfce4-panel', '/panels/panel-90/plugin-ids'])
            self.assertEqual(values['xfce4-panel', '/plugins/plugin-2/show-labels'], 'false')
            for identifier, desktop in profiles.LAUNCHERS.items():
                self.assertTrue((ROOT / 'system/usr/share/applications' / desktop).is_file())
                self.assertEqual(values['xfce4-panel', f'/plugins/plugin-{identifier}'], 'launcher' if name == 'gnome' else None)
        mac = dict((key, value) for _ch, key, _kind, value in profiles.settings('mac'))
        self.assertEqual(mac['/general/button_layout'], 'CHM|')
        self.assertEqual(mac['/general/title_alignment'], 'center')

    def test_arrays_round_trip_and_unrelated_panels_and_settings_survive(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        xfconf.values['xfce4-panel', '/panels'] = ['1', '23']
        xfconf.values['xfce4-panel', '/panels/panel-23/size'] = '33'
        xfconf.values['xsettings', '/Gtk/FontName'] = 'Kişisel Yazı 12'
        original = dict(xfconf.values)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            profiles.apply('mac', directory, xfconf)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels'], ['1', '23', '90'])
            profiles.apply('gnome', directory, xfconf)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels'], ['1', '23', '90'])
            profiles.apply('oguzdows', directory, xfconf)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels'], ['1', '23'])
            profiles.restore(directory, xfconf)
            self.assertEqual(xfconf.values, original)
            self.assertTrue(any('--force-array' in command for command in xfconf.calls))
            self.assertTrue(all(command[0] == 'xfconf-query' for command in xfconf.calls))

    def test_personal_plugins_and_nonowned_dock_survive_single_panel_styles(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        xfconf.values['xfce4-panel', '/panels'] = ['1', '90']
        xfconf.values['xfce4-panel', '/panels/panel-1/plugin-ids'] = ['1', '2', '37', '3', '4', '5', '6', '7']
        xfconf.values['xfce4-panel', '/plugins/plugin-37'] = 'notes'
        xfconf.values['xfce4-panel', '/plugins/plugin-90'] = 'user-plugin'
        xfconf.values['xfce4-panel', '/panels/panel-90/size'] = '42'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('xfce', root, xfconf)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels'], ['1', '90'])
            self.assertIn('37', xfconf.values['xfce4-panel', '/panels/panel-1/plugin-ids'])
            self.assertEqual(xfconf.values['xfce4-panel', '/plugins/plugin-37'], 'notes')
            self.assertEqual(xfconf.values['xfce4-panel', '/plugins/plugin-90'], 'user-plugin')
            self.assertFalse((root / 'layout-v2').exists())
            with self.assertRaisesRegex(ValueError, 'üzerine yazılmadı'):
                profiles.apply('mac', root, xfconf)

    def test_releasing_our_dock_does_not_claim_a_future_personal_dock(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('mac', root, xfconf)
            profiles.apply('xfce', root, xfconf)
            self.assertFalse((root / 'layout-v2').exists())
            xfconf.values['xfce4-panel', '/plugins/plugin-90'] = 'user-plugin'
            with self.assertRaisesRegex(ValueError, 'üzerine yazılmadı'):
                profiles.apply('gnome', root, xfconf)
        xfconf = Xfconf(profiles.settings('oguzdows'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('mac', root, xfconf)
            profiles.restore(root, xfconf)
            self.assertFalse((root / 'layout-v2').exists())

    def test_legacy_scalar_backup_is_kept_and_new_keys_are_only_appended_once(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        legacy = [['xfce4-panel', '/panels/panel-1/length', 'uint', '82'],
                  ['xsettings', '/Net/ThemeName', 'string', 'MyTheme']]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backup = root / 'before-first-change.json'
            backup.write_text(json.dumps(legacy))
            profiles.apply('mac', root, xfconf)
            profiles.apply('gnome', root, xfconf)
            values = json.loads(backup.read_text())
            self.assertEqual(values[:2], legacy)
            self.assertEqual(sum(row[1] == '/panels/panel-1/length' for row in values), 1)
            profiles.restore(root, xfconf)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels/panel-1/length'], '82')
            self.assertEqual(xfconf.values['xsettings', '/Net/ThemeName'], 'MyTheme')

    def test_light_mac_dock_keeps_dark_text_on_a_light_background_across_theme_switch(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('mac', root, xfconf)
            rgba = 'xfce4-panel', '/panels/panel-90/background-rgba'
            self.assertGreater(float(xfconf.values[rgba][0]), .9)
            before = xfconf.values['xfce4-panel', '/panels/panel-90/position']
            profiles.set_appearance('dark', root, xfconf)
            self.assertLess(float(xfconf.values[rgba][0]), .2)
            profiles.set_appearance('light', root, xfconf)
            self.assertGreater(float(xfconf.values[rgba][0]), .9)
            self.assertEqual(xfconf.values['xfce4-panel', '/panels/panel-90/position'], before)

    def test_reserved_user_panel_is_rejected_before_any_mutation(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        xfconf.values['xfce4-panel', '/plugins/plugin-90'] = 'user-plugin'
        original = dict(xfconf.values)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'üzerine yazılmadı'):
                profiles.apply('mac', Path(temporary), xfconf)
        self.assertEqual(xfconf.values, original)
        self.assertTrue(all(len(command) == 5 for command in xfconf.calls))

    def test_late_failure_rolls_back_arrays_and_new_launcher_nodes(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        original = dict(xfconf.values)
        def execute(command):
            if command[4] == '/panels' and len(command) > 5 and '90' in command:
                return subprocess.CompletedProcess(command, 1, '', '')
            return xfconf(command)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(RuntimeError):
                profiles.apply('mac', root, execute)
            self.assertFalse((root / 'selected').exists())
            self.assertFalse((root / 'layout-v2').exists())
            self.assertEqual(xfconf.values, original)

    def test_bad_array_backup_and_duplicate_keys_are_rejected_without_commands(self):
        bad = [
            [['xfce4-panel', '/panels', 'int-array', 'not-array']],
            [['xfce4-panel', '/panels', 'int-array', [1]]],
            [['xfce4-panel', '/panels', 'int-array', ['1']]] * 2,
            [['xfce4-panel', '/panels', 'int-array', []]],
        ]
        for value in bad:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / 'before-first-change.json').write_text(json.dumps(value))
                with patch.object(profiles, 'run') as execute, self.assertRaises(ValueError):
                    profiles.restore(root, execute)
                execute.assert_not_called()

    def test_malformed_cli_array_cannot_be_mistaken_for_scalar_success(self):
        for text in ('1\n2', 'Value is an array with 3 items:\n\n1\n2', 'Value is an array with 0 items:\n\n'):
            execute = lambda command: subprocess.CompletedProcess(command, 0, text, '')
            with self.assertRaises(ValueError):
                profiles.read_property('xfce4-panel', '/panels', 'int-array', execute)

    def test_real_xfconf_six_decimal_output_is_normalized_and_nonfinite_rejected(self):
        execute = lambda command: subprocess.CompletedProcess(command, 0, '100.000000\n', '')
        self.assertEqual(profiles.read_property('xfce4-panel', '/panels/panel-1/length', 'double', execute), '100')
        execute = lambda command: subprocess.CompletedProcess(command, 0, 'Value is an array with 4 items:\n\n0.090000\n0.160000\n0.250000\n1.000000\n', '')
        self.assertEqual(profiles.read_property('xfce4-panel', '/color', 'double-array', execute), ['0.09', '0.16', '0.25', '1'])
        for value in ('nan', 'inf', '-inf', '0,94'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                profiles.decimal_value(value)

    def test_failed_legacy_restore_rolls_back_same_property_despite_old_uint_type(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        original = dict(xfconf.values)
        def execute(command):
            if len(command) > 5 and command[4] == '/Net/ThemeName' and command[-1] == 'fail':
                return subprocess.CompletedProcess(command, 1, '', '')
            return xfconf(command)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            values = [['xfce4-panel', '/panels/panel-1/length', 'uint', '77'],
                      ['xsettings', '/Net/ThemeName', 'string', 'fail']]
            (root / 'before-first-change.json').write_text(json.dumps(values))
            with self.assertRaises(RuntimeError):
                profiles.restore(root, execute)
            self.assertEqual(xfconf.values, original)

    def test_real_panel_smoke_rejects_non_ci_or_missing_private_bus_before_work(self):
        for env in ({'CI': 'false', 'DBUS_SESSION_BUS_ADDRESS': 'fake'}, {'CI': 'true'}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'must-not-exist'
                result = subprocess.run([sys.executable, str(ROOT / 'tests/smoke-profiles.py'), '--output', str(output)],
                                        env={**env, 'PATH': os.environ.get('PATH', '')}, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('tek kullanımlık CI', result.stderr)
                self.assertFalse(output.exists())

    def test_explicit_reload_is_separate_and_never_uses_kill_or_root(self):
        commands = []
        profiles.reload_panels(lambda command: commands.append(command) or subprocess.CompletedProcess(command, 0))
        self.assertEqual(commands, [['xfce4-panel', '--restart']])
        with self.assertRaises(RuntimeError):
            profiles.reload_panels(lambda command: subprocess.CompletedProcess(command, 1))
        source = (ROOT / 'system/usr/lib/oguzdows/welcome.py').read_text()
        reload = source.split('    def reload_panels(', 1)[1].split('    def change_appearance', 1)[0]
        self.assertIn('dialog.set_default_response(Gtk.ResponseType.CANCEL)', reload)
        self.assertIn('self.external_installing', reload)

    def test_themes_are_independent_and_effect_preference_does_not_move_panels(self):
        xfconf = Xfconf(profiles.settings('oguzdows'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles.apply('gnome', root, xfconf)
            before = xfconf.values['xfce4-panel', '/panels/panel-90/position']
            profiles.set_appearance('dark', root, xfconf)
            self.assertEqual(xfconf.values['xsettings', '/Net/ThemeName'], 'OguzDowsGnomeDark')
            profiles.set_effects('glass', root, xfconf, resources={'compositing': False})
            self.assertEqual(profiles.effect_selection(root), 'glass')
            self.assertEqual(xfconf.values['xfwm4', '/general/use_compositing'], 'false')
            self.assertEqual(xfconf.values['xfce4-panel', '/panels/panel-90/position'], before)


if __name__ == '__main__':
    unittest.main()
