/**
 * Vite plugin that spawns the Python/FastAPI backend and proxies /api requests
 * to it via stdin/stdout, avoiding the need for the backend to bind a port.
 *
 * Strategy: spawn a Python child process that uses a custom ASGI-over-stdio
 * protocol, then intercept /api requests in Vite's middleware and forward them.
 *
 * Actually, a simpler approach: since uvicorn can't bind, we use Python's
 * built-in `http.server` capabilities through a custom WSGI bridge — but
 * FastAPI is ASGI so we need uvicorn.
 *
 * Simplest working approach: use `spawn` + stdio pipes for request/response.
 */
import type { Plugin, ViteDevServer } from 'vite'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import http from 'http'

interface QueuedRequest {
  resolve: (value: { status: number; headers: Record<string, string>; body: string }) => void
  reject: (err: Error) => void
}

export default function backendPlugin(): Plugin {
  let backendProcess: ChildProcess | null = null
  let backendReady = false
  const requestQueue: Map<string, QueuedRequest> = new Map()
  const pendingRequests: Array<() => void> = []
  let buffer = ''

  return {
    name: 'vite-backend-proxy',
    configureServer(server: ViteDevServer) {
      const projectRoot = path.resolve(__dirname, '..')
      const pythonPath = path.join(projectRoot, 'backend', 'venv', 'bin', 'python')
      const bridgeScript = path.join(projectRoot, 'backend', 'stdio_bridge.py')

      // Spawn the backend bridge
      console.log('🚀 Starting backend via stdio bridge...')
      backendProcess = spawn(pythonPath, [bridgeScript], {
        cwd: projectRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
      })

      backendProcess.stderr?.on('data', (data: Buffer) => {
        const msg = data.toString()
        if (msg.includes('READY')) {
          backendReady = true
          console.log('✅ Backend is ready')
          // Flush any queued requests that arrived before READY
          pendingRequests.forEach(fn => fn())
          pendingRequests.length = 0
        }
        // Forward backend logs
        process.stderr.write(`[backend] ${msg}`)
      })

      backendProcess.stdout?.on('data', (data: Buffer) => {
        buffer += data.toString()
        // Process complete JSON responses separated by newlines
        let newlineIdx: number
        while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
          const line = buffer.slice(0, newlineIdx).trim()
          buffer = buffer.slice(newlineIdx + 1)
          if (!line) continue
          try {
            const response = JSON.parse(line)
            const queued = requestQueue.get(response.id)
            if (queued) {
              requestQueue.delete(response.id)
              queued.resolve({
                status: response.status || 200,
                headers: response.headers || {},
                body: response.body || '',
              })
            }
          } catch (e) {
            // Not JSON, might be a log line
            process.stderr.write(`[backend-stdout] ${line}\n`)
          }
        }
      })

      backendProcess.on('exit', (code) => {
        console.log(`Backend process exited with code ${code}`)
        backendReady = false
      })

      // Middleware to intercept /api requests
      server.middlewares.use('/api', (req, res) => {
        if (!backendReady || !backendProcess?.stdin) {
          res.writeHead(503, {
            'Content-Type': 'application/json',
            'Retry-After': '2',
          })
          res.end(JSON.stringify({
            error: 'Backend is starting up',
            status: 'loading',
          }))
          return
        }

        let body = ''
        req.on('data', (chunk: Buffer) => { body += chunk.toString() })
        req.on('end', () => {
          const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

          const request = {
            id: requestId,
            method: req.method || 'GET',
            path: '/api' + (req.url || ''),
            headers: req.headers,
            body: body || undefined,
          }

          const timeout = setTimeout(() => {
            requestQueue.delete(requestId)
            res.writeHead(503, {
              'Content-Type': 'application/json',
              'Retry-After': '2',
            })
            res.end(JSON.stringify({
              error: 'Backend is taking too long to respond',
              status: 'loading',
            }))
          }, 10000)

          requestQueue.set(requestId, {
            resolve: (response) => {
              clearTimeout(timeout)
              const headers: Record<string, string> = {
                'Content-Type': 'application/json',
                ...response.headers,
              }
              res.writeHead(response.status, headers)
              res.end(response.body)
            },
            reject: (err) => {
              clearTimeout(timeout)
              res.writeHead(500, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({ error: err.message }))
            },
          })

          // Send request to backend via stdin
          try {
            backendProcess!.stdin!.write(JSON.stringify(request) + '\n')
          } catch (e: any) {
            requestQueue.delete(requestId)
            clearTimeout(timeout)
            res.writeHead(500, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: 'Failed to communicate with backend: ' + e.message }))
          }
        })
      })
    },
    closeBundle() {
      backendProcess?.kill()
    },
  }
}
