package org.oguzdows.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
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
import static org.junit.Assert.*;

/** Explicit CI-only network acceptance: official pinned F-Droid index + one hashed APK. */
@RunWith(AndroidJUnit4.class)
public final class LiveRepositoryTest {
    @Test public void officialSignedCatalogAndApkCanBeFetchedAndReviewedWithoutInstalling() throws Exception {
        assertTrue("emulator only", Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish"));
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        JSONObject info = FdroidRepository.sync(context);
        assertTrue("real catalog, not the 24-item curated list", info.getLong("apps") > 1000);
        assertTrue(info.getLong("compatible") > 100);
        assertTrue(info.getString("source").equals(FdroidRepository.PRIMARY) || info.getString("source").equals(FdroidRepository.MIRROR));
        JSONArray rows = CatalogDb.get(context).search("com.beemdevelopment.aegis", true);
        JSONObject app = null;
        for (int i = 0; i < rows.length(); i++) if (rows.getJSONObject(i).getString("package").equals("com.beemdevelopment.aegis")) app = rows.getJSONObject(i);
        assertNotNull("known F-Droid package has a compatible signed-index APK", app);
        File apk = FdroidRepository.downloadApk(context, app);
        assertEquals(app.getLong("size"), apk.length());
        PackageInfo archive = context.getPackageManager().getPackageArchiveInfo(apk.getAbsolutePath(), 0);
        assertNotNull(archive); assertEquals(app.getString("package"), archive.packageName); assertEquals(app.getLong("code"), archive.getLongVersionCode());
        UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
        context.startActivity(new Intent(context, SourceStoreActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        assertTrue(device.wait(Until.hasObject(By.text("Mağaza · canlı kaynaklar")), 15000));
        SystemClock.sleep(1500);
        File folder = new File(context.getExternalFilesDir(null), "evidence"); folder.mkdirs();
        assertTrue(device.takeScreenshot(new File(folder, "native-live-fdroid-store.png")));
        context.startActivity(new Intent(context, InstallReviewActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .putExtra("privateApk", apk.getAbsolutePath()).putExtra("expectedHash", app.getString("hash"))
            .putExtra("expectedPackage", app.getString("package")).putExtra("expectedVersion", app.getLong("code")));
        UiObject2 cancel = device.wait(Until.findObject(By.text("Vazgeç")), 15000); assertNotNull(cancel);
        assertTrue(device.takeScreenshot(new File(folder, "native-live-apk-review.png"))); cancel.click();
        Bundle evidence = new Bundle(); evidence.putString("stream", "\nLIVE_REPO_EVIDENCE " + info.toString() + "\nAPK_REVIEW " + app.getString("package") + " code=" + app.getLong("code") + " sha256=" + app.getString("hash") + " bytes=" + app.getLong("size") + " installed=false\n");
        InstrumentationRegistry.getInstrumentation().sendStatus(0, evidence);
    }
}
