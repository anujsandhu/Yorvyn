"""
YORVYN Intelligence Platform (YIP) — Phase 17.5 Guided Live Garment Capture & Reconstruction Readiness.

Provides:
- Capture modes (hanger, mannequin, flat_lay, worn) with mode-specific instructions & honest disclosures
- Category-adaptive multi-view checklists (never forces all 12 views unnecessarily)
- Real CV-measured image quality intelligence (sharpness, exposure, garment_visibility, framing,
  occlusion, background_quality, view_confidence) with zero fabricated confidence scores
- Single prioritized plain-English corrective instruction per frame/image
- Multi-view consistency validation (SHA-256 duplicates, perceptual dHash, dominant color & category match)
- Server-authoritative Reconstruction Readiness Gate (never trusts client scores)
- Owner-isolated capture sessions with EXIF stripping, retention expiry & idempotent durable job handoff
"""
from __future__ import annotations

import hashlib
import io
import logging
import threading
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from backend.app.services.ai.multiview.view_classifier import GarmentViewType, ViewClassifier, view_classifier
from backend.app.services.garments.job_manager import garment_job_manager
from backend.app.services.intelligence.recommendation_taxonomy import normalize_category_and_subcategory
from backend.app.services.ml.model_registry import unified_model_registry

logger = logging.getLogger(__name__)

CAPTURE_SCHEMA_VERSION = "17.5.0"
MAX_CAPTURE_IMAGE_BYTES = 15 * 1024 * 1024
MIN_CAPTURE_IMAGE_BYTES = 1024
SESSION_RETENTION_SECONDS = 3600.0


class CaptureMode(str, Enum):
    HANGER = "hanger"
    MANNEQUIN = "mannequin"
    FLAT_LAY = "flat_lay"
    WORN = "worn"


class EvidenceState(str, Enum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNVERIFIED = "UNVERIFIED"


class SessionStatus(str, Enum):
    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    NEEDS_MORE_IMAGES = "NEEDS_MORE_IMAGES"
    RETAKE_REQUIRED = "RETAKE_REQUIRED"
    RECONSTRUCTION_UNSUPPORTED = "RECONSTRUCTION_UNSUPPORTED"


class ReadinessOutcome(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_LIMITATIONS = "APPROVED_WITH_LIMITATIONS"
    MORE_EVIDENCE_REQUIRED = "MORE_EVIDENCE_REQUIRED"
    RETAKE_REQUIRED = "RETAKE_REQUIRED"
    UNSUPPORTED_CATEGORY = "UNSUPPORTED_CATEGORY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RECONSTRUCTION_BLOCKED = "RECONSTRUCTION_BLOCKED"


SUPPORTED_CAPTURE_CATEGORIES: Set[str] = {
    "tops", "bottoms", "outerwear", "dresses_and_skirts", "footwear", "accessories", "traditional",
}

CAPTURE_MODE_GUIDANCE: Dict[CaptureMode, Dict[str, Any]] = {
    CaptureMode.HANGER: {
        "title": "Hanger Mode",
        "instructions": [
            "Hang the garment on a suitable hanger.",
            "Ensure the garment is fully visible from shoulders to hem.",
            "Keep the hanger from covering important collar or shoulder regions.",
            "Use a plain background and spread sleeves naturally.",
            "Avoid deep folds or overlapping objects.",
        ],
        "disclosure": "Hanger geometry is excluded; lower drape reflects natural hanging gravity.",
    },
    CaptureMode.MANNEQUIN: {
        "title": "Mannequin Mode",
        "instructions": [
            "Position the mannequin upright on a plain background.",
            "Ensure the garment fits naturally without clips hiding seams.",
            "Capture the front, back, and both sides clearly.",
            "Keep accessories and mannequin arms from obstructing garment edges.",
        ],
        "disclosure": "Mannequin silhouette aids 3D volume estimation; internal seam allowances remain inferred.",
    },
    CaptureMode.FLAT_LAY: {
        "title": "Flat-Lay Mode",
        "instructions": [
            "Place the garment on a clean, flat, high-contrast surface.",
            "Spread sleeves and hems naturally without overlapping folds.",
            "Keep the complete garment outline inside the guide.",
            "Avoid strong directional shadows and capture both front and reverse sides.",
        ],
        "disclosure": "Flat-lay images lack true 3D side depth and are NOT equivalent to full 3D multi-view captures.",
    },
    CaptureMode.WORN: {
        "title": "Worn-Garment Mode",
        "instructions": [
            "Wear the garment naturally and stand in a neutral posture.",
            "Keep arms slightly away from the torso so side seams are visible.",
            "Avoid poses, hair, or bags that hide garment boundaries.",
            "Capture front, back, and side views while framing only the garment (avoid unnecessary face capture).",
        ],
        "disclosure": "Body shape, posture, and garment-body interaction influence reconstruction; worn photos do not yield manufacturing-grade geometry.",
    },
}

CATEGORY_VIEW_CHECKLISTS: Dict[str, Dict[str, List[str]]] = {
    "tops": {
        "required": ["front", "back"],
        "recommended": ["left_side", "right_side", "collar_detail", "sleeve_detail", "hem_detail", "texture_closeup"],
    },
    "bottoms": {
        "required": ["front", "back"],
        "recommended": ["left_side", "right_side", "hem_detail", "texture_closeup"],
    },
    "outerwear": {
        "required": ["front", "back"],
        "recommended": ["left_side", "right_side", "collar_detail", "sleeve_detail", "hem_detail", "texture_closeup"],
    },
    "dresses_and_skirts": {
        "required": ["front", "back"],
        "recommended": ["left_side", "right_side", "collar_detail", "hem_detail", "texture_closeup"],
    },
    "footwear": {
        "required": ["front", "left_side", "right_side"],
        "recommended": ["back", "texture_closeup"],
    },
    "accessories": {
        "required": ["front"],
        "recommended": ["back", "left_side", "texture_closeup"],
    },
    "traditional": {
        "required": ["front", "back"],
        "recommended": ["left_side", "right_side", "hem_detail", "texture_closeup"],
    },
}


class CaptureQualityReport(BaseModel):
    sharpness: float
    exposure: float
    garment_visibility: float
    framing: float
    occlusion: float
    background_quality: float
    view_confidence: float
    usable: bool
    primary_issue: Optional[str] = None
    corrective_instruction: Optional[str] = None
    metrics_detail: Dict[str, Any] = Field(default_factory=dict)


class CapturedViewRecord(BaseModel):
    image_id: str
    view_label: str
    detected_view: str
    view_confidence: float
    image_hash: str
    perceptual_hash: str
    width: int
    height: int
    byte_size: int
    dominant_rgb: Tuple[int, int, int]
    captured_at: float
    quality: CaptureQualityReport
    evidence_state: EvidenceState


class MultiViewConsistencyReport(BaseModel):
    consistent: bool
    evidence_state: EvidenceState
    duplicate_pairs: List[Tuple[str, str, str]] = Field(default_factory=list)
    color_spread: float = 0.0
    contradictions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ReadinessEvaluation(BaseModel):
    outcome: ReadinessOutcome
    session_status: SessionStatus
    can_reconstruct: bool
    summary_reason: str
    required_views: List[str] = Field(default_factory=list)
    observed_views: List[str] = Field(default_factory=list)
    missing_required_views: List[str] = Field(default_factory=list)
    missing_recommended_views: List[str] = Field(default_factory=list)
    evidence_states: Dict[str, EvidenceState] = Field(default_factory=dict)
    model_compatibility: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    next_instruction: Optional[str] = None


class CaptureSessionRecord(BaseModel):
    schema_version: str = CAPTURE_SCHEMA_VERSION
    session_id: str
    session_version: int = 1
    owner_id: str
    garment_category: str
    garment_subcategory: str = ""
    capture_mode: CaptureMode
    consent_granted: bool = True
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    retention_expires_at: float = Field(default_factory=lambda: time.time() + SESSION_RETENTION_SECONDS)
    frozen: bool = False
    cancelled: bool = False
    handoff_job_id: Optional[str] = None
    images: List[CapturedViewRecord] = Field(default_factory=list)
    consistency: Optional[MultiViewConsistencyReport] = None
    readiness: Optional[ReadinessEvaluation] = None
    mode_instructions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


def _normalize_capture_category(raw_cat: str, raw_sub: str = "") -> Tuple[str, str]:
    cat_l = (raw_cat or "tops").strip().lower()
    alias = {
        "top": "tops",
        "bottom": "bottoms",
        "jacket": "outerwear",
        "coat": "outerwear",
        "dress": "dresses_and_skirts",
        "skirt": "dresses_and_skirts",
    }.get(cat_l, cat_l)
    return normalize_category_and_subcategory(alias, raw_sub)


def evaluate_capture_image_quality(
    image: Image.Image,
    *,
    expected_view: Optional[str] = None,
    classifier: Optional[ViewClassifier] = None,
) -> Tuple[CaptureQualityReport, str, float, Tuple[int, int, int]]:
    """
    Computes genuine pixel/contour-based capture quality measurements (never fabricated).
    Returns (CaptureQualityReport, detected_view, view_confidence, dominant_rgb).
    """
    vc = classifier or view_classifier
    rgb = image.convert("RGB")
    w, h = rgb.size
    arr = np.asarray(rgb, dtype=np.float32)
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)

    # 1. Sharpness (high-pass residual variance / edge clarity)
    blurred = np.asarray(rgb.convert("L").filter(ImageFilter.BoxBlur(1)), dtype=np.float32)
    lap_mean = float(np.mean(np.abs(gray - blurred)))
    sharpness = float(min(1.0, max(0.0, lap_mean / 12.0)))

    # 2. Exposure & uneven lighting
    mean_luma = float(np.mean(gray))
    under_frac = float(np.mean(gray < 28.0))
    over_frac = float(np.mean(gray > 240.0))
    q_means = [
        float(np.mean(gray[: h // 2, : w // 2])),
        float(np.mean(gray[: h // 2, w // 2 :])),
        float(np.mean(gray[h // 2 :, : w // 2])),
        float(np.mean(gray[h // 2 :, w // 2 :])),
    ]
    illum_spread = float(max(q_means) - min(q_means))
    exp_penalty = 0.0
    if mean_luma < 55.0:
        exp_penalty += (55.0 - mean_luma) / 55.0
    elif mean_luma > 215.0:
        exp_penalty += (mean_luma - 215.0) / 40.0
    if under_frac > 0.45:
        exp_penalty += 0.35
    if over_frac > 0.35:
        exp_penalty += 0.35
    exposure = float(min(1.0, max(0.0, 1.0 - exp_penalty)))

    # 3. Foreground vs border background separation & framing
    b = max(4, min(w, h) // 16)
    border_pixels = np.concatenate([
        arr[:b, :, :].reshape(-1, 3),
        arr[-b:, :, :].reshape(-1, 3),
        arr[:, :b, :].reshape(-1, 3),
        arr[:, -b:, :].reshape(-1, 3),
    ], axis=0)
    bg_rgb = np.median(border_pixels, axis=0)
    bg_std = float(np.mean(np.std(border_pixels, axis=0)))
    color_dist = np.linalg.norm(arr - bg_rgb.reshape(1, 1, 3), axis=2)
    fg_mask = color_dist > max(22.0, bg_std * 1.15)
    fg_ratio = float(np.mean(fg_mask))

    # Dominant RGB inside foreground (or center crop fallback)
    if np.sum(fg_mask) >= 100:
        dom_arr = np.median(arr[fg_mask], axis=0)
    else:
        cy0, cy1 = h // 4, (3 * h) // 4
        cx0, cx1 = w // 4, (3 * w) // 4
        dom_arr = np.median(arr[cy0:cy1, cx0:cx1, :].reshape(-1, 3), axis=0)
    dominant_rgb = (int(dom_arr[0]), int(dom_arr[1]), int(dom_arr[2]))

    # Check boundary clipping (top/bottom/left/right edge touch ratios)
    top_touch = float(np.mean(fg_mask[: max(2, h // 40), :]))
    bot_touch = float(np.mean(fg_mask[-max(2, h // 40) :, :]))
    left_touch = float(np.mean(fg_mask[:, : max(2, w // 40)]))
    right_touch = float(np.mean(fg_mask[:, -max(2, w // 40) :]))

    # Check horizontal dual-cluster split heuristic (multiple overlapping garments side-by-side)
    col_fg = np.mean(fg_mask[h // 5 : (4 * h) // 5, :], axis=0)
    left_peak = float(np.max(col_fg[: w // 3])) if w >= 12 else 0.0
    mid_valley = float(np.min(col_fg[w // 3 : (2 * w) // 3])) if w >= 12 else 1.0
    right_peak = float(np.max(col_fg[(2 * w) // 3 :])) if w >= 12 else 0.0
    multi_garment_suspected = bool(left_peak > 0.35 and right_peak > 0.35 and mid_valley < 0.05 and fg_ratio > 0.15)

    # Visibility & framing scores
    if fg_ratio < 0.06:
        garment_visibility = round(fg_ratio / 0.06 * 0.4, 3)
    elif fg_ratio > 0.88:
        garment_visibility = round(max(0.25, 1.0 - (fg_ratio - 0.88) * 4.0), 3)
    else:
        garment_visibility = round(min(1.0, 0.55 + min(fg_ratio, 0.65) * 0.7), 3)

    clip_max = max(top_touch, bot_touch, left_touch, right_touch)
    framing_penalty = 0.0
    if bot_touch > 0.35 or top_touch > 0.40 or left_touch > 0.40 or right_touch > 0.40:
        framing_penalty += 0.45
    if fg_ratio < 0.08:
        framing_penalty += 0.40
    if w < 224 or h < 224:
        framing_penalty += 0.35
    framing = float(min(1.0, max(0.0, 1.0 - framing_penalty)))

    # Background quality & occlusion proxy
    bg_clutter = min(1.0, bg_std / 65.0)
    fg_bg_sep = float(np.mean(color_dist[fg_mask])) / 110.0 if np.any(fg_mask) else 0.0
    background_quality = round(min(1.0, max(0.0, 0.65 * (1.0 - bg_clutter) + 0.35 * min(1.0, fg_bg_sep))), 3)

    interior_contrast = float(np.std(gray[fg_mask])) if np.sum(fg_mask) >= 50 else float(np.std(gray))
    fold_or_occlusion_risk = 0.35 if (interior_contrast > 68.0 and fg_ratio > 0.12) else 0.05
    if multi_garment_suspected:
        fold_or_occlusion_risk = max(fold_or_occlusion_risk, 0.55)
    occlusion = round(max(0.0, 1.0 - fold_or_occlusion_risk), 3)

    detected_view_enum, view_conf, _ = vc.classify_view(rgb, user_hint=expected_view)
    detected_view = detected_view_enum.value

    # Single prioritized plain-English corrective instruction (never contradictory)
    primary_issue: Optional[str] = None
    instruction: Optional[str] = None
    if w < 128 or h < 128:
        primary_issue = "low_resolution"
        instruction = "Use a higher-resolution photo or move closer so garment details remain clear."
    elif exposure < 0.42:
        primary_issue = "poor_lighting"
        if mean_luma > 215.0 or over_frac > 0.35:
            instruction = "Reduce direct glare or bright light. Overexposed areas are washing out fabric details."
        else:
            instruction = "Increase the lighting or move closer to a well-lit area. Dark regions are hiding garment details."
    elif sharpness < 0.22:
        primary_issue = "blur_detected"
        instruction = "Hold your camera steady and wait for it to focus before capturing."
    elif bot_touch > 0.35:
        primary_issue = "bottom_cut_off"
        instruction = "Move the camera slightly farther away. The bottom of your garment is outside the frame."
    elif top_touch > 0.40 or left_touch > 0.40 or right_touch > 0.40:
        primary_issue = "garment_cut_off"
        instruction = "Center the garment and step back slightly so all edges fit inside the guide."
    elif fg_ratio < 0.06:
        primary_issue = "garment_not_visible"
        instruction = "Move closer to the garment or use a plain contrasting background so the outline is clear."
    elif multi_garment_suspected:
        primary_issue = "multiple_garments"
        instruction = "Capture one garment at a time. Other garments may confuse the reconstruction process."
    elif expected_view and expected_view not in {"detail", "close_up", "texture_closeup"} and detected_view != "unknown":
        # Soft check only when front vs back or side strongly disagrees without matching hint
        if expected_view == "back" and detected_view == "front" and view_conf >= 0.72:
            primary_issue = "wrong_view_angle"
            instruction = "Move the camera toward the back of the garment. We still need a clear rear view."
    elif background_quality < 0.30:
        primary_issue = "cluttered_background"
        instruction = "Use a cleaner, plain background with good contrast against the garment color."

    usable = primary_issue not in {"low_resolution", "poor_lighting", "blur_detected", "garment_not_visible", "bottom_cut_off", "garment_cut_off", "multiple_garments"}
    report = CaptureQualityReport(
        sharpness=round(sharpness, 3),
        exposure=round(exposure, 3),
        garment_visibility=garment_visibility,
        framing=round(framing, 3),
        occlusion=occlusion,
        background_quality=background_quality,
        view_confidence=round(float(view_conf), 3),
        usable=usable,
        primary_issue=primary_issue,
        corrective_instruction=instruction,
        metrics_detail={
            "mean_luma": round(mean_luma, 1),
            "fg_ratio": round(fg_ratio, 3),
            "illum_spread": round(illum_spread, 1),
            "clip_max_edge": round(clip_max, 3),
            "bg_std": round(bg_std, 1),
            "interior_contrast": round(interior_contrast, 1),
        },
    )
    return report, detected_view, float(view_conf), dominant_rgb


class CaptureSessionStore:
    """Owner-isolated manager for Phase 17.5 Guided Live Garment Capture sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: Dict[str, CaptureSessionRecord] = {}
        self._image_bytes: Dict[Tuple[str, str], bytes] = {}  # (session_id, image_id) -> bytes
        self._handoff_idem: Dict[str, str] = {}  # (owner_id:session_id:version) -> job_id

    def purge_expired_sessions(self) -> int:
        now = time.time()
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if now > s.retention_expires_at]
            for sid in expired:
                self._purge_session_unlocked(sid)
            return len(expired)

    def _purge_session_unlocked(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        keys = [k for k in self._image_bytes if k[0] == session_id]
        for k in keys:
            self._image_bytes.pop(k, None)

    def create_session(
        self,
        *,
        owner_id: str,
        garment_category: str,
        garment_subcategory: str = "",
        capture_mode: CaptureMode = CaptureMode.HANGER,
        consent_granted: bool = True,
    ) -> CaptureSessionRecord:
        self.purge_expired_sessions()
        norm_cat, norm_sub = _normalize_capture_category(garment_category, garment_subcategory)
        mode_meta = CAPTURE_MODE_GUIDANCE[capture_mode]
        sid = f"cap_{uuid.uuid4().hex[:12]}"
        rec = CaptureSessionRecord(
            session_id=sid,
            owner_id=str(owner_id),
            garment_category=norm_cat,
            garment_subcategory=norm_sub,
            capture_mode=capture_mode,
            consent_granted=bool(consent_granted),
            mode_instructions=list(mode_meta["instructions"]),
            limitations=[mode_meta["disclosure"]],
        )
        with self._lock:
            self._sessions[sid] = rec
        rec.readiness = self.evaluate_readiness(session_id=sid, owner_id=owner_id)
        return rec

    def get_session(self, *, session_id: str, owner_id: str) -> CaptureSessionRecord:
        with self._lock:
            rec = self._sessions.get(session_id)
            if rec is None:
                raise KeyError(f"Capture session '{session_id}' not found.")
            if rec.owner_id != str(owner_id):
                raise PermissionError(f"Owner '{owner_id}' cannot access capture session '{session_id}'.")
            return rec.model_copy(deep=True)

    def add_captured_image(
        self,
        *,
        session_id: str,
        owner_id: str,
        image_bytes: bytes,
        view_label: str,
        filename: Optional[str] = None,
    ) -> CapturedViewRecord:
        if not image_bytes or len(image_bytes) < MIN_CAPTURE_IMAGE_BYTES:
            raise ValueError("Captured image is empty or smaller than 1024 bytes.")
        if len(image_bytes) > MAX_CAPTURE_IMAGE_BYTES:
            raise ValueError("Captured image exceeds 15MB limit.")

        # Decode cleanly and strip sensitive EXIF metadata while preserving orientation
        try:
            with Image.open(io.BytesIO(image_bytes)) as raw_img:
                fmt = (raw_img.format or "").upper()
                if fmt not in {"JPEG", "JPG", "PNG", "WEBP"}:
                    raise ValueError(f"Unsupported image format '{fmt or 'unknown'}'.")
                clean_img = ImageOps.exif_transpose(raw_img).convert("RGB")
                buf = io.BytesIO()
                clean_img.save(buf, format="WEBP", quality=90)
                sanitized_bytes = buf.getvalue()
                w, h = clean_img.size
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Invalid or corrupted image bytes: {type(exc).__name__}") from exc

        img_hash = ViewClassifier.compute_image_hash(sanitized_bytes)
        phash = view_classifier.compute_perceptual_hash(clean_img)
        quality, det_view, v_conf, dom_rgb = evaluate_capture_image_quality(
            clean_img, expected_view=view_label
        )
        ev_state = EvidenceState.OBSERVED if quality.usable else EvidenceState.INSUFFICIENT_EVIDENCE
        norm_label = (view_label or "front").strip().lower()

        with self._lock:
            rec = self._sessions.get(session_id)
            if rec is None:
                raise KeyError(f"Capture session '{session_id}' not found.")
            if rec.owner_id != str(owner_id):
                raise PermissionError(f"Owner '{owner_id}' cannot modify capture session '{session_id}'.")
            if rec.cancelled:
                raise ValueError("Cannot add images to a cancelled capture session.")
            if rec.frozen:
                raise ValueError("Capture session is frozen after finalization; start a new session version.")

            # Replace existing image for the same view slot if retaking, or append cleanly
            rec.images = [im for im in rec.images if im.view_label != norm_label]
            iid = f"img_{uuid.uuid4().hex[:8]}"
            view_rec = CapturedViewRecord(
                image_id=iid,
                view_label=norm_label,
                detected_view=det_view,
                view_confidence=round(v_conf, 3),
                image_hash=img_hash,
                perceptual_hash=phash,
                width=w,
                height=h,
                byte_size=len(sanitized_bytes),
                dominant_rgb=dom_rgb,
                captured_at=time.time(),
                quality=quality,
                evidence_state=ev_state,
            )
            rec.images.append(view_rec)
            rec.session_version += 1
            rec.updated_at = time.time()
            self._image_bytes[(session_id, iid)] = sanitized_bytes
            return view_rec

    def remove_captured_image(self, *, session_id: str, owner_id: str, image_id: str) -> CaptureSessionRecord:
        with self._lock:
            rec = self._sessions.get(session_id)
            if rec is None:
                raise KeyError(f"Capture session '{session_id}' not found.")
            if rec.owner_id != str(owner_id):
                raise PermissionError(f"Owner '{owner_id}' cannot modify capture session '{session_id}'.")
            if rec.frozen:
                raise ValueError("Cannot remove images from a frozen capture session.")
            rec.images = [im for im in rec.images if im.image_id != image_id]
            self._image_bytes.pop((session_id, image_id), None)
            rec.session_version += 1
            rec.updated_at = time.time()
            return rec.model_copy(deep=True)

    def validate_multiview_consistency(self, *, session_id: str, owner_id: str) -> MultiViewConsistencyReport:
        rec = self.get_session(session_id=session_id, owner_id=owner_id)
        if not rec.images:
            rep = MultiViewConsistencyReport(
                consistent=False,
                evidence_state=EvidenceState.NOT_OBSERVED,
                warnings=["No images captured yet."],
            )
        else:
            dups: List[Tuple[str, str, str]] = []
            contradictions: List[str] = []
            warnings: List[str] = []
            for i in range(len(rec.images)):
                for j in range(i + 1, len(rec.images)):
                    a, b = rec.images[i], rec.images[j]
                    if a.image_hash == b.image_hash:
                        dups.append((a.view_label, b.view_label, "exact_duplicate"))
                    else:
                        ham = bin(int(a.perceptual_hash, 16) ^ int(b.perceptual_hash, 16)).count("1")
                        if ham <= 2:
                            dups.append((a.view_label, b.view_label, "near_duplicate"))

            # Dominant color consistency across primary views (front/back/left_side/right_side)
            primary = [
                im for im in rec.images
                if im.view_label in {"front", "back", "left_side", "right_side", "front_left_3q", "front_right_3q"}
            ]
            color_spread = 0.0
            if len(primary) >= 2:
                rgbs = [np.asarray(im.dominant_rgb, dtype=np.float32) for im in primary]
                dists = [
                    float(np.linalg.norm(rgbs[i] - rgbs[j]))
                    for i in range(len(rgbs))
                    for j in range(i + 1, len(rgbs))
                ]
                color_spread = round(max(dists), 2) if dists else 0.0
                if color_spread > 155.0:
                    contradictions.append(
                        f"Dominant garment color diverges sharply across views (RGB distance {color_spread:.1f} > 155); verify all photos depict the same garment."
                    )

            if dups:
                warnings.append(
                    f"Duplicate or near-identical views detected ({dups[0][0]} & {dups[0][1]}); retake from distinct angles."
                )

            consistent = (len(contradictions) == 0) and (len(dups) == 0)
            ev_state = (
                EvidenceState.CONTRADICTED
                if contradictions
                else (EvidenceState.OBSERVED if consistent else EvidenceState.INSUFFICIENT_EVIDENCE)
            )
            rep = MultiViewConsistencyReport(
                consistent=consistent,
                evidence_state=ev_state,
                duplicate_pairs=dups,
                color_spread=color_spread,
                contradictions=contradictions,
                warnings=warnings,
            )

        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].consistency = rep
        return rep

    def evaluate_readiness(self, *, session_id: str, owner_id: str) -> ReadinessEvaluation:
        rec = self.get_session(session_id=session_id, owner_id=owner_id)
        consistency = self.validate_multiview_consistency(session_id=session_id, owner_id=owner_id)

        if rec.garment_category not in SUPPORTED_CAPTURE_CATEGORIES:
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.UNSUPPORTED_CATEGORY,
                session_status=SessionStatus.RECONSTRUCTION_UNSUPPORTED,
                can_reconstruct=False,
                summary_reason=f"Garment category '{rec.garment_category}' is not supported by the reconstruction pipeline.",
            )
            with self._lock:
                self._sessions[session_id].readiness = ev
            return ev

        # Check required model availability from UnifiedModelRegistry cleanly
        catalog = {m.model_id: m for m in unified_model_registry.get_yip_model_catalog()}
        clf = catalog.get("universal-garment-classifier")
        seg = catalog.get("human_parsing_segformer_b2")
        xat = catalog.get("xatlas_unwrapper")
        model_compat = {
            "classifier_available": bool(clf and clf.availability == "AVAILABLE"),
            "segmenter_available": bool(seg and seg.availability == "AVAILABLE"),
            "uv_unwrapper_available": bool(xat and xat.availability == "AVAILABLE"),
            "remote_neural_3d_available": False,  # Honest local procedural/image-conditioned status
        }
        if not model_compat["classifier_available"]:
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.MODEL_UNAVAILABLE,
                session_status=SessionStatus.RECONSTRUCTION_UNSUPPORTED,
                can_reconstruct=False,
                summary_reason="Required local garment classifier checkpoint is unavailable.",
                model_compatibility=model_compat,
            )
            with self._lock:
                self._sessions[session_id].readiness = ev
            return ev

        checklist = CATEGORY_VIEW_CHECKLISTS.get(rec.garment_category, CATEGORY_VIEW_CHECKLISTS["tops"])
        required_views = list(checklist["required"])
        recommended_views = list(checklist["recommended"])

        by_view = {im.view_label: im for im in rec.images}
        usable_views = {im.view_label for im in rec.images if im.quality.usable}
        unusable = [im for im in rec.images if not im.quality.usable]

        missing_req = [v for v in required_views if v not in usable_views]
        missing_rec = [v for v in recommended_views if v not in usable_views]
        evidence_states: Dict[str, EvidenceState] = {}
        for v in required_views + recommended_views:
            if v in by_view:
                evidence_states[v] = by_view[v].evidence_state
            else:
                evidence_states[v] = EvidenceState.NOT_OBSERVED

        limitations = list(rec.limitations)
        if rec.capture_mode == CaptureMode.FLAT_LAY:
            limitations.append("Flat-lay capture cannot observe true 3D side volume; side profile will be procedurally estimated.")
        if missing_rec:
            limitations.append(f"Optional views not captured ({', '.join(missing_rec[:4])}); fine details may be inferred.")

        # Priority gate decisions (never hides critical defects behind average scores)
        if unusable:
            bad = unusable[0]
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.RETAKE_REQUIRED,
                session_status=SessionStatus.RETAKE_REQUIRED,
                can_reconstruct=False,
                summary_reason=f"View '{bad.view_label}' failed quality verification ({bad.quality.primary_issue}).",
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=missing_req,
                missing_recommended_views=missing_rec,
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=limitations,
                next_instruction=bad.quality.corrective_instruction or f"Retake the '{bad.view_label}' photo clearly.",
            )
        elif consistency.contradictions:
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.RETAKE_REQUIRED,
                session_status=SessionStatus.RETAKE_REQUIRED,
                can_reconstruct=False,
                summary_reason=consistency.contradictions[0],
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=missing_req,
                missing_recommended_views=missing_rec,
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=limitations,
                next_instruction="Retake mismatched views so all angles depict the same garment.",
            )
        elif consistency.duplicate_pairs:
            d0, d1, _ = consistency.duplicate_pairs[0]
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.RETAKE_REQUIRED,
                session_status=SessionStatus.RETAKE_REQUIRED,
                can_reconstruct=False,
                summary_reason=f"Views '{d0}' and '{d1}' are duplicates and do not provide independent angles.",
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=missing_req,
                missing_recommended_views=missing_rec,
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=limitations,
                next_instruction=f"Retake '{d1}' from its actual angle instead of reusing '{d0}'.",
            )
        elif missing_req:
            next_v = missing_req[0]
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.MORE_EVIDENCE_REQUIRED,
                session_status=SessionStatus.NEEDS_MORE_IMAGES,
                can_reconstruct=False,
                summary_reason=f"Missing required view(s) for {rec.garment_category}: {', '.join(missing_req)}.",
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=missing_req,
                missing_recommended_views=missing_rec,
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=limitations,
                next_instruction=f"Capture a clear '{next_v.replace('_', ' ')}' view of the garment.",
            )
        elif limitations:
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.APPROVED_WITH_LIMITATIONS,
                session_status=SessionStatus.READY_WITH_LIMITATIONS,
                can_reconstruct=True,
                summary_reason="Required views verified; reconstruction approved with documented limitations.",
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=[],
                missing_recommended_views=missing_rec,
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=limitations,
                next_instruction="Ready to generate 3D garment, or capture optional detail angles for higher fidelity.",
            )
        else:
            ev = ReadinessEvaluation(
                outcome=ReadinessOutcome.APPROVED,
                session_status=SessionStatus.READY,
                can_reconstruct=True,
                summary_reason="All required and recommended views verified cleanly.",
                required_views=required_views,
                observed_views=sorted(usable_views),
                missing_required_views=[],
                missing_recommended_views=[],
                evidence_states=evidence_states,
                model_compatibility=model_compat,
                limitations=[],
                next_instruction="Ready to generate 3D garment.",
            )

        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].readiness = ev
        return ev

    def finalize_and_handoff(
        self,
        *,
        session_id: str,
        owner_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Freezes verified capture evidence and creates an idempotent durable reconstruction job."""
        rec = self.get_session(session_id=session_id, owner_id=owner_id)
        if rec.cancelled:
            raise ValueError("Cannot finalize a cancelled capture session.")
        if rec.handoff_job_id:
            return {
                "session_id": rec.session_id,
                "session_version": rec.session_version,
                "frozen": True,
                "job_id": rec.handoff_job_id,
                "readiness": rec.readiness.model_dump() if rec.readiness else None,
                "idempotent_reuse": True,
            }

        readiness = self.evaluate_readiness(session_id=session_id, owner_id=owner_id)
        if not readiness.can_reconstruct:
            raise ValueError(
                f"Reconstruction blocked ({readiness.outcome.value}): {readiness.summary_reason}"
            )

        with self._lock:
            live = self._sessions.get(session_id)
            if live is None:
                raise KeyError(f"Capture session '{session_id}' not found.")
            if live.handoff_job_id:
                return {
                    "session_id": live.session_id,
                    "session_version": live.session_version,
                    "frozen": True,
                    "job_id": live.handoff_job_id,
                    "readiness": readiness.model_dump(),
                    "idempotent_reuse": True,
                }

            by_view = {im.view_label: im for im in live.images}
            front_rec = by_view.get("front") or live.images[0]
            back_rec = by_view.get("back")
            side_rec = by_view.get("left_side") or by_view.get("right_side")
            detail_rec = by_view.get("texture_closeup") or by_view.get("collar_detail") or by_view.get("hem_detail")

            front_bytes = self._image_bytes.get((session_id, front_rec.image_id))
            if not front_bytes:
                raise ValueError("Missing verified front image bytes for reconstruction handoff.")
            # Verify cryptographic integrity before handoff
            if ViewClassifier.compute_image_hash(front_bytes) != front_rec.image_hash:
                raise ValueError("Image hash integrity check failed prior to reconstruction handoff.")

            back_bytes = self._image_bytes.get((session_id, back_rec.image_id)) if back_rec else None
            side_bytes = self._image_bytes.get((session_id, side_rec.image_id)) if side_rec else None
            detail_bytes = self._image_bytes.get((session_id, detail_rec.image_id)) if detail_rec else None

            eff_idem = idempotency_key or f"cap_{session_id}_v{live.session_version}"
            evidence_bundle = {
                "capture_session_id": live.session_id,
                "capture_session_version": live.session_version,
                "capture_mode": live.capture_mode.value,
                "readiness_outcome": readiness.outcome.value,
                "observed_views": readiness.observed_views,
                "missing_views": readiness.missing_recommended_views,
                "image_hashes": {im.view_label: im.image_hash for im in live.images},
                "limitations": readiness.limitations,
            }

            job = garment_job_manager.create_job(
                user_id=str(owner_id),
                front_image_bytes=front_bytes,
                category=live.garment_category,
                subcategory=live.garment_subcategory or None,
                back_image_bytes=back_bytes,
                side_image_bytes=side_bytes,
                detail_image_bytes=detail_bytes,
                detection_metadata=evidence_bundle,
                idempotency_key=eff_idem,
            )
            live.frozen = True
            live.handoff_job_id = job.job_id
            live.updated_at = time.time()

            return {
                "session_id": live.session_id,
                "session_version": live.session_version,
                "frozen": True,
                "job_id": job.job_id,
                "job_status": job.status,
                "readiness": readiness.model_dump(),
                "limitations": readiness.limitations,
                "idempotent_reuse": False,
            }

    def cancel_and_purge_session(self, *, session_id: str, owner_id: str) -> Dict[str, Any]:
        with self._lock:
            rec = self._sessions.get(session_id)
            if rec is None:
                raise KeyError(f"Capture session '{session_id}' not found.")
            if rec.owner_id != str(owner_id):
                raise PermissionError(f"Owner '{owner_id}' cannot delete capture session '{session_id}'.")
            rec.cancelled = True
            self._purge_session_unlocked(session_id)
            return {"session_id": session_id, "deleted": True}


capture_session_store = CaptureSessionStore()
