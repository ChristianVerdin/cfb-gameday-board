/* UI shell only. /api/live is never cached; games.js is network-first so the
   last snapshot still renders offline, clearly marked as such by app.js. */
const VERSION = "cfb-gameday-v5";
const SHELL = ["/", "/index.html", "/site.css", "/app.js", "/games.js", "/manifest.webmanifest", "/privacy", "/support",
               "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;            // live data: network only, no fallback
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) caches.open(VERSION).then((c) => c.put(e.request, res.clone()));
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })
      .then((hit) => hit || (e.request.mode === "navigate" ? caches.match("/index.html") : Response.error())))
  );
});
