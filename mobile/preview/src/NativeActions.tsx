import { useState } from "react";
import { inNativeApp, nativeRequest, useNativeStatus } from "./native";
import { Icon, Notice } from "./ui";

export function NativeAction({
  action,
  args = {},
  children,
  className = "secondary-button",
}: {
  action: string;
  args?: Record<string, unknown>;
  children: React.ReactNode;
  className?: string;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!inNativeApp) return null;
  return (
    <>
      <button
        className={className}
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            await nativeRequest(action, args);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {children}
      </button>
      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}
    </>
  );
}
export function NativeStoreActions() {
  if (!inNativeApp) return null;
  return (
    <section className="native-store-card">
      <span className="eyebrow">GERÇEK CİHAZ · AYRI GÜVEN YOLLARI</span>
      <h3>Seçkiden daha fazlası.</h3>
      <p>
        İmzalı F-Droid kataloğunda ara; API/ABI sürüm filtresi, yüklü sürüm
        karşılaştırması, SHA-256 doğrulaması ve onaylı sistem yükleyicisini
        kullan.
      </p>
      <NativeAction action="store.open" className="primary-button">
        <Icon name="ShoppingBag" size={18} /> Canlı katalog ve güncellemeler
      </NativeAction>
      <div className="native-action-row">
        <NativeAction action="google.play">
          <Icon name="Play" size={16} /> Cihazdaki Google Play
        </NativeAction>
        <NativeAction action="apk.pick">
          <Icon name="Upload" size={16} /> Yerel APK
        </NativeAction>
      </div>
      <p>
        Buradaki 24 kart seçkidir; canlı sürüm sonucu değildir. Otomatik
        indirme/kurulum yok. Play/GMS bu pakete dahil değil.
      </p>
    </section>
  );
}
export function NativeSettings() {
  const { status } = useNativeStatus();
  if (!inNativeApp) return null;
  return (
    <section className="native-role-panel">
      <div className="section-line">
        <span>YEREL UYGULAMA · {status?.version || "DURUM OKUNUYOR"}</span>
      </div>
      <div className="native-action-row">
        <NativeAction action="role.request" args={{ role: "home" }}>
          Ana ekran olarak seç
        </NativeAction>
        <NativeAction action="role.request" args={{ role: "assistant" }}>
          Rıfkı’yı yardımcı seç
        </NativeAction>
        <NativeAction action="settings.open" args={{ panel: "defaults" }}>
          Varsayılan uygulamalar
        </NativeAction>
        <NativeAction action="settings.open" args={{ panel: "app" }}>
          Sistem izinleri / uygulama verisi
        </NativeAction>
      </div>
      <Notice icon="ShieldCheck">
        Görünüm, OğuzDows’un zengin arayüzü ve yerel Mağaza/uygulama/APK
        ekranlarında eşleşir; başka üreticinin uygulama temasını zorla
        değiştirmez. Bu bir başlatıcı/Telefon/SMS test APK’sıdır; cihaz ROM’u
        veya GMS sertifikası değildir.
      </Notice>
    </section>
  );
}
