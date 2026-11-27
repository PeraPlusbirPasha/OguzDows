import { useCallback, useEffect, useState } from "react";
import type { Props } from "./Everyday";
import { phoneNumber } from "./core.mjs";
import { smsState } from "./native-state.mjs";
import {
  nativeRequest,
  refreshNativeStatus,
  useNativeStatus,
  type NativeSms,
} from "./native";
import { Icon, Notice, ScreenTitle } from "./ui";

export function NativeRolePanel({ scope }: { scope: "phone" | "sms" }) {
  const { status, error } = useNativeStatus();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const held = scope === "phone" ? status?.dialerRole : status?.smsRole;
  const granted =
    scope === "phone" ? status?.phonePermission : status?.smsPermission;
  async function run(action: string, args: Record<string, unknown>) {
    setBusy(true);
    setResult("");
    try {
      await nativeRequest(action, args);
      await refreshNativeStatus();
      setResult(
        "Sistem seçimi okundu. Arama veya SMS kendiliğinden başlatılmadı.",
      );
    } catch (err) {
      setResult((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="native-role-panel" aria-label="Yerel telefon izinleri">
      <div className="section-line">
        <span>YEREL {scope === "phone" ? "TELEFON" : "SMS"} SERVİSİ</span>
        <span>
          {!status
            ? "OKUNUYOR"
            : held && granted
              ? "ROL / İZİN HAZIR"
              : "SEÇİM BEKLİYOR"}
        </span>
      </div>
      <p>
        {scope === "phone"
          ? "Arama OğuzDows görüşme ekranında yönetilir; hat durumunu cihazın Telecom servisi bildirir."
          : "Düz SMS, cihazın SMS servisiyle alınır/gönderilir. MMS, RCS ve ekler bu sürümde tamamlanmış değil."}
      </p>
      <div className="native-action-row">
        <button
          className="secondary-button"
          disabled={busy || held}
          onClick={() =>
            void run("role.request", {
              role: scope === "phone" ? "dialer" : "sms",
            })
          }
        >
          <Icon name="Smartphone" size={16} />{" "}
          {held
            ? "Varsayılan seçili"
            : `Varsayılan ${scope === "phone" ? "Telefon" : "SMS"} seç`}
        </button>
        <button
          className="secondary-button"
          disabled={busy || (scope === "sms" && !held)}
          onClick={() => void run("permissions.request", { scope })}
        >
          <Icon name="ShieldCheck" size={16} />{" "}
          {granted ? "İzinleri kontrol et" : "İzinleri seç"}
        </button>
      </div>
      {status && !status.notificationPermission && (
        <p>Bildirim izni kapalı; gelen arama/SMS uyarıları kısıtlanabilir.</p>
      )}
      {(error || result) && <p role="status">{result || error}</p>}
      <button
        className="text-button"
        onClick={() => void run("settings.open", { panel: "defaults" })}
      >
        Varsayılanları yönet / geri al <Icon name="ArrowUpRight" size={14} />
      </button>
    </section>
  );
}

export function NativePhone({
  number,
  onNumber,
  onCompose,
  prefs,
  go,
  toast,
}: Props) {
  const { status } = useNativeStatus();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const normalized = phoneNumber(number);
  const contact = prefs.contacts.find((c) => c.number === normalized);
  async function call() {
    setBusy(true);
    setResult("");
    try {
      const response = await nativeRequest<{ message: string }>("call.place", {
        number: normalized,
      });
      setResult(response.message);
      await refreshNativeStatus();
    } catch (err) {
      setResult((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
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
      <div className="page-body communication-page native-communication">
        <NativeRolePanel scope="phone" />
        {status?.call && (
          <button
            className="native-call-card"
            onClick={() =>
              void nativeRequest("call.show").catch((e: Error) =>
                toast(e.message),
              )
            }
          >
            <Icon name="Phone" />
            <span>
              <strong>{status.call.label}</strong>
              <small>{status.call.number} · görüşme ekranını aç</small>
            </span>
            <Icon name="ChevronRight" />
          </button>
        )}
        <div className="dial-display">
          <span>{contact?.name || "Kimi aramak istersin?"}</span>
          <input
            type="tel"
            inputMode="tel"
            aria-label="Aranacak numara"
            autoComplete="off"
            placeholder="Numara yaz"
            maxLength={40}
            value={number}
            onChange={(e) => {
              onNumber(e.target.value);
              setResult("");
            }}
          />
          <button
            className="icon-button"
            aria-label="Son rakamı sil"
            disabled={!number}
            onClick={() => onNumber(number.slice(0, -1))}
          >
            <Icon name="Delete" />
          </button>
        </div>
        <div className="dial-pad real-dial-pad">
          {"123456789*0#".split("").map((digit, i) => (
            <button
              key={digit}
              aria-label={`${digit} tuşu`}
              onClick={() => onNumber((number + digit).slice(0, 40))}
            >
              <strong>{digit}</strong>
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
          <button
            className="dial-call"
            aria-label="OğuzDows içinde ara"
            disabled={
              busy ||
              !normalized ||
              !status?.dialerRole ||
              !status?.phonePermission
            }
            onClick={() => void call()}
          >
            <Icon name="Phone" size={27} />
            <span>{busy ? "Onay…" : "Ara"}</span>
          </button>
          <button
            className="icon-button"
            aria-label="Bu numaraya mesaj yaz"
            disabled={!normalized}
            onClick={() => onCompose(normalized)}
          >
            <Icon name="MessageCircle" />
          </button>
        </div>
        {result && (
          <p className="handoff-status" role="status">
            {result}
          </p>
        )}
        {!!number && !normalized && (
          <p className="error" role="alert">
            3–20 rakam ve başta + kullan. USSD/servis kodları gönderilmez.
          </p>
        )}
        <p className="handoff-caption">
          Son alıcı/ücret onayından sonra cihazın hattına istek iletilir.
          Bağlandı durumu yalnız Telecom bildirirse gösterilir.
        </p>
        {!!prefs.contacts.length && (
          <div className="recipient-chips" aria-label="Aranacak kişiyi seç">
            {prefs.contacts.slice(0, 12).map((c) => (
              <button key={c.id} onClick={() => onNumber(c.number)}>
                {c.name}
              </button>
            ))}
          </div>
        )}
        <Notice icon="ShieldCheck">
          Acil numaralar sistem acil arayıcısına yönlendirilir; bu deneysel
          arayüzden acil arama başlatılmaz. Emülatör sanal radyosu gerçek SIM,
          operatör, VoLTE/VoWiFi veya acil çağrı testi değildir.
        </Notice>
      </div>
    </>
  );
}

export function NativeMessages({ prefs, update, go, toast }: Props) {
  const { status } = useNativeStatus();
  const [rows, setRows] = useState<NativeSms[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [reply, setReply] = useState<{ number: string; body: string } | null>(
    null,
  );
  const draft = prefs.messageDraft;
  const load = useCallback(async () => {
    if (!status?.smsRole || !status.smsPermission) {
      setRows([]);
      return;
    }
    try {
      setRows(await nativeRequest<NativeSms[]>("messages.list"));
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [status?.smsRole, status?.smsPermission]);
  useEffect(() => {
    void load();
    const changed = () => {
      if (!document.hidden) void load();
    };
    window.addEventListener("oguz-native-state", changed);
    document.addEventListener("visibilitychange", changed);
    return () => {
      window.removeEventListener("oguz-native-state", changed);
      document.removeEventListener("visibilitychange", changed);
    };
  }, [load]);
  useEffect(() => {
    void nativeRequest<{ number: string; body: string }>(
      "messages.pendingReply",
    )
      .then((value) => {
        if (value.number && value.body) setReply(value);
      })
      .catch(() => {});
  }, []);
  const change = (value: Partial<typeof draft>) => {
    update({ messageDraft: { ...draft, ...value } });
    setResult("");
  };
  async function send() {
    setBusy(true);
    setResult("");
    try {
      const receipt = await nativeRequest<{ message: string }>(
        "messages.send",
        { number: phoneNumber(draft.number), body: draft.body },
      );
      setResult(receipt.message);
      await load();
    } catch (err) {
      setResult((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ScreenTitle
        title="Mesajlar"
        eyebrow="BİR MESAJLIK MESAFE"
        onBack={() => go("home")}
      />
      <div className="page-body communication-page native-communication">
        <NativeRolePanel scope="sms" />
        {!!status?.mmsNotices && (
          <Notice icon="CircleHelp">
            {status.mmsNotices} MMS bildirimi saklandı; içerikleri indirilmedi.
            MMS için eksiksiz bir varsayılan mesajlaşma uygulaması seç.
          </Notice>
        )}
        {reply && (
          <button
            className="secondary-button"
            onClick={() => {
              update({ messageDraft: reply });
              setReply(null);
              void nativeRequest("messages.clearPendingReply").catch(() => {});
            }}
          >
            Bekleyen hızlı yanıtı taslağa al · gönderilmedi
          </button>
        )}
        <label className="field-label">
          Alıcı
          <input
            type="tel"
            inputMode="tel"
            aria-label="Mesaj alıcısı"
            autoComplete="off"
            maxLength={40}
            value={draft.number}
            placeholder="+90… veya yerel numara"
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
            maxLength={2000}
            value={draft.body}
            placeholder="Merhaba…"
            onChange={(e) => change({ body: e.target.value })}
          />
        </label>
        <div className="section-line">
          <span>{draft.body.length} / 2000 KARAKTER</span>
          <span>TASLAK · GÖNDERİLMEDİ</span>
        </div>
        <button
          className="primary-button"
          disabled={
            busy ||
            !phoneNumber(draft.number) ||
            !draft.body.trim() ||
            !status?.smsRole ||
            !status.smsPermission
          }
          onClick={() => void send()}
        >
          <Icon name="SendHorizontal" size={18} />{" "}
          {busy ? "Sistem onayı bekleniyor…" : "OğuzDows içinden SMS gönder"}
        </button>
        {(result || error) && (
          <p className="handoff-status" role="status">
            {result || error}
          </p>
        )}
        <div className="section-line">
          <span>SON 50 SMS · SİSTEM KAYITLARI</span>
          <button className="text-button" onClick={() => void load()}>
            Yenile
          </button>
        </div>
        <div className="native-sms-history">
          {rows.map((row) => (
            <article
              className={`native-message ${row.type === 1 ? "incoming" : "outgoing"}`}
              key={row.id}
            >
              <div>
                <strong>{row.number || "Bilinmeyen gönderen"}</strong>
                <time dateTime={new Date(row.date).toISOString()}>
                  {new Date(row.date).toLocaleString("tr-TR", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </div>
              <p>{row.body}</p>
              <small>
                {smsState(row.type, row.status)}
                {row.type === 5 && row.errorCode
                  ? ` · kod ${row.errorCode}`
                  : ""}
              </small>
              <button
                className="text-button"
                onClick={() => {
                  change({ number: phoneNumber(row.number) });
                  toast("Alıcı taslağa alındı; mesaj gönderilmedi.");
                }}
              >
                Bu numaraya yaz
              </button>
            </article>
          ))}
          {!rows.length && (
            <p className="empty-state">
              {status?.smsRole && status.smsPermission
                ? "Sistem sağlayıcısında gösterilecek SMS yok."
                : "SMS listesi rol ve okuma izninden sonra açılır."}
            </p>
          )}
        </div>
        <Notice icon="LockKeyhole">
          SMS geçmişi cihazın sistem sağlayıcısındadır; taslak ve yerel kişiler
          uygulama verisinde şifrelenmeden tutulur. İletiler ağa/model servisine
          yüklenmez. Gönderim/teslim ayrı durumlardır; hata veya eksik raporda
          otomatik tekrar yapılmaz.
        </Notice>
      </div>
    </>
  );
}
