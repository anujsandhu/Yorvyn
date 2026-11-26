"""Phase 15.4. Run from the repository root using the backend Python environment.

preflight probes configured planners. --photo authorizes this photograph for the Gemini probe.
recovery uses disposable loopback infrastructure. --live requires live provider receipts.
No backend process or database supplied by the environment is restarted.
"""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
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
import uuid

import requests
from jose import jwt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PASS, PARTIAL, MISSING, INFRA, FAIL = (
    "VERIFIED_COMPLETE", "PARTIALLY_VERIFIED", "BLOCKED_MISSING_CREDENTIAL",
    "BLOCKED_INFRASTRUCTURE", "FAILED")
PHOTO = ROOT / "data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg"


class GateError(Exception):
    pass


def require(condition, label):
    if not condition:
        raise GateError(label)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def photo_input(path):
    with Image.open(path) as image:
        mime = Image.MIME[image.format]
        image.verify()
    source = path.read_bytes()
    require(mime in {"image/jpeg", "image/png", "image/webp"}, "unsupported image format")
    if path.resolve() == PHOTO.resolve():
        require(digest(source) == "f87ac6c4b1a7a0279635afe249f8cf519be80f3336b5395fe83e878e9bcb0e61",
                "licensed fixture does not match its source manifest")
    return source, mime


def probe_status(error):
    if error == "BLOCKED_NO_CREDENTIALS":
        return MISSING
    if error in {"INVALID_CREDENTIAL", "PERMISSION_DENIED", "QUOTA_EXHAUSTED", "RATE_LIMIT",
                 "TLS_FAILED", "NETWORK_FAILURE", "TIMEOUT"}:
        return "BLOCKED_" + error
    return FAIL


def probe_record(name, model, credential, capability):
    return {"provider": name, "configured_model": model, "credential_configured": credential,
            "capability": capability, "capability_verified": False, "endpoint_reachable": None,
            "status": INFRA if credential else MISSING,
            "error": "NOT_PROBED" if credential else "BLOCKED_NO_CREDENTIALS"}


def record_probe(record, valid, model, request_id, error, http_status=None):
    record.update(status=PASS if valid else probe_status(error), error=None if valid else error,
                  upstream_model=model, request_id=request_id, http_status=http_status,
                  capability_verified=bool(valid),
                  endpoint_reachable=True if valid or http_status or model or error == "MALFORMED_OUTPUT" else None)


def preflight(path):
    from backend.app.services.ai.providers.gemini_provider import GeminiVisionProvider
    from backend.app.services.ai.base import AIRequest, TaskType
    from backend.app.services.llm.garment_plan import plan_turn, llm_registry
    vision = GeminiVisionProvider()
    info = probe_record(vision.name, vision.model_name, vision.is_available(), "garment image to structured JSON")
    if info["credential_configured"] and path:
        data, mime = photo_input(path)
        result = vision.execute(AIRequest(request_id=str(uuid.uuid4()), image_bytes=data, image_mime_type=mime,
                                         task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING, require_vision=True))
        valid = (result.success and result.provider_name == vision.name and result.model_metadata.device == "cloud"
                 and not result.cached and bool(result.upstream_model))
        record_probe(info, valid, result.upstream_model, result.upstream_request_id,
                     result.error.error_code if result.error else "MISSING_LIVE_EVIDENCE",
                     result.error.status_code if result.error else 200)
        info["image_sha256"] = digest(data)
        if valid:
            info.update(usage=result.token_usage.model_dump() if result.usage_reported else None,
                        category=result.structured_data["garment"]["category"])
    planners = []
    for name in ("groq", "openrouter", "gemini"):
        provider = llm_registry.get_provider(name)
        record = probe_record(name, provider.default_model, provider.health_check(), "text to plan_garment tool call")
        if record["credential_configured"]:
            plan, trace = plan_turn("Create a 3D model of the uploaded jacket.", True, False, provider_only=name)
            valid = (trace["provider"] == name and bool(trace.get("upstream_model"))
                     and plan is not None and plan.action == "reconstruct")
            observation = (trace["previous_attempts"] or [trace])[-1]
            record_probe(record, valid, observation.get("upstream_model"), observation.get("upstream_request_id"),
                         observation.get("error", "INVALID_PLANNER_RESPONSE"), observation.get("http_status"))
            record["validated_provider_action"] = plan.action if valid else None
        planners.append(record)
    requested = os.getenv("GARMENT_CHAT_PLANNER")
    eligible = [p for p in planners if not requested or p["provider"] == requested]
    selected = next((p["provider"] for p in eligible if p["status"] == PASS), None)
    status = info["status"]
    if requested and not eligible:
        status = "BLOCKED_INVALID_PLANNER_CONFIGURATION"
    elif status == PASS and not selected:
        status = next((p["status"] for p in eligible if p["credential_configured"]), MISSING)
    return {"mode": "preflight", "vision": info, "planners": planners, "requested_planner": requested,
            "selected_live_planner": selected, "status": status}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop(process, abrupt=False):
    if process.poll() is None:
        process.kill() if abrupt else process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def wait_http(url, process):
    for _ in range(360):
        require(process.poll() is None, "service exited before readiness")
        try:
            if requests.get(url, timeout=1).ok:
                return
        except requests.ConnectionError:
            pass
        time.sleep(.25)
    raise GateError("service readiness timed out")


@contextmanager
def gateway(port):
    """Mirror the Supabase REST prefix onto the real disposable PostgREST process."""
    class Proxy(BaseHTTPRequestHandler):
        def dispatch(self):
            if not self.path.startswith("/rest/v1/"):
                self.send_error(404)
                return
            response = requests.request(self.command, f"http://127.0.0.1:{port}" + self.path[8:],
                                        headers={k: self.headers[k] for k in ("Authorization", "Prefer", "Content-Type")
                                                 if k in self.headers},
                                        data=self.rfile.read(int(self.headers.get("Content-Length", 0))), timeout=4)
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(response.content)

        do_GET = do_POST = do_PATCH = do_DELETE = dispatch

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def recovery(args, report):
    rest_bin = shutil.which(os.environ.get("POSTGREST_BIN", "postgrest"))
    for program in ("initdb", "pg_ctl", "psql", "redis-server"):
        require(shutil.which(program), f"missing executable {program}")
    require(rest_bin, "missing executable postgrest")
    source, mime = photo_input(args.photo or PHOTO)
    with ExitStack() as stack:
        work = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        database, pg, redis, rest, api = work / "pg", free_port(), free_port(), free_port(), free_port()
        dsn = f"postgresql://127.0.0.1:{pg}/postgres"
        secret = secrets.token_hex(32)
        uid, other = str(uuid.uuid4()), str(uuid.uuid4())

        def token(user, seconds=1800):
            return jwt.encode({"sub": user, "role": "authenticated", "aud": "authenticated",
                               "exp": int(time.time()) + seconds}, secret)
        quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        def sql(statement):
            return subprocess.check_output(["psql", dsn, "-XAtq", "-v", "ON_ERROR_STOP=1"], input=statement,
                                           text=True, stderr=subprocess.DEVNULL).strip()

        subprocess.run(["initdb", "-D", database, "-A", "trust"], check=True, **quiet)
        def pgctl(action):
            cmd = ["pg_ctl", "-D", database, "-w", action]
            if action == "start":
                cmd += ["-o", f"-p {pg} -h 127.0.0.1 -k {work}", "-l", work / "postgres.log"]
            subprocess.run(cmd, check=True, **quiet)
        pgctl("start")
        stack.callback(lambda: pgctl("stop") if (database / "postmaster.pid").exists() else None)
        sql("CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS; CREATE SCHEMA auth;"
            "CREATE TABLE auth.users(id uuid primary key);"
            "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT "
            "(current_setting('request.jwt.claims',true)::jsonb->>'sub')::uuid $$;"
            f"INSERT INTO auth.users VALUES ('{uid}'), ('{other}');")
        for migration in ("010_persistent_ai_sessions.sql", "012_durable_conversation_sequence.sql"):
            sql((ROOT / "backend/migrations" / migration).read_text())
        sql("GRANT USAGE ON SCHEMA public TO service_role; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES "
            "IN SCHEMA public TO service_role; GRANT USAGE ON SCHEMA public, auth TO authenticated;"
            "GRANT SELECT ON yorvyn_ai_sessions, yorvyn_ai_messages TO authenticated;")
        env = dict(os.environ, YORVYN_PG_DSN=dsn, REDIS_HOST="127.0.0.1", REDIS_PORT=str(redis),
                   YORVYN_REQUIRE_DURABLE_SESSIONS="1", YORVYN_GARMENT_JOB_TIMEOUT_SECONDS="75", GARMENT_CHAT_DAILY_UNITS="3", YORVYN_GARMENT_ASSET_DIR=str(work/"assets"),
                   YORVYN_GARMENT_TEMP_DIR=str(work/"inputs"), SUPABASE_JWT_SECRET=secret,
                   DATABASE_URL=f"sqlite:///{work}/app.db", HF_HUB_OFFLINE="1",
                   SUPABASE_SERVICE_ROLE_KEY=jwt.encode({"role":"service_role","exp":int(time.time())+1800}, secret))
        for key in ("CLOUDINARY_URL","CLOUDINARY_CLOUD_NAME","CLOUDINARY_API_KEY","CLOUDINARY_API_SECRET",
                    "HF_API_KEY","OPENAI_API_KEY","NEXT_PUBLIC_SUPABASE_URL","SUPABASE_ANON_KEY",
                    "STRIPE_SECRET_KEY","STRIPE_WEBHOOK_SECRET","STRIPE_PUBLISHABLE_KEY"):
            env[key] = ""
        env["YORVYN_STAGING_LIVE_RECEIPTS"] = "1" if args.live else "0"
        if not args.live:
            for key in ("GROQ_API_KEY","OPENROUTER_API_KEY","GOOGLE_API_KEY","GEMINI_API_KEY"):
                env[key] = ""
            env["GARMENT_CHAT_PLANNER"] = "offline_rules"
        broker = subprocess.Popen(["redis-server","--port",str(redis),"--bind","127.0.0.1",
                                   "--dir",str(work),"--save",""], **quiet)
        stack.callback(stop, broker)
        rest_env = dict(env, PGRST_DB_URI=dsn, PGRST_DB_ANON_ROLE="anon", PGRST_JWT_SECRET=secret,
                        PGRST_SERVER_HOST="127.0.0.1", PGRST_SERVER_PORT=str(rest), PGRST_DB_POOL_ACQUISITION_TIMEOUT="1")
        service = subprocess.Popen([rest_bin], env=rest_env, **quiet)
        stack.callback(stop, service)
        wait_http(f"http://127.0.0.1:{rest}/", service)
        env["SUPABASE_URL"] = stack.enter_context(gateway(rest))
        origin = f"http://127.0.0.1:{api}"

        def start():
            process = subprocess.Popen([sys.executable,"-m","uvicorn","backend.app.main:app","--host","127.0.0.1",
                                        "--port",str(api),"--no-access-log"], cwd=ROOT, env=env, **quiet)
            stack.callback(stop, process)
            wait_http(origin+"/api/health", process)
            return process

        def request(method, route, *, identity=uid, code=200, auth=None, **kwargs):
            headers = {"Authorization":"Bearer "+(auth or token(identity))} if identity else {}
            response = requests.request(method,origin+route,headers=headers,timeout=180,**kwargs)
            require(response.status_code == code, f"{method} {route.split('?')[0]} expected {code}, got {response.status_code}")
            return response

        process = start()
        base = "/api/ai/sessions"
        browser_env = None
        if args.browser or args.live:
            web_port = free_port()
            web = f"http://127.0.0.1:{web_port}"
            account = {"access_token":token(uid),"refresh_token":"disposable-test","expires_at":int(time.time())+1800,
                       "token_type":"bearer","user":{"id":uid,"aud":"authenticated","user_metadata":{},"app_metadata":{}}}
            browser_env = dict(env, VITE_API_URL="/api", VITE_FASHION_API_URL="/api/fashion", VITE_BACKEND_TARGET=origin,
                               VITE_SUPABASE_URL=origin, VITE_SUPABASE_ANON_KEY="sb_publishable_disposable_test",
                               CHAT_TEST_SESSION=json.dumps(account), CHAT_TEST_ORIGIN=web,
                               CHAT_INSTRUCTION=args.instruction, CHAT_RECOVERY_STATE=str(work/"browser-state.json"),
                               CHAT_RECOVERY_SESSION=str(work/"session-id"))
            vite = subprocess.Popen(["node","node_modules/vite/bin/vite.js","--host","127.0.0.1","--port",str(web_port),
                                     "--strictPort"],cwd=ROOT/"frontend",env=browser_env,**quiet)
            stack.callback(stop,vite)
            wait_http(web,vite)

        def browser(stage, expected_hash=""):
            subprocess.run(["node",str(ROOT/"scripts/verify_garment_browser.cjs"),str(args.photo or PHOTO)],check=True,
                           env=dict(browser_env,CHAT_RECOVERY_STAGE=stage,CHAT_RECOVERY_HASH=expected_hash),**quiet)

        if browser_env:
            browser("create")
            sid = str(uuid.UUID((work/"session-id").read_text()))
        else:
            sid = request("POST",base,code=201,json={"title":"Disposable restart verification",
                                                    "session_type":"fashion_stylist"}).json()["session"]["id"]
        conv = f"{base}/{sid}"
        turns = conv + "/garment-turns"
        original_id, edit_id = str(uuid.uuid4()), str(uuid.uuid4())
        files = {"images":("garment."+mime.split("/")[1],source,mime)}
        command = {"request_id":original_id,"instruction":args.instruction}
        if browser_env:
            items = request("GET",conv+"/messages").json()["items"]
            replies = [m for m in items if m["role"] == "assistant"]
            require(len(replies) == 2, "browser did not create original and edited turns")
            reply, edited_reply = replies
            original_id = reply["metadata"]["garment"]["turn_id"]
            edit_id = edited_reply["metadata"]["garment"]["turn_id"]
            command["request_id"] = original_id
        else:
            reply = request("POST",turns,data=command,files=files).json()
        ctx = reply["metadata"]["garment"]
        require(ctx.get("job_id") and ctx["source_sha256"] == [digest(source)], "image/job link missing")
        report["source_sha256"] = ctx["source_sha256"]
        report["planner"] = ctx["planner"]
        execution = ctx["intelligence_execution"]
        require(execution["user_id"] == uid and execution["conversation_id"] == sid, "execution ownership")
        require(execution["job_id"] == ctx["job_id"] and execution["input_sha256"] == ctx["source_sha256"],
                "execution references differ from the accepted turn")
        require(all(op["status"] == "COMPLETED" for op in execution["operations"]), "incomplete operation")
        if not args.live:
            require(execution["accounting"]["provider_request_count"] == 0, "unexpected external request")
            require(execution["classifiers"] and all(c["sha256"] for c in execution["classifiers"]),
                    "local release execution receipt missing")
        report["intelligence_execution"] = execution
        receipts = ctx["recognition"]["model_execution_provenance"]
        views = ctx["recognition"]["views"]
        require(all(receipts[v["image_id"]]["vision_execution"]["image_sha256"] == v["image_hash"]
                    for v in views if v["usable"]), "vision receipt does not match recognized input")
        report["vision"] = [v["vision_execution"] for v in receipts.values()]
        if args.live:
            require(ctx["plan"]["action"] == "reconstruct" and ctx["planner"].get("upstream_model")
                    and ctx["planner"]["provider"] == os.environ["GARMENT_CHAT_PLANNER"], "live planner gate failed")
            require(report["vision"] and all(v["provider"] == "gemini_vision" and not v["mock"] and not v["cached"]
                        and v["upstream_model"] for v in report["vision"]), "live vision gate failed")
        job_id = ctx["job_id"]
        job_url = f"/api/fashion/garment-gen/jobs/{job_id}"
        require(request("POST",turns,data=command).json()["id"] == reply["id"], "request replay changed reply")
        for _ in range(240):
            job = request("GET",job_url).json()
            if job["status"] == "completed" and job["result"]:
                break
            require(job["status"] not in {"failed","timed_out","cancelled"}, "worker failed")
            time.sleep(1)
        else:
            raise GateError("worker timeout")
        report["geometry_provenance"] = job["result"]["reconstruction_provenance"]
        worker = job["result"]["intelligence_execution"]
        require(worker["mesh_structure"] == "PASSED" and worker["geometry_accuracy"] == "NOT_EVALUATED",
                "independent quality gates")
        report["worker_execution"] = worker
        original_url = f"{turns}/{original_id}/candidate"
        original_hash = digest(request("GET",original_url).content)
        if not browser_env:
            edited_reply = request("POST",turns,data={"request_id":edit_id,"previous":original_id,
                                                      "instruction":"Make it wider."}).json()
        edit = edited_reply["metadata"]["garment"]
        if args.live:
            require(edit["planner"].get("upstream_model") and edit["plan"]["action"] == "widen", "live edit planner gate")
        require(edit.get("parent_turn_id") == original_id and edit.get("edits"), "edit did not create a child candidate")
        final_url = f"{turns}/{edit_id}/candidate"
        before = digest(request("GET",final_url).content)
        require(before == edit["candidate_sha256"] and before != original_hash, "edited bytes disagree with metadata")
        history = request("GET",conv+"/messages").json()["items"]
        state = request("GET",conv).json()
        require(state["message_count"] == len(history) == 4 and state["user_id"] == uid, "durable session count or owner")
        saved = json.loads(sql(f"SELECT row_to_json(t) FROM (SELECT user_id,asset_path,asset_sha256,current_state,idempotency_key "
                               f"FROM yorvyn_jobs WHERE job_id='{job_id}') t"))
        # Parameterize opaque identifiers through psql variables in the database probe.
        evidence = subprocess.check_output(["psql",dsn,"-XAtq","-v","ON_ERROR_STOP=1","-v","owner="+uid,
                                            "-v","garment="+ctx["garment_id"]], text=True, stderr=subprocess.DEVNULL,
            input="SELECT specification FROM yorvyn_garment_evidence_specs WHERE user_id=:'owner' AND garment_id=:'garment';")
        require(json.loads(evidence) == ctx["recognition"] and saved["idempotency_key"] == f"{sid}:{original_id}",
                "durable evidence does not match conversation and job")
        asset = Path(saved["asset_path"])
        require(asset.parent.resolve() == (work/"assets").resolve() and saved["user_id"] == uid and saved["current_state"] == "COMPLETED"
                and digest(asset.read_bytes()) == saved["asset_sha256"] == edit["source_candidate_sha256"], "committed asset evidence")
        report.update(user_id=uid,conversation_id=sid,message_count=len(history),conversation_state=state["status"],
                      job_id=job_id,candidate_id=edit_id,parent_candidate_id=original_id,asset=asset.name,
                      committed_sha256=saved["asset_sha256"],original_sha256=original_hash,before_sha256=before)
        jobs = "/api/fashion/garment-gen/jobs"
        def submit(metadata):
            payload = {"category":"jacket", "idempotency_key":str(uuid.uuid4()), "detection_metadata":json.dumps(metadata)}
            return request("POST",jobs,files={"front_image":files["images"]},data=payload).json()["job_id"]

        broken = submit({"canonical_specification_v2":{"invalid":"missing evidence"}})
        for _ in range(30):
            if request("GET",f"{jobs}/{broken}").json()["status"] == "failed":
                break
            time.sleep(.25)
        else:
            raise GateError("worker failure was not reported")
        interrupted = submit({"source":"restart acceptance"})
        unfinished = request("GET",f"{jobs}/{interrupted}").json()
        require(unfinished["status"] not in {"completed","cancelled","failed","timed_out"}, "interruption missed active worker")
        stop(process, abrupt=True)
        require(process.poll() is not None, "original backend still running")
        fresh = start()
        require(fresh.pid != process.pid, "backend PID did not change")
        require(request("GET",conv).json() == state and request("GET",conv+"/messages").json()["items"] == history,
                "session or messages changed after restart")
        require(request("GET",job_url).json()["result"] == job["result"], "recovered job changed")
        after = digest(request("GET",final_url).content)
        require(after == before and digest(request("GET",original_url).content) == original_hash, "recovery hash mismatch")
        if browser_env:
            browser("recover", after)
            report["browser_recovery"] = PASS
        report.update(backend_pids=[process.pid,fresh.pid],after_sha256=after,restart=PASS)
        request("GET",conv,identity=None,code=401)
        request("GET",conv,auth=token(uid,-60),code=401)
        request("GET",conv,identity=other,code=404)
        request("GET",final_url,identity=other,code=404)
        request("GET",job_url,identity=other,code=403)
        request("GET",base+"/"+str(uuid.uuid4()),code=404)
        require(request("POST",turns,data=command).json()["id"] == reply["id"], "replay after restart changed reply")
        for subject, expected_count in ((uid, 4), (other, 0)):
            rows = requests.get(env["SUPABASE_URL"] + "/rest/v1/yorvyn_ai_messages",
                                headers={"Authorization":"Bearer " + token(subject)},
                                params={"session_id":f"eq.{sid}"}, timeout=5)
            require(rows.status_code == 200 and len(rows.json()) == expected_count, "database row ownership")
        request("POST",turns,data={"request_id":str(uuid.uuid4()),"previous":edit_id,
                                   "instruction":"Inspect"},code=429)
        require(request("GET",f"{jobs}/{broken}").json()["status"] == "failed", "worker failure lost on restart")
        for _ in range(90):
            incomplete = request("GET",f"{jobs}/{interrupted}").json()
            require(incomplete["result"] is None and incomplete["status"] != "completed", "interrupted job claimed success")
            if incomplete["status"] == "failed":
                break
            time.sleep(1)
        else:
            raise GateError("interrupted job never reached a terminal failure")
        report["interrupted_job"] = {"before": unfinished["status"], "after":incomplete["status"]}
        intact = asset.read_bytes()
        asset.unlink()
        request("GET",final_url,code=404)
        asset.write_bytes(b"damaged")
        request("GET",final_url,code=409)
        asset.write_bytes(intact)
        pgctl("stop")
        request("GET",conv,code=503)
        pgctl("start")
        report["negative_checks"] = ["anonymous","expired","cross-user session/candidate/job","unknown session",
                                     "duplicate before and after restart","missing asset","corrupt asset","database loss",
                                     "worker failure persisted across restart","interrupted worker deadline",
                                     "database row-level ownership","daily budget after restart"]
        report["status"] = PASS if args.live else PARTIAL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["preflight","recovery"])
    parser.add_argument("--photo", type=Path)
    parser.add_argument("--browser", action="store_true", help="Drive the existing Stylist for upload, edit and recovery")
    parser.add_argument("--live", action="store_true", help="Allow live providers in the isolated staging backend")
    parser.add_argument("--instruction", default="Create a 3D model of the denim jacket.")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    report = {"mode":args.mode,"environment":"disposable loopback staging","live_required":args.live}
    try:
        if args.mode == "preflight":
            report = preflight(args.photo)
        else:
            if args.live:
                require(args.photo, "explicit authorized --photo required for live inference")
                checks = preflight(args.photo)
                report["preflight"] = checks
                if checks["status"] != PASS:
                    print(json.dumps(dict(report,status=checks["status"]),indent=2))
                    return 2
                os.environ["GARMENT_CHAT_PLANNER"] = checks["selected_live_planner"]
            recovery(args,report)
    except GateError as exc:
        reason = str(exc)
        report.update(status=INFRA if reason.startswith("missing executable") else FAIL, reason=reason)
    except Exception as exc:
        report.update(status=FAIL,error_type=type(exc).__name__)
    print(json.dumps(report,indent=2))
    return 0 if report["status"] in {PASS,PARTIAL} else 2


if __name__ == "__main__":
    sys.exit(main())
