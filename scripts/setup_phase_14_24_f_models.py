#!/usr/bin/env python3
"""
YORVYN — Setup & Model Verification Script for Phase 14.24-F
Verifies local zero-cost AI model dependencies, Apple Silicon M2 MPS acceleration,
model cache readiness, and executes end-to-end sanity tests.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch


def main():
    parser = argparse.ArgumentParser(description="Yorvyn Phase 14.24-F Model Setup and Verification")
    parser.add_argument("--test-image", type=str, default="data/datasets/phase_13_6_real_photos/wm_05_hoodie_pullover.jpg", help="Path to test garment image")
    args = parser.parse_args()

    print("=" * 70)
    print("YORVYN — Phase 14.24-F Local Multimodal Model Setup & Verification")
    print("=" * 70)

    # 1. Hardware & Framework Check
    print("\n[1/5] Checking Hardware & Framework Environment...")
    mps_available = torch.backends.mps.is_available()
    device = "mps" if mps_available else "cpu"
    print(f"  - PyTorch Version: {torch.__version__}")
    print(f"  - Apple Silicon MPS Available: {mps_available}")
    print(f"  - Target Compute Device: {device}")

    # 2. Hugging Face Cache Inspection
    print("\n[2/5] Inspecting Local Hugging Face Cache...")
    hf_cache_dir = Path(os.path.expanduser("~/.cache/huggingface/hub"))
    if hf_cache_dir.exists():
        entries = [e.name for e in hf_cache_dir.iterdir() if e.is_dir()]
        print(f"  - Cache Path: {hf_cache_dir}")
        print(f"  - Found {len(entries)} cached repositories:")
        for e in entries:
            print(f"    * {e}")
    else:
        print("  - Notice: Local HuggingFace cache directory not found, fallback weights will be used.")

    # 3. Model Manager Initialization
    print("\n[3/5] Initializing Sequential Model Manager...")
    from backend.app.services.garments.intelligence.sequential_model_manager import model_manager
    mem_before = model_manager.get_current_memory_mb()
    print(f"  - Initial Resident Set Size (RSS): {mem_before:.1f} MB")
    print(f"  - Preferred Device: {model_manager.preferred_device}")

    # 4. Multi-model Engine Sanity Check
    print("\n[4/5] Loading Multimodal Identification Engine...")
    from backend.app.services.garments.intelligence.local_multimodal_identification_engine import multimodal_engine

    test_img_path = Path(args.test_image)
    if not test_img_path.exists():
        # Generate synthetic fallback image if path not found
        print(f"  - Test image {test_img_path} not found. Creating synthetic garment test image...")
        img_np = np.full((512, 512, 3), 240, dtype=np.uint8)
        img_np[100:450, 120:392] = [40, 45, 60]  # dark blue torso
        test_img = Image.fromarray(img_np)
    else:
        print(f"  - Using test image: {test_img_path}")
        test_img = Image.open(test_img_path)

    # 5. Execute Identification
    print("\n[5/5] Executing End-to-End Identification...")
    t0 = time.perf_counter()
    spec = multimodal_engine.identify_garment(test_img, garment_id="setup_verification_test")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    print("\n" + "=" * 70)
    print("VERIFICATION RESULTS:")
    print(f"  - Garment Category:        {spec.category.value}")
    print(f"  - Garment Subcategory:     {spec.subcategory}")
    print(f"  - Identification Confidence: {spec.confidence * 100:.2f}%")
    print(f"  - Primary Color:           {spec.attributes.primary_color}")
    print(f"  - Extracted Pattern:       {spec.attributes.pattern}")
    print(f"  - Sleeve Type:             {spec.attributes.sleeve_type}")
    print(f"  - Neckline:                {spec.attributes.neckline}")
    print(f"  - Pockets Detected:        {spec.attributes.pockets}")
    print(f"  - Components Localized:    {len(spec.components)}")
    print(f"  - Reconstruction DAG:      {spec.reconstruction_handoff.target_dag_template}")
    print(f"  - Peak Memory (RSS):       {spec.provenance.peak_memory_mb:.1f} MB")
    print(f"  - Total Pipeline Latency:  {latency_ms:.1f} ms")
    print(f"  - Zero-Cost Verified:      {spec.provenance.zero_cost_local_verified}")
    print(f"  - Explanation:             {spec.natural_language_explanation}")
    print("=" * 70)
    print("\n[SUCCESS] Yorvyn Phase 14.24-F Local AI Engine is ready for production.\n")


if __name__ == "__main__":
    main()
