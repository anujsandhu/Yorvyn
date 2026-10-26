# Yorvyn Dataset Ingestion & Evaluation Pipeline

## 1. Overview & Principles

Yorvyn integrates real-world fashion datasets to evaluate and power fashion intelligence tasks:
- **Zero Synthetic Datasets**: All datasets originate from authorized, genuine fashion catalogs and repositories.
- **Hardware Optimization**: Built specifically to execute smoothly on Apple Silicon (M2 with 8GB unified memory), avoiding multi-gigabyte memory bloat and CUDA lock-in.
- **Strict Separation of Storage**:
  - `data/datasets/`: Read-only verified dataset files.
  - `models/`: Saved model weights, checkpoints, and evaluation metrics (`metrics.json`).
  - `uploads/`: Ephemeral user uploads, strictly deleted post-inference.

---

## 2. Ingestion & Preprocessing Architecture

```text
Official Repository (GitHub / Hugging Face)
                   │
                   ▼ (SHA-256 Checksum Verification)
         `data/datasets/fashion_mnist/`
                   │
                   ▼ (Binary idx-ubyte parser)
         `backend/app/services/ml/fashion_classifier.py`
                   │
                   ├───────────► Feature Extraction (Normalized Grayscale 28x28)
                   │
                   ▼
     Multiclass Classifier Baseline (scikit-learn SGD / Logistic Regression)
                   │
                   ▼
         `models/fashion_classifier.pkl` & `models/metrics.json`
```

---

## 3. Evaluation Metrics & Task Definition

### Task: 10-Class Fashion Article Categorization
- **Inputs**: 28x28 pixel intensity arrays normalized to `[0, 1]`.
- **Outputs**: Discrete probabilities across 10 fashion categories:
  - Tops (T-shirt, Pullover, Coat, Shirt)
  - Bottoms (Trouser)
  - One-Piece (Dress)
  - Footwear (Sandal, Sneaker, Ankle boot)
  - Accessories (Bag)
- **Primary Metrics**:
  - Top-1 Classification Accuracy
  - Weighted Precision, Recall, and Macro F1-Score
  - Per-class confusion performance
