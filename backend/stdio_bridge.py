#!/usr/bin/env python3
"""
stdio_bridge.py — ASGI-over-stdio bridge for Vite dev proxy.

The Vite plugin (vite-backend-plugin.ts) spawns this script and communicates
with it by writing JSON request objects to stdin and reading JSON response
objects from stdout, one per line.

Request format  (stdin, newline-delimited JSON):
  { "id": str, "method": str, "path": str, "headers": dict, "body": str|null }

Response format (stdout, newline-delimited JSON):
  { "id": str, "status": int, "headers": dict, "body": str }

Startup signal (stderr):
  Writes "READY\n" once the ASGI app is loaded and the event loop is running.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
from pathlib import Path
from io import BytesIO

# ── Path setup ────────────────────────────────────────────────────────
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ── Import the FastAPI app ────────────────────────────────────────────
from backend.app.main import app  # noqa: E402  (after sys.path insert)


# ── Minimal ASGI → response collector ────────────────────────────────

async def call_asgi(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
) -> tuple[int, dict, bytes]:
    """Run one HTTP request through the ASGI app and return (status, headers, body)."""

    # Normalise path / query string
    if "?" in path:
        raw_path, query_string = path.split("?", 1)
    else:
        raw_path, query_string = path, ""

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "path": raw_path,
        "raw_path": raw_path.encode(),
        "query_string": query_string.encode(),
        "root_path": "",
        "scheme": "http",
        "server": ("localhost", 8000),
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in headers.items()
            if isinstance(k, str) and isinstance(v, str)
        ],
    }

    # ASGI send/receive callables
    body_iter = BytesIO(body)
    response_started = False
    status_code = 200
    response_headers: dict[str, str] = {}
    response_body = BytesIO()

    async def receive() -> dict:
        chunk = body_iter.read(65536)
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": False,
        }

    async def send(message: dict) -> None:
        nonlocal response_started, status_code, response_headers
        if message["type"] == "http.response.start":
            response_started = True
            status_code = message["status"]
            response_headers = {
                k.decode(): v.decode()
                for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            response_body.write(message.get("body", b""))

    await app(scope, receive, send)
    return status_code, response_headers, response_body.getvalue()


# ── Main event loop ───────────────────────────────────────────────────

async def main() -> None:
    loop = asyncio.get_event_loop()

    # Warm up the app (triggers startup events — loads ML model)
    await app.router.startup()

    # Signal readiness to the Vite plugin
    sys.stderr.write("READY\n")
    sys.stderr.flush()

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    stdout_transport, stdout_protocol = await loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout.buffer
    )

    async def write_response(obj: dict) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        stdout_transport.write(line.encode())

    async def handle_request(raw: str) -> None:
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            return

        req_id  = req.get("id", "unknown")
        method  = req.get("method", "GET")
        path    = req.get("path", "/")
        headers = req.get("headers", {})
        body_s  = req.get("body") or ""
        body    = body_s.encode() if isinstance(body_s, str) else b""

        try:
            status, resp_headers, resp_body = await call_asgi(method, path, headers, body)
            await write_response({
                "id":      req_id,
                "status":  status,
                "headers": resp_headers,
                "body":    resp_body.decode("utf-8", errors="replace"),
            })
        except Exception as exc:
            sys.stderr.write(f"[bridge] Error handling {method} {path}: {exc}\n")
            sys.stderr.flush()
            await write_response({
                "id":     req_id,
                "status": 500,
                "headers": {"content-type": "application/json"},
                "body":   json.dumps({"detail": str(exc)}),
            })

    # Read requests line-by-line from stdin
    while True:
        try:
            line = await reader.readline()
        except Exception:
            break
        if not line:
            break
        raw = line.decode("utf-8", errors="replace").strip()
        if raw:
            asyncio.ensure_future(handle_request(raw))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
