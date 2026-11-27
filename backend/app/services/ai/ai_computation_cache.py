"""
YORVYN — Deterministic AI & Geometry Computation Cache (Phase 17.6)

Reuses deterministic preprocessing, embeddings, classification, and geometry
validation results only when:
  - input content SHA-256 matches
  - model ID and checkpoint SHA-256 match
  - pipeline version & processing config match
  - owner boundary matches (private inputs never cross owner scopes)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Optional, Tuple

from backend.app.core.cache_service import AppCacheService, app_cache


class AIComputationCache:
    NAMESPACE = "ai_compute"
    PIPELINE_VERSION = "17.6.0"

    def __init__(self, cache: Optional[AppCacheService] = None) -> None:
        self._cache = cache or app_cache

    @staticmethod
    def compute_input_hash(payload_bytes: bytes) -> str:
        return hashlib.sha256(payload_bytes).hexdigest()

    @staticmethod
    def compute_config_hash(config: Optional[Dict[str, Any]]) -> str:
        serialized = json.dumps(config or {}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def build_computation_key(
        self,
        *,
        operation: str,
        input_sha256: str,
        model_id: str,
        checkpoint_sha256: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        cfg_hash = self.compute_config_hash(config)
        return (
            f"{operation}:{self.PIPELINE_VERSION}:{model_id}:{checkpoint_sha256[:16]}"
            f":{cfg_hash}:{input_sha256}"
        )

    def get_or_compute(
        self,
        *,
        owner_id: str,
        operation: str,
        input_bytes: bytes,
        model_id: str,
        checkpoint_sha256: str,
        compute_fn: Callable[[], Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 3600,
    ) -> Tuple[Dict[str, Any], bool]:
        if not owner_id:
            raise ValueError("owner_id is required for AI computation cache isolation.")
        input_sha = self.compute_input_hash(input_bytes)
        comp_key = self.build_computation_key(
            operation=operation,
            input_sha256=input_sha,
            model_id=model_id,
            checkpoint_sha256=checkpoint_sha256,
            config=config,
        )
        return self._cache.get_or_set(
            self.NAMESPACE,
            comp_key,
            compute_fn,
            ttl_seconds=ttl_seconds,
            owner_id=owner_id,
            is_public=False,
        )

    def get_stats(self) -> Dict[str, Any]:
        return self._cache.get_stats()


ai_computation_cache = AIComputationCache()
