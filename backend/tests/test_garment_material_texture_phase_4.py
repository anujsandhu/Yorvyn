"""
YORVYN — Phase 4: Intelligent Garment Material, Texture, UV & Surface Reconstruction Test Suite
Tests:
1. GarmentAppearanceAnalyzer: color extraction, distribution, fabric categorization,
   pattern classification, graphic print localization, hardware detection, and provenance.
2. CategoryMaterialSystem: category PBR priors (9 categories), specular evidence refinement.
3. GarmentUVReconstructionEngine: category-tailored UV layouts, island bounds, UV stretch conformal metric.
4. ReferenceTextureReconstructor: 4-channel PBR map generation (diffuse, normal, metallic-roughness, AO),
   graphic isolation, multi-view rear mapping vs non-mirrored rear synthesis.
5. GLBExporter: embedding all PBR maps (baseColor, normal, metallicRoughness, occlusion),
   preserving Ara 3D 20-bone skinning.
6. AppearanceModelEvaluator: open-weight learned model audit and Apple Silicon M2 8GB constraints.
7. REST API: GET /api/fashion/garment-gen/appearance-evaluations endpoint.
"""

import os
import io
from typing import Tuple, List, Dict, Optional, Any
import pytest
import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.garments.garment_mesh_builder import garment_mesh_builder
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.services.garments.reconstruction import TopsReconstructionEngine, BottomsReconstructionEngine
from backend.app.services.garments.appearance import (
    garment_appearance_analyzer,
    CategoryMaterialSystem,
    GarmentUVReconstructionEngine,
    reference_texture_reconstructor,
    AppearanceModelEvaluator
)
from backend.app.models.garment_intelligence_models import (
    GarmentAppearanceResultV2,
    FabricPBRPropertiesV2,
    GraphicPrintPlacementV2
)

client = TestClient(app)


def _create_synthetic_graphic_tshirt(width=400, height=400) -> Tuple[Image.Image, np.ndarray]:
    """Generates synthetic navy T-shirt with a white chest graphic logo and transparent background."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark Navy T-Shirt body
    navy = (20, 30, 60, 255)
    draw.rectangle([130, 90, 270, 350], fill=navy)
    draw.polygon([(130, 90), (70, 160), (105, 190), (130, 145)], fill=navy) # Left sleeve
    draw.polygon([(270, 90), (330, 160), (295, 190), (270, 145)], fill=navy) # Right sleeve

    # White Chest Graphic (logo / text box)
    white = (245, 245, 250, 255)
    draw.rectangle([165, 150, 235, 210], fill=white)
    draw.text((175, 175), "YORVYN", fill=(20, 30, 60, 255))

    alpha_mask = np.array(img.split()[3])
    return img, alpha_mask


def _create_synthetic_denim_jeans(width=400, height=400) -> Tuple[Image.Image, np.ndarray]:
    """Generates synthetic denim blue jeans with waistband and legs."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    denim_blue = (40, 75, 125, 255)
    # Pelvis
    draw.rectangle([130, 40, 270, 150], fill=denim_blue)
    # Left leg
    draw.rectangle([130, 150, 190, 380], fill=denim_blue)
    # Right leg
    draw.rectangle([210, 150, 270, 380], fill=denim_blue)
    # Gold waistband rivet button
    draw.ellipse([195, 55, 205, 65], fill=(220, 180, 50, 255))

    alpha_mask = np.array(img.split()[3])
    return img, alpha_mask


# ── 1. Garment Appearance Intelligence Tests ─────────────────────────────────

def test_appearance_analyzer_graphic_tshirt():
    """Verifies appearance analyzer extracts navy color, cotton fabric, chest graphic, and provenance."""
    img, alpha = _create_synthetic_graphic_tshirt()
    res = garment_appearance_analyzer.analyze_appearance(
        image=img,
        alpha_mask=alpha,
        category="tops",
        subcategory="tshirt",
        has_back_view=False,
        job_id="test_graphic_tshirt"
    )

    assert isinstance(res, GarmentAppearanceResultV2)
    assert res.primary_color_name.lower() in ["navy", "blue", "charcoal", "black", "indigo"]
    assert res.fabric.fabric_category in ["cotton", "synthetic"]
    assert res.fabric.roughness > 0.60
    assert res.pattern_type in ["graphic_print", "solid"]
    assert res.graphic.detected is True
    assert res.graphic.target_region == "chest"
    assert res.graphic.bbox is not None
    assert res.observed_front_surface_ratio < 0.90  # Single view -> rear is inferred
    assert res.provenance == "observed_front_inferred_rear"


def test_appearance_analyzer_denim_jeans():
    """Verifies appearance analyzer extracts denim twill weave, hardware button, and contrast stitching."""
    img, alpha = _create_synthetic_denim_jeans()
    res = garment_appearance_analyzer.analyze_appearance(
        image=img,
        alpha_mask=alpha,
        category="bottoms",
        subcategory="jeans",
        has_back_view=True,
        job_id="test_denim_jeans"
    )

    assert res.fabric.fabric_category == "denim"
    assert res.fabric.surface_texture == "twill_diagonal"
    assert res.fabric.roughness >= 0.75
    assert len(res.hardware) >= 1
    hw_types = [h.hardware_type for h in res.hardware]
    assert "button" in hw_types
    assert res.has_contrast_stitching is True
    assert res.provenance == "observed_front_and_rear"
    assert res.observed_front_surface_ratio > 0.90


# ── 2. Category-Specific Material System Tests ────────────────────────────────

def test_category_material_system_profiles():
    """Verifies all 9 categories receive distinct, physically grounded PBR material profiles."""
    cats = [
        ("tops", "tshirt", "cotton"),
        ("tops", "formal_shirt", "cotton"),
        ("tops", "hoodie", "fleece"),
        ("outerwear", "jacket", "denim"),
        ("bottoms", "jeans", "denim"),
        ("dresses_and_skirts", "dress", "silk"),
        ("traditional", "kurta", "silk"),
        ("footwear", "sneakers", "leather"),
        ("accessories", "caps", "cotton")
    ]

    for cat, subcat, expected_fabric in cats:
        prof = CategoryMaterialSystem.get_material_profile(cat, subcat)
        assert prof.fabric_category == expected_fabric, f"Failed for {cat}/{subcat}"
        assert 0.0 <= prof.roughness <= 1.0
        assert 0.0 <= prof.metalness <= 1.0
        assert 0.0 <= prof.sheen <= 1.0
        assert 0.0 <= prof.clearcoat <= 1.0


def test_category_material_specular_refinement():
    """Verifies high specular evidence dynamically reduces roughness and increases clearcoat."""
    matte = CategoryMaterialSystem.get_material_profile("tops", "tshirt", specular_evidence=0.05)
    glossy = CategoryMaterialSystem.get_material_profile("tops", "tshirt", specular_evidence=0.90)

    assert glossy.roughness < matte.roughness
    assert glossy.clearcoat > matte.clearcoat


# ── 3. UV Reconstruction Engine Tests ─────────────────────────────────────────

def test_uv_reconstruction_engine_layouts():
    """Verifies valid non-overlapping UV layouts for all 9 categories."""
    cats = ["tops", "formal_shirt", "hoodie", "jacket", "bottoms", "dresses_and_skirts", "traditional", "footwear", "accessories"]

    for cat in cats:
        layout = GarmentUVReconstructionEngine.get_layout(cat)
        assert len(layout.islands) >= 2
        for isl in layout.islands:
            assert 0.0 <= isl.u_min < isl.u_max <= 1.0
            assert 0.0 <= isl.v_min < isl.v_max <= 1.0
            assert isl.width > 0.02
            assert isl.height > 0.02


def test_uv_stretch_conformal_metric():
    """Verifies conformal UV stretch metric on Tops and Bottoms meshes."""
    mesh_top = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt").mesh
    stretch_top = GarmentUVReconstructionEngine.calculate_uv_stretch(mesh_top)
    assert 0.65 <= stretch_top <= 1.0

    mesh_bot = BottomsReconstructionEngine().reconstruct(category="bottoms", subcategory="jeans").mesh
    stretch_bot = GarmentUVReconstructionEngine.calculate_uv_stretch(mesh_bot)
    assert 0.65 <= stretch_bot <= 1.0


def test_render_uv_layout_preview():
    """Verifies UV schematic rendering produces valid RGBA image."""
    layout = GarmentUVReconstructionEngine.get_layout("tops")
    img = GarmentUVReconstructionEngine.render_uv_layout_preview(layout, size=256)
    assert isinstance(img, Image.Image)
    assert img.size == (256, 256)
    assert img.mode == "RGBA"


# ── 4. Reference-Driven Texture Reconstruction Tests ──────────────────────────

def test_reference_texture_reconstruction_tshirt(tmp_path):
    """Verifies diffuse, normal, metallic-roughness, and AO texture synthesis for graphic T-shirt."""
    img, alpha = _create_synthetic_graphic_tshirt()
    app_res = garment_appearance_analyzer.analyze_appearance(
        image=img,
        alpha_mask=alpha,
        category="tops",
        subcategory="tshirt",
        has_back_view=False,
        job_id="test_tex_tshirt"
    )

    out_dir = str(tmp_path / "tex_tshirt")
    res = reference_texture_reconstructor.reconstruct_textures(
        segmented_front=img,
        appearance=app_res,
        category="tops",
        subcategory="tshirt",
        output_dir=out_dir,
        texture_size=256
    )

    assert os.path.exists(res["diffuse_path"])
    assert os.path.exists(res["normal_path"])
    assert os.path.exists(res["metallic_roughness_path"])
    assert os.path.exists(res["occlusion_path"])

    # Verify diffuse texture size and mode
    with Image.open(res["diffuse_path"]) as d_img:
        assert d_img.size == (256, 256)
        assert d_img.mode == "RGB"

    # Verify normal map is centered around flat plane [128, 128, 255]
    with Image.open(res["normal_path"]) as n_img:
        n_arr = np.array(n_img)
        assert n_arr.shape == (256, 256, 3)
        # Blue channel should be strong (> 200) for outward Z normals
        assert np.mean(n_arr[:, :, 2]) > 210

    # Verify metallic-roughness map has roughness in Green and low metalness in Blue for cotton
    with Image.open(res["metallic_roughness_path"]) as mr_img:
        mr_arr = np.array(mr_img)
        # Cotton cloth metalness in Blue channel should be low (< 25)
        assert np.mean(mr_arr[:, :, 2]) < 25
        # Roughness in Green channel should be around cotton level (0.75 * 255 = ~190)
        assert np.mean(mr_arr[:, :, 1]) > 140

    # Verify color similarity metrics
    assert res["color_delta_e"] < 25.0
    assert res["histogram_similarity"] > 0.65


def test_reference_texture_reconstruction_multi_view(tmp_path):
    """Verifies rear photo is projected to rear UV island without mirroring front graphic."""
    front_img, front_alpha = _create_synthetic_graphic_tshirt()
    # Rear view is solid navy without the graphic
    back_img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(back_img)
    b_draw.rectangle([130, 90, 270, 350], fill=(20, 30, 60, 255))
    back_alpha = np.array(back_img.split()[3])

    app_res = garment_appearance_analyzer.analyze_appearance(
        image=front_img,
        alpha_mask=front_alpha,
        category="tops",
        subcategory="tshirt",
        has_back_view=True,
        job_id="test_mv_tshirt"
    )

    out_dir = str(tmp_path / "tex_mv_tshirt")
    res = reference_texture_reconstructor.reconstruct_textures(
        segmented_front=front_img,
        appearance=app_res,
        category="tops",
        subcategory="tshirt",
        output_dir=out_dir,
        segmented_back=back_img,
        texture_size=256
    )

    assert os.path.exists(res["diffuse_path"])
    with Image.open(res["diffuse_path"]) as d_img:
        d_arr = np.array(d_img)
        # Front torso island: x in [0.04, 0.46] * 256 = [10, 117]
        # Back torso island: x in [0.54, 0.96] * 256 = [138, 245]
        front_patch = d_arr[120:180, 30:90]
        back_patch = d_arr[120:180, 150:210]

        # Front patch should have white graphic pixels (max > 220)
        assert np.max(front_patch) > 220
        # Back patch should NOT have white graphic pixels (max < 100, navy base)
        assert np.max(back_patch) < 120


# ── 5. glTF 2.0 Binary Export with Full PBR Integration ───────────────────────

def test_glb_exporter_full_pbr_integration(tmp_path):
    """Verifies GLB exporter embeds diffuse, normal, metallic-roughness, and occlusion maps with 20-bone skinning."""
    mesh = TopsReconstructionEngine().reconstruct("tops", "tshirt").mesh

    def _make_dummy_bytes(c, mode="RGB"):
        im = Image.new(mode, (16, 16), c)
        b = io.BytesIO()
        im.save(b, format="PNG")
        return b.getvalue()

    diff_bytes = _make_dummy_bytes((30, 50, 90))
    norm_bytes = _make_dummy_bytes((128, 128, 255))
    mr_bytes = _make_dummy_bytes((255, 190, 10))
    ao_bytes = _make_dummy_bytes(240, mode="L")

    glb_data = glb_exporter.export(
        mesh=mesh,
        diffuse_png_bytes=diff_bytes,
        normal_png_bytes=norm_bytes,
        metallic_roughness_png_bytes=mr_bytes,
        occlusion_png_bytes=ao_bytes,
        name="test_pbr_glb",
        metallic_factor=0.05,
        roughness_factor=0.75
    )

    assert len(glb_data) > 1000
    assert glb_data[:4] == b"glTF"

    # Inspect internal glTF JSON chunk
    import json
    json_len = int.from_bytes(glb_data[12:16], "little")
    gltf = json.loads(glb_data[20:20 + json_len].decode("utf-8"))

    # Must contain 4 textures and 4 images
    tex_names = [t["name"] for t in gltf["textures"]]
    assert "baseColorTexture" in tex_names
    assert "normalTexture" in tex_names
    assert "metallicRoughnessTexture" in tex_names
    assert "occlusionTexture" in tex_names

    # Check PBR material definition
    mat = gltf["materials"][0]
    assert "pbrMetallicRoughness" in mat
    assert mat["pbrMetallicRoughness"]["metallicFactor"] == 0.05
    assert mat["pbrMetallicRoughness"]["roughnessFactor"] == 0.75
    assert "metallicRoughnessTexture" in mat["pbrMetallicRoughness"]
    assert "occlusionTexture" in mat
    assert "normalTexture" in mat

    # Check 20-bone skinning is preserved
    assert len(gltf["skins"]) == 1
    assert len(gltf["skins"][0]["joints"]) == 20


# ── 6. Learned Appearance Model Evaluator Tests ───────────────────────────────

def test_learned_appearance_model_evaluator():
    """Verifies technical audit for FabricNet, SF3D, Paint3D, and ControlNet Tile."""
    summary = AppearanceModelEvaluator.get_summary_report()
    assert summary["evaluated_models_count"] == 4
    models = summary["models"]

    assert "fabricnet_vit" in models
    assert "OPERATIONAL_LOCAL" in models["fabricnet_vit"]["apple_silicon_m2_8gb_status"]
    assert models["fabricnet_vit"]["weights_size_gb"] <= 0.5

    assert "paint3d_texture_generator" in models
    assert "INCOMPATIBLE_OOM" in models["paint3d_texture_generator"]["apple_silicon_m2_8gb_status"]
    assert models["paint3d_texture_generator"]["min_vram_gb"] >= 14.0


# ── 7. REST API Diagnostics & Appearance Evaluations ─────────────────────────

def test_api_appearance_evaluations_endpoint():
    """Verifies GET /api/fashion/garment-gen/appearance-evaluations returns benchmark report."""
    resp = client.get("/api/fashion/garment-gen/appearance-evaluations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluated_models_count"] == 4
    assert "fabricnet_vit" in data["models"]
    assert "sf3d_texture_delighter" in data["models"]
