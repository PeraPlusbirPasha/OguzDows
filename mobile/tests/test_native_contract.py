"""Source contracts only; native build/runtime results live in CI evidence, not these assertions."""
import hashlib
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android/app/src/main'
JAVA = ANDROID / 'java/org/oguzdows/mobile'
NS = '{http://schemas.android.com/apk/res/android}'


class NativeSourceContracts(unittest.TestCase):
    def setUp(self):
        self.manifest = ET.parse(ANDROID / 'AndroidManifest.xml').getroot()
        self.home = (JAVA / 'HomeActivity.java').read_text()

    def test_permissions_are_explicit_and_exclude_microphone_contacts_root_and_all_files(self):
        actual = {p.attrib[NS + 'name'].removeprefix('android.permission.')
                  for p in self.manifest.findall('uses-permission')}
        self.assertEqual(actual, {'INTERNET', 'MODIFY_AUDIO_SETTINGS', 'REQUEST_INSTALL_PACKAGES',
            'CALL_PHONE', 'READ_PHONE_STATE', 'SEND_SMS', 'RECEIVE_SMS', 'READ_SMS', 'RECEIVE_MMS',
            'RECEIVE_WAP_PUSH', 'POST_NOTIFICATIONS', 'USE_FULL_SCREEN_INTENT'})
        for denied in ('RECORD_AUDIO', 'READ_CONTACTS', 'READ_CALL_LOG', 'MANAGE_EXTERNAL_STORAGE',
                       'INSTALL_PACKAGES', 'WRITE_SECURE_SETTINGS', 'WRITE_SETTINGS', 'WRITE_SMS'):
            self.assertNotIn(denied, actual)
        feature = self.manifest.find('uses-feature')
        self.assertEqual(feature.attrib[NS + 'required'], 'false')

    def test_phone_sms_home_roles_have_platform_components_without_boot_or_fake_connection_service(self):
        home = self.manifest.find("application/activity[@" + NS + "name='.HomeActivity']")
        actions = {node.attrib[NS + 'name'] for node in home.iter('action')}
        categories = {node.attrib[NS + 'name'] for node in home.iter('category')}
        self.assertTrue({'android.intent.action.DIAL', 'android.intent.action.SENDTO'} <= actions)
        self.assertTrue({'android.intent.category.HOME', 'android.intent.category.LAUNCHER'} <= categories)
        services = {node.attrib[NS + 'name']: node for node in self.manifest.findall('application/service')}
        self.assertEqual(services['.OguzInCallService'].attrib[NS + 'permission'], 'android.permission.BIND_INCALL_SERVICE')
        self.assertEqual(services['.RespondViaMessageService'].attrib[NS + 'permission'], 'android.permission.SEND_RESPOND_VIA_MESSAGE')
        self.assertNotIn('BOOT_COMPLETED', ET.tostring(self.manifest).decode())
        self.assertNotIn('ConnectionService', ET.tostring(self.manifest).decode())
        self.assertIn('roles.createRequestRoleIntent', self.home)
        self.assertIn('TelephonyManager.ACTION_RESPOND_VIA_MESSAGE', (JAVA / 'RespondViaMessageService.java').read_text())
        for name in ('.CallActivity', '.SourceStoreActivity', '.InstalledAppsActivity', '.InstallReviewActivity'):
            activity = self.manifest.find("application/activity[@" + NS + "name='" + name + "']")
            self.assertEqual(activity.attrib[NS + 'exported'], 'false')

    def test_receivers_are_system_permission_protected_and_receipts_are_not_exported(self):
        receivers = {node.attrib[NS + 'name']: node for node in self.manifest.findall('application/receiver')}
        self.assertEqual(receivers['.SmsDeliverReceiver'].attrib[NS + 'permission'], 'android.permission.BROADCAST_SMS')
        self.assertEqual(receivers['.MmsDeliverReceiver'].attrib[NS + 'permission'], 'android.permission.BROADCAST_WAP_PUSH')
        self.assertEqual(receivers['.SmsStatusReceiver'].attrib[NS + 'exported'], 'false')
        sms = (JAVA / 'SmsController.java').read_text()
        self.assertIn('new Intent(context, SmsStatusReceiver.class)', sms)
        self.assertIn('FLAG_IMMUTABLE', sms)
        self.assertIn('FLAG_MUTABLE', sms)  # Explicit delivery target needs the real network PDU extras.

    def test_web_bridge_is_origin_and_main_frame_bound_and_remote_content_is_not_loaded(self):
        for token in ('WebViewAssetLoader', 'WebViewCompat.addWebMessageListener',
            'Collections.singleton(ORIGIN)', 'if (!isMainFrame', 'sourceOrigin.toString()',
            'setAllowFileAccess(false)', 'setAllowUniversalAccessFromFileURLs(false)',
            'MIXED_CONTENT_NEVER_ALLOW', 'request.deny()', 'Content-Security-Policy',
            "frame-src 'none'", 'raw.length() > 16384', 'WebMessageCompat.TYPE_STRING',
            'Bundled UI has no network access', '403'):
            self.assertIn(token, self.home)
        self.assertNotIn('addJavascriptInterface', self.home)
        self.assertNotRegex(self.home, r'Runtime\.getRuntime|ProcessBuilder|\bexec\(')
        self.assertIn('default: reply.error', self.home)
        self.assertNotIn('setWebContentsDebuggingEnabled(true)', self.home)

    def test_call_and_sms_require_native_consent_and_no_success_is_inferred_from_a_request(self):
        self.assertIn('telecom.placeCall', self.home)
        self.assertIn('Aramayı onayla', self.home)
        self.assertIn('PlatformState.role(this, RoleManager.ROLE_DIALER)', self.home)
        self.assertIn('PlatformState.granted(this, Manifest.permission.CALL_PHONE)', self.home)
        self.assertIn('getSystemDialerPackage()', self.home)
        self.assertNotIn('createLaunchEmergencyDialerIntent', self.home)  # Not in the public SDK.
        self.assertIn('No call/SMS is retried after a role decision', self.home)
        self.assertIn('No call/SMS is retried after a permission decision', self.home)
        sms = (JAVA / 'SmsController.java').read_text()
        for token in ('SMS gönderimini onayla', 'sendMultipartTextMessage', 'parts.size() > 30',
                      'SubscriptionManager.isValidSubscriptionId', 'MESSAGE_TYPE_OUTBOX', '"queued"'):
            self.assertIn(token, sms)
        self.assertNotIn('MESSAGE_TYPE_SENT', sms)
        journal = (JAVA / 'SmsJournal.java').read_text()
        self.assertIn('sent == full', journal)
        self.assertIn('delivered == full', journal)
        receipt = (JAVA / 'SmsStatusReceiver.java').read_text()
        self.assertIn('No report is not a delivery confirmation', receipt)
        self.assertIn('message.getStatus()', receipt)
        self.assertIn('pdu == null', receipt)
        self.assertIn('call.registerCallback', (JAVA / 'OguzInCallService.java').read_text())

    def test_apk_review_and_read_only_provider_do_not_enable_silent_installation(self):
        provider = self.manifest.find('application/provider')
        self.assertEqual(provider.attrib[NS + 'exported'], 'false')
        self.assertEqual(provider.attrib[NS + 'authorities'], '${applicationId}.apk')
        paths = ET.parse(ANDROID / 'res/xml/apk_paths.xml').getroot()
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].tag, 'cache-path')
        self.assertEqual(paths[0].attrib['path'], 'apk-inbox/')
        installer = (JAVA / 'InstallReviewActivity.java').read_text()
        for token in ('256L * 1024 * 1024', '64 * 1024', 'retained >= 3', 'count > 100000',
                      'getPackageArchiveInfo', 'GET_SIGNING_CERTIFICATES', 'getApkContentsSigners',
                      'Build.SUPPORTED_ABIS', 'minSdkVersion', 'canRequestPackageInstalls',
                      'ACTION_MANAGE_UNKNOWN_APP_SOURCES', 'Sistem yükleyicisine geç',
                      'FLAG_GRANT_READ_URI_PERMISSION', 'Intent.EXTRA_RETURN_RESULT',
                      'installed.getLongVersionCode() == version', 'signer.equals(certificate(installed))'):
            self.assertIn(token, installer)
        self.assertIn('cert.matches("[a-f0-9]{64}")', installer)
        self.assertIn('signer.matches("[a-f0-9]{64}")', installer)
        self.assertNotIn('FLAG_GRANT_WRITE_URI_PERMISSION', installer)
        self.assertNotIn('file://', installer)
        self.assertIn('file.getParentFile()', installer)

    def test_live_store_anchor_signature_hash_https_and_atomic_rollback_are_mandatory(self):
        trust = json.loads((ROOT / 'android/store-trust.json').read_text())
        self.assertEqual(trust['certificate_sha256'], '43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab')
        self.assertIn('d2cf05bb7805cc2a8544ae76ba6a88cc3e788721', trust['source'])
        repo = (JAVA / 'FdroidRepository.java').read_text()
        for token in (trust['certificate_sha256'], 'new JarFile(jarPath, true)', 'entry.getCodeSigners()',
                      'cert.checkValidity()', 'MessageDigest.isEqual', 'expectedHash',
                      '!actual.equals(expectedHash)', 'setInstanceFollowRedirects(false)',
                      '"https".equals(url.getProtocol())', 'url.getUserInfo() == null'):
            self.assertIn(token, repo)
        db = (JAVA / 'CatalogDb.java').read_text()
        for token in ('db.beginTransaction()', 'db.setTransactionSuccessful()', 'db.endTransaction()',
                      'timestamp < previous', 'targetSdk < 24', 'KnownVuln', 'Build.SUPPORTED_ABIS'):
            self.assertIn(token, db)

    def test_assistant_services_require_system_binding_permission_and_do_not_listen(self):
        for name in ('.RifkiVoiceService', '.RifkiSessionService', '.RifkiRecognitionService'):
            service = self.manifest.find("application/service[@" + NS + "name='" + name + "']")
            self.assertEqual(service.attrib[NS + 'permission'], 'android.permission.BIND_VOICE_INTERACTION')
        recognition = (JAVA / 'RifkiRecognitionService.java').read_text()
        self.assertIn('ERROR_INSUFFICIENT_PERMISSIONS', recognition)
        self.assertNotIn('AudioRecord', recognition)
        self.assertNotIn('MediaRecorder', recognition)
        voice = (JAVA / 'RifkiVoiceService.java').read_text()
        self.assertIn('setDisabledShowContext', voice)
        self.assertIn('SHOW_WITH_ASSIST', voice)
        self.assertIn('SHOW_WITH_SCREENSHOT', voice)
        metadata = ET.parse(ANDROID / 'res/xml/rifki_voice.xml').getroot()
        self.assertEqual(metadata.attrib[NS + 'supportsLaunchVoiceAssistFromKeyguard'], 'false')
        local = (JAVA / 'RifkiText.java').read_text()
        self.assertIn('kural tabanlı', local)
        self.assertIn('Üretken model burada bağlı değil', local)

    def test_identity_licensing_and_twenty_three_desktop_function_map_are_not_replaced_by_certification_claims(self):
        app = self.manifest.find('application')
        self.assertEqual(app.attrib[NS + 'label'], 'OğuzDows Mobile')
        self.assertEqual(app.attrib[NS + 'allowBackup'], 'false')
        self.assertEqual(app.attrib[NS + 'usesCleartextTraffic'], 'false')
        parity = json.loads((ROOT / 'feature-parity.json').read_text())
        for key in ('rom_built', 'physical_device_tested', 'live_generative_model_tested'):
            self.assertIs(parity[key], False)
        self.assertEqual(len(parity['workbench']), 16)
        self.assertEqual(len(parity['other_seven_new_functions']), 7)
        self.assertEqual(len({f['id'] for f in parity['workbench']}), 16)
        self.assertNotIn('ro.build', self.home)

    def test_native_routes_are_wired_instead_of_reusing_browser_tel_sms_handoffs(self):
        source = (ROOT / 'preview/src/Everyday.tsx').read_text()
        self.assertTrue(re.search(r'inNativeApp\s*\?\s*\(?\s*<NativePhone', source), 'Native phone route must be wired')
        self.assertTrue(re.search(r'inNativeApp\s*\?\s*\(?\s*<NativeMessages', source), 'Native SMS route must be wired')
        native = (ROOT / 'preview/src/NativeCommunications.tsx').read_text()
        self.assertIn('"call.place"', native)
        self.assertIn('"messages.send"', native)
        self.assertIn('"messages.list"', native)
        self.assertNotIn('href="tel:', native)
        self.assertNotIn('href="sms:', native)
        transport = (ROOT / 'preview/src/native.ts').read_text()
        self.assertIn('location.origin === ORIGIN', transport)
        self.assertNotIn('localStorage', transport)
        app = (ROOT / 'preview/src/App.tsx').read_text()
        self.assertLess(app.index('window.addEventListener("oguz-native-intent", intent)'), app.index('nativeRequest("ui.ready")'))
        self.assertIn('case "ui.ready": frontendReady = true;', self.home)
        self.assertIn('intent == null || !frontendReady', self.home)
        self.assertIn('intentDelivered = true', self.home)
        self.assertIn('draftIntentDelivered', self.home)
        self.assertNotIn('intent.setAction(Intent.ACTION_MAIN)', self.home)

    def test_build_wrapper_is_pinned_and_emulator_tests_refuse_physical_traffic(self):
        wrapper = ROOT / 'android/gradle/wrapper/gradle-wrapper.jar'
        self.assertEqual(hashlib.sha256(wrapper.read_bytes()).hexdigest(),
            '498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17')
        settings = (ROOT / 'android/gradle/wrapper/gradle-wrapper.properties').read_text()
        self.assertIn('distributionSha256Sum=d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab', settings)
        smoke = (ROOT / 'scripts/emulator-smoke.py').read_text()
        self.assertIn("serial.startswith('emulator-')", smoke)
        self.assertIn("'ro.kernel.qemu'", smoke)
        self.assertIn("'physical_sim_tested': False", smoke)
        self.assertIn("'emergency_calls_tested': False", smoke)
        self.assertNotIn('--bypass-role-qualification', smoke)

    def test_native_store_icons_preserve_symbol_paths_licenses_and_reproducible_hashes(self):
        records = json.loads((ROOT / 'android/native-icons.json').read_text())
        self.assertEqual(len(records), 24)
        self.assertEqual(len({row['package'] for row in records}), 24)
        original = {row['id']: row for row in json.loads((ROOT / 'preview/public/assets/apps/manifest.json').read_text())}
        generated = (JAVA / 'CuratedIcons.java').read_text()
        for row in records:
            with self.subTest(icon=row['id']):
                source = ROOT / row['source_svg']
                vector = ANDROID / 'res/drawable' / ('catalog_' + row['id'] + '.xml')
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), row['source_svg_sha256'])
                self.assertEqual(hashlib.sha256(vector.read_bytes()).hexdigest(), row['vector_sha256'])
                path = ET.parse(source).getroot().find('{http://www.w3.org/2000/svg}path').attrib['d']
                self.assertEqual(ET.parse(vector).getroot().find('group/path').attrib[NS + 'pathData'], path)
                self.assertEqual(row['license'], original[row['id']]['license'])
                self.assertIn('case "' + row['package'] + '":', generated)
        self.assertEqual(original['fdroid']['license']['type'], 'CC-BY-SA-3.0')
        store = (JAVA / 'SourceStoreActivity.java').read_text()
        self.assertIn('AppIcons.get', store)
        self.assertIn('(LinearLayout) recycled', store)
        self.assertIn('1536 * 1024', (JAVA / 'AppIcons.java').read_text())

    def test_resources_parse_and_api_contract_remains_explicit(self):
        for path in ANDROID.rglob('*.xml'):
            with self.subTest(path=path): ET.parse(path)
        nazar = ET.parse(ANDROID / 'res/drawable/nazar.xml').getroot()
        self.assertGreaterEqual(len(nazar.findall('path')), 5)
        gradle = (ROOT / 'android/app/build.gradle.kts').read_text()
        self.assertRegex(gradle, r'minSdk\s*=\s*29')
        self.assertRegex(gradle, r'targetSdk\s*=\s*35')
        self.assertIn('generated/bundled-ui', gradle)
        self.assertIn('generated/test-assets', gradle)


if __name__ == '__main__':
    unittest.main()
