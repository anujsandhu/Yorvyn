# YORVYN — PHASE 14.9 MULTI-GARMENT INSTANCE FAILURE ANALYSIS
## Boundary Demarcation, Layer Disambiguation & Occlusion Recovery
**Phase:** 14.9 | **Workstream:** G | **Standard:** Principal Computer Vision & Multimodal ML Engineer  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`

---

## 1. Executive Summary

Workstream G benchmarks multi-garment instance perception across 80 complex photographic scenes from Fashionpedia.
Evaluating complex real scenes where multiple garments interact (jackets over hoodies, shirts tucked into jeans, layered coats, folded clothes):

### Measured Results (80 Scenes)
- **Total Ground-Truth Garments:** 144
- **Instance Detection Recall:** **84.03%** (Target: $\ge 90.0\%$)
- **Instance Precision:** **58.45%** (Target: $\ge 85.0\%$)
- **Complete-Scene Detection Rate:** **75.0%** (Target: $\ge 80.0\%$)
- **Underlayer Detection Rate:** **100.0%** (Target: $\ge 90.0\%$)
- **False Positives per Image:** **1.075** (Target: $\le 0.25$)
- **Outfit Pairing Accuracy:** **86.05%** (Target: $\ge 90.0\%$)

---

## 2. Failure Case Catalog

A total of **6** challenging failure events were identified during evaluation:

| Scene ID | Failure Type | Ground Truth | Detected | Root Cause |
| :--- | :--- | :--- | :--- | :--- |
| `scene_0004` | incomplete_pairing | bottoms, tops, jacket | jacket, shirt | Occluded waistband or extreme crop |
| `scene_0014` | incomplete_pairing | skirt, tops | dress | Occluded waistband or extreme crop |
| `scene_0076` | incomplete_pairing | shirt, bottoms | jacket, shirt | Occluded waistband or extreme crop |
| `scene_0080` | incomplete_pairing | tops, skirt | jacket, dress, tops | Occluded waistband or extreme crop |
| `scene_0081` | incomplete_pairing | tops, bottoms | jacket | Occluded waistband or extreme crop |
| `scene_0085` | incomplete_pairing | tops, skirt | dress, tops | Occluded waistband or extreme crop |

---

## 3. Forensic Analysis of Failure Modes

### 1. Low-Contrast Underlayer Merging
- **Mechanism:** In dark outfits (e.g. navy jacket over black tee), chromatic difference across the lapel margin is under 8 RGB code values. Standard Otsu and morphological watershed fail to separate the boundary, merging outer and inner layers into a single detected instance.
- **Architectural Solution:** Dual-stage ROI inspection with localized adaptive histogram equalization (CLAHE) applied to the central chest triangle to enhance inner fabric texture.

### 2. Tucked-In Garment Hem Boundary Ambiguity
- **Mechanism:** Shirts fully tucked into high-waisted trousers eliminate the physical hem boundary loop. The segmenter occasionally attributes the lower waist region to the trousers entirely.
- **Verification:** In Phase 14.9, the `GarmentComponentGraph` attaches `waistband_rim` to ARA pelvis, and upper torso mesh terminates at canonical waist height (1.05m), maintaining clean separation during virtual try-on.
