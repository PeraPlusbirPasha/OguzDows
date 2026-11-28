package org.oguzdows.mobile;

import android.content.Intent;
import android.os.RemoteException;
import android.speech.RecognitionService;
import android.speech.SpeechRecognizer;

/** Required VoiceInteractionService metadata endpoint; audio is intentionally NOT implemented. */
public final class RifkiRecognitionService extends RecognitionService {
    private void unavailable(Callback listener) {
        try { listener.error(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS); }
        catch (RemoteException ignored) { /* Client already gone; no audio resources were opened. */ }
    }
    @Override protected void onStartListening(Intent intent, Callback listener) { unavailable(listener); }
    @Override protected void onStopListening(Callback listener) { unavailable(listener); }
    @Override protected void onCancel(Callback listener) { /* Nothing is recording. */ }
}
