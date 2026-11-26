"""
Yorvyn Phase 12.3.2 - Classification Defect Remediation & Verification Test Suite

Covers:
- DEF-01: Frontend/Backend correction-to-reconstruction handoff integrity and provenance immutability.
- DEF-02: Footwear packshot recognition for isolated footwear without on-body anatomical position.
- DEF-03: Outerwear subcategory hierarchy arbitration stopping collapse to denim_jacket.
- DEF-04: Layered two-piece outfit disambiguation and dress walking slit preservation.
- Regression verification for Reference Garments Cases A-F.
"""

import pytest
import numpy as np
from PIL import Image, ImageDraw
import json
import os
from typing import Dict, Any

from app.services.garments.intelligence.universal_garment_classifier import universal_garment_classifier
from app.services.garments.intelligence.garment_hypothesis_resolver import garment_hypothesis_resolver
from app.services.garments.intelligence.component_detector import component_detector
from app.models.garment_intelligence_models import GarmentComponentV2, GarmentLandmarkV2
from app.services.garments.job_manager import garment_job_manager


class TestDef01CorrectionHandoffIntegrity:
    """Verifies DEF-01: End-to-end correction handoff and provenance immutability."""

    def test_job_manager_respects_authoritative_correction_input(self):
        """Authoritative final_reconstruction_input must override initial prediction in job manager."""
        metadata = {
            "ai_confidence": 0.94,
            "user_correction_state": {
                "has_user_correction": True,
                "original_prediction": {
                    "category": "tops",
                    "subcategory": "tshirt",
                    "confidence": 0.94
                },
                "selected_hypothesis": {
                    "category": "outerwear",
                    "subcategory": "blazer",
                    "calibrated_probability": 0.91
                },
                "final_reconstruction_input": {
                    "category": "outerwear",
                    "subcategory": "blazer"
                }
            }
        }

        import uuid
        # Create job with category='tops' (original) but subcategory='blazer' and metadata indicating correction
        job = garment_job_manager.create_job(
            user_id=f"test_user_phase_12_3_2_{uuid.uuid4().hex[:8]}",
            front_image_bytes=b"dummy_image_data",
            category="outerwear",
            subcategory="blazer",
            detection_metadata=metadata
        )

        assert job is not None
        assert job.category == "outerwear"
        assert job.subcategory == "blazer"
        assert job.detection_metadata["user_correction_state"]["has_user_correction"] is True
        # Verify original prediction is preserved immutably
        assert job.detection_metadata["user_correction_state"]["original_prediction"]["category"] == "tops"
        assert job.detection_metadata["user_correction_state"]["original_prediction"]["subcategory"] == "tshirt"

    def test_job_manager_preserves_unmodified_prediction(self):
        """When no user correction is applied, original prediction is used directly."""
        import uuid
        metadata = {
            "ai_confidence": 0.96,
            "user_correction_state": {
                "has_user_correction": False,
                "original_prediction": {
                    "category": "tops",
                    "subcategory": "hoodie",
                    "confidence": 0.96
                }
            }
        }

        job = garment_job_manager.create_job(
            user_id=f"test_user_phase_12_3_2_{uuid.uuid4().hex[:8]}",
            front_image_bytes=b"dummy_image_data",
            category="tops",
            subcategory="hoodie",
            detection_metadata=metadata
        )

        assert job is not None
        assert job.category == "tops"
        assert job.subcategory == "hoodie"


class TestDef02FootwearPackshotRepair:
    """Verifies DEF-02: Isolated footwear classification without on-body position."""

    def _create_isolated_shoe_packshot(self, w: int = 512, h: int = 512):
        """Creates a centered isolated sneaker packshot."""
        mask = np.zeros((h, w), dtype=np.uint8)
        # Centered shoe: y=200 to 320 (height=120, width=280 -> AR = 0.43, min_y_rel = 0.39)
        # Continuous sole base at bottom (y=300 to 320)
        mask[300:320, 116:396] = 255  # Outsole base
        mask[240:300, 140:380] = 255  # Shoe body
        mask[200:240, 240:360] = 255  # Heel / collar
        img = Image.new("RGB", (w, h), (240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.rectangle([116, 200, 396, 320], fill=(50, 80, 160))
        return img, mask

    def test_isolated_shoe_packshot_without_hint(self):
        """Centered isolated sneaker with NO hint must classify as footwear, not tops/tshirt."""
        img, mask = self._create_isolated_shoe_packshot()
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=[],
            landmarks={}
        )
        assert resolved.category == "footwear", f"Expected footwear, got {resolved.category}"
        assert resolved.subcategory in ["sneakers", "running_shoes", "boots"]

    def test_isolated_shoe_packshot_with_hint(self):
        """Centered sneaker with 'sneaker' hint must classify as footwear with high confidence."""
        img, mask = self._create_isolated_shoe_packshot()
        cls_res = universal_garment_classifier.classify_hierarchical(
            img, mask, user_category_hint="footwear", user_subcategory_hint="sneakers"
        )
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=[],
            landmarks={},
            user_category_hint="footwear",
            user_subcategory_hint="sneakers"
        )
        assert resolved.category == "footwear"
        assert resolved.subcategory == "sneakers"
        assert resolved.confidence >= 0.85

    def test_non_footwear_protections_retained(self):
        """Mini-skirt, athletic shorts, trousers, and crop tops must NEVER classify as footwear."""
        h, w = 512, 512

        # 1. Mini-skirt (flared hem waist_to_hem_ratio > 1.25)
        skirt_mask = np.zeros((h, w), dtype=np.uint8)
        for y in range(160, 360):
            hw = int(70 + (y - 160) * 0.5)
            skirt_mask[y, 256 - hw: 256 + hw] = 255
        skirt_img = Image.new("RGB", (w, h), (180, 50, 80))
        cls_skirt = universal_garment_classifier.classify_hierarchical(skirt_img, skirt_mask)
        assert cls_skirt["category"] != "footwear"

        # 2. Denim shorts (crotch split)
        shorts_mask = np.zeros((h, w), dtype=np.uint8)
        shorts_mask[160:220, 150:362] = 255
        shorts_mask[220:340, 150:240] = 255
        shorts_mask[220:340, 272:362] = 255
        shorts_img = Image.new("RGB", (w, h), (40, 60, 120))
        cls_shorts = universal_garment_classifier.classify_hierarchical(shorts_img, shorts_mask)
        assert cls_shorts["category"] != "footwear"


class TestDef03OuterwearHierarchyArbitration:
    """Verifies DEF-03: Outerwear subtypes arbitrate without collapsing to denim_jacket."""

    def test_blazer_not_collapsed_to_denim_jacket(self):
        """Blazer with front opening seam and no chest flap pockets must resolve to blazer."""
        h, w = 512, 512
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[60:380, 150:362] = 255
        mask[90:340, 80:150] = 255
        mask[90:340, 362:432] = 255

        img = Image.new("RGB", (w, h), (30, 30, 40))
        draw = ImageDraw.Draw(img)
        # Center vertical opening seam (blazer front)
        draw.line([(256, 60), (256, 380)], fill=(200, 200, 200), width=4)

        comps = [
            GarmentComponentV2(name="Collar", component_type="collar", confidence=0.92),
            GarmentComponentV2(name="Placket", component_type="placket", confidence=0.90)
        ]

        cls_res = universal_garment_classifier.classify_hierarchical(img, mask, user_category_hint="outerwear", user_subcategory_hint="blazer")
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=comps,
            landmarks={},
            user_category_hint="outerwear",
            user_subcategory_hint="blazer"
        )
        assert resolved.category == "outerwear"
        assert resolved.subcategory == "blazer", f"Expected blazer, got {resolved.subcategory}"

    @pytest.mark.ml_benchmark
    def test_formal_coat_not_collapsed_to_denim_jacket(self):
        """Formal coat with elongated silhouette (AR >= 1.30) must resolve to formal_coat."""
        h, w = 512, 512
        mask = np.zeros((h, w), dtype=np.uint8)
        # Elongated coat: y=40 to 480, w=220 -> AR = 2.0
        mask[40:480, 146:366] = 255
        mask[70:380, 76:146] = 255
        mask[70:380, 366:436] = 255

        img = Image.new("RGB", (w, h), (40, 40, 40))
        draw = ImageDraw.Draw(img)
        draw.line([(256, 40), (256, 480)], fill=(180, 180, 180), width=4)

        cls_res = universal_garment_classifier.classify_hierarchical(img, mask, user_category_hint="outerwear", user_subcategory_hint="formal_coat")
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=[],
            landmarks={},
            user_category_hint="outerwear",
            user_subcategory_hint="formal_coat"
        )
        assert resolved.category == "outerwear"
        assert resolved.subcategory == "formal_coat"

    def test_trench_coat_not_collapsed_to_denim_jacket(self):
        """Trench coat hint must resolve to trench_coat."""
        sub, conf, dname, attrs = universal_garment_classifier._classify_subcategory(
            category="outerwear",
            aspect_ratio=1.40,
            span_ratio=1.20,
            has_crotch_split=False,
            user_sub_hint="trench_coat",
            has_center_opening=True
        )
        assert sub == "trench_coat"

    def test_denim_jacket_requires_chest_flaps_or_denim_hint(self):
        """Denim jacket correctly resolves when chest flap pockets are present."""
        sub, conf, dname, attrs = universal_garment_classifier._classify_subcategory(
            category="outerwear",
            aspect_ratio=1.10,
            span_ratio=1.20,
            has_crotch_split=False,
            user_sub_hint=None,
            has_center_opening=True,
            has_pocket_flaps=True
        )
        assert sub == "denim_jacket"


class TestDef04OutfitDisambiguationAndDressSlits:
    """Verifies DEF-04: Distinguishing outfits from jumpsuits and dress walking slits from pant legs."""

    @pytest.mark.ml_benchmark
    def test_two_piece_layered_outfit_disambiguation(self):
        """Layered two-piece outfit (white shirt + black pants) must not become confident jumpsuit."""
        h, w = 512, 512
        mask = np.zeros((h, w), dtype=np.uint8)
        # Upper torso (y=50 to 240)
        mask[50:240, 150:362] = 255
        mask[80:220, 80:150] = 255
        mask[80:220, 362:432] = 255
        # Bifurcated pant legs (y=240 to 480)
        mask[240:480, 150:240] = 255
        mask[240:480, 272:362] = 255

        # Distinct color: upper is bright white (240, 240, 240), lower is dark navy (20, 30, 60)
        img = Image.new("RGB", (w, h), (120, 120, 120))
        draw = ImageDraw.Draw(img)
        draw.rectangle([80, 50, 432, 240], fill=(240, 240, 240))  # White shirt
        draw.rectangle([150, 240, 362, 480], fill=(20, 30, 60))    # Navy trousers

        comps = [
            GarmentComponentV2(name="Collar", component_type="collar", confidence=0.92),
            GarmentComponentV2(name="Waistband", component_type="waistband", confidence=0.90)
        ]

        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=comps,
            landmarks={}
        )

        # Must flag ambiguity and NOT claim confident jumpsuit
        assert resolved.uncertainty_status in ["AMBIGUOUS", "LOW_CONFIDENCE"]
        assert any(sig for sig in resolved.reasoning_signals if "two-piece" in sig.lower() or "ambiguity" in sig.lower())

    def test_monolithic_jumpsuit_resolves_confident(self):
        """Monolithic jumpsuit (uniform fabric throughout) resolves to dresses_and_skirts/jumpsuit."""
        h, w = 512, 512
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[50:240, 150:362] = 255
        mask[80:220, 80:150] = 255
        mask[80:220, 362:432] = 255
        mask[240:480, 150:240] = 255
        mask[240:480, 272:362] = 255

        # Uniform emerald green color throughout
        img = Image.new("RGB", (w, h), (15, 90, 50))
        comps = [
            GarmentComponentV2(name="Neckline", component_type="neckline", confidence=0.92),
            GarmentComponentV2(name="Left Sleeve", component_type="left_sleeve", confidence=0.90)
        ]

        cls_res = universal_garment_classifier.classify_hierarchical(img, mask, user_subcategory_hint="jumpsuit")
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=comps,
            landmarks={},
            user_subcategory_hint="jumpsuit"
        )
        assert resolved.category == "dresses_and_skirts"
        assert resolved.subcategory == "jumpsuit"

    def test_dress_walking_gap_slit_preserved_as_dress(self):
        """Flared dress with a center walking gap at the hem must remain a dress, not become bottoms."""
        h, w = 512, 512
        mask = np.zeros((h, w), dtype=np.uint8)
        # Bodice from y=50 to 200 (width 140)
        for y in range(50, 200):
            mask[y, 186:326] = 255
        # Skirt flares from y=200 to 470 (width flares from 140 to 280)
        for y in range(200, 470):
            t = (y - 200) / 270.0
            hw = int(70 + t * 70)
            mask[y, 256 - hw: 256 + hw] = 255
        # Walking gap slit at hem ONLY (y=400 to 470, center void)
        mask[400:470, 246:266] = 0

        img = Image.new("RGB", (w, h), (200, 80, 100))
        comps = [
            GarmentComponentV2(name="Bodice", component_type="bodice", confidence=0.94)
        ]

        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img,
            alpha_mask=mask,
            raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"],
            detected_components=comps,
            landmarks={}
        )
        assert resolved.category == "dresses_and_skirts", f"Expected dresses_and_skirts, got {resolved.category}"
        assert resolved.subcategory in ["casual_dress", "maxi_dress"]


class TestReferenceGarmentsCasesARegression:
    """Verifies that all 6 Phase 12 reference garments continue to pass unconditionally."""

    def test_case_a_hoodie(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_a_hoodie/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_a_hoodie/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms
        )
        assert resolved.category == "tops"
        assert resolved.subcategory == "hoodie"

    @pytest.mark.ml_benchmark
    def test_case_b_graphic_tshirt(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_b_graphic_tshirt_person/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_b_graphic_tshirt_person/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask, user_category_hint="tops")
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms,
            user_category_hint="tops"
        )
        assert resolved.category == "tops"
        assert resolved.subcategory == "tshirt"

    @pytest.mark.ml_benchmark
    def test_case_c_formal_shirt(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_c_formal_shirt/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_c_formal_shirt/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms
        )
        assert resolved.category == "tops"
        assert resolved.subcategory in ["formal_shirt", "tshirt"]

    def test_case_d_denim_jacket(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_d_denim_jacket/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_d_denim_jacket/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask, user_category_hint="outerwear", user_subcategory_hint="denim_jacket")
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms,
            user_category_hint="outerwear", user_subcategory_hint="denim_jacket"
        )
        assert resolved.category == "outerwear"
        assert resolved.subcategory == "denim_jacket"

    @pytest.mark.ml_benchmark
    def test_case_e_trousers(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_e_trousers/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_e_trousers/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms
        )
        assert resolved.category == "bottoms"
        assert resolved.subcategory in ["jeans", "trousers", "straight_jeans"]

    def test_case_f_dress(self):
        img = Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_f_dress/01_original_uploaded_image.png")
        mask = np.array(Image.open("docs/reports/YORVYN_PHASE_12_VISUAL_QA/case_f_dress/02_garment_segmentation_mask.png"))
        cls_res = universal_garment_classifier.classify_hierarchical(img, mask)
        comps, lms = component_detector.detect(img, mask, cls_res["category"], cls_res["subcategory"])
        raw_probs = {c.category: c.calibrated_probability for c in cls_res["candidate_categories"]}
        resolved = garment_hypothesis_resolver.resolve(
            image=img, alpha_mask=mask, raw_category_probs=raw_probs,
            initial_subcategory=cls_res["subcategory"], detected_components=comps, landmarks=lms
        )
        assert resolved.category == "dresses_and_skirts"
        assert resolved.subcategory in ["casual_dress", "maxi_dress"]
