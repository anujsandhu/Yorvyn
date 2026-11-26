"""
YORVYN — Hugging Face candidate catalog and cached DINOv2 embeddings
Provides catalog metadata and DINOv2 embedding execution when pretrained weights are cached:
- Model license audit: Code license vs Checkpoint license
- No model downloads or commercial license assertions
- Extracts 384-dim normalized visual embeddings
"""

from __future__ import annotations

import io
import os
import time
import logging
from typing import Dict, Any, List, Optional
from PIL import Image

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
from backend.app.services.ml.dinov2_feature_extractor import dinov2_extractor

logger = logging.getLogger(__name__)

# Candidate model catalog. Entries are not assertions that a checkpoint is cached,
# loaded, licensed for commercial use, or used by the current adapter.
HF_OPEN_MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "FashionCLIP": {
        "repository": "openai/clip-vit-base-patch32",
        "task": "zero_shot_fashion_classification",
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "hardware_target": "Apple Silicon MPS / CPU",
        "parameters": "151M",
        "measured_memory_mb": None,
        "measured_latency_ms": None,
        "deployment_status": "GENERIC_CLIP_CHECKPOINT_NOT_FASHIONCLIP"
    },
    "SigLIP": {
        "repository": "google/siglip-base-patch16-224",
        "task": "multi_label_attribute_extraction",
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "hardware_target": "Apple Silicon MPS / CPU",
        "parameters": "151M",
        "measured_memory_mb": None,
        "measured_latency_ms": None,
        "deployment_status": "NOT_USED_BY_CURRENT_ADAPTER"
    },
    "DINOv2": {
        "repository": "facebook/dinov2-small",
        "task": "dense_visual_embeddings",
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "hardware_target": "Apple Silicon MPS / CPU",
        "parameters": "22M",
        "measured_memory_mb": None,
        "measured_latency_ms": None,
        "deployment_status": "CACHED_CHECKPOINT_REQUIRED"
    },
    "Grounded-SAM2": {
        "repository": None,
        "task": "apparel_component_segmentation",
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "hardware_target": "Apple Silicon MPS / CPU",
        "parameters": "Not applicable; heuristic",
        "measured_memory_mb": None,
        "measured_latency_ms": None,
        "deployment_status": "HEURISTIC_ADAPTER_NO_MODEL_WEIGHTS"
    },
    "Depth-Anything-V2": {
        "repository": None,
        "task": "monocular_disparity_and_relief",
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "hardware_target": "Apple Silicon MPS / CPU",
        "parameters": "Not applicable; heuristic",
        "measured_memory_mb": None,
        "measured_latency_ms": None,
        "deployment_status": "HEURISTIC_ADAPTER_NO_MODEL_WEIGHTS"
    }
}


class HuggingFaceProvider(AIProvider):
    """Production provider for Hugging Face open model discovery and visual embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("huggingface")
        self._api_key = (
            api_key or
            os.environ.get("HF_API_KEY") or
            os.environ.get("HUGGINGFACE_API_KEY") or
            getattr(settings, "hf_api_key", None) or
            ""
        )
        self.registry = HF_OPEN_MODEL_REGISTRY
        self.feature_extractor = dinov2_extractor

    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.EMBEDDINGS,
            ProviderCapability.VISION_MULTIMODAL,
            ProviderCapability.OFFLINE_LOCAL
        ]

    def is_available(self) -> bool:
        return self.feature_extractor.cached_weights_available and self.check_circuit_allows_execution()

    def health_check(self) -> ProviderHealth:
        weights_loaded = bool(self.feature_extractor.pretrained_weights_loaded)
        cache_ready = self.feature_extractor.cached_weights_available
        inference_succeeded = self.feature_extractor.successful_inferences > 0
        status_msg = "Cached DINOv2 inference succeeded locally" if inference_succeeded else (
            "Cached DINOv2 weights loaded; no successful inference has been recorded" if weights_loaded else
            "Cached DINOv2 weights detected; inference has not yet succeeded" if cache_ready
            else "Unavailable: no cached DINOv2 weights detected; network downloads are disabled"
        )

        return ProviderHealth(
            provider_name=self.name,
            is_available=cache_ready,
            status_message=status_msg,
            active_capabilities=self.capabilities(),
            last_latency_ms=0.0,
            failure_count=self._failure_count,
            state=(ProviderHealthState.AVAILABLE if inference_succeeded else ProviderHealthState.CONFIGURED if cache_ready else ProviderHealthState.UNAVAILABLE),
            circuit_state=self.circuit_state,
            circuit_open=self.circuit_state == "OPEN"
        )

    def execute(self, request: AIRequest) -> AIProviderResponse:
        """Generates dense self-supervised visual features using cached DINOv2 backbone."""
        t0 = time.perf_counter()

        image: Optional[Image.Image] = None
        if request.image_bytes:
            image = Image.open(io.BytesIO(request.image_bytes)).convert("RGB")
        elif request.image_path:
            image = Image.open(request.image_path).convert("RGB")

        if image is None:
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(provider_name=self.name, model_name="DINOv2 feature extractor (not loaded)", is_local=True),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="MISSING_IMAGE",
                    message="Hugging Face provider requires valid image_bytes or image_path.",
                    is_retryable=False
                )
            )

        try:
            feats = self.feature_extractor.extract_features(image)
            if not feats.get("semantic_valid"):
                self.record_failure()
                return AIProviderResponse(
                    request_id=request.request_id,
                    provider_name=self.name,
                    model_metadata=ModelMetadata(
                        provider_name=self.name,
                        model_name=str(feats.get("model", "untrained fallback")),
                        device=str(self.feature_extractor.device),
                        is_local=True
                    ),
                    task_type=request.task_type,
                    success=False,
                    error=ProviderError(
                        provider_name=self.name,
                        error_code="PRETRAINED_WEIGHTS_UNAVAILABLE",
                        message="Cached DINOv2 weights are unavailable; an untrained fallback is not served as semantic embeddings.",
                        is_retryable=False
                    ),
                    latency_ms=(time.perf_counter() - t0) * 1000.0
                )
            latency_ms = (time.perf_counter() - t0) * 1000.0
            self.record_success()

            cls_emb = feats["cls_embedding"].tolist()
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(
                    provider_name=self.name,
                    model_name=str(feats["model"]),
                    model_version="1.0",
                    device=str(self.feature_extractor.device),
                    is_local=True,
                    commercial_licensed=False,
                    license_type="Not independently verified"
                ),
                task_type=request.task_type,
                success=True,
                structured_data={
                    "embedding": cls_emb,
                    "embedding_dim": len(cls_emb),
                    "embedding_vector": cls_emb[:32],  # Sample vector preview
                    "patch_feature_shape": feats["patch_feature_shape"],
                    "model_source": "local_cache",
                    "execution_backend": feats["execution_backend"],
                    "pretrained_weights_loaded": feats["pretrained_weights_loaded"]
                },
                token_usage=TokenUsage(total_tokens=0, estimated_cost_usd=0.00),
                latency_ms=latency_ms,
                provenance_notes=[
                    "Cached pretrained DINOv2 weights executed locally",
                    "Checkpoint license was not independently verified by this runtime"
                ]
            )

        except Exception as e:
            self.record_failure()
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(provider_name=self.name, model_name="DINOv2 cached-weight inference failed", is_local=True),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="HF_INFERENCE_ERROR",
                    message=f"Hugging Face feature extraction error: {str(e)}",
                    is_retryable=False,
                    raw_error=str(e)
                ),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
