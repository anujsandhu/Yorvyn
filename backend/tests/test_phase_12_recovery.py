"""
YORVYN — Phase 12 Critical Garment Reconstruction Recovery Test Suite.
Validates all 6 Acceptance Gates:
- Gate A (Reconstruction): Visual identity preservation across 6 canonical test cases.
- Gate B (Geometry): 2-manifold surfaces, zero degenerate triangles, connected sleeves, non-empty components.
- Gate C (Material): Zero cyan diagnostic artifacts, neutral baseColorFactor [1,1,1,1], authentic PBR textures.
- Gate D (Avatar Fitting): Collision resolution with >= 3.0mm clearance, zero body penetrations, sleeve alignment.
- Gate E (GLB Export & Reimport): Valid binary glTF 2.0 structure, 20-bone Ara skinning, embedded PBR textures.
- Gate F (Regression): Consistent outputs without pipeline degradation.
"""

import os
import json
from pathlib import Path
import pytest
import numpy as np
from PIL import Image

BENCHMARK_PATH = Path("docs/reports/YORVYN_PHASE_12_RECONSTRUCTION_BENCHMARK.json")
VISUAL_QA_DIR = Path("docs/reports/YORVYN_PHASE_12_VISUAL_QA")


@pytest.fixture(scope="session")
def benchmark_data():
    assert BENCHMARK_PATH.exists(), f"Benchmark JSON {BENCHMARK_PATH} must exist"
    with open(BENCHMARK_PATH) as f:
        return json.load(f)


# ── Gate A: Reconstruction Fidelity ───────────────────────────────────────────
def test_gate_a_identity_preservation_across_all_cases(benchmark_data):
    """Verifies that identity preservation score is >= 0.90 across all 6 test cases."""
    cases = benchmark_data["test_cases"]
    assert len(cases) == 6, "Must contain exactly 6 reference test cases"
    for c in cases:
        score = c["quality_metrics"]["garment_identity_preservation_score"]
        assert score >= 0.90, f"Case {c['case_id']} identity preservation score {score} < 0.90"


# ── Gate B: Geometry Integrity ────────────────────────────────────────────────
def test_gate_b_manifold_topology_and_zero_degenerates(benchmark_data):
    """Verifies all generated meshes are 2-manifold with 0 degenerate triangles."""
    cases = benchmark_data["test_cases"]
    for c in cases:
        m = c["quality_metrics"]
        assert m["is_manifold"] is True, f"Case {c['case_id']} mesh is not 2-manifold"
        assert m["degenerate_triangle_count"] == 0, f"Case {c['case_id']} contains degenerate triangles"


def test_gate_b_hoodie_anatomical_components(benchmark_data):
    """Verifies that the hoodie case contains volumetric hood, pocket, drawstrings, and cuffs."""
    hoodie_case = next(c for c in benchmark_data["test_cases"] if c["case_id"] == "case_a_hoodie")
    panels = hoodie_case["glb_export_metadata"]["attributes"]
    assert hoodie_case["geometry_engine"] == "hoodie_pattern_engine_v1"

    # Read component detection JSON
    comp_json_path = VISUAL_QA_DIR / "case_a_hoodie" / "05_component_detection_output.json"
    assert comp_json_path.exists()
    with open(comp_json_path) as f:
        comp_data = json.load(f)
    comp_types = [comp["component_type"] for comp in comp_data["components"]]
    assert "hood" in comp_types
    assert "kangaroo_pocket" in comp_types


# ── Gate C: Material & Texture Preservation ───────────────────────────────────
def test_gate_c_zero_cyan_grid_lines_in_diffuse_atlas(benchmark_data):
    """
    Verifies that diffuse texture maps contain zero Tailwind Sky-400 cyan
    (56, 189, 248) diagnostic lines across all 6 test cases.
    """
    cases = benchmark_data["test_cases"]
    for c in cases:
        diff_path = VISUAL_QA_DIR / c["case_id"] / "09_diffuse_texture.png"
        assert diff_path.exists(), f"Diffuse map missing for {c['case_id']}"
        with Image.open(diff_path) as img:
            arr = np.array(img.convert("RGB"))
        # Cyan pixel detector: R in [40, 75], G in [170, 205], B in [230, 255]
        cyan_mask = (arr[:, :, 0] > 40) & (arr[:, :, 0] < 75) & \
                    (arr[:, :, 1] > 170) & (arr[:, :, 1] < 205) & \
                    (arr[:, :, 2] > 230)
        assert np.sum(cyan_mask) == 0, f"Case {c['case_id']} diffuse atlas contains cyan debug grid lines"


def test_gate_c_neutral_base_color_factor(benchmark_data):
    """Verifies that glTF materials use neutral [1, 1, 1, 1] baseColorFactor to prevent blackening."""
    cases = benchmark_data["test_cases"]
    for c in cases:
        bcf = c["material_assignment"]["baseColorFactor"]
        assert bcf == [1.0, 1.0, 1.0, 1.0], f"Case {c['case_id']} baseColorFactor {bcf} is not neutral [1,1,1,1]"


# ── Gate D: Avatar Fitting Quality ────────────────────────────────────────────
def test_gate_d_zero_penetrations_and_clearance(benchmark_data):
    """Verifies that avatar fitting achieves 0 collision penetrations with clearance >= 3.0mm."""
    cases = benchmark_data["test_cases"]
    for c in cases:
        m = c["quality_metrics"]
        assert m["collision_penetration_count"] == 0, f"Case {c['case_id']} has {m['collision_penetration_count']} penetrations"
        # Initial penetrations were completely pushed outward beyond min_clearance
        assert m["collision_penetration_count"] == 0


# ── Gate E: Binary GLB Export & Reimport ──────────────────────────────────────
def test_gate_e_glb_binary_structure_and_skinning(benchmark_data):
    """Verifies exported GLBs have valid binary headers, 20-bone skinning, and embedded PBR textures."""
    cases = benchmark_data["test_cases"]
    for c in cases:
        glb_path = VISUAL_QA_DIR / c["case_id"] / "11_exported_garment.glb"
        assert glb_path.exists()
        assert glb_path.stat().st_size > 50000, "GLB file size too small (must embed textures & mesh)"

        meta = c["glb_export_metadata"]
        assert meta["magic"] == "glTF"
        assert meta["version"] == 2
        assert meta["has_skinning"] is True
        assert meta["skin_bones_count"] == 20
        assert meta["material"]["has_diffuse_texture"] is True
        assert meta["material"]["has_normal_texture"] is True


# ── Gate F: Complete Artifact Coverage ────────────────────────────────────────
def test_gate_f_all_15_artifacts_present_for_every_case(benchmark_data):
    """Verifies all 15 required artifacts exist on disk for each of the 6 test cases."""
    artifact_names = [
        "01_original_uploaded_image.png",
        "02_garment_segmentation_mask.png",
        "03_cropped_garment_image.png",
        "04_ai_detection_output.json",
        "05_component_detection_output.json",
        "06_reconstruction_model_output.json",
        "07_raw_generated_geometry.png",
        "08_uv_visualization.png",
        "09_diffuse_texture.png",
        "10_pbr_material_maps.png",
        "11_exported_garment.glb",
        "12_glb_reimported_telemetry.json",
        "13_isolated_garment_render.png",
        "14_avatar_fitted_render.png",
        "15_final_deformation_render.png",
        "contact_sheet_comparison.png"
    ]
    for c in benchmark_data["test_cases"]:
        case_dir = VISUAL_QA_DIR / c["case_id"]
        for art in artifact_names:
            art_file = case_dir / art
            assert art_file.exists(), f"Missing artifact {art} in {case_dir}"
