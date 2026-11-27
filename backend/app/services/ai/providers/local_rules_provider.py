"""
YORVYN — Local Rule-Based Attribute Normalizer & Fallback Provider (Phase 14.26)
Provides 100% offline, deterministic fashion attribute normalization and taxonomy resolution:
- Used as fallback when cloud reasoning providers (Groq) are uncredentialed or unavailable
- Normalizes category, subcategory, construction parameters, and material presets
- Zero cloud cost, sub-millisecond execution, completely deterministic
"""

from __future__ import annotations

import time
import logging
from typing import Dict, Any, List, Optional

from backend.app.services.ai.base import (
    AIProvider,
    AIRequest,
    AIProviderResponse,
    ProviderCapability,
    ProviderHealth,
    ProviderError,
    ModelMetadata,
    TokenUsage,
    TaskType
)

logger = logging.getLogger(__name__)


class LocalRulesProvider(AIProvider):
    """Offline deterministic rule-based normalizer and fallback reasoning engine."""

    def __init__(self):
        super().__init__("local_rules")

    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.TEXT_REASONING,
            ProviderCapability.STRUCTURED_JSON,
            ProviderCapability.ATTRIBUTE_NORMALIZATION,
            ProviderCapability.OFFLINE_LOCAL
        ]

    def is_available(self) -> bool:
        return True

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            is_available=True,
            status_message="Operational (Deterministic Local Fashion Rules Engine)",
            active_capabilities=self.capabilities(),
            last_latency_ms=0.5,
            failure_count=0,
            circuit_open=False
        )

    def execute(self, request: AIRequest) -> AIProviderResponse:
        t0 = time.perf_counter()

        v_ctx = request.structured_context or {}
        garment_info = v_ctx.get("garment", {})
        cat = garment_info.get("category", "hoodie").lower().replace(" ", "_")
        subcat = garment_info.get("subcategory", f"standard_{cat}").lower().replace(" ", "_")
        comps = v_ctx.get("components", {})
        app = v_ctx.get("appearance", {})

        # Determine taxonomy tier
        tier = "tops"
        if cat in ["jeans", "trousers", "shorts", "skirt"]:
            tier = "bottoms"
        elif cat in ["jacket", "coat"]:
            tier = "outerwear"
        elif cat in ["dress"]:
            tier = "dresses_and_skirts"
        elif cat in ["kurta", "tunic", "traditional_clothing"]:
            tier = "traditional"

        # Determine sleeve type
        sleeve_info = comps.get("sleeves", {})
        sleeve_present = sleeve_info.get("present", True) if isinstance(sleeve_info, dict) else True
        sleeve_type = sleeve_info.get("type", "long") if isinstance(sleeve_info, dict) else "long"
        normalized_sleeve = "long_sleeve"
        if not sleeve_present:
            normalized_sleeve = "sleeveless"
        elif "short" in sleeve_type or cat == "tshirt":
            normalized_sleeve = "short_sleeve"

        # Determine neckline
        neck_info = comps.get("neckline", {})
        neck_type = neck_info.get("type", "crewneck") if isinstance(neck_info, dict) else "crewneck"
        if cat == "hoodie":
            neck_type = "hooded"
        elif cat == "shirt":
            neck_type = "collared"

        # Determine pockets
        has_pocket = False
        pocket_type = None
        pocket_info = comps.get("pockets", {})
        if isinstance(pocket_info, dict) and pocket_info.get("present", False):
            has_pocket = True
            pocket_type = pocket_info.get("type", "kangaroo" if cat == "hoodie" else "patch")
        elif cat == "hoodie":
            has_pocket = True
            pocket_type = "kangaroo_pocket"

        # DAG Template resolution
        dag_mapping = {
            "hoodie": "hoodie_construction",
            "shirt": "shirt_construction",
            "jacket": "jacket_construction",
            "tshirt": "tshirt_construction",
            "sweatshirt": "sweatshirt_construction",
            "sweater": "sweater_construction",
            "jeans": "bottoms",
            "trousers": "bottoms",
            "shorts": "bottoms",
            "dress": "dress",
            "skirt": "skirt",
            "kurta": "kurta",
            "traditional_clothing": "kurta"
        }
        target_dag = dag_mapping.get(cat, "hoodie_construction")

        # Material preset resolution
        fabric = app.get("fabric_appearance", "cotton").lower()
        if "fleece" in fabric or cat == "hoodie":
            material_preset = "cotton_fleece_pbr"
        elif "denim" in fabric or cat in ["jeans", "jacket"]:
            material_preset = "denim_twill_pbr"
        elif "knit" in fabric or cat in ["sweater", "sweatshirt"]:
            material_preset = "wool_knit_pbr"
        elif "silk" in fabric or cat in ["dress", "traditional_clothing"]:
            material_preset = "silk_satin_pbr"
        else:
            material_preset = "cotton_broadcloth_pbr"

        normalized_data = {
            "category": cat,
            "subcategory": subcat,
            "taxonomy_tier": tier,
            "attributes": {
                "fit": "oversized" if "oversized" in subcat else "regular",
                "pattern": app.get("pattern", "solid"),
                "sleeve_type": normalized_sleeve,
                "neckline": neck_type,
                "closure": "pullover" if cat in ["hoodie", "tshirt", "sweatshirt"] else "button_placket",
                "pockets": [pocket_type] if pocket_type else []
            },
            "reconstruction_parameters": {
                "target_dag_template": target_dag,
                "enable_hood_mesh": (cat == "hoodie" or "hood" in comps),
                "enable_pocket_mesh": has_pocket,
                "pocket_type": pocket_type,
                "material_preset": material_preset
            },
            "conflict_resolutions": [
                {
                    "attribute": "taxonomy_and_dag",
                    "winner": "local_rules_engine",
                    "reason": f"Deterministic patternmaker mapping applied for category '{cat}'."
                }
            ],
            "reasoning_summary": f"Deterministic local rule normalization for {subcat} ({cat}) in {tier} tier."
        }

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return AIProviderResponse(
            request_id=request.request_id,
            provider_name=self.name,
            model_metadata=ModelMetadata(
                provider_name=self.name,
                model_name="Deterministic-Rule-Engine",
                model_version="1.0-offline",
                device="cpu",
                is_local=True,
                commercial_licensed=False,
                license_type="Repository license not independently verified"
            ),
            task_type=request.task_type,
            success=True,
            raw_text=str(normalized_data),
            structured_data=normalized_data,
            token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
            latency_ms=latency_ms,
            provenance_notes=["Deterministic local rule engine execution (100% offline fallback)"]
        )
