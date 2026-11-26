"""
YORVYN Intelligence Platform (YIP) — Fashion Intelligence Engine (Phase 17.0 Stage 3).

Coordinates Phase 16.1 component understanding, Phase 16.2 pattern/construction graphs,
visual fabric & drape estimation, and strict OBSERVED vs INFERRED vs AMBIGUOUS vs UNSUPPORTED provenance.
Never claims hidden rear construction as observed or laboratory fiber identity without measurements.
"""
from __future__ import annotations

import io
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from backend.app.services.garments.appearance.material_profiles import CategoryMaterialSystem
from backend.app.services.intelligence.inference_adapters import inference_telemetry


class FashionEvidenceState(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


class FabricIntelligenceReport(BaseModel):
    fabric_appearance: str
    weave_or_knit_appearance: str
    estimated_drape: str
    estimated_weight_gsm: float
    roughness: float
    specular_score: float
    evidence_state: FashionEvidenceState = FashionEvidenceState.INFERRED
    is_laboratory_composition: bool = False
    limitations: str = "Visual surface cues estimate fabric appearance and computational drape only; physical textile composition requires lab testing."


class FashionComponentEntry(BaseModel):
    component_id: str
    category_role: str
    presence_state: FashionEvidenceState
    visibility: str
    confidence: Optional[float] = None
    source_views: List[str] = Field(default_factory=list)


class FashionConstructionSummary(BaseModel):
    panel_count: int
    seam_count: int
    symmetry_score: float
    has_back_view: bool
    hidden_rear_state: FashionEvidenceState
    pattern_valid: bool
    validation_issues: List[str] = Field(default_factory=list)


class FashionIntelligenceReport(BaseModel):
    category: str
    subcategory: str
    style_family: str
    silhouette: str
    structural_complexity: str
    classification_state: FashionEvidenceState
    components: List[FashionComponentEntry] = Field(default_factory=list)
    construction: FashionConstructionSummary
    fabric: FabricIntelligenceReport
    evidence_summary: Dict[str, List[str]] = Field(default_factory=dict)
    latency_ms: float = 0.0


_COMPLEXITY_MAP = {
    "tshirt": "low",
    "skirt": "low_to_medium",
    "shirt": "medium",
    "hoodie": "medium_to_high",
    "jacket": "high",
    "dress": "medium_to_high",
    "trousers": "medium",
    "jeans": "medium_to_high",
}


class FashionIntelligenceEngine:
    """Specialized Phase 17.0 garment classification, component, construction, and fabric engine."""

    def analyze_fabric_appearance(
        self,
        image: Image.Image,
        *,
        category: str,
        subcategory: str,
    ) -> FabricIntelligenceReport:
        rgb = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)

        # Specular peak detection (HSV S-low / V-high ratio) and high-pass surface roughness
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        v_ch = hsv[:, :, 2]
        s_ch = hsv[:, :, 1]
        specular = float(np.mean((v_ch > 215) & (s_ch < 45)))
        lap_std = float(np.std(cv2.Laplacian(gray, cv2.CV_32F)))

        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()

        if "denim" in sub_l:
            appearance, weave, drape = "denim", "diagonal_twill", "structured_rigid"
            weight_gsm = 390.0
        elif cat_l == "jacket" or "leather" in sub_l or specular > 0.08:
            appearance, weave, drape = "structured_outerwear", "tight_plain_or_coated", "crisp_structured"
            weight_gsm = 340.0
        elif cat_l == "hoodie" or "fleece" in sub_l or "sweatshirt" in cat_l:
            appearance, weave, drape = "cotton_fleece", "brushed_knit_terry", "heavy_soft_drape"
            weight_gsm = 360.0
        elif "sweater" in cat_l or "knit" in sub_l or lap_std > 28.0:
            appearance, weave, drape = "knit_wool_blend", "interlock_rib_knit", "compliant_stretch_drape"
            weight_gsm = 310.0
        elif cat_l in {"dress", "skirt"} and specular > 0.04:
            appearance, weave, drape = "satin_or_silk_appearance", "high_sheen_plain_weave", "fluid_drape"
            weight_gsm = 150.0
        else:
            appearance, weave, drape = "cotton_jersey_or_poplin", "fine_plain_or_jersey", "balanced_drape"
            weight_gsm = 195.0

        prof = CategoryMaterialSystem.get_material_profile(
            category=cat_l,
            subcategory=sub_l,
            fabric_hint=appearance,
            specular_evidence=specular,
        )
        return FabricIntelligenceReport(
            fabric_appearance=appearance,
            weave_or_knit_appearance=weave,
            estimated_drape=drape,
            estimated_weight_gsm=weight_gsm,
            roughness=round(float(getattr(prof, "roughness", 0.72)), 3),
            specular_score=round(specular, 4),
            evidence_state=FashionEvidenceState.INFERRED,
            is_laboratory_composition=False,
        )

    def analyze_garment(
        self,
        *,
        image_bytes: Optional[bytes] = None,
        back_image_bytes: Optional[bytes] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        silhouette: Optional[str] = None,
    ) -> FashionIntelligenceReport:
        t0 = time.perf_counter()
        resolved_cat = (category or "jacket").lower()
        resolved_sub = (subcategory or f"standard_{resolved_cat}").lower()
        classification_state = FashionEvidenceState.INFERRED

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB") if image_bytes else Image.new("RGB", (256, 256), (120, 130, 145))

        if image_bytes and not category:
            try:
                from backend.app.services.intelligence.local_perception import classifier_prediction
                pred = classifier_prediction(image_bytes)
                if pred and pred.get("confidence", 0.0) >= 0.45:
                    resolved_cat = pred["category"]
                    resolved_sub = pred["subcategory"]
                    classification_state = FashionEvidenceState.OBSERVED if pred["confidence"] >= 0.75 else FashionEvidenceState.INFERRED
            except Exception:
                classification_state = FashionEvidenceState.AMBIGUOUS

        has_back = bool(back_image_bytes)
        fabric = self.analyze_fabric_appearance(img, category=resolved_cat, subcategory=resolved_sub)

        # Build canonical pattern construction & graph through existing Phase 16.2 engine
        from backend.app.services.ai.contracts import (
            CanonicalGarmentSpecificationV2,
            GarmentItemEvidence,
            ImageEvidenceRecord,
            ReconstructionReadiness,
        )
        from backend.app.services.intelligence.component_evidence import analyze_garment_components
        from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine

        views = [
            ImageEvidenceRecord(
                image_id="front_1",
                image_hash="h_front",
                view_type="front",
                usable=True,
                resolution=img.size,
            )
        ]
        f_bytes = image_bytes
        if not f_bytes:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            f_bytes = buf.getvalue()

        img_inputs = [("front_1", f_bytes, "front")]
        if has_back and back_image_bytes:
            views.append(ImageEvidenceRecord(
                image_id="back_1",
                image_hash="h_back",
                view_type="back",
                usable=True,
                resolution=img.size,
            ))
            img_inputs.append(("back_1", back_image_bytes, "back"))

        spec = CanonicalGarmentSpecificationV2(
            garment_id="yip_fashion_analysis",
            garment=GarmentItemEvidence(
                category=resolved_cat,
                subcategory=resolved_sub,
                confidence=0.80,
            ),
            views=views,
            reconstruction_readiness=ReconstructionReadiness(status="READY" if has_back else "PARTIAL"),
        )
        comp_bundle = analyze_garment_components(
            img_inputs,
            garment_id="yip_fashion_analysis",
            category=resolved_cat,
            subcategory=resolved_sub,
            view_records=views,
        )
        handoff = pattern_construction_engine.build_construction(
            garment_id="yip_fashion_analysis",
            category=resolved_cat,
            subcategory=resolved_sub,
            component_bundle=comp_bundle,
            specification=spec,
        )

        components_out: List[FashionComponentEntry] = []
        observed_list: List[str] = []
        inferred_list: List[str] = ["rear_panel_construction" if not has_back else "rear_panel_observed", "fabric_composition_unmeasured"]
        unsupported_list: List[str] = ["laboratory_fiber_percentage", "certified_sewing_seam_allowance"]

        for cid, comp in comp_bundle.fused_components.items():
            ev_val = comp.evidence_status.value.upper()
            if "OBSERVED" in ev_val and "NOT_" not in ev_val:
                state = FashionEvidenceState.OBSERVED
                observed_list.append(cid)
            elif "CONFLICT" in ev_val or comp.contradicted:
                state = FashionEvidenceState.AMBIGUOUS
            else:
                state = FashionEvidenceState.INFERRED
                inferred_list.append(cid)
            components_out.append(FashionComponentEntry(
                component_id=cid,
                category_role=comp.component_type,
                presence_state=state,
                visibility=comp.best_visibility.value,
                confidence=comp.confidence,
                source_views=list(comp.source_views),
            ))

        graph = handoff.construction_graph
        construction = FashionConstructionSummary(
            panel_count=len(graph.pieces),
            seam_count=len(graph.seams),
            symmetry_score=round(float(graph.construction_confidence), 3),
            has_back_view=has_back,
            hidden_rear_state=FashionEvidenceState.OBSERVED if has_back else FashionEvidenceState.INFERRED,
            pattern_valid=bool(handoff.validation_report.is_valid),
            validation_issues=[iss.message for iss in (handoff.validation_report.issues or [])[:5]],
        )

        style_family = "tailored_structured" if resolved_cat in {"jacket", "shirt", "trousers"} else "casual_contemporary"
        silhouette_val = silhouette or ("boxy_relaxed" if resolved_cat in {"hoodie", "jacket"} else "regular_block")
        complexity = _COMPLEXITY_MAP.get(resolved_cat, "medium")

        lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("pattern-construction-v16.2", lat_ms, device="cpu", backend="deterministic_cad")
        return FashionIntelligenceReport(
            category=resolved_cat,
            subcategory=resolved_sub,
            style_family=style_family,
            silhouette=silhouette_val,
            structural_complexity=complexity,
            classification_state=classification_state,
            components=components_out,
            construction=construction,
            fabric=fabric,
            evidence_summary={
                "OBSERVED": sorted(set(observed_list)),
                "INFERRED": sorted(set(inferred_list)),
                "UNSUPPORTED": unsupported_list,
            },
            latency_ms=lat_ms,
        )


fashion_intelligence_v17 = FashionIntelligenceEngine()
