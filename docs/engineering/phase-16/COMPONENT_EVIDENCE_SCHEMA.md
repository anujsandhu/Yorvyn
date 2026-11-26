# YORVYN — Component Evidence Schema (Phase 16.1)

**Contract Module:** [contracts.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/ai/contracts.py)  
**Graph & Handoff Builder:** [garment_structure_graph.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/garment_structure_graph.py)

## 1. Visibility & Evidence Enumerations

- `VisibilityState`: `FULLY_VISIBLE`, `PARTIALLY_VISIBLE`, `OCCLUDED`, `OUT_OF_FRAME`, `LOW_IMAGE_QUALITY`, `UNKNOWN`
- `ComponentEvidenceStatus`: `OBSERVED`, `NOT_OBSERVED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`, `UNVERIFIED`
- `DetectionState`: `DETECTED`, `ABSENT_VERIFIED`, `NOT_DETECTED`, `UNCERTAIN`, `UNAVAILABLE`
- `ReconstructionDecision`: `SAFE_TO_USE`, `USE_WITH_UNCERTAINTY`, `REQUIRE_MORE_EVIDENCE`, `DO_NOT_INFER`

## 2. Core Data Contracts

### `ComponentObservation`
Produced per view by `_analyze_single_view_components()` inside `analyze_garment_components()`:
- **Identities:** `observation_id`, `component_id`, `component_type`, `parent_component`, `garment_id`, `garment_category`, `garment_subcategory`, `side_or_orientation`
- **Provenance:** `source_image_id`, `source_image_hash` (SHA-256), `source_view`, `model_id`, `checkpoint_identity`, `capability_id`, `execution_provenance`, `processing_ms`
- **Spatial Localization (never fabricated when unproduced):** `bbox` `(ymin, xmin, ymax, xmax)` clamped in `[0.0, 1.0]`, `segmentation_mask_ref`, `landmark_refs`
- **Visibility & Uncertainty:** `visibility_state`, `detection_state`, `evidence_status`, `confidence`, `calibrated_probability`, `uncertainty` (`UncertaintyBreakdown`: `total_uncertainty`, `epistemic_uncertainty`, `aleatoric_uncertainty`, `evidence_completeness`, `reasons`)

### `FusedComponentAssessment`
Cross-view fused component record preserving all underlying observations (`observations`, `observation_ids`), `visibility_by_view`, `best_visibility`, `evidence_completeness`, `agreement_score`, `contradicted`, `contradiction_notes`, `downstream_decision`, and `decision_rationale`.

### `GarmentStructureGraphContract`
- **Nodes (`StructureGraphNode`):** component IDs carrying visibility, detection state, evidence status, confidence, uncertainty, contradiction flags, and source view citations.
- **Edges (`StructureGraphEdge`):** typed relations (`ATTACHED_TO`, `PART_OF`, `CONNECTED_TO`, `OVERLAPS`, `SYMMETRIC_WITH`, `ADJACENT_TO`, `SUPPORTED_BY_VIEW`). Unobserved endpoints remain `NOT_OBSERVED`; verified-absent components do not spawn fabricated attachment edges.

### `ComponentHandoffContract`
Phase 16.2 / 16.3 handoff contract classifying components into `safe_components` (`SAFE_TO_USE`), `uncertain_components` (`USE_WITH_UNCERTAINTY`), `more_evidence_components` (`REQUIRE_MORE_EVIDENCE`), and `blocked_components` (`DO_NOT_INFER`), paired with natural-language `clarification_prompts` for Stylist.

## 3. Integrity Validation

`CanonicalGarmentSpecificationV2.validate_evidence_integrity()` enforces:
1. Every `ComponentObservation.source_image_id` exists in `views` and matches `image_hash`.
2. Every `bbox` satisfies `0.0 <= ymin < ymax <= 1.0` and `0.0 <= xmin < xmax <= 1.0`.
3. Every `OBSERVED` property cites valid usable source IDs (or explicitly flagged `crop_of_existing_view`).
4. Every `CONFLICTED` property links to an explicit conflict entry with at least 2 competing records.
