"""Kaynak/API sınırları ve planlar; gerçek Mutter/KWin çalışması iddiası yok."""
import json
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

from support import ROOT
import aero
import desktop_decoration as decoration
import desktop_gnome as gnome
import desktop_plasma as plasma
import desktop_runtime as runtime
import desktop_state as state
from resource_policy import policy


class AeroPlanTests(unittest.TestCase):
    def prefs(self, **changes):
        return {**state.DEFAULTS, 'effects': 'aero', 'motion': 'spring', 'blur': True, **changes}

    def test_low_resources_or_no_explicit_aero_never_probe_or_enable(self):
        for resources in (policy(0), policy(524288), policy(2097152), policy(8388608, nomodeset=True), policy(8388608, graphics=False)):
            with self.subTest(resources=resources), patch.object(aero, 'probe') as probe:
                result = aero.plan(self.prefs(snap_animation=True), resources)
                self.assertEqual(result['config'], aero.BASE)
                self.assertFalse(any(result[key] for key in ('blur_configured', 'spring_configured', 'snap_configured')))
                probe.assert_not_called()
        with patch.object(aero, 'probe') as probe:
            aero.plan(self.prefs(effects='glass'), policy(8388608)); probe.assert_not_called()

    def test_migration_preserves_legacy_aero_without_new_gpu_work(self):
        with patch.object(aero, 'probe') as probe:
            result = aero.plan(self.prefs(motion='smooth', blur=False), policy(8388608))
            self.assertEqual(result['config'], aero.BASE); probe.assert_not_called()
            result = aero.plan(self.prefs(motion='reduced', blur=False), policy(8388608))
            self.assertEqual(result['config'].name, 'still.conf'); probe.assert_not_called()

    def test_glx_and_version_gates_select_only_fixed_supported_recipes(self):
        cases = [({'major': 12, 'accelerated': False}, {}, 'picom.conf', False, False),
                 ({'major': 8, 'accelerated': True}, {}, 'picom.conf', False, False),
                 ({'major': 9, 'accelerated': True}, {}, 'blur9.conf', True, False),
                 ({'major': 11, 'accelerated': True}, {'snap_animation': True}, 'blur.conf', True, False),
                 ({'major': 12, 'accelerated': True}, {}, 'full.conf', True, True),
                 ({'major': 12, 'accelerated': True}, {'snap_animation': True}, 'full-snap.conf', True, True),
                 ({'major': 12, 'accelerated': True}, {'blur': False}, 'motion.conf', False, True),
                 ({'major': 12, 'accelerated': True}, {'blur': False, 'snap_animation': True}, 'snap.conf', False, True),
                 ({'major': 9, 'accelerated': True}, {'motion': 'reduced'}, 'blur9-still.conf', True, False)]
        for capability, extra, filename, blur, spring in cases:
            with self.subTest(capability=capability, extra=extra):
                result = aero.plan(self.prefs(**extra), policy(8388608), capability)
                self.assertIn(result['config'], aero.CONFIGS)
                self.assertEqual(result['config'].name, filename)
                self.assertEqual(result['blur_configured'], blur); self.assertEqual(result['spring_configured'], spring)
                self.assertEqual(result['snap_configured'], spring and extra.get('snap_animation', False))

    def test_probe_checks_real_direct_acceleration_and_software_override(self):
        version = subprocess.CompletedProcess([], 0, 'v12.5\n')
        report = subprocess.CompletedProcess([], 0, 'direct rendering: Yes\nAccelerated: yes\nOpenGL renderer: GPU')
        with patch.object(aero.subprocess, 'run', side_effect=[version, report]) as run:
            self.assertEqual(aero.probe(), {'major': 12, 'accelerated': True})
            self.assertTrue(all(call.kwargs['timeout'] == 4 and not call.kwargs['check'] for call in run.call_args_list))
        for text in ('direct rendering: Yes\nAccelerated: yes\nllvmpipe', 'direct rendering: No\nAccelerated: yes', ''):
            with self.subTest(text=text), patch.object(aero.subprocess, 'run', side_effect=[version, subprocess.CompletedProcess([], 0, text)]):
                self.assertFalse(aero.probe()['accelerated'])
        with patch.dict(os.environ, {'LIBGL_ALWAYS_SOFTWARE': 'true'}), patch.object(aero.subprocess, 'run', side_effect=[version, report]):
            self.assertFalse(aero.probe()['accelerated'])
        with patch.object(aero.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 4)):
            self.assertEqual(aero.probe(), {'major': 0, 'accelerated': False})

    def test_modern_rules_retain_exclusions_in_new_api_not_ignored_old_keys(self):
        for name in ('motion', 'full', 'snap', 'full-snap'):
            text = (ROOT / 'system/usr/share/oguzdows/compositor' / (name + '.conf')).read_text()
            self.assertIn('rules = (', text)
            self.assertNotIn('shadow-exclude =', text); self.assertNotIn('blur-background-exclude =', text)
            self.assertIn("window_type = 'desktop'\"; shadow = false; blur-background = false", text)
            self.assertIn("window_type = 'dock'\"; shadow = false; fade = false", text)
            self.assertEqual('triggers = [ "geometry" ]' in text, name in ('snap', 'full-snap'))
            self.assertIn('user-response', text); self.assertNotIn('eval(', text)
        for name in ('blur', 'blur-still', 'blur9', 'blur9-still', 'still'):
            text = (ROOT / 'system/usr/share/oguzdows/compositor' / (name + '.conf')).read_text()
            self.assertNotIn('animations =', text); self.assertNotIn('window_shader', text)


class RuntimeTests(unittest.TestCase):
    def test_actual_shell_is_detected_before_installed_xfce_tools(self):
        for text, expected in (('ubuntu:GNOME:XFCE', 'gnome'), ('KDE:XFCE', 'kde'), ('Plasma', 'kde'), ('XFCE', 'xfce'), ('', 'unknown')):
            self.assertEqual(runtime.current({'XDG_CURRENT_DESKTOP': text}), expected)

    def test_no_graphical_session_root_and_unknown_shell_are_never_changed(self):
        for uid, env in ((0, {'DISPLAY': ':98', 'XDG_CURRENT_DESKTOP': 'GNOME'}), (1000, {}), (1000, {'DISPLAY': ':98'})):
            with patch.object(runtime.os, 'getuid', return_value=uid), patch.dict(os.environ, env, clear=True), self.assertRaises(ValueError):
                runtime.normal_session()

    def test_native_tools_do_not_fall_through_to_another_shell(self):
        spawn = Mock(); commands = []
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'binary', side_effect=lambda names: commands.append(names[0]) or '/usr/bin/' + names[0]):
            runtime.native_control('audio', 'gnome', spawn=spawn)
        self.assertEqual(spawn.call_args.args[1], ['/usr/bin/gnome-control-center', 'sound'])
        self.assertNotIn('pavucontrol', commands)
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'binary', return_value=None), self.assertRaises(RuntimeError):
            runtime.native_control('widgets', 'gnome', spawn=spawn)
        with self.assertRaises(ValueError): runtime.native_control('sh -c anything', spawn=spawn)

    def test_plasma_operations_use_fixed_native_panel_and_widget_apis(self):
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'dbus') as bus:
            runtime.native_control('widgets', 'kde'); self.assertEqual(bus.call_args.args[3], 'toggleWidgetExplorer')
            runtime.native_control('panels', 'kde'); self.assertEqual(bus.call_args.args[3], 'evaluateScript')
            self.assertIn('showConfigurationInterface()', bus.call_args.args[-1][0])
            self.assertNotIn('remove(', bus.call_args.args[-1][0])
            runtime.native_control('apps', 'gnome'); self.assertEqual(bus.call_args.args[3], 'ShowApplications')

    def test_plasma_snap_loads_only_fixed_bridge_and_uses_versioned_script_paths_not_maximize_toggle(self):
        for major in (5, 6):
            replies = [(7,)] + ([RuntimeError('UnknownObject')] if major == 5 else []) + [(), ()]
            with self.subTest(major=major), patch.object(runtime, 'normal_session'), patch.object(runtime, 'current', return_value='kde'), patch.object(state, 'locked'), patch.object(runtime, 'dbus', side_effect=replies) as bus:
                runtime.snap('restore')
                calls = bus.call_args_list
                self.assertEqual(calls[0].args[-1], ('/usr/share/oguzdows/kwin/snap.js', 'oguzdows-snap-v1'))
                self.assertEqual(calls[-1].args[-1], ('OguzDows Snap restore',))
                self.assertEqual(calls[-2].args[1], '/7' if major == 5 else '/Scripting/Script7')
                self.assertNotIn('Window Maximize', str(calls))
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'current', return_value='kde'), patch.object(state, 'locked'), patch.object(runtime, 'dbus', side_effect=[(-1,), ()]) as bus:
            runtime.snap('maximize')
            self.assertEqual(bus.call_count, 2)
        with patch.object(runtime, 'normal_session'), patch.object(runtime, 'current', return_value='kde'), patch.object(state, 'locked'), patch.object(runtime, 'dbus', side_effect=[(9,), RuntimeError('AccessDenied')]) as bus:
            with self.assertRaisesRegex(RuntimeError, 'AccessDenied'): runtime.snap('left')
            self.assertEqual(bus.call_count, 2)

    def test_installation_gate_only_queries_existing_actions_and_does_not_start_apps(self):
        with patch.object(runtime, 'dbus', side_effect=[(True, '', [False]), (True, '', [True])]) as bus:
            self.assertTrue(runtime.installation_busy())
            self.assertTrue(all(call.args[3] == 'Describe' for call in bus.call_args_list))
        with patch.object(runtime, 'dbus', side_effect=RuntimeError('no owner')):
            self.assertFalse(runtime.installation_busy())


class BackendPlanTests(unittest.TestCase):
    def prefs(self, **changes): return {**state.DEFAULTS, **changes}

    def test_false_and_empty_gsettings_user_variants_are_not_absent_values(self):
        backend = object.__new__(gnome.GnomeSettings)
        setting = Mock()
        backend.setting = Mock(return_value=(setting, 'fixture'))
        for token, value in (('snap-animation', False), ('glass-enabled', False), ('picture-uri', '')):
            # GLib.Variant.__bool__ değeri açar; saf Mock bunu taklit etmez.
            class FalsyVariant:
                def __bool__(self): return False
                def unpack(self): return value
            setting.get_user_value.return_value = FalsyVariant()
            self.assertEqual(backend.read(token), value)
        setting.get_user_value.return_value = None
        self.assertIsNone(backend.read('snap-animation'))

    def test_gnome_membership_not_whole_extension_list_and_native_accent_is_nearest(self):
        backend = Mock(supports=lambda token: token != 'native-accent')
        result = gnome.changes(self.prefs(effects='aero', blur=True, motion='spring'), policy(8388608), backend)
        self.assertTrue(result['extension-enabled']); self.assertTrue(result['glass-enabled'])
        self.assertNotIn('native-accent', result)
        self.assertEqual(gnome.KEYS['extension-enabled'][1], 'enabled-extensions')
        self.assertEqual(gnome.closest_accent('#3584e4'), 'blue')
        result = gnome.changes(self.prefs(effects='aero', blur=True, motion='spring'), policy(524288), backend)
        self.assertFalse(result['glass-enabled']); self.assertEqual(result['motion'], 'reduced')
        self.assertTrue(result['extension-enabled'])  # yerel araç köprüsü kalır
        for token in result:
            self.assertIn(token, gnome.KEYS)
        self.assertFalse(any('panel' in token or 'binding' in token for token in result))

    def test_kwin_reconfigure_tolerates_only_a_bounded_transient_effects_object_gap(self):
        attempts = 0
        def bus(_destination, path, _interface, method, *_args):
            nonlocal attempts
            if path == '/Effects' and method == 'loadEffect':
                attempts += 1
                if attempts == 1: raise RuntimeError('org.freedesktop.DBus.Error.UnknownObject')
            return (True,) if method == 'isEffectLoaded' else ()
        with patch.object(plasma, 'dbus', side_effect=bus), patch.object(plasma, 'notify_settings'), patch.object(plasma.time, 'sleep') as sleep:
            result = plasma.refresh(self.prefs(effects='aero', blur=True, motion='spring'), policy(8388608))
            self.assertTrue(result['blur_active']); self.assertTrue(result['spring_active'])
            self.assertEqual(sleep.call_count, 1)
        with patch.object(plasma, 'dbus', side_effect=[(), RuntimeError('AccessDenied')]), patch.object(plasma.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'AccessDenied'):
                plasma.refresh(self.prefs(), policy(8388608))
            sleep.assert_not_called()
        with patch.object(plasma, 'dbus', side_effect=[(), RuntimeError('UnknownObject')]), patch.object(plasma.time, 'monotonic', side_effect=[0, 3]), patch.object(plasma.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'UnknownObject'):
                plasma.refresh(self.prefs(), policy(8388608))
            sleep.assert_not_called()

    def test_plasma5_and_6_use_real_distinct_effect_ids_and_restoreable_tokens(self):
        for major in (5, 6):
            result = plasma.changes(self.prefs(effects='aero', blur=True, motion='spring'), policy(8388608), major, True)
            self.assertEqual(result['blur'], 'true')
            self.assertEqual(result['scale5' if major == 5 else 'scale'], 'false')
            self.assertEqual(result['fading5' if major == 5 else 'fading'], 'false')
            self.assertEqual(result['decoration-library'], 'org.kde.kwin.aurorae')
            self.assertTrue(result['decoration-theme'].startswith('__aurorae__svg__oguzdows-glass-'))
            self.assertLessEqual(set(result), plasma.PlasmaSettings.keys)
            self.assertFalse(any('panel' in token or 'plasmoid' in token for token in result))
        low = plasma.changes(self.prefs(effects='aero', blur=True, motion='spring'), policy(524288), 5, True)
        self.assertEqual(low['blur'], 'false'); self.assertEqual(low['aero-motion'], 'false')
        self.assertEqual(low['duration'], '0'); self.assertNotIn('decoration-library', low)

    def test_kconfig_nested_groups_no_unsupported_notify_and_readback(self):
        values, commands = {}, []
        def execute(argv):
            commands.append(argv)
            args = argv[1:]; key = args[args.index('--key') + 1]
            if argv[0].endswith('kreadconfig5'):
                return subprocess.CompletedProcess(argv, 0, values.get(key, args[args.index('--default') + 1]) + '\n')
            if '--delete' in args: values.pop(key, None)
            else: values[key] = args[-1]
            return subprocess.CompletedProcess(argv, 0, '')
        with patch.object(plasma, 'binary', side_effect=lambda names: '/usr/bin/' + ('kreadconfig5' if names[0].startswith('kread') else names[0])):
            backend = plasma.PlasmaSettings(execute)
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'XDG_CONFIG_HOME': temporary}):
            token = 'palette:Header][Inactive:BackgroundNormal'
            backend.write(token, '20,30,40'); self.assertEqual(backend.read(token), '20,30,40')
            self.assertEqual(backend.arguments(token)[2:6], ['--group', 'Colors:Header', '--group', 'Inactive'])
            backend.write(token, None); self.assertIsNone(backend.read(token))
            self.assertNotIn('--notify', sum(commands, []))
            self.assertEqual(backend.major, 5)
        with self.assertRaises(ValueError): backend.write('arbitrary-file', 'command')
        with self.assertRaises(ValueError): backend.write('theme', 'x\ny')

    def test_palette_is_from_installed_scheme_and_selection_remains_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text = ''.join(f'[Colors:{group}]\n' + ''.join(f'{key}=80,90,100\n' for key in plasma.COLOR_KEYS) + '\n' for group in plasma.COLOR_GROUPS)
            (root / 'BreezeLight.colors').write_text(text)
            for accent, foreground in (('#ffffff', '0,0,0'), ('#000000', '255,255,255')):
                result = plasma.palette(self.prefs(accent=accent), root)
                self.assertEqual(result['palette:Selection:ForegroundNormal'], foreground)
                self.assertEqual(result['palette:Window:BackgroundNormal'], '80,90,100')
                self.assertEqual(result['palette:Window:DecorationFocus'], '255,255,255' if accent == '#ffffff' else '0,0,0')
                self.assertIn('effect:Disabled:ContrastAmount', result)
            with self.assertRaises(ValueError): plasma.palette(self.prefs(appearance='dark'), root)
            (root / 'BreezeLight.colors').write_text('[Colors:Window]\nBackgroundNormal=999,0,0\n')
            with self.assertRaises(ValueError): plasma.palette(self.prefs(), root)

    def test_wallpaper_values_are_data_and_cannot_escape_fixed_plasma_script(self):
        row = {'id': 12, 'plugin': 'org.kde.image', 'image': 'file:///x/\";throw 2;//'}
        with patch.object(plasma, 'dbus') as bus, patch.object(plasma, 'wallpaper_state', return_value=[row]):
            plasma.write_wallpapers([row])
            script = bus.call_args.args[-1][0]
            self.assertIn(json.dumps([row]), script)
            self.assertEqual(bus.call_args.args[3], 'evaluateScript')
        for rows in ([], [dict(row, id=True)], [dict(row, plugin='x;exec()')], [row, row], [dict(row, extra='x')]):
            with self.subTest(rows=rows), self.assertRaises(ValueError): plasma.validate_wallpapers(rows)

    def test_aurorae_discovery_matches_the_real_kde5_and_6_library_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for major, relative in ((5, 'x86_64-linux-gnu/qt5/plugins/org.kde.kdecoration2/kwin5_aurorae.so'),
                                    (6, 'aarch64-linux-gnu/qt6/plugins/org.kde.kdecoration3/org.kde.kwin.aurorae.so')):
                self.assertFalse(decoration.available(major, root))
                library = root / relative; library.parent.mkdir(parents=True)
                library.touch()
                self.assertTrue(decoration.available(major, root))
            self.assertFalse(decoration.available(7, root))
        source = (ROOT / 'system/usr/lib/oguzdows/maintenance.py').read_text()
        self.assertNotIn("'kwin-decoration-aurorae'", source)

    def test_original_aurorae_frames_have_alpha_mask_and_opaque_controls(self):
        for dark in (False, True):
            svg = ET.fromstring(decoration.decoration_svg('#36b6c5', dark))
            ids = {element.get('id') for element in svg.iter()}
            self.assertIn('mask-center', ids); self.assertIn('decoration-top', ids)
            self.assertIn('fill-opacity=".82"', ET.tostring(svg, encoding='unicode'))
            for action in ('close', 'minimize', 'maximize', 'restore', 'help'):
                text = decoration.button_svg(action, '#36b6c5', dark)
                ET.fromstring(text); self.assertNotIn('fill-opacity', text)
        with self.assertRaises(ValueError): decoration.decoration_svg('bad" onclick="x', False)
        with self.assertRaises(ValueError): decoration.install('../evil', '#36b6c5', False)
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'XDG_DATA_HOME': temporary}):
            name = plasma.theme_name(self.prefs())
            self.assertEqual(decoration.install(name, '#36b6c5', False), '__aurorae__svg__' + name)
            path = Path(temporary) / 'aurorae/themes' / name
            self.assertTrue((path / (name + 'rc')).is_file())
            self.assertIn('PaddingLeft=16', (path / (name + 'rc')).read_text())
            self.assertFalse(any(file.suffix == '.qml' for file in path.iterdir()))

    def test_gnome_abi_assets_and_kwin_metadata_are_explicit_not_web_mockups(self):
        for suite, expected in (('bookworm', ['43', '44']), ('trixie', ['45', '46', '47', '48'])):
            self.assertEqual(gnome.extension_metadata(suite)[1], expected)
        schema = ET.parse(ROOT / 'system/usr/share/glib-2.0/schemas/org.oguzdows.desktop.gschema.xml')
        defaults = {key.get('name'): key.findtext('default') for key in schema.findall('.//key')}
        self.assertEqual(defaults['glass-enabled'], 'false'); self.assertEqual(defaults['snap-animation'], 'false')
        metadata = json.loads((ROOT / 'system/usr/share/kwin/effects/oguzdows-aero/metadata.json').read_text())
        self.assertFalse(metadata['KPlugin']['EnabledByDefault'])
        core = (ROOT / 'system/usr/share/oguzdows/gnome/core.js').read_text()
        self.assertIn('Shell.BlurMode.BACKGROUND', core)
        self.assertNotIn('setInterval', core); self.assertNotIn('completed_map(', core)
        self.assertNotIn('Eval', (ROOT / 'system/usr/lib/oguzdows/desktop_runtime.py').read_text())


if __name__ == '__main__':
    unittest.main()
