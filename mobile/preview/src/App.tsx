import {
  useCallback,
  useEffect,
  useRef,
  useState,
  lazy,
  Suspense,
  type CSSProperties,
} from "react";
import { apps, WALLPAPER_NAMES, type Preferences, type Screen } from "./data";
import {
  initialState,
  restoreState,
  STORAGE_KEY,
  swipeAction,
} from "./core.mjs";
import {
  Apps,
  Culture,
  Files,
  Google,
  Monitor,
  News,
  Settings,
  Store,
  Workbench,
} from "./Screens";
import { Rifki } from "./Rifki";
import { AppBadge, Dialog, Icon, Nazar, Notice } from "./ui";
import { ControlCenter } from "./ControlCenter";
import { inNativeApp, nativeRequest, useNativeStatus } from "./native";
import { NativePower } from "./NativePower";
const Everyday = lazy(() => import("./Everyday"));

const screens: Screen[] = [
  "home",
  "apps",
  "search",
  ...apps.map((app) => app.id),
];
const everydayScreens: Screen[] = [
  "phone",
  "messages",
  "contacts",
  "calendar",
  "clock",
  "media",
  "browser",
  "gallery",
  "search",
];
const toolShortcuts: Partial<Record<Screen, string>> = {
  notes: "notes",
  tasks: "tasks",
  calculator: "calculator",
};
function readSaved() {
  try {
    return {
      prefs: restoreState(localStorage.getItem(STORAGE_KEY)) as Preferences,
      error: "",
    };
  } catch (err) {
    return {
      prefs: initialState() as Preferences,
      error: (err as Error).message,
    };
  }
}
function hashScreen(): Screen {
  const value = location.hash.replace("#/", "") as Screen;
  return screens.includes(value) ? value : "home";
}
export default function App() {
  const { status: nativeStatus } = useNativeStatus();
  const [now, setNow] = useState(() => new Date());
  const nativeTime = now.toLocaleTimeString("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  useEffect(() => {
    if (!inNativeApp) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const tick = () => {
      clearInterval(timer);
      if (!document.hidden) {
        setNow(new Date());
        timer = setInterval(() => setNow(new Date()), 30000);
      }
    };
    tick();
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, []);
  const [loaded] = useState(readSaved);
  const [prefs, setPrefs] = useState<Preferences>(loaded.prefs);
  const [storageError, setStorageError] = useState(loaded.error);
  const [screen, setScreen] = useState<Screen>(hashScreen);
  const [overlay, setOverlay] = useState("");
  const [tool, setTool] = useState("");
  const [storeTab, setStoreTab] = useState("discover");
  const [storeSelected, setStoreSelected] = useState("");
  const [toastText, setToast] = useState("");
  const [seed, setSeed] = useState("");
  const [locked, setLocked] = useState<"lock" | "off" | "">("");
  const [dial, setDial] = useState("");
  const [homePage, setHomePage] = useState(0);
  const homePageCount = Math.ceil(apps.length / 8);
  const touch = useRef<{ x: number; y: number; blocked: boolean } | null>(null);
  const ignoreClickUntil = useRef(0);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(() => {
    if (storageError) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
      setStorageError(
        "Yerel depolama kullanılamıyor. Değişiklikler yalnız bu açık oturumda kalır.",
      );
    }
  }, [prefs, storageError]);
  useEffect(() => {
    const back = () => {
      setScreen(hashScreen());
      setOverlay("");
    };
    window.addEventListener("popstate", back);
    window.addEventListener("hashchange", back);
    return () => {
      window.removeEventListener("popstate", back);
      window.removeEventListener("hashchange", back);
      clearTimeout(toastTimer.current);
    };
  }, []);
  const update = useCallback(
    (value: Partial<Preferences>) => setPrefs((p) => ({ ...p, ...value })),
    [],
  );
  const toast = useCallback((text: string) => {
    setToast(text);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4500);
  }, []);
  const go = useCallback((next: Screen) => {
    setScreen(next);
    setOverlay("");
    setLocked("");
    setTool("");
    setStoreTab("discover");
    setStoreSelected("");
    if (location.hash !== `#/${next}`)
      history.pushState({ screen: next }, "", `#/${next}`);
  }, []);
  const seedUsed = useCallback(() => setSeed(""), []);
  const closeDialog = useCallback(() => setOverlay(""), []);
  function openTool(id: string) {
    go("workbench");
    setTool(id);
  }
  function openApk() {
    go("store");
    setStoreTab("apk");
  }
  function ask(text: string) {
    go("rifki");
    setSeed(text);
  }
  function assistantAction(action: string) {
    if (action === "dark" || action === "light") {
      update({ theme: action });
      toast("Görünüm bu önizlemenin tüm yerel ekranlarına uygulandı.");
    } else if (action === "low-power") {
      update({ lowPower: true });
      toast("Hafif görsel profil etkin. Donanım güç ayarı değişmedi.");
    } else if (action === "apk") openApk();
    else if (action === "tasks" || action === "notes") openTool(action);
    else if (action === "controls") setOverlay("quick");
    else if (
      [
        "google",
        "culture",
        "phone",
        "messages",
        "contacts",
        "calendar",
        "clock",
        "media",
      ].includes(action)
    )
      go(action as Screen);
  }
  function openCatalog(id: string) {
    go("store");
    setStoreSelected(id);
  }
  function openCall(value: string) {
    setDial(value);
    go("phone");
  }
  function openCompose(value: string) {
    update({ messageDraft: { ...prefs.messageDraft, number: value } });
    go("messages");
  }
  function gestureStart(
    x: number,
    y: number,
    target: EventTarget,
    root: HTMLElement,
  ) {
    ignoreClickUntil.current = 0;
    const bounds = root.getBoundingClientRect();
    touch.current = {
      x: x - bounds.left,
      y: y - bounds.top,
      blocked:
        target instanceof Element &&
        !!target.closest("input,textarea,select,a,[data-gesture-ignore]"),
    };
  }
  function gestureEnd(x: number, y: number, root: HTMLElement) {
    const bounds = root.getBoundingClientRect();
    const action = swipeAction(
      touch.current,
      { x: x - bounds.left, y: y - bounds.top },
      { home: screen === "home", blocked: !!overlay || !!locked },
    );
    touch.current = null;
    if (!action) return;
    ignoreClickUntil.current = Date.now() + 350;
    if (action === "quick") setOverlay("quick");
    else if (action === "apps") go("apps");
    else if (action === "next-page")
      setHomePage((page) => (page + 1) % homePageCount);
    else if (action === "previous-page")
      setHomePage((page) => (page - 1 + homePageCount) % homePageCount);
  }
  useEffect(() => {
    if (!inNativeApp) return;
    void nativeRequest("device.theme", { value: prefs.theme }).catch(() => {});
  }, [prefs.theme]);
  useEffect(() => {
    if (!inNativeApp) return;
    void nativeRequest("device.brightness", { value: prefs.brightness }).catch(
      () => {},
    );
  }, [prefs.brightness]);
  useEffect(() => {
    const intent = (event: Event) => {
      const value = (
        event as CustomEvent<{
          screen: Screen;
          number?: string;
          body?: string;
          theme?: "light" | "dark";
        }>
      ).detail;
      if (
        !value ||
        ![
          "home",
          "phone",
          "messages",
          "contacts",
          "calendar",
          "clock",
          "media",
          "browser",
          "gallery",
          "calculator",
          "notes",
          "tasks",
          "workbench",
          "news",
          "culture",
          "files",
          "google",
          "monitor",
          "settings",
          "rifki",
          "store",
          "apps",
          "search",
        ].includes(value.screen)
      )
        return;
      if (value.theme === "light" || value.theme === "dark")
        update({ theme: value.theme });
      if (value.screen === "phone") setDial(value.number || "");
      if (value.screen === "messages" && (value.number || value.body))
        update({
          messageDraft: { number: value.number || "", body: value.body || "" },
        });
      go(value.screen); // Incoming intents populate drafts only, never invoke call/SMS send.
    };
    window.addEventListener("oguz-native-intent", intent);
    // Register before acknowledging readiness; a cold-start intent must only populate a draft, never disappear or send.
    if (inNativeApp) void nativeRequest("ui.ready").catch(() => {});
    return () => window.removeEventListener("oguz-native-intent", intent);
  }, [go, update]);
  const pageProps = { prefs, update, go, toast };
  const stages = [
    { id: "home", label: "Ana ekran" },
    { id: "rifki", label: "Rıfkı" },
    { id: "workbench", label: "Atölye" },
    { id: "settings", label: "Sana göre" },
  ] as const;
  return (
    <main
      className={`lab theme-${prefs.theme} accent-${prefs.accent} ${prefs.lowPower ? "low-power" : ""} ${prefs.reducedMotion ? "reduced-motion" : ""}`}
    >
      <header className="lab-header">
        <a
          href="#/home"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            go("home");
          }}
          aria-label="OğuzDows Mobile ana ekran"
        >
          <Nazar size={37} />
          <span>
            oğuz<span className="brand-dows">dows</span>
            <small>M O B I L E</small>
          </span>
        </a>
        <nav className="lab-nav" aria-label="Önizleme ekranları">
          {stages.map((s, i) => (
            <button
              key={s.id}
              className={screen === s.id ? "active" : ""}
              onClick={() => go(s.id)}
            >
              <small>0{i + 1}</small>
              {s.label}
            </button>
          ))}
        </nav>
        <div className="lab-header-actions">
          <span className="preview-status">
            <i /> Etkileşimli tasarım
          </span>
          <button
            className="icon-button lab-theme-toggle"
            aria-label={
              prefs.theme === "light"
                ? "Koyu tasarıma geç"
                : "Açık tasarıma geç"
            }
            onClick={() =>
              update({ theme: prefs.theme === "light" ? "dark" : "light" })
            }
          >
            <Icon name={prefs.theme === "light" ? "Moon" : "Sun"} size={20} />
          </button>
        </div>
      </header>
      <section
        className="design-stage"
        aria-label="OğuzDows Mobile tasarım laboratuvarı"
      >
        <aside className="story-column">
          <div className="edition">
            <span /> KÖKLERİ BURADA. GELECEĞİ CEBİNDE.
          </div>
          <h1>
            Cebinde,
            <br />
            senden bir
            <br />
            <span>dünya.</span>
            <i>✳</i>
          </h1>
          <p className="story-description">
            Bildiğin OğuzDows ruhu.
            <br />
            Şimdi daha kişisel, daha dokunulur
            <br />
            ve her zaman senin yanında.
          </p>
          <div className="story-tags">
            <span>
              <Icon name="ShieldCheck" size={13} /> Seçim sende
            </span>
            <span>
              <Icon name="Leaf" size={13} /> Hafif düşünür
            </span>
          </div>
          <div className="wallpaper-selector">
            <div className="section-line">
              <span>BİR MANZARA SEÇ</span>
              <Icon name="Image" size={15} />
            </div>
            <div className="wallpaper-swatches">
              {Object.entries(WALLPAPER_NAMES).map(([id, name]) => (
                <button
                  key={id}
                  className={prefs.wallpaper === id ? "chosen" : ""}
                  onClick={() => update({ wallpaper: id })}
                  aria-label={`${name} duvar kâğıdını uygula`}
                  aria-pressed={prefs.wallpaper === id}
                >
                  <img src={`/assets/${id}.webp`} alt="" />
                  {prefs.wallpaper === id && (
                    <span>
                      <Icon name="Check" size={12} />
                    </span>
                  )}
                </button>
              ))}
            </div>
            <p>
              {WALLPAPER_NAMES[prefs.wallpaper]}{" "}
              <span>OğuzDows koleksiyonu</span>
            </p>
          </div>
          <button
            className="light-profile-card"
            onClick={() => update({ lowPower: !prefs.lowPower })}
            aria-pressed={prefs.lowPower}
          >
            <span className="leaf-orbit">
              <Icon name="Leaf" size={21} />
            </span>
            <span>
              <strong>
                {prefs.lowPower ? "Hafiflik açık." : "Az yük. Çok hayat."}
              </strong>
              <small>
                {prefs.lowPower
                  ? "Efektler sadeleştirildi."
                  : "Hafif görsel profili dene."}
              </small>
            </span>
            <Icon name={prefs.lowPower ? "Check" : "ArrowUpRight"} size={18} />
          </button>
          <div className="design-note">
            <span>01 / BİR ARAYÜZDEN FAZLASI</span>
            <p>
              Türkçe karakteri, açık kaynak yaklaşımı
              <br />
              ve küçük detayların büyük farkı.
            </p>
          </div>
        </aside>
        <div className="device-column">
          <div className="phone-top-label">
            <span>OĞUZDOWS MOBILE</span>
            <span>01 — TASARIM ÖNİZLEMESİ</span>
          </div>
          <div className="phone-frame">
            <div
              className={`phone-screen ${screen === "home" ? "home-screen" : "app-screen"} ${prefs.layout === "compact" ? "compact" : ""}`}
              data-theme={prefs.theme}
              style={
                {
                  "--wallpaper": `url('/assets/${prefs.wallpaper}.webp')`,
                } as CSSProperties
              }
              onTouchStart={(e) => {
                if (e.touches.length === 1)
                  gestureStart(
                    e.changedTouches[0].clientX,
                    e.changedTouches[0].clientY,
                    e.target,
                    e.currentTarget,
                  );
                else touch.current = null;
              }}
              onTouchEnd={(e) => {
                if (!e.touches.length && e.changedTouches.length)
                  gestureEnd(
                    e.changedTouches[0].clientX,
                    e.changedTouches[0].clientY,
                    e.currentTarget,
                  );
              }}
              onTouchCancel={() => {
                touch.current = null;
              }}
              onPointerDown={(e) => {
                if (e.pointerType === "mouse")
                  gestureStart(e.clientX, e.clientY, e.target, e.currentTarget);
              }}
              onPointerUp={(e) => {
                if (e.pointerType === "mouse")
                  gestureEnd(e.clientX, e.clientY, e.currentTarget);
              }}
              onPointerCancel={() => {
                touch.current = null;
              }}
              onClickCapture={(e) => {
                if (
                  Date.now() < ignoreClickUntil.current &&
                  e.target instanceof Element &&
                  e.target.closest(".status-bar,.home-content")
                ) {
                  e.preventDefault();
                  e.stopPropagation();
                }
              }}
            >
              <h1 className="visually-hidden">
                {inNativeApp ? "OğuzDows Mobile" : "OğuzDows Mobile önizlemesi"}
              </h1>
              <div className="camera-hole" aria-hidden="true" />
              <span className="mobile-preview-label">
                {inNativeApp ? "YEREL TEST APK" : "ÖNİZLEME"}
              </span>
              <div className="status-bar">
                <button
                  aria-label="Denetim merkezini aç"
                  className="status-time"
                  onClick={() => setOverlay("quick")}
                >
                  {inNativeApp ? nativeTime : "09:41"}
                  <Icon name={prefs.focus ? "Moon" : "Bell"} size={11} />
                </button>
                <div className="status-right">
                  <button
                    className="status-radios"
                    aria-label="Bağlantılar ve denetim merkezi"
                    onClick={() => setOverlay("quick")}
                  >
                    <Icon
                      name={
                        inNativeApp
                          ? "Smartphone"
                          : prefs.airplane
                            ? "Plane"
                            : "SignalHigh"
                      }
                      size={15}
                    />
                    {!inNativeApp && prefs.wifi && !prefs.airplane && (
                      <Icon name="Wifi" size={15} />
                    )}
                    <Icon name="ChevronDown" size={10} />
                  </button>
                  <button
                    className="nazar-power"
                    aria-label="Nazar boncuğu güç menüsü"
                    onClick={() => setOverlay("power")}
                  >
                    <Nazar size={20} power />
                    <span>
                      {inNativeApp ? (nativeStatus?.battery ?? "—") : 86}
                    </span>
                  </button>
                </div>
              </div>
              {storageError && (
                <button
                  className="storage-error"
                  onClick={() => setOverlay("storage")}
                >
                  <Icon name="CircleHelp" size={13} /> Yerel kayıt
                  kullanılamıyor · ayrıntılar
                </button>
              )}
              <div
                className={`phone-content ${screen === "rifki" ? "chat-content" : ""}`}
              >
                <div key={screen} className="page-transition">
                  {screen === "home" && (
                    <div className="home-content">
                      <div className="home-greeting">
                        <span>MERHABA, GÜZEL BİR GÜN.</span>
                        {!inNativeApp && (
                          <button
                            className="weather-pill"
                            onClick={() =>
                              toast(
                                "22° / İstanbul, yalnız tasarım için örnek hava durumudur. Konum veya hava servisi bağlı değil.",
                              )
                            }
                            aria-label="İstanbul 22 derece, örnek hava durumu"
                          >
                            <Icon name="Sun" size={16} />
                            <span>22°</span>
                          </button>
                        )}
                      </div>
                      <div className="home-clock">
                        <h2>
                          {inNativeApp ? (
                            nativeTime
                          ) : (
                            <>
                              09<span>:</span>41
                            </>
                          )}
                        </h2>
                        <p>
                          {inNativeApp ? (
                            <>
                              {now.toLocaleDateString("tr-TR", {
                                weekday: "long",
                                day: "numeric",
                                month: "long",
                              })}
                              <span>Yerel saat</span>
                            </>
                          ) : (
                            <>
                              Salı, 17 Kasım <span>İstanbul</span>
                            </>
                          )}
                        </p>
                      </div>
                      <button
                        className="home-rifki"
                        onClick={() => go("rifki")}
                      >
                        <div>
                          <span className="eyebrow">
                            <span /> RIFKI YANINDA
                          </span>
                          <h3>Bir fikrin mi var?</h3>
                          <p>Beraber bir şeyler yapalım.</p>
                          <span className="rifki-cta">
                            Rıfkı’ya sor <Icon name="ArrowUpRight" size={16} />
                          </span>
                        </div>
                        <img
                          src="/assets/rifki.webp"
                          alt="Rıfkı, OğuzDows’un kedi rehberi"
                        />
                      </button>
                      <div className="home-section-label">
                        <span>SENİN ALANIN</span>
                        <button
                          aria-label="Tüm uygulamaları aç"
                          onClick={() => go("apps")}
                        >
                          <Icon name="Grip" size={18} />
                        </button>
                      </div>
                      <div className="home-apps" key={homePage}>
                        {apps
                          .slice(homePage * 8, (homePage + 1) * 8)
                          .map((app) => (
                            <button
                              className="app-tile"
                              key={app.id}
                              onClick={() => go(app.id)}
                            >
                              <AppBadge icon={app.icon} color={app.color} />
                              <span>{app.name}</span>
                            </button>
                          ))}
                      </div>
                      <button
                        className="home-search"
                        aria-label="Cihazında ara"
                        onClick={() => go("search")}
                      >
                        <Icon name="Search" size={17} />
                        <span>Cihazında bir şey bul…</span>
                        <span className="search-shortcut">⌕</span>
                      </button>
                      <div
                        className="home-pagination"
                        aria-label="Ana ekran sayfaları"
                      >
                        {Array.from({ length: homePageCount }, (_, index) => (
                          <button
                            key={index}
                            aria-label={`Ana ekran sayfası ${index + 1}`}
                            aria-pressed={homePage === index}
                            className={homePage === index ? "active" : ""}
                            onClick={() => setHomePage(index)}
                          >
                            <i />
                          </button>
                        ))}
                      </div>
                      <div className="home-dock">
                        <button
                          className="dock-item call"
                          aria-label="Telefon seçenekleri"
                          onClick={() => go("phone")}
                        >
                          <Icon name="Phone" size={24} />
                        </button>
                        <button
                          className="dock-item message"
                          aria-label="Mesajlaşma seçenekleri"
                          onClick={() => go("messages")}
                        >
                          <Icon name="MessageCircle" size={24} />
                        </button>
                        <button
                          className="dock-item browser"
                          aria-label="Tarayıcıyı aç"
                          onClick={() => go("browser")}
                        >
                          <Icon name="Globe2" size={24} />
                        </button>
                        <button
                          className="dock-item camera"
                          aria-label="Fotoğraf seç veya sistem kamerasını kullan"
                          onClick={() => go("gallery")}
                        >
                          <Icon name="Camera" size={24} />
                        </button>
                      </div>
                    </div>
                  )}
                  {screen === "apps" && <Apps {...pageProps} />}
                  {screen === "rifki" && (
                    <Rifki
                      onBack={() => go("home")}
                      onAction={assistantAction}
                      seed={seed}
                      onSeedUsed={seedUsed}
                    />
                  )}
                  {screen === "store" && (
                    <Store
                      {...pageProps}
                      key={`${storeTab}:${storeSelected}`}
                      initialTab={storeTab}
                      initialSelected={storeSelected}
                    />
                  )}
                  {screen === "workbench" && (
                    <Workbench {...pageProps} key={tool} initialTool={tool} />
                  )}
                  {screen === "news" && <News {...pageProps} />}
                  {screen === "google" && <Google {...pageProps} />}
                  {screen === "culture" && <Culture {...pageProps} />}
                  {screen === "files" && <Files {...pageProps} />}
                  {screen === "monitor" && <Monitor {...pageProps} />}
                  {toolShortcuts[screen] && (
                    <Workbench
                      {...pageProps}
                      key={screen}
                      initialTool={toolShortcuts[screen]}
                    />
                  )}
                  {everydayScreens.includes(screen) && (
                    <Suspense
                      fallback={
                        <div className="page-loading" role="status">
                          <Icon name="Sparkles" /> Açılıyor…
                        </div>
                      }
                    >
                      <Everyday
                        {...pageProps}
                        screen={screen}
                        number={dial}
                        onNumber={setDial}
                        onCall={openCall}
                        onCompose={openCompose}
                        onTool={openTool}
                        onCatalog={openCatalog}
                        onControls={() => setOverlay("quick")}
                      />
                    </Suspense>
                  )}
                  {screen === "settings" && (
                    <Settings
                      {...pageProps}
                      onAbout={() => setOverlay("about")}
                      onReset={() => setOverlay("reset")}
                    />
                  )}
                </div>
              </div>
              {screen !== "home" && screen !== "rifki" && (
                <nav className="phone-nav" aria-label="Mobil gezinme">
                  {[
                    { id: "home", icon: "Home", name: "Ana ekran" },
                    { id: "store", icon: "ShoppingBag", name: "Mağaza" },
                    { id: "rifki", icon: "Sparkles", name: "Rıfkı" },
                    { id: "workbench", icon: "Shapes", name: "Atölye" },
                    { id: "settings", icon: "Settings2", name: "Ayarlar" },
                  ].map((n) => (
                    <button
                      key={n.id}
                      aria-label={n.name}
                      className={screen === n.id ? "active" : ""}
                      onClick={() => go(n.id as Screen)}
                    >
                      {n.id === "rifki" ? (
                        <img src="/assets/rifki.webp" alt="" />
                      ) : (
                        <Icon name={n.icon} size={20} />
                      )}
                      <span>{n.name}</span>
                    </button>
                  ))}
                </nav>
              )}
              <div className="gesture-zone">
                <button
                  className="gesture-bar"
                  aria-label="Ana ekran hareket çubuğu"
                  onClick={() => go("home")}
                />
              </div>
              <div
                className="phone-dimmer"
                aria-hidden="true"
                style={{
                  opacity: inNativeApp ? 0 : (100 - prefs.brightness) / 120,
                }}
              />
              {toastText && (
                <div className="toast" role="status">
                  {toastText}
                </div>
              )}
              {overlay === "quick" && (
                <ControlCenter
                  {...pageProps}
                  onClose={closeDialog}
                  onPower={() => setOverlay("power")}
                />
              )}
              {overlay === "power" && (
                <Dialog title="Biraz nefes alalım." onClose={closeDialog}>
                  <div className="power-identity">
                    <Nazar size={76} power />
                    <h3>Gözümüz gibi.</h3>
                    <p>Nazar boncuğu, OğuzDows’un güç simgesi.</p>
                  </div>
                  <div className="power-actions">
                    <button
                      onClick={() => {
                        setOverlay("");
                        setLocked("lock");
                      }}
                    >
                      <Icon name="LockKeyhole" />
                      <span>
                        Kilit ekranını dene<small>Yalnız önizleme</small>
                      </span>
                      <Icon name="ChevronRight" size={17} />
                    </button>
                    <button
                      onClick={() => {
                        go("home");
                        toast(
                          "Önizleme ana ekrana döndü. Gerçek cihaz yeniden başlatılmadı.",
                        );
                      }}
                    >
                      <Icon name="Radio" />
                      <span>
                        Önizlemeyi yeniden başlat
                        <small>Notların ve tercihlerin korunur</small>
                      </span>
                      <Icon name="ChevronRight" size={17} />
                    </button>
                    <button
                      onClick={() => {
                        setOverlay("");
                        setLocked("off");
                      }}
                    >
                      <Nazar size={23} power />
                      <span>
                        Önizleme ekranını kapat
                        <small>Gerçek cihazı kapatmaz</small>
                      </span>
                      <Icon name="ChevronRight" size={17} />
                    </button>
                  </div>
                  <NativePower />
                </Dialog>
              )}
              {overlay === "about" && (
                <Dialog title="OğuzDows Mobile" onClose={closeDialog}>
                  <div className="about-identity">
                    <Nazar size={54} />
                    <h3>
                      Ruhu tanıdık.
                      <br />
                      Dünyası yeni.
                    </h3>
                    <p>
                      {inNativeApp
                        ? "Yerel Telefon / SMS / Mağaza test APK’sı · 0.2.0"
                        : "Etkileşimli tasarım önizlemesi · 0.1.0"}
                    </p>
                  </div>
                  <Notice icon="Smartphone">
                    {inNativeApp
                      ? "Bu APK, paketlenmiş çevrimdışı arayüzü yerel Telefon/SMS ve imzalı katalog servislerine bağlar. Cihaz ROM’u/ISO’su değildir. Fiziksel SIM/operatör, GMS, MMS/RCS ve tüm uygulama uyumluluğu doğrulanmış değildir."
                      : "Bu bir ROM, APK çalıştırıcısı, donanım emülatörü veya yüklenebilir işletim sistemi değildir. Gerçek cihaz desteği doğrulanmadı."}
                  </Notice>
                  <dl className="about-list">
                    <div>
                      <dt>Hedef temel</dt>
                      <dd>Android / AOSP, cihaz özelinde</dd>
                    </div>
                    <div>
                      <dt>Ürün kimliği</dt>
                      <dd>OğuzDows Mobile</dd>
                    </div>
                    <div>
                      <dt>Rıfkı</dt>
                      <dd>Yerel rehber; model isteğe bağlı</dd>
                    </div>
                    <div>
                      <dt>Google</dt>
                      <dd>Web hazır; GMS lisans/sertifika koşullu</dd>
                    </div>
                    <div>
                      <dt>APK</dt>
                      <dd>
                        {inNativeApp
                          ? "Özel kopya incelemesi + onaylı sistem yükleyicisi"
                          : "Özet/başlık inceleme; tarayıcıda kurulum yok"}
                      </dd>
                    </div>
                    <div>
                      <dt>Kalıcı kayıt</dt>
                      <dd>
                        {inNativeApp
                          ? "Uygulama özel alanı / sistem SMS sağlayıcısı; şifreli kasa değil"
                          : "Bu tarayıcıda; şifreli değil"}
                      </dd>
                    </div>
                  </dl>
                  <p className="fine-print">
                    Platformun teknik kimliği, üçüncü taraf lisansları, güvenlik
                    uyarıları ve izin ekranları gizlenmez. Masaüstü/Pi yayınları
                    ve sürüm numaraları değiştirilmedi.
                  </p>
                  <p className="fine-print">
                    Mağaza marka simgeleri: Simple Icons 15.22.0, çoğu CC0;
                    F-Droid: F-Droid artwork / Simple Icons contributors, zemin
                    ve sunum değişikliğiyle CC BY-SA 3.0.{" "}
                    <a
                      href="/assets/apps/manifest.json"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Köken ve lisans manifesti ↗
                    </a>
                    {" · "}
                    <a
                      href="/assets/apps/LICENSE.txt"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      CC0 metni ↗
                    </a>
                    {" · "}
                    <a
                      href="https://creativecommons.org/licenses/by-sa/3.0/"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      F-Droid lisansı ↗
                    </a>
                    . İlgili marka hakları saklıdır; ortaklık iddia edilmez.
                  </p>
                </Dialog>
              )}
              {(overlay === "reset" || overlay === "storage") && (
                <Dialog
                  title={
                    overlay === "reset"
                      ? "Önizleme verilerini temizle?"
                      : "Yerel kayıt bilgisi"
                  }
                  onClose={closeDialog}
                >
                  {overlay === "storage" && <Notice>{storageError}</Notice>}
                  <p className="dialog-copy">
                    Bu işlem yalnız bu önizlemenin kişilerini, SMS taslağını,
                    takvim planlarını, sayaçlarını, notlarını, görevlerini,
                    listelerini ve tercihlerini bu tarayıcıdan siler. Diğer
                    dosyalara veya cihaz ayarlarına dokunmaz. Geri alınamaz.
                  </p>
                  <button
                    className="primary-button danger-fill"
                    onClick={() => {
                      try {
                        localStorage.removeItem(STORAGE_KEY);
                        setStorageError("");
                        setPrefs(initialState() as Preferences);
                        setOverlay("");
                        toast("Yalnız önizlemenin yerel kaydı temizlendi.");
                      } catch {
                        toast(
                          "Tarayıcı depolamaya izin vermedi. Veri silinemedi.",
                        );
                      }
                    }}
                  >
                    Evet, yalnız önizleme verilerini temizle
                  </button>
                  <button className="secondary-button" onClick={closeDialog}>
                    Vazgeç
                  </button>
                </Dialog>
              )}
              {locked && (
                <div
                  className={`lock-screen ${locked === "off" ? "powered-off" : ""}`}
                >
                  <Nazar size={64} power />
                  {locked === "lock" ? (
                    <>
                      <h2>{inNativeApp ? nativeTime : "09:41"}</h2>
                      <p>Salı, 17 Kasım</p>
                      <span className="lock-hint">
                        <Icon name="LockKeyhole" size={16} /> Tasarım kilidi ·
                        güvenlik kilidi değildir
                      </span>
                    </>
                  ) : (
                    <>
                      <h3>Küçük bir mola.</h3>
                      <p>Yalnız önizleme ekranı kapalı.</p>
                    </>
                  )}
                  <button
                    onClick={() => setLocked("")}
                    className="unlock-button"
                  >
                    <Icon name="ArrowUpRight" size={20} /> Önizlemeyi aç
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="device-caption">
            <span>
              <i /> ÜSTTEN KAYDIR. DENETİM SENDE.
            </span>
            <button
              onClick={() => setOverlay("about")}
              aria-label="Önizleme ve teknik sınırlar"
            >
              <Icon name="CircleHelp" size={15} />
            </button>
          </div>
        </div>
        <aside className="companion-column">
          <div className="companion-overline">
            <span>İYİ Kİ BURADASIN.</span>
            <Icon name="Sparkles" size={16} />
          </div>
          <div className="companion-card">
            <div className="companion-cat">
              <span className="cat-halo" />
              <img
                src="/assets/rifki.webp"
                alt="Bir gözü mavi, bir gözü kehribar olan Rıfkı"
              />
              <span className="hello-bubble">
                Merhaba! <span>✦</span>
              </span>
            </div>
            <div className="companion-card-body">
              <span className="eyebrow">TANIŞTIRALIM, RIFKI.</span>
              <h2>
                Bir asistandan
                <br />
                biraz daha fazlası.
              </h2>
              <p>
                Tanıdık bir yüz. Küçük bir yardım.
                <br />
                Günün nasıl geçiyorsa, yanında.
              </p>
              <button className="primary-button" onClick={() => go("rifki")}>
                Birlikte düşünelim <Icon name="ArrowUpRight" size={17} />
              </button>
              <span className="local-label">
                <i /> Yerel rehber hazır · model isteğe bağlı
              </span>
            </div>
          </div>
          <div className="try-actions">
            <span className="section-caption">BİR ŞEYLER DENE</span>
            <button onClick={() => ask("Bugünümü planla")}>
              <span className="try-icon">
                <Icon name="ListTodo" size={18} />
              </span>
              <span>Bugünümü planla</span>
              <Icon name="ArrowUpRight" size={15} />
            </button>
            <button onClick={() => ask("Koyu görünüme geç")}>
              <span className="try-icon">
                <Icon name="Palette" size={18} />
              </span>
              <span>Biraz değişiklik yapalım</span>
              <Icon name="ArrowUpRight" size={15} />
            </button>
          </div>
          <div className="ecosystem-card">
            <span className="ecosystem-icons">
              <AppBadge icon="Globe2" color="white" small />
              <AppBadge icon="Code2" color="mint" small />
            </span>
            <h3>Alışkanlıkların yanında.</h3>
            <p>
              Google seçenekleri. APK özgürlüğü.
              <br />
              Kaynağı ve onayı hep görünür.
            </p>
            <div>
              <button onClick={() => go("google")}>
                Google <Icon name="ArrowUpRight" size={13} />
              </button>
              <span>·</span>
              <button onClick={openApk}>
                APK incele <Icon name="ArrowUpRight" size={13} />
              </button>
            </div>
          </div>
        </aside>
      </section>
      <footer className="lab-footer">
        <span>
          OĞUZDOWS MOBILE <i>—</i> AYNI RUH. YENİ BİR DÜNYA.
        </span>
        <p>
          Tarayıcı tasarımıdır, ROM değildir. Durum göstergeleri örnektir.{" "}
          <button onClick={() => setOverlay("about")}>
            Tasarım sınırları <Icon name="ArrowUpRight" size={12} />
          </button>
        </p>
        <span>
          ÖZGÜRLÜK, CEBİNE YAKIŞTI. <Nazar size={16} />
        </span>
      </footer>
    </main>
  );
}
