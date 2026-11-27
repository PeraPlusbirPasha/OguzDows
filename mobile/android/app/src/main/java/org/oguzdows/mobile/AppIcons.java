package org.oguzdows.mobile;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;

/** Installed package icon -> licensed local brand vector -> honest monogram, never a broken image. */
final class AppIcons {
    private static final int[] COLORS = {0xFF326B60, 0xFF445CAE, 0xFF86583F, 0xFF775484, 0xFF426B88, 0xFF84622F};
    // Bounded to 1.5 MiB. Installing an app always takes precedence over an old generated placeholder.
    private static final android.util.LruCache<String, Bitmap> MONOGRAMS = new android.util.LruCache<String, Bitmap>(1536 * 1024) {
        @Override protected int sizeOf(String key, Bitmap bitmap) { return bitmap.getAllocationByteCount(); }
    };
    private AppIcons() {}
    static Drawable get(Context context, String pkg, String label) {
        try { return context.getPackageManager().getApplicationIcon(pkg); }
        catch (android.content.pm.PackageManager.NameNotFoundException ignored) { }
        int known = CuratedIcons.resource(pkg);
        if (known != 0) return context.getDrawable(known);
        int size = Math.max(48, Math.round(44 * context.getResources().getDisplayMetrics().density));
        String key = pkg + ":" + size + ":" + (label == null || label.isEmpty() ? "?" : label.codePointAt(0));
        Bitmap cached = MONOGRAMS.get(key);
        if (cached != null) return new BitmapDrawable(context.getResources(), cached);
        Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888); Canvas canvas = new Canvas(bitmap);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG); paint.setColor(COLORS[Math.floorMod(pkg.hashCode(), COLORS.length)]);
        canvas.drawRoundRect(0, 0, size, size, size * .29f, size * .29f, paint);
        paint.setColor(Color.WHITE); paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(size * .43f); paint.setTextAlign(Paint.Align.CENTER);
        String initial = label == null || label.isEmpty() ? "?" : new String(Character.toChars(label.codePointAt(0))).toUpperCase(java.util.Locale.forLanguageTag("tr-TR"));
        canvas.drawText(initial, size / 2f, size / 2f - (paint.ascent() + paint.descent()) / 2f, paint);
        MONOGRAMS.put(key, bitmap);
        return new BitmapDrawable(context.getResources(), bitmap);
    }
}
