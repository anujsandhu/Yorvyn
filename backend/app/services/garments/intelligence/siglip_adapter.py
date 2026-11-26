"""
YORVYN — Generic CLIP visual-language attribute prompt adapter
Uses CLIP logits with an uncalibrated sigmoid transform; it does not load SigLIP.
"""

import time
import math
import logging
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image
import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# Attribute query banks
ATTRIBUTE_QUERY_GROUPS = {
    "pattern": {
        "solid": "solid uniform monochrome color without print or pattern",
        "striped": "horizontal or vertical striped pattern lines",
        "plaid": "plaid tartan or gingham checkered pattern fabric",
        "graphic": "printed graphic artwork text or illustration on chest",
        "floral": "floral botanical flower print pattern",
        "cable_knit": "textured braided cable-knit sweater texture",
        "checkered": "grid checkerboard pattern"
    },
    "sleeve_type": {
        "long_sleeve": "full length long sleeves reaching the wrists",
        "short_sleeve": "short sleeves ending around mid-bicep",
        "sleeveless": "sleeveless without sleeves bare arms",
        "raglan": "raglan continuous shoulder sleeve construction"
    },
    "neckline_and_collar": {
        "hooded": "hooded cowl with attached hood over neck",
        "crew_neck": "round circular crewneck ribbed collar",
        "v_neck": "v-shaped v-neckline opening",
        "mandarin_collar": "standing upright mandarin collar band",
        "button_down_collar": "folded shirt collar with points and button placket",
        "spread_collar": "wide formal spread shirt collar",
        "turtle_neck": "high folded turtleneck collar covering neck"
    },
    "closure": {
        "pullover": "pullover garment without front opening or buttons",
        "front_zipper": "metal or plastic front zipper running down center",
        "full_button_placket": "vertical row of buttons along front placket",
        "drawstring": "adjustable drawstring ties with eyelets"
    },
    "pockets": {
        "kangaroo_pocket": "large front kangaroo pouch pocket on lower torso",
        "chest_pockets": "two chest patch pockets with flaps",
        "welt_pockets": "slit welt side hand pockets",
        "patch_pockets": "sewn exterior patch pockets",
        "five_pocket": "classic five-pocket denim jean styling"
    },
    "fit": {
        "regular": "standard regular fit garment silhouette",
        "oversized": "baggy oversized drop-shoulder loose silhouette",
        "slim": "fitted slim snug silhouette hugging torso",
        "relaxed": "relaxed casual comfortable fit"
    },
    "fabric_texture": {
        "cotton_fleece": "soft heavyweight cotton fleece or french terry fabric",
        "denim_twill": "rugged diagonal denim twill weave fabric",
        "ribbed_knit": "ribbed knitted wool or acrylic yarn texture",
        "smooth_cotton": "smooth lightweight woven or jersey cotton fabric",
        "woven_wool": "tailored structured woven wool suit fabric"
    }
}


class SigLIPAdapter:
    """
    Generic CLIP prompt-score adapter with a sigmoid score transform.
    The transformed scores are uncalibrated and are not SigLIP probabilities.
    """

    def __init__(self, device: Optional[str] = None):
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device
        self.model_name = "OpenAI CLIP ViT-B/32 with sigmoid score transform (not SigLIP)"
        self.execution_backend = "uninitialized"
        self._clip_model = None
        self._processor = None
        logger.info(f"Initialized SigLIPAdapter on {self.device}")

    def _ensure_model(self):
        """Loads generic CLIP weights from the local cache without downloading models."""
        if self._clip_model is not None:
            return

        from transformers import CLIPModel, CLIPProcessor
        try:
            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True)
            self._clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True).to(self.device)
        except Exception as exc:
            raise RuntimeError(f"Cached generic CLIP weights are unavailable; network downloads are disabled: {exc}") from exc
        self._clip_model.eval()
        self.execution_backend = "cached_generic_openai_clip"

    def extract_attributes(self, image: Image.Image) -> Dict[str, Any]:
        """
        Scores attribute prompts with a sigmoid transform; probabilities are not calibrated.
        """
        t0 = time.perf_counter()
        self._ensure_model()

        results: Dict[str, Any] = {}
        all_attr_keys: List[Tuple[str, str]] = []
        all_queries: List[str] = []

        for group_name, query_dict in ATTRIBUTE_QUERY_GROUPS.items():
            for attr_name, query_text in query_dict.items():
                all_attr_keys.append((group_name, attr_name))
                all_queries.append(query_text)

        with torch.no_grad():
            inputs = self._processor(
                text=all_queries,
                images=image.convert("RGB"),
                return_tensors="pt",
                padding=True
            ).to(self.device)

            outputs = self._clip_model(**inputs)
            # Apply an uncalibrated sigmoid transform to generic CLIP similarity logits.
            logits = outputs.logits_per_image[0]  # shape: (N,)
            # Temperature-scaled centered sigmoid
            scaled_logits = (logits - torch.mean(logits)) / (torch.std(logits) + 1e-6)
            sigmoid_probs = torch.sigmoid(scaled_logits * 1.5).cpu().numpy()

        grouped_scores: Dict[str, Dict[str, float]] = {g: {} for g in ATTRIBUTE_QUERY_GROUPS}
        for (g, attr), prob in zip(all_attr_keys, sigmoid_probs):
            grouped_scores[g][attr] = float(prob)

        # Select highest-scoring or thresholded candidates per group
        pattern_cand = max(grouped_scores["pattern"].items(), key=lambda kv: kv[1])
        sleeve_cand = max(grouped_scores["sleeve_type"].items(), key=lambda kv: kv[1])
        neck_cand = max(grouped_scores["neckline_and_collar"].items(), key=lambda kv: kv[1])
        closure_cand = max(grouped_scores["closure"].items(), key=lambda kv: kv[1])
        fit_cand = max(grouped_scores["fit"].items(), key=lambda kv: kv[1])
        texture_cand = max(grouped_scores["fabric_texture"].items(), key=lambda kv: kv[1])

        # Active pockets: any pocket with probability > 0.40
        active_pockets = [
            pocket for pocket, prob in grouped_scores["pockets"].items()
            if prob >= 0.40
        ]
        if not active_pockets:
            top_pocket = max(grouped_scores["pockets"].items(), key=lambda kv: kv[1])
            if top_pocket[1] > 0.30:
                active_pockets.append(top_pocket[0])

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "pattern": pattern_cand[0],
            "pattern_confidence": pattern_cand[1],
            "sleeve_type": sleeve_cand[0],
            "sleeve_confidence": sleeve_cand[1],
            "neckline": neck_cand[0],
            "neckline_confidence": neck_cand[1],
            "closure": closure_cand[0],
            "closure_confidence": closure_cand[1],
            "fit": fit_cand[0],
            "fit_confidence": fit_cand[1],
            "fabric_texture": texture_cand[0],
            "fabric_confidence": texture_cand[1],
            "detected_pockets": active_pockets,
            "raw_scores": grouped_scores,
            "latency_ms": latency_ms,
            "device": str(self.device),
            "model": self.model_name,
            "execution_backend": self.execution_backend,
            "weights_loaded": self._clip_model is not None,
            "scores_calibrated": False
        }
