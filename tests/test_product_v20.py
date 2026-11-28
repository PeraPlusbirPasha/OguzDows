"""Current Akıncı product identity; immutable previous release receipts stay separate."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from support import ROOT, load

product_info = load('akinci_product_info_test', 'system/usr/lib/oguzdows/product_info.py')
config = load('akinci_pc_overlay_test', 'scripts/configure.py')


class AkinciProductTests(unittest.TestCase):
    def test_shared_actual_product_android_and_installer_identity(self):
        product = product_info.product_info()
        self.assertEqual((product['version'], product['codename'], product['release_tag']), ('2.0', 'Akıncı', 'v2.0'))
        self.assertEqual((product['mobile_version_name'], product['mobile_version_code']), ('2.0.0-akinci', 20))
        self.assertEqual(product['bridge_protocol'], 1)
        self.assertIn('/download/v2.0/' + product['mobile_apk'], product['apk_url'])
        installer = yaml.safe_load((ROOT / 'installer/branding/branding.desc').read_text())
        self.assertEqual(installer['strings']['version'], product['version'])
        gradle = (ROOT / 'mobile/android/app/build.gradle.kts').read_text()
        for expected in ('system/usr/share/oguzdows/product.json', 'product["mobile_version_code"]', 'product["mobile_version_name"]'):
            self.assertIn(expected, gradle)
        self.assertNotIn('0.4.0-connected', gradle)
        platform = (ROOT / 'mobile/android/app/src/main/java/org/oguzdows/mobile/PlatformState.java').read_text()
        self.assertIn('state.put("version", BuildConfig.VERSION_NAME)', platform)
        for name in ('package.json', 'package-lock.json'):
            self.assertEqual(json.loads((ROOT / 'mobile/preview' / name).read_text())['version'], '2.0.0')
        cli = subprocess.run(['python3', str(ROOT / 'system/usr/lib/oguzdows/bridge.py'), '--version'],
                             capture_output=True, text=True, timeout=5, check=True)
        self.assertIn('2.0 · Akıncı · protocol 1', cli.stdout)

    def test_pc_overlay_contains_real_bridge_identity_help_and_exact_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'pc'; config.configure('amd64', output)
            overlay = output / 'includes.chroot'
            for name in ('bridge.py', 'bridge_core.py', 'bridge_capture.py', 'product_info.py'):
                path = 'usr/lib/oguzdows/' + name
                self.assertEqual((overlay / path).read_bytes(), (ROOT / 'system' / path).read_bytes())
            self.assertEqual((overlay / 'usr/share/oguzdows/product.json').read_bytes(),
                             (ROOT / 'system/usr/share/oguzdows/product.json').read_bytes())
            self.assertEqual((overlay / 'usr/share/doc/oguzdows/AKINCI-BAGLANTI.md').read_bytes(),
                             (ROOT / 'docs/AKINCI-BAGLANTI.md').read_bytes())
            self.assertTrue((overlay / 'usr/share/applications/oguzdows-bridge.desktop').is_file())
        smoke = (ROOT / 'tests/smoke-iso-target.py').read_text()
        for name in ('bridge_core.py', 'product.json', 'AKINCI-BAGLANTI.md'):
            self.assertIn(name, smoke)

    def test_release_workflows_keep_mandatory_mobile_acceptance_and_source_input(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/main.yml').read_text())
        on = workflow.get('on', workflow.get(True))
        self.assertEqual(on['workflow_dispatch']['inputs']['mobile_evidence_run']['default'], '')
        job = str(workflow['jobs']['release'])
        self.assertIn('${{ inputs.mobile_evidence_run }}', job)
        self.assertIn('--mobile-run', job)
        self.assertIn('aapt apksigner', job)
        mobile = (ROOT / '.github/workflows/mobile-emulator.yml').read_text()
        self.assertLess(mobile.index('mobile/scripts/acceptance.py'), mobile.index('mobile/scripts/package-mobile.py'))
        self.assertIn('system/usr/share/oguzdows/product.json', mobile)
        self.assertNotIn('0.4.0-connected-debug.apk', mobile)
        self.assertNotIn('release upload', mobile)


if __name__ == '__main__':
    unittest.main()
