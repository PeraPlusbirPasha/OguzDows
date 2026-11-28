package org.oguzdows.mobile;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import static org.junit.Assert.*;

/** Real Android JAR signature verification, SQLite rollback and schema/API/ABI tests, no network mocks. */
@RunWith(AndroidJUnit4.class)
public final class RepositorySecurityTest {
    private final Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
    private File fixture(String name) throws Exception {
        File output = new File(context.getCacheDir(), "test-" + java.util.UUID.randomUUID());
        try (InputStream in = InstrumentationRegistry.getInstrumentation().getContext().getAssets().open("generated/" + name);
             FileOutputStream out = new FileOutputStream(output)) {
            byte[] bytes = new byte[16384]; int n; while ((n = in.read(bytes)) != -1) out.write(bytes, 0, n);
        } return output;
    }
    @Test public void signaturePinTamperAndUnsignedInputsAreEnforced() throws Exception {
        File metadata = fixture("metadata.json"), good = fixture("signed-index.jar"), tampered = fixture("tampered-index.jar"), unsigned = fixture("unsigned-index.jar");
        File output = new File(context.getCacheDir(), "verified-test-index.json");
        try {
            String pin = new JSONObject(new String(Files.readAllBytes(metadata.toPath()), StandardCharsets.UTF_8)).getString("certificateSha256");
            assertNotEquals("test key never replaces production anchor", FdroidRepository.CERTIFICATE_SHA256, pin);
            FdroidRepository.verifyAndExtract(good, output, pin); assertTrue(output.length() > 0);
            for (File rejected : new File[]{tampered, unsigned}) {
                try { FdroidRepository.verifyAndExtract(rejected, output, pin); fail("untrusted JAR accepted"); }
                catch (SecurityException expected) { assertFalse(output.exists()); }
            }
            try { FdroidRepository.verifyAndExtract(good, output, FdroidRepository.CERTIFICATE_SHA256); fail("wrong signing key accepted"); }
            catch (SecurityException expected) { assertFalse(output.exists()); }
        } finally { for (File file : new File[]{metadata, good, tampered, unsigned, output}) file.delete(); }
    }
    @Test public void verifiedCatalogChoosesCompatibleVersionAndRejectsRollbackAtomically() throws Exception {
        File valid = fixture("index.json"), rollback = fixture("rollback.json");
        String name = "catalog-security-test.db"; context.deleteDatabase(name);
        try (CatalogDb db = new CatalogDb(context, name)) {
            db.replaceVerified(valid, "test-fixture-not-live"); long timestamp = db.timestamp();
            JSONArray rows = db.search("org.oguzdows.fixture", true); assertEquals(1, rows.length());
            JSONObject row = rows.getJSONObject(0);
            assertEquals(1, row.getLong("code")); // Later versions have invalid API/ABI or KnownVuln.
            assertEquals("Rıfkı test paketi", row.getString("name"));
            assertEquals(0, db.search("%", true).length()); // LIKE wildcards are escaped, not executable.
            try { db.replaceVerified(rollback, "test-fixture-not-live"); fail("rollback accepted"); }
            catch (Exception expected) { assertEquals(timestamp, db.timestamp()); assertEquals(1, db.search("org.oguzdows.fixture", true).length()); }
        } finally { valid.delete(); rollback.delete(); context.deleteDatabase(name); }
    }
    @Test public void networkEndpointsRejectCredentialsCleartextAndTraversalBeforeConnecting() throws Exception {
        File output = new File(context.getCacheDir(), "rejected-download");
        for (String url : new String[]{"http://f-droid.org/repo/index-v1.jar", "https://user:pass@f-droid.org/repo/index-v1.jar",
            "https://f-droid.org.evil.test/repo/index-v1.jar", "https://f-droid.org/repo/../secret", "https://f-droid.org/repo/%2e%2e/secret",
            "https://f-droid.org:8443/repo/index-v1.jar", "https://ftp.fau.de/other/file.apk"}) {
            try { FdroidRepository.download(url, output, 1024, -1, null); fail("unapproved endpoint connected"); }
            catch (SecurityException expected) { }
        }
        assertFalse(output.exists());
    }
}
