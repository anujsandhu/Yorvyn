"""Garment tool turns in an existing authenticated stylist conversation."""
import asyncio
import json
import os
import hashlib
import io
import re
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image
from starlette.datastructures import Headers, UploadFile as MemoryUpload
from starlette.concurrency import run_in_threadpool

from backend.app.api.garment_generation_routes import cancel_job, retry_job, get_job_canonical_artifact
from backend.app.api.garment_identification_routes import (
    MAX_IMAGES_PER_REQUEST, MAX_IMAGE_FILE_SIZE_BYTES, MAX_TOTAL_BATCH_SIZE_BYTES,
    multiview_identify_endpoint, multiview_reconstruct_endpoint,
)
from backend.app.core.security import UserContext, get_current_user
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.garments.chat_candidate import EDIT_OPERATIONS, edit_candidate, remove_invalid_triangles
from backend.app.services.garments.job_manager import garment_job_manager
from backend.app.services.garments.mesh_validation_service import MeshValidationService
from backend.app.services.intelligence.garment_execution import ExecutionContext
from backend.app.services.intelligence.garment_adapters import create_garment_router
from backend.app.services.intelligence.garment_policy import ASK, reconstruction_decision

router = APIRouter(prefix="/api/ai/sessions", tags=["Conversational garments"])


def session_for(sid, user):
    session = supabase_repo.get_ai_session(str(sid), user.user_id)
    if not session or session.get("user_id") != user.user_id:
        raise HTTPException(404, "Conversation unavailable.")
    return session


def candidate_context(sid, turn_id, user):
    record = supabase_repo.get_message_by_request_id(user.user_id, f"{sid}:{turn_id}:reply")
    if not record or record["session_id"] != str(sid) or record["role"] != "assistant":
        raise HTTPException(404, "Garment turn unavailable.")
    return record["metadata"]["garment"]


def isolate_subject(data, question):
    """Keep the full view unless the detector finds competing garment instances."""
    from backend.app.services.garments.intelligence.garment_instance_detector import garment_instance_detector
    with Image.open(io.BytesIO(data)) as image:
        scene = garment_instance_detector.detect_instances(image)
        choices = [i for i in scene.instances if i.reconstruction_eligible]
        if len(choices) < 2:
            return None, []
        matches = [i for i in choices if any(
            re.search(r"\b" + re.escape(label.lower().replace("_", " ")) + r"\b", question.lower())
            for label in (i.category, i.subcategory, i.display_name) if label)]
        if len(matches) != 1:
            return None, [i.display_name for i in choices]
        # Use the detector's original pixel bounds so the input remains photographic.
        cropped = image.convert("RGB").crop(matches[0].bbox)
        buffer = io.BytesIO()
        cropped.save(buffer, "PNG")
        buffer.seek(0)
        return buffer, []


async def candidate_bytes(ctx, user):
    job = await run_in_threadpool(garment_job_manager.get_job, ctx["job_id"])
    if not job or job.user_id != user.user_id:
        raise HTTPException(404, "Garment job unavailable.")
    if job.status.value != "completed":
        raise HTTPException(409, "The garment job has not completed.")
    response = await get_job_canonical_artifact(job.job_id, user)
    data = await run_in_threadpool(Path(response.path).read_bytes)
    source_hash = hashlib.sha256(data).hexdigest()
    if supabase_repo.require_durable_sessions and not job.asset_sha256:
        raise HTTPException(409, "Reconstruction has no committed asset checksum.")
    if job.asset_sha256 and source_hash != job.asset_sha256:
        raise HTTPException(409, "The garment asset failed its committed checksum.")
    if ctx.get("source_candidate_sha256", source_hash) != source_hash:
        raise HTTPException(409, "The original candidate changed. Reopen its original turn before editing.")
    for edit in ctx.get("edits", []):
        if edit == "remove_invalid_triangles":
            data = await run_in_threadpool(remove_invalid_triangles, data)
        else:
            data = await run_in_threadpool(edit_candidate, data, edit)
    report = await run_in_threadpool(MeshValidationService.validate_glb_bytes, data, ctx["category"])
    if not report.is_valid and (report.degenerate_faces or report.duplicate_faces):
        repaired = await run_in_threadpool(remove_invalid_triangles, data)
        inspection = await run_in_threadpool(MeshValidationService.validate_glb_bytes, repaired, ctx["category"])
        if inspection.is_valid:
            return repaired, dict(inspection.to_dict(), source_candidate_sha256=source_hash, repair="remove_invalid_triangles", before=report.to_dict())
    if not report.is_valid:
        raise HTTPException(422, "Candidate failed mesh inspection. " + " ".join(report.issues[:3]))
    return data, dict(report.to_dict(), source_candidate_sha256=source_hash)


async def control_job(action, job_id, user):
    if action == "retry":
        job = await run_in_threadpool(garment_job_manager.get_job, job_id)
        if job and job.user_id == user.user_id and job.retry_count >= 2 and job.status.value == "failed":
            raise HTTPException(409, "Reconstruction has failed repeatedly. Please add a clearer front or side view.")
    if action == "cancel":
        return await cancel_job(job_id, user)
    if action == "retry":
        return await retry_job(job_id, user)
    raise ValueError("Unsupported job operation")


garment_router = create_garment_router(isolate_subject, multiview_identify_endpoint, multiview_reconstruct_endpoint,
                                       candidate_bytes, candidate_context, control_job)


@router.get("/{session_id}/garment-turns/{turn_id}/candidate")
async def download_candidate(session_id: uuid.UUID, turn_id: uuid.UUID, user=Depends(get_current_user)):
    await run_in_threadpool(session_for, session_id, user)
    ctx = await run_in_threadpool(candidate_context, session_id, turn_id, user)
    if not ctx.get("job_id"):
        raise HTTPException(409, "This turn has no reconstruction.")
    execution = ExecutionContext(user.user_id, session_id, turn_id)
    data, _ = await garment_router.execute(execution, "candidate.inspect", ctx, user, refs=[ctx["job_id"]])
    if ctx.get("candidate_sha256") and hashlib.sha256(data).hexdigest() != ctx["candidate_sha256"]:
        raise HTTPException(409, "Candidate checksum mismatch.")
    return Response(data, media_type="model/gltf-binary", headers={
        "Cache-Control": "private, no-store", "ETag": '"' + hashlib.sha256(data).hexdigest() + '"'})


def record_activity(sid, turn, label, done=False):
    client = garment_job_manager._redis_broker.client
    key = f"chat:garment:events:{sid}:{turn}"
    pipe = client.pipeline()
    pipe.xadd(key, {"activity":label, "done":"1" if done else "0"}, maxlen=24)
    pipe.expire(key, 600)
    pipe.execute()


@router.get("/{session_id}/garment-turns/{turn_id}/activity")
async def garment_activity(session_id: uuid.UUID, turn_id: uuid.UUID, user=Depends(get_current_user)):
    await run_in_threadpool(session_for, session_id, user)
    async def stream():
        cursor = "0-0"
        deadline = time.monotonic() + 180
        client = garment_job_manager._redis_broker.client
        key = f"chat:garment:events:{session_id}:{turn_id}"
        while time.monotonic() < deadline:
            events = await run_in_threadpool(client.xrange, key, min=f"({cursor}", count=24)
            for cursor, event in events:
                yield json.dumps({"activity":event["activity"]}) + "\n"
                if event["done"] == "1":
                    return
            await asyncio.sleep(.5)
    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control":"private, no-store","X-Accel-Buffering":"no"})


async def turn_access(session_id: uuid.UUID, request_id: uuid.UUID = Form(...), user=Depends(get_current_user)):
    await run_in_threadpool(session_for, session_id, user)
    from redis.exceptions import RedisError
    client = garment_job_manager._redis_broker.client
    budget_key = f"chat:garment:minute:{user.user_id}:{int(time.time()) // 60}"
    lock = client.lock(f"chat:garment:turn:{session_id}:{request_id}", timeout=600, thread_local=False)
    try:
        pipeline = client.pipeline()
        pipeline.incr(budget_key)
        pipeline.expire(budget_key, 120)
        count, _ = await run_in_threadpool(pipeline.execute)
        if count > 12:
            raise HTTPException(429, "Garment request limit reached. Try again in a minute.")
        if not await run_in_threadpool(lock.acquire, blocking=False):
            raise HTTPException(409, "This garment request is already processing.")
    except RedisError as exc:
        raise HTTPException(503, "Garment request scheduling is unavailable.") from exc
    try:
        yield user
    finally:
        if await run_in_threadpool(lock.owned):
            await run_in_threadpool(lock.release)


@router.post("/{session_id}/garment-turns")
async def garment_turn(session_id: uuid.UUID, request_id: uuid.UUID = Form(...),
                       instruction: str = Form(..., min_length=1, max_length=2000),
                       previous: uuid.UUID = Form(None), images: List[UploadFile] = File(default=[]),
                       user: UserContext = Depends(turn_access)):
    session = await run_in_threadpool(session_for, session_id, user)
    if session["status"] != "active":
        raise HTTPException(409, "This conversation is archived.")
    sid = str(session_id)
    key = f"{sid}:{request_id}"
    prior = await run_in_threadpool(supabase_repo.get_message_by_request_id, user.user_id, key + ":reply")
    if prior and prior["session_id"] == sid:
        return prior
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(413, "Too many garment views.")
    # Charge a daily ceiling on provider work, including failed attempts. A multi-view
    # request can fan out to multiple provider calls, so count its views separately.
    client = garment_job_manager._redis_broker.client
    daily = f"chat:garment:daily:{user.user_id}:{int(time.time()) // 86400}"
    pipe = client.pipeline()
    pipe.incrby(daily, 1 + len(images))
    pipe.expire(daily, 172800)
    used, _ = await run_in_threadpool(pipe.execute)
    if used > int(os.environ.get("GARMENT_CHAT_DAILY_UNITS", "120")):
        raise HTTPException(429, "Daily garment analysis budget reached.")
    total = 0
    for upload in images:
        data = await upload.read(MAX_IMAGE_FILE_SIZE_BYTES + 1)
        total += len(data)
        if len(data) > MAX_IMAGE_FILE_SIZE_BYTES or total > MAX_TOTAL_BATCH_SIZE_BYTES:
            raise HTTPException(413, "Garment images exceed the upload limit.")
        try:
            with Image.open(io.BytesIO(data)) as image:
                if (image.format not in {"JPEG", "PNG", "WEBP"} or Image.MIME[image.format] != upload.content_type
                        or image.width * image.height > 50_000_000):
                    raise ValueError
                image.verify()
        except (OSError, ValueError, Image.DecompressionBombError, SyntaxError) as exc:
            raise HTTPException(422, "Use a readable JPEG, PNG or WebP garment image.") from exc
        await upload.seek(0)
    execution = ExecutionContext(user.user_id, sid, request_id)
    prior_ctx = await garment_router.execute(execution, "candidate.history", session_id, previous, user,
                                              refs=[str(previous)]) if previous else {}
    ctx = {} if images else dict(prior_ctx)
    await run_in_threadpool(record_activity, sid, request_id, "Planning the garment request…")
    try:
        plan, trace = await garment_router.execute(execution, "intent.plan", instruction, bool(images),
                                                  bool(ctx.get("job_id")), user.user_id, refs=[key],
                                                  parameters={"view_count": len(images)})
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "Garment planning timed out.") from exc
    decision = trace["decision"]
    execution.requires_details = plan.action != "identify" or bool(re.search(
        r"\b(component|sleeve|collar|pocket|closure|fabric|texture|pattern)s?\b", instruction, re.I))
    if trace.get("previous_attempts"):
        execution.operations[-1]["fallback_reason"] = trace["reason"]
    await run_in_threadpool(supabase_repo.create_ai_message, sid, user.user_id, "user", instruction, request_id=key + ":user")
    ctx.pop("last_error", None)
    text = "Which change would you like to make to the garment?"
    try:
        if images:
            await run_in_threadpool(record_activity, sid, request_id, "Locating garments in the photos…")
            inputs = []
            hashes = []
            selected_subject = False
            for upload in images:
                raw = await upload.read()
                hashes.append(hashlib.sha256(raw).hexdigest())
                crop, choices = await garment_router.execute(execution, "subject.select", raw, instruction, refs=[hashes[-1]])
                if choices:
                    decision = ASK
                    ctx["pending_action"] = plan.action
                    raise HTTPException(409, "Which garment should I use? I found " + ", ".join(choices[:6]) + ".")
                await upload.seek(0)
                selected_subject = selected_subject or crop is not None
                inputs.append(MemoryUpload(crop, filename="crop.png", headers=Headers({"content-type":"image/png"})) if crop else upload)
            await run_in_threadpool(record_activity, sid, request_id, "Analyzing the selected garment and its views…")
            spec = await garment_router.execute(execution, "views.identify", inputs, None, None, False, user.user_id, user,
                                                refs=hashes, parameters={"view_count": len(inputs)})
            execution.operations[-1]["result_ref"] = spec.garment_id
            if execution.requires_details:
                comp_inputs = []
                for idx_u, upload in enumerate(inputs):
                    await upload.seek(0)
                    raw_u = await upload.read()
                    await upload.seek(0)
                    view_hint_u = spec.views[idx_u].view_type if idx_u < len(spec.views) else None
                    comp_inputs.append((spec.views[idx_u].image_id if idx_u < len(spec.views) else (upload.filename or f"view_{idx_u+1}"), raw_u, view_hint_u))
                comp_bundle = await garment_router.execute(
                    execution,
                    "components.identify",
                    comp_inputs,
                    spec.garment_id,
                    spec.garment.category,
                    spec.garment.subcategory,
                    spec.views,
                    refs=hashes,
                    parameters={"category": spec.garment.category, "subcategory": spec.garment.subcategory, "view_count": len(comp_inputs)},
                )
                execution.operations[-1]["result_ref"] = f"{spec.garment_id}:components"
                if comp_bundle.handoff.clarification_prompts and plan.action == "identify":
                    spec.clarification_prompts = list(comp_bundle.handoff.clarification_prompts)
            ctx = {"garment_id": spec.garment_id, "category": spec.garment.category,
                   "recognition": spec.model_dump(mode="json"), "source_sha256": hashes, "edits": []}
            text = spec.natural_language_explanation or f"I identified a {spec.garment.subcategory}."
            if plan.action == "identify" and spec.clarification_prompts:
                text = f"{text} {spec.clarification_prompts[0]}"
            if plan.action == "reconstruct" or (selected_subject and prior_ctx.get("pending_action") == "reconstruct" and plan.action not in {"cancel", "clarify"}):
                decision, reason = reconstruction_decision(spec)
                if decision == ASK:
                    raise HTTPException(409, reason)
                for upload in inputs:
                    await upload.seek(0)
                await run_in_threadpool(record_activity, sid, request_id, "Submitting reconstruction…")
                job = await garment_router.execute(execution, "geometry.submit", spec.model_dump_json(), inputs,
                                                   user.user_id, None, None, key, user, refs=[spec.garment_id, *hashes],
                                                   parameters={"category": spec.garment.category,
                                                               "subcategory": spec.garment.subcategory, "view_count": len(inputs)})
                execution.operations[-1]["result_ref"] = job["job_id"]
                ctx["job_id"] = job["job_id"]
                text += " Reconstruction has started."
            elif plan.action not in {"identify", "inspect"}:
                text += " Ask me to create a 3D model with these photos before editing it."
        elif ctx.get("job_id"):
            if plan.action in EDIT_OPERATIONS:
                if len(ctx["edits"]) >= 12:
                    raise HTTPException(409, "Undo an edit before adding another.")
                await run_in_threadpool(record_activity, sid, request_id, "Inspecting the original and edited geometry…")
                _, before = await garment_router.execute(execution, "candidate.inspect", ctx, user, refs=[ctx["job_id"]])
                parent_edits = list(ctx["edits"])
                if before.get("repair"):
                    parent_edits.append("remove_invalid_triangles")
                proposed = dict(ctx, edits=[*parent_edits, plan.action], parent_turn_id=str(previous))
                data, report = await garment_router.execute(execution, "candidate.edit", proposed, user,
                                                           refs=[before["source_candidate_sha256"], str(previous)],
                                                           parameters={"action": plan.action})
                ctx = dict(proposed, source_candidate_sha256=before["source_candidate_sha256"], previous_mesh_report=before, mesh_report=report, candidate_sha256=hashlib.sha256(data).hexdigest())
                execution.operations[-1]["result_ref"] = ctx["candidate_sha256"]
                text = {
                    "widen": "I widened the garment by 10%.",
                    "shorten": "I shortened the garment by 10%.",
                    "widen_sleeves": "I widened the sleeve cross-sections by 10%.",
                    "denim": "I applied an indigo denim appearance and preserved the texture.",
                }[plan.action] + " The edited candidate passed mesh inspection."
            elif plan.action == "undo" and ctx["edits"]:
                if ctx.get("parent_turn_id"):
                    ctx = dict(await garment_router.execute(execution, "candidate.history", session_id, ctx["parent_turn_id"],
                                                            user, refs=[ctx["parent_turn_id"]]))
                else:
                    # Older turns store the edit list without a parent turn.
                    ctx["edits"] = ctx["edits"][:-1]
                    if ctx["edits"][-1:] == ["remove_invalid_triangles"]:
                        ctx["edits"].pop()
                    for field in ("candidate_sha256", "mesh_report", "previous_mesh_report"):
                        ctx.pop(field, None)
                text = "Restored the previous garment candidate."
            elif plan.action in {"cancel", "retry"}:
                result = await garment_router.execute(execution, "job.control", plan.action, ctx["job_id"], user,
                                                      refs=[ctx["job_id"]], parameters={"action": plan.action})
                if plan.action == "cancel":
                    text = "The reconstruction was cancelled."
                else:
                    text = result.get("current_stage") or "Check the job for its retry status."
            elif plan.action in {"inspect", "reconstruct"}:
                from backend.app.services.llm.garment_plan import parse_stylist_design_command
                cmd = parse_stylist_design_command(instruction)
                if cmd:
                    ctx["design_command"] = cmd
                    text = cmd["reply"]
                else:
                    text = "Here is the current garment candidate."
        else:
            text = "Attach the garment photos to start reconstruction."
    except HTTPException as error:
        if error.status_code == 409 and "view" in str(error.detail).lower():
            decision = ASK
        text = str(error.detail)
        ctx["last_error"] = text
    except asyncio.TimeoutError:
        text = "Garment processing timed out. Check the current job before retrying."
        ctx["last_error"] = text
    except ValueError as error:
        text = str(error)
        ctx["last_error"] = text
    ctx["intelligence_execution"] = execution.report(ctx, decision)
    ctx.update(turn_id=str(request_id), plan=plan.model_dump(), planner=trace)
    await run_in_threadpool(record_activity, sid, request_id, "Garment response ready.", done=True)
    return await run_in_threadpool(supabase_repo.create_ai_message, sid, user.user_id, "assistant", text,
                                           metadata={"garment": ctx}, request_id=key + ":reply")
