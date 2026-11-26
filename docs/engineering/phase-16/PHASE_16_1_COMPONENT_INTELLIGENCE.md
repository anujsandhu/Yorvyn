# YORVYN — Phase 16.1 Component Intelligence Architecture & Implementation Gap Report

**Date:** 2026-11-25  
**Base Phase:** 16.0 (`GarmentRouter`, `CapabilityRegistry`, `ExecutionContext`)

## 1. Phase 16.0 Audit & Implementation Gap Report

| Inspected System | Phase 16.0 State | Gaps Identified Before Phase 16.1 | Phase 16.1 Resolution |
| :--- | :--- | :--- | :--- |
| **Capability Registry & Router** (`capability_registry.py`, `garment_adapters.py`) | `components.identify` was `DEGRADED` and unbound in `GarmentRouter` | Calling `components.identify` raised `ValueError` | Implemented & bound `analyze_garment_components()`, verified contract, upgraded state to `VERIFIED` |
| **Component Taxonomy** (`component_registry.py`, `component_detector.py`) | Scattered naming (`torso_body`, `hood_cowl`, freeform strings) | No versioned multi-category schema separating upper/lower/dress parts | Added `TAXONOMY_VERSION = "16.1.0"` with 59 component entries & 8 category profiles |
| **Component Localization** (`component_perception.py`, `grounded_sam2_adapter.py`) | Hardcoded `kangaroo_pocket`/`drawstrings` on hoodies; fabricated `back_torso` from front photos | No visibility states, no occlusion check, no first-class uncertainty, no zero-box honesty | Multi-signal pipeline using SegFormer-B2 occluder parsing, cached CLIP crop checks, Sobel/contour localizer, explicit visibility & uncertainty |
| **Multi-View Fusion** (`view_classifier.py`, `fusion_engine.py`) | Only fused boolean `any_present`; ignored sub-crops; discarded view disagreements | Missing `three_quarter`/`close_up`; repeated crops could inflate view counts | Added `detect_subcrop_similarity`, view-aware fusion, contradiction preservation, structure graph |
| **Structure Graph** (`universal_construction_graph.py`) | Template-first hardcoded construction DAG | Invented missing nodes/edges as `"inferred"` (`0.65`) | Added evidence-grounded `GarmentStructureGraphContract` (`ATTACHED_TO`, `PART_OF`, `CONNECTED_TO`, `OVERLAPS`, `SYMMETRIC_WITH`, `ADJACENT_TO`, `SUPPORTED_BY_VIEW`) |
| **Evaluation** (`component_evaluator.py`, `garment_evaluation_pilot_v1.json`) | Missing boxes scored `1.0` IoU in presence mode; empty pilot manifest | Lacked mask IoU, visibility accuracy, false-absence rate, greedy multi-box matching | Fixed localization IoU honesty; added multi-instance IoU, visibility accuracy, false-absence rate, calibration; evaluated 7 real photos + 50 Fashionpedia val samples |
| **Stylist Integration** (`conversational_garments.py`, `GarmentJobMessage.tsx`) | Only invoked `views.identify` | `components.identify` never dispatched; missing-component guidance wasn't surfaced | Bound automatic `components.identify` on detail/identification turns + non-jargon UI/clarification output |

## 2. Executable Pipeline Architecture

1. **Deduplication & Sub-crop Screening:** SHA-256 exact match -> 64-bit dHash near-duplicate -> OpenCV normalized cross-correlation sub-crop check (`crop_of_existing_view`).
2. **Preprocessing & Caching:** Bounded 768px working image, Laplacian sharpness, contrast, border-touch `OUT_OF_FRAME` test, cached by `(image_hash, view_type, category, subcategory)` (LRU 256).
3. **Segmentation & Occlusion:** Cached `HumanParsingSegmenter` (`mattmdjaga/segformer_b2_clothes`) separates garment pixels from limbs, hair, bags, belts, scarves, and other overlapping clothing; falls back cleanly to OpenCV Otsu+color connected-component isolation.
4. **Region Localization & Neural Verification:** Morphological profile & Sobel/Canny contour detectors localize body panels, lateral sleeve lobes, cuffs, collars, lapels, hoods, zippers, button plackets, pockets, waistbands, legs, crotch seams, bodices, and skirts. Cached OpenAI CLIP ViT-B/32 confirms upper-neckline and center-closure crops without external LLM calls.
5. **Structure Graph & Reconstruction Handoff:** Emits typed structural edges only between grounded components and classifies every component as `SAFE_TO_USE`, `USE_WITH_UNCERTAINTY`, `REQUIRE_MORE_EVIDENCE`, or `DO_NOT_INFER`.
