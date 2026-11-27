"""Executable local component evidence engine (Phase 16.1).

Reuses verified local perception components (SegFormer-B2 human parsing if cached,
OpenAI CLIP ViT-B/32 region crop scoring if cached, and deterministic OpenCV geometry)
with SHA-256 caching, strict visibility/uncertainty tracking, zero box fabrication,
per-component error isolation, and cancellation support.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import io
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

import cv2
import numpy as np
from PIL import Image

from backend.app.services.ai.contracts import (
    ComponentAnalysisBundle,
    ComponentObservation,
    FusedComponentAssessment,
    ImageEvidenceRecord,
    UncertaintyBreakdown,
)
from backend.app.services.ai.evaluation.calibration import ConfidenceCalibrator
from backend.app.services.ai.multiview.view_classifier import GarmentViewType, view_classifier
from backend.app.services.intelligence.component_taxonomy import (
    COMPONENT_TAXONOMY,
    ComponentEvidenceStatus,
    DetectionState,
    GarmentFamily,
    VisibilityState,
    resolve_category_profile,
)
from backend.app.services.intelligence.garment_structure_graph import (
    build_component_handoff_contract,
    build_garment_structure_graph,
    decide_downstream_action,
)

logger = logging.getLogger(__name__)

_CALIBRATOR = ConfidenceCalibrator(temperature=1.2)
_MAX_COMPONENT_CACHE = 256
_MAX_INFERENCE_DIM = 768

_COMPONENT_CACHE: "OrderedDict[Tuple[str, str, str, str], Dict[str, Any]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CLIP_LOCK = threading.Lock()
_CLIP_STATE: Dict[str, Any] = {"loaded": False, "model": None, "processor": None, "device": "cpu"}


def _clamp_box(ymin: float, xmin: float, ymax: float, xmax: float) -> Optional[Tuple[float, float, float, float]]:
    y0 = max(0.0, min(1.0, float(ymin)))
    y1 = max(0.0, min(1.0, float(ymax)))
    x0 = max(0.0, min(1.0, float(xmin)))
    x1 = max(0.0, min(1.0, float(xmax)))
    if y1 - y0 < 0.005 or x1 - x0 < 0.005:
        return None
    return (round(y0, 4), round(x0, 4), round(y1, 4), round(x1, 4))


def _box_from_mask(mask: np.ndarray, h: int, w: int) -> Optional[Tuple[float, float, float, float]]:
    ys, xs = np.where(mask > 0)
    if len(ys) < 12:
        return None
    return _clamp_box(int(ys.min()) / h, int(xs.min()) / w, (int(ys.max()) + 1) / h, (int(xs.max()) + 1) / w)


def _cached_clip_crop_scores(crop: Image.Image, prompts: List[str]) -> Optional[Dict[str, float]]:
    """Run cached OpenAI CLIP ViT-B/32 on a small localized garment crop without network access."""
    if os.getenv("YORVYN_DISABLE_COMPONENT_CLIP") == "1":
        return None
    try:
        import torch
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        snapshots = hf_home / "hub" / "models--openai--clip-vit-base-patch32" / "snapshots"
        if not snapshots.is_dir():
            return None
        with _CLIP_LOCK:
            if not _CLIP_STATE["loaded"]:
                from transformers import CLIPModel, CLIPProcessor
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True)  # nosec B615
                mdl = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True).to(device).eval()  # nosec B615
                _CLIP_STATE.update(loaded=True, model=mdl, processor=proc, device=device)
            proc = _CLIP_STATE["processor"]
            mdl = _CLIP_STATE["model"]
            dev = _CLIP_STATE["device"]
            with torch.inference_mode():
                inputs = proc(text=prompts, images=crop.convert("RGB"), return_tensors="pt", padding=True).to(dev)
                logits = mdl(**inputs).logits_per_image[0]
                probs = torch.softmax(logits, dim=0).detach().cpu().numpy().tolist()
        return dict(zip(prompts, [float(p) for p in probs]))
    except Exception:
        return None


def _run_segformer_parsing(image: Image.Image, category_hint: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Dict[str, Any]]:
    """Extract garment mask and occluder mask using cached SegFormer-B2 Clothes when available."""
    if os.getenv("YORVYN_DISABLE_SEGFORMER") == "1":
        return None, None, {"backend": "disabled_by_env", "weights_loaded": False}
    try:
        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        snapshots = hf_home / "hub" / "models--mattmdjaga--segformer_b2_clothes" / "snapshots"
        if not snapshots.is_dir():
            return None, None, {"backend": "weights_absent", "weights_loaded": False}
        from backend.app.services.garments.segmentation.human_parsing_segmenter import (
            GARMENT_CLASSES,
            PERSON_CLASSES,
            human_parsing_segmenter,
        )
        pred_seg, conf_seg = human_parsing_segmenter.parse_full_body(image)
        target_cls, _ = human_parsing_segmenter.resolve_target_garment_class(pred_seg, category_hint)
        garment_mask = (pred_seg == target_cls).astype(np.uint8) * 255
        if int(np.sum(garment_mask > 0)) < int(0.015 * pred_seg.size):
            # Pick dominant clothing class when hint didn't match parsed label
            counts = {c: int(np.sum(pred_seg == c)) for c in GARMENT_CLASSES}
            best_c = max(counts, key=counts.get)
            if counts[best_c] >= int(0.015 * pred_seg.size):
                target_cls = best_c
                garment_mask = (pred_seg == best_c).astype(np.uint8) * 255
        # Non-target clothing + limbs/hair/accessories can occlude expected garment zones.
        occluder_classes = (PERSON_CLASSES | {16, 17, 8}) | (GARMENT_CLASSES - {target_cls})
        occluder_mask = np.isin(pred_seg, list(occluder_classes)).astype(np.uint8) * 255
        mean_conf = float(np.mean(conf_seg[garment_mask > 0])) if np.any(garment_mask > 0) else 0.0
        return garment_mask, occluder_mask, {
            "backend": "segformer_b2_clothes",
            "model_id": "human_parsing_segformer_b2",
            "checkpoint": "mattmdjaga/segformer_b2_clothes",
            "weights_loaded": True,
            "target_class": int(target_cls),
            "mean_mask_confidence": round(mean_conf, 4),
        }
    except Exception as exc:
        return None, None, {"backend": "segformer_error", "error": type(exc).__name__, "weights_loaded": False}


def _opencv_foreground_mask(rgb_np: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    border = np.concatenate([gray[:8, :].ravel(), gray[-8:, :].ravel(), gray[:, :8].ravel(), gray[:, -8:].ravel()])
    bg_median = float(np.median(border))
    thresh_mode = cv2.THRESH_BINARY_INV if bg_median > 165.0 else cv2.THRESH_BINARY
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, fg = cv2.threshold(blurred, 0, 255, thresh_mode + cv2.THRESH_OTSU)
    # Also allow color difference from border background when luminance is close
    border_rgb = np.median(
        np.vstack([rgb_np[:8, :, :].reshape(-1, 3), rgb_np[-8:, :, :].reshape(-1, 3)]),
        axis=0,
    )
    color_dist = np.linalg.norm(rgb_np.astype(np.float32) - border_rgb.astype(np.float32), axis=2)
    color_fg = (color_dist > 28.0).astype(np.uint8) * 255
    fg = cv2.bitwise_or(fg, color_fg) if float(np.mean(color_fg > 0)) < 0.85 else fg
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=1)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)
    # Keep largest connected component if reasonable
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if n_labels > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = 1 + int(np.argmax(areas))
        if stats[keep, cv2.CC_STAT_AREA] > 0.02 * h * w:
            fg = ((labels == keep).astype(np.uint8) * 255)
    return fg


def _region_visibility(
    region_box: Tuple[int, int, int, int],
    img_shape: Tuple[int, int],
    quality: Dict[str, Any],
    fg_mask: np.ndarray,
    occluder_mask: Optional[np.ndarray],
) -> Tuple[VisibilityState, float, List[str]]:
    """Determine visibility state and occlusion ratio for a pixel rectangle (y0, x0, y1, x1)."""
    h, w = img_shape
    y0, x0, y1, x1 = max(0, region_box[0]), max(0, region_box[1]), min(h, region_box[2]), min(w, region_box[3])
    reasons: List[str] = []
    if not quality.get("image_usable", True) or quality.get("sharpness", 10.0) < 2.2 or quality.get("contrast", 20.0) < 16.0:
        reasons.append("Low resolution, blur, or low contrast impairs reliable region inspection.")
        return VisibilityState.LOW_IMAGE_QUALITY, 0.0, reasons
    # Border truncation check
    edge_touches = []
    if y0 <= 2 and float(np.mean(fg_mask[:4, x0:max(x0 + 1, x1)] > 0)) > 0.25:
        edge_touches.append("top")
    if y1 >= h - 2 and float(np.mean(fg_mask[max(0, h - 4):, x0:max(x0 + 1, x1)] > 0)) > 0.25:
        edge_touches.append("bottom")
    if x0 <= 2 and float(np.mean(fg_mask[y0:max(y0 + 1, y1), :4] > 0)) > 0.25:
        edge_touches.append("left")
    if x1 >= w - 2 and float(np.mean(fg_mask[y0:max(y0 + 1, y1), max(0, w - 4):] > 0)) > 0.25:
        edge_touches.append("right")
    if edge_touches:
        reasons.append(f"Region touches image frame border ({', '.join(edge_touches)}).")
        return VisibilityState.OUT_OF_FRAME, 0.0, reasons

    occ_ratio = 0.0
    if occluder_mask is not None and y1 > y0 and x1 > x0:
        sub_occ = occluder_mask[y0:y1, x0:x1] > 0
        occ_ratio = float(np.mean(sub_occ))
        if occ_ratio >= 0.45:
            reasons.append(f"Region heavily occluded ({occ_ratio * 100:.0f}% covered).")
            return VisibilityState.OCCLUDED, occ_ratio, reasons
        if occ_ratio >= 0.16:
            reasons.append(f"Region partially occluded ({occ_ratio * 100:.0f}% covered).")
            return VisibilityState.PARTIALLY_VISIBLE, occ_ratio, reasons
    return VisibilityState.FULLY_VISIBLE, occ_ratio, reasons


def _make_uncertainty(
    visibility: VisibilityState,
    confidence: Optional[float],
    completeness: float,
    extra_reasons: List[str],
    occlusion_ratio: float = 0.0,
) -> UncertaintyBreakdown:
    aleatoric = 0.12
    if visibility == VisibilityState.PARTIALLY_VISIBLE:
        aleatoric = min(0.75, 0.35 + occlusion_ratio * 0.6)
    elif visibility in (VisibilityState.OCCLUDED, VisibilityState.OUT_OF_FRAME, VisibilityState.LOW_IMAGE_QUALITY):
        aleatoric = 0.80
    elif visibility == VisibilityState.UNKNOWN:
        aleatoric = 0.90

    if confidence is None:
        epistemic = 0.95
    else:
        epistemic = max(0.05, min(0.95, 1.0 - confidence))
    total = round(min(1.0, max(0.05, 0.5 * epistemic + 0.5 * aleatoric)), 4)
    return UncertaintyBreakdown(
        total_uncertainty=total,
        epistemic_uncertainty=round(epistemic, 4),
        aleatoric_uncertainty=round(aleatoric, 4),
        evidence_completeness=round(max(0.0, min(1.0, completeness)), 4),
        reasons=extra_reasons,
    )


def _analyze_single_view_components(
    image_id: str,
    image_hash: str,
    image_bytes: bytes,
    view_type: str,
    garment_id: str,
    category: str,
    subcategory: str,
    precomputed_seg: Optional[Dict[str, Any]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """Localize components in a single garment view with explicit visibility, bounds, and uncertainty."""
    cache_key = (image_hash, view_type, category.lower(), subcategory.lower())
    with _CACHE_LOCK:
        if cache_key in _COMPONENT_CACHE:
            _COMPONENT_CACHE.move_to_end(cache_key)
            cached = _COMPONENT_CACHE[cache_key]
            # Re-bind image_id and garment_id while reusing localization computation.
            rebound = []
            for obs in cached["observations"]:
                rebound.append(obs.model_copy(update={
                    "observation_id": f"obs_{uuid.uuid4().hex[:10]}",
                    "garment_id": garment_id,
                    "source_image_id": image_id,
                }))
            return {
                "observations": rebound,
                "landmarks": dict(cached["landmarks"]),
                "cache_hit": True,
                "latency_ms": 0.1,
                "warnings": list(cached["warnings"]),
            }

    t0 = time.perf_counter()
    if cancel_check and cancel_check():
        raise TimeoutError("Component analysis cancelled before image preprocessing.")

    with Image.open(io.BytesIO(image_bytes)) as src:
        rgb_full = src.convert("RGB")
        orig_w, orig_h = rgb_full.size
        scale = min(1.0, _MAX_INFERENCE_DIM / float(max(orig_w, orig_h)))
        if scale < 1.0:
            rgb_img = rgb_full.resize((max(64, int(orig_w * scale)), max(64, int(orig_h * scale))), Image.Resampling.BILINEAR)
        else:
            rgb_img = rgb_full

    quality = view_classifier.evaluate_quality(rgb_img)
    rgb_np = np.array(rgb_img)
    h, w = rgb_np.shape[:2]
    gray = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2GRAY)

    warnings: List[str] = []
    # Foreground + occluder segmentation (reuse supplied mask or SegFormer, fallback OpenCV)
    seg_info: Dict[str, Any] = {"backend": "opencv_contour", "weights_loaded": False}
    fg_mask = None
    occluder_mask = None
    if precomputed_seg and precomputed_seg.get("alpha_mask") is not None:
        m = np.asarray(precomputed_seg["alpha_mask"], dtype=np.uint8)
        fg_mask = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
        seg_info = {"backend": precomputed_seg.get("backend", "supplied_mask"), "weights_loaded": False}
    else:
        fg_mask, occluder_mask, seg_info = _run_segformer_parsing(rgb_img, category)
        if fg_mask is None or int(np.sum(fg_mask > 0)) < int(0.02 * h * w):
            fg_mask = _opencv_foreground_mask(rgb_np)
            seg_info = {"backend": "opencv_otsu_color_cc", "weights_loaded": False}

    ys, xs = np.where(fg_mask > 20)
    if len(ys) < 64:
        warnings.append(f"No distinct garment silhouette segmented in '{image_id}'.")
        return {
            "observations": [],
            "landmarks": {},
            "cache_hit": False,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "warnings": warnings,
        }

    min_y, max_y = int(ys.min()), int(ys.max())
    min_x, max_x = int(xs.min()), int(xs.max())
    gh = max(1, max_y - min_y + 1)
    gw = max(1, max_x - min_x + 1)
    cx = (min_x + max_x) // 2

    gray_masked = np.where(fg_mask > 20, gray, 0)
    sobel_x = np.abs(cv2.Sobel(gray_masked, cv2.CV_64F, 1, 0, ksize=3))
    sobel_y = np.abs(cv2.Sobel(gray_masked, cv2.CV_64F, 0, 1, ksize=3))
    grad_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    edges = cv2.Canny(gray_masked, 55, 145)

    profile = resolve_category_profile(category, subcategory)
    observations: List[ComponentObservation] = []
    landmarks: Dict[str, Tuple[float, float]] = {}

    is_front_like = view_type in (GarmentViewType.FRONT.value, GarmentViewType.THREE_QUARTER.value, "front", "three_quarter")
    is_back_like = view_type in (GarmentViewType.BACK.value, "back")
    is_side_like = view_type in (GarmentViewType.LEFT_SIDE.value, GarmentViewType.RIGHT_SIDE.value, "left_side", "right_side")
    is_detail_like = view_type in (GarmentViewType.DETAIL.value, GarmentViewType.CLOSE_UP.value, "detail", "close_up")
    if view_type == GarmentViewType.UNKNOWN.value:
        # Without a verified viewpoint hint or strong front cue, keep view-specific claims conservative.
        is_front_like = False

    def record_obs(
        component_id: str,
        vis: VisibilityState,
        det_state: DetectionState,
        ev_status: ComponentEvidenceStatus,
        raw_conf: Optional[float],
        bbox: Optional[Tuple[float, float, float, float]],
        reasons: List[str],
        occ_ratio: float = 0.0,
        lm_refs: Optional[List[str]] = None,
        extra_prov: Optional[Dict[str, Any]] = None,
        mask_tag: Optional[str] = None,
        comp_t0: Optional[float] = None,
    ) -> None:
        entry = COMPONENT_TAXONOMY.get(component_id)
        if not entry:
            return
        cal_p = _CALIBRATOR.calibrate_probability(raw_conf) if raw_conf is not None else None
        expected_v = entry.expected_views
        completeness = 1.0 if view_type in expected_v and vis == VisibilityState.FULLY_VISIBLE else (0.55 if vis == VisibilityState.PARTIALLY_VISIBLE else 0.2)
        if det_state == DetectionState.NOT_DETECTED and ev_status == ComponentEvidenceStatus.NOT_OBSERVED:
            completeness = 0.0
        unc = _make_uncertainty(vis, cal_p, completeness, reasons, occ_ratio)
        proc_ms = round((time.perf_counter() - comp_t0) * 1000.0, 3) if comp_t0 else 0.2
        observations.append(ComponentObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:10]}",
            component_id=component_id,
            component_type=entry.component_type,
            parent_component=entry.parent_component,
            garment_id=garment_id,
            garment_category=category,
            garment_subcategory=subcategory,
            side_or_orientation=entry.default_side,
            source_image_id=image_id,
            source_image_hash=image_hash,
            source_view=view_type,
            bbox=bbox,
            segmentation_mask_ref=mask_tag,
            landmark_refs=lm_refs or [],
            visibility_state=vis,
            detection_state=det_state,
            evidence_status=ev_status,
            confidence=round(raw_conf, 4) if raw_conf is not None else None,
            calibrated_probability=cal_p,
            uncertainty=unc,
            model_id=str(seg_info.get("model_id", "deterministic_cv_component_localizer")),
            checkpoint_identity=str(seg_info.get("checkpoint", "opencv-sobel-contour-v16.1")),
            capability_id="components.identify",
            execution_provenance={**seg_info, **(extra_prov or {})},
            processing_ms=proc_ms,
        ))

    def clip_score_crop(px_box: Tuple[int, int, int, int], prompts: List[str]) -> Optional[Dict[str, float]]:
        y0, x0, y1, x1 = max(0, px_box[0]), max(0, px_box[1]), min(h, px_box[2]), min(w, px_box[3])
        if y1 - y0 < 24 or x1 - x0 < 24:
            return None
        return _cached_clip_crop_scores(rgb_img.crop((x0, y0, x1, y1)), prompts)

    # ── BRANCH 1: LOWER-BODY GARMENTS ────────────────────────────────────────
    if profile.family == GarmentFamily.LOWER_BODY:
        wb_h = max(6, int(gh * 0.13))
        wb_box_px = (min_y, min_x, min_y + wb_h, max_x)
        wb_vis, wb_occ, wb_r = _region_visibility(wb_box_px, (h, w), quality, fg_mask, occluder_mask)
        wb_mask = np.zeros_like(fg_mask)
        wb_mask[min_y:min_y + wb_h, min_x:max_x] = fg_mask[min_y:min_y + wb_h, min_x:max_x]
        wb_bbox = _box_from_mask(wb_mask, h, w)
        if wb_bbox:
            landmarks["waist_center"] = (round(cx / w, 4), round(min_y / h, 4))
            record_obs("lower_waistband", wb_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       0.86 if wb_vis == VisibilityState.FULLY_VISIBLE else 0.65, wb_bbox,
                       wb_r or ["Top foreground waistband band localized."], wb_occ, ["waist_center"],
                       mask_tag=f"seg:{image_hash[:10]}:lower_waistband")

        # Leg bifurcation check (search middle-lower zone for background gap around center x)
        crotch_y = min_y + int(gh * 0.35)
        bifurcated = False
        for ry in range(min_y + int(gh * 0.25), min_y + int(gh * 0.65), max(2, gh // 40)):
            left_fill = float(np.mean(fg_mask[ry, min_x:cx - max(2, int(gw * 0.06))] > 0))
            mid_fill = float(np.mean(fg_mask[ry, cx - max(2, int(gw * 0.05)):cx + max(2, int(gw * 0.05))] > 0))
            right_fill = float(np.mean(fg_mask[ry, cx + max(2, int(gw * 0.06)):max_x] > 0))
            if left_fill > 0.25 and right_fill > 0.25 and mid_fill < 0.25:
                crotch_y = ry
                bifurcated = True
                break
        landmarks["crotch"] = (round(cx / w, 4), round(crotch_y / h, 4))

        for side_cid, x0_l, x1_l, ank_name in (
            ("left_leg", min_x, cx, "left_ankle"),
            ("right_leg", cx, max_x, "right_ankle"),
        ):
            t_c = time.perf_counter()
            leg_mask = np.zeros_like(fg_mask)
            leg_mask[min_y + wb_h:max_y, x0_l:x1_l] = fg_mask[min_y + wb_h:max_y, x0_l:x1_l]
            leg_bbox = _box_from_mask(leg_mask, h, w)
            vis, occ, r = _region_visibility((min_y + wb_h, x0_l, max_y, x1_l), (h, w), quality, fg_mask, occluder_mask)
            if leg_bbox and float(np.sum(leg_mask > 0)) > 0.05 * np.sum(fg_mask > 0):
                landmarks[ank_name] = (round(((x0_l + x1_l) / 2) / w, 4), round(max_y / h, 4))
                record_obs(side_cid, vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           0.88 if bifurcated else 0.72, leg_bbox,
                           r or [f"Leg region segmented ({'bifurcated' if bifurcated else 'silhouette split'})."], occ,
                           [ank_name], mask_tag=f"seg:{image_hash[:10]}:{side_cid}", comp_t0=t_c)

        # Crotch seam & fly (front) / pockets
        if bifurcated:
            cs_box = _clamp_box((crotch_y - 6) / h, (cx - gw * 0.1) / w, (crotch_y + 10) / h, (cx + gw * 0.1) / w)
            record_obs("crotch_seam", VisibilityState.FULLY_VISIBLE, DetectionState.DETECTED,
                       ComponentEvidenceStatus.OBSERVED, 0.84, cs_box, ["Bifurcation notch localized."], 0.0, ["crotch"])
        if is_front_like:
            fly_zone = sobel_x[min_y + wb_h:min(max_y, crotch_y), max(0, cx - int(gw * 0.08)):min(w, cx + int(gw * 0.08))]
            fly_edge = float(np.mean(fly_zone > 20)) if fly_zone.size else 0.0
            fly_box = _clamp_box((min_y + wb_h) / h, (cx - gw * 0.07) / w, crotch_y / h, (cx + gw * 0.07) / w)
            if fly_edge > 0.08:
                record_obs("fly", VisibilityState.FULLY_VISIBLE, DetectionState.DETECTED,
                           ComponentEvidenceStatus.OBSERVED, min(0.90, 0.60 + fly_edge), fly_box,
                           [f"Vertical fly seam edge density {fly_edge:.2f}."])
            else:
                record_obs("fly", VisibilityState.FULLY_VISIBLE, DetectionState.UNCERTAIN,
                           ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE, 0.45, None,
                           ["Weak center fly edge contrast."])
            record_obs("back_pocket", VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                       ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                       ["Back view is required before determining back pocket presence or absence."])
        elif is_back_like:
            record_obs("fly", VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                       ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                       ["Front view required for center fly closure."])
            # Back pocket check on upper-rear leg panel
            bp_y0, bp_y1 = min_y + int(gh * 0.14), min_y + int(gh * 0.36)
            bp_edge = float(np.mean(edges[bp_y0:bp_y1, min_x + int(gw * 0.12):max_x - int(gw * 0.12)] > 0))
            bp_vis, bp_occ, bp_r = _region_visibility((bp_y0, min_x, bp_y1, max_x), (h, w), quality, fg_mask, occluder_mask)
            if bp_edge > 0.05 and bp_vis == VisibilityState.FULLY_VISIBLE:
                bp_box = _clamp_box(bp_y0 / h, (min_x + gw * 0.15) / w, bp_y1 / h, (max_x - gw * 0.15) / w)
                record_obs("back_pocket", bp_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           min(0.88, 0.60 + bp_edge * 2.0), bp_box, ["Rear pocket seam edges localized."], bp_occ)
            elif bp_vis == VisibilityState.FULLY_VISIBLE and bp_edge < 0.015:
                record_obs("back_pocket", bp_vis, DetectionState.ABSENT_VERIFIED, ComponentEvidenceStatus.OBSERVED,
                           0.76, None, ["Rear hip panel fully visible without pocket seam contours."], bp_occ)
            else:
                record_obs("back_pocket", bp_vis, DetectionState.UNCERTAIN, ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                           0.40, None, bp_r or ["Back pocket evidence inconclusive."], bp_occ)

        # Leg openings / hem
        hem_vis, hem_occ, hem_r = _region_visibility((max_y - int(gh * 0.1), min_x, max_y, max_x), (h, w), quality, fg_mask, occluder_mask)
        hem_box = _clamp_box((max_y - int(gh * 0.08)) / h, min_x / w, max_y / h, max_x / w)
        record_obs("leg_opening", hem_vis, DetectionState.DETECTED if hem_vis != VisibilityState.OUT_OF_FRAME else DetectionState.UNCERTAIN,
                   ComponentEvidenceStatus.OBSERVED if hem_vis == VisibilityState.FULLY_VISIBLE else ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                   0.84 if hem_vis == VisibilityState.FULLY_VISIBLE else 0.45, hem_box,
                   hem_r or ["Lower ankle opening boundary localized."], hem_occ)

    # ── BRANCH 2: DRESSES & ONE-PIECE ────────────────────────────────────────
    elif profile.family == GarmentFamily.DRESS_ONE_PIECE:
        waist_split_y = min_y + int(gh * 0.38)
        if category != "skirt":
            bod_box_px = (min_y, min_x, waist_split_y, max_x)
            b_vis, b_occ, b_r = _region_visibility(bod_box_px, (h, w), quality, fg_mask, occluder_mask)
            bod_mask = np.zeros_like(fg_mask)
            bod_mask[min_y:waist_split_y, min_x:max_x] = fg_mask[min_y:waist_split_y, min_x:max_x]
            bod_bbox = _box_from_mask(bod_mask, h, w)
            if bod_bbox:
                record_obs("bodice", b_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           0.86 if b_vis == VisibilityState.FULLY_VISIBLE else 0.62, bod_bbox,
                           b_r or ["Upper bodice region segmented."], b_occ, mask_tag=f"seg:{image_hash[:10]}:bodice")
            neck_box = _clamp_box(min_y / h, (cx - gw * 0.22) / w, (min_y + gh * 0.15) / h, (cx + gw * 0.22) / w)
            n_vis, n_occ, n_r = _region_visibility((min_y, int(cx - gw * 0.25), min_y + int(gh * 0.16), int(cx + gw * 0.25)),
                                                   (h, w), quality, fg_mask, occluder_mask)
            if neck_box:
                landmarks["neck_center"] = (round(cx / w, 4), round(min_y / h, 4))
                record_obs("neckline", n_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           0.80, neck_box, n_r or ["Neckline region localized."], n_occ, ["neck_center"])
            w_box = _clamp_box((waist_split_y - gh * 0.04) / h, min_x / w, (waist_split_y + gh * 0.04) / h, max_x / w)
            landmarks["waist_center"] = (round(cx / w, 4), round(waist_split_y / h, 4))
            record_obs("waistline", b_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED, 0.78, w_box,
                       ["Waistline contour region localized."], b_occ, ["waist_center"])
        else:
            waist_split_y = min_y

        sk_vis, sk_occ, sk_r = _region_visibility((waist_split_y, min_x, max_y, max_x), (h, w), quality, fg_mask, occluder_mask)
        sk_mask = np.zeros_like(fg_mask)
        sk_mask[waist_split_y:max_y, min_x:max_x] = fg_mask[waist_split_y:max_y, min_x:max_x]
        sk_bbox = _box_from_mask(sk_mask, h, w)
        if sk_bbox:
            record_obs("skirt", sk_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       0.87 if sk_vis == VisibilityState.FULLY_VISIBLE else 0.64, sk_bbox,
                       sk_r or ["Skirt drape segmented."], sk_occ, mask_tag=f"seg:{image_hash[:10]}:skirt")
        hem_vis, hem_occ, hem_r = _region_visibility((max_y - int(gh * 0.1), min_x, max_y, max_x), (h, w), quality, fg_mask, occluder_mask)
        hem_box = _clamp_box((max_y - int(gh * 0.08)) / h, min_x / w, max_y / h, max_x / w)
        record_obs("hem", hem_vis, DetectionState.DETECTED if hem_vis != VisibilityState.OUT_OF_FRAME else DetectionState.UNCERTAIN,
                   ComponentEvidenceStatus.OBSERVED if hem_vis == VisibilityState.FULLY_VISIBLE else ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                   0.84 if hem_vis == VisibilityState.FULLY_VISIBLE else 0.45, hem_box, hem_r or ["Hem contour localized."], hem_occ)
        if not is_back_like:
            record_obs("dress_closures", VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                       ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                       ["Back view not shown; rear dress zipper or buttons cannot be verified."])

    # ── BRANCH 3: UPPER-BODY GARMENTS ────────────────────────────────────────
    else:
        # 1. Measure torso horizontal width profile to find neck narrowing & armpit shoulder inflection
        neck_y_end = min_y + int(gh * 0.25)
        neck_sample_widths = []
        for r_pct in np.linspace(0.08, 0.26, 9):
            ry = min_y + int(gh * r_pct)
            r_xs = xs[(ys >= ry - 2) & (ys <= ry + 2)]
            if len(r_xs):
                neck_sample_widths.append((float(r_xs.max() - r_xs.min()) / gw, ry))
        collar_y = min_y + int(gh * 0.16)
        if neck_sample_widths:
            neck_sample_widths.sort(key=lambda item: item[0])
            collar_y = neck_sample_widths[0][1]

        # Armpit/torso span inferred from waist/lower chest width stability [0.42..0.68*gh]
        mid_widths = []
        for r_pct in np.linspace(0.42, 0.68, 7):
            ry = min_y + int(gh * r_pct)
            # Inside inner 70% horizontal slice around center
            r_xs = xs[(ys >= ry - 2) & (ys <= ry + 2) & (xs >= cx - int(gw * 0.36)) & (xs <= cx + int(gw * 0.36))]
            if len(r_xs):
                mid_widths.append(int(r_xs.max() - r_xs.min()))
        torso_half_w = int(np.median(mid_widths) * 0.5) if mid_widths else int(gw * 0.25)
        torso_half_w = max(int(gw * 0.16), min(int(gw * 0.36), torso_half_w))
        torso_x0 = max(min_x, cx - torso_half_w)
        torso_x1 = min(max_x, cx + torso_half_w)
        shoulder_y = min_y + int(gh * 0.12)

        landmarks["shoulder_left"] = (round(torso_x0 / w, 4), round(shoulder_y / h, 4))
        landmarks["shoulder_right"] = (round(torso_x1 / w, 4), round(shoulder_y / h, 4))
        landmarks["hem_center"] = (round(cx / w, 4), round(max_y / h, 4))

        # 2. Body panel strictly anchored to visible side (never fabricate back_body on front!)
        body_mask = np.zeros_like(fg_mask)
        body_mask[shoulder_y:max_y, torso_x0:torso_x1] = fg_mask[shoulder_y:max_y, torso_x0:torso_x1]
        body_bbox = _box_from_mask(body_mask, h, w)
        b_vis, b_occ, b_r = _region_visibility((shoulder_y, torso_x0, max_y, torso_x1), (h, w), quality, fg_mask, occluder_mask)
        if is_front_like and body_bbox:
            record_obs("front_body", b_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       0.90 if b_vis == VisibilityState.FULLY_VISIBLE else 0.65, body_bbox,
                       b_r or ["Front torso silhouette segmented."], b_occ, ["shoulder_left", "shoulder_right", "hem_center"],
                       mask_tag=f"seg:{image_hash[:10]}:front_body")
            record_obs("back_body", VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                       ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                       ["Back body panel is unobserved in front/three-quarter views."])
        elif is_back_like and body_bbox:
            record_obs("back_body", b_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       0.90 if b_vis == VisibilityState.FULLY_VISIBLE else 0.65, body_bbox,
                       b_r or ["Rear torso silhouette segmented."], b_occ, ["shoulder_left", "shoulder_right", "hem_center"],
                       mask_tag=f"seg:{image_hash[:10]}:back_body")
            record_obs("front_body", VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                       ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                       ["Front body panel is unobserved in rear view."])
        elif is_side_like and body_bbox:
            side_cid = "side_panel"
            record_obs(side_cid, b_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       0.82, body_bbox, b_r or ["Lateral side panel localized."], b_occ,
                       mask_tag=f"seg:{image_hash[:10]}:side_panel")

        # 3. Sleeves (actual pixel lobes outside torso column!)
        fg_total = max(1, int(np.sum(fg_mask > 0)))
        for s_cid, sx0, sx1, lm_k, side_skip in (
            ("left_sleeve", min_x, torso_x0, "cuff_left", view_type == GarmentViewType.RIGHT_SIDE.value),
            ("right_sleeve", torso_x1, max_x, "cuff_right", view_type == GarmentViewType.LEFT_SIDE.value),
        ):
            t_c = time.perf_counter()
            if side_skip:
                record_obs(s_cid, VisibilityState.OCCLUDED, DetectionState.NOT_DETECTED,
                           ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                           [f"{s_cid} faces away from the {view_type} camera."])
                continue
            sm = np.zeros_like(fg_mask)
            sm[shoulder_y:max_y, sx0:sx1] = fg_mask[shoulder_y:max_y, sx0:sx1]
            s_px = int(np.sum(sm > 0))
            s_box = _box_from_mask(sm, h, w)
            s_vis, s_occ, s_r = _region_visibility((shoulder_y, sx0, max_y, sx1), (h, w), quality, fg_mask, occluder_mask)
            if s_box and s_px >= 0.025 * fg_total:
                sys_m, sxs_m = np.where(sm > 0)
                landmarks[lm_k] = (round(int(sxs_m.min() if s_cid == "left_sleeve" else sxs_m.max()) / w, 4),
                                   round(int(sys_m.max()) / h, 4))
                record_obs(s_cid, s_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           0.88 if s_vis == VisibilityState.FULLY_VISIBLE else 0.62, s_box,
                           s_r or [f"{s_cid} lateral mask fraction {s_px / fg_total:.2f}."], s_occ, [lm_k],
                           mask_tag=f"seg:{image_hash[:10]}:{s_cid}", comp_t0=t_c)
                # Cuff / sleeve opening check on long sleeves
                s_span_h = (int(sys_m.max()) - int(sys_m.min())) / float(gh)
                if s_span_h > 0.45:
                    s_bot = int(sys_m.max()) + 1
                    cuff_y0 = max(0, s_bot - max(6, int((s_bot - int(sys_m.min())) * 0.14)))
                    cuff_full = np.zeros_like(sm)
                    cuff_full[cuff_y0:s_bot, :] = sm[cuff_y0:s_bot, :]
                    cuff_edge = float(np.mean(grad_mag[cuff_y0:s_bot, sx0:sx1] > 20)) if s_bot > cuff_y0 else 0.0
                    c_box = _box_from_mask(cuff_full, h, w)
                    if c_box and cuff_edge > 0.04:
                        record_obs("cuff", s_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                                   0.76, c_box, [f"Wrist cuff transition detected on {s_cid}."], s_occ, [lm_k])
            else:
                if s_vis == VisibilityState.FULLY_VISIBLE and is_front_like:
                    record_obs(s_cid, s_vis, DetectionState.ABSENT_VERIFIED, ComponentEvidenceStatus.OBSERVED,
                               0.78, None, [f"Unobstructed shoulder contour without lateral {s_cid} lobe."], s_occ)
                else:
                    record_obs(s_cid, s_vis, DetectionState.NOT_DETECTED, ComponentEvidenceStatus.NOT_OBSERVED,
                               None, None, s_r or [f"{s_cid} not observed cleanly in this view."], s_occ)

        # 4. Neck, Collar, Hood, Lapel (localized upper crop + edge energy + cached CLIP confirmation)
        neck_px_box = (min_y, max(min_x, cx - int(gw * 0.28)), min(max_y, min_y + int(gh * 0.30)), min(max_x, cx + int(gw * 0.28)))
        n_vis, n_occ, n_r = _region_visibility(neck_px_box, (h, w), quality, fg_mask, occluder_mask)
        neck_mask = np.zeros_like(fg_mask)
        neck_mask[neck_px_box[0]:neck_px_box[2], neck_px_box[1]:neck_px_box[3]] = fg_mask[neck_px_box[0]:neck_px_box[2], neck_px_box[1]:neck_px_box[3]]
        neck_box_norm = _box_from_mask(neck_mask, h, w)
        clip_neck = clip_score_crop(neck_px_box, [
            "a clothing hood or hoodie cowl",
            "a folded shirt or jacket collar",
            "a tailored jacket lapel",
            "a plain round crewneck or v-neck opening without collar",
        ])
        landmarks["collar_center"] = (round(cx / w, 4), round(collar_y / h, 4))

        if clip_neck:
            hood_p = clip_neck["a clothing hood or hoodie cowl"]
            collar_p = clip_neck["a folded shirt or jacket collar"]
            lapel_p = clip_neck["a tailored jacket lapel"]
            neck_p = clip_neck["a plain round crewneck or v-neck opening without collar"]
            neck_src = {"clip_crop_scores": {k: round(v, 4) for k, v in clip_neck.items()}}
        else:
            # Pure deterministic fallback based on profile & upper geometry
            hood_p = 0.72 if category == "hoodie" and (collar_y - min_y) / gh > 0.14 else 0.10
            collar_p = 0.72 if category in ("shirt", "jacket", "traditional") else 0.15
            lapel_p = 0.55 if category == "jacket" and "blazer" in subcategory else 0.10
            neck_p = 0.75 if category == "tops" else 0.20
            neck_src = {"clip_crop_scores": None}

        if hood_p >= 0.42:
            hood_px = (min_y, max(min_x, cx - int(gw * 0.24)), min(max_y, min_y + int(gh * 0.30)), min(max_x, cx + int(gw * 0.24)))
            h_mask = np.zeros_like(fg_mask)
            h_mask[hood_px[0]:hood_px[2], hood_px[1]:hood_px[3]] = fg_mask[hood_px[0]:hood_px[2], hood_px[1]:hood_px[3]]
            h_box = _box_from_mask(h_mask, h, w)
            record_obs("hood", n_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       min(0.92, 0.55 + hood_p * 0.4), h_box, n_r or ["Hood contour confirmed in neckline crop."],
                       n_occ, ["collar_center"], neck_src, mask_tag=f"seg:{image_hash[:10]}:hood")
        elif "hood" in profile.expected_components and n_vis == VisibilityState.FULLY_VISIBLE and neck_p > 0.55:
            record_obs("hood", n_vis, DetectionState.ABSENT_VERIFIED, ComponentEvidenceStatus.OBSERVED,
                       0.74, None, ["Full neckline clearly visible without hood cowl structure."], n_occ, extra_prov=neck_src)

        if collar_p >= 0.32 or (category in ("shirt", "jacket") and collar_p >= 0.22):
            c_box = _clamp_box(min_y / h, (cx - gw * 0.18) / w, (min_y + gh * 0.18) / h, (cx + gw * 0.18) / w)
            record_obs("collar", n_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       min(0.90, 0.50 + collar_p * 0.45), c_box, n_r or ["Collar edges/structure observed."],
                       n_occ, ["collar_center"], neck_src)
        elif neck_box_norm:
            record_obs("neck_opening", n_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       min(0.86, 0.55 + neck_p * 0.3), neck_box_norm, n_r or ["Neck opening contour localized."],
                       n_occ, ["collar_center"], neck_src)

        if lapel_p >= 0.30 and is_front_like:
            lap_box = _clamp_box((min_y + gh * 0.08) / h, (cx - gw * 0.20) / w, (min_y + gh * 0.42) / h, (cx + gw * 0.20) / w)
            record_obs("lapel", n_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                       min(0.86, 0.48 + lapel_p * 0.4), lap_box, ["Lapel edge geometry scored in upper chest."], n_occ, extra_prov=neck_src)

        # 5. Center Front Closures (STRICT: hidden on back view; real edge/blob + CLIP verification)
        if is_front_like or is_detail_like:
            mid_px = (min_y + int(gh * 0.18), max(min_x, cx - int(gw * 0.14)), min(max_y, min_y + int(gh * 0.85)), min(max_x, cx + int(gw * 0.14)))
            c_vis, c_occ, c_r = _region_visibility(mid_px, (h, w), quality, fg_mask, occluder_mask)
            strip_x0, strip_x1 = max(0, cx - max(4, int(gw * 0.05))), min(w, cx + max(4, int(gw * 0.05)))
            left_x0, left_x1 = max(0, cx - max(14, int(gw * 0.20))), max(1, cx - max(6, int(gw * 0.10)))
            center_edge_density = float(np.mean(sobel_x[mid_px[0]:mid_px[2], strip_x0:strip_x1] > 22))
            side_edge_density = float(np.mean(sobel_x[mid_px[0]:mid_px[2], left_x0:left_x1] > 22))
            track_contrast = max(0.0, center_edge_density - side_edge_density)

            clip_cls = clip_score_crop(mid_px, [
                "a vertical metal or plastic front zipper closure",
                "a front button placket with buttons",
                "hoodie drawstrings hanging from the neck",
                "a smooth solid pullover front without zipper or buttons",
            ])
            cl_box = _clamp_box(mid_px[0] / h, strip_x0 / w, mid_px[2] / h, strip_x1 / w)
            zip_score = (clip_cls["a vertical metal or plastic front zipper closure"] if clip_cls else (0.72 if track_contrast > 0.10 else 0.15))
            btn_score = (clip_cls["a front button placket with buttons"] if clip_cls else (0.70 if category in ("shirt", "jacket") and track_contrast > 0.06 else 0.15))
            draw_score = (clip_cls["hoodie drawstrings hanging from the neck"] if clip_cls else (0.68 if category == "hoodie" and zip_score < 0.4 else 0.10))
            smooth_score = clip_cls["a smooth solid pullover front without zipper or buttons"] if clip_cls else 0.3

            prov_c = {"center_track_edge_delta": round(track_contrast, 4), "clip_closure_scores": clip_cls}
            if zip_score >= 0.40 and track_contrast >= 0.03:
                record_obs("zipper", c_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           min(0.90, 0.50 + zip_score * 0.4), cl_box, c_r or ["Front zipper track edge contrast confirmed."], c_occ, extra_prov=prov_c)
            elif btn_score >= 0.36 and (track_contrast >= 0.02 or category in ("shirt", "jacket")):
                record_obs("button_placket", c_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           min(0.89, 0.48 + btn_score * 0.45), cl_box, c_r or ["Center front button placket detected."], c_occ, extra_prov=prov_c)
                record_obs("button", c_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           min(0.85, 0.45 + btn_score * 0.45), cl_box, ["Fastener buttons associated with placket."], c_occ, extra_prov=prov_c)
            elif "zipper" in profile.expected_components or "button_placket" in profile.expected_components:
                # Explicitly distinguish uncertain vs clean pullover verified absence
                if smooth_score >= 0.55 and track_contrast < 0.04 and c_vis == VisibilityState.FULLY_VISIBLE:
                    record_obs("zipper", c_vis, DetectionState.ABSENT_VERIFIED, ComponentEvidenceStatus.OBSERVED,
                               0.76, None, ["Smooth continuous front center observed without zipper track."], c_occ, extra_prov=prov_c)
                else:
                    target_cl = "button_placket" if category in ("shirt", "jacket") else "zipper"
                    record_obs(target_cl, c_vis, DetectionState.UNCERTAIN, ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                               0.42, None, c_r or ["Center front closure detail is ambiguous."], c_occ, extra_prov=prov_c)

            if category == "hoodie" and draw_score >= 0.36:
                dr_box = _clamp_box((min_y + gh * 0.14) / h, (cx - gw * 0.09) / w, (min_y + gh * 0.40) / h, (cx + gw * 0.09) / w)
                record_obs("drawstring", c_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                           min(0.84, 0.45 + draw_score * 0.45), dr_box, ["Neck drawstring evidence observed."], c_occ, extra_prov=prov_c)
        elif is_back_like:
            for hidden_c in ("zipper", "button_placket", "kangaroo_pocket"):
                if hidden_c in profile.expected_components:
                    record_obs(hidden_c, VisibilityState.UNKNOWN, DetectionState.NOT_DETECTED,
                               ComponentEvidenceStatus.NOT_OBSERVED, None, None,
                               [f"{hidden_c} is an anterior feature not observable from a rear view."])

        # 6. Pockets (Edge-verified kangaroo / chest pockets, never fabricated blindly!)
        if is_front_like:
            if "kangaroo_pocket" in profile.expected_components:
                p_y0, p_y1 = min_y + int(gh * 0.56), min_y + int(gh * 0.88)
                p_x0, p_x1 = max(torso_x0, cx - int(gw * 0.20)), min(torso_x1, cx + int(gw * 0.20))
                p_vis, p_occ, p_r = _region_visibility((p_y0, p_x0, p_y1, p_x1), (h, w), quality, fg_mask, occluder_mask)
                p_edge = float(np.mean(edges[p_y0:p_y1, p_x0:p_x1] > 0)) if p_y1 > p_y0 and p_x1 > p_x0 else 0.0
                if p_edge >= 0.025 and p_vis in (VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE):
                    p_box = _clamp_box(p_y0 / h, p_x0 / w, p_y1 / h, p_x1 / w)
                    landmarks["pocket_top_center"] = (round(cx / w, 4), round(p_y0 / h, 4))
                    record_obs("kangaroo_pocket", p_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                               min(0.88, 0.55 + p_edge * 3.0), p_box, [f"Lower abdomen pouch edge density {p_edge:.3f}."], p_occ, ["pocket_top_center"])
                elif p_vis == VisibilityState.FULLY_VISIBLE and p_edge < 0.012:
                    record_obs("kangaroo_pocket", p_vis, DetectionState.ABSENT_VERIFIED, ComponentEvidenceStatus.OBSERVED,
                               0.74, None, ["Lower front abdomen unobstructed with no pouch seam lines."], p_occ)
                else:
                    record_obs("kangaroo_pocket", p_vis, DetectionState.UNCERTAIN, ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                               0.40, None, p_r or ["Abdomen pocket contours inconclusive."], p_occ)

            if "chest_pocket" in profile.expected_components:
                ch_y0, ch_y1 = min_y + int(gh * 0.24), min_y + int(gh * 0.50)
                ch_x0, ch_x1 = torso_x0 + int(torso_half_w * 0.1), torso_x1 - int(torso_half_w * 0.1)
                ch_vis, ch_occ, ch_r = _region_visibility((ch_y0, ch_x0, ch_y1, ch_x1), (h, w), quality, fg_mask, occluder_mask)
                ch_edge = float(np.mean(edges[ch_y0:ch_y1, ch_x0:ch_x1] > 0)) if ch_y1 > ch_y0 and ch_x1 > ch_x0 else 0.0
                if ch_edge >= 0.035:
                    ch_box = _clamp_box(ch_y0 / h, ch_x0 / w, ch_y1 / h, ch_x1 / w)
                    record_obs("chest_pocket", ch_vis, DetectionState.DETECTED, ComponentEvidenceStatus.OBSERVED,
                               min(0.86, 0.52 + ch_edge * 2.5), ch_box, [f"Chest region pocket seam edge density {ch_edge:.3f}."], ch_occ)
                elif ch_vis == VisibilityState.FULLY_VISIBLE:
                    record_obs("chest_pocket", ch_vis, DetectionState.UNCERTAIN, ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                               0.42, None, ["Chest pocket contours not prominent."], ch_occ)

        # 7. Lower Hem & Waistband
        hem_px = (max(min_y, max_y - int(gh * 0.10)), torso_x0, max_y, torso_x1)
        h_vis, h_occ, h_r = _region_visibility(hem_px, (h, w), quality, fg_mask, occluder_mask)
        hem_box = _clamp_box(hem_px[0] / h, torso_x0 / w, max_y / h, torso_x1 / w)
        target_hem = "waistband" if "waistband" in profile.expected_components else "hem"
        if hem_box:
            record_obs(target_hem, h_vis, DetectionState.DETECTED if h_vis != VisibilityState.OUT_OF_FRAME else DetectionState.UNCERTAIN,
                       ComponentEvidenceStatus.OBSERVED if h_vis in (VisibilityState.FULLY_VISIBLE, VisibilityState.PARTIALLY_VISIBLE) else ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE,
                       0.87 if h_vis == VisibilityState.FULLY_VISIBLE else 0.45, hem_box,
                       h_r or ["Lower garment boundary localized."], h_occ, ["hem_center"])

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    with _CACHE_LOCK:
        _COMPONENT_CACHE[cache_key] = {
            "observations": list(observations),
            "landmarks": dict(landmarks),
            "warnings": list(warnings),
        }
        if len(_COMPONENT_CACHE) > _MAX_COMPONENT_CACHE:
            _COMPONENT_CACHE.popitem(last=False)

    return {
        "observations": observations,
        "landmarks": landmarks,
        "cache_hit": False,
        "latency_ms": latency_ms,
        "warnings": warnings,
    }


def fuse_component_observations(
    garment_id: str,
    category: str,
    subcategory: str,
    observations: List[ComponentObservation],
    view_records: List[ImageEvidenceRecord],
) -> Dict[str, FusedComponentAssessment]:
    """Fuse multi-view component observations while preserving contradictions and provenance."""
    profile = resolve_category_profile(category, subcategory)
    by_component: Dict[str, List[ComponentObservation]] = {}
    for obs in observations:
        by_component.setdefault(obs.component_id, []).append(obs)

    # Seed expected/required category components so unseen components remain explicit NOT_OBSERVED.
    for cid in profile.required_components + profile.expected_components:
        by_component.setdefault(cid, [])

    usable_independent_views = {
        v.view_type for v in view_records
        if v.usable and v.counts_as_independent_view and v.view_type != GarmentViewType.UNKNOWN.value
    }
    vis_rank = {
        VisibilityState.FULLY_VISIBLE: 5,
        VisibilityState.PARTIALLY_VISIBLE: 4,
        VisibilityState.LOW_IMAGE_QUALITY: 3,
        VisibilityState.OCCLUDED: 2,
        VisibilityState.OUT_OF_FRAME: 1,
        VisibilityState.UNKNOWN: 0,
    }

    fused: Dict[str, FusedComponentAssessment] = {}
    for cid, obs_list in sorted(by_component.items()):
        entry = COMPONENT_TAXONOMY.get(cid)
        if not entry:
            continue
        expected_views = set(entry.expected_views)
        covered_expected = len(usable_independent_views & expected_views)
        completeness = round(min(1.0, covered_expected / max(1, min(len(expected_views), 2))), 4) if usable_independent_views else 0.0

        if not obs_list:
            unc = UncertaintyBreakdown(
                total_uncertainty=1.0,
                epistemic_uncertainty=1.0,
                aleatoric_uncertainty=0.9,
                evidence_completeness=completeness,
                reasons=["No usable view produced an observation for this component."],
            )
            item = FusedComponentAssessment(
                component_id=cid,
                component_type=entry.component_type,
                parent_component=entry.parent_component,
                side_or_orientation=entry.default_side,
                garment_category=category,
                garment_subcategory=subcategory,
                detection_state=DetectionState.NOT_DETECTED,
                evidence_status=ComponentEvidenceStatus.NOT_OBSERVED,
                visibility_by_view={},
                best_visibility=VisibilityState.UNKNOWN,
                confidence=None,
                calibrated_probability=None,
                uncertainty=unc,
                evidence_completeness=completeness,
                agreement_score=1.0,
                source_image_ids=[],
                source_image_hashes=[],
                source_views=[],
                observation_ids=[],
                observations=[],
            )
            dec, rationale = decide_downstream_action(item)
            item.downstream_decision = dec
            item.decision_rationale = rationale
            fused[cid] = item
            continue

        vis_by_view: Dict[str, VisibilityState] = {}
        for obs in obs_list:
            prev = vis_by_view.get(obs.source_view)
            if prev is None or vis_rank[obs.visibility_state] > vis_rank[prev]:
                vis_by_view[obs.source_view] = obs.visibility_state
        best_vis = max(vis_by_view.values(), key=lambda v: vis_rank[v])

        detected_obs = [o for o in obs_list if o.detection_state == DetectionState.DETECTED]
        absent_obs = [o for o in obs_list if o.detection_state == DetectionState.ABSENT_VERIFIED]
        uncertain_obs = [o for o in obs_list if o.detection_state == DetectionState.UNCERTAIN]

        contradicted = False
        contradiction_notes: List[str] = []

        # Cross-view contradiction: one view detects it clearly while another view verified absent on overlapping face.
        if detected_obs and absent_obs:
            # Check if same view-face disagrees (e.g. both front, or close_up vs front)
            det_views = {o.source_view for o in detected_obs}
            abs_views = {o.source_view for o in absent_obs}
            contradicted = True
            contradiction_notes.append(
                f"Detected on {', '.join(sorted(det_views))} but verified absent on {', '.join(sorted(abs_views))}."
            )

        if contradicted:
            det_state = DetectionState.UNCERTAIN
            ev_status = ComponentEvidenceStatus.CONTRADICTED
            confs = [o.confidence for o in obs_list if o.confidence is not None]
            conf = round(max(confs), 4) if confs else None
            cal_p = round(sum(o.calibrated_probability or 0.0 for o in obs_list) / len(obs_list), 4) if confs else None
            agree = 0.0
        elif detected_obs:
            det_state = DetectionState.DETECTED
            ev_status = ComponentEvidenceStatus.OBSERVED
            confs = [o.confidence for o in detected_obs if o.confidence is not None]
            conf = round(max(confs), 4) if confs else None
            cals = [o.calibrated_probability for o in detected_obs if o.calibrated_probability is not None]
            cal_p = round(max(cals), 4) if cals else None
            agree = round(len(detected_obs) / max(1, len(detected_obs) + len(uncertain_obs)), 4)
        elif absent_obs:
            det_state = DetectionState.ABSENT_VERIFIED
            ev_status = ComponentEvidenceStatus.OBSERVED
            confs = [o.confidence for o in absent_obs if o.confidence is not None]
            conf = round(max(confs), 4) if confs else None
            cals = [o.calibrated_probability for o in absent_obs if o.calibrated_probability is not None]
            cal_p = round(max(cals), 4) if cals else None
            agree = 1.0
        elif uncertain_obs:
            det_state = DetectionState.UNCERTAIN
            ev_status = ComponentEvidenceStatus.INSUFFICIENT_EVIDENCE
            confs = [o.confidence for o in uncertain_obs if o.confidence is not None]
            conf = round(max(confs), 4) if confs else None
            cal_p = _CALIBRATOR.calibrate_probability(conf) if conf is not None else None
            agree = 0.5
        else:
            det_state = DetectionState.NOT_DETECTED
            ev_status = ComponentEvidenceStatus.NOT_OBSERVED
            conf = None
            cal_p = None
            agree = 1.0

        # Pick best localized bbox from highest-confidence detected observation
        best_det = max(detected_obs, key=lambda o: (vis_rank[o.visibility_state], o.confidence or 0.0)) if detected_obs else None
        cited_obs = detected_obs or absent_obs or obs_list
        src_ids = list(dict.fromkeys(o.source_image_id for o in cited_obs))
        src_hashes = list(dict.fromkeys(o.source_image_hash for o in cited_obs))
        src_views = list(dict.fromkeys(o.source_view for o in cited_obs))
        lm_refs = list(dict.fromkeys(lm for o in cited_obs for lm in o.landmark_refs))

        all_reasons = list(dict.fromkeys(r for o in obs_list for r in o.uncertainty.reasons)) + contradiction_notes
        unc_val = round(min(o.uncertainty.total_uncertainty for o in cited_obs), 4) if cited_obs else 1.0
        if contradicted:
            unc_val = 1.0
        fused_unc = UncertaintyBreakdown(
            total_uncertainty=unc_val,
            epistemic_uncertainty=round(min(o.uncertainty.epistemic_uncertainty for o in cited_obs), 4) if not contradicted else 1.0,
            aleatoric_uncertainty=round(min(o.uncertainty.aleatoric_uncertainty for o in cited_obs), 4),
            evidence_completeness=completeness,
            reasons=all_reasons,
        )

        item = FusedComponentAssessment(
            component_id=cid,
            component_type=entry.component_type,
            parent_component=entry.parent_component,
            side_or_orientation=entry.default_side,
            garment_category=category,
            garment_subcategory=subcategory,
            detection_state=det_state,
            evidence_status=ev_status,
            visibility_by_view=vis_by_view,
            best_visibility=best_vis,
            confidence=conf,
            calibrated_probability=cal_p,
            uncertainty=fused_unc,
            evidence_completeness=completeness,
            agreement_score=agree,
            contradicted=contradicted,
            contradiction_notes=contradiction_notes,
            source_image_ids=src_ids,
            source_image_hashes=src_hashes,
            source_views=src_views,
            observation_ids=[o.observation_id for o in obs_list],
            observations=obs_list,
            localized_bbox=best_det.bbox if best_det else None,
            segmentation_mask_ref=best_det.segmentation_mask_ref if best_det else None,
            landmark_refs=lm_refs,
        )
        dec, rationale = decide_downstream_action(item)
        item.downstream_decision = dec
        item.decision_rationale = rationale
        fused[cid] = item

    # Closure mutual-exclusivity contradiction check (front zipper vs front button_placket detected on same garment).
    if ("zipper" in fused and "button_placket" in fused
            and fused["zipper"].detection_state == DetectionState.DETECTED
            and fused["button_placket"].detection_state == DetectionState.DETECTED
            and fused["zipper"].source_views and fused["button_placket"].source_views
            and set(fused["zipper"].source_views) != set(fused["button_placket"].source_views)):
        note = "Competing front closures observed across views (zipper vs button_placket)."
        for cid in ("zipper", "button_placket"):
            fused[cid].contradicted = True
            fused[cid].evidence_status = ComponentEvidenceStatus.CONTRADICTED
            fused[cid].contradiction_notes.append(note)
            fused[cid].uncertainty.total_uncertainty = 1.0
            fused[cid].downstream_decision, fused[cid].decision_rationale = decide_downstream_action(fused[cid])

    return fused


def analyze_garment_components(
    images_input: List[Tuple[str, bytes, Optional[str]]],
    garment_id: Optional[str] = None,
    category: str = "tops",
    subcategory: str = "",
    view_records: Optional[List[ImageEvidenceRecord]] = None,
    precomputed_segmentation: Optional[Dict[str, Dict[str, Any]]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> ComponentAnalysisBundle:
    """Unified Phase 16.1 entry point analyzing garment components across uploaded images."""
    t_start = time.perf_counter()
    gid = garment_id or f"garment_{uuid.uuid4().hex[:8]}"
    if not images_input:
        raise ValueError("analyze_garment_components requires at least one image.")

    records_by_id: Dict[str, ImageEvidenceRecord] = {v.image_id: v for v in (view_records or [])}
    normalized_views: List[ImageEvidenceRecord] = list(view_records or [])
    all_observations: List[ComponentObservation] = []
    landmarks: Dict[str, Tuple[float, float]] = {}
    per_image_ms: Dict[str, float] = {}
    cache_hits = 0
    warnings: List[str] = []

    for idx, (img_id, img_bytes, hint) in enumerate(images_input):
        if cancel_event and cancel_event.is_set():
            raise TimeoutError("Garment component analysis cancelled.")
        actual_id = img_id or f"view_{idx + 1:02d}"
        img_hash = hashlib.sha256(img_bytes).hexdigest()
        rec = records_by_id.get(actual_id)
        if rec is None:
            with Image.open(io.BytesIO(img_bytes)) as pil:
                rgb = pil.convert("RGB")
                v_type, v_conf, v_feats = view_classifier.classify_view(rgb, hint)
                q = view_classifier.evaluate_quality(rgb)
            rec = ImageEvidenceRecord(
                image_id=actual_id,
                image_hash=img_hash,
                view_type=v_type.value,
                view_assignment_source="provided_hint" if hint else "heuristic",
                user_view_hint=hint,
                view_confidence=v_conf,
                quality_score=q["quality_score"],
                resolution=q["resolution"],
                usable=q["image_usable"],
                detected_features=v_feats,
                associated_garment_id=gid,
            )
            normalized_views.append(rec)
            records_by_id[actual_id] = rec

        if rec.duplicate_type in ("exact_bytes", "perceptual_near_duplicate"):
            continue

        try:
            res = _analyze_single_view_components(
                image_id=rec.image_id,
                image_hash=rec.image_hash,
                image_bytes=img_bytes,
                view_type=rec.view_type,
                garment_id=gid,
                category=category,
                subcategory=subcategory,
                precomputed_seg=(precomputed_segmentation or {}).get(rec.image_id),
                cancel_check=cancel_event.is_set if cancel_event else None,
            )
            all_observations.extend(res["observations"])
            for k, pt in res["landmarks"].items():
                landmarks.setdefault(k, pt)
            per_image_ms[rec.image_id] = res["latency_ms"]
            if res["cache_hit"]:
                cache_hits += 1
            warnings.extend(res["warnings"])
        except Exception as exc:
            warnings.append(f"Component analysis degraded on '{rec.image_id}': {type(exc).__name__}")
            logger.warning("Component analysis error on %s: %s", rec.image_id, exc)

    fused = fuse_component_observations(gid, category, subcategory, all_observations, normalized_views)
    has_back = any(
        v.usable and v.counts_as_independent_view and v.view_type == GarmentViewType.BACK.value
        for v in normalized_views
    )
    graph = build_garment_structure_graph(gid, category, subcategory, fused)
    handoff = build_component_handoff_contract(gid, category, subcategory, fused, has_back_view=has_back)

    return ComponentAnalysisBundle(
        garment_id=gid,
        category=category,
        subcategory=subcategory,
        views_analyzed=normalized_views,
        observations=all_observations,
        fused_components=fused,
        structure_graph=graph,
        handoff=handoff,
        landmarks=landmarks,
        per_image_timing_ms=per_image_ms,
        total_latency_ms=round((time.perf_counter() - t_start) * 1000.0, 2),
        cache_hits=cache_hits,
        warnings=warnings,
    )
