/** Pure, bounded preview logic. No shell, model, device or network access. */
export const STORAGE_KEY = "oguzdows.mobile.preview.v1";
export const WALLPAPERS = ["bosphorus", "cappadocia", "mountains", "salt-lake"];
export const TOOLS = [
  ["tasks", "Günüm", "Görevlerine biraz yer aç.", "ListTodo", true],
  ["notes", "Defter", "Aklından geçenler kaybolmasın.", "NotebookPen", true],
  [
    "snippets",
    "Metin rafı",
    "Sık kullandığın cümleler.",
    "ClipboardList",
    true,
  ],
  [
    "places",
    "Yerlerim",
    "Seçtiğin klasörler, tek yerde.",
    "FolderHeart",
    false,
  ],
  ["find", "Dosya bul", "İndeksleyici olmadan ara.", "Search", false],
  [
    "rename",
    "Toplu adlandır",
    "Önizle, onayla, geri al.",
    "TextCursorInput",
    false,
  ],
  ["checksum", "Dosya doğrula", "Gerçek SHA-256 hesapla.", "ShieldCheck", true],
  ["image", "Görsel hazırla", "Aslını koruyan dönüşümler.", "Image", false],
  ["diff", "Metin karşılaştır", "Farkları yan yana incele.", "Columns2", false],
  ["json", "JSON masası", "Doğrula ve biçimlendir.", "Braces", true],
  ["calculator", "Hesap", "Sade, güvenli aritmetik.", "Calculator", true],
  ["units", "Birimler", "Uzunluk ve sıcaklık.", "Ruler", true],
  ["color", "Renk stüdyosu", "Renk ve WCAG kontrastı.", "Palette", true],
  ["clocks", "Dünya saatleri", "Dört şehir, tek bakış.", "Globe2", true],
  ["text", "Metin işle", "Türkçe harfleri anlayarak.", "CaseSensitive", true],
  [
    "startup",
    "Başlangıç",
    "Platformun izin verdiği kadar.",
    "SlidersHorizontal",
    false,
  ],
].map(([id, name, description, icon, interactive]) => ({
  id: String(id),
  name: String(name),
  description: String(description),
  icon: String(icon),
  interactive: interactive === true,
}));

export function normalize(text, limit = 2000) {
  return String(text)
    .toLocaleLowerCase("tr-TR")
    .replaceAll("ı", "i")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .slice(
      0,
      Number.isSafeInteger(limit) ? Math.max(0, Math.min(20000, limit)) : 2000,
    );
}
export function initialState() {
  return {
    version: 1,
    theme: "light",
    wallpaper: "bosphorus",
    accent: "sea",
    lowPower: false,
    reducedMotion: false,
    wifi: true,
    bluetooth: false,
    airplane: false,
    focus: false,
    brightness: 100,
    volume: 55,
    muted: false,
    layout: "comfort",
    tasks: [{ id: "welcome", title: "Kendime biraz zaman ayır", done: false }],
    notes: "",
    snippets: [],
    wishlist: [],
    saved: [],
    read: [],
    contacts: [],
    events: [],
    messageDraft: { number: "", body: "" },
    timerEnd: null,
    stopwatch: { elapsed: 0, startedAt: null },
  };
}
export function restoreState(raw) {
  const base = initialState();
  if (!raw) return base;
  if (raw.length > 150_000)
    throw new Error(
      "Yerel kayıt beklenen boyuttan büyük; otomatik üzerine yazılmadı.",
    );
  let value;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error("Yerel kayıt okunamadı; otomatik üzerine yazılmadı.");
  }
  if (!value || value.version !== 1 || typeof value !== "object")
    throw new Error(
      "Yerel kayıt sürümü tanınmıyor; otomatik üzerine yazılmadı.",
    );
  for (const key of [
    "lowPower",
    "reducedMotion",
    "wifi",
    "bluetooth",
    "airplane",
    "focus",
    "muted",
  ])
    if (typeof value[key] === "boolean") base[key] = value[key];
  if (["light", "dark"].includes(value.theme)) base.theme = value.theme;
  if (WALLPAPERS.includes(value.wallpaper)) base.wallpaper = value.wallpaper;
  if (["sea", "copper", "plum"].includes(value.accent))
    base.accent = value.accent;
  if (["comfort", "compact"].includes(value.layout)) base.layout = value.layout;
  if (Number.isFinite(value.brightness))
    base.brightness = Math.round(Math.max(25, Math.min(100, value.brightness)));
  if (Number.isFinite(value.volume))
    base.volume = Math.round(Math.max(0, Math.min(100, value.volume)));
  const timestamp = (n) =>
    Number.isSafeInteger(n) && n >= 946684800000 && n <= 4133980800000;
  if (timestamp(value.timerEnd)) base.timerEnd = value.timerEnd;
  if (value.stopwatch && typeof value.stopwatch === "object") {
    base.stopwatch = {
      elapsed: Number.isFinite(value.stopwatch.elapsed)
        ? Math.max(0, Math.min(86400000, value.stopwatch.elapsed))
        : 0,
      startedAt: timestamp(value.stopwatch.startedAt)
        ? value.stopwatch.startedAt
        : null,
    };
  }
  if (value.messageDraft && typeof value.messageDraft === "object") {
    base.messageDraft = {
      number:
        typeof value.messageDraft.number === "string"
          ? value.messageDraft.number.slice(0, 40)
          : "",
      body:
        typeof value.messageDraft.body === "string"
          ? value.messageDraft.body.slice(0, 2000)
          : "",
    };
  }
  if (Array.isArray(value.contacts)) {
    const seen = new Set();
    base.contacts = value.contacts
      .slice(0, 60)
      .filter((c) => {
        if (
          !c ||
          typeof c.id !== "string" ||
          !c.id.trim() ||
          typeof c.name !== "string" ||
          !c.name.trim() ||
          !phoneNumber(c.number) ||
          seen.has(c.id.slice(0, 80))
        )
          return false;
        seen.add(c.id.slice(0, 80));
        return true;
      })
      .map((c) => ({
        id: c.id.slice(0, 80),
        name: c.name.trim().slice(0, 60),
        number: phoneNumber(c.number),
        favorite: c.favorite === true,
      }));
  }
  if (Array.isArray(value.events)) {
    const seen = new Set();
    base.events = value.events
      .slice(0, 80)
      .filter((event) => {
        if (
          !event ||
          typeof event.id !== "string" ||
          !event.id.trim() ||
          typeof event.title !== "string" ||
          !event.title.trim() ||
          !validDate(event.date) ||
          seen.has(event.id.slice(0, 80))
        )
          return false;
        seen.add(event.id.slice(0, 80));
        return true;
      })
      .map((event) => ({
        id: event.id.slice(0, 80),
        date: event.date,
        title: event.title.trim().slice(0, 140),
      }));
  }
  if (typeof value.notes === "string")
    base.notes = value.notes.slice(0, 16_384);
  if (Array.isArray(value.tasks))
    base.tasks = value.tasks
      .slice(0, 100)
      .filter(
        (x) => x && typeof x.id === "string" && typeof x.title === "string",
      )
      .map((x) => ({
        id: x.id.slice(0, 80),
        title: x.title.slice(0, 180),
        done: x.done === true,
      }));
  for (const key of ["snippets", "wishlist", "saved", "read"])
    if (Array.isArray(value[key]))
      base[key] = [
        ...new Set(
          value[key]
            .filter((x) => typeof x === "string")
            .map((x) => x.slice(0, key === "snippets" ? 300 : 80)),
        ),
      ].slice(0, key === "read" ? 100 : 40);
  return base;
}

export function localReply(text) {
  const q = normalize(text);
  if (/\b(rm\s+-|sudo|mkfs|fastboot|adb\s+shell|format|kilid.*ac)\b/.test(q))
    return {
      text: "Komut çalıştırmam, cihaz kilidini açmam veya veri silmem. Bir mobil port için önce tam model ve bootloader koşulları incelenmeli. Telefonunun yedeğini almadan ilerleme.",
    };
  if (q.includes("koyu") || q.includes("karanlik"))
    return {
      text: "Koyu görünümü birlikte açabiliriz. Bu önizlemenin tüm yerel ekranları aynı tercihi izler; üçüncü taraf uygulamaların görünümünü değiştiremem.",
      action: "dark",
      label: "Koyu görünümü uygula",
    };
  if (q.includes("acik tema") || q.includes("aydinlik"))
    return {
      text: "Açık görünümü uygulamamı ister misin?",
      action: "light",
      label: "Açık görünümü uygula",
    };
  if (q.includes("apk") || q.includes("yukle") || q.includes("kurulum"))
    return {
      text: "APK dosyanı seçip ZIP başlığını ve SHA-256 özetini inceleyebilirsin. Tarayıcı APK kuramaz; imza, paket izinleri ve kurulum için yerel sistem yükleyicisi gerekir. Güvenmediğin bir dosyayı yükleme.",
      action: "apk",
      label: "APK incelemesini aç",
    };
  if (q.includes("google") || q.includes("play"))
    return {
      text: "Google web kısayollarını açabilirim. Play Store ve Google Play hizmetleri ROM’a kendiliğinden eklenmez: lisans, cihaz sertifikası ve uyumluluk gerekir. Banka/DRM/Play Integrity garantisi yok.",
      action: "google",
      label: "Google seçeneklerini aç",
    };
  if (
    q.includes("pil") ||
    q.includes("nazar") ||
    q.includes("guc") ||
    q.includes("sarj")
  )
    return {
      text: "Nazar boncuğu hem güç menüsünün hem pil kimliğinin parçası. Hafif profil görsel efektleri sadeleştirir; gerçek pil tasarrufu ölçülmüş değildir. Buradaki pil/radyo göstergeleri örnektir.",
      action: "low-power",
      label: "Hafif profili etkinleştir",
    };
  if (q.includes("mesaj") || q.includes("sms"))
    return {
      text: "Alıcı ve taslağı Mesajlar’da hazırlayabilirsin. Gönderim ancak cihazının sistem mesajlaşma uygulamasında ve senin onayınla olur; ben SMS göndermem.",
      action: "messages",
      label: "Mesajlar’ı aç",
    };
  if (q.includes("telefon") || q.includes("numara") || q.includes("arama yap"))
    return {
      text: "Telefon ekranında numara çevirebilirsin. Arama, cihazının kendi uygulamasına devredilir; bağlantı kurulduğunu varsaymam.",
      action: "phone",
      label: "Telefon’u aç",
    };
  if (q.includes("rehber") || q.includes("kisiler"))
    return {
      text: "Önizleme rehberine kendi kişilerini ekleyebilirsin. Cihazının sistem kişilerini okumam ve ağa göndermem.",
      action: "contacts",
      label: "Kişiler’i aç",
    };
  if (q.includes("ses") || q.includes("parlak") || q.includes("panel"))
    return {
      text: "Denetim merkezinde bu önizlemenin medya sesini ve görünüm parlaklığını ayarlayabilirsin. Cihazının genel sistem ayarını sessizce değiştirmem.",
      action: "controls",
      label: "Denetim merkezini aç",
    };
  if (q.includes("takvim"))
    return {
      text: "Takvim’e yerel bir plan ekleyebilirsin. Bu, sistem takvimi veya bildirim alarmı değildir.",
      action: "calendar",
      label: "Takvim’i aç",
    };
  if (q.includes("muzik"))
    return {
      text: "Kendi ses dosyanı seçerek dinleyebilir, üst panelden sesini ayarlayabilirsin. Dosya sunucuya gönderilmez.",
      action: "media",
      label: "Müzik’i aç",
    };
  if (q.includes("kronometre") || q.includes("sayac"))
    return {
      text: "Saat’te kronometre ve sayaç var. Sistem alarmı veya arka plan bildirimi kurulmaz.",
      action: "clock",
      label: "Saat’i aç",
    };
  if (q.includes("not") || q.includes("yaz"))
    return {
      text: "Defter’i açayım. Kaydettiklerin yalnız bu tarayıcıda tutulur; şifreli kasa veya cihazlar arası eşitleme değildir.",
      action: "notes",
      label: "Defter’i aç",
    };
  if (q.includes("gun") || q.includes("plan") || q.includes("gorev"))
    return {
      text: "Önce küçük bir adım seçelim. Günüm’e bir görev ekleyebilir, tamamladığında işaretleyebilirsin. Ben takvimine veya mesajlarına izinsiz erişmem.",
      action: "tasks",
      label: "Günüm’ü aç",
    };
  if (q.includes("duvar") || q.includes("kultur"))
    return {
      text: "OğuzDows’un kültür koleksiyonunu cebine taşıyalım. Bir görsel seçmen yeterli; yalnız bu önizlemenin ana ekranı değişir.",
      action: "culture",
      label: "Koleksiyona göz at",
    };
  if (q.includes("kimsin") || q.includes("zeka") || q.includes("model"))
    return {
      text: "Ben Rıfkı. Şu an sınırlı, kural tabanlı çevrimdışı rehber modundayım; üretken bir model çalışmıyor. Sunucuya bir model bağlanır ve sen açıkça izin verirsen gerçek sohbet kipine geçebilirsin. Sohbet için mikrofon dinlemem.",
    };
  return {
    text: "Buradayım. Gününü planlama, notlar, görünüm, güç profili, Google seçenekleri ve APK inceleme konusunda yardımcı olabilirim. Bu çevrimdışı kip genel amaçlı üretken yapay zekâ değildir; bilmediğim bir yanıtı uydurmam.",
  };
}

/** Recursive descent arithmetic; never eval or Function. */
export function calculate(source) {
  const input = String(source)
    .replaceAll(",", ".")
    .replaceAll("×", "*")
    .replaceAll("÷", "/");
  if (!input.trim() || input.length > 128 || /[^\d.\s+*/()\-]/.test(input))
    throw new Error(
      "En çok 128 karakter: sayılar, parantez ve + − × ÷ kullan.",
    );
  const tokens = input.match(/(?:\d+(?:\.\d*)?|\.\d+)|[+*/()\-]/g) || [];
  if (tokens.length > 64) throw new Error("İfade çok uzun.");
  let i = 0,
    depth = 0;
  const atom = () => {
    if (++depth > 20) throw new Error("Çok fazla iç içe parantez.");
    let result;
    const t = tokens[i++];
    if (t === "(") {
      result = sum();
      if (tokens[i++] !== ")") throw new Error("Parantezler eşleşmiyor.");
    } else if (t === "+" || t === "-") result = (t === "-" ? -1 : 1) * atom();
    else {
      if (!t || !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(t))
        throw new Error("Geçerli bir ifade yaz.");
      result = Number(t);
    }
    depth--;
    return result;
  };
  const product = () => {
    let n = atom();
    while (tokens[i] === "*" || tokens[i] === "/") {
      const op = tokens[i++];
      const b = atom();
      if (op === "/" && b === 0) throw new Error("Sıfıra bölünemez.");
      n = op === "*" ? n * b : n / b;
    }
    return n;
  };
  const sum = () => {
    let n = product();
    while (tokens[i] === "+" || tokens[i] === "-") {
      const op = tokens[i++];
      const b = product();
      n = op === "+" ? n + b : n - b;
    }
    return n;
  };
  const result = sum();
  if (
    i !== tokens.length ||
    !Number.isFinite(result) ||
    Math.abs(result) > 1e15
  )
    throw new Error("İfade eksik veya sonuç desteklenen aralığın dışında.");
  return Number(result.toPrecision(12));
}
export function contrast(hex, against = "#ffffff") {
  const lum = (v) => {
    if (!/^#[0-9a-f]{6}$/i.test(v))
      throw new Error("Altı haneli bir renk kullan.");
    const c = v
      .slice(1)
      .match(/../g)
      .map((h) => parseInt(h, 16) / 255)
      .map((n) => (n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const a = lum(hex),
    b = lum(against);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
export function convert(value, kind) {
  const n = Number(value);
  if (!String(value).trim() || !Number.isFinite(n) || Math.abs(n) > 1e12)
    throw new Error("Geçerli, sınırlı bir sayı yaz.");
  if (kind === "c-f") {
    if (n < -273.15) throw new Error("Mutlak sıfırın altı olamaz.");
    return (n * 9) / 5 + 32;
  }
  if (kind === "km-m") return n * 1000;
  if (kind === "m-km") return n / 1000;
  if (kind === "mib-mb") return (n * 1048576) / 1000000;
  throw new Error("Dönüşüm desteklenmiyor.");
}
export function inspectApkHeader(name, size, bytes) {
  if (!/\.apk$/i.test(name))
    throw new Error(
      "Tek bir .apk dosyası seç. APKS/XAPK paketleri desteklenmiyor.",
    );
  if (!Number.isSafeInteger(size) || size < 4 || size > 32 * 1024 * 1024)
    throw new Error("Önizleme APK boyutu 4 bayt–32 MiB aralığında olmalı.");
  if (
    bytes[0] !== 0x50 ||
    bytes[1] !== 0x4b ||
    bytes[2] !== 0x03 ||
    bytes[3] !== 0x04
  )
    throw new Error("Beklenen ZIP/APK başlangıcı bulunamadı.");
  return { name, size, signatureVerified: false, installableHere: false };
}
export async function sha256(buffer) {
  const result = await globalThis.crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(result)]
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("");
}
export function formatBytes(n) {
  return n >= 1048576
    ? (n / 1048576).toFixed(1) + " MiB"
    : Math.ceil(n / 1024) + " KiB";
}
export function allowedHttps(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && !u.username && !u.password;
  } catch {
    return false;
  }
}

/** Only ordinary telephone numbers. No USSD, pauses, URI parameters or control codes. */
export function phoneNumber(value) {
  if (
    typeof value !== "string" ||
    value.length > 40 ||
    /[^\d+().\s-]/u.test(value) ||
    /[\u0000-\u001f\u007f]/u.test(value)
  )
    return "";
  const number = value.replace(/[().\s-]/gu, "");
  return /^\+?\d{3,20}$/u.test(number) ? number : "";
}
export function phoneHref(value) {
  const number = phoneNumber(value);
  return number ? `tel:${number}` : "";
}
export function smsHref(value, body = "") {
  const number = phoneNumber(value);
  if (!number || typeof body !== "string" || body.length > 2000) return "";
  return `sms:${number}${body ? `?body=${encodeURIComponent(body)}` : ""}`;
}
export function browserHref(value) {
  if (typeof value !== "string" || !value.trim() || value.length > 500)
    return "";
  const input = value.trim();
  if (/^[a-z][a-z\d+.-]*:/iu.test(input))
    return allowedHttps(input) ? new URL(input).href : "";
  if (
    !/\s/u.test(input) &&
    /^[\p{L}\d-]+(?:\.[\p{L}\d-]+)+(?:[/?#].*)?$/u.test(input)
  ) {
    const url = `https://${input}`;
    return allowedHttps(url) ? new URL(url).href : "";
  }
  return `https://www.google.com/search?q=${encodeURIComponent(input)}`;
}
export function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/u.test(value))
    return false;
  const date = new Date(`${value}T12:00:00Z`);
  return (
    Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value &&
    date.getUTCFullYear() >= 2000 &&
    date.getUTCFullYear() <= 2100
  );
}
/** Coordinates relative to the phone. Scrolls in app content and sliders are not gestures. */
export function swipeAction(
  start,
  end,
  { home = false, blocked = false } = {},
) {
  if (!start || !end || blocked || start.blocked) return "";
  const dx = end.x - start.x,
    dy = end.y - start.y;
  if (![dx, dy, start.y].every(Number.isFinite)) return "";
  if (
    home &&
    start.y > 76 &&
    Math.abs(dx) >= 75 &&
    Math.abs(dy) <= Math.abs(dx) * 0.6
  )
    return dx < 0 ? "next-page" : "previous-page";
  if (Math.abs(dx) > Math.abs(dy) * 0.65) return "";
  if (start.y >= 0 && start.y <= 76 && dy >= 64) return "quick";
  if (home && start.y > 76 && dy <= -80) return "apps";
  return "";
}
