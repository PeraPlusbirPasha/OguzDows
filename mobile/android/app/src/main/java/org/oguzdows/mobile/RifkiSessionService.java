package org.oguzdows.mobile;

import android.os.Bundle;
import android.service.voice.VoiceInteractionSession;
import android.service.voice.VoiceInteractionSessionService;
import android.text.InputFilter;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Text interaction only. No microphone, hotword engine, model or screen-context reader. */
public final class RifkiSessionService extends VoiceInteractionSessionService {
    @Override public VoiceInteractionSession onNewSession(Bundle args) {
        return new VoiceInteractionSession(this) {
            @Override public View onCreateContentView() {
                LinearLayout box = new LinearLayout(getContext());
                box.setOrientation(LinearLayout.VERTICAL);
                int padding = Math.round(24 * getResources().getDisplayMetrics().density);
                box.setPadding(padding, padding, padding, padding);
                box.setBackgroundColor(0xFFF4F3EB);
                ImageView portrait = new ImageView(getContext()); portrait.setImageResource(R.drawable.rifki);
                portrait.setContentDescription("Rıfkı, OğuzDows’un kedi rehberi");
                portrait.setScaleType(ImageView.ScaleType.FIT_CENTER);
                box.addView(portrait, new LinearLayout.LayoutParams(-1, padding * 5));
                TextView answer = new TextView(getContext()); answer.setTextColor(0xFF263C38); answer.setTextSize(17);
                answer.setText("Merhaba, ben Rıfkı. Bu iskelette çevrimdışı, sınırlı yerel rehberim; üretken model bağlı değil. Mikrofonunu veya ekranını okumam. Notlar, APK ve Google hakkında sorabilirsin.");
                box.addView(answer);
                EditText input = new EditText(getContext()); input.setTextColor(0xFF263C38); input.setHintTextColor(0xFF73837A);
                input.setHint("Aklından ne geçiyor?"); input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(2000)});
                box.addView(input);
                Button send = new Button(getContext()); send.setText("Rıfkı’ya sor"); send.setAllCaps(false);
                send.setOnClickListener(v -> answer.setText(RifkiText.reply(input.getText().toString())));
                box.addView(send);
                Button close = new Button(getContext()); close.setText("Kapat"); close.setOnClickListener(v -> hide()); box.addView(close);
                return box;
            }
        };
    }
}
