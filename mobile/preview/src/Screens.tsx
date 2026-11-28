import { useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  apps,
  articles,
  catalog,
  googleLinks,
  WALLPAPER_NAMES,
  type Preferences,
  type Screen,
} from "./data";
import {
  TOOLS,
  calculate,
  contrast,
  convert,
  formatBytes,
  inspectApkHeader,
  normalize,
  sha256,
} from "./core.mjs";
import { AppBadge, Dialog, Icon, Notice, ScreenTitle, Toggle } from "./ui";
import { inNativeApp } from "./native";
import {
  NativeAction,
  NativeSettings,
  NativeStoreActions,
} from "./NativeActions";

export type PageProps = {
  prefs: Preferences;
  update: (value: Partial<Preferences>) => void;
  go: (screen: Screen) => void;
  toast: (text: string) => void;
};
export function downloadText(text: string, name: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function ApkInspector({
  checksumOnly = false,
}: {
  checksumOnly?: boolean;
}) {
  const [result, setResult] = useState<{
    name: string;
    size: number;
    hash: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function select(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || busy) return;
    setError("");
    setResult(null);
    setBusy(true);
    try {
      if (file.size > 32 * 1024 * 1024 || file.size < 1)
        throw new Error("Önizleme dosya sınırı: 1 bayt–32 MiB.");
      if (!checksumOnly)
        inspectApkHeader(
          file.name,
          file.size,
          new Uint8Array(await file.slice(0, 4).arrayBuffer()),
        );
      const hash = await sha256(await file.arrayBuffer());
      if (alive.current) setResult({ name: file.name, size: file.size, hash });
    } catch (err) {
      if (alive.current) setError((err as Error).message);
    } finally {
      if (alive.current) setBusy(false);
      e.target.value = "";
    }
  }
  if (inNativeApp && !checksumOnly)
    return (
      <div className="apk-inspector">
        <NativeAction action="apk.pick" className="primary-button">
          <Icon name="Upload" size={22} /> Sistemden APK seç ve incele
        </NativeAction>
        <Notice icon="ShieldCheck">
          Sistem belge seçicisiyle seçilen tek APK, özel kopyaya alınır.
          Paket/sürüm, API/ABI, izinler, SHA-256 ve ilk imzacı özeti gösterilir;
          sonra ayrı kaynak izni ve sistem yükleme onayı gerekir. En çok 256
          MiB; split/APKS/XAPK ve sessiz kurulum yok.
        </Notice>
      </div>
    );
  return (
    <div className="apk-inspector">
      <label className={`file-pick ${busy ? "disabled" : ""}`}>
        <Icon name={checksumOnly ? "FileCheck2" : "Upload"} size={27} />
        <strong>
          {busy
            ? "Özet hesaplanıyor…"
            : checksumOnly
              ? "Bir dosya seç"
              : "APK dosyanı seç"}
        </strong>
        <span>Yalnız cihazında incelenir · en çok 32 MiB</span>
        <input
          aria-label={
            checksumOnly ? "SHA-256 için dosya seç" : "İncelemek için APK seç"
          }
          type="file"
          accept={checksumOnly ? undefined : ".apk"}
          onChange={select}
          disabled={busy}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="inspection-result">
          <span className="small-label">
            {checksumOnly ? "ÖZET HESAPLANDI" : "YALNIZ ZIP BAŞLIĞI UYGUN"}
          </span>
          <h3>{result.name}</h3>
          <p>{formatBytes(result.size)}</p>
          <label>
            SHA-256<code>{result.hash}</code>
          </label>
          {!checksumOnly && (
            <Notice icon="ShieldCheck">
              Bu sonuç APK yapısını, geliştiriciyi, izinleri veya imzayı
              doğrulamaz. Dosya kurmadı, açmadı ve ağa göndermedi.
            </Notice>
          )}
        </div>
      )}
      <Notice icon="LockKeyhole">
        {checksumOnly
          ? "SHA-256 bir bütünlük özetidir; dosyanın güvenli veya imzalı olduğunu kanıtlamaz."
          : "Bu tarayıcı APK kuramaz. Gerçek cihazda sistem yükleyicisi, özel kaynak izni ve son kullanıcı onayı gerekir. XAPK/APKS ve split paketler bu önizlemede yoktur."}
      </Notice>
    </div>
  );
}
export function Apps({ go }: PageProps) {
  const [query, setQuery] = useState("");
  return (
    <>
      <ScreenTitle title="Uygulamaların" onBack={() => go("home")} />
      <div className="page-body">
        {inNativeApp && (
          <NativeAction action="apps.open" className="primary-button">
            <Icon name="Grid2X2" size={18} /> Cihazda yüklü uygulamalar · gerçek
            simgeler
          </NativeAction>
        )}
        <div className="search-field">
          <Icon name="Search" />
          <input
            autoFocus
            aria-label="Uygulama ara"
            placeholder="Bir uygulama bul…"
            maxLength={80}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="section-line">
          <span>TÜM UYGULAMALAR</span>
          <span>
            {
              apps.filter((a) =>
                normalize(`${a.name} ${a.short} ${a.keywords || ""}`).includes(
                  normalize(query),
                ),
              ).length
            }
          </span>
        </div>
        <div className="drawer-grid">
          {apps
            .filter((a) =>
              normalize(`${a.name} ${a.short} ${a.keywords || ""}`).includes(
                normalize(query),
              ),
            )
            .map((app) => (
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
        {!apps.some((a) =>
          normalize(`${a.name} ${a.short} ${a.keywords || ""}`).includes(
            normalize(query),
          ),
        ) && <p className="empty-state">Burada böyle bir uygulama yok.</p>}
        <Notice>
          Burada yalnız önizleme uygulamaları listelenir. Yerel başlatıcı,
          cihazda yüklü ve başlatılabilir uygulamaları sistemden sorgular.
        </Notice>
      </div>
    </>
  );
}
export function Store(
  props: PageProps & { initialTab?: string; initialSelected?: string },
) {
  const { go, prefs, update } = props;
  const [tab, setTab] = useState(props.initialTab || "discover");
  const [selected, setSelected] = useState<(typeof catalog)[number] | null>(
    catalog.find((app) => app.id === props.initialSelected) || null,
  );
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("Tümü");
  const categories = ["Tümü", ...new Set(catalog.map((app) => app.category))];
  const filtered = catalog.filter(
    (app) =>
      (tab !== "wishlist" || prefs.wishlist.includes(app.id)) &&
      (category === "Tümü" || app.category === category) &&
      normalize(`${app.name} ${app.category} ${app.note}`).includes(
        normalize(query),
      ),
  );
  const wish = (id: string) =>
    update({
      wishlist: prefs.wishlist.includes(id)
        ? prefs.wishlist.filter((x) => x !== id)
        : [...prefs.wishlist, id].slice(0, 40),
    });
  return (
    <>
      <ScreenTitle
        title="Mağaza"
        onBack={() => go("home")}
        action={<span className="tiny-pill">SENİN SEÇİMİN</span>}
      />
      <div className="page-body">
        <NativeStoreActions />
        <div className="segmented">
          <button
            className={tab === "discover" ? "active" : ""}
            onClick={() => setTab("discover")}
          >
            Keşfet
          </button>
          <button
            className={tab === "wishlist" ? "active" : ""}
            onClick={() => setTab("wishlist")}
          >
            İstek listem
          </button>
          <button
            className={tab === "apk" ? "active" : ""}
            onClick={() => setTab("apk")}
          >
            APK incele
          </button>
        </div>
        {tab === "apk" ? (
          <ApkInspector />
        ) : (
          <>
            <div className="store-hero">
              <span className="eyebrow">24 UYGULAMA · 8 KATEGORİ</span>
              <h3>
                İyi uygulamalar.
                <br />
                Daha çok özgürlük.
              </h3>
              <p>İletişimden müziğe. Sana uyanı keşfet.</p>
              <div className="store-hero-art" aria-hidden="true">
                {catalog.slice(0, 4).map((app) => (
                  <AppBadge
                    key={app.id}
                    icon={app.icon}
                    color={app.color}
                    artwork={app.artwork}
                  />
                ))}
              </div>
            </div>
            <div className="search-field">
              <Icon name="Search" />
              <input
                placeholder="Katalogda ara"
                aria-label="Mağaza kataloğunda ara"
                value={query}
                maxLength={80}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div
              className="category-chips"
              role="group"
              aria-label="Mağaza kategorileri"
            >
              {categories.map((value) => (
                <button
                  key={value}
                  className={category === value ? "active" : ""}
                  aria-pressed={category === value}
                  onClick={() => setCategory(value)}
                >
                  {value}
                </button>
              ))}
            </div>
            <div className="section-line">
              <span>
                {tab === "wishlist" ? "SENİN LİSTEN" : "CEBİNE YAKIŞANLAR"}
              </span>
              <span aria-live="polite">{filtered.length} UYGULAMA</span>
            </div>
            <div className="store-list">
              {filtered.map((app) => (
                <article className="store-item" key={app.id}>
                  <AppBadge
                    icon={app.icon}
                    color={app.color}
                    artwork={app.artwork}
                    small
                  />
                  <button
                    className="store-item-title"
                    onClick={() => setSelected(app)}
                  >
                    <strong>{app.name}</strong>
                    <span>
                      {app.category} · {app.note}
                    </span>
                  </button>
                  <button
                    className={`icon-button ${prefs.wishlist.includes(app.id) ? "selected" : ""}`}
                    aria-label={`${app.name} ${prefs.wishlist.includes(app.id) ? "istek listesinden çıkar" : "istek listesine ekle"}`}
                    aria-pressed={prefs.wishlist.includes(app.id)}
                    onClick={() => wish(app.id)}
                  >
                    <Icon name="Heart" size={19} />
                  </button>
                  <button
                    className="get-button"
                    onClick={() => setSelected(app)}
                  >
                    İncele
                  </button>
                </article>
              ))}
            </div>
            {!filtered.length && (
              <p className="empty-state">
                {tab === "wishlist" && !prefs.wishlist.length
                  ? "Bir kalbe dokun. Seçtiklerin burada kalsın."
                  : "Bu aramada uygulama yok. Başka bir kategori veya isim dene."}
              </p>
            )}
            <Notice>
              Bu seçki açık kaynak ve diğer lisanslı uygulamaları birlikte
              gösterir. Simgeler bu uygulamayla yerel sunulur. Güncel
              sürüm/fiyat indirilmez; “İncele” resmî kaynağı açar, uygulama
              kurmaz.
            </Notice>
            <button className="full-row" onClick={() => go("google")}>
              <AppBadge icon="Globe2" color="white" small />
              <span>
                <strong>Google seçenekleri</strong>
                <small>Web kısayolları ve sertifikasyon sınırları</small>
              </span>
              <Icon name="ChevronRight" />
            </button>
          </>
        )}
      </div>
      {selected && (
        <Dialog title={selected.name} onClose={() => setSelected(null)}>
          <div className="app-detail">
            <AppBadge
              icon={selected.icon}
              color={selected.color}
              artwork={selected.artwork}
            />
            <h3>Önce kaynağına bakalım.</h3>
            <p>
              Bu önizleme uygulama indirmez veya kurmaz. Aşağıdaki düğme, ayrı
              sekmede geliştiricinin resmî sitesini açar.
            </p>
            <code>{selected.package}</code>
            <a
              className="primary-button"
              href={selected.url}
              rel="noopener noreferrer"
              target="_blank"
            >
              Resmî geliştiriciye git <Icon name="ExternalLink" size={17} />
            </a>
            {selected.play && inNativeApp && (
              <NativeAction
                action="google.play"
                args={{ package: selected.package }}
              >
                <Icon name="Play" size={16} /> Cihazdaki Play’de görüntüle
              </NativeAction>
            )}
            {selected.play && !inNativeApp && (
              <a
                className="secondary-button"
                href={`https://play.google.com/store/apps/details?id=${selected.package}`}
                rel="noopener noreferrer"
                target="_blank"
              >
                Google Play sayfası <Icon name="ExternalLink" size={16} />
              </a>
            )}
            <Notice>
              Bir paketin varlığı; cihazına uygun ABI, Google hizmeti, DRM veya
              banka uygulaması uyumluluğu garantisi değildir.
            </Notice>
          </div>
        </Dialog>
      )}
    </>
  );
}
export function Google({ go }: PageProps) {
  return (
    <>
      <ScreenTitle title="Google seçenekleri" onBack={() => go("home")} />
      <div className="page-body">
        {inNativeApp && (
          <NativeAction action="google.play" className="primary-button">
            <Icon name="Play" size={18} /> Cihazdaki Google Play’i aç
          </NativeAction>
        )}
        <div className="google-hero">
          <span className="google-mark">
            G<span>o</span>
            <i>o</i>gle
          </span>
          <h3>
            Alıştığın dünya,
            <br />
            senin kararın.
          </h3>
          <p>Hizmetlere web üzerinden ulaş. Hesabını bu önizlemeye girme.</p>
        </div>
        <div className="google-grid">
          {googleLinks.map((item) => (
            <a
              href={item.url}
              key={item.name}
              target="_blank"
              rel="noopener noreferrer"
            >
              <AppBadge icon={item.icon} color={item.color} />
              <span>{item.name}</span>
              <Icon name="ExternalLink" size={12} />
            </a>
          ))}
        </div>
        <Notice icon="ShieldCheck">
          Bunlar güvenli HTTPS web kısayollarıdır, kurulu Google uygulamaları
          değildir. Giriş yalnız Google’ın kendi sitesinde yapılır.
        </Notice>
        <div className="info-card">
          <span className="eyebrow">GERÇEK CİHAZ İÇİN</span>
          <h3>Play hizmetleri ayrı bir katman.</h3>
          <p>
            GMS/Play Store dağıtımı lisans ve cihaz sertifikasına bağlıdır.
            Tasarım, sertifikasız ROM’da Play Integrity, banka veya DRM
            uyumluluğu vaat etmez. Google paketleri bu depoda bulunmaz.
          </p>
        </div>
      </div>
    </>
  );
}
export function Culture({ prefs, update, go }: PageProps) {
  return (
    <>
      <ScreenTitle title="Koleksiyon" onBack={() => go("home")} />
      <div className="page-body">
        <p className="page-intro">Cebinde, senden bir manzara.</p>
        <div className="wallpaper-grid">
          {Object.entries(WALLPAPER_NAMES).map(([id, name]) => (
            <button
              key={id}
              className={`wallpaper-option ${prefs.wallpaper === id ? "chosen" : ""}`}
              onClick={() => update({ wallpaper: id })}
              aria-pressed={prefs.wallpaper === id}
              aria-label={`${name} duvar kâğıdını uygula`}
            >
              <img src={`/assets/${id}.webp`} alt="" loading="lazy" />
              <span>
                {name}
                {prefs.wallpaper === id && <Icon name="Check" size={16} />}
              </span>
            </button>
          ))}
        </div>
        <Notice>
          Seçim bu önizlemenin ana ekranına uygulanır. Görseller mevcut OğuzDows
          kültür koleksiyonundan türetilmiştir; gerçek kamera fotoğrafı iddiası
          yoktur.
        </Notice>
        <button className="primary-button" onClick={() => go("home")}>
          Ana ekranda gör <Icon name="ArrowRight" size={17} />
        </button>
      </div>
    </>
  );
}
export function Settings({
  prefs,
  update,
  go,
  onAbout,
  onReset,
}: { onAbout: () => void; onReset: () => void } & PageProps) {
  return (
    <>
      <ScreenTitle title="Sana göre" onBack={() => go("home")} />
      <div className="page-body">
        <NativeSettings />
        <div className="settings-hero">
          <AppBadge icon="SlidersHorizontal" color="mint" />
          <h3>
            Her detayında
            <br />
            biraz sen.
          </h3>
        </div>
        <span className="section-caption">GÖRÜNÜM</span>
        <div className="theme-options">
          {(["light", "dark"] as const).map((t) => (
            <button
              className={prefs.theme === t ? "chosen" : ""}
              key={t}
              onClick={() => update({ theme: t })}
              aria-pressed={prefs.theme === t}
            >
              <span className={`mini-ui ${t}`}>
                <i />
                <b />
                <b />
              </span>
              <span>
                {t === "light" ? "Gün ışığı" : "Gece mavisi"}
                {prefs.theme === t && <Icon name="Check" size={14} />}
              </span>
            </button>
          ))}
        </div>
        <div className="settings-row">
          <div>
            <strong>Senin rengin</strong>
            <small>Ortak yerel ekranlara uygulanır.</small>
          </div>
          <div className="accent-options">
            {(["sea", "copper", "plum"] as const).map((a) => (
              <button
                key={a}
                className={`accent-dot ${a}`}
                aria-label={`${a === "sea" ? "Boğaz" : a === "copper" ? "Bakır" : "Mürdüm"} vurgu rengi`}
                aria-pressed={prefs.accent === a}
                onClick={() => update({ accent: a })}
              >
                {prefs.accent === a && <Icon name="Check" size={13} />}
              </button>
            ))}
          </div>
        </div>
        <button
          className="settings-row button-row"
          onClick={() => go("culture")}
        >
          <div>
            <strong>Duvar kâğıdı</strong>
            <small>{WALLPAPER_NAMES[prefs.wallpaper]}</small>
          </div>
          <Icon name="ChevronRight" />
        </button>
        <div className="settings-row">
          <div>
            <strong>Kompakt düzen</strong>
            <small>Ana ekranda daha sıkı aralıklar.</small>
          </div>
          <Toggle
            label="Kompakt düzen"
            on={prefs.layout === "compact"}
            onChange={() =>
              update({
                layout: prefs.layout === "compact" ? "comfort" : "compact",
              })
            }
          />
        </div>
        <span className="section-caption">SANA VE CİHAZINA SAYGILI</span>
        <div className="settings-row">
          <div>
            <strong>Hafif profil</strong>
            <small>Gölge ve geçişleri azaltır.</small>
          </div>
          <Toggle
            label="Hafif profil"
            on={prefs.lowPower}
            onChange={() => update({ lowPower: !prefs.lowPower })}
          />
        </div>
        <div className="settings-row">
          <div>
            <strong>Hareketi azalt</strong>
            <small>Sistem erişilebilirlik tercihi de izlenir.</small>
          </div>
          <Toggle
            label="Hareketi azalt"
            on={prefs.reducedMotion}
            onChange={() => update({ reducedMotion: !prefs.reducedMotion })}
          />
        </div>
        <button className="settings-row button-row" onClick={onAbout}>
          <div>
            <strong>OğuzDows Mobile hakkında</strong>
            <small>Teknik bilgiler ve önizleme sınırları</small>
          </div>
          <Icon name="CircleHelp" />
        </button>
        <button className="text-button danger" onClick={onReset}>
          <Icon name="Trash2" size={15} /> Yalnız bu önizlemenin verilerini
          temizle
        </button>
      </div>
    </>
  );
}
export function Monitor({ prefs, update, go }: PageProps) {
  return (
    <>
      <ScreenTitle title="Cihazım" onBack={() => go("home")} />
      <div className="page-body">
        <div className="monitor-hero">
          <Icon name="Leaf" size={42} />
          <h3>
            Gösterişi sever.
            <br />
            İsrafı sevmez.
          </h3>
          <p>
            OğuzDows’un düşük kaynak yaklaşımı, mobilde de tasarımın merkezinde.
          </p>
        </div>
        <div className="settings-row">
          <div>
            <strong>Hafif profil</strong>
            <small>Efektler ve geçişler sadeleşir.</small>
          </div>
          <Toggle
            label="Hafif profil"
            on={prefs.lowPower}
            onChange={() => update({ lowPower: !prefs.lowPower })}
          />
        </div>
        {[
          ["Görsel yük", "Tek duvar kâğıdı; uygulamalar açılınca oluşturulur."],
          ["Arka plan", "Yeni indeksleyici veya sürekli animasyon yok."],
          ["Rıfkı", "Varsayılan yerel rehber. Mikrofon/arka plan dinleme yok."],
          ["Veriler", "Notlar ve görevler bu tarayıcının yerel deposunda."],
        ].map(([a, b]) => (
          <div className="resource-row" key={a}>
            <Icon name="Check" size={17} />
            <div>
              <strong>{a}</strong>
              <p>{b}</p>
            </div>
          </div>
        ))}
        <Notice>
          Gerçek CPU, RAM, şarj, modem ve pil ömrü ölçülmüyor. Hafif profil bu
          web arayüzünü etkiler; fiziksel cihaz tasarrufu veya belirli RAM
          kullanımı iddiası değildir.
        </Notice>
      </div>
    </>
  );
}
export function Files({ go }: PageProps) {
  return (
    <>
      <ScreenTitle title="Dosyalar" onBack={() => go("home")} />
      <div className="page-body">
        <div className="files-hero">
          <Icon name="FolderClosed" size={48} />
          <h3>Dosyaların sende kalsın.</h3>
          <p>Yalnızca senin seçtiğin dosya okunur.</p>
        </div>
        <ApkInspector checksumOnly />
        <Notice>
          Genel dosya sistemi taranmaz. Gerçek mobil sürümde klasörler ve
          belgeler sistem belge seçicisinin (SAF) verdiği izinlerle açılacak;
          tüm depolamaya erişim istenmeyecek.
        </Notice>
      </div>
    </>
  );
}
export function News({ prefs, update, go }: PageProps) {
  const [tab, setTab] = useState("all");
  const [selected, setSelected] = useState<(typeof articles)[number] | null>(
    null,
  );
  function open(article: (typeof articles)[number]) {
    setSelected(article);
    if (!prefs.read.includes(article.id))
      update({ read: [...prefs.read, article.id].slice(-100) });
  }
  function save(id: string) {
    update({
      saved: prefs.saved.includes(id)
        ? prefs.saved.filter((x) => x !== id)
        : [...prefs.saved, id].slice(-40),
    });
  }
  return (
    <>
      <ScreenTitle
        title="Biraz keşfet"
        eyebrow="HABER & OKUMA"
        onBack={() => go("home")}
      />
      <div className="page-body">
        <div className="segmented">
          <button
            className={tab === "all" ? "active" : ""}
            onClick={() => setTab("all")}
          >
            Senin için
          </button>
          <button
            className={tab === "saved" ? "active" : ""}
            onClick={() => setTab("saved")}
          >
            Kitaplığım
          </button>
          <button
            className={tab === "unread" ? "active" : ""}
            onClick={() => setTab("unread")}
          >
            Okunmamış
          </button>
        </div>
        <span className="offline-label">
          <span /> Çevrimdışı seçki · özgün örnek metinler
        </span>
        <div className="article-list">
          {articles
            .filter(
              (a) =>
                tab === "all" ||
                (tab === "saved"
                  ? prefs.saved.includes(a.id)
                  : !prefs.read.includes(a.id)),
            )
            .map((article) => (
              <article className="article-card" key={article.id}>
                <button className="article-open" onClick={() => open(article)}>
                  <img
                    src={`/assets/${article.image}.webp`}
                    alt=""
                    loading="lazy"
                  />
                  <span className="article-category">
                    {article.category} <small>{article.time}</small>
                  </span>
                  <h3>{article.title}</h3>
                  <p>{article.subtitle}</p>
                </button>
                <div className="article-meta">
                  <span>
                    {prefs.read.includes(article.id)
                      ? "Okundu"
                      : "Yeni bir okuma"}
                  </span>
                  <button
                    className={`icon-button ${prefs.saved.includes(article.id) ? "selected" : ""}`}
                    aria-label={`${article.title} ${prefs.saved.includes(article.id) ? "kitaplıktan çıkar" : "kitaplığa ekle"}`}
                    aria-pressed={prefs.saved.includes(article.id)}
                    onClick={() => save(article.id)}
                  >
                    <Icon name="Bookmark" size={18} />
                  </button>
                </div>
              </article>
            ))}
        </div>
        {tab === "saved" && !prefs.saved.length && (
          <p className="empty-state">
            Sakladığın okumalar burada, ağ olmadan da yanında.
          </p>
        )}
      </div>
      {selected && (
        <Dialog title="Okuma molası" onClose={() => setSelected(null)}>
          <div className="reader">
            <img src={`/assets/${selected.image}.webp`} alt="" />
            <span className="eyebrow">{selected.category} · ÖRNEK İÇERİK</span>
            <h3>{selected.title}</h3>
            {selected.body.split("\n\n").map((text, i) => (
              <p key={i}>{text}</p>
            ))}
            <button
              className="primary-button"
              onClick={() => save(selected.id)}
            >
              <Icon name="Bookmark" size={17} />
              {prefs.saved.includes(selected.id)
                ? "Kitaplığımdan çıkar"
                : "Kitaplığıma ekle"}
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                downloadText(
                  `${selected.title}\n\n${selected.body}\n\nOğuzDows Mobile · özgün çevrimdışı örnek metin\n`,
                  `${selected.id}.txt`,
                )
              }
            >
              <Icon name="Download" size={17} /> TXT olarak dışa aktar
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
export function Workbench(props: PageProps & { initialTool?: string }) {
  const { prefs, update, go, toast } = props;
  const [tool, setTool] = useState(props.initialTool || "");
  const [query, setQuery] = useState("");
  const selected = TOOLS.find((x) => x.id === tool);
  return (
    <>
      <ScreenTitle
        title={selected?.name || "Atölye"}
        eyebrow="KÜÇÜK ARAÇLAR, BÜYÜK FİKİRLER"
        onBack={() => (selected ? setTool("") : go("home"))}
      />
      <div className="page-body">
        {!selected ? (
          <>
            <p className="page-intro">İhtiyacın kadar. Tam elinin altında.</p>
            <div className="search-field">
              <Icon name="Search" />
              <input
                placeholder="16 araç içinde ara…"
                aria-label="Atölye aracı ara"
                value={query}
                maxLength={80}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="section-line">
              <span>10 ETKİLEŞİMLİ · 6 YEREL ENTEGRASYON</span>
            </div>
            <div className="tool-grid">
              {TOOLS.filter((t) =>
                normalize(t.name).includes(normalize(query)),
              ).map((t) => (
                <button
                  key={t.id}
                  className="tool-card"
                  onClick={() => setTool(t.id)}
                >
                  <Icon name={t.icon} size={23} />
                  <strong>{t.name}</strong>
                  <span>{t.description}</span>
                  {!t.interactive && <small>Yerel aşama</small>}
                </button>
              ))}
            </div>
          </>
        ) : !selected.interactive ? (
          <div className="native-pending">
            <AppBadge icon={selected.icon} color="mint" />
            <h3>{selected.name}, doğru yerde.</h3>
            <p>
              Bu aracın güvenli mobil karşılığı yerel sistem entegrasyonu
              gerektiriyor. Tarayıcıda dosya sistemi, başka uygulamanın
              başlangıcı veya sistem izinleri üzerinde kontrolümüz yok.
            </p>
            <Notice>
              Bu ekran işlevi tamamlanmış gibi göstermez. Belge seçici,
              önizleme/onay, çakışma koruması ve geri alma gereklilikleri mobil
              özellik haritasında tanımlı.
            </Notice>
            <button className="secondary-button" onClick={() => setTool("")}>
              Diğer araçlara dön
            </button>
          </div>
        ) : (
          <ToolContent {...props} key={tool} tool={tool} toast={toast} />
        )}
      </div>
    </>
  );
}
function ToolContent({
  tool,
  prefs,
  update,
  toast,
}: PageProps & { tool: string }) {
  const [input, setInput] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [kind, setKind] = useState("km-m");
  const [color, setColor] = useState("#24675f");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (tool !== "clocks") return;
    let timer: ReturnType<typeof setInterval> | undefined;
    const sync = () => {
      clearInterval(timer);
      if (!document.hidden) {
        setTick((x) => x + 1);
        timer = setInterval(() => setTick((x) => x + 1), 60000);
      }
    };
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", sync);
    };
  }, [tool]);
  const run = (fn: () => unknown) => {
    try {
      setResult(String(fn()));
      setError("");
    } catch (err) {
      setError((err as Error).message);
      setResult("");
    }
  };
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Yalnız seçtiğin metin panoya kopyalandı.");
    } catch {
      toast("Pano izni alınamadı. Metni elle seçebilirsin.");
    }
  }
  if (tool === "tasks")
    return (
      <>
        <div className="tool-heading">
          <Icon name="ListTodo" size={34} />
          <h3>Bir küçük adım.</h3>
          <p>
            {prefs.tasks.filter((t) => t.done).length} / {prefs.tasks.length}{" "}
            tamamlandı · yalnız bu tarayıcıda
          </p>
        </div>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim() && prefs.tasks.length < 100) {
              update({
                tasks: [
                  ...prefs.tasks,
                  {
                    id: crypto.randomUUID(),
                    title: input.trim().slice(0, 180),
                    done: false,
                  },
                ],
              });
              setInput("");
            }
          }}
        >
          <input
            value={input}
            maxLength={180}
            aria-label="Yeni görev"
            placeholder="Bugün ne yapmak istersin?"
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            className="primary-square"
            aria-label="Görev ekle"
            disabled={!input.trim() || prefs.tasks.length >= 100}
          >
            <Icon name="Plus" />
          </button>
        </form>
        <div className="task-list">
          {prefs.tasks.map((t) => (
            <div className={`task-row ${t.done ? "done" : ""}`} key={t.id}>
              <button
                className="task-check"
                role="checkbox"
                aria-checked={t.done}
                aria-label={`${t.title} tamamlandı`}
                onClick={() =>
                  update({
                    tasks: prefs.tasks.map((x) =>
                      x.id === t.id ? { ...x, done: !x.done } : x,
                    ),
                  })
                }
              >
                {t.done && <Icon name="Check" size={15} />}
              </button>
              <span>{t.title}</span>
              <button
                className="icon-button"
                aria-label={`${t.title} görevini sil`}
                onClick={() =>
                  update({ tasks: prefs.tasks.filter((x) => x.id !== t.id) })
                }
              >
                <Icon name="X" size={17} />
              </button>
            </div>
          ))}
        </div>
        <Notice>
          En çok 100 görev. Hatırlatıcı veya sistem takvim erişimi yoktur.
        </Notice>
      </>
    );
  if (tool === "notes")
    return (
      <>
        <div className="tool-heading">
          <Icon name="NotebookPen" size={32} />
          <h3>Aklında kalmasın.</h3>
          <p>Yazdıkların bu tarayıcıda saklanır; şifreli kasa değil.</p>
        </div>
        <textarea
          className="note-paper"
          aria-label="Defter notu"
          maxLength={16384}
          placeholder="Bir fikir, bir tarif, küçük bir hatırlatma…"
          value={prefs.notes}
          onChange={(e) => update({ notes: e.target.value })}
        />
        <div className="section-line">
          <span>{prefs.notes.length} / 16384 KARAKTER</span>
          <button
            className="text-button"
            onClick={() => downloadText(prefs.notes, "oguzdows-defter.txt")}
          >
            <Icon name="Download" size={14} /> TXT
          </button>
        </div>
      </>
    );
  if (tool === "checksum") return <ApkInspector checksumOnly />;
  if (tool === "clocks")
    return (
      <div className="clocks" data-minute={tick}>
        {[
          ["İstanbul", "Europe/Istanbul"],
          ["Londra", "Europe/London"],
          ["Tokyo", "Asia/Tokyo"],
          ["New York", "America/New_York"],
        ].map(([name, tz]) => (
          <div className="clock-card" key={tz}>
            <span>{name}</span>
            <strong>
              {new Intl.DateTimeFormat("tr-TR", {
                hour: "2-digit",
                minute: "2-digit",
                timeZone: tz,
              }).format(new Date())}
            </strong>
            <small>{tz}</small>
          </div>
        ))}
        <Notice>
          Tarayıcının gerçek saati ve saat dilimi verisi kullanılır. Ağ veya
          konum izni gerekmez. Sayfa gizliyken zamanlayıcı durur.
        </Notice>
      </div>
    );
  if (tool === "snippets")
    return (
      <>
        <p className="page-intro">Sık kullandıkların, bir dokunuş uzakta.</p>
        <textarea
          className="tool-input"
          maxLength={300}
          aria-label="Yeni metin parçası"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Bir cümle ekle…"
        />
        <button
          className="primary-button"
          disabled={!input.trim() || prefs.snippets.length >= 40}
          onClick={() => {
            update({
              snippets: [...new Set([...prefs.snippets, input.trim()])].slice(
                0,
                40,
              ),
            });
            setInput("");
          }}
        >
          Rafa ekle <Icon name="Plus" size={17} />
        </button>
        {prefs.snippets.map((s, i) => (
          <div className="snippet-row" key={i}>
            <p>{s}</p>
            <button
              className="icon-button"
              aria-label={`${i + 1}. metni kopyala`}
              onClick={() => copy(s)}
            >
              <Icon name="Copy" size={17} />
            </button>
            <button
              className="icon-button"
              aria-label={`${i + 1}. metni kaldır`}
              onClick={() =>
                update({ snippets: prefs.snippets.filter((_, j) => j !== i) })
              }
            >
              <Icon name="X" size={17} />
            </button>
          </div>
        ))}
        <Notice>
          En çok 40 parça / 300 karakter. Pano izlenmez; yalnız düğmeyle
          kopyalanır.
        </Notice>
      </>
    );
  if (tool === "color")
    return (
      <>
        <div className="color-sample" style={{ background: color }}>
          <span>Biraz renk.</span>
        </div>
        <label className="form-label">
          Bir renk seç
          <input
            type="color"
            value={color}
            aria-label="Kontrast rengi"
            onChange={(e) => setColor(e.target.value)}
          />
        </label>
        <div className="result-card">
          <span>BEYAZLA WCAG KONTRASTI</span>
          <strong>{contrast(color).toFixed(2)} : 1</strong>
          <p>
            {contrast(color) >= 4.5
              ? "AA normal metin eşiğini karşılıyor."
              : "AA normal metin için 4.5 : 1 gerekir."}
          </p>
          <code>{color.toUpperCase()}</code>
        </div>
      </>
    );
  return (
    <>
      <div className="tool-heading">
        <h3>
          {tool === "calculator"
            ? "Hesabın burada."
            : tool === "units"
              ? "Küçük bir dönüşüm."
              : tool === "json"
                ? "Düzen, birkaç satır ötede."
                : "Kelimelere alan aç."}
        </h3>
      </div>
      {tool === "calculator" ? (
        <input
          className="calculation-input"
          aria-label="Hesap ifadesi"
          maxLength={128}
          placeholder="(24 + 18) × 2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") run(() => calculate(input));
          }}
        />
      ) : tool === "units" ? (
        <>
          <input
            className="calculation-input"
            aria-label="Dönüştürülecek değer"
            inputMode="decimal"
            maxLength={30}
            placeholder="1"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <select
            className="tool-select"
            aria-label="Dönüşüm türü"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="km-m">Kilometre → metre</option>
            <option value="m-km">Metre → kilometre</option>
            <option value="c-f">Celsius → Fahrenheit</option>
            <option value="mib-mb">MiB → MB</option>
          </select>
        </>
      ) : (
        <textarea
          className="tool-input"
          aria-label={tool === "json" ? "JSON girdisi" : "İşlenecek metin"}
          maxLength={16384}
          placeholder={
            tool === "json" ? ' { "merhaba": "dünya" }' : "Metnini buraya yaz…"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
      )}
      <div className="tool-actions">
        {tool === "calculator" ? (
          <button
            className="primary-button"
            onClick={() => run(() => calculate(input))}
          >
            Hesapla <Icon name="Calculator" size={17} />
          </button>
        ) : tool === "units" ? (
          <button
            className="primary-button"
            onClick={() =>
              run(() =>
                Number(convert(input.replace(",", "."), kind).toPrecision(12)),
              )
            }
          >
            Dönüştür
          </button>
        ) : tool === "json" ? (
          <button
            className="primary-button"
            onClick={() =>
              run(() => {
                if (!input.trim()) throw new Error("Önce JSON yaz.");
                const parsed = JSON.parse(input);
                let nodes = 0;
                const bound = (v: unknown, depth = 0) => {
                  if (depth > 20 || ++nodes > 4000)
                    throw new Error("JSON fazla derin veya büyük.");
                  if (v && typeof v === "object")
                    Object.values(v).forEach((x) => bound(x, depth + 1));
                };
                bound(parsed);
                return JSON.stringify(parsed, null, 2);
              })
            }
          >
            Doğrula ve biçimlendir
          </button>
        ) : (
          <>
            <button
              className="secondary-button"
              onClick={() => run(() => input.toLocaleUpperCase("tr-TR"))}
            >
              BÜYÜK
            </button>
            <button
              className="secondary-button"
              onClick={() => run(() => input.toLocaleLowerCase("tr-TR"))}
            >
              küçük
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                run(() =>
                  [
                    ...new Set(
                      input
                        .split("\n")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    ),
                  ].join("\n"),
                )
              }
            >
              Satırları temizle
            </button>
          </>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result !== "" && (
        <div className="result-card" role="status">
          <span>SONUÇ</span>
          <pre>{result}</pre>
          <button className="text-button" onClick={() => copy(result)}>
            <Icon name="Copy" size={15} /> Kopyala
          </button>
        </div>
      )}
      <Notice>
        {tool === "calculator"
          ? "Sınırlı, kayan noktalı aritmetik. Kod çalıştırmaz; finansal hassasiyetli hesap makinesi değildir."
          : tool === "json"
            ? "En çok 16 KiB karakter / 20 katman / 4000 düğüm. Yinelenen anahtar denetimi bu önizlemede yok; son değer kalır."
            : "İşlem yalnız bu sayfadaki girdiye uygulanır; dosyalarını değiştirmez."}
      </Notice>
    </>
  );
}
