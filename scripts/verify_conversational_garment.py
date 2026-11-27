"""Run the authenticated garment conversation with disposable PostgreSQL and Redis.

Usage: backend/venv/bin/python scripts/verify_conversational_garment.py IMAGE
The local provider fallback is exercised with external services disabled.
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def verify(path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jose import jwt
    from backend.app.api.ai_session_routes import router as sessions
    from backend.app.api.conversational_garments import router as garments
    from backend.app.api.garment_generation_routes import router as jobs
    app = FastAPI()
    for router in (sessions, garments, jobs):
        app.include_router(router)
    def auth():
        claims = {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600}
        return {"Authorization": "Bearer " + jwt.encode(claims, os.environ["SUPABASE_JWT_SECRET"])}
    if "--browser" in sys.argv:
        import threading
        import uvicorn
        api_port, web_port = port(), port()
        origin = f"http://127.0.0.1:{web_port}"
        target = f"http://127.0.0.1:{api_port}"
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1",port=api_port,log_level="error"))
        thread = threading.Thread(target=server.run,daemon=True)
        thread.start()
        token = auth()["Authorization"].split()[1]
        claims = jwt.get_unverified_claims(token)
        session = {"access_token":token,"refresh_token":"local-integration-test","expires_at":claims["exp"],
                   "token_type":"bearer","user":{"id":claims["sub"],"aud":"authenticated","user_metadata":{},"app_metadata":{}}}
        env = dict(os.environ,VITE_SUPABASE_URL=target,VITE_SUPABASE_ANON_KEY="sb_publishable_localtest",
                   VITE_API_URL="/api",VITE_FASHION_API_URL="/api/fashion",VITE_BACKEND_TARGET=target,
                   CHAT_TEST_ORIGIN=origin, CHAT_TEST_SESSION=json.dumps(session))
        vite = subprocess.Popen(["node","node_modules/vite/bin/vite.js","--host","127.0.0.1","--strictPort","--port",str(web_port)],
                                cwd=ROOT/"frontend",env=env,stdout=subprocess.DEVNULL)
        try:
            import urllib.request
            for _ in range(100):
                try:
                    urllib.request.urlopen(origin,timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            subprocess.run(["node",str(ROOT/"scripts/verify_garment_browser.cjs"),str(path)],env=env,check=True)
        finally:
            vite.terminate()
            vite.wait()
            server.should_exit=True
            thread.join(10)
        return
    client = TestClient(app, headers=auth())
    session = client.post("/api/ai/sessions", json={"title":"Verification"}).json()["session"]["id"]
    turns = f"/api/ai/sessions/{session}/garment-turns"
    turn = str(uuid.uuid4())
    payload = {"instruction":"Create a 3D garment from this.", "request_id":turn}
    assert client.post(turns, data=payload, headers=auth()).status_code == 404
    assert client.post(turns, data=payload, files={"images":("bad.png",b"bad","image/png")}).status_code == 422
    with path.open("rb") as image:
        response = client.post(turns, data=payload, files={"images":(path.name,image,"image/jpeg")})
    response.raise_for_status()
    reply = response.json()
    g = reply["metadata"]["garment"]
    print("Recognition:", g.get("category"), "plan:", g["plan"], "reply:", reply["content"], flush=True)
    expected_messages = 6
    if g.get("pending_action") == "reconstruct":
        assert "Which garment" in reply["content"]
        previous = turn
        turn = str(uuid.uuid4())
        payload = {"instruction":"The denim jacket.", "request_id":turn,"previous":previous}
        photo = path.read_bytes()
        response = client.post(turns, data=payload, files=[
            ("images", (path.name, photo, "image/jpeg")), ("images", (path.name, photo, "image/jpeg"))])
        response.raise_for_status()
        reply = response.json()
        g = reply["metadata"]["garment"]
        views = g["recognition"]["views"]
        assert len(views) == 2 and views[1]["duplicate_of_image_id"] == views[0]["image_id"]
        assert not views[1]["usable"]
        expected_messages += 2
    assert g.get("job_id"), reply["content"]
    events = client.get(f"{turns}/{turn}/activity")
    events.raise_for_status()
    labels = [json.loads(line)["activity"] for line in events.text.splitlines()]
    assert "Submitting reconstruction…" in labels and labels[-1] == "Garment response ready.", labels
    assert client.post(turns,data=payload).json()["id"] == reply["id"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = client.get(f"/api/fashion/garment-gen/jobs/{g['job_id']}")
        result.raise_for_status()
        status = result.json()["status"]
        if status in ("completed","failed","timed_out","cancelled"):
            break
        time.sleep(1)
    assert status == "completed", result.text
    url = f"{turns}/{turn}/candidate"
    original = client.get(url)
    assert original.status_code == 200, original.text[:300]
    assert original.content.startswith(b"glTF")
    assert client.get(url, headers=auth()).status_code == 404
    edited = str(uuid.uuid4())
    result = client.post(turns, data={"request_id":edited, "previous":turn, "instruction":"Make it wider."}).json()
    assert result["metadata"]["garment"]["edits"] == ["widen"], result["content"]
    updated = client.get(f"{turns}/{edited}/candidate")
    assert updated.content.startswith(b"glTF") and original.content != updated.content
    undo = str(uuid.uuid4())
    client.post(turns, data={"request_id":undo,"previous":edited,"instruction":"Undo."}).raise_for_status()
    assert client.get(f"{turns}/{undo}/candidate").content == original.content
    assert len(client.get(f"/api/ai/sessions/{session}/messages").json()["items"]) == expected_messages
    from backend.app.services.garments.job_manager import GarmentJobManager
    reader = GarmentJobManager()
    restored_job = reader.get_job(g["job_id"])
    assert restored_job and restored_job.result and restored_job.result.mesh_vertex_count > 0
    print("Verified cold job metadata, activity stream, original, edited and restored GLBs:",len(original.content),len(updated.content))


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as work:
        pg, redis = port(), port()
        os.environ.update({key:"" for key in ("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","NEXT_PUBLIC_SUPABASE_URL",
                          "GROQ_API_KEY","OPENROUTER_API_KEY","GEMINI_API_KEY","GOOGLE_API_KEY","CLOUDINARY_URL",
                          "CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET","HF_API_KEY")})
        os.environ.update(YORVYN_PG_DSN=f"postgresql://127.0.0.1:{pg}/postgres", REDIS_PORT=str(redis),
                          YORVYN_GARMENT_ASSET_DIR=work+"/assets", YORVYN_GARMENT_TEMP_DIR=work+"/inputs",
                          SUPABASE_JWT_SECRET=secrets.token_hex(32), HF_HUB_OFFLINE="1")
        db = work+"/pg"
        subprocess.run(["initdb","-D",db,"-A","trust"],check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["pg_ctl","-D",db,"-o",f"-p {pg} -h 127.0.0.1 -k {work}","-l",work+"/pg.log","-w","start"],check=True)
        proc = subprocess.Popen(["redis-server","--port",str(redis),"--bind","127.0.0.1","--dir",work,"--save",""],stdout=subprocess.DEVNULL)
        try:
            verify(path)
        finally:
            proc.terminate()
            proc.wait()
            subprocess.run(["pg_ctl","-D",db,"-w","stop"],check=True)
