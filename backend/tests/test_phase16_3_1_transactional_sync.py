"""Phase 16.3.1 Tests: Semantic Pattern-to-Mesh Correspondence, Construction Constraint Validation,
Dimensional Scoped Arithmetic, 13-Step Atomic Transactional Design Engine, and Stylist Commands."""
from __future__ import annotations

import base64
import io
import threading

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from backend.app.core.security import UserContext, get_current_user_optional
from backend.app.main import app
from backend.app.services.garments.design_revisions import design_revision_service
from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.services.garments.reconstruction.base_reconstruction_engine import (
    GarmentComponentGraph,
    GarmentComponentNode,
)
from backend.app.services.garments.reconstruction.pattern_geometry import ConstructionVerificationState
from backend.app.services.garments.transactional_design_engine import (
    DesignTransactionRequest,
    transactional_design_engine,
    validate_extended_construction,
)
from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine
from backend.app.services.intelligence.semantic_correspondence import (
    MeasurementScope,
    SyncStatus,
    apply_panel_ease_to_chest,
    build_semantic_correspondence,
    half_chest_to_circumference_m,
    net_dimension_excluding_seam_allowance_m,
    panel_width_to_half_chest_m,
    validate_correspondence_against_topology,
)
from backend.app.services.llm.garment_plan import parse_stylist_design_command


def _sample_rigged_jacket_glb() -> bytes:
    pts = np.array([
        [-0.22, 0.86, 0.0], [0.22, 0.86, 0.0], [0.22, 1.43, 0.0], [-0.22, 1.43, 0.14],
        [-0.12, 1.40, 0.0], [0.12, 1.40, 0.0], [0.12, 1.48, 0.0], [-0.12, 1.48, 0.08],
        [-0.50, 1.15, 0.0], [-0.24, 1.15, 0.0], [-0.24, 1.40, 0.0], [-0.50, 1.40, 0.08],
    ], dtype=float)
    faces = np.array([
        [0, 1, 2], [0, 2, 3], [0, 1, 3], [1, 2, 3],
        [4, 5, 6], [4, 6, 7], [4, 5, 7], [5, 6, 7],
        [8, 9, 10], [8, 10, 11], [8, 9, 11], [9, 10, 11],
    ])
    mesh = GarmentMesh(pts, np.tile([0.0, 0.0, 1.0], (len(pts), 1)), np.zeros((len(pts), 2)), faces)
    nodes = [
        GarmentComponentNode(component_id="main_torso", category="outerwear", semantic_type="torso", triangle_range=(0, 4)),
        GarmentComponentNode(component_id="lapels_and_collar", category="outerwear", semantic_type="lapel", parent_id="main_torso", triangle_range=(4, 4)),
        GarmentComponentNode(component_id="left_sleeve", category="outerwear", semantic_type="sleeve", parent_id="main_torso", triangle_range=(8, 4)),
    ]
    cg = GarmentComponentGraph(nodes={n.component_id: n for n in nodes}, root_ids=["main_torso"])
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
    return glb_exporter.export(mesh, buf.getvalue(), buf.getvalue(), component_graph=cg)


def test_dimensional_contract_and_panel_ease_forensic_reconciliation():
    # Prove exact conversions across scopes
    assert panel_width_to_half_chest_m(0.216, MeasurementScope.PATTERN_PANEL_HALF) == 0.432
    assert half_chest_to_circumference_m(0.432) == 0.864
    assert net_dimension_excluding_seam_allowance_m(0.452, 0.01, sides=2) == 0.432

    # Verify forensic explanation of earlier 54.0 cm -> 61.5 cm observation AND exact new behavior:
    # Old client heuristic applied (0.216 + 0.03) / 0.216 * 54.0 = 61.5 cm.
    # Explicit Phase 16.3.1 contract computes +3.0 cm on a 21.6 cm half-panel cleanly:
    conv = apply_panel_ease_to_chest(
        panel_width_m=0.216,
        panel_scope=MeasurementScope.PATTERN_PANEL_HALF,
        ease_delta_m=0.03,
        apply_symmetrically=True,
    )
    assert conv["panel_width"].value_cm == 24.6
    assert conv["half_garment_flat"].value_cm == 49.2
    assert conv["finished_garment_circumference"].value_cm == 98.4
    assert conv["applied_ease_delta"].value_cm == 3.0


def test_semantic_correspondence_lookup_invalidation_and_evidence_preservation():
    handoff = pattern_construction_engine.build_construction("g_corr_1", "jacket", "denim_jacket")
    corr = build_semantic_correspondence(
        garment_id="g_corr_1",
        candidate_id="cand_1",
        graph=handoff.construction_graph,
        available_3d_regions=["main_torso", "lapels_and_collar", "left_sleeve", "right_sleeve", "left_cuff", "right_cuff"],
        pattern_version=1,
        geometry_version=1,
    )
    corr.topology_signature.vertex_count = 12
    corr.topology_signature.triangle_count = 12

    assert corr.piece_mappings["front_left_body"].mesh_region_ids == ["main_torso"]
    assert corr.piece_mappings["front_left_body"].panel_scope == MeasurementScope.PATTERN_PANEL_HALF
    assert corr.piece_mappings["left_sleeve"].uv_region_id == "sleeve_left_uv"
    # Unobserved back piece MUST stay INFERRED inside correspondence too
    assert corr.piece_mappings["back_body"].verification_state == ConstructionVerificationState.INFERRED

    ok, status, reasons = validate_correspondence_against_topology(
        corr, expected_vertex_count=12, expected_triangle_count=12, operation_name="torso_width",
    )
    assert ok is True
    assert status == SyncStatus.SYNCHRONIZED_WITH_UNCERTAINTY
    assert not reasons

    # Topology change invalidates mapping
    ok_bad, status_bad, reasons_bad = validate_correspondence_against_topology(
        corr, expected_vertex_count=20, expected_triangle_count=12, operation_name="torso_width",
    )
    assert ok_bad is False
    assert status_bad == SyncStatus.MAPPING_INVALID
    assert "Vertex count changed" in reasons_bad[0]

    # Unsupported category operation fails explicitly without guessing
    ok_unsup, status_unsup, _ = validate_correspondence_against_topology(
        build_semantic_correspondence(garment_id="g_corr_1", candidate_id="cand_1", graph=handoff.construction_graph),
        expected_vertex_count=0, expected_triangle_count=0, operation_name="leg_width",
    )
    assert ok_unsup is False and status_unsup == SyncStatus.NOT_SUPPORTED


def test_extended_construction_validator_catches_disconnected_and_asymmetric_panels():
    handoff = pattern_construction_engine.build_construction("g_val_1", "shirt", "casual_shirt")
    g = handoff.construction_graph.model_copy(deep=True)
    # Remove seams for left_cuff so it becomes disconnected
    g.seams = [s for s in g.seams if s.piece_a != "left_cuff" and s.piece_b != "left_cuff"]
    # Corrupt symmetry
    g.pieces["front_left_body"].area_m2 *= 1.5
    # Invalid seam allowance
    g.pieces["collar"].seam_allowance_m = 0.25

    rep = validate_extended_construction(g, allow_asymmetric=False)
    assert not rep.is_valid
    codes = {i.code for i in rep.issues}
    assert "DISCONNECTED_PATTERN_PANELS" in codes
    assert "SYMMETRY_VIOLATION" in codes
    assert "INVALID_SEAM_ALLOWANCE" in codes


def test_atomic_transaction_commit_rollback_idempotency_and_cancellation():
    gid = "g_tx_atomic_01"
    uid = "tx_tester_1"
    glb_b64 = base64.b64encode(_sample_rigged_jacket_glb()).decode("ascii")

    # 1. Successful atomic commit with +3 cm scoped panel ease + real GLB
    res1 = transactional_design_engine.execute_transaction(
        user_id=uid,
        garment_id=gid,
        req=DesignTransactionRequest(
            request_id="req_tx_01",
            operation_name="torso_width",
            category="jacket",
            subcategory="denim_jacket",
            panel_ease_delta_m=0.03,
            target_piece_id="front_left_body",
            glb_base64=glb_b64,
        ),
    )
    assert res1.committed is True and res1.rolled_back is False
    assert res1.revision is not None and res1.revision.design_version == 1
    assert res1.sync_status == SyncStatus.SYNCHRONIZED_WITH_UNCERTAINTY
    # Jacket front_left_body starts at 21.75 cm (PATTERN_PANEL_HALF); +3.0 cm ease -> 24.75 cm exact
    assert res1.scoped_measurements["panel_width"]["value_cm"] == 24.75
    assert res1.scoped_measurements["half_garment_flat"]["value_cm"] == 49.5
    assert res1.scoped_measurements["finished_garment_circumference"]["value_cm"] == 99.0
    assert res1.edited_glb_base64 is not None

    # 2. Idempotent replay returns exact same revision
    res_dup = transactional_design_engine.execute_transaction(
        user_id=uid,
        garment_id=gid,
        req=DesignTransactionRequest(request_id="req_tx_01", operation_name="torso_width", category="jacket"),
    )
    assert res_dup.revision.revision_id == res1.revision.revision_id
    assert len(design_revision_service.list_revisions(uid, gid)) == 1

    # 3. Failed pattern validation MUST rollback and preserve v1 untouched
    res_bad = transactional_design_engine.execute_transaction(
        user_id=uid,
        garment_id=gid,
        req=DesignTransactionRequest(
            request_id="req_tx_bad_poly",
            expected_parent_version=1,
            operation_name="pattern_edit",
            category="jacket",
            piece_overrides=[{
                "piece_id": "front_left_body",
                "boundary_polygon": [{"x": 0.0, "y": 0.0}, {"x": 0.3, "y": 0.3}, {"x": 0.3, "y": 0.0}, {"x": 0.0, "y": 0.3}],
            }],
        ),
    )
    assert res_bad.committed is False and res_bad.rolled_back is True
    assert res_bad.sync_status == SyncStatus.VALIDATION_FAILED
    assert len(design_revision_service.list_revisions(uid, gid)) == 1

    # 4. Stale parent version returns CONSTRUCTION_CONFLICT
    res_stale = transactional_design_engine.execute_transaction(
        user_id=uid,
        garment_id=gid,
        req=DesignTransactionRequest(request_id="req_tx_stale", expected_parent_version=0, operation_name="torso_width", category="jacket"),
    )
    assert res_stale.committed is False and res_stale.sync_status == SyncStatus.CONSTRUCTION_CONFLICT

    # 5. Cancelled transaction preserves v1 cleanly
    ev = threading.Event()
    ev.set()
    res_cancel = transactional_design_engine.execute_transaction(
        user_id=uid,
        garment_id=gid,
        req=DesignTransactionRequest(request_id="req_tx_cancel", expected_parent_version=1, operation_name="torso_width", category="jacket"),
        cancel_event=ev,
    )
    assert res_cancel.committed is False and res_cancel.rolled_back is True
    assert len(design_revision_service.list_revisions(uid, gid)) == 1


def test_http_transaction_correspondence_and_stylist_command_routes():
    uid = {"id": "route_owner_1"}

    async def override():
        return UserContext(user_id=uid["id"], email="r@test.local")

    app.dependency_overrides[get_current_user_optional] = override
    try:
        client = TestClient(app)
        corr_r = client.get("/api/garments/g_rt_01/correspondence?category=bottoms&subcategory=jeans")
        assert corr_r.status_code == 200
        ops = {op["operation_name"] for op in corr_r.json()["supported_operations"]}
        assert {"leg_width", "leg_length", "waistband_width"}.issubset(ops)
        assert "collar_width" not in ops

        tx_ok = client.post(
            "/api/garments/g_rt_01/transactions/execute",
            json={"operation_name": "leg_width", "category": "bottoms", "subcategory": "jeans", "geometry_params": {"leg_width_scale": 1.12}},
        )
        assert tx_ok.status_code == 200, tx_ok.text
        assert tx_ok.json()["committed"] is True

        tx_unsup = client.post(
            "/api/garments/g_rt_01/transactions/execute",
            json={"operation_name": "collar_width", "category": "bottoms", "subcategory": "jeans"},
        )
        assert tx_unsup.status_code == 422
        assert tx_unsup.json()["detail"]["sync_status"] == "NOT_SUPPORTED"

        # Verify all required Section 12 Stylist commands map deterministically
        assert parse_stylist_design_command("Widen the jacket chest")["operation"] == "torso_width"
        assert parse_stylist_design_command("Shorten the sleeves")["operation"] == "sleeve_length"
        assert parse_stylist_design_command("Increase the collar width")["operation"] == "collar_width"
        assert parse_stylist_design_command("Make the trouser legs wider")["operation"] == "leg_width"
        assert parse_stylist_design_command("Adjust the hem")["operation"] == "hem_width"
        assert parse_stylist_design_command("Move the pocket")["operation"] == "pocket_placement"
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)
