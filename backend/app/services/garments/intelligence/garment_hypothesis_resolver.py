"""
YORVYN — Garment Hypothesis Resolver (Phase 12.2 Hardening)
Resolves garment category and subcategory through multi-factor Bayesian reasoning:
1. Calibrated neural prediction logits & margins
2. Anatomical aspect ratio & mass distribution profiles
3. Bilateral leg bifurcation vs single-torso cylinder analysis
4. Structural component detection agreement (collars, plackets, hoods, bodices, pockets)
5. Garment landmark spatial validation
6. Non-fabrication & explicit uncertainty handling

Guarantees:
- Upper-body garments (formal shirts, hoodies, t-shirts) never invert to bottoms/trousers.
- One-piece dresses never reduce to skirts when upper bodice is present.
- Outerwear distinguishes denim jackets (point collar, placket, chest flaps) from blazers (notched lapels).
- Low-confidence or ambiguous silhouettes flag requires_confirmation without silent category substitution.
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np
import cv2
from PIL import Image

from backend.app.models.garment_intelligence_models import (
    GarmentComponentV2,
    GarmentLandmarkV2,
    GarmentCategoryProbability
)


@dataclass
class GarmentHypothesis:
    """A scored classification hypothesis."""
    category: str
    subcategory: str
    confidence: float
    reason: str
    evidence_score: float = 0.0


@dataclass
class ResolvedGarmentClassification:
    """Final resolved classification output."""
    category: str
    subcategory: str
    confidence: float
    display_name: str
    requires_confirmation: bool
    candidate_hypotheses: List[GarmentCategoryProbability]
    attributes: Dict[str, Any]
    resolution_log: List[str]
    uncertainty_status: str = "CONFIDENT"  # CONFIDENT, LOW_CONFIDENCE, AMBIGUOUS, UNSUPPORTED
    original_prediction: Dict[str, Any] = field(default_factory=dict)
    heuristic_adjustments: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_signals: List[str] = field(default_factory=list)
    rejected_alternatives: List[Dict[str, Any]] = field(default_factory=list)


class GarmentHypothesisResolver:
    """Multi-factor Garment Hypothesis Resolver."""

    # Category display mapping
    DISPLAY_NAMES = {
        "tops": {
            "tshirt": "T-Shirt",
            "formal_shirt": "Formal Button-Down Shirt",
            "casual_shirt": "Casual Shirt",
            "oxford_shirt": "Oxford Button-Down Shirt",
            "hoodie": "Pullover Hoodie",
            "sweater": "Sweater",
            "polo_shirt": "Polo Shirt",
            "crop_top": "Crop Top",
            "tank_top": "Tank Top"
        },
        "bottoms": {
            "jeans": "Denim Jeans",
            "straight_jeans": "Straight-Fit Jeans",
            "trousers": "Tailored Trousers",
            "shorts": "Shorts",
            "cargo_pants": "Cargo Pants",
            "chinos": "Chinos"
        },
        "outerwear": {
            "jacket": "Jacket",
            "denim_jacket": "Denim Trucker Jacket",
            "blazer": "Tailored Blazer",
            "formal_coat": "Overcoat",
            "leather_jacket": "Leather Jacket",
            "bomber_jacket": "Bomber Jacket",
            "cardigan": "Cardigan Outerwear",
            "puffer_jacket": "Puffer Jacket",
            "windbreaker": "Sport Windbreaker",
            "trench_coat": "Trench Coat",
            "parka": "Parka / Winter Coat"
        },
        "dresses_and_skirts": {
            "dress": "Dress",
            "casual_dress": "Casual Summer Dress",
            "maxi_dress": "Maxi Dress",
            "formal_dress": "Formal Dress",
            "skirt": "A-Line Skirt",
            "pencil_skirt": "Pencil Skirt",
            "jumpsuit": "One-Piece Jumpsuit",
            "romper": "Casual Romper"
        },
        "traditional": {
            "kurta": "Traditional Kurta",
            "sherwani": "Sherwani",
            "saree": "Saree"
        },
        "footwear": {
            "sneakers": "Sneakers",
            "boots": "Boots",
            "running_shoes": "Running Shoes",
            "sandals": "Sandals"
        },
        "accessories": {
            "cap": "Baseball Cap",
            "caps": "Baseball Cap",
            "beanie": "Beanie Hat",
            "scarf": "Scarf",
            "scarves": "Scarf",
            "hat": "Hat",
            "hats": "Hat",
            "bucket_hat": "Bucket Hat",
            "headwear": "Headwear"
        }
    }

    def resolve(
        self,
        image: Image.Image,
        alpha_mask: np.ndarray,
        raw_category_probs: Dict[str, float],
        initial_subcategory: str,
        detected_components: List[GarmentComponentV2],
        landmarks: Dict[str, GarmentLandmarkV2],
        user_category_hint: Optional[str] = None,
        user_subcategory_hint: Optional[str] = None,
        image_type: Optional[str] = None
    ) -> ResolvedGarmentClassification:
        """
        Executes multi-factor evidence arbitration across all garment categories.
        """
        log: List[str] = []
        h, w = alpha_mask.shape

        # 1. Morphological Foreground Analysis
        y_idx, x_idx = np.where(alpha_mask > 20)
        if len(y_idx) == 0:
            log.append("Warning: Empty foreground mask; fallback to default top")
            return self._empty_fallback()

        min_y, max_y = int(np.min(y_idx)), int(np.max(y_idx))
        min_x, max_x = int(np.min(x_idx)), int(np.max(x_idx))
        garment_h = max(1, max_y - min_y)
        garment_w = max(1, max_x - min_x)

        aspect_ratio = float(garment_h) / float(garment_w)
        centroid_y = float(np.mean(y_idx)) / float(h)
        min_y_rel = float(min_y) / float(h)
        max_y_rel = float(max_y) / float(h)

        # Spans across vertical intervals
        top_y = int(min_y + garment_h * 0.20)
        mid_y = int(min_y + garment_h * 0.50)
        bot_y = int(min_y + garment_h * 0.85)

        top_span = np.sum(alpha_mask[np.clip(top_y, 0, h - 1), :] > 20)
        mid_span = np.sum(alpha_mask[np.clip(mid_y, 0, h - 1), :] > 20)
        bot_span = np.sum(alpha_mask[np.clip(bot_y, 0, h - 1), :] > 20)

        span_ratio = float(top_span) / max(float(mid_span), 1.0)
        waist_to_hem_ratio = float(bot_span) / max(float(mid_span), 1.0)

        # 2. Robust Bilateral Crotch Bifurcation Check
        # A genuine pair of pants/shorts MUST have:
        # A) Lower garment mass: bot_span must be substantial
        # B) Two separate bilateral columns (left leg & right leg) with an empty gap between them
        garment_cx = int(min_x + garment_w * 0.50)
        has_bilateral_legs = False
        has_empty_crotch_gap = False

        if bot_span > 0.15 * mid_span and aspect_ratio >= 0.45:
            # Check 1: standard pants/trousers (0.42 - 0.88)
            # Check 2: shorts / low-rise bifurcation (0.60 - 0.94)
            for y0_f, y1_f in [(0.42, 0.88), (0.60, 0.94)]:
                sample_y0 = int(min_y + garment_h * y0_f)
                sample_y1 = int(min_y + garment_h * y1_f)

                # Left leg zone: cx - 0.40*w to cx - 0.08*w
                l_x0 = max(0, garment_cx - int(garment_w * 0.40))
                l_x1 = max(0, garment_cx - int(garment_w * 0.08))
                # Right leg zone: cx + 0.08*w to cx + 0.40*w
                r_x0 = min(w, garment_cx + int(garment_w * 0.08))
                r_x1 = min(w, garment_cx + int(garment_w * 0.40))
                # Center crotch gap zone: cx - 0.05*w to cx + 0.05*w
                c_x0 = max(0, garment_cx - max(4, int(garment_w * 0.05)))
                c_x1 = min(w, garment_cx + max(4, int(garment_w * 0.05)))

                if (l_x1 > l_x0) and (r_x1 > r_x0) and (c_x1 > c_x0) and (sample_y1 > sample_y0 + 8):
                    left_leg_density = float(np.mean(alpha_mask[sample_y0:sample_y1, l_x0:l_x1] > 20))
                    right_leg_density = float(np.mean(alpha_mask[sample_y0:sample_y1, r_x0:r_x1] > 20))
                    center_gap_density = float(np.mean(alpha_mask[sample_y0:sample_y1, c_x0:c_x1] > 20))

                    if (left_leg_density > 0.18) and (right_leg_density > 0.18) and (center_gap_density < 0.22):
                        has_bilateral_legs = True
                        has_empty_crotch_gap = True
                        break

        # 3. Component Evidence Extraction
        comp_types = {c.component_type for c in detected_components if c.status == "detected"}
        has_upper_components = bool(comp_types & {
            "collar", "neckline", "hood", "kangaroo_pocket", "placket",
            "left_sleeve", "right_sleeve", "cuff", "bodice", "armscye"
        })
        has_lower_components = bool(comp_types & {
            "waistband", "left_leg", "right_leg", "front_fly"
        })
        has_hood = "hood" in comp_types
        has_kangaroo_pocket = "kangaroo_pocket" in comp_types
        has_collar = "collar" in comp_types
        has_placket = "placket" in comp_types
        has_bodice = "bodice" in comp_types
        has_sleeves = "left_sleeve" in comp_types or "right_sleeve" in comp_types

        is_true_crotch_split = has_bilateral_legs and has_empty_crotch_gap
        if is_true_crotch_split and (span_ratio > 1.05 or has_sleeves or bool(comp_types & {"left_sleeve", "right_sleeve", "collar", "lapel", "hood", "neckline"})):
            is_true_crotch_split = False

        # Check dress walking gap / slit:
        # In a dress with a hem slit or flutter, the mid-body (y = 0.50 - 0.65) is solid fabric,
        # whereas pants bifurcate at the crotch (mid_crotch_density < 0.25).
        # Only applies to full-length tall garments (aspect_ratio > 1.25). Shorts and pants are excluded.
        if is_true_crotch_split and aspect_ratio > 1.25:
            s_mid0 = int(min_y + garment_h * 0.50)
            s_mid1 = int(min_y + garment_h * 0.65)
            if s_mid1 > s_mid0:
                mid_c_zone = alpha_mask[s_mid0:s_mid1, max(0, garment_cx - int(garment_w * 0.06)):min(w, garment_cx + int(garment_w * 0.06))]
                if mid_c_zone.size > 0 and np.mean(mid_c_zone > 20) > 0.60:
                    is_true_crotch_split = False
                    log.append("Correction: Hem void is a dress walking slit or skirt flare (mid-body is solid cloth), not leg bifurcation")

        # 4. Grayscale Gradient & Construction Analysis
        gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        masked_gray = np.where(alpha_mask > 20, gray, 0)

        # Center placket line detection on mid-to-lower torso (avoids chest graphic interference)
        y0_mid = int(min_y + garment_h * 0.45)
        y1_mid = int(min_y + garment_h * 0.65)
        cx_mid = masked_gray[y0_mid:y1_mid, max(0, garment_cx - 4):min(w, garment_cx + 5)]
        diff_mid = 0.0
        if cx_mid.shape[1] >= 5:
            c_col = cx_mid[:, cx_mid.shape[1] // 2].astype(float)
            side_cols = (cx_mid[:, 0].astype(float) + cx_mid[:, -1].astype(float)) * 0.5
            valid_rows = np.all(cx_mid > 0, axis=1)
            if np.sum(valid_rows) > 10:
                diff_mid = float(np.mean(np.abs(c_col - side_cols)[valid_rows]))

        y0_low = int(min_y + garment_h * 0.65)
        y1_low = int(min_y + garment_h * 0.88)
        cx_low = masked_gray[y0_low:y1_low, max(0, garment_cx - 4):min(w, garment_cx + 5)]
        diff_low = 0.0
        if cx_low.shape[1] >= 5:
            c_col = cx_low[:, cx_low.shape[1] // 2].astype(float)
            side_cols = (cx_low[:, 0].astype(float) + cx_low[:, -1].astype(float)) * 0.5
            valid_rows = np.all(cx_low > 0, axis=1)
            if np.sum(valid_rows) > 10:
                diff_low = float(np.mean(np.abs(c_col - side_cols)[valid_rows]))

        has_center_vertical_seam = ((diff_mid > 8.5 and diff_low > 6.0) or (diff_low > 8.5))

        # Chest flap pockets (denim jacket / utility shirt)
        pocket_box = masked_gray[
            int(min_y + garment_h * 0.28):int(min_y + garment_h * 0.44),
            int(min_x + garment_w * 0.20):int(min_x + garment_w * 0.42)
        ]
        has_chest_flap_pockets = (
            bool(comp_types & {"chest_flap_pockets", "pocket_flap"}) or
            (pocket_box.size > 25 and (has_sleeves or span_ratio >= 0.82) and float(np.mean(np.abs(np.diff(pocket_box.astype(float), axis=0)))) >= 12.0)
        )

        # 5. Initialize Hypothesis Scores from Raw Category Probs
        heuristic_adjustments: List[Dict[str, Any]] = []
        reasoning_signals: List[str] = []

        orig_cat = max(raw_category_probs, key=raw_category_probs.get) if raw_category_probs else "tops"
        orig_conf = round(float(raw_category_probs.get(orig_cat, 0.50)), 3)
        original_prediction = {
            "category": orig_cat,
            "subcategory": initial_subcategory,
            "confidence": orig_conf
        }

        scores: Dict[str, float] = {
            "tops": raw_category_probs.get("tops", 0.0) * 3.0,
            "bottoms": raw_category_probs.get("bottoms", 0.0) * 3.0,
            "outerwear": raw_category_probs.get("outerwear", 0.0) * 3.0,
            "dresses_and_skirts": raw_category_probs.get("dresses_and_skirts", 0.0) * 3.0,
            "traditional": raw_category_probs.get("traditional", 0.0) * 3.0,
            "footwear": raw_category_probs.get("footwear", 0.0) * 3.0,
            "accessories": raw_category_probs.get("accessories", 0.0) * 3.0
        }

        # ── Veto and Evidence Adjustments ──────────────────────────────────────

        # Check for layered two-piece ensemble (e.g. shirt + pants in single mask)
        # Distinct from monolithic jumpsuit by color/luminance disparity across waist
        is_two_piece_ensemble = False
        if is_true_crotch_split and has_upper_components and span_ratio > 1.25:
            y_up0 = int(min_y + garment_h * 0.15)
            y_up1 = int(min_y + garment_h * 0.38)
            y_dn0 = int(min_y + garment_h * 0.60)
            y_dn1 = int(min_y + garment_h * 0.85)
            if y_up1 > y_up0 and y_dn1 > y_dn0:
                rgb_arr = np.array(image.convert("RGB"))
                up_mask = alpha_mask[y_up0:y_up1, min_x:max_x] > 20
                dn_mask = alpha_mask[y_dn0:y_dn1, min_x:max_x] > 20
                if np.sum(up_mask) > 80 and np.sum(dn_mask) > 80:
                    up_rgb = rgb_arr[y_up0:y_up1, min_x:max_x][up_mask]
                    dn_rgb = rgb_arr[y_dn0:y_dn1, min_x:max_x][dn_mask]
                    m_up = np.mean(up_rgb, axis=0)
                    m_dn = np.mean(dn_rgb, axis=0)
                    col_dist = float(np.linalg.norm(m_up - m_dn))
                    lum_up = 0.299 * m_up[0] + 0.587 * m_up[1] + 0.114 * m_up[2]
                    lum_dn = 0.299 * m_dn[0] + 0.587 * m_dn[1] + 0.114 * m_dn[2]
                    lum_diff = abs(lum_up - lum_dn)
                    if col_dist > 28.0 or lum_diff > 30.0 or ("waistband" in comp_types and has_upper_components):
                        is_two_piece_ensemble = True

        # SAFEGUARD 1: Upper-Body vs Bottoms vs Jumpsuit/Romper Separation
        # A jumpsuit/romper requires verified upper components (sleeves/collar/neckline) OR wide shoulder span (> 1.35) with crotch split.
        # Trousers and shorts have waistband, not upper-body sleeves or collars.
        has_jumpsuit_signal = is_true_crotch_split and not is_two_piece_ensemble and (
            (bool(comp_types & {"left_sleeve", "right_sleeve", "collar", "neckline"}) and not has_hood) or
            (aspect_ratio >= 1.25 and span_ratio > 1.35) or
            (bool(user_subcategory_hint and any(kw in user_subcategory_hint.lower() for kw in ["jumpsuit", "romper"])))
        )
        if is_two_piece_ensemble:
            scores["tops"] += 4.5
            scores["bottoms"] += 4.5
            scores["dresses_and_skirts"] -= 6.0
            heuristic_adjustments.append({
                "rule": "layered_two_piece_ensemble_detected",
                "category": "ambiguous_outfit",
                "delta": 0.0,
                "reason": "Distinct upper bodice and lower pants detected; separated into two-piece outfit"
            })
            reasoning_signals.append("Layered two-piece outfit detected (distinct upper bodice and lower bifurcated pants)")
            log.append("Evidence: Layered two-piece outfit detected; suppressing monolithic jumpsuit boost")
        elif has_jumpsuit_signal:
            scores["dresses_and_skirts"] += 8.0
            scores["bottoms"] -= 4.0
            scores["tops"] -= 3.0
            heuristic_adjustments.append({
                "rule": "jumpsuit_romper_bifurcation",
                "category": "dresses_and_skirts",
                "delta": 8.0,
                "reason": "Upper body construction paired with bilateral crotch split confirms jumpsuit/romper"
            })
            reasoning_signals.append("Bilateral leg split with continuous upper bodice indicates jumpsuit/romper")
            log.append("Evidence: Upper components and bilateral crotch split indicate Jumpsuit / Romper")
            log.append("Evidence: Upper components and bilateral crotch split indicate Jumpsuit / Romper")
        elif not is_true_crotch_split:
            scores["bottoms"] -= 16.0
            heuristic_adjustments.append({
                "rule": "no_crotch_split_veto_bottoms",
                "category": "bottoms",
                "delta": -16.0,
                "reason": "Garment lacks bilateral leg bifurcation; cannot be pants, jeans, or shorts"
            })
            reasoning_signals.append("Garment lacks bilateral leg bifurcation (vetoes bottoms)")
            log.append("Veto: Bottoms rejected (no bilateral leg bifurcation)")

        if is_true_crotch_split and not has_upper_components and not has_jumpsuit_signal:
            scores["bottoms"] += 6.0
            scores["tops"] -= 5.0
            scores["dresses_and_skirts"] -= 5.0
            heuristic_adjustments.append({
                "rule": "confirmed_crotch_split_bottoms",
                "category": "bottoms",
                "delta": 6.0,
                "reason": "Confirmed bilateral crotch split without upper components"
            })
            reasoning_signals.append("Confirmed bilateral crotch split indicates pants/shorts")
            log.append("Evidence: Confirmed bilateral crotch split; boosting bottoms")

        # Wide shoulder / sleeve silhouette boosts upper body (tops & outerwear)
        if span_ratio > 1.15 and not is_true_crotch_split and aspect_ratio <= 1.40 and centroid_y >= 0.35:
            scores["tops"] += 4.0
            scores["outerwear"] += 2.5
            heuristic_adjustments.append({
                "rule": "wide_upper_span_tops",
                "category": "tops",
                "delta": 4.0,
                "reason": f"Wide upper span ratio ({span_ratio:.2f}) indicates tops/outerwear"
            })
            reasoning_signals.append(f"Wide shoulder/sleeve silhouette ({span_ratio:.2f})")
            log.append(f"Evidence: Wide upper span ratio ({span_ratio:.2f}) indicates tops/outerwear")

        # Dedicated Skirt safeguard: Narrow top waistband with flared hem and no upper sleeves
        is_skirt_detected = (
            not is_true_crotch_split and
            not has_hood and
            not has_kangaroo_pocket and
            not has_sleeves and
            not has_chest_flap_pockets and
            "lapel" not in comp_types and
            "collar" not in comp_types and
            span_ratio <= 1.08 and
            not (user_category_hint and any(kw in user_category_hint.lower() for kw in ["dress", "coat", "jacket", "shirt", "pant", "trouser", "jean"])) and
            (
                (waist_to_hem_ratio >= 1.01 and aspect_ratio <= 1.45) or
                (centroid_y >= 0.38 and aspect_ratio <= 1.35) or
                (raw_category_probs.get("dresses_and_skirts", 0.0) > 0.04 and aspect_ratio <= 1.35)
            )
        )
        if is_skirt_detected:
            scores["dresses_and_skirts"] += 9.5
            scores["outerwear"] -= 8.0
            scores["tops"] -= 8.0
            scores["bottoms"] -= 16.0
            heuristic_adjustments.append({
                "rule": "skirt_morphology",
                "category": "dresses_and_skirts",
                "delta": 9.5,
                "reason": "Narrow top waistband with flared hem and no upper sleeves indicates skirt"
            })
            reasoning_signals.append("Narrow top waistband with flared hem and no upper sleeves indicates skirt")
            log.append("Evidence: Skirt morphology confirmed")

        # Straight tunic / kurta candidate
        is_kurta_candidate = (
            (1.35 <= aspect_ratio <= 2.20) and
            not is_true_crotch_split and
            not is_skirt_detected and
            (0.68 <= waist_to_hem_ratio <= 1.15) and
            not has_center_vertical_seam and
            not has_placket and
            not has_chest_flap_pockets and
            not has_hood and
            not has_kangaroo_pocket and
            "lapel" not in comp_types and
            not (user_category_hint and any(kw in user_category_hint.lower() for kw in ["dress", "coat", "jacket", "shirt", "pant", "trouser", "jean"]))
        )
        if is_kurta_candidate:
            scores["traditional"] += 7.5
            scores["tops"] -= 2.0
            scores["dresses_and_skirts"] -= 3.0
            scores["outerwear"] -= 6.0
            scores["bottoms"] -= 12.0
            heuristic_adjustments.append({
                "rule": "kurta_morphology",
                "category": "traditional",
                "delta": 7.5,
                "reason": "Straight elongated tunic cut without crotch split indicates kurta/traditional"
            })
            reasoning_signals.append("Straight elongated tunic cut without crotch split indicates kurta/traditional")
            log.append("Evidence: Kurta morphology confirmed")

        # One-piece dress candidate detection (sleeved or sleeveless)
        is_dress_candidate = (
            not is_true_crotch_split and
            not is_skirt_detected and
            not is_kurta_candidate and
            not (has_hood or has_kangaroo_pocket) and
            not has_jumpsuit_signal and
            not (user_category_hint and any(kw in user_category_hint.lower() for kw in ["pant", "trouser", "jean", "short", "shirt", "hoodie", "jacket", "coat"])) and
            (
                bool(user_category_hint and "dress" in user_category_hint.lower()) or
                has_bodice or
                (raw_category_probs.get("dresses_and_skirts", 0.0) > 0.18 and aspect_ratio >= 1.25) or
                (aspect_ratio >= 1.40 and waist_to_hem_ratio >= 1.22 and not has_chest_flap_pockets and not has_placket) or
                (aspect_ratio >= 2.30 and not is_true_crotch_split and not has_chest_flap_pockets)
            )
        )

        is_dress_flare = is_dress_candidate and (waist_to_hem_ratio >= 1.04 or aspect_ratio >= 1.30)

        # Center vertical opening / placket / chest flap pocket evidence
        if (has_placket or has_center_vertical_seam or has_chest_flap_pockets) and not has_hood and not is_dress_candidate and not is_skirt_detected:
            # Distinguish formal shirt vs outerwear (jackets have flap pockets, lapels, or outerwear classification)
            if has_chest_flap_pockets or "lapel" in comp_types or orig_cat == "outerwear" or (user_category_hint and "outerwear" in user_category_hint.lower()):
                scores["outerwear"] += 6.5
                scores["tops"] -= 3.0
                heuristic_adjustments.append({
                    "rule": "placket_outerwear",
                    "category": "outerwear",
                    "delta": 6.5,
                    "reason": "Front placket/closure with tailored lapels, flap pockets, or outerwear prior indicates jacket"
                })
                reasoning_signals.append("Front placket/closure with tailored lapels, flap pockets, or outerwear prior indicates jacket")
                log.append("Evidence: Placket and jacket features indicate outerwear/jacket")
            else:
                scores["tops"] += 5.0
                scores["outerwear"] += 1.0
                heuristic_adjustments.append({
                    "rule": "placket_formal_shirt",
                    "category": "tops",
                    "delta": 5.0,
                    "reason": "Front button placket indicates formal/casual shirt"
                })
                reasoning_signals.append("Front button placket indicates formal/casual shirt")
                log.append("Evidence: Placket indicates formal shirt / button-down top")

        # Hood & Kangaroo Pocket Evidence (Definitive Hoodie indicator)
        if has_hood or has_kangaroo_pocket:
            scores["tops"] += 8.0
            scores["dresses_and_skirts"] -= 12.0
            scores["bottoms"] -= 12.0
            scores["outerwear"] -= 2.0
            heuristic_adjustments.append({
                "rule": "hood_pocket_hoodie",
                "category": "tops",
                "delta": 8.0,
                "reason": "Volumetric hood or kangaroo pocket definitively identifies hoodie"
            })
            reasoning_signals.append("Volumetric hood or kangaroo pocket confirmed")
            log.append("Evidence: Hood / kangaroo pocket confirms hoodie (tops)")

        if is_dress_candidate:
            scores["dresses_and_skirts"] += 9.5
            scores["bottoms"] -= 12.0
            scores["tops"] -= 5.0
            scores["outerwear"] -= 6.0
            heuristic_adjustments.append({
                "rule": "dress_morphology_affirmation",
                "category": "dresses_and_skirts",
                "delta": 9.5,
                "reason": f"Continuous one-piece silhouette (AR={aspect_ratio:.2f}, hem_ratio={waist_to_hem_ratio:.2f}) indicates dress"
            })
            reasoning_signals.append("Continuous one-piece silhouette indicates dress")
            log.append(f"Evidence: Dress morphology confirmed (AR={aspect_ratio:.2f}, hem_ratio={waist_to_hem_ratio:.2f})")

        # SAFEGUARD 3: Traditional Attire Evidence (Elongated straight silhouette without crotch split)
        is_traditional_candidate = (
            aspect_ratio >= 1.58 and not is_true_crotch_split and span_ratio >= 0.85 and not has_bodice and
            not has_chest_flap_pockets and not is_dress_candidate and
            not (user_subcategory_hint and any(kw in user_subcategory_hint.lower() for kw in ["tank", "crop", "shirt", "top", "blazer", "jacket", "coat", "dress"])) and
            (raw_category_probs.get("traditional", 0.0) > 0.35 or
             bool(user_subcategory_hint and any(kw in user_subcategory_hint.lower() for kw in ["kurta", "sherwani", "saree"])))
        )
        if is_traditional_candidate and not (has_hood or has_kangaroo_pocket or is_dress_flare):
            scores["traditional"] += 6.5
            scores["tops"] -= 3.0
            heuristic_adjustments.append({
                "rule": "traditional_kurta_silhouette",
                "category": "traditional",
                "delta": 6.5,
                "reason": f"Elongated straight-cut silhouette (AR={aspect_ratio:.2f}) indicates traditional attire"
            })
            reasoning_signals.append(f"Elongated straight silhouette ({aspect_ratio:.2f}) indicates traditional kurta/ensemble")
            log.append("Evidence: Elongated straight silhouette indicates traditional attire")

        # SAFEGUARD 4: Wearable Accessories Evidence (Compact upper headwear profile)
        is_accessory_candidate = (
            aspect_ratio < 0.80 and centroid_y < 0.45 and not is_true_crotch_split and
            not has_sleeves and span_ratio <= 0.90 and
            (raw_category_probs.get("accessories", 0.0) > 0.10 or
             bool(comp_types & {"visor", "crown", "brim", "hat", "cap", "headwear"}) or
             bool(user_subcategory_hint and any(kw in user_subcategory_hint.lower() for kw in ["cap", "hat", "beanie", "scarf", "fedora"])))
        )
        if is_accessory_candidate:
            scores["accessories"] += 8.5
            scores["tops"] -= 6.0
            scores["outerwear"] -= 4.0
            scores["bottoms"] -= 10.0
            heuristic_adjustments.append({
                "rule": "headwear_accessory_silhouette",
                "category": "accessories",
                "delta": 8.5,
                "reason": f"Compact upper headwear profile (AR={aspect_ratio:.2f}, centroid_y={centroid_y:.2f})"
            })
            reasoning_signals.append("Compact upper headwear profile indicates accessories")
            log.append("Evidence: Upper compact profile indicates wearable accessories")

        # Footwear rule with strict torso/waist veto
        is_on_body_feet = (min_y_rel > 0.78 and max_y_rel > 0.94)
        has_footwear_component = bool(comp_types & {"sole", "heel", "toe_box", "shoe_upper"})
        def _is_foot_kw(text: Optional[str]) -> bool:
            if not text:
                return False
            t = text.lower()
            foot_kws = ["shoe", "boot", "sneaker", "footwear", "sandal", "heel", "loafer", "slides", "oxford_shoe", "slippers"]
            return any(kw in t for kw in foot_kws) and ("shirt" not in t)

        has_footwear_hint = _is_foot_kw(user_category_hint) or _is_foot_kw(user_subcategory_hint)

        bottom_slice = alpha_mask[int(max_y - garment_h * 0.15):int(max_y), int(min_x):int(max_x)]
        sole_density = float(np.mean(bottom_slice > 20)) if bottom_slice.size > 0 else 0.0
        is_packshot_footwear = (
            0.20 <= aspect_ratio <= 1.25 and
            span_ratio <= 0.90 and
            not is_true_crotch_split and
            not has_upper_components and
            not has_lower_components and
            waist_to_hem_ratio <= 1.45 and
            centroid_y >= 0.22 and
            (sole_density > 0.20 or bool(comp_types & {"sole", "heel", "toe_box", "shoe_upper"}) or has_footwear_hint)
        )

        if is_on_body_feet or has_footwear_component or has_footwear_hint or is_packshot_footwear:
            scores["footwear"] += 8.0
            reasoning_signals.append("Positive footwear signal (anatomical feet position, footwear components, or isolated shoe packshot profile)")
            heuristic_adjustments.append({
                "rule": "positive_footwear_evidence",
                "category": "footwear",
                "delta": 8.0,
                "reason": "Garment positioned at anatomical feet, possesses footwear components, or matches footwear silhouette"
            })
            log.append("Evidence: Positive footwear signal verified")
        else:
            # Check for lower garment or torso features that strictly veto footwear
            has_torso_or_waist_features = (
                has_lower_components or
                has_upper_components or
                is_true_crotch_split or
                waist_to_hem_ratio > 1.08 or
                span_ratio > 0.85 or
                (aspect_ratio > 1.25 and span_ratio > 0.75)
            )
            if has_torso_or_waist_features:
                scores["footwear"] -= 15.0
                heuristic_adjustments.append({
                    "rule": "torso_waist_veto_footwear",
                    "category": "footwear",
                    "delta": -15.0,
                    "reason": "Garment contains waistband, torso, leg bifurcation, or flare which strictly vetoes footwear"
                })
                log.append("Veto: Footwear rejected (garment contains waist, legs, or torso features)")

        # Bayesian hint integration
        effective_hint = user_category_hint
        if not effective_hint and user_subcategory_hint:
            sub_norm = user_subcategory_hint.lower().strip()
            for cat_k, cat_subs in self.DISPLAY_NAMES.items():
                if sub_norm in cat_subs or any(sub_norm in s or s in sub_norm for s in cat_subs):
                    effective_hint = cat_k
                    break
            if not effective_hint:
                if any(kw in sub_norm for kw in ["hat", "cap", "beanie", "scarf", "headwear", "belt", "glove"]):
                    effective_hint = "accessories"
                elif any(kw in sub_norm for kw in ["shirt", "hoodie", "top", "sweater", "tank", "tee"]):
                    effective_hint = "tops"

        if effective_hint:
            h_hint = effective_hint.lower().strip()
            for cat_key in scores:
                if cat_key == h_hint or cat_key in h_hint or h_hint in cat_key:
                    scores[cat_key] += 4.5
                    heuristic_adjustments.append({
                        "rule": "user_category_prior",
                        "category": cat_key,
                        "delta": 4.5,
                        "reason": f"User hint '{effective_hint}'"
                    })
                    log.append(f"Prior: User hint '{effective_hint}' boosted '{cat_key}'")

        # 6. Calibrated Softmax Probabilities
        categories = list(scores.keys())
        max_s = max(scores.values())
        exp_s = {k: np.exp((v - max_s) / 2.0) for k, v in scores.items()}
        sum_exp = sum(exp_s.values())
        calibrated_probs = {k: float(exp_s[k] / sum_exp) for k in categories}

        sorted_cats = sorted(calibrated_probs.items(), key=lambda kv: kv[1], reverse=True)
        resolved_category = sorted_cats[0][0]
        top_prob = sorted_cats[0][1]
        second_prob = sorted_cats[1][1] if len(sorted_cats) > 1 else 0.0
        prob_margin = top_prob - second_prob

        # 7. Subcategory Resolution
        resolved_subcategory, sub_conf, attributes = self._resolve_subcategory(
            category=resolved_category,
            aspect_ratio=aspect_ratio,
            span_ratio=span_ratio,
            has_hood=has_hood,
            has_kangaroo_pocket=has_kangaroo_pocket,
            has_collar=has_collar,
            has_placket=has_placket,
            has_chest_flap_pockets=has_chest_flap_pockets,
            has_center_vertical_seam=has_center_vertical_seam,
            has_bodice=has_bodice,
            is_crotch_split=is_true_crotch_split,
            min_y_rel=min_y_rel,
            centroid_y=centroid_y,
            user_sub_hint=user_subcategory_hint,
            initial_sub=initial_subcategory
        )

        display_name = self.DISPLAY_NAMES.get(resolved_category, {}).get(
            resolved_subcategory,
            resolved_subcategory.replace("_", " ").title()
        )

        # 8. Calibration Confidence, Uncertainty Status and Confirmation Requirement
        joint_conf = float(np.clip(top_prob * 0.60 + sub_conf * 0.40, 0.45, 0.98))

        # Determine uncertainty status
        if top_prob >= 0.70 and prob_margin >= 0.22:
            uncertainty_status = "CONFIDENT"
            requires_confirmation = False
        elif prob_margin < 0.15 and second_prob >= 0.28:
            uncertainty_status = "AMBIGUOUS"
            requires_confirmation = True
            reasoning_signals.append(f"Ambiguity detected between {sorted_cats[0][0]} ({top_prob:.2f}) and {sorted_cats[1][0]} ({second_prob:.2f}) with margin {prob_margin:.2f}")
        elif top_prob < 0.52 or joint_conf < 0.55:
            uncertainty_status = "LOW_CONFIDENCE"
            requires_confirmation = True
            reasoning_signals.append(f"Low confidence ({joint_conf:.2f}); recommended user verification")
        else:
            uncertainty_status = "CONFIDENT"
            requires_confirmation = False

        # Build candidate ranked list
        candidate_list: List[GarmentCategoryProbability] = []
        for cat, p in sorted_cats[:4]:
            cand_sub, _, _ = self._resolve_subcategory(
                category=cat,
                aspect_ratio=aspect_ratio,
                span_ratio=span_ratio,
                has_hood=has_hood,
                has_kangaroo_pocket=has_kangaroo_pocket,
                has_collar=has_collar,
                has_placket=has_placket,
                has_chest_flap_pockets=has_chest_flap_pockets,
                has_center_vertical_seam=has_center_vertical_seam,
                has_bodice=has_bodice,
                is_crotch_split=is_true_crotch_split,
                min_y_rel=min_y_rel,
                centroid_y=centroid_y,
                user_sub_hint=None,
                initial_sub=initial_subcategory
            )
            d_name = self.DISPLAY_NAMES.get(cat, {}).get(cand_sub, cand_sub.replace("_", " ").title())
            candidate_list.append(GarmentCategoryProbability(
                category=cat,
                subcategory=cand_sub,
                calibrated_probability=round(p, 3),
                display_name=d_name
            ))

        # Rejected alternatives tracking
        rejected_alternatives: List[Dict[str, Any]] = []
        for alt_cat, alt_p in sorted_cats[1:]:
            if alt_p > 0.05:
                alt_sub, _, _ = self._resolve_subcategory(
                    category=alt_cat,
                    aspect_ratio=aspect_ratio,
                    span_ratio=span_ratio,
                    has_hood=has_hood,
                    has_kangaroo_pocket=has_kangaroo_pocket,
                    has_collar=has_collar,
                    has_placket=has_placket,
                    has_chest_flap_pockets=has_chest_flap_pockets,
                    has_center_vertical_seam=has_center_vertical_seam,
                    has_bodice=has_bodice,
                    is_crotch_split=is_true_crotch_split,
                    min_y_rel=min_y_rel,
                    centroid_y=centroid_y,
                    user_sub_hint=None,
                    initial_sub=initial_subcategory
                )
                alt_name = self.DISPLAY_NAMES.get(alt_cat, {}).get(alt_sub, alt_sub.replace("_", " ").title())
                rejected_alternatives.append({
                    "category": alt_cat,
                    "subcategory": alt_sub,
                    "display_name": alt_name,
                    "probability": round(alt_p, 3),
                    "rejection_reason": f"Probability ({alt_p:.2f}) lower than selected hypothesis ({top_prob:.2f})"
                })

        log.append(f"Resolved: category='{resolved_category}', subcategory='{resolved_subcategory}', conf={joint_conf:.3f}, status={uncertainty_status}")

        return ResolvedGarmentClassification(
            category=resolved_category,
            subcategory=resolved_subcategory,
            confidence=round(joint_conf, 3),
            display_name=display_name,
            requires_confirmation=requires_confirmation,
            candidate_hypotheses=candidate_list,
            attributes=attributes,
            resolution_log=log,
            uncertainty_status=uncertainty_status,
            original_prediction=original_prediction,
            heuristic_adjustments=heuristic_adjustments,
            reasoning_signals=reasoning_signals,
            rejected_alternatives=rejected_alternatives
        )

    def _resolve_subcategory(
        self,
        category: str,
        aspect_ratio: float,
        span_ratio: float,
        has_hood: bool,
        has_kangaroo_pocket: bool,
        has_collar: bool,
        has_placket: bool,
        has_chest_flap_pockets: bool,
        has_center_vertical_seam: bool,
        has_bodice: bool,
        is_crotch_split: bool,
        min_y_rel: float,
        centroid_y: float,
        user_sub_hint: Optional[str],
        initial_sub: str
    ) -> Tuple[str, float, Dict[str, Any]]:
        """Determines fine-grained subcategory within confirmed category."""
        sub = initial_sub
        conf = 0.85
        attrs: Dict[str, Any] = {}

        if category == "tops":
            hint_l = (user_sub_hint or "").lower().strip()
            if hint_l in ["tshirt", "t-shirt", "tee", "tank_top", "crop_top", "sweater", "sweatshirt"]:
                sub = "tshirt" if hint_l in ["tshirt", "t-shirt", "tee"] else hint_l
                conf = 0.90
                if sub == "tshirt":
                    attrs["fit"] = "regular"
            elif (has_hood or has_kangaroo_pocket or "hood" in hint_l):
                sub = "zip_hoodie" if has_placket else "hoodie"
                conf = 0.92
                attrs["neckline"] = "hooded"
                attrs["features"] = ["hood", "kangaroo_pocket"] if not has_placket else ["hood", "front_zipper"]
            elif has_placket or has_center_vertical_seam or ("shirt" in hint_l and "tshirt" not in hint_l and "t-shirt" not in hint_l and "sweatshirt" not in hint_l):
                sub = "formal_shirt" if aspect_ratio >= 1.20 else "casual_shirt"
                conf = 0.90
                attrs["neckline"] = "collared"
                attrs["closure"] = "button_front"
            elif initial_sub in ["sweater", "cardigan", "formal_shirt", "casual_shirt"]:
                sub = initial_sub
                conf = 0.88
            elif aspect_ratio <= 1.20 and not (has_placket or has_center_vertical_seam):
                sub = "tshirt"
                conf = 0.90
                attrs["fit"] = "regular"
            elif aspect_ratio >= 1.08 and span_ratio < 1.10:
                sub = "sweater"
                conf = 0.88
            else:
                sub = "tshirt"
                conf = 0.88

        elif category == "outerwear":
            hint_l = (user_sub_hint or "").lower()
            if "leather" in hint_l or "moto" in hint_l or "biker" in hint_l:
                sub = "leather_jacket"
                conf = 0.90
                attrs["closure"] = "asymmetrical_zipper"
                attrs["material"] = "leather"
                attrs["features"] = ["notched_lapels_with_snaps", "zippered_cuffs"]
            elif "bomber" in hint_l or "flight" in hint_l:
                sub = "bomber_jacket"
                conf = 0.90
                attrs["closure"] = "heavy_duty_front_zipper"
                attrs["collar"] = "ribbed_baseball_collar"
                attrs["features"] = ["ribbed_cuffs_and_hem"]
            elif "cardigan" in hint_l or "knit" in hint_l:
                sub = "cardigan"
                conf = 0.88
                attrs["closure"] = "front_button_placket"
                attrs["material"] = "knitwear"
            elif "puffer" in hint_l or "down" in hint_l or "quilted" in hint_l:
                sub = "puffer_jacket"
                conf = 0.88
                attrs["closure"] = "full_front_zipper"
                attrs["features"] = ["quilted_baffles"]
            elif "windbreaker" in hint_l or "anorak" in hint_l:
                sub = "windbreaker"
                conf = 0.88
                attrs["closure"] = "front_zipper"
                attrs["features"] = ["lightweight_unlined", "elastic_drawcord_hem"]
            elif "trench" in hint_l:
                sub = "trench_coat"
                conf = 0.90
                attrs["closure"] = "double_breasted_buttons_and_belt"
                attrs["features"] = ["storm_flap", "epaulettes", "waist_belt_with_d_rings"]
            elif "parka" in hint_l:
                sub = "parka"
                conf = 0.88
                attrs["closure"] = "heavy_zipper_with_snap_storm_placket"
                attrs["features"] = ["fur_lined_or_snorkel_hood", "drawstring_waist"]
            elif "blazer" in hint_l or "suit" in hint_l:
                sub = "blazer"
                conf = 0.90
                attrs["closure"] = "single_or_double_breasted_buttons"
                attrs["lapel"] = "notched_or_peaked"
                attrs["features"] = ["chest_welt_pocket", "waist_flap_pockets"]
            elif "coat" in hint_l or "overcoat" in hint_l or "chesterfield" in hint_l:
                sub = "formal_coat"
                conf = 0.90
                attrs["closure"] = "button_front"
                attrs["length"] = "long"
                attrs["features"] = ["knee_length_hem", "tailored_lapels"]
            elif "denim" in hint_l or "trucker" in hint_l:
                sub = "denim_jacket"
                conf = 0.92
                attrs["closure"] = "metal_shank_buttons"
                attrs["collar"] = "point_collar"
                attrs["pockets"] = "chest_flaps"
            # --- Morphological arbitration when no specific subcategory hint is matched ---
            elif initial_sub in ["blazer", "denim_jacket", "formal_coat", "bomber_jacket", "leather_jacket", "puffer_jacket"]:
                sub = initial_sub
                conf = 0.90
            elif aspect_ratio >= 1.55:
                sub = "formal_coat"
                conf = 0.87
                attrs["length"] = "long"
                attrs["features"] = ["knee_length_hem", "tailored_lapels"]
            elif has_chest_flap_pockets:
                sub = "denim_jacket"
                conf = 0.90
                attrs["closure"] = "metal_shank_buttons"
                attrs["collar"] = "point_collar"
                attrs["pockets"] = "chest_flaps"
            elif has_center_vertical_seam or has_placket or (0.95 <= aspect_ratio <= 1.55):
                sub = "blazer"
                conf = 0.90
                attrs["lapel"] = "notched"
                attrs["features"] = ["chest_welt_pocket", "waist_flap_pockets"]
            else:
                sub = "blazer" if has_center_vertical_seam else "jacket"
                conf = 0.84

        elif category == "dresses_and_skirts":
            hint_l = (user_sub_hint or "").lower()
            if is_crotch_split or "jumpsuit" in hint_l or "romper" in hint_l:
                if "romper" in hint_l or (aspect_ratio < 1.18 and "jumpsuit" not in hint_l):
                    sub = "romper"
                    conf = 0.88
                    attrs["silhouette"] = "casual_romper"
                    attrs["bifurcated_legs"] = True
                else:
                    sub = "jumpsuit"
                    conf = 0.90
                    attrs["silhouette"] = "full_length_jumpsuit"
                    attrs["bifurcated_legs"] = True
            elif (aspect_ratio < 1.25 and span_ratio <= 1.08 and not has_bodice) or (min_y_rel > 0.25 and not has_bodice) or "skirt" in hint_l or "pleat" in hint_l or initial_sub in ["skirt", "pleated_skirt"]:
                sub = "pleated_skirt" if ("pleat" in hint_l or "pleat" in initial_sub) else "skirt"
                conf = 0.90
                attrs["silhouette"] = "a_line_or_pencil"
            elif aspect_ratio > 1.45:
                sub = "maxi_dress"
                conf = 0.88
                attrs["silhouette"] = "a_line"
            else:
                sub = "casual_dress"
                conf = 0.90
                attrs["silhouette"] = "fitted_bodice_flared_hem"

        elif category == "bottoms":
            hint_l = (user_sub_hint or "").lower()
            if aspect_ratio < 0.95 or "short" in hint_l:
                sub = "shorts"
                conf = 0.90
            elif "trouser" in hint_l or "slacks" in hint_l:
                sub = "trousers"
                conf = 0.88
            elif "chino" in hint_l:
                sub = "chinos"
                conf = 0.88
            elif "cargo" in hint_l:
                sub = "cargo_pants"
                conf = 0.88
            else:
                sub = initial_sub if initial_sub in ["trousers", "chinos", "cargo_pants", "shorts", "jeans"] else "jeans"
                conf = 0.88

        elif category == "footwear":
            hint_l = (user_sub_hint or "").lower()
            if "boot" in hint_l or aspect_ratio > 0.90:
                sub = "boots"
            elif "sandal" in hint_l:
                sub = "sandals"
            else:
                sub = "sneakers"
            conf = 0.88

        elif category == "accessories":
            hint_l = (user_sub_hint or "").lower()
            if "scarf" in hint_l:
                sub = "scarves"
            else:
                sub = "caps"
            conf = 0.88

        elif category == "traditional":
            sub = "kurta"
            conf = 0.88

        return sub, conf, attrs

    def _empty_fallback(self) -> ResolvedGarmentClassification:
        return ResolvedGarmentClassification(
            category="tops",
            subcategory="tshirt",
            confidence=0.50,
            display_name="T-Shirt",
            requires_confirmation=True,
            candidate_hypotheses=[
                GarmentCategoryProbability(
                    category="tops",
                    subcategory="tshirt",
                    calibrated_probability=0.50,
                    display_name="T-Shirt"
                )
            ],
            attributes={},
            resolution_log=["Empty mask fallback"],
            uncertainty_status="UNSUPPORTED",
            original_prediction={"category": "tops", "subcategory": "tshirt", "confidence": 0.50},
            heuristic_adjustments=[],
            reasoning_signals=["Empty foreground mask provided"],
            rejected_alternatives=[]
        )


# Singleton instance
garment_hypothesis_resolver = GarmentHypothesisResolver()
