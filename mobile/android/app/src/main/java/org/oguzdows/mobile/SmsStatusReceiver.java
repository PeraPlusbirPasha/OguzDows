package org.oguzdows.mobile;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.SmsMessage;

/** Explicit, non-exported PendingIntent target. Only real radio receipts advance message state. */
public final class SmsStatusReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        String id = intent.getStringExtra("id");
        int part = intent.getIntExtra("part", -1);
        if (id == null || !id.matches("[a-f0-9-]{36}") || part < 0 || part >= 30) return;
        boolean delivery = intent.getBooleanExtra("delivery", false);
        int code = getResultCode();
        boolean success = code == Activity.RESULT_OK;
        if (delivery) {
            byte[] pdu = intent.getByteArrayExtra("pdu");
            if (pdu == null || pdu.length > 4096) return; // No report is not a delivery confirmation.
            SmsMessage message;
            try { message = SmsMessage.createFromPdu(pdu, intent.getStringExtra("format")); }
            catch (RuntimeException ignored) { return; }
            if (message == null) return;
            code = message.getStatus();
            if (code >= 32 && code < 64) return; // Network says still pending.
            success = code >= 0 && code < 32;
        }
        final int resultCode = code;
        final boolean accepted = success;
        PendingResult pending = goAsync();
        new Thread(() -> {
            try { SmsJournal.get(context).receipt(context, id, part, delivery, accepted, resultCode); }
            catch (RuntimeException ignored) { /* Provider role may have been revoked; never fabricate success. */ }
            finally { PlatformState.changed(context); pending.finish(); }
        }, "sms-receipt").start();
    }
}
