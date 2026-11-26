"""
YORVYN — Phase 13.2: Hybrid AI Orchestration Comprehensive Test Suite
Verifies:
1. Unified Model Registry registration, specs, SHA256 hashes, path traversal security, and health report
2. Authoritative Trimesh Mesh Validation Service (manifoldness, boundary loops, watertightness, degenerate faces, category bounds)
3. Hybrid Workload Router strict policy compliance (LOCAL_REQUIRED, CLOUD_REQUIRED, AUTO)
4. Non-repudiable feature reconciliation and provenance tracking bound to authenticated user
5. GLB Streaming Bounded Ingestion & Size Rejection (413 Payload Too Large, 400 Bad Request)
6. FastAPI Orchestration Endpoint Authentication (401 on missing, expired, anon, or malformed tokens)
"""

import io
import time
import struct
import pytest
import trimesh
import numpy as np
from jose import jwt
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.settings import settings
from backend.app.models.hybrid_ai_contracts import (
    DeviceCapabilitiesPayload,
    HybridGarmentFeaturesPayload,
    HybridProcessingRequestPayload
)
from backend.app.services.ml.model_registry import unified_model_registry
from backend.app.services.garments.mesh_validation_service import (
    mesh_validation_service,
    TRIMESH_AVAILABLE
)
from backend.app.services.orchestration.hybrid_workload_router import hybrid_workload_router

client = TestClient(app)


def _generate_test_glb_bytes() -> bytes:
    """Generates a valid manifold subdivided cylinder mesh in GLB format using Trimesh."""
    cyl = trimesh.creation.cylinder(radius=0.25, height=0.6, sections=16)
    cyl.visual = trimesh.visual.ColorVisuals(mesh=cyl, vertex_colors=[180, 150, 120, 255])
    return cyl.export(file_type="glb")


def _generate_jwt(user_id: str = "test_user_42", email: str = "user@yorvyn.ai", role: str = "authenticated", aud: str = "authenticated", expired: bool = False) -> str:
    secret = settings.supabase_jwt_secret or settings.secret_key
    now_ts = int(time.time())
    exp_ts = now_ts - 3600 if expired else now_ts + 7200
    claims = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "role": role,
        "exp": exp_ts,
        "iat": now_ts - 100
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestModelRegistry:
    def test_list_registered_models(self):
        models = unified_model_registry.list_models()
        assert len(models) >= 4
        model_ids = [m["model_id"] for m in models]
        assert "universal-garment-classifier" in model_ids
        assert "human-pose-and-landmarks" in model_ids
        assert "garment-silhouette-segmenter" in model_ids

    def test_get_specific_model_spec(self):
        spec = unified_model_registry.get_model_spec("universal-garment-classifier")
        assert spec is not None
        assert spec["target_backend"] in ("pytorch", "onnxruntime")
        assert "input_tensor" in spec
        assert "output_tensor" in spec
        assert spec["vram_required_mb"] > 0

    def test_verify_model_checksum_matches(self):
        test_data = b"YORVYN_TEST_MODEL_WEIGHTS"
        import hashlib
        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert unified_model_registry.verify_checksum(test_data, expected_hash) is True
        assert unified_model_registry.verify_checksum(test_data, "bad_hash_value") is False

    @pytest.mark.requires_local_assets
    def test_verify_real_server_checkpoints_on_disk(self):
        # 1. Universal garment classifier
        res_ugc = unified_model_registry.verify_server_checkpoint("universal-garment-classifier")
        assert res_ugc["valid"] is True
        assert res_ugc["actual_sha"] == "1cc5d8a9afddb8113ec90258d73e51f8382418f5c7e053ba037286db2a49c3fc"
        assert res_ugc["resolved_path"].endswith("/garment_classifier_v6.pt")
        # The historical deployment remains independently pinned to its own release.
        from backend.app.services.ml.model_registry import UnifiedModelRegistry
        legacy = UnifiedModelRegistry(unified_model_registry.registry_file)
        old = legacy.get_model("universal-garment-classifier")["server"]
        assert old["sha256_checksum"] == "44eacae47d318ef7c5508be776d295d71c095e9514e2a8ab5c01946e994c04b8"
        checked = legacy.verify_server_checkpoint("universal-garment-classifier")
        assert checked["valid"] == (checked.get("actual_sha") == old["sha256_checksum"])

        # 2. Human pose and landmarks
        res_pose = unified_model_registry.verify_server_checkpoint("human-pose-and-landmarks")
        assert res_pose["valid"] is True
        assert res_pose["actual_sha"] == "618e2a539fbb80f33d337b0d94f943ba47d1c00042375848ffb2f1b6d993a33b"

    def test_path_traversal_prevention(self):
        path, err = unified_model_registry.resolve_safe_path("../../../../../etc/passwd")
        assert path is None
        assert "Path traversal" in err

    @pytest.mark.requires_local_assets
    def test_registry_health_report(self):
        report = unified_model_registry.get_registry_health_report()
        expected = {m["model_id"] for m in unified_model_registry.list_models()}
        assert {"universal-garment-classifier", "feature-embedder", "garment-silhouette-segmenter",
                "human-pose-and-landmarks", "dinov2_small", "depth_anything_v2", "grounded_sam2",
                "xatlas_unwrapper"} <= expected
        assert set(report["results"]) == expected
        assert report["models_evaluated"] == len(expected) == report["models_healthy"] + report["models_unhealthy"]
        assert report["models_healthy"] >= 2
        assert report["results"]["universal-garment-classifier"]["client_status"] == "VALID_ON_DISK"


class TestMeshValidationService:
    def test_validate_valid_manifold_mesh(self):
        if not TRIMESH_AVAILABLE:
            pytest.skip("Trimesh not available in environment")

        glb_bytes = _generate_test_glb_bytes()
        report = mesh_validation_service.validate_glb_bytes(glb_bytes, category="top")

        assert report.is_valid is True
        assert report.vertex_count >= 20
        assert report.face_count >= 10
        assert report.is_watertight is True
        assert report.is_manifold is True
        assert report.non_manifold_edges_count == 0
        assert report.degenerate_faces == 0
        assert len(report.extents) == 3

    def test_validate_open_boundary_garment_mesh(self):
        if not TRIMESH_AVAILABLE:
            pytest.skip("Trimesh not available in environment")

        cyl = trimesh.creation.cylinder(radius=0.25, height=0.6, sections=16)
        # Delete end-caps to create open cuffs / collar
        mask = [True] * len(cyl.faces)
        for i, n in enumerate(cyl.face_normals):
            if abs(n[2]) > 0.9:
                mask[i] = False
        cyl.update_faces(mask)
        glb_open = cyl.export(file_type="glb")

        report = mesh_validation_service.validate_glb_bytes(glb_open, category="top")
        assert report.is_valid is True
        assert report.is_manifold is True
        assert report.is_watertight is False
        assert report.boundary_edges_count > 0

    def test_validate_deliberately_non_manifold_mesh(self):
        if not TRIMESH_AVAILABLE:
            pytest.skip("Trimesh not available in environment")

        verts = np.array([[0,0,0], [0.5,0,0], [0,0.5,0], [0,-0.5,0], [0,0,0.5], [0.5,0.5,0.5]], dtype=np.float32)
        faces = np.array([[0,1,2], [0,1,3], [0,1,4], [1,2,5], [2,4,5], [3,4,5], [0,2,5], [1,3,5], [0,3,5], [0,4,5]], dtype=np.int64)
        bad_m = trimesh.Trimesh(vertices=verts, faces=faces)
        glb_bad = bad_m.export(file_type="glb")

        report = mesh_validation_service.validate_glb_bytes(glb_bad, category="top")
        assert report.is_valid is False
        assert report.is_manifold is False
        assert report.non_manifold_edges_count > 0

    def test_anthropometric_bounding_limits(self):
        if not TRIMESH_AVAILABLE:
            pytest.skip("Trimesh not available in environment")

        # Gigantic 50-meter cylinder exceeds avatar scale
        huge_cyl = trimesh.creation.cylinder(radius=10.0, height=50.0, sections=16)
        huge_glb = huge_cyl.export(file_type="glb")

        report = mesh_validation_service.validate_glb_bytes(huge_glb, category="top")
        assert report.is_valid is False
        assert any("exceed human avatar scale limits" in iss for iss in report.issues)


class TestHybridWorkloadRouter:
    def test_plan_auto_policy_routing(self):
        plan = hybrid_workload_router.plan_workload("IMAGE_PREPROCESS", policy="AUTO")
        assert plan["selected_location"] == "CLIENT_WORKER"

        plan_rec = hybrid_workload_router.plan_workload("NEURAL_RECONSTRUCTION", policy="AUTO")
        assert plan_rec["selected_location"] == "CLOUD_GPU"

    def test_plan_local_required_strict_policy(self):
        # Workloads that cannot run locally must return POLICY_UNSATISFIED
        plan_unsat = hybrid_workload_router.plan_workload("NEURAL_RECONSTRUCTION", policy="LOCAL_REQUIRED")
        assert plan_unsat["status"] == "POLICY_UNSATISFIED"
        assert plan_unsat["selected_location"] is None
        assert plan_unsat["error_code"] == "POLICY_UNSATISFIED"

        # Workloads that can run locally must succeed on client
        plan_sat = hybrid_workload_router.plan_workload("IMAGE_PREPROCESS", policy="LOCAL_REQUIRED")
        assert plan_sat["status"] == "SUCCESS"
        assert plan_sat["selected_location"] == "CLIENT_WORKER"

    def test_plan_cloud_required_strict_policy(self):
        # Interactive cloth simulation cannot execute on cloud
        plan_sim = hybrid_workload_router.plan_workload("CLOTH_SIMULATION", policy="CLOUD_REQUIRED")
        assert plan_sim["status"] == "POLICY_UNSATISFIED"
        assert plan_sim["selected_location"] is None
        assert plan_sim["error_code"] == "POLICY_UNSATISFIED"

        # Image preprocess offloads to CLOUD_CPU
        plan_pre = hybrid_workload_router.plan_workload("IMAGE_PREPROCESS", policy="CLOUD_REQUIRED")
        assert plan_pre["status"] == "SUCCESS"
        assert plan_pre["selected_location"] == "CLOUD_CPU"

    def test_validate_and_reconcile_features_provenance(self):
        edge_pred = HybridGarmentFeaturesPayload(
            category="top",
            subcategory="hoodie",
            confidence_score=0.92,
            palette=["#2b1a11", "#150d09"],
            has_hood=True,
            has_kangaroo_pocket=True
        )
        server_pred = HybridGarmentFeaturesPayload(
            category="top",
            subcategory="hoodie",
            confidence_score=0.95,
            palette=["#2b1a11", "#150d09"],
            has_hood=True,
            has_kangaroo_pocket=True
        )
        user_corr = {"fit": "oversized"}

        prov = hybrid_workload_router.validate_and_reconcile_features(
            edge_prediction=edge_pred,
            server_prediction=server_pred,
            user_correction=user_corr,
            bandwidth_saved_bytes=14500000,
            edge_latency_ms=18.5,
            cloud_latency_ms=42.0
        )

        assert prov.original_ai_prediction.category == "top"
        assert prov.original_ai_prediction.subcategory == "hoodie"
        assert prov.final_authoritative_features.fit == "oversized"
        assert prov.bandwidth_saved_bytes == 14500000


class TestFastAPIOrchestrationRoutesAndSecurity:
    def test_orchestration_health_public(self):
        response = client.get("/api/fashion/orchestration/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "server_acceleration" in data
        assert "max_upload_bytes" in data

    def test_orchestration_unauthenticated_requests_strictly_rejected(self):
        # 1. /plan without token -> 401
        res1 = client.post("/api/fashion/orchestration/plan", params={"workload_type": "IMAGE_PREPROCESS"})
        assert res1.status_code == 401

        # 2. /models without token -> 401
        res2 = client.get("/api/fashion/orchestration/models")
        assert res2.status_code == 401

        # 3. /validate-mesh without token -> 401
        res3 = client.post("/api/fashion/orchestration/validate-mesh")
        assert res3.status_code == 401

        # 4. /reconcile-provenance without token -> 401
        res4 = client.post("/api/fashion/orchestration/reconcile-provenance", json={})
        assert res4.status_code == 401

    def test_orchestration_invalid_tokens_rejected(self):
        # Expired token -> 401
        expired_token = _generate_jwt(expired=True)
        res_exp = client.get("/api/fashion/orchestration/models", headers=_auth_header(expired_token))
        assert res_exp.status_code == 401

        # Malformed token -> 401
        res_mal = client.get("/api/fashion/orchestration/models", headers=_auth_header("invalid.jwt.token"))
        assert res_mal.status_code == 401

        # Supabase anonymous token -> 401
        anon_token = _generate_jwt(role="anon", aud="anon")
        res_anon = client.get("/api/fashion/orchestration/models", headers=_auth_header(anon_token))
        assert res_anon.status_code == 401
        assert "Anonymous tokens cannot access protected" in res_anon.json()["detail"]

    def test_orchestration_authenticated_endpoints_succeed(self):
        token = _generate_jwt(user_id="user_prod_99")
        auth = _auth_header(token)

        # 1. /models
        res_m = client.get("/api/fashion/orchestration/models", headers=auth)
        assert res_m.status_code == 200
        assert res_m.json()["status"] == "success"

        # 2. /plan
        res_p = client.post("/api/fashion/orchestration/plan", params={"workload_type": "IMAGE_PREPROCESS"}, headers=auth)
        assert res_p.status_code == 200
        assert res_p.json()["selected_location"] == "CLIENT_WORKER"

        # 3. /validate-mesh with valid GLB
        glb_bytes = _generate_test_glb_bytes()
        res_v = client.post(
            "/api/fashion/orchestration/validate-mesh",
            files={"file": ("test_mesh.glb", glb_bytes, "model/gltf-binary")},
            data={"category": "top"},
            headers=auth
        )
        assert res_v.status_code == 200
        assert res_v.json()["status"] == "success"

        # 4. /reconcile-provenance
        payload = {
            "edge_prediction": {"category": "top", "subcategory": "hoodie", "confidence_score": 0.91},
            "server_prediction": {"category": "top", "subcategory": "hoodie", "confidence_score": 0.94},
            "user_correction": {"fit": "oversized"},
            "bandwidth_saved_bytes": 12500000,
            "edge_latency_ms": 15.0,
            "cloud_latency_ms": 38.0
        }
        res_r = client.post("/api/fashion/orchestration/reconcile-provenance", json=payload, headers=auth)
        assert res_r.status_code == 200
        assert res_r.json()["provenance"]["user_id"] == "user_prod_99"

    def test_glb_streaming_size_limit_rejection(self):
        token = _generate_jwt()
        auth = _auth_header(token)

        # 1. Oversized Content-Length header -> 413 immediately
        huge_headers = dict(auth)
        huge_headers["Content-Length"] = str(60 * 1024 * 1024) # 60 MB
        res_cl = client.post(
            "/api/fashion/orchestration/validate-mesh",
            files={"file": ("test.glb", b"glTF" + b"\x00" * 100, "model/gltf-binary")},
            headers=huge_headers
        )
        assert res_cl.status_code == 413
        assert "Payload Too Large" in res_cl.json()["detail"]

    def test_glb_malformed_header_rejection(self):
        token = _generate_jwt()
        auth = _auth_header(token)

        # 1. Bad magic -> 400
        bad_magic_glb = b"NOT_GLTF_HEADER_BYTE" + b"\x00" * 50
        res_bad = client.post(
            "/api/fashion/orchestration/validate-mesh",
            files={"file": ("bad.glb", bad_magic_glb, "model/gltf-binary")},
            headers=auth
        )
        assert res_bad.status_code == 400
        assert "Malformed GLB" in res_bad.json()["detail"]

        # 2. Too short -> 400
        res_short = client.post(
            "/api/fashion/orchestration/validate-mesh",
            files={"file": ("short.glb", b"short", "model/gltf-binary")},
            headers=auth
        )
        assert res_short.status_code == 400
        assert "Malformed GLB" in res_short.json()["detail"]

    def test_cross_user_provenance_rejected(self):
        token = _generate_jwt(user_id="user_owner_1")
        auth = _auth_header(token)

        payload = {
            "user_id": "attacker_user_2",
            "edge_prediction": {"category": "top", "subcategory": "hoodie", "confidence_score": 0.91},
            "server_prediction": {"category": "top", "subcategory": "hoodie", "confidence_score": 0.94},
            "bandwidth_saved_bytes": 1000,
            "edge_latency_ms": 15.0,
            "cloud_latency_ms": 38.0
        }
        res = client.post("/api/fashion/orchestration/reconcile-provenance", json=payload, headers=auth)
        assert res.status_code == 403
        assert "Cross-user provenance rejected" in res.json()["detail"]

    def test_per_user_rate_limit_enforced(self):
        token = _generate_jwt(user_id="rate_limited_user")
        auth = _auth_header(token)

        # Fire 60 requests to saturate quota
        for _ in range(60):
            res = client.get("/api/fashion/orchestration/models", headers=auth)
            assert res.status_code == 200

        # 61st request must trigger 429
        res_exceeded = client.get("/api/fashion/orchestration/models", headers=auth)
        assert res_exceeded.status_code == 429
        assert "Rate limit exceeded" in res_exceeded.json()["detail"]
