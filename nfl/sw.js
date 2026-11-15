/* UI shell for /nfl/ only. Network-first so the board is never stale when online;
   /api/ is never cached. Offline, the last copy of a page renders. */
const VERSION = "pfb-v1";
const SHELL = ["/nfl/", "/nfl/index.html", "/nfl/app.js", "/nfl/sheet.js", "/nfl/nfl.css", "/nfl/sheet.css", "/site.css"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("pfb-") && k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;
  if (!url.pathname.startsWith("/nfl/") && url.pathname !== "/site.css") return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) caches.open(VERSION).then((c) => c.put(e.request, res.clone()));
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })
      .then((hit) => hit || (e.request.mode === "navigate" ? caches.match("/nfl/index.html") : Response.error())))
  );
});
