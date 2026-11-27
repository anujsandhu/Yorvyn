"""Local task interpretation and capability-specific evidence gates."""
import os
import re

from backend.app.services.llm.garment_plan import GarmentPlan, local_plan, plan_turn

LOCAL = "EXECUTE_LOCAL"
ASK = "REQUEST_MORE_EVIDENCE"
REASON = "ESCALATE_FOR_REASONING"


def route_intent(instruction, images, candidate, owner):
    local, trace = local_plan(instruction, images)
    # Explicit staging-only path to independently test credentialed providers.
    acceptance = os.getenv("YORVYN_STAGING_LIVE_RECEIPTS") == "1"
    protected = re.search(r"\b(do not|don't|never|without|collars?|cuffs?|panels?|pockets?|hems?|zippers?)\b", instruction, re.I)
    multi_edit = re.search(r"\b(and|then)\b", instruction, re.I) and local.action in {"widen", "shorten", "widen_sleeves", "denim"}
    if multi_edit or (protected and local.action == "clarify"):
        return GarmentPlan(action="clarify"), dict(trace, decision=ASK, reason="clarify_target_or_single_edit")
    if images and local.action == "identify" and not re.search(
            r"\b(identify|classify|what|which|recognize|describe|analyse|analyze|photo|image|this garment)\b", instruction, re.I):
        local = GarmentPlan(action="clarify")
    if not images and not candidate:
        return GarmentPlan(action="clarify"), dict(trace, decision=ASK, reason="no_garment_evidence")
    if not acceptance and local.action != "clarify":
        return local, dict(trace, decision=LOCAL, reason="supported_local_intent")
    plan, external = plan_turn(instruction, images, candidate, owner)
    if external["provider"] == "local_rules":
        return plan, dict(external, decision=ASK, reason="no_validated_external_plan")
    if (not candidate and plan.action in {"undo", "denim", "widen", "shorten", "widen_sleeves", "cancel", "retry"}
            or plan.action in {"cancel", "retry", "undo"} and local.action != plan.action):
        return GarmentPlan(action="clarify"), dict(external, decision=ASK, reason="operation_precondition")
    return plan, dict(external, decision=REASON, reason="credentialed_probe" if acceptance else "ambiguous_instruction")


def reconstruction_decision(spec):
    usable = [v for v in spec.views if v.usable]
    if (not usable or not any(v.view_type.lower() == "front" for v in usable)
            or spec.reconstruction_readiness.status not in {"READY", "PARTIAL"}
            or spec.validate_evidence_integrity()):
        return ASK, "A clear front view of the same garment is needed before reconstruction."
    if spec.garment.confidence < 0.50:
        return ASK, "The category evidence is weak. Please add another view of the garment."
    if any(view.get("category_routing", {}).get("identity_conflict") for view in spec.model_execution_provenance.values() if isinstance(view, dict)):
        return ASK, "The classifiers disagree about the garment. Please add a clearer front view."
    if spec.garment.category.lower() in {"unknown", "other", ""} or any(
            c.resolution_status == "UNRESOLVED_CONFLICT" for c in spec.conflicts):
        return ASK, "The views disagree. Please confirm the garment with a clear photograph."
    return LOCAL, "usable_front_and_consistent_identity"


def geometry_strategy(category, subcategory):
    if category in {"bottom", "bottoms", "trousers", "dress", "dresses_and_skirts", "skirt", "footwear", "accessories"}:
        return "category_parametric"
    if subcategory in {"formal_trousers", "sneakers", "maxi_dress"}:
        return "category_parametric"
    return "image_conditioned"
