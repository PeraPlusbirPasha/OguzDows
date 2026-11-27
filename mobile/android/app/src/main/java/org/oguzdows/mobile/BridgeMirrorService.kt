package org.oguzdows.mobile

import android.app.Activity
import android.app.KeyguardManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.SystemClock
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import java.io.ByteArrayOutputStream

/** No process-persistent credentials. Only the visible native Activity can create/choose this host. */
object BridgeRuntime {
    @Volatile var host: BridgeHost? = null
    @Volatile var visible = false
}

/** Read-only, no audio, 2 fps / longest edge 1280. Every start needs fresh system capture consent. */
class BridgeMirrorService : Service() {
    private var projection: MediaProjection? = null
    private var session: BridgeHost? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var worker: HandlerThread? = null
    private var registered = false
    private var lastFrame = 0L
    private val screenOff = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) { stopSelf() }
    }
    companion object {
        const val STOP = "org.oguzdows.mobile.STOP_MIRROR"
        @Volatile var running = false
            private set
    }
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP || intent == null) { stopSelf(); return START_NOT_STICKY }
        val host = BridgeRuntime.host
        val consent = IntentCompat.getParcelableExtra(intent, "consent", Intent::class.java)
        val keyguard = getSystemService(KeyguardManager::class.java)
        if (running || host == null || host.closed || host.viewer == null || consent == null ||
            intent.getIntExtra("result", 0) != Activity.RESULT_OK || keyguard.isKeyguardLocked) {
            stopSelf(); return START_NOT_STICKY
        }
        session = host
        try {
            val notifications = getSystemService(NotificationManager::class.java)
            notifications.createNotificationChannel(NotificationChannel("oguzkopru-mirror", "OğuzKöprü ekran paylaşımı", NotificationManager.IMPORTANCE_LOW))
            val stop = PendingIntent.getService(this, 702, Intent(this, BridgeMirrorService::class.java).setAction(STOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val open = PendingIntent.getActivity(this, 703, Intent(this, BridgeActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = Notification.Builder(this, "oguzkopru-mirror").setSmallIcon(R.drawable.nazar)
                .setContentTitle("OğuzKöprü · ekranın paylaşılıyor")
                .setContentText("Salt görüntü · ses ve uzaktan kontrol yok. Durdurmak için dokun.")
                .setContentIntent(open).setOngoing(true).setVisibility(Notification.VISIBILITY_SECRET)
                .addAction(Notification.Action.Builder(null, "Paylaşımı durdur", stop).build()).build()
            ServiceCompat.startForeground(this, 701, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
            projection = getSystemService(MediaProjectionManager::class.java).getMediaProjection(Activity.RESULT_OK, consent)
            val thread = HandlerThread("oguzkopru-frames").apply { start() }; worker = thread
            val handler = Handler(thread.looper)
            projection!!.registerCallback(object : MediaProjection.Callback() { override fun onStop() { stopSelf() } }, Handler(mainLooper))
            val metrics = resources.displayMetrics
            val bounds = if (Build.VERSION.SDK_INT >= 30) getSystemService(android.view.WindowManager::class.java).maximumWindowMetrics.bounds
                else android.graphics.Rect(0, 0, metrics.widthPixels, metrics.heightPixels)
            val scale = minOf(1f, 1280f / maxOf(bounds.width(), bounds.height()).coerceAtLeast(1))
            val width = (bounds.width() * scale).toInt().coerceAtLeast(2)
            val height = (bounds.height() * scale).toInt().coerceAtLeast(2)
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2).apply {
                setOnImageAvailableListener({ source ->
                    val image = source.acquireLatestImage() ?: return@setOnImageAvailableListener
                    try {
                        if (host.closed || host.viewer == null || keyguard.isKeyguardLocked) { stopSelf(); return@setOnImageAvailableListener }
                        val now = SystemClock.elapsedRealtime()
                        if (now - lastFrame < 500) return@setOnImageAvailableListener
                        lastFrame = now
                        val plane = image.planes[0]
                        if (plane.pixelStride != 4) return@setOnImageAvailableListener
                        val paddedWidth = plane.rowStride / plane.pixelStride
                        if (paddedWidth !in width..(width + 256)) return@setOnImageAvailableListener
                        val padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888)
                        var cropped: Bitmap? = null
                        try {
                            plane.buffer.rewind(); padded.copyPixelsFromBuffer(plane.buffer)
                            cropped = Bitmap.createBitmap(padded, 0, 0, width, height)
                            val bytes = ByteArrayOutputStream()
                            cropped.compress(Bitmap.CompressFormat.JPEG, 55, bytes)
                            if (bytes.size() <= BridgeRules.MAX_FRAME) host.frame(bytes.toByteArray())
                        } finally { if (cropped !== padded) cropped?.recycle(); padded.recycle() }
                    } catch (_: Exception) { stopSelf() }
                    finally { image.close() }
                }, handler)
            }
            display = projection!!.createVirtualDisplay("OğuzKöprü · onaylı görüntü", width, height, metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader!!.surface, null, handler)
            ContextCompat.registerReceiver(this, screenOff, IntentFilter(Intent.ACTION_SCREEN_OFF), ContextCompat.RECEIVER_NOT_EXPORTED)
            registered = true; running = true
            handler.post(object : Runnable { override fun run() {
                if (host.closed || host.viewer == null || keyguard.isKeyguardLocked) stopSelf() else handler.postDelayed(this, 500)
            } })
        } catch (_: Exception) { host.stopMirror(); stopSelf() }
        return START_NOT_STICKY
    }
    override fun onDestroy() {
        running = false
        session?.stopMirror()
        if (registered) unregisterReceiver(screenOff)
        display?.release(); reader?.close()
        try { projection?.stop() } catch (_: Exception) { }
        worker?.quitSafely()
        stopForeground(STOP_FOREGROUND_REMOVE)
        if (!BridgeRuntime.visible) { session?.close(); if (BridgeRuntime.host === session) BridgeRuntime.host = null }
        super.onDestroy()
    }
    override fun onTaskRemoved(rootIntent: Intent?) { stopSelf() }
}
