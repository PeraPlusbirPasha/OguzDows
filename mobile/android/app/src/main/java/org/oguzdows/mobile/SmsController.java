package org.oguzdows.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.app.role.RoleManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.Telephony;
import android.telephony.SmsManager;
import android.telephony.SubscriptionManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.UUID;

/** Plain SMS only. No RCS/MMS substitution, hidden retries or optimistic success states. */
public final class SmsController {
    public interface Result { void success(JSONObject result); void error(String message); }
    private static boolean confirmationOpen;
    private static long lastApproved;
    private SmsController() {}

    public static void confirmSend(Activity activity, String rawNumber, String body, Result result) {
        String number = PlatformRules.number(rawNumber);
        if (number.isEmpty() || !PlatformRules.smsBody(body)) { result.error("Geçerli alıcı ve 1–2000 karakterlik bir SMS yaz. Servis kodları kabul edilmez."); return; }
        if (!PlatformState.role(activity, RoleManager.ROLE_SMS)) { result.error("Önce varsayılan SMS uygulaması seçimini açıkça yapmalısın."); return; }
        if (!PlatformState.granted(activity, Manifest.permission.SEND_SMS)
            || !PlatformState.granted(activity, Manifest.permission.READ_SMS)) { result.error("SMS izinlerini önce ayrı düğmeden onayla; mesaj otomatik yeniden gönderilmez."); return; }
        int subscription = SubscriptionManager.getDefaultSmsSubscriptionId();
        if (!SubscriptionManager.isValidSubscriptionId(subscription)) { result.error("Varsayılan SMS SIM’i seçili değil. Sistem SIM ayarlarında bir SMS hattı seç; otomatik hat seçilmez."); return; }
        SmsManager manager = SmsManager.getSmsManagerForSubscriptionId(subscription);
        ArrayList<String> parts = manager.divideMessage(body);
        if (parts.isEmpty() || parts.size() > 30) { result.error("Bu mesaj 30 SMS parçası sınırını aşıyor."); return; }
        if (confirmationOpen || android.os.SystemClock.elapsedRealtime() - lastApproved < 5000) { result.error("Önceki gönderim/onay sürüyor. Birkaç saniye bekle; otomatik tekrar yok."); return; }
        confirmationOpen = true;
        AlertDialog dialog = new AlertDialog.Builder(activity).setTitle("SMS gönderimini onayla")
            .setMessage("Alıcı: " + number + "\nVarsayılan SMS hattı: abonelik " + subscription
                + "\nParça: " + parts.size() + " (her parça ücretlendirilebilir)\n\n" + body
                + "\n\nBu gerçek SMS isteğidir. Şebekeye verilmesi, karşıya teslim edildiği anlamına gelmez. MMS/RCS gönderilmez.")
            .setNegativeButton("Vazgeç", (d, w) -> result.error("Gönderim iptal edildi; SMS gönderilmedi."))
            .setPositiveButton("SMS gönder", (d, w) -> {
                lastApproved = android.os.SystemClock.elapsedRealtime();
                try {
                    // Consent is not a permission: re-check role and grants after the dialog.
                    if (!PlatformState.role(activity, RoleManager.ROLE_SMS) || !PlatformState.granted(activity, Manifest.permission.SEND_SMS))
                        throw new IllegalStateException("SMS rolü veya izni değişti; gönderim durduruldu.");
                    ContentValues values = new ContentValues();
                    values.put(Telephony.Sms.ADDRESS, number); values.put(Telephony.Sms.BODY, body);
                    values.put(Telephony.Sms.DATE, System.currentTimeMillis()); values.put(Telephony.Sms.READ, 1);
                    values.put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_OUTBOX);
                    values.put(Telephony.Sms.STATUS, Telephony.Sms.STATUS_PENDING);
                    values.put(Telephony.Sms.SUBSCRIPTION_ID, subscription);
                    Uri uri = activity.getContentResolver().insert(Telephony.Sms.CONTENT_URI, values);
                    if (uri == null) throw new IllegalStateException("Giden SMS kaydı oluşturulamadı; gönderim başlatılmadı.");
                    String id = UUID.randomUUID().toString();
                    SmsJournal.get(activity).add(id, uri, parts.size());
                    ArrayList<PendingIntent> sent = new ArrayList<>(), delivered = new ArrayList<>();
                    for (int i = 0; i < parts.size(); i++) {
                        sent.add(receipt(activity, id, i, false)); delivered.add(receipt(activity, id, i, true));
                    }
                    try { manager.sendMultipartTextMessage(number, null, parts, sent, delivered); }
                    catch (RuntimeException error) {
                        SmsJournal.get(activity).receipt(activity, id, 0, false, false, -1000);
                        throw error;
                    }
                    result.success(new JSONObject().put("id", id).put("state", "queued").put("parts", parts.size())
                        .put("message", "SMS şebekeye gönderim için sıraya alındı; henüz gönderildi veya teslim edildi sonucu yok."));
                    PlatformState.changed(activity);
                } catch (Exception error) { result.error(error instanceof IllegalStateException ? error.getMessage() : "SMS isteği başarısız. İzin/SIM/radyo durumunu kontrol et. Otomatik yeniden gönderilmedi."); }
            }).create();
        dialog.setOnCancelListener(d -> result.error("Gönderim iptal edildi; SMS gönderilmedi."));
        dialog.setOnDismissListener(d -> confirmationOpen = false);
        dialog.show();
    }
    private static PendingIntent receipt(Context context, String id, int part, boolean delivered) {
        Intent intent = new Intent(context, SmsStatusReceiver.class)
            .setAction(delivered ? "org.oguzdows.mobile.SMS_DELIVERED" : "org.oguzdows.mobile.SMS_SENT")
            .setData(Uri.parse("oguz-receipt://" + id + "/" + part + "/" + (delivered ? "delivered" : "sent")))
            .putExtra("id", id).putExtra("part", part).putExtra("delivery", delivered);
        return PendingIntent.getBroadcast(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | (delivered ? PendingIntent.FLAG_MUTABLE : PendingIntent.FLAG_IMMUTABLE));
    }
    public static JSONArray messages(Context context) throws Exception {
        if (!PlatformState.role(context, RoleManager.ROLE_SMS) || !PlatformState.granted(context, Manifest.permission.READ_SMS))
            throw new SecurityException("SMS listesi için varsayılan SMS rolü ve okuma izni gerekiyor.");
        JSONArray list = new JSONArray();
        String[] columns = {Telephony.Sms._ID, Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE,
            Telephony.Sms.TYPE, Telephony.Sms.STATUS, Telephony.Sms.ERROR_CODE, Telephony.Sms.READ};
        try (Cursor c = context.getContentResolver().query(Telephony.Sms.CONTENT_URI, columns, null, null, Telephony.Sms.DATE + " DESC")) {
            while (c != null && c.moveToNext() && list.length() < 50) {
                String body = c.getString(2);
                list.put(new JSONObject().put("id", c.getLong(0)).put("number", c.getString(1))
                    .put("body", body == null ? "" : body.substring(0, Math.min(20000, body.length())))
                    .put("date", c.getLong(3)).put("type", c.getInt(4)).put("status", c.getInt(5))
                    .put("errorCode", c.getInt(6)).put("read", c.getInt(7) != 0));
            }
        }
        return list;
    }
}
