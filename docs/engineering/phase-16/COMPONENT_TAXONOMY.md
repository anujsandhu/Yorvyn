# YORVYN — Phase 16.1 Component Taxonomy

**Taxonomy Version:** `16.1.0`  
**Source Module:** [component_taxonomy.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/component_taxonomy.py)

## 1. Design Principles

1. **Versioned and Extensible:** `TAXONOMY_VERSION = "16.1.0"` governs every `ComponentObservation`, `FusedComponentAssessment`, `GarmentStructureGraphContract`, and `ComponentHandoffContract`.
2. **Category-Conditioned Profiles:** Garments are evaluated against their `CategoryComponentProfile` (`jacket`, `hoodie`, `shirt`, `tops`, `traditional`, `bottoms`, `dress`, `skirt`) rather than forcing trousers or dresses into a jacket schema.
3. **Never Confuse `NOT_OBSERVED` with `ABSENT`:** Expected components whose face is obscured, out of frame, or facing away from the camera remain `NOT_OBSERVED` / `NOT_DETECTED`. `ABSENT_VERIFIED` requires explicit unobstructed full-view evidence under documented category rules.

## 2. Structural Component Catalog

### A. Upper-body Garments (`upper_body`)

| Sub-group | Component IDs | Parent Anchor | Expected Views |
| :--- | :--- | :--- | :--- |
| **Body construction** | `front_body`, `back_body`, `left_body_panel`, `right_body_panel`, `shoulder_panel`, `side_panel` | `body` / `front_body` | `front`, `back`, `left_side`, `right_side`, `three_quarter` |
| **Sleeves** | `left_sleeve`, `right_sleeve`, `sleeve_opening`, `cuff`, `sleeve_seam`, `sleeve_attachment` | `front_body` / `sleeve` | `front`, `back`, `left_side`, `right_side`, `close_up`, `detail` |
| **Neck and collar** | `collar`, `collar_stand`, `lapel`, `neck_opening`, `hood`, `hood_opening`, `neckband` | `neck_opening` / `front_body` | `front`, `back`, `three_quarter`, `close_up`, `detail` |
| **Closures** | `zipper`, `button`, `button_placket`, `snap`, `hook`, `drawstring`, `velcro_closure` | `front_body` / `hood` / `button_placket` | `front`, `three_quarter`, `close_up`, `detail` |
| **Pockets** | `chest_pocket`, `side_pocket`, `patch_pocket`, `welt_pocket`, `flap_pocket`, `pocket_opening`, `kangaroo_pocket` | `front_body` / `patch_pocket` | `front`, `back`, `left_side`, `right_side`, `close_up`, `detail` |
| **Construction details** | `shoulder_seam`, `side_seam`, `hem`, `waistband`, `ribbing`, `stitching` | `front_body` / `waistband` | `front`, `back`, `left_side`, `right_side`, `close_up`, `detail` |

### B. Lower-body Garments (`lower_body`)

| Component ID | Type | Parent Anchor | Expected Views | Absence Constraint |
| :--- | :--- | :--- | :--- | :--- |
| `lower_waistband` | `waistband` | `None` | `front`, `back`, `left_side`, `right_side` | Full top contour visible |
| `belt_loops` | `belt_loops` | `lower_waistband` | `front`, `back`, `close_up`, `detail` | Sharp waistband zoom visible |
| `fly` | `fly` | `lower_waistband` | `front`, `close_up` | Never evaluated on back view |
| `front_rise`, `back_rise` | `front_rise`, `back_rise` | `lower_waistband` | `front` / `back` | View-exclusive |
| `left_leg`, `right_leg` | `left_leg`, `right_leg` | `lower_waistband` | `front`, `back`, `left_side`, `right_side` | Clear full leg silhouette |
| `inseam`, `outseam`, `crotch_seam` | seam types | `left_leg` / `front_rise` | `front`, `back`, `left_side`, `right_side`, `detail` | Requires seam visibility |
| `leg_opening`, `hem` | opening / hem | `left_leg` | `front`, `back`, `close_up` | Bottom must not be `OUT_OF_FRAME` |
| `front_pocket`, `back_pocket` | `pocket` | `front_rise` / `back_rise` | `front`+sides / `back` | `back_pocket` NEVER marked absent from front view |

### C. Dresses and One-Piece Garments (`dress_one_piece`)

| Component ID | Type | Parent Anchor | Expected Views |
| :--- | :--- | :--- | :--- |
| `bodice` | `bodice` | `None` | `front`, `back`, `three_quarter` |
| `waistline` | `waistline` | `bodice` | `front`, `back`, `left_side`, `right_side` |
| `skirt` | `skirt` | `waistline` | `front`, `back`, `left_side`, `right_side` |
| `neckline` | `neckline` | `bodice` | `front`, `three_quarter` |
| `straps` | `straps` | `bodice` | `front`, `back` |
| `dress_panels` | `panels` | `skirt` | `front`, `back`, `left_side`, `right_side` |
| `dress_closures` | `closures` | `bodice` | `back`, `left_side`, `right_side`, `close_up` |

### D. Required Per-Component Attributes

Every component observation and fused record exposes: `component_id`, `component_type`, `parent_component`, `garment_category`, `garment_subcategory`, `side_or_orientation`, `visibility_state`, `detection_state`, `evidence_status`, `source_image_id`/`source_image_ids`, `source_image_hash`/`source_image_hashes`, `source_view`/`source_views`, `bbox`/`localized_bbox`, `segmentation_mask_ref`, `landmark_refs`, `confidence`, `calibrated_probability`, and `uncertainty` (`total_uncertainty`, `epistemic_uncertainty`, `aleatoric_uncertainty`, `evidence_completeness`).
