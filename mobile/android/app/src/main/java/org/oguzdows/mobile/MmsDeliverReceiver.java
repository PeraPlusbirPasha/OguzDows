package org.oguzdows.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;

/** Retains bounded WAP notices, but does NOT claim MMS downloading/decoding support. */
public final class MmsDeliverReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.WAP_PUSH_DELIVER_ACTION.equals(intent.getAction())) return;
        byte[] data = intent.getByteArrayExtra("data");
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                if (data != null && data.length > 0 && data.length <= 65536) SmsJournal.get(context).retainMms(data);
                MessageNotifications.show(context, "MMS henüz desteklenmiyor", "MMS bildirimi alındı; içerik indirilmedi. Eksiksiz mesajlaşma için sistemde başka bir varsayılan SMS/MMS uygulaması seç.");
            } finally { PlatformState.changed(context); pending.finish(); }
        }, "mms-notice").start();
    }
}
