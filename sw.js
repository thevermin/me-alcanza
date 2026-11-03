// Guarda la página para que abra rápido y funcione sin conexión con el último dato descargado.
const CACHE = "bolsillo-v1";
const ARCHIVOS = ["./", "index.html", "manifest.webmanifest", "icon.svg", "data/datos.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Primero la red (para tener siempre el dato nuevo); si no hay conexión, lo guardado.
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copia)); return r; })
      .catch(() => caches.match(e.request))
  );
});
