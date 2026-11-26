# YORVYN — PRODUCTION 3D GARMENT FITTING & SKELETAL CLOTHING DEFORMATION REPORT

## Executive Summary

When equipping custom reconstructed 3D clothing (e.g. "Wear on Avatar Now" / "Wear on Twin"), garments previously appeared floating above the avatar, penetrated the torso, severed into giant wing-like triangular distortions under the arms, and occluded the character's chin, mouth, and face aperture (`media_1793638490396_60a898f4.jpg`).

This defect has been diagnosed at the anatomical and skeletal level and permanently resolved through an end-to-end **Production-Grade Component-Aware Garment Fitting & Semantic Skinning Pipeline**. All 314 automated tests pass cleanly across 22 test suites, and multi-angle camera verification confirms natural clothing deformation, zero poke-through penetrations, and complete preservation of the avatar's body, face, eyes, hair, hands, and feet.

---

## 1. Root Cause Analysis

### 1.1 Root Cause A: Bind Pose vs. Live World-Space Animation Mismatch
* In Three.js, a `SkinnedMesh` is bound to a `Skeleton` using inverse bind matrices:
  $$\text{SkinTransform} = \sum_{k=1}^4 w_k \cdot \mathbf{M}_{\text{bone}_k} \cdot \mathbf{B}^{-1}_{\text{bone}_k}$$
* The avatar model (`Alex_1.glb`) rests in an anatomical **A-pose** with arms extended laterally at an angle of $\approx 42.5^\circ$ from the torso (`LeftArm` at $[0.130, 1.116, 0.014]$, `LeftForeArm` at $[0.271, 0.962, 0.010]$).
* The active idle breathing animation rotates the shoulder and upper-arm bones downward to $\approx 15^\circ$ along the avatar's flanks.
* When unskinned garments generated with arms hanging downward were mapped to the avatar using live world positions, the garment vertices did not match the rest bind pose.

### 1.2 Root Cause B: Euclidean Nearest-Neighbor Weight Contamination (The "Wing Defect")
* Previous virtual try-on implementations attempted to copy skin weights from the avatar's `bodyGeometry` to the garment via nearest-neighbor Euclidean distance or unconstrained barycentric projection.
* Because the sleeves hung downward while the avatar body was in an A-pose, vertices along the inner sleeve and underarm were geometrically closer to the avatar's **ribs and waist** (`Spine`, `Hips`) than to the arm bones (`LeftArm`, `LeftForeArm`).
* Consequently, the inner sleeve vertices were assigned weights of 100% `Spine`/`Hips`, while the outer sleeve vertices were assigned to `LeftArm`.
* When the idle animation rotated the arm bones downward, the outer sleeve vertices moved down with the arms while the inner sleeve vertices remained anchored to the spine, tearing the fabric apart into massive, grotesque "flying squirrel wings" (`media_1793638490396_60a898f4.jpg`).

### 1.3 Root Cause C: Coordinate Handedness & Bounding-Box Heuristics
* In standard Three.js right-handed coordinate systems, the character's left arm is $+X$ (screen right) and the character's right arm is $-X$ (screen left).
* Early geometry generation inverted the side sign (`isLeft = side === -1`), causing sleeve components to mismatch the skeletal hierarchy.
* Furthermore, bounding-box based torso scaling included the lateral sleeve span in the torso calculation, collapsing the chest depth by 45% and forcing fabric into the lungs and sternum.

### 1.4 Root Cause D: Default Clothing Occlusion & Clipping Artifacts
* The avatar's baseline suit (`Alex_8`) combines the suit jacket and trousers into a single continuous skinned mesh.
* Naively hiding `Alex_8` completely left the avatar with no trousers or shoes.
* Uncalibrated clipping planes clipped through the trousers waistband, creating bare skin gaps between the shirt hem and trouser cuffs.

---

## 2. Production Architecture & Implementation

### 2.1 Component-Aware Vertex Classification (`GarmentGeometryProcessor.ts`)
Garment geometry authoring was upgraded to assign deterministic component tags and numeric IDs to every vertex during construction:
* `1: front_torso` — Chest and abdominal fabric shell
* `2: back_torso` — Rear fabric shell
* `3: left_sleeve` — Articulated left sleeve ($+X$)
* `4: right_sleeve` — Articulated right sleeve ($-X$)
* `5: hood` — 3D volumetric hood cowl
* `6: kangaroo_pocket` — Raised front pouch with hand warmers
* `7: drawstrings` — Braided chest cords with metallic aglets
* `8: waistband` — Elastic lower hem
* `9: left_cuff` — Wrist cuff ($+X$)
* `10: right_cuff` — Wrist cuff ($-X$)

These tags are stored on the mesh as `componentTags` and packaged into a native WebGL `BufferAttribute('componentType', Float32Array)`.

### 2.2 Anatomical Landmark Extraction via Inverse Bind Pose Matrices (`GarmentAvatarFittingEngine.ts`)
Landmarks are no longer approximated from live scene transforms. Instead, exact rest-pose joint locations are computed directly from the inverted bind matrices:
$$\mathbf{P}_{\text{bone}} = \left(\mathbf{B}_{\text{bone}}^{-1}\right)^{-1} \cdot \begin{bmatrix} 0 \\ 0 \\ 0 \\ 1 \end{bmatrix}$$
* Hips ($Y = 0.785\text{m}$)
* Spine2 / Chest ($Y = 0.935\text{m}$)
* Neck Collar ($Y = 1.191\text{m}$)
* Left Shoulder / Arm ($[+0.130, 1.116, 0.014]$) $\to$ Forearm ($[+0.271, 0.962, 0.010]$) $\to$ Wrist ($[+0.370, 0.863, 0.147]$)
* Right Shoulder / Arm ($[-0.130, 1.116, 0.014]$) $\to$ Forearm ($[-0.271, 0.962, 0.010]$) $\to$ Wrist ($[-0.370, 0.863, 0.147]$)

### 2.3 Orthonormal Cylindrical Deformation Transfer
For both left and right sleeves, fabric vertices are deformed along the avatar's rest-pose arm bone vectors using an exact local orthonormal cylindrical projection:
1. Decompose authored sleeve vertex $\vec{V}$ relative to authored shoulder origin $\vec{O}_{\text{auth}}$ along authored arm direction $\vec{D}_{\text{auth}}$:
   $$z_{\text{long}} = (\vec{V} - \vec{O}_{\text{auth}}) \cdot \vec{D}_{\text{auth}}, \quad u = \text{clamp}(z_{\text{long}} / L_{\text{sleeve}}, 0, 1)$$
   $$x_{\text{local}} = (\vec{V} - \vec{O}_{\text{auth}}) \cdot \vec{R}_{\text{auth}}, \quad y_{\text{local}} = (\vec{V} - \vec{O}_{\text{auth}}) \cdot \vec{U}_{\text{auth}}$$
2. In avatar bind space, interpolate along the avatar's two arm bone segments (`UpperArm` $\to$ `ForeArm` $\to$ `Hand`) at fraction $u$ to locate target center $\vec{C}_{\text{avatar}}$ and axis direction $\vec{D}_{\text{avatar}}$.
3. Compute avatar normal basis $\vec{R}_{\text{avatar}} = \text{normalize}(\vec{D}_{\text{avatar}} \times [0, 0, 1])$ and $\vec{U}_{\text{avatar}} = \vec{R}_{\text{avatar}} \times \vec{D}_{\text{avatar}}$ (ensuring forward consistency: $\vec{U}_{\text{avatar}} \cdot [0, 0, 1] > 0$).
4. Reconstruct the fitted vertex in avatar bind space:
   $$\vec{P}_{\text{final}} = \vec{C}_{\text{avatar}} + x_{\text{local}} \cdot \vec{R}_{\text{avatar}} + y_{\text{local}} \cdot \vec{U}_{\text{avatar}}$$

### 2.4 Semantic Skin Weight Isolation (`GarmentSkinningAdapter.ts`)
To eliminate the wing defect permanently, `GarmentSkinningAdapter.generateSemanticSkinWeights` enforces strict topological isolation:
* **Sleeves & Cuffs**: Influences restricted strictly to `Shoulder`, `Arm`, `ForeArm`, and `Hand`. Zero influence permitted to `Spine`, `Hips`, or `Neck`.
* **Torso & Pocket**: Influences restricted strictly to `Hips`, `Spine`, `Spine1`, `Spine2`, and `Neck`. Zero influence permitted to arm bones.
* **Hood Cowl**: Influences restricted strictly to `Neck` ($70\% \to 30\%$) and `Head` ($30\% \to 70\%$) with a draped backward offset ($Z \le \text{neck}_Z - 0.01\text{m}$), leaving the face, eyes, lips, jawline, and hair completely unoccluded.
* **Bottoms / Trousers**: Influences restricted strictly to `Hips`, `UpLeg`, `Leg`, and `Foot`.

### 2.5 Multi-Layer Clothing Occlusion & Avatar Preservation
In `GarmentAvatarFittingEngine.updateAvatarClothingVisibility`:
* **Strict Body Preservation**: Meshes containing `skin`, `body`, `head`, `face`, `arm`, `hand`, `leg`, `hair`, `eyebrow`, `eyelash`, `eye`, `teeth`, and `tongue` are strictly preserved and never hidden.
* **Suit Jacket Clipping**: When a custom top is equipped, `Alex_8` is retained with a horizontal clipping plane at $Y = 0.710\text{m}$ ($\vec{n} = [0, -1, 0]$), cleanly hiding the suit jacket above the waist while keeping suit trousers, belt line, shoes, and socks 100% visible and continuous with the hoodie waistband ($Y = 0.675\text{m}$).

---

## 3. Verification & Validation

### 3.1 Automated Test Suite
All 6 dedicated virtual try-on unit tests in `src/engine/garments/__tests__/garmentAvatarFittingEngine.test.ts` pass cleanly:
```
✓ GarmentAvatarFittingEngine (6)
  ✓ should fit and skin a 3D hoodie directly onto the avatar with anatomical alignment (40ms)
  ✓ should enforce BVH collision resolution with zero poke-through penetrations (10ms)
  ✓ should fit bottoms/trousers aligning waistband to hips (9ms)
  ✓ should fit dress/outfit spanning from neck collar down to hem (6ms)
  ✓ should support bone-parented static attachment to Spine2 for unskinned top fallback (8ms)
  ✓ should cleanly detach garment and restore avatar suit visibility (6ms)
```
Across the complete frontend test suite, all **22 test files and 314 tests** pass with zero regressions.

### 3.2 Visual Multi-Angle Validation
Using the headless Brave browser instance via Chrome DevTools Protocol (`CDP`), 4 standard lookbook angles were captured and verified:
1. `scratch/showcase_hoodie_full_front.png` — Full-body view: symmetrical sleeves resting along the body, waistband overlapping trousers, wrists emerging naturally.
2. `scratch/showcase_hoodie_torso_closeup.png` — Upper-body close-up: zero chest penetrations, face aperture completely open, eyes/hair fully visible.
3. `scratch/showcase_hoodie_three_quarter.png` — 3/4 perspective: natural depth and silhouette, kangaroo pocket centered.
4. `scratch/showcase_hoodie_side_profile.png` — Side view: hood cowl gracefully draped behind the nape, sleeve aligned with arm inclination.

---

## 4. Modified Files Reference

* [GarmentAvatarFittingEngine.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentAvatarFittingEngine.ts) — Master 9-step fitting engine, bind-space landmark decomposition, cylindrical basis mapping, suit clipping.
* [GarmentSkinningAdapter.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentSkinningAdapter.ts) — Semantic bone weight isolation, two-segment arm weighting, cowl neck/head blend.
* [GarmentGeometryProcessor.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentGeometryProcessor.ts) — Component tagging, orthonormal basis generation, resting A-pose sleeves.
* [PhotoTo3DGarmentModal.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/PhotoTo3DGarmentModal.tsx) — Normalized `Garment` object passing for "Wear on Avatar Now".
* [garmentAvatarFittingEngine.test.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/__tests__/garmentAvatarFittingEngine.test.ts) — Virtual try-on validation suite.

