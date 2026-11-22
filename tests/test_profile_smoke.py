"""Gerçek panel testi eklenti kaybını geçerli saymaz; temizlik kendi grubuyla sınırlı."""
import hashlib
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from support import ROOT, load

smoke = load('profile_smoke_helpers', 'tests/smoke-profiles.py')


class ProfileSmokeTests(unittest.TestCase):
    def test_preflight_requires_all_packaged_plugins_and_dock_launchers(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, 'power-manager-plugin'):
                smoke.plugin_manifest(directory)
            plugins = ('whiskermenu', 'tasklist', 'separator', 'systray', 'pulseaudio',
                       'power-manager-plugin', 'clock', 'launcher')
            for name in plugins:
                (directory / (name + '.desktop')).write_text(name)
            manifest = smoke.plugin_manifest(directory)
            self.assertEqual(set(manifest), set(plugins))
            self.assertEqual(manifest['power-manager-plugin'], hashlib.sha256(b'power-manager-plugin').hexdigest())
            (directory / 'power-manager-plugin.desktop').unlink()
            with self.assertRaisesRegex(RuntimeError, 'eksik: power-manager-plugin\\.'):
                smoke.plugin_manifest(directory)

    def test_smoke_workflow_installs_every_external_plugin_used_by_the_real_skeleton(self):
        workflow = (ROOT / '.github/workflows/main.yml').read_text().split('      - name: Doğrulama araçları', 1)[1].split('      - name:', 1)[0]
        packages = set(workflow.replace('\\', '').split())
        self.assertTrue({'xfce4-panel', 'xfce4-whiskermenu-plugin', 'xfce4-power-manager-plugins',
                         'xfce4-pulseaudio-plugin', 'xfce4-settings', 'xfwm4'} <= packages)
        production = set((ROOT / 'packages/common.list').read_text().splitlines())
        self.assertIn('xfce4-power-manager-plugins', production)

    def test_cleanup_signals_only_its_own_new_process_group_and_reaps_parent(self):
        process = Mock(pid=41237)
        with patch.object(smoke.os, 'killpg') as killpg:
            smoke.stop_owned_process(process)
        self.assertEqual(killpg.call_args_list, [call(41237, signal.SIGTERM), call(41237, signal.SIGKILL)])
        self.assertEqual(process.wait.call_args_list, [call(timeout=4), call(timeout=4)])
        with patch.object(smoke.os, 'killpg') as killpg:
            smoke.stop_owned_process(None)
        killpg.assert_not_called()

    def test_cleanup_handles_already_exited_or_unresponsive_test_panel_without_masking_error(self):
        process = Mock(pid=41238)
        process.wait.side_effect = [subprocess.TimeoutExpired(['test-child'], 4), 0]
        with patch.object(smoke.os, 'killpg', side_effect=[None, ProcessLookupError()]) as killpg:
            smoke.stop_owned_process(process)
        self.assertEqual(killpg.call_args_list[-1], call(41238, signal.SIGKILL))
        self.assertEqual(process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
