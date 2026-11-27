package org.oguzdows.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Signed live F-Droid catalog + real installed-version comparisons; Play and local APK remain separate. */
public final class SourceStoreActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final List<JSONObject> items = new ArrayList<>();
    private NativeUi ui;
    private TextView status;
    private EditText query;
    private CheckBox compatible, updates;
    private Button refresh;
    private CatalogAdapter adapter;
    private boolean busy;
    private int generation;
    private final Runnable search = this::search;

    @Override public void onCreate(Bundle saved) {
        NativeUi.theme(this); super.onCreate(saved); ui = new NativeUi(this);
        LinearLayout root = ui.column(); setContentView(root); NativeUi.insets(root);
        root.addView(ui.text("Mağaza · canlı kaynaklar", 25, true));
        root.addView(ui.text("F-Droid · sabitlenmiş depo imzası\nGoogle Play ve yerel APK, ayrı güven/izin yollarıdır. GNOME Software bu APK altyapısının yerine geçmez.", 12, false));
        status = ui.text("Yerel katalog okunuyor…", 12, false); status.setContentDescription("repo-status"); root.addView(status);
        refresh = ui.button("F-Droid kataloğunu eşitle", this::confirmSync); root.addView(refresh);
        LinearLayout sources = new LinearLayout(this);
        Button apk = ui.button("Yerel APK", () -> startActivity(new Intent(this, InstallReviewActivity.class)));
        Button play = ui.button("Google Play", this::play);
        sources.addView(apk, new LinearLayout.LayoutParams(0, -2, 1)); sources.addView(play, new LinearLayout.LayoutParams(0, -2, 1)); root.addView(sources);
        query = new EditText(this); query.setHint("Binlerce uygulamada isim/paket ara…"); query.setTextColor(ui.ink); query.setSingleLine(true);
        query.setContentDescription("Canlı katalogda ara"); query.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(80)}); root.addView(query);
        LinearLayout filters = new LinearLayout(this);
        compatible = new CheckBox(this); compatible.setText("API/ABI uygun"); compatible.setTextColor(ui.ink); compatible.setChecked(true);
        updates = new CheckBox(this); updates.setText("Güncellemeler"); updates.setTextColor(ui.ink);
        filters.addView(compatible); filters.addView(updates); root.addView(filters);
        compatible.setOnCheckedChangeListener((button, checked) -> scheduleSearch()); updates.setOnCheckedChangeListener((button, checked) -> scheduleSearch());
        query.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { scheduleSearch(); }
            public void afterTextChanged(Editable editable) {}
        });
        ListView list = new ListView(this); adapter = new CatalogAdapter(); list.setAdapter(adapter);
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1)); list.setOnItemClickListener((p, v, position, id) -> detail(items.get(position)));
        root.addView(ui.button("OğuzDows’a dön", this::finish));
    }
    @Override protected void onResume() { super.onResume(); if (query != null) scheduleSearch(); }
    private void scheduleSearch() { handler.removeCallbacks(search); handler.postDelayed(search, 250); }
    private void search() {
        String text = query.getText().toString(); boolean onlyCompatible = compatible.isChecked(), onlyUpdates = updates.isChecked(); int revision = ++generation;
        worker.execute(() -> {
            try {
                // Search limit is explicit; updates are comparisons within these matching rows, not a universal updater.
                JSONArray rows = CatalogDb.get(this).search(text, onlyCompatible); JSONObject info = CatalogDb.get(this).info();
                List<JSONObject> next = new ArrayList<>();
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject row = rows.getJSONObject(i); long installed = installedVersion(row.getString("package"));
                    row.put("installedCode", installed);
                    if (!onlyUpdates || (installed >= 0 && !row.isNull("code") && row.getLong("code") > installed)) next.add(row);
                }
                runOnUiThread(() -> {
                    if (isDestroyed() || revision != generation) return;
                    items.clear(); items.addAll(next); adapter.notifyDataSetChanged();
                    long count = info.optLong("apps");
                    String timestamp = info.has("timestamp") ? DateFormat.getDateTimeInstance().format(new Date(info.optLong("timestamp"))) : "henüz yok";
                    status.setText(count == 0 ? "Henüz eşitlenmiş katalog yok. Ağ erişimi yalnız onayından sonra başlar."
                        : count + " uygulama · " + info.optLong("compatible") + " uygun sürüm\nİmzalı indeks: " + timestamp
                            + "\n" + next.size() + " sonuç (en çok 80 eşleşme); güncelleme filtresi yalnız bu eşleşmeleri karşılaştırır."
                            + (System.currentTimeMillis() - info.optLong("timestamp") > 7L * 86400000 ? "\nKatalog 7 günden eski; kurmadan önce eşitle." : ""));
                });
            } catch (Exception error) { fail("Katalog okunamadı. Önceki doğrulanmış katalog silinmedi."); }
        });
    }
    private long installedVersion(String pkg) {
        try { return getPackageManager().getPackageInfo(pkg, 0).getLongVersionCode(); }
        catch (Exception ignored) { return -1; } // Invisible/non-installed are not asserted installed.
    }
    private void confirmSync() {
        if (busy) return;
        new AlertDialog.Builder(this).setTitle("F-Droid eşitlemesini onayla")
            .setMessage("F-Droid resmî deposundan, ağ hatasında resmî FAU aynasından imzalı katalog indirilecek. IP/ağ bilgisi depoya gider; kişiler, SMS, notlar ve yüklü uygulama listen gönderilmez.\n\nİndeks en çok 48 MiB; açılmış JSON en çok 256 MiB. İmza/sertifika/zaman damgası doğrulanmadan katalog değiştirilmez. Otomatik APK indirme, yükleme veya güncelleme yok.")
            .setPositiveButton("Kataloğu indir", (d, w) -> {
                busy = true; refresh.setEnabled(false); status.setText("İmzalı katalog indiriliyor ve doğrulanıyor…");
                worker.execute(() -> {
                    try { FdroidRepository.sync(this); runOnUiThread(() -> { if (!isDestroyed()) { busy = false; refresh.setEnabled(true); scheduleSearch(); } }); }
                    catch (Exception error) { runOnUiThread(() -> { if (!isDestroyed()) { busy = false; refresh.setEnabled(true); status.setText("Eşitleme başarısız; önceki katalog korundu."); fail(error instanceof SecurityException ? "İmza veya bütünlük doğrulanmadı. Katalog kullanılmadı." : error.getMessage()); } }); }
                });
            }).setNegativeButton("Vazgeç", null).show();
    }
    private void detail(JSONObject row) {
        try {
            boolean installable = !row.isNull("apk"); long installed = installedVersion(row.getString("package"));
            String description = row.getString("summary") + "\n\nPaket: " + row.getString("package") + "\nLisans: " + row.optString("license")
                + "\nF-Droid uyarıları: " + (row.optString("anti").isEmpty() ? "bildirilmemiş" : row.optString("anti"))
                + (installable ? "\nSürüm: " + row.getString("version") + " (" + row.getLong("code") + ")\nBoyut: " + (row.getLong("size") / 1024) + " KiB"
                    + "\nMinimum/hedef API: " + row.getInt("minSdk") + "/" + row.getInt("targetSdk")
                    + "\nABI: " + (row.optString("abis").isEmpty() ? "yerel kütüphane bildirilmemiş" : row.optString("abis"))
                    + "\nSHA-256: " + row.getString("hash") : "\nBu cihaz/sınırlar için uygun tek APK seçilemedi.")
                + "\nYüklü sürüm kodu: " + (installed < 0 ? "görünür değil / yüklü değil" : installed)
                + "\n\nKaynak: F-Droid. Play sürümleri farklı imzalanabilir; sistem imza uyuşmazlığını reddeder. İmza/hash, zararsızlık veya GMS uyumluluğu garantisi değildir. Sessiz kurulum yok.";
            AlertDialog.Builder dialog = new AlertDialog.Builder(this).setTitle(row.getString("name")).setMessage(description).setNegativeButton("Geri", null);
            if (installable && !busy && (installed < 0 || row.getLong("code") >= installed)) dialog.setPositiveButton("APK indir ve incele", (d, w) -> download(row));
            dialog.show();
        } catch (Exception error) { fail("Paket ayrıntısı okunamadı."); }
    }
    private void download(JSONObject app) {
        if (busy) return;
        new AlertDialog.Builder(this).setTitle("APK indirmesini onayla")
            .setMessage(app.optString("name") + "\n\nİmzalı katalogdaki dosya indirilecek; boyut/SHA-256/paket/sürüm denetiminden sonra ayrı APK incelemesi açılır. İndirme yükleme değildir; son karar sistem yükleyicisinde ve sendedir.")
            .setPositiveButton("APK indir", (d, w) -> {
                busy = true; refresh.setEnabled(false); status.setText("APK indiriliyor; henüz kurulmadı…");
                worker.execute(() -> {
                    try {
                        File file = FdroidRepository.downloadApk(this, app);
                        Intent review = new Intent(this, InstallReviewActivity.class).putExtra("privateApk", file.getAbsolutePath())
                            .putExtra("expectedHash", app.getString("hash")).putExtra("expectedPackage", app.getString("package")).putExtra("expectedVersion", app.getLong("code"));
                        runOnUiThread(() -> { if (!isDestroyed()) { busy = false; refresh.setEnabled(true); startActivity(review); scheduleSearch(); } });
                    } catch (Exception error) { runOnUiThread(() -> { if (!isDestroyed()) { busy = false; refresh.setEnabled(true); status.setText("APK indirmesi tamamlanamadı; yüklenmiş sayılmadı."); fail(error.getMessage()); } }); }
                });
            }).setNegativeButton("Vazgeç", null).show();
    }
    private void play() {
        Intent launch = getPackageManager().getLaunchIntentForPackage("com.android.vending");
        if (launch != null) { startActivity(launch); return; }
        new AlertDialog.Builder(this).setTitle("Google Play ayrı bir kaynak")
            .setMessage("Bu cihazda lisanslı Play uygulaması görünmüyor. OğuzDows GMS/Play dağıtmaz. Google API’leri, Play Integrity, bankacılık/DRM ve her uygulamanın çalışması garanti edilmez. GNOME Software eklemek bunları sağlamaz.")
            .setPositiveButton("Web kataloğunu aç", (d, w) -> {
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps"))); }
                catch (RuntimeException error) { fail("Web tarayıcısı bulunamadı."); }
            }).setNegativeButton("Geri", null).show();
    }
    private final class CatalogAdapter extends BaseAdapter {
        public int getCount() { return items.size(); }
        public Object getItem(int p) { return items.get(p); }
        public long getItemId(int p) { return p; }
        public View getView(int p, View recycled, ViewGroup parent) {
            JSONObject app = items.get(p); LinearLayout row = new LinearLayout(SourceStoreActivity.this); row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, ui.dp(8), 0, ui.dp(8));
            ImageView icon = new ImageView(SourceStoreActivity.this);
            try { icon.setImageDrawable(getPackageManager().getApplicationIcon(app.getString("package"))); }
            catch (Exception ignored) { icon.setImageResource(R.drawable.nazar); }
            row.addView(icon, new LinearLayout.LayoutParams(ui.dp(40), ui.dp(40)));
            long installed = app.optLong("installedCode", -1);
            String state = installed < 0 ? "" : !app.isNull("code") && app.optLong("code") > installed ? " · Güncelleme var" : " · Yüklü";
            TextView label = ui.text(app.optString("name") + state + "\n" + app.optString("summary")
                + "\n" + (app.isNull("version") ? "Uygun sürüm seçilemedi" : app.optString("version") + " · F-Droid"), 13, false);
            label.setPadding(ui.dp(12), 0, 0, 0); row.addView(label, new LinearLayout.LayoutParams(0, -2, 1)); return row;
        }
    }
    private void fail(String message) {
        runOnUiThread(() -> { if (!isDestroyed() && !isFinishing()) new AlertDialog.Builder(this).setTitle("Mağaza işlemi tamamlanamadı").setMessage(message == null ? "Ağ, depolama veya doğrulama hatası." : message).setPositiveButton("Tamam", null).show(); });
    }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); worker.shutdownNow(); super.onDestroy(); }
}
