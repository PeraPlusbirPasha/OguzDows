"""Source-only contracts. NOT an Android SDK build, emulator or device test."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android/app/src/main'
NS = '{http://schemas.android.com/apk/res/android}'


class NativeSourceContracts(unittest.TestCase):
    def setUp(self):
        self.manifest = ET.parse(ANDROID / 'AndroidManifest.xml').getroot()
        self.home = (ANDROID / 'java/org/oguzdows/mobile/HomeActivity.java').read_text()

    def test_only_unknown_source_special_permission_is_requested(self):
        permissions = {p.attrib[NS + 'name'] for p in self.manifest.findall('uses-permission')}
        self.assertEqual(permissions, {'android.permission.REQUEST_INSTALL_PACKAGES'})
        # No INTERNET, mic, SMS, contacts, location, screen capture or all-files permission.

    def test_home_is_user_selectable_and_has_no_boot_receiver(self):
        categories = {p.attrib[NS + 'name'] for p in self.manifest.iter('category')}
        self.assertIn('android.intent.category.HOME', categories)
        self.assertIn('android.intent.category.LAUNCHER', categories)
        self.assertFalse(list(self.manifest.iter('receiver')))
        self.assertIn('Settings.ACTION_HOME_SETTINGS', self.home)
        self.assertIn('roles.createRequestRoleIntent', self.home)

    def test_assistant_services_require_system_signature_permission(self):
        services = self.manifest.findall('application/service')
        self.assertEqual(len(services), 3)
        for service in services:
            self.assertEqual(service.attrib[NS + 'permission'], 'android.permission.BIND_VOICE_INTERACTION')
        recognition = (ANDROID / 'java/org/oguzdows/mobile/RifkiRecognitionService.java').read_text()
        self.assertIn('ERROR_INSUFFICIENT_PERMISSIONS', recognition)
        self.assertNotIn('AudioRecord', recognition)
        self.assertNotIn('MediaRecorder', recognition)
        voice = (ANDROID / 'java/org/oguzdows/mobile/RifkiVoiceService.java').read_text()
        self.assertIn('setDisabledShowContext', voice)
        self.assertIn('SHOW_WITH_ASSIST', voice)
        self.assertIn('SHOW_WITH_SCREENSHOT', voice)
        metadata = ET.parse(ANDROID / 'res/xml/rifki_voice.xml').getroot()
        self.assertEqual(metadata.attrib[NS + 'supportsLaunchVoiceAssistFromKeyguard'], 'false')
        self.assertEqual(metadata.attrib[NS + 'recognitionService'], 'org.oguzdows.mobile.RifkiRecognitionService')

    def test_file_provider_is_not_exported_and_exposes_only_private_inbox(self):
        provider = self.manifest.find('application/provider')
        self.assertEqual(provider.attrib[NS + 'exported'], 'false')
        self.assertEqual(provider.attrib[NS + 'authorities'], '${applicationId}.apk')
        paths = ET.parse(ANDROID / 'res/xml/apk_paths.xml').getroot()
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].tag, 'cache-path')
        self.assertEqual(paths[0].attrib['path'], 'apk-inbox/')
        self.assertIn('FileProvider.getUriForFile', self.home)
        self.assertIn('FLAG_GRANT_READ_URI_PERMISSION', self.home)
        self.assertNotIn('FLAG_GRANT_WRITE_URI_PERMISSION', self.home)

    def test_apk_copy_inspection_and_system_installer_are_bounded_and_separate(self):
        for text in ('32 * 1024 * 1024', '64 * 1024', 'retained >= 3', 'count > 10000',
                     'getPackageArchiveInfo', 'GET_SIGNING_CERTIFICATES', 'getApkContentsSigners',
                     'Build.SUPPORTED_ABIS', 'minSdkVersion', 'canRequestPackageInstalls',
                     'ACTION_MANAGE_UNKNOWN_APP_SOURCES', 'Sistem yükleyicisine geç'):
            self.assertIn(text, self.home)
        self.assertNotIn('getAbsolutePath(), "application/vnd', self.home)
        self.assertNotRegex(self.home, r'Runtime\.getRuntime|ProcessBuilder|\bexec\(')
        self.assertNotIn('android.permission.INSTALL_PACKAGES', {
            p.attrib[NS + 'name'] for p in self.manifest.findall('uses-permission')})

    def test_application_does_not_override_platform_identity_or_package_google_services(self):
        app = self.manifest.find('application')
        self.assertEqual(app.attrib[NS + 'label'], 'OğuzDows Mobile')
        self.assertEqual(app.attrib[NS + 'allowBackup'], 'false')
        self.assertEqual(app.attrib[NS + 'usesCleartextTraffic'], 'false')
        self.assertNotIn('ro.build', self.home)
        self.assertFalse(list(ROOT.rglob('*.apk')))
        self.assertFalse(list(ROOT.rglob('*.img')))

    def test_native_and_browser_model_scope_is_explicitly_not_a_completed_rom(self):
        parity = json.loads((ROOT / 'feature-parity.json').read_text())
        for key in ('rom_built', 'native_apk_built', 'physical_device_tested', 'live_generative_model_tested'):
            self.assertIs(parity[key], False)
        self.assertEqual(len(parity['workbench']), 16)
        self.assertEqual(len(parity['other_seven_new_functions']), 7)
        self.assertEqual(len({f['id'] for f in parity['workbench']}), 16)
        local = (ANDROID / 'java/org/oguzdows/mobile/RifkiText.java').read_text()
        self.assertIn('kural tabanlı', local)
        self.assertIn('Üretken model burada bağlı değil', local)

    def test_daily_actions_delegate_to_system_without_call_sms_or_settings_write_privileges(self):
        for token in ('Intent.ACTION_DIAL', 'Intent.ACTION_SENDTO', 'Uri.fromParts("smsto"',
                      'Settings.Panel.ACTION_VOLUME', 'Settings.Panel.ACTION_WIFI',
                      'Settings.ACTION_DISPLAY_SETTINGS', 'CATEGORY_APP_CONTACTS',
                      'CATEGORY_APP_CALENDAR', 'INTENT_ACTION_STILL_IMAGE_CAMERA'):
            self.assertIn(token, self.home)
        self.assertNotIn('Intent.ACTION_CALL', self.home)
        self.assertNotIn('SmsManager', self.home)
        self.assertNotIn('Settings.System.put', self.home)
        self.assertIn('ordinaryNumber', self.home)
        self.assertIn('setError', self.home)

    def test_resources_are_well_formed_and_nazar_not_standard_power_glyph(self):
        for path in ANDROID.rglob('*.xml'):
            with self.subTest(path=path):
                ET.parse(path)
        nazar = ET.parse(ANDROID / 'res/drawable/nazar.xml').getroot()
        self.assertGreaterEqual(len(nazar.findall('path')), 5)
        self.assertTrue((ANDROID / 'res/drawable/rifki.webp').is_file())
        gradle = (ROOT / 'android/app/build.gradle.kts').read_text()
        self.assertRegex(gradle, r'minSdk\s*=\s*29')
        self.assertRegex(gradle, r'targetSdk\s*=\s*35')


if __name__ == '__main__':
    unittest.main()
