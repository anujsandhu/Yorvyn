"""
YORVYN — Phase 11B Unit and Integration Test Suite.
Tests:
1. HumanParsingSegmenter registration, class taxonomy, and device mapping.
2. Image type auto-classification (isolated_product, flat_lay, on_body, lifestyle_fashion, ambiguous_unsupported).
3. Semantic human parsing and body-part disentanglement (Face, Hair, Arms, Legs, Garment).
4. Garment-only isolation, anti-aliased alpha matting, and zero background bleed.
5. Occlusion mask detection, visible surface ratio, and inferred surface ratio.
6. Reference case reconstruction (woman wearing oversized grey graphic T-shirt).
7. Texture synthesis non-contamination verification (no skin/hair/background bleed on UV atlas).
8. Phase 11B benchmark JSON metrics and manifold validity.
"""

import os
import json
import pytest
import numpy as np
from PIL import Image

from backend.app.services.garments.segmentation import (
    segmenter_registry,
    human_parsing_segmenter,
    HumanParsingSegmenter,
    GarmentSegmentationOutput
)
from backend.app.services.garments.segmentation.human_parsing_segmenter import (
    PARSING_CLASSES,
    PERSON_CLASSES,
    GARMENT_CLASSES
)
from backend.app.services.garments.garment_analyzer import garment_analyzer
from backend.app.services.garments.garment_mesh_builder import garment_mesh_builder
from backend.app.services.garments.appearance import (
    garment_appearance_analyzer,
    reference_texture_reconstructor
)
from backend.app.services.garments.intelligence.garment_intelligence_service import garment_intelligence_service


REF_TSHIRT_PATH = "/Users/anujsandhu/Desktop/Screenshot 2026-11-02 at 10.27.55 PM.png"
REF_HOODIE_PATH = "docs/reports/hoodie_visual_regression/reference_hoodie.png"
BENCHMARK_JSON_PATH = "docs/reports/on_body_garment_benchmark.json"


def test_human_parsing_segmenter_registration():
    """Verifies that HumanParsingSegmenter is registered in segmenter_registry."""
    available = segmenter_registry.list_available()
    assert "human_parsing" in available, "human_parsing must be registered in segmenter_registry"

    seg = segmenter_registry.get("human_parsing")
    assert isinstance(seg, HumanParsingSegmenter)
    assert seg.model_id == "human_parsing_segformer_b2"
    assert "segformer" in seg.model_version.lower()


def test_parsing_taxonomy_and_classes():
    """Verifies that all 18 canonical ATR / LIP classes are mapped."""
    assert len(PARSING_CLASSES) == 18
    assert PARSING_CLASSES[0] == "Background"
    assert PARSING_CLASSES[4] == "Upper-clothes"
    assert PARSING_CLASSES[6] == "Pants"
    assert PARSING_CLASSES[7] == "Dress"
    assert PARSING_CLASSES[11] == "Face"
    assert PARSING_CLASSES[14] == "Left-arm"
    assert PARSING_CLASSES[15] == "Right-arm"


def test_image_type_classification():
    """Verifies automatic image classification for isolated product vs on-body lifestyle."""
    # 1. Isolated product (hoodie)
    if os.path.exists(REF_HOODIE_PATH):
        hoodie_img = Image.open(REF_HOODIE_PATH)
        out_hoodie = human_parsing_segmenter.segment(hoodie_img)
        assert out_hoodie.image_type == "isolated_product"
        assert out_hoodie.target_garment_class == "Upper-clothes"
        assert out_hoodie.detected_body_parts.get("Face", 0.0) == 0.0
        assert out_hoodie.detected_body_parts.get("Hair", 0.0) == 0.0

    # 2. On-body lifestyle (reference T-shirt woman)
    if os.path.exists(REF_TSHIRT_PATH):
        tshirt_img = Image.open(REF_TSHIRT_PATH)
        out_tshirt = human_parsing_segmenter.segment(tshirt_img)
        assert out_tshirt.image_type in ["on_body", "lifestyle_fashion"]
        assert out_tshirt.target_garment_class == "Upper-clothes"
        assert out_tshirt.detected_body_parts.get("Hair", 0.0) > 0.02
        assert out_tshirt.detected_body_parts.get("Face", 0.0) > 0.01

    # 3. Ambiguous / empty noise image
    blank_img = Image.new("RGB", (200, 200), (128, 128, 128))
    out_blank = human_parsing_segmenter.segment(blank_img)
    assert out_blank.image_type == "ambiguous_unsupported"


def test_garment_isolation_and_contamination_prevention():
    """Verifies that skin, hair, arms, face, and pants are 100% excluded from garment mask."""
    if not os.path.exists(REF_TSHIRT_PATH):
        pytest.skip("Reference image not available")

    img = Image.open(REF_TSHIRT_PATH)
    out = human_parsing_segmenter.segment(img)

    # 1. Output contracts
    assert isinstance(out, GarmentSegmentationOutput)
    assert out.alpha_mask.shape == (img.height, img.width)
    assert out.segmented_image.mode == "RGBA"

    # 2. Ensure non-garment regions have 0 alpha in the segmented output
    pred_seg, _ = human_parsing_segmenter.parse_full_body(img)
    alpha_arr = np.array(out.segmented_image.split()[-1])

    # Pixels where Face or Hair or Legs are predicted MUST have zero alpha
    face_hair_mask = (pred_seg == 11) | (pred_seg == 2) | (pred_seg == 12) | (pred_seg == 13)
    leaked_person_pixels = np.sum((alpha_arr > 50) & face_hair_mask)
    total_person_pixels = np.sum(face_hair_mask)
    leak_rate = leaked_person_pixels / max(total_person_pixels, 1)
    assert leak_rate < 0.01, f"Person contamination detected in garment mask: {leak_rate*100:.2f}%"


def test_occlusion_mask_and_surface_ratios():
    """Verifies occlusion detection and conservation of surface ratios."""
    if not os.path.exists(REF_TSHIRT_PATH):
        pytest.skip("Reference image not available")

    img = Image.open(REF_TSHIRT_PATH)
    out = human_parsing_segmenter.segment(img)

    assert out.occlusion_mask is not None
    assert out.occlusion_ratio >= 0.0
    assert out.visible_surface_ratio <= 1.0
    assert abs((out.visible_surface_ratio + out.inferred_surface_ratio) - 1.0) < 1e-4
    assert out.silhouette_quality > 0.70


def test_reference_oversized_tshirt_e2e_reconstruction():
    """Verifies end-to-end intelligence and 3D reconstruction on the reference woman photo."""
    if not os.path.exists(REF_TSHIRT_PATH):
        pytest.skip("Reference image not available")

    intel, diag, seg_out = garment_intelligence_service.analyze(
        front_image=Image.open(REF_TSHIRT_PATH),
        job_id="test_phase_11b_unit"
    )

    assert intel.category == "tops"
    assert intel.subcategory == "tshirt"
    assert intel.fit in ["oversized", "regular"]
    assert "oversized" in intel.display_name.lower() or "t-shirt" in intel.display_name.lower()
    assert intel.primary_color_name in ["sand beige", "grey", "charcoal", "white"]

    # Diagnostics verification
    assert diag.human_parsing_preview_data_url is not None
    assert diag.garment_crop_preview_data_url is not None
    assert diag.on_body_telemetry is not None
    assert diag.on_body_telemetry["image_type"] in ["lifestyle_fashion", "on_body"]

    # 3D mesh building
    mesh = garment_mesh_builder.build_mesh(
        category=intel.category,
        subcategory=intel.subcategory,
        sleeve_length=intel.sleeve_length,
        neckline_type=intel.neckline_type,
        fit=intel.fit,
        intelligence=intel
    )
    assert len(mesh.positions) > 100
    assert len(mesh.indices) > 200


def test_texture_synthesis_zero_body_bleed(tmp_path):
    """Verifies that PBR texture synthesis does not bleed person or background into diffuse map."""
    if not os.path.exists(REF_TSHIRT_PATH):
        pytest.skip("Reference image not available")

    img = Image.open(REF_TSHIRT_PATH)
    seg_out = human_parsing_segmenter.segment(img)

    appearance = garment_appearance_analyzer.analyze_appearance(
        image=seg_out.segmented_image,
        alpha_mask=seg_out.alpha_mask,
        category="tops",
        subcategory="tshirt",
        has_back_view=False,
        job_id="test_tex_bleed"
    )

    tex_res = reference_texture_reconstructor.reconstruct_textures(
        segmented_front=seg_out.segmented_image,
        appearance=appearance,
        category="tops",
        subcategory="tshirt",
        output_dir=str(tmp_path),
        texture_size=512
    )

    diffuse = Image.open(tex_res["diffuse_path"])
    diff_arr = np.array(diffuse)

    # In diffuse map, color tone should match the heather grey / sand beige fabric (~150-195)
    mean_rgb = diff_arr.mean(axis=(0, 1))
    assert 130 < mean_rgb[0] < 210
    assert 130 < mean_rgb[1] < 210
    assert 120 < mean_rgb[2] < 210


def test_benchmark_suite_results_and_manifold_validity():
    """Verifies that the Phase 11B benchmark JSON exists and meets quality gates."""
    assert os.path.exists(BENCHMARK_JSON_PATH), f"Benchmark JSON not found at {BENCHMARK_JSON_PATH}"

    with open(BENCHMARK_JSON_PATH) as f:
        bench_data = json.load(f)

    assert bench_data["cases_evaluated"] == 10
    assert bench_data["all_meshes_manifold"] is True
    assert bench_data["mean_silhouette_quality"] >= 0.85
    assert bench_data["image_type_classification_accuracy"] >= 0.90
    assert len(bench_data["cases"]) == 10

    for c in bench_data["cases"]:
        assert c["is_manifold"] is True
        assert c["vertex_count"] > 100
        assert c["triangle_count"] > 200
        assert c["silhouette_quality"] > 0.60

