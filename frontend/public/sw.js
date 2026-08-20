// Yorvyn Service Worker v3
// Self-destructs in dev, safe network-first in prod

const CACHE = 'yorvyn-v3'

// Detect dev by checking if origin is localhost
const IS_DEV = self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1'

if (IS_DEV) {
  // In dev: immediately unregister self and delete all caches
  self.addEventListener('install', () => self.skipWaiting())
  self.addEventListener('activate', e => {
    e.waitUntil(
      caches.keys()
        .then(keys => Promise.all(keys.map(k => caches.delete(k))))
        .then(() => self.registration.unregister())
        .then(() => self.clients.matchAll())
        .then(clients => clients.forEach(c => c.navigate(c.url)))
    )
  })
} else {
  // Production: safe network-first SW
  const BYPASS = ['/@vite', '/@react-refresh', '/@fs', '/__vite', '/node_modules']

  function shouldBypass(url) {
    try {
      const u = new URL(url)
      if (u.origin !== self.location.origin) return true
      return BYPASS.some(p => u.pathname.startsWith(p))
    } catch { return true }
  }

  self.addEventListener('install', e => {
    e.waitUntil(
      caches.open(CACHE)
        .then(c => c.addAll(['/', '/index.html']))
        .then(() => self.skipWaiting())
    )
  })

  self.addEventListener('activate', e => {
    e.waitUntil(
      caches.keys()
        .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
        .then(() => self.clients.claim())
    )
  })

  self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return
    if (shouldBypass(e.request.url)) return
    e.respondWith(
      fetch(e.request)
        .then(r => {
          if (r && r.status === 200) {
            caches.open(CACHE).then(c => c.put(e.request, r.clone()))
          }
          return r
        })
        .catch(() => caches.match(e.request))
        .then(r => r || new Response('Offline', { status: 503 }))
    )
  })
}
