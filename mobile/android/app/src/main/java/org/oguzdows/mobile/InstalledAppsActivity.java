package org.oguzdows.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import java.text.Collator;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Real launchable applications, real package icons, no QUERY_ALL_PACKAGES inventory upload. */
public final class InstalledAppsActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final List<ResolveInfo> all = new ArrayList<>(), visible = new ArrayList<>();
    private NativeUi ui;
    private AppsAdapter adapter;
    @Override public void onCreate(Bundle state) {
        NativeUi.theme(this); super.onCreate(state); ui = new NativeUi(this);
        LinearLayout root = ui.column(); setContentView(root); NativeUi.insets(root);
        root.addView(ui.text("Uygulamaların", 27, true));
        root.addView(ui.text("Bu cihazda gerçekten yüklü ve başlatılabilir olanlar. En çok 250; başka uygulamaların özel verileri okunmaz.", 13, false));
        EditText search = new EditText(this); search.setHint("İsim veya paket ara…"); search.setTextColor(ui.ink);
        search.setSingleLine(true); search.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(80)});
        root.addView(search);
        ListView list = new ListView(this); adapter = new AppsAdapter(); list.setAdapter(adapter);
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        root.addView(ui.button("OğuzDows’a dön", this::finish));
        list.setOnItemClickListener((parent, view, position, id) -> {
            ResolveInfo item = visible.get(position);
            try {
                startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                    .setComponent(new ComponentName(item.activityInfo.packageName, item.activityInfo.name))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED));
            } catch (RuntimeException error) { new AlertDialog.Builder(this).setMessage("Uygulama açılamadı; devre dışı veya artık yüklü olmayabilir.").setPositiveButton("Tamam", null).show(); }
        });
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { filter(s.toString()); }
            public void afterTextChanged(Editable value) {}
        });
        worker.execute(() -> {
            List<ResolveInfo> results = getPackageManager().queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0);
            Collator sorter = Collator.getInstance(Locale.forLanguageTag("tr-TR"));
            results.sort((a, b) -> sorter.compare(a.loadLabel(getPackageManager()).toString(), b.loadLabel(getPackageManager()).toString()));
            runOnUiThread(() -> { if (!isDestroyed()) { all.addAll(results.subList(0, Math.min(250, results.size()))); filter(search.getText().toString()); } });
        });
    }
    private void filter(String value) {
        String query = value.toLowerCase(Locale.forLanguageTag("tr-TR")); visible.clear();
        for (ResolveInfo item : all) if ((item.loadLabel(getPackageManager()) + " " + item.activityInfo.packageName).toLowerCase(Locale.forLanguageTag("tr-TR")).contains(query)) visible.add(item);
        adapter.notifyDataSetChanged();
    }
    private final class AppsAdapter extends BaseAdapter {
        public int getCount() { return visible.size(); }
        public Object getItem(int p) { return visible.get(p); }
        public long getItemId(int p) { return p; }
        public View getView(int p, View recycled, ViewGroup parent) {
            ResolveInfo item = visible.get(p);
            LinearLayout row = new LinearLayout(InstalledAppsActivity.this); row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.setPadding(0, ui.dp(9), 0, ui.dp(9));
            ImageView icon = new ImageView(InstalledAppsActivity.this); icon.setImageDrawable(item.loadIcon(getPackageManager()));
            row.addView(icon, new LinearLayout.LayoutParams(ui.dp(44), ui.dp(44)));
            TextView label = ui.text(item.loadLabel(getPackageManager()) + "\n" + item.activityInfo.packageName, 14, false);
            label.setPadding(ui.dp(14), 0, 0, 0); row.addView(label, new LinearLayout.LayoutParams(0, -2, 1)); return row;
        }
    }
    @Override protected void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
