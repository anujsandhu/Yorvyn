"""Launch disposable PostgreSQL + Redis + FastAPI + Vite and run real Chromium Phase 16.3 verification."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    photo = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg").resolve()
    default_out = ROOT / "docs/reports/PHASE_16_3_BROWSER_PERF_EVIDENCE.json"
    out_path = Path(os.environ.get("PHASE_16_3_BROWSER_OUT", str(default_out))).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as work_str:
        work = Path(work_str)
        pg_bin = Path(shutil.which("postgres")).parent
        pg_port = _free_port()
        rd_port = _free_port()
        pg_dir = work / "pg"
        pg_sock = work / "pgsock"
        rd_dir = work / "redis"
        pg_sock.mkdir()
        rd_dir.mkdir()
        subprocess.run([str(pg_bin / "initdb"), "-D", str(pg_dir), "-U", "yorvyn", "-A", "trust"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(pg_bin / "pg_ctl"), "-D", str(pg_dir), "-l", str(work / "pg.log"), "-o", f"-p {pg_port} -k {pg_sock}", "start"], check=True, stdout=subprocess.DEVNULL)
        redis = subprocess.Popen([shutil.which("redis-server"), "--port", str(rd_port), "--dir", str(rd_dir), "--save", ""], stdout=subprocess.DEVNULL)

        os.environ.update(
            DEBUG="false",
            YORVYN_DURABLE_SESSIONS="true",
            DATABASE_URL=f"postgresql://yorvyn@127.0.0.1:{pg_port}/postgres",
            REDIS_URL=f"redis://127.0.0.1:{rd_port}/0",
            SUPABASE_JWT_SECRET=secrets.token_urlsafe(32),
            GARMENT_CHAT_PLANNER="offline_rules",
            GEMINI_API_KEY="",
            GROQ_API_KEY="",
            OPENROUTER_API_KEY="",
            HF_TOKEN="",
            PHASE_16_3_BROWSER_OUT=str(out_path),
        )
        try:
            import uvicorn
            from jose import jwt
            from fastapi import FastAPI
            from backend.app.api.ai_session_routes import router as sessions
            from backend.app.api.conversational_garments import router as garments
            from backend.app.api.garment_generation_routes import router as jobs
            from backend.app.api.garment_identification_routes import router as ident
            from backend.app.api.garment_design_routes import router as design

            app = FastAPI()
            for r in (sessions, garments, jobs, ident, design):
                app.include_router(r)

            api_port = _free_port()
            web_port = _free_port()
            origin = f"http://127.0.0.1:{web_port}"
            target = f"http://127.0.0.1:{api_port}"
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="error"))
            t = threading.Thread(target=server.run, daemon=True)
            t.start()

            claims = {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600}
            token = jwt.encode(claims, os.environ["SUPABASE_JWT_SECRET"])
            session = {
                "access_token": token,
                "refresh_token": "local-16-3-test",
                "expires_at": claims["exp"],
                "token_type": "bearer",
                "user": {"id": claims["sub"], "aud": "authenticated", "user_metadata": {}, "app_metadata": {}},
            }

            pw_mod = "/Users/anujsandhu/.npm/_npx/420ff84f11983ee5/node_modules"
            env = dict(
                os.environ,
                NODE_PATH=pw_mod,
                VITE_SUPABASE_URL=target,
                VITE_SUPABASE_ANON_KEY="sb_publishable_localtest",
                VITE_API_URL="/api",
                VITE_FASHION_API_URL="/api/fashion",
                VITE_BACKEND_TARGET=target,
                CHAT_TEST_ORIGIN=origin,
                CHAT_TEST_SESSION=json.dumps(session),
            )
            vite = subprocess.Popen(
                ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--strictPort", "--port", str(web_port)],
                cwd=ROOT / "frontend",
                env=env,
                stdout=subprocess.DEVNULL,
            )
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(origin, timeout=1).close()
                        break
                    except OSError:
                        time.sleep(0.1)
                subprocess.run(["node", str(ROOT / "scripts/verify_phase16_3_browser.cjs"), str(photo)], env=env, check=True)
            finally:
                vite.terminate()
                vite.wait()
                server.should_exit = True
                t.join(10)
        finally:
            redis.terminate()
            redis.wait()
            subprocess.run([str(pg_bin / "pg_ctl"), "-D", str(pg_dir), "stop"], check=False, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
