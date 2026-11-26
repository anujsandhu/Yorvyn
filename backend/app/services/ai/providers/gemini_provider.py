"""
YORVYN — Google Gemini Vision Multimodal Garment Intelligence Provider (Phase 14.26)
Integrates Google Gemini multimodal models (gemini-2.5-flash / gemini-1.5-flash) for
fine-grained visual garment understanding:
- Multi-category identification & component localization
- Strict JSON schema generation with response_mime_type="application/json"
- Distinguishes visible evidence vs inferred properties vs unknown properties
- Bounded retries, exponential backoff, rate-limit capture, error normalization
- Safe offline fallback when credentials are absent or blocked
"""

from __future__ import annotations

import os
import json
import base64
import time
import logging
from typing import Dict, Any, List, Optional
import requests
from backend.app.services.intelligence import provider_meter

from backend.app.services.ai.provider_diagnostics import http_failure, exception_failure
from backend.app.core.settings import settings
from backend.app.services.ai.base import (
    AIProvider,
    AIRequest,
    AIProviderResponse,
    ProviderCapability,
    ProviderHealth,
    ProviderHealthState,
    ProviderError,
    ModelMetadata,
    TokenUsage,
    TaskType,
    EvidenceStatus
)

logger = logging.getLogger(__name__)

GEMINI_GARMENT_PROMPT = """You are an expert AI garment technologist and fashion patternmaker.
Analyze the provided garment photograph with forensic geometric precision.
Distinguish strictly between DIRECTLY VISIBLE evidence, INFERRED properties, and UNKNOWN/UNOBSERVABLE details.
Do NOT invent hidden internal construction details that are not visible.

Return ONLY a valid JSON object matching this exact schema:
{
  "garment": {
    "category": "<hoodie | shirt | jacket | tshirt | sweater | sweatshirt | coat | dress | kurta | tunic | jeans | trousers | shorts | skirt | traditional_clothing>",
    "subcategory": "<e.g. pullover_hoodie, denim_jacket, formal_dress_shirt, graphic_tshirt>",
    "confidence": <float between 0.0 and 1.0>
  },
  "components": {
    "hood": {"present": <bool>, "type": "<cowl | standard | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "sleeves": {"present": <bool>, "type": "<long | short | sleeveless | raglan>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "pockets": {"present": <bool>, "type": "<kangaroo | chest_flap | welt | patch | five_pocket | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "neckline": {"present": <bool>, "type": "<hooded | crewneck | v_neck | mandarin | collared | scoop>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "collar": {"present": <bool>, "type": "<turn_down | button_down | mandarin | ribbed | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "closure": {"present": <bool>, "type": "<pullover | zipper | button_placket | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "cuffs": {"present": <bool>, "type": "<ribbed | barrel | straight | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"},
    "hem": {"present": <bool>, "type": "<ribbed_waistband | curved_shirttail | straight | none>", "confidence": <float>, "evidence_status": "<observed | inferred | unknown | not_applicable>"}
  },
  "appearance": {
    "primary_color": "<color name>",
    "secondary_color": "<color name or null>",
    "pattern": "<solid | striped | plaid | graphic | floral | cable_knit>",
    "fabric_appearance": "<fleece-like | denim_twill | knit | smooth_cotton | woven>"
  },
  "orientation": "<front | back | side | angled>",
  "visible_evidence": ["<list of directly observable features>"],
  "inferred_properties": ["<list of inferred features based on context>"],
  "unknown_properties": ["<list of features occluded or unobservable>"],
  "quality": {
    "image_usable": <bool>,
    "occlusion_detected": <bool>,
    "contrast_acceptable": <bool>,
    "ambiguity_notes": ["<any lighting, fold, or crop warnings>"]
  }
}
"""


class GeminiVisionProvider(AIProvider):
    """Production adapter for Google Gemini multimodal vision intelligence."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 20.0
    ):
        super().__init__("gemini_vision")
        self._api_key = (
            api_key or
            os.environ.get("GEMINI_API_KEY") or
            os.environ.get("GOOGLE_API_KEY") or
            getattr(settings, "gemini_api_key", None) or
            getattr(settings, "google_api_key", None) or
            ""
        )
        self.model_name = model_name or getattr(settings, "gemini_model", "gemini-2.5-flash")
        self.timeout_seconds = timeout_seconds
        self.api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.VISION_MULTIMODAL,
            ProviderCapability.STRUCTURED_JSON,
            ProviderCapability.TEXT_REASONING,
            ProviderCapability.ATTRIBUTE_NORMALIZATION
        ]

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        if any(self._api_key.startswith(p) for p in ["your_", "AIzaSyDummy", "dummy_"]):
            return False
        return self.check_circuit_allows_execution()

    def health_check(self) -> ProviderHealth:
        avail = self.is_available()
        c_state = self.circuit_state
        if c_state == "OPEN":
            state = ProviderHealthState.DEGRADED
            status_msg = "CIRCUIT_OPEN: Temporarily suspended due to recent upstream failures"
        elif c_state == "HALF_OPEN":
            state = ProviderHealthState.DEGRADED
            status_msg = "CIRCUIT_HALF_OPEN: Probing upstream service recovery"
        elif not self._api_key or any(self._api_key.startswith(p) for p in ["your_", "AIzaSyDummy", "dummy_"]):
            state = ProviderHealthState.BLOCKED
            status_msg = "BLOCKED: No valid Gemini API key configured"
        elif self._last_success_time:
            state = ProviderHealthState.AVAILABLE
            status_msg = "A live Gemini request succeeded in this process; this does not guarantee current upstream availability."
        else:
            state = ProviderHealthState.CONFIGURED
            status_msg = "Credential configured; live Gemini authentication and reachability have not been verified."

        return ProviderHealth(
            provider_name=self.name,
            is_available=avail,
            status_message=status_msg,
            active_capabilities=self.capabilities(),
            state=state,
            circuit_state=c_state,
            failure_count=self._failure_count,
            circuit_open=(c_state == "OPEN")
        )

    def _execute_mock(self, request: AIRequest) -> AIProviderResponse:
        """Controlled mock harness for testing validation without external network or API keys."""
        t0 = time.perf_counter()
        mock_data = {
            "garment": {
                "category": "hoodie",
                "subcategory": "oversized_hoodie",
                "confidence": 0.94
            },
            "components": {
                "hood": {"present": True, "type": "cowl", "confidence": 0.97, "evidence_status": "observed"},
                "sleeves": {"present": True, "type": "long", "confidence": 0.98, "evidence_status": "observed"},
                "pockets": {"present": True, "type": "kangaroo", "confidence": 0.91, "evidence_status": "observed"},
                "neckline": {"present": True, "type": "hooded", "confidence": 0.96, "evidence_status": "observed"},
                "collar": {"present": False, "type": "none", "confidence": 0.95, "evidence_status": "observed"},
                "closure": {"present": True, "type": "pullover", "confidence": 0.95, "evidence_status": "observed"},
                "cuffs": {"present": True, "type": "ribbed", "confidence": 0.92, "evidence_status": "observed"},
                "hem": {"present": True, "type": "ribbed_waistband", "confidence": 0.94, "evidence_status": "observed"}
            },
            "appearance": {
                "primary_color": "black",
                "secondary_color": None,
                "pattern": "solid",
                "fabric_appearance": "fleece-like"
            },
            "orientation": "front",
            "visible_evidence": ["cowl hood with drawstrings", "kangaroo pouch pocket", "ribbed wrist cuffs", "ribbed waistband"],
            "inferred_properties": ["heavyweight cotton-poly blend fleece"],
            "unknown_properties": ["rear back panel seam construction", "interior fleece brushedness"],
            "quality": {
                "image_usable": True,
                "occlusion_detected": False,
                "contrast_acceptable": True,
                "ambiguity_notes": []
            }
        }
        latency = (time.perf_counter() - t0) * 1000.0
        return AIProviderResponse(
            request_id=request.request_id,
            provider_name=self.name,
            model_metadata=ModelMetadata(
                provider_name=self.name,
                model_name=f"{self.model_name}-mock-harness",
                model_version="gemini-2.5-mock",
                prompt_version="v14.26",
                device="cloud-simulated",
                commercial_licensed=False,
                license_type="Mock output; provider terms not verified"
            ),
            task_type=request.task_type,
            success=True,
            raw_text=json.dumps(mock_data),
            structured_data=mock_data,
            token_usage=TokenUsage(prompt_tokens=450, completion_tokens=220, total_tokens=670, estimated_cost_usd=0.00015),
            latency_ms=latency,
            provenance_notes=["Controlled mock test harness execution (Phase 14.26 verified)"]
        )

    def execute(self, request: AIRequest) -> AIProviderResponse:
        """Executes multimodal image understanding request against Gemini API."""
        if request.mock_mode:
            return self._execute_mock(request)

        if not self.is_available():
            circuit_open = self.circuit_state == "OPEN"
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(
                    provider_name=self.name,
                    model_name=self.model_name,
                    is_local=False
                ),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="CIRCUIT_OPEN" if circuit_open else "BLOCKED_NO_CREDENTIALS",
                    message="Provider circuit is open." if circuit_open else "Gemini credential is unavailable.",
                    is_retryable=False
                )
            )

        t0 = time.perf_counter()

        # Prepare image payload
        image_bytes = request.image_bytes
        if not image_bytes and request.image_path and os.path.exists(request.image_path):
            with open(request.image_path, "rb") as f:
                image_bytes = f.read()

        if not image_bytes:
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(provider_name=self.name, model_name=self.model_name),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="MISSING_IMAGE",
                    message="Gemini Vision requires image bytes or valid image_path.",
                    is_retryable=False
                )
            )

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = request.text_prompt or GEMINI_GARMENT_PROMPT

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": request.image_mime_type,
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens
            }
        }

        url = self.api_endpoint
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}

        # Retry logic with bounded backoff
        max_retries = 2
        last_error = None
        upstream_model = None
        upstream_id = None

        for attempt in range(max_retries + 1):
            try:
                resp = provider_meter.post("gemini", url, json=payload, headers=headers, timeout=request.timeout_seconds, retry=attempt > 0)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                upstream_id = resp.headers.get("x-request-id")
                if resp.status_code == 200:
                    data = resp.json()
                    upstream_model = data.get("modelVersion")
                    upstream_id = data.get("responseId") or upstream_id
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini returned zero response candidates")

                    part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                    parsed_json = json.loads(part_text)

                    garment = parsed_json["garment"]
                    confidence = garment["confidence"]
                    if (not all(isinstance(garment.get(k), str) and garment[k].strip()
                                for k in ("category", "subcategory"))
                            or type(confidence) not in (int, float) or not 0 <= confidence <= 1):
                        raise ValueError("Invalid garment classification")

                    # Usage metadata
                    usage_meta = data.get("usageMetadata", {})
                    token_usage = TokenUsage(
                        prompt_tokens=usage_meta.get("promptTokenCount", 0),
                        completion_tokens=usage_meta.get("candidatesTokenCount", 0),
                        total_tokens=usage_meta.get("totalTokenCount", 0),
                        estimated_cost_usd=round(usage_meta.get("totalTokenCount", 0) * 0.0000003, 6)
                    )

                    self.record_success()
                    return AIProviderResponse(
                        request_id=request.request_id,
                        provider_name=self.name,
                        model_metadata=ModelMetadata(
                            provider_name=self.name,
                            model_name=self.model_name,
                            model_version=data.get("modelVersion") or "unreported",
                            prompt_version="v14.26-json",
                            device="cloud"
                        ),
                        task_type=request.task_type,
                        success=True,
                        upstream_request_id=data.get("responseId") or resp.headers.get("x-request-id"),
                        upstream_model=data.get("modelVersion"),
                        usage_reported=bool(usage_meta),
                        raw_text=part_text,
                        structured_data=parsed_json,
                        token_usage=token_usage,
                        latency_ms=latency_ms
                    )

                code = http_failure(resp)
                last_error = ProviderError(provider_name=self.name, error_code=code, message=code,
                                           status_code=resp.status_code,
                                           is_retryable=code in {"RATE_LIMIT", "TIMEOUT"} or resp.status_code in (500, 502, 503))
            except (requests.RequestException, AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
                code = exception_failure(exc)
                last_error = ProviderError(provider_name=self.name, error_code=code, message=code,
                                           is_retryable=code == "TIMEOUT")
            if not last_error.is_retryable:
                break
            if attempt < max_retries and last_error.error_code == "RATE_LIMIT":
                time.sleep(attempt + 1)

        self.record_failure()
        return AIProviderResponse(
            request_id=request.request_id,
            provider_name=self.name,
            model_metadata=ModelMetadata(provider_name=self.name, model_name=self.model_name),
            task_type=request.task_type,
            success=False,
            upstream_model=upstream_model,
            error=last_error,
            upstream_request_id=upstream_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0
        )
