package org.oguzdows.mobile;

import android.service.voice.VoiceInteractionService;
import android.service.voice.VoiceInteractionSession;

/** System-bound only after explicit default-assistant selection; never listens to audio. */
public final class RifkiVoiceService extends VoiceInteractionService {
    @Override public void onReady() {
        super.onReady();
        // No screen text or screenshots are needed for this text-only starter.
        setDisabledShowContext(VoiceInteractionSession.SHOW_WITH_ASSIST | VoiceInteractionSession.SHOW_WITH_SCREENSHOT);
    }
}
