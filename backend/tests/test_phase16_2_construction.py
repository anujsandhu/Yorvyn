"""Phase 16.2 tests: Garment Pattern Intelligence, 2D Pattern Geometry, Assembly Validation,
Evidence-Driven Inference Policy, Export Verification, Router & API Integration, and Evaluation Integrity."""
from __future__ import annotations

import threading
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.api.garment_identification_routes import MULTIVIEW_SPECS_STORE
from backend.app.services.ai.contracts import (
    CanonicalGarmentSpecificationV2,
    ComponentAnalysisBundle,
    ComponentEvidenceStatus,
    ComponentHandoffContract,
    ComponentHandoffDecisionItem,
    DetectionState,
    FusedComponentAssessment,
    GarmentItemEvidence,
    GarmentStructureGraphContract,
    ImageEvidenceRecord,
    ReconstructionDecision,
    UncertaintyBreakdown,
    VisibilityState,
)
from backend.app.services.garments.evaluation.pattern_evaluator import pattern_evaluator
from backend.app.services.garments.reconstruction.engine_registry import reconstruction_registry
from backend.app.services.garments.reconstruction.pattern_exporter import (
    export_pattern_dxf,
    export_pattern_json,
    export_pattern_svg,
    verify_dxf_entities,
    verify_svg_xml,
)
from backend.app.services.garments.reconstruction.pattern_geometry import (
    CONSTRUCTION_SCHEMA_VERSION,
    AssemblyValidationReport,
    ConstructionToGeometryHandoff,
    ConstructionVerificationState,
    EdgeRole,
    Point2DPattern,
    SeamConnection,
    compute_seam_allowance_polygon,
    validate_polygon_2d,
)
from backend.app.services.garments.reconstruction.universal_construction_graph import (
    UniversalConstructionGraph,
)
from backend.app.services.intelligence.capability_registry import garment_capabilities, State
from backend.app.services.intelligence.garment_adapters import create_garment_router
from backend.app.services.intelligence.garment_execution import ExecutionContext
from backend.app.services.intelligence.pattern_construction_engine import (
    AssemblyValidator,
    pattern_construction_engine,
)


def _make_bundle(
    garment_id: str,
    category: str,
    subcategory: str = "",
    *,
    views: tuple[str, ...] = ("front",),
    components: tuple[tuple[str, str, float], ...] = (),
) -> tuple[CanonicalGarmentSpecificationV2, ComponentAnalysisBundle]:
    view_records = [
        ImageEvidenceRecord(
            image_id=f"img_{v}",
            image_hash=f"sha256_{garment_id}_{v}",
            view_type=v,
            view_confidence=0.95,
        )
        for v in views
    ]
    spec = CanonicalGarmentSpecificationV2(
        garment_id=garment_id,
        views=view_records,
        garment=GarmentItemEvidence(
            category=category,
            subcategory=subcategory or category,
            confidence=0.90,
        ),
    )
    fused: dict[str, FusedComponentAssessment] = {}
    handoff_items: dict[str, ComponentHandoffDecisionItem] = {}
    safe_list: list[str] = []
    expanded: list[tuple[str, str, float]] = []
    for comp_type, vtype, conf in components:
        if comp_type == "sleeve":
            expanded.extend([("left_sleeve", vtype, conf), ("right_sleeve", vtype, conf)])
        else:
            expanded.append((comp_type, vtype, conf))

    for idx, (comp_type, vtype, conf) in enumerate(expanded):
        cid = f"{comp_type}_{idx}"
        fused[comp_type] = FusedComponentAssessment(
            component_id=cid,
            component_type=comp_type,
            garment_category=category,
            garment_subcategory=subcategory or category,
            detection_state=DetectionState.DETECTED,
            evidence_status=ComponentEvidenceStatus.OBSERVED,
            visibility_by_view={vtype: VisibilityState.FULLY_VISIBLE},
            best_visibility=VisibilityState.FULLY_VISIBLE,
            confidence=conf,
            calibrated_probability=conf,
            uncertainty=UncertaintyBreakdown(
                total_uncertainty=round(1.0 - conf, 4),
                epistemic_uncertainty=0.1,
                aleatoric_uncertainty=round(1.0 - conf, 4),
                evidence_completeness=1.0,
            ),
            evidence_completeness=1.0,
            source_image_ids=[f"img_{vtype}"],
            source_image_hashes=[f"sha256_{garment_id}_{vtype}"],
            source_views=[vtype],
            downstream_decision=ReconstructionDecision.SAFE_TO_USE,
        )
        handoff_items[comp_type] = ComponentHandoffDecisionItem(
            component_id=cid,
            component_type=comp_type,
            decision=ReconstructionDecision.SAFE_TO_USE,
            evidence_status=ComponentEvidenceStatus.OBSERVED,
            visibility_state=VisibilityState.FULLY_VISIBLE,
            detection_state=DetectionState.DETECTED,
            confidence=conf,
            uncertainty=round(1.0 - conf, 4),
            evidence_completeness=1.0,
            source_image_ids=[f"img_{vtype}"],
        )
        safe_list.append(comp_type)

    bundle = ComponentAnalysisBundle(
        garment_id=garment_id,
        category=category,
        subcategory=subcategory or category,
        views_analyzed=view_records,
        fused_components=fused,
        structure_graph=GarmentStructureGraphContract(
            garment_id=garment_id,
            category=category,
            subcategory=subcategory or category,
        ),
        handoff=ComponentHandoffContract(
            garment_id=garment_id,
            category=category,
            subcategory=subcategory or category,
            components=handoff_items,
            safe_components=safe_list,
        ),
    )
    return spec, bundle


@pytest.mark.parametrize(
    "category,subcategory,expected_min_pieces",
    [
        ("jacket", "denim_jacket", 5),
        ("hoodie", "pullover_hoodie", 7),
        ("hoodie", "zip_hoodie", 7),
        ("shirt", "casual_shirt", 6),
        ("tops", "t_shirt", 4),
        ("bottoms", "straight_fit_jeans", 6),
        ("bottoms", "shorts", 6),
        ("dress", "a_line_dress", 5),
        ("skirt", "pleated_skirt", 3),
        ("traditional", "kurta", 4),
        ("traditional", "lehenga", 3),
        ("traditional", "sherwani", 6),
    ],
)
def test_all_categories_produce_valid_ccw_patterns_and_compatible_handoffs(category, subcategory, expected_min_pieces):
    spec, bundle = _make_bundle(
        f"g_{category}_{subcategory}",
        category,
        subcategory,
        views=("front", "back"),
        components=(
            ("sleeve", "front", 0.88),
            ("collar", "front", 0.86),
        ),
    )
    handoff = pattern_construction_engine.build_construction(
        f"g_{category}_{subcategory}",
        category,
        subcategory=subcategory,
        component_bundle=bundle,
        specification=spec,
    )
    assert isinstance(handoff, ConstructionToGeometryHandoff)
    graph = handoff.construction_graph
    assert graph.schema_version == CONSTRUCTION_SCHEMA_VERSION
    assert len(graph.pieces) >= expected_min_pieces
    assert len(graph.seams) >= 2
    assert graph.validation_report is not None
    assert graph.validation_report.is_valid, f"Validation issues for {category}/{subcategory}: {graph.validation_report.issues}"
    assert not graph.validation_report.has_cycles

    for pid, piece in graph.pieces.items():
        issues = validate_polygon_2d(piece.boundary_polygon, piece.edges)
        assert not issues, f"{pid} polygon issues: {issues}"
        assert piece.area_m2 > 0.001
        assert piece.perimeter_m > 0.05
        assert piece.grainline is not None
        assert len(piece.edges) >= 3
        sa_poly = compute_seam_allowance_polygon(piece.boundary_polygon, piece.seam_allowance_m)
        assert len(sa_poly) == len(piece.boundary_polygon)

    compat = reconstruction_registry.validate_construction_handoff(handoff)
    assert compat["compatible"] is True
    assert compat["engine_match"] is True


def test_hoodie_zip_vs_pullover_and_dress_darts_and_kurta_slits():
    spec_zip, bundle_zip = _make_bundle(
        "g_zip_hoodie", "hoodie", "zip_hoodie",
        views=("front", "back"),
        components=(
            ("hood", "front", 0.91),
            ("zipper", "front", 0.90),
            ("kangaroo_pocket", "front", 0.87),
        ),
    )
    zip_h = pattern_construction_engine.build_construction(
        "g_zip_hoodie", "hoodie", subcategory="zip_hoodie",
        component_bundle=bundle_zip, specification=spec_zip,
    )
    zip_graph = zip_h.construction_graph
    assert any(s.seam_type == EdgeRole.ZIPPER_ATTACHMENT for s in zip_graph.seams)
    assert "front_left_body" in zip_graph.pieces and "front_right_body" in zip_graph.pieces

    dress_h = pattern_construction_engine.build_construction("g_dress", "dress", subcategory="a_line_dress")
    bodice = dress_h.construction_graph.pieces["bodice_front"]
    assert len(bodice.darts) >= 1
    assert all(d.depth_m > 0.0 for d in bodice.darts)

    kurta_h = pattern_construction_engine.build_construction("g_kurta", "traditional", subcategory="kurta")
    kurta_front = kurta_h.construction_graph.pieces["front_body"]
    assert any(e.edge_id == "side_slit_left" and e.role == EdgeRole.HEMMED for e in kurta_front.edges)
    assert any(e.bezier is not None for e in kurta_front.edges)


def test_evidence_isolation_front_only_never_marks_back_observed():
    spec, bundle = _make_bundle(
        "g_front_only_jacket",
        "jacket",
        "denim_jacket",
        views=("front",),
        components=(
            ("front_body", "front", 0.93),
            ("collar", "front", 0.90),
            ("sleeve", "front", 0.88),
        ),
    )
    handoff = pattern_construction_engine.build_construction(
        "g_front_only_jacket", "jacket", "denim_jacket",
        component_bundle=bundle, specification=spec,
    )
    graph = handoff.construction_graph
    back_piece = graph.pieces["back_body"]
    assert back_piece.verification_state != ConstructionVerificationState.OBSERVED
    assert back_piece.verification_state in (
        ConstructionVerificationState.INFERRED,
        ConstructionVerificationState.UNSUPPORTED,
    )
    front_piece = graph.pieces["front_left_body"]
    assert front_piece.verification_state == ConstructionVerificationState.OBSERVED
    assert len(handoff.missing_or_ambiguous_features) >= 1 or len(handoff.inferred_features) >= 1
    for rec in graph.inference_records:
        if "back" in rec.construction_feature:
            assert rec.verification_state != ConstructionVerificationState.OBSERVED


def test_polygon_validation_rejects_bowtie_cw_and_duplicates():
    cw_poly = [
        Point2DPattern(x=0.0, y=0.0),
        Point2DPattern(x=0.0, y=1.0),
        Point2DPattern(x=1.0, y=1.0),
        Point2DPattern(x=1.0, y=0.0),
    ]
    issues_cw = validate_polygon_2d(cw_poly)
    assert any("counter-clockwise" in msg.lower() for msg in issues_cw)

    bowtie = [
        Point2DPattern(x=0.0, y=0.0),
        Point2DPattern(x=1.0, y=1.0),
        Point2DPattern(x=1.0, y=0.0),
        Point2DPattern(x=0.0, y=1.0),
    ]
    issues_bow = validate_polygon_2d(bowtie)
    assert any("self-intersect" in msg.lower() for msg in issues_bow)

    dup_poly = [
        Point2DPattern(x=0.0, y=0.0),
        Point2DPattern(x=0.0, y=0.0),
        Point2DPattern(x=1.0, y=0.0),
        Point2DPattern(x=0.0, y=1.0),
    ]
    issues_dup = validate_polygon_2d(dup_poly)
    assert any("duplicate" in msg.lower() or "degenerate" in msg.lower() for msg in issues_dup)


def test_assembly_validator_detects_mismatches_cycles_and_missing_endpoints():
    handoff = pattern_construction_engine.build_construction("g_shirt_err", "shirt", "casual_shirt")
    graph = handoff.construction_graph.model_copy(deep=True)

    graph.seams.append(
        SeamConnection(
            seam_id="bad_mismatch_seam",
            piece_a="front_left_body",
            edge_a="side_seam",
            piece_b="back_body",
            edge_b="side_left",
            seam_type=EdgeRole.SEWN,
            edge_a_length_m=0.45,
            edge_b_length_m=0.62,
            length_m=0.45,
        )
    )
    graph.seams.append(
        SeamConnection(
            seam_id="missing_edge_seam",
            piece_a="front_left_body",
            edge_a="nonexistent_edge",
            piece_b="back_body",
            edge_b="side_right",
            seam_type=EdgeRole.SEWN,
            edge_a_length_m=0.40,
            edge_b_length_m=0.40,
            length_m=0.40,
        )
    )
    graph.assembly_dependencies.append(("left_sleeve", "front_left_body"))

    report: AssemblyValidationReport = AssemblyValidator.validate(graph, length_tolerance_m=0.03)
    assert not report.is_valid
    assert report.has_cycles
    codes = {iss.code for iss in report.issues}
    assert "SEAM_LENGTH_MISMATCH" in codes
    assert "MISSING_SEAM_EDGE" in codes
    assert "ASSEMBLY_GRAPH_CYCLE" in codes


def test_exports_svg_dxf_json_and_universal_graph_bridge():
    handoff = pattern_construction_engine.build_construction("g_jacket_exp", "jacket", "denim_jacket")
    js = export_pattern_json(handoff)
    assert '"schema_version": "16.2.0"' in js

    svg = export_pattern_svg(handoff)
    svg_info = verify_svg_xml(svg)
    assert svg_info["valid_xml"] is True
    assert svg_info["piece_groups"] == len(handoff.construction_graph.pieces)

    dxf = export_pattern_dxf(handoff)
    dxf_info = verify_dxf_entities(dxf)
    assert dxf_info["valid_dxf"] is True
    assert dxf_info["polylines"] == len(handoff.construction_graph.pieces) * 2

    ugraph = UniversalConstructionGraph.from_unified_contract(handoff.construction_graph)
    assert len(ugraph.nodes) == len(handoff.construction_graph.pieces)
    assert len(ugraph.seams) == len(handoff.construction_graph.seams)


@pytest.mark.asyncio
async def test_garment_router_executes_and_cancels_phase_16_2_capabilities():
    assert garment_capabilities.get("structure.construct").availability == State.VERIFIED
    assert garment_capabilities.get("pattern.interpret").availability == State.VERIFIED

    noop = lambda *a, **k: None
    router = create_garment_router(noop, noop, noop, noop, noop, noop)
    ctx = ExecutionContext("user_16_2", "sess_16_2", "req_16_2")
    handoff = await router.execute(ctx, "pattern.interpret", "g_router_1", "hoodie", "pullover_hoodie")
    assert isinstance(handoff, ConstructionToGeometryHandoff)
    assert handoff.construction_graph.category == "hoodie"
    assert any(op["capability_id"] == "pattern.interpret" for op in ctx.operations)

    ev = threading.Event()
    ev.set()
    with pytest.raises((TimeoutError, RuntimeError), match="cancelled"):
        pattern_construction_engine.build_construction(
            "g_cancel", "shirt", "casual_shirt", cancel_event=ev,
        )


def test_api_construction_plan_endpoint_and_evaluator_fail_closed():
    spec, _ = _make_bundle("g_api_01", "hoodie", "zip_hoodie", views=("front", "back"))
    MULTIVIEW_SPECS_STORE["g_api_01"] = ("default_user", spec)
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/garments/g_api_01/construction-plan",
            data={"include_svg": "true", "include_dxf": "true", "fit": "regular"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["handoff"]["construction_graph"]["schema_version"] == CONSTRUCTION_SCHEMA_VERSION
        assert data["registry_compatibility"]["compatible"] is True
        assert verify_svg_xml(data["svg"])["valid_xml"] is True
        assert verify_dxf_entities(data["dxf"])["valid_dxf"] is True
    finally:
        MULTIVIEW_SPECS_STORE.pop("g_api_01", None)

    empty_res = pattern_evaluator.evaluate_against_reference([], [], dataset_kind="real_holdout")
    assert empty_res["evaluation_status"] == "NOT_EVALUATED_EMPTY_DATASET"
    assert empty_res["sample_count"] == 0

    g1 = pattern_construction_engine.build_construction("g_eval_1", "jacket", "denim_jacket").construction_graph
    g2 = pattern_construction_engine.build_construction("g_eval_2", "jacket", "denim_jacket").construction_graph
    syn = pattern_evaluator.evaluate_against_reference([g1], [g2], dataset_kind="synthetic")
    assert syn["evaluation_status"] == "SYNTHETIC_SMOKE_ONLY"
    assert syn["by_category"]["jacket"]["seam_f1"] == 1.0
    assert syn["by_category"]["jacket"]["pattern_topology_validity"] == 1.0
