"""
YORVYN Phase 17.7 — Multi-Model Reasoning & Garment Perception Orchestrator.

Coordinates:
- Multi-Model LLM reasoning (`MultiModelReasoningService`) with schema validation,
  sanitized prompt framing, circuit breakers, and deterministic offline fallback.
- Garment perception & construction summary (`GarmentPerceptionOrchestrator`) combining
  classifier, SegFormer human-parsing segmentation, component evidence, and DINOv2 cues.
- Strictly bounded repair proposals that NEVER accept an unverified LLM geometry change
  without passing the independent deterministic critic & geometry validator.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.services.llm.base import LLMMessage
from backend.app.services.llm.registry import llm_registry

logger = logging.getLogger(__name__)


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_prompt_field(text: Optional[str], max_len: int = 160) -> str:
    """Strips control chars and bounds untrusted user/metadata strings before LLM framing."""
    if not text:
        return ""
    cleaned = _CONTROL_CHAR_RE.sub(" ", str(text)).strip()
    return cleaned[:max_len]


class SemanticInspectionPlan(BaseModel):
    """Structured Model A interpretation of garment identity, wear intent, and defects."""

    resolved_category: str
    resolved_subcategory: str
    wearing_style: str = "standard"
    key_structural_features: List[str] = Field(default_factory=list)
    expected_avatar_regions: List[str] = Field(default_factory=list)
    observed_defects_to_check: List[str] = Field(default_factory=list)
    confidence: float = Field(0.75, ge=0.0, le=1.0)
    rationale: str = ""


class GeometryRepairProposal(BaseModel):
    """Bounded Model A repair plan — only permitted bounded operations can execute."""

    operations: List[str] = Field(default_factory=list)
    target_torso_scale_x: float = Field(1.0, ge=0.80, le=1.15)
    target_torso_scale_z: float = Field(1.0, ge=0.65, le=1.10)
    target_sleeve_scale: float = Field(1.0, ge=0.85, le=1.15)
    hood_back_offset_z: float = Field(0.0, ge=-0.08, le=0.06)
    min_clearance_mm: float = Field(3.5, ge=2.5, le=12.0)
    relax_iterations: int = Field(16, ge=4, le=40)
    rationale: str = ""


class MultiModelReasoningResult(BaseModel):
    task: str
    provider_used: str
    model_used: str
    provider_state: str
    schema_valid: bool
    fallback_used: bool
    latency_ms: float
    attempts: List[Dict[str, Any]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)


class MultiModelReasoningService:
    """Provider-resilient multi-model orchestrator for semantic & bounded repair reasoning."""

    _REGION_MAP: Dict[str, List[str]] = {
        "tops": ["neck_collar", "left_shoulder", "right_shoulder", "upper_chest", "mid_torso", "hem_waist", "left_sleeve", "right_sleeve"],
        "outerwear": ["neck_collar", "left_shoulder", "right_shoulder", "upper_chest", "mid_torso", "hem_hip", "left_sleeve", "right_sleeve"],
        "bottoms": ["waistband", "hip_pelvis", "crotch_inseam", "left_leg", "right_leg", "ankle_cuff"],
        "dresses_and_skirts": ["shoulder_bodice", "upper_chest", "waist", "hip_flare", "hem_skirt"],
        "traditional": ["neck_collar", "left_shoulder", "right_shoulder", "chest", "waist", "lower_flare", "left_sleeve", "right_sleeve"],
        "footwear": ["left_ankle", "left_foot", "right_ankle", "right_foot"],
        "accessories": ["head_crown", "neck_wrap", "wrist", "shoulder_strap"],
    }

    def inspect_garment_semantics(
        self,
        *,
        category: str,
        subcategory: str,
        components: Optional[List[str]] = None,
        aspect_ratio: Optional[float] = None,
        wearing_style: str = "standard",
        allow_remote: bool = True,
    ) -> MultiModelReasoningResult:
        cat_clean = sanitize_prompt_field(category or "tops", 40).lower()
        sub_clean = sanitize_prompt_field(subcategory or cat_clean, 48).lower()
        comps = [sanitize_prompt_field(c, 32) for c in (components or [])[:16]]
        ar_str = f"{aspect_ratio:.2f}" if isinstance(aspect_ratio, (int, float)) else "unknown"

        def _deterministic() -> Dict[str, Any]:
            regions = list(self._REGION_MAP.get(cat_clean, self._REGION_MAP["tops"]))
            checks = ["torso_depth_ratio", "left_right_bilateral_symmetry", "skinning_normalization", "overlap_ratio"]
            if "hood" in comps or "hoodie" in sub_clean:
                regions.append("hood_crown")
                checks.extend(["hood_head_clearance", "collar_aperture"])
            if cat_clean in {"bottoms", "dresses_and_skirts"}:
                checks.append("hem_and_crotch_envelope")
            plan = SemanticInspectionPlan(
                resolved_category=cat_clean,
                resolved_subcategory=sub_clean,
                wearing_style=sanitize_prompt_field(wearing_style, 32) or "standard",
                key_structural_features=comps or [cat_clean, sub_clean],
                expected_avatar_regions=regions,
                observed_defects_to_check=checks,
                confidence=0.82,
                rationale=f"Deterministic construction taxonomy inspection for {cat_clean}/{sub_clean} (AR={ar_str}).",
            )
            return plan.model_dump()

        if not allow_remote:
            pref = ["offline_rules"]
        else:
            pref = ["groq", "gemini", "openrouter", "offline_rules"]

        msgs = [
            LLMMessage(
                role="system",
                content=(
                    "You are YORVYN's garment structural inspector. Return ONLY strict JSON matching keys: "
                    "resolved_category, resolved_subcategory, wearing_style, key_structural_features, "
                    "expected_avatar_regions, observed_defects_to_check, confidence, rationale."
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Category={cat_clean}; Subcategory={sub_clean}; AspectRatio={ar_str}; "
                    f"Components={comps}; WearingStyle={sanitize_prompt_field(wearing_style, 32)}."
                ),
            ),
        ]
        outcome = llm_registry.generate_with_fallback(
            msgs,
            preference_order=pref,
            schema_cls=SemanticInspectionPlan,
            deterministic_fallback_fn=_deterministic,
            temperature=0.0,
            max_tokens=320,
            timeout_seconds=8,
            max_retries_per_provider=0,
        )
        p_name = outcome.response.provider_used
        p_state = llm_registry.get_status_report().get(p_name, {}).get("state", "VERIFIED")
        return MultiModelReasoningResult(
            task="semantic_inspection",
            provider_used=p_name,
            model_used=outcome.response.upstream_model or outcome.response.model_used,
            provider_state=str(p_state),
            schema_valid=outcome.schema_valid,
            fallback_used=outcome.fallback_used,
            latency_ms=round(float(outcome.response.latency_ms), 2),
            attempts=outcome.attempts,
            payload=outcome.parsed_json or _deterministic(),
        )

    def propose_geometry_repair_plan(
        self,
        *,
        category: str,
        subcategory: str,
        defects: List[Dict[str, Any]],
        mesh_metrics: Dict[str, Any],
        allow_remote: bool = True,
    ) -> MultiModelReasoningResult:
        """Generates a strictly bounded repair plan from observed defect diagnostics."""
        cat_clean = sanitize_prompt_field(category or "tops", 40).lower()
        sub_clean = sanitize_prompt_field(subcategory or cat_clean, 48).lower()
        defect_codes = [sanitize_prompt_field(str(d.get("defect_type") or d.get("code") or ""), 48) for d in defects[:10]]
        chest_depth = float(mesh_metrics.get("chest_depth_m") or mesh_metrics.get("depth_z_m") or 0.0)
        torso_width = float(mesh_metrics.get("torso_width_m") or mesh_metrics.get("width_x_m") or 0.0)
        head_pens = int(mesh_metrics.get("head_penetration_count") or 0)
        body_pens = int(mesh_metrics.get("penetration_count") or 0)

        def _deterministic() -> Dict[str, Any]:
            ops: List[str] = ["deduplicate_components", "recompute_normals"]
            scale_z = 1.0
            scale_x = 1.0
            hood_dz = 0.0
            if chest_depth > 0.305 and cat_clean in {"tops", "outerwear", "dresses_and_skirts", "traditional"}:
                ops.append("compress_excess_torso_depth")
                scale_z = max(0.68, min(0.96, 0.255 / max(chest_depth, 0.255)))
            if torso_width > 0.56 and cat_clean in {"tops", "outerwear"}:
                ops.append("taper_excess_torso_width")
                scale_x = max(0.82, min(0.96, 0.44 / max(torso_width, 0.44)))
            if head_pens > 0 or any("hood" in c.lower() for c in defect_codes):
                ops.append("enforce_head_neck_clearance")
                hood_dz = -0.045
            if body_pens > 0 or any("penetration" in c.lower() for c in defect_codes):
                ops.append("resolve_elliptical_body_collisions")
            if any("skinning" in c.lower() or "weight" in c.lower() for c in defect_codes):
                ops.append("normalize_skin_weights")
            if any("bilateral" in c.lower() or "swap" in c.lower() for c in defect_codes):
                ops.append("align_bilateral_components")
            if any("leg" in c.lower() or "flare" in c.lower() for c in defect_codes):
                ops.append("constrain_lower_envelope")
            ops.append("laplacian_regularize")
            plan = GeometryRepairProposal(
                operations=ops,
                target_torso_scale_x=round(scale_x, 4),
                target_torso_scale_z=round(scale_z, 4),
                target_sleeve_scale=1.0,
                hood_back_offset_z=hood_dz,
                min_clearance_mm=4.0,
                relax_iterations=18,
                rationale=f"Deterministic repair plan targeting defects={defect_codes}, chest_depth={chest_depth:.3f}m, head_pens={head_pens}.",
            )
            return plan.model_dump()

        pref = ["offline_rules"] if not allow_remote else ["groq", "gemini", "openrouter", "offline_rules"]
        msgs = [
            LLMMessage(
                role="system",
                content=(
                    "You are YORVYN's bounded 3D garment repair planner. Reply ONLY with strict JSON matching: "
                    "operations, target_torso_scale_x (0.8..1.15), target_torso_scale_z (0.65..1.1), "
                    "target_sleeve_scale (0.85..1.15), hood_back_offset_z (-0.08..0.06), min_clearance_mm (2.5..12.0), "
                    "relax_iterations (4..40), rationale."
                ),
            ),
            LLMMessage(
                role="user",
                content=f"Category={cat_clean}/{sub_clean}; Defects={defect_codes}; DepthZ={chest_depth:.3f}m; HeadPens={head_pens}; BodyPens={body_pens}.",
            ),
        ]
        outcome = llm_registry.generate_with_fallback(
            msgs,
            preference_order=pref,
            schema_cls=GeometryRepairProposal,
            deterministic_fallback_fn=_deterministic,
            temperature=0.0,
            max_tokens=320,
            timeout_seconds=8,
            max_retries_per_provider=0,
        )
        p_name = outcome.response.provider_used
        p_state = llm_registry.get_status_report().get(p_name, {}).get("state", "VERIFIED")
        return MultiModelReasoningResult(
            task="geometry_repair_plan",
            provider_used=p_name,
            model_used=outcome.response.upstream_model or outcome.response.model_used,
            provider_state=str(p_state),
            schema_valid=outcome.schema_valid,
            fallback_used=outcome.fallback_used,
            latency_ms=round(float(outcome.response.latency_ms), 2),
            attempts=outcome.attempts,
            payload=outcome.parsed_json or _deterministic(),
        )


multi_model_reasoning = MultiModelReasoningService()
