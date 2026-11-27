<USER_REQUEST>
# YORVYN — PHASE 14.5 MASTER EXECUTION PROMPT
## VISION-LANGUAGE GARMENT PERCEPTION, REMOTE NEURAL 3D INFERENCE & REAL-GARMENT VIRTUAL TRY-ON

**Project:** YORVYN Fashion Intelligence & 3D Virtual Try-On Platform  
**Phase:** 14.5  
**Role:** Principal Computer Vision Engineer, Multimodal ML Engineer, Neural 3D Reconstruction Engineer, Computational Geometry Engineer, Three.js/WebGL Engineer  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Primary Objective:** Move YORVYN from predominantly analytical garment generation toward demonstrable image-conditioned garment reconstruction and avatar fitting.

---

## 1. MISSION

Execute a comprehensive engineering phase addressing the unresolved limitations from Phase 14.4.

The objective is not to generate another architecture proposal or another collection of synthetic benchmark results.

The objective is to implement and validate a working pipeline:

**Real garment photograph → garment understanding → segmentation → geometry reconstruction → texture/material generation → avatar fitting → Three.js visualization.**

The implementation must preserve the existing working application and infrastructure. Inspect the repository before modifying anything. Reuse existing services where appropriate and avoid unnecessary rewrites.

### Mandatory priorities

1. Implement and benchmark a vision-language garment perception strategy.
2. Resolve the flat-lay classification failure.
3. Improve complete-instance garment detection.
4. Establish a real remote neural 3D inference endpoint.
5. Generate actual image-conditioned 3D garment assets.
6. Integrate generated assets with the existing avatar fitting pipeline.
7. Compare neural reconstruction against the existing procedural engine.
8. Validate actual uploaded garment likeness through visual evidence.
9. Preserve provenance, reproducibility, security, and dataset integrity.

---

## 2. PHASE 14.4 BASELINE — MUST BE PRESERVED

Use these reported results as the starting reference, not as independently verified ground truth.

| Metric | Phase 14.4 |
|---|---:|
| Raw flat-lay accuracy | 17.65% |
| Best isolated flat-lay accuracy | 29.41% |
| Detection recall | 62.55% |
| Detection mAP50 | 81.20% |
| Detection mAP50–95 | 56.40% |
| Complete-instance recovery | 38.00% |
| Accepted-set ECE | 0.0335 |
| Full-holdout ECE | 0.0990 |
| Opening preservation | 89.66% |
| Mask IoU | 89.57% |
| Boundary F-score | 84.83% |
| Multi-view Recall@1 | 99.50% |
| Neural 3D endpoint | Unset / blocked |
| Primary 3D engine | Analytical/procedural |
| Reported WebGPU browser pipeline | 71.58 ms |

### Mandatory baseline correction

Phase 14.3 reported 47.06% isolated letterboxed flat-lay holdout accuracy, whereas Phase 14.4 reported 29.41%.

Investigate this discrepancy before claiming improvement. Reproduce both protocols using the same identity-disjoint test population where possible. If the historical benchmark cannot be reproduced, document that limitation explicitly.

Do not silently redefine the baseline.

---

## 3. WORKSTREAM A — VISION-LANGUAGE GARMENT PERCEPTION

### 3.1 Architecture investigation

Evaluate suitable pretrained vision-language and vision models, including:

- CLIP / OpenCLIP
- SigLIP
- Florence-2
- Qwen2-VL
- Other compatible lightweight visual encoders where justified

Do not integrate every model. Select candidates based on measured performance, hardware requirements, licensing, latency, memory, and deployment feasibility.

### 3.2 Hybrid perception architecture

Implement a controlled architecture combining:

1. Existing garment classifier.
2. Vision-language image embeddings.
3. Garment taxonomy text embeddings.
4. Segmentation-derived garment crops.
5. Shape and silhouette descriptors.
6. Confidence calibration.
7. Selective prediction and human correction.

The system should reason over garment appearance, shape, components, and context instead of relying on background or image composition.

### 3.3 Required classification outputs

Each garment prediction should include:

- Domain: product, flat-lay, on-body, lifestyle, mannequin, folded.
- Category.
- Exact subcategory.
- Garment colour.
- Pattern.
- Fabric family.
- Sleeve type.
- Neckline.
- Closure type.
- Visible components.
- Occlusion estimate.
- Confidence and calibrated confidence.
- Evidence source and model provenance.

Unknown or visually unsupported properties must remain unknown. Never invent hidden garment details.

### 3.4 Evaluation protocol

Use identity-disjoint train, validation, and holdout sets.

Report:

- Domain accuracy.
- Category accuracy.
- Exact subcategory accuracy.
- Macro F1.
- Per-class precision and recall.
- Flat-lay-specific accuracy.
- Folded-garment accuracy.
- Calibration ECE and Brier score.
- Selective risk versus coverage.
- Inference latency and memory.

Evaluate full-frame, neutral-letterboxed, garment-crop, mask-conditioned, and multimodal representations separately.

### Targets

- Raw flat-lay accuracy: ≥65%.
- Isolated flat-lay accuracy: ≥80%.
- Flat-lay macro F1: ≥0.70.
- Full-holdout ECE: ≤0.08.
- Accepted-set ECE: ≤0.05.

If these targets are not achieved, report the actual result and remaining error categories. Do not relax the benchmark to manufacture a pass.

---

## 4. WORKSTREAM B — COMPLETE-INSTANCE DETECTION

Improve detection across:

- Multi-garment outfits.
- Partially occluded garments.
- Under-layers.
- Footwear.
- Accessories.
- Small garment components.
- Overlapping garments.
- Folded and stacked garments.

### Required improvements

- Class-aware detection.
- Better small-object recovery.
- Occlusion-aware detection.
- Garment-specific region proposals.
- Instance-level segmentation.
- Duplicate suppression without deleting overlapping valid garments.
- Stable garment instance identifiers.

### Mandatory success definitions

Report separately:

1. Any-instance detection rate.
2. At-least-two-instance detection rate.
3. Per-instance recall.
4. Complete-instance recovery rate.
5. False-positive instances per image.
6. Per-category recall.
7. Occluded-instance recall.

A scene counts as complete only when every annotated target garment is recovered under the defined matching threshold.

### Targets

- Recall ≥70%.
- mAP50 ≥80%.
- mAP50–95 ≥55%.
- Complete-instance recovery ≥80%.

Do not claim complete multi-garment success based on detecting only one garment in an outfit.

---

## 5. WORKSTREAM C — REMOTE NEURAL 3D RECONSTRUCTION

**This is the highest-priority workstream.**

Phase 14.4 explicitly confirmed that remote neural 3D inference was blocked because `GARMENT_AI_REMOTE_INFERENCE_URL` was unset.

Phase 14.5 must attempt to establish a real inference path.

### 5.1 Candidate evaluation

Investigate and select an appropriate model, including:

- Hunyuan3D.
- TRELLIS.
- Stable Fast 3D.
- InstantMesh.
- Other suitable image-conditioned reconstruction models.

Check current official implementation requirements, hardware, license, model weights, input requirements, output format, and commercial-use restrictions before selecting a model.

Do not assume that a model producing a generic object mesh is automatically suitable for clothing reconstruction.

### 5.2 Remote GPU service

Implement a secure inference service with:

- Dedicated GPU runtime.
- Authenticated requests.
- Job IDs.
- Queue management.
- Progress updates.
- Timeout handling.
- Cancellation.
- Retry policy.
- Output validation.
- Asset storage.
- Model version tracking.
- Cost and latency instrumentation.

Configure the existing integration contract rather than introducing unnecessary parallel APIs.

The frontend must never receive GPU credentials or private model-provider secrets.

### 5.3 Input contract

Accept:

- Original garment photograph.
- Garment segmentation mask.
- Bounding box.
- Garment category and subcategory.
- Visible component landmarks.
- Camera/domain metadata.
- Optional additional views.
- Confidence and occlusion information.

Support additional views when available. Do not claim that a single photograph reveals hidden rear geometry.

### 5.4 Output contract

Return:

- GLB or GLTF asset.
- Mesh geometry.
- UV coordinates.
- Albedo texture.
- PBR material properties where available.
- Vertex normals.
- Garment coordinate frame.
- Reconstruction provenance.
- Model version.
- Inference duration.
- Validation results.
- Confidence and known limitations.

Validate the resulting asset before it reaches the browser.

### 5.5 Provenance rules

Every generated asset must declare one of:

- `neural_reconstruction`
- `neural_reconstruction_refined`
- `hybrid_neural_procedural`
- `procedural_fallback`

Never label procedural geometry as neural reconstruction.

If remote inference is unavailable, expose the actual blocked status and use the procedural fallback explicitly.

### Acceptance condition

At least one selected neural reconstruction candidate must run against real uploaded garment photographs and return actual generated 3D assets.

A model feasibility document, mock endpoint, placeholder mesh, or hardcoded GLB does not satisfy this requirement.

---

## 6. WORKSTREAM D — GARMENT-SPECIFIC 3D GEOMETRY

A generic object reconstruction is insufficient for virtual try-on.

Investigate garment-aware geometry and reconstruction refinement for:

- T-shirts.
- Shirts.
- Hoodies.
- Jackets.
- Trousers.
- Shorts.
- Dresses.
- Skirts.
- Traditional garments.

Preserve critical garment structures:

- Neckline and collar.
- Shoulder width.
- Sleeve length and orientation.
- Sleeve openings.
- Armholes.
- Waistline.
- Hem.
- Pockets.
- Buttons and closures.
- Seams.
- Pleats.
- Slits.
- Cuffs.
- Layering.

### Geometry requirements

- Correct front/back orientation.
- Valid UV mapping.
- Consistent normals.
- Manifold validation where the chosen representation requires it.
- Self-intersection checks.
- Degenerate triangle checks.
- Reasonable topology density.
- Preservation of garment openings.
- Stable scale and coordinate conventions.

Do not artificially close legitimate openings simply to satisfy manifold checks.

---

## 7. WORKSTREAM E — AVATAR FITTING AND CLOTH SIMULATION

Integrate reconstructed garments with the existing avatar and fitting architecture.

Validate:

- Shoulder alignment.
- Neckline alignment.
- Sleeve attachment.
- Sleeve orientation.
- Waist placement.
- Hip alignment.
- Trouser length.
- Dress length.
- Garment scale.
- Avatar-specific ease.
- Collision and penetration.
- Pose stability.
- Skinning and deformation.

Separate:

- Bind-pose geometric clearance.
- Runtime dynamic collision.
- Visual occlusion.
- Actual garment-avatar penetration.

A static clearance test must not be reported as proof of collision-free runtime simulation.

Use the existing procedural fitting engine as a baseline and fallback, not as a substitute for testing neural garment reconstruction.

---

## 8. WORKSTREAM F — REAL VISUAL FIDELITY BENCHMARK

Expand the Phase 14.4 eight-case benchmark substantially.

### Minimum evaluation scope

- At least 100 real garment photographs.
- All nine canonical garment categories where supported.
- Multiple fabric families.
- Flat-lay and on-body inputs.
- Folded garments.
- Multi-garment and occluded examples.
- Front and rear views where available.

Maintain identity-disjoint evaluation.

### Compare three systems

1. Existing procedural reconstruction.
2. Neural reconstruction.
3. Hybrid neural-plus-procedural reconstruction.

### Evaluate

- Silhouette IoU.
- Length proportion fidelity.
- Width proportion fidelity.
- Shoulder and sleeve geometry.
- Neckline and collar fidelity.
- Component completeness.
- Texture similarity.
- UV distortion.
- Surface detail.
- Rear-view accuracy where ground truth exists.
- Mesh validity.
- Avatar fit quality.
- Visual human acceptance.

Where ground-truth 3D scans do not exist, explicitly label metrics as 2D projection comparisons or proxy evaluations.

Do not present a 2D silhouette score as proof of full 3D geometric accuracy.

### Mandatory visual QA

Generate contact sheets containing:

1. Original input.
2. Segmentation mask.
3. Garment crop.
4. Procedural reconstruction.
5. Neural reconstruction.
6. Hybrid reconstruction.
7. Front avatar fitting.
8. Side avatar fitting.
9. Rear avatar fitting where supported.

Include real model outputs, not mockups or manually substituted reference images.

---

## 9. WORKSTREAM G — MULTI-VIEW IDENTITY VALIDATION

Preserve the Phase 14.4 benchmark, but audit it independently.

Report separate results for:

- Positive pairs.
- Same-category hard negatives.
- Cross-category negatives.
- Different SKUs with similar designs.
- Different views of the same physical garment.
- Flat-lay-to-on-body matching.

Use identity-disjoint splits and remove near-duplicate leakage.

Report exact denominator and matching formula for Recall@1, Recall@5, MRR, Precision@1, FMR, and FRR.

Do not combine easy distractor negatives with hard negatives when reporting the primary identity metric.

---

## 10. WORKSTREAM H — FRONTEND AND BROWSER INTEGRATION

Integrate the real reconstruction pipeline into the existing YORVYN application.

The user journey should be:

1. Upload garment photograph.
2. Automatic garment analysis.
3. Show predicted garment attributes.
4. Allow correction when necessary.
5. Submit reconstruction job.
6. Display progress.
7. Receive generated GLB.
8. Validate and load asset.
9. Fit garment to avatar.
10. Display interactive 3D result.
11. Save garment to wardrobe.

### UI requirements

- Preserve the current design system.
- Maintain the persistent Three.js canvas.
- Avoid unnecessary scene recreation.
- Show reconstruction provenance.
- Show errors and fallback status.
- Support loading, retry, and cancellation.
- Keep the interface responsive.
- Avoid blocking the main thread.

Measure upload-to-result latency separately from browser-only inference latency.

---

## 11. WORKSTREAM I — SECURITY, COST AND OPERATIONAL RELIABILITY

Audit the remote GPU integration for:

- Authentication and authorization.
- User ownership.
- Signed asset URLs.
- File-size limits.
- MIME and file validation.
- Request rate limits.
- Queue bounds.
- Job cancellation.
- Retry idempotency.
- Storage lifecycle.
- GPU cost per job.
- Model warm-up time.
- Cold-start latency.
- Failure recovery.
- Sensitive image handling.

Do not expose user-uploaded garment images to external model providers without appropriate authorization and data-handling controls.

Do not introduce unbounded queues or uncontrolled GPU usage.

---

## 12. REQUIRED DELIVERABLES

Create a complete Phase 14.5 engineering report and machine-readable evidence.

Required deliverables:

1. `YORVYN_PHASE_14_5_MASTER_ENGINEERING_REPORT.md`
2. `YORVYN_PHASE_14_5_VLM_EVALUATION.json`
3. `YORVYN_PHASE_14_5_FLATLAY_EVALUATION.json`
4. `YORVYN_PHASE_14_5_DETECTION_EVALUATION.json`
5. `YORVYN_PHASE_14_5_MULTIVIEW_EVALUATION.json`
6. `YORVYN_PHASE_14_5_NEURAL_3D_INFERENCE.json`
7. `YORVYN_PHASE_14_5_RECONSTRUCTION_EVALUATION.json`
8. `YORVYN_PHASE_14_5_AVATAR_FITTING_EVALUATION.json`
9. `YORVYN_PHASE_14_5_VISUAL_FIDELITY_BENCHMARK.json`
10. `YORVYN_PHASE_14_5_BROWSER_PERFORMANCE.json`
11. `YORVYN_PHASE_14_5_SECURITY_AUDIT.json`
12. `YORVYN_PHASE_14_5_MODEL_PROVENANCE.json`
13. `YORVYN_PHASE_14_5_DATASET_AUDIT.json`
14. Visual QA contact sheets with original inputs and actual generated outputs.

Every metric must include:

- Dataset identifier.
- Split.
- Sample count.
- Denominator.
- Evaluation code or protocol.
- Model version.
- Hardware.
- Reproduction command.
- Baseline comparison.
- Confidence interval where appropriate.

---

## 13. EXECUTION RULES

1. Inspect the existing repository before implementation.
2. Preserve the baseline commit.
3. Do not commit, push, reset, or deploy.
4. Do not delete existing working systems.
5. Do not fabricate inference results.
6. Do not use mock outputs as real neural reconstruction evidence.
7. Do not leak test data into training or calibration.
8. Do not count synthetic images as genuine photographs.
9. Do not claim a target passed when it missed the threshold.
10. Preserve backward compatibility where possible.
11. Run relevant backend and frontend regression tests.
12. Document every blocker honestly.
13. Do not replace the existing working application with a demo-only implementation.

If GPU infrastructure, model weights, licenses, credentials, or provider authorization are unavailable, stop at the actual boundary, document what is missing, and provide the exact configuration required to continue. Do not simulate success.

---

## 14. FINAL ACCEPTANCE GATES

Phase 14.5 cannot receive an overall production-ready verdict unless all critical gates are demonstrated.

| Gate | Required evidence |
|---|---|
| Vision-language perception | Reproducible holdout comparison |
| Flat-lay understanding | Measured improvement on identity-disjoint real images |
| Complete-instance detection | Per-scene complete recovery benchmark |
| Calibration | Full-holdout ECE and reliability analysis |
| Neural 3D inference | Real remote inference on uploaded photographs |
| GLB output | Actual generated and validated asset |
| Avatar integration | Reconstructed garment visibly fitted on avatar |
| Garment likeness | Real-image visual benchmark |
| Provenance | Correct neural/hybrid/procedural declaration |
| Security | Authenticated and bounded remote inference |
| Regression | Existing application remains functional |

### Final verdict options

- `PASS`: All critical acceptance gates met.
- `PASS_WITH_QUALIFICATIONS`: Core pipeline works, but explicitly identified non-critical limitations remain.
- `PARTIAL`: Important engineering milestones achieved, but one or more core capabilities remain incomplete.
- `BLOCKED`: Required infrastructure or implementation prevents meaningful validation.
- `FAIL`: Critical functionality regressed or acceptance criteria were not met.

**The most important rule: YORVYN must reconstruct the garment the user actually uploaded, not merely generate a plausible garment of the same category.**

End Phase 14.5 with an honest evidence-backed verdict, a complete list of remaining blockers, and the next engineering roadmap.
</USER_REQUEST>
<ADDITIONAL_METADATA>
The current local time is: 2026-11-18T23:51:14+05:30.

The user's current state is as follows:
Active Document: /Users/anujsandhu/Projects/yorvyn/docs/reports/YORVYN_PHASE_14_4_MASTER_ENGINEERING_REPORT.md (LANGUAGE_UNSPECIFIED)
Cursor is on line: 1
Other open documents:
- /Users/anujsandhu/Projects/yorvyn/backend/app/api/ai_orchestration_routes.py (LANGUAGE_UNSPECIFIED)
- /Users/anujsandhu/Projects/yorvyn/backend/app/models/garment_reconstruction_contract.py (LANGUAGE_UNSPECIFIED)
- /Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/segmentation/human_parsing_segmenter.py (LANGUAGE_UNSPECIFIED)
- /Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/intelligence/garment_instance_detector.py (LANGUAGE_UNSPECIFIED)
- /Users/anujsandhu/Projects/yorvyn/frontend/src/components/PhotoTo3DGarmentModal.tsx (LANGUAGE_UNSPECIFIED)
</ADDITIONAL_METADATA>