package org.oguzdows.mobile

import android.Manifest
import android.content.Intent
import android.database.ContentObserver
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.ContactsContract
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Real provider read/add, opt-in read and write permissions independently. Paid actions remain drafts. */
class ContactsActivity : ComponentActivity() {
    private var rows by mutableStateOf(emptyList<SystemContact>())
    private var readAllowed by mutableStateOf(false)
    private var writeAllowed by mutableStateOf(false)
    private var busy by mutableStateOf(false)
    private var notice by mutableStateOf("")
    private var observing = false
    private var readJob: Job? = null
    private var generation = 0
    private val observer = object : ContentObserver(Handler(Looper.getMainLooper())) { override fun onChange(selfChange: Boolean) { refresh() } }
    private val readPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { refresh() }
    private val writePermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { refresh() }
    override fun onCreate(savedInstanceState: Bundle?) {
        NativeUi.theme(this); super.onCreate(savedInstanceState)
        setContent { val store = remember { LauncherStore(this) }
            ConnectedTheme(NativeUi.dark(this), store.wallpaper(), store.glass(), store.lightEffects()) { Screen() }
        }
    }
    override fun onStart() { super.onStart(); refresh() }
    override fun onResume() { super.onResume(); refresh(); shellFullscreen(LauncherStore(this).fullscreen()) }
    override fun onStop() {
        generation++; readJob?.cancel(); rows = emptyList()
        if (observing) contentResolver.unregisterContentObserver(observer)
        observing = false; super.onStop()
    }
    private fun refresh() {
        generation++; val version = generation; readJob?.cancel()
        readAllowed = PlatformState.granted(this, Manifest.permission.READ_CONTACTS)
        writeAllowed = PlatformState.granted(this, Manifest.permission.WRITE_CONTACTS)
        if (!readAllowed) { rows = emptyList(); if (observing) contentResolver.unregisterContentObserver(observer); observing = false; return }
        if (!observing && lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.STARTED)) {
            try { contentResolver.registerContentObserver(ContactsContract.Contacts.CONTENT_URI, true, observer); observing = true }
            catch (_: SecurityException) { rows = emptyList(); readAllowed = false; return }
        }
        readJob = lifecycleScope.launch {
            try {
                val loaded = withContext(Dispatchers.IO) { SystemContacts.read(this@ContactsActivity) }
                if (version == generation && PlatformState.granted(this@ContactsActivity, Manifest.permission.READ_CONTACTS)) { rows = loaded; notice = "" }
            } catch (cancel: CancellationException) { throw cancel }
            catch (_: Exception) { if(version == generation) { rows = emptyList(); notice = "Rehber okunamadı. İzin/profil durumunu kontrol et." } }
        }
    }
    private fun draft(contact: SystemContact, sms: Boolean) {
        startActivity(Intent(this, HomeActivity::class.java).setAction(if(sms) Intent.ACTION_SENDTO else Intent.ACTION_DIAL)
            .setData(Uri.fromParts(if(sms) "smsto" else "tel", contact.number, null)).putExtra("fromLauncher", true))
    }
    @OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
    @Composable private fun Screen() {
        var query by rememberSaveable { mutableStateOf("") }
        var add by rememberSaveable { mutableStateOf(false) }
        var name by rememberSaveable { mutableStateOf("") }
        var number by rememberSaveable { mutableStateOf("") }
        var confirm by remember { mutableStateOf(false) }
        val appearance = LocalAero.current
        Box(Modifier.fillMaxSize()) {
            Image(painterResource(ShellWallpapers[LauncherStore(this).wallpaper()]), null, Modifier.fillMaxSize(), contentScale=ContentScale.Crop)
            Box(Modifier.fillMaxSize().background(if(appearance.dark) Color(0xDC10262F) else Color(0xE8F1F6F2)))
            Surface(Modifier.fillMaxSize().testTag("system-contacts").semantics { testTagsAsResourceId = true }, color=Color.Transparent) {
            Column(Modifier.fillMaxSize().systemBarsPadding().imePadding().padding(20.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { finish() }) { Text("Geri") }
                    TextButton(onClick = { add = !add }) { Text(if(add) "Listeye dön" else "+ Kişi") }
                }
                Text("Kişilerin, gerçekten.", style = MaterialTheme.typography.headlineSmall)
                Text("Telefonun sistem rehberi · ağ/bulut kopyası yok", style = MaterialTheme.typography.bodySmall)
                if (!readAllowed) {
                    Text("Mevcut kişileri yalnız izin verdiğinde okuruz. Reddedersen telefon ve SMS’e numarayı elle yazabilirsin.", modifier = Modifier.padding(vertical=14.dp))
                    Button(onClick = { readPermission.launch(Manifest.permission.READ_CONTACTS) }) { Text("Rehberi okumaya izin ver") }
                } else Text("${rows.size} numara · en çok ${SystemContacts.LIMIT}", modifier=Modifier.padding(vertical=8.dp))
                if (notice.isNotBlank()) Text(notice, modifier=Modifier.testTag("contacts-notice"))
                if (add) {
                    Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                        OutlinedTextField(name, { name=it.take(120) }, label={Text("Ad soyad")}, singleLine=true,
                            modifier=Modifier.fillMaxWidth().testTag("contact-name"))
                        OutlinedTextField(number, {number=it.take(40)}, label={Text("Telefon numarası")}, singleLine=true,
                            modifier=Modifier.fillMaxWidth().testTag("contact-number"))
                        Text("Yeni kayıt cihazın yerel rehberine eklenir; mevcut kişiler değiştirilmez. Hesap eşitlemesini sistemin hesap ayarları yönetir.",
                            style=MaterialTheme.typography.bodySmall, modifier=Modifier.padding(vertical=12.dp))
                        if(!writeAllowed) Button(onClick={writePermission.launch(Manifest.permission.WRITE_CONTACTS)}) {
                            Text("Yeni kişi için yazma izni ver")
                        }
                        Button(enabled=writeAllowed && !busy && name.isNotBlank() && PlatformRules.number(number).isNotEmpty(),
                            onClick={confirm=true}, modifier=Modifier.testTag("contact-save")) { Text("Rehbere ekle") }
                    }
                } else {
                    OutlinedTextField(query,{query=it.take(120)},label={Text("Kişi ara")},singleLine=true,
                        modifier=Modifier.fillMaxWidth().testTag("contacts-search"))
                    val q=LauncherRules.normalize(query)
                    LazyColumn(Modifier.weight(1f)) {
                        items(rows.filter{LauncherRules.normalize(it.name+" "+it.number).contains(q)},key={"${it.id}:${it.number}"}) { contact ->
                            ListItem(
                                colors=ListItemDefaults.colors(containerColor=MaterialTheme.colorScheme.surface.copy(alpha=if(appearance.glass && !appearance.light) .65f else 1f)),
                                headlineContent={Text(contact.name)},
                                supportingContent={Text(contact.number)},
                                trailingContent={
                                    Row {
                                        TextButton(onClick={draft(contact,false)}) { Text("Ara") }
                                        TextButton(onClick={draft(contact,true)}) { Text("SMS") }
                                    }
                                },
                            )
                        }
                    }
                }
                TextButton(onClick={ startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:$packageName"))) }) {Text("İzinleri yönet / geri al")}
            }
        }
        }
        if(confirm) AlertDialog(onDismissRequest={confirm=false},title={Text("Yeni kişiyi kaydet?")},text={Text("${name.trim()}\n${PlatformRules.number(number)}\n\nYalnız bu yeni yerel kayıt eklenir.")},
            confirmButton={TextButton(onClick={confirm=false;busy=true;lifecycleScope.launch {
                try {withContext(Dispatchers.IO){SystemContacts.insert(this@ContactsActivity,name,number)};name="";number="";add=false;refresh()}
                catch (_:Exception){notice="Kayıt eklenemedi; izin/sağlayıcı değişmiş olabilir. Otomatik tekrar yapılmadı."}
                finally{busy=false}
            }}){Text("Kaydet")}},dismissButton={TextButton(onClick={confirm=false}){Text("Vazgeç")}})
    }
}
