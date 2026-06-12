'use strict';
// Incrementar CACHE al actualizar index.html para forzar recarga en clientes.
const CACHE = 'dir-v1';
const SCOPE = self.registration.scope;

const APP_SHELL = [
  SCOPE,
  SCOPE + 'manifest.json',
  SCOPE + 'icon.svg',
];
const DATA_URL = SCOPE + 'data/empresas.json';

self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', ev => {
  ev.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', ev => {
  const { request } = ev;
  if (!request.url.startsWith('http')) return;

  // Datos: network-first para que el semanal llegue siempre
  if (request.url === DATA_URL) {
    ev.respondWith(
      fetch(request)
        .then(res => {
          caches.open(CACHE).then(c => c.put(request, res.clone()));
          return res;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // App shell: cache-first
  ev.respondWith(
    caches.match(request).then(cached => cached ?? fetch(request))
  );
});
