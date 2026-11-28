import { useEffect, useRef, useState, type FormEvent } from "react";
import { localReply } from "./core.mjs";
import { Dialog, Icon } from "./ui";
type Message = {
  role: "user" | "assistant";
  text: string;
  action?: string;
  label?: string;
  mode?: "local" | "model";
};
const welcome: Message = {
  role: "assistant",
  text: "Merhaba, ben Rıfkı. Bugün birlikte ne yapalım? Notlar, günlük plan, görünüm ve APK incelemesinde yol gösterebilirim.",
  mode: "local",
};
export function Rifki({
  onBack,
  onAction,
  seed,
  onSeedUsed,
}: {
  onBack: () => void;
  onAction: (action: string) => void;
  seed: string;
  onSeedUsed: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([welcome]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"local" | "model">("local");
  const [dialog, setDialog] = useState(false);
  const [consent, setConsent] = useState(false);
  const [provider, setProvider] = useState({
    enabled: false,
    label: "",
    checked: false,
  });
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages, busy]);
  useEffect(() => {
    if (seed) {
      setMessages([
        welcome,
        { role: "user", text: seed },
        { role: "assistant", ...localReply(seed), mode: "local" },
      ]);
      onSeedUsed();
    }
  }, [seed, onSeedUsed]);
  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError("");
    const next: Message[] = [
      ...messages,
      { role: "user" as const, text },
    ].slice(-12);
    setMessages(next);
    if (mode === "local") {
      setMessages(
        [
          ...next,
          {
            role: "assistant" as const,
            ...localReply(text),
            mode: "local" as const,
          },
        ].slice(-12),
      );
      return;
    }
    setBusy(true);
    const abort = new AbortController();
    controller.current = abort;
    try {
      let history = next.map((m) => ({
        role: m.role,
        content: m.text.slice(0, 2000),
      }));
      while (history.reduce((n, m) => n + m.content.length, 0) > 12000)
        history = history.slice(1);
      const response = await fetch("/api/rifki/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Rifki-Consent": "1" },
        body: JSON.stringify({ consent: true, messages: history }),
        signal: abort.signal,
      });
      const result = await response.json();
      if (!response.ok || typeof result.text !== "string")
        throw new Error(result.error || "Yanıt alınamadı.");
      if (!abort.signal.aborted)
        setMessages(
          [
            ...next,
            {
              role: "assistant" as const,
              text: result.text,
              mode: "model" as const,
            },
          ].slice(-12),
        );
    } catch (err) {
      if (!abort.signal.aborted) setError((err as Error).message);
    } finally {
      if (!abort.signal.aborted) setBusy(false);
    }
  }
  async function openModel() {
    setDialog(true);
    setConsent(false);
    try {
      const r = await fetch("/api/rifki/status", { cache: "no-store" });
      if (!r.ok) throw new Error();
      const data = await r.json();
      setProvider({
        enabled: data.enabled === true,
        label: String(data.label || ""),
        checked: true,
      });
    } catch {
      setProvider({
        enabled: false,
        label: "Model köprüsüne ulaşılamadı.",
        checked: true,
      });
    }
  }
  return (
    <div className="rifki-page">
      <header className="rifki-header">
        <button
          className="icon-button"
          aria-label="Ana ekrana dön"
          onClick={onBack}
        >
          <Icon name="ArrowLeft" />
        </button>
        <span className="cat-avatar">
          <img
            src="/assets/rifki.webp"
            alt="Rıfkı, bir gözü mavi bir gözü kehribar kedi"
          />
        </span>
        <div>
          <h2>Rıfkı</h2>
          <span>
            <i />
            {mode === "local" ? "Yerel rehber · çevrimdışı" : provider.label}
          </span>
        </div>
        <button className="model-button" onClick={openModel}>
          <Icon name="SlidersHorizontal" size={17} />
          <span>Model</span>
        </button>
      </header>
      <div className="chat-log" ref={log}>
        <div className="chat-welcome">
          <span className="chat-cat">
            <img src="/assets/rifki.webp" alt="" />
          </span>
          <span className="eyebrow">BİRLİKTE DÜŞÜNELİM</span>
          <h3>
            Bir soru.
            <br />
            Bir fikir. Birlikte.
          </h3>
          <p>
            {mode === "local"
              ? "Şu an sınırlı yerel rehber modundayım. Üretken yapay zekâ modeli bağlı değil."
              : "Mesajların, onayladığın sunucu modeline gönderilir. Sistem veya dosya erişimim yok."}
          </p>
        </div>
        <div className="messages" aria-live="polite" aria-relevant="additions">
          {messages.map((m, i) => (
            <div className={`message ${m.role}`} key={i}>
              {m.role === "assistant" && (
                <span className="message-label">
                  RIFKI{" "}
                  <small>
                    {m.mode === "model" ? "MODEL YANITI" : "YEREL REHBER"}
                  </small>
                </span>
              )}
              <p>{m.text}</p>
              {m.action && (
                <button
                  className="suggested-action"
                  onClick={() => onAction(m.action!)}
                >
                  {m.label}
                  <Icon name="ArrowUpRight" size={16} />
                </button>
              )}
            </div>
          ))}
          {busy && (
            <div className="message assistant">
              <span className="message-label">RIFKI</span>
              <p>Model yanıtı bekleniyor…</p>
              <button
                className="text-button"
                onClick={() => {
                  controller.current?.abort();
                  setBusy(false);
                  setError(
                    "Bekleme durduruldu. Sağlayıcının aldığı mesaj geri çekilemez.",
                  );
                }}
              >
                Beklemeyi durdur
              </button>
            </div>
          )}
        </div>
        {messages.length <= 1 && (
          <div className="chat-suggestions">
            {[
              "Bugünümü planla",
              "Koyu görünüme geç",
              "APK açmak istiyorum",
              "Sen bir yapay zekâ mısın?",
            ].map((q) => (
              <button key={q} onClick={() => setInput(q)}>
                {q}
                <Icon name="ArrowUpRight" size={15} />
              </button>
            ))}
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>
      <div className="chat-composer-wrap">
        <form className="chat-composer" onSubmit={send}>
          <input
            aria-label="Rıfkı’ya mesaj"
            value={input}
            maxLength={2000}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Aklından ne geçiyor?"
          />
          <button
            type="button"
            className="icon-button"
            disabled
            title="Sesli giriş bu önizlemede bağlı değil"
            aria-label="Sesli giriş henüz bağlı değil"
          >
            <Icon name="Mic" size={19} />
          </button>
          <button
            className="send-button"
            aria-label="Mesajı gönder"
            disabled={!input.trim() || busy}
          >
            <Icon name="ArrowUpRight" size={21} />
          </button>
        </form>
        <p>
          {mode === "local"
            ? "Mesajların bu kipte ağa gönderilmez."
            : "Yalnız bu sohbette yazdıkların modele gönderilir."}{" "}
          Sohbet kalıcı kaydedilmez.
        </p>
      </div>
      {dialog && (
        <Dialog
          title="Rıfkı’nın çalışma biçimi"
          onClose={() => setDialog(false)}
        >
          <div className="model-choices">
            <div className="privacy-illustration">
              <Icon name="ShieldCheck" size={34} />
            </div>
            <h3>Kontrol her zaman sende.</h3>
            <p>
              Yerel rehber kurallarla çalışır; genel amaçlı üretken model
              değildir. Gerçek bir modele bağlanmak tamamen isteğe bağlıdır.
            </p>
            <button
              className={`model-option ${mode === "local" ? "chosen" : ""}`}
              onClick={() => {
                setMode("local");
                setMessages([welcome]);
                setDialog(false);
                setError("");
              }}
            >
              <Icon name="Leaf" />
              <span>
                <strong>Yerel rehber</strong>
                <small>Ağ yok. Mikrofon yok. Sınırlı komutlar.</small>
              </span>
              {mode === "local" && <Icon name="Check" size={17} />}
            </button>
            <div className="model-option">
              <Icon name="Sparkles" />
              <span>
                <strong>
                  {provider.checked
                    ? provider.enabled
                      ? provider.label
                      : "Üretken model bağlı değil"
                    : "Bağlantı kontrol ediliyor…"}
                </strong>
                <small>Sunucuda OpenAI uyumlu API veya yerel model.</small>
              </span>
            </div>
            {provider.enabled ? (
              <>
                <label className="consent-check">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                  />
                  <span>
                    Yeni sohbette yazdığım mesajların bağlı model sağlayıcısına
                    gönderilmesini onaylıyorum. Parola ve özel bilgi
                    paylaşmayacağım. Eski yerel sohbet gönderilmez.
                  </span>
                </label>
                <button
                  className="primary-button"
                  disabled={!consent}
                  onClick={() => {
                    setMode("model");
                    setMessages([]);
                    setDialog(false);
                    setError("");
                  }}
                >
                  Yeni model sohbeti aç <Icon name="ArrowRight" size={16} />
                </button>
              </>
            ) : (
              <p className="model-setup">
                Geliştirici: sunucuda RIFKI_ENABLED, RIFKI_API_BASE ve
                RIFKI_MODEL ayarlanmalı. Anahtarlar tarayıcıya girilmez;
                dokümandaki güvenlik koşullarını izleyin.
              </p>
            )}
            <p className="fine-print">
              Model yanıtları yalnız metindir. Ayar değiştirme, kurulum, arama
              ve dosya erişimi yetkisi verilmez.
            </p>
          </div>
        </Dialog>
      )}
    </div>
  );
}
