"""Phase 16.3 tests: Design Revisions Persistence, Version Conflict Detection,
2D-to-3D Pattern Sync, Bounded Parametric GLB Editing, and Stylist Design Commands."""
from __future__ import annotations

import base64
import io
import json
import struct

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from backend.app.main import app
from backend.app.core.security import UserContext, get_current_user_optional
from backend.app.services.garments.chat_candidate import apply_parametric_design_edit
from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.services.garments.mesh_validation_service import MeshValidationService
from backend.app.services.garments.reconstruction.base_reconstruction_engine import (
    GarmentComponentGraph,
    GarmentComponentNode,
)
from backend.app.services.llm.garment_plan import local_plan, parse_stylist_design_command


def _sample_component_glb() -> bytes:
    """Create a multi-component manifold-safe test GLB with torso + collar + sleeves."""
    # Torso vertices 0..3, collar vertices 4..7, left_sleeve vertices 8..11
    pts = np.array([
        [-0.25, 0.0, 0.0], [0.25, 0.0, 0.0], [0.25, 0.60, 0.0], [-0.25, 0.60, 0.15],
        [-0.12, 0.58, 0.0], [0.12, 0.58, 0.0], [0.12, 0.68, 0.0], [-0.12, 0.68, 0.08],
        [-0.55, 0.30, 0.0], [-0.26, 0.30, 0.0], [-0.26, 0.58, 0.0], [-0.55, 0.58, 0.08],
    ], dtype=float)
    faces = np.array([
        [0, 1, 2], [0, 2, 3], [0, 1, 3], [1, 2, 3],
        [4, 5, 6], [4, 6, 7], [4, 5, 7], [5, 6, 7],
        [8, 9, 10], [8, 10, 11], [8, 9, 11], [9, 10, 11],
    ])
    norms = np.tile([0.0, 0.0, 1.0], (len(pts), 1))
    uvs = np.zeros((len(pts), 2), dtype=float)
    mesh = GarmentMesh(pts, norms, uvs, faces)

    nodes = [
        GarmentComponentNode(
            component_id="torso", category="jacket", semantic_type="torso",
            triangle_range=(0, 4), dimensions_m=(0.50, 0.60, 0.15),
            bounding_box_3d=((-0.25, 0.0, 0.0), (0.25, 0.60, 0.15)),
        ),
        GarmentComponentNode(
            component_id="collar", category="jacket", semantic_type="collar",
            parent_id="torso", triangle_range=(4, 4), dimensions_m=(0.24, 0.10, 0.08),
            bounding_box_3d=((-0.12, 0.58, 0.0), (0.12, 0.68, 0.08)),
        ),
        GarmentComponentNode(
            component_id="left_sleeve", category="jacket", semantic_type="sleeve",
            parent_id="torso", triangle_range=(8, 4), dimensions_m=(0.29, 0.28, 0.08),
            bounding_box_3d=((-0.55, 0.30, 0.0), (-0.26, 0.58, 0.08)),
        ),
    ]
    cgraph = GarmentComponentGraph(nodes={n.component_id: n for n in nodes}, root_ids=["torso"])
    img = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(img, format="PNG")
    return glb_exporter.export(mesh, img.getvalue(), img.getvalue(), component_graph=cgraph)


def test_parametric_glb_edit_preserves_topology_and_enforces_bounds():
    src = _sample_component_glb()
    edited = apply_parametric_design_edit(
        src,
        torso_width_scale=1.15,
        torso_length_scale=0.92,
        collar_width_scale=0.85,
        sleeve_width_scale=1.10,
        base_color_rgba=[0.12, 0.23, 0.37, 1.0],
        roughness=0.88,
        metalness=0.04,
    )
    assert edited.startswith(b"glTF") and edited != src
    report = MeshValidationService.validate_glb_bytes(edited, "jacket")
    assert report.is_valid, report.issues

    # Unbounded scales must fail closed
    with pytest.raises(ValueError, match="outside valid bounds"):
        apply_parametric_design_edit(src, torso_width_scale=3.0)


def test_revisions_persistence_version_conflict_and_owner_isolation():
    current_uid = {"id": "user_alpha"}

    async def override_user():
        return UserContext(user_id=current_uid["id"], email="a@test.local")

    app.dependency_overrides[get_current_user_optional] = override_user
    try:
        client = TestClient(app)
        gid = "garment_rev_test_1"
        r1 = client.post(
            f"/api/garments/{gid}/revisions",
            json={
                "category": "jacket",
                "subcategory": "denim_jacket",
                "geometry_params": {"torso_width_scale": 1.08},
                "material_config": {"preset": "denim", "base_color": "#1e3a5f", "roughness": 0.86},
                "measurements": {"chest_width_m": 0.583},
            },
        )
        assert r1.status_code == 200, r1.text
        rev1 = r1.json()["revision"]
        assert rev1["design_version"] == 1
        assert rev1["geometry_hash"] and rev1["pattern_hash"]

        # Stale parent version must be rejected with 409 Conflict
        conflict = client.post(
            f"/api/garments/{gid}/revisions",
            json={"expected_parent_version": 0, "geometry_params": {"torso_width_scale": 1.2}},
        )
        assert conflict.status_code == 409

        # Owner Beta cannot see or restore Alpha's saved revisions
        current_uid["id"] = "user_beta"
        assert client.get(f"/api/garments/{gid}/revisions").json()["count"] == 0
        assert client.get(f"/api/garments/{gid}/revisions/{rev1['revision_id']}").status_code == 404

        # Owner Alpha restores exact revision cleanly
        current_uid["id"] = "user_alpha"
        restored = client.get(f"/api/garments/{gid}/revisions/{rev1['revision_id']}")
        assert restored.status_code == 200
        assert restored.json()["revision"]["material_config"]["preset"] == "denim"
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)


def test_sync_pattern_validation_and_candidate_edit_gl_endpoint():
    client = TestClient(app)
    # Valid 2D polygon override propagates to 3D scale factors & generates SVG/DXF/JSON exports
    ok = client.post(
        "/api/garments/g_sync_01/sync-pattern",
        json={
            "category": "tops",
            "subcategory": "tshirt",
            "piece_overrides": [
                {
                    "piece_id": "front_body",
                    "boundary_polygon": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 0.60, "y": 0.0},
                        {"x": 0.60, "y": 0.72},
                        {"x": 0.0, "y": 0.72},
                    ],
                }
            ],
            "include_exports": True,
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["synced_geometry_params"]["torso_width_scale"] != 1.0
    assert "<svg" in body["exports"]["svg"] and "ENTITIES" in body["exports"]["dxf"]

    # Self-intersecting bowtie polygon MUST fail validation (422) without mutating graph
    bad = client.post(
        "/api/garments/g_sync_01/sync-pattern",
        json={
            "category": "tops",
            "piece_overrides": [
                {
                    "piece_id": "front_body",
                    "boundary_polygon": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 0.5, "y": 0.5},
                        {"x": 0.5, "y": 0.0},
                        {"x": 0.0, "y": 0.5},
                    ],
                }
            ],
        },
    )
    assert bad.status_code == 422

    # Candidate binary GLB parametric edit route
    src_b64 = base64.b64encode(_sample_component_glb()).decode("ascii")
    gl_res = client.post(
        "/api/garments/g_sync_01/candidate-edit-gl",
        json={"glb_base64": src_b64, "category": "jacket", "collar_width_scale": 0.85},
    )
    assert gl_res.status_code == 200, gl_res.text
    assert gl_res.json()["mesh_report"]["is_valid"] is True


def test_stylist_design_commands_preserve_safety_and_map_view_material_geometry():
    plan_wf, _ = local_plan("Show the garment in wireframe", False)
    assert plan_wf.action == "inspect"
    assert parse_stylist_design_command("Show the garment in wireframe")["patch"] == {"wireframe": True}
    assert parse_stylist_design_command("Display the stitching")["material"]["stitchVisible"] is True
    assert parse_stylist_design_command("Change the print placement")["material"]["printScale"] == 1.15
    assert parse_stylist_design_command("Change the fabric to dark denim")["material"]["preset"] == "denim"
    assert parse_stylist_design_command("Make the collar narrower")["geometry"]["collarWidthScale"] == 0.88
    assert parse_stylist_design_command("Add a chest pocket")["kind"] == "rebuild_or_component"
    assert parse_stylist_design_command("Don't show wireframe") is None
