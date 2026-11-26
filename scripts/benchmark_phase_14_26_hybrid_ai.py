#!/usr/bin/env python3
"""
YORVYN — Master Verification Benchmark Suite for Phase 14.26
Hybrid AI Provider Integration & Production Readiness
(Gemini Vision + Groq + Hugging Face + Local AI Orchestration)

Verifies across 6 rigorous suites:
- Suite 1: Provider Contract & Capability Enforcement
- Suite 2: Multi-Provider Multimodal Garment Understanding
- Suite 3: Groq Fast Reasoning & Attribute Normalization
- Suite 4: Hugging Face Model Discovery & Embeddings
- Suite 5: Capability-Aware Fallback & Graceful Degradation
- Suite 6: End-to-End API Routes & 3D Reconstruction Integration

Outputs authoritative evidence artifact:
docs/reports/PHASE_14_26_MASTER_VERIFICATION_EVIDENCE.json
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image
import numpy as np

# Ensure repository root is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.ai.base import (
    AIProvider,
    AIRequest,
    AIProviderResponse,
    ProviderCapability,
    ProviderHealth,
    ProviderError,
    EvidenceStatus,
    TaskType,
    TokenUsage,
    ModelMetadata
)
from backend.app.services.ai.contracts import (
    CanonicalGarmentSpecification,
    GarmentItemEvidence,
    ComponentDetail,
    AppearanceDetail,
    ImageQualityAssessment,
    GeometricEstimate,
    HandoffToReconstruction
)
from backend.app.services.ai.providers.gemini_provider import GeminiVisionProvider
from backend.app.services.ai.providers.groq_provider import GroqReasoningProvider
from backend.app.services.ai.providers.local_cv_provider import LocalCVProvider
from backend.app.services.ai.providers.hf_provider import HuggingFaceProvider, HF_OPEN_MODEL_REGISTRY
from backend.app.services.ai.providers.local_rules_provider import LocalRulesProvider
from backend.app.services.ai.orchestration.capability_resolver import CapabilityResolver
from backend.app.services.ai.orchestration.fallback_manager import FallbackManager
from backend.app.services.ai.orchestration.orchestrator import ai_orchestrator
from backend.app.services.ai.monitoring.usage_tracker import usage_tracker
from backend.app.services.garments.reconstruction.universal_construction_graph import UniversalConstructionGraph


def load_test_image_bytes() -> bytes:
    """Loads a real garment photograph for test suites."""
    candidate_paths = [
        REPO_ROOT / "data/datasets/garment_classification_real/real_onbody_01_isolated_hoodie.png",
        REPO_ROOT / "data/datasets/phase_13_6_real_photos/wm_00.jpg",
        REPO_ROOT / "data/datasets/garment_classification_real/real_ref_01_case_a_hoodie.png"
    ]
    for p in candidate_paths:
        if p.exists():
            with open(p, "rb") as f:
                return f.read()
    
    # Fallback to in-memory PIL image
    img = Image.new("RGB", (512, 512), (180, 50, 50))
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def run_suite_1_contract_and_capability() -> Dict[str, Any]:
    """Suite 1: Provider Contract & Capability Enforcement."""
    print("\n--- Running Suite 1: Provider Contract & Capability Enforcement ---")
    t0 = time.perf_counter()
    results = {}

    providers = {
        "gemini_vision": GeminiVisionProvider(),
        "groq_reasoning": GroqReasoningProvider(),
        "local_cv": LocalCVProvider(),
        "huggingface": HuggingFaceProvider(),
        "local_rules": LocalRulesProvider()
    }

    # 1. Health checks & availability status
    health_results = {}
    for name, p in providers.items():
        h = p.health_check()
        assert isinstance(h, ProviderHealth), f"{name} health check did not return ProviderHealth"
        caps = p.capabilities()
        assert isinstance(caps, list) and len(caps) > 0, f"{name} capabilities list is empty"
        health_results[name] = {
            "is_available": h.is_available,
            "status_message": h.status_message,
            "capabilities": [c.value for c in h.active_capabilities]
        }
    results["provider_health"] = health_results

    # 2. Strict Capability Guard: Send binary image to text-only Groq model
    groq = providers["groq_reasoning"]
    dummy_image = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # minimal jpeg header
    invalid_req = AIRequest(
        request_id="test_cap_guard_01",
        task_type=TaskType.ATTRIBUTE_NORMALIZATION,
        image_bytes=dummy_image,
        mock_mode=False
    )
    guard_resp = groq.execute(invalid_req)
    assert not guard_resp.success, "Groq text model must reject binary image bytes"
    assert guard_resp.error is not None and guard_resp.error.error_code == "UNSUPPORTED_MODALITY", (
        f"Expected UNSUPPORTED_MODALITY error, got: {guard_resp.error}"
    )
    results["groq_capability_guard"] = {
        "passed": True,
        "error_code": guard_resp.error.error_code,
        "message": guard_resp.error.message
    }

    # 3. Missing image check on Local CV
    local_cv = providers["local_cv"]
    missing_img_req = AIRequest(
        request_id="test_missing_img_01",
        task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING
    )
    missing_resp = local_cv.execute(missing_img_req)
    assert not missing_resp.success, "Local CV must fail when no image is provided"
    assert missing_resp.error is not None and missing_resp.error.error_code == "MISSING_IMAGE"
    results["local_cv_missing_image_guard"] = {
        "passed": True,
        "error_code": missing_resp.error.error_code
    }

    # 4. CapabilityResolver Task-to-Provider matching
    vision_req = AIRequest(request_id="v_req", task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING, image_bytes=dummy_image)
    eligible_vision = CapabilityResolver.filter_eligible_providers(providers, vision_req)
    assert any(p.name == "local_cv" for p in eligible_vision), "local_cv must be eligible for vision"
    assert not any(p.name == "groq_reasoning" for p in eligible_vision), "groq_reasoning must NOT be eligible for raw vision"

    text_req = AIRequest(request_id="t_req", task_type=TaskType.ATTRIBUTE_NORMALIZATION)
    eligible_text = CapabilityResolver.filter_eligible_providers(providers, text_req)
    assert any(p.name in ["groq_reasoning", "local_rules"] for p in eligible_text), "Text providers must match text reasoning"

    results["capability_resolver_routing"] = {
        "passed": True,
        "eligible_for_vision": [p.name for p in eligible_vision],
        "eligible_for_text": [p.name for p in eligible_text]
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 1 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 1: Provider Contract & Capability Enforcement",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def run_suite_2_multimodal_garment_understanding() -> Dict[str, Any]:
    """Suite 2: Multi-Provider Multimodal Garment Understanding."""
    print("\n--- Running Suite 2: Multi-Provider Multimodal Garment Understanding ---")
    t0 = time.perf_counter()
    image_bytes = load_test_image_bytes()
    results = {}

    # 1. Local CV live multimodal understanding
    local_cv = LocalCVProvider()
    req_local = AIRequest(
        request_id="suite2_local_cv_01",
        task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING,
        image_bytes=image_bytes
    )
    resp_local = local_cv.execute(req_local)
    assert resp_local.success, f"Local CV failed: {resp_local.error}"
    s_data = resp_local.structured_data
    assert "garment" in s_data, "Local CV must extract garment evidence"
    assert "components" in s_data, "Local CV must extract components"
    assert "appearance" in s_data, "Local CV must extract appearance"
    assert "orientation" in s_data, "Local CV must extract orientation"
    assert resp_local.token_usage.estimated_cost_usd == 0.0, "Local CV cost must be exactly $0.00"

    results["local_cv_real_execution"] = {
        "passed": True,
        "category": s_data["garment"]["category"],
        "subcategory": s_data["garment"]["subcategory"],
        "confidence": s_data["garment"]["confidence"],
        "components_detected": list(s_data["components"].keys()),
        "primary_color": s_data["appearance"]["primary_color"],
        "cost_usd": resp_local.token_usage.estimated_cost_usd,
        "latency_ms": resp_local.latency_ms
    }

    # 2. Gemini Vision Provider mock mode (schema & contract validation)
    gemini = GeminiVisionProvider()
    req_gemini_mock = AIRequest(
        request_id="suite2_gemini_mock_01",
        task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING,
        image_bytes=image_bytes,
        mock_mode=True
    )
    resp_gemini_mock = gemini.execute(req_gemini_mock)
    assert resp_gemini_mock.success, f"Gemini mock failed: {resp_gemini_mock.error}"
    g_data = resp_gemini_mock.structured_data
    assert g_data["garment"]["category"] in ["hoodie", "jacket", "shirt", "tshirt"], "Gemini mock category valid"
    assert "visible_evidence" in g_data, "Must contain visible evidence"
    assert "inferred_properties" in g_data, "Must contain inferred properties"
    assert "unknown_properties" in g_data, "Must contain unknown properties"

    results["gemini_mock_contract"] = {
        "passed": True,
        "category": g_data["garment"]["category"],
        "subcategory": g_data["garment"]["subcategory"],
        "visible_evidence": g_data["visible_evidence"],
        "inferred_properties": g_data["inferred_properties"],
        "unknown_properties": g_data["unknown_properties"]
    }

    # 3. Gemini Vision Provider live uncredentialed behavior (must fail gracefully)
    req_gemini_live = AIRequest(
        request_id="suite2_gemini_live_01",
        task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING,
        image_bytes=image_bytes,
        mock_mode=False
    )
    resp_gemini_live = gemini.execute(req_gemini_live)
    # When credentials are missing, it must return success=False with appropriate code
    assert not resp_gemini_live.success, "Uncredentialed Gemini call must not report success"
    assert resp_gemini_live.error is not None and resp_gemini_live.error.error_code in [
        "BLOCKED_NO_CREDENTIALS", "AUTH_REQUIRED", "AUTH_FAILED", "API_ERROR", "PERMISSION_DENIED"
    ], (
        f"Expected auth failure or blocked code, got {resp_gemini_live.error}"
    )
    results["gemini_uncredentialed_safe_block"] = {
        "passed": True,
        "error_code": resp_gemini_live.error.error_code,
        "message": resp_gemini_live.error.message
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 2 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 2: Multi-Provider Multimodal Garment Understanding",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def run_suite_3_groq_reasoning_and_normalization() -> Dict[str, Any]:
    """Suite 3: Groq Fast Reasoning & Attribute Normalization."""
    print("\n--- Running Suite 3: Groq Fast Reasoning & Attribute Normalization ---")
    t0 = time.perf_counter()
    results = {}

    groq = GroqReasoningProvider()
    local_rules = LocalRulesProvider()

    test_context = {
        "garment": {"category": "hoodie", "subcategory": "oversized_hoodie", "confidence": 0.94},
        "components": {
            "hood": {"present": True, "type": "standard", "confidence": 0.92},
            "pockets": {"present": True, "type": "kangaroo", "confidence": 0.88},
            "sleeves": {"present": True, "type": "long", "confidence": 0.95}
        },
        "appearance": {
            "primary_color": "charcoal_black",
            "pattern": "solid",
            "fabric_appearance": "cotton_fleece"
        }
    }

    # 1. Groq Mock Mode Reasoning Execution
    req_mock = AIRequest(
        request_id="suite3_groq_mock_01",
        task_type=TaskType.ATTRIBUTE_NORMALIZATION,
        structured_context=test_context,
        mock_mode=True
    )
    resp_mock = groq.execute(req_mock)
    assert resp_mock.success, f"Groq mock failed: {resp_mock.error}"
    r_data = resp_mock.structured_data
    assert r_data["category"] == "hoodie"
    assert "reconstruction_parameters" in r_data
    assert r_data["reconstruction_parameters"]["target_dag_template"] == "hoodie_construction"
    assert r_data["reconstruction_parameters"]["enable_hood_mesh"] is True
    assert "conflict_resolutions" in r_data
    assert "reasoning_summary" in r_data

    results["groq_mock_reasoning"] = {
        "passed": True,
        "category": r_data["category"],
        "dag_template": r_data["reconstruction_parameters"]["target_dag_template"],
        "token_usage": resp_mock.token_usage.model_dump(),
        "latency_ms": resp_mock.latency_ms
    }

    # 2. Local Rules Deterministic Provider (Offline Fallback for Groq)
    req_rules = AIRequest(
        request_id="suite3_rules_01",
        task_type=TaskType.ATTRIBUTE_NORMALIZATION,
        structured_context=test_context,
        mock_mode=False
    )
    resp_rules = local_rules.execute(req_rules)
    assert resp_rules.success, f"Local rules failed: {resp_rules.error}"
    rules_data = resp_rules.structured_data
    assert rules_data["category"] == "hoodie"
    assert rules_data["taxonomy_tier"] == "tops"
    assert rules_data["reconstruction_parameters"]["target_dag_template"] == "hoodie_construction"
    assert rules_data["reconstruction_parameters"]["enable_hood_mesh"] is True
    assert rules_data["reconstruction_parameters"]["material_preset"] == "cotton_fleece_pbr"
    assert resp_rules.token_usage.estimated_cost_usd == 0.0

    results["local_rules_deterministic_execution"] = {
        "passed": True,
        "category": rules_data["category"],
        "taxonomy_tier": rules_data["taxonomy_tier"],
        "target_dag": rules_data["reconstruction_parameters"]["target_dag_template"],
        "material_preset": rules_data["reconstruction_parameters"]["material_preset"],
        "latency_ms": resp_rules.latency_ms,
        "cost_usd": resp_rules.token_usage.estimated_cost_usd
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 3 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 3: Groq Fast Reasoning & Attribute Normalization",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def run_suite_4_hf_model_discovery_and_embeddings() -> Dict[str, Any]:
    """Suite 4: Hugging Face Model Discovery & Embeddings."""
    print("\n--- Running Suite 4: Hugging Face Model Discovery & Embeddings ---")
    t0 = time.perf_counter()
    results = {}

    # 1. HF Open Model Registry Audit Table
    expected_models = ["FashionCLIP", "SigLIP", "DINOv2", "Grounded-SAM2", "Depth-Anything-V2"]
    registry_audit = {}
    for m in expected_models:
        assert m in HF_OPEN_MODEL_REGISTRY, f"Missing model in registry: {m}"
        meta = HF_OPEN_MODEL_REGISTRY[m]
        assert meta["commercial_usage_permitted"] is True, f"Model {m} must permit commercial use"
        assert meta["code_license"] in ["MIT", "Apache 2.0"], f"Model {m} code license non-compliant"
        assert meta["checkpoint_license"] in ["MIT", "Apache 2.0"], f"Model {m} checkpoint license non-compliant"
        registry_audit[m] = {
            "repository": meta["repository"],
            "task": meta["task"],
            "code_license": meta["code_license"],
            "checkpoint_license": meta["checkpoint_license"],
            "commercial_usage_permitted": meta["commercial_usage_permitted"],
            "parameters": meta["parameters"],
            "memory_mb": meta["measured_memory_mb"]
        }
    results["registry_audit"] = registry_audit

    # 2. Local Visual Embedding Generation (DINOv2)
    image_bytes = load_test_image_bytes()
    hf_provider = HuggingFaceProvider()
    emb_req = AIRequest(
        request_id="suite4_hf_dinov2_01",
        task_type=TaskType.VISUAL_EMBEDDINGS,
        image_bytes=image_bytes
    )
    emb_resp = hf_provider.execute(emb_req)
    assert emb_resp.success, f"HF Visual Embedding failed: {emb_resp.error}"
    s_data = emb_resp.structured_data
    assert "embedding" in s_data, "Structured data must contain 'embedding'"
    embedding = s_data["embedding"]
    dim = len(embedding)
    assert dim == 384, f"DINOv2 embedding must be 384 dimensions, got {dim}"

    # Verify unit normalization (L2 norm ≈ 1.0)
    norm = float(np.linalg.norm(np.array(embedding)))
    assert 0.99 <= norm <= 1.01, f"Embedding must be L2 normalized, got norm {norm:.4f}"

    results["visual_embeddings"] = {
        "passed": True,
        "model_name": s_data.get("model_name", "DINOv2-Small"),
        "dimension": dim,
        "l2_norm": norm,
        "sample_preview": embedding[:5],
        "latency_ms": emb_resp.latency_ms,
        "cost_usd": emb_resp.token_usage.estimated_cost_usd
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 4 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 4: Hugging Face Model Discovery & Embeddings",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def run_suite_5_fallback_and_graceful_degradation() -> Dict[str, Any]:
    """Suite 5: Capability-Aware Fallback & Graceful Degradation."""
    print("\n--- Running Suite 5: Capability-Aware Fallback & Graceful Degradation ---")
    t0 = time.perf_counter()
    image_bytes = load_test_image_bytes()
    results = {}

    providers = {
        "gemini_vision": GeminiVisionProvider(),
        "groq_reasoning": GroqReasoningProvider(),
        "local_cv": LocalCVProvider(),
        "huggingface": HuggingFaceProvider(),
        "local_rules": LocalRulesProvider()
    }
    fallback_mgr = FallbackManager(providers)

    # 1. Vision Fallback: Request prefers Gemini, but Gemini is uncredentialed -> falls back to Local CV
    v_req = AIRequest(
        request_id="suite5_v_fallback_01",
        task_type=TaskType.GARMENT_IMAGE_UNDERSTANDING,
        image_bytes=image_bytes,
        preferred_provider="gemini_vision",
        require_vision=True,
        mock_mode=False
    )
    v_resp = fallback_mgr.execute_with_fallback(v_req)
    assert v_resp.success, f"Vision fallback failed: {v_resp.error}"
    assert v_resp.provider_name == "local_cv", f"Expected fallback to local_cv, got {v_resp.provider_name}"
    results["vision_fallback"] = {
        "passed": True,
        "preferred": "gemini_vision",
        "actual_provider": v_resp.provider_name,
        "notes": v_resp.provenance_notes
    }

    # 2. Reasoning Fallback: Request prefers Groq, but Groq is uncredentialed -> falls back to Local Rules
    r_req = AIRequest(
        request_id="suite5_r_fallback_01",
        task_type=TaskType.ATTRIBUTE_NORMALIZATION,
        structured_context=v_resp.structured_data,
        preferred_provider="groq_reasoning",
        mock_mode=False
    )
    r_resp = fallback_mgr.execute_with_fallback(r_req)
    assert r_resp.success, f"Reasoning fallback failed: {r_resp.error}"
    assert r_resp.provider_name == "local_rules", f"Expected fallback to local_rules, got {r_resp.provider_name}"
    results["reasoning_fallback"] = {
        "passed": True,
        "preferred": "groq_reasoning",
        "actual_provider": r_resp.provider_name,
        "notes": r_resp.provenance_notes
    }

    # 3. Circuit Breaker Execution
    gemini = providers["gemini_vision"]
    # Trigger 3 consecutive recorded failures to open circuit
    gemini.record_failure()
    gemini.record_failure()
    gemini.record_failure()
    assert gemini._circuit_open is True, "Circuit breaker must open after 3 consecutive failures"

    # With circuit open, health check must report CIRCUIT_OPEN
    h = gemini.health_check()
    assert h.circuit_open is True
    assert "CIRCUIT_OPEN" in h.status_message

    # Reset circuit breaker for clean slate
    gemini.record_success()
    assert gemini._circuit_open is False, "Record success must close circuit"

    results["circuit_breaker"] = {
        "passed": True,
        "tripped_after_failures": 3,
        "reset_on_success": True
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 5 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 5: Capability-Aware Fallback & Graceful Degradation",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def run_suite_6_e2e_api_and_3d_handoff() -> Dict[str, Any]:
    """Suite 6: End-to-End API Routes & 3D Reconstruction Integration."""
    print("\n--- Running Suite 6: End-to-End API Routes & 3D Reconstruction Integration ---")
    t0 = time.perf_counter()
    image_bytes = load_test_image_bytes()
    results = {}

    client = TestClient(app)

    # 1. GET /api/garments/hybrid-orchestrated-providers
    resp_providers = client.get("/api/garments/hybrid-orchestrated-providers")
    assert resp_providers.status_code == 200, f"GET providers failed: {resp_providers.text}"
    prov_data = resp_providers.json()
    assert prov_data["status"] == "active"
    assert "gemini_vision" in prov_data["providers_health"]
    assert "local_cv" in prov_data["providers_health"]
    assert "usage_and_costs" in prov_data

    results["providers_endpoint"] = {
        "passed": True,
        "status_code": resp_providers.status_code,
        "active_providers": list(prov_data["providers_health"].keys()),
        "total_requests_tracked": prov_data["usage_and_costs"].get("total_requests", 0)
    }

    # 2. POST /api/garments/hybrid-orchestrated-identify (Offline Fallback Path)
    files = {"image": ("test_hoodie.png", image_bytes, "image/png")}
    data = {"garment_id": "test_g_14_26", "mock_mode": "false"}
    resp_id = client.post("/api/garments/hybrid-orchestrated-identify", files=files, data=data)
    assert resp_id.status_code == 200, f"Identify endpoint failed: {resp_id.text}"
    spec_data = resp_id.json()

    assert spec_data["garment_id"] == "test_g_14_26"
    assert "garment" in spec_data
    assert "components" in spec_data
    assert "appearance" in spec_data
    assert "reconstruction_handoff" in spec_data
    handoff = spec_data["reconstruction_handoff"]
    assert "target_dag_template" in handoff
    assert "material_preset" in handoff

    results["identify_endpoint"] = {
        "passed": True,
        "status_code": resp_id.status_code,
        "garment_category": spec_data["garment"]["category"],
        "subcategory": spec_data["garment"]["subcategory"],
        "target_dag": handoff["target_dag_template"],
        "enable_hood_mesh": handoff["enable_hood_mesh"],
        "material_preset": handoff["material_preset"],
        "provenance": [m["provider_name"] for m in spec_data["provenance_chain"]]
    }

    # 3. POST /api/garments/hybrid-orchestrated-reconstruct
    resp_recon = client.post("/api/garments/hybrid-orchestrated-reconstruct", json=spec_data)
    assert resp_recon.status_code == 200, f"Reconstruct endpoint failed: {resp_recon.text}"
    recon_data = resp_recon.json()

    assert recon_data["status"] == "DAG_ASSEMBLED_READY_FOR_3D_SYNTHESIS"
    assert recon_data["dag_nodes_count"] > 0, "Universal Construction Graph must have assembled nodes"
    assert recon_data["dag_seams_count"] > 0, "Universal Construction Graph must have assembled seams"
    nodes = recon_data["dag_nodes"]
    seams = recon_data["dag_seams"]

    # Verify structural components
    assert any("torso" in n for n in nodes), "DAG must contain torso geometry"
    assert any("sleeve" in n for n in nodes), "DAG must contain sleeve geometry"

    results["reconstruct_endpoint"] = {
        "passed": True,
        "status_code": resp_recon.status_code,
        "status": recon_data["status"],
        "dag_nodes_count": recon_data["dag_nodes_count"],
        "dag_seams_count": recon_data["dag_seams_count"],
        "dag_nodes_sample": nodes[:8],
        "dag_seams_sample": seams[:6]
    }

    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Suite 6 Passed ({latency_ms:.2f} ms)")
    return {
        "suite_name": "Suite 6: End-to-End API Routes & 3D Reconstruction Integration",
        "passed": True,
        "latency_ms": latency_ms,
        "details": results
    }


def main():
    print("=" * 80)
    print("YORVYN — PHASE 14.26 MASTER VERIFICATION BENCHMARK SUITE")
    print("Hybrid AI Provider Integration (Gemini + Groq + HF + Local CV)")
    print("=" * 80)

    t_start = time.perf_counter()
    report: Dict[str, Any] = {
        "phase": "14.26",
        "benchmark_title": "Hybrid AI Provider Integration & Production Readiness",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "cloud_spend_mandatory": "$0.00",
            "git_baseline_commit": "7139fc7eea4e1f890e28da9140db2e8550081267"
        },
        "suites": []
    }

    suites = [
        run_suite_1_contract_and_capability,
        run_suite_2_multimodal_garment_understanding,
        run_suite_3_groq_reasoning_and_normalization,
        run_suite_4_hf_model_discovery_and_embeddings,
        run_suite_5_fallback_and_graceful_degradation,
        run_suite_6_e2e_api_and_3d_handoff
    ]

    all_passed = True
    for suite_fn in suites:
        try:
            res = suite_fn()
            report["suites"].append(res)
            if not res.get("passed", False):
                all_passed = False
        except Exception as e:
            all_passed = False
            print(f"FAILED: {suite_fn.__name__} raised: {e}")
            import traceback
            traceback.print_exc()
            report["suites"].append({
                "suite_name": suite_fn.__name__,
                "passed": False,
                "error": str(e)
            })

    total_latency = (time.perf_counter() - t_start)
    report["total_runtime_seconds"] = total_latency
    report["overall_passed"] = all_passed
    report["verdict"] = "PASS" if all_passed else "FAIL"

    # Save to docs/reports/PHASE_14_26_MASTER_VERIFICATION_EVIDENCE.json
    out_dir = REPO_ROOT / "docs" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "PHASE_14_26_MASTER_VERIFICATION_EVIDENCE.json"

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"BENCHMARK COMPLETED: {6 if all_passed else len([s for s in report['suites'] if s.get('passed')])}/6 Suites Passed")
    print(f"Total Runtime: {total_latency:.2f} seconds")
    print(f"Authoritative Evidence Saved to: {out_path}")
    print("=" * 80)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
