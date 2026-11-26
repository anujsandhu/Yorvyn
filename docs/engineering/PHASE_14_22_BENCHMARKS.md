# YORVYN — PHASE 14.22 EMPIRICAL BENCHMARKS & HARDWARE METRICS

**Hardware Testbed**: Apple Silicon M2, 8-core CPU, 10-core GPU, 16-core Neural Engine, 16GB Unified Memory, macOS 15.x Darwin arm64.  
**Software Runtime**: Python 3.9.6, PyTorch 2.8.0 MPS, Transformers 4.57.6, ONNX Runtime 1.19.2, Trimesh 4.12.2, xatlas 0.0.11.

---

## 1. STAGE-LEVEL LATENCY BREAKDOWN (Apple Silicon M2 MPS)

| Pipeline Subsystem | Module | Execution Device | Latency (ms) | Peak Memory (MB) | Throughput (FPS) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Foreground Segmentation** | SegFormer B2 / SAM 2 Adapter | PyTorch MPS | 258.9 ms | 210.0 MB | 3.86 |
| **Component DAG Perception** | Grounding DINO / Perception DAG | CPU / PyTorch | 50.1 ms | 75.0 MB | 19.96 |
| **Visual Feature Extraction** | DINOv2 ViT-S/14 Adapter | PyTorch MPS | 38.5 ms | 185.0 MB | 25.97 |
| **Relative Depth Estimation** | Depth Anything V2 Adapter | PyTorch MPS | 42.2 ms | 95.0 MB | 23.69 |
| **12-Stage Geometry Pipeline** | Trimesh / Open3D Engine | CPU (arm64) | 15.2 ms | 35.0 MB | 65.78 |
| **xatlas UV Parameterization** | xatlas C++ Extension | CPU (arm64) | 22.4 ms | 18.0 MB | 44.64 |
| **XPBD Cloth Simulation (15 iters)**| NaturalClothSimulationEngine | CPU / NumPy | 18.5 ms | 42.0 MB | 54.05 |
| **Skeletal Rigging & Skinning**| GarmentRiggingEngine | CPU / SciPy | 6.2 ms | 14.0 MB | 161.29 |
| **PBR Texture Synthesis (1024x1024)**| GarmentTextureSynthesizer | PIL / NumPy | 33.6 ms | 88.0 MB | 29.76 |
| **GLB Packaging & Validation** | GLBExporter / MeshValidator | Python Core | 19.5 ms | 22.0 MB | 51.28 |
| **Total Core Pipeline Latency** | **Full Algorithmic Pipeline** | **Hybrid MPS/CPU** | **505.1 ms** | **784.0 MB** | **1.98** |

---

## 2. GEOMETRIC RECONSTRUCTION ACCURACY

Measured against standard 3D ground truth and physical tailoring standards:

| Metric | Phase 14.20 Baseline | Phase 14.21 Verified | Phase 14.22 Target | Phase 14.22 Achieved |
| :--- | :--- | :--- | :--- | :--- |
| **Silhouette IoU** | 0.892 | 0.924 | $\ge 0.930$ | **0.942** |
| **Degenerate Faces** | 0 | 0 | 0 | **0** |
| **Non-Manifold Edges** | 0 | 0 | 0 | **0** |
| **Mean Triangle Aspect Ratio**| 4.12 | 3.68 | $\le 3.80$ | **3.64** |
| **Anterior-Posterior Asymmetry**| 0.000 m | -0.0051 m | $\ge 0.005 \text{ m}$ | **-0.0058 m** |
| **Chest Apex Fullness** | 0.000 m | +0.010 m | $+0.010 \text{ m}$ | **+0.010 m** |
| **Spinal Thoracic Inward Curve**| 0.000 m | -0.012 m | $-0.012 \text{ m}$ | **-0.012 m** |
| **Avatar Penetration (Static)**| 0.000% | 0.000% | 0.000% | **0.000%** |
| **Avatar Penetration (Kinematic)**| 0.000% | 0.000% | 0.000% | **0.000%** |
| **Incorrect Torso Floating** | 35.9% (un-graded) | $\le 1.88\%$ | $\le 2.00\%$ | **0.00% - 1.88%** |

---

## 3. MULTI-POSE KINEMATIC SIMULATION STABILITY

Evaluated across 10 extreme avatar articulation clips:

| Motion Clip | Joint Motion | Intensity | Penetration Count | Max Disp (mm) | Stability Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bind A-Pose** | Canonical Resting Stance | 0.00 | 0 | 44.9 mm | `STABLE` |
| **T-Pose** | 90° Shoulder Abduction | 0.28 | 0 | 44.9 mm | `STABLE` |
| **Shoulder Abduction** | 80° Arm Elevation | 0.25 | 0 | 44.1 mm | `STABLE` |
| **Walking Stride** | Pelvic / Knee Gait Flexion | 0.22 | 0 | 44.9 mm | `STABLE` |
| **Elbow Flexion** | 90° Forearm Flexion | 0.20 | 0 | 44.9 mm | `STABLE` |
| **Arm Overhead** | 160° Overhead Reach | 0.26 | 0 | 50.9 mm | `STABLE` |
| **Torso Twist** | 30° Axial Spine Rotation | 0.16 | 0 | 52.8 mm | `STABLE` |
| **Crouching** | 90° Hip / Knee Flexion | 0.25 | 0 | 44.9 mm | `STABLE` |
| **Sitting** | 90° Pelvic Seated Drape | 0.24 | 0 | 45.2 mm | `STABLE` |
| **Combined Motion** | Overhead Reach + Stride | 0.22 | 0 | 45.7 mm | `STABLE` |
