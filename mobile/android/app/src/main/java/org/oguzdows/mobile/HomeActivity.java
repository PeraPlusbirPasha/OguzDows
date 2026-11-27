package org.oguzdows.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.role.RoleManager;
import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.database.ContentObserver;
import android.graphics.Color;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.provider.Telephony;
import android.telecom.TelecomManager;
import android.telephony.TelephonyManager;
import android.view.ViewGroup;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.FrameLayout;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.webkit.JavaScriptReplyProxy;
import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Bundled offline rich UI + narrow origin-bound platform adapter; not a ROM or remote website. */
public final class HomeActivity extends Activity {
    public static final String ORIGIN = "https://appassets.androidplatform.net";
    private static final int ROLE_REQUEST = 61, PERMISSION_REQUEST = 62, FILE_REQUEST = 63;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    WebView webView;
    private Reply pending;
    private ValueCallback<Uri[]> fileCallback;
    private boolean receiverRegistered, observerRegistered, contactsObserved, frontendReady, intentDelivered;
    private final ContentObserver contactsObserver = new ContentObserver(main) {
        @Override public void onChange(boolean selfChange) { signal(); }
    };
    private final BroadcastReceiver stateReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) { signal(); }
    };
    private final ContentObserver smsObserver = new ContentObserver(main) {
        @Override public void onChange(boolean selfChange) { signal(); }
    };

    @Override public void onCreate(Bundle state) {
        NativeUi.theme(this); super.onCreate(state);
        intentDelivered = state != null && state.getBoolean("draftIntentDelivered", false);
        FrameLayout root = new FrameLayout(this); root.setBackgroundColor(Color.parseColor("#17262B"));
        webView = new WebView(this); root.addView(webView, new FrameLayout.LayoutParams(-1, -1)); setContentView(root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            Insets ime = insets.getInsets(WindowInsetsCompat.Type.ime());
            root.setPadding(bars.left, bars.top, bars.right, Math.max(bars.bottom, ime.bottom));
            return insets;
        });
        ViewCompat.requestApplyInsets(root);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false); settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true); settings.setGeolocationEnabled(false);
        WebView.setWebContentsDebuggingEnabled(false);
        WebViewAssetLoader assets = new WebViewAssetLoader.Builder()
            .addPathHandler("/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        webView.setWebViewClient(new WebViewClientCompat() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (isLocal(url) && "GET".equals(request.getMethod())) {
                    if ("/api/rifki/status".equals(url.getPath()))
                        return response("application/json", "{\"enabled\":false,\"tools\":false,\"message\":\"Yerel rehber; model bağlı değil.\"}", 200);
                    WebResourceResponse result = assets.shouldInterceptRequest(url);
                    if (result != null) {
                        if ("text/html".equals(result.getMimeType())) {
                            java.util.Map<String, String> headers = new java.util.HashMap<>();
                            if (result.getResponseHeaders() != null) headers.putAll(result.getResponseHeaders());
                            headers.put("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; media-src 'self' blob: data:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'");
                            headers.put("X-Content-Type-Options", "nosniff"); result.setResponseHeaders(headers);
                        }
                        return result;
                    }
                    return response("text/plain", "Not found", 404);
                }
                return response("text/plain", "Bundled UI has no network access", 403);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (isLocal(request.getUrl())) return false;
                if (request.isForMainFrame() && request.hasGesture()) confirmExternal(request.getUrl().toString());
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                frontendReady = false;
                super.onPageStarted(view, url, favicon);
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (isLocal(Uri.parse(url))) { deliverIntent(getIntent()); signal(); }
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) { request.deny(); }
            @Override public void onGeolocationPermissionsShowPrompt(String origin, android.webkit.GeolocationPermissions.Callback callback) { callback.invoke(origin, false, false); }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                try { startActivityForResult(intent, FILE_REQUEST); }
                catch (ActivityNotFoundException error) { fileCallback.onReceiveValue(null); fileCallback = null; }
                return true;
            }
        });
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            new AlertDialog.Builder(this).setTitle("Web görünümü güncellemesi gerekiyor")
                .setMessage("Güvenli yerel köprü bu sistem WebView sürümünde yok. Telefon/SMS köprüsü açılmadı; sistem WebView bileşenini güncelle.")
                .setPositiveButton("Tamam", null).show();
        } else {
            WebViewCompat.addWebMessageListener(webView, "OguzPlatform", Collections.singleton(ORIGIN),
                (view, message, sourceOrigin, isMainFrame, proxy) -> {
                    if (!isMainFrame || !ORIGIN.equals(sourceOrigin.toString())) return;
                    receive(message, proxy);
                });
        }
        // Bootstrap the shared native theme before React's first device.theme effect. This also
        // covers external DIAL/SENDTO launches, not just a launcher-provided screen intent.
        webView.loadUrl(ORIGIN + "/index.html?nativeTheme=" + (NativeUi.dark(this) ? "dark" : "light")
            + "&nativeAccent=" + ShellStyles.webAccent(new LauncherStore(this).wallpaper()));
        if (Build.VERSION.SDK_INT >= 33) getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
            android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::back);
    }
    static boolean isLocal(Uri uri) {
        return "https".equals(uri.getScheme()) && "appassets.androidplatform.net".equals(uri.getHost())
            && uri.getPort() == -1 && uri.getUserInfo() == null;
    }
    private static WebResourceResponse response(String mime, String body, int code) {
        WebResourceResponse result = new WebResourceResponse(mime, "UTF-8", new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8)));
        result.setStatusCodeAndReasonPhrase(code, code == 200 ? "OK" : "Blocked");
        result.setResponseHeaders(Collections.singletonMap("Cache-Control", "no-store")); return result;
    }
    private final class Reply {
        final String id; final JavaScriptReplyProxy proxy; boolean done;
        Reply(String id, JavaScriptReplyProxy proxy) { this.id = id; this.proxy = proxy; }
        void ok(Object result) { send(true, result); }
        void error(String error) { send(false, error == null ? "İşlem tamamlanamadı." : error); }
        void send(boolean ok, Object value) {
            main.post(() -> {
                if (done || isFinishing() || isDestroyed()) return; done = true;
                try { proxy.postMessage(new JSONObject().put("id", id).put("ok", ok).put(ok ? "result" : "error", value == null ? JSONObject.NULL : value).toString()); }
                catch (Exception ignored) { /* The originating page may have closed. */ }
            });
        }
    }
    private void receive(WebMessageCompat message, JavaScriptReplyProxy proxy) {
        if (message.getType() != WebMessageCompat.TYPE_STRING) return;
        String raw = message.getData();
        if (raw == null || raw.length() > 16384) return;
        Reply reply = null;
        try {
            JSONObject request = new JSONObject(raw); String id = request.optString("id");
            if (!id.matches("[A-Za-z0-9-]{1,80}")) return;
            reply = new Reply(id, proxy);
            JSONObject args = request.optJSONObject("args"); if (args == null) args = new JSONObject();
            switch (request.optString("action")) {
                case "ui.ready": frontendReady = true; deliverIntent(getIntent()); reply.ok(true); break;
                case "launcher.home": {
                    reply.ok(true);
                    main.post(() -> {
                        if (isFinishing() || isDestroyed()) return;
                        startActivity(new Intent(this, LauncherActivity.class).setAction(Intent.ACTION_MAIN)
                            .addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP));
                        finish();
                    }); break;
                }
                case "status": reply.ok(PlatformState.snapshot(this)); break;
                case "role.request": requestRole(args.getString("role"), reply); break;
                case "permissions.request": requestPermissionsFor(args.getString("scope"), reply); break;
                case "call.place": placeCall(args.getString("number"), reply); break;
                case "call.show": startActivity(new Intent(this, CallActivity.class)); reply.ok(true); break;
                case "messages.send": {
                    Reply target = reply;
                    SmsController.confirmSend(this, args.getString("number"), args.getString("body"), new SmsController.Result() {
                        @Override public void success(JSONObject result) { target.ok(result); }
                        @Override public void error(String text) { target.error(text); }
                    }); break;
                }
                case "messages.list": {
                    Reply target = reply;
                    worker.execute(() -> { try { target.ok(SmsController.messages(this)); } catch (Exception error) { target.error("SMS listesi okunamadı. Varsayılan SMS rolü ve okuma iznini kontrol et."); } }); break;
                }
                case "messages.pendingReply": {
                    android.content.SharedPreferences p = getSharedPreferences("pending-reply", MODE_PRIVATE);
                    reply.ok(new JSONObject().put("number", p.getString("number", "")).put("body", p.getString("body", ""))); break;
                }
                case "messages.clearPendingReply": getSharedPreferences("pending-reply", MODE_PRIVATE).edit().clear().apply(); reply.ok(true); break;
                case "contacts.open": startActivity(new Intent(this, ContactsActivity.class)); reply.ok(true); break;
                case "bridge.open": startActivity(new Intent(this, BridgeActivity.class)); reply.ok(true); break;
                case "contacts.list": {
                    Reply target = reply;
                    worker.execute(() -> { try { target.ok(SystemContacts.json(this)); }
                        catch (Exception error) { target.error("Rehber okunamadı. Kişiler ekranından açık okuma iznini kontrol et."); } }); break;
                }
                case "store.open": startActivity(new Intent(this, SourceStoreActivity.class)); reply.ok(true); break;
                case "apk.pick": startActivity(new Intent(this, InstallReviewActivity.class)); reply.ok(true); break;
                case "apps.open": startActivity(new Intent(this, InstalledAppsActivity.class)); reply.ok(true); break;
                case "google.play": openPlay(args.optString("package")); reply.ok(true); break;
                case "settings.open": openSettings(args.getString("panel")); reply.ok(true); break;
                case "device.volume": {
                    int value = args.getInt("value"); if (value < 0 || value > 100) throw new IllegalArgumentException();
                    AudioManager audio = getSystemService(AudioManager.class);
                    int max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
                    audio.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(value * max / 100f), 0);
                    reply.ok(PlatformState.snapshot(this)); signal(); break;
                }
                case "device.theme": {
                    String theme = args.getString("value");
                    if (!"dark".equals(theme) && !"light".equals(theme)) throw new IllegalArgumentException();
                    getSharedPreferences("native-ui", MODE_PRIVATE).edit().putBoolean("dark", "dark".equals(theme)).apply();
                    NativeUi.theme(this); PlatformState.changed(this); reply.ok(theme); break;
                }
                case "device.brightness": {
                    int value = args.getInt("value"); if (value < 25 || value > 100) throw new IllegalArgumentException();
                    android.view.WindowManager.LayoutParams window = getWindow().getAttributes(); window.screenBrightness = value / 100f;
                    getWindow().setAttributes(window); reply.ok(value); break;
                }
                default: reply.error("Bu yerel işlem izin listesinde yok.");
            }
        } catch (Exception error) {
            if (reply != null) reply.error("İşlem tamamlanamadı; istek, uygulama veya sistem izni uygun değil.");
        }
    }
    private void requestRole(String name, Reply reply) {
        if (pending != null) { reply.error("Önceki sistem seçimini tamamla."); return; }
        String role;
        switch (name) {
            case "dialer": role = RoleManager.ROLE_DIALER; break;
            case "sms": role = RoleManager.ROLE_SMS; break;
            case "home": role = RoleManager.ROLE_HOME; break;
            case "assistant": role = RoleManager.ROLE_ASSISTANT; break;
            default: reply.error("Bilinmeyen rol."); return;
        }
        RoleManager roles = getSystemService(RoleManager.class);
        if (!roles.isRoleAvailable(role)) { reply.error("Bu sistem rolü cihazda sunulmuyor."); return; }
        if (roles.isRoleHeld(role)) { try { reply.ok(PlatformState.snapshot(this)); } catch (Exception error) { reply.error("Durum okunamadı."); } return; }
        Runnable open = () -> { pending = reply; startActivityForResult(roles.createRequestRoleIntent(role), ROLE_REQUEST); };
        if (RoleManager.ROLE_SMS.equals(role)) {
            new AlertDialog.Builder(this).setTitle("Varsayılan SMS · emülatör aşaması")
                .setMessage("OğuzDows düz SMS alır ve gönderir; SMS geçmişini sistem sağlayıcısında tutar. MMS, RCS, ekler, grup mesajı ve operatör özellikleri tamamlanmış değildir. Varsayılanı değiştirince eski uygulama MMS alamayabilir. Fiziksel günlük telefonunda eksiksiz mesajlaşma uygulamanı koru. Bu seçimi sistem Varsayılan uygulamalar ayarından geri alabilirsin.\n\nRol veya izin vermek, taslağı göndermez. Her SMS için ayrıca alıcı/ücret onayı istenir.")
                .setPositiveButton("Sistem seçimine geç", (d, w) -> open.run()).setNegativeButton("Vazgeç", (d, w) -> reply.error("Rol değiştirilmedi."))
                .setOnCancelListener(d -> reply.error("Rol değiştirilmedi.")).show();
        } else open.run();
    }
    private void requestPermissionsFor(String scope, Reply reply) {
        if (pending != null) { reply.error("Önceki sistem seçimini tamamla."); return; }
        ArrayList<String> permissions = new ArrayList<>();
        if ("phone".equals(scope)) { permissions.add(Manifest.permission.CALL_PHONE); permissions.add(Manifest.permission.READ_PHONE_STATE); }
        else if ("sms".equals(scope) && PlatformState.role(this, RoleManager.ROLE_SMS)) {
            permissions.add(Manifest.permission.SEND_SMS); permissions.add(Manifest.permission.RECEIVE_SMS); permissions.add(Manifest.permission.READ_SMS);
        } else { reply.error("SMS izinlerinden önce SMS rolünü açıkça seç. Bilinmeyen izin kapsamı reddedildi."); return; }
        if (Build.VERSION.SDK_INT >= 33) permissions.add(Manifest.permission.POST_NOTIFICATIONS);
        permissions.removeIf(p -> PlatformState.granted(this, p));
        if (permissions.isEmpty()) { try { reply.ok(PlatformState.snapshot(this)); } catch (Exception error) { reply.error("İzin durumu okunamadı."); } return; }
        pending = reply; requestPermissions(permissions.toArray(new String[0]), PERMISSION_REQUEST);
    }
    private void placeCall(String raw, Reply reply) {
        String number = PlatformRules.number(raw);
        if (number.isEmpty()) { reply.error("3–20 rakam ve isteğe bağlı + kullan. USSD/servis kodları reddedildi."); return; }
        TelecomManager telecom = getSystemService(TelecomManager.class);
        TelephonyManager telephony = getSystemService(TelephonyManager.class);
        boolean emergency = "112".equals(number) || "911".equals(number);
        try { emergency |= telephony != null && telephony.isEmergencyNumber(number); } catch (RuntimeException ignored) { }
        if (emergency) {
            new AlertDialog.Builder(this).setTitle("Acil arama · sistem yolu")
                .setMessage("Acil arama, cihazın ön yüklü sistem acil arayıcısında yapılmalıdır. Bu deneysel arayüzden acil çağrı başlatılmaz; emülatörde acil numara test edilmez.")
                .setPositiveButton("Sistem acil arayıcısını aç", (d, w) -> {
                    try {
                        String systemDialer = telecom.getSystemDialerPackage();
                        if (systemDialer == null || getPackageName().equals(systemDialer)) throw new ActivityNotFoundException();
                        startActivity(new Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", number, null)).setPackage(systemDialer));
                        reply.error("Ön yüklü sistem arayıcısı açıldı; burada arama yapılmadı.");
                    } catch (RuntimeException error) { reply.error("Ön yüklü arayıcı açılamadı. Cihazın fiziksel acil arama yolunu kullan."); }
                })
                .setNegativeButton("Vazgeç", (d, w) -> reply.error("Arama yapılmadı.")).show(); return;
        }
        if (!PlatformState.role(this, RoleManager.ROLE_DIALER) || !PlatformState.granted(this, Manifest.permission.CALL_PHONE)) {
            reply.error("Önce varsayılan Telefon rolünü ve arama iznini ayrı düğmelerden seç. Arama otomatik tekrar başlatılmaz."); return;
        }
        new AlertDialog.Builder(this).setTitle("Aramayı onayla")
            .setMessage(number + "\n\nCihazın telefon hattından arama isteği gönderilecek; operatör ücreti olabilir. Bağlantı durumu Telecom servisinden okunur.")
            .setPositiveButton("Aramayı başlat", (d, w) -> {
                try {
                    if (!PlatformState.role(this, RoleManager.ROLE_DIALER)
                        || checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) throw new SecurityException();
                    telecom.placeCall(Uri.fromParts("tel", number, null), new Bundle());
                    reply.ok(new JSONObject().put("state", "requested").put("message", "Telecom’a arama isteği iletildi; henüz bağlantı doğrulanmadı."));
                } catch (SecurityException error) { reply.error("Arama izni veya Telefon rolü değişti. Arama yeniden denenmedi."); }
                catch (Exception error) { reply.error("Telecom arama isteğini kabul etmedi. İzin, hat ve şebeke durumunu kontrol et."); }
            }).setNegativeButton("Vazgeç", (d, w) -> reply.error("Arama iptal edildi."))
            .setOnCancelListener(d -> reply.error("Arama iptal edildi.")).show();
    }
    private void confirmExternal(String raw) {
        Uri uri = Uri.parse(raw);
        if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || raw.length() > 2048) return;
        new AlertDialog.Builder(this).setTitle("Harici tarayıcıda aç")
            .setMessage(uri.getHost() + "\n\nBu site ayrı sistem tarayıcısında açılır; yerel telefon/SMS köprüsüne erişemez.")
            .setPositiveButton("Siteyi aç", (d, w) -> {
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)); }
                catch (ActivityNotFoundException ignored) { new AlertDialog.Builder(this).setMessage("HTTPS tarayıcısı bulunamadı.").setPositiveButton("Tamam", null).show(); }
            }).setNegativeButton("Vazgeç", null).show();
    }
    private void openPlay(String packageName) {
        if (!packageName.isEmpty() && !PlatformRules.packageName(packageName)) throw new IllegalArgumentException();
        Intent intent = packageName.isEmpty() ? getPackageManager().getLaunchIntentForPackage("com.android.vending")
            : new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + packageName)).setPackage("com.android.vending");
        if (intent != null && intent.resolveActivity(getPackageManager()) != null) startActivity(intent);
        else new AlertDialog.Builder(this).setTitle("Google Play bu cihazda yok")
            .setMessage("GMS/Play paketlenmez veya sonradan sessizce kurulmaz. Lisanslı Play sistem imajı/sertifikalı cihaz gerekir. Web kataloğu GMS, Play Integrity, bankacılık veya DRM uyumluluğu sağlamaz.")
            .setPositiveButton("Web kataloğu", (d, w) -> confirmExternal("https://play.google.com/store/apps"))
            .setNegativeButton("Geri", null).show();
    }
    private void openSettings(String panel) {
        String action;
        switch (panel) {
            case "all": action = Settings.ACTION_SETTINGS; break;
            case "security": action = Settings.ACTION_SECURITY_SETTINGS; break;
            case "wifi": action = Settings.Panel.ACTION_WIFI; break;
            case "bluetooth": action = Settings.ACTION_BLUETOOTH_SETTINGS; break;
            case "airplane": action = Settings.ACTION_AIRPLANE_MODE_SETTINGS; break;
            case "focus": action = Settings.ACTION_ZEN_MODE_PRIORITY_SETTINGS; break;
            case "display": action = Settings.ACTION_DISPLAY_SETTINGS; break;
            case "volume": action = Settings.Panel.ACTION_VOLUME; break;
            case "sim": action = Settings.ACTION_WIRELESS_SETTINGS; break;
            case "defaults": action = Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS; break;
            case "home": action = Settings.ACTION_HOME_SETTINGS; break;
            case "battery": action = Intent.ACTION_POWER_USAGE_SUMMARY; break;
            case "app": action = Settings.ACTION_APPLICATION_DETAILS_SETTINGS; break;
            case "notifications": action = Settings.ACTION_APP_NOTIFICATION_SETTINGS; break;
            default: throw new IllegalArgumentException();
        }
        Intent intent = new Intent(action);
        if ("app".equals(panel)) intent.setData(Uri.parse("package:" + getPackageName()));
        if ("notifications".equals(panel)) intent.putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
        startActivity(intent);
    }
    private void deliverIntent(Intent intent) {
        // Do not consume a cold-start dial/message intent before React has registered its draft-only listener.
        if (webView == null || intent == null || !frontendReady || intentDelivered) return;
        String screen = intent.getStringExtra("screen");
        if (!java.util.Arrays.asList("home", "phone", "messages", "contacts", "calendar", "clock", "media", "browser", "gallery", "calculator", "notes", "tasks", "workbench", "news", "culture", "files", "google", "monitor", "settings", "rifki", "store", "apps", "search").contains(screen == null ? "" : screen)) screen = "";
        String number = "", body = "";
        if (Intent.ACTION_DIAL.equals(intent.getAction()) || Intent.ACTION_VIEW.equals(intent.getAction()) || Intent.ACTION_SENDTO.equals(intent.getAction())) {
            Uri data = intent.getData();
            if (data != null && data.getScheme() != null && java.util.Arrays.asList("tel", "sms", "smsto", "mms", "mmsto").contains(data.getScheme())) {
                number = PlatformRules.number(data.getSchemeSpecificPart().split("[?;]", 2)[0]);
                screen = "tel".equals(data.getScheme()) ? "phone" : "messages";
                String extra = intent.getStringExtra("sms_body");
                body = extra == null ? "" : extra.substring(0, Math.min(2000, extra.length()));
            }
        }
        if (!screen.isEmpty()) {
            try {
                JSONObject payload = new JSONObject().put("screen", screen).put("number", number).put("body", body);
                String launcherTheme = intent.getStringExtra("launcherTheme");
                if (intent.getBooleanExtra("fromLauncher", false) && ("dark".equals(launcherTheme) || "light".equals(launcherTheme)))
                    payload.put("theme", launcherTheme);
                webView.evaluateJavascript("window.dispatchEvent(new CustomEvent('oguz-native-intent',{detail:" + payload + "}));", null);
                // Keep framework routing metadata immutable. Consuming a draft is separate state;
                // mutating action/data also breaks AndroidX lifecycle tracking for cold-start intents.
                intentDelivered = true;
            } catch (Exception ignored) { }
        }
    }
    private void signal() {
        if (webView != null && !isDestroyed()) webView.evaluateJavascript("window.dispatchEvent(new Event('oguz-native-state'))", null);
        observeSms();
        boolean contactsAllowed = PlatformState.granted(this, Manifest.permission.READ_CONTACTS);
        if (contactsAllowed && !contactsObserved && receiverRegistered) {
            try { getContentResolver().registerContentObserver(android.provider.ContactsContract.Contacts.CONTENT_URI, true, contactsObserver); contactsObserved = true; }
            catch (SecurityException ignored) { }
        } else if (!contactsAllowed && contactsObserved) { getContentResolver().unregisterContentObserver(contactsObserver); contactsObserved = false; }
    }
    private void observeSms() {
        boolean allowed = PlatformState.role(this, RoleManager.ROLE_SMS) && PlatformState.granted(this, Manifest.permission.READ_SMS);
        if (allowed && !observerRegistered && receiverRegistered) {
            try { getContentResolver().registerContentObserver(Telephony.Sms.CONTENT_URI, true, smsObserver); observerRegistered = true; }
            catch (SecurityException ignored) { }
        } else if (!allowed && observerRegistered) { getContentResolver().unregisterContentObserver(smsObserver); observerRegistered = false; }
    }
    @Override protected void onStart() {
        super.onStart();
        androidx.core.content.ContextCompat.registerReceiver(this, stateReceiver,
            new IntentFilter(PlatformState.CHANGED), androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED);
        receiverRegistered = true; observeSms();
    }
    @Override protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
        signal();
    }
    @Override protected void onPause() {
        // Per-view lifecycle: stop unnecessary off-screen WebView rendering during
        // native call/installer/settings transitions. Never pause global WebView timers.
        if (webView != null) webView.onPause();
        super.onPause();
    }
    @Override protected void onStop() {
        if (receiverRegistered) { unregisterReceiver(stateReceiver); receiverRegistered = false; }
        if (observerRegistered) { getContentResolver().unregisterContentObserver(smsObserver); observerRegistered = false; }
        if (contactsObserved) { getContentResolver().unregisterContentObserver(contactsObserver); contactsObserved = false; }
        super.onStop();
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent); intentDelivered = false; deliverIntent(intent);
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("draftIntentDelivered", intentDelivered); super.onSaveInstanceState(state);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == FILE_REQUEST) {
            ArrayList<Uri> uris = new ArrayList<>();
            if (result == RESULT_OK && data != null) {
                if (data.getClipData() != null) for (int i = 0; i < Math.min(6, data.getClipData().getItemCount()); i++) {
                    Uri uri = data.getClipData().getItemAt(i).getUri(); if (uri != null && "content".equals(uri.getScheme())) uris.add(uri);
                }
                else if (data.getData() != null && "content".equals(data.getData().getScheme())) uris.add(data.getData());
            }
            if (fileCallback != null) fileCallback.onReceiveValue(uris.isEmpty() ? null : uris.toArray(new Uri[0])); fileCallback = null;
        }
        if (request == ROLE_REQUEST && pending != null) {
            try { pending.ok(PlatformState.snapshot(this)); } catch (Exception error) { pending.error("Rol durumu okunamadı."); }
            pending = null; signal(); // No call/SMS is retried after a role decision.
        }
    }
    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request == PERMISSION_REQUEST && pending != null) {
            try { pending.ok(PlatformState.snapshot(this)); } catch (Exception error) { pending.error("İzin durumu okunamadı."); }
            pending = null; signal(); // No call/SMS is retried after a permission decision.
        }
    }
    private void back() {
        // A launcher module returns to the real native HOME, never to the obsolete web home.
        if (getIntent().getBooleanExtra("fromLauncher", false)) finish();
        else if (webView.canGoBack()) webView.goBack();
        else webView.evaluateJavascript("location.hash='/home'", null);
    }
    @SuppressWarnings("deprecation") @Override public void onBackPressed() { back(); }
    @Override protected void onDestroy() {
        worker.shutdownNow();
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (webView != null) { ((ViewGroup)webView.getParent()).removeView(webView); webView.destroy(); webView = null; }
        super.onDestroy();
    }
}
