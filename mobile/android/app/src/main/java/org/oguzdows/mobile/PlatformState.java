package org.oguzdows.mobile;

import android.Manifest;
import android.app.NotificationManager;
import android.app.role.RoleManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.os.BatteryManager;
import android.os.Build;
import android.telephony.SubscriptionManager;

import org.json.JSONObject;

/** Only platform-derived state. No synthetic connected/sent/installed values. */
public final class PlatformState {
    public static final String CHANGED = "org.oguzdows.mobile.STATE_CHANGED";
    private PlatformState() {}

    public static boolean granted(Context context, String permission) {
        return context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    public static boolean role(Context context, String role) {
        RoleManager roles = context.getSystemService(RoleManager.class);
        return roles != null && roles.isRoleAvailable(role) && roles.isRoleHeld(role);
    }

    public static void changed(Context context) {
        context.sendBroadcast(new Intent(CHANGED).setPackage(context.getPackageName()));
    }

    public static JSONObject snapshot(Context context) throws Exception {
        PackageManager pm = context.getPackageManager();
        RoleManager roles = context.getSystemService(RoleManager.class);
        JSONObject state = new JSONObject();
        state.put("platform", "android");
        state.put("version", "0.4.0-connected");
        state.put("sdk", Build.VERSION.SDK_INT);
        state.put("contactsPermission", granted(context, Manifest.permission.READ_CONTACTS));
        state.put("themeAccent", ShellStyles.webAccent(new LauncherStore(context).wallpaper()));
        state.put("themeColor", String.format(java.util.Locale.ROOT, "#%06X",
            ShellStyles.accent(new LauncherStore(context).wallpaper(), NativeUi.dark(context)) & 0x00FFFFFF));
        state.put("callingAvailable", pm.hasSystemFeature(PackageManager.FEATURE_TELEPHONY));
        state.put("smsAvailable", pm.hasSystemFeature(PackageManager.FEATURE_TELEPHONY));
        state.put("dialerRoleAvailable", roles != null && roles.isRoleAvailable(RoleManager.ROLE_DIALER));
        state.put("smsRoleAvailable", roles != null && roles.isRoleAvailable(RoleManager.ROLE_SMS));
        state.put("dialerRole", role(context, RoleManager.ROLE_DIALER));
        state.put("smsRole", role(context, RoleManager.ROLE_SMS));
        state.put("phonePermission", granted(context, Manifest.permission.CALL_PHONE));
        state.put("smsPermission", granted(context, Manifest.permission.SEND_SMS)
            && granted(context, Manifest.permission.RECEIVE_SMS) && granted(context, Manifest.permission.READ_SMS));
        state.put("notificationPermission", Build.VERSION.SDK_INT < 33 || granted(context, Manifest.permission.POST_NOTIFICATIONS));
        state.put("smsSubscription", SubscriptionManager.getDefaultSmsSubscriptionId());
        JSONObject call = CallController.snapshot();
        state.put("call", call == null ? JSONObject.NULL : call);
        state.put("mmsNotices", SmsJournal.get(context).mmsCount());
        Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int level = battery == null ? -1 : battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = battery == null ? -1 : battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        state.put("battery", level < 0 || scale < 1 ? JSONObject.NULL : level * 100 / scale);
        AudioManager audio = context.getSystemService(AudioManager.class);
        int max = audio == null ? 0 : audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        state.put("mediaVolume", max < 1 ? JSONObject.NULL : Math.round(100f * audio.getStreamVolume(AudioManager.STREAM_MUSIC) / max));
        state.put("modelConnected", false);
        state.put("mmsSupported", false);
        state.put("rcsSupported", false);
        state.put("gmsBundled", false);
        NotificationManager notifications = context.getSystemService(NotificationManager.class);
        state.put("notificationsEnabled", notifications != null && notifications.areNotificationsEnabled());
        return state;
    }
}
