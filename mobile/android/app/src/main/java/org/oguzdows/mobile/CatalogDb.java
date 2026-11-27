package org.oguzdows.mobile;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.os.Build;
import android.util.JsonReader;
import android.util.JsonToken;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Offline searchable catalog. A failed/untrusted refresh atomically preserves the previous catalog. */
public final class CatalogDb extends SQLiteOpenHelper {
    private static CatalogDb instance;
    public static synchronized CatalogDb get(Context context) {
        if (instance == null) instance = new CatalogDb(context.getApplicationContext()); return instance;
    }
    private CatalogDb(Context context) { this(context, "fdroid-catalog.db"); }
    CatalogDb(Context context, String databaseName) { super(context, databaseName, null, 1); }
    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE apps (package TEXT PRIMARY KEY, name TEXT NOT NULL, summary TEXT NOT NULL, license TEXT NOT NULL, anti TEXT NOT NULL)");
        db.execSQL("CREATE TABLE versions (package TEXT PRIMARY KEY, version TEXT NOT NULL, code INTEGER NOT NULL, apk TEXT NOT NULL, hash TEXT NOT NULL, size INTEGER NOT NULL, min_sdk INTEGER NOT NULL, target_sdk INTEGER NOT NULL, abis TEXT NOT NULL)");
        db.execSQL("CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), timestamp INTEGER NOT NULL, synced INTEGER NOT NULL, source TEXT NOT NULL)");
    }
    @Override public void onUpgrade(SQLiteDatabase db, int old, int current) { throw new IllegalStateException("Unsupported catalog upgrade"); }
    public synchronized long timestamp() {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT timestamp FROM meta WHERE id=1", null)) { return c.moveToFirst() ? c.getLong(0) : 0; }
    }
    public synchronized JSONObject info() throws Exception {
        JSONObject info = new JSONObject().put("apps", android.database.DatabaseUtils.queryNumEntries(getReadableDatabase(), "apps"))
            .put("compatible", android.database.DatabaseUtils.queryNumEntries(getReadableDatabase(), "versions"));
        try (Cursor c = getReadableDatabase().rawQuery("SELECT timestamp,synced,source FROM meta WHERE id=1", null)) {
            if (c.moveToFirst()) info.put("timestamp", c.getLong(0)).put("synced", c.getLong(1)).put("source", c.getString(2));
        }
        return info;
    }
    public synchronized void replaceVerified(File json, String source) throws Exception {
        SQLiteDatabase db = getWritableDatabase(); long previous = timestamp();
        db.beginTransaction();
        try (JsonReader reader = new JsonReader(new InputStreamReader(new FileInputStream(json), StandardCharsets.UTF_8))) {
            db.delete("apps", null, null); db.delete("versions", null, null);
            long timestamp = 0; int apps = 0, packages = 0;
            reader.beginObject();
            while (reader.hasNext()) {
                if (Thread.currentThread().isInterrupted()) throw new Exception("Katalog eşitlemesi durduruldu.");
                switch (reader.nextName()) {
                    case "repo":
                        reader.beginObject(); while (reader.hasNext()) {
                            if ("timestamp".equals(reader.nextName())) timestamp = integer(reader, 0); else reader.skipValue();
                        } reader.endObject(); break;
                    case "apps":
                        reader.beginArray(); while (reader.hasNext()) {
                            if (++apps > 20000) throw new Exception("Katalog uygulama sınırı aşıldı."); parseApp(reader, db);
                        } reader.endArray(); break;
                    case "packages":
                        reader.beginObject(); while (reader.hasNext()) {
                            if (++packages > 20000) throw new Exception("Katalog paket sınırı aşıldı.");
                            String name = reader.nextName(); parseVersions(reader, db, name);
                        } reader.endObject(); break;
                    default: reader.skipValue();
                }
            }
            reader.endObject();
            long now = System.currentTimeMillis();
            if (timestamp <= 0 || timestamp < previous || timestamp > now + 2L * 86400000 || timestamp < now - 60L * 86400000)
                throw new Exception("İmzalı katalog zaman damgası eski, gelecekte veya önceki sürümden geri. Önceki katalog korundu.");
            if (apps < 1 || packages < 1 || android.database.DatabaseUtils.queryNumEntries(db, "versions") < 1)
                throw new Exception("Katalogda bu cihaz için doğrulanabilir APK sürümü yok; önceki katalog korundu.");
            ContentValues values = new ContentValues(); values.put("id", 1); values.put("timestamp", timestamp);
            values.put("synced", now); values.put("source", source);
            db.insertWithOnConflict("meta", null, values, SQLiteDatabase.CONFLICT_REPLACE);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    private static String string(JsonReader reader, int max) throws Exception {
        if (reader.peek() != JsonToken.STRING && reader.peek() != JsonToken.NUMBER) { reader.skipValue(); return ""; }
        String value = reader.nextString(); if (value.length() > 1000000) throw new Exception("Katalog metin sınırı aşıldı.");
        return value.substring(0, Math.min(max, value.length()));
    }
    private static long integer(JsonReader reader, long fallback) throws Exception {
        try { return Long.parseLong(string(reader, 30)); } catch (NumberFormatException error) { return fallback; }
    }
    private static String strings(JsonReader reader) throws Exception {
        if (reader.peek() != JsonToken.BEGIN_ARRAY) return string(reader, 1000);
        List<String> list = new ArrayList<>(); reader.beginArray(); int count = 0;
        while (reader.hasNext()) { if (++count > 256) throw new Exception("Katalog dizi sınırı aşıldı."); list.add(string(reader, 200)); }
        reader.endArray(); return String.join(", ", list);
    }
    private static void parseApp(JsonReader reader, SQLiteDatabase db) throws Exception {
        String pkg = "", name = "", summary = "", license = "", anti = "", localizedName = "", localizedSummary = "";
        int localeRank = 0;
        reader.beginObject(); while (reader.hasNext()) {
            switch (reader.nextName()) {
                case "packageName": pkg = string(reader, 200); break;
                case "name": name = string(reader, 160); break;
                case "summary": summary = string(reader, 400); break;
                case "license": license = string(reader, 200); break;
                case "antiFeatures": anti = strings(reader); break;
                case "localized":
                    reader.beginObject(); while (reader.hasNext()) {
                        String locale = reader.nextName(); int rank = locale.equals("tr-TR") ? 4 : locale.equals("tr") ? 3 : locale.equals("en-US") ? 2 : locale.equals("en") ? 1 : 0;
                        if (rank <= localeRank) { reader.skipValue(); continue; }
                        String n = "", s = ""; reader.beginObject(); while (reader.hasNext()) {
                            String key = reader.nextName(); if (key.equals("name")) n = string(reader, 160); else if (key.equals("summary")) s = string(reader, 400); else reader.skipValue();
                        } reader.endObject();
                        if (!n.isEmpty() || !s.isEmpty()) { localizedName = n; localizedSummary = s; localeRank = rank; }
                    } reader.endObject(); break;
                default: reader.skipValue();
            }
        } reader.endObject();
        if (!PlatformRules.packageName(pkg)) return;
        ContentValues values = new ContentValues(); values.put("package", pkg);
        values.put("name", !localizedName.isEmpty() ? localizedName : name.isEmpty() ? pkg : name);
        values.put("summary", localizedSummary.isEmpty() ? summary : localizedSummary); values.put("license", license); values.put("anti", anti);
        db.insertWithOnConflict("apps", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    }
    private static void parseVersions(JsonReader reader, SQLiteDatabase db, String pkg) throws Exception {
        ContentValues best = null; long bestCode = -1; int versions = 0;
        reader.beginArray(); while (reader.hasNext()) {
            if (++versions > 2000) throw new Exception("Paket sürüm sınırı aşıldı.");
            String name = "", apk = "", hash = "", hashType = "", abis = "", anti = "";
            long code = -1, size = 0, minSdk = 1, targetSdk = 0, maxSdk = 0;
            reader.beginObject(); while (reader.hasNext()) {
                switch (reader.nextName()) {
                    case "versionName": name = string(reader, 100); break;
                    case "versionCode": code = integer(reader, -1); break;
                    case "apkName": apk = string(reader, 240); break;
                    case "hash": hash = string(reader, 100); break;
                    case "hashType": hashType = string(reader, 30); break;
                    case "size": size = integer(reader, 0); break;
                    case "minSdkVersion": minSdk = integer(reader, 1); break;
                    case "targetSdkVersion": targetSdk = integer(reader, 0); break;
                    case "maxSdkVersion": maxSdk = integer(reader, 0); break;
                    case "nativecode": abis = strings(reader); break;
                    case "antiFeatures": anti = strings(reader); break;
                    default: reader.skipValue();
                }
            } reader.endObject();
            boolean nativeOk = abis.isEmpty();
            List<String> supported = Arrays.asList(abis.split(", "));
            for (String abi : Build.SUPPORTED_ABIS) if (supported.contains(abi)) nativeOk = true;
            if (!PlatformRules.packageName(pkg) || code <= bestCode || !PlatformRules.apkName(apk)
                || !hash.matches("[a-fA-F0-9]{64}") || !"sha256".equals(hashType) || size < 1 || size > InstallReviewActivity.MAX_APK
                || minSdk > Build.VERSION.SDK_INT || (maxSdk > 0 && maxSdk < Build.VERSION.SDK_INT)
                || (Build.VERSION.SDK_INT >= 35 && targetSdk < 24) || !nativeOk || anti.contains("KnownVuln")) continue;
            bestCode = code; best = new ContentValues(); best.put("package", pkg); best.put("version", name); best.put("code", code);
            best.put("apk", apk); best.put("hash", hash.toLowerCase(java.util.Locale.ROOT)); best.put("size", size);
            best.put("min_sdk", minSdk); best.put("target_sdk", targetSdk); best.put("abis", abis);
        } reader.endArray();
        if (best != null) db.insertWithOnConflict("versions", null, best, SQLiteDatabase.CONFLICT_REPLACE);
    }
    public synchronized JSONArray search(String query, boolean compatibleOnly) throws Exception {
        String escaped = query.substring(0, Math.min(80, query.length())).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
        String like = "%" + escaped + "%";
        String sql = "SELECT a.package,a.name,a.summary,a.license,a.anti,v.version,v.code,v.apk,v.hash,v.size,v.min_sdk,v.target_sdk,v.abis FROM apps a LEFT JOIN versions v ON a.package=v.package WHERE (a.name LIKE ? ESCAPE '\\' OR a.package LIKE ? ESCAPE '\\' OR a.summary LIKE ? ESCAPE '\\')"
            + (compatibleOnly ? " AND v.code IS NOT NULL" : "") + " ORDER BY a.name COLLATE NOCASE LIMIT 80";
        JSONArray result = new JSONArray();
        try (Cursor c = getReadableDatabase().rawQuery(sql, new String[]{like, like, like})) {
            while (c.moveToNext()) {
                JSONObject row = new JSONObject();
                String[] fields = {"package", "name", "summary", "license", "anti", "version", "code", "apk", "hash", "size", "minSdk", "targetSdk", "abis"};
                for (int i = 0; i < fields.length; i++) row.put(fields[i], c.isNull(i) ? JSONObject.NULL : c.getType(i) == Cursor.FIELD_TYPE_INTEGER ? c.getLong(i) : c.getString(i));
                result.put(row);
            }
        } return result;
    }
}
