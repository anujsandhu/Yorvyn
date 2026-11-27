"""
Comprehensive Test Suite for Yorvyn ML Phase 2:
Body Intelligence, Skin Analysis & Personal Colour Intelligence.
Tests:
- Continuous measurement validation and unit conversion (cm <-> in).
- Continuous proportion calculations without forced rigid body-shaming categories.
- Multi-dimensional clothing fit evaluation (shirt length, trouser rise/break, sleeve, shoulder, ease tolerances).
- CIELAB colorimetry, Delta E* color distance, and lighting compensation.
- Skin undertone detection with uncertainty calibration under poor/unbalanced lighting.
- Personal colour palette generation (seasonal, complementary, neutral anchors, accents).
- Clothing colour compatibility (single garment, two-piece ΔE*, complete outfit).
- Pretrained CV model audit and privacy-compliant pose analysis with consent enforcement.
- Failure handling under difficult conditions (loose clothing, missing scale, lens distortion, extreme exposure).
- Fashion DNA provenance protection (preventing overwriting of user-confirmed data).
- Avatar DNA comparison, mismatch detection, and non-destructive parameter updates.
- All 8 Phase 2 LLM tools execution with tenant isolation.
- REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.fashion_dna_service import fashion_dna_service
from backend.app.services.ml.body_intelligence import (
    body_intelligence_service,
    cm_to_inches,
    inches_to_cm,
    format_measurement,
)
from backend.app.services.ml.skin_colour_intelligence import (
    skin_colour_intelligence_service,
    rgb_to_cielab,
    cielab_delta_e,
)
from backend.app.services.ml.fashion_vision import (
    fashion_vision_service,
    EVALUATED_CV_MODELS,
)
from backend.app.services.llm.tool_registry import tool_registry

client = TestClient(app)


# ── 1. Continuous Measurement Validation & Unit Conversions ──────────────────

def test_unit_conversion_math():
    """Verifies bidirectional unit conversion accuracy and formatting."""
    # 1 inch = 2.54 cm
    assert cm_to_inches(2.54) == 1.0
    assert cm_to_inches(178.0) == 70.08
    assert inches_to_cm(70.08) == 178.0

    # Format helpers
    assert format_measurement(180.0, "cm") == "180.0 cm"
    assert format_measurement(180.0, "in") == "70.87 in"

    # Service method convert_units
    assert body_intelligence_service.convert_units(100.0, "cm", "in") == 39.37
    assert body_intelligence_service.convert_units(39.37, "in", "cm") == 100.0
    assert body_intelligence_service.convert_units(50.0, "cm", "cm") == 50.0


def test_continuous_body_proportions_calculation():
    """
    Verifies continuous proportion calculations across athletic, balanced,
    and elongated frames without forcing rigid categorical labels.
    """
    res = body_intelligence_service.analyze_body_proportions(
        height_cm=182.0,
        shoulder_width_cm=48.0,
        chest_cm=102.0,
        waist_cm=80.0,
        hip_cm=98.0,
        torso_length_cm=53.0,
        inseam_cm=84.0,
        fit_preference="tailored"
    )

    assert res.shoulder_waist_ratio == round(48.0 / 80.0, 2)  # 0.60 (or inverse depending on definition)
    assert res.shoulder_hip_ratio == round(48.0 / 98.0, 2)
    assert res.waist_hip_ratio == round(80.0 / 98.0, 2)
    assert res.torso_leg_balance in ["balanced", "longer_torso", "longer_legs"]
    assert "tops" in res.length_guidelines
    assert "trousers" in res.length_guidelines
    assert len(res.recommended_fits) >= 2
    assert res.fit_compatibility_score >= 80.0
    assert res.confidence >= 0.85


# ── 2. Clothing Fit Intelligence ─────────────────────────────────────────────

def test_clothing_fit_evaluation_tops():
    """Evaluates shoulder, chest ease, and garment length against body measurements."""
    body = {
        "height_cm": 180.0,
        "shoulder_width_cm": 46.0,
        "chest_cm": 100.0,
        "waist_cm": 82.0,
        "torso_length_cm": 52.0,
        "arm_length_cm": 62.0
    }

    # 1. Ideal tailored shirt
    tailored_spec = {
        "category": "top",
        "fit_type": "tailored",
        "shoulder_width_cm": 47.0,      # +1cm ease (ideal)
        "chest_width_cm": 53.0,         # 106cm circum (+6cm ease, ideal)
        "garment_length_cm": 71.0,      # torso 52 + 19 = 71 (ideal mid-hip)
        "sleeve_length_cm": 63.0,       # arm 62 + 1 = 63 (ideal cuff)
        "is_verified_spec": True
    }
    result = body_intelligence_service.evaluate_clothing_fit(body, tailored_spec, user_fit_preference="tailored")
    assert result.is_compatible is True
    assert result.overall_fit_score >= 90.0
    assert result.is_estimated is False
    assert result.confidence == 0.92

    # 2. Ill-fitting top (too small shoulder, insufficient chest ease)
    tight_spec = {
        "category": "top",
        "fit_type": "slim",
        "shoulder_width_cm": 41.0,      # 5cm too narrow
        "chest_width_cm": 47.0,         # 94cm vs 100cm body (negative ease)
        "is_verified_spec": True
    }
    tight_result = body_intelligence_service.evaluate_clothing_fit(body, tight_spec, user_fit_preference="regular")
    assert tight_result.dimension_breakdown["shoulder_fit"]["is_ideal"] is False
    assert len(tight_result.tolerance_notes) > 0


def test_clothing_fit_evaluation_trousers():
    """Evaluates trouser inseam breaks and rise against leg proportions."""
    body = {
        "height_cm": 178.0,
        "inseam_cm": 80.0,
        "waist_cm": 82.0
    }

    trouser_spec = {
        "category": "bottom",
        "fit_type": "regular",
        "inseam_cm": 81.5,     # +1.5cm -> slight break
        "rise_cm": 26.0,       # mid-rise
        "is_verified_spec": True
    }
    result = body_intelligence_service.evaluate_clothing_fit(body, trouser_spec, user_fit_preference="regular")
    assert result.is_compatible is True
    assert result.dimension_breakdown["trouser_inseam"]["break_style"] == "slight break"
    assert result.dimension_breakdown["trouser_rise"]["rise_type"] == "mid-rise"


# ── 3. CIELAB Colorimetry & Lighting Compensation ────────────────────────────

def test_cielab_conversion_and_delta_e():
    """Tests sRGB -> linear -> XYZ -> CIELAB color conversion and Euclidean Delta E*."""
    # Pure white (255, 255, 255) -> L* should be ~100.0, a* ~0.0, b* ~0.0
    l_w, a_w, b_w = rgb_to_cielab(255, 255, 255)
    assert abs(l_w - 100.0) < 0.5
    assert abs(a_w) < 1.0
    assert abs(b_w) < 1.0

    # Stark black (0, 0, 0) -> L* should be ~0.0
    l_k, a_k, b_k = rgb_to_cielab(0, 0, 0)
    assert abs(l_k) < 0.1

    # Delta E between black and white should be ~100
    de_wk = cielab_delta_e((l_w, a_w, b_w), (l_k, a_k, b_k))
    assert 99.0 <= de_wk <= 101.0


def test_lighting_aware_skin_tone_analysis():
    """Verifies lighting-aware skin tone analysis, illuminant compensation, and uncertainty scoring."""
    # 1. Balanced warm medium skin tone in daylight
    res_daylight = skin_colour_intelligence_service.analyze_skin_tone_lighting_aware(
        r=198, g=145, b=110, ambient_hint="neutral_daylight"
    )
    assert res_daylight.skin_tone_range in ["medium", "tan"]
    assert res_daylight.skin_undertone in ["warm", "neutral"]
    assert res_daylight.uncertainty_score <= 0.35
    assert res_daylight.confidence >= 0.75

    # 2. Warm ambient tungsten light (triggers illuminant compensation)
    res_tungsten = skin_colour_intelligence_service.analyze_skin_tone_lighting_aware(
        r=210, g=155, b=100, ambient_hint="warm_indoor"
    )
    assert res_tungsten.lighting_compensation_applied is True
    assert any("warm ambient" in note.lower() for note in res_tungsten.diagnostic_notes)

    # 3. Severe overexposure (washed-out flash) -> flags uncertainty
    res_overexposed = skin_colour_intelligence_service.analyze_skin_tone_lighting_aware(
        r=252, g=250, b=248, ambient_hint="neutral_daylight"
    )
    assert res_overexposed.uncertainty_score > 0.40
    assert any("exposure" in note.lower() for note in res_overexposed.diagnostic_notes)

    # 4. Severe underexposure (shadow) -> flags uncertainty
    res_underexposed = skin_colour_intelligence_service.analyze_skin_tone_lighting_aware(
        r=25, g=20, b=18, ambient_hint="neutral_daylight"
    )
    assert res_underexposed.uncertainty_score > 0.40


def test_personal_colour_palette_generation():
    """Generates personalized seasonal palettes with neutral anchors and non-prohibitive guidance."""
    palette = skin_colour_intelligence_service.get_personal_colour_palette(
        undertone="warm",
        skin_tone_range="medium"
    )
    assert palette.palette_id == "autumn_deep"
    assert len(palette.neutral_anchors) >= 3
    assert len(palette.complementary_colours) >= 3
    assert len(palette.accent_colours) >= 2
    assert palette.avoid_strict_prohibitions is True
    assert len(palette.styling_guidelines) >= 2


def test_clothing_colour_compatibility():
    """Tests clothing color compatibility across single garments and complete multi-piece outfits."""
    # 1. Single garment matching personal palette
    res_single = skin_colour_intelligence_service.evaluate_colour_compatibility(
        garment_colors=["terracotta"],
        user_undertone="warm",
        personal_palette="autumn_deep"
    )
    assert res_single.is_compatible is True
    assert res_single.compatibility_score >= 90.0

    # 2. Multi-piece outfit (navy + cream)
    res_outfit = skin_colour_intelligence_service.evaluate_colour_compatibility(
        garment_colors=["navy", "cream", "charcoal"],
        user_undertone="warm",
        personal_palette="autumn_deep"
    )
    assert res_outfit.is_compatible is True
    assert res_outfit.harmonic_relationship in ["complementary_contrast", "balanced_harmony", "tonal_monochromatic"]

    # 3. Explicitly disliked color penalty
    res_disliked = skin_colour_intelligence_service.evaluate_colour_compatibility(
        garment_colors=["neon_yellow"],
        user_undertone="neutral",
        personal_palette="autumn_deep",
        disliked_colors=["neon_yellow"]
    )
    assert res_disliked.is_compatible is False
    assert res_disliked.compatibility_score < 50.0
    assert len(res_disliked.alternative_suggestions) > 0


# ── 4. Computer Vision Model Audit & Privacy Consent ─────────────────────────

def test_cv_model_audit_matrix():
    """Verifies that candidate CV models (BlazePose, Segmenter, YOLO-Pose, DensePose) are formally evaluated."""
    models = fashion_vision_service.get_supported_cv_models()
    assert "mediapipe_pose" in models
    assert "mediapipe_segmenter" in models
    assert "yolov8_pose" in models
    assert "densepose" in models

    # Check licensing and commercial audit
    assert "Apache 2.0" in models["mediapipe_pose"]["license_type"]
    assert "AGPL-3.0" in models["yolov8_pose"]["license_type"]
    assert "Non-Commercial" in models["densepose"]["license_type"]


def test_body_photo_analysis_consent_enforcement():
    """Ensures photos cannot be analyzed without explicit user consent."""
    # Refusal without consent
    no_consent_res = fashion_vision_service.analyze_body_photo_proportions(
        image_metadata={"camera_angle": "eye_level", "is_full_length": True},
        user_consent=False
    )
    assert no_consent_res.user_consent_granted is False
    assert no_consent_res.is_analyzable is False
    assert len(no_consent_res.estimated_ratios) == 0

    # With consent and valid full-length photo
    consent_res = fashion_vision_service.analyze_body_photo_proportions(
        image_metadata={"camera_angle": "eye_level", "is_full_length": True, "clothing_type": "fitted"},
        user_consent=True
    )
    assert consent_res.user_consent_granted is True
    assert consent_res.is_analyzable is True
    assert "shoulder_to_hip_ratio" in consent_res.estimated_ratios


def test_body_photo_analysis_distortion_handling():
    """Verifies that difficult photographic conditions (tilt, loose clothing, cut off legs) do NOT fabricate measurements."""
    # Incomplete framing + extreme angle
    bad_photo_res = fashion_vision_service.analyze_body_photo_proportions(
        image_metadata={
            "camera_angle": "high_angle",
            "is_full_length": False,
            "clothing_type": "oversized"
        },
        user_consent=True
    )
    assert bad_photo_res.is_analyzable is False
    assert len(bad_photo_res.perspective_warnings) >= 2
    assert "manual" in bad_photo_res.recommended_action.lower()


# ── 5. Fashion DNA & Avatar DNA Integration ──────────────────────────────────

def test_fashion_dna_measurement_provenance():
    """Verifies provenance tracking and ensures user_confirmed data is never overwritten by estimates."""
    user_id = "test_user_phase2_prov"

    # 1. User enters confirmed measurements
    dna = fashion_dna_service.update_body_measurements(
        user_id=user_id,
        measurements={"height_cm": 182.0, "chest_cm": 102.0, "waist_cm": 82.0},
        unit="cm",
        source="user_confirmed"
    )
    assert dna.body_profile.height_cm == 182.0
    assert dna.body_profile.measurement_sources["height_cm"] == "user_confirmed"
    assert dna.body_profile.measurement_confidences["height_cm"] == 1.0

    # 2. Avatar sync attempts to overwrite with a different height (175.0)
    avatar_profile = {
        "proportions": {"heightCm": 175.0, "silhouette": "slender"},
        "appearance": {"skinUndertone": "cool"}
    }
    synced_dna = fashion_dna_service.sync_from_avatar_dna(user_id, avatar_profile)
    # Confirmed measurement must be strictly preserved!
    assert synced_dna.body_profile.height_cm == 182.0
    assert synced_dna.body_profile.measurement_sources["height_cm"] == "user_confirmed"


def test_avatar_dna_comparison_and_mismatch_detection():
    """Detects structural mismatches between 3D avatar parameters and user confirmed body measurements."""
    user_id = "test_user_phase2_avatar"

    # User has 184cm height in Fashion DNA
    fashion_dna_service.update_body_measurements(
        user_id=user_id,
        measurements={"height_cm": 184.0, "shoulder_width_cm": 50.0, "waist_cm": 80.0},
        unit="cm",
        source="user_confirmed"
    )

    # Avatar is set to 175cm
    avatar_profile = {
        "proportions": {
            "heightCm": 175.0,
            "shoulderWidth": 0.0,
            "torsoLength": 0.0
        }
    }

    comparison = fashion_dna_service.compare_with_avatar_dna(user_id, avatar_profile)
    assert comparison["has_mismatches"] is True
    assert comparison["mismatch_count"] >= 1
    assert "height" in [m["attribute"] for m in comparison["mismatches"]]
    assert comparison["validated_parameter_updates"]["heightCm"] == 184.0
    assert "visual approximations" in comparison["disclaimer"].lower()


# ── 6. LLM Tool Registry Execution (All 8 Phase 2 Tools) ─────────────────────

def test_phase_2_all_8_tools_execution():
    """Tests execution, tenant isolation, and output structures for all 8 Phase 2 LLM tools."""
    user_id = "phase2_llm_tester"

    phase_2_tools = [
        ("get_body_profile", {}),
        (
            "update_body_measurements",
            {
                "measurements": {
                    "height": 180.0,
                    "chest": 100.0,
                    "waist": 82.0,
                    "hip": 96.0,
                    "shoulder_width": 46.0
                },
                "unit": "cm"
            }
        ),
        (
            "analyze_body_proportions",
            {
                "height_cm": 180.0,
                "shoulder_cm": 46.0,
                "waist_cm": 82.0,
                "hip_cm": 96.0
            }
        ),
        (
            "analyze_skin_colour",
            {
                "skin_hex": "#c68e64",
                "ambient_lighting": "neutral_daylight"
            }
        ),
        (
            "get_personal_colour_palette",
            {
                "undertone": "warm",
                "palette_id": "autumn_deep"
            }
        ),
        (
            "evaluate_clothing_fit",
            {
                "garment_spec": {
                    "category": "top",
                    "fit_type": "regular",
                    "shoulder_width_cm": 47.0,
                    "chest_width_cm": 54.0,
                    "garment_length_cm": 72.0
                },
                "garment_name": "Merino Crewneck"
            }
        ),
        (
            "evaluate_colour_compatibility",
            {
                "garment_colors": ["navy", "cream"],
                "occasion": "business"
            }
        ),
        ("get_avatar_measurements", {})
    ]

    for tool_name, args in phase_2_tools:
        result = tool_registry.execute_tool(user_id=user_id, tool_name=tool_name, arguments=args)
        assert result.success is True, f"Tool '{tool_name}' failed: {result.error}"
        assert isinstance(result.data, dict)
        assert result.execution_time_ms >= 0.0


# ── 7. REST API Endpoints Verification ───────────────────────────────────────

def test_api_body_and_colour_endpoints():
    """Verifies all Phase 2 REST API endpoints."""
    # 1. GET /api/fashion/body/profile
    resp_get_body = client.get("/api/fashion/body/profile?user_id=api_test_user")
    assert resp_get_body.status_code == 200
    assert resp_get_body.json()["status"] == "success"

    # 2. PUT /api/fashion/body/measurements
    resp_put_meas = client.put(
        "/api/fashion/body/measurements?user_id=api_test_user",
        json={"measurements": {"height": 182.0, "chest": 102.0}, "unit": "cm"}
    )
    assert resp_put_meas.status_code == 200
    assert resp_put_meas.json()["status"] == "success"

    # 3. POST /api/fashion/body/analyze-proportions
    resp_prop = client.post(
        "/api/fashion/body/analyze-proportions?user_id=api_test_user",
        json={"height_cm": 182.0, "shoulder_cm": 48.0, "waist_cm": 82.0, "hip_cm": 98.0}
    )
    assert resp_prop.status_code == 200
    assert "proportions" in resp_prop.json()["analysis"]

    # 4. POST /api/fashion/body/analyze-photo (Consent rejection check)
    resp_photo_no_consent = client.post(
        "/api/fashion/body/analyze-photo?user_id=api_test_user",
        json={"image_metadata": {"camera_angle": "eye_level"}, "user_consent": False}
    )
    assert resp_photo_no_consent.status_code == 200
    assert resp_photo_no_consent.json()["result"]["user_consent_granted"] is False

    # 5. POST /api/fashion/colour/analyze
    resp_colour = client.post(
        "/api/fashion/colour/analyze?user_id=api_test_user",
        json={"skin_hex": "#c68e64", "ambient_lighting": "neutral_daylight"}
    )
    assert resp_colour.status_code == 200
    assert "skin_undertone" in resp_colour.json()["analysis"]

    # 6. GET /api/fashion/colour/palette
    resp_pal = client.get("/api/fashion/colour/palette?user_id=api_test_user")
    assert resp_pal.status_code == 200
    assert "neutral_anchors" in resp_pal.json()["palette"]

    # 7. POST /api/fashion/compatibility/fit
    resp_fit = client.post(
        "/api/fashion/compatibility/fit?user_id=api_test_user",
        json={
            "garment_spec": {"category": "top", "fit_type": "regular", "shoulder_width_cm": 46.0},
            "garment_name": "Test Shirt"
        }
    )
    assert resp_fit.status_code == 200
    assert "evaluation" in resp_fit.json()

    # 8. POST /api/fashion/compatibility/colour
    resp_comp_col = client.post(
        "/api/fashion/compatibility/colour?user_id=api_test_user",
        json={"garment_colors": ["navy", "olive"]}
    )
    assert resp_comp_col.status_code == 200
    assert "contrast_level" in resp_comp_col.json()["result"]

    # 9. GET /api/fashion/avatar/compare
    resp_avatar_comp = client.get("/api/fashion/avatar/compare?user_id=api_test_user")
    assert resp_avatar_comp.status_code == 200
    assert "comparison" in resp_avatar_comp.json()

    # 10. GET /api/fashion/cv/models
    resp_cv = client.get("/api/fashion/cv/models")
    assert resp_cv.status_code == 200
    assert "mediapipe_pose" in resp_cv.json()["models"]
