import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./Screens";
import { Dialog, Icon, Nazar, Notice } from "./ui";

/** A brief, user-triggered preview sound, never a system-volume or telephony API. */
export function ControlCenter({
  prefs,
  update,
  go,
  toast,
  onClose,
  onPower,
}: PageProps & { onClose: () => void; onPower: () => void }) {
  const context = useRef<AudioContext | null>(null);
  const [playing, setPlaying] = useState(false);
  const effectiveVolume = prefs.muted ? 0 : prefs.volume;
  useEffect(
    () => () => {
      const active = context.current;
      context.current = null;
      void active?.close().catch(() => {});
    },
    [],
  );
  useEffect(() => {
    if (context.current && (prefs.muted || prefs.volume === 0)) {
      void context.current.close().catch(() => {});
      context.current = null;
      setPlaying(false);
    }
  }, [prefs.muted, prefs.volume]);
  async function previewSound() {
    if (!effectiveVolume) {
      toast("Önizleme sesi kapalı. Sesi açarak yeniden dene.");
      return;
    }
    try {
      if (context.current) await context.current.close();
      const audio = new AudioContext();
      context.current = audio;
      await audio.resume();
      const oscillator = audio.createOscillator(),
        gain = audio.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(523.25, audio.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(
        659.25,
        audio.currentTime + 0.16,
      );
      gain.gain.setValueAtTime(0, audio.currentTime);
      gain.gain.linearRampToValueAtTime(
        (0.075 * effectiveVolume) / 100,
        audio.currentTime + 0.025,
      );
      gain.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + 0.32);
      oscillator.connect(gain);
      gain.connect(audio.destination);
      setPlaying(true);
      oscillator.onended = () => {
        void audio.close().catch(() => {});
        if (context.current === audio) {
          context.current = null;
          setPlaying(false);
        }
      };
      oscillator.start();
      oscillator.stop(audio.currentTime + 0.35);
    } catch {
      setPlaying(false);
      toast(
        "Tarayıcı ses oynatmaya izin vermedi. Müzik uygulamasında kendi dosyanı da deneyebilirsin.",
      );
    }
  }
  const volume = (next: number) =>
    update({ volume: Math.max(0, Math.min(100, next)), muted: next <= 0 });
  return (
    <Dialog title="Denetim merkezi" onClose={onClose} placement="top">
      <div className="control-heading">
        <div>
          <span className="eyebrow">HER ŞEY ELİNİN ALTINDA</span>
          <p>Kaydır. Ayarla. Devam et.</p>
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
        {(
          [
            { key: "wifi", label: "Wi-Fi", icon: "Wifi" },
            { key: "bluetooth", label: "Bluetooth", icon: "Bluetooth" },
            { key: "airplane", label: "Uçak modu", icon: "Plane" },
            { key: "focus", label: "Odak", icon: "Moon" },
          ] as const
        ).map((item) => (
          <button
            key={item.key}
            className={prefs[item.key] ? "on" : ""}
            aria-pressed={prefs[item.key]}
            onClick={() => update({ [item.key]: !prefs[item.key] })}
          >
            <Icon name={item.icon} size={23} />
            <strong>{item.label}</strong>
            <span>{prefs[item.key] ? "Açık" : "Kapalı"} · örnek</span>
          </button>
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
          <span>{prefs.lowPower ? "Efektler sade" : "Efektler açık"}</span>
        </button>
      </div>
      <div className="control-slider-card">
        <div className="control-slider-title">
          <span>
            <Icon name="Sun" size={17} /> Önizleme parlaklığı
          </span>
          <output>{prefs.brightness}%</output>
        </div>
        <input
          type="range"
          aria-label="Önizleme parlaklığı"
          min={25}
          max={100}
          step={1}
          value={prefs.brightness}
          onChange={(e) => update({ brightness: Number(e.target.value) })}
        />
        <div className="control-slider-title">
          <span>
            <Icon name={effectiveVolume ? "Volume2" : "VolumeX"} size={17} />{" "}
            Medya sesi
          </span>
          <output>{prefs.muted ? "Sessiz" : `${prefs.volume}%`}</output>
        </div>
        <div className="volume-controls">
          <button
            className="icon-button"
            aria-label="Sesi azalt"
            onClick={() => volume(prefs.volume - 10)}
            disabled={prefs.volume === 0}
          >
            <Icon name="Minus" size={18} />
          </button>
          <input
            type="range"
            aria-label="Medya sesi"
            min={0}
            max={100}
            step={1}
            value={prefs.volume}
            onChange={(e) => volume(Number(e.target.value))}
          />
          <button
            className="icon-button"
            aria-label="Sesi artır"
            onClick={() => volume(prefs.volume + 10)}
            disabled={prefs.volume === 100}
          >
            <Icon name="Plus" size={18} />
          </button>
        </div>
        <div className="control-audio-actions">
          <button
            aria-label={prefs.muted ? "Sesi aç" : "Sesi kapat"}
            aria-pressed={prefs.muted}
            onClick={() =>
              update({
                muted: !prefs.muted,
                volume: !prefs.muted || prefs.volume ? prefs.volume : 55,
              })
            }
          >
            <Icon name={prefs.muted ? "VolumeX" : "Volume2"} size={17} />
            {prefs.muted ? "Sesi aç" : "Sessize al"}
          </button>
          <button onClick={previewSound} disabled={playing}>
            <Icon name="Play" size={15} />
            {playing ? "Çalıyor…" : "Sesi dene"}
          </button>
        </div>
      </div>
      <button className="control-settings" onClick={() => go("settings")}>
        <Icon name="Settings2" size={19} />
        <span>Tüm ayarlar</span>
        <Icon name="ChevronRight" size={17} />
      </button>
      <Notice icon="SlidersHorizontal">
        Ses, bu önizlemede oynattığın medyaya; parlaklık, bu arayüze uygulanır.
        Anahtarlar gerçek Wi-Fi, Bluetooth veya sistem sesini değiştirmez.
        Saat/pil/radyo göstergeleri örnektir.
      </Notice>
    </Dialog>
  );
}
