"""Evidence-backed garment structure graph and Phase 16.2/16.3 handoff decisions."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from backend.app.services.ai.contracts import (
    ComponentHandoffContract,
    ComponentHandoffDecisionItem,
    FusedComponentAssessment,
    GarmentStructureGraphContract,
    StructureGraphEdge,
    StructureGraphNode,
)
from backend.app.services.intelligence.component_taxonomy import (
    TAXONOMY_VERSION,
    ComponentEvidenceStatus,
    DetectionState,
    ReconstructionDecision,
    VisibilityState,
    resolve_category_profile,
)


def _bbox_overlaps(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ay0, ax0, ay1, ax1 = a
    by0, bx0, by1, bx1 = b
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    inter = iy * ix
    if inter <= 0.0:
        return False
    area_a = max(1e-6, (ay1 - ay0) * (ax1 - ax0))
    area_b = max(1e-6, (by1 - by0) * (bx1 - bx0))
    return (inter / min(area_a, area_b)) > 0.05


def _edge_status(a: FusedComponentAssessment, b: FusedComponentAssessment) -> Tuple[ComponentEvidenceStatus, Optional[float], float, bool]:
    if a.contradicted or b.contradicted:
        return ComponentEvidenceStatus.CONTRADICTED, None, 1.0, True
    if a.evidence_status == ComponentEvidenceStatus.OBSERVED and b.evidence_status == ComponentEvidenceStatus.OBSERVED:
        conf_a = a.confidence if a.confidence is not None else 0.0
        conf_b = b.confidence if b.confidence is not None else 0.0
        unc = round(max(a.uncertainty.total_uncertainty, b.uncertainty.total_uncertainty), 4)
        return ComponentEvidenceStatus.OBSERVED, round(min(conf_a, conf_b), 4), unc, False
    if a.evidence_status == ComponentEvidenceStatus.NOT_OBSERVED or b.evidence_status == ComponentEvidenceStatus.NOT_OBSERVED:
        return ComponentEvidenceStatus.NOT_OBSERVED, None, 1.0, False
    return ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE, None, max(a.uncertainty.total_uncertainty, b.uncertainty.total_uncertainty), False


def build_garment_structure_graph(
    garment_id: str,
    category: str,
    subcategory: str,
    fused_components: Dict[str, FusedComponentAssessment],
) -> GarmentStructureGraphContract:
    """Build an evidence-preserving component graph without inventing unobserved structure."""
    nodes: List[StructureGraphNode] = []
    edges: List[StructureGraphEdge] = []
    contradictions: List[str] = []

    for cid, comp in sorted(fused_components.items()):
        nodes.append(StructureGraphNode(
            node_id=cid,
            component_id=cid,
            component_type=comp.component_type,
            side_or_orientation=comp.side_or_orientation,
            visibility_state=comp.best_visibility,
            detection_state=comp.detection_state,
            evidence_status=comp.evidence_status,
            confidence=comp.confidence,
            uncertainty=comp.uncertainty.total_uncertainty,
            contradicted=comp.contradicted,
            downstream_decision=comp.downstream_decision,
            source_image_ids=list(comp.source_image_ids),
            source_views=list(comp.source_views),
            observation_ids=list(comp.observation_ids),
        ))
        if comp.contradicted:
            contradictions.extend(comp.contradiction_notes or [f"Contradictory observations on component '{cid}'."])
        for img_id in comp.source_image_ids:
            edges.append(StructureGraphEdge(
                edge_id=f"view:{cid}->{img_id}",
                source_node=cid,
                target_node=img_id,
                relation="SUPPORTED_BY_VIEW",
                evidence_status=comp.evidence_status,
                confidence=comp.confidence,
                uncertainty=comp.uncertainty.total_uncertainty,
                source_image_ids=[img_id],
                contradicted=comp.contradicted,
            ))

    edge_idx = 0

    def add_rel(src: str, dst: str, rel: str, notes: str = "") -> None:
        nonlocal edge_idx
        if src not in fused_components or dst not in fused_components:
            return
        a, b = fused_components[src], fused_components[dst]
        # Do not invent structural edges between unseen/not-detected parts.
        if a.detection_state == DetectionState.ABSENT_VERIFIED or b.detection_state == DetectionState.ABSENT_VERIFIED:
            return
        status, conf, unc, contradicted = _edge_status(a, b)
        sources = sorted(set(a.source_image_ids) | set(b.source_image_ids))
        edge_idx += 1
        edges.append(StructureGraphEdge(
            edge_id=f"rel_{edge_idx:03d}_{rel.lower()}",
            source_node=src,
            target_node=dst,
            relation=rel,
            evidence_status=status,
            confidence=conf,
            uncertainty=round(unc, 4),
            source_image_ids=sources,
            contradicted=contradicted,
            notes=notes,
        ))

    # 1. Parent / attachment relations from grounded components
    for cid, comp in sorted(fused_components.items()):
        parent = comp.parent_component
        if parent and parent in fused_components:
            rel = "PART_OF" if parent in {"body", "collar", "hood", "skirt", "bodice", "front_body", "lower_waistband"} else "ATTACHED_TO"
            add_rel(cid, parent, rel, f"{cid} {rel.lower()} {parent}")

    # 2. Category-aware adjacency & attachment pairs (only when both endpoints have evidence records)
    structural_pairs = (
        ("left_sleeve", "front_body", "ATTACHED_TO"),
        ("right_sleeve", "front_body", "ATTACHED_TO"),
        ("cuff", "left_sleeve", "ATTACHED_TO"),
        ("cuff", "right_sleeve", "ATTACHED_TO"),
        ("hood", "neck_opening", "ATTACHED_TO"),
        ("collar", "neck_opening", "ATTACHED_TO"),
        ("collar", "button_placket", "ADJACENT_TO"),
        ("shoulder_seam", "front_body", "CONNECTED_TO"),
        ("shoulder_seam", "back_body", "CONNECTED_TO"),
        ("side_seam", "front_body", "CONNECTED_TO"),
        ("side_seam", "back_body", "CONNECTED_TO"),
        ("lower_waistband", "fly", "ADJACENT_TO"),
        ("left_leg", "lower_waistband", "ATTACHED_TO"),
        ("right_leg", "lower_waistband", "ATTACHED_TO"),
        ("crotch_seam", "left_leg", "CONNECTED_TO"),
        ("crotch_seam", "right_leg", "CONNECTED_TO"),
        ("bodice", "waistline", "CONNECTED_TO"),
        ("waistline", "skirt", "CONNECTED_TO"),
    )
    for src, dst, rel in structural_pairs:
        add_rel(src, dst, rel)

    # 3. Bilateral symmetry pairs
    for left_k, right_k in (
        ("left_sleeve", "right_sleeve"),
        ("left_leg", "right_leg"),
        ("left_body_panel", "right_body_panel"),
    ):
        if left_k in fused_components and right_k in fused_components:
            add_rel(left_k, right_k, "SYMMETRIC_WITH", f"Bilateral pair {left_k} / {right_k}")

    # 4. Spatial overlaps verified from localized bounding boxes in shared source views
    ids = sorted(fused_components)
    for i, a_id in enumerate(ids):
        a = fused_components[a_id]
        if a.localized_bbox is None or a.evidence_status != ComponentEvidenceStatus.OBSERVED:
            continue
        for b_id in ids[i + 1:]:
            b = fused_components[b_id]
            if b.localized_bbox is None or b.evidence_status != ComponentEvidenceStatus.OBSERVED:
                continue
            shared_views = set(a.source_image_ids) & set(b.source_image_ids)
            if shared_views and _bbox_overlaps(a.localized_bbox, b.localized_bbox):
                add_rel(a_id, b_id, "OVERLAPS", f"Spatial overlap in {', '.join(sorted(shared_views))}")

    return GarmentStructureGraphContract(
        taxonomy_version=TAXONOMY_VERSION,
        garment_id=garment_id,
        category=category,
        subcategory=subcategory,
        nodes=nodes,
        edges=edges,
        contradictions=sorted(set(contradictions)),
    )


def decide_downstream_action(comp: FusedComponentAssessment) -> Tuple[ReconstructionDecision, str]:
    """Map fused evidence, visibility, uncertainty, and contradictions into reconstruction gate."""
    if comp.contradicted or comp.evidence_status == ComponentEvidenceStatus.CONTRADICTED:
        return ReconstructionDecision.REQUIRE_MORE_EVIDENCE, "Contradictory observations across views; clarify before reconstruction."
    if comp.detection_state == DetectionState.ABSENT_VERIFIED and comp.evidence_status == ComponentEvidenceStatus.OBSERVED:
        return ReconstructionDecision.SAFE_TO_USE, "Verified absent under unobstructed full-view visibility."
    if comp.evidence_status in (ComponentEvidenceStatus.NOT_OBSERVED, ComponentEvidenceStatus.UNVERIFIED):
        return ReconstructionDecision.DO_NOT_INFER, "Component was not observed in available views; do not fabricate."
    if comp.evidence_status == ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE:
        if comp.best_visibility in (VisibilityState.OCCLUDED, VisibilityState.OUT_OF_FRAME, VisibilityState.LOW_IMAGE_QUALITY):
            return ReconstructionDecision.REQUIRE_MORE_EVIDENCE, f"Visibility is {comp.best_visibility.value}; capture a clearer unobstructed view."
        return ReconstructionDecision.DO_NOT_INFER, "Insufficient visual evidence for safe downstream reconstruction."
    conf = comp.calibrated_probability if comp.calibrated_probability is not None else (comp.confidence or 0.0)
    unc = comp.uncertainty.total_uncertainty
    if comp.best_visibility == VisibilityState.FULLY_VISIBLE and conf >= 0.72 and unc <= 0.35:
        return ReconstructionDecision.SAFE_TO_USE, "Observed clearly with low uncertainty."
    if conf >= 0.50 and unc <= 0.65:
        return ReconstructionDecision.USE_WITH_UNCERTAINTY, f"Usable with uncertainty ({comp.best_visibility.value}, uncertainty={unc:.2f})."
    return ReconstructionDecision.REQUIRE_MORE_EVIDENCE, "Low calibrated confidence or elevated uncertainty."


def build_component_handoff_contract(
    garment_id: str,
    category: str,
    subcategory: str,
    fused_components: Dict[str, FusedComponentAssessment],
    has_back_view: bool,
) -> ComponentHandoffContract:
    """Create the Phase 16.2/16.3 handoff contract plus natural Stylist clarification prompts."""
    items: Dict[str, ComponentHandoffDecisionItem] = {}
    safe, uncertain, more_evidence, blocked = [], [], [], []
    prompts: List[str] = []

    for cid, comp in sorted(fused_components.items()):
        decision = comp.downstream_decision
        items[cid] = ComponentHandoffDecisionItem(
            component_id=cid,
            component_type=comp.component_type,
            decision=decision,
            evidence_status=comp.evidence_status,
            visibility_state=comp.best_visibility,
            detection_state=comp.detection_state,
            confidence=comp.confidence,
            uncertainty=comp.uncertainty.total_uncertainty,
            evidence_completeness=comp.evidence_completeness,
            source_image_ids=list(comp.source_image_ids),
            bbox=comp.localized_bbox,
            notes=comp.decision_rationale,
        )
        if decision == ReconstructionDecision.SAFE_TO_USE:
            safe.append(cid)
        elif decision == ReconstructionDecision.USE_WITH_UNCERTAINTY:
            uncertain.append(cid)
        elif decision == ReconstructionDecision.REQUIRE_MORE_EVIDENCE:
            more_evidence.append(cid)
        else:
            blocked.append(cid)

    profile = resolve_category_profile(category, subcategory)
    if not has_back_view:
        prompts.append("The back of the garment is not shown yet—add a rear photo if you want back details included accurately.")

    contradicted_names = [cid.replace("_", " ") for cid, c in fused_components.items() if c.contradicted]
    if contradicted_names:
        prompts.append(f"The photos appear to disagree about the {', '.join(sorted(contradicted_names)[:3])}. Please share a clearer close-up.")

    low_quality = [
        cid.replace("_", " ")
        for cid, c in fused_components.items()
        if cid in profile.required_components and c.best_visibility == VisibilityState.LOW_IMAGE_QUALITY
    ]
    if low_quality:
        prompts.append(f"The {', '.join(sorted(low_quality)[:3])} is a bit blurry or dark to inspect clearly.")

    occluded_or_cropped = [
        cid.replace("_", " ")
        for cid, c in fused_components.items()
        if cid in profile.expected_components and c.best_visibility in (VisibilityState.OCCLUDED, VisibilityState.OUT_OF_FRAME)
    ]
    if occluded_or_cropped:
        prompts.append(f"Part of the {', '.join(sorted(occluded_or_cropped)[:3])} is covered or cropped out of frame.")

    # Closure ambiguity check for jackets/shirts/hoodies
    closure_cids = [cid for cid in ("zipper", "button_placket", "button") if cid in fused_components]
    if closure_cids and all(fused_components[cid].detection_state == DetectionState.UNCERTAIN for cid in closure_cids):
        prompts.append("The front closure style (such as zipper versus buttons) isn't clear from this angle—a closer front photo would help.")

    return ComponentHandoffContract(
        garment_id=garment_id,
        category=category,
        subcategory=subcategory,
        components=items,
        safe_components=safe,
        uncertain_components=uncertain,
        more_evidence_components=more_evidence,
        blocked_components=blocked,
        clarification_prompts=prompts,
    )
