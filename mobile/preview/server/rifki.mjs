/** Optional server-only model bridge. Off by default. No tools, secrets in UI or transcript logging. */
const SYSTEM =
  "Sen Rıfkı, OğuzDows Mobile için Türkçe bir yardımcısın. Kısa, nazik ve dürüst ol. Bu bir tarayıcı tasarım önizlemesi, kurulu telefon işletim sistemi değil. Cihaza, mikrofonuna, dosyalarına, Google hesabına veya sisteme erişimin ve eylem çalıştırma yetkin yok. Kurulum, arama, mesaj, dosya silme veya ayar değiştirme yaptığını iddia etme. Parola, API anahtarı ve ödeme bilgisi isteme. Riskli işlemler için açık onay ve gerçek sistem arayüzünü öner. Bilmediğini belirt.";
const MAX_BODY = 24_576;
export function configuration(env = process.env) {
  const base = env.RIFKI_API_BASE || "";
  let valid = false;
  try {
    const u = new URL(base);
    valid =
      !u.username &&
      !u.password &&
      !u.search &&
      !u.hash &&
      (u.protocol === "https:" ||
        (u.protocol === "http:" &&
          ["localhost", "127.0.0.1", "[::1]"].includes(u.hostname)));
  } catch {
    /* Unconfigured, not a public error. */
  }
  const enabled =
    env.RIFKI_ENABLED === "true" &&
    valid &&
    /^[\w./:@-]{1,100}$/.test(env.RIFKI_MODEL || "");
  return {
    enabled,
    base: base.replace(/\/$/, ""),
    model: env.RIFKI_MODEL || "",
    key: env.RIFKI_API_KEY || "",
    label: (env.RIFKI_MODEL_LABEL || "Bağlı üretken model").slice(0, 60),
  };
}
export function validateMessages(body) {
  if (
    !body ||
    body.consent !== true ||
    !Array.isArray(body.messages) ||
    body.messages.length < 1 ||
    body.messages.length > 12
  )
    throw new Error("Geçerli mesajlar ve açık gönderim onayı gerekli.");
  let total = 0;
  const messages = body.messages.map((m) => {
    if (
      !m ||
      !["user", "assistant"].includes(m.role) ||
      typeof m.content !== "string" ||
      !m.content.trim() ||
      m.content.length > 2000
    )
      throw new Error("Mesajlar en çok 2000 karakter olmalı.");
    total += m.content.length;
    return { role: m.role, content: m.content };
  });
  if (total > 12000 || messages.at(-1).role !== "user")
    throw new Error("Sohbet sınırı aşıldı veya son mesaj geçersiz.");
  return messages;
}
async function boundedJson(response) {
  if (!response.body) throw new Error("Yanıt yok.");
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 65536) throw new Error("Yanıt sınırı.");
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
  const merged = Buffer.concat(chunks);
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(merged));
}
export function rifkiMiddleware(options = {}) {
  const config = options.config || configuration();
  const fetcher = options.fetch || globalThis.fetch;
  let active = 0;
  const limits = new Map();
  return async (req, res, next) => {
    const path = (req.url || "").split("?")[0];
    if (!path.startsWith("/api/rifki/")) return next();
    const send = (code, value) => {
      if (res.destroyed) return;
      res.statusCode = code;
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.setHeader("X-Content-Type-Options", "nosniff");
      res.end(JSON.stringify(value));
    };
    if (path === "/api/rifki/status" && req.method === "GET")
      return send(200, {
        enabled: config.enabled,
        label: config.enabled ? config.label : "Yerel rehber",
        logging: false,
        tools: false,
      });
    if (path !== "/api/rifki/chat")
      return send(404, { error: "Uç bulunamadı." });
    if (req.method !== "POST") return send(405, { error: "POST gerekli." });
    if (
      req.headers["x-rifki-consent"] !== "1" ||
      !(req.headers["content-type"] || "").startsWith("application/json")
    )
      return send(403, { error: "Açık onay ve JSON isteği gerekli." });
    if (req.headers.origin) {
      try {
        const origin = new URL(req.headers.origin);
        const hosts = [
          req.headers.host,
          String(req.headers["x-forwarded-host"] || "")
            .split(",")[0]
            .trim(),
        ];
        if (!hosts.includes(origin.host))
          return send(403, {
            error: "Yalnız aynı kökenden istek kabul edilir.",
          });
      } catch {
        return send(403, { error: "Geçersiz köken." });
      }
    }
    if (!config.enabled)
      return send(503, {
        error: "Üretken model bağlı değil. Yerel rehberi kullanabilirsin.",
      });
    if (Number(req.headers["content-length"]) > MAX_BODY)
      return send(413, { error: "İstek çok büyük." });
    const now = Date.now(),
      ip = req.socket.remoteAddress || "unknown";
    for (const [key, value] of limits)
      if (now - value.since > 60000) limits.delete(key);
    const limit = limits.get(ip) || { since: now, count: 0 };
    if (
      active >= 2 ||
      limit.count >= 8 ||
      (limits.size >= 1000 && !limits.has(ip))
    )
      return send(429, { error: "Çok fazla istek. Biraz sonra yeniden dene." });
    let body;
    try {
      let size = 0;
      const chunks = [];
      for await (const chunk of req) {
        size += chunk.length;
        if (size > MAX_BODY) throw new Error("İstek sınırı aşıldı.");
        chunks.push(chunk);
      }
      body = JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)),
      );
      body = { messages: validateMessages(body) };
    } catch {
      return send(400, {
        error:
          "Geçersiz veya fazla büyük mesaj. En çok 12 mesaj / 12000 karakter.",
      });
    }
    // Body reads yield: re-check fresh counters before reserving an inference slot.
    const current = limits.get(ip) || { since: Date.now(), count: 0 };
    if (
      active >= 2 ||
      current.count >= 8 ||
      (limits.size >= 1000 && !limits.has(ip))
    )
      return send(429, { error: "Çok fazla istek. Biraz sonra yeniden dene." });
    current.count++;
    limits.set(ip, current);
    active++;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    const cancel = () => {
      if (!res.writableEnded) controller.abort();
    };
    res.on("close", cancel);
    try {
      const headers = { "Content-Type": "application/json" };
      if (config.key) headers.Authorization = `Bearer ${config.key}`;
      const upstream = await fetcher(config.base + "/chat/completions", {
        method: "POST",
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          model: config.model,
          messages: [{ role: "system", content: SYSTEM }, ...body.messages],
          max_tokens: 600,
          stream: false,
        }),
      });
      if (!upstream.ok) {
        await upstream.body?.cancel();
        throw new Error("Model kullanılamıyor.");
      }
      const result = await boundedJson(upstream);
      const text = result.choices?.[0]?.message?.content;
      if (typeof text !== "string" || !text.trim() || text.length > 10000)
        throw new Error("Model yanıtı geçersiz.");
      send(200, { text, mode: "model", label: config.label });
    } catch {
      send(502, {
        error:
          "Modelden güvenilir biçimde yanıt alınamadı. Anahtar/sağlayıcı ayrıntıları kayda alınmaz. Yerel rehbere dönebilirsin.",
      });
    } finally {
      clearTimeout(timer);
      res.off("close", cancel);
      active--;
    }
  };
}
