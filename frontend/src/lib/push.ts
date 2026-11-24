/** Push bildirishnomalari: brauzer obunasi va serverga ro'yxatdan o'tkazish. */
import { api } from "@/lib/api";

export interface PushConfig {
  enabled: boolean;
  public_key: string | null;
  devices: number;
}

export function pushSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function permissionState(): NotificationPermission | "unsupported" {
  return pushSupported() ? Notification.permission : "unsupported";
}

/** VAPID ochiq kaliti base64url → brauzer kutadigan bayt massivi. */
function decodeKey(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url + "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  return (await registration?.pushManager.getSubscription()) ?? null;
}

export class PushDenied extends Error {}

export async function enablePush(publicKey: string): Promise<PushConfig> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new PushDenied(permission);
  const registration = await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: decodeKey(publicKey),
    }));
  return api<PushConfig>("/notifications/push/subscribe/", {
    method: "POST",
    body: subscription.toJSON(),
  });
}

export async function disablePush(): Promise<void> {
  const subscription = await currentSubscription();
  if (!subscription) return;
  await api("/notifications/push/unsubscribe/", {
    method: "POST",
    body: { endpoint: subscription.endpoint },
  }).catch(() => undefined);
  await subscription.unsubscribe();
}

/**
 * Ilova ochilganda obunani server bilan solishtiradi.
 * Shu tufayli obuna "jim" yo'qolmaydi: brauzer uni almashtirsa yoki shu qurilmaga
 * boshqa xodim kirsa, yozuv o'z-o'zidan to'g'rilanadi.
 */
export async function syncPushSubscription(): Promise<void> {
  if (!pushSupported() || Notification.permission !== "granted") return;
  const subscription = await currentSubscription();
  if (!subscription) return;
  await api("/notifications/push/subscribe/", {
    method: "POST",
    body: subscription.toJSON(),
  }).catch(() => undefined);
}
