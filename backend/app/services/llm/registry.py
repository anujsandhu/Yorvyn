"""
LLM Provider Registry for Yorvyn LLM Architecture (Phase 17.7 Hardened).
Manages provider adapters, live verification state vs credential presence,
circuit breakers, bounded retries/backoff, telemetry, and fallback resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolDefinition
from backend.app.services.llm.providers.groq_provider import GroqProvider
from backend.app.services.llm.providers.gemini_provider import GeminiProvider
from backend.app.services.llm.providers.openrouter_provider import OpenRouterProvider
from backend.app.services.llm.providers.offline_rules_provider import OfflineRulesProvider

logger = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ProviderState(str, Enum):
    """Strict distinction between credential presence, verified connectivity, and failure modes."""

    VERIFIED = "VERIFIED"
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED_NO_CREDENTIALS = "BLOCKED_NO_CREDENTIALS"


@dataclass
class ProviderHealthMetrics:
    provider_name: str
    state: ProviderState = ProviderState.UNAVAILABLE
    model_id: str = ""
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    circuit_open_until_ts: float = 0.0
    last_latency_ms: Optional[float] = None
    last_error_code: Optional[str] = None
    last_http_status: Optional[int] = None
    last_checked_ts: Optional[float] = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    def is_circuit_open(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return self.circuit_open_until_ts > now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "state": self.state.value,
            "model_id": self.model_id,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "circuit_open": self.is_circuit_open(),
            "last_latency_ms": self.last_latency_ms,
            "last_error_code": self.last_error_code,
            "last_http_status": self.last_http_status,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
        }


@dataclass
class ResilientLLMOutcome:
    """Outcome of a provider-resilient generation with deterministic fallback receipt."""

    response: LLMResponse
    parsed_json: Optional[Dict[str, Any]] = None
    schema_valid: bool = False
    fallback_used: bool = False
    attempts: List[Dict[str, Any]] = field(default_factory=list)


_NON_RETRYABLE_ERROR_CODES = {
    "INVALID_CREDENTIAL",
    "PERMISSION_DENIED",
    "QUOTA_EXHAUSTED",
    "UNSUPPORTED_MODEL",
    "UNSUPPORTED_MODALITY",
}


class LLMProviderRegistry:
    """Registry managing available LLM provider adapters, circuit breakers, and fallback."""

    CIRCUIT_THRESHOLD = 2
    CIRCUIT_COOLDOWN_SECONDS = 60.0

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._metrics: Dict[str, ProviderHealthMetrics] = {}
        self.register(OfflineRulesProvider())
        self.register(GroqProvider())
        self.register(GeminiProvider())
        self.register(OpenRouterProvider())

    def register(self, provider: LLMProvider) -> None:
        """Registers a provider adapter instance and initializes initial honest state."""
        name = provider.provider_name.lower()
        if name in self._providers:
            raise ValueError(f"Duplicate provider registration: {name}")
        self._providers[name] = provider
        if name == "offline_rules":
            init_state = ProviderState.VERIFIED
        elif provider.health_check():
            init_state = ProviderState.AVAILABLE
        else:
            init_state = ProviderState.BLOCKED_NO_CREDENTIALS
        model_id = str(getattr(provider, "default_model", None) or getattr(provider, "model_name", None) or name)
        self._metrics[name] = ProviderHealthMetrics(provider_name=name, state=init_state, model_id=model_id)

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Retrieves provider by name."""
        return self._providers.get(name.lower())

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def refresh_initial_states(self) -> None:
        for name, provider in self._providers.items():
            m = self._metrics[name]
            if name == "offline_rules":
                m.state = ProviderState.VERIFIED
            elif not provider.health_check():
                m.state = ProviderState.BLOCKED_NO_CREDENTIALS
            elif m.state == ProviderState.BLOCKED_NO_CREDENTIALS:
                m.state = ProviderState.AVAILABLE

    def record_success(self, name: str, response: LLMResponse) -> None:
        m = self._metrics.get(name.lower())
        if m is None:
            return
        m.state = ProviderState.VERIFIED
        m.model_id = response.upstream_model or response.model_used or m.model_id
        m.total_requests += 1
        m.total_successes += 1
        m.consecutive_failures = 0
        m.circuit_open_until_ts = 0.0
        m.last_latency_ms = round(float(response.latency_ms), 2)
        m.last_error_code = None
        m.last_http_status = 200
        m.last_checked_ts = time.time()
        m.total_prompt_tokens += int(response.prompt_tokens or 0)
        m.total_completion_tokens += int(response.completion_tokens or 0)

    def record_failure(self, name: str, exc: Exception, latency_ms: Optional[float] = None) -> None:
        m = self._metrics.get(name.lower())
        if m is None:
            return
        code = str(getattr(exc, "code", None) or type(exc).__name__)
        status_code = getattr(exc, "status_code", None)
        m.total_requests += 1
        m.total_failures += 1
        m.consecutive_failures += 1
        m.last_error_code = code
        m.last_http_status = status_code
        m.last_checked_ts = time.time()
        if latency_ms is not None:
            m.last_latency_ms = round(float(latency_ms), 2)
        if code in {"INVALID_CREDENTIAL", "PERMISSION_DENIED"}:
            m.state = ProviderState.DEGRADED
            m.circuit_open_until_ts = time.time() + self.CIRCUIT_COOLDOWN_SECONDS * 3.0
        else:
            m.state = ProviderState.DEGRADED if m.consecutive_failures < self.CIRCUIT_THRESHOLD else ProviderState.UNAVAILABLE
            if m.consecutive_failures >= self.CIRCUIT_THRESHOLD:
                m.circuit_open_until_ts = time.time() + self.CIRCUIT_COOLDOWN_SECONDS

    def resolve_provider(self, primary_preference: str = "groq", fallback_preference: str = "offline_rules") -> LLMProvider:
        """
        Resolves best available provider: checks credential availability + circuit breaker,
        always guaranteeing OfflineRulesProvider as ultimate safeguard.
        """
        self.refresh_initial_states()
        now = time.time()
        for pref in (primary_preference, fallback_preference):
            p = self.get_provider(pref)
            if p is None:
                continue
            m = self._metrics[pref.lower()]
            if m.state == ProviderState.BLOCKED_NO_CREDENTIALS:
                continue
            if m.is_circuit_open(now):
                continue
            if p.health_check():
                return p
        return self._providers["offline_rules"]

    @staticmethod
    def extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
        """Safely extracts a JSON object from raw LLM output (stripping markdown fences if present)."""
        text = (raw_text or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            loaded = json.loads(text)
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                try:
                    loaded = json.loads(text[start : end + 1])
                    return loaded if isinstance(loaded, dict) else None
                except json.JSONDecodeError:
                    return None
            return None

    def generate_with_fallback(
        self,
        messages: List[LLMMessage],
        *,
        preference_order: Optional[List[str]] = None,
        tools: Optional[List[ToolDefinition]] = None,
        schema_cls: Optional[Type[SchemaT]] = None,
        expect_json: bool = False,
        deterministic_fallback_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 600,
        timeout_seconds: int = 12,
        max_retries_per_provider: int = 1,
    ) -> ResilientLLMOutcome:
        """
        Executes LLM generation across preference_order with circuit breakers, bounded retry/backoff,
        strict schema validation, and guaranteed deterministic fallback.
        """
        self.refresh_initial_states()
        order = list(preference_order or ["groq", "gemini", "openrouter"])
        if "offline_rules" not in order:
            order.append("offline_rules")

        attempts: List[Dict[str, Any]] = []
        now = time.time()

        for pname in order:
            pname_l = pname.lower()
            prov = self.get_provider(pname_l)
            m = self._metrics.get(pname_l)
            if prov is None or m is None:
                continue
            if pname_l != "offline_rules":
                if m.state == ProviderState.BLOCKED_NO_CREDENTIALS or not prov.health_check():
                    attempts.append({"provider": pname_l, "status": "SKIPPED_NO_CREDENTIALS"})
                    continue
                if m.is_circuit_open(now):
                    attempts.append({"provider": pname_l, "status": "SKIPPED_CIRCUIT_OPEN", "last_error": m.last_error_code})
                    continue

            if pname_l == "offline_rules" and deterministic_fallback_fn is not None:
                t0 = time.perf_counter()
                payload = deterministic_fallback_fn()
                lat = round((time.perf_counter() - t0) * 1000, 2)
                content = json.dumps(payload)
                resp = LLMResponse(
                    content=content,
                    provider_used="offline_rules",
                    model_used="offline-rules-deterministic-v1",
                    prompt_tokens=sum(len(mm.content) // 4 for mm in messages),
                    completion_tokens=len(content) // 4,
                    latency_ms=lat,
                    finish_reason="stop",
                )
                valid = True
                if schema_cls is not None:
                    try:
                        schema_cls.model_validate(payload)
                    except ValidationError:
                        valid = False
                self.record_success("offline_rules", resp)
                attempts.append({"provider": "offline_rules", "status": "FALLBACK_OK", "latency_ms": lat})
                return ResilientLLMOutcome(
                    response=resp,
                    parsed_json=payload,
                    schema_valid=valid,
                    fallback_used=len(attempts) > 1,
                    attempts=attempts,
                )

            max_tries = 1 + max(0, max_retries_per_provider)
            for attempt_idx in range(max_tries):
                t0 = time.perf_counter()
                try:
                    resp = prov.generate(
                        messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_seconds=timeout_seconds,
                    )
                    parsed = self.extract_json_object(resp.content)
                    schema_ok = parsed is not None
                    if schema_ok and schema_cls is not None:
                        try:
                            schema_cls.model_validate(parsed)
                        except ValidationError:
                            schema_ok = False
                    if (schema_cls is not None or expect_json) and not schema_ok:
                        raise ValueError("LLM response failed strict JSON schema validation")
                    self.record_success(pname_l, resp)
                    attempts.append({
                        "provider": pname_l,
                        "status": "OK",
                        "latency_ms": round(resp.latency_ms, 2),
                        "model": resp.upstream_model or resp.model_used,
                    })
                    return ResilientLLMOutcome(
                        response=resp,
                        parsed_json=parsed,
                        schema_valid=schema_ok,
                        fallback_used=len(attempts) > 1,
                        attempts=attempts,
                    )
                except Exception as exc:
                    lat = round((time.perf_counter() - t0) * 1000, 2)
                    code = str(getattr(exc, "code", None) or type(exc).__name__)
                    self.record_failure(pname_l, exc, latency_ms=lat)
                    attempts.append({
                        "provider": pname_l,
                        "attempt": attempt_idx + 1,
                        "status": "FAILED",
                        "error_code": code,
                        "http_status": getattr(exc, "status_code", None),
                        "latency_ms": lat,
                    })
                    if code in _NON_RETRYABLE_ERROR_CODES or pname_l == "offline_rules":
                        break
                    if attempt_idx + 1 < max_tries:
                        time.sleep(min(0.4 * (2 ** attempt_idx), 1.5))

        # Absolute final deterministic safeguard
        fallback_payload = deterministic_fallback_fn() if deterministic_fallback_fn else {"status": "fallback", "notes": ["offline_rules"]}
        resp = LLMResponse(
            content=json.dumps(fallback_payload),
            provider_used="offline_rules",
            model_used="offline-rules-v1",
            latency_ms=0.0,
            finish_reason="stop",
        )
        return ResilientLLMOutcome(
            response=resp,
            parsed_json=fallback_payload,
            schema_valid=True,
            fallback_used=True,
            attempts=attempts,
        )

    def probe_all(self, timeout_seconds: int = 8) -> Dict[str, Dict[str, Any]]:
        """Runs a live minimal check on every registered provider without ever logging secrets."""
        self.refresh_initial_states()
        probe_msgs = [
            LLMMessage(role="system", content='Reply ONLY with JSON matching {"status":"ok"}.'),
            LLMMessage(role="user", content="Ping"),
        ]
        report: Dict[str, Dict[str, Any]] = {}
        for name, prov in self._providers.items():
            m = self._metrics[name]
            if name != "offline_rules" and not prov.health_check():
                m.state = ProviderState.BLOCKED_NO_CREDENTIALS
                report[name] = m.to_dict()
                continue
            t0 = time.perf_counter()
            try:
                resp = prov.generate(probe_msgs, temperature=0.0, max_tokens=20, timeout_seconds=timeout_seconds)
                self.record_success(name, resp)
            except Exception as exc:
                self.record_failure(name, exc, latency_ms=(time.perf_counter() - t0) * 1000)
            report[name] = self._metrics[name].to_dict()
        return report

    def get_status_report(self) -> Dict[str, Dict[str, Any]]:
        self.refresh_initial_states()
        return {name: m.to_dict() for name, m in self._metrics.items()}


# Global singleton
llm_registry = LLMProviderRegistry()
