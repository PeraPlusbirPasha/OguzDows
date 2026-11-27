import { useEffect, useSyncExternalStore } from "react";

const ORIGIN = "https://appassets.androidplatform.net";
export const inNativeApp = location.origin === ORIGIN;

type Transport = {
  postMessage: (data: string) => void;
  onmessage?: (event: { data: string }) => void;
};
declare global {
  interface Window {
    OguzPlatform?: Transport;
  }
}
export type NativeCall = {
  id: string;
  state: number;
  label: string;
  number: string;
  canHold: boolean;
  muted: boolean;
  speaker: boolean;
  speakerAvailable: boolean;
  count: number;
};
export type NativeStatus = {
  platform: "android";
  version: string;
  sdk: number;
  callingAvailable: boolean;
  smsAvailable: boolean;
  dialerRoleAvailable: boolean;
  smsRoleAvailable: boolean;
  dialerRole: boolean;
  smsRole: boolean;
  phonePermission: boolean;
  smsPermission: boolean;
  notificationPermission: boolean;
  notificationsEnabled: boolean;
  smsSubscription: number;
  battery: number | null;
  mediaVolume: number | null;
  call: NativeCall | null;
  mmsNotices: number;
  modelConnected: false;
  mmsSupported: false;
  rcsSupported: false;
  gmsBundled: false;
};
export type NativeSms = {
  id: number;
  number: string;
  body: string;
  date: number;
  type: number;
  status: number;
  errorCode: number;
  read: boolean;
};
const requests = new Map<
  string,
  {
    resolve: (result: unknown) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  }
>();
const subscribers = new Set<() => void>();
let current: NativeStatus | null = null;
let statusRequest: Promise<NativeStatus> | null = null;
let statusError = "";
let snapshot: { status: NativeStatus | null; error: string } = {
  status: current,
  error: statusError,
};
function emit() {
  snapshot = { status: current, error: statusError };
  subscribers.forEach((listener) => listener());
}
if (inNativeApp && window.OguzPlatform) {
  window.OguzPlatform.onmessage = (event) => {
    if (typeof event.data !== "string" || event.data.length > 2_000_000) return;
    try {
      const response = JSON.parse(event.data);
      const request = requests.get(response.id);
      if (!request || typeof response.ok !== "boolean") return;
      clearTimeout(request.timer);
      requests.delete(response.id);
      if (response.ok) request.resolve(response.result);
      else
        request.reject(
          new Error(
            typeof response.error === "string"
              ? response.error
              : "Yerel işlem tamamlanamadı.",
          ),
        );
    } catch {
      // Invalid messages never become platform state or execute code.
    }
  };
}
export function nativeRequest<T = unknown>(
  action: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  const transport = window.OguzPlatform;
  if (!inNativeApp || !transport)
    return Promise.reject(
      new Error(
        "Güvenli yerel köprü yok. Tarayıcı SIM erişimi sağlayamaz; yerel uygulamada sistem WebView güncellemesi gerekebilir.",
      ),
    );
  if (requests.size >= 12)
    return Promise.reject(new Error("Önce açık sistem işlemini tamamla."));
  const id = crypto.randomUUID();
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      requests.delete(id);
      reject(
        new Error(
          "Sistem yanıtı alınmadı. İşlem başarılı sayılmadı; arama/SMS için otomatik tekrar yapılmaz.",
        ),
      );
    }, 180_000);
    requests.set(id, {
      resolve: (result) => resolve(result as T),
      reject,
      timer,
    });
    try {
      const data = JSON.stringify({ id, action, args });
      if (data.length > 16384) throw new Error("Yerel istek sınırı aşıldı.");
      transport.postMessage(data);
    } catch (error) {
      clearTimeout(timer);
      requests.delete(id);
      reject(
        error instanceof Error ? error : new Error("Köprü isteği başarısız."),
      );
    }
  });
}
export function refreshNativeStatus() {
  if (!inNativeApp) return Promise.resolve(null);
  if (statusRequest) return statusRequest;
  statusRequest = nativeRequest<NativeStatus>("status")
    .then((state) => {
      if (state.platform !== "android" || !Number.isInteger(state.sdk))
        throw new Error("Geçersiz platform durumu.");
      current = state;
      statusError = "";
      emit();
      return state;
    })
    .catch((error: Error) => {
      statusError = error.message;
      emit();
      throw error;
    })
    .finally(() => {
      statusRequest = null;
    });
  return statusRequest;
}
function subscribe(listener: () => void) {
  subscribers.add(listener);
  return () => {
    subscribers.delete(listener);
  };
}
export function useNativeStatus() {
  const value = useSyncExternalStore(subscribe, () => snapshot);
  useEffect(() => {
    if (inNativeApp) void refreshNativeStatus().catch(() => {});
  }, []);
  return value;
}
if (inNativeApp) {
  const update = () => {
    if (!document.hidden) void refreshNativeStatus().catch(() => {});
  };
  window.addEventListener("oguz-native-state", update);
  window.addEventListener("focus", update);
  document.addEventListener("visibilitychange", update);
  document.documentElement.classList.add("native-host");
}
