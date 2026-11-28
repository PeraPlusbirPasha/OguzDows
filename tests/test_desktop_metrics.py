"""GTK gerektirmeyen gerçek C sayaç testini hedef derleyicide çalıştırır."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT


class NativeMetricsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C derleyicisi yok; CI yerel sayaçları derler')
    def test_proc_deltas_are_computed_by_real_native_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); binary = root / 'metrics-test'; fixture = root / 'proc'; fixture.mkdir()
            result = subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT / 'native'), str(ROOT / 'tests/native-metrics.c'), str(ROOT / 'native/metrics.c'),
                '-o', str(binary), '-lm'], capture_output=True, text=True, check=False, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary), str(fixture)], capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('native metrics:', result.stdout)

    def test_no_js_python_webview_polling_or_unbounded_history_in_monitor(self):
        source = (ROOT / 'native/monitor.c').read_text()
        self.assertIn('#define HISTORY 90', source)
        self.assertIn('g_timeout_add_seconds(interval', source)
        self.assertIn('!minimized && !obscured && !paused', source)
        self.assertIn('g_source_remove(timer)', source)
        for word in ('webkit', 'curl', 'python', 'system(', 'popen('):
            self.assertNotIn(word, source.lower() if word != 'python' else source)  # açıklama dışında Python motoru yok
        script = (ROOT / 'scripts/build-desktop.sh').read_text()
        for forbidden in ('-march=native', '-mfpu=neon'):
            self.assertNotIn(forbidden, '\n'.join(line for line in script.splitlines() if not line.startswith('#')))
        self.assertIn('-Werror', script); self.assertIn('-fPIE -pie', script)


if __name__ == '__main__':
    unittest.main()
