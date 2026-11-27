package org.oguzdows.mobile;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

/** A caller's quick response becomes a draft notification, never an unconfirmed paid SMS. */
public final class RespondViaMessageService extends Service {
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && Intent.ACTION_RESPOND_VIA_MESSAGE.equals(intent.getAction())) {
            String number = intent.getData() == null ? "" : PlatformRules.number(intent.getData().getSchemeSpecificPart());
            String body = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (!number.isEmpty() && PlatformRules.smsBody(body)) {
                getSharedPreferences("pending-reply", MODE_PRIVATE).edit().putString("number", number).putString("body", body).apply();
                MessageNotifications.show(this, "Hızlı yanıt · gönderilmedi", "Mesajlar ekranında taslağı gözden geçirip SMS gönderimini ayrıca onayla.");
            }
        }
        stopSelf(startId); return START_NOT_STICKY;
    }
}
