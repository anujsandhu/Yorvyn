// Yorvyn Service Worker v4 — Multi-Strategy Cache with Strict Auth/API Bypass
const STATIC_CACHE = 'yorvyn-static-v4';
const SWR_CACHE = 'yorvyn-swr-v4';
const ACTIVE_CACHES = new Set([STATIC_CACHE, SWR_CACHE]);

const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1';

if (IS_DEV) {
  self.addEventListener('install', () => self.skipWaiting());
  self.addEventListener('activate', (e) => {
    e.waitUntil(
      caches.keys()
        .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
        .then(() => self.registration.unregister())
        .then(() => self.clients.matchAll())
        .then((clients) => clients.forEach((c) => c.navigate(c.url)))
    );
  });
} else {
  const DEV_BYPASS = ['/@vite', '/@react-refresh', '/@fs', '/__vite', '/node_modules'];
  const NETWORK_ONLY_PREFIXES = ['/api/', '/auth/', '/rest/v1/', '/storage/v1/'];

  function isNetworkOnly(request) {
    if (request.method !== 'GET') return true;
    if (request.headers && request.headers.has('Authorization')) return true;
    try {
      const u = new URL(request.url);
      if (u.origin !== self.location.origin) return true;
      if (DEV_BYPASS.some((p) => u.pathname.startsWith(p))) return true;
      if (NETWORK_ONLY_PREFIXES.some((p) => u.pathname.startsWith(p))) return true;
      return false;
    } catch {
      return true;
    }
  }

  function isImmutableAsset(pathname) {
    return (
      /^\/assets\/.*-[a-f0-9]{6,}\./i.test(pathname) ||
      /\.(woff2|woff|ttf)$/i.test(pathname)
    );
  }

  function isPublicSWR(pathname) {
    return (
      pathname.startsWith('/ara-assets/') ||
      pathname.startsWith('/items/') ||
      pathname === '/yorvyn-logo.png' ||
      pathname === '/manifest.json'
    );
  }

  self.addEventListener('install', (e) => {
    e.waitUntil(
      caches.open(STATIC_CACHE)
        .then((c) => c.addAll(['/', '/index.html']))
        .then(() => self.skipWaiting())
    );
  });

  self.addEventListener('activate', (e) => {
    e.waitUntil(
      caches.keys()
        .then((keys) => Promise.all(keys.filter((k) => !ACTIVE_CACHES.has(k)).map((k) => caches.delete(k))))
        .then(() => self.clients.claim())
    );
  });

  self.addEventListener('fetch', (e) => {
    if (isNetworkOnly(e.request)) return;
    const url = new URL(e.request.url);

    // 1. Cache First for content-hashed immutable bundles and fonts
    if (isImmutableAsset(url.pathname)) {
      e.respondWith(
        caches.open(STATIC_CACHE).then((cache) =>
          cache.match(e.request).then((hit) => {
            if (hit) return hit;
            return fetch(e.request).then((resp) => {
              if (resp && resp.status === 200) cache.put(e.request, resp.clone());
              return resp;
            });
          })
        )
      );
      return;
    }

    // 2. Stale-While-Revalidate for public non-sensitive static assets
    if (isPublicSWR(url.pathname)) {
      e.respondWith(
        caches.open(SWR_CACHE).then((cache) =>
          cache.match(e.request).then((cached) => {
            const networkPromise = fetch(e.request)
              .then((resp) => {
                if (resp && resp.status === 200) cache.put(e.request, resp.clone());
                return resp;
              })
              .catch(() => cached);
            return cached || networkPromise;
          })
        )
      );
      return;
    }

    // 3. Network First + Offline Shell fallback for navigation/mutable assets
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          if (resp && resp.status === 200 && e.request.mode === 'navigate') {
            caches.open(STATIC_CACHE).then((c) => c.put(e.request, resp.clone()));
          }
          return resp;
        })
        .catch(() =>
          caches.match(e.request).then((hit) => hit || (e.request.mode === 'navigate' ? caches.match('/index.html') : undefined))
        )
        .then((r) => r || new Response('Offline', { status: 503 }))
    );
  });
}
