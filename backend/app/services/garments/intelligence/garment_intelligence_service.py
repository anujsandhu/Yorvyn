"""
Master Garment Intelligence Service (V2).
Orchestrates neural/geometric segmentation, hierarchical taxonomy classification,
component and landmark detection, photographic quality calibration, and multi-view reasoning.
Zero fake MD5 seeds; zero hardcoded aspect ratio mocks.
"""

import time
import logging
from dataclasses import asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from PIL import Image

from backend.app.models.garment_intelligence_models import (
    GarmentIntelligenceV2Result,
    GarmentDiagnosticsV2,
    SegmentationMetrics
)
from backend.app.services.garments.segmentation import segmenter_registry, GarmentSegmentationOutput
from .universal_garment_classifier import universal_garment_classifier, find_closest_fashion_color, hex_to_rgb
from .component_detector import component_detector
from .garment_hypothesis_resolver import garment_hypothesis_resolver
from .confidence_engine import confidence_engine
from .multiview_engine import multiview_engine
from .universal_garment_intelligence_model import universal_intelligence_model
from .reliability_engine import reliability_engine

logger = logging.getLogger(__name__)


class GarmentIntelligenceService:
    """Canonical Garment Intelligence Engine v2.0."""

    def analyze(
        self,
        front_image: Image.Image,
        job_id: str = "preview_job",
        category_hint: Optional[str] = None,
        subcategory_hint: Optional[str] = None,
        back_image: Optional[Image.Image] = None,
        segmenter_name: Optional[str] = None
    ) -> Tuple[GarmentIntelligenceV2Result, GarmentDiagnosticsV2, GarmentSegmentationOutput]:
        """
        Executes complete multi-model garment intelligence pipeline.
        Returns:
            Tuple of (GarmentIntelligenceV2Result, GarmentDiagnosticsV2, front_segmentation_output).
        """
        stage_latencies: Dict[str, float] = {}

        # ── Stage 1: Segmentation & Boundary Isolation ────────────────────────
        t0 = time.perf_counter()
        if segmenter_name:
            segmenter = segmenter_registry.get(segmenter_name)
            seg_output = segmenter.segment(front_image)
        else:
            # Intelligent routing: use HumanParsingSegmenter for on-body, lifestyle, or isolated garments
            try:
                from backend.app.services.garments.segmentation import human_parsing_segmenter
                seg_output = human_parsing_segmenter.segment(front_image, category_hint=category_hint)
                # If human parsing found garment pixels, keep it; if empty/fallback required, use default
                w_f, h_f = front_image.size
                if np.sum(seg_output.alpha_mask > 20) < (0.04 * w_f * h_f):
                    default_seg = segmenter_registry.get("opencv_contour")
                    seg_fallback = default_seg.segment(front_image)
                    if np.sum(seg_fallback.alpha_mask > 20) > np.sum(seg_output.alpha_mask > 20):
                        seg_output = seg_fallback
            except Exception as seg_err:
                logger.warning(f"Human parsing fallback to default segmenter: {seg_err}")
                segmenter = segmenter_registry.get("opencv_contour")
                seg_output = segmenter.segment(front_image)

        # Ensure segmentation mask and RGBA crop match front_image dimensions
        w_f, h_f = front_image.size
        if seg_output.alpha_mask.shape[0] != h_f or seg_output.alpha_mask.shape[1] != w_f:
            alpha_pil = Image.fromarray(seg_output.alpha_mask).resize((w_f, h_f), Image.BILINEAR)
            seg_output.alpha_mask = np.array(alpha_pil, dtype=np.uint8)
            rgba_full = front_image.convert("RGBA")
            rgba_full.putalpha(alpha_pil)
            seg_output.segmented_image = rgba_full

        stage_latencies["segmentation_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # ── Stage 2: Hierarchical Classification & Embeddings ──────────────────
        t0 = time.perf_counter()
        cls_result = universal_garment_classifier.classify_hierarchical(
            image=front_image,
            alpha_mask=seg_output.alpha_mask,
            user_category_hint=category_hint,
            user_subcategory_hint=subcategory_hint
        )
        embedding = universal_garment_classifier.extract_semantic_embedding(front_image)
        p_name, p_hex, palette = universal_garment_classifier.extract_dominant_colors(
            seg_output.segmented_image, seg_output.alpha_mask
        )
        stage_latencies["classification_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        pred_category = cls_result["category"]
        pred_subcategory = cls_result["subcategory"]
        attrs = cls_result["attributes"]

        # ── Stage 3: Spatial Component & Landmark Detection ───────────────────
        t0 = time.perf_counter()
        components, landmarks = component_detector.detect(
            image=front_image,
            alpha_mask=seg_output.alpha_mask,
            category=pred_category,
            subcategory=pred_subcategory
        )

        # Multi-task neural perception pass with category-harmonized mapping
        model_cat_hint = "hoodie" if (pred_subcategory in ["hoodie", "zip_hoodie", "pullover_hoodie"] or (subcategory_hint and "hoodie" in subcategory_hint.lower())) else (category_hint or pred_category)
        model_subcat_hint = "pullover_hoodie" if model_cat_hint == "hoodie" and (subcategory_hint is None or subcategory_hint == "hoodie") else (subcategory_hint or pred_subcategory)

        neural_intel = universal_intelligence_model.predict(
            image=front_image,
            alpha_mask=seg_output.alpha_mask,
            category_hint=model_cat_hint,
            subcategory_hint=model_subcat_hint
        )
        if neural_intel.attributes:
            attrs.update(neural_intel.attributes)

        # Merge any specialized detected components from neural head
        existing_comp_types = {c.component_type for c in components}
        for n_comp in neural_intel.components:
            if n_comp.status == "detected" and n_comp.component_type not in existing_comp_types:
                components.append(n_comp)
                existing_comp_types.add(n_comp.component_type)

        stage_latencies["component_detection_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        stage_latencies["neural_intelligence_ms"] = neural_intel.inference_latency_ms

        # ── Stage 3.5: Multi-Factor Garment Hypothesis Arbitration ────────────
        raw_probs = {c.category: c.calibrated_probability for c in cls_result.get("candidate_categories", [])}
        orig_pred_cat = pred_category
        orig_pred_sub = pred_subcategory
        resolved = garment_hypothesis_resolver.resolve(
            image=front_image,
            alpha_mask=seg_output.alpha_mask,
            raw_category_probs=raw_probs,
            initial_subcategory=pred_subcategory,
            detected_components=components,
            landmarks=landmarks,
            user_category_hint=category_hint,
            user_subcategory_hint=subcategory_hint,
            image_type=getattr(seg_output, "image_type", None)
        )

        pred_category = resolved.category
        pred_subcategory = resolved.subcategory
        cls_result["category"] = resolved.category
        cls_result["subcategory"] = resolved.subcategory
        cls_result["display_name"] = resolved.display_name
        cls_result["category_confidence"] = resolved.confidence
        cls_result["requires_confirmation"] = resolved.requires_confirmation
        cls_result["candidate_categories"] = resolved.candidate_hypotheses
        cls_result["uncertainty_status"] = resolved.uncertainty_status
        cls_result["original_prediction"] = resolved.original_prediction
        cls_result["heuristic_adjustments"] = resolved.heuristic_adjustments
        cls_result["reasoning_signals"] = resolved.reasoning_signals
        cls_result["rejected_alternatives"] = resolved.rejected_alternatives

        if resolved.attributes:
            attrs.update(resolved.attributes)

        if resolved.category != orig_pred_cat or resolved.subcategory != orig_pred_sub:
            logger.info(
                f"GarmentHypothesisResolver arbitrated classification: "
                f"({orig_pred_cat}/{orig_pred_sub}) -> ({resolved.category}/{resolved.subcategory})"
            )
            # Re-run component detection for updated category
            components, landmarks = component_detector.detect(
                image=front_image,
                alpha_mask=seg_output.alpha_mask,
                category=pred_category,
                subcategory=pred_subcategory
            )

        # ── Stage 4: Photographic Quality & Confidence Calibration ───────────
        t0 = time.perf_counter()
        seg_metrics = SegmentationMetrics(
            silhouette_quality=seg_output.silhouette_quality,
            boundary_sharpness=seg_output.edge_sharpness,
            compactness=seg_output.compactness,
            hole_count=len(seg_output.holes),
            outer_contour_point_count=len(seg_output.outer_contour),
            processing_time_ms=seg_output.processing_time_ms,
            model_id=seg_output.model_id,
            model_version=seg_output.model_version
        )

        validation = confidence_engine.evaluate(
            image=front_image,
            alpha_mask=seg_output.alpha_mask,
            category=pred_category,
            subcategory=pred_subcategory,
            category_confidence=cls_result["category_confidence"],
            components=components,
            segmentation_metrics=seg_metrics
        )
        stage_latencies["validation_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        if not validation.is_valid:
            error_msg = "; ".join(validation.rejection_reasons)
            remedy_msg = "; ".join(validation.remediation_guidance)
            raise ValueError(f"Input image rejected: {error_msg} Guidance: {remedy_msg}")

        # ── Stage 5: Multi-View Consistency ───────────────────────────────────
        t0 = time.perf_counter()
        views_dict = {
            "front": multiview_engine.analyze_view(front_image, seg_output.alpha_mask, expected_view="front")
        }

        if back_image:
            try:
                from backend.app.services.garments.segmentation import human_parsing_segmenter
                back_seg = human_parsing_segmenter.segment(back_image, category_hint=category_hint)
            except Exception:
                back_seg = segmenter_registry.get("opencv_contour").segment(back_image)
            back_view_res = multiview_engine.analyze_view(
                image=back_image,
                alpha_mask=back_seg.alpha_mask,
                expected_view="back",
                front_embedding=embedding,
                front_primary_hex=p_hex
            )
            views_dict["back"] = back_view_res

            if back_view_res.is_duplicate:
                validation.warnings.append("Back image appears to be a duplicate of the front image.")
            elif back_view_res.identity_match_with_front is False:
                validation.warnings.append("Warning: Back image colors or texture differ from front image. Inspect consistency.")
        stage_latencies["multiview_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # ── Assemble Canonical Intelligence V2 Result ─────────────────────────
        all_warnings = seg_output.warnings + validation.warnings

        sec_hex = palette[1] if len(palette) > 1 and palette[1] != p_hex else None
        s_name, _ = find_closest_fashion_color(
            hex_to_rgb(sec_hex)
        ) if sec_hex else (None, None)

        intelligence_v2 = GarmentIntelligenceV2Result(
            job_id=job_id,
            category=pred_category,
            subcategory=pred_subcategory,
            display_name=cls_result["display_name"],
            category_confidence=cls_result["category_confidence"],
            requires_confirmation=cls_result["requires_confirmation"],
            candidate_categories=cls_result["candidate_categories"],
            uncertainty_status=cls_result.get("uncertainty_status", "CONFIDENT"),
            original_prediction=cls_result.get("original_prediction", {}),
            heuristic_adjustments=cls_result.get("heuristic_adjustments", []),
            reasoning_signals=cls_result.get("reasoning_signals", []),
            rejected_alternatives=cls_result.get("rejected_alternatives", []),
            classification_version="3.0.0-generalized",
            model_prediction=cls_result.get("model_prediction"),
            model_confidence=cls_result.get("model_confidence"),
            model_probabilities=cls_result.get("model_probabilities"),
            rule_hypothesis=cls_result.get("rule_hypothesis"),
            rule_confidence=cls_result.get("rule_confidence"),
            final_prediction=cls_result.get("final_prediction"),
            final_confidence=cls_result.get("final_confidence"),
            decision_reason=cls_result.get("decision_reason"),
            components=components,
            landmarks=landmarks,
            primary_color_name=p_name,
            primary_color_hex=p_hex,
            secondary_color_name=s_name,
            secondary_color_hex=sec_hex,
            palette=palette,
            pattern=attrs.get("pattern", "solid"),
            material_hint=attrs.get("material_hint", "cotton"),
            fit=attrs.get("fit", "regular"),
            neckline_type=attrs.get("neckline_type", "crewneck"),
            sleeve_length=attrs.get("sleeve_length", "short"),
            hem_length=attrs.get("hem_length", "standard"),
            closure_type=attrs.get("closure_type", "pullover"),
            formality=attrs.get("formality", 4),
            warmth=attrs.get("warmth", 4),
            semantic_embedding=embedding,
            image_type=getattr(seg_output, "image_type", "isolated_product") or "isolated_product",
            occlusion_ratio=getattr(seg_output, "occlusion_ratio", 0.0),
            visible_surface_ratio=getattr(seg_output, "visible_surface_ratio", 1.0),
            inferred_surface_ratio=getattr(seg_output, "inferred_surface_ratio", 0.0),
            detected_body_parts=getattr(seg_output, "detected_body_parts", {}),
            quality_metrics=validation.quality_metrics,
            segmentation_metrics=seg_metrics,
            views=views_dict,
            warnings=all_warnings,
            model_provenance={
                "segmentation_model": seg_output.model_id,
                "classifier_backbone": "PyTorch-MobileNetV3-Features",
                "neural_intelligence_model": neural_intel.model_id,
                "neural_checkpoint": neural_intel.checkpoint_version,
                "neural_device": neural_intel.device_used,
                "component_engine": "SpatialGradientContourDetector-v2",
                "quality_engine": "LaplacianContrastEstimator-v2"
            }
        )

        # ── Assemble Diagnostics Payload ──────────────────────────────────────
        # Normalized outer contour and holes polygons in [0.0, 1.0] coordinates
        w_img, h_img = front_image.size
        norm_outer = [[round(p[0] / max(w_img, 1), 4), round(p[1] / max(h_img, 1), 4)] for p in seg_output.outer_contour]
        norm_holes = [
            [[round(p[0] / max(w_img, 1), 4), round(p[1] / max(h_img, 1), 4)] for p in h_pts]
            for h_pts in seg_output.holes
        ]

        # Phase 11B preview data URLs
        human_parsing_b64 = seg_output.to_human_parsing_data_url() if hasattr(seg_output, "to_human_parsing_data_url") else None
        occlusion_b64 = seg_output.to_occlusion_mask_data_url() if hasattr(seg_output, "to_occlusion_mask_data_url") else None
        
        crop_b64 = None
        if hasattr(seg_output, "bbox") and seg_output.bbox:
            try:
                import io, base64
                cr_img = seg_output.segmented_image.crop(seg_output.bbox)
                c_buf = io.BytesIO()
                cr_img.save(c_buf, format="PNG")
                crop_b64 = f"data:image/png;base64,{base64.b64encode(c_buf.getvalue()).decode('ascii')}"
            except Exception:
                crop_b64 = None

        on_body_telemetry = {
            "image_type": getattr(seg_output, "image_type", "isolated_product"),
            "target_garment_class": getattr(seg_output, "target_garment_class", pred_category),
            "occlusion_ratio": getattr(seg_output, "occlusion_ratio", 0.0),
            "visible_surface_ratio": getattr(seg_output, "visible_surface_ratio", 1.0),
            "inferred_surface_ratio": getattr(seg_output, "inferred_surface_ratio", 0.0),
            "detected_body_parts": getattr(seg_output, "detected_body_parts", {}),
        }

        # ── Stage 6: Reliability & Calibration Assessment ─────────────────────
        t0 = time.perf_counter()
        cross_delta = getattr(views_dict.get("back"), "color_delta_e_with_front", None) if "back" in views_dict else None
        rel_assessment = reliability_engine.evaluate_reliability(
            image=front_image,
            category=pred_category,
            subcategory=pred_subcategory,
            category_confidence=cls_result["category_confidence"],
            components_detected=components,
            silhouette_quality=seg_output.silhouette_quality,
            mesh_is_manifold=True,
            is_multi_view=(back_image is not None),
            cross_view_delta_e=cross_delta
        )
        stage_latencies["reliability_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        diagnostics = GarmentDiagnosticsV2(
            job_id=job_id,
            intelligence=intelligence_v2,
            alpha_mask_data_url=seg_output.to_alpha_mask_data_url(),
            segmented_preview_data_url=seg_output.to_segmented_preview_data_url(),
            human_parsing_preview_data_url=human_parsing_b64,
            occlusion_preview_data_url=occlusion_b64,
            garment_crop_preview_data_url=crop_b64,
            on_body_telemetry=on_body_telemetry,
            outer_contour_polygon=norm_outer,
            holes_polygons=norm_holes,
            pipeline_stage_latencies_ms=stage_latencies,
            reliability_assessment=asdict(rel_assessment)
        )

        return intelligence_v2, diagnostics, seg_output


# Global singleton master service
garment_intelligence_service = GarmentIntelligenceService()
