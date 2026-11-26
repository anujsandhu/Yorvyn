# YORVYN Phase 16.9 — Security Review, Export Validation & Real-World Validation Plan

## 1. Security & Phase 16.0 Boundary Compliance

Implemented in [`AnimationAssetSecurityValidator`](../../../backend/app/services/motion/motion_core.py) & [`motion_routes.py`](../../../backend/app/api/motion_routes.py):
- **No arbitrary filesystem paths:** `validate_safe_asset_ref` rejects `..`, leading `/`, backslashes, shell metacharacters, and paths >512 chars (`HTTP 400`).
- **Strict Pydantic `extra="forbid"` schemas:** Every MotionCore route (`transition/validate`, `fabric-profile`, `skeleton/retarget-check`, `compute/select`, `glb/validate`, `evaluate`) rejects unpermitted fields and cannot inject arbitrary animation scripts or override capability gates.
- **Asset & buffer limits:** Binary GLB payloads validated against header magic `0x46546C67`, version `2`, chunk boundaries, and `MAX_GLB_BYTES = 50 MiB`.
- **Owner & Phase 16.0 Router Enforcement:** Capabilities registered in `GarmentRouter` preserve timeouts, single execution slots, and owner provenance.
- **Non-mutating preview:** Character animation runs purely in runtime GPU/XPBD particle buffers and never overwrites candidate design revisions or semantic correspondence maps.

---

## 2. GLB Animation & Export Classification Matrix

| Mode (`ExportAnimationKind`) | Meaning | Trigger Condition |
|---|---|---|
| `skeletal_animation_export` | Rigged bone transforms + clip keyframes | `animations.length > 0` without garment extras or baked vertex morphs |
| `skeletal_with_garment_deformation` | Skeleton animations paired with garment attachment metadata | `animations.length > 0` + `extras.component_id` / `garment_attached` |
| `baked_simulation_export` | Baked mesh morph/vertex animation tracks | Validated morph `weights` animation channel + primitive `targets` present (otherwise rejected!) |
| `static_garment_export` | Static mesh / un-animated GLB | `animations.length === 0` |

---

## 3. Real-World Validation Plan (Required Before Physical Accuracy Certification)

Automated unit and synthetic Chromium tests establish **software correctness and crash-free stability**, not real tailor drape accuracy. Physical certification requires a future evaluation benchmark dataset containing:
1. **Multi-category garment corpus:** `denim_jacket`, `hoodie`, `shirt`, `tshirt`, `trousers`, `jeans`, `dress`, `skirt`, `traditional`, `sportswear`, `footwear` (front/side/back multi-view captures).
2. **Material diversity with lab references:** Known GSM areal density, Kawabata/FAST bend & stretch reference curves for cotton jersey, 14 oz twill denim, silk satin, worsted wool, rib knit, leather, linen, and technical polyester.
3. **Real rigged scan/avatar assets & calibrated reference motion sequences:** Synchronized optical motion-capture marker / multi-camera silhouette sequences covering walk, run, turn, arm raise, bend, sit, and return-to-idle.
4. **Reference body & garment measurements:** Calibrated scan circumferences, ease gaps, and independent interpenetration / Hausdorff surface error thresholds against real captured cloth silhouettes.
