"""
YORVYN — Comprehensive Model Registry & Licensing Audit (Phase 14.27)
Performs strict forensic audit of registered fashion AI models:
- Separates Code License from Checkpoint/Weights License
- Validates commercial use permissions
- Distinguishes lifecycle states:
  REGISTERED -> DOWNLOADED -> LOADED -> CONFIGURED -> EXECUTED -> VALIDATED
- Records hardware targets, parameter counts, memory budgets, and known limitations.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Dict, Any, List
from pathlib import Path


class ModelLifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    DOWNLOADED = "DOWNLOADED"
    LOADED = "LOADED"
    CONFIGURED = "CONFIGURED"
    EXECUTED = "EXECUTED"
    VALIDATED = "VALIDATED"


# Candidate catalog. Static source inspection only; a registry entry is not proof
# that a checkpoint is present, loaded, executed, measured, or commercially cleared.
COMPREHENSIVE_MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "FashionCLIP": {
        "repository_id": "openai/clip-vit-base-patch32",
        "checkpoint_weights": "Current adapter uses generic openai/clip-vit-base-patch32; FashionCLIP weights not verified",
        "architecture": "Generic CLIP ViT-B/32",
        "model_version": "unverified",
        "intended_capability": "15-Category zero-shot classification, subcategory disambiguation, text-image matching",
        "execution_mode": "Local Offline Cache",
        "supported_hardware": "Apple Silicon M2 (MPS), CPU, CUDA (Optional)",
        "verified_device": "not verified",
        "parameter_count": "not verified",
        "memory_active_mb": None,
        "memory_peak_mb": None,
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "known_limitations": "Generic CLIP is not FashionCLIP; adapter only loads from local cache.",
        "lifecycle_state": ModelLifecycleState.REGISTERED.value,
        "verification_evidence": "STATIC: current source names generic OpenAI CLIP and no independent accuracy reproduction was run."
    },
    "SigLIP": {
        "repository_id": "openai/clip-vit-base-patch32",
        "checkpoint_weights": "Current adapter uses generic openai/clip-vit-base-patch32; SigLIP weights are not loaded",
        "architecture": "Generic CLIP ViT-B/32 with a sigmoid score transform",
        "model_version": "unverified",
        "intended_capability": "Multi-label co-occurring attribute extraction (pattern, sleeves, neckline, closure, pockets)",
        "execution_mode": "Local Offline Cache",
        "supported_hardware": "Apple Silicon M2 (MPS), CPU, CUDA (Optional)",
        "verified_device": "not verified",
        "parameter_count": "not verified",
        "memory_active_mb": None,
        "memory_peak_mb": None,
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "known_limitations": "Current adapter is not SigLIP and its score transform is not calibrated.",
        "lifecycle_state": ModelLifecycleState.REGISTERED.value,
        "verification_evidence": "STATIC: current adapter loads generic CLIP from local cache only."
    },
    "DINOv2": {
        "repository_id": "facebook/dinov2-small",
        "checkpoint_weights": "facebook/dinov2-small (Self-Supervised Vision Transformer ViT-S/14)",
        "architecture": "Vision Transformer (ViT-S/14)",
        "model_version": "1.0-small",
        "intended_capability": "Dense 384-dimensional visual embeddings, patch feature grid, structural consistency",
        "execution_mode": "Local Offline Cache",
        "supported_hardware": "Apple Silicon M2 (MPS), CPU, CUDA (Optional)",
        "verified_device": "not verified",
        "parameter_count": "not verified",
        "memory_active_mb": None,
        "memory_peak_mb": None,
        "code_license": "Not independently verified",
        "checkpoint_license": "Not independently verified",
        "commercial_usage_permitted": False,
        "known_limitations": "Does not output categorical semantics directly; requires linear probing or cosine similarity.",
        "lifecycle_state": ModelLifecycleState.REGISTERED.value,
        "verification_evidence": "STATIC: cached weights are required; fallback features are explicitly non-semantic."
    },
    "Grounded-SAM2": {
        "repository_id": None,
        "checkpoint_weights": "No model checkpoint loaded by the current adapter",
        "architecture": "OpenCV Otsu mask and proportional boxes",
        "model_version": "heuristic",
        "intended_capability": "Apparel component localization, bounding-box detection, and pixel-level semantic masks",
        "execution_mode": "Local Offline Cache",
        "supported_hardware": "Apple Silicon M2 (MPS / CPU)",
        "verified_device": "cpu/opencv",
        "parameter_count": "0 learned parameters",
        "memory_active_mb": None,
        "memory_peak_mb": None,
        "code_license": "Not independently verified",
        "checkpoint_license": "Not applicable; no checkpoint loaded",
        "commercial_usage_permitted": False,
        "known_limitations": "Prompt labels map to fixed proportional regions; not Grounding DINO or SAM2.",
        "lifecycle_state": ModelLifecycleState.EXECUTED.value,
        "verification_evidence": "STATIC: adapter source uses thresholding and proportional box rules."
    },
    "Depth-Anything-V2": {
        "repository_id": None,
        "checkpoint_weights": "No Depth Anything checkpoint loaded by the current adapter",
        "architecture": "Analytic image-intensity and torso-prior heuristic",
        "model_version": "heuristic",
        "intended_capability": "Relative monocular surface fold relief, wrinkle displacement, depth layering",
        "execution_mode": "Local Offline Cache",
        "supported_hardware": "Apple Silicon M2 (MPS / CPU)",
        "verified_device": "cpu/opencv",
        "parameter_count": "0 learned parameters",
        "memory_active_mb": None,
        "memory_peak_mb": None,
        "code_license": "Not independently verified",
        "checkpoint_license": "Not applicable; no checkpoint loaded",
        "commercial_usage_permitted": False,
        "known_limitations": "Estimates relative disparity, NOT calibrated metric centimeters (scale reference required).",
        "lifecycle_state": ModelLifecycleState.EXECUTED.value,
        "verification_evidence": "STATIC: source implements analytic relative disparity, not Depth Anything V2."
    },
    "Local-Rule-Engine": {
        "repository_id": "yorvyn-native/rule-engine",
        "checkpoint_weights": "Deterministic Fashion Construction Rules (Patternmaker Topology Rules)",
        "architecture": "Deterministic Rule Graph & Taxonomy Normalizer",
        "model_version": "14.27-native",
        "intended_capability": "Zero-cost offline attribute normalization, conflict resolution, and material presets",
        "execution_mode": "In-Memory Python CPU",
        "supported_hardware": "Universal CPU (macOS, Linux, Windows)",
        "verified_device": "cpu",
        "parameter_count": "0 (Deterministic Heuristics)",
        "memory_active_mb": 0.5,
        "memory_peak_mb": 1.0,
        "code_license": "Not independently verified",
        "checkpoint_license": "N/A",
        "commercial_usage_permitted": False,
        "known_limitations": "Cannot observe unseen visual features; depends on upstream perception evidence.",
        "lifecycle_state": ModelLifecycleState.REGISTERED.value,
        "verification_evidence": "STATIC: deterministic local rules are implemented; independent timing/reproducibility was not run."
    }
}


def audit_model_registry() -> Dict[str, Any]:
    """Audits model registry and validates commercial license compliance."""
    results = {}
    compliant_count = 0

    for model_name, info in COMPREHENSIVE_MODEL_REGISTRY.items():
        is_compliant = info["commercial_usage_permitted"] and info["code_license"] in ["MIT License", "Apache 2.0", "Proprietary / MIT Permitted"]
        if is_compliant:
            compliant_count += 1

        results[model_name] = {
            "checkpoint": info["checkpoint_weights"],
            "architecture": info["architecture"],
            "parameters": info["parameter_count"],
            "memory_active_mb": info["memory_active_mb"],
            "code_license": info["code_license"],
            "checkpoint_license": info["checkpoint_license"],
            "commercial_compliant": is_compliant,
            "lifecycle_state": info["lifecycle_state"],
            "verified_device": info["verified_device"]
        }

    return {
        "total_models_audited": len(COMPREHENSIVE_MODEL_REGISTRY),
        "commercial_compliant_models": compliant_count,
        "compliance_rate": round(compliant_count / len(COMPREHENSIVE_MODEL_REGISTRY), 2),
        "hardware_target": "Apple Silicon M2 (16GB Unified Memory)",
        "models": results
    }
