package org.oguzdows.mobile

import android.app.KeyguardManager
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** An explicit companion surface ABOVE the real keyguard, never an authentication replacement. */
class LockActivity : ComponentActivity() {
    private var message by mutableStateOf("")
    override fun onCreate(savedInstanceState: Bundle?) {
        NativeUi.theme(this); super.onCreate(savedInstanceState)
        setShowWhenLocked(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContent {
            val store=remember{LauncherStore(this)}
            var now by remember {mutableStateOf(LocalDateTime.now())}
            LaunchedEffect(Unit) {while(true){now=LocalDateTime.now();delay(1000)}}
            ConnectedTheme(NativeUi.dark(this),store.wallpaper(),store.glass(),store.lightEffects()) {
                BackHandler { finish() } // System keyguard remains underneath; no trapping or fake PIN.
                Box(Modifier.fillMaxSize().testTag("oguz-lock-surface")) {
                    Image(painterResource(ShellWallpapers[store.wallpaper()]),null,Modifier.fillMaxSize(),contentScale=ContentScale.Crop)
                    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0x44203235),Color(0xED14282F)))))
                    Column(Modifier.fillMaxSize().systemBarsPadding().padding(26.dp),horizontalAlignment=Alignment.CenterHorizontally) {
                        Spacer(Modifier.height(30.dp));Image(painterResource(R.drawable.nazar),"OğuzDows",Modifier.size(38.dp))
                        Text("SENİN DÜNYAN. BİRAZ SAKİN.",color=Color.White,fontSize=10.sp,modifier=Modifier.padding(top=16.dp))
                        Text(now.format(DateTimeFormatter.ofPattern("HH:mm")),color=Color.White,fontSize=76.sp)
                        Text(now.format(DateTimeFormatter.ofPattern("d MMMM EEEE",Locale.forLanguageTag("tr-TR"))),color=Color.White)
                        Spacer(Modifier.weight(1f));Image(painterResource(R.drawable.rifki),null,Modifier.size(120.dp))
                        GlassSurface(Modifier.fillMaxWidth()) {Column(Modifier.padding(20.dp)) {
                            Text("Rıfkı nöbette.",style=MaterialTheme.typography.titleLarge)
                            Text(if(getSystemService(KeyguardManager::class.java).isDeviceSecure)
                                "Güvenlik sistemin PIN/parmak izindedir. Özel kişi/SMS/bildirim içeriği burada gösterilmez."
                                else "Bu bir OğuzDows karşılama perdesi; güvenlik kilidi DEĞİL. Cihazda önce sistem PIN/parmak izini ayarla.",style=MaterialTheme.typography.bodySmall)
                            if(message.isNotBlank()) Text(message)
                            Button(onClick=::unlock,modifier=Modifier.fillMaxWidth().testTag("lock-continue")){Text("Sistemle devam et")}
                            TextButton(onClick={startActivity(Intent(Settings.ACTION_SECURITY_SETTINGS))}){Text("Gerçek kilit ve güvenlik ayarları")}
                        }}
                        var travel by remember {mutableFloatStateOf(0f)}
                        Box(Modifier.fillMaxWidth().height(64.dp).pointerInput(Unit){detectVerticalDragGestures(onDragStart={travel=0f},onDragEnd={if(travel < -50)unlock()}){change,dy->change.consume();travel+=dy}},contentAlignment=Alignment.Center){Text("↑ Yukarı kaydır veya düğmeye dokun",color=Color.White)}
                        Text("Stok güvenli kilit kaldırılmaz. Bu yüzey kendiliğinden diğer uygulamaların üstüne açılmaz.",color=Color.White.copy(.8f),fontSize=10.sp)
                    }
                }
            }
        }
    }
    override fun onResume(){super.onResume();shellFullscreen(true)}
    private fun unlock() {
        val keyguard=getSystemService(KeyguardManager::class.java)
        if(!keyguard.isKeyguardLocked){finish();return}
        keyguard.requestDismissKeyguard(this,object:KeyguardManager.KeyguardDismissCallback(){
            override fun onDismissSucceeded(){finish()}
            override fun onDismissCancelled(){message="Sistem kilidi açılmadı; özel içerik kapalı."}
            override fun onDismissError(){message="Sistemin kendi kilit açma hareketini kullan."}
        })
    }
}
