package org.oguzdows.mobile;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Small platform-view palette; native screens share the rich shell's explicit theme preference. */
final class NativeUi {
    final Activity activity;
    final int ink, muted, paper, surface, brand;
    NativeUi(Activity activity) {
        this.activity = activity;
        boolean dark = dark(activity);
        ink = Color.parseColor(dark ? "#E2EEEB" : "#263C38");
        muted = Color.parseColor(dark ? "#A6BBB2" : "#52665D");
        paper = Color.parseColor(dark ? "#17262B" : "#F8F9F5");
        surface = Color.parseColor(dark ? "#294047" : "#E7EFE7");
        brand = ShellStyles.accent(new LauncherStore(activity).wallpaper(), dark);
    }
    static boolean dark(Context context) { return context.getSharedPreferences("native-ui", Context.MODE_PRIVATE).getBoolean("dark", false); }
    static void theme(Activity activity) { activity.setTheme(dark(activity) ? R.style.AppThemeDark : R.style.AppTheme); }
    int dp(int n) { return Math.round(n * activity.getResources().getDisplayMetrics().density); }
    LinearLayout column() {
        LinearLayout box = new LinearLayout(activity); box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(12), dp(20), dp(20)); box.setBackgroundColor(paper); return box;
    }
    TextView text(String value, int size, boolean bold) {
        TextView t = new TextView(activity); t.setText(value); t.setTextSize(size); t.setTextColor(ink);
        t.setPadding(0, dp(8), 0, dp(8)); if (bold) t.setTypeface(null, Typeface.BOLD); return t;
    }
    Button button(String label, Runnable action) {
        Button b = new Button(activity); b.setText(label); b.setTextColor(ink); b.setAllCaps(false); b.setMinHeight(dp(52));
        GradientDrawable shape = new GradientDrawable(); shape.setColor(surface); shape.setCornerRadius(dp(16));
        b.setBackground(new android.graphics.drawable.RippleDrawable(
            android.content.res.ColorStateList.valueOf(dark(activity) ? 0x30FFFFFF : 0x22256052), shape, null));
        b.setStateListAnimator(null); b.setClipToOutline(true);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2); lp.setMargins(0, dp(5), 0, dp(5)); b.setLayoutParams(lp);
        b.setOnClickListener(v -> action.run()); return b;
    }
    static void insets(android.view.View root) {
        int left = root.getPaddingLeft(), top = root.getPaddingTop(), right = root.getPaddingRight(), bottom = root.getPaddingBottom();
        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars() | androidx.core.view.WindowInsetsCompat.Type.displayCutout());
            androidx.core.graphics.Insets ime = insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.ime());
            root.setPadding(left + bars.left, top + bars.top, right + bars.right, bottom + Math.max(bars.bottom, ime.bottom)); return insets;
        });
        androidx.core.view.ViewCompat.requestApplyInsets(root);
    }
}
