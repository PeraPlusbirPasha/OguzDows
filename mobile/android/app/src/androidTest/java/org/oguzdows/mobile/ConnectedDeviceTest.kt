package org.oguzdows.mobile

import android.Manifest
import android.app.KeyguardManager
import android.content.ContentUris
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import android.provider.ContactsContract
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleCallback
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
import androidx.test.uiautomator.Until
import org.junit.Assert.*
import org.junit.Before
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import java.util.regex.Pattern

/** New device cases; existing communications / widget / installer cases remain mandatory. */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class ConnectedDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val device = UiDevice.getInstance(instrumentation)
    @Before fun emulatorOnly() {
        assertTrue(Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"))
        device.wakeUp(); device.pressMenu()
    }
    private fun waitFor(label: String, condition: () -> Boolean) {
        val end = SystemClock.elapsedRealtime() + 25000
        do { if (condition()) return; SystemClock.sleep(200) } while (SystemClock.elapsedRealtime() < end)
        DeviceDiagnostics.missing(device, "Timed out: $label", image = false)
    }
    private fun node(tag: String): UiObject2 = DeviceDiagnostics.find(device, By.res(tag), 20000)
        ?: DeviceDiagnostics.missing(device, tag)
    private fun text(value: String): UiObject2 = DeviceDiagnostics.find(device, By.text(value), 15000)
        ?: DeviceDiagnostics.missing(device, value)
    private fun scrollTo(tag: String, scrollTag: String = "launcher-control-panel"): UiObject2 {
        repeat(10) {
            val visible = device.findObject(By.res(tag))
            if (visible != null && visible.visibleBounds.height() > 10) return visible
            node(scrollTag).scroll(Direction.DOWN, .65f)
        }
        return node(tag)
    }
    private fun screenshot(name: String) {
        val directory = File(context.getExternalFilesDir(null), "evidence").apply { mkdirs() }
        assertTrue(device.takeScreenshot(File(directory, "$name.png")))
    }
    private fun homeJs(script: String): String? {
        val out = AtomicReference<String?>(null); val latch = CountDownLatch(1)
        instrumentation.runOnMainSync {
            val home = androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry.getInstance()
                .getActivitiesInStage(androidx.test.runner.lifecycle.Stage.RESUMED).filterIsInstance<HomeActivity>().firstOrNull()
            if (home == null) latch.countDown() else home.webView.evaluateJavascript(script) { out.set(it); latch.countDown() }
        }
        latch.await(2, TimeUnit.SECONDS); return out.get()
    }
    /** Drive the HOME task selected by the OS, not startActivitySync's standard test task.
     * A real Home key can select another instance; using the initial ActivityScenario after
     * that tests a STOPPED instance even though the actual launcher is correctly RESUMED.
     */
    private fun withResumedHome(action: (LauncherActivity) -> Unit): Boolean {
        var found = false
        instrumentation.runOnMainSync {
            val home = ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED)
                .filterIsInstance<LauncherActivity>().singleOrNull()
            if (home != null) {
                assertTrue("system HOME is the task root", home.isTaskRoot)
                assertEquals(Intent.ACTION_MAIN, home.intent.action)
                assertTrue("system HOME intent", home.intent.hasCategory(Intent.CATEGORY_HOME))
                found = true; action(home)
            }
        }
        return found
    }
    private fun recreateActualHome() {
        val monitor = ActivityLifecycleMonitorRegistry.getInstance()
        val previous = AtomicReference<LauncherActivity?>(null)
        val previousTask = java.util.concurrent.atomic.AtomicInteger(-1)
        val destroyed = AtomicBoolean(false); val replacementResumed = AtomicBoolean(false)
        val callback = ActivityLifecycleCallback { activity, stage ->
            val old = previous.get()
            if (old != null) {
                if (activity === old && stage == Stage.DESTROYED) destroyed.set(true)
                if (activity is LauncherActivity && activity !== old && stage == Stage.RESUMED && activity.taskId == previousTask.get())
                    replacementResumed.set(true)
            }
        }
        instrumentation.runOnMainSync { monitor.addLifecycleCallback(callback) }
        try {
            assertTrue("recreate the currently resumed system HOME", withResumedHome {
                previous.set(it); previousTask.set(it.taskId); it.recreate()
            })
            waitFor("old HOME destroyed and a distinct replacement resumed in the same task") {
                destroyed.get() && replacementResumed.get()
            }
            assertTrue("replacement is still the real HOME", withResumedHome { assertTrue(it !== previous.get()) })
        } finally {
            instrumentation.runOnMainSync { monitor.removeLifecycleCallback(callback) }
            previous.set(null)
        }
    }
    @Test fun test01FullscreenGesturesLayoutsPersistenceAndRealSettings() {
        val store = LauncherStore(context)
        val oldLayout = store.layout(); val oldWallpaper = store.wallpaper(); val oldFull = store.fullscreen()
        try {
            store.fullscreen(true); store.layout("oguzdows")
            device.pressHome(); node("launcher-root")
            waitFor("actual system HOME resumed") { withResumedHome { } }
            val root = node("launcher-root").visibleBounds
            node("launcher-controls") // The first-use system education may initially cover the header.
            // Whole-workspace vertical movement, not the old 54 dp header-only hit area.
            device.swipe(root.centerX(), (root.height() * .35f).toInt(), root.centerX(), (root.height() * .68f).toInt(), 24)
            val panel = node("launcher-control-panel").visibleBounds
            assertTrue("full-screen panel, not a 650dp phone bottom sheet", panel.height() > root.height() * .7f)
            for (id in listOf("mac", "windows11", "gnome", "xfce", "kde", "oguzdows")) {
                scrollTo("layout-$id").click()
                waitFor("persisted $id") { LauncherStore(context).layout() == id }
            }
            scrollTo("layout-mac").click()
            device.pressHome(); node("launcher-root")
            assertTrue(node("launcher-layout-label").text.contains("macOS"))
            recreateActualHome(); node("launcher-root")
            assertEquals("mac", LauncherStore(context).layout())
            assertTrue(node("launcher-layout-label").text.contains("macOS"))
            screenshot("connected-mac-layout")
            assertTrue(withResumedHome { activity ->
                activity.model.wallpaper(1)
                assertEquals(ShellStyles.accent(1, NativeUi.dark(context)), NativeUi(activity).brand)
            })
            node("launcher-controls").click()
            scrollTo("launcher-system-settings").click()
            assertTrue("opens the phone's real Settings activity", device.wait(Until.hasObject(By.pkg("com.android.settings")), 15000))
            device.pressBack(); node("launcher-root")
            val area = node("launcher-root").visibleBounds
            device.swipe(area.centerX(), (area.height() * .62f).toInt(), area.centerX(), (area.height() * .37f).toInt(), 24)
            val drawer = node("launcher-drawer").visibleBounds
            assertTrue("upward drawer occupies the display", drawer.height() > area.height() * .7f)
            device.pressHome(); node("launcher-root")
        } finally { store.layout(oldLayout); store.wallpaper(oldWallpaper); store.fullscreen(oldFull) }
    }
    @Test fun test02DeniedContactsHaveNoProviderAccessOrInventedRows() {
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.READ_CONTACTS))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.WRITE_CONTACTS))
        try { SystemContacts.read(context); fail("No denied read") } catch (_: IllegalStateException) { }
        try { SystemContacts.insert(context, "must not be inserted", "5551234"); fail("No denied write") } catch (_: IllegalStateException) { }
        ActivityScenario.launch<ContactsActivity>(Intent(context, ContactsActivity::class.java)).use {
            node("system-contacts"); text("Rehberi okumaya izin ver")
            assertTrue(device.hasObject(By.textContains("Mevcut kişileri yalnız izin verdiğinde")))
            assertNull(device.findObject(By.text("must not be inserted")))
        }
    }
    @Test fun test03RealProviderAddCancelObserverAndSmsDraft() {
        val originalName = "OguzConnected_${SystemClock.elapsedRealtime()}"
        val updatedName = originalName + "_Updated"
        val number = "15555215556"
        var dataId: Long? = null
        var rawId: Long? = null
        fun find(): Pair<Long, Long>? = context.contentResolver.query(ContactsContract.Data.CONTENT_URI,
            arrayOf(ContactsContract.Data._ID, ContactsContract.Data.RAW_CONTACT_ID),
            "${ContactsContract.Data.MIMETYPE}=? AND ${ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME}=?",
            arrayOf(ContactsContract.CommonDataKinds.StructuredName.CONTENT_ITEM_TYPE, originalName), null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) to cursor.getLong(1) else null
        }
        try {
            ActivityScenario.launch<ContactsActivity>(Intent(context, ContactsActivity::class.java)).use { scenario ->
                node("system-contacts"); text("Rehberi okumaya izin ver").click()
                val allow = device.wait(Until.findObject(By.text(Pattern.compile("allow|[iIıİ]z[iIıİ]n ver", Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE))), 15000)
                allow?.click()
                waitFor("real read permission") { PlatformState.granted(context, Manifest.permission.READ_CONTACTS) }
                text("+ Kişi").click()
                if (!PlatformState.granted(context, Manifest.permission.WRITE_CONTACTS)) {
                    // Wait for the add form to compose; an optional immediate find used to
                    // skip the real request entirely. The OS may grant a second permission
                    // in the same group without another dialog, but the request is mandatory.
                    text("Yeni kişi için yazma izni ver").click()
                    waitFor("explicit write scope") {
                        if (PlatformState.granted(context, Manifest.permission.WRITE_CONTACTS)) true
                        else {
                            device.findObject(By.res(Pattern.compile("com\\.(?:android|google\\.android)\\.permissioncontroller:id/permission_allow_button")))?.click()
                            false
                        }
                    }
                }
                node("contact-name").text = originalName; node("contact-number").text = number
                val ime = AtomicReference(false)
                scenario.onActivity { ime.set(androidx.core.view.ViewCompat.getRootWindowInsets(it.window.decorView)
                    ?.isVisible(androidx.core.view.WindowInsetsCompat.Type.ime()) == true) }
                if (ime.get()) device.pressBack()
                node("contact-save").click(); text("Yeni kişiyi kaydet?"); text("Vazgeç").click()
                assertNull("cancel did not write a provider row", find())
                node("contact-save").click(); text("Kaydet").click()
                waitFor("real provider batch committed") { find() != null }
                val ids = requireNotNull(find()); dataId = ids.first; rawId = ids.second
                node("contacts-search").text = originalName
                text(originalName)
                context.contentResolver.update(ContentUris.withAppendedId(ContactsContract.Data.CONTENT_URI, ids.first),
                    ContentValues().apply { put(ContactsContract.CommonDataKinds.StructuredName.DISPLAY_NAME, updatedName) }, null, null)
                waitFor("visible list reacts to actual provider observer") { device.hasObject(By.text(updatedName)) }
                screenshot("connected-real-contacts")
                // The contact's SMS button may only prepare an explicit SENDTO draft.
                text("SMS").click()
                waitFor("real system recipient in SMS draft") { homeJs("document.querySelector('[aria-label=\"Mesaj alıcısı\"]')?.value") == "\"$number\"" }
                assertNull("contact selection did not place a call", CallController.snapshot())
                assertFalse("contact selection did not click send/consent", device.hasObject(By.textContains("SMS gönderimini onayla")))
                assertEquals("false", homeJs("!!document.querySelector('a[href^=\"sms:\"]')"))
                device.pressBack(); node("system-contacts")
                scenario.recreate(); node("system-contacts")
                assertTrue(SystemContacts.read(context).any { it.name == updatedName && it.number == number })
            }
        } finally {
            if (rawId == null && PlatformState.granted(context, Manifest.permission.READ_CONTACTS)) rawId = find()?.second
            rawId?.let { context.contentResolver.delete(ContentUris.withAppendedId(ContactsContract.RawContacts.CONTENT_URI, it), null, null) }
        }
    }
    @Test fun test04BrandedLockDoesNotCollectPinOrDisableKeyguard() {
        val keyguard = context.getSystemService(KeyguardManager::class.java)
        val secure = keyguard.isDeviceSecure
        ActivityScenario.launch<LockActivity>(Intent(context, LockActivity::class.java)).use {
            node("oguz-lock-surface")
            assertFalse(device.hasObject(By.clazz("android.widget.EditText")))
            assertEquals(secure, keyguard.isDeviceSecure)
            text("Sistemle devam et").click()
            waitFor("companion surface dismisses, not system credentials") { !device.hasObject(By.res("oguz-lock-surface")) }
            assertEquals(secure, keyguard.isDeviceSecure)
        }
    }
}
