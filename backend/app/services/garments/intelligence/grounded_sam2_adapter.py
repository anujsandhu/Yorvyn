"""
YORVYN — OpenCV garment-region heuristic
Uses thresholding and fixed proportional regions; no Grounding DINO or SAM 2 checkpoints are loaded.
"""

import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np
from PIL import Image
import cv2

import torch

logger = logging.getLogger(__name__)


@dataclass
class DetectedComponent:
    label: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # (ymin, xmin, ymax, xmax) normalized [0, 1]
    mask: Optional[np.ndarray] = None       # 2D uint8 mask
    source_model: str = "grounded_sam2"
    prompt_used: str = ""


class GroundedSAM2Adapter:
    """Heuristic garment-region adapter; not a learned detector or segmenter."""

    def __init__(self, device: Optional[str] = None):
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device
        self.model_version = "OpenCV Otsu silhouette and proportional component heuristic (no SAM2/GroundingDINO weights)"
        logger.info(f"GroundedSAM2Adapter initialized on {self.device}")

    def detect_and_segment(
        self,
        image: Image.Image,
        prompts: Optional[List[str]] = None,
        category: str = "tops",
        subcategory: str = "hoodie"
    ) -> Dict[str, Any]:
        """
        Executes grounded component detection and prompt-based segmentation.
        """
        t0 = time.perf_counter()
        img_np = np.array(image.convert("RGB"))
        h, w = img_np.shape[:2]

        default_prompts = {
            "hoodie": ["hood cowl", "main torso", "left sleeve", "right sleeve", "kangaroo front pocket", "ribbed cuffs", "waistband", "drawstrings"],
            "zip_hoodie": ["hood cowl", "main torso", "zipper placket", "left sleeve", "right sleeve", "split pockets", "cuffs", "waistband"],
            "tshirt": ["crew neckline", "main torso", "short left sleeve", "short right sleeve", "lower hem"],
            "sweatshirt": ["ribbed crewneck", "main torso", "left sleeve", "right sleeve", "ribbed cuffs", "ribbed waistband"],
            "jacket": ["folded collar", "button placket", "chest pockets", "main torso", "left sleeve", "right sleeve", "cuffs", "hem"],
            "shirt": ["tailored button-down collar", "front placket", "main torso", "left sleeve", "right sleeve", "cuffs", "curved hem"],
            "sweater": ["ribbed neck", "knit torso", "left sleeve", "right sleeve", "knit cuffs", "ribbed waistband"],
            "jeans": ["waistband", "left trouser leg", "right trouser leg", "crotch seam", "front pockets", "ankle hems"],
            "trousers": ["waistband", "left trouser leg", "right trouser leg", "crotch seam", "side pockets", "ankle hems"],
            "dress": ["fitted bodice", "scoop neckline", "flared skirt", "lower hemline"],
            "kurta": ["mandarin collar", "button placket", "long tunic torso", "side slits", "straight sleeves", "lower hem"]
        }

        active_prompts = prompts or default_prompts.get(subcategory, default_prompts.get(category, ["garment torso", "sleeves", "hem"]))

        # Perform foreground silhouette extraction
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        bg_is_light = float(np.mean(gray[:10, :10])) > 180.0
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        _, fg_mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        ys, xs = np.where(fg_mask > 20)
        if len(ys) == 0:
            ymin, ymax, xmin, xmax = 0, h, 0, w
        else:
            ymin, ymax = int(np.min(ys)), int(np.max(ys))
            xmin, xmax = int(np.min(xs)), int(np.max(xs))
        gh = max(1, ymax - ymin)
        gw = max(1, xmax - xmin)

        detected_components: Dict[str, DetectedComponent] = {}

        # Synthesize prompt-driven spatial bounding boxes and refined masks
        for p in active_prompts:
            clean_label = p.replace(" ", "_").lower()
            conf = 0.92

            if "hood" in clean_label:
                comp_ymin, comp_ymax = ymin, ymin + int(gh * 0.32)
                comp_xmin, comp_xmax = xmin + int(gw * 0.22), xmin + int(gw * 0.78)
            elif "pocket" in clean_label:
                comp_ymin, comp_ymax = ymin + int(gh * 0.58), ymin + int(gh * 0.84)
                comp_xmin, comp_xmax = xmin + int(gw * 0.28), xmin + int(gw * 0.72)
            elif "left_sleeve" in clean_label or "left_trouser_leg" in clean_label:
                comp_ymin, comp_ymax = ymin + int(gh * 0.12), ymax
                comp_xmin, comp_xmax = xmin, xmin + int(gw * 0.48)
            elif "right_sleeve" in clean_label or "right_trouser_leg" in clean_label:
                comp_ymin, comp_ymax = ymin + int(gh * 0.12), ymax
                comp_xmin, comp_xmax = xmin + int(gw * 0.52), xmax
            elif "waistband" in clean_label:
                comp_ymin, comp_ymax = ymax - int(gh * 0.12), ymax
                comp_xmin, comp_xmax = xmin + int(gw * 0.18), xmin + int(gw * 0.82)
            elif "collar" in clean_label or "neck" in clean_label:
                comp_ymin, comp_ymax = ymin, ymin + int(gh * 0.16)
                comp_xmin, comp_xmax = xmin + int(gw * 0.30), xmin + int(gw * 0.70)
            elif "skirt" in clean_label:
                comp_ymin, comp_ymax = ymin + int(gh * 0.38), ymax
                comp_xmin, comp_xmax = xmin, xmax
            elif "bodice" in clean_label:
                comp_ymin, comp_ymax = ymin, ymin + int(gh * 0.40)
                comp_xmin, comp_xmax = xmin + int(gw * 0.15), xmin + int(gw * 0.85)
            else:  # torso / general
                comp_ymin, comp_ymax = ymin + int(gh * 0.15), ymax - int(gh * 0.10)
                comp_xmin, comp_xmax = xmin + int(gw * 0.20), xmin + int(gw * 0.80)

            comp_mask = np.zeros((h, w), dtype=np.uint8)
            comp_mask[comp_ymin:comp_ymax, comp_xmin:comp_xmax] = fg_mask[comp_ymin:comp_ymax, comp_xmin:comp_xmax]

            detected_components[clean_label] = DetectedComponent(
                label=clean_label,
                confidence=conf,
                bbox=(comp_ymin / h, comp_xmin / w, comp_ymax / h, comp_xmax / w),
                mask=comp_mask,
                source_model=self.model_version,
                prompt_used=p
            )

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "model_version": self.model_version,
            "device": self.device,
            "component_count": len(detected_components),
            "components": detected_components,
            "foreground_mask": fg_mask,
            "latency_ms": latency_ms,
            "execution_provenance": "HEURISTIC_OPENCV_OTSU_AND_PROPORTIONAL_BOXES",
            "weights_loaded": False,
            "model_name": self.model_version
        }


grounded_sam2_adapter = GroundedSAM2Adapter()
