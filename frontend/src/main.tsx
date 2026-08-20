import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { registerSW } from './utils/pwa'

// Suppress unhandled rejections from third-party SDKs (Firebase Analytics,
// AdGuard blocking gtag, etc.) that we can't control
window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason
  // Suppress Firebase/Analytics/AdGuard noise
  const msg = String(reason?.message || reason || '')
  if (
    msg.includes('fetch') ||
    msg.includes('network') ||
    msg.includes('gtag') ||
    msg.includes('analytics') ||
    msg.includes('firebaseapp') ||
    msg.includes('googleapis') ||
    msg.includes('blocked')
  ) {
    event.preventDefault()
  }
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

registerSW()

if (import.meta.env.PROD) {
  import('./utils/firebase').then(({ initAnalytics }) => initAnalytics()).catch(() => {})
}
