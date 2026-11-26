"""
YORVYN — Generic CLIP prompt-based garment classification adapter
Uses cached generic OpenAI CLIP weights if present; this is not FashionCLIP:
- Full coverage of 15 garment categories
- Multi-template prompt ensembling for robust zero-shot classification
- Subcategory disambiguation (e.g. pullover hoodie vs zip hoodie, plaid shirt vs formal shirt)
- Calibrated softmax distribution, entropy, top-1/top-2 margin, and confidence
- Optimized for Apple Silicon M2 MPS with CPU fallback
"""

import time
import math
import logging
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image
import numpy as np
import torch
import torch.nn.functional as F

from backend.app.models.structured_garment_specification import GarmentCategory

logger = logging.getLogger(__name__)


# 15 Standard Categories with descriptive prompt ensembles
FASHION_CATEGORY_PROMPTS: Dict[GarmentCategory, List[str]] = {
    GarmentCategory.TSHIRT: [
        "a photo of a casual short-sleeve t-shirt, cotton crewneck tee",
        "a studio photograph of a short-sleeve t-shirt top",
        "a casual short sleeve crewneck graphic or plain t-shirt"
    ],
    GarmentCategory.SHIRT: [
        "a photo of a collared button-down shirt with front placket",
        "a studio shot of a tailored dress shirt or casual button-up shirt",
        "a plaid flannel shirt or formal buttoned shirt",
        "a button-front collared shirt"
    ],
    GarmentCategory.HOODIE: [
        "a photo of a hooded sweatshirt, hoodie with a hood and cowl",
        "a studio photograph of a hoodie pullover with kangaroo pocket",
        "a casual fleece hoodie with hood strings",
        "a hooded sweatshirt garment"
    ],
    GarmentCategory.SWEATSHIRT: [
        "a photo of a crewneck sweatshirt without a hood",
        "a studio photograph of a fleece sweatshirt with ribbed collar",
        "a casual long sleeve crew neck sweatshirt",
        "a cotton sweatshirt without hood"
    ],
    GarmentCategory.SWEATER: [
        "a photo of a knitted sweater, wool jumper or knit pullover",
        "a studio photograph of a cable-knit sweater",
        "a ribbed knitted winter sweater",
        "a warm knit cardigan or wool sweater"
    ],
    GarmentCategory.JACKET: [
        "a photo of an outerwear jacket or utility jacket",
        "a studio photograph of a casual outerwear jacket",
        "a tailored blazer or zip-up outerwear jacket"
    ],
    GarmentCategory.COAT: [
        "a photo of a long winter overcoat, trench coat, or heavy wool coat",
        "a studio photograph of a long wool overcoat reaching the knees",
        "a tailored long trench coat outerwear"
    ],
    GarmentCategory.DRESS: [
        "a photo of a women's dress, gown or sundress",
        "a studio photograph of a woman wearing a one-piece dress",
        "a full-length dress or a-line dress covering bodice and skirt",
        "a casual summer dress or evening dress"
    ],
    GarmentCategory.KURTA: [
        "a photo of an Indian ethnic kurta tunic shirt",
        "a studio photograph of a traditional long kurta with mandarin collar",
        "a south asian kurta ethnic tunic"
    ],
    GarmentCategory.TUNIC: [
        "a photo of a loose tunic top, women's long tunic blouse",
        "a studio photograph of a flowy women's tunic top shirt",
        "a long tunic top covering hips"
    ],
    GarmentCategory.JEANS: [
        "a photo of a pair of blue denim jeans pants",
        "a studio photograph of denim blue jeans pants with waistband and pockets",
        "a pair of classic blue denim jeans pants",
        "blue jeans denim pants trousers"
    ],
    GarmentCategory.TROUSERS: [
        "a photo of a pair of tailored trousers, dress slacks, or chino pants",
        "a studio photograph of cotton chino pants or formal trousers",
        "a pair of tailored dress trousers slacks pants"
    ],
    GarmentCategory.SHORTS: [
        "a photo of a pair of casual shorts, short pants ending above the knees",
        "a studio photograph of casual shorts or bermuda shorts",
        "a pair of casual summer shorts"
    ],
    GarmentCategory.SKIRT: [
        "a photo of a women's skirt, midi skirt, mini skirt, or pleated skirt",
        "a studio photograph of a woman's skirt garment without pants legs",
        "a pleated or pencil skirt waist down"
    ],
    GarmentCategory.TRADITIONAL_CLOTHING: [
        "a photo of traditional ethnic sherwani or ceremonial cultural attire",
        "a studio photograph of traditional folk attire or ceremonial sherwani",
        "traditional cultural costume and ethnic ceremonial wear"
    ]
}

# Subcategory definitions per category
SUBCATEGORY_PROMPTS: Dict[GarmentCategory, Dict[str, str]] = {
    GarmentCategory.HOODIE: {
        "pullover_hoodie": "a pullover hoodie with front kangaroo pocket",
        "zip_hoodie": "a full zip hoodie with front zipper and split pockets",
        "oversized_hoodie": "an oversized slouchy streetwear hoodie"
    },
    GarmentCategory.SHIRT: {
        "plaid_flannel_shirt": "a plaid or tartan patterned button-down flannel shirt",
        "formal_dress_shirt": "a crisp solid tailored formal dress shirt with collar",
        "casual_oxford_shirt": "a casual cotton oxford button-down shirt"
    },
    GarmentCategory.JACKET: {
        "denim_jacket": "a classic blue denim trucker jacket with metal buttons",
        "blazer_jacket": "a structured formal tailored suit blazer jacket",
        "bomber_jacket": "a casual nylon or leather bomber jacket with ribbed collar"
    },
    GarmentCategory.SWEATER: {
        "cable_knit_sweater": "a textured cable-knit wool sweater",
        "crewneck_sweater": "a fine knit classic crewneck sweater pullover",
        "turtleneck_sweater": "a ribbed high turtleneck knit sweater"
    },
    GarmentCategory.TSHIRT: {
        "graphic_tshirt": "a printed graphic t-shirt with front artwork or logo",
        "plain_crewneck_tshirt": "a solid plain monochrome cotton crewneck t-shirt",
        "vneck_tshirt": "a casual solid v-neck cotton t-shirt"
    },
    GarmentCategory.JEANS: {
        "classic_denim_jeans": "classic blue five-pocket denim jeans",
        "slim_tapered_jeans": "modern slim fit tapered denim jeans",
        "relaxed_straight_jeans": "relaxed fit straight leg denim jeans"
    },
    GarmentCategory.TROUSERS: {
        "chino_trousers": "casual cotton twill chino trousers",
        "dress_slacks": "formal tailored wool dress slacks trousers",
        "cargo_pants": "casual utility cargo pants with side pockets"
    },
    GarmentCategory.DRESS: {
        "aline_dress": "a flattering fit-and-flare A-line dress",
        "maxi_dress": "a long flowy floor-length casual maxi dress",
        "sheath_dress": "a tailored knee-length sheath dress"
    },
    GarmentCategory.KURTA: {
        "classic_mandarin_kurta": "a classic long cotton kurta with mandarin collar",
        "embroidered_festive_kurta": "an embroidered ethnic festive silk or cotton kurta",
        "short_kurta_tunic": "a modern short length casual kurta tunic"
    },
    GarmentCategory.SWEATSHIRT: {
        "crewneck_sweatshirt": "a classic athletic fleece crewneck sweatshirt",
        "oversized_sweatshirt": "a relaxed drop-shoulder oversized sweatshirt"
    },
    GarmentCategory.COAT: {
        "wool_overcoat": "a tailored long wool tailored overcoat",
        "trench_coat": "a double-breasted belted trench coat"
    },
    GarmentCategory.TUNIC: {
        "boho_flowy_tunic": "a relaxed flowy bohemian tunic blouse",
        "button_front_tunic": "a long button-front tunic shirt"
    },
    GarmentCategory.SHORTS: {
        "denim_shorts": "casual denim jean cut-off shorts",
        "chino_shorts": "clean tailored cotton chino shorts"
    },
    GarmentCategory.SKIRT: {
        "pleated_skirt": "a classic pleated midi or mini skirt",
        "pencil_skirt": "a fitted tailored high-waist pencil skirt"
    },
    GarmentCategory.TRADITIONAL_CLOTHING: {
        "ethnic_sherwani": "a structured formal ethnic sherwani or bandhgala",
        "traditional_tunic": "traditional regional cultural tunic or costume"
    }
}


class FashionCLIPAdapter:
    """
    Generic CLIP adapter; no FashionCLIP-specific checkpoint is loaded.
    Performs multi-template zero-shot identification across 15 fashion categories.
    """

    def __init__(self, device: Optional[str] = None):
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device
        self.model_name = "OpenAI CLIP ViT-B/32 (generic checkpoint; not FashionCLIP)"
        self.execution_backend = "uninitialized"
        self._model = None
        self._processor = None
        self._text_embeddings_cache: Dict[str, torch.Tensor] = {}
        logger.info(f"Initialized FashionCLIPAdapter on {self.device}")

    def _ensure_model(self):
        """Loads generic CLIP weights from the local cache without downloading models."""
        if self._model is not None:
            return

        try:
            from transformers import CLIPModel, CLIPProcessor
            self._processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True)
            self._model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", local_files_only=True).to(self.device)
            self._model.eval()
            self.execution_backend = "cached_generic_openai_clip"
            logger.info(f"Successfully loaded cached generic CLIP model on {self.device}; this is not FashionCLIP")
        except Exception as e:
            logger.error(f"Failed to load CLIP model on {self.device}: {e}")
            raise RuntimeError(f"Cached generic CLIP weights are unavailable; network downloads are disabled: {e}")

    def classify_garment(self, image: Image.Image) -> Dict[str, Any]:
        """
        Classifies garment across all 15 standard categories and extracts subcategory.
        """
        t0 = time.perf_counter()
        self._ensure_model()

        # Build prompt list and category index mapping
        category_list = list(FASHION_CATEGORY_PROMPTS.keys())
        all_prompts: List[str] = []
        prompt_to_category: List[GarmentCategory] = []

        for cat in category_list:
            for p in FASHION_CATEGORY_PROMPTS[cat]:
                all_prompts.append(p)
                prompt_to_category.append(cat)

        with torch.no_grad():
            inputs = self._processor(
                text=all_prompts,
                images=image.convert("RGB"),
                return_tensors="pt",
                padding=True
            ).to(self.device)

            outputs = self._model(**inputs)
            logits_per_image = outputs.logits_per_image[0]  # shape: (N_prompts,)
            prompt_probs = F.softmax(logits_per_image, dim=0).cpu().numpy()

        # Aggregate ensemble prompt probabilities per category
        category_scores: Dict[GarmentCategory, float] = {cat: 0.0 for cat in category_list}
        prompt_counts: Dict[GarmentCategory, int] = {cat: 0 for cat in category_list}

        for prob, cat in zip(prompt_probs, prompt_to_category):
            category_scores[cat] += float(prob)
            prompt_counts[cat] += 1

        # Normalize aggregated scores
        total_score = sum(category_scores.values())
        if total_score > 0:
            category_probs = {cat: score / total_score for cat, score in category_scores.items()}
        else:
            category_probs = {cat: 1.0 / len(category_list) for cat in category_list}

        # Rank categories
        sorted_cats = sorted(category_probs.items(), key=lambda kv: kv[1], reverse=True)
        top1_cat, top1_prob = sorted_cats[0]
        top2_cat, top2_prob = sorted_cats[1]

        # Calculate prediction entropy and margin
        entropy = -sum(p * math.log(max(p, 1e-12)) for p in category_probs.values())
        margin = float(top1_prob - top2_prob)

        # Classify subcategory for the winning category
        subcat_prompts = SUBCATEGORY_PROMPTS.get(top1_cat, {})
        top_subcategory = f"{top1_cat.value}_standard"
        subcat_confidence = top1_prob

        if subcat_prompts:
            subcat_keys = list(subcat_prompts.keys())
            subcat_texts = [subcat_prompts[k] for k in subcat_keys]
            with torch.no_grad():
                sub_inputs = self._processor(
                    text=subcat_texts,
                    images=image.convert("RGB"),
                    return_tensors="pt",
                    padding=True
                ).to(self.device)
                sub_outputs = self._model(**sub_inputs)
                sub_logits = sub_outputs.logits_per_image[0]
                sub_probs = F.softmax(sub_logits, dim=0).cpu().numpy()

            best_sub_idx = int(np.argmax(sub_probs))
            top_subcategory = subcat_keys[best_sub_idx]
            subcat_confidence = float(sub_probs[best_sub_idx])

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "category": top1_cat,
            "category_confidence": float(top1_prob),
            "top2_category": top2_cat,
            "top2_confidence": float(top2_prob),
            "margin": margin,
            "entropy": entropy,
            "all_probabilities": {cat.value: float(prob) for cat, prob in sorted_cats},
            "subcategory": top_subcategory,
            "subcategory_confidence": subcat_confidence,
            "latency_ms": latency_ms,
            "device": str(self.device),
            "model": self.model_name,
            "execution_backend": self.execution_backend,
            "weights_loaded": self._model is not None,
            "confidence_calibrated": False
        }
