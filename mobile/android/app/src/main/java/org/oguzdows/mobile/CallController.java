package org.oguzdows.mobile;

import android.content.Context;
import android.net.Uri;
import android.telecom.Call;
import android.telecom.CallAudioState;
import android.telecom.VideoProfile;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArraySet;

/** Main-thread InCallService model. The modem/Telecom, never a UI timer, owns call state. */
public final class CallController {
    private static final Map<Call, String> CALLS = new LinkedHashMap<>();
    private static final CopyOnWriteArraySet<Runnable> LISTENERS = new CopyOnWriteArraySet<>();
    private static OguzInCallService service;
    private static CallAudioState audio;
    private static long sequence;
    private CallController() {}

    static void attach(OguzInCallService value) { service = value; }
    static void detach(OguzInCallService value) {
        if (service == value) { service = null; audio = null; }
    }
    static void add(Context context, Call call) {
        CALLS.put(call, "call-" + (++sequence));
        changed(context);
    }
    static void remove(Context context, Call call) {
        CALLS.remove(call);
        changed(context);
    }
    static void audio(Context context, CallAudioState value) { audio = value; changed(context); }
    static void changed(Context context) {
        PlatformState.changed(context);
        for (Runnable listener : LISTENERS) listener.run();
    }
    public static void listen(Runnable listener) { LISTENERS.add(listener); }
    public static void unlisten(Runnable listener) { LISTENERS.remove(listener); }

    private static Call primary() {
        for (Call call : CALLS.keySet()) if (call.getState() == Call.STATE_RINGING) return call;
        for (Call call : CALLS.keySet()) if (call.getState() != Call.STATE_DISCONNECTED) return call;
        return CALLS.isEmpty() ? null : CALLS.keySet().iterator().next();
    }

    static String label(int state) {
        switch (state) {
            case Call.STATE_NEW: return "Yeni çağrı";
            case Call.STATE_CONNECTING: return "Şebekeye bağlanıyor";
            case Call.STATE_SELECT_PHONE_ACCOUNT: return "Arama hesabı seçimi bekleniyor";
            case Call.STATE_DIALING: return "Aranıyor";
            case Call.STATE_RINGING: return "Gelen arama";
            case Call.STATE_ACTIVE: return "Görüşme sürüyor";
            case Call.STATE_HOLDING: return "Beklemede";
            case Call.STATE_DISCONNECTING: return "Sonlandırılıyor";
            case Call.STATE_DISCONNECTED: return "Görüşme sona erdi";
            default: return "Telecom durumu: " + state;
        }
    }

    public static JSONObject snapshot() throws Exception {
        Call call = primary();
        if (call == null) return null;
        JSONObject result = new JSONObject();
        result.put("id", CALLS.get(call));
        result.put("state", call.getState());
        result.put("label", label(call.getState()));
        Uri handle = call.getDetails() == null ? null : call.getDetails().getHandle();
        String raw = handle == null ? "" : handle.getSchemeSpecificPart();
        String number = PlatformRules.number(raw);
        result.put("number", number.isEmpty() ? "Gizli / bilinmeyen numara" : number);
        result.put("canHold", call.getDetails() != null && call.getDetails().can(Call.Details.CAPABILITY_HOLD));
        result.put("muted", audio != null && audio.isMuted());
        result.put("speaker", audio != null && audio.getRoute() == CallAudioState.ROUTE_SPEAKER);
        result.put("speakerAvailable", audio != null && (audio.getSupportedRouteMask() & CallAudioState.ROUTE_SPEAKER) != 0);
        result.put("count", CALLS.size());
        JSONArray accounts = new JSONArray();
        if (call.getState() == Call.STATE_SELECT_PHONE_ACCOUNT && call.getDetails() != null
            && call.getDetails().getIntentExtras() != null) {
            java.util.ArrayList<android.telecom.PhoneAccountHandle> handles = call.getDetails().getIntentExtras()
                .getParcelableArrayList(Call.AVAILABLE_PHONE_ACCOUNTS);
            if (handles != null) for (int i = 0; i < handles.size(); i++) accounts.put(i);
        }
        result.put("accounts", accounts);
        if (call.getState() == Call.STATE_DISCONNECTED && call.getDetails() != null
            && call.getDetails().getDisconnectCause() != null)
            result.put("disconnectCode", call.getDetails().getDisconnectCause().getCode());
        return result;
    }

    public static void answer() { Call c = primary(); if (c != null && c.getState() == Call.STATE_RINGING) c.answer(VideoProfile.STATE_AUDIO_ONLY); }
    public static void end() {
        Call c = primary();
        if (c == null) return;
        if (c.getState() == Call.STATE_RINGING) c.reject(false, null); else c.disconnect();
    }
    public static void hold() {
        Call c = primary();
        if (c == null || c.getDetails() == null || !c.getDetails().can(Call.Details.CAPABILITY_HOLD)) return;
        if (c.getState() == Call.STATE_HOLDING) c.unhold(); else if (c.getState() == Call.STATE_ACTIVE) c.hold();
    }
    public static void mute() { if (service != null && audio != null) service.setMuted(!audio.isMuted()); }
    @SuppressWarnings("deprecation") public static void speaker() {
        if (service == null || audio == null) return;
        int route = audio.getRoute() == CallAudioState.ROUTE_SPEAKER
            ? ((audio.getSupportedRouteMask() & CallAudioState.ROUTE_WIRED_HEADSET) != 0
                ? CallAudioState.ROUTE_WIRED_HEADSET : CallAudioState.ROUTE_EARPIECE)
            : CallAudioState.ROUTE_SPEAKER;
        if ((audio.getSupportedRouteMask() & route) != 0) service.setAudioRoute(route);
    }
    public static void tone(char digit) {
        Call c = primary();
        if (c != null && c.getState() == Call.STATE_ACTIVE && "0123456789*#".indexOf(digit) >= 0) c.playDtmfTone(digit);
    }
    public static void stopTone() { Call c = primary(); if (c != null) c.stopDtmfTone(); }
    public static void selectAccount(int position) {
        Call c = primary();
        if (c == null || c.getState() != Call.STATE_SELECT_PHONE_ACCOUNT || c.getDetails() == null
            || c.getDetails().getIntentExtras() == null) return;
        java.util.ArrayList<android.telecom.PhoneAccountHandle> handles = c.getDetails().getIntentExtras()
            .getParcelableArrayList(Call.AVAILABLE_PHONE_ACCOUNTS);
        if (handles != null && position >= 0 && position < handles.size()) c.phoneAccountSelected(handles.get(position), false);
    }
}
