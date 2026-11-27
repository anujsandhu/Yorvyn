"""
YORVYN — Multi-View Garment Evidence Fusion Engine (Phase 14.27)
Fuses visual observations across multiple garment photographs (Front, Back, Side, Detail, Label):
- Strictly distinguishes OBSERVED vs INFERRED vs UNKNOWN vs CONFLICTED evidence
- Preserves fine-grained image-level provenance (source_image_ids on every property)
- Cross-view conflict detection and evidence ranking
- Evaluates 3D reconstruction readiness (READY, PARTIAL, INSUFFICIENT_EVIDENCE, CONFLICTED)
- Guarantees zero fabrication of unseen posterior or internal construction details
"""

from __future__ import annotations

import io
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

from backend.app.services.ai.base import (
    EvidenceStatus,
    ModelMetadata,
    TokenUsage
)
from backend.app.services.ai.contracts import (
    GarmentItemEvidence,
    ComponentDetail,
    AppearanceDetail,
    ImageQualityAssessment,
    GeometricEstimate,
    HandoffToReconstruction,
    CanonicalGarmentSpecification,
    CanonicalGarmentSpecificationV2,
    PropertyEvidence,
    MultiViewComponentDetail,
    ImageEvidenceRecord,
    ConflictingObservation,
    ReconstructionReadiness
)
from backend.app.services.ai.multiview.view_classifier import (
    view_classifier,
    GarmentViewType,
    ViewClassifier
)
from backend.app.services.ai.orchestration.orchestrator import ai_orchestrator

logger = logging.getLogger(__name__)


class MultiViewGarmentFusionEngine:
    """
    Orchestrates multi-view garment identification, viewpoint disambiguation,
    conflict detection, and cross-angle evidence fusion.
    """

    def __init__(self):
        self.classifier = view_classifier

    def fuse_garment_views(
        self,
        images_input: List[Tuple[str, bytes, Optional[str]]],
        garment_id: Optional[str] = None,
        mock_mode: bool = False
    ) -> CanonicalGarmentSpecificationV2:
        """
        Fuses a list of uploaded images into a CanonicalGarmentSpecificationV2.
        Each item in images_input is: (image_id, image_bytes, optional_user_view_hint).
        """
        t_start = time.perf_counter()
        gid = garment_id or f"garment_{uuid.uuid4().hex[:8]}"

        if not images_input:
            raise ValueError("MultiViewGarmentFusionEngine requires at least one image input.")

        # ---------------------------------------------------------------------
        # 1. Image Deduplication, Hashing & Viewpoint Classification
        # ---------------------------------------------------------------------
        seen_hashes: Dict[str, str] = {}  # exact hash -> first image id
        seen_perceptual_hashes: List[Tuple[str, str]] = []  # perceptual hash, first image id
        seen_pil_images: List[Tuple[str, Image.Image]] = []
        view_records: List[ImageEvidenceRecord] = []
        unique_images: List[Tuple[str, bytes, GarmentViewType, Dict[str, Any]]] = []
        component_images_input: List[Tuple[str, bytes, Optional[str]]] = []
        conflicts: List[ConflictingObservation] = []

        for idx, (img_id, img_bytes, user_hint) in enumerate(images_input):
            actual_id = img_id or f"view_{idx+1:02d}_{uuid.uuid4().hex[:6]}"
            # A filename is only a display hint; it is not a unique evidence identifier.
            if any(record.image_id == actual_id for record in view_records):
                base_id = actual_id
                suffix = 2
                while any(record.image_id == f"{base_id}#{suffix}" for record in view_records):
                    suffix += 1
                actual_id = f"{base_id}#{suffix}"
            h = ViewClassifier.compute_image_hash(img_bytes)
            try:
                with Image.open(io.BytesIO(img_bytes)) as image:
                    phash = self.classifier.compute_perceptual_hash(image)
            except Exception:
                phash = None
            near_match = next((
                prior_id for prior_hash, prior_id in seen_perceptual_hashes
                if phash is not None and bin(int(phash, 16) ^ int(prior_hash, 16)).count("1") <= 2
            ), None)
            duplicate_of = seen_hashes.get(h) or near_match

            if duplicate_of:
                duplicate_type = "exact_bytes" if h in seen_hashes else "perceptual_near_duplicate"
                logger.info(f"Duplicate image detected: {actual_id} matches {duplicate_of} ({duplicate_type})")
                # Record as duplicate view record without re-running heavy models
                view_records.append(ImageEvidenceRecord(
                    image_id=actual_id,
                    image_hash=h,
                    perceptual_hash=phash,
                    duplicate_of_image_id=duplicate_of,
                    duplicate_type=duplicate_type,
                    counts_as_independent_view=False,
                    view_type=GarmentViewType.UNKNOWN.value,
                    view_confidence=1.0,
                    quality_score=0.9,
                    usable=False,
                    detected_features=["Duplicate upload of " + duplicate_of],
                    associated_garment_id=gid
                ))
                continue

            seen_hashes[h] = actual_id

            try:
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            except Exception as e:
                logger.warning(f"Failed to decode image {actual_id}: {e}")
                view_records.append(ImageEvidenceRecord(
                    image_id=actual_id,
                    image_hash=h,
                    view_type=GarmentViewType.UNKNOWN.value,
                    view_confidence=0.0,
                    quality_score=0.0,
                    usable=False,
                    detected_features=[f"Corrupted or invalid image format: {str(e)}"],
                    associated_garment_id=gid
                ))
                continue

            # Check if this image is a repeated crop of a previously submitted photo
            crop_of_id = None
            for ref_id, ref_pil in seen_pil_images:
                if self.classifier.detect_subcrop_similarity(pil_img, ref_pil) is not None:
                    crop_of_id = ref_id
                    break

            # Classify viewpoint
            v_type, v_conf, v_reasons = self.classifier.classify_view(pil_img, user_hint)
            q_info = self.classifier.evaluate_quality(pil_img)
            if crop_of_id:
                v_reasons.append(f"Repeated spatial crop of '{crop_of_id}'; not counted as an independent camera view.")

            record = ImageEvidenceRecord(
                image_id=actual_id,
                image_hash=h,
                perceptual_hash=phash,
                duplicate_type="crop_of_existing_view" if crop_of_id else None,
                crop_of_image_id=crop_of_id,
                counts_as_independent_view=not bool(crop_of_id),
                view_type=v_type.value,
                view_assignment_source="provided_hint" if user_hint else "heuristic",
                user_view_hint=user_hint,
                view_confidence=v_conf,
                quality_score=q_info["quality_score"],
                resolution=q_info["resolution"],
                usable=q_info["image_usable"],
                detected_features=v_reasons,
                associated_garment_id=gid
            )
            view_records.append(record)
            if phash is not None:
                seen_perceptual_hashes.append((phash, actual_id))
            if not crop_of_id:
                seen_pil_images.append((actual_id, pil_img))

            if q_info["image_usable"]:
                component_images_input.append((actual_id, img_bytes, v_type.value))
                if not crop_of_id:
                    unique_images.append((actual_id, img_bytes, v_type, q_info))

        def insufficient(reason):
            readiness = ReconstructionReadiness(
                status="INSUFFICIENT_EVIDENCE",
                missing_evidence=[reason],
                recommended_additional_views=["front", "back"]
            )
            return CanonicalGarmentSpecificationV2(
                garment_id=gid,
                garment=GarmentItemEvidence(
                    category="unknown",
                    subcategory="unknown",
                    confidence=0.0,
                    evidence_status=EvidenceStatus.UNKNOWN,
                    direct_evidence_text=reason
                ),
                views=view_records,
                conflicts=[],
                reconstruction_readiness=readiness,
                v2_components={},
                property_evidence={},
                natural_language_explanation=reason
            )

        if not unique_images:
            return insufficient("No usable photograph. Please add a clear front view.")

        # ---------------------------------------------------------------------
        # 2. Perception & Evidence Extraction per View
        # ---------------------------------------------------------------------
        view_perceptions: Dict[str, Dict[str, Any]] = {}
        primary_view_id: Optional[str] = None
        has_front = False
        has_back = False

        from backend.app.services.intelligence.local_perception import EvidenceRequired
        uncertain_views = 0
        for (img_id, img_bytes, v_type, q_info) in unique_images:
            try:
                # Execute hybrid perception
                spec = ai_orchestrator.process_garment_image(
                    image_bytes=img_bytes,
                    garment_id=f"{gid}_{img_id}",
                    mock_mode=mock_mode
                )
                if v_type == GarmentViewType.FRONT and not has_front:
                    primary_view_id = img_id
                    has_front = True
                elif v_type == GarmentViewType.BACK:
                    has_back = True
                view_perceptions[img_id] = {
                    "view_type": v_type,
                    "spec": spec,
                    "quality": q_info
                }
            except Exception as e:
                if isinstance(e, EvidenceRequired):
                    uncertain_views += 1
                record = next(view for view in view_records if view.image_id == img_id)
                record.usable = False
                record.detected_features.append("Visual analysis failed for this view.")
                logger.warning(f"Perception failed for image {img_id}: {e}")

        if not view_perceptions and uncertain_views == len(unique_images):
            return insufficient("Local evidence is inconclusive. Please add another clear view of the selected garment.")
        if not view_perceptions:
            raise RuntimeError("Perception extraction failed across all valid images.")

        # Fallback primary view if front wasn't classified
        if not primary_view_id:
            primary_view_id = next(iter(view_perceptions))

        primary_spec: CanonicalGarmentSpecification = view_perceptions[primary_view_id]["spec"]

        # ---------------------------------------------------------------------
        # 3. Cross-View Category Concordance & Conflict Detection
        # ---------------------------------------------------------------------
        category_votes: Dict[str, List[Tuple[str, float]]] = {}
        for img_id, p_info in view_perceptions.items():
            cat = p_info["spec"].garment.category
            conf = p_info["spec"].garment.confidence
            category_votes.setdefault(cat, []).append((img_id, conf))

        # Check for category conflicts
        fused_category = primary_spec.garment.category
        fused_subcategory = primary_spec.garment.subcategory
        category_status = primary_spec.garment.evidence_status
        cat_conf = primary_spec.garment.confidence
        category_source_images = [primary_view_id]

        if len(category_votes) > 1:
            # Conflict detected across views
            conflict_entry = ConflictingObservation(
                attribute_name="category",
                conflicting_views=[view_perceptions[iid]["view_type"].value for iid, _ in sum(category_votes.values(), [])],
                competing_values=[
                    {"category": c, "voters": voters} for c, voters in category_votes.items()
                ],
                resolution_status="UNRESOLVED_CONFLICT",
                resolution_rationale="Conflicting garment categories observed in different viewpoints."
            )
            # Check if one category dominates or front landmark takes precedence for related families
            sorted_cats = sorted(category_votes.items(), key=lambda item: sum(v[1] for v in item[1]), reverse=True)
            top_cat, top_voters = sorted_cats[0]
            runner_up_cat, runner_voters = sorted_cats[1]
            top_score = sum(v[1] for v in top_voters)
            runner_score = sum(v[1] for v in runner_voters)

            is_front_lead = any(view_perceptions[v[0]]["view_type"] == GarmentViewType.FRONT for v in top_voters)
            is_related_family = (
                (top_cat in ["hoodie", "sweatshirt"] and runner_up_cat in ["hoodie", "sweatshirt"]) or
                (top_cat in ["jacket", "coat"] and runner_up_cat in ["jacket", "coat"]) or
                (top_cat in ["jeans", "trousers"] and runner_up_cat in ["jeans", "trousers"]) or
                (top_cat in ["shirt", "tshirt"] and runner_up_cat in ["shirt", "tshirt"])
            )

            if top_score > runner_score * 1.15 or (is_front_lead and (top_score >= runner_score or is_related_family)):
                conflict_entry.resolution_status = "RESOLVED"
                conflict_entry.winning_value = top_cat
                conflict_entry.resolution_rationale = (
                    f"Resolved via multi-view evidence ranking: {top_cat} (score {top_score:.2f}) "
                    f"takes precedence over {runner_up_cat} (score {runner_score:.2f}) due to primary front landmark observation."
                )
                fused_category = top_cat
                category_source_images = [v[0] for v in top_voters]
            else:
                category_status = EvidenceStatus.CONFLICTED

            conflicts.append(conflict_entry)

        # ---------------------------------------------------------------------
        # 4. Multi-View Component Fusion & Association
        # ---------------------------------------------------------------------
        v2_components: Dict[str, MultiViewComponentDetail] = {}
        property_evidence: Dict[str, PropertyEvidence] = {}

        def provider_for_image(image_id: str) -> str:
            provider_chain = view_perceptions[image_id]["spec"].provenance_chain
            return provider_chain[0].provider_name if provider_chain else "unknown_provider"

        # Category property evidence
        category_providers = {provider_for_image(image_id) for image_id in category_source_images}
        property_evidence["category"] = PropertyEvidence(
            value=fused_category,
            status=category_status,
            confidence=cat_conf if category_status != EvidenceStatus.UNKNOWN else None,
            source_image_ids=category_source_images,
            source_provider=next(iter(category_providers)) if len(category_providers) == 1 else "multi_provider_fusion",
            evidence_type="conflict_resolution" if category_status == EvidenceStatus.CONFLICTED else "provider_prediction",
            validation_status="validated" if category_status != EvidenceStatus.CONFLICTED else "conflicted",
            justification=(
                "Garment category is a provider prediction from the cited image(s)."
                if category_status == EvidenceStatus.INFERRED else
                "Category conflict is retained across the cited viewpoints."
                if category_status == EvidenceStatus.CONFLICTED else ""
            )
        )

        # Fuse components
        known_components = set()
        for p_info in view_perceptions.values():
            known_components.update(p_info["spec"].components.keys())

        # Ensure rear construction details are tracked when back view is absent
        if not has_back:
            known_components.add("back_yoke")

        for c_name in known_components:
            # Gather observations across views
            presence_votes: List[Tuple[str, str, bool, float, EvidenceStatus, str]] = []  # image, view, present, confidence, evidence status, provider
            type_observations: List[Tuple[str, str]] = []  # (img_id, type)
            bboxes: List[Tuple[float, float, float, float]] = []
            source_views: List[str] = []

            for img_id, p_info in view_perceptions.items():
                v_type = p_info["view_type"].value
                comp = p_info["spec"].components.get(c_name)
                if comp:
                    presence_votes.append((img_id, v_type, comp.present, comp.confidence, comp.evidence_status, provider_for_image(img_id)))
                    type_observations.append((img_id, comp.component_type))
                    if comp.bbox:
                        bboxes.append(comp.bbox)
                    source_views.append(v_type)

            # Resolve presence
            # A feature visible in Front is NOT necessarily expected in Rear (e.g. kangaroo pocket)
            # But if a feature is seen in any canonical view, mark OBSERVED
            any_present = any(v[2] for v in presence_votes)
            pos_voters = [v[0] for v in presence_votes if v[2]]
            component_sources = pos_voters if any_present else [v[0] for v in presence_votes]
            component_providers = {v[5] for v in presence_votes if v[0] in component_sources}
            component_provider = next(iter(component_providers)) if len(component_providers) == 1 else "multi_provider_fusion"

            if any_present:
                c_status = (
                    EvidenceStatus.OBSERVED
                    if any(v[4] == EvidenceStatus.OBSERVED for v in presence_votes if v[2])
                    else EvidenceStatus.INFERRED
                )
                c_conf = max(v[3] for v in presence_votes if v[2])
                c_srcs = pos_voters
                c_type = type_observations[0][1] if type_observations else "standard"
            else:
                c_status = (
                    EvidenceStatus.OBSERVED
                    if presence_votes and all(v[4] == EvidenceStatus.OBSERVED for v in presence_votes)
                    else EvidenceStatus.INFERRED
                )
                c_conf = 0.90
                c_srcs = [v[0] for v in presence_votes]
                c_type = "none"

            # Check if this component is rear-specific (e.g. back_yoke_seam, rear_pocket)
            if c_name in ["back_yoke", "rear_pocket", "back_panel_seam"] and not has_back:
                # Rear details are completely unobserved when Back view is absent
                c_status = EvidenceStatus.UNKNOWN
                c_conf = None
                c_srcs = []
                c_type = "unknown"

            v2_components[c_name] = MultiViewComponentDetail(
                name=c_name,
                presence=PropertyEvidence(
                    value=any_present,
                    status=c_status,
                    confidence=c_conf,
                    source_image_ids=c_srcs,
                    source_provider=component_provider,
                    evidence_type="direct_visual_detection" if c_status == EvidenceStatus.OBSERVED else "heuristic_prior",
                    justification=(
                        "Component presence is estimated by the local perception adapter."
                        if c_status == EvidenceStatus.INFERRED else ""
                    )
                ),
                component_type=PropertyEvidence(
                    value=c_type,
                    status=c_status,
                    confidence=c_conf,
                    source_image_ids=c_srcs,
                    source_provider=component_provider,
                    evidence_type="heuristic_prior" if c_status == EvidenceStatus.INFERRED else "direct_visual_detection",
                    justification=(
                        "Component type is estimated by the local perception adapter."
                        if c_status == EvidenceStatus.INFERRED else ""
                    )
                ),
                bbox=bboxes[0] if bboxes else None,
                source_views=list(set(source_views)),
                notes=f"Fused across {len(presence_votes)} viewpoint observations."
            )
            property_evidence[c_name] = v2_components[c_name].presence

        # ---------------------------------------------------------------------
        # 4b. Deep Component Evidence & Structure Graph (Phase 16.1)
        # ---------------------------------------------------------------------
        from backend.app.services.intelligence.component_evidence import analyze_garment_components
        comp_bundle = None
        if component_images_input:
            try:
                comp_bundle = analyze_garment_components(
                    images_input=component_images_input,
                    garment_id=gid,
                    category=fused_category,
                    subcategory=fused_subcategory,
                    view_records=view_records,
                )
            except Exception as comp_exc:
                logger.warning(f"Phase 16.1 component evidence extraction degraded: {comp_exc}")

        if comp_bundle is not None:
            for fc_id, fc in comp_bundle.fused_components.items():
                if fc.contradicted:
                    conflicts.append(ConflictingObservation(
                        attribute_name=f"component:{fc_id}",
                        conflicting_views=list(fc.source_views),
                        competing_values=[
                            {
                                "observation_id": o.observation_id,
                                "view": o.source_view,
                                "detection_state": o.detection_state.value,
                                "confidence": o.confidence,
                            }
                            for o in fc.observations
                        ],
                        resolution_status="UNRESOLVED_CONFLICT",
                        resolution_rationale="; ".join(fc.contradiction_notes) or "Conflicting component observations.",
                    ))

        # ---------------------------------------------------------------------
        # 5. Reconstruction Readiness Assessment
        # ---------------------------------------------------------------------
        missing_evidence = []
        recommended_views = []
        observed_geom = [f"front_silhouette_{primary_view_id}"] if has_front else []
        inferred_geom = []
        unknown_geom = []

        if not has_back:
            missing_evidence.append("Rear viewpoint photograph missing.")
            recommended_views.append("back")
            unknown_geom.append("Posterior back panel construction, rear yoke, and center back drape.")
            inferred_geom.append("Bilateral symmetry drape prior applied to rear mesh.")
        else:
            observed_geom.append("Direct rear contour and back panel photographic observation.")

        if category_status == EvidenceStatus.CONFLICTED:
            readiness_status = "CONFLICTED"
            missing_evidence.append("Unresolved garment category conflict between viewpoints.")
        elif not has_front:
            readiness_status = "PARTIAL"
            missing_evidence.append("Front viewpoint missing or ambiguous.")
            recommended_views.append("front")
        elif not has_back:
            readiness_status = "PARTIAL"
        else:
            readiness_status = "READY"

        readiness = ReconstructionReadiness(
            status=readiness_status,
            missing_evidence=missing_evidence,
            observed_geometry=observed_geom,
            inferred_geometry=inferred_geom,
            unknown_geometry=unknown_geom,
            recommended_additional_views=recommended_views
        )

        # ---------------------------------------------------------------------
        # 6. Natural Language Summary with Forensic Evidence Details
        # ---------------------------------------------------------------------
        view_summary = ", ".join([f"{v.view_type} ({v.image_id})" for v in view_records if v.usable])
        explanation = (
            f"Multi-View Analysis ({readiness_status}): Analyzed {len(view_perceptions)} of {len(view_records)} submitted views [{view_summary}]. "
            f"Identified garment as {fused_category} ({fused_subcategory}) with {cat_conf * 100:.1f}% confidence. "
        )
        if not has_back:
            explanation += "Rear viewpoint was not provided; posterior geometry will be inferred via bilateral symmetry. "
        if conflicts:
            explanation += f"Encountered {len(conflicts)} visual conflicts ({[c.attribute_name for c in conflicts]})."

        total_latency = (time.perf_counter() - t_start) * 1000.0

        # Build CanonicalGarmentSpecificationV2
        v2_spec = CanonicalGarmentSpecificationV2(
            garment_id=gid,
            garment=GarmentItemEvidence(
                category=fused_category,
                subcategory=fused_subcategory,
                confidence=cat_conf,
                evidence_status=category_status,
                direct_evidence_text=f"Provider prediction: {fused_subcategory} from {len(category_source_images)} cited view(s)."
            ),
            components=primary_spec.components,
            appearance=primary_spec.appearance,
            orientation="multi_view" if len(unique_images) > 1 else primary_spec.orientation,
            orientation_status=EvidenceStatus.OBSERVED,
            quality=primary_spec.quality,
            geometry=primary_spec.geometry,
            reconstruction_handoff=primary_spec.reconstruction_handoff,
            provenance_chain=primary_spec.provenance_chain,
            model_execution_provenance={
                image_id: p_info["spec"].model_execution_provenance
                for image_id, p_info in view_perceptions.items()
            },
            directly_visible_evidence=observed_geom,
            inferred_properties=inferred_geom,
            unknown_unobservable_properties=unknown_geom,
            natural_language_explanation=explanation,
            total_pipeline_latency_ms=total_latency,
            estimated_cost_usd=0.0,
            views=view_records,
            conflicts=conflicts,
            reconstruction_readiness=readiness,
            v2_components=v2_components,
            property_evidence=property_evidence,
            component_observations=comp_bundle.observations if comp_bundle else [],
            fused_components=comp_bundle.fused_components if comp_bundle else {},
            structure_graph=comp_bundle.structure_graph if comp_bundle else None,
            component_handoff=comp_bundle.handoff if comp_bundle else None,
            clarification_prompts=comp_bundle.handoff.clarification_prompts if comp_bundle else [],
        )

        return v2_spec


# Singleton instance
multi_view_fusion_engine = MultiViewGarmentFusionEngine()
