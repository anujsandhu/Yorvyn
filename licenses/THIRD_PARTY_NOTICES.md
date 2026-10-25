# Yorvyn Technology Library — Third-Party Notices & Attribution

This document provides copyright, licensing, and attribution notices for open-source and research repositories evaluated, acquired, or adapted within the Yorvyn Private Technology Library.

---

## 1. Ara 3D Gen (`3d-gen`)

- **Upstream Source**: [https://github.com/olatunde85/3d-gen](https://github.com/olatunde85/3d-gen)
- **Pinned Commit**: `0c3473d7d46a2badcdcd1dcfd4aeb0762eb04b20`
- **Copyright**: (c) 2026 Josh Ola and Ara 3D Gen contributors
- **Code License**: MIT License
- **Asset / Data License**: MakeHuman CC0 / MIT (base mesh, morph targets, rigging landmarks)
- **Commercial Use**: **PERMITTED** under MIT / CC0 terms with attribution retained.
- **Attribution Notice**:
```
MIT License
Copyright (c) 2026 Josh Ola and Ara 3D Gen contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 2. Clothware (`Digital-clothing`)

- **Upstream Source**: [https://github.com/cameronking4/Clothware](https://github.com/cameronking4/Clothware)
- **Pinned Commit**: `c5579d17962ca1cbb6e79e70c84c77ad4d60d84e`
- **Copyright**: Cameron King (cameronking4)
- **Code License**: **No Explicit License Provided** (Default copyright applies to upstream source files).
- **Dependency Licenses**:
  - DeepFashion2 API: Non-commercial academic research agreement.
  - MMDetection / PyTorch: Apache 2.0 / BSD-3.
- **Commercial Use**: **RESTRICTED / NOT PERMITTED** for direct upstream code without written authorization; DeepFashion2 checkpoints are academic-only.
- **Yorvyn Policy**: Upstream code is kept strictly in `research/upstream/Clothware` for benchmarking and structural comparison. Yorvyn's production garment builder uses clean-room, independently authored parametric manifold code.

---

## 3. Garment3DGen (Meta Reality Labs)

- **Project Website**: [https://nsarafianos.github.io/garment3dgen](https://nsarafianos.github.io/garment3dgen)
- **Upstream Source**: [https://github.com/nsarafianos/Garment3DGen](https://github.com/nsarafianos/Garment3DGen)
- **Pinned Commit**: `496e113a72a17d263f157c69ada488d633e74e27`
- **Authors**: Nikolaos Sarafianos, Tuur Stuyck, et al. (Meta Reality Labs)
- **License**: **Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC 4.0)**
- **Model Checkpoints**: Wonder3D / InstantMesh checkpoints (Non-commercial research).
- **Commercial Use**: **PROHIBITED** for commercial exploitation without an enterprise license agreement from Meta Reality Labs.
- **Yorvyn Policy**: Retained in `research/upstream/Garment3DGen` as an experimental neural benchmark. Decoupled behind `packages/ai-adapters` so no non-commercial code enters the core SaaS product runtime.

---

## 4. ReMu (Multi-Layer Clothed Human Reconstruction)

- **Upstream Source**: [https://github.com/eth-ait/ReMu](https://github.com/eth-ait/ReMu)
- **Pinned Commit**: `3cf1563e800ca40d08ba269865dc7420507c06ba`
- **Authors**: ETH Zurich Advanced Interactive Technologies Lab (ETH-AIT)
- **Code License**: MIT License (core codebase)
- **Third-Party / Asset Licenses**:
  - SMPL-X (Max Planck Institute): Non-commercial research license.
  - SiTH / UP2You / ContourCraft: Non-commercial academic licenses.
- **Commercial Use**: **RESTRICTED** due to mandatory SMPL-X body model dependencies.
- **Yorvyn Policy**: Isolated under `research/upstream/ReMu`. Serves as an academic reference for boundary extraction and multi-layer clothing separation.
