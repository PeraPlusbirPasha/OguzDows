"""Source boundaries for the connected milestone; not a native compilation/runtime substitute."""
import ast
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT/'mobile/android/app/src/main'
SRC = MAIN/'java/org/oguzdows/mobile'
NS = '{http://schemas.android.com/apk/res/android}'


class ConnectedSourceContracts(unittest.TestCase):
    def test_layout_ids_match_the_real_desktop_profiles_and_are_persisted(self):
        tree = ast.parse((ROOT/'system/usr/lib/oguzdows/profiles.py').read_text())
        profiles = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        ids = re.findall(r'ShellLayout\("([a-z0-9]+)"', (SRC/'ShellStyles.kt').read_text())
        self.assertEqual(set(ids), set(profiles))
        self.assertEqual(len(ids), 6)
        store = (SRC/'LauncherStore.kt').read_text()
        self.assertIn('putString("layout"', store)
        screen = (SRC/'NativeLauncherScreen.kt').read_text()
        for value in ('layout.columns', 'layout.rail', 'ConnectedTheme(', 'FullAeroPanel(', 'gestureThreshold', 'PointerEventPass.Final', 'change.position != change.previousPosition', 'enabled = workspaceScroll.maxValue > 0'):
            self.assertIn(value, screen)
        device = (ROOT/'mobile/android/app/src/androidTest/java/org/oguzdows/mobile/ConnectedDeviceTest.kt').read_text()
        for value in ('withResumedHome', 'home.isTaskRoot', 'Intent.CATEGORY_HOME', 'Stage.DESTROYED',
                      'Stage.RESUMED', 'activity !== old', 'activity.taskId == previousTask.get()',
                      'it.recreate()', 'monitor.removeLifecycleCallback(callback)', 'com.android.settings',
                      'panel.height() > root.height() * .7f', 'drawer.height() > area.height() * .7f'):
            self.assertIn(value, device)

    def test_contacts_use_system_provider_and_do_not_expose_a_web_write_action(self):
        system = (SRC/'SystemContacts.kt').read_text()
        for value in ('ContactsContract', 'READ_CONTACTS', 'WRITE_CONTACTS', 'applyBatch', 'withValueBackReference', 'LIMIT = 1000', 'while (scanned < LIMIT && cursor.moveToNext())'):
            self.assertIn(value, system)
        self.assertLess(system.index('scanned++'), system.index('PlatformRules.number(cursor.getString(2)'))
        home = (SRC/'HomeActivity.java').read_text()
        self.assertIn('case "contacts.list":', home)
        self.assertIn('case "contacts.open":', home)
        self.assertNotIn('case "contacts.insert"', home)
        native = (ROOT/'mobile/preview/src/NativeCommunications.tsx').read_text()
        self.assertIn('useSystemRecipients', native)
        self.assertNotIn('prefs.contacts', native)
        self.assertNotIn('localStorage', (SRC/'SystemContacts.kt').read_text())
        contact = (SRC/'ContactsActivity.kt').read_text()
        for value in ('RequestPermission()', 'ContentObserver', 'unregisterContentObserver', 'Yeni kişiyi kaydet?', 'confirm=false', 'ACTION_SENDTO', 'ACTION_DIAL', 'val acceptedName=name; val acceptedNumber=number', 'SystemContacts.insert(this@ContactsActivity,acceptedName,acceptedNumber)'):
            self.assertIn(value, contact)

    def test_lock_and_mirroring_are_not_privileged_security_replacements(self):
        manifest = ET.parse(MAIN/'AndroidManifest.xml').getroot()
        for name in ('.ContactsActivity', '.BridgeActivity', '.LockActivity'):
            node = manifest.find('application/activity[@'+NS+"name='"+name+"']")
            self.assertEqual(node.attrib[NS+'exported'], 'false')
        service = manifest.find('application/service[@'+NS+"name='.BridgeMirrorService']")
        self.assertEqual(service.attrib[NS+'exported'], 'false')
        self.assertEqual(service.attrib[NS+'foregroundServiceType'], 'mediaProjection')
        lock = (SRC/'LockActivity.kt').read_text()
        for value in ('requestDismissKeyguard', 'isDeviceSecure', 'FLAG_SECURE', 'finish()', 'güvenlik kilidi DEĞİL'):
            self.assertIn(value, lock)
        for value in ('disableKeyguard', 'DISMISS_KEYGUARD', 'DevicePolicyManager', 'setOnKeyListener'):
            self.assertNotIn(value, lock)
        mirror = (SRC/'BridgeMirrorService.kt').read_text()
        for value in ('getMediaProjection', 'START_NOT_STICKY', 'ACTION_SCREEN_OFF', 'isKeyguardLocked', 'startForeground', 'MAX_FRAME', 'image.close()', '500'):
            self.assertIn(value, mirror)
        self.assertNotIn('AudioRecord', mirror)
        self.assertNotIn('MediaRecorder', mirror)

    def test_local_tls_does_not_broaden_web_origin_phone_or_installer_authority(self):
        manifest = ET.parse(MAIN/'AndroidManifest.xml').getroot()
        self.assertEqual(manifest.find('application').attrib[NS+'usesCleartextTraffic'], 'false')
        server = (SRC/'BridgeServer.kt').read_text()
        for value in ('SSLServerSocket', '0.0.0.0', 'Semaphore(4)', 'soTimeout = 15000', 'origin', 'transfer-encoding', 'ensureAuthorized'):
            self.assertIn(value, server)
        client = (SRC/'BridgeClient.kt').read_text()
        for value in ('instanceFollowRedirects = false', 'MessageDigest.isEqual', 'chain[0].encoded', 'Proxy.NO_PROXY', 'BridgeRules.verify', 'createNewFile()'):
            self.assertIn(value, client)
        host = (SRC/'BridgeHost.kt').read_text()
        for forbidden in ('SmsManager', 'TelecomManager', 'WebView', 'startActivity', 'ProcessBuilder', 'Runtime.getRuntime'):
            self.assertNotIn(forbidden, host)
        provider = ET.parse(MAIN/'res/xml/apk_paths.xml').getroot()
        self.assertEqual([n.attrib['path'] for n in provider], ['apk-inbox/'])
        self.assertNotIn('android:scheme="oguzkopru1"', (MAIN/'AndroidManifest.xml').read_text())

    def test_desktop_peer_is_explicit_portable_and_not_an_autostart_daemon(self):
        wrapper = ROOT/'system/usr/local/bin/oguzdows-bridge'
        self.assertTrue(wrapper.stat().st_mode & 0o111)
        self.assertIn('/usr/bin/python3 -I /usr/lib/oguzdows/bridge.py', wrapper.read_text())
        desktop = (ROOT/'system/usr/share/applications/oguzdows-bridge.desktop').read_text()
        self.assertIn('Exec=/usr/local/bin/oguzdows-bridge', desktop)
        self.assertIn('openssl', (ROOT/'packages/common.list').read_text())
        self.assertFalse((ROOT/'system/etc/xdg/autostart/oguzdows-bridge.desktop').exists())
        self.assertFalse((ROOT/'system/usr/lib/systemd/system/oguzdows-bridge.service').exists())


if __name__ == '__main__':
    unittest.main()
