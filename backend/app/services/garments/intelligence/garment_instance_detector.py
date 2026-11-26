"""
YORVYN — Multi-Garment Instance Detection & Scene Perception Engine.
Detects, isolates, segments, and classifies individual garments in complex scenes,
including on-body ensembles, outfit grids, flat-lays, folded clothes, and multi-piece garments.
Guarantees discrete instance records, hole preservation, and aspect-ratio-preserving letterboxing.
"""

import time
import uuid
import logging
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from PIL import Image
import cv2

from backend.app.models.garment_instance_models import (
    GarmentInstanceRecord,
    MultiGarmentSceneAnalysis
)
from backend.app.services.garments.segmentation import (
    human_parsing_segmenter,
    segmenter_registry,
    GarmentSegmentationOutput
)
from backend.app.services.garments.segmentation.human_parsing_segmenter import (
    PARSING_CLASSES,
    PERSON_CLASSES,
    GARMENT_CLASSES
)
from .universal_garment_classifier import universal_garment_classifier, find_closest_fashion_color
from .aspect_ratio_preprocessor import (
    letterbox_image,
    crop_garment_instance,
    pil_to_data_url,
    NEUTRAL_GRAY
)

logger = logging.getLogger(__name__)

# Mapping from Human Parsing semantic class IDs to canonical YORVYN domain categories
PARSING_TO_DOMAIN: Dict[int, str] = {
    4: "tops",          # Upper-clothes
    5: "skirt",         # Skirt
    6: "bottoms",       # Pants
    7: "dress",         # Dress
    8: "accessories",   # Belt
    9: "footwear",      # Left-shoe
    10: "footwear",     # Right-shoe
    16: "accessories",  # Bag
    17: "accessories",  # Scarf
    1: "accessories"    # Hat
}


class GarmentInstanceDetector:
    """
    Autonomous multi-garment instance detector and segmentation analyzer.
    Extracts every wearable garment as an independent instance record.
    """

    def __init__(self):
        self._model_version = "14.4.0-instance-detector"

    def detect_instances(
        self,
        image: Image.Image,
        category_hint: Optional[str] = None
    ) -> MultiGarmentSceneAnalysis:
        """
        Executes end-to-end multi-garment detection and segmentation.
        """
        t0 = time.perf_counter()
        rgb_img = image.convert("RGB")
        orig_w, orig_h = rgb_img.size
        total_px = orig_w * orig_h

        instances: List[GarmentInstanceRecord] = []
        detected_categories: List[str] = []

        # ── 1. Semantic Human Parsing Pass ───────────────────────────────────
        pred_seg, conf_seg = human_parsing_segmenter.parse_full_body(rgb_img)
        img_type, body_metrics = human_parsing_segmenter.classify_image_type(rgb_img, pred_seg)

        person_ratio = body_metrics.get("person_ratio", 0.0)
        has_real_person = (
            person_ratio >= 0.015 or
            (body_metrics.get("Face", 0.0) + body_metrics.get("Hair", 0.0) > 0.008) or
            (body_metrics.get("Left-arm", 0.0) + body_metrics.get("Right-arm", 0.0) > 0.008) or
            (body_metrics.get("Left-leg", 0.0) + body_metrics.get("Right-leg", 0.0) > 0.008)
        )

        # ── 2. Strategy A: Semantic Garment Classes ──────────────────────────
        # Target classes: upper-clothes (4), pants (6), dress (7), skirt (5),
        # left-shoe (9), right-shoe (10), bag (16), scarf (17), hat (1), belt (8)
        target_classes = [4, 6, 7, 5, 9, 10, 16, 17, 1, 8]

        for cls_id in target_classes:
            raw_mask = (pred_seg == cls_id).astype(np.uint8)
            cls_name = PARSING_CLASSES.get(cls_id, "Garment")

            is_footwear = cls_id in (9, 10)
            is_accessory = cls_id in (1, 8, 16, 17)
            min_class_px = (0.0010 * total_px) if is_footwear else ((0.0014 * total_px) if is_accessory else (0.0045 * total_px))

            cls_px = int(np.sum(raw_mask))
            if cls_px < min_class_px:
                continue

            # Connected components to isolate multiple garments of the same class (e.g. left & right shoes, folded stacks)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(raw_mask, connectivity=8)
            min_comp_area = (0.0008 * total_px) if is_footwear else ((0.0012 * total_px) if is_accessory else (0.0035 * total_px))

            for label_idx in range(1, num_labels):
                comp_area = stats[label_idx, cv2.CC_STAT_AREA]
                if comp_area < min_comp_area:
                    continue

                comp_mask = (labels == label_idx).astype(np.uint8)

                # Cleanse human skin/limbs/hair from this instance mask
                exclusion_mask = np.zeros((orig_h, orig_w), dtype=bool)
                for p_cls in PERSON_CLASSES | {0}:
                    exclusion_mask |= (pred_seg == p_cls)
                for other_g in GARMENT_CLASSES:
                    if other_g != cls_id:
                        exclusion_mask |= (pred_seg == other_g)

                cleansed_mask = comp_mask.copy()
                cleansed_mask[exclusion_mask] = 0

                # Morphological closing to seal internal micro-gaps while preserving true openings
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3) if (is_footwear or is_accessory) else (5, 5))
                refined_mask = cv2.morphologyEx(cleansed_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

                mask_px = int(np.sum(refined_mask))
                min_mask_px = (0.0008 * total_px) if is_footwear else ((0.0010 * total_px) if is_accessory else (0.0030 * total_px))
                if mask_px < min_mask_px:
                    continue

                # Bounding box
                x = stats[label_idx, cv2.CC_STAT_LEFT]
                y = stats[label_idx, cv2.CC_STAT_TOP]
                w = stats[label_idx, cv2.CC_STAT_WIDTH]
                h = stats[label_idx, cv2.CC_STAT_HEIGHT]
                bbox = (int(x), int(y), int(min(orig_w, x + w)), int(min(orig_h, y + h)))

                inst_record = self._build_instance_record(
                    image=rgb_img,
                    mask=refined_mask,
                    bbox=bbox,
                    semantic_domain=PARSING_TO_DOMAIN.get(cls_id, "tops"),
                    source_strategy="human_parsing_semantic",
                    instance_index=len(instances),
                    total_px=total_px,
                    photography_domain="on_body" if has_real_person else "flat_lay"
                )
                instances.append(inst_record)
                detected_categories.append(inst_record.category)

                # Under-layer detection: ONLY for genuine outer layers (jacket, coat, blazer, open hoodie)
                # Check if outer garment subcategory or parsing indicates open outer layer
                is_outer_layer = (inst_record.subcategory in ["jacket", "blazer", "coat", "cardigan", "leather_jacket", "denim_jacket", "bomber_jacket"] or
                                  "jacket" in inst_record.category or "coat" in inst_record.category)
                
                if cls_id == 4 and comp_area > (0.15 * total_px) and has_real_person and is_outer_layer:
                    # Look at chest center between lapels
                    cy, cx = int(centroids[label_idx][1]), int(centroids[label_idx][0])
                    inner_h = int(h * 0.38)
                    inner_w = int(w * 0.28)
                    iy1, iy2 = max(0, cy - inner_h // 2), min(orig_h, cy + inner_h // 2)
                    ix1, ix2 = max(0, cx - inner_w // 2), min(orig_w, cx + inner_w // 2)
                    inner_crop = rgb_img.crop((ix1, iy1, ix2, iy2))
                    inner_arr = np.array(inner_crop)
                    
                    # Verify true chromatic and gradient contrast between inner chest and outer lapels
                    outer_left_crop = rgb_img.crop((max(0, ix1 - inner_w // 2), iy1, ix1, iy2))
                    outer_arr = np.array(outer_left_crop)
                    if outer_arr.size > 0 and inner_arr.size > 0:
                        chroma_diff = np.linalg.norm(np.mean(inner_arr, axis=(0, 1)) - np.mean(outer_arr, axis=(0, 1)))
                    else:
                        chroma_diff = 0.0

                    if chroma_diff > 32.0 and np.std(inner_arr) > 22.0 and (inner_w * inner_h) > (0.015 * total_px):
                        inner_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
                        inner_mask[iy1:iy2, ix1:ix2] = 255
                        under_inst = self._build_instance_record(
                            image=rgb_img,
                            mask=inner_mask,
                            bbox=(ix1, iy1, ix2, iy2),
                            semantic_domain="tops",
                            source_strategy="underlayer_extraction",
                            instance_index=len(instances),
                            total_px=total_px,
                            photography_domain="on_body"
                        )
                        under_inst.category = "shirt"
                        under_inst.subcategory = "tshirt"
                        instances.append(under_inst)
                        detected_categories.append("shirt")

        # ── 3. Strategy B: Synergistic Salient Multi-Object Contour Extraction ───
        # Only run contour candidate extraction for flat-lays or when no person parsing was found
        if not has_real_person or not instances:
            contour_instances = self._extract_flatlay_contour_instances(
                image=rgb_img,
                existing_instances=instances,
                total_px=total_px
            )
            for c_inst in contour_instances:
                instances.append(c_inst)
                detected_categories.append(c_inst.category)

        # ── 4. Fallback if no discrete instances detected ────────────────────
        if not instances:
            default_bbox = (0, 0, orig_w, orig_h)
            full_mask = np.ones((orig_h, orig_w), dtype=np.uint8) * 255
            fallback_inst = self._build_instance_record(
                image=rgb_img,
                mask=full_mask,
                bbox=default_bbox,
                semantic_domain=category_hint or "tops",
                source_strategy="full_image_fallback",
                instance_index=0,
                total_px=total_px,
                photography_domain="flat_lay" if not has_real_person else "on_body"
            )
            instances.append(fallback_inst)
            detected_categories.append(fallback_inst.category)

        # Filter out noise detections with category-adaptive area thresholds
        filtered_instances: List[GarmentInstanceRecord] = []
        for inst in instances:
            min_area = 0.0025 if inst.category == "footwear" else (0.0030 if inst.category == "accessories" else 0.0070)
            if inst.area_ratio >= min_area and inst.confidence >= 0.44:
                filtered_instances.append(inst)

        if not filtered_instances and instances:
            filtered_instances = [max(instances, key=lambda x: x.area_pixels)]

        # Class-aware hierarchical soft NMS to suppress duplicate overlapping detections
        UPPER_GROUP = {"tops", "shirt", "jacket", "hoodie", "sweater", "outerwear", "dress"}
        LOWER_GROUP = {"bottoms", "pants", "shorts", "skirt"}

        nms_instances: List[GarmentInstanceRecord] = []
        for inst in sorted(filtered_instances, key=lambda x: (x.confidence * x.area_pixels), reverse=True):
            overlap = False
            for kept in nms_instances:
                iou = self._compute_iou(inst.bbox, kept.bbox)
                # Same exact category suppression
                if inst.category == kept.category and iou > 0.35:
                    overlap = True
                    break
                # Same taxonomic group (both upper or both lower)
                both_upper = (inst.category in UPPER_GROUP and kept.category in UPPER_GROUP)
                both_lower = (inst.category in LOWER_GROUP and kept.category in LOWER_GROUP)
                if both_upper or both_lower:
                    is_underlayer = (inst.source_strategy == "underlayer_extraction" or 
                                     kept.source_strategy == "underlayer_extraction" or
                                     (inst.area_pixels < 0.32 * kept.area_pixels and iou < 0.40))
                    if not is_underlayer and iou > 0.45:
                        overlap = True
                        break
            if not overlap:
                nms_instances.append(inst)

        instances = nms_instances
        # Sort instances by area descending
        instances.sort(key=lambda x: x.area_pixels, reverse=True)
        for idx, inst in enumerate(instances):
            inst.instance_id = f"inst_{idx}_{inst.category}"

        # ── 5. Scene Context & Outfit Grid Reasoning ─────────────────────────
        has_top = any(inst.category in ["tops", "shirt", "hoodie", "jacket"] for inst in instances)
        has_bottom = any(inst.category in ["bottoms", "skirt"] for inst in instances)
        has_footwear = any(inst.category == "footwear" for inst in instances)

        outfit_pairing = has_top and has_bottom
        ensemble_categories = sorted(list(set(detected_categories)))

        if not has_real_person:
            if len(instances) > 1:
                scene_type = "outfit_grid"
            else:
                scene_type = "flat_lay" if img_type == "flat_lay" else "product_packshot"
        else:
            scene_type = "on_body" if len(instances) <= 2 else "lifestyle_ensemble"

        # Prioritize top garment or dress as default selection
        selected_id = instances[0].instance_id
        for inst in instances:
            if inst.category in ["tops", "jacket", "shirt", "hoodie", "dress"]:
                selected_id = inst.instance_id
                break

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return MultiGarmentSceneAnalysis(
            analysis_id=f"scene_{uuid.uuid4().hex[:12]}",
            image_width=orig_w,
            image_height=orig_h,
            scene_type=scene_type,
            total_instances_detected=len(instances),
            instances=instances,
            selected_instance_id=selected_id,
            outfit_pairing_detected=outfit_pairing,
            ensemble_categories=ensemble_categories,
            processing_time_ms=round(elapsed_ms, 2),
            provenance_statement="Analytical multi-garment instance detection & segmentation; genuine neural classification"
        )

    def _extract_flatlay_contour_instances(
        self,
        image: Image.Image,
        existing_instances: List[GarmentInstanceRecord],
        total_px: int
    ) -> List[GarmentInstanceRecord]:
        """
        Extracts separated clothing instances in flat-lay and outfit-grid scenes
        via adaptive background isolation and multi-level contour hierarchy.
        """
        orig_w, orig_h = image.size
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

        # Morphological gradient to highlight garment boundaries
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)

        # Adaptive thresholding
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 25, 4
        )

        # Border-assisted flood fill to isolate table / background
        h, w = gray.shape
        fg_mask = np.zeros((h, w), dtype=np.uint8)
        # Background estimation from corners
        corners = [
            gray[0:15, 0:15], gray[0:15, w-15:w],
            gray[h-15:h, 0:15], gray[h-15:h, w-15:w]
        ]
        bg_mean = float(np.mean([np.mean(c) for c in corners]))
        diff = np.abs(gray.astype(np.float32) - bg_mean)
        fg_mask[diff > 25.0] = 255

        # Refine foreground mask
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        cleaned_fg = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)

        # Connected components for candidate garment clusters
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned_fg, connectivity=8)
        contour_instances: List[GarmentInstanceRecord] = []

        for label_idx in range(1, num_labels):
            area = stats[label_idx, cv2.CC_STAT_AREA]
            if area < (0.008 * total_px):
                continue

            x = stats[label_idx, cv2.CC_STAT_LEFT]
            y = stats[label_idx, cv2.CC_STAT_TOP]
            cw = stats[label_idx, cv2.CC_STAT_WIDTH]
            ch = stats[label_idx, cv2.CC_STAT_HEIGHT]
            cand_bbox = (int(x), int(y), int(min(orig_w, x + cw)), int(min(orig_h, y + ch)))

            # Check overlap with existing semantic instances
            overlap = False
            for exist in existing_instances:
                ex_bbox = exist.bbox
                iou = self._compute_iou(cand_bbox, ex_bbox)
                if iou > 0.40:
                    overlap = True
                    break
            if overlap:
                continue

            cand_mask = (labels == label_idx).astype(np.uint8)

            inst_record = self._build_instance_record(
                image=image,
                mask=cand_mask,
                bbox=cand_bbox,
                semantic_domain="tops", # Will be classified by neural network
                source_strategy="contour_cluster",
                instance_index=len(existing_instances) + len(contour_instances),
                total_px=total_px,
                photography_domain="flat_lay"
            )
            # Only retain if classifier recognized it as a valid garment with confidence
            if inst_record.confidence >= 0.35 and inst_record.selective_outcome != "rejected_invalid_input":
                contour_instances.append(inst_record)

        return contour_instances

    def _build_instance_record(
        self,
        image: Image.Image,
        mask: np.ndarray,
        bbox: Tuple[int, int, int, int],
        semantic_domain: str,
        source_strategy: str,
        instance_index: int,
        total_px: int,
        photography_domain: str
    ) -> GarmentInstanceRecord:
        """
        Builds a comprehensive GarmentInstanceRecord with isolated crop, classification,
        hole extraction, color analysis, and metadata.
        """
        orig_w, orig_h = image.size
        min_x, min_y, max_x, max_y = bbox
        norm_bbox = (
            round(min_x / max(orig_w, 1), 4),
            round(min_y / max(orig_h, 1), 4),
            round(max_x / max(orig_w, 1), 4),
            round(max_y / max(orig_h, 1), 4)
        )
        mask_px = int(np.sum(mask > 0))

        # 1. Extract contours and internal holes (preserving genuine neck/arm openings)
        outer_contour: List[List[int]] = []
        holes: List[List[List[int]]] = []
        try:
            contours, hierarchy = cv2.findContours(
                mask.copy(), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours and hierarchy is not None:
                # Find largest outer contour
                areas = [cv2.contourArea(c) for c in contours]
                max_idx = int(np.argmax(areas))
                outer_contour = contours[max_idx].reshape(-1, 2).tolist()

                # Find child contours (holes) belonging to the main outer contour
                for c_idx, h_info in enumerate(hierarchy[0]):
                    # h_info: [Next, Previous, First_Child, Parent]
                    parent_idx = h_info[3]
                    if parent_idx == max_idx:
                        hole_area = cv2.contourArea(contours[c_idx])
                        # Keep holes that are at least 0.5% of main garment area
                        if hole_area >= (0.005 * areas[max_idx]):
                            holes.append(contours[c_idx].reshape(-1, 2).tolist())
        except Exception as e:
            logger.warning(f"Contour extraction error: {e}")

        # 2. Extract aspect-ratio-preserving neutral letterboxed crop
        crop_pil, crop_meta = crop_garment_instance(
            image=image,
            bbox=bbox,
            mask=mask,
            pad_factor=0.06,
            target_size=(224, 224),
            suppress_background=False
        )
        crop_data_url = pil_to_data_url(crop_pil, format="JPEG", quality=88)

        # 3. Create alpha mask data URL
        alpha_mask_pil = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        mask_data_url = pil_to_data_url(alpha_mask_pil, format="PNG")

        # 4. Neural classification on isolated garment crop
        # Let the neural model predict directly from the isolated letterboxed crop.
        # Only pass semantic domain hint for accessories/footwear
        clf_hint = semantic_domain if semantic_domain in ["footwear", "accessories"] else None
        clf_result = universal_garment_classifier.classify_hierarchical(
            image=crop_pil,
            alpha_mask=(mask * 255).astype(np.uint8),
            user_category_hint=clf_hint
        )

        category = clf_result.get("category", semantic_domain)
        subcategory = clf_result.get("subcategory", "tshirt")

        # Derive initial fabric family
        fabric_family = "cotton_jersey"
        if "fleece" in subcategory or "hoodie" in subcategory:
            fabric_family = "fleece"
        elif "denim" in subcategory or "jean" in subcategory:
            fabric_family = "denim"
        elif "shirt" in subcategory or "blouse" in subcategory:
            fabric_family = "cotton_poplin"
        elif "leather" in subcategory:
            fabric_family = "leather"
        elif "knit" in subcategory or "sweater" in subcategory:
            fabric_family = "ribbed_knit"

        # Anatomical spatial validity constraint: Upper-body cannot be bottoms; legs cannot be tops
        if source_strategy == "human_parsing_semantic":
            if semantic_domain == "tops" and category in ["bottoms", "footwear", "accessories"]:
                # Denim/corduroy upper garments often confuse fabric classifiers into predicting jeans
                category = "jacket" if ("jacket" in subcategory or "denim" in subcategory or "denim" in fabric_family) else "tops"
                subcategory = "denim_jacket" if ("denim" in fabric_family or "jean" in subcategory) else "casual_jacket"
            elif semantic_domain == "bottoms" and category in ["tops", "jacket", "hoodie", "shirt", "dress"]:
                category = "bottoms"
                subcategory = "jeans" if ("denim" in fabric_family or "jean" in subcategory) else "trousers"
            elif semantic_domain == "skirt" and category not in ["skirt", "dress"]:
                category = "skirt"
                subcategory = "skirt"
            elif semantic_domain == "footwear":
                category = "footwear"
                if subcategory in ["tshirt", "jeans", "dress"]:
                    subcategory = "sneakers"

        display_name = subcategory.replace("_", " ").title()
        confidence = float(clf_result.get("confidence", 0.70))
        selective_outcome = clf_result.get("decision_reason", "accepted_high_confidence")

        # 5. Extract dominant colors from masked region
        dominant_colors = self._extract_colors(image, mask, bbox)

        inst_id = f"inst_{instance_index}_{category}"

        return GarmentInstanceRecord(
            instance_id=inst_id,
            bbox=bbox,
            normalized_bbox=norm_bbox,
            area_pixels=mask_px,
            area_ratio=round(mask_px / max(total_px, 1), 4),
            category=category,
            subcategory=subcategory,
            display_name=display_name,
            confidence=round(confidence, 4),
            selective_outcome=selective_outcome,
            photography_domain=photography_domain,
            visibility_ratio=1.0,
            occlusion_ratio=0.0,
            outer_contour=outer_contour,
            holes=holes,
            mask_data_url=mask_data_url,
            crop_data_url=crop_data_url,
            letterbox_metadata=crop_meta,
            dominant_colors=dominant_colors,
            fabric_family=fabric_family,
            silhouette="regular",
            sleeve_type="long_sleeve" if "long" in subcategory or "hoodie" in subcategory or "jacket" in subcategory else "short_sleeve",
            neckline="hooded" if "hoodie" in subcategory else ("collar" if "shirt" in subcategory else "crew_neck"),
            length="full_length" if category in ["bottoms", "dress"] else "regular",
            visible_components=["hood", "pocket"] if "hoodie" in subcategory else ["collar", "cuff"] if "shirt" in subcategory else ["waistband"],
            detector_model=f"segformer_b2_clothes-v2+{source_strategy}",
            source_strategy=source_strategy,
            classifier_model="HierarchicalMultiTaskNetworkV6",
            reconstruction_eligible=confidence >= 0.40 and selective_outcome != "rejected_invalid_input"
        )

    def _extract_colors(
        self,
        image: Image.Image,
        mask: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> List[Dict[str, Any]]:
        """Extracts dominant palette colors from inside the garment mask."""
        min_x, min_y, max_x, max_y = bbox
        img_np = np.array(image.convert("RGB"))
        crop_rgb = img_np[min_y:max_y, min_x:max_x]
        crop_mask = mask[min_y:max_y, min_x:max_x]

        garment_pixels = crop_rgb[crop_mask > 0]
        if len(garment_pixels) < 20:
            return [{"hex": "#2B2D42", "name": "Navy Blue", "percentage": 100.0}]

        # Subsample for speed
        if len(garment_pixels) > 5000:
            indices = np.random.choice(len(garment_pixels), 5000, replace=False)
            garment_pixels = garment_pixels[indices]

        # K-means clustering (k=2)
        pixels_float = np.float32(garment_pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels_float, 2, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

        counts = np.bincount(labels.flatten())
        total = float(len(labels))
        palette = []
        for idx in np.argsort(-counts):
            rgb = tuple(int(v) for v in centers[idx])
            hex_val = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            name, _ = find_closest_fashion_color(rgb)
            pct = float(round((counts[idx] / total) * 100.0, 1))
            palette.append({"hex": hex_val, "name": name, "percentage": pct})

        return palette

    def _compute_iou(self, boxA: Tuple[int, int, int, int], boxB: Tuple[int, int, int, int]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        denom = float(boxAArea + boxBArea - interArea)
        return interArea / denom if denom > 0 else 0.0


# Singleton instance
garment_instance_detector = GarmentInstanceDetector()
