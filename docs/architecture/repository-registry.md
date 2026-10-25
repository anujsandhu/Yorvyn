# Yorvyn Technology Library — Upstream Source Acquisition Registry

This registry tracks all evaluated, acquired, and integrated third-party repositories within the Yorvyn Private Technology Library.

---

## Candidate 1: Ara 3D Gen (`3d-gen`)

| Attribute | Specification |
| :--- | :--- |
| **Project Name** | Ara 3D Gen (MIT Character Engine) |
| **Official Source URL** | [https://github.com/olatunde85/3d-gen](https://github.com/olatunde85/3d-gen) |
| **Git Clone URL** | `https://github.com/olatunde85/3d-gen.git` |
| **Pinned Commit SHA** | `0c3473d7d46a2badcdcd1dcfd4aeb0762eb04b20` |
| **Upstream License** | MIT License |
| **Asset / Weights License** | MakeHuman base mesh & targets (CC0 / MIT). Permissive commercial use. |
| **Runtime Requirements** | Node.js 18+, TypeScript 5+, Three.js r160+. No Python or CUDA required. |
| **Hardware & Storage** | Runs on standard CPU/browser WebGL. Client bundle: ~3.5MB assets. |
| **Commercial Compatibility**| **100% Permitted**. Fully compatible with commercial SaaS. |
| **Security & Maintenance** | Pure browser TypeScript/GLTF; zero binary execution vulnerabilities. |
| **Intended Yorvyn Module** | `packages/avatar-core`, `packages/avatar-generation`, `packages/avatar-rigging` |
| **Integration Status** | **Production Integrated** in `frontend/src/engine/ara/`. |
| **Known Limitations** | Anime styling is stylized; requires custom clothing meshes for outerwear. |

---

## Candidate 2: Clothware (`Digital-clothing`)

| Attribute | Specification |
| :--- | :--- |
| **Project Name** | Clothware (Digital-Clothing Monocular Garment Reconstruction) |
| **Official Source URL** | [https://github.com/cameronking4/Clothware](https://github.com/cameronking4/Clothware) |
| **Git Clone URL** | `https://github.com/cameronking4/Clothware.git` |
| **Pinned Commit SHA** | `c5579d17962ca1cbb6e79e70c84c77ad4d60d84e` |
| **Upstream License** | No explicit LICENSE file committed (Default copyright reserved). |
| **Asset / Weights License** | DeepFashion2 API / MMDetection weights (Non-commercial academic use only). |
| **Runtime Requirements** | Python 3.7.9 (deprecated), PyTorch 1.10.1, CUDA 10.2/11.1, Ubuntu 20.04. |
| **Hardware & Storage** | Requires Nvidia GPU with CUDA. Weights: ~1.8GB. |
| **Commercial Compatibility**| **Restricted / Unsuitable for Direct Commercial Distribution** without licensing. |
| **Security & Maintenance** | Unmaintained repository (last commit 2022); outdated dependencies. |
| **Intended Yorvyn Module** | Benchmarked under `research/upstream/Clothware`. |
| **Integration Status** | **Adapted as Clean-Room Architecture**: Parametric manifold builder in `packages/garment-core` and `backend/app/fashion/garment_3d`. |
| **Known Limitations** | Only supports shirts and pants; template deformation can distort asymmetrical patterns. |

---

## Candidate 3: Garment3DGen (Meta Reality Labs)

| Attribute | Specification |
| :--- | :--- |
| **Project Name** | Garment3DGen: 3D Garment Stylization and Generation |
| **Project Website** | [https://nsarafianos.github.io/garment3dgen](https://nsarafianos.github.io/garment3dgen) |
| **Git Clone URL** | `https://github.com/nsarafianos/Garment3DGen.git` |
| **Pinned Commit SHA** | `496e113a72a17d263f157c69ada488d633e74e27` |
| **Upstream License** | Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0) |
| **Asset / Weights License** | Wonder3D / InstantMesh diffusion checkpoints (Research-only). |
| **Runtime Requirements** | Python 3.10+, PyTorch 2.1+, CUDA 11.8+, `nvdiffrast`, `pytorch3d`. |
| **Hardware & Storage** | High-end Nvidia GPU with >= 16GB VRAM. Checkpoint footprint: ~12GB. |
| **Commercial Compatibility**| **Non-Commercial Research Only**. Commercial use requires Meta enterprise agreement. |
| **Security & Maintenance** | Active research codebase with complex C++/CUDA compiler extensions. |
| **Intended Yorvyn Module** | `packages/ai-adapters` (Remote GPU Worker target interface). |
| **Integration Status** | **Acquired in `research/upstream/Garment3DGen`**; decoupled behind adapter boundary. |
| **Known Limitations** | Cannot run natively on macOS Apple Silicon; requires dedicated cloud worker pool. |

---

## Candidate 4: ReMu (ETH Zurich)

| Attribute | Specification |
| :--- | :--- |
| **Project Name** | ReMu: Clothed Human 3D Reconstruction with Multi-Layer Clothing |
| **Official Source URL** | [https://github.com/eth-ait/ReMu](https://github.com/eth-ait/ReMu) |
| **Git Clone URL** | `https://github.com/eth-ait/ReMu.git` |
| **Pinned Commit SHA** | `3cf1563e800ca40d08ba269865dc7420507c06ba` |
| **Upstream License** | MIT License (codebase) |
| **Asset / Weights License** | SMPL-X (Max Planck Institute: strictly Non-Commercial / Academic). |
| **Runtime Requirements** | Python 3.9+, PyTorch 2.0+, CUDA 11.8+, Chamfer3D, DiffRast. |
| **Hardware & Storage** | Nvidia GPU with >= 12GB VRAM. Storage: ~6.5GB model checkpoints. |
| **Commercial Compatibility**| **Restricted** due to SMPL-X body model licensing terms. |
| **Security & Maintenance** | Modern Python 3.9 research repository; clean documentation. |
| **Intended Yorvyn Module** | `packages/garment-fitting` and `research/upstream/ReMu`. |
| **Integration Status** | **Acquired in `research/upstream/ReMu`**; used as boundary layer reference. |
| **Known Limitations** | Reconstructs human body together with clothes; requires complex mesh peeling. |
