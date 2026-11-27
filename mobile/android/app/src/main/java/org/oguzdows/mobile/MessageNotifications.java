package org.oguzdows.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;

final class MessageNotifications {
    private MessageNotifications() {}
    static void show(Context context, String title, String text) {
        NotificationManager nm = context.getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("messages", "Mesajlar", NotificationManager.IMPORTANCE_DEFAULT));
        PendingIntent open = PendingIntent.getActivity(context, 720,
            new Intent(context, HomeActivity.class).putExtra("screen", "messages")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        try {
            nm.notify(720, new Notification.Builder(context, "messages").setSmallIcon(R.drawable.nazar)
                .setContentTitle(title).setContentText(text).setContentIntent(open).setAutoCancel(true)
                .setCategory(Notification.CATEGORY_MESSAGE).setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(context, "messages").setSmallIcon(R.drawable.nazar)
                    .setContentTitle("OğuzDows · yeni mesaj").build()).build());
        } catch (SecurityException ignored) { /* The message remains stored if notifications were denied. */ }
    }
}
