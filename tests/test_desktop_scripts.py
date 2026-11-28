"""JavaScript source/API contracts, not native compositor or performance proof."""
import shutil
import subprocess
import unittest

from support import ROOT


class DesktopScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node yok; gerçek kabuk testleri CI içinde ayrı çalışır')
    def test_native_script_contracts_with_explicit_stubbed_apis(self):
        result = subprocess.run(['node', str(ROOT / 'tests/desktop-scripts.test.js')],
                                cwd=ROOT, capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('not real compositor evidence', result.stdout)


if __name__ == '__main__':
    unittest.main()
