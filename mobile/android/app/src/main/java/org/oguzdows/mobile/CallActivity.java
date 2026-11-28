package org.oguzdows.mobile;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.telecom.Call;
import android.view.Gravity;
import android.view.MotionEvent;
import android.widget.Button;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

/** In-package, lock-screen-capable native call UI, backed exclusively by Telecom callbacks. */
public final class CallActivity extends Activity {
    private final Runnable listener = this::render;
    private boolean keypad;
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setShowWhenLocked(true);
        setTurnScreenOn(true);
        render();
    }
    @Override protected void onStart() { super.onStart(); CallController.listen(listener); render(); }
    @Override protected void onStop() { CallController.unlisten(listener); CallController.stopTone(); super.onStop(); }
    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); render(); }

    private TextView text(String value, int size) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(size);
        view.setTextColor(Color.parseColor("#E2EEEB")); view.setGravity(Gravity.CENTER);
        view.setPadding(0, dp(12), 0, dp(12)); return view;
    }
    private Button button(String value, String color, Runnable action) {
        Button b = new Button(this); b.setText(value); b.setAllCaps(false); b.setTextSize(16);
        b.setTextColor(Color.WHITE); b.setMinHeight(dp(56));
        GradientDrawable shape = new GradientDrawable(); shape.setColor(Color.parseColor(color)); shape.setCornerRadius(dp(22));
        b.setBackground(shape);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2); lp.setMargins(0, dp(6), 0, dp(6)); b.setLayoutParams(lp);
        b.setOnClickListener(v -> action.run()); return b;
    }
    private void render() {
        if (isFinishing() || isDestroyed()) return;
        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        GradientDrawable background = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
            new int[]{Color.parseColor("#19383C"), Color.parseColor("#111E29")}); scroll.setBackground(background);
        LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setGravity(Gravity.CENTER);
        box.setPadding(dp(28), dp(40), dp(28), dp(28));
        scroll.addView(box); setContentView(scroll);
        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(scroll, (v, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(androidx.core.view.WindowInsetsCompat.Type.systemBars());
            box.setPadding(dp(28) + bars.left, dp(32) + bars.top, dp(28) + bars.right, dp(24) + bars.bottom); return insets;
        });
        box.addView(text("OĞUZDOWS · GÖRÜŞME", 13));
        android.widget.ImageView nazar = new android.widget.ImageView(this); nazar.setImageResource(R.drawable.nazar);
        box.addView(nazar, new LinearLayout.LayoutParams(dp(80), dp(80)));
        try {
            JSONObject call = CallController.snapshot();
            if (call == null) {
                TextView status = text("Etkin görüşme yok", 24); status.setContentDescription("call-state-none"); box.addView(status);
                box.addView(button("Telefona dön", "#2A645A", () -> { startActivity(new Intent(this, HomeActivity.class).putExtra("screen", "phone")); finish(); }));
                return;
            }
            TextView number = text(call.getString("number"), 28); number.setTypeface(null, Typeface.BOLD); box.addView(number);
            int state = call.getInt("state");
            TextView status = text(call.getString("label"), 19); status.setContentDescription("call-state-" + state); box.addView(status);
            if (call.optInt("count") > 1) box.addView(text(call.optInt("count") + " çağrı · öncelikli olan gösteriliyor", 13));
            if (state == Call.STATE_RINGING) {
                box.addView(button("Yanıtla", "#26755E", CallController::answer));
                box.addView(button("Reddet", "#A83E45", CallController::end));
            } else if (state == Call.STATE_DISCONNECTED) {
                box.addView(text("Telecom sonlandırma kodu: " + call.optInt("disconnectCode"), 13));
                box.addView(button("Kapat", "#2A645A", this::finish));
            } else {
                if (state == Call.STATE_SELECT_PHONE_ACCOUNT) {
                    org.json.JSONArray accounts = call.getJSONArray("accounts");
                    for (int i = 0; i < accounts.length(); i++) {
                        int position = i;
                        box.addView(button("Arama hesabı " + (i + 1), "#2A645A", () -> CallController.selectAccount(position)));
                    }
                    if (accounts.length() == 0) box.addView(text("Telecom hesap seçimini bekliyor. Sistem SIM ayarlarını kontrol et.", 14));
                }
                box.addView(button(call.optBoolean("muted") ? "Mikrofonu aç" : "Mikrofonu sustur", "#304A50", CallController::mute));
                Button speaker = button(call.optBoolean("speaker") ? "Ahizeye geç" : "Hoparlöre geç", "#304A50", CallController::speaker);
                speaker.setEnabled(call.optBoolean("speakerAvailable")); box.addView(speaker);
                if (call.optBoolean("canHold")) box.addView(button(state == Call.STATE_HOLDING ? "Görüşmeye dön" : "Beklet", "#304A50", CallController::hold));
                if (state == Call.STATE_ACTIVE) {
                    box.addView(button(keypad ? "Tuş takımını gizle" : "Tuş takımı · DTMF", "#304A50", () -> { keypad = !keypad; render(); }));
                    if (keypad) {
                        GridLayout pad = new GridLayout(this); pad.setColumnCount(3);
                        for (char digit : "123456789*0#".toCharArray()) {
                            Button key = new Button(this); key.setText(String.valueOf(digit)); key.setTextColor(Color.WHITE);
                            key.setContentDescription("Görüşme tuşu " + digit);
                            key.setOnTouchListener((view, event) -> {
                                if (event.getAction() == MotionEvent.ACTION_DOWN) CallController.tone(digit);
                                else if (event.getAction() == MotionEvent.ACTION_UP || event.getAction() == MotionEvent.ACTION_CANCEL) CallController.stopTone();
                                return false;
                            });
                            key.setOnClickListener(v -> { CallController.tone(digit); key.postDelayed(CallController::stopTone, 120); });
                            pad.addView(key, new android.view.ViewGroup.LayoutParams(dp(82), dp(56)));
                        }
                        box.addView(pad);
                    }
                }
                box.addView(button("Görüşmeyi bitir", "#A83E45", CallController::end));
                box.addView(button("Ana ekrana dön · görüşme sürer", "#304A50", () -> {
                    startActivity(new Intent(this, HomeActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
                }));
            }
            box.addView(text("Durum cihazın telefon servisinden gelir. Emülatör, gerçek SIM/operatör testi değildir.", 12));
        } catch (Exception error) {
            box.addView(text("Görüşme durumu okunamadı. Sistem telefon bildirimini kullan.", 16));
        }
    }
}
