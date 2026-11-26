# YORVYN — PHASE 14.22 HARDWARE & RUNTIME COMPATIBILITY MATRIX

## 1. COMPATIBILITY ASSESSMENT SUMMARY

| Technology | Target Platform | Supported Accelerators | Evaluation Result | Production Integration Path |
| :--- | :--- | :--- | :--- | :--- |
| **PyTorch 2.8.0** | macOS arm64, Linux x86_64 | Apple Silicon MPS, CPU, CUDA | `FULLY COMPATIBLE` | Primary AI Runtime |
| **ONNX Runtime 1.19.2**| macOS arm64, Linux x86_64 | Core ML EP, CPU, CUDA EP | `FULLY COMPATIBLE` | Secondary AI Runtime & Fallback |
| **xatlas 0.0.11** | macOS arm64, Linux x86_64 | CPU Native Binary Wheel | `FULLY COMPATIBLE` | Automated UV Unwrapping |
| **Trimesh 4.12.2** | Platform Independent | CPU Native | `FULLY COMPATIBLE` | Geometry Processing Core |
| **OpenCV 5.0.0** | macOS arm64, Linux x86_64 | CPU Accelerate Framework | `FULLY COMPATIBLE` | Image Morphology & Slicing |
| **DINOv2 ViT** | Apple Silicon M2 | PyTorch MPS | `FULLY COMPATIBLE` | Feature Vector Extraction |
| **Depth Anything V2**| Apple Silicon M2 | PyTorch MPS / ONNX | `FULLY COMPATIBLE` | Disparity & Fold Relief |
| **SAM 2** | Apple Silicon M2 | PyTorch MPS / CPU | `ADAPTED WITH FALLBACK`| Precision Segmentation |
| **Grounding DINO** | Apple Silicon M2 | PyTorch MPS / CPU | `ADAPTED WITH FALLBACK`| Open-Vocabulary Detection |
| **DUSt3R / MASt3R** | Linux CUDA / macOS | PyTorch MPS (Partial) | `EXPERIMENTAL ADAPTER` | Offline Multi-View Research |
| **COLMAP** | macOS arm64 (Homebrew) | CPU / Metal (Limited) | `CLI INTEGRATION` | Batch Photogrammetry |
| **InstantMesh** | Linux x86_64 | NVIDIA CUDA 11.8+ (12GB) | `INCOMPATIBLE WITH M2` | Blocked under Zero-Cost Policy |
| **TripoSR** | Linux x86_64 | NVIDIA CUDA 11.8+ (8GB) | `INCOMPATIBLE WITH M2` | Blocked under Zero-Cost Policy |
| **Neuralangelo** | Linux x86_64 | NVIDIA CUDA 11.8+ (16GB) | `INCOMPATIBLE WITH M2` | Blocked under Zero-Cost Policy |
| **nvdiffrast** | Linux x86_64 | NVIDIA Hardware Only | `INCOMPATIBLE WITH M2` | Proprietary NVIDIA Hardware Required |
| **Detectron2** | Linux / macOS Intel | GCC / Clang C++ Extensions | `BUILD INCOMPATIBLE` | Fragile build on macOS Apple Silicon |
| **Three.js** | Modern Web Browsers | WebGL 2.0 / WebGPU | `FULLY COMPATIBLE` | Frontend 3D Canvas & Studio Inspector |

---

## 2. ZERO-COST LOCAL DEVELOPMENT COMPLIANCE
- All development and testing execute strictly on local Apple Silicon M2 hardware.
- Cloud spend is verified at exactly **$0.00 USD**.
- Remote CUDA clusters remain strictly `BLOCKED` in compliance with project policy.
