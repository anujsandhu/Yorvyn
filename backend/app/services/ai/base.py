"""
YORVYN — Unified AI Provider Base Interface & Common Types (Phase 14.26)
Defines provider-independent contracts for multimodal garment intelligence:
- AIProvider abstract base class
- AIRequest and AIProviderResponse models
- ProviderCapability and ProviderHealth schemas
- TokenUsage, ModelMetadata, and ProviderError normalization
"""

from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field


class ProviderCapability(str, Enum):
    VISION_MULTIMODAL = "vision_multimodal"
    TEXT_REASONING = "text_reasoning"
    STRUCTURED_JSON = "structured_json"
    EMBEDDINGS = "embeddings"
    COMPONENT_SEGMENTATION = "component_segmentation"
    DEPTH_ESTIMATION = "depth_estimation"
    ATTRIBUTE_NORMALIZATION = "attribute_normalization"
    OFFLINE_LOCAL = "offline_local"


class EvidenceStatus(str, Enum):
    OBSERVED = "observed"           # Directly visible in photograph
    INFERRED = "inferred"           # Deduced from visible context/prior
    UNKNOWN = "unknown"             # Hidden, occluded, or unobservable
    CONFLICTED = "conflicted"       # Competing contradictory evidence from different views
    NOT_APPLICABLE = "not_applicable" # Irrelevant to this category


class ProviderHealthState(str, Enum):
    REGISTERED = "registered"
    CONFIGURED = "configured"
    AUTHENTICATED = "authenticated"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class TaskType(str, Enum):
    GARMENT_IMAGE_UNDERSTANDING = "garment_image_understanding"
    LOCAL_SEGMENTATION = "local_segmentation"
    VISUAL_EMBEDDINGS = "visual_embeddings"
    ATTRIBUTE_NORMALIZATION = "attribute_normalization"
    TAXONOMY_MAPPING = "taxonomy_mapping"
    CONFLICT_RESOLUTION = "conflict_resolution"
    EXPLANATION_GENERATION = "explanation_generation"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ModelMetadata(BaseModel):
    provider_name: str
    model_name: str
    model_version: str = "1.0"
    prompt_version: str = "v1"
    device: str = "cloud"          # "mps", "cpu", "cuda", "cloud"
    is_local: bool = False
    commercial_licensed: bool = False
    license_type: str = "Not independently verified"


class ProviderError(BaseModel):
    provider_name: str
    error_code: str                # e.g., "RATE_LIMIT", "TIMEOUT", "AUTH_FAILED", "MALFORMED_OUTPUT"
    message: str
    is_retryable: bool = False
    status_code: Optional[int] = None
    raw_error: Optional[str] = None


class ProviderHealth(BaseModel):
    provider_name: str
    is_available: bool
    status_message: str
    active_capabilities: List[ProviderCapability]
    state: ProviderHealthState = ProviderHealthState.AVAILABLE
    circuit_state: str = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
    last_latency_ms: float = 0.0
    failure_count: int = 0
    circuit_open: bool = False


class AIRequest(BaseModel):
    request_id: str
    task_type: TaskType
    image_bytes: Optional[bytes] = None
    image_path: Optional[str] = None
    image_mime_type: str = "image/jpeg"
    text_prompt: Optional[str] = None
    structured_context: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.2
    max_tokens: int = 1500
    timeout_seconds: float = 20.0
    preferred_provider: Optional[str] = None
    require_vision: bool = False
    mock_mode: bool = False


class AIProviderResponse(BaseModel):
    upstream_request_id: Optional[str] = None
    upstream_model: Optional[str] = None
    usage_reported: bool = False
    request_id: str
    provider_name: str
    model_metadata: ModelMetadata
    task_type: TaskType
    success: bool
    raw_text: Optional[str] = None
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    error: Optional[ProviderError] = None
    cached: bool = False
    provenance_notes: List[str] = Field(default_factory=list)


class AIProvider(ABC):
    """Abstract Base Class for all YORVYN AI Providers (Gemini, Groq, HF, Local CV, Local Rules)."""

    def __init__(self, provider_name: str):
        self._provider_name = provider_name
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
        self._circuit_reset_time = 0.0
        self._last_success_time = 0.0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._provider_name

    @abstractmethod
    def capabilities(self) -> List[ProviderCapability]:
        """Returns the set of capabilities supported by this provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if provider is configured and available for execution."""
        pass

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Returns current operational status and health metrics."""
        pass

    @abstractmethod
    def execute(self, request: AIRequest) -> AIProviderResponse:
        """Synchronously or asynchronously executes the AI request."""
        pass

    @property
    def circuit_state(self) -> str:
        with self._lock:
            if self._circuit_state == "OPEN" and time.time() >= self._circuit_reset_time:
                return "HALF_OPEN"
            return self._circuit_state

    def check_circuit_allows_execution(self) -> bool:
        """Concurrency-safe check whether circuit breaker permits execution."""
        with self._lock:
            if self._circuit_state == "CLOSED":
                return True
            if self._circuit_state == "OPEN":
                if time.time() >= self._circuit_reset_time:
                    # Transition to HALF_OPEN probe state
                    self._circuit_state = "HALF_OPEN"
                    return True
                return False
            if self._circuit_state == "HALF_OPEN":
                # Currently in probe state; disallow parallel probe requests
                return False
            return True

    def record_success(self):
        """Records successful execution, closing circuit and resetting failure counts."""
        with self._lock:
            self._failure_count = 0
            self._circuit_open = False
            self._circuit_state = "CLOSED"
            self._last_success_time = time.time()

    def record_failure(self):
        """Records failure, tripping circuit after 3 consecutive errors or immediate probe failure."""
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= 3 or self._circuit_state == "HALF_OPEN":
                self._circuit_open = True
                self._circuit_state = "OPEN"
                self._circuit_reset_time = time.time() + 30.0  # 30-second cooldown window
