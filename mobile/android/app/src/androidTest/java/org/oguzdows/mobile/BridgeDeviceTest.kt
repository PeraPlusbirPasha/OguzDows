package org.oguzdows.mobile

import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.UiObject2
import androidx.test.uiautomator.Until
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream
import java.io.File
import java.util.concurrent.atomic.AtomicReference
import java.util.regex.Pattern

/** Real native TLS sockets + Python peer interoperability + actual MediaProjection, QEMU only. */
@RunWith(AndroidJUnit4::class)
class BridgeDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val device = UiDevice.getInstance(instrumentation)
    @Before fun emulatorOnly() {
        assertTrue(Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"))
        device.wakeUp(); device.pressMenu()
    }
    private fun waitFor(label: String, timeout: Long = 30000, condition: () -> Boolean) {
        val end = SystemClock.elapsedRealtime() + timeout
        do { if (condition()) return; SystemClock.sleep(150) } while (SystemClock.elapsedRealtime() < end)
        throw AssertionError("Timed out: $label; package=${device.currentPackageName}")
    }
    private fun node(tag: String): UiObject2 = DeviceDiagnostics.find(device, By.res(tag), 20000)
        ?: DeviceDiagnostics.missing(device, tag, image = false)
    private fun text(value: String): UiObject2 {
        // Give the real host snapshot one poll before moving the viewport away from
        // its new pair row; search both directions instead of blindly scrolling past it.
        DeviceDiagnostics.find(device, By.text(value), 2500)?.let { return it }
        var direction = Direction.DOWN
        repeat(12) {
            DeviceDiagnostics.education(device)
            device.findObject(By.text(value))?.let { return it }
            val scroll = device.findObject(By.res("bridge-scroll"))
            if (scroll?.scroll(direction, .5f) != true) direction = if(direction == Direction.DOWN) Direction.UP else Direction.DOWN
            SystemClock.sleep(150)
        }
        return DeviceDiagnostics.find(device, By.text(value), 3000) ?: DeviceDiagnostics.missing(device, value, image = false)
    }
    private fun invite(host: BridgeHost) = BridgeInvitation("127.0.0.1", host.server.port, host.server.pin, host.secret)
    private fun pairNative(client: BridgeClient, host: BridgeHost, name: String): JSONObject = try {
        client.pair(name)
    } catch (error: Exception) { throw AssertionError("Pinned native TLS failed: ${host.server.lastTlsFailure}", error) }
    @Test fun nativeTls() {
        val host = BridgeHost(context, "Native TLS fixture").start()
        val out = File(context.cacheDir, "bridge-test-${BridgeRules.token(16)}")
        var client: BridgeClient? = null
        try {
            val wrong = BridgeClient(invite(host).copy(pin = "0".repeat(64)))
            try { wrong.pair("must not arrive"); fail("wrong pin") } catch (_: Exception) { } finally { wrong.forget() }
            assertTrue("no name/secret was sent on an unpinned channel", host.snapshot().first.isEmpty())
            val c = BridgeClient(invite(host)); client = c
            val pair = pairNative(c, host, "same-device inert client")
            assertEquals("pending", c.pollPair())
            try { c.state(); fail("unapproved") } catch (_: BridgeDenied) { }
            assertEquals(pair.getString("code"), host.snapshot().first.single().code)
            host.approvePair(pair.getString("id"), true); assertEquals("approved", c.pollPair())
            val raw = "native TLS download fixture\n".toByteArray()
            host.offer(ByteArrayInputStream(raw), "İmece.txt")
            val item = c.state().files.single(); assertEquals("İmece.txt", item.name)
            c.receive(item, out); assertArrayEquals(raw, out.readBytes())
            try { c.receive(item, out); fail("must not overwrite") } catch (_: IllegalStateException) { }
            assertArrayEquals(raw, out.readBytes())
            val request = c.propose(item)
            try { c.upload(request, out); fail("no recipient consent") } catch (_: BridgeDenied) { }
            host.approveInbox(request, true); assertEquals("ready", c.upload(request, out))
            assertArrayEquals(raw, host.received(request).second.readBytes())
            try { c.frame(); fail("file pairing is not screen consent") } catch (_: BridgeDenied) { }
            val peer = host.snapshot().second.single()
            host.revoke(peer.id)
            try { c.state(); fail("revoked") } catch (_: BridgeDenied) { }
        } finally { client?.forget(); host.close(); out.delete() }
        assertFalse(host.root.exists())
    }
    @Test fun pcArmInterop() {
        val folder = requireNotNull(context.getExternalFilesDir(null))
        val nativeInvitation = File(folder, "bridge-native-invitation.txt")
        val desktopInvitation = File(folder, "bridge-desktop-invitation.txt")
        val pcVerified = File(folder, "bridge-pc-verified")
        val complete = File(folder, "bridge-interop-complete")
        val host = BridgeHost(context, "Native interoperability fixture").start()
        val received = File(context.cacheDir, "bridge-interop-${BridgeRules.token(16)}")
        var client: BridgeClient? = null
        try {
            host.offer(ByteArrayInputStream("native-host to desktop-client fixture\n".toByteArray()), "native-to-desktop.txt")
            nativeInvitation.writeText(invite(host).encode()) // Out-of-band test transport; NEVER pulled as evidence.
            waitFor("Python peer sent a real TLS pairing", 90000) { host.snapshot().first.isNotEmpty() }
            host.approvePair(host.snapshot().first.single().id, true)
            waitFor("Python peer explicitly proposes an upload") { host.snapshot().third.isNotEmpty() }
            val incoming = host.snapshot().third.single(); assertEquals("desktop-upload.txt", incoming.name)
            host.approveInbox(incoming.id, true)
            waitFor("Python upload committed real hash") { host.snapshot().third.single().status == "ready" }
            assertEquals("desktop-client to native-host fixture\n", host.received(incoming.id).second.readText())
            waitFor("Python server invitation exists", 60000) { desktopInvitation.isFile }
            val c = BridgeClient(BridgeInvitation.parse(desktopInvitation.readText())); client = c
            c.pair("Native client fixture")
            waitFor("Python host also requires explicit local approval") { c.pollPair() == "approved" }
            val item = c.state().files.single(); assertEquals("desktop-to-native.txt", item.name)
            c.receive(item, received)
            assertEquals("desktop-host to native-client fixture\n", received.readText())
            val raw = "native-client to desktop-host fixture\n".toByteArray()
            val local = File(context.cacheDir, "bridge-upload-${BridgeRules.token(16)}").apply { writeBytes(raw) }
            try {
                val meta = BridgeItem(BridgeRules.token(16), "native-upload.txt", raw.size.toLong(), BridgeRules.sha(raw))
                val id = c.propose(meta)
                waitFor("Python host explicitly approved incoming metadata") { c.uploadStatus(id) == "approved" }
                assertEquals("ready", c.upload(id, local))
                waitFor("Python independently checked actual received bytes") { pcVerified.isFile }
            } finally { local.delete() }
            c.disconnect()
            complete.writeText("bidirectional TLS and SHA256 verified")
            val hashes = JSONObject()
                .put("native-to-desktop.txt", host.offered().single().sha256)
                .put("desktop-upload.txt", BridgeRules.sha(host.received(incoming.id).second.readBytes()))
                .put("desktop-to-native.txt", BridgeRules.sha(received.readBytes()))
                .put("native-upload.txt", BridgeRules.sha(raw))
            instrumentation.sendStatus(0, Bundle().apply { putString("stream", "\nBRIDGE_INTEROP_EVIDENCE " + JSONObject()
                .put("protocol", 1).put("native_host_python_client", true).put("python_host_native_client", true)
                .put("pinned_tls", true).put("sha256_verified", true).put("files_verified", 4).put("file_sha256", hashes)
                .put("physical_devices", false).toString() + "\n") })
        } finally { client?.forget(); host.close(); nativeInvitation.delete(); desktopInvitation.delete(); received.delete() }
    }
    @Test fun systemProjection() {
        val reference = AtomicReference<BridgeHost?>()
        var client: BridgeClient? = null
        val scenario = ActivityScenario.launch<BridgeActivity>(Intent(context, BridgeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        try {
            node("oguz-bridge"); node("bridge-host").click()
            waitFor("native session started without capture permission") { scenario.onActivity { reference.set(it.model.host) }; reference.get() != null }
            val host = requireNotNull(reference.get())
            val c = BridgeClient(invite(host)); client = c
            pairNative(c, host, "CI mirror receiver")
            text("Kod aynı · izin ver").click(); assertEquals("approved", c.pollPair())
            assertFalse(c.state().mirror); assertFalse(BridgeMirrorService.running)
            text("Ekranımı paylaş…").click(); text("Sistem ekran iznine geç").click()
            val cancel = device.wait(Until.findObject(By.text(Pattern.compile("cancel|vazgeç", Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE))), 15000)
            assertNotNull("real system screen-capture consent, not a fake app switch", cancel); cancel!!.click()
            node("oguz-bridge"); assertFalse(BridgeMirrorService.running); assertFalse(c.state().mirror)
            text("Ekranımı paylaş…").click(); text("Sistem ekran iznine geç").click()
            // API35 offers one-app or entire-screen capture. This test deliberately selects the latter,
            // then displays the already genuinely installed no-permission fixture, never real user data.
            val spinner = device.wait(Until.findObject(By.res("com.android.systemui:id/screen_share_mode_spinner")), 4000)
                ?: device.findObject(By.clazz("android.widget.Spinner"))
            if (spinner != null) {
                spinner.click()
                val entire = device.wait(Until.findObject(By.text(Pattern.compile("entire screen|full screen|tüm ekran", Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE))), 5000)
                assertNotNull("entire-screen option", entire); entire!!.click()
            }
            val start = device.wait(Until.findObject(By.text(Pattern.compile("start now|start sharing|share screen|şimdi başlat|paylaş", Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE))), 10000)
            assertNotNull("system final screen-sharing button", start); start!!.click()
            waitFor("real foreground MediaProjection started", 20000) { BridgeMirrorService.running && host.viewer != null }
            context.startActivity(requireNotNull(context.packageManager.getLaunchIntentForPackage("org.oguzdows.fixture")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            assertTrue(device.wait(Until.hasObject(By.pkg("org.oguzdows.fixture")), 15000))
            var captured: ByteArray? = null
            waitFor("real non-secure fixture pixels arrive through pinned TLS", 30000) {
                val bytes = try { c.frame() } catch (_: Exception) { ByteArray(0) }
                if (bytes.isEmpty()) false else {
                    val image = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    if (image == null) false else try {
                        val center = image.getPixel(image.width/2, image.height/2)
                        val valid = image.width in 1..1280 && image.height in 1..1280 && Color.red(center) > 170 && Color.green(center) > 170
                        if (valid) captured = bytes
                        valid
                    } finally { image.recycle() }
                }
            }
            val bytes = requireNotNull(captured)
            val evidence = File(context.getExternalFilesDir(null), "evidence").apply { mkdirs() }
            File(evidence, "connected-real-mediaprojection.jpg").writeBytes(bytes)
            context.stopService(Intent(context, BridgeMirrorService::class.java))
            waitFor("notification/service stop tears down sharing") { !BridgeMirrorService.running && host.viewer == null }
            instrumentation.sendStatus(0, Bundle().apply { putString("stream", "\nBRIDGE_CAPTURE_EVIDENCE " + JSONObject().put("stop_tested", true).put("media_projection_consent", true)
                .put("cancel_tested", true).put("foreground_service", true).put("frame_bytes", bytes.size).put("sha256", BridgeRules.sha(bytes))
                .put("fixture_only", true).put("remote_input", false).toString() + "\n") })
        } finally { context.stopService(Intent(context, BridgeMirrorService::class.java)); client?.forget(); scenario.close(); reference.get()?.close() }
    }
}
