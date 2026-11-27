# YORVYN Phase 16.3.1 — Semantic Pattern-to-Mesh Correspondence Specification

**Version:** `16.3.1`  
**Status:** Verified Implementation (Offline & Local Engine; Scientific CAD Sewing Accuracy Blocked Without Real Ground-Truth Benchmarks)  
**Primary Modules:**
- Backend: [`backend/app/services/intelligence/semantic_correspondence.py`](../../../backend/app/services/intelligence/semantic_correspondence.py)
- Frontend: [`frontend/src/engine/designStudio/SemanticCorrespondenceEngine.ts`](../../../frontend/src/engine/designStudio/SemanticCorrespondenceEngine.ts)

---

## 1. Architectural Purpose

Phase 16.3 synchronized 2D patterns and 3D edits proportionally across bounding boxes. While functional for uniform studio edits, uniform bounding-box ratios fail when modifying individual construction parts, asymmetrically shifting edges, or mixing measurement scopes (`PATTERN_PANEL_HALF` vs `HALF_GARMENT_FLAT` vs `FULL_CIRCUMFERENCE`).

Phase 16.3.1 establishes a **versioned, explicit, construction-aware `SemanticCorrespondenceMap` (`16.3.1`)** connecting Phase 16.2 2D pattern entities to Phase 14.20–16.3 named 3D mesh components (`GarmentComponentNode` extras/names) and parametric zones.

---

## 2. Explicit 2D → 3D Mapping Schema (`PatternRegionMapping`)

Each pattern piece in `UnifiedConstructionGraphContract` maps deterministically to its 3D target:

| Field | Semantics |
|---|---|
| `mapping_id` | Deterministic piece correspondence identifier (`map_{piece_id}`) |
| `piece_id` | Phase 16.2 pattern piece identifier (e.g. `front_left_body`, `sleeve_left`, `collar_stand`) |
| `pattern_vertex_ids`, `pattern_edge_ids`, `curve_ids` | Bound 2D CAD boundary vertices, semantic `EdgeRole`s, and Bézier curve identifiers |
| `seam_ids`, `dart_ids`, `notch_ids`, `grainline_id` | Explicit seam, dart, notch, and grainline references on the panel |
| `local_coordinate_system` | `2D_METRIC_Z_UP_CCW` (units: meters `m`) |
| `panel_scope` | `PATTERN_PANEL_HALF` \| `PATTERN_PANEL_FULL` |
| `mesh_id`, `mesh_region_ids`, `garment_component_id` | Target 3D node(s) (`main_torso`, `lapels_and_collar`, `left_sleeve`, `right_sleeve`, `left_cuff`, `right_cuff`, `hood_cowl`, `kangaroo_pocket`, `waistband_and_pelvis`, `left_leg`, `right_leg`) |
| `surface_correspondence` | `direct_component` \| `parametric_zone` \| `unmapped` |
| `uv_region_id`, `material_region_ref` | Target UV atlas quadrant & material shell |
| `construction_relations` | Typed links (`ATTACHED_TO`, `SEWN_TO`, `MIRRORED_BY`, `SYMMETRIC_WITH`, `CONSTRAINED_BY`, `DEFORMS_WITH`, `SUPPORTED_BY_VIEW`, `INFERRED_WITH_UNCERTAINTY`) |
| `evidence_support` | Provenance (`OBSERVED`, `INFERRED`, `UNSUPPORTED`) + supporting view IDs from Phase 16.1/16.2 |

---

## 3. Supported Semantic Operation Matrix (`SEMANTIC_OPERATION_SPECS`)

| Operation | Supported Pattern Pieces | Target 3D Mesh Regions | Boundary Rule |
|---|---|---|---|
| `torso_length` | `front_left_body`, `front_right_body`, `front_body`, `back_body`, `lower_front`, `lower_back` | `main_torso`, `front_zipper_track`, `front_placket`, `kangaroo_pocket` | Bounded Y-scaling anchored below neckline |
| `torso_width` | `front_left_body`, `front_right_body`, `front_body`, `back_body` | `main_torso` | Scoped panel ease (`+cm`) translated exactly into half-garment & full circumference |
| `shoulder_width` | `front_left_body`, `front_right_body`, `front_body`, `back_body` | `main_torso` (shoulder cap zone `y > 0.25`) | Shifts sleeve armscye attach points laterally |
| `sleeve_length` | `sleeve_left`, `sleeve_right`, `sleeve_panel` | `left_sleeve`, `right_sleeve`, `left_cuff`, `right_cuff` | Axial scaling along sleeve arm vector; repositions cuffs |
| `sleeve_width` | `sleeve_left`, `sleeve_right`, `sleeve_panel` | `left_sleeve`, `right_sleeve`, `left_cuff`, `right_cuff` | Radial cross-section scaling perpendicular to arm axis |
| `collar_width` | `collar_stand`, `collar_panel` | `lapels_and_collar`, `collar_and_stand`, `hood_cowl` | Radial scale around neck ring; propagates neckline opening constraint |
| `cuff_width` | `cuff_left`, `cuff_right`, `cuff_panel` | `left_cuff`, `right_cuff` | Radial cuff circumferences; triggers armscye/sleeve hem coupling |
| `hem_width` | `front_left_body`, `front_right_body`, `front_body`, `back_body`, `lower_front`, `lower_back`, `front_leg_left`, `front_leg_right` | `main_torso`, `left_leg`, `right_leg` | Smooth falloff at bottom hem (`y < 0.15`) |
| `waistband_width` | `waistband` | `waistband_and_pelvis` | Trouser/skirt waistband radial scale |
| `leg_width` | `front_leg_left`, `front_leg_right`, `back_leg_left`, `back_leg_right` | `left_leg`, `right_leg` | Inseam/outseam lateral scale around leg centerline |
| `leg_length` | `front_leg_left`, `front_leg_right`, `back_leg_left`, `back_leg_right` | `left_leg`, `right_leg`, `left_cuff`, `right_cuff` | Trouser length Y-scaling |
| `pocket_position` | `kangaroo_pocket`, `patch_pocket` | `kangaroo_pocket` | Bounded Y-offset relative to lower torso panel (`[-0.08, +0.08] m`) |

Category filtering in [`GarmentDesignWorkspace.tsx`](../../../frontend/src/components/design/GarmentDesignWorkspace.tsx) ensures upper-body garments do not present bottom-only sliders (`waistbandWidthScale`, `legWidthScale`, `legLengthScale`), bottoms hide collar/sleeve/shoulder sliders, and `pocketOffsetYM` is presented only when a pocket piece is mapped.

---

## 4. Dimensional Reconciliation & Forensic Resolution of `+3 cm Panel Ease`

In Phase 16.3 browser verification, clicking `+3 cm Panel Ease` caused the telemetry readout to jump from `Chest: 54.0 cm` to `Chest: 61.5 cm` (an unintended `+7.5 cm` shift).

**Exact mathematical cause preserved in Phase 16.3 historical audit:**
1. `DesignStateEngine` initialized `chestWidthM` to `0.54 m` (`54.0 cm`, a full flat-front assumption), while hydrating `front_left_body` (`PATTERN_PANEL_HALF`, width `0.216 m`).
2. Clicking `+3 cm Panel Ease` shifted a vertex by `+0.03 m`: `0.216 -> 0.246 m`.
3. `applyPatternVertexEdit` computed an unscoped ratio `0.246 / 0.216 = 1.138889` and multiplied `0.54 * 1.138889 = 0.6150 m` (`61.5 cm`).

**Phase 16.3.1 resolution:**
1. `MeasurementScope` distinguishes `PATTERN_PANEL_HALF`, `PATTERN_PANEL_FULL`, `HALF_GARMENT_FLAT`, `FULL_CIRCUMFERENCE`, `SEAM_ALLOWANCE`, and `EASE_ALLOWANCE`.
2. `DesignStateEngine.hydrateConstructionPattern` sets `activePanelScope = 'PATTERN_PANEL_HALF'` when `front_left_body`/`front_right_body` is active, hydrating `activePanelWidthM` from the actual polygon X-span and deriving `chestWidthM` (`half_garment_flat`) and `chestCircumferenceM` cleanly.
3. `DesignStateEngine.applyPanelEase` / `apply_panel_ease_to_chest` adds `+0.03 m` (`+3.0 cm`) directly to the targeted panel net width (`21.6 cm -> 24.6 cm`, or `21.75 cm -> 24.75 cm` on jacket front-left with placket overlap), updating `half_garment_flat` (`+6.0 cm` symmetric) and `finished_garment_circumference` (`+12.0 cm` symmetric) deterministically without multiplicative scope distortion.
