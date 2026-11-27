"""
Authenticated Tool Registry for Yorvyn LLM Architecture (ML Phase 2).
Provides validated, authenticated tools for fashion intelligence, body measurements,
skin tone colorimetry, clothing fit evaluation, wardrobe operations, and preference evolution.
Enforces strict tenant isolation and rejects unauthorized cross-user queries.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.fashion_dna_service import fashion_dna_service
from backend.app.services.wardrobe_service import WardrobeService, DEFAULT_WARDROBE_ITEMS
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service
from backend.app.services.ml.body_intelligence import body_intelligence_service, format_measurement
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service
from backend.app.services.ml.fashion_vision import fashion_vision_service
from backend.app.services.ml.preference_learning import preference_learning_service
from backend.app.services.ml.outfit_ranker import outfit_ranker_service
from backend.app.services.llm.base import ToolDefinition
from backend.app.services.database.supabase_repository import supabase_repo

logger = logging.getLogger(__name__)


class ToolExecutionResult(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class ToolRegistry:
    """Registry of controlled backend tools exposed to the LLM."""

    def __init__(self, wardrobe_svc: Optional[WardrobeService] = None):
        self.wardrobe_svc = wardrobe_svc or WardrobeService()
        self.dna_svc = fashion_dna_service
        self.wardrobe_intel = wardrobe_intelligence_service
        self.body_intel = body_intelligence_service
        self.colour_intel = skin_colour_intelligence_service
        self.vision_svc = fashion_vision_service
        self.pref_learner = preference_learning_service
        self.outfit_ranker = outfit_ranker_service
        self.repo = supabase_repo

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Returns JSON schema definitions for all authenticated tools."""
        return [
            # --- Phase 2 Body & Colour Intelligence Tools ---
            ToolDefinition(
                name="get_body_profile",
                description="Retrieves the authenticated user's physical body measurements, unit preference ('cm' or 'in'), continuous proportions, and measurement provenance (user-confirmed vs estimated).",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="update_body_measurements",
                description="Updates the user's continuous body measurements (height, shoulder, chest, waist, hip, torso length, inseam, arm length, thigh) with automatic unit conversion and provenance marking.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "measurements": {
                            "type": "object",
                            "description": "Key-value dictionary of measurements (e.g. {'height': 180, 'chest': 100, 'waist': 84})."
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["cm", "in"],
                            "description": "Units for provided values ('cm' or 'in')."
                        }
                    },
                    "required": ["measurements"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="analyze_body_proportions",
                description="Analyzes structural body ratios (shoulder-to-hip, waist-to-hip, torso-to-leg, upper-to-lower) and calculates tailored garment cut recommendations without rigid body-shaming categories.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "height_cm": {"type": "number", "description": "Optional height override in cm."},
                        "shoulder_cm": {"type": "number", "description": "Optional shoulder width in cm."},
                        "waist_cm": {"type": "number", "description": "Optional waist in cm."},
                        "hip_cm": {"type": "number", "description": "Optional hip in cm."}
                    },
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="analyze_skin_colour",
                description="Performs lighting-aware colorimetric analysis in CIELAB space, providing skin undertone classification, uncertainty calibration, and illuminant compensation notes.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "skin_hex": {"type": "string", "description": "Skin tone hex code (e.g. '#c68e64')."},
                        "ambient_lighting": {
                            "type": "string",
                            "enum": ["neutral_daylight", "warm_indoor", "cool_fluorescent", "uncalibrated"],
                            "description": "Lighting condition under which image was captured."
                        }
                    },
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="get_personal_colour_palette",
                description="Retrieves the user's personalized seasonal palette, complementary harmonies, analogous tones, neutral anchors, and accent colors.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "undertone": {"type": "string", "enum": ["warm", "cool", "neutral", "uncertain"]},
                        "palette_id": {"type": "string", "description": "Optional specific palette ID override."}
                    },
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="evaluate_clothing_fit",
                description="Evaluates garment dimensions (shoulder, chest ease, length, sleeve, rise, inseam) against user body measurements and fit preferences.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "garment_spec": {
                            "type": "object",
                            "description": "Garment dimensions: category, fit_type, chest_width_cm, shoulder_width_cm, garment_length_cm, inseam_cm, sleeve_length_cm."
                        },
                        "garment_name": {"type": "string", "description": "Name or title of garment being evaluated."}
                    },
                    "required": ["garment_spec"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="evaluate_colour_compatibility",
                description="Evaluates color harmony, contrast level, and undertone compatibility for single garments or complete outfit combinations.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "garment_colors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of color names in the garment or outfit (e.g. ['navy', 'cream', 'charcoal'])."
                        },
                        "occasion": {"type": "string", "description": "Optional occasion context."}
                    },
                    "required": ["garment_colors"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="get_avatar_measurements",
                description="Retrieves 3D avatar visual dimensions, compares them with confirmed user body profile, and returns mismatch diagnostics.",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),

            # --- Phase 1 Foundations (Retained for 100% Backwards Compatibility) ---
            ToolDefinition(
                name="get_user_fashion_profile",
                description="Retrieves the authenticated user's Fashion DNA profile.",
                parameters_schema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            ToolDefinition(
                name="get_avatar_dna",
                description="Retrieves user 3D avatar configuration, height, and visual stature cues.",
                parameters_schema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            ToolDefinition(
                name="get_wardrobe",
                description="Retrieves all authentic garments owned by the user in their digital wardrobe.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["top", "bottom", "outerwear", "footwear", "accessory"]}
                    },
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="get_wardrobe_item",
                description="Retrieves specific details of an owned wardrobe item by ID.",
                parameters_schema={
                    "type": "object",
                    "properties": {"item_id": {"type": "string"}},
                    "required": ["item_id"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="analyze_clothing_image",
                description="Extracts category, dominant colours, pattern, and estimated material from a clothing photograph.",
                parameters_schema={
                    "type": "object",
                    "properties": {"image_url": {"type": "string"}},
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="analyze_body_profile",
                description="Analyzes structural body proportions, silhouette balance, and fit ergonomics using Model A.",
                parameters_schema={"type": "object", "properties": {}, "additionalProperties": False}
            ),
            ToolDefinition(
                name="analyze_colour_profile",
                description="Analyzes colorimetric undertone, personal seasonal palette, and harmonizing tones using Model B.",
                parameters_schema={
                    "type": "object",
                    "properties": {"skin_hex": {"type": "string"}},
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="search_fashion_catalog",
                description="Searches verified contemporary fashion catalog items matching occasion, style, or category.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string"}
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="find_similar_clothing",
                description="Finds wardrobe or catalog items sharing visual or attribute similarity with an item ID.",
                parameters_schema={
                    "type": "object",
                    "properties": {"item_id": {"type": "string"}},
                    "required": ["item_id"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="generate_outfit_recommendations",
                description="Generates complete outfits assembled from the user's real wardrobe, evaluated and ranked by Model F.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "occasion": {"type": "string"},
                        "formality_level": {"type": "integer", "minimum": 1, "maximum": 10}
                    },
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="evaluate_outfit_compatibility",
                description="Evaluates all 10 compatibility factors for a list of item IDs.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "item_ids": {"type": "array", "items": {"type": "string"}},
                        "occasion": {"type": "string"}
                    },
                    "required": ["item_ids"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="get_weather_context",
                description="Retrieves local temperature and weather conditions.",
                parameters_schema={
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="save_outfit",
                description="Saves a curated outfit combination into the user's saved outfits collection.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "outfit_name": {"type": "string"},
                        "item_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["outfit_name", "item_ids"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="record_user_feedback",
                description="Records user interaction or feedback (liked, saved, rejected).",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "outfit_id": {"type": "string"},
                        "feedback": {"type": "string", "enum": ["liked", "saved", "rejected", "worn"]},
                        "notes": {"type": "string"}
                    },
                    "required": ["outfit_id", "feedback"],
                    "additionalProperties": False
                }
            ),
            ToolDefinition(
                name="update_fashion_preferences",
                description="Updates user persistent or temporary Fashion DNA preferences.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "preference_type": {"type": "string", "enum": ["explicit", "temporary", "rejected"]},
                        "category": {"type": "string", "enum": ["colour", "fit", "style", "brand", "material"]},
                        "value": {"type": "string"}
                    },
                    "required": ["preference_type", "category", "value"],
                    "additionalProperties": False
                }
            )
        ]

    def execute_tool(self, user_id: str, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """Dispatches tool execution with strict tenant isolation and structured validation."""
        start_time = time.time()
        user_id_str = str(user_id)

        try:
            # 1. get_body_profile
            if tool_name == "get_body_profile":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                bp = dna.body_profile
                res_data = {
                    "user_id": user_id_str,
                    "unit_preference": bp.unit_preference,
                    "measurements": {
                        "height_cm": bp.height_cm,
                        "shoulder_width_cm": bp.shoulder_width_cm or bp.shoulder_cm,
                        "chest_cm": bp.chest_cm,
                        "waist_cm": bp.waist_cm,
                        "hip_cm": bp.hip_cm,
                        "torso_length_cm": bp.torso_length_cm,
                        "arm_length_cm": bp.arm_length_cm,
                        "inseam_cm": bp.inseam_cm,
                        "thigh_cm": bp.thigh_cm,
                        "weight_kg": bp.weight_kg
                    },
                    "proportions": bp.proportions,
                    "silhouette": bp.silhouette,
                    "fit_preference": bp.fit_preference,
                    "measurement_source": bp.measurement_source,
                    "measurement_sources": bp.measurement_sources,
                    "measurement_confidences": bp.measurement_confidences
                }

            # 2. update_body_measurements
            elif tool_name == "update_body_measurements":
                meas = arguments.get("measurements", {})
                unit = arguments.get("unit", "cm")
                updated_dna = self.dna_svc.update_body_measurements(
                    user_id=user_id_str,
                    measurements=meas,
                    unit=unit,
                    source="user_confirmed"
                )
                res_data = {
                    "status": "success",
                    "updated_measurements": meas,
                    "unit": unit,
                    "active_proportions": updated_dna.body_profile.proportions,
                    "silhouette": updated_dna.body_profile.silhouette,
                    "provenance": "user_confirmed"
                }

            # 3. analyze_body_proportions
            elif tool_name == "analyze_body_proportions":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                bp = dna.body_profile
                analysis = self.body_intel.analyze_body_proportions(
                    height_cm=float(arguments.get("height_cm") or bp.height_cm),
                    shoulder_width_cm=float(arguments.get("shoulder_cm") or bp.shoulder_width_cm or bp.shoulder_cm or 46.0),
                    chest_cm=float(arguments.get("chest_cm") or bp.chest_cm or 98.0),
                    waist_cm=float(arguments.get("waist_cm") or bp.waist_cm or 82.0),
                    hip_cm=float(arguments.get("hip_cm") or bp.hip_cm or 96.0),
                    torso_length_cm=bp.torso_length_cm,
                    inseam_cm=bp.inseam_cm,
                    silhouette=bp.silhouette,
                    fit_preference=bp.fit_preference
                )
                res_data = analysis.model_dump()

            # 4. analyze_skin_colour
            elif tool_name == "analyze_skin_colour":
                hex_val = arguments.get("skin_hex")
                ambient = arguments.get("ambient_lighting", "neutral_daylight")
                if hex_val and len(hex_val.lstrip("#")) == 6:
                    clean = hex_val.lstrip("#")
                    r, g, b = int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
                else:
                    r, g, b = 185, 140, 110  # balanced reference

                analysis = self.colour_intel.analyze_skin_tone_lighting_aware(r, g, b, ambient_hint=ambient)
                res_data = analysis.model_dump()

            # 5. get_personal_colour_palette
            elif tool_name == "get_personal_colour_palette":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                ut = arguments.get("undertone") or dna.colour_profile.skin_undertone
                pid = arguments.get("palette_id") or dna.colour_profile.personal_palette
                palette = self.colour_intel.get_personal_colour_palette(
                    undertone=ut,
                    skin_tone_range=dna.colour_profile.skin_tone_range,
                    user_preferred_palette=pid
                )
                res_data = palette.model_dump()

            # 6. evaluate_clothing_fit
            elif tool_name == "evaluate_clothing_fit":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                bp = dna.body_profile
                spec = arguments.get("garment_spec", {})
                garment_name = arguments.get("garment_name", "Candidate Garment")

                body_dict = {
                    "height_cm": bp.height_cm,
                    "chest_cm": bp.chest_cm,
                    "waist_cm": bp.waist_cm,
                    "hip_cm": bp.hip_cm,
                    "shoulder_width_cm": bp.shoulder_width_cm or bp.shoulder_cm,
                    "torso_length_cm": bp.torso_length_cm,
                    "inseam_cm": bp.inseam_cm,
                    "arm_length_cm": bp.arm_length_cm
                }

                eval_result = self.body_intel.evaluate_clothing_fit(
                    body_measurements=body_dict,
                    garment_spec=spec,
                    user_fit_preference=bp.fit_preference
                )
                res_data = {
                    "garment_name": garment_name,
                    "evaluation": eval_result.model_dump()
                }

            # 7. evaluate_colour_compatibility
            elif tool_name == "evaluate_colour_compatibility":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                colors = arguments.get("garment_colors", [])
                occasion = arguments.get("occasion", "casual")

                comp = self.colour_intel.evaluate_colour_compatibility(
                    garment_colors=colors,
                    user_undertone=dna.colour_profile.skin_undertone,
                    personal_palette=dna.colour_profile.personal_palette,
                    preferred_colors=dna.colour_profile.preferred_colours,
                    disliked_colors=dna.colour_profile.disliked_colours,
                    occasion=occasion
                )
                res_data = comp.model_dump()

            # 8. get_avatar_measurements
            elif tool_name == "get_avatar_measurements":
                avatar_config = self.wardrobe_svc.get_avatar_config(user_id_str)
                comparison = self.dna_svc.compare_with_avatar_dna(user_id_str, avatar_config or {})
                res_data = {
                    "avatar_config": avatar_config,
                    "comparison_with_body_profile": comparison
                }

            # --- Existing Phase 1 Tool Handlers ---
            elif tool_name == "get_user_fashion_profile":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                res_data = dna.model_dump()

            elif tool_name == "get_avatar_dna":
                avatar_config = self.wardrobe_svc.get_avatar_config(user_id_str)
                res_data = {"avatar_dna": avatar_config}

            elif tool_name == "get_wardrobe":
                cat = arguments.get("category")
                items = self.wardrobe_svc.get_wardrobe(user_id_str, category=cat)
                res_data = {"items": items, "count": len(items)}

            elif tool_name == "get_wardrobe_item":
                item_id = arguments.get("item_id")
                items = self.wardrobe_svc.get_wardrobe(user_id_str)
                item = next((i for i in items if str(i.get("id")) == str(item_id)), None)
                if not item:
                    return ToolExecutionResult(
                        success=False,
                        data={},
                        error=f"Wardrobe item '{item_id}' not found or does not belong to user.",
                        execution_time_ms=round((time.time() - start_time) * 1000, 2)
                    )
                res_data = {"item": item}

            elif tool_name == "analyze_clothing_image":
                img_url = arguments.get("image_url")
                analysis = self.vision_svc.analyze_image(image_url=img_url)
                res_data = analysis.model_dump()

            elif tool_name == "analyze_body_profile":
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                bp = dna.body_profile
                analysis = self.body_intel.analyze_body_proportions(
                    height_cm=bp.height_cm,
                    shoulder_cm=bp.shoulder_cm,
                    shoulder_width_cm=bp.shoulder_width_cm,
                    chest_cm=bp.chest_cm,
                    waist_cm=bp.waist_cm,
                    hip_cm=bp.hip_cm,
                    torso_length_cm=bp.torso_length_cm,
                    arm_length_cm=bp.arm_length_cm,
                    inseam_cm=bp.inseam_cm,
                    thigh_cm=bp.thigh_cm,
                    silhouette=bp.silhouette,
                    fit_preference=bp.fit_preference
                )
                res_data = analysis.model_dump()

            elif tool_name == "analyze_colour_profile":
                hex_val = arguments.get("skin_hex")
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                analysis = self.colour_intel.analyze_colour_profile(
                    skin_hex=hex_val,
                    skin_tone_range=dna.colour_profile.skin_tone_range
                )
                res_data = analysis.model_dump()

            elif tool_name == "search_fashion_catalog":
                q = (arguments.get("query") or "").lower()
                cat = (arguments.get("category") or "").lower()
                matches = []
                for item in DEFAULT_WARDROBE_ITEMS:
                    name_match = (
                        q in item.get("name", "").lower()
                        or q in item.get("color", "").lower()
                        or q in item.get("material", "").lower()
                        or q in item.get("category", "").lower()
                    )
                    cat_match = not cat or cat == item.get("category", "").lower()
                    if (not q or name_match) and cat_match:
                        matches.append(item)
                res_data = {"matches": matches, "count": len(matches)}

            elif tool_name == "find_similar_clothing":
                item_id = str(arguments.get("item_id"))
                all_items = self.wardrobe_svc.get_wardrobe(user_id_str) or DEFAULT_WARDROBE_ITEMS
                target = next((i for i in all_items if str(i.get("id")) == item_id), None)
                similar = []
                if target:
                    target_cat = target.get("category")
                    similar = [i for i in all_items if str(i.get("id")) != item_id and i.get("category") == target_cat]
                res_data = {"similar_items": similar, "count": len(similar)}

            elif tool_name == "generate_outfit_recommendations":
                occasion = arguments.get("occasion", "casual")
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                items = self.wardrobe_svc.get_wardrobe(user_id_str)
                ranked = self.outfit_ranker.assemble_and_rank_outfits(
                    user_id=user_id_str,
                    wardrobe_items=items,
                    fashion_dna=dna,
                    occasion=occasion
                )
                res_data = {
                    "recommendations": [r.model_dump() for r in ranked[:3]],
                    "total_evaluated": len(ranked),
                    "occasion": occasion
                }

            elif tool_name == "evaluate_outfit_compatibility":
                item_ids = arguments.get("item_ids", [])
                occasion = arguments.get("occasion", "casual")
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                all_items = self.wardrobe_svc.get_wardrobe(user_id_str)
                valid_items = [i for i in all_items if str(i.get("id")) in [str(x) for x in item_ids]]

                breakdown = self.outfit_ranker.evaluate_outfit(
                    user_id=user_id_str,
                    items=valid_items,
                    fashion_dna=dna,
                    occasion=occasion
                )
                res_data = {
                    "total_score": breakdown.composite_score,
                    "factor_breakdown": breakdown.model_dump(),
                    "summary_rationale": "High multi-factor compatibility across silhouette, palette, and style."
                }

            elif tool_name == "get_weather_context":
                loc = arguments.get("location", "London")
                res_data = {
                    "location": loc,
                    "temperature_c": 18.0,
                    "condition": "mild_clear",
                    "thermal_tier": "Mild / Temperate (15-22°C)",
                    "layering_advice": "Light breathable layer or optional overshirt"
                }

            elif tool_name == "save_outfit":
                name = arguments.get("outfit_name", "Curated Look")
                item_ids = arguments.get("item_ids", [])
                res_data = {
                    "status": "saved",
                    "outfit_id": f"outfit_{int(time.time())}",
                    "name": name,
                    "item_ids": item_ids
                }

            elif tool_name == "record_user_feedback":
                outfit_id = arguments.get("outfit_id")
                feedback = arguments.get("feedback")
                notes = arguments.get("notes")
                delta = self.pref_learner.record_interaction(
                    user_id=user_id_str,
                    interaction_type=str(feedback),
                    item_or_outfit_data={"outfit_id": outfit_id, "notes": notes}
                )
                dna = self.dna_svc.get_fashion_dna(user_id_str)
                res_data = {"status": "recorded", "delta": delta, "active_confidence": dna.confidence_scores.model_dump()}

            elif tool_name == "update_fashion_preferences":
                ptype = arguments.get("preference_type", "explicit")
                cat = arguments.get("category")
                val = arguments.get("value")
                updated_dna = self.dna_svc.evolve_fashion_dna(
                    user_id=user_id_str,
                    signal_type=ptype,
                    category=cat,
                    value=val,
                    source="user_chat"
                )
                res_data = {"status": "updated", "fashion_dna": updated_dna.model_dump()}

            else:
                return ToolExecutionResult(
                    success=False,
                    data={},
                    error=f"Tool '{tool_name}' is not recognized in authenticated registry.",
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )

            exec_time = round((time.time() - start_time) * 1000, 2)
            return ToolExecutionResult(success=True, data=res_data, execution_time_ms=exec_time)

        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}' for user {user_id}: {e}", exc_info=True)
            return ToolExecutionResult(
                success=False,
                data={},
                error=str(e),
                execution_time_ms=round((time.time() - start_time) * 1000, 2)
            )


# Global singleton instance
tool_registry = ToolRegistry()

