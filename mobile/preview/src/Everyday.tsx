import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from "react";
import type { PageProps } from "./Screens";
import {
  apps,
  catalog,
  WALLPAPER_NAMES,
  type Contact,
  type Screen,
} from "./data";
import {
  browserHref,
  calculate,
  normalize,
  phoneHref,
  phoneNumber,
  smsHref,
  TOOLS,
} from "./core.mjs";
import { AppBadge, Dialog, Icon, Notice, ScreenTitle } from "./ui";
import { inNativeApp } from "./native";
import { NativeMessages, NativePhone } from "./NativeCommunications";

export type Props = PageProps & {
  screen: Screen;
  number: string;
  onNumber: (value: string) => void;
  onCall: (value: string) => void;
  onCompose: (value: string) => void;
  onTool: (id: string) => void;
  onCatalog: (id: string) => void;
  onControls: () => void;
};
export default function Everyday(props: Props) {
  switch (props.screen) {
    case "phone":
      return <PhonePage {...props} />;
    case "messages":
      return <Messages {...props} />;
    case "contacts":
      return <Contacts {...props} />;
    case "calendar":
      return <Calendar {...props} />;
    case "clock":
      return <Clock {...props} />;
    case "media":
      return <Media {...props} />;
    case "browser":
      return <Browser {...props} />;
    case "gallery":
      return <Gallery {...props} />;
    case "search":
      return <Search {...props} />;
    default:
      return null;
  }
}
async function copyNumber(number: string, toast: Props["toast"]) {
  try {
    await navigator.clipboard.writeText(number);
    toast("Numara panoya kopyalandı.");
  } catch {
    toast(
      "Pano izni alınamadı. Numarayı giriş alanından seçip kopyalayabilirsin.",
    );
  }
}
function PhonePage({ number, onNumber, onCompose, prefs, go, toast }: Props) {
  const [tab, setTab] = useState("keypad");
  const [handoff, setHandoff] = useState(false);
  const target = phoneHref(number);
  const contact = prefs.contacts.find((c) => c.number === phoneNumber(number));
  return (
    <>
      <ScreenTitle
        title="Telefon"
        eyebrow="BİR SES KADAR YAKIN"
        onBack={() => go("home")}
        action={
          <button
            className="icon-button"
            aria-label="Kişileri aç"
            onClick={() => go("contacts")}
          >
            <Icon name="ContactRound" />
          </button>
        }
      />
      <div className="page-body communication-page">
        <div className="segmented">
          <button
            className={tab === "keypad" ? "active" : ""}
            onClick={() => setTab("keypad")}
          >
            Tuş takımı
          </button>
          <button
            className={tab === "contacts" ? "active" : ""}
            onClick={() => setTab("contacts")}
          >
            Kişilerim <span>{prefs.contacts.length}</span>
          </button>
        </div>
        {tab === "keypad" ? (
          <>
            <div className="dial-display">
              <span>{contact?.name || "Kimi aramak istersin?"}</span>
              <input
                type="tel"
                inputMode="tel"
                autoComplete="off"
                aria-label="Aranacak numara"
                placeholder="Numara yaz"
                maxLength={40}
                value={number}
                onChange={(e) => {
                  onNumber(e.target.value);
                  setHandoff(false);
                }}
              />
              <button
                className="icon-button"
                aria-label="Son rakamı sil"
                disabled={!number}
                onClick={() => {
                  onNumber(number.slice(0, -1));
                  setHandoff(false);
                }}
              >
                <Icon name="Delete" size={23} />
              </button>
            </div>
            <div className="dial-pad real-dial-pad">
              {"123456789*0#".split("").map((n, i) => (
                <button
                  key={n}
                  aria-label={`${n} tuşu`}
                  onClick={() => {
                    onNumber((number + n).slice(0, 40));
                    setHandoff(false);
                  }}
                >
                  <strong>{n}</strong>
                  <small>
                    {[
                      "",
                      "ABC",
                      "DEF",
                      "GHI",
                      "JKL",
                      "MNO",
                      "PQRS",
                      "TUV",
                      "WXYZ",
                      "",
                      "+",
                      "",
                    ][i] || "\u00a0"}
                  </small>
                </button>
              ))}
            </div>
            <div className="dial-actions">
              <button
                className="icon-button"
                aria-label="Artı ekle"
                onClick={() =>
                  onNumber(number.startsWith("+") ? number : `+${number}`)
                }
              >
                <Icon name="Plus" />
              </button>
              <a
                className={`dial-call ${!target ? "disabled" : ""}`}
                href={target || undefined}
                aria-label="Arama uygulamasında aç"
                role="link"
                tabIndex={target ? 0 : -1}
                aria-disabled={!target}
                onClick={() => {
                  if (target) setHandoff(true);
                }}
              >
                <Icon name="Phone" size={27} />
                <span>Ara</span>
              </a>
              <button
                className="icon-button"
                aria-label="Bu numaraya mesaj yaz"
                disabled={!target}
                onClick={() => onCompose(phoneNumber(number))}
              >
                <Icon name="MessageCircle" />
              </button>
            </div>
            <p className="handoff-caption">
              Sistem arama ekranı açılır; aramayı orada sen başlatırsın.
            </p>
            {!!number && !target && (
              <p className="error" role="alert">
                3–20 rakam ve başta + kullan. Servis kodları (* / #) bu
                önizlemeden aktarılmaz.
              </p>
            )}
            {handoff && (
              <p className="handoff-status" role="status">
                Arama uygulamasına geçiş istendi. Açılmadıysa bu cihazda tel:
                işleyicisi olmayabilir; numarayı kopyalayabilirsin. Arama
                bağlandı diye işaretlenmedi.
              </p>
            )}
            {target && (
              <button
                className="text-button copy-number"
                onClick={() => copyNumber(phoneNumber(number), toast)}
              >
                <Icon name="Copy" size={15} /> Numarayı kopyala
              </button>
            )}
          </>
        ) : (
          <div className="contact-quick-list">
            {prefs.contacts.length ? (
              prefs.contacts.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    onNumber(c.number);
                    setTab("keypad");
                  }}
                >
                  <span className="contact-avatar">
                    {c.name.slice(0, 1).toLocaleUpperCase("tr-TR")}
                  </span>
                  <span>
                    <strong>{c.name}</strong>
                    <small>{c.number}</small>
                  </span>
                  <Icon name="Phone" size={18} />
                </button>
              ))
            ) : (
              <Empty
                icon="ContactRound"
                title="İlk tanıdık yüzünü ekle."
                text="Kişiler uygulamasında kendi rehberini oluştur; burada da görünsün."
                action={
                  <button
                    className="secondary-button"
                    onClick={() => go("contacts")}
                  >
                    Kişilere git
                  </button>
                }
              />
            )}
          </div>
        )}
        <Notice icon="Smartphone">
          Bu web önizlemesinin modem/SIM erişimi yok. Telefon bağlantısı,
          destekleyen cihazın kendi uygulamasına devredilir; bilgisayarda
          telefon işleyicisi bulunmayabilir. Acil çağrı için cihazının gerçek
          Telefon uygulamasını kullan.
        </Notice>
      </div>
    </>
  );
}
function Messages({ prefs, update, go, toast }: Props) {
  const [handoff, setHandoff] = useState(false);
  const draft = prefs.messageDraft;
  const target = smsHref(draft.number, draft.body);
  const change = (next: Partial<typeof draft>) => {
    update({ messageDraft: { ...draft, ...next } });
    setHandoff(false);
  };
  return (
    <>
      <ScreenTitle
        title="Mesajlar"
        eyebrow="BİR MESAJLIK MESAFE"
        onBack={() => go("home")}
      />
      <div className="page-body communication-page">
        <div className="daily-intro">
          <span className="daily-orbit">
            <Icon name="MessageCircle" size={33} />
          </span>
          <h3>Aklındakini paylaş.</h3>
          <p>Bir taslak yaz. Göndermeye sen karar ver.</p>
        </div>
        <label className="field-label">
          Alıcı
          <input
            type="tel"
            inputMode="tel"
            aria-label="Mesaj alıcısı"
            autoComplete="off"
            placeholder="+90… veya yerel numara"
            maxLength={40}
            value={draft.number}
            onChange={(e) => change({ number: e.target.value })}
          />
        </label>
        {!!prefs.contacts.length && (
          <div className="recipient-chips" aria-label="Alıcı seç">
            {prefs.contacts.slice(0, 12).map((c) => (
              <button key={c.id} onClick={() => change({ number: c.number })}>
                {c.name}
              </button>
            ))}
          </div>
        )}
        <label className="field-label">
          Mesajın
          <textarea
            className="message-draft"
            aria-label="SMS taslağı"
            placeholder="Merhaba…"
            maxLength={2000}
            value={draft.body}
            onChange={(e) => change({ body: e.target.value })}
          />
        </label>
        <div className="section-line">
          <span>{draft.body.length} / 2000 KARAKTER</span>
          <span>TASLAK · GÖNDERİLMEDİ</span>
        </div>
        <a
          href={target || undefined}
          role="link"
          tabIndex={target ? 0 : -1}
          aria-disabled={!target}
          className={`primary-button ${!target ? "disabled" : ""}`}
          onClick={() => {
            if (target) setHandoff(true);
          }}
        >
          <Icon name="SendHorizontal" size={18} /> Sistem mesajlaşmasında aç
        </a>
        {handoff && (
          <p className="handoff-status" role="status">
            Sistem mesajlaşmasına geçiş istendi; mesaj gönderilmedi. Açılmazsa
            taslağı kopyalayarak kullanabilirsin.
          </p>
        )}
        <button
          className="secondary-button"
          disabled={!draft.body}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(draft.body);
              toast("Mesaj taslağı kopyalandı; gönderilmedi.");
            } catch {
              toast(
                "Pano izni yok. Taslağı metin alanından seçip kopyalayabilirsin.",
              );
            }
          }}
        >
          <Icon name="Copy" size={17} /> Taslağı kopyala
        </button>
        <Notice icon="LockKeyhole">
          Bu taslak yalnız bu tarayıcıda, şifrelenmeden saklanır. SMS/MMS
          okunmaz veya burada gönderilmez. Son alıcı, ücret/operatör ve gönderim
          onayı sistem uygulamasındadır; sms: desteği cihaza bağlıdır.
        </Notice>
      </div>
    </>
  );
}
function Contacts(props: Props) {
  const { prefs, update, go, onCall, onCompose } = props;
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Contact | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const visible = prefs.contacts
    .filter((c) =>
      normalize(`${c.name} ${c.number}`).includes(normalize(query)),
    )
    .sort(
      (a, b) =>
        Number(b.favorite) - Number(a.favorite) ||
        a.name.localeCompare(b.name, "tr"),
    );
  function save(e: FormEvent) {
    e.preventDefault();
    if (!editing || !editing.name.trim() || !phoneNumber(editing.number))
      return;
    const contact = {
      ...editing,
      name: editing.name.trim(),
      number: phoneNumber(editing.number),
    };
    update({
      contacts: prefs.contacts.some((c) => c.id === contact.id)
        ? prefs.contacts.map((c) => (c.id === contact.id ? contact : c))
        : [...prefs.contacts, contact].slice(0, 60),
    });
    setEditing(null);
  }
  return (
    <>
      <ScreenTitle
        title="Kişiler"
        eyebrow="NUMARALAR DEĞİL, İNSANLAR"
        onBack={() => go("home")}
        action={<span className="tiny-pill">{prefs.contacts.length} KİŞİ</span>}
      />
      <div className="page-body">
        <div className="search-field">
          <Icon name="Search" />
          <input
            aria-label="Kişilerde ara"
            placeholder="İsim veya numara bul…"
            maxLength={80}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <button
          className="primary-button"
          disabled={prefs.contacts.length >= 60}
          onClick={() => {
            setEditing({
              id: crypto.randomUUID(),
              name: "",
              number: "",
              favorite: false,
            });
            setConfirmDelete(false);
          }}
        >
          <Icon name="Plus" size={18} /> Kişi ekle
        </button>
        {!visible.length && (
          <Empty
            icon="ContactRound"
            title={query ? "Bu isim burada yok." : "Rehberin senden başlasın."}
            text={
              query
                ? "İsim veya numaranın bir bölümünü dene."
                : "Kişi ekle; telefon, mesajlar ve aramada aynı rehberi kullan."
            }
          />
        )}
        <div className="contacts-list">
          {visible.map((c) => (
            <article className="contact-card" key={c.id}>
              <span className="contact-avatar">
                {c.name.slice(0, 1).toLocaleUpperCase("tr-TR")}
              </span>
              <div>
                <h3>{c.name}</h3>
                <p>{c.number}</p>
                <div className="contact-actions">
                  <button
                    onClick={() => onCall(c.number)}
                    aria-label={`${c.name} için numara çevir`}
                  >
                    <Icon name="Phone" size={16} /> Ara
                  </button>
                  <button
                    onClick={() => onCompose(c.number)}
                    aria-label={`${c.name} için mesaj yaz`}
                  >
                    <Icon name="MessageCircle" size={16} /> Mesaj
                  </button>
                </div>
              </div>
              <div className="contact-side">
                <button
                  className={`icon-button ${c.favorite ? "selected" : ""}`}
                  aria-label={`${c.name} ${c.favorite ? "favorilerden çıkar" : "favorilere ekle"}`}
                  aria-pressed={c.favorite}
                  onClick={() =>
                    update({
                      contacts: prefs.contacts.map((x) =>
                        x.id === c.id ? { ...x, favorite: !x.favorite } : x,
                      ),
                    })
                  }
                >
                  <Icon name="Heart" size={17} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`${c.name} kişisini düzenle`}
                  onClick={() => {
                    setEditing({ ...c });
                    setConfirmDelete(false);
                  }}
                >
                  <Icon name="NotebookPen" size={17} />
                </button>
              </div>
            </article>
          ))}
        </div>
        <Notice icon="LockKeyhole">
          En çok 60 kişi, yalnız bu tarayıcıda ve şifrelenmeden. Cihazının
          sistem rehberi okunmaz; rehber eşitlemesi veya kişi yüklemesi
          yapılmaz.
        </Notice>
      </div>
      {editing && (
        <Dialog
          title={
            prefs.contacts.some((c) => c.id === editing.id)
              ? "Kişiyi düzenle"
              : "Yeni kişi"
          }
          onClose={() => setEditing(null)}
        >
          <form className="contact-form" onSubmit={save}>
            <label className="field-label">
              Ad
              <input
                aria-label="Kişi adı"
                required
                maxLength={60}
                autoComplete="off"
                value={editing.name}
                onChange={(e) =>
                  setEditing({ ...editing, name: e.target.value })
                }
              />
            </label>
            <label className="field-label">
              Telefon
              <input
                aria-label="Kişinin telefon numarası"
                type="tel"
                inputMode="tel"
                required
                maxLength={40}
                value={editing.number}
                onChange={(e) =>
                  setEditing({ ...editing, number: e.target.value })
                }
              />
            </label>
            <button
              className="primary-button"
              disabled={!editing.name.trim() || !phoneNumber(editing.number)}
            >
              <Icon name="Check" size={18} /> Kişiyi kaydet
            </button>
          </form>
          {prefs.contacts.some((c) => c.id === editing.id) &&
            (confirmDelete ? (
              <div className="delete-confirm">
                <p>Bu kişi yalnız önizleme rehberinden silinecek.</p>
                <button
                  className="secondary-button danger"
                  onClick={() => {
                    update({
                      contacts: prefs.contacts.filter(
                        (c) => c.id !== editing.id,
                      ),
                    });
                    setEditing(null);
                  }}
                >
                  Evet, kişiyi sil
                </button>
                <button
                  className="text-button"
                  onClick={() => setConfirmDelete(false)}
                >
                  Vazgeç
                </button>
              </div>
            ) : (
              <button
                className="text-button danger"
                onClick={() => setConfirmDelete(true)}
              >
                <Icon name="Trash2" size={16} /> Kişiyi sil
              </button>
            ))}
        </Dialog>
      )}
    </>
  );
}
function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function Calendar({ prefs, update, go }: Props) {
  const [today] = useState(() => new Date());
  const [view, setView] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1),
  );
  const [selected, setSelected] = useState(() => dateKey(today));
  const [title, setTitle] = useState("");
  const first = (view.getDay() + 6) % 7,
    days = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
  const entries = prefs.events.filter((event) => event.date === selected);
  const dateLabel = (date: Date) =>
    new Intl.DateTimeFormat("tr-TR", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(date);
  function move(delta: number) {
    const next = new Date(view.getFullYear(), view.getMonth() + delta, 1);
    if (next.getFullYear() >= 2000 && next.getFullYear() <= 2100) setView(next);
  }
  return (
    <>
      <ScreenTitle
        title="Takvim"
        eyebrow="GÜNLERİNE BİRAZ YER AÇ"
        onBack={() => go("home")}
      />
      <div className="page-body calendar-page">
        <div className="calendar-month">
          <button
            className="icon-button"
            aria-label="Önceki ay"
            onClick={() => move(-1)}
            disabled={view.getFullYear() === 2000 && view.getMonth() === 0}
          >
            <Icon name="ChevronLeft" />
          </button>
          <h3>
            {new Intl.DateTimeFormat("tr-TR", {
              month: "long",
              year: "numeric",
            }).format(view)}
          </h3>
          <button
            className="icon-button"
            aria-label="Sonraki ay"
            onClick={() => move(1)}
            disabled={view.getFullYear() === 2100 && view.getMonth() === 11}
          >
            <Icon name="ChevronRight" />
          </button>
        </div>
        <div className="calendar-grid" role="group" aria-label="Ay takvimi">
          {["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pz"].map((day, i) => (
            <span className="calendar-weekday" key={`w${i}`}>
              {day}
            </span>
          ))}
          {Array.from({ length: first }, (_, i) => (
            <span key={`empty${i}`} />
          ))}
          {Array.from({ length: days }, (_, i) => {
            const date = new Date(view.getFullYear(), view.getMonth(), i + 1),
              key = dateKey(date);
            return (
              <button
                key={key}
                aria-label={dateLabel(date)}
                aria-pressed={selected === key}
                className={`${key === selected ? "chosen" : ""} ${key === dateKey(today) ? "today" : ""}`}
                onClick={() => setSelected(key)}
              >
                <span>{i + 1}</span>
                {prefs.events.some((event) => event.date === key) && <i />}
              </button>
            );
          })}
        </div>
        <button
          className="text-button calendar-today"
          onClick={() => {
            setView(new Date(today.getFullYear(), today.getMonth(), 1));
            setSelected(dateKey(today));
          }}
        >
          Bugüne dön
        </button>
        <div className="section-line">
          <span>{dateLabel(new Date(`${selected}T12:00:00`))}</span>
          <span>{entries.length} PLAN</span>
        </div>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim() && prefs.events.length < 80) {
              update({
                events: [
                  ...prefs.events,
                  {
                    id: crypto.randomUUID(),
                    date: selected,
                    title: title.trim(),
                  },
                ],
              });
              setTitle("");
            }
          }}
        >
          <input
            aria-label="Yeni takvim planı"
            placeholder="Bu güne bir plan ekle…"
            maxLength={140}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <button
            className="primary-square"
            aria-label="Plan ekle"
            disabled={!title.trim() || prefs.events.length >= 80}
          >
            <Icon name="Plus" />
          </button>
        </form>
        {!entries.length && (
          <p className="empty-state">
            Bugün için boş bir sayfa. İstersen bir plan ekle.
          </p>
        )}
        <div className="agenda-list">
          {entries.map((event) => (
            <article key={event.id}>
              <span className="agenda-dot" />
              <p>{event.title}</p>
              <button
                className="icon-button"
                aria-label={`${event.title} planını sil`}
                onClick={() =>
                  update({
                    events: prefs.events.filter((x) => x.id !== event.id),
                  })
                }
              >
                <Icon name="X" size={17} />
              </button>
            </article>
          ))}
        </div>
        <Notice icon="CalendarDays">
          En çok 80 yerel plan; yeniden açtığında korunur. Sistem takvimine
          bağlanmaz, alarm veya arka plan bildirimi kurmaz.
        </Notice>
      </div>
    </>
  );
}
function duration(ms: number, tenths = false) {
  const n = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(n / 3600)).padStart(2, "0")}:${String(Math.floor(n / 60) % 60).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}${tenths ? `.${Math.floor((ms % 1000) / 100)}` : ""}`;
}
function Clock({ prefs, update, go, onTool }: Props) {
  const [tab, setTab] = useState("stopwatch"),
    [minutes, setMinutes] = useState("5"),
    [now, setNow] = useState(Date.now),
    [laps, setLaps] = useState<number[]>([]);
  const running = prefs.stopwatch.startedAt !== null;
  const elapsed = Math.min(
    86400000,
    prefs.stopwatch.elapsed +
      (running ? Math.max(0, now - prefs.stopwatch.startedAt!) : 0),
  );
  const remaining =
    prefs.timerEnd === null ? 0 : Math.max(0, prefs.timerEnd - now);
  const timerLive = remaining > 0;
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    const sync = () => {
      clearInterval(interval);
      setNow(Date.now());
      if (!document.hidden && (running || timerLive))
        interval = setInterval(() => setNow(Date.now()), running ? 100 : 500);
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", sync);
    };
  }, [running, prefs.timerEnd, timerLive]);
  return (
    <>
      <ScreenTitle
        title="Saat"
        eyebrow="BİR AN, BİR MOLA"
        onBack={() => go("home")}
      />
      <div className="page-body clock-page">
        <div className="segmented">
          <button
            className={tab === "stopwatch" ? "active" : ""}
            onClick={() => setTab("stopwatch")}
          >
            Kronometre
          </button>
          <button
            className={tab === "timer" ? "active" : ""}
            onClick={() => setTab("timer")}
          >
            Sayaç
          </button>
          <button onClick={() => onTool("clocks")}>Dünya</button>
        </div>
        <div
          className={`clock-face ${running && tab === "stopwatch" ? "is-running" : ""}`}
        >
          <span className="clock-ring" />
          <Icon name="Clock3" size={28} />
          <span className="eyebrow">
            {tab === "stopwatch"
              ? "ŞİMDİKİ AN"
              : prefs.timerEnd !== null && !remaining
                ? "SÜRE DOLDU"
                : "KENDİNE BİR MOLA"}
          </span>
          <output
            className="clock-digits"
            aria-label={
              tab === "stopwatch" ? "Kronometre süresi" : "Kalan süre"
            }
          >
            {tab === "stopwatch"
              ? duration(elapsed, true)
              : duration(remaining)}
          </output>
        </div>
        {tab === "stopwatch" ? (
          <>
            <div className="clock-actions">
              <button
                className="secondary-button"
                disabled={!elapsed && !running}
                onClick={() => {
                  update({ stopwatch: { elapsed: 0, startedAt: null } });
                  setLaps([]);
                }}
              >
                <Icon name="RotateCcw" size={17} /> Sıfırla
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  const time = Date.now();
                  setNow(time);
                  update({
                    stopwatch: running
                      ? {
                          elapsed: Math.min(
                            86400000,
                            prefs.stopwatch.elapsed +
                              Math.max(0, time - prefs.stopwatch.startedAt!),
                          ),
                          startedAt: null,
                        }
                      : { ...prefs.stopwatch, startedAt: time },
                  });
                }}
              >
                <Icon name={running ? "Pause" : "Play"} size={17} />
                {running ? "Duraklat" : elapsed ? "Sürdür" : "Başlat"}
              </button>
            </div>
            <button
              className="text-button lap-button"
              disabled={!running || laps.length >= 8}
              onClick={() => setLaps([elapsed, ...laps])}
            >
              Tur ekle
            </button>
            <div className="lap-list">
              {laps.map((lap, i) => (
                <div key={`${lap}-${i}`}>
                  <span>Tur {laps.length - i}</span>
                  <strong>{duration(lap, true)}</strong>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            <label className="field-label">
              Süre (dakika)
              <input
                type="number"
                min={1}
                max={180}
                aria-label="Sayaç süresi dakika"
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
                disabled={prefs.timerEnd !== null && remaining > 0}
              />
            </label>
            <div className="timer-presets">
              {[1, 5, 15, 25].map((n) => (
                <button
                  key={n}
                  disabled={prefs.timerEnd !== null && remaining > 0}
                  onClick={() => setMinutes(String(n))}
                >
                  {n} dk
                </button>
              ))}
            </div>
            <button
              className="primary-button"
              disabled={
                prefs.timerEnd === null &&
                (!/^\d{1,3}$/.test(minutes) ||
                  Number(minutes) < 1 ||
                  Number(minutes) > 180)
              }
              onClick={() => {
                const time = Date.now();
                setNow(time);
                update({
                  timerEnd:
                    prefs.timerEnd === null
                      ? time + Number(minutes) * 60000
                      : null,
                });
              }}
            >
              <Icon
                name={prefs.timerEnd === null ? "Play" : "Square"}
                size={17}
              />
              {prefs.timerEnd === null
                ? "Sayacı başlat"
                : remaining
                  ? "Sayacı iptal et"
                  : "Sayacı sıfırla"}
            </button>
          </>
        )}
        <Notice icon="Clock3">
          Başlangıç zamanı bu tarayıcıda saklanır; başka ekrana gidip
          dönebilirsin. Bu bir sistem alarmı değildir: arka plan bildirimi/ses
          garantisi yoktur. Tur listesi yalnız bu açık ekranda kalır; kronometre
          24 saatle sınırlıdır.
        </Notice>
      </div>
    </>
  );
}
function Media({ prefs, update, go, onControls, toast }: Props) {
  const [track, setTrack] = useState<{ name: string; url: string } | null>(
      null,
    ),
    [playing, setPlaying] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(
    () => () => {
      if (track) URL.revokeObjectURL(track.url);
    },
    [track],
  );
  useEffect(() => {
    if (audio.current) {
      audio.current.volume = prefs.volume / 100;
      audio.current.muted = prefs.muted;
    }
  }, [prefs.volume, prefs.muted, track]);
  function select(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (
      file.size > 32 * 1024 * 1024 ||
      !file.size ||
      !(
        file.type.startsWith("audio/") ||
        /\.(mp3|m4a|ogg|wav|flac|aac|webm)$/i.test(file.name)
      )
    ) {
      toast("En çok 32 MiB bir ses dosyası seç.");
      e.target.value = "";
      return;
    }
    setTrack({ name: file.name.slice(0, 160), url: URL.createObjectURL(file) });
    setPlaying(false);
    e.target.value = "";
  }
  return (
    <>
      <ScreenTitle
        title="Müzik"
        eyebrow="KENDİ RİTMİNDE"
        onBack={() => go("home")}
        action={
          <button
            className="icon-button"
            aria-label="Ses denetimlerini aç"
            onClick={onControls}
          >
            <Icon name="SlidersHorizontal" />
          </button>
        }
      />
      <div className="page-body media-page">
        <div className={`record-art ${playing ? "playing" : ""}`}>
          <div className="record-disc">
            <div>
              <Icon name="Music2" size={42} />
            </div>
          </div>
          <span className="record-spark">✳</span>
        </div>
        <h3>{track?.name || "Günün bir ritmi olsun."}</h3>
        <p>
          {track
            ? "Yalnız bu cihazda seçtiğin dosya"
            : "Kendi müziğini seç, sesi sana göre ayarla."}
        </p>
        {track && (
          <audio
            ref={audio}
            controls
            src={track.url}
            preload="metadata"
            aria-label="Seçilen müzik"
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onError={() => {
              setPlaying(false);
              toast(
                "Bu ses biçimi tarayıcıda çözülemedi. Başka bir dosya dene.",
              );
            }}
            onVolumeChange={() => {
              const el = audio.current;
              if (
                el &&
                (Math.round(el.volume * 100) !== prefs.volume ||
                  el.muted !== prefs.muted)
              )
                update({
                  volume: Math.round(el.volume * 100),
                  muted: el.muted,
                });
            }}
          />
        )}
        <label className="file-pick compact-pick">
          <Icon name="Music2" size={25} />
          <strong>{track ? "Başka müzik seç" : "Bir ses dosyası seç"}</strong>
          <span>MP3, OGG, WAV… · en çok 32 MiB</span>
          <input
            type="file"
            aria-label="Müzik dosyası seç"
            accept="audio/*,.mp3,.m4a,.ogg,.wav,.flac,.aac"
            onChange={select}
          />
        </label>
        <button className="secondary-button" onClick={onControls}>
          <Icon name={prefs.muted ? "VolumeX" : "Volume2"} size={18} />
          {prefs.muted ? "Sessiz" : `Medya sesi · ${prefs.volume}%`}
          <Icon name="ChevronRight" size={16} />
        </button>
        <Notice icon="LockKeyhole">
          Dosyan ağa gönderilmez. Ses paneli bu oynatıcıyı gerçekten etkiler,
          cihazın genel sesini değil. Bu sayfadan ayrılınca oynatma durur; arka
          plan müzik servisi yoktur.
        </Notice>
      </div>
    </>
  );
}
function Browser({ go }: Props) {
  const [query, setQuery] = useState("");
  const href = browserHref(query);
  return (
    <>
      <ScreenTitle
        title="Tarayıcı"
        eyebrow="YENİ BİR PENCERE"
        onBack={() => go("home")}
      />
      <div className="page-body browser-page">
        <div className="daily-intro">
          <span className="daily-orbit">
            <Icon name="Globe2" size={34} />
          </span>
          <h3>Merak ettiğin ne varsa.</h3>
          <p>Bir adres yaz ya da webde bir şey ara.</p>
        </div>
        <form
          className="browser-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (href) window.open(href, "_blank", "noopener,noreferrer");
          }}
        >
          <div className="search-field">
            <Icon name="Search" />
            <input
              type="search"
              aria-label="Web adresi veya arama"
              maxLength={500}
              placeholder="Adres ya da arama…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button className="primary-button" disabled={!href}>
            Webde aç <Icon name="ArrowUpRight" size={17} />
          </button>
        </form>
        {query.trim() && !href && (
          <p className="error" role="alert">
            Yalnız güvenli HTTPS adresleri açılır. Komut veya dosya bağlantısı
            kullanma.
          </p>
        )}
        {href && (
          <a
            className="browser-target"
            href={href}
            rel="noopener noreferrer"
            target="_blank"
          >
            <Icon name="ExternalLink" size={17} />
            <span>{href}</span>
          </a>
        )}
        <div className="browser-shortcuts">
          {[
            ["Wikipedia", "BookOpen", "https://tr.wikipedia.org/"],
            ["Google", "Search", "https://www.google.com/"],
            ["Haritalar", "Map", "https://maps.google.com/"],
            ["E-posta", "Mail", "https://mail.google.com/"],
          ].map(([name, icon, url]) => (
            <a key={name} href={url} target="_blank" rel="noopener noreferrer">
              <AppBadge icon={icon} color="blue" small />
              <span>{name}</span>
              <Icon name="ArrowUpRight" size={13} />
            </a>
          ))}
        </div>
        <Notice icon="ExternalLink">
          Siteler cihazının tarayıcısında, ayrı sekmede açılır; bu bir gömülü
          web motoru değildir. Yazdığın sorgu ancak “Webde aç”a basınca arama
          sağlayıcısına gider. Açılmazsa yukarıdaki bağlantıyı kullan.
        </Notice>
      </div>
    </>
  );
}
function Gallery({ go, toast }: Props) {
  const [photos, setPhotos] = useState<
      { id: string; name: string; url: string }[]
    >([]),
    [selected, setSelected] = useState<{
      name: string;
      url: string;
      id?: string;
    } | null>(null);
  const urls = useRef<string[]>([]);
  useEffect(
    () => () => {
      urls.current.forEach((url) => URL.revokeObjectURL(url));
    },
    [],
  );
  function select(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const valid = files
      .filter(
        (file) =>
          ["image/jpeg", "image/png", "image/webp"].includes(file.type) &&
          file.size > 0 &&
          file.size <= 8 * 1024 * 1024,
      )
      .slice(0, Math.max(0, 6 - photos.length));
    const added = valid.map((file) => ({
      id: crypto.randomUUID(),
      name: file.name.slice(0, 120),
      url: URL.createObjectURL(file),
    }));
    urls.current.push(...added.map((p) => p.url));
    setPhotos([...photos, ...added]);
    e.target.value = "";
    if (valid.length < files.length)
      toast(
        "En çok 6 fotoğraf; her biri en çok 8 MiB JPEG, PNG veya WebP olmalı.",
      );
  }
  return (
    <>
      <ScreenTitle
        title="Galeri"
        eyebrow="GÜZEL ANLARINA BİR BAK"
        onBack={() => go("home")}
      />
      <div className="page-body gallery-page">
        <div className="gallery-pickers">
          <label
            className={`secondary-button ${photos.length >= 6 ? "disabled" : ""}`}
          >
            <Icon name="Image" size={18} /> Fotoğraf seç
            <input
              className="visually-hidden"
              aria-label="Galeriye fotoğraf seç"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              onChange={select}
              disabled={photos.length >= 6}
            />
          </label>
          <label
            className={`primary-button ${photos.length >= 6 ? "disabled" : ""}`}
          >
            <Icon name="Camera" size={18} /> Kamera
            <input
              className="visually-hidden"
              aria-label="Sistem kamerasından fotoğraf seç"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              onChange={select}
              disabled={photos.length >= 6}
            />
          </label>
        </div>
        <div className="section-line">
          <span>SENİN SEÇTİKLERİN</span>
          <span>{photos.length} / 6</span>
        </div>
        {photos.length ? (
          <div className="photo-grid">
            {photos.map((photo) => (
              <button
                key={photo.id}
                onClick={() => setSelected(photo)}
                aria-label={`${photo.name} fotoğrafını aç`}
              >
                <img src={photo.url} alt="" />
                <span>{photo.name}</span>
              </button>
            ))}
          </div>
        ) : (
          <Empty
            icon="Camera"
            title="Bir anı burada gör."
            text="Yalnız seçtiğin fotoğraflar açılır. Sistem galerinin tamamı taranmaz."
          />
        )}
        <div className="section-line">
          <span>OĞUZDOWS KÜLTÜR SEÇKİSİ</span>
          <span>AI GÖRSELLER</span>
        </div>
        <div className="photo-grid culture-photos">
          {Object.entries(WALLPAPER_NAMES).map(([id, name]) => (
            <button
              key={id}
              onClick={() => setSelected({ name, url: `/assets/${id}.webp` })}
              aria-label={`${name} görselini aç`}
            >
              <img src={`/assets/${id}.webp`} alt="" loading="lazy" />
              <span>{name}</span>
            </button>
          ))}
        </div>
        <Notice icon="LockKeyhole">
          Seçilen fotoğraflar yalnız bu açık sayfada kalır; ağa gönderilmez veya
          kalıcı kaydedilmez. Kamera desteği sistem seçicisine bağlıdır. Kültür
          görselleri gerçek kamera fotoğrafı değildir.
        </Notice>
      </div>
      {selected && (
        <Dialog title={selected.name} onClose={() => setSelected(null)}>
          <img
            className="photo-preview"
            src={selected.url}
            alt={selected.name}
          />
          {selected.id && (
            <button
              className="secondary-button"
              onClick={() => {
                const id = selected.id;
                URL.revokeObjectURL(selected.url);
                urls.current = urls.current.filter(
                  (url) => url !== selected.url,
                );
                setPhotos(photos.filter((photo) => photo.id !== id));
                setSelected(null);
              }}
            >
              <Icon name="X" size={17} /> Önizlemeden kaldır
            </button>
          )}
          <a
            className="secondary-button"
            href={selected.url}
            download={selected.id ? selected.name : `${selected.name}.webp`}
          >
            <Icon name="Download" size={17} /> Görseli indir
          </a>
        </Dialog>
      )}
    </>
  );
}
function Search({ prefs, go, onTool, onCatalog, onCall, onControls }: Props) {
  const [query, setQuery] = useState("");
  const q = normalize(query.trim());
  const matchingApps = apps.filter(
    (app) =>
      !q ||
      normalize(`${app.name} ${app.short} ${app.keywords || ""}`).includes(q),
  );
  const matchingTools = q
    ? TOOLS.filter((tool) =>
        normalize(`${tool.name} ${tool.description}`).includes(q),
      ).slice(0, 5)
    : [];
  const matchingCatalog = q
    ? catalog
        .filter((app) => normalize(`${app.name} ${app.category}`).includes(q))
        .slice(0, 6)
    : [];
  const matchingContacts = q
    ? prefs.contacts
        .filter((c) => normalize(`${c.name} ${c.number}`).includes(q))
        .slice(0, 5)
    : [];
  const matchingTasks = q
    ? prefs.tasks
        .filter((task) => normalize(task.title).includes(q))
        .slice(0, 5)
    : [];
  const noteMatch = q.length >= 2 && normalize(prefs.notes, 16384).includes(q);
  const controlsMatch =
    !!q &&
    ["ses", "parlak", "wifi", "wi-fi", "bluetooth", "panel", "denetim"].some(
      (word) => q.includes(word),
    );
  let result = "";
  if (q && /^[\d\s+\-*/×÷().,]+$/.test(q)) {
    try {
      result = String(calculate(query));
    } catch {
      /* incomplete expression is just a search */
    }
  }
  const count =
    matchingApps.length +
    matchingTools.length +
    matchingCatalog.length +
    matchingContacts.length +
    matchingTasks.length +
    Number(noteMatch) +
    Number(controlsMatch) +
    Number(!!result);
  return (
    <>
      <ScreenTitle
        title="Cihazında ara"
        eyebrow="ARADIĞIN, ELİNİN ALTINDA"
        onBack={() => go("home")}
      />
      <div className="page-body universal-search">
        <div className="search-field">
          <Icon name="Search" />
          <input
            type="search"
            autoFocus
            aria-label="Cihazında ara"
            placeholder="Uygulama, kişi, not, araç…"
            maxLength={80}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              className="icon-button"
              aria-label="Aramayı temizle"
              onClick={() => setQuery("")}
            >
              <Icon name="X" size={16} />
            </button>
          )}
        </div>
        <div className="search-hints">
          {["Telefon", "Not", "Ses", "Harita"].map((value) => (
            <button key={value} onClick={() => setQuery(value)}>
              {value}
            </button>
          ))}
        </div>
        {result && (
          <button
            className="search-calculation"
            onClick={() => onTool("calculator")}
          >
            <Icon name="Calculator" />
            <span>
              {query}
              <strong>= {result}</strong>
            </span>
            <Icon name="ArrowUpRight" size={17} />
          </button>
        )}
        {controlsMatch && (
          <button className="full-row search-result" onClick={onControls}>
            <AppBadge icon="SlidersHorizontal" color="blue" small />
            <span>
              <strong>Ses ve denetim merkezi</strong>
              <small>Medya sesi, sessiz, görünüm ve parlaklık</small>
            </span>
            <Icon name="ChevronRight" size={17} />
          </button>
        )}
        {!!matchingApps.length && (
          <>
            <div className="section-line">
              <span>{q ? "UYGULAMALAR" : "HIZLI ERİŞİM"}</span>
              <span>{matchingApps.length}</span>
            </div>
            <div className="drawer-grid search-app-grid">
              {(q ? matchingApps : matchingApps.slice(0, 8)).map((app) => (
                <button
                  key={app.id}
                  className="app-tile"
                  onClick={() => go(app.id)}
                >
                  <AppBadge icon={app.icon} color={app.color} />
                  <span>{app.name}</span>
                </button>
              ))}
            </div>
          </>
        )}
        {!!matchingContacts.length && (
          <>
            <div className="section-line">
              <span>KİŞİLERİN</span>
            </div>
            {matchingContacts.map((c) => (
              <button
                key={c.id}
                className="full-row search-result"
                onClick={() => onCall(c.number)}
              >
                <AppBadge icon="ContactRound" color="blue" small />
                <span>
                  <strong>{c.name}</strong>
                  <small>{c.number} · numara çevir</small>
                </span>
                <Icon name="Phone" size={17} />
              </button>
            ))}
          </>
        )}
        {!!matchingTools.length && (
          <>
            <div className="section-line">
              <span>ATÖLYE ARAÇLARI</span>
            </div>
            {matchingTools.map((tool) => (
              <button
                key={tool.id}
                className="full-row search-result"
                onClick={() => onTool(tool.id)}
              >
                <AppBadge icon={tool.icon} color="mint" small />
                <span>
                  <strong>{tool.name}</strong>
                  <small>
                    {tool.interactive
                      ? tool.description
                      : "Yerel entegrasyon aşamasında"}
                  </small>
                </span>
                <Icon name="ChevronRight" size={17} />
              </button>
            ))}
          </>
        )}
        {(noteMatch || !!matchingTasks.length) && (
          <>
            <div className="section-line">
              <span>NOTLARIN VE GÖREVLERİN</span>
            </div>
            {noteMatch && (
              <button
                className="full-row search-result"
                onClick={() => onTool("notes")}
              >
                <AppBadge icon="NotebookPen" color="sand" small />
                <span>
                  <strong>Defter’de eşleşme</strong>
                  <small>{prefs.notes.slice(0, 90)}</small>
                </span>
                <Icon name="ChevronRight" size={17} />
              </button>
            )}
            {matchingTasks.map((task) => (
              <button
                key={task.id}
                className="full-row search-result"
                onClick={() => onTool("tasks")}
              >
                <AppBadge icon="ListTodo" color="lavender" small />
                <span>
                  <strong>{task.title}</strong>
                  <small>
                    {task.done ? "Tamamlandı" : "Günüm’de bekliyor"}
                  </small>
                </span>
                <Icon name="ChevronRight" size={17} />
              </button>
            ))}
          </>
        )}
        {!!matchingCatalog.length && (
          <>
            <div className="section-line">
              <span>MAĞAZADA KEŞFET</span>
            </div>
            {matchingCatalog.map((app) => (
              <button
                key={app.id}
                className="full-row search-result"
                onClick={() => onCatalog(app.id)}
              >
                <AppBadge
                  icon={app.icon}
                  color={app.color}
                  artwork={app.artwork}
                  small
                />
                <span>
                  <strong>{app.name}</strong>
                  <small>{app.category} · kaynak sayfasını incele</small>
                </span>
                <Icon name="ArrowUpRight" size={17} />
              </button>
            ))}
          </>
        )}
        {q && !count && (
          <Empty
            icon="Search"
            title="Henüz bir eşleşme yok."
            text="İsmin bir bölümünü, uygulama türünü veya araç adını dene."
          />
        )}
        {!!q && (
          <a
            className="secondary-button"
            href={`https://www.google.com/search?q=${encodeURIComponent(query)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Icon name="Globe2" size={17} /> Webde ara{" "}
            <Icon name="ExternalLink" size={14} />
          </a>
        )}
        <p className="local-search-note">
          <Icon name="LockKeyhole" size={13} /> Yerel arama. Yazdıkların
          kendiliğinden ağa gönderilmez.
        </p>
      </div>
    </>
  );
}
function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: string;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="daily-empty">
      <span>
        <Icon name={icon} size={28} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
