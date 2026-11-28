import { useEffect, useState } from "react";
import type { PageProps } from "./Screens";
import { NativeAction } from "./NativeActions";
import { nativeRequest, refreshNativeStatus, useNativeStatus } from "./native";
import { Dialog, Icon, Nazar, Notice } from "./ui";

export function NativeControlCenter({
  prefs,
  update,
  toast,
  onClose,
  onPower,
}: PageProps & { onClose: () => void; onPower: () => void }) {
  const { status, error } = useNativeStatus();
  const [volume, setVolume] = useState<number | null>(null);
  useEffect(() => {
    if (typeof status?.mediaVolume === "number") setVolume(status.mediaVolume);
  }, [status?.mediaVolume]);
  async function setSystemVolume(value: number) {
    setVolume(value);
    try {
      await nativeRequest("device.volume", { value });
      await refreshNativeStatus();
    } catch (err) {
      toast((err as Error).message);
    }
  }
  return (
    <Dialog title="Denetim merkezi" onClose={onClose} placement="top">
      <div className="control-heading">
        <div>
          <span className="eyebrow">CİHAZINDAN OKUNAN GERÇEK DURUM</span>
          <p>
            Pil {status?.battery == null ? "okunamadı" : `%${status.battery}`} ·
            API {status?.sdk ?? "—"}
          </p>
        </div>
        <button
          className="icon-button"
          aria-label="Güç menüsü"
          onClick={onPower}
        >
          <Nazar size={29} power />
        </button>
      </div>
      <div className="quick-grid control-tiles">
        {[
          { panel: "wifi", label: "Wi-Fi ayarları", icon: "Wifi" },
          {
            panel: "bluetooth",
            label: "Bluetooth ayarları",
            icon: "Bluetooth",
          },
          { panel: "airplane", label: "Uçak modu ayarları", icon: "Plane" },
          { panel: "focus", label: "Odak ayarları", icon: "Moon" },
        ].map((item) => (
          <NativeAction
            key={item.panel}
            className="native-setting-tile"
            action="settings.open"
            args={{ panel: item.panel }}
          >
            <Icon name={item.icon} size={23} />
            <strong>{item.label}</strong>
            <span>Sistem panelini aç</span>
          </NativeAction>
        ))}
        <button
          className={prefs.theme === "dark" ? "on" : ""}
          role="switch"
          aria-label="Koyu görünüm"
          aria-checked={prefs.theme === "dark"}
          onClick={() =>
            update({ theme: prefs.theme === "dark" ? "light" : "dark" })
          }
        >
          <Icon name={prefs.theme === "dark" ? "Moon" : "Sun"} size={23} />
          <strong>Görünüm</strong>
          <span>{prefs.theme === "dark" ? "Gece mavisi" : "Gün ışığı"}</span>
        </button>
        <button
          className={prefs.lowPower ? "on" : ""}
          aria-pressed={prefs.lowPower}
          onClick={() => update({ lowPower: !prefs.lowPower })}
        >
          <Icon name="Leaf" size={23} />
          <strong>Hafif profil</strong>
          <span>Yalnız arayüz efektleri</span>
        </button>
      </div>
      <div className="control-slider-card">
        <div className="control-slider-title">
          <span>
            <Icon name="Sun" size={17} /> Bu uygulamanın ekran parlaklığı
          </span>
          <output>{prefs.brightness}%</output>
        </div>
        <input
          type="range"
          aria-label="Uygulama parlaklığı"
          min={25}
          max={100}
          value={prefs.brightness}
          onChange={(e) => update({ brightness: Number(e.target.value) })}
        />
        <div className="control-slider-title">
          <span>
            <Icon name="Volume2" size={17} /> Sistem medya sesi
          </span>
          <output>{volume == null ? "Okunuyor" : `${volume}%`}</output>
        </div>
        <div className="volume-controls">
          <button
            className="icon-button"
            aria-label="Sistem sesini azalt"
            disabled={volume == null || volume <= 0}
            onClick={() =>
              void setSystemVolume(Math.max(0, (volume ?? 0) - 10))
            }
          >
            <Icon name="Minus" size={18} />
          </button>
          <input
            type="range"
            aria-label="Sistem medya sesi"
            min={0}
            max={100}
            value={volume ?? 0}
            disabled={volume == null}
            onChange={(e) => setVolume(Number(e.target.value))}
            onPointerUp={(e) =>
              void setSystemVolume(Number(e.currentTarget.value))
            }
            onKeyUp={(e) => void setSystemVolume(Number(e.currentTarget.value))}
          />
          <button
            className="icon-button"
            aria-label="Sistem sesini artır"
            disabled={volume == null || volume >= 100}
            onClick={() =>
              void setSystemVolume(Math.min(100, (volume ?? 0) + 10))
            }
          >
            <Icon name="Plus" size={18} />
          </button>
        </div>
        <NativeAction action="settings.open" args={{ panel: "volume" }}>
          Tüm sistem ses kanalları
        </NativeAction>
      </div>
      {error && (
        <p className="error" role="status">
          {error}
        </p>
      )}
      <Notice icon="SlidersHorizontal">
        Medya sesi AudioManager’dan okunur ve medya kanalına uygulanır;
        arama/zil sesi ayrı sistem panelindedir. Parlaklık yalnız bu uygulamanın
        penceresini etkiler. Radyo düğmeleri sahte açık/kapalı durumu göstermez;
        gerçek sistem ayarını açar.
      </Notice>
    </Dialog>
  );
}
