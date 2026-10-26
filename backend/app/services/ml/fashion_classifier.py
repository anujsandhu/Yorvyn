"""
Yorvyn Fashion Machine Learning Engine.
Implements binary idx-ubyte dataset parsing for real Fashion-MNIST,
training of clothing category classifiers, multi-metric evaluation
(Accuracy, Precision, Recall, F1 score), and checkpoint persistence.
"""

from __future__ import annotations

import json
import os
import pickle
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import classification_report, accuracy_score, precision_recall_fscore_support

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATASET_DIR = REPO_ROOT / "data" / "datasets" / "fashion_mnist"
MODELS_DIR = REPO_ROOT / "models"
CHECKPOINT_PATH = MODELS_DIR / "fashion_classifier.pkl"
METRICS_PATH = MODELS_DIR / "metrics.json"

FASHION_CLASSES = {
    0: "T-shirt/top",
    1: "Trouser",
    2: "Pullover",
    3: "Dress",
    4: "Coat",
    5: "Sandal",
    6: "Shirt",
    7: "Sneaker",
    8: "Bag",
    9: "Ankle boot"
}


def load_mnist_images(filepath: Path) -> np.ndarray:
    """Parses idx3-ubyte binary image file."""
    with open(filepath, "rb") as f:
        magic, num_images, rows, cols = struct.unpack(">IIII", f.read(16))
        if magic != 2051:
            raise ValueError(f"Invalid magic number {magic} in {filepath}")
        image_data = np.frombuffer(f.read(), dtype=np.uint8)
        images = image_data.reshape(num_images, rows * cols)
        return images.astype(np.float32) / 255.0


def load_mnist_labels(filepath: Path) -> np.ndarray:
    """Parses idx1-ubyte binary label file."""
    with open(filepath, "rb") as f:
        magic, num_labels = struct.unpack(">II", f.read(8))
        if magic != 2049:
            raise ValueError(f"Invalid magic number {magic} in {filepath}")
        labels = np.frombuffer(f.read(), dtype=np.uint8)
        return labels


def load_dataset(dataset_dir: Path = DATASET_DIR) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Loads training and testing splits of Fashion-MNIST."""
    train_images_path = dataset_dir / "train-images-idx3-ubyte"
    train_labels_path = dataset_dir / "train-labels-idx1-ubyte"
    test_images_path = dataset_dir / "t10k-images-idx3-ubyte"
    test_labels_path = dataset_dir / "t10k-labels-idx1-ubyte"

    if not all(p.exists() for p in [train_images_path, train_labels_path, test_images_path, test_labels_path]):
        raise FileNotFoundError(f"One or more Fashion-MNIST ubyte files missing in {dataset_dir}. Run scripts/acquire_fashion_dataset.py first.")

    X_train = load_mnist_images(train_images_path)
    y_train = load_mnist_labels(train_labels_path)
    X_test = load_mnist_images(test_images_path)
    y_test = load_mnist_labels(test_labels_path)

    return X_train, y_train, X_test, y_test


class FashionMLClassifier:
    """Scikit-Learn based lightweight fashion classifier optimized for Apple Silicon."""

    def __init__(self):
        self.model = None
        self.metrics = None
        self.load_checkpoint_if_exists()

    def train_and_evaluate(self, max_train_samples: int = 15000) -> Dict[str, Any]:
        """
        Trains SGD classifier with log_loss (logistic regression) on real fashion dataset.
        Evaluates on full 10,000 held-out test records.
        """
        print(f"Loading Fashion-MNIST from {DATASET_DIR}...")
        X_train, y_train, X_test, y_test = load_dataset()

        # Subsample training set if specified for fast, interactive training on 8GB RAM
        if max_train_samples and max_train_samples < len(X_train):
            indices = np.random.RandomState(42).choice(len(X_train), max_train_samples, replace=False)
            X_train_sub = X_train[indices]
            y_train_sub = y_train[indices]
        else:
            X_train_sub = X_train
            y_train_sub = y_train

        print(f"Training on {len(X_train_sub)} samples, evaluating on {len(X_test)} test samples...")
        start_time = time.time()

        # SGD Classifier with modified Huber loss for calibrated probabilistic classification
        clf = SGDClassifier(
            loss="modified_huber",
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            random_state=42,
            n_jobs=-1
        )
        clf.fit(X_train_sub, y_train_sub)
        duration = round(time.time() - start_time, 2)

        # Predict on held-out test split
        y_pred = clf.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")

        report = classification_report(
            y_test,
            y_pred,
            target_names=[FASHION_CLASSES[i] for i in range(10)],
            output_dict=True
        )

        metrics = {
            "model_type": "SGDClassifier (Modified Huber / Linear Probabilistic)",
            "training_samples": len(X_train_sub),
            "test_samples": len(X_test),
            "training_duration_seconds": duration,
            "accuracy": round(acc, 4),
            "weighted_precision": round(float(precision), 4),
            "weighted_recall": round(float(recall), 4),
            "weighted_f1_score": round(float(f1), 4),
            "per_class_report": {
                name: {
                    "precision": round(stats["precision"], 4),
                    "recall": round(stats["recall"], 4),
                    "f1_score": round(stats["f1-score"], 4),
                    "support": stats["support"]
                }
                for name, stats in report.items() if isinstance(stats, dict)
            }
        }

        self.model = clf
        self.metrics = metrics
        self.save_checkpoint()
        return metrics

    def predict(self, pixel_array: np.ndarray) -> Dict[str, Any]:
        """Predicts clothing category for a 28x28 grayscale image normalized to [0, 1]."""
        if self.model is None:
            raise RuntimeError("Model is not trained. Call train_and_evaluate() first.")

        flat = pixel_array.reshape(1, -1)
        probs = self.model.predict_proba(flat)[0]
        top_idx = int(np.argmax(probs))

        top_3 = sorted(
            [{"class_id": i, "category": FASHION_CLASSES[i], "confidence": round(float(probs[i]), 4)} for i in range(10)],
            key=lambda x: x["confidence"],
            reverse=True
        )[:3]

        return {
            "predicted_category": FASHION_CLASSES[top_idx],
            "confidence": round(float(probs[top_idx]), 4),
            "top_candidates": top_3
        }

    def save_checkpoint(self):
        """Persists trained model and evaluation report to models/ directory."""
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(CHECKPOINT_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2)
        print(f"✓ Model checkpoint saved to {CHECKPOINT_PATH}")
        print(f"✓ Evaluation report saved to {METRICS_PATH}")

    def load_checkpoint_if_exists(self):
        """Loads existing model checkpoint from disk if present."""
        if CHECKPOINT_PATH.exists() and METRICS_PATH.exists():
            try:
                with open(CHECKPOINT_PATH, "rb") as f:
                    self.model = pickle.load(f)
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
            except Exception as e:
                print(f"Warning: could not load checkpoint: {e}")


fashion_ml_classifier = FashionMLClassifier()

if __name__ == "__main__":
    metrics = fashion_ml_classifier.train_and_evaluate()
    print("\n═════════════════════════════════════════════════════════════════════")
    print(f" 🎯 FASHION CLASSIFIER EVALUATION REPORT")
    print("═════════════════════════════════════════════════════════════════════")
    print(f"Accuracy:  {metrics['accuracy'] * 100:.2f}%")
    print(f"F1-Score:  {metrics['weighted_f1_score'] * 100:.2f}%")
    print(f"Precision: {metrics['weighted_precision'] * 100:.2f}%")
    print(f"Recall:    {metrics['weighted_recall'] * 100:.2f}%")
