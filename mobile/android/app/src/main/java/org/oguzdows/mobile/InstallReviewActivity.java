package org.oguzdows.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** SAF/download -> bounded immutable private copy -> review -> user-consented system installer. */
public final class InstallReviewActivity extends Activity {
    public static final long MAX_APK = 256L * 1024 * 1024;
    private static final int PICK = 41, INSTALL = 42;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private File reviewed;
    private String packageName, signer;
    private long version;
    private boolean busy;
    private NativeUi ui;

    @Override public void onCreate(Bundle state) {
        NativeUi.theme(this); super.onCreate(state); ui = new NativeUi(this);
        android.widget.LinearLayout root = ui.column(); setContentView(root); NativeUi.insets(root);
        root.addView(ui.text("Önce incele. Sonra karar ver.", 26, true));
        root.addView(ui.text("Tek APK · en çok 256 MiB. Split APK/APKS/XAPK, paket deposu, root ve sessiz yükleme yok. Sistem imza/kurulum politikaları son sözü söyler.", 14, false));
        root.addView(ui.button("APK dosyası seç", this::choose));
        root.addView(ui.button("Seçili kopyayı yeniden incele", () -> { if (reviewed != null && !busy) inspectAsync(reviewed); }));
        root.addView(ui.button("Geri", this::finish));
        String path = getIntent().getStringExtra("privateApk");
        if (path == null) { if (state == null) choose(); }
        else {
            try {
                File file = new File(path).getCanonicalFile();
                File parent = new File(getCacheDir(), "apk-inbox").getCanonicalFile();
                if (!parent.equals(file.getParentFile()) || !file.getName().matches("[a-f0-9-]{36}\\.apk")) throw new SecurityException();
                reviewed = file; inspectAsync(file);
            } catch (Exception error) { fail("Özel APK yolu geçerli değil."); }
        }
    }
    public static synchronized File allocate(Context context) throws Exception {
        File directory = new File(context.getCacheDir(), "apk-inbox");
        if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Özel inceleme alanı açılamadı.");
        int retained = 0; File[] previous = directory.listFiles();
        if (previous != null) for (File old : previous) {
            if (old.isFile() && old.lastModified() < System.currentTimeMillis() - 86400000L) old.delete();
            if (old.exists()) retained++;
        }
        if (retained >= 3) throw new Exception("En çok üç özel APK kopyası tutulur. Eski kopyalar 24 saat sonra yeni seçimde temizlenir; sistem uygulama ayarından önbelleği de temizleyebilirsin.");
        if (directory.getUsableSpace() < 64L * 1024 * 1024) throw new Exception("APK için yeterli boş alan yok.");
        File file = new File(directory, UUID.randomUUID() + ".apk");
        if (!file.createNewFile()) throw new Exception("Özel dosya ayrılamadı."); return file;
    }
    private void choose() {
        if (busy) return;
        Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType("application/vnd.android.package-archive")
            .putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/vnd.android.package-archive", "application/octet-stream"});
        try { startActivityForResult(pick, PICK); }
        catch (ActivityNotFoundException error) { fail("Sistem belge seçicisi bulunamadı."); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == PICK && result == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData(); if (!"content".equals(uri.getScheme()) || busy) return;
            busy = true;
            worker.execute(() -> {
                File file = null;
                try {
                    String name = "";
                    try (Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                        if (c != null && c.moveToFirst()) name = c.getString(0);
                    }
                    if (name == null || name.length() > 255 || !name.toLowerCase(Locale.ROOT).endsWith(".apk")) throw new Exception("Tek .apk dosyası seç; split paket kapsayıcıları desteklenmez.");
                    file = allocate(this);
                    try (InputStream in = getContentResolver().openInputStream(uri); FileOutputStream out = new FileOutputStream(file)) {
                        if (in == null) throw new Exception("Belge okunamadı.");
                        byte[] buffer = new byte[64 * 1024]; long total = 0; int n;
                        while ((n = in.read(buffer)) != -1) {
                            total += n; if (total > MAX_APK || Thread.currentThread().isInterrupted()) throw new Exception("256 MiB sınırı aşıldı veya inceleme durduruldu.");
                            out.write(buffer, 0, n);
                        }
                    }
                    reviewed = file; inspect(file);
                } catch (Exception error) { if (file != null) file.delete(); fail(error.getMessage()); }
            });
        } else if (request == INSTALL) {
            boolean verified = false;
            if (result == RESULT_OK && packageName != null) {
                try {
                    PackageInfo installed = getPackageManager().getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES);
                    verified = installed.getLongVersionCode() == version && signer != null
                        && signer.matches("[a-f0-9]{64}") && signer.equals(certificate(installed));
                } catch (Exception ignored) { }
            }
            final String text = verified
                ? "Sistem yükleyicisi başarı döndürdü; yüklü paket sürümü ve ilk imzacı özeti incelenen kopyayla eşleşti."
                : "Doğrulanmış bir yükleme başarısı alınmadı. İşlem iptal edilmiş, sistemce reddedilmiş veya sonuç sorgusu görünür olmayabilir. Uygulamalar listesini kontrol et; yüklenmiş gibi işaretlenmedi.";
            getSharedPreferences("installer-state", MODE_PRIVATE).edit().putBoolean("verified", verified).putLong("at", System.currentTimeMillis()).apply();
            new AlertDialog.Builder(this).setTitle(verified ? "Yükleme doğrulandı" : "Yükleme doğrulanmadı").setMessage(text).setPositiveButton("Tamam", null).show();
        }
    }
    private void inspectAsync(File file) { busy = true; worker.execute(() -> { try { inspect(file); } catch (Exception e) { fail(e.getMessage()); } }); }
    private void inspect(File file) throws Exception {
        if (!file.isFile() || file.length() < 1 || file.length() > MAX_APK) throw new Exception("APK kopyası yok veya boyut sınırını aşıyor.");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[64 * 1024]; int n;
            while ((n = in.read(buffer)) != -1) { if (Thread.currentThread().isInterrupted()) throw new Exception("İnceleme durduruldu."); hash.update(buffer, 0, n); }
        }
        String sha256 = PlatformRules.hex(hash.digest());
        String expectedHash = getIntent().getStringExtra("expectedHash");
        if (expectedHash != null && !expectedHash.equalsIgnoreCase(sha256)) throw new Exception("İmzalı depo indeksindeki SHA-256 eşleşmiyor; yükleme kapalı.");
        PackageInfo info = getPackageManager().getPackageArchiveInfo(file.getAbsolutePath(), PackageManager.GET_SIGNING_CERTIFICATES | PackageManager.GET_PERMISSIONS);
        if (info == null || info.applicationInfo == null || !PlatformRules.packageName(info.packageName)) throw new Exception("APK paket bilgisi okunamadı.");
        String expectedPackage = getIntent().getStringExtra("expectedPackage");
        if (expectedPackage != null && (!expectedPackage.equals(info.packageName) || getIntent().getLongExtra("expectedVersion", -1) != info.getLongVersionCode()))
            throw new Exception("İmzalı indeksin paket/sürüm bilgisi APK ile eşleşmiyor.");
        Set<String> abis = new HashSet<>();
        try (ZipFile zip = new ZipFile(file)) {
            java.util.Enumeration<? extends ZipEntry> entries = zip.entries(); int count = 0;
            while (entries.hasMoreElements()) {
                if (++count > 100000) throw new Exception("Çok fazla arşiv girdisi.");
                String name = entries.nextElement().getName(); String[] parts = name.split("/");
                if (parts.length >= 3 && "lib".equals(parts[0])) abis.add(parts[1]);
            }
        }
        boolean architecture = abis.isEmpty() || abis.stream().anyMatch(abi -> Arrays.asList(Build.SUPPORTED_ABIS).contains(abi));
        String cert = certificate(info);
        boolean compatible = architecture && info.applicationInfo.minSdkVersion <= Build.VERSION.SDK_INT
            && (Build.VERSION.SDK_INT < 35 || info.applicationInfo.targetSdkVersion >= 24) && cert.matches("[a-f0-9]{64}");
        String[] permissions = info.requestedPermissions == null ? new String[0] : info.requestedPermissions;
        String details = "Paket: " + info.packageName + "\nSürüm: " + info.versionName + " (" + info.getLongVersionCode() + ")"
            + "\nMinimum/hedef API: " + info.applicationInfo.minSdkVersion + "/" + info.applicationInfo.targetSdkVersion
            + "\nABI: " + (abis.isEmpty() ? "yerel kütüphane görünmüyor" : String.join(", ", abis))
            + "\nSHA-256: " + sha256 + "\nİlk imzacı özeti: " + cert
            + "\n\nBildirilen izinler (ilk 40):\n" + String.join("\n", Arrays.copyOf(permissions, Math.min(40, permissions.length)))
            + "\n\nİndeks/hash ve paket bilgisi zararlı yazılım taraması, GMS veya uygulamanın çalışacağı garantisi değildir. Android sistem yükleyicisi tam imza/politika/son kullanıcı onayını uygular."
            + (compatible ? "" : "\n\nAPI/ABI/hedef API veya imzacı özeti ön koşulu uyuşmuyor; yükleme düğmesi kapalı.");
        runOnUiThread(() -> {
            busy = false; if (isDestroyed() || isFinishing()) return;
            packageName = info.packageName; version = info.getLongVersionCode(); signer = cert;
            AlertDialog.Builder dialog = new AlertDialog.Builder(this).setTitle("APK · incelenen özel kopya").setMessage(details).setNegativeButton("Vazgeç", null);
            if (compatible) dialog.setPositiveButton("Sistem yükleyicisine geç", (d, w) -> install(file));
            dialog.show();
        });
    }
    private static String certificate(PackageInfo info) throws Exception {
        if (info.signingInfo == null) return "okunamadı";
        Signature[] signers = info.signingInfo.getApkContentsSigners();
        return signers == null || signers.length == 0 ? "okunamadı" : PlatformRules.hex(MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray()));
    }
    private void install(File file) {
        if (!getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(this).setTitle("Kaynak izni gerekiyor")
                .setMessage("Yalnız OğuzDows için bu özel kaynak iznini seçebilirsin. Dönüşte otomatik yükleme yapılmaz; seçili kopyayı yeniden inceleyip tekrar onaylamalısın.")
                .setPositiveButton("Kaynak ayarını aç", (d, w) -> startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))))
                .setNegativeButton("Vazgeç", null).show(); return;
        }
        Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".apk", file);
        Intent intent = new Intent(Intent.ACTION_INSTALL_PACKAGE).setDataAndType(uri, "application/vnd.android.package-archive")
            .putExtra(Intent.EXTRA_RETURN_RESULT, true).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.setClipData(android.content.ClipData.newRawUri("İncelenen özel APK kopyası", uri));
        try { startActivityForResult(intent, INSTALL); }
        catch (RuntimeException error) { fail("Sistem paket yükleyicisi açılamadı."); }
    }
    private void fail(String message) {
        runOnUiThread(() -> { busy = false; if (!isDestroyed() && !isFinishing()) new AlertDialog.Builder(this).setTitle("İnceleme tamamlanamadı").setMessage(message == null ? "Dosya okunamadı." : message).setPositiveButton("Tamam", null).show(); });
    }
    @Override protected void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
