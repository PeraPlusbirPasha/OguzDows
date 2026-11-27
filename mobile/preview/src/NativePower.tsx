import { NativeAction } from "./NativeActions";
import { inNativeApp } from "./native";
import { Icon, Notice } from "./ui";

export function NativePower() {
  if (!inNativeApp) return null;
  return (
    <div className="native-power-actions">
      <NativeAction
        action="settings.open"
        args={{ panel: "battery" }}
        className="primary-button"
      >
        <Icon name="Battery" size={19} /> Gerçek pil ve güç ayarları
      </NativeAction>
      <NativeAction action="settings.open" args={{ panel: "display" }}>
        <Icon name="Sun" size={18} /> Ekran ayarları
      </NativeAction>
      <Notice icon="ShieldCheck">
        Nazar boncuğu OğuzDows’un güç simgesidir. Normal bir uygulama cihazı
        güvenle kapatamaz, yeniden başlatamaz veya güvenlik kilidi koyamaz.
        Gerçek güç/kilit menüsü için cihazın fiziksel düğmesini kullan;
        kapatılmış veya kilitlenmiş gibi gösterilmez.
      </Notice>
    </div>
  );
}
