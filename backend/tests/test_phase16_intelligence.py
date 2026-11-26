"""Synthetic contract and scheduling checks; no holdout accuracy measurements."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from backend.app.services.intelligence import garment_policy as policy
from backend.app.services.intelligence.capability_registry import CapabilityRegistry, State, garment_capabilities
from backend.app.services.intelligence.garment_execution import Binding, ExecutionContext, GarmentRouter, Parameters, current_execution
from backend.app.services.intelligence.local_perception import local_vision
from backend.app.services.intelligence.provider_meter import post
from backend.app.services.ai.base import AIRequest, TaskType
from backend.app.services.llm.garment_plan import GarmentPlan


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv("YORVYN_STAGING_LIVE_RECEIPTS", raising=False)
    monkeypatch.setenv("GARMENT_CHAT_PLANNER", "offline_rules")


def context(i="turn"):
    return ExecutionContext("owner", "session", i)


def test_catalog_rejects_duplicates_and_exposes_verification():
    entries = garment_capabilities.entries()
    with pytest.raises(ValueError, match="Duplicate"):
        CapabilityRegistry([entries[0], entries[0]])
    for cap in entries:
        assert cap.input_schema and cap.output_schema and cap.dependencies and cap.limitation and cap.categories
    assert garment_capabilities.get("geometry.neural").availability == State.UNAVAILABLE
    assert garment_capabilities.get("evaluate.reprojection").availability == State.DECLARED


@pytest.mark.parametrize("instruction,images,candidate,action", [
    ("Create a 3d model of this dress", True, False, "reconstruct"),
    ("Shorten it", False, True, "shorten"), ("Undo", False, True, "undo"),
    ("Make the sleeves wider", False, True, "widen_sleeves"),
    ("Shorten and widen it", False, True, "clarify"), ("Don't shorten it", False, True, "clarify")])
def test_local_intents_never_contact_provider(monkeypatch, instruction, images, candidate, action):
    monkeypatch.setattr(policy, "plan_turn", lambda *a: pytest.fail("unnecessary external request"))
    result, trace = policy.route_intent(instruction, images, candidate, "owner")
    assert result.action == action and trace["provider"] == "local_rules"


def test_escalation_preserves_failures_and_limits_authority(monkeypatch):
    attempts = [{"error": "PERMISSION_DENIED"}]
    monkeypatch.setattr(policy, "plan_turn", lambda *a: (GarmentPlan(action="clarify"),
                                                        {"provider": "local_rules", "previous_attempts": attempts}))
    plan, trace = policy.route_intent("take up the drape", False, True, "owner")
    assert plan.action == "clarify" and trace["decision"] == policy.ASK and trace["previous_attempts"] == attempts
    for action, decision in (("shorten", policy.REASON), ("cancel", policy.ASK)):
        monkeypatch.setattr(policy, "plan_turn", lambda *a: (GarmentPlan(action=action), {"provider": "unit-double"}))
        _, trace = policy.route_intent("take up the drape", False, True, "owner")
        assert trace["decision"] == decision
    with pytest.raises(ValidationError):
        GarmentPlan(action="overwrite", path="arbitrary")


def test_reconstruction_decision_uses_evidence_and_capability_specific_confidence():
    spec = SimpleNamespace(views=[], conflicts=[], garment=SimpleNamespace(category="jacket", confidence=.99),
                           validate_evidence_integrity=lambda: [], model_execution_provenance={},
                           reconstruction_readiness=SimpleNamespace(status="PARTIAL"))
    assert policy.reconstruction_decision(spec)[0] == policy.ASK
    spec.views.append(SimpleNamespace(usable=True, view_type="FRONT"))
    assert policy.reconstruction_decision(spec)[0] == policy.LOCAL
    spec.model_execution_provenance["front"] = {"category_routing": {"identity_conflict": True}}
    assert policy.reconstruction_decision(spec)[0] == policy.ASK
    spec.model_execution_provenance.clear()
    spec.garment.confidence = .15
    assert policy.reconstruction_decision(spec)[0] == policy.ASK


@pytest.mark.parametrize("category,expected", [("jacket","image_conditioned"), ("hoodie","image_conditioned"),
                          ("dress","category_parametric"), ("bottoms","category_parametric"), ("footwear","category_parametric")])
def test_strategy(category, expected):
    assert policy.geometry_strategy(category, "") == expected


def test_inference_routing_checks_loaded_model_and_input_quality():
    req = AIRequest(request_id="fixture", image_bytes=b"synthetic", task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING)
    weak = dict(confidence=.31, category="jacket", subcategory="denim_jacket", model_id="fixture", device="cpu")
    cv = Mock()
    cv.is_available.return_value = False
    for unavailable in (None, weak):
        with pytest.raises(ValueError, match="Insufficient"):
            local_vision(req, cv, predict=lambda _: unavailable)
    strong = dict(weak, confidence=.83, sha256="fixture")
    run = context()
    run.requires_details = False
    token = current_execution.set(run)
    try:
        value = local_vision(req, cv, predict=lambda _: strong)
    finally:
        current_execution.reset(token)
    assert value.model_metadata.is_local and value.structured_data["garment"]["category"] == "jacket"
    cv.execute.assert_not_called()
    cv.is_available.return_value = True
    cv.execute.return_value = SimpleNamespace(success=True, structured_data={"garment":{"category":"dress"}})
    assert local_vision(req, cv, predict=lambda _: None).structured_data["model_execution_provenance"]["category_routing"]["classifier_fallback"]


@pytest.mark.asyncio
async def test_dispatch_validation_and_failure_receipts():
    router = GarmentRouter({"intent.plan": Binding(lambda: "invalid", lambda r: False, "rules", "action schema", 1)})
    run = context()
    for cap in ("not.a.capability", "geometry.neural", "avatar.attach"):
        with pytest.raises(ValueError):
            await router.execute(run, cap)
    with pytest.raises(ValidationError):
        await router.execute(run, "intent.plan", parameters={"filesystem": "/"})
    with pytest.raises(ValueError, match="Invalid result"):
        await router.execute(run, "intent.plan", refs=["turn:example"])
    op, = run.operations
    assert op["status"] == "FAILED" and op["capability_id"] == "intent.plan"
    assert op["task_id"] == run.task and op["duration_ms"] >= 0 and op["max_retries"] == 0
    assert Parameters.model_validate({"view_count":1}).view_count == 1


@pytest.mark.asyncio
async def test_timeout_holds_slot_until_native_work_finishes():
    finish, started = threading.Event(), threading.Event()
    def native():
        started.set()
        finish.wait(2)
        return True
    router = GarmentRouter({"intent.plan": Binding(native, bool, "test", "bool", .12)}, concurrency=1)
    first, second = context("first"), context("second")
    try:
        with pytest.raises(asyncio.TimeoutError):
            await router.execute(first, "intent.plan")
        assert started.is_set() and first.operations[0]["status"] == "TIMED_OUT"
        with pytest.raises(asyncio.TimeoutError):
            await router.execute(second, "intent.plan")
        assert "thread_cpu_ms" not in second.operations[0]
    finally:
        finish.set()
    await asyncio.sleep(.04)
    assert await router.execute(context(), "intent.plan")


@pytest.mark.asyncio
async def test_cancellation_and_concurrent_context_ownership():
    started, release = threading.Event(), threading.Event()
    def native(should_wait):
        if should_wait:
            started.set()
            release.wait(2)
        return current_execution.get().owner
    router = GarmentRouter({"intent.plan": Binding(native, bool, "test", "owner", 2)}, concurrency=2)
    first, second = context(), ExecutionContext("another-owner","other-session","other-task")
    pending = asyncio.create_task(router.execute(first,"intent.plan",True))
    try:
        assert await asyncio.to_thread(started.wait,1)
        assert await router.execute(second,"intent.plan",False) == second.owner
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert first.operations[0]["status"] == "CANCELLED"
        assert second.report({},policy.LOCAL)["quality"]["geometry_accuracy"] == "NOT_EVALUATED"
    finally:
        release.set()
        await asyncio.sleep(.02)


def test_measured_costs_remain_unknown_without_usage(monkeypatch):
    run = context()
    assert run.report({},policy.LOCAL)["accounting"]["external_input_tokens"] == 0
    token = current_execution.set(run)
    response = Mock(ok=True,status_code=200,headers={})
    response.json.return_value = {"model":"fixture","usage":{"prompt_tokens":7,"completion_tokens":3,"cost_usd":0.002}}
    monkeypatch.setattr("requests.post", lambda *a, **kw: response)
    try:
        post("synthetic","https://example.invalid", headers={"Authorization":"private-key"})
        assert run.report({},policy.REASON)["accounting"]["external_input_tokens"] == 7
        assert run.report({},policy.REASON)["accounting"]["provider_billed_usd"] == .002
        response.ok = False
        response.status_code = 429
        post("synthetic","https://example.invalid",retry=True)
    finally:
        current_execution.reset(token)
    report = run.report({},policy.REASON)
    assert report["accounting"]["provider_request_count"] == 2 and report["accounting"]["provider_retry_count"] == 1
    assert report["accounting"]["external_input_tokens"] is None and report["accounting"]["provider_billed_usd"] is None
    assert "private-key" not in repr(report) and "example.invalid" not in repr(report)


@pytest.mark.parametrize("actual,expected,loaded,state", [
    ("a","b",True,State.UNAVAILABLE), (None,None,False,State.UNAVAILABLE),
    ("a","a",False,State.UNAVAILABLE), ("a","a",True,State.VERIFIED)])
def test_live_model_state_is_distinct_from_release_history(actual, expected, loaded, state):
    model = SimpleNamespace(checkpoint_receipt={"valid":True,"expected_sha":expected,"actual_sha":actual},
                            device=SimpleNamespace(type="cpu"), _has_neural_model=loaded, _neural_model=object())
    assert garment_capabilities.classifier_status(model) == state


@pytest.mark.asyncio
async def test_owner_and_session_checks_precede_asset_access():
    from backend.app.api.conversational_garments import garment_router
    with pytest.raises(PermissionError):
        await garment_router.execute(context(), "candidate.inspect", {"job_id":"fixture"}, SimpleNamespace(user_id="elsewhere"))


@pytest.mark.asyncio
async def test_registered_quality_operations_keep_reference_and_fixture_status():
    import numpy as np
    from backend.app.api.conversational_garments import garment_router
    run = context()
    mask = np.eye(5, dtype=bool)
    missing = await garment_router.execute(run, "evaluate.surface", None, None)
    assert missing["status"] == "NOT_EVALUATED"
    value = await garment_router.execute(run, "evaluate.silhouette", mask, mask)
    assert value["iou"] == 1 and value["status"] == "SYNTHETIC_SMOKE_ONLY"

def test_classifier_device_error_degrades_to_live_local_adapter():
    def device_error(_):
        raise RuntimeError("sensitive diagnostic omitted")
    cv = Mock()
    cv.is_available.return_value = True
    cv.execute.return_value = SimpleNamespace(success=True, structured_data={"garment":{"category":"jacket"}})
    req = AIRequest(request_id="fixture", image_bytes=b"synthetic", task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING)
    result = local_vision(req, cv, predict=device_error)
    assert result.structured_data["model_execution_provenance"]["category_routing"]["classifier_fallback"] == "RuntimeError"
    assert "sensitive" not in repr(result.structured_data)
