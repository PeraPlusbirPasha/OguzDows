package org.oguzdows.mobile;

import android.content.Context;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.security.CodeSigner;
import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Set;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

import javax.net.ssl.HttpsURLConnection;

/** Fixed-source HTTPS + pinned signed index + SHA-256 APKs. Never treats TLS alone as repo trust. */
public final class FdroidRepository {
    public static final String PRIMARY = "https://f-droid.org/repo";
    public static final String MIRROR = "https://ftp.fau.de/fdroid/repo";
    // SHA-256 of the F-Droid repo X.509 certificate, not the APK signing certificate.
    // Provenance: store-trust.json pins the upstream fdroidclient source revision.
    public static final String CERTIFICATE_SHA256 = "43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab";
    private static final long INDEX_LIMIT = 48L * 1024 * 1024, JSON_LIMIT = 256L * 1024 * 1024;
    private FdroidRepository() {}

    public static synchronized org.json.JSONObject sync(Context context) throws Exception {
        File directory = new File(context.getCacheDir(), "repo-sync");
        if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Katalog önbelleği açılamadı.");
        if (directory.getUsableSpace() < 384L * 1024 * 1024) throw new Exception("İmzalı katalog eşitlemesi için en az 384 MiB boş alan gerekir.");
        File jar = new File(directory, "index-v1.jar"), json = new File(directory, "index-v1.json");
        try {
            String source = PRIMARY;
            try { download(PRIMARY + "/index-v1.jar", jar, INDEX_LIMIT, -1, null); }
            catch (java.io.IOException networkFailure) { source = MIRROR; download(MIRROR + "/index-v1.jar", jar, INDEX_LIMIT, -1, null); }
            verifyAndExtract(jar, json, CERTIFICATE_SHA256);
            CatalogDb.get(context).replaceVerified(json, source);
            return CatalogDb.get(context).info();
        } finally { jar.delete(); json.delete(); }
    }
    /** Visible for signature/tamper tests. Caller-supplied anchors are never accepted by production UI. */
    static void verifyAndExtract(File jarPath, File output, String pinnedCertificate) throws Exception {
        if (jarPath.length() < 1 || jarPath.length() > INDEX_LIMIT) throw new Exception("İndeks boyut sınırı aşıldı.");
        Set<String> names = new HashSet<>(); int count = 0;
        try (ZipFile zip = new ZipFile(jarPath)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement(); String name = entry.getName();
                if (++count > 32 || !names.add(name) || entry.getSize() < 0 || entry.getSize() > ("index-v1.json".equals(name) ? JSON_LIMIT : 2L * 1024 * 1024))
                    throw new SecurityException("İndeks arşivi sınırı veya yinelenen girdi.");
                if (!"index-v1.json".equals(name) && !name.startsWith("META-INF/")) throw new SecurityException("Beklenmeyen indeks girdisi.");
            }
        }
        try (JarFile jar = new JarFile(jarPath, true)) {
            JarEntry entry = jar.getJarEntry("index-v1.json");
            if (entry == null) throw new SecurityException("İmzalı katalog girdisi yok.");
            long total = 0;
            try (InputStream in = jar.getInputStream(entry); FileOutputStream out = new FileOutputStream(output)) {
                byte[] buffer = new byte[64 * 1024]; int n;
                // Reading to EOF triggers JAR digest/signature verification before any JSON is trusted.
                while ((n = in.read(buffer)) != -1) {
                    total += n; if (total > JSON_LIMIT || Thread.currentThread().isInterrupted()) throw new SecurityException("Açılmış indeks sınırı aşıldı veya durduruldu.");
                    out.write(buffer, 0, n);
                }
            }
            CodeSigner[] signers = entry.getCodeSigners();
            if (signers == null || signers.length != 1 || signers[0].getSignerCertPath().getCertificates().isEmpty())
                throw new SecurityException("Katalog tek, doğrulanmış imzacı taşımıyor.");
            X509Certificate cert = (X509Certificate)signers[0].getSignerCertPath().getCertificates().get(0);
            cert.checkValidity();
            String actual = PlatformRules.hex(MessageDigest.getInstance("SHA-256").digest(cert.getEncoded()));
            if (!MessageDigest.isEqual(actual.getBytes(java.nio.charset.StandardCharsets.US_ASCII), pinnedCertificate.getBytes(java.nio.charset.StandardCharsets.US_ASCII)))
                throw new SecurityException("F-Droid depo sertifikası sabitlenen anahtarla eşleşmiyor.");
        } catch (Exception error) { output.delete(); throw error; }
    }
    public static File downloadApk(Context context, org.json.JSONObject app) throws Exception {
        String apk = app.getString("apk"), hash = app.getString("hash"); long size = app.getLong("size");
        if (!PlatformRules.apkName(apk) || !hash.matches("[a-f0-9]{64}") || size < 1 || size > InstallReviewActivity.MAX_APK) throw new SecurityException("Geçersiz imzalı paket kaydı.");
        String source = CatalogDb.get(context).info().optString("source", PRIMARY);
        if (!PRIMARY.equals(source) && !MIRROR.equals(source)) throw new SecurityException("Bilinmeyen depo kaynağı.");
        File file = InstallReviewActivity.allocate(context);
        try { download(source + "/" + apk, file, InstallReviewActivity.MAX_APK, size, hash); return file; }
        catch (Exception error) { file.delete(); throw error; }
    }
    private static boolean allowed(URL url) {
        String path = url.getPath();
        return "https".equals(url.getProtocol()) && url.getUserInfo() == null && (url.getPort() == -1 || url.getPort() == 443)
            && url.getQuery() == null && url.getRef() == null
            && (("f-droid.org".equals(url.getHost()) && path.startsWith("/repo/"))
                || ("ftp.fau.de".equals(url.getHost()) && path.startsWith("/fdroid/repo/")))
            && !path.contains("..") && !path.contains("%");
    }
    static void download(String address, File target, long limit, long expectedSize, String expectedHash) throws Exception {
        URL url = new URL(address);
        for (int redirect = 0; redirect <= 3; redirect++) {
            if (!allowed(url)) throw new SecurityException("HTTPS depo adresi izinli değil.");
            HttpsURLConnection connection = (HttpsURLConnection)url.openConnection();
            connection.setConnectTimeout(20000); connection.setReadTimeout(60000); connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "OguzDows-Mobile/0.2 (explicit repository sync)");
            connection.setRequestProperty("Accept-Encoding", "identity");
            try {
                int code = connection.getResponseCode();
                if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308) {
                    String location = connection.getHeaderField("Location"); if (location == null) throw new java.io.IOException("Depo yönlendirmesi eksik.");
                    url = new URL(url, location); continue;
                }
                if (code != 200) throw new java.io.IOException("Depo HTTP yanıtı: " + code);
                long length = connection.getContentLengthLong();
                if (length > limit || (length >= 0 && expectedSize >= 0 && length != expectedSize)) throw new SecurityException("Depo dosya boyutu uyuşmuyor.");
                MessageDigest digest = MessageDigest.getInstance("SHA-256"); long total = 0;
                try (InputStream in = connection.getInputStream(); FileOutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[64 * 1024]; int n;
                    while ((n = in.read(buffer)) != -1) {
                        total += n; if (total > limit || (expectedSize >= 0 && total > expectedSize) || Thread.currentThread().isInterrupted()) throw new SecurityException("İndirme sınırı aşıldı veya durduruldu.");
                        digest.update(buffer, 0, n); out.write(buffer, 0, n);
                    }
                }
                if (total < 1 || (expectedSize >= 0 && total != expectedSize)) throw new SecurityException("Eksik depo dosyası.");
                String actual = PlatformRules.hex(digest.digest());
                if (expectedHash != null && !actual.equals(expectedHash)) throw new SecurityException("İmzalı katalogdaki SHA-256 eşleşmiyor.");
                return;
            } finally { connection.disconnect(); }
        }
        throw new java.io.IOException("Çok fazla depo yönlendirmesi.");
    }
}
