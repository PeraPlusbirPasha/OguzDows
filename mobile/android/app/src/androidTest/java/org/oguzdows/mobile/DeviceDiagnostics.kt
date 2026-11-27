package org.oguzdows.mobile

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.util.Xml
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import androidx.test.uiautomator.UiDevice
import org.json.JSONArray
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File

/** Failure-only diagnostics BEFORE ActivityScenario closes the actual failing window.
 * Never runs on a phone, captures a bridge invitation, or alters/dismisses a system dialog.
 */
object DeviceDiagnostics {
    fun missing(device: UiDevice, label: String, image: Boolean = true): Nothing {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        if (Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")) try {
            val report = JSONObject().put("missing", label.take(100)).put("package", device.currentPackageName)
            val activities = JSONArray()
            instrumentation.runOnMainSync {
                ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED).forEach {
                    activities.put(it.javaClass.simpleName + ":" + it.window.decorView.width + "x" + it.window.decorView.height)
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
                        val small = Bitmap.createScaledBitmap(source, 234, (source.height * 234f / source.width).toInt().coerceAtLeast(1), true)
                        val out = ByteArrayOutputStream(); small.compress(Bitmap.CompressFormat.JPEG, 45, out)
                        if (source !== small) source.recycle()
                        small.recycle()
                        if (out.size() <= 21000) instrumentation.sendStatus(0, Bundle().apply {
                            putString("stream", "\nDEVICE_UI_PREVIEW " + file.nameWithoutExtension + " " + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP) + "\n")
                        })
                    }
                }
            }
        } catch (_: Exception) { /* Diagnostics never turn a failure into a pass. */ }
        throw AssertionError("Missing native UI: $label; package=${device.currentPackageName}")
    }
}
