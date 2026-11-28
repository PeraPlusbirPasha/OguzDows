package org.oguzdows.mobile

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.util.Base64
import android.util.Xml
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.By
import androidx.test.uiautomator.BySelector
import androidx.test.uiautomator.UiObject2
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File

/** Emulator-only lookup/first-use education and failure diagnostics BEFORE ActivityScenario cleanup.
 * Never captures a bridge invitation. Only education() acknowledges the specifically identified
 * immersive tutorial; no helper grants permission or dismisses other system dialogs.
 */
object DeviceDiagnostics {
    /** Acknowledge ONLY the OS immersive education identified in the genuine CI capture.
     * Not a permission, ANR, installer, keyguard or MediaProjection confirmation.
     */
    fun education(device: UiDevice) {
        check(Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"))
        if (device.hasObject(By.res("android:id/immersive_cling_title")) &&
            device.hasObject(By.res("android:id/immersive_cling_description"))) {
            device.findObject(By.res("android:id/ok"))?.click()
        }
    }
    fun find(device: UiDevice, selector: BySelector, timeout: Long): UiObject2? {
        val end = SystemClock.elapsedRealtime() + timeout
        do {
            education(device)
            device.findObject(selector)?.let { return it }
            SystemClock.sleep(150)
        } while (SystemClock.elapsedRealtime() < end)
        return null
    }
    fun missing(device: UiDevice, label: String, image: Boolean = true): Nothing {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        if (Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")) try {
            val report = JSONObject().put("missing", label.take(100)).put("package", device.currentPackageName)
            val activities = JSONArray()
            instrumentation.runOnMainSync {
                ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED).forEach {
                    activities.put(it.javaClass.simpleName + ":" + it.window.decorView.width + "x" + it.window.decorView.height
                        + ":task=" + it.taskId + ":root=" + it.isTaskRoot + ":focus=" + it.hasWindowFocus() + ":action=" + it.intent?.action)
                }
            }
            report.put("resumed", activities)
            val xml = ByteArrayOutputStream()
            device.dumpWindowHierarchy(xml)
            val parser = Xml.newPullParser().apply { setInput(ByteArrayInputStream(xml.toByteArray()), "UTF-8") }
            val labels = linkedSetOf<String>(); val ids = linkedSetOf<String>()
            while (parser.next() != XmlPullParser.END_DOCUMENT) {
                if (parser.eventType != XmlPullParser.START_TAG || parser.name != "node") continue
                val text = parser.getAttributeValue(null, "text").orEmpty()
                val id = parser.getAttributeValue(null, "resource-id").orEmpty()
                if (text.isNotBlank() && !text.contains("oguzkopru1:") && labels.size < 24) labels.add(text.take(65))
                if (id.isNotBlank() && ids.size < 24) ids.add(id.take(65))
            }
            report.put("labels", JSONArray(labels.toList())).put("resource_ids", JSONArray(ids.toList()))
            instrumentation.sendStatus(0, Bundle().apply { putString("stream", "\nDEVICE_UI_DIAGNOSTIC $report\n") })
            // BridgeActivity is FLAG_SECURE and may show temporary credentials: no image even in CI.
            if (image) {
                val folder = File(instrumentation.targetContext.getExternalFilesDir(null), "evidence").apply { mkdirs() }
                val file = File(folder, "failure-" + label.replace(Regex("[^a-zA-Z0-9-]"), "-").take(60) + ".png")
                if (device.takeScreenshot(file)) {
                    val source = BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = 3 })
                    if (source != null) {
                        val small = Bitmap.createScaledBitmap(source, 140, (source.height * 140f / source.width).toInt().coerceAtLeast(1), true)
                        val out = ByteArrayOutputStream(); small.compress(Bitmap.CompressFormat.JPEG, 30, out)
                        if (source !== small) source.recycle()
                        small.recycle()
                        if (out.size() <= 7400) instrumentation.sendStatus(0, Bundle().apply {
                            putString("stream", "\nDEVICE_UI_PREVIEW " + file.nameWithoutExtension + " " + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP) + "\n")
                        })
                    }
                }
            }
        } catch (_: Exception) { /* Diagnostics never turn a failure into a pass. */ }
        throw AssertionError("Missing native UI: $label; package=${device.currentPackageName}")
    }
}
