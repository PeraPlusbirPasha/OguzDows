package org.oguzdows.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;
import android.telecom.Call;
import android.telecom.CallAudioState;
import android.telecom.InCallService;

import java.util.HashMap;
import java.util.Map;

/** Bound only by Telecom. No fake ConnectionService, simulated call or microphone recorder. */
public final class OguzInCallService extends InCallService {
    private static final int NOTIFICATION = 710;
    private final Map<Call, Call.Callback> callbacks = new HashMap<>();

    @Override public void onCreate() {
        super.onCreate();
        CallController.attach(this);
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("calls", "Görüşmeler", NotificationManager.IMPORTANCE_HIGH));
    }
    @Override public void onCallAdded(Call call) {
        super.onCallAdded(call);
        Call.Callback callback = new Call.Callback() {
            @Override public void onStateChanged(Call c, int state) { update(); }
            @Override public void onDetailsChanged(Call c, Call.Details details) { update(); }
        };
        callbacks.put(call, callback);
        call.registerCallback(callback);
        CallController.add(this, call);
        update();
        // The selected phone app owns this UI. Notification is the fallback if OS blocks a background launch.
        try { startActivity(new Intent(this, CallActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP)); }
        catch (RuntimeException ignored) { /* The call notification remains actionable. */ }
    }
    @Override public void onCallRemoved(Call call) {
        Call.Callback callback = callbacks.remove(call);
        if (callback != null) call.unregisterCallback(callback);
        CallController.remove(this, call);
        update();
        super.onCallRemoved(call);
    }
    @Override public void onCallAudioStateChanged(CallAudioState state) {
        super.onCallAudioStateChanged(state);
        CallController.audio(this, state);
    }
    private void update() {
        CallController.changed(this);
        NotificationManager nm = getSystemService(NotificationManager.class);
        try {
            org.json.JSONObject state = CallController.snapshot();
            if (state == null) { nm.cancel(NOTIFICATION); return; }
            PendingIntent open = PendingIntent.getActivity(this, 710,
                new Intent(this, CallActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            Notification.Builder notification = new Notification.Builder(this, "calls")
                .setSmallIcon(R.drawable.nazar).setContentTitle("OğuzDows · " + state.getString("label"))
                .setContentText(state.getString("number")).setContentIntent(open).setOngoing(true)
                .setCategory(Notification.CATEGORY_CALL).setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(this, "calls").setSmallIcon(R.drawable.nazar)
                    .setContentTitle("OğuzDows görüşmesi").setContentText("Görüşme ekranını aç").build());
            if (state.getInt("state") == Call.STATE_RINGING
                && (Build.VERSION.SDK_INT < 34 || nm.canUseFullScreenIntent())) notification.setFullScreenIntent(open, true);
            nm.notify(NOTIFICATION, notification.build());
        } catch (Exception ignored) { /* Permission/notification failure never invents a call state. */ }
    }
    @Override public void onDestroy() {
        for (Map.Entry<Call, Call.Callback> item : callbacks.entrySet()) item.getKey().unregisterCallback(item.getValue());
        callbacks.clear();
        getSystemService(NotificationManager.class).cancel(NOTIFICATION);
        CallController.detach(this);
        super.onDestroy();
    }
}
