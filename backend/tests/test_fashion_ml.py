"""
Unit and Integration Tests for Real Fashion Dataset Loader and ML Classifier.
Executes directly without requiring external HTTP client libraries.
"""

import numpy as np
import pytest

from backend.app.services.ml.fashion_classifier import (
    fashion_ml_classifier,
    load_dataset,
    FASHION_CLASSES,
    METRICS_PATH
)
from backend.app.api.fashion_routes import get_fashion_ml_metrics


def test_fashion_dataset_loader():
    """Validates real dataset parsing and array dimensions."""
    X_train, y_train, X_test, y_test = load_dataset()

    assert X_train.shape == (60000, 784)
    assert y_train.shape == (60000,)
    assert X_test.shape == (10000, 784)
    assert y_test.shape == (10000,)

    # Verify normalization range [0, 1]
    assert np.min(X_train) >= 0.0
    assert np.max(X_train) <= 1.0


def test_fashion_ml_prediction():
    """Validates real ML prediction on dummy 28x28 garment tensor."""
    dummy_input = np.ones((28, 28), dtype=np.float32) * 0.5
    res = fashion_ml_classifier.predict(dummy_input)

    assert "predicted_category" in res
    assert res["predicted_category"] in FASHION_CLASSES.values()
    assert 0.0 <= res["confidence"] <= 1.0
    assert len(res["top_candidates"]) == 3


def test_fashion_ml_metrics_endpoint():
    """Validates get_fashion_ml_metrics handler returns real benchmark data."""
    data = get_fashion_ml_metrics()

    assert "accuracy" in data
    assert data["accuracy"] > 0.70  # Baseline accuracy exceeds 70%
    assert data["test_samples"] == 10000
    assert "per_class_report" in data
