# Yorvyn Real Fashion Dataset Registry

This registry documents all fashion understanding, garment reconstruction, and aesthetic datasets investigated and integrated for the Yorvyn AI Fashion Stylist platform.

---

## 1. Integrated & Verified Datasets

### 🟢 Zalando Fashion-MNIST
- **Official Custodian**: Zalando Research (`https://github.com/zalandoresearch/fashion-mnist`)
- **Citation**: Han Xiao, Kashif Rasul, Roland Vollgraf. *Fashion-MNIST: a Novel Image Dataset for Benchmarking Machine Learning Algorithms.* arXiv:1708.07747, 2017.
- **License**: **MIT License** (Unrestricted commercial and non-commercial development).
- **Scale**: 70,000 real fashion catalog product items (60,000 training, 10,000 test).
- **Tasks**: Fashion article classification, garment silhouette detection, retrieval benchmarking.
- **Classes**:
  1. `0: T-shirt/top`
  2. `1: Trouser`
  3. `2: Pullover`
  4. `3: Dress`
  5. `4: Coat`
  6. `5: Sandal`
  7. `6: Shirt`
  8: `7: Sneaker`
  9. `8: Bag`
  10. `9: Ankle boot`
- **Yorvyn Status**: **VERIFIED ACQUIRED & ACTIVE IN ML PIPELINE**.
  - Local path: `data/datasets/fashion_mnist/`
  - Manifest: `research/datasets/manifest.json`
  - ML Pipeline: `backend/app/services/ml/fashion_classifier.py`

---

## 2. Cataloged & Gated Datasets

### 🟡 DeepFashion (CUHK Multimedia Lab)
- **Official Source**: [https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html)
- **Scope**: 800,000 diverse fashion images with 50 categories and 1,000 attributes.
- **Licensing Terms**: Strictly restricted to **Non-Commercial Academic Research**.
  - The official terms require signing a written agreement and emailing the CUHK research team.
  - Direct commercial use or training production models for commercial release is strictly prohibited without explicit commercial agreement.
- **Yorvyn Compliance Policy**: **GATED / RESTRICTED**.
  - The dataset will not be ingested into commercial production runtime or committed to version control.
  - Integration remains blocked until formal commercial authorization is obtained.

### 🟡 DeepFashion2 (switchablenorms)
- **Official Source**: [https://github.com/switchablenorms/DeepFashion2](https://github.com/switchablenorms/DeepFashion2)
- **Scope**: 491,000 images with 13 clothing categories, fine-grained landmarks, and commercial retrieval pairs.
- **Licensing Terms**: **Non-Commercial Research Only**.
  - Access requires registration and agreement forms.
- **Yorvyn Compliance Policy**: **GATED / RESTRICTED**.
  - Strictly quarantined from commercial runtime inference.

### 🟡 Fashionpedia
- **Official Source**: [https://fashionpedia.github.io/home/](https://fashionpedia.github.io/home/)
- **Scope**: 48,000 apparel photos with 27 main apparel categories, 19 garment parts, and 294 fine-grained attributes.
- **Licensing Terms**:
  - Annotations & Ontology: **Creative Commons Attribution 4.0 (CC BY 4.0)**.
  - Raw Images: Subject to fair use / web origin terms.
- **Yorvyn Compliance Policy**: **ANNOTATED FOR FUTURE SEGMENTATION**.
  - Permitted for fine-grained garment ontology structuring.
