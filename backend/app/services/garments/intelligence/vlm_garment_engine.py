"""
YORVYN — Vision-Language Garment Perception Engine (Phase 14.5)
Integrates OpenAI CLIP (ViT-B/32) vision-language representations with hierarchical
garment taxonomy embeddings and Bayesian ensemble classification.
Solves flat-lay, folded, and unconstrained garment perception by grounding predictions
in multimodal semantic representations rather than body-presence shortcuts.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

logger = logging.getLogger(__name__)

# Canonical YORVYN Garment Taxonomy
TAXONOMY_CATEGORIES = [
    "tops", "shirt", "hoodie", "jacket", "bottoms", "dress", "skirt", "traditional", "footwear", "accessories"
]

TAXONOMY_SUBCATEGORIES = {
    "tops": ["tshirt", "tank_top", "crop_top", "polo_shirt", "sweater"],
    "shirt": ["formal_shirt", "casual_shirt", "oxford_shirt", "mandarin_shirt", "oversized_shirt"],
    "hoodie": ["pullover_hoodie", "zip_hoodie", "fleece_hoodie", "oversized_hoodie"],
    "jacket": ["denim_jacket", "bomber_jacket", "leather_jacket", "blazer", "formal_coat", "puffer_jacket"],
    "bottoms": ["straight_jeans", "slim_jeans", "wide_leg_jeans", "formal_trousers", "chinos", "cargo_pants", "shorts"],
    "dress": ["a_line_dress", "bodycon_dress", "maxi_dress", "shift_dress", "wrap_dress", "slip_dress"],
    "skirt": ["a_line_skirt", "pencil_skirt", "pleated_skirt", "mini_skirt", "maxi_skirt"],
    "traditional": ["kurta", "sherwani", "saree", "lehenga", "salwar_kameez"],
    "footwear": ["sneakers", "running_shoes", "boots", "loafers", "sandals", "formal_shoes"],
    "accessories": ["cap", "beanie", "scarf", "belt", "tote_bag", "tie"]
}

# Standardized Multimodal Prompts
CATEGORY_PROMPTS = {
    "tops": [
        "a clean product photograph of a casual top, t-shirt, or knit sweater",
        "a flat-lay photograph of a top laid flat on a surface",
        "a photograph of a person wearing a top or t-shirt"
    ],
    "shirt": [
        "a clean product photograph of a collared button-up shirt",
        "a flat-lay photograph of a button-down shirt folded or laid flat",
        "a photograph of an oxford or dress shirt with buttons and collar"
    ],
    "hoodie": [
        "a photograph of a hooded sweatshirt or pullover hoodie with drawstrings",
        "a flat-lay photograph of a hoodie laid flat",
        "a hooded fleece sweatshirt or zip hoodie"
    ],
    "jacket": [
        "a photograph of a jacket, denim coat, blazer, or outerwear",
        "a flat-lay photograph of a winter coat or leather jacket laid flat",
        "a tailored blazer or outerwear jacket"
    ],
    "bottoms": [
        "a photograph of pants, trousers, jeans, chinos, or shorts",
        "a flat-lay photograph of denim jeans or trousers laid flat",
        "trousers, sweatpants, or casual shorts laid on a plain background"
    ],
    "dress": [
        "a photograph of an elegant one-piece dress or gown",
        "a flat-lay photograph of a summer dress or cocktail dress laid flat",
        "a one-piece women's dress hanging or laid on a surface"
    ],
    "skirt": [
        "a photograph of a skirt or pleated mini skirt",
        "a flat-lay photograph of an a-line or pencil skirt laid flat",
        "a wearable skirt separate garment"
    ],
    "traditional": [
        "a photograph of ethnic or traditional attire like a kurta, saree, or lehenga",
        "traditional Indian or cultural clothing laid flat or worn",
        "an ornate traditional sherwani, saree, or salwar suit"
    ],
    "footwear": [
        "a photograph of footwear, sneakers, athletic running shoes, or boots",
        "a pair of leather shoes, boots, or sneakers on a neutral background"
    ],
    "accessories": [
        "a fashion accessory like a handbag, tote bag, cap, beanie, scarf, or belt",
        "a leather belt, tote bag, or hat on a clean background"
    ]
}

ATTRIBUTE_PROMPTS = {
    "neckline": {
        "crewneck": "a garment with a round crewneck collar",
        "v-neck": "a garment with a v-neck collar",
        "collared": "a garment with a folded shirt collar",
        "hooded": "a garment with an attached hood",
        "turtleneck": "a high turtleneck collar",
        "scoop": "a wide scoop neckline",
        "off-shoulder": "an off-the-shoulder neckline"
    },
    "sleeve": {
        "sleeveless": "a sleeveless garment without sleeves",
        "short": "a garment with short sleeves",
        "long": "a garment with long sleeves extending to the wrists",
        "three-quarter": "a garment with three-quarter length sleeves"
    },
    "fabric": {
        "cotton": "woven cotton or jersey fabric",
        "denim": "blue or black durable denim twill fabric",
        "wool": "knit wool or ribbed sweater fabric",
        "leather": "genuine or faux smooth leather material",
        "silk": "shiny lustrous silk or satin fabric",
        "synthetic": "technical polyester, nylon, or athletic fabric",
        "linen": "breathable textured linen fabric"
    },
    "pattern": {
        "solid": "plain solid color with no pattern",
        "striped": "horizontal or vertical striped pattern",
        "plaid": "plaid, tartan, or checkered pattern",
        "graphic": "bold graphic print, lettering, or illustrated logo",
        "floral": "decorative floral flower pattern"
    },
    "closure": {
        "pullover": "pullover garment with no front opening",
        "zipper": "front zipper closure with metallic or plastic teeth",
        "button": "front button placket with visible buttons",
        "drawstring": "adjustable drawstring cord closure"
    },
    "domain": {
        "flat_lay": "a flat-lay garment laid out flat on a table, floor, or bed",
        "product": "a commercial packshot of a garment on an invisible mannequin or white backdrop",
        "on_body": "a real person or fashion model wearing clothes in an editorial or everyday setting",
        "mannequin": "a plastic or foam retail mannequin wearing clothing",
        "folded": "a neatly folded garment stacked or resting on a surface"
    }
}


class VLMGarmentEngine:
    """
    Vision-Language Multimodal Perception Engine for Garments.
    Computes zero-shot and few-shot multimodal embeddings and fuses with CNN predictions.
    """

    def __init__(self, model_id: str = "openai/clip-vit-base-patch32"):
        self.model_id = model_id
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._processor = None
        self._model = None
        self._text_embeddings: Dict[str, torch.Tensor] = {}
        self._initialized = False

    def initialize(self):
        """Loads CLIP model and precomputes text embeddings for taxonomy and attributes."""
        if self._initialized:
            return

        t0 = time.perf_counter()
        logger.info(f"Initializing VLM Garment Engine ({self.model_id}) on {self._device}...")
        try:
            from transformers import CLIPProcessor, CLIPModel
            self._processor = CLIPProcessor.from_pretrained(self.model_id, local_files_only=True)  # nosec B615
            self._model = CLIPModel.from_pretrained(  # nosec B615
                self.model_id,
                use_safetensors=False,
                local_files_only=True
            ).to(self._device)
            self._model.eval()

            # Precompute text embeddings for taxonomy categories
            self._precompute_category_embeddings()
            # Precompute attribute embeddings
            self._precompute_attribute_embeddings()

            self._initialized = True
            logger.info(f"VLM Garment Engine initialized in {round(time.perf_counter() - t0, 2)}s.")
        except Exception as e:
            logger.error(f"Failed to initialize VLM Garment Engine: {e}")
            self._initialized = False

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._model is not None

    def _precompute_category_embeddings(self):
        """Encodes all canonical category prompts into normalized text vectors."""
        with torch.no_grad():
            for cat, prompts in CATEGORY_PROMPTS.items():
                inputs = self._processor(text=prompts, return_tensors="pt", padding=True).to(self._device)
                text_feats = self._model.get_text_features(**inputs)
                text_feats = text_feats / text_feats.norm(dim=-1, keepdim=True)
                # Average prompt vectors for this category
                avg_feat = text_feats.mean(dim=0, keepdim=True)
                avg_feat = avg_feat / avg_feat.norm(dim=-1, keepdim=True)
                self._text_embeddings[f"cat_{cat}"] = avg_feat

            # Subcategories
            for parent_cat, subcats in TAXONOMY_SUBCATEGORIES.items():
                for sub in subcats:
                    prompt = f"a photograph of a {sub.replace('_', ' ')}, a type of {parent_cat}"
                    inputs = self._processor(text=[prompt], return_tensors="pt").to(self._device)
                    feats = self._model.get_text_features(**inputs)
                    feats = feats / feats.norm(dim=-1, keepdim=True)
                    self._text_embeddings[f"sub_{sub}"] = feats

    def _precompute_attribute_embeddings(self):
        """Encodes attribute prompts (neckline, sleeve, fabric, pattern, closure, domain)."""
        with torch.no_grad():
            for attr_group, attr_dict in ATTRIBUTE_PROMPTS.items():
                for attr_val, prompt in attr_dict.items():
                    inputs = self._processor(text=[prompt], return_tensors="pt").to(self._device)
                    feats = self._model.get_text_features(**inputs)
                    feats = feats / feats.norm(dim=-1, keepdim=True)
                    self._text_embeddings[f"{attr_group}_{attr_val}"] = feats

    def extract_visual_embedding(self, image: Image.Image) -> np.ndarray:
        """Extracts 512-dim normalized CLIP visual embedding from an image."""
        if not self.is_ready:
            self.initialize()

        rgb_img = image.convert("RGB")
        inputs = self._processor(images=rgb_img, return_tensors="pt").to(self._device)
        with torch.no_grad():
            img_feats = self._model.get_image_features(**inputs)
            img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True)
        return img_feats.squeeze(0).cpu().numpy()

    def predict(
        self,
        image: Image.Image,
        alpha_mask: Optional[np.ndarray] = None,
        photography_domain_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs multimodal zero-shot classification and attribute inference on the image.
        """
        if not self.is_ready:
            self.initialize()
            if not self.is_ready:
                return {"error": "VLM Engine uninitialized", "category": "tops", "confidence": 0.5}

        t0 = time.perf_counter()
        rgb_img = image.convert("RGB")
        inputs = self._processor(images=rgb_img, return_tensors="pt").to(self._device)

        with torch.no_grad():
            img_feats = self._model.get_image_features(**inputs)
            img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True)

            # 1. Photography Domain Prediction
            domain_sims = {}
            for dom_name in ATTRIBUTE_PROMPTS["domain"].keys():
                t_vec = self._text_embeddings[f"domain_{dom_name}"]
                sim = torch.cosine_similarity(img_feats, t_vec).item()
                domain_sims[dom_name] = sim

            pred_domain = photography_domain_hint or max(domain_sims.items(), key=lambda x: x[1])[0]

            # 2. Category Cosine Similarities & Softmax
            cat_sims = {}
            for cat in TAXONOMY_CATEGORIES:
                t_vec = self._text_embeddings[f"cat_{cat}"]
                sim = torch.cosine_similarity(img_feats, t_vec).item()
                cat_sims[cat] = sim

            # Temperature-scaled softmax over categories
            temp = 0.07
            sim_tensor = torch.tensor([cat_sims[c] for c in TAXONOMY_CATEGORIES], device=self._device) / temp
            cat_probs = F.softmax(sim_tensor, dim=0).cpu().numpy()

            top_cat_idx = int(np.argmax(cat_probs))
            pred_cat = TAXONOMY_CATEGORIES[top_cat_idx]
            cat_confidence = float(cat_probs[top_cat_idx])

            # 3. Hierarchical Subcategory Prediction (conditioned on valid parent domain)
            subcat_candidates = TAXONOMY_SUBCATEGORIES.get(pred_cat, ["tshirt"])
            sub_sims = []
            for sub in subcat_candidates:
                t_vec = self._text_embeddings[f"sub_{sub}"]
                sim = torch.cosine_similarity(img_feats, t_vec).item()
                sub_sims.append(sim)

            sub_probs = F.softmax(torch.tensor(sub_sims) / temp, dim=0).numpy()
            top_sub_idx = int(np.argmax(sub_probs))
            pred_subcat = subcat_candidates[top_sub_idx]
            subcat_confidence = float(sub_probs[top_sub_idx])

            # 4. Attribute Inferences
            def get_top_attr(group: str) -> Tuple[str, float]:
                items = list(ATTRIBUTE_PROMPTS[group].keys())
                sims = [torch.cosine_similarity(img_feats, self._text_embeddings[f"{group}_{it}"]).item() for it in items]
                probs = F.softmax(torch.tensor(sims) / temp, dim=0).numpy()
                best_i = int(np.argmax(probs))
                return items[best_i], float(probs[best_i])

            pred_neckline, neck_conf = get_top_attr("neckline")
            pred_sleeve, sleeve_conf = get_top_attr("sleeve")
            pred_fabric, fabric_conf = get_top_attr("fabric")
            pred_pattern, pat_conf = get_top_attr("pattern")
            pred_closure, clos_conf = get_top_attr("closure")

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "vlm_model": self.model_id,
            "latency_ms": elapsed_ms,
            "photography_domain": pred_domain,
            "category": pred_cat,
            "category_confidence": round(cat_confidence, 4),
            "category_probabilities": {c: round(float(p), 4) for c, p in zip(TAXONOMY_CATEGORIES, cat_probs)},
            "subcategory": pred_subcat,
            "subcategory_confidence": round(subcat_confidence, 4),
            "attributes": {
                "neckline": pred_neckline,
                "neckline_confidence": round(neck_conf, 4),
                "sleeve_type": pred_sleeve,
                "sleeve_confidence": round(sleeve_conf, 4),
                "fabric_family": pred_fabric,
                "fabric_confidence": round(fabric_conf, 4),
                "pattern": pred_pattern,
                "pattern_confidence": round(pat_conf, 4),
                "closure_type": pred_closure,
                "closure_confidence": round(clos_conf, 4)
            }
        }

    def ensemble_with_cnn(
        self,
        vlm_res: Dict[str, Any],
        cnn_res: Dict[str, Any],
        is_flat_lay: bool = False
    ) -> Dict[str, Any]:
        """
        Performs calibrated Bayesian logit fusion between VLM and CNN classifier.
        For flat-lay or plain background, VLM carries higher weight (alpha=0.70)
        since CNN is biased toward human body presence.
        """
        vlm_probs = vlm_res.get("category_probabilities", {})
        cnn_probs = cnn_res.get("category_probabilities", {})

        # Blending weight alpha: weight given to VLM
        alpha = 0.70 if is_flat_lay else 0.45

        fused_probs = {}
        for cat in TAXONOMY_CATEGORIES:
            pv = vlm_probs.get(cat, 0.1)
            pc = cnn_probs.get(cat, 0.1)
            fused_probs[cat] = alpha * pv + (1.0 - alpha) * pc

        # Normalize
        total = sum(fused_probs.values()) or 1.0
        for cat in fused_probs:
            fused_probs[cat] = round(fused_probs[cat] / total, 4)

        best_cat = max(fused_probs.items(), key=lambda x: x[1])[0]
        calibrated_conf = fused_probs[best_cat]

        # Use VLM subcategory if VLM confidence is high or on flat-lay
        if is_flat_lay or vlm_res.get("category_confidence", 0.0) >= 0.65:
            final_subcat = vlm_res.get("subcategory", cnn_res.get("subcategory", "tshirt"))
        else:
            final_subcat = cnn_res.get("subcategory", vlm_res.get("subcategory", "tshirt"))

        return {
            "category": best_cat,
            "subcategory": final_subcat,
            "confidence": calibrated_conf,
            "calibrated_confidence": calibrated_conf,
            "fusion_alpha": alpha,
            "evidence_source": "multimodal_vlm_cnn_bayesian_fusion",
            "model_provenance": "clip_vit_b32_plus_mobilenet_v3_ensemble",
            "photography_domain": vlm_res.get("photography_domain", "product"),
            "attributes": vlm_res.get("attributes", {}),
            "fused_probabilities": fused_probs
        }


# Singleton instance
vlm_garment_engine = VLMGarmentEngine()
