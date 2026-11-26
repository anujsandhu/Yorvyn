# YORVYN — Multi-View Evidence Policy (Phase 16.1)

**Implementation Modules:** [view_classifier.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/ai/multiview/view_classifier.py), [fusion_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/ai/multiview/fusion_engine.py), [component_evidence.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/component_evidence.py)

## 1. Supported Viewpoints & View Isolation

- Supported canonical views: `front`, `back`, `left_side`, `right_side`, `three_quarter`, `close_up`, `detail`, `label`, `unknown`.
- Every uploaded image is hashed with SHA-256 and a 64-bit difference hash (`dHash`).
- **Repeated Crop Protection:** Normalized cross-correlation template matching (`detect_subcrop_similarity`) screens smaller submissions against previously ingested full photographs. Matched sub-crops are marked `duplicate_type = "crop_of_existing_view"`, `crop_of_image_id = <ref>`, and `counts_as_independent_view = False` so a crop of a front photo can enrich detail analysis without ever masquerading as an independent rear or side camera view.

## 2. Visibility vs Absence Rules

1. **`NOT_OBSERVED != ABSENT`:** Unseen features (such as `back_body`, `back_pocket`, `dress_closures` on a front-only upload) remain `ComponentEvidenceStatus.NOT_OBSERVED` / `DetectionState.NOT_DETECTED` with `confidence = None` and `ReconstructionDecision.DO_NOT_INFER`.
2. **Permissible Absence Verification (`ABSENT_VERIFIED`):** A component may only be declared absent when its expected face is `FULLY_VISIBLE` in an unobstructed, sharp view under a category-specific rule (e.g., unobstructed front neckline for `hood` or unobstructed lower abdomen for `kangaroo_pocket`).
3. **Occlusion & Truncation:** Borders touched by the garment silhouette yield `VisibilityState.OUT_OF_FRAME`. Overlapping SegFormer occluders (arms, hair, bags, non-target clothing) downgrade visibility to `PARTIALLY_VISIBLE` or `OCCLUDED` and increase aleatoric uncertainty.

## 3. Contradiction Preservation & Handoff Gates

- If one view detects a component (`DETECTED`) while another view declares it absent (`ABSENT_VERIFIED`), or if incompatible closures (`zipper` vs `button_placket`) are detected across distinct views, fusion **never drops the contradiction**.
- Both observations remain retained inside `FusedComponentAssessment.observations`, `evidence_status` becomes `CONTRADICTED`, `total_uncertainty = 1.0`, a conflict record enters `CanonicalGarmentSpecificationV2.conflicts`, and reconstruction readiness/handoff switches to `REQUIRE_MORE_EVIDENCE` so Stylist requests user clarification.
