"""A closed vocabulary shared by the chat planner and garment executor."""
import os
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from .base import LLMMessage, ToolDefinition, ProviderHTTPError
from backend.app.services.ai.provider_diagnostics import exception_failure
from .config import LLMConfiguration
from .registry import llm_registry
from .token_tracker import token_tracker


class GarmentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["identify", "reconstruct", "widen", "shorten", "widen_sleeves",
                    "denim", "undo", "inspect", "cancel", "retry", "clarify"]


def plan_turn(instruction: str, has_images: bool, has_candidate: bool, user_id: str = "", *, provider_only: str = ""):
    config = LLMConfiguration.from_settings()
    primary = os.getenv("GARMENT_CHAT_PLANNER", config.primary_provider)
    fallback = os.getenv("GARMENT_CHAT_FALLBACK_PLANNER", config.fallback_provider)
    attempts = []
    for name in ((provider_only,) if provider_only else dict.fromkeys((primary, fallback))):
        if name == "offline_rules":
            break
        provider = llm_registry.get_provider(name)
        if not provider or not provider.health_check():
            attempts.append({"provider": name, "status": "unavailable", "error": "BLOCKED_NO_CREDENTIALS"})
            continue
        response = None
        try:
            response = provider.generate([
                LLMMessage(role="system", content=f"Call plan_garment once. Images supplied: {has_images}. "
                           f"Existing candidate: {has_candidate}. Use clarify for unsupported changes, "
                           "ambiguous instructions or multiple edits. Widen and shorten affect the whole garment."),
                LLMMessage(role="user", content=instruction)],
                tools=[ToolDefinition(name="plan_garment", description="Select one supported garment operation",
                                      parameters_schema=GarmentPlan.model_json_schema())],
                max_tokens=100, temperature=0, timeout_seconds=config.timeout_seconds)
            usage = None
            if user_id and response.usage_reported:
                usage = token_tracker.record_usage(user_id, response.provider_used, response.model_used,
                                                   response.prompt_tokens, response.completion_tokens, response.latency_ms)
            if len(response.tool_calls) == 1 and response.tool_calls[0].function_name == "plan_garment":
                plan = GarmentPlan.model_validate(response.tool_calls[0].arguments)
                return plan, {"provider": response.provider_used, "model": response.model_used,
                              "input_tokens": response.prompt_tokens if response.usage_reported else None,
                              "output_tokens": response.completion_tokens if response.usage_reported else None,
                              "latency_ms": response.latency_ms, "previous_attempts": attempts,
                              "purpose": "plan_garment", "arguments": plan.model_dump(),
                              "upstream_request_id": response.upstream_request_id, "upstream_model": response.upstream_model,
                              "estimated_cost_usd": usage.estimated_cost_usd if usage else None}
            attempts.append({"provider": name, "status": "missing_tool_call", "error": "MALFORMED_OUTPUT",
                             "upstream_request_id": response.upstream_request_id, "upstream_model": response.upstream_model})
        except ProviderHTTPError as exc:
            attempts.append({"provider": name, "status": "failed", "http_status": exc.status_code, "error": exc.code,
                             "upstream_request_id": exc.request_id, "upstream_model": exc.upstream_model})
        except Exception as exc:
            attempts.append({"provider": name, "status": "failed", "error_type": type(exc).__name__,
                             "error": exception_failure(exc),
                             "upstream_request_id": getattr(response, "upstream_request_id", None),
                             "upstream_model": getattr(response, "upstream_model", None)})
    if provider_only:
        return None, {"provider": None, "previous_attempts": attempts}
    plan, trace = local_plan(instruction, has_images)
    trace["previous_attempts"] = attempts
    return plan, trace


def local_plan(instruction: str, has_images: bool):
    text = instruction.lower()
    rules = [
        (r"\b(don't|do not|never|without)\b", "clarify"),
        (r"\bcancel\b", "cancel"),
        (r"\bretry\b", "retry"),
        (r"\b(undo|revert)\b", "undo"),
        (r"\b(create|build|generate|reconstruct|make)\b.*\b(3d|model)\b", "reconstruct"),
        (r"\b(?:change|switch|apply|use|make|turn)\b.*\bdenim\b", "denim"),
        (r"\bsleeves?\b.*\b(wider|looser)\b|\bwiden\b.*\bsleeves?\b", "widen_sleeves"),
        (r"\b(collars?|cuffs?|pockets?|panels?|sleeves?|hems?|hoods?|zippers?)\b", "clarify"),
        (r"\b(wider|oversized|widen)\b", "widen"),
        (r"\b(shorten|shorter)\b", "shorten"),
        (r"\b(export|download|preview|inspect|status|progress|try.on|wireframe|stitching|print placement|show seams?)\b", "inspect"),
        (r"\b(3d|reconstruct|model)\b", "reconstruct"),
    ]
    action = next((action for pattern, action in rules if re.search(pattern, text)),
                  "identify" if has_images else "clarify")
    return GarmentPlan(action=action), {"provider": "local_rules", "previous_attempts": []}


def parse_stylist_design_command(instruction: str):
    """Map supported natural-language design instructions to validated local design patches."""
    text = instruction.lower()
    if re.search(r"\b(don't|do not|never|without)\b", text):
        return None
    if "wireframe" in text:
        enable = "hide" not in text and "off" not in text
        return {"kind": "view_mode", "patch": {"wireframe": enable}, "reply": "Toggled wireframe mode in the interactive 3D viewport."}
    if "stitch" in text or "seam" in text:
        enable = "hide" not in text and "off" not in text
        return {"kind": "material_or_view", "material": {"stitchVisible": enable}, "view": {"showSeams": enable}, "reply": "Enabled stitching & seam overlay in the interactive viewer."}
    if "print placement" in text or "shift print" in text or "move print" in text:
        return {"kind": "material", "material": {"offsetX": 0.15, "offsetY": 0.10, "printScale": 1.15}, "reply": "Updated print placement and repeat offsets on the candidate UV surface."}
    if "dark denim" in text or re.search(r"\bdenim\b", text):
        return {"kind": "material", "material": {"preset": "denim", "baseColor": "#1e3a5f", "roughness": 0.88}, "reply": "Applied dark indigo denim material preset (visual approximation)."}
    if "collar" in text and re.search(r"\bnarrow", text):
        return {"kind": "geometry", "operation": "collar_width", "geometry": {"collarWidthScale": 0.88}, "reply": "Applied bounded collar narrowing (-12%) across synced 2D/3D design state."}
    if "collar" in text and re.search(r"\b(increase|widen|wider|larger)\b", text):
        return {"kind": "geometry", "operation": "collar_width", "geometry": {"collarWidthScale": 1.12}, "reply": "Increased collar width (+12%) via semantic correspondence."}
    if "chest" in text and re.search(r"\b(widen|wider|increase)\b", text):
        return {"kind": "geometry", "operation": "torso_width", "geometry": {"torsoWidthScale": 1.10}, "reply": "Widened chest panel and 3D torso cross-section (+10%)."}
    if "sleeve" in text and re.search(r"\bshorten\b", text):
        return {"kind": "geometry", "operation": "sleeve_length", "geometry": {"sleeveLengthScale": 0.88}, "reply": "Shortened sleeve pattern panels & 3D sleeves (-12%)."}
    if "leg" in text and re.search(r"\b(widen|wider|increase)\b", text):
        return {"kind": "geometry", "operation": "leg_width", "geometry": {"legWidthScale": 1.12}, "reply": "Widened trouser leg panels & 3D leg tubes (+12%)."}
    if "hem" in text and re.search(r"\b(adjust|widen|flare|taper)\b", text):
        scale = 0.90 if "taper" in text or "narrow" in text else 1.10
        return {"kind": "geometry", "operation": "hem_width", "geometry": {"hemWidthScale": scale}, "reply": "Adjusted hem width across body & waistband correspondence."}
    if "pocket" in text and re.search(r"\b(move|shift|adjust)\b", text):
        offset = -0.025 if "down" in text or "lower" in text else 0.025
        return {"kind": "geometry", "operation": "pocket_placement", "geometry": {"pocketOffsetYM": offset}, "reply": "Moved pocket placement within verified torso pattern bounds."}
    if "chest pocket" in text and re.search(r"\badd\b", text):
        return {"kind": "rebuild_or_component", "component": "chest_pocket", "reply": "Adding a structural chest pocket requires pattern & mesh rebuild while preserving the current preview."}
    return None
