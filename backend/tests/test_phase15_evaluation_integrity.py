import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.services.ai.evaluation.component_evaluator import ComponentEvaluator
from backend.app.services.garments.evaluation.ground_truth_evaluator import GarmentGroundTruthEvaluator
from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from backend.app.services.garments import mesh_validation_service


def test_component_evaluator_rejects_sample_count_mismatch():
    evaluator = ComponentEvaluator()
    with pytest.raises(ValueError, match="sample counts must match"):
        evaluator.evaluate_component_detections(
            [{"hood": {"present": True}}],
            [],
        )


def test_component_evaluator_marks_empty_data_not_evaluated():
    result = ComponentEvaluator().evaluate_component_detections([], [])
    assert result["evaluation_status"] == "NOT_EVALUATED_EMPTY_DATASET"
    assert result["sample_count"] == 0
    assert result["components"] == {}


def _mesh(points):
    points = np.asarray(points, dtype=np.float32)
    return GarmentMesh(
        positions=points,
        normals=np.tile(np.array([[0, 0, 1]], dtype=np.float32), (len(points), 1)),
        uvs=np.zeros((len(points), 2), dtype=np.float32),
        indices=np.array([[0, 1, 2]], dtype=np.uint32),
    )


def test_chamfer_uses_supplied_reference_and_is_symmetric():
    reference = _mesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
    identical = GarmentGroundTruthEvaluator._compute_chamfer_and_fscores(
        reference.positions, reference.positions.copy()
    )
    assert identical[0] == 0
    assert identical[1:] == (1.0, 1.0, 1.0)

    shifted = reference.positions + np.array([0.01, 0, 0], dtype=np.float32)
    chamfer, f5, f10, f20 = GarmentGroundTruthEvaluator._compute_chamfer_and_fscores(
        shifted, reference.positions
    )
    assert chamfer == pytest.approx(0.01, abs=1e-5)
    assert f5 == 0
    assert f10 == pytest.approx(1.0)
    assert f20 == pytest.approx(1.0)


def test_silhouette_iou_requires_matching_real_masks():
    reference = np.array([[1, 1], [0, 0]], dtype=bool)
    same = reference.copy()
    assert GarmentGroundTruthEvaluator._compute_mask_iou(reference, same) == 1.0
    with pytest.raises(ValueError, match="identical dimensions"):
        GarmentGroundTruthEvaluator._compute_mask_iou(reference, np.ones((3, 3), dtype=bool))


def test_postgres_dsn_prefers_explicit_yorvyn_setting():
    from backend.app.services.garments.orchestration.unified_state_machine import resolve_postgres_dsn

    assert resolve_postgres_dsn({
        "YORVYN_PG_DSN": "postgresql://explicit/db",
        "DATABASE_URL": "postgresql://compose/db",
    }) == "postgresql://explicit/db"


def test_postgres_dsn_uses_compose_database_url_fallback():
    from backend.app.services.garments.orchestration.unified_state_machine import resolve_postgres_dsn

    assert resolve_postgres_dsn({"DATABASE_URL": "postgresql://compose/db"}) == "postgresql://compose/db"


def test_glb_validation_does_not_claim_topology_without_trimesh(monkeypatch):
    monkeypatch.setattr(mesh_validation_service, "TRIMESH_AVAILABLE", False)
    report = mesh_validation_service.MeshValidationService.validate_glb_bytes(b"glTF" + b"0" * 32)
    assert report.is_valid is False
    assert report.vertex_count == 0
    assert report.is_manifold is False
    assert "UNVERIFIED" in report.warnings[0]


def test_procedural_benchmark_manifest_is_explicitly_synthetic(tmp_path):
    from backend.app.services.garments.evaluation.real_world_benchmark import (
        YorvynSyntheticGarmentSmokeFixtures,
    )

    fixtures = YorvynSyntheticGarmentSmokeFixtures(output_dir=str(tmp_path))
    manifest_path = fixtures.export_benchmark_manifest()
    import json
    with open(manifest_path, encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    assert manifest["evaluation_status"] == "SYNTHETIC_FIXTURE_ONLY_NOT_REAL_WORLD_EVALUATION"
    assert "synthetic_smoke_fixture_manifest.json" in manifest_path


def test_empty_real_pilot_is_not_ready(tmp_path):
    import json
    from backend.app.services.garments.evaluation.dataset_manifest import GarmentEvaluationDataset

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "1.0.0", "dataset_kind": "real", "samples": []}))
    dataset = GarmentEvaluationDataset(manifest)
    report = dataset.load()
    assert report["evaluation_state"] == "REAL_DATASET_INCOMPLETE"
    assert report["verified_samples"] == 0
    assert dataset.evaluation_gate("geometry")["allowed"] is False


def test_dataset_loader_verifies_assets_provenance_and_split_integrity(tmp_path):
    import hashlib
    import json
    from backend.app.services.garments.evaluation.dataset_manifest import GarmentEvaluationDataset

    from PIL import Image
    image_path = tmp_path / "front.png"
    Image.new("RGB", (8, 6), "white").save(image_path)
    image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
    sample = {
        "sample_id": "s1", "garment_identity_id": "g1", "category": "tops", "subcategory": "tshirt", "split": "holdout",
        "views": [{"view_type": "front", "image": {"path": "front.png", "sha256": image_hash}, "dimensions": {"width": 8, "height": 6}, "camera": None}],
        "reference_geometry": {"asset": {"path": "front.png", "sha256": image_hash}},
        "reference_masks": [{"view_type": "front", "asset": {"path": "front.png", "sha256": image_hash}}],
        "annotations": {"status": "complete", "annotation_owner": "annotator-1", "provenance": "annotation-record-1", "landmarks": [{"name": "hem", "status": "annotated", "x": 0.5, "y": 0.9}], "components": [{"name": "body", "status": "observed", "present": True}]},
        "provenance": {"license": {"license_id": "CC0", "source_url": "https://example.org/source", "evaluation_allowed": True, "redistribution_allowed": True, "attribution_required": False, "restrictions": []}, "consent": {"evidence_id": "consent-1", "evaluation_allowed": True}},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": "1.0.0", "dataset_kind": "real", "samples": [sample]}))
    loader = GarmentEvaluationDataset(manifest_path)
    report = loader.load()
    assert report["evaluation_state"] == "READY_FOR_REAL_EVALUATION"
    assert loader.evaluation_gate("geometry")["allowed"] is True
    assert loader.evaluation_gate("silhouette")["allowed"] is True

    sample2 = dict(sample, sample_id="s2", split="training")
    manifest_path.write_text(json.dumps({"schema_version": "1.0.0", "dataset_kind": "real", "samples": [sample, sample2]}))
    report = GarmentEvaluationDataset(manifest_path).load()
    assert report["evaluation_state"] == "REAL_DATASET_INCOMPLETE"
    assert "garment_identity_cross_split_leakage" in report["failures"]


def test_dataset_loader_rejects_bad_hash_and_missing_provenance(tmp_path):
    import json
    from backend.app.services.garments.evaluation.dataset_manifest import GarmentEvaluationDataset

    manifest_path = tmp_path / "manifest.json"
    sample = {"sample_id": "s1", "garment_identity_id": "g1", "split": "holdout", "views": [{"view_type": "front", "image": {"path": "missing.png", "sha256": "0" * 64}}], "annotations": {"status": "complete", "landmarks": [1], "components": [1]}, "provenance": {}}
    manifest_path.write_text(json.dumps({"schema_version": "1.0.0", "dataset_kind": "real", "samples": [sample]}))
    report = GarmentEvaluationDataset(manifest_path).load()
    assert report["evaluation_state"] == "REAL_DATASET_INCOMPLETE"
    assert report["rejected_samples"] == 1
    assert any("license_provenance_invalid" in failure for failure in report["failures"])


def test_deterministic_splits_are_stable_and_identity_based():
    from backend.app.services.garments.evaluation.dataset_manifest import deterministic_identity_splits

    first = deterministic_identity_splits(["g1", "g2", "g3"], seed="fixed")
    second = deterministic_identity_splits(["g3", "g1", "g2"], seed="fixed")
    assert first == second
    assert set(first) == {"g1", "g2", "g3"}


def test_synthetic_manifest_cannot_enter_real_evaluation(tmp_path):
    import json
    from backend.app.services.garments.evaluation.dataset_manifest import GarmentEvaluationDataset

    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps({"schema_version": "1.0.0", "dataset_kind": "synthetic", "samples": [{"sample_id": "x"}]}))
    loader = GarmentEvaluationDataset(path)
    assert loader.load()["evaluation_state"] == "SYNTHETIC_SMOKE_ONLY"
    assert loader.evaluation_gate("geometry")["allowed"] is False


def test_surface_geometry_metrics_are_area_sampled_reproducible_and_translation_sensitive():
    from backend.app.services.garments.evaluation.geometric_evaluator import GeometricEvaluator

    mesh = _mesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
    contract = {"units": "m", "coordinate_system": "YORVYN_RH_RIGHT_HANDED"}
    kwargs = dict(sample_count=1000, seed=7, coordinate_contract=contract)
    identical = GeometricEvaluator.evaluate_surfaces(mesh, mesh, **kwargs)
    repeated = GeometricEvaluator.evaluate_surfaces(mesh, mesh, **kwargs)
    assert identical["status"] == "SYNTHETIC_SMOKE_ONLY"
    assert identical["sampling"]["method"] == "area_weighted_triangle_surface_barycentric"
    assert identical["chamfer"] == repeated["chamfer"]
    assert identical["chamfer"]["symmetric_mean_m"] == pytest.approx(0.0, abs=1e-8)

    shifted = _mesh(np.asarray(mesh.positions) + np.array([0.1, 0, 0]))
    result = GeometricEvaluator.evaluate_surfaces(shifted, mesh, **kwargs)
    assert result["chamfer"]["symmetric_mean_m"] > 0
    assert result["surface_distance"]["p95_m"] > 0


def test_surface_eval_requires_coordinate_contract_and_real_gate():
    from backend.app.services.garments.evaluation.geometric_evaluator import GeometricEvaluator

    mesh = _mesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
    assert GeometricEvaluator.evaluate_surfaces(mesh, mesh)["status"] == "NOT_EVALUATED"
    denied = GeometricEvaluator.evaluate_surfaces(
        mesh, mesh, coordinate_contract={"units": "m", "coordinate_system": "world"},
        evaluation_context={"allowed": False, "evaluation_state": "REAL_DATASET_INCOMPLETE"},
    )
    assert denied["status"] == "REAL_DATASET_INCOMPLETE"


def test_silhouette_reports_shape_and_reference_metrics_without_inventing_masks():
    from backend.app.services.garments.evaluation.geometric_evaluator import GeometricEvaluator

    ref = np.zeros((8, 8), dtype=bool)
    ref[2:6, 2:6] = True
    same = GeometricEvaluator.evaluate_silhouette(ref, ref.copy())
    assert same["status"] == "SYNTHETIC_SMOKE_ONLY"
    assert same["iou"] == 1.0 and same["dice"] == 1.0
    invalid = GeometricEvaluator.evaluate_silhouette(ref, np.zeros((4, 4), dtype=bool))
    assert invalid["status"] == "NOT_EVALUATED"


def test_landmark_error_and_camera_projection_require_valid_inputs():
    from backend.app.services.garments.evaluation.geometric_evaluator import GeometricEvaluator

    lm = GeometricEvaluator.evaluate_landmarks({"hem": [0, 0, 0], "shoulder": [1, 0, 0]}, {"hem": [0.1, 0, 0]}, normalization_scale=2)
    assert lm["mean_error_m"] == pytest.approx(0.1)
    assert lm["missing_landmark_rate"] == pytest.approx(0.5)
    camera = GeometricEvaluator.project_points(
        np.array([[0, 0, 2.0]]), np.eye(3), np.hstack([np.eye(3), np.zeros((3, 1))]), (640, 480)
    )
    assert camera["pixels"] == [[0.0, 0.0]]
    invalid = GeometricEvaluator.project_points(np.zeros((1, 3)), np.eye(3), np.zeros((3, 4)), (640, 480))
    assert invalid["status"] == "NOT_EVALUATED"


def _spec_with_component(status, value=True):
    from backend.app.services.ai.base import EvidenceStatus
    from backend.app.services.ai.contracts import (
        CanonicalGarmentSpecificationV2,
        GarmentItemEvidence,
        ImageEvidenceRecord,
        MultiViewComponentDetail,
        PropertyEvidence,
    )

    image_id = "front-image"
    return CanonicalGarmentSpecificationV2(
        garment_id="garment-evidence-test",
        garment=GarmentItemEvidence(category="hoodie", subcategory="hoodie", confidence=0.7),
        views=[ImageEvidenceRecord(image_id=image_id, image_hash="a" * 64, view_type="front")],
        v2_components={
            "hood": MultiViewComponentDetail(
                name="hood",
                presence=PropertyEvidence(
                    value=value,
                    status=status,
                    confidence=0.8 if status != EvidenceStatus.UNKNOWN else None,
                    source_image_ids=[image_id] if status != EvidenceStatus.UNKNOWN else [],
                    justification="prior estimate" if status == EvidenceStatus.INFERRED else "",
                ),
                component_type=PropertyEvidence(
                    value="attached",
                    status=EvidenceStatus.INFERRED,
                    confidence=0.6,
                    justification="construction prior",
                ),
            )
        },
    )


class _FakeIntelligence:
    def __init__(self):
        self.components = []
        self.model_provenance = {}

    def model_copy(self, deep=True):
        clone = _FakeIntelligence()
        clone.components = list(self.components)
        clone.model_provenance = dict(self.model_provenance)
        return clone


def test_reconstruction_adapter_only_promotes_cited_observed_presence():
    from backend.app.services.ai.base import EvidenceStatus
    from backend.app.services.garments.reconstruction.evidence_adapter import apply_observed_components

    adapted = apply_observed_components(_FakeIntelligence(), _spec_with_component(EvidenceStatus.OBSERVED))
    assert len(adapted.components) == 1
    assert adapted.components[0].component_type == "hood"
    assert adapted.components[0].status == "detected"
    assert adapted.components[0].provenance == "observed"
    assert adapted.model_provenance["canonical_v2_observed_components"] == "hood"

    inferred = apply_observed_components(_FakeIntelligence(), _spec_with_component(EvidenceStatus.INFERRED))
    assert inferred.components == []
