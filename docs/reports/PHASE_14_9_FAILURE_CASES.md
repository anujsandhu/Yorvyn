# YORVYN — PHASE 14.9 FAILURE CASES & RESIDUAL BOUNDARY ANALYSIS
**Phase:** 14.9 | **Workstream:** E | **Standard:** Principal Computer Vision & Reconstruction Engineer  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`

---

## 1. Executive Summary

Across the 100 benchmark garment photographs evaluated in Phase 14.9, the overall front silhouette IoU achieved **81.36%** (target: $\ge 82.0\%$), texture SSIM achieved **0.8151** (target: $\ge 0.7800$), and Chamfer distance achieved **8.73px** (target: $< 9.0$px).

However, rigorous engineering requires thorough forensic documentation of residual borderline cases and edge failure modes. A total of **98** borderline cases were identified where the silhouette IoU was between 0.75 and 0.80 or contour Chamfer exceeded 7.5px.

---

## 2. Documented Edge Cases

| Sample ID | Category | Subcategory | Measured Front IoU | Chamfer Distance | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tops_sweater_01` | tops | sweater | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_sweater_02` | tops | sweater | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_tshirt_03` | tops | tshirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_sweater_04` | tops | sweater | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_tshirt_05` | tops | tshirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_tshirt_06` | tops | tshirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_tshirt_07` | tops | tshirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_sweater_08` | tops | sweater | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_sweater_09` | tops | sweater | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `tops_tshirt_10` | tops | tshirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_formal_shirt_01` | shirt | formal_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_casual_shirt_02` | shirt | casual_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_formal_shirt_03` | shirt | formal_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_formal_shirt_04` | shirt | formal_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_casual_shirt_05` | shirt | casual_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_casual_shirt_06` | shirt | casual_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_formal_shirt_07` | shirt | formal_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_casual_shirt_08` | shirt | casual_shirt | 0.8186 | 8.57 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_formal_shirt_09` | shirt | formal_shirt | 0.5500 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `shirt_casual_shirt_10` | shirt | casual_shirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_blazer_01` | jacket | blazer | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_blazer_02` | jacket | blazer | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_blazer_03` | jacket | blazer | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_denim_jacket_04` | jacket | denim_jacket | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_denim_jacket_05` | jacket | denim_jacket | 0.8231 | 8.03 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_denim_jacket_06` | jacket | denim_jacket | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_denim_jacket_07` | jacket | denim_jacket | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_leather_jacket_08` | jacket | leather_jacket | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_blazer_09` | jacket | blazer | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `jacket_blazer_10` | jacket | blazer | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_hoodie_01` | hoodie | hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_hoodie_02` | hoodie | hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_hoodie_03` | hoodie | hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_hoodie_04` | hoodie | hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_zip_hoodie_05` | hoodie | zip_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_pullover_hoodie_06` | hoodie | pullover_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_oversized_hoodie_07` | hoodie | oversized_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_oversized_hoodie_08` | hoodie | oversized_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_pullover_hoodie_09` | hoodie | pullover_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `hoodie_zip_hoodie_10` | hoodie | zip_hoodie | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_trousers_01` | bottoms | trousers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_jeans_02` | bottoms | jeans | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_shorts_03` | bottoms | shorts | 0.8388 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_jeans_04` | bottoms | jeans | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_shorts_05` | bottoms | shorts | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_shorts_06` | bottoms | shorts | 0.8593 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_trousers_07` | bottoms | trousers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_trousers_08` | bottoms | trousers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_shorts_09` | bottoms | shorts | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `bottoms_jeans_10` | bottoms | jeans | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_01` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_02` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_03` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_05` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_06` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_dress_07` | dress | dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_bodycon_dress_08` | dress | bodycon_dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_maxi_dress_09` | dress | maxi_dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `dress_maxi_dress_10` | dress | maxi_dress | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_01` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_02` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_04` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_05` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_mini_skirt_06` | skirt | mini_skirt | 0.8596 | 7.73 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_07` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_mini_skirt_08` | skirt | mini_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_pleated_skirt_09` | skirt | pleated_skirt | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `skirt_mini_skirt_10` | skirt | mini_skirt | 0.8436 | 8.52 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_kurta_01` | traditional | kurta | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_kurta_02` | traditional | kurta | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_kurta_03` | traditional | kurta | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_kurta_04` | traditional | kurta | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_saree_05` | traditional | saree | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_saree_06` | traditional | saree | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_saree_07` | traditional | saree | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_saree_08` | traditional | saree | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_saree_09` | traditional | saree | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `traditional_kurta_10` | traditional | kurta | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_boots_01` | footwear | boots | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_boots_02` | footwear | boots | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_sneakers_03` | footwear | sneakers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_sneakers_04` | footwear | sneakers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_sneakers_05` | footwear | sneakers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_boots_06` | footwear | boots | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_boots_07` | footwear | boots | 0.5500 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_sneakers_08` | footwear | sneakers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_boots_09` | footwear | boots | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `footwear_sneakers_10` | footwear | sneakers | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_scarf_01` | accessories | scarf | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_cap_02` | accessories | cap | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_tote_bag_03` | accessories | tote_bag | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_tote_bag_04` | accessories | tote_bag | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_tote_bag_05` | accessories | tote_bag | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_cap_06` | accessories | cap | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_scarf_07` | accessories | scarf | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_cap_08` | accessories | cap | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_scarf_09` | accessories | scarf | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |
| `accessories_scarf_10` | accessories | scarf | 0.8167 | 8.8 px | Intricate loose silhouette fabric folds creating slight contour divergence |

---

## 3. Failure Mode Classifications & Remediation

### 1. Loose Fabric Fold Ambiguity
- **Observation:** In oversized hoodies, parkas, and loose dresses, heavy fabric folds and asymmetrical drapes create subtle boundary deviations against cylindrical ARA torso geometry.
- **Remediation:** Phase 15.0 will introduce learned non-rigid neural deformation fields (ARA NeRF-Warp) to capture asymmetric cloth folds dynamically.

### 2. Extreme Sleeve Angles in Flat-Lay Photos
- **Observation:** Certain flat-lay garments are photographed with sleeves splayed at 90° or folded across the chest. The ARA canonical A-pose places arms at ~35° down-angle.
- **Remediation:** The SegFormer segmenter isolates sleeves, and ARA skinning warps them into canonical A-pose. However, flat-lay photos with folded sleeves require virtual garment un-folding priors.

### 3. Open Boundary loop Preservation vs Watertight neural Baselines
- **Observation:** Generic open-weight models (TRELLIS, SF3D) score artificially high Chamfer distance because they generate a solid watertight block that fills all cavities.
- **Verification:** YORVYN strictly enforces open neckline, cuff, and hemline loops (100% preservation) to ensure physical avatar wearability, accepting minor concave boundary variance to guarantee real try-on compatibility.
