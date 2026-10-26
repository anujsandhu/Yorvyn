# Yorvyn AI Model Licensing, Provenance & Compliance

## 1. Governance Principles

1. **Lawful Dataset Acquisition**: Yorvyn only trains or evaluates on datasets whose source terms explicitly permit the intended task.
2. **Attribution & Provenance**: All models, weights, and datasets document their original author, license, and version.
3. **Quarantine of Non-Commercial Data**: Datasets with Non-Commercial restrictions (such as DeepFashion) are strictly quarantined from commercial production runtime and inference artifacts.
4. **User Privacy**: Private user photographs uploaded for garment generation or styling are ephemeral; they are never added to model training corpora without explicit, informed consent.

---

## 2. Permitted & Restricted Datasets

| Dataset | License | Permitted Commercial ML | Action in Yorvyn |
| :--- | :--- | :--- | :--- |
| **Zalando Fashion-MNIST** | MIT License | YES | Ingested, evaluated, and deployed in classification services. |
| **DeepFashion** | Non-Commercial Research Form | NO | Quarantined; cataloged in `research/datasets/registry.md` as restricted. |
| **DeepFashion2** | Non-Commercial Research Form | NO | Quarantined; cataloged as restricted. |
| **Fashionpedia** | Annotations: CC BY 4.0 | Conditionally (Annotations only) | Used for taxonomy schema definitions. |
