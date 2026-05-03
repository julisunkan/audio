const CACHE_NAME    = "audiobooks-v2";
const OFFLINE_URL   = "/static/offline.html";
const STATIC_ASSETS = [
  "/",
  "/dashboard",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
  OFFLINE_URL
];

// ── Install: pre-cache all static assets including the offline page ──
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// ── Activate: purge old caches ───────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch ────────────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);

  // Static assets: cache-first
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) => cached || fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
      )
    );
    return;
  }

  // Navigation requests (HTML pages): network-first, fall back to offline page
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match(OFFLINE_URL).then(
          (cached) => cached || new Response(
            "<h1>You are offline</h1>",
            { headers: { "Content-Type": "text/html" } }
          )
        )
      )
    );
    return;
  }

  // API / other requests: network-first, fail silently
  event.respondWith(
    fetch(event.request).catch(() => new Response(
      JSON.stringify({ error: "You are offline" }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    ))
  );
});
