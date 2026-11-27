package org.oguzdows.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.util.regex.Pattern;
import static org.junit.Assert.*;

/** Explicit CI-only network acceptance: official pinned F-Droid index + one hashed APK. */
@RunWith(AndroidJUnit4.class)
public final class LiveRepositoryTest {
    private void evidence(String text) {
        Bundle status = new Bundle(); status.putString("stream", "\n" + text + "\n");
        InstrumentationRegistry.getInstrumentation().sendStatus(0, status);
    }
    @Test public void officialSignedCatalogAndApkCanBeFetchedAndReviewedWithoutInstalling() throws Exception {
        assertTrue("emulator only", Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"));
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        JSONObject info = FdroidRepository.sync(context);
        assertTrue("real catalog, not the 24-item curated list", info.getLong("apps") > 1000);
        assertTrue("compatible catalog is substantive", info.getLong("compatible") > 100);
        assertTrue("only pinned official source or mirror", info.getString("source").equals(FdroidRepository.PRIMARY) || info.getString("source").equals(FdroidRepository.MIRROR));
        evidence("LIVE_REPO_EVIDENCE " + info.toString()); // Catalog proof alone is not yet APK review proof.
        JSONArray rows = CatalogDb.get(context).search("com.beemdevelopment.aegis", true);
        JSONObject app = null;
        for (int i = 0; i < rows.length(); i++) if (rows.getJSONObject(i).getString("package").equals("com.beemdevelopment.aegis")) app = rows.getJSONObject(i);
        assertNotNull("known F-Droid package has a compatible signed-index APK", app);
        File apk = FdroidRepository.downloadApk(context, app);
        assertEquals("signed-index APK size", app.getLong("size"), apk.length());
        PackageInfo archive = context.getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), 0);
        assertNotNull("downloaded APK metadata", archive); assertEquals(app.getString("package"), archive.packageName); assertEquals(app.getLong("code"), archive.getLongVersionCode());
        try { context.getPackageManager().getPackageInfo("com.beemdevelopment.aegis", 0); fail("live fixture must not be preinstalled"); }
        catch (PackageManager.NameNotFoundException expected) { }
        UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        try (ActivityScenario<SourceStoreActivity> store = ActivityScenario.launch(
                new Intent(context, SourceStoreActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))) {
            if (DeviceDiagnostics.INSTANCE.find(device, By.text("Mağaza · canlı kaynaklar"), 25000) == null) {
                DeviceDiagnostics.INSTANCE.missing(device, "native-live-store", true);
            }
            SystemClock.sleep(1500);
            File folder = new File(context.getExternalFilesDir(null), "evidence"); folder.mkdirs();
            assertTrue("live Store screenshot", device.takeScreenshot(new File(folder, "native-live-fdroid-store.png")));
            Intent review = new Intent(context, InstallReviewActivity.class)
                .putExtra("privateApk", apk.getAbsolutePath()).putExtra("expectedHash", app.getString("hash"))
                .putExtra("expectedPackage", app.getString("package")).putExtra("expectedVersion", app.getLong("code"));
            store.onActivity(a -> a.startActivity(review));
            Pattern cancelText = Pattern.compile(Pattern.quote("Vazgeç"), Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
            UiObject2 cancel = device.wait(Until.findObject(By.text(cancelText)), 25000);
            assertNotNull("live APK private-copy review cancellation", cancel);
            assertTrue("live APK review screenshot", device.takeScreenshot(new File(folder, "native-live-apk-review.png"))); cancel.click();
            device.pressBack();
            try { context.getPackageManager().getPackageInfo("com.beemdevelopment.aegis", 0); fail("cancel must not install live APK"); }
            catch (PackageManager.NameNotFoundException expected) { }
            evidence("APK_REVIEW " + app.getString("package") + " code=" + app.getLong("code") + " sha256=" + app.getString("hash") + " bytes=" + app.getLong("size") + " installed=false");
        }
    }
}
