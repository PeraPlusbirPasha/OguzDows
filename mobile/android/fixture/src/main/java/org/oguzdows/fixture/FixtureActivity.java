package org.oguzdows.fixture;

/** Inert, no-permission fixture for genuine system-installer consent tests. */
public final class FixtureActivity extends android.app.Activity {
    @Override public void onCreate(android.os.Bundle state) {
        super.onCreate(state);
        android.widget.TextView text = new android.widget.TextView(this);
        text.setText("OğuzDows kurulum testi\nBu küçük paket yalnız yükleyici testi içindir.");
        text.setTextSize(24); text.setPadding(32, 64, 32, 32); setContentView(text);
    }
}
