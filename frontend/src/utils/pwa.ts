export function registerSW() {
  if (!('serviceWorker' in navigator)) return

  if (import.meta.env.DEV) {
    // Dev: aggressively unregister everything and clear caches
    navigator.serviceWorker.getRegistrations().then(regs => {
      regs.forEach(r => r.unregister())
    })
    caches.keys().then(keys => keys.forEach(k => caches.delete(k)))
    return
  }

  // Production only: register the SW
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
