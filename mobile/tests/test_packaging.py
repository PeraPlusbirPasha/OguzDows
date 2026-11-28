"""Packaging synthetic files exercises integrity gates, not SDK/emulator acceptance."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_acceptance import synthetic_build, synthetic_device

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'mobile/scripts'))
spec = importlib.util.spec_from_file_location('mobile_release_package_test', ROOT / 'mobile/scripts/package-mobile.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class MobilePackagingTests(unittest.TestCase):
    def fixture(self, root):
        product = json.loads((ROOT / 'system/usr/share/oguzdows/product.json').read_text())
        path = root / 'system/usr/share/oguzdows/product.json'; path.parent.mkdir(parents=True)
        path.write_text(json.dumps(product))
        (root / 'docs').mkdir(); shutil.copyfile(ROOT / 'docs/AKINCI-BAGLANTI.md', root / 'docs/AKINCI-BAGLANTI.md')
        (root / 'mobile/preview/dist').mkdir(parents=True)
        (root / 'mobile/preview/dist/index.html').write_text('<html>Synthetic web packaging fixture</html>')
        shutil.copyfile(ROOT / 'mobile/ASSETS.md', root / 'mobile/ASSETS.md')
        build = synthetic_build(); device, frame = synthetic_device(); device['passed'] = True
        for index, item in enumerate(build['assembled']):
            file = root / 'mobile/android' / item['file']; file.parent.mkdir(parents=True, exist_ok=True)
            content = b'Synthetic APK bytes: ' + str(index).encode(); file.write_bytes(content)
            item.update(bytes=len(content), sha256=pack.hashlib.sha256(content).hexdigest())
        # A benign ordering change must not swap the main/test/fixture APKs.
        build['assembled'].reverse()
        metadata = root / 'mobile/android/app/build/outputs/apk/debug/output-metadata.json'
        metadata.write_text(json.dumps(dict(applicationId='org.oguzdows.mobile', elements=[dict(versionCode=20, versionName='2.0.0-akinci')])))
        output = root / 'test-results/mobile'; output.mkdir(parents=True)
        for name, data in [('build.json', build), ('emulator/evidence.json', device),
                           ('acceptance.json', dict(source_sha='a' * 40, passed=True))]:
            path = output / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data))
        (output / 'emulator/connected-real-mediaprojection.jpg').write_bytes(frame)
        return output

    def run_package(self, root):
        def command(args, **kwargs):
            if args[0] == 'git': return 'a' * 40 + '\n'
            self.assertEqual(args[1:4], ['verify', '--verbose', '--print-certs'])
            return 'Signer #1 certificate SHA-256 digest: ' + 'b' * 64 + '\n'
        with patch.object(pack, 'ROOT', root), patch.dict(pack.os.environ, {'ANDROID_HOME': str(root / 'synthetic-sdk')}), \
                patch.object(pack.subprocess, 'check_output', side_effect=command), patch('builtins.print'):
            pack.package()

    def test_accepted_actual_bytes_shared_version_web_and_all_three_signers_are_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = self.fixture(root); self.run_package(root)
            receipt = json.loads((output / 'release-package.json').read_text())
            self.assertEqual(receipt['version_code'], 20)
            self.assertEqual(len(receipt['certificate_sha256']), 3)
            self.assertFalse(receipt['production_signing'])
            self.assertTrue((output / 'OguzDows-Web-2.0-Akinci.tar.gz').is_file())
            main = next(item for item in receipt['files'] if item['file'].endswith('-debug.apk'))
            self.assertEqual((output / 'package' / main['file']).read_bytes(), b'Synthetic APK bytes: 0')

    def test_old_actual_apk_version_and_incomplete_emulator_acceptance_cannot_package(self):
        for what in ('version', 'native', 'gate'):
            with self.subTest(what=what), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); output = self.fixture(root)
                if what == 'version':
                    path = root / 'mobile/android/app/build/outputs/apk/debug/output-metadata.json'
                    data = json.loads(path.read_text()); data['elements'][0]['versionName'] = '0.4.0-connected'
                elif what == 'native':
                    path = output / 'emulator/evidence.json'; data = json.loads(path.read_text()); data['tests'].pop()
                else:
                    path = output / 'acceptance.json'; data = dict(source_sha='a' * 40, passed=False)
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): self.run_package(root)
                self.assertFalse((output / 'package').exists())

    def test_apk_changed_after_acceptance_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = self.fixture(root)
            (root / 'mobile/android/app/build/outputs/apk/debug/app-debug.apk').write_bytes(b'altered')
            with self.assertRaises(ValueError): self.run_package(root)
            self.assertFalse((output / 'release-package.json').exists())


if __name__ == '__main__':
    unittest.main()
