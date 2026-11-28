package org.oguzdows.mobile;

import android.app.role.RoleManager;
import android.content.BroadcastReceiver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

/** SMS_DELIVER is sent only to the chosen SMS app and protected by BROADCAST_SMS. */
public final class SmsDeliverReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_DELIVER_ACTION.equals(intent.getAction())
            || !PlatformState.role(context, RoleManager.ROLE_SMS)) return;
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                SmsMessage[] parts = Telephony.Sms.Intents.getMessagesFromIntent(intent);
                if (parts == null || parts.length == 0 || parts.length > 255) return;
                StringBuilder body = new StringBuilder();
                for (SmsMessage part : parts) {
                    if (part == null) return;
                    if (part.getMessageBody() != null) body.append(part.getMessageBody());
                    if (body.length() > 50000) throw new IllegalStateException("SMS too large");
                }
                ContentValues values = new ContentValues();
                values.put(Telephony.Sms.ADDRESS, parts[0].getOriginatingAddress()); values.put(Telephony.Sms.BODY, body.toString());
                values.put(Telephony.Sms.DATE, System.currentTimeMillis()); values.put(Telephony.Sms.DATE_SENT, parts[0].getTimestampMillis());
                values.put(Telephony.Sms.READ, 0); values.put(Telephony.Sms.SEEN, 0);
                values.put(Telephony.Sms.SUBSCRIPTION_ID, intent.getIntExtra("subscription", -1));
                values.put(Telephony.Sms.PROTOCOL, parts[0].getProtocolIdentifier());
                values.put(Telephony.Sms.SERVICE_CENTER, parts[0].getServiceCenterAddress());
                if (context.getContentResolver().insert(Telephony.Sms.Inbox.CONTENT_URI, values) == null)
                    throw new IllegalStateException("SMS insert failed");
                MessageNotifications.show(context, "OğuzDows · yeni SMS", "Mesajlar uygulamasında oku.");
            } catch (Exception ignored) {
                MessageNotifications.show(context, "SMS kayıt sorunu", "SMS bildirimi alındı fakat sisteme kaydedilemedi. SMS rolünü ve depolamayı kontrol et.");
            } finally { PlatformState.changed(context); pending.finish(); }
        }, "sms-deliver").start();
    }
}
