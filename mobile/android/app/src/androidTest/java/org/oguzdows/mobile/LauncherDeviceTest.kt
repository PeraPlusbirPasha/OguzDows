package org.oguzdows.mobile

import android.app.role.RoleManager
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.Base64
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
import androidx.test.uiautomator.Until
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.atomic.AtomicReference
import java.util.regex.Pattern

/** Actual native HOME / LauncherApps / layout / controls / RemoteViews acceptance. QEMU only. */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class LauncherDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val device = UiDevice.getInstance(instrumentation)
    private lateinit var scenario: ActivityScenario<LauncherActivity>
    private var originalDark = false
    @Before fun start() {
        assertTrue("QEMU only; never alter a daily phone", Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"))
        originalDark = NativeUi.dark(context)
        LauncherStore(context).reset()
        device.wakeUp(); device.pressMenu()
        scenario = ActivityScenario.launch(Intent(context, LauncherActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        node("launcher-root")
        waitFor("real application scan") {
            val loaded = AtomicReference(false)
            scenario.onActivity { loaded.set(!it.model.ui.value.loading && it.model.ui.value.entries.isNotEmpty()) }
            loaded.get()
        }
    }
    @After fun close() {
        if (this::scenario.isInitialized) scenario.close()
        context.getSharedPreferences("native-ui",0).edit().putBoolean("dark",originalDark).commit()
    }
    private fun waitFor(label:String, condition:()->Boolean) {
        val end=SystemClock.elapsedRealtime()+25000
        do {if(condition())return;SystemClock.sleep(200)}while(SystemClock.elapsedRealtime()<end)
        throw AssertionError("Timed out: $label")
    }
    private fun node(tag:String):UiObject2 = device.wait(Until.findObject(By.res(tag)),25000)
        ?:throw AssertionError("Native node not found: $tag; current package=${device.currentPackageName}")
    private fun desc(label:String):UiObject2 = device.wait(Until.findObject(By.desc(label)),25000)
        ?:throw AssertionError("Native action not found: $label; package=${device.currentPackageName}")
    private fun pins():List<String> {
        val out=AtomicReference<List<String>>()
        scenario.onActivity{out.set(it.model.ui.value.pins)}
        return out.get()
    }
    private fun screenshot(name:String):File {
        val dir=File(context.getExternalFilesDir(null),"evidence");dir.mkdirs()
        val file=File(dir,"$name.png");assertTrue(device.takeScreenshot(file));return file
    }
    @Test fun test01ActualNativeHomeAndInventory() {
        assertTrue(PlatformState.role(context,RoleManager.ROLE_HOME))
        val home=context.packageManager.resolveActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME),PackageManager.MATCH_DEFAULT_ONLY)
        assertEquals(LauncherActivity::class.java.name,home?.activityInfo?.name)
        val fixture=AtomicReference<LauncherEntry>()
        scenario.onActivity{fixture.set(it.model.ui.value.entries.find{entry->entry.packageName=="org.oguzdows.fixture"})}
        assertNotNull("fixture was genuinely installed by prior installer acceptance",fixture.get())
        assertEquals("org.oguzdows.fixture",fixture.get().component.packageName)
        assertFalse("home is native, not a WebView",device.hasObject(By.clazz("android.webkit.WebView")))
        screenshot("launcher-native-home")
        node("launcher-search-open").click(); node("launcher-search").text="cihazim"
        desc("Modülü aç: Cihazım").click(); node("launcher-device-panel")
        assertTrue(device.hasObject(By.textContains("Sistem belleği")))
        device.pressHome(); node("launcher-root")
        node("launcher-search-open").click(); node("launcher-search").text="koleksiyon"
        desc("Modülü aç: Koleksiyon").click(); node("launcher-wallpapers")
        desc("Duvar kâğıdı: Kapadokya ışığı").click()
        waitFor("real persisted wallpaper choice") { LauncherStore(context).wallpaper()==1 }
        device.pressHome(); node("launcher-root")
    }
    @Test fun test02SearchLaunchesInstalledActivityAndHomeReturns() {
        node("launcher-search-open").click();node("launcher-drawer")
        node("launcher-search").text="test paketi"
        desc("Uygulamayı aç: OğuzDows test paketi").click()
        assertTrue("real fixture foreground",device.wait(Until.hasObject(By.pkg("org.oguzdows.fixture")),15000))
        device.pressHome();node("launcher-root")
        assertEquals(context.packageName,device.currentPackageName)
    }
    @Test fun test03PinMoveAndPersistenceAreReal() {
        node("launcher-search-open").click();node("launcher-search").text="test paketi"
        desc("Uygulamayı sabitle: OğuzDows test paketi").click()
        waitFor("pin is in native layout"){pins().any{it.contains("org.oguzdows.fixture")}}
        val key=pins().first{it.contains("org.oguzdows.fixture")}
        desc("Kısayolu düzenle: OğuzDows test paketi").click()
        device.wait(Until.findObject(By.text("Öne al")),10000)!!.click()
        waitFor("move changed order"){pins().indexOf(key)==11}
        val expected=pins()
        waitFor("disk persistence, not just view state"){LauncherStore(context).pins()==expected}
        device.pressHome(); node("launcher-root")
        // A new ViewModel must read disk; configuration recreation alone retains a ViewModel.
        scenario.close()
        scenario = ActivityScenario.launch(Intent(context, LauncherActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        node("launcher-root")
        assertEquals(expected,pins())
        assertEquals(expected,LauncherStore(context).pins())
        val preferences=context.getSharedPreferences("launcher-layout-v1",0)
        preferences.edit().putString("pins","{broken-layout").commit()
        val corrupt=LauncherStore(context)
        assertEquals(LauncherRules.defaultPins,corrupt.pins())
        assertFalse(corrupt.writable)
        assertFalse(corrupt.savePins(expected))
        assertEquals("{broken-layout",preferences.getString("pins",null))
        corrupt.reset()
        assertEquals(LauncherRules.defaultPins,corrupt.pins())
    }
    @Test fun test04ControlsAndRifkiUseActualState() {
        val audio=context.getSystemService(AudioManager::class.java)
        val before=audio.getStreamVolume(AudioManager.STREAM_MUSIC)
        try {
            node("launcher-controls").click();node("launcher-control-panel")
            val old=NativeUi.dark(context)
            node("launcher-dark-switch").click()
            waitFor("shared native theme actually changed"){NativeUi.dark(context)!=old}
            val slider=node("launcher-volume").visibleBounds
            val fraction=if(before<audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)/2) .8f else .2f
            device.click(slider.left+(slider.width()*fraction).toInt(),slider.centerY())
            waitFor("AudioManager volume changed"){audio.getStreamVolume(AudioManager.STREAM_MUSIC)!=before}
            device.pressHome();node("launcher-rifki").click();node("launcher-rifki-panel")
            assertTrue(device.hasObject(By.textContains("Bulut bağlı değil")))
            node("rifki-input").text="gece modu"
            val ime = AtomicReference(false)
            scenario.onActivity { ime.set(androidx.core.view.ViewCompat.getRootWindowInsets(it.window.decorView)
                ?.isVisible(androidx.core.view.WindowInsetsCompat.Type.ime()) == true) }
            if (ime.get()) device.pressBack() // Never dismiss the sheet when no keyboard is shown.
            node("rifki-send").click()
            assertTrue(node("rifki-answer").text.contains("Gece mavisi"))
            node("rifki-suggestion").click()
            waitFor("explicit suggestion applied native theme"){NativeUi.dark(context)}
            assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission("android.permission.RECORD_AUDIO"))
            screenshot("launcher-native-rifki")
        } finally {audio.setStreamVolume(AudioManager.STREAM_MUSIC,before,0)}
    }
    @Test fun test05RealWidgetBindingRenderingAndRemoval() {
        val providerLabel = AtomicReference<String>()
        scenario.onActivity {
            val providers = it.widgets.providers()
            val fixture = providers.find { provider -> provider.provider.packageName == "org.oguzdows.fixture" }
            assertNotNull("Actual platform providers: " + providers.joinToString { provider -> provider.provider.flattenToShortString() }, fixture)
            providerLabel.set(fixture!!.loadLabel(context.packageManager))
        }
        desc("Widget alanı").click();node("launcher-widget-space")
        node("launcher-add-widget").click();node("launcher-widget-picker")
        node("launcher-widget-search").text="org.oguzdows.fixture"
        desc("Widget seç: ${providerLabel.get()}").click()
        // HOME may already be authorized; otherwise exercise the actual system bind consent.
        val allow=device.wait(Until.findObject(By.text(Pattern.compile("allow|create|[iIıİ]z[iIıİ]n ver|oluştur",Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE))),3000)
        allow?.click()
        waitFor("widget id persisted only after platform binding"){LauncherStore(context).widgetIds().size==1}
        val id=LauncherStore(context).widgetIds().single()
        val bound=AtomicReference(false)
        scenario.onActivity{bound.set(it.widgets.manager.getAppWidgetInfo(id)?.provider?.packageName=="org.oguzdows.fixture")}
        assertTrue("real AppWidgetManager binding",bound.get())
        node("launcher-widget-$id")
        assertTrue("provider RemoteViews rendered",device.wait(Until.hasObject(By.textContains("Widget hazır")),15000))
        screenshot("launcher-native-widget")
        scenario.recreate()
        desc("Widget alanı").click(); node("launcher-widget-space")
        assertEquals(listOf(id),LauncherStore(context).widgetIds())
        node("launcher-widget-$id")
        assertTrue("RemoteViews restored with a new host",device.wait(Until.hasObject(By.textContains("Widget hazır")),15000))
        desc("Widget kaldır: $id").click()
        waitFor("widget removed from persisted layout"){LauncherStore(context).widgetIds().isEmpty()}
        scenario.onActivity{assertNull(it.widgets.manager.getAppWidgetInfo(id))}
        device.pressHome();node("launcher-root")
        // Bounded, emulator-only visual diagnostic; full PNG also stays in the normal artifact.
        val file=screenshot("launcher-native-final")
        val source=BitmapFactory.decodeFile(file.absolutePath,BitmapFactory.Options().apply{inSampleSize=3})
        val small=Bitmap.createScaledBitmap(source,234,(source.height*234f/source.width).toInt(),true)
        val bytes=ByteArrayOutputStream();small.compress(Bitmap.CompressFormat.JPEG,45,bytes)
        source.recycle();small.recycle()
        if(bytes.size()<=21000) instrumentation.sendStatus(0,Bundle().apply{putString("stream","\nNATIVE_LAUNCHER_PREVIEW "+Base64.encodeToString(bytes.toByteArray(),Base64.NO_WRAP)+"\n")})
    }
}
