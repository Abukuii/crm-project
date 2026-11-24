/// <reference lib="webworker" />
/**
 * Savdo service worker.
 *
 * Vazifalari:
 *  1. Ilova qobig'ini (JS/CSS/HTML/ikonka) keshlash — internet sekin yoki yo'q bo'lsa ham ochiladi.
 *  2. Shriftlarni keshlash.
 *  3. Push bildirishnomalarini ko'rsatish va bosilganda kerakli sahifani ochish.
 *
 * MUHIM: /api/ so'rovlari hech qachon keshlanmaydi — narx va qoldiq har doim serverdan olinadi.
 */
import { clientsClaim } from "workbox-core";
import { ExpirationPlugin } from "workbox-expiration";
import { CacheableResponsePlugin } from "workbox-cacheable-response";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst, StaleWhileRevalidate } from "workbox-strategies";

// __WB_MANIFEST ni qurish paytida vite-plugin-pwa to'ldiradi (keshlanadigan fayllar ro'yxati)
declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

interface PushPayload {
  title?: string;
  body?: string;
  url?: string;
  tag?: string;
}

// ── Ilova qobig'i ────────────────────────────────────────────────────────────
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Sahifa ochilganda index.html keshdan beriladi (SPA marshrutlari shu yerda hal bo'ladi).
// /api/, /admin/ (Django admin), /static/, /media/ — har doim tarmoqqa ketadi.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    denylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
  }),
);

// ── Shriftlar (Google Fonts) ─────────────────────────────────────────────────
registerRoute(
  ({ url }) => url.origin === "https://fonts.googleapis.com",
  new StaleWhileRevalidate({ cacheName: "google-fonts-css" }),
);
registerRoute(
  ({ url }) => url.origin === "https://fonts.gstatic.com",
  new CacheFirst({
    cacheName: "google-fonts-files",
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 30, maxAgeSeconds: 365 * 24 * 60 * 60 }),
    ],
  }),
);

// ── Yangilanish ──────────────────────────────────────────────────────────────
// Foydalanuvchi "Yangilash" tugmasini bosganda ilova shu xabarni yuboradi.
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") void self.skipWaiting();
});
clientsClaim();

// ── Push bildirishnomalari ───────────────────────────────────────────────────
self.addEventListener("push", (event) => {
  let data: PushPayload = {};
  try {
    data = (event.data?.json() ?? {}) as PushPayload;
  } catch {
    data = { body: event.data?.text() };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Savdo", {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-96.png",
      tag: data.tag,
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data as { url?: string } | undefined)?.url || "/";
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin) {
          await client.focus();
          if ("navigate" in client) await client.navigate(url);
          return;
        }
      }
      await self.clients.openWindow(url);
    })(),
  );
});
