# YORVYN — PHASE 14.22 OPEN SOURCE & INTELLECTUAL PROPERTY LICENSE AUDIT

**Audit Date**: November 2026  
**Auditor**: ML Infrastructure & Legal Engineering Role  
**Policy**: Commercial permissive open-source licenses required for production core. Copyleft and non-commercial restrictions must be quarantined or rejected.

---

## 1. PRODUCTION DEPENDENCY LICENSES

| Library / Model | Version | License | Commercial Use Permitted? | Patent Grant? | Redistribution Terms | Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PyTorch** | 2.8.0 | BSD-3-Clause | YES | YES | Retain copyright notice | `APPROVED` |
| **ONNX Runtime** | 1.19.2 | MIT | YES | YES | Retain copyright notice | `APPROVED` |
| **Transformers** | 4.57.6 | Apache 2.0 | YES | YES | Apache Notice requirements | `APPROVED` |
| **Trimesh** | 4.12.2 | MIT | YES | YES | Retain copyright notice | `APPROVED` |
| **xatlas** | 0.0.11 | MIT | YES | YES | Retain copyright notice | `APPROVED` |
| **OpenCV** | 5.0.0 | Apache 2.0 | YES | YES | Apache Notice requirements | `APPROVED` |
| **SciPy** | 1.13.1 | BSD-3-Clause | YES | YES | Retain copyright notice | `APPROVED` |
| **Pillow** | 11.3.0 | HPND | YES | YES | Retain historical permission | `APPROVED` |
| **DINOv2** | Weights | Apache 2.0 | YES | YES | Permissive open commercial | `APPROVED` |
| **SAM 2** | Weights | Apache 2.0 | YES | YES | Permissive open commercial | `APPROVED` |
| **Depth Anything V2**| Weights | Apache 2.0 | YES | YES | Permissive open commercial | `APPROVED` |
| **Grounding DINO** | Weights | Apache 2.0 | YES | YES | Permissive open commercial | `APPROVED` |

---

## 2. QUARANTINED OR REJECTED TECHNOLOGIES

| Technology | License | Reason for Rejection / Quarantine | Status |
| :--- | :--- | :--- | :--- |
| **PyMeshLab** | GPL v3 | Strong copyleft license requires viral open-sourcing of proprietary business logic | `REJECTED` |
| **CGAL** | GPL / LGPL | Strong copyleft components pose licensing risks in SaaS distribution | `REJECTED` |
| **DUSt3R / MASt3R** | CC BY-NC-SA 4.0 | Non-Commercial restriction prohibits commercial fashion virtual try-on SaaS deployment | `QUARANTINED FOR RESEARCH` |
| **Neuralangelo** | Custom Non-Commercial| Research only, non-commercial clause forbids production utilization | `REJECTED` |
| **nvdiffrast** | Nvidia Source License | Proprietary hardware lock-in to NVIDIA GPUs; incompatible with Apple Silicon | `REJECTED` |
| **SMPL / SMPL-X** | Custom Research EULA | Restrictive commercial licensing and fee structures; YORVYN uses proprietary ARA rig | `REJECTED` |

---

## 3. AUDIT CONCLUSION
The active production pipeline of YORVYN Phase 14.22 contains **100% permissively licensed components** (Apache 2.0, MIT, BSD-3-Clause, HPND). Zero GPL or copyleft contamination is present in the core reconstruction path.
