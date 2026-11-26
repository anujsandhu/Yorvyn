# Construction Inference Policy (Phase 16.2)

## 1. Strict Evidence vs Inference Separation

Phase 16.2 enforces strict epistemic separation between what is visually supported by Phase 16.1 component observations and what is hypothesized by garment construction rules:

- **`OBSERVED`**: Assigned ONLY when an independent viewpoint directly supports the component (`ComponentEvidenceStatus.OBSERVED` with non-empty `source_image_ids` and `source_views`).
- **`INFERRED`**: Structural symmetry priors (e.g., `back_body` panels, `hood_lining`, waist darts) derived from category construction rules when no rear or internal photograph was supplied. Front-only uploads **cannot** mark rear pieces, rear darts, or rear pockets as `OBSERVED`.
- **`UNSUPPORTED`**: Features that cannot be established from the supplied evidence (e.g., `back_pocket` construction when only a front trouser photo is present, or rear dress closures on a front-only dress upload).
- **`AMBIGUOUS`**: Features where conflicting or low-completeness component observations prevent high-confidence panel selection.

## 2. Dimensional Uncertainty Policy

Every piece records explicit `MeasuredDimension` metadata:
- `IMAGE_DERIVED`: Supported by observed view/component bounding geometry; carries tighter `uncertainty_m` scaled by view/component uncertainty (`0.02 + uncertainty * 0.05` m).
- `CATEGORY_PRIOR`: Derived from `GarmentProportionsEstimator` category expectations when direct evidence for that panel is absent; carries explicit category prior uncertainty and zero fabricated image references.
- **No fabricated ground truth**: Neither single-photo dimensions nor inferred seams are ever presented as `DIRECTLY_MEASURED` tailors' tape measurements.

## 3. Fail-Closed Guarantees

- When `has_back_view == False`:
  - Rear body pieces (`back_body`, `left_back_leg`, `right_back_leg`, `bodice_back`, `skirt_back`) carry `source_views=[]`, `evidence_refs=[]`, `verification_state != OBSERVED`, and high explicit uncertainty (`>= 0.55`).
  - Rear pockets (`back_pocket_left`) and rear closures record `ConstructionVerificationState.UNSUPPORTED` in `graph.inference_records` and appear under `handoff.missing_or_ambiguous_features`.
- Real-photo execution in `scripts/evaluate_phase_16_2_construction.py` asserts `zero_rear_leakage == True` across all 7 front-only garment photographs.
