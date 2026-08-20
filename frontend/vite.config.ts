import { defineConfig } from 'vite'
import type { Plugin, ProxyOptions } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import type { ServerResponse } from 'http'

/** Injects a tiny script that kills any stale SW on every dev page load */
function killSwPlugin(): Plugin {
  return {
    name: 'kill-sw',
    apply: 'serve', // dev only
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          attrs: { 'data-kill-sw': '' },
          children: `
            if ('serviceWorker' in navigator) {
              navigator.serviceWorker.getRegistrations().then(function(regs) {
                regs.forEach(function(r) { r.unregister(); });
              });
              if ('caches' in window) {
                caches.keys().then(function(keys) {
                  keys.forEach(function(k) { caches.delete(k); });
                });
              }
            }
          `,
          injectTo: 'head-prepend', // runs before anything else
        },
      ]
    },
  }
}

export default defineConfig(async () => {
  const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8002'

  const apiProxy: ProxyOptions = {
    target: backendTarget,
    changeOrigin: true,
    configure(proxy) {
      proxy.on('error', (err, _req, res) => {
        console.warn(`[vite] Backend proxy unavailable at ${backendTarget}: ${err.message}`)

        const serverRes = res as ServerResponse | undefined
        if (!serverRes || serverRes.headersSent || serverRes.writableEnded) {
          return
        }

        serverRes.writeHead(503, {
          'Content-Type': 'application/json',
          'Retry-After': '2',
        })
        serverRes.end(JSON.stringify({
          error: 'Backend is unavailable or still starting',
          status: 'loading',
        }))
      })
    },
  }

  return {
    plugins: [killSwPlugin(), react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@components': path.resolve(__dirname, './src/components'),
        '@pages': path.resolve(__dirname, './src/pages'),
        '@hooks': path.resolve(__dirname, './src/hooks'),
        '@utils': path.resolve(__dirname, './src/utils'),
        '@T': path.resolve(__dirname, './src/types'),
      },
    },
    server: {
      port: 5174,
      cors: true,
      proxy: {
        '/api': apiProxy,
      },
    },
  }
})
