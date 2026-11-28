package org.oguzdows.mobile;

import android.app.Instrumentation;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import org.json.JSONObject;
import java.util.concurrent.atomic.AtomicLong;

/** QEMU-only observation, never an ANR timeout override, retry or product component.
 * Instrumentation can terminate on a focus timeout before DropBox saves the app trace.
 * Sample the actual app main thread BEFORE that happens, without blocking or dismissing UI.
 */
final class UiStallWatch implements AutoCloseable {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicLong heartbeat = new AtomicLong(SystemClock.elapsedRealtime());
    private volatile boolean active = true;
    private volatile String phase = "installer startup";
    private final Runnable pulse = new Runnable() {
        @Override public void run() {
            heartbeat.set(SystemClock.elapsedRealtime());
            if (active) main.postDelayed(this, 200);
        }
    };
    private final Thread observer;

    UiStallWatch(Instrumentation instrumentation) {
        if (!Build.HARDWARE.contains("ranchu") && !Build.HARDWARE.contains("goldfish"))
            throw new AssertionError("Emulator diagnostics only");
        String process = instrumentation.getTargetContext().getPackageName();
        main.post(pulse);
        observer = new Thread(() -> {
            try {
                while (active) {
                    Thread.sleep(250);
                    long delay = SystemClock.elapsedRealtime() - heartbeat.get();
                    if (delay < 2000) continue;
                    StringBuilder stack = new StringBuilder();
                    for (StackTraceElement line : Looper.getMainLooper().getThread().getStackTrace()) {
                        stack.append("  at ").append(line).append('\n');
                        if (stack.length() > 2400) break;
                    }
                    JSONObject report = new JSONObject().put("process", process).put("phase", phase).put("pid", android.os.Process.myPid())
                        .put("main_delay_ms", delay).put("main", stack.toString());
                    Bundle status = new Bundle(); status.putString("stream", "\nNATIVE_MAIN_STALL " + report + "\n");
                    instrumentation.sendStatus(0, status);
                    return; // One diagnostic only; never change the test result or touch the UI.
                }
            } catch (InterruptedException stopped) { Thread.currentThread().interrupt(); }
            catch (Exception ignored) { /* Missing diagnostics cannot turn a failure into a pass. */ }
        }, "oguz-ci-main-observer");
        observer.setDaemon(true); observer.start();
    }
    void phase(String value) { phase = value; }
    @Override public void close() { active = false; main.removeCallbacks(pulse); observer.interrupt(); }
}
