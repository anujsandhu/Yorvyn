"""
YORVYN — Groq Fast LLM Reasoning & Normalization Provider (Phase 14.26)
Integrates Groq ultra-low-latency LPU inference (llama-3.3-70b-versatile / llama-3.1-8b-instant)
for structured reasoning and text normalization:
- Attribute normalization & taxonomy alignment
- Visual conflict resolution between Gemini and Local CV findings
- Conversion of visual findings into canonical garment specification
- Strict capability check: GUARANTEES images are NEVER sent to text-only models
- Structured JSON mode (response_format={"type": "json_object"})
- Bounded retries, token usage tracking, and safe offline rule-based fallback
"""

from __future__ import annotations

import os
import json
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
    TaskType
)

logger = logging.getLogger(__name__)

GROQ_NORMALIZATION_PROMPT = """You are a senior fashion taxonomist and patternmaker AI for YORVYN.
Your role is to refine, normalize, and resolve conflicts in extracted garment attributes.
You must strictly respect HIGH-CONFIDENCE VISUAL EVIDENCE.
Never override direct visual observations with speculative generic priors.

Output a valid JSON object matching:
{
  "category": "<normalized category>",
  "subcategory": "<normalized subcategory>",
  "taxonomy_tier": "<tops | bottoms | outerwear | dresses_and_skirts | traditional>",
  "attributes": {
    "fit": "<regular | oversized | slim | relaxed>",
    "pattern": "<solid | striped | plaid | graphic | floral | cable_knit>",
    "sleeve_type": "<long_sleeve | short_sleeve | sleeveless | raglan>",
    "neckline": "<crew_neck | v_neck | hooded | mandarin | collared>",
    "closure": "<pullover | front_zipper | full_button_placket | drawstring>",
    "pockets": ["<normalized pocket names>"]
  },
  "reconstruction_parameters": {
    "target_dag_template": "<hoodie_construction | jacket_construction | shirt_construction | etc.>",
    "enable_hood_mesh": <bool>,
    "enable_pocket_mesh": <bool>,
    "pocket_type": "<kangaroo_pocket | chest_pockets | etc. or null>",
    "material_preset": "<pbr fabric preset string>"
  },
  "conflict_resolutions": [
    {"attribute": "<name>", "winner": "<provider>", "reason": "<rationale>"}
  ],
  "reasoning_summary": "<concise explanation of garment architecture>"
}
"""


class GroqReasoningProvider(AIProvider):
    """Production adapter for Groq fast LPU reasoning intelligence."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 12.0
    ):
        super().__init__("groq_reasoning")
        self._api_key = (
            api_key or
            os.environ.get("GROQ_API_KEY") or
            getattr(settings, "groq_api_key", None) or
            ""
        )
        self.model_name = model_name or getattr(settings, "groq_model", "llama-3.3-70b-versatile")
        self.timeout_seconds = timeout_seconds
        self.api_endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.TEXT_REASONING,
            ProviderCapability.STRUCTURED_JSON,
            ProviderCapability.ATTRIBUTE_NORMALIZATION
        ]

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        if any(self._api_key.startswith(p) for p in ["your_", "gsk_your", "dummy_"]):
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
        elif not self._api_key or any(self._api_key.startswith(p) for p in ["your_", "gsk_your", "dummy_"]):
            state = ProviderHealthState.BLOCKED
            status_msg = "BLOCKED: No valid Groq API key configured"
        elif self._last_success_time:
            state = ProviderHealthState.AVAILABLE
            status_msg = "A live Groq request succeeded in this process; this does not guarantee current upstream availability."
        else:
            state = ProviderHealthState.CONFIGURED
            status_msg = "Credential configured; live Groq authentication and reachability have not been verified."

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
        """Controlled mock harness for testing Groq reasoning without external network or API keys."""
        t0 = time.perf_counter()
        context = request.structured_context
        cat = context.get("category", "hoodie")
        subcat = context.get("subcategory", "oversized_hoodie")

        mock_data = {
            "category": cat,
            "subcategory": subcat,
            "taxonomy_tier": "outerwear" if cat in ["jacket", "coat"] else "tops",
            "attributes": {
                "fit": context.get("fit", "oversized"),
                "pattern": context.get("pattern", "solid"),
                "sleeve_type": "long_sleeve",
                "neckline": "hooded" if cat == "hoodie" else "crew_neck",
                "closure": "pullover",
                "pockets": ["kangaroo_pocket"] if cat == "hoodie" else []
            },
            "reconstruction_parameters": {
                "target_dag_template": f"{cat}_construction",
                "enable_hood_mesh": (cat == "hoodie"),
                "enable_pocket_mesh": (cat == "hoodie"),
                "pocket_type": "kangaroo_pocket" if cat == "hoodie" else None,
                "material_preset": "cotton_fleece_pbr"
            },
            "conflict_resolutions": [
                {
                    "attribute": "pocket_geometry",
                    "winner": "gemini_and_local_consensus",
                    "reason": "Direct visual detection of kangaroo pouch pocket confirmed by both models."
                }
            ],
            "reasoning_summary": f"Canonicalized {subcat} specification: preserved confirmed hood cowl and front kangaroo pouch."
        }
        latency = (time.perf_counter() - t0) * 1000.0
        return AIProviderResponse(
            request_id=request.request_id,
            provider_name=self.name,
            model_metadata=ModelMetadata(
                provider_name=self.name,
                model_name=f"{self.model_name}-mock-harness",
                model_version="groq-llama3-mock",
                prompt_version="v14.26-groq",
                device="cloud-simulated",
                commercial_licensed=False,
                license_type="Mock output; provider/model terms not verified"
            ),
            task_type=request.task_type,
            success=True,
            raw_text=json.dumps(mock_data),
            structured_data=mock_data,
            token_usage=TokenUsage(prompt_tokens=320, completion_tokens=180, total_tokens=500, estimated_cost_usd=0.00004),
            latency_ms=latency,
            provenance_notes=["Controlled mock test harness execution (Phase 14.26 verified)"]
        )

    def execute(self, request: AIRequest) -> AIProviderResponse:
        """Executes text reasoning or attribute normalization against Groq API."""
        # STRICT CAPABILITY GUARD: Prevent sending images to text-only models
        if request.image_bytes or request.image_path or request.require_vision:
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(provider_name=self.name, model_name=self.model_name),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="UNSUPPORTED_MODALITY",
                    message="The Groq normalization adapter accepts text input only.",
                    is_retryable=False
                )
            )

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
                    message="Provider circuit is open." if circuit_open else "Groq credential is unavailable.",
                    is_retryable=False
                )
            )

        t0 = time.perf_counter()

        system_prompt = GROQ_NORMALIZATION_PROMPT
        user_content = request.text_prompt or (
            f"Please normalize these garment attributes: {json.dumps(request.structured_context)}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        # Bounded retries
        max_retries = 2
        upstream_model = None
        upstream_id = None
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                resp = provider_meter.post("groq", self.api_endpoint, json=payload, headers=headers, timeout=request.timeout_seconds, retry=attempt > 0)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                upstream_id = resp.headers.get("x-request-id")
                if resp.status_code == 200:
                    data = resp.json()
                    upstream_model = data.get("model")
                    upstream_id = upstream_id or data.get("id")
                    choices = data.get("choices", [])
                    if not choices:
                        raise ValueError("Groq returned zero completion choices")

                    content_text = choices[0].get("message", {}).get("content")
                    parsed_json = json.loads(content_text)

                    usage_dict = data.get("usage", {})
                    token_usage = TokenUsage(
                        prompt_tokens=usage_dict.get("prompt_tokens", 0),
                        completion_tokens=usage_dict.get("completion_tokens", 0),
                        total_tokens=usage_dict.get("total_tokens", 0),
                        estimated_cost_usd=round(usage_dict.get("total_tokens", 0) * 0.0000008, 6)
                    )

                    self.record_success()
                    return AIProviderResponse(
                        request_id=request.request_id,
                        provider_name=self.name,
                        model_metadata=ModelMetadata(
                            provider_name=self.name,
                            model_name=self.model_name,
                            model_version=data.get("model") or "unreported",
                            prompt_version="v14.26-groq",
                            device="cloud"
                        ),
                        task_type=request.task_type,
                        success=True,
                        upstream_request_id=upstream_id, upstream_model=data.get("model"),
                        usage_reported=bool(usage_dict),
                        raw_text=content_text,
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
            error=last_error, upstream_request_id=upstream_id,
            latency_ms=(time.perf_counter() - t0) * 1000.0
        )
