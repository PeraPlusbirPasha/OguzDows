package org.oguzdows.mobile;

import android.app.Instrumentation;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.os.Build;
import android.os.SystemClock;
import android.provider.Telephony;
import android.telecom.Call;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

import static org.junit.Assert.*;

/** Genuine emulator radio/provider/installer tests. Refuses physical hardware to prevent paid test traffic. */
@RunWith(AndroidJUnit4.class)
public final class NativeDeviceTest {
    private final Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
    private final Context context = instrumentation.getTargetContext();
    private final UiDevice device = UiDevice.getInstance(instrumentation);
    private ActivityScenario<HomeActivity> scenario;

    @Before public void emulatorOnly() throws Exception {
        assertTrue("These tests MUST NOT place traffic from a physical SIM", Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"));
        device.wakeUp(); device.pressMenu();
    }
    @After public void close() { if (scenario != null) scenario.close(); }
    private interface Check { boolean yes() throws Exception; }
    private void waitFor(String description, long timeout, Check condition) throws Exception {
        long end = SystemClock.elapsedRealtime() + timeout;
        do { if (condition.yes()) return; SystemClock.sleep(200); } while (SystemClock.elapsedRealtime() < end);
        fail("Timed out: " + description);
    }
    private void home() throws Exception {
        scenario = ActivityScenario.launch(new Intent(context, HomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        // A cold WebView can discard evaluateJavascript callbacks during its initial navigation.
        // Wait for a visible committed page before probing JS; never retry a paid bridge action.
        waitFor("visible bundled page committed", 60000, () -> {
            AtomicReference<Boolean> committed = new AtomicReference<>(false);
            scenario.onActivity(a -> committed.set(a.hasWindowFocus() && a.webView.getProgress() == 100 && a.webView.getHeight() > 0));
            return committed.get();
        });
        waitFor("bundled rich UI + secure bridge", 30000,
            () -> "true".equals(js("!!window.OguzPlatform && !!document.querySelector('.phone-content')")));
        postJs("location.hash='/home'");
        waitFor("home route", 15000, () -> "true".equals(js("!!document.querySelector('.home-content')")));
    }
    private void postJs(String code) {
        scenario.onActivity(activity -> activity.webView.evaluateJavascript(code, null));
    }
    private String js(String code) throws Exception {
        AtomicReference<String> result = new AtomicReference<>(); CountDownLatch latch = new CountDownLatch(1);
        scenario.onActivity(activity -> activity.webView.evaluateJavascript(code, value -> { result.set(value); latch.countDown(); }));
        boolean responded = latch.await(20, TimeUnit.SECONDS);
        AtomicReference<String> debug = new AtomicReference<>("");
        if (!responded) scenario.onActivity(a -> debug.set(" progress=" + a.webView.getProgress()
            + " focus=" + a.hasWindowFocus() + " visible=" + a.webView.getWindowVisibility() + " url=" + a.webView.getUrl()));
        assertTrue("WebView JS callback: " + code.substring(0, Math.min(100, code.length())) + debug.get(), responded);
        return result.get();
    }
    private String begin(String action, JSONObject args) throws Exception {
        String id = "test-" + java.util.UUID.randomUUID();
        JSONObject request = new JSONObject().put("id", id).put("action", action).put("args", args);
        // Native consent may immediately cover the WebView; do not wait on its JS return before tapping consent.
        postJs("(()=>{window.__nativeTestReply=null;const old=window.OguzPlatform.onmessage;window.OguzPlatform.onmessage=(e)=>{try{if(old)old(e);}catch(_){}try{const r=JSON.parse(e.data);if(r.id===" + JSONObject.quote(id) + "){window.__nativeTestReply=r;window.OguzPlatform.onmessage=old;}}catch(_){}};window.OguzPlatform.postMessage(" + JSONObject.quote(request.toString()) + ");})()");
        return id;
    }
    private JSONObject response() throws Exception {
        waitFor("native reply", 15000, () -> !"null".equals(js("window.__nativeTestReply || null")));
        return new JSONObject(js("window.__nativeTestReply"));
    }
    private JSONObject request(String action, JSONObject args) throws Exception { begin(action, args); return response(); }
    private static Pattern buttonText(String text) {
        // Platform AlertDialog buttons may be uppercased by the system theme (including Turkish İ).
        return Pattern.compile(Pattern.quote(text), Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
    }
    private void tap(String text) {
        UiObject2 object = device.wait(Until.findObject(By.text(buttonText(text))), 20000);
        assertNotNull("Button not found: " + text, object); object.click();
    }
    private JSONObject call() {
        AtomicReference<JSONObject> state = new AtomicReference<>();
        instrumentation.runOnMainSync(() -> { try { state.set(CallController.snapshot()); } catch (Exception error) { throw new RuntimeException(error); } });
        return state.get();
    }
    private void ready(String name) throws Exception {
        try (FileOutputStream out = new FileOutputStream(new File(context.getExternalFilesDir(null), name))) {
            out.write("ready".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
    }
    private void screenshot(String name) {
        File folder = new File(context.getExternalFilesDir(null), "evidence"); folder.mkdirs();
        assertTrue(device.takeScreenshot(new File(folder, name + ".png")));
    }

    @Test public void bundledBridgeRolesValidationAndIsolation() throws Exception {
        home();
        JSONObject status = request("status", new JSONObject()).getJSONObject("result");
        assertEquals("android", status.getString("platform"));
        assertTrue("real default dialer role", status.getBoolean("dialerRole"));
        assertTrue("real default SMS role", status.getBoolean("smsRole"));
        assertFalse(status.getBoolean("modelConnected")); assertFalse(status.getBoolean("gmsBundled"));
        assertFalse(status.getBoolean("mmsSupported")); assertFalse(status.getBoolean("rcsSupported"));
        assertTrue(status.isNull("call"));
        assertFalse(request("call.place", new JSONObject().put("number", "*#06#")).getBoolean("ok"));
        assertFalse(request("messages.send", new JSONObject().put("number", "5551234").put("body", "\u0000")).getBoolean("ok"));
        assertFalse(request("shell.exec", new JSONObject().put("command", "id")).getBoolean("ok"));
        assertFalse(HomeActivity.isLocal(android.net.Uri.parse("https://appassets.androidplatform.net.evil.test/index.html")));
        assertFalse(HomeActivity.isLocal(android.net.Uri.parse("http://appassets.androidplatform.net/index.html")));
        assertFalse(HomeActivity.isLocal(android.net.Uri.parse("https://user@appassets.androidplatform.net/index.html")));
        assertFalse(HomeActivity.isLocal(android.net.Uri.parse("https://appassets.androidplatform.net:8443/index.html")));
        AudioManager audio = context.getSystemService(AudioManager.class);
        int before = audio.getStreamVolume(AudioManager.STREAM_MUSIC);
        String injection = "<script>if(window.OguzPlatform)window.OguzPlatform.postMessage(JSON.stringify({id:'subframe-test',action:'device.volume',args:{value:0}}))</script>";
        js("(()=>{const f=document.createElement('iframe');f.sandbox='allow-scripts';f.srcdoc=" + JSONObject.quote(injection) + ";document.body.appendChild(f);return true;})()");
        SystemClock.sleep(1000);
        assertEquals("subframe cannot change native volume", before, audio.getStreamVolume(AudioManager.STREAM_MUSIC));
        js("document.querySelectorAll('iframe').forEach(f=>f.remove())");
        postJs("location.hash='/phone'");
        waitFor("native dial button, not a tel handoff", 15000, () -> "true".equals(js("!!document.querySelector('[aria-label=\"OğuzDows içinde ara\"]')")));
        assertEquals("false", js("!!document.querySelector('a[href^=\"tel:\"]')"));
        screenshot("native-phone");
    }
    @Test public void paidActionsRequireFinalNativeConsent() throws Exception {
        home();
        begin("call.place", new JSONObject().put("number", "5551234")); tap("Vazgeç");
        assertFalse(response().getBoolean("ok")); assertNull(call());
        int before = SmsController.messages(context).length();
        begin("messages.send", new JSONObject().put("number", "5551234").put("body", "OguzDows_cancelled_fixture"));
        tap("Vazgeç"); assertFalse(response().getBoolean("ok"));
        assertEquals("cancelled SMS never entered the provider outbox", before, SmsController.messages(context).length());
    }
    @Test public void systemVolumeBrightnessAndNativeThemeAreReal() throws Exception {
        home(); AudioManager audio = context.getSystemService(AudioManager.class);
        int before = audio.getStreamVolume(AudioManager.STREAM_MUSIC);
        JSONObject result = request("device.volume", new JSONObject().put("value", 40)); assertTrue(result.getBoolean("ok"));
        int max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        assertEquals(Math.round(40 * max / 100f), audio.getStreamVolume(AudioManager.STREAM_MUSIC));
        assertFalse(request("device.volume", new JSONObject().put("value", 101)).getBoolean("ok"));
        assertTrue(request("device.brightness", new JSONObject().put("value", 40)).getBoolean("ok"));
        scenario.onActivity(a -> assertEquals(0.4f, a.getWindow().getAttributes().screenBrightness, 0.001f));
        assertTrue(request("device.theme", new JSONObject().put("value", "dark")).getBoolean("ok"));
        assertTrue(NativeUi.dark(context));
        assertTrue(request("device.theme", new JSONObject().put("value", "light")).getBoolean("ok"));
        assertTrue(request("device.brightness", new JSONObject().put("value", 100)).getBoolean("ok"));
        request("device.volume", new JSONObject().put("value", Math.round(before * 100f / max)));
    }
    @Test public void incomingSmsUsesTheRealProviderAndRichInbox() throws Exception {
        home(); ready("incoming-sms-ready");
        waitFor("SMS_DELIVER receiver inserted modem PDU", 30000, () -> {
            JSONArray rows = SmsController.messages(context);
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.getJSONObject(i);
                if (row.getString("body").equals("OguzDows_emulator_inbound")) return row.getInt("type") == Telephony.Sms.MESSAGE_TYPE_INBOX;
            } return false;
        });
        postJs("location.hash='/messages'");
        waitFor("rich inbox shows received provider SMS", 20000, () -> "true".equals(js("!!document.querySelector('.native-sms-history') && document.querySelector('.native-sms-history').textContent.includes('OguzDows_emulator_inbound')")));
        screenshot("native-sms-inbox");
    }
    @Test public void outgoingSmsWaitsForActualSentCallback() throws Exception {
        home();
        begin("messages.send", new JSONObject().put("number", "5551234").put("body", "OguzDows_emulator_outbound"));
        tap("SMS gönder");
        JSONObject queued = response(); assertTrue(queued.toString(), queued.getBoolean("ok"));
        assertEquals("queued", queued.getJSONObject("result").getString("state"));
        waitFor("radio sent callback, not optimistic JS success", 45000, () -> {
            JSONArray rows = SmsController.messages(context);
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.getJSONObject(i);
                if (!row.getString("body").equals("OguzDows_emulator_outbound")) continue;
                assertNotEquals("emulator has no carrier delivery receipt", Telephony.Sms.STATUS_COMPLETE, row.getInt("status"));
                assertNotEquals("radio rejected fixture SMS", Telephony.Sms.MESSAGE_TYPE_FAILED, row.getInt("type"));
                return row.getInt("type") == Telephony.Sms.MESSAGE_TYPE_SENT;
            } return false;
        });
    }
    @Test public void outgoingCallUsesTelecomAndOurInCallService() throws Exception {
        home(); begin("call.place", new JSONObject().put("number", "5551234")); tap("Aramayı başlat");
        // Telecom legitimately brings CallActivity forward; do not expect a background renderer to answer JS probes.
        waitFor("Telecom bound OğuzDows InCallService", 30000, () -> call() != null);
        JSONObject value = call();
        if (value.getInt("state") == Call.STATE_SELECT_PHONE_ACCOUNT) {
            instrumentation.runOnMainSync(() -> CallController.selectAccount(0));
        }
        waitFor("genuine outgoing Telecom state", 20000, () -> {
            JSONObject c = call(); if (c == null) return false;
            int state = c.getInt("state"); return state == Call.STATE_DIALING || state == Call.STATE_CONNECTING || state == Call.STATE_ACTIVE;
        });
        screenshot("native-call-outgoing");
        instrumentation.runOnMainSync(CallController::end);
        waitFor("outgoing call ends via Telecom", 15000, () -> call() == null || call().getInt("state") == Call.STATE_DISCONNECTED);
        context.startActivity(new Intent(context, HomeActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
        JSONObject requested = response(); assertTrue(requested.toString(), requested.getBoolean("ok"));
        assertEquals("requested", requested.getJSONObject("result").getString("state"));
    }
    @Test public void incomingCallCanBeAnsweredMutedAndEndedInOurUi() throws Exception {
        ready("incoming-ready");
        waitFor("injected incoming modem call", 30000, () -> call() != null && call().getInt("state") == Call.STATE_RINGING);
        context.startActivity(new Intent(context, CallActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        tap("Yanıtla");
        waitFor("Telecom ACTIVE after answering virtual radio", 20000, () -> call() != null && call().getInt("state") == Call.STATE_ACTIVE);
        screenshot("native-call-active");
        tap("Mikrofonu sustur");
        waitFor("InCallService audio mute callback", 10000, () -> call() != null && call().getBoolean("muted"));
        tap("Mikrofonu aç");
        waitFor("InCallService audio unmute callback", 10000, () -> call() != null && !call().getBoolean("muted"));
        tap("Görüşmeyi bitir");
        waitFor("real call removal/disconnection", 15000, () -> call() == null || call().getInt("state") == Call.STATE_DISCONNECTED);
    }
    @Test public void localApkReviewCancelAndSystemInstall() throws Exception {
        home(); // Start review from a visible activity, not an API-35 background-activity-launch exception.
        boolean installed;
        try { context.getPackageManager().getPackageInfo("org.oguzdows.fixture", 0); installed = true; }
        catch (PackageManager.NameNotFoundException missing) { installed = false; }
        assertFalse("fixture must not be preinstalled", installed);
        File file = InstallReviewActivity.allocate(context);
        try (InputStream in = instrumentation.getContext().getAssets().open("generated/fixture.apk"); FileOutputStream out = new FileOutputStream(file)) {
            byte[] buffer = new byte[16384]; int n; while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
        }
        Intent review = new Intent(context, InstallReviewActivity.class).putExtra("privateApk", file.getAbsolutePath()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        scenario.onActivity(a -> a.startActivity(review));
        assertTrue("private APK review ready", device.wait(Until.hasObject(By.text(buttonText("Sistem yükleyicisine geç"))), 25000));
        screenshot("native-apk-review"); tap("Vazgeç");
        try { context.getPackageManager().getPackageInfo("org.oguzdows.fixture", 0); fail("review cancellation must not install"); }
        catch (PackageManager.NameNotFoundException expected) { }
        device.pressBack(); // Close the first review Activity after cancelling its dialog.
        scenario.onActivity(a -> a.startActivity(review)); tap("Sistem yükleyicisine geç");
        UiObject2 install = device.wait(Until.findObject(By.text(Pattern.compile("(?i)install|yükle"))), 20000);
        assertNotNull("real system installer final consent", install); screenshot("system-installer-consent"); install.click();
        waitFor("inert fixture actually installed by OS", 30000, () -> {
            try { return context.getPackageManager().getPackageInfo("org.oguzdows.fixture", 0).getLongVersionCode() == 1; }
            catch (PackageManager.NameNotFoundException missing) { return false; }
        });
        waitFor("verified installer return + installed signer/version", 15000,
            () -> context.getSharedPreferences("installer-state", Context.MODE_PRIVATE).getBoolean("verified", false));
        screenshot("native-install-verified");
    }
}
