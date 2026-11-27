# Yorvyn Fashion Intelligence: Datasets & Pretrained Models Audit

This document records the official audit of fashion computer vision datasets, 3D body pose datasets, and pretrained representation models evaluated for the Yorvyn AI Personalized Fashion Intelligence platform (ML Phase 1).

---

## 1. Fashion Vision & Clothing Analysis Datasets

### A. Fashion-MNIST
- **Official Source**: [Zalando Research GitHub](https://github.com/zalandoresearch/fashion-mnist)
- **Version**: 1.0 (70,000 28x28 grayscale images across 10 clothing categories)
- **License**: MIT License
- **Commercial Use**: Permitted without restriction.
- **Access Requirements**: Publicly downloadable directly via HTTP/binary stream.
- **Download Status**: **Downloaded and verified in repository** (`data/datasets/fashion_mnist/`). Binary files: `train-images-idx3-ubyte` (47 MB), `t10k-images-idx3-ubyte` (7.8 MB).
- **Intended ML Task**: Baseline garment category classification, unit test verification, and CI/CD model checkpoint training (`models/fashion_classifier.pkl`).
- **Trained Status**: Trained and evaluated in Phase 11/12 with metrics recorded in `models/metrics.json` (Accuracy: 84.4%, Weighted F1: 84.3%).

---

### B. DeepFashion (Category & Attribute Prediction Benchmark)
- **Official Source**: Multimedia Laboratory, The Chinese University of Hong Kong ([CUHK MMLab](http://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html))
- **Version**: v1.0 (800,000 diverse fashion images with 50 categories and 1,000 attributes)
- **License**: Non-Commercial Academic Research Agreement (MMLab License).
- **Commercial Use**: **Restricted / Non-Commercial Only**. Commercial deployment requires custom institutional licensing from CUHK.
- **Access Requirements**: Academic email verification and signed agreement form submitted to MMLab.
- **Download Status**: Audited; not downloaded into root repo due to 35GB size and commercial license limitations.
- **Intended ML Task**: Fine-grained attribute prediction (materials, necklines, sleeve lengths) and consumer-to-shop retrieval.
- **Integration Strategy**: Pretrained weights fine-tuned on permissive subsets or synthetic anchors; production commercial pipelines utilize open-permissive models.

---

### C. DeepFashion2
- **Official Source**: [DeepFashion2 Consortium / CVPR 2019](https://github.com/switchablenorms/DeepFashion2)
- **Version**: 2.0 (491,000 clothing images with 13 categories, 801k clothing items with landmarks and per-pixel masks)
- **License**: DeepFashion2 Academic License.
- **Commercial Use**: Non-Commercial. Commercial usage requires formal license authorization.
- **Access Requirements**: Registration form submission.
- **Download Status**: Audited; evaluated for garment keypoints and landmark detection.
- **Intended ML Task**: Landmark detection for 3D garment fitting and mesh boundary deformation.

---

### D. Fashionpedia
- **Official Source**: [Fashionpedia (CVPR 2020)](https://fashionpedia.github.io/home/)
- **Version**: 1.0 (48,825 images, 342,000 apparel instances with 46 apparel categories and 294 fine-grained attribute types)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0) for annotations; images under original Flickr licenses.
- **Commercial Use**: Permitted under CC BY 4.0 with attribution, subject to individual image license checks.
- **Access Requirements**: Open access via AWS S3 / Google Drive public mirrors.
- **Download Status**: Evaluated for localized attribute tagging (buttons, collars, pleats).
- **Intended ML Task**: Detailed garment attribute parsing and segment-level material extraction.

---

## 2. 3D Body Structure & Pose Datasets

### A. SMPL & SMPL-X (Skinned Multi-Person Linear Model)
- **Official Source**: Max Planck Institute for Intelligent Systems ([SMPL-X Project](https://smpl-x.is.tue.mpg.de/))
- **Version**: SMPL-X 2020 (v1.1)
- **License**: Non-Commercial Research License. Commercial license available via Amazon/Meshcapade.
- **Commercial Use**: Prohibited without a commercial license from Meshcapade GmbH.
- **Access Requirements**: Account creation and non-commercial license click-through.
- **Download Status**: Audited for parametric body proportion mapping.
- **Integration Strategy in Yorvyn**: Yorvyn uses an independent, custom parametric bone-rig deformation system (`frontend/src/engine/ara/core/`) and mathematical anthropometric proportion ratios (Model A) rather than distributing proprietary SMPL binary weights.

---

### B. COCO (Common Objects in Context - Keypoints)
- **Official Source**: [COCO Consortium](https://cocodataset.org/)
- **Version**: 2017 Keypoints (150,000+ person instances with 17 body keypoints)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Commercial Use**: Permitted with attribution.
- **Access Requirements**: Open download.
- **Download Status**: Pretrained keypoint detectors available via open weights (e.g. YOLOv8-pose, MoveNet).
- **Intended ML Task**: 2D body proportion extraction from uploaded reference photos.

---

## 3. Pretrained Visual & Multimodal Embedding Backbones

### A. OpenAI CLIP (Contrastive Language-Image Pre-Training)
- **Model Versions**: `ViT-B/32`, `ViT-L/14` (OpenCLIP / HuggingFace `openai/clip-vit-base-patch32`)
- **License**: MIT License
- **Commercial Use**: Fully permitted for commercial production.
- **Access Requirements**: Open download via HuggingFace Hub / PyTorch.
- **Resource Footprint**: ~350MB VRAM/RAM for ViT-B/32. Well within 8GB RAM host constraints.
- **Intended ML Task**: Zero-shot clothing classification, cross-modal text-to-clothing search, and 64-dimensional semantic embedding generation.
- **Integration Status**: Model C visual semantic embedding architecture (`fashion_vision.py`) mirrors the 64-d normalized projection of lightweight vision transformers.

---

### B. Meta DINOv2 (Self-Supervised Vision Transformer)
- **Model Versions**: `dinov2_vits14` (Small: 21M parameters, ~85MB)
- **License**: Apache 2.0
- **Commercial Use**: Permitted.
- **Intended ML Task**: Dense garment feature clustering, fabric texture extraction without requiring labeled annotations.

---

## 4. Hardware & Resource Budget Compliance (8GB RAM Host)

| Component | Target Model / Approach | Memory Footprint | Inference Latency | Cost |
| :--- | :--- | :--- | :--- | :--- |
| **Model A: Body Intelligence** | Analytical Anthropometrics | < 5 MB | < 2 ms | \$0.00 |
| **Model B: Skin & Colour** | Colorimetric CIELAB/RGB | < 5 MB | < 1 ms | \$0.00 |
| **Model C: Fashion Vision** | Normalized 64-d Embeddings | < 20 MB | < 15 ms | \$0.00 |
| **Model D: Wardrobe Graph** | Pairwise Compatibility Matrix | < 10 MB | < 5 ms | \$0.00 |
| **Model E: Preference Model** | Calibrated Interaction Matrix | < 5 MB | < 2 ms | \$0.00 |
| **Model F: Outfit Ranker** | 10-Factor Composite Scorer | < 10 MB | < 10 ms | \$0.00 |
| **LLM Reasoning Engine** | Groq Llama 3.3 70B / Gemini Flash | Cloud API / 0 MB Local | 250-700 ms | ~\$0.0008 / turn |
| **LLM Offline Safeguard** | Haute Couture Rule Engine | < 10 MB | < 5 ms | \$0.00 |

