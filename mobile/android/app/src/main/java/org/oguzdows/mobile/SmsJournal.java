package org.oguzdows.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.net.Uri;
import android.provider.Telephony;

/** Durable multipart receipts survive process death. Message bodies stay in the system SMS provider. */
public final class SmsJournal extends SQLiteOpenHelper {
    private static SmsJournal instance;
    public static synchronized SmsJournal get(Context context) {
        if (instance == null) instance = new SmsJournal(context.getApplicationContext());
        return instance;
    }
    private SmsJournal(Context context) { super(context, "sms-receipts.db", null, 1); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE receipts (id TEXT PRIMARY KEY, uri TEXT NOT NULL, parts INTEGER NOT NULL, sent INTEGER NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0, delivery_failed INTEGER NOT NULL DEFAULT 0, error INTEGER, created INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE mms_notices (_id INTEGER PRIMARY KEY, received INTEGER NOT NULL, pdu BLOB NOT NULL)");
    }
    @Override public void onUpgrade(SQLiteDatabase db, int old, int current) { throw new IllegalStateException("Unsupported database upgrade"); }

    public synchronized void add(String id, Uri uri, int parts) {
        ContentValues values = new ContentValues(); values.put("id", id); values.put("uri", uri.toString());
        values.put("parts", parts); values.put("created", System.currentTimeMillis());
        SQLiteDatabase db = getWritableDatabase();
        db.delete("receipts", "created < ?", new String[]{String.valueOf(System.currentTimeMillis() - 30L * 86400000)});
        db.insertOrThrow("receipts", null, values);
    }
    public synchronized void receipt(Context context, String id, int part, boolean delivery, boolean success, int code) {
        SQLiteDatabase db = getWritableDatabase();
        try (Cursor c = db.query("receipts", null, "id = ?", new String[]{id}, null, null, null)) {
            if (!c.moveToFirst()) return;
            int parts = c.getInt(c.getColumnIndexOrThrow("parts"));
            if (part < 0 || part >= parts || parts > 30) return;
            long bit = 1L << part;
            long sent = c.getLong(c.getColumnIndexOrThrow("sent"));
            long delivered = c.getLong(c.getColumnIndexOrThrow("delivered"));
            boolean failed = c.getInt(c.getColumnIndexOrThrow("failed")) != 0;
            boolean deliveryFailed = c.getInt(c.getColumnIndexOrThrow("delivery_failed")) != 0;
            ContentValues row = new ContentValues();
            if (delivery) {
                if (success) delivered |= bit; else deliveryFailed = true;
                row.put("delivered", delivered); row.put("delivery_failed", deliveryFailed ? 1 : 0);
            } else {
                if (success) sent |= bit; else failed = true;
                row.put("sent", sent); row.put("failed", failed ? 1 : 0);
            }
            if (!success) row.put("error", code);
            db.update("receipts", row, "id = ?", new String[]{id});
            ContentValues sms = new ContentValues();
            long full = (1L << parts) - 1;
            if (failed) { sms.put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_FAILED); sms.put(Telephony.Sms.ERROR_CODE, code); }
            else if (sent == full) sms.put(Telephony.Sms.TYPE, Telephony.Sms.MESSAGE_TYPE_SENT);
            if (deliveryFailed) sms.put(Telephony.Sms.STATUS, Telephony.Sms.STATUS_FAILED);
            else if (delivered == full) sms.put(Telephony.Sms.STATUS, Telephony.Sms.STATUS_COMPLETE);
            // Role may have been revoked while the radio was working. Never reclaim it silently.
            if (sms.size() > 0 && PlatformState.role(context, android.app.role.RoleManager.ROLE_SMS))
                context.getContentResolver().update(Uri.parse(c.getString(c.getColumnIndexOrThrow("uri"))), sms, null, null);
        }
    }
    public synchronized void retainMms(byte[] pdu) {
        SQLiteDatabase db = getWritableDatabase();
        ContentValues values = new ContentValues(); values.put("received", System.currentTimeMillis()); values.put("pdu", pdu);
        db.insertOrThrow("mms_notices", null, values);
        db.execSQL("DELETE FROM mms_notices WHERE _id NOT IN (SELECT _id FROM mms_notices ORDER BY _id DESC LIMIT 20)");
    }
    public synchronized int mmsCount() {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM mms_notices", null)) { return c.moveToFirst() ? c.getInt(0) : 0; }
    }
}
