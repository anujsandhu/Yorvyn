"""Release checks use real files. Provider diagnostic tests use isolated response doubles."""
import json

import numpy as np
import pytest
import requests
import torch
from PIL import Image

from backend.app.services.ai.provider_diagnostics import exception_failure, http_failure
from backend.app.services.llm.garment_plan import llm_registry, plan_turn
from backend.app.services.ml.model_registry import UnifiedModelRegistry, unified_model_registry
from scripts.verify_staging_garment import MISSING, PHOTO, preflight


def http_reply(status, data):
    response = requests.Response()
    response.status_code = status
    response.headers["x-request-id"] = "fixture-id"
    response._content = json.dumps(data).encode()
    return response


@pytest.mark.parametrize("status,error,expected", [
    (401, {}, "INVALID_CREDENTIAL"),
    (400, {"details": [{"reason": "API_KEY_INVALID"}]}, "INVALID_CREDENTIAL"),
    (403, {}, "PERMISSION_DENIED"),
    (404, {"code": "model_not_found"}, "UNSUPPORTED_MODEL"),
    (400, {"message": "model does not support image inputs"}, "UNSUPPORTED_MODALITY"),
    (400, {"status": "INVALID_ARGUMENT"}, "INVALID_REQUEST_SCHEMA"),
    (429, {"code": "rate_limit_exceeded"}, "RATE_LIMIT"),
    (429, {"message": "exceeded your current quota", "quotaId": "RequestsPerMinute"}, "RATE_LIMIT"),
    (429, {"code": "insufficient_quota"}, "QUOTA_EXHAUSTED"),
    (402, {}, "QUOTA_EXHAUSTED"),
    (504, {}, "TIMEOUT"),
    (502, {}, "HTTP_ERROR"),
])
def test_upstream_codes(status, error, expected):
    assert http_failure(http_reply(status, {"error": error})) == expected


@pytest.mark.parametrize("exc,code", [(requests.exceptions.SSLError(), "TLS_FAILED"),
                                      (requests.Timeout(), "TIMEOUT"),
                                      (requests.ConnectionError(), "NETWORK_FAILURE")])
def test_transport_failures(exc, code):
    assert exception_failure(exc) == code


@pytest.mark.parametrize("name", ["groq", "openrouter", "gemini"])
@pytest.mark.parametrize("status,body,expected", [
    (429, {"error": {"code": "insufficient_quota", "message": "private-body"}}, "QUOTA_EXHAUSTED"),
    (200, [], "MALFORMED_OUTPUT"),
    (200, {"choices": [], "candidates": []}, "MALFORMED_OUTPUT")
])
def test_planner_probe_fails_without_local_substitution(monkeypatch, name, status, body, expected):
    monkeypatch.setattr(llm_registry.get_provider(name), "_api_key", "test-credential")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: http_reply(status, body))
    plan, trace = plan_turn("reconstruct", True, False, provider_only=name)
    assert plan is None and trace["provider"] is None
    attempt, = trace["previous_attempts"]
    assert attempt["error"] == expected and attempt["upstream_request_id"] == "fixture-id"
    assert "private-body" not in repr(trace) and "test-credential" not in repr(trace)


def test_missing_credentials_block_every_preflight_gate(monkeypatch):
    monkeypatch.delenv("GARMENT_CHAT_PLANNER", raising=False)
    from backend.app.core.settings import settings
    for key in ("google_api_key", "gemini_api_key"):
        monkeypatch.setattr(settings, key, "")
        monkeypatch.delenv(key.upper(), raising=False)
    for name in ("groq", "openrouter", "gemini"):
        monkeypatch.setattr(llm_registry.get_provider(name), "_api_key", "")
    monkeypatch.setattr(requests, "post", lambda *a, **kw: pytest.fail("unexpected network call"))
    result = preflight(PHOTO)
    assert result["status"] == MISSING
    for row in [result["vision"], *result["planners"]]:
        assert row["status"] == MISSING and not row["capability_verified"]
        assert row["endpoint_reachable"] is None


@pytest.mark.parametrize("entries", [
    '"a":{"model_id":"same"},"b":{"model_id":"same"}',
    '"a":{"model_id":"first"},"first":{"model_id":"second"}',
    '"a":{"model_id":"first"},"a":{"model_id":"second"}',
    '"external":{"model_id":"depth_anything_v2"}',
])
def test_duplicate_identity_is_an_initialization_error(tmp_path, entries):
    path = tmp_path / "registry.json"
    path.write_text('{"models":{' + entries + '}}')
    with pytest.raises(ValueError, match="Duplicate"):
        UnifiedModelRegistry(str(path))


def test_registry_order_aliases_and_metadata():
    registry = UnifiedModelRegistry()
    assert registry.list_models() == unified_model_registry.list_models()
    assert registry.get_model("universal_garment_classifier") is registry.get_model("universal-garment-classifier")
    ids = []
    for model in registry.list_models():
        assert {"version", "artifact_identity", "capabilities", "availability_status", "confidence_limitations",
                "hardware_requirements", "execution_cost", "input_schema", "output_schema", "execution_type"} <= model.keys()
        ids.append(model["model_id"])
    assert ids == sorted(set(ids))


def test_reject_unpinned_or_modified_bytes(tmp_path, monkeypatch):
    registry = UnifiedModelRegistry()
    monkeypatch.setattr(registry, "repo_root", tmp_path)
    spec = registry.get_model("universal-garment-classifier")["server"]
    spec["checkpoint_path"] = "modified.pt"
    (tmp_path / "modified.pt").write_bytes(b"replacement")
    for digest in (None, "0" * 64):
        spec["sha256_checksum"] = digest
        receipt, weights = registry.read_server_checkpoint("universal-garment-classifier")
        assert not receipt["valid"] and weights is None


@pytest.mark.requires_local_assets
def test_real_photo_through_release_classifier():
    from backend.app.services.garments.intelligence.universal_garment_classifier import (
        NEURAL_CATEGORIES, NEURAL_SUBCATEGORIES, universal_garment_classifier as classifier)
    assert classifier._has_neural_model
    assert classifier.checkpoint_receipt["actual_sha"] == "1cc5d8a9afddb8113ec90258d73e51f8382418f5c7e053ba037286db2a49c3fc"
    with Image.open(PHOTO) as photo, torch.inference_mode():
        rgb = photo.convert("RGB")
        category, subcategory = classifier._neural_model(classifier._transform(rgb).unsqueeze(0).to(classifier.device))
        for vector, size in ((category, len(NEURAL_CATEGORIES)), (subcategory, len(NEURAL_SUBCATEGORIES))):
            assert vector.shape == (1, size)
            assert torch.isfinite(vector).all() and (vector >= 0).all()
            assert vector.sum().item() == pytest.approx(1, abs=1e-5)
        result = classifier.classify_hierarchical(rgb, np.full((rgb.height, rgb.width), 255, dtype=np.uint8))
    assert result["model_prediction"]["raw_category"] == NEURAL_CATEGORIES[category.argmax().item()]
    assert set(result["model_probabilities"]) == set(NEURAL_CATEGORIES)
    print("Neural prediction:", result["model_prediction"]["raw_category"], result["model_confidence"])


@pytest.mark.requires_local_assets
@pytest.mark.parametrize("case", ["simulated", "cached", "missing_model"])
def test_preflight_rejects_vision_results_without_live_evidence(monkeypatch, case):
    from backend.app.services.ai.base import AIProviderResponse, ModelMetadata
    from backend.app.services.ai.providers.gemini_provider import GeminiVisionProvider
    monkeypatch.setattr(GeminiVisionProvider, "is_available", lambda self: True)

    def double(self, request):
        return AIProviderResponse(request_id=request.request_id, task_type=request.task_type, success=True,
                                  provider_name=self.name, cached=case == "cached",
                                  upstream_model=None if case == "missing_model" else "test-model",
                                  model_metadata=ModelMetadata(provider_name=self.name, model_name="test-model",
                                                               device="cloud-simulated" if case == "simulated" else "cloud"))
    monkeypatch.setattr(GeminiVisionProvider, "execute", double)
    for name in ("groq", "gemini", "openrouter"):
        monkeypatch.setattr(llm_registry.get_provider(name), "_api_key", "")
    report = preflight(PHOTO)
    assert report["vision"]["error"] == "MISSING_LIVE_EVIDENCE"
    assert not report["vision"]["capability_verified"] and report["selected_live_planner"] is None


def test_stylist_preserves_diagnostic_without_logging_sensitive_details(caplog):
    from backend.app.services.ai.provider_diagnostics import ProviderHTTPError
    from backend.app.services.llm.error_handler import LLMErrorHandler, LLMErrorType
    exc = ProviderHTTPError.from_response(http_reply(403, {"error": "private-content"}))
    code = LLMErrorHandler.classify_exception(exc)
    assert code == LLMErrorType.PERMISSION_DENIED
    assert LLMErrorHandler.create_fallback_response(code, "", "private-detail")["is_fallback"]
    assert "private" not in caplog.text
