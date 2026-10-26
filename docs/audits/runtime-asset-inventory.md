# Yorvyn Technology Library — Runtime Asset Inventory

**Audit Date**: October 26, 2026  
**Auditor**: Senior 3D Graphics & Asset Pipeline Engineer (Antigravity)  
**Subject**: Complete Catalog of Static and Generated 3D Runtime Assets  

---

## 1. Overview

Yorvyn's production application loads 3D models, textures, morph targets, and animation clips exclusively from project-managed, version-controlled directories or local persistent storage. No runtime assets are fetched from external cloned repositories.

---

## 2. Avatar Geometry, Skeleton & Morph Data

| Asset Identifier | Format | Size | Source | License | Local Storage Location | Loading Path | Independence Verified? |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- | :---: |
| **base_human.bin** | Binary Buffer | ~2.4 MB | MakeHuman / Ara 3D Gen | CC0 / MIT | `frontend/public/ara-assets/base_human.bin` | `/ara-assets/base_human.bin` | Yes |
| **avatar_skeleton.bin** | 65-bone joint matrix | ~48 KB | Ara 3D Gen Rigging | MIT | `frontend/public/ara-assets/skeleton.bin` | `/ara-assets/skeleton.bin` | Yes |
| **morph_targets.bin** | Delta displacement | ~4.8 MB | Anthropometry morphs | CC0 / MIT | `frontend/public/ara-assets/targets/` | `/ara-assets/targets/*.bin` | Yes |
| **sunglasses.glb** | glTF 2.0 Binary | 148 KB | Yorvyn Studio Catalog | Permissive MIT | `frontend/public/ara-assets/items/sunglasses.glb` | `/ara-assets/items/sunglasses.glb` | Yes |

---

## 3. Skeletal Animation Clips

| Clip Name | Duration | Keyframe Tracks | Source | License | Storage Path | Playback Method |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **Idle** | 3.5s | 22 humanoid bones | Ara 3D Gen Animation | MIT | Baked in memory / `AraService.ts` | Continuous Three.js AnimationAction loop |
| **Wave** | 2.2s | 28 humanoid bones | Ara 3D Gen Animation | MIT | Baked in memory / `AraService.ts` | One-shot gesture with smooth crossfade back to Idle |
| **Cheer** | 3.0s | 32 humanoid bones | Ara 3D Gen Animation | MIT | Baked in memory / `AraService.ts` | One-shot gesture with smooth crossfade back to Idle |
| **Turn (360°)**| 2.0s | 20 humanoid bones | Ara 3D Gen Animation | MIT | Baked in memory / `AraService.ts` | Procedural turntable spin & root orientation |

---

## 4. Materials, Textures & Shaders

| Asset Name | Type / Format | Resolution | Source | License | Storage Path | Loading Path |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **avatar_skin_diffuse.png** | Diffuse texture | 1024x1024 | Ara 3D Gen / Yorvyn | CC0 | `frontend/public/ara-assets/textures/` | `/ara-assets/textures/skin.png` |
| **avatar_skin_normal.png** | Tangent normal map | 1024x1024 | Synthetic | Permissive | `frontend/public/ara-assets/textures/` | `/ara-assets/textures/skin_normal.png` |
| **studio_room_env** | RoomEnvironment HDR | N/A | Three.js Standard | MIT | Generated in Three.js | In-memory via `RoomEnvironment` |
| **garment_pbr_diffuse.png** | De-lighted diffuse | 512x512 | Generated | User-owned | `backend/app/static/wardrobe/textures/` | `/api/fashion/garment-gen/assets/...` |
| **garment_pbr_normal.png** | Tangent normal map | 512x512 | Synthesized | Proprietary | `backend/app/static/wardrobe/textures/` | `/api/fashion/garment-gen/assets/...` |

---

## 5. Generated 3D Garments & Digital Wardrobe

| Item ID | Mesh Type | Vertex / Triangle Count | File Size | Storage Path | Reload After Restart? |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `item_long_sleeve_01` | Separable 3D Top | 420 v / 712 f | ~518 KB | `backend/app/static/wardrobe/models/*.glb` | Yes |
| `preview_thumbnail_01`| Software 3D Preview PNG | 512x512 | ~20 KB | `backend/app/static/wardrobe/thumbnails/*.png` | Yes |
| `wardrobe_metadata.json`| JSON Metadata | 1.2 KB | Yorvyn DB | `backend/app/data/wardrobe.json` | Yes |

---

## 6. Fonts and UI Icons

| Asset | Format | Source | License | Bundle Status |
| :--- | :--- | :--- | :--- | :--- |
| **Inter / Outfit** | WOFF2 / Web Font | Google Fonts | SIL Open Font License (OFL) | Loaded via CSS |
| **Lucide Icons** | SVG React Components | Lucide Project | ISC License | Bundled in frontend |
| **Yorvyn Brand Mark** | PNG | Yorvyn Design System | Proprietary | `frontend/src/assets/yorvyn-logo.png` |

---

## 7. Model Weights Independence

- **Current Architecture**: The active production pipeline operates as a **clean-room parametric and procedural geometry synthesizer**.
- **No Large Unverified Checkpoints**: Unlike research repositories that require 15 GB+ checkpoint downloads (e.g. Stable Diffusion 2.1 in Garment3DGen), Yorvyn's core production application runs in **zero weights mode** on local CPU and standard memory (fits within 8 GB unified memory on Apple Silicon).
- **Future Weights Integration**: Optional high-fidelity diffusion weights are isolated behind the `RemoteGpuWorkerAdapter` and will only be deployed on dedicated cloud infrastructure when explicitly scheduled.
