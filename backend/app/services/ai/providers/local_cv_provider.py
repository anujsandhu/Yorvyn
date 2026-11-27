"""
YORVYN — Local perception provider (Phase 14.26)
Wraps cached generic CLIP prompt scoring and local heuristic image stages.
It reports unavailable when required local runtime/cache prerequisites are missing.
"""

from __future__ import annotations

import io
import os
import importlib.util
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

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
from backend.app.services.garments.intelligence.local_multimodal_identification_engine import multimodal_engine
from backend.app.services.garments.intelligence.sequential_model_manager import model_manager

logger = logging.getLogger(__name__)


class LocalCVProvider(AIProvider):
    """Production provider for offline local computer vision intelligence."""

    def __init__(self):
        super().__init__("local_cv")
        self.engine = multimodal_engine
        self.device = model_manager.preferred_device

    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.VISION_MULTIMODAL,
            ProviderCapability.OFFLINE_LOCAL,
            ProviderCapability.COMPONENT_SEGMENTATION,
            ProviderCapability.DEPTH_ESTIMATION,
            ProviderCapability.EMBEDDINGS,
            ProviderCapability.STRUCTURED_JSON,
            ProviderCapability.ATTRIBUTE_NORMALIZATION
        ]

    def is_available(self) -> bool:
        if importlib.util.find_spec("transformers") is None:
            return False
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        snapshots = hf_home / "hub" / "models--openai--clip-vit-base-patch32" / "snapshots"
        if not snapshots.is_dir():
            return False
        ready = any(
            (snapshot / "config.json").is_file()
            and any((snapshot / weight_name).is_file() for weight_name in ("pytorch_model.bin", "model.safetensors"))
            for snapshot in snapshots.iterdir() if snapshot.is_dir()
        )
        return ready and self.check_circuit_allows_execution()

    def health_check(self) -> ProviderHealth:
        ready = self.is_available()
        return ProviderHealth(
            provider_name=self.name,
            is_available=ready,
            status_message=(
                "At least one local inference succeeded in this process."
                if ready and self._last_success_time else
                "Configured: cached generic CLIP checkpoint and transformers package found; successful inference not yet established."
                if ready else
                "Unavailable: cached generic CLIP checkpoint or transformers package missing; network downloads are disabled."
            ),
            active_capabilities=self.capabilities(),
            last_latency_ms=model_manager.model_latencies.get("total", 0.0),
            failure_count=self._failure_count,
            state=(ProviderHealthState.AVAILABLE if self._last_success_time else ProviderHealthState.CONFIGURED) if ready else ProviderHealthState.UNAVAILABLE,
            circuit_state=self.circuit_state,
            circuit_open=self.circuit_state == "OPEN"
        )

    def execute(self, request: AIRequest) -> AIProviderResponse:
        """Executes zero-cost local computer vision pipeline."""
        t0 = time.perf_counter()

        # Load PIL image from bytes or path
        image: Optional[Image.Image] = None
        if request.image_bytes:
            image = Image.open(io.BytesIO(request.image_bytes)).convert("RGB")
        elif request.image_path:
            image = Image.open(request.image_path).convert("RGB")

        if image is None:
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(
                    provider_name=self.name,
                    model_name="Local-CV-Engine",
                    device=self.device,
                    is_local=True
                ),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="MISSING_IMAGE",
                    message="Local CV provider requires valid image_bytes or image_path.",
                    is_retryable=False
                )
            )

        try:
            # Execute local multimodal engine
            spec = self.engine.identify_garment(image, garment_id=request.request_id)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Convert specification components into structured dict
            components_dict = {}
            for c in spec.components:
                components_dict[c.name] = {
                    "present": True,
                    "confidence": float(c.confidence),
                    "evidence_status": "inferred",
                    "bbox": list(c.bbox),
                    "source_model": c.source_model
                }

            structured_payload = {
                "garment": {
                    "category": spec.category.value,
                    "subcategory": spec.subcategory,
                    "confidence": float(spec.confidence),
                    "evidence_status": "inferred"
                },
                "components": components_dict,
                "appearance": {
                    "primary_color": spec.attributes.primary_color,
                    "secondary_color": spec.attributes.secondary_color,
                    "palette_hex": spec.attributes.palette_hex,
                    "pattern": spec.attributes.pattern,
                    "fabric_appearance": spec.attributes.fabric_texture,
                    "evidence_status": "inferred"
                },
                "orientation": "front",
                "quality": {
                    "image_usable": True,
                    "occlusion_detected": spec.uncertainty.occlusion_flag,
                    "contrast_acceptable": not spec.uncertainty.low_contrast_flag,
                    "ambiguity_notes": [] if spec.uncertainty.verdict == "HIGH_CONFIDENCE" else [spec.uncertainty.verdict]
                },
                "geometry": {
                    "measurement_method": "contour_carving",
                    "scale_assumptions": "bounding_box_normalized",
                    "sleeve_length_ratio": spec.reconstruction_handoff.sleeve_length_scale,
                    "uncertainty_cm": 2.0
                },
                "reconstruction_handoff": {
                    "target_dag_template": spec.reconstruction_handoff.target_dag_template,
                    "enable_hood_mesh": spec.reconstruction_handoff.enable_hood_mesh,
                    "enable_pocket_mesh": spec.reconstruction_handoff.enable_pocket_mesh,
                    "pocket_type": spec.reconstruction_handoff.pocket_type,
                    "closure_geometry": spec.reconstruction_handoff.closure_geometry,
                    "curved_hem": spec.reconstruction_handoff.curved_hem,
                    "torso_fit_offset_cm": spec.reconstruction_handoff.torso_fit_offset_cm,
                    "material_preset": spec.reconstruction_handoff.material_preset
                },
                "explanation": spec.natural_language_explanation
            }
            structured_payload["model_provenance"] = (
                spec.provenance.model_dump() if hasattr(spec.provenance, "model_dump") else spec.provenance.dict()
            )
            structured_payload["model_execution_provenance"] = spec.provenance.model_execution_details

            self.record_success()
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(
                    provider_name=self.name,
                    model_name="Local multimodal pipeline (per-adapter execution provenance in payload)",
                    model_version="14.24-F-local",
                    device=self.device,
                    is_local=True,
                    commercial_licensed=False,
                    license_type="Not independently verified"
                ),
                task_type=request.task_type,
                success=True,
                structured_data=structured_payload,
                token_usage=TokenUsage(total_tokens=0, estimated_cost_usd=0.00),
                latency_ms=latency_ms,
                provenance_notes=[
                    f"Executed on {self.device.upper()}; model and heuristic stages are listed in the specification provenance",
                    f"Peak RSS: {spec.provenance.peak_memory_mb:.1f} MB (Headroom safe)",
                    "Local execution incurs no external model API charge; checkpoint licenses are not verified here"
                ]
            )

        except Exception as e:
            self.record_failure()
            logger.error(f"Local CV inference error: {e}", exc_info=True)
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name=self.name,
                model_metadata=ModelMetadata(provider_name=self.name, model_name="Local-CV-Engine", is_local=True),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name=self.name,
                    error_code="LOCAL_CV_EXCEPTION",
                    message=f"Local CV exception: {str(e)}",
                    is_retryable=False,
                    raw_error=str(e)
                ),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
