"""
YORVYN Intelligence Platform (YIP) — Unified Multimodal AI Engine (Phase 17.0 Stage 2).

Coordinates visual, textual, and cross-modal understanding without duplicating
existing Phase 16 classifiers, segmenters, or multi-view fusion engines. Every output
carries model identity, version, source, confidence, and explicit limitations.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.intelligence.inference_adapters import (
    HardwareSelector,
    inference_telemetry,
)
from backend.app.services.ml.model_registry import unified_model_registry


class ModelReceipt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model_id: str
    version: str
    source: str
    device: str = "cpu"
    confidence: Optional[float] = None
    latency_ms: float = 0.0
    limitations: str = ""
    executed: bool = True


class TextUnderstandingResult(BaseModel):
    instruction: str
    intent: str
    ambiguity_detected: bool = False
    ambiguity_reasons: List[str] = Field(default_factory=list)
    requested_action: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    construction_terms: List[str] = Field(default_factory=list)
    measurement_targets_cm: Dict[str, float] = Field(default_factory=dict)
    model_receipt: ModelReceipt


class ImageQualityReport(BaseModel):
    width: int
    height: int
    sharpness_laplacian: float
    mean_brightness: float
    foreground_coverage_ratio: float
    view_orientation_hint: str
    occlusion_risk: str
    usable: bool
    issues: List[str] = Field(default_factory=list)


class VisualUnderstandingResult(BaseModel):
    image_sha256: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    category_confidence: Optional[float] = None
    primary_color: str = "unknown"
    palette_hex: List[str] = Field(default_factory=list)
    silhouette_aspect_ratio: float = 1.0
    pattern_cues: List[str] = Field(default_factory=list)
    embedding_available: bool = False
    embedding_dim: int = 0
    embedding_sha256: Optional[str] = None
    embedding_vector: Optional[List[float]] = None
    quality: ImageQualityReport
    receipts: List[ModelReceipt] = Field(default_factory=list)


class CrossModalMatch(BaseModel):
    item_id: str
    similarity_score: float
    method: str
    similarity_does_not_certify_semantics: bool = True
    matched_attributes: List[str] = Field(default_factory=list)
    model_receipt: ModelReceipt


class MultimodalUnderstandingOutput(BaseModel):
    request_sha256: str
    visual: Optional[VisualUnderstandingResult] = None
    text: Optional[TextUnderstandingResult] = None
    cross_modal_note: str = ""
    total_latency_ms: float = 0.0


_CONSTRUCTION_TERMS = {
    "collar", "lapel", "placket", "cuff", "hem", "sleeve", "armscye",
    "seam", "dart", "yoke", "hood", "pocket", "waistband", "zipper",
    "ease", "drape", "gusset", "pleat", "grainline", "panel",
}


class MultimodalIntelligenceEngine:
    """Unified visual + text + cross-modal intelligence coordinator."""

    def __init__(self) -> None:
        self._dinov2 = None

    def _get_dinov2(self):
        if self._dinov2 is None:
            from backend.app.services.ml.dinov2_feature_extractor import Dinov2FeatureExtractor
            self._dinov2 = Dinov2FeatureExtractor()
        return self._dinov2

    @staticmethod
    def assess_image_quality(image: Image.Image) -> ImageQualityReport:
        rgb = np.array(image.convert("RGB"))
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))

        # Foreground estimation via border-referenced threshold + Otsu fallback
        border = np.concatenate([gray[:8, :].ravel(), gray[-8:, :].ravel(), gray[:, :8].ravel(), gray[:, -8:].ravel()])
        bg_mean = float(np.mean(border))
        thresh_mode = cv2.THRESH_BINARY_INV if bg_mean > 175.0 else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_mode + cv2.THRESH_OTSU)
        fg_ratio = float(np.mean(mask > 20))
        if fg_ratio < 0.05 or fg_ratio > 0.96:
            diff = np.abs(gray.astype(np.float32) - bg_mean)
            fg_ratio = float(np.mean(diff > 18.0))

        issues: List[str] = []
        if min(w, h) < 128:
            issues.append("low_resolution_under_128px")
        if sharpness < 18.0:
            issues.append("low_sharpness_or_blur")
        if brightness < 24.0 or brightness > 246.0:
            issues.append("extreme_exposure")
        if fg_ratio < 0.04:
            issues.append("insufficient_foreground_signal")

        aspect = round(w / max(1, h), 3)
        orientation_hint = "portrait_front_or_back_candidate" if aspect <= 0.95 else ("square_catalog" if aspect <= 1.25 else "wide_or_multi_subject")
        occlusion_risk = "moderate" if (fg_ratio < 0.12 or fg_ratio > 0.92) else "low"
        usable = min(w, h) >= 64 and fg_ratio >= 0.02 and 10.0 <= brightness <= 250.0
        return ImageQualityReport(
            width=w,
            height=h,
            sharpness_laplacian=round(sharpness, 2),
            mean_brightness=round(brightness, 2),
            foreground_coverage_ratio=round(fg_ratio, 4),
            view_orientation_hint=orientation_hint,
            occlusion_risk=occlusion_risk,
            usable=usable,
            issues=issues,
        )

    def interpret_text_instruction(self, instruction: str) -> TextUnderstandingResult:
        t0 = time.perf_counter()
        text = (instruction or "").strip()
        lower = text.lower()
        ambiguities: List[str] = []

        # Reuse Phase 16 closed garment action planner cleanly
        from backend.app.services.llm.garment_plan import local_plan
        plan, _trace = local_plan(text or "inspect", [])

        intent = "general_query"
        if any(w in lower for w in ("fit", "tight", "loose", "size", "measurement", "chest", "waist", "ease")):
            intent = "fit_analysis"
        elif any(w in lower for w in ("critic", "defect", "quality", "check mesh", "evaluate")):
            intent = "quality_evaluation"
        elif any(w in lower for w in ("reconstruct", "3d", "glb", "model")):
            intent = "reconstruction"
        elif any(w in lower for w in ("seam", "pattern", "fabric", "weave", "construction", "explain", "what is")):
            intent = "knowledge_or_construction"
        elif any(w in lower for w in ("recommend", "outfit", "style", "match", "wardrobe")):
            intent = "styling_recommendation"
        elif plan.action in {"widen", "shorten", "widen_sleeves", "denim", "undo"} or (
            any(v in lower for v in ("shorten", "widen", "lengthen", "taper", "tighten", "loosen"))
            and any(t in lower for t in _CONSTRUCTION_TERMS)
        ):
            intent = "design_modification"

        if not text:
            ambiguities.append("empty_instruction")
        elif plan.action == "clarify" and intent == "general_query":
            ambiguities.append("unspecified_target_or_compound_request")
        if re.search(r"\b(it|this|that)\b", lower) and not any(t in lower for t in _CONSTRUCTION_TERMS):
            if len(lower.split()) <= 4:
                ambiguities.append("pronoun_without_explicit_component_target")

        # Extract numeric cm measurements cleanly
        measurements_cm: Dict[str, float] = {}
        for field_name in ("chest", "waist", "hip", "shoulder", "sleeve", "length", "inseam"):
            m = re.search(rf"\b{field_name}s?\b(?:\s+(?:is|by|to|=|:))?\s*(\d+(?:\.\d+)?)\s*(cm|in|inch|inches)?\b", lower)
            if m:
                val = float(m.group(1))
                unit = (m.group(2) or "cm").lower()
                if unit.startswith("in"):
                    val = round(val * 2.54, 2)
                measurements_cm[f"{field_name}_cm"] = val

        terms = sorted([t for t in _CONSTRUCTION_TERMS if re.search(rf"\b{t}s?\b", lower)])
        attrs: Dict[str, Any] = {}
        for color in ("black", "white", "navy", "denim", "blue", "grey", "beige", "olive", "brown", "burgundy"):
            if re.search(rf"\b{color}\b", lower):
                attrs.setdefault("colors", []).append(color)
        for fit_word in ("slim", "regular", "relaxed", "oversized", "tailored"):
            if re.search(rf"\b{fit_word}\b", lower):
                attrs["fit"] = fit_word

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("yorvyn-text-parser-v17", latency_ms, device="cpu", backend="deterministic_nlp")
        return TextUnderstandingResult(
            instruction=text,
            intent=intent,
            ambiguity_detected=bool(ambiguities),
            ambiguity_reasons=ambiguities,
            requested_action=plan.action,
            attributes=attrs,
            construction_terms=terms,
            measurement_targets_cm=measurements_cm,
            model_receipt=ModelReceipt(
                model_id="yorvyn-text-parser-v17",
                version="17.0.0",
                source="deterministic_rules + garment_plan.local_plan",
                device="cpu",
                confidence=0.65 if ambiguities else 0.90,
                latency_ms=latency_ms,
                limitations="Deterministic parser handles structured fashion/construction requests; unconstrained open-ended semantics require clarification.",
            ),
        )

    def analyze_image(
        self,
        image_bytes: bytes,
        *,
        include_embedding: bool = True,
    ) -> VisualUnderstandingResult:
        sha = hashlib.sha256(image_bytes).hexdigest()
        receipts: List[ModelReceipt] = []
        with Image.open(io.BytesIO(image_bytes)) as raw_im:
            img = raw_im.convert("RGB")

        quality = self.assess_image_quality(img)
        rgb = np.array(img)
        h, w = rgb.shape[:2]

        # 1. Foreground color + high-frequency texture/stripe cues
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        border_mean = float(np.mean(gray[:8, :]))
        t_type = cv2.THRESH_BINARY_INV if border_mean > 175.0 else cv2.THRESH_BINARY
        _, fg = cv2.threshold(gray, 0, 255, t_type + cv2.THRESH_OTSU)
        ys, xs = np.where(fg > 20)
        silhouette_ar = round(
            (int(xs.max() - xs.min() + 1) / max(1, int(ys.max() - ys.min() + 1)))
            if len(xs) > 10 else (w / max(1, h)),
            3,
        )

        # Palette & pattern frequency cues via existing classifier helpers
        from backend.app.services.garments.intelligence.universal_garment_classifier import (
            find_closest_fashion_color,
        )
        fg_pixels = rgb[fg > 20]
        if len(fg_pixels) < 50:
            fg_pixels = rgb.reshape(-1, 3)
        step = max(1, len(fg_pixels) // 1000)
        mean_rgb = tuple(int(v) for v in np.mean(fg_pixels[::step], axis=0))
        color_name, color_hex = find_closest_fashion_color(mean_rgb)
        palette_hex = [color_hex]

        gx = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))))
        gy = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))))
        pattern_cues: List[str] = []
        if gx > 18.0 and gy > 18.0:
            pattern_cues.append("high_texture_or_grid_contrast")
        elif gx > 1.45 * max(1.0, gy) and gx > 12.0:
            pattern_cues.append("vertical_linear_cues")
        elif gy > 1.45 * max(1.0, gx) and gy > 12.0:
            pattern_cues.append("horizontal_linear_cues")
        else:
            pattern_cues.append("predominantly_solid_surface")

        # 2. Local v6 Classifier prediction (strictly verified checkpoint only)
        cat = subcat = cat_conf = None
        try:
            from backend.app.services.intelligence.local_perception import classifier_prediction
            pred = classifier_prediction(image_bytes)
            if pred:
                cat = pred["category"]
                subcat = pred["subcategory"]
                cat_conf = round(float(pred["confidence"]), 4)
                dur = float(pred["duration_ms"])
                inference_telemetry.record("universal-garment-classifier", dur, device=pred["device"], backend="pytorch")
                receipts.append(ModelReceipt(
                    model_id=pred["model_id"],
                    version="6.0.0",
                    source=f"sha256:{pred['sha256'][:16]}...",
                    device=pred["device"],
                    confidence=cat_conf,
                    latency_ms=dur,
                    limitations=pred["calibration"],
                ))
        except Exception as exc:
            receipts.append(ModelReceipt(
                model_id="universal-garment-classifier",
                version="6.0.0",
                source="local_checkpoint",
                executed=False,
                limitations=f"Classifier unavailable: {type(exc).__name__}",
            ))

        # 3. Cached DINOv2 embedding extraction (respecting env opt-out for constrained tests)
        emb_vec: Optional[List[float]] = None
        emb_dim = 0
        emb_sha: Optional[str] = None
        emb_avail = False
        if include_embedding and os.getenv("YORVYN_DISABLE_DINOV2") != "1":
            ext = self._get_dinov2()
            if ext.cached_weights_available:
                try:
                    t0 = time.perf_counter()
                    feats = ext.extract_features(img)
                    lat = round((time.perf_counter() - t0) * 1000.0, 3)
                    vec = np.asarray(feats["cls_embedding"], dtype=np.float32)
                    emb_vec = [round(float(v), 6) for v in vec.tolist()]
                    emb_dim = len(emb_vec)
                    emb_sha = hashlib.sha256(vec.tobytes()).hexdigest()
                    emb_avail = bool(feats.get("semantic_valid"))
                    inference_telemetry.record("dinov2_small", lat, device=str(feats.get("device", "cpu")), backend=str(feats.get("execution_backend")))
                    receipts.append(ModelReceipt(
                        model_id="dinov2_small",
                        version="1.0",
                        source="facebook/dinov2-small (local HF cache)",
                        device=str(feats.get("device", "cpu")),
                        latency_ms=lat,
                        limitations="Self-supervised representation; cosine distance does not prove garment category equality.",
                        executed=emb_avail,
                    ))
                except Exception as exc:
                    receipts.append(ModelReceipt(
                        model_id="dinov2_small",
                        version="1.0",
                        source="facebook/dinov2-small",
                        executed=False,
                        limitations=f"DINOv2 skipped: {type(exc).__name__}",
                    ))

        return VisualUnderstandingResult(
            image_sha256=sha,
            category=cat,
            subcategory=subcat,
            category_confidence=cat_conf,
            primary_color=color_name,
            palette_hex=palette_hex,
            silhouette_aspect_ratio=silhouette_ar,
            pattern_cues=pattern_cues,
            embedding_available=emb_avail,
            embedding_dim=emb_dim,
            embedding_sha256=emb_sha,
            embedding_vector=emb_vec,
            quality=quality,
            receipts=receipts,
        )

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na < 1e-8 or nb < 1e-8:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def rank_similarity(
        self,
        candidates: List[Dict[str, Any]],
        *,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[CrossModalMatch]:
        """Ranks candidate garments using DINOv2 embeddings (when present) and lexical/attribute overlap."""
        t0 = time.perf_counter()
        q_tokens = set(re.findall(r"[a-z0-9_]+", (query_text or "").lower()))
        q_vec = np.asarray(query_embedding, dtype=np.float32) if query_embedding else None

        ranked: List[CrossModalMatch] = []
        hw = HardwareSelector.select_device(allow_mps=False)
        for item in candidates:
            item_id = str(item.get("id") or item.get("item_id") or item.get("name") or "unknown")
            c_vec_raw = item.get("embedding_vector")
            text_blob = " ".join(
                str(item.get(k, "")) for k in ("name", "category", "subcategory", "color", "brand", "pattern", "fabric", "fit", "notes")
            ).lower()
            c_tokens = set(re.findall(r"[a-z0-9_]+", text_blob))
            overlap = sorted(q_tokens & c_tokens) if q_tokens else []
            lex_score = (len(overlap) / max(1, len(q_tokens))) if q_tokens else 0.0

            vis_score = None
            if q_vec is not None and isinstance(c_vec_raw, list) and len(c_vec_raw) == len(q_vec):
                vis_score = max(0.0, self._cosine(q_vec, np.asarray(c_vec_raw, dtype=np.float32)))

            if vis_score is not None and q_tokens:
                score = 0.65 * vis_score + 0.35 * lex_score
                method = "dinov2_visual_plus_attribute_hybrid"
                model_id = "dinov2_small"
            elif vis_score is not None:
                score = vis_score
                method = "dinov2_cosine_similarity"
                model_id = "dinov2_small"
            else:
                score = lex_score
                method = "structured_attribute_overlap"
                model_id = "yorvyn-attribute-matcher-v17"

            lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            ranked.append(CrossModalMatch(
                item_id=item_id,
                similarity_score=round(float(score), 4),
                method=method,
                matched_attributes=overlap,
                model_receipt=ModelReceipt(
                    model_id=model_id,
                    version="17.0.0",
                    source="local_similarity",
                    device=hw,
                    confidence=round(float(score), 4),
                    latency_ms=lat_ms,
                    limitations="Similarity ranking measures visual or metadata proximity and does not establish physical construction equality.",
                ),
            ))

        ranked.sort(key=lambda m: m.similarity_score, reverse=True)
        return ranked[: max(1, min(top_k, 50))]

    def understand(
        self,
        *,
        image_bytes: Optional[bytes] = None,
        instruction: Optional[str] = None,
        include_embedding: bool = True,
    ) -> MultimodalUnderstandingOutput:
        t0 = time.perf_counter()
        h = hashlib.sha256((image_bytes or b"") + (instruction or "").encode("utf-8")).hexdigest()
        visual = self.analyze_image(image_bytes, include_embedding=include_embedding) if image_bytes else None
        text = self.interpret_text_instruction(instruction) if instruction is not None else None

        cross_note = ""
        if visual and text:
            if visual.category and text.requested_action == "clarify":
                cross_note = f"Visual evidence indicates {visual.category}; instruction requires clarification before mutation."
            elif visual.category:
                cross_note = f"Aligned '{text.intent}' intent with observed garment category '{visual.category}'."

        reg_note = unified_model_registry.select_model("multimodal_vision")
        if reg_note and not cross_note and visual:
            cross_note = f"Executed under registry model preference ({reg_note.model_id})."

        return MultimodalUnderstandingOutput(
            request_sha256=h,
            visual=visual,
            text=text,
            cross_modal_note=cross_note,
            total_latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


multimodal_intelligence = MultimodalIntelligenceEngine()
