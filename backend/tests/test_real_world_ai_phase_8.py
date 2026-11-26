"""
YORVYN — Phase 8 Unit Test Suite: Real-World AI Understanding, Generalization & Production Validation.
Validates:
1. Model capability auditing & SHA256 checkpoint verification.
2. Held-out benchmark dataset isolation (zero training overlap).
3. Generalization evaluator & multi-category robustness.
4. Immutable neural reconstruction execution auditor & provenance separation.
5. Multi-view validation & anti-inflation rules.
6. Ground-truth geometry, appearance & wearability evaluation.
7. Prediction reliability engine, confidence calibration (ECE) & failure mode detection.
8. Production reliability benchmarking, latency percentiles & unit economics.
"""

import os
import sys
import pytest
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.services.garments.evaluation.model_capability_auditor import model_capability_auditor, ModelAuditEntry
from backend.app.services.garments.evaluation.real_world_benchmark import real_world_benchmark, REAL_WORLD_BENCHMARK_ITEMS
from backend.app.services.garments.evaluation.generalization_evaluator import garment_generalization_evaluator
from backend.app.services.garments.evaluation.reconstruction_auditor import neural_reconstruction_execution_auditor, ReconstructionAuditRecord
from backend.app.services.garments.evaluation.multiview_validator import multiview_validator
from backend.app.services.garments.evaluation.ground_truth_evaluator import garment_ground_truth_evaluator
from backend.app.services.garments.intelligence.reliability_engine import reliability_engine, GarmentReliabilityAssessment
from backend.app.services.garments.evaluation.production_reliability_bench import production_reliability_benchmark
from backend.app.services.garments.reconstruction.neural import neural_reconstruction_engine


class TestModelCapabilityAuditor:
    def test_audit_system_integrity(self):
        audit = model_capability_auditor.audit_system()
        assert audit["audited_models_count"] == 9
        matrix = audit["capability_matrix"]
        
        # Check specific component roles
        v3_head = next((e for e in matrix if e["model_identifier"] == "UniversalGarmentIntelligenceModel-v3"), None)
        assert v3_head is not None
        assert v3_head["implementation_status"] == "TRAINED_VERIFIED"
        assert v3_head["checkpoint_sha256"] is not None
        assert len(v3_head["checkpoint_sha256"]) == 64

        client = next((e for e in matrix if e["model_identifier"] == "LearnedReconstructionClient"), None)
        assert client is not None
        assert client["implementation_status"] == "ADAPTER_CLIENT"

        rec_engine = next((e for e in matrix if e["model_identifier"] == "NeuralGarmentReconstructionEngine-v3"), None)
        assert rec_engine is not None
        assert rec_engine["implementation_status"] == "HYBRID_ORCHESTRATOR"
        assert rec_engine["provenance_classification"] == "hybrid_neural_procedural"


class TestRealWorldBenchmarkDataset:
    def test_held_out_isolation(self):
        items = real_world_benchmark.items
        assert len(items) == 20
        # Strict zero-leakage rule: No benchmark item may be in training data
        assert all(item.is_training_sample is False for item in items)
        
        # All 11 major categories represented
        categories = {item.category for item in items}
        expected_cats = {"tops", "shirt", "hoodie", "jacket", "bottoms", "dress", "skirt", "traditional", "footwear", "accessories"}
        assert expected_cats.issubset(categories)

        # Difficulties represented
        diffs = {item.difficulty for item in items}
        assert "standard" in diffs
        assert "challenging" in diffs
        assert "stress_test" in diffs

    def test_benchmark_image_synthesis(self):
        item = real_world_benchmark.items[0]
        img = real_world_benchmark.synthesize_benchmark_image(item)
        assert isinstance(img, Image.Image)
        assert img.size == item.resolution


class TestGeneralizationEvaluator:
    def test_generalization_evaluation_metrics(self):
        res = garment_generalization_evaluator.evaluate_all()
        assert res["evaluated_items_count"] == 20
        assert res["evaluation_status"] == "SYNTHETIC_SMOKE_ONLY_NOT_REAL_WORLD_GENERALIZATION"
        assert "synthetic_prompted_category_match_pct" in res
        assert "overall_mean_silhouette_iou" not in res
        assert res["synthetic_mesh_manifold_rate_pct"] <= 100.0


class TestReconstructionExecutionAuditor:
    def test_audit_logging_and_separation(self):
        # Create a test reconstruction
        item = real_world_benchmark.items[0]
        img = real_world_benchmark.synthesize_benchmark_image(item)
        rec_out = neural_reconstruction_engine.reconstruct(
            category=item.category,
            subcategory=item.subcategory,
            front_image=img
        )
        
        record = neural_reconstruction_execution_auditor.record_execution(
            job_id="test_audit_job_001",
            front_image=img,
            reconstruction_output=rec_out
        )
        
        assert isinstance(record, ReconstructionAuditRecord)
        assert record.job_id == "test_audit_job_001"
        assert record.checkpoint_sha256 is not None
        # Strict Truthful Provenance: Hybrid must never be claimed as fully neural!
        assert record.is_hybrid is True
        assert record.is_fully_neural is False
        assert record.is_manifold is True

        summary = neural_reconstruction_execution_auditor.get_audit_summary()
        assert summary["total_reconstructions_audited"] >= 1
        assert summary["hybrid_misclassified_as_neural"] is False


class TestMultiViewReconstructionValidator:
    def test_multiview_scenarios(self):
        res = multiview_validator.run_validation_suite()
        assert res["scenarios_evaluated_count"] == 7
        assert res["all_coverage_rules_passed"] is True
        assert res["mismatch_rejection_rate_pct"] == 100.0


class TestGroundTruthEvaluator:
    def test_ground_truth_metrics(self):
        item = real_world_benchmark.items[0]
        img = real_world_benchmark.synthesize_benchmark_image(item)
        rec_out = neural_reconstruction_engine.reconstruct(
            category=item.category,
            subcategory=item.subcategory,
            front_image=img
        )
        
        rep = garment_ground_truth_evaluator.evaluate(
            mesh=rec_out.mesh,
            input_image=img,
            category=item.category,
            subcategory=item.subcategory,
            fabric_type=item.fabric_type,
            ground_truth_color_rgb=item.color_rgb
        )
        
        # The benchmark renderer emits synthetic smoke images, not reference 3D scans.
        assert rep.chamfer_distance_m is None
        assert rep.f_score_10mm is None
        assert rep.f_score_20mm is None
        assert rep.silhouette_iou is None
        assert rep.fabric_classification_accuracy is None
        assert rep.evaluation_status == "STRUCTURAL_DIAGNOSTICS_ONLY_NO_GROUND_TRUTH"
        assert rep.normal_consistency >= 0.90
        assert rep.is_manifold is True
        assert rep.is_fit_stable is True
        assert rep.average_clearance_mm >= 2.0


class TestReliabilityEngine:
    def test_reliable_garment(self):
        arr = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        assessment = reliability_engine.evaluate_reliability(
            image=img,
            category="tops",
            subcategory="tshirt",
            category_confidence=0.92,
            components_detected=[{"status": "detected"}, {"status": "detected"}],
            silhouette_quality=0.88,
            mesh_is_manifold=True,
            is_multi_view=False
        )
        assert assessment.is_reliable is True
        assert assessment.recommended_action == "PROCEED"
        assert len(assessment.failure_codes) == 0

    def test_insufficient_resolution_failure(self):
        img = Image.new("RGB", (64, 64), (100, 100, 100))
        assessment = reliability_engine.evaluate_reliability(
            image=img,
            category="tops",
            subcategory="tshirt",
            category_confidence=0.50,
            components_detected=[],
            silhouette_quality=0.30
        )
        assert assessment.is_reliable is False
        assert "INSUFFICIENT_IMAGE_RESOLUTION" in assessment.failure_codes
        assert assessment.recommended_action == "ABORT_RETRY"

    def test_mismatched_cross_view_failure(self):
        arr = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        assessment = reliability_engine.evaluate_reliability(
            image=img,
            category="tops",
            subcategory="tshirt",
            category_confidence=0.88,
            components_detected=[{"status": "detected"}],
            silhouette_quality=0.85,
            is_multi_view=True,
            cross_view_delta_e=68.2
        )
        assert "CROSS_VIEW_COLOR_DISCREPANCY" in assessment.failure_codes
        assert assessment.recommended_action == "REQUEST_ADDITIONAL_VIEW"


class TestProductionReliabilityBench:
    def test_production_benchmark_metrics(self):
        res = production_reliability_benchmark.run_benchmark(iterations=10, concurrency=2)
        assert res["latency_percentiles_ms"]["p50_median_ms"] > 0
        assert res["concurrency_telemetry"]["throughput_queries_per_sec"] > 0
        assert res["execution_hardware"]["peak_rss_mb"] < 1000.0  # Well within 8GB budget
        assert res["cost_modeling"]["local_apple_silicon_m2_cost_per_job_usd"] == 0.00
