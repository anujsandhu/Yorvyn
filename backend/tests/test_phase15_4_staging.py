"""Unit checks for Phase 15.4. Provider responses in this file are test doubles."""
import base64
import io
import json

import pytest
import requests
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from backend.app.services.ai.base import AIRequest, TaskType
from backend.app.services.ai.providers.gemini_provider import GeminiVisionProvider
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.llm.garment_plan import GarmentPlan, llm_registry, plan_turn
from backend.app.services.llm.base import LLMResponse, ToolCallRequest


def image_request():
    out = io.BytesIO()
    Image.new("RGB", (8, 8)).save(out, "PNG")
    return AIRequest(request_id="test", task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING,
                     image_bytes=out.getvalue(), image_mime_type="image/png")


def reply(status, body):
    response = requests.Response()
    response.status_code = status
    response.headers["x-request-id"] = "test-request"
    response._content = json.dumps(body).encode()
    return response


def test_vision_forwards_exact_bytes_and_records_response_identity(monkeypatch):
    req = image_request()
    def send(url, *, json, headers, timeout):
        assert "key=" not in url
        inline = json["contents"][0]["parts"][1]["inline_data"]
        assert inline["mime_type"] == "image/png" and base64.b64decode(inline["data"]) == req.image_bytes
        return reply(200, {"modelVersion":"test-model-version","responseId":"test-response","usageMetadata":{
            "promptTokenCount":17, "candidatesTokenCount":4, "totalTokenCount":21},
            "candidates":[{"content":{"parts":[{"text":'{"garment":{"category":"jacket","subcategory":"denim","confidence":0.6}}'}]}}]})
    monkeypatch.setattr(requests, "post", send)
    result = GeminiVisionProvider(api_key="unit-test").execute(req)
    assert result.success and result.upstream_model == "test-model-version"
    assert result.upstream_request_id == "test-response" and result.token_usage.total_tokens == 21


@pytest.mark.parametrize("status,code", [(401,"INVALID_CREDENTIAL"), (403,"PERMISSION_DENIED"), (200,"MALFORMED_OUTPUT")])
def test_vision_rejects_errors_without_echoing_provider_content(monkeypatch, status, code):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: reply(status, {"private":"private-test-payload"}))
    result = GeminiVisionProvider(api_key="unit-test").execute(image_request())
    assert not result.success and result.error.error_code == code
    assert "private-test-payload" not in result.model_dump_json()


def test_vision_timeout_is_not_execution_evidence(monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout
    monkeypatch.setattr(requests, "post", timeout)
    result = GeminiVisionProvider(api_key="unit-test").execute(image_request())
    assert not result.success and result.error.error_code == "TIMEOUT" and result.upstream_model is None


@pytest.mark.parametrize("arguments", [{"action":"unsupported"}, {"action":"widen","arbitrary":"extra"}, {}])
def test_invalid_planner_arguments_cannot_be_returned_as_a_live_plan(monkeypatch, arguments):
    class Stub:
        def health_check(self):
            return True

        def generate(self, *args, **kwargs):
            return LLMResponse(provider_used="test",model_used="test",
                               tool_calls=[ToolCallRequest(id="test",function_name="plan_garment",arguments=arguments)])
    with pytest.raises(ValidationError):
        GarmentPlan.model_validate(arguments)
    monkeypatch.setenv("GARMENT_CHAT_PLANNER","test")
    monkeypatch.setenv("GARMENT_CHAT_FALLBACK_PLANNER","offline_rules")
    monkeypatch.setattr(llm_registry,"get_provider",lambda name: Stub())
    _, trace = plan_turn("inspect",False,True)
    assert trace["provider"] == "local_rules" and trace["previous_attempts"][0]["error_type"] == "ValidationError"


def test_durable_session_reads_fail_closed_on_outage(monkeypatch):
    monkeypatch.setenv("YORVYN_REQUIRE_DURABLE_SESSIONS","1")
    monkeypatch.setattr(supabase_repo,"_supabase_url","http://127.0.0.1")
    monkeypatch.setattr(supabase_repo,"_service_key","unit-test")
    monkeypatch.setitem(supabase_repo._ai_sessions,"unit",{"id":"unit","user_id":"test","status":"active"})
    monkeypatch.setattr(requests,"request",lambda *a,**kw: reply(503,{}))
    with pytest.raises(HTTPException) as exc:
        supabase_repo.get_ai_session("unit","test")
    assert exc.value.status_code == 503
    monkeypatch.setattr(requests,"request",lambda *a,**kw: reply(200,[]))
    assert supabase_repo.get_ai_session("unit","test") is None
