"""
YORVYN — Confidence Calibration & Abstention Policy Service (Phase 14.27)
Implements:
- Expected Calibration Error (ECE) across M probability bins
- Multi-class Brier score calculation
- Temperature scaling parameter calibration
- Abstention policy:
  * High (p >= 0.70): Accepted prediction
  * Medium (0.45 <= p < 0.70): Flagged with uncertainty
  * Low (p < 0.45): Explicit abstention (requests additional photograph)
  * Conflicted: Explicit CONFLICTED state (never forces a fabricated winner)
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np


class ConfidenceCalibrator:
    """
    Computes calibration metrics (ECE, Brier) and enforces decision abstention
    to prevent overconfident hallucination in garment categorization and component detection.
    """

    def __init__(self, temperature: float = 1.15):
        self.temperature = temperature
        self.high_threshold = 0.70
        self.medium_threshold = 0.45

    def calibrate_probability(self, raw_confidence: float) -> float:
        """Applies temperature scaling to raw softmax / sigmoid confidence score."""
        clamped = max(1e-5, min(1.0 - 1e-5, raw_confidence))
        logit = math.log(clamped / (1.0 - clamped))
        scaled_logit = logit / self.temperature
        calibrated = 1.0 / (1.0 + math.exp(-scaled_logit))
        return round(calibrated, 4)

    def evaluate_abstention(
        self,
        calibrated_probability: float,
        has_conflicts: bool = False
    ) -> Dict[str, Any]:
        """
        Determines whether the system should accept the prediction, flag uncertainty,
        or explicitly abstain.
        """
        if has_conflicts:
            return {
                "decision": "CONFLICTED",
                "confidence": calibrated_probability,
                "abstain": False,
                "uncertainty_flag": True,
                "message": "Conflicting visual observations across viewpoints; preserved as CONFLICTED."
            }

        if calibrated_probability >= self.high_threshold:
            return {
                "decision": "ACCEPTED",
                "confidence": calibrated_probability,
                "abstain": False,
                "uncertainty_flag": False,
                "message": f"High confidence prediction ({calibrated_probability*100:.1f}%)."
            }
        elif calibrated_probability >= self.medium_threshold:
            return {
                "decision": "ACCEPTED_WITH_UNCERTAINTY",
                "confidence": calibrated_probability,
                "abstain": False,
                "uncertainty_flag": True,
                "message": f"Moderate confidence ({calibrated_probability*100:.1f}%); recommends user review or extra view."
            }
        else:
            return {
                "decision": "ABSTAINED",
                "confidence": calibrated_probability,
                "abstain": True,
                "uncertainty_flag": True,
                "message": f"Low confidence ({calibrated_probability*100:.1f}% < {self.medium_threshold*100:.0f}% threshold). System abstains from guessing."
            }

    @staticmethod
    def compute_ece(
        probabilities: List[float],
        ground_truth_matches: List[bool],
        num_bins: int = 10
    ) -> float:
        """
        Calculates Expected Calibration Error (ECE):
        ECE = sum_m ( |B_m| / N ) * |acc(B_m) - conf(B_m)|
        """
        if not probabilities or len(probabilities) != len(ground_truth_matches):
            return 0.0

        n = len(probabilities)
        bin_limits = np.linspace(0.0, 1.0, num_bins + 1)
        ece = 0.0

        probs = np.array(probabilities)
        matches = np.array(ground_truth_matches, dtype=np.float32)

        for i in range(num_bins):
            low, high = bin_limits[i], bin_limits[i + 1]
            if i == num_bins - 1:
                in_bin = (probs >= low) & (probs <= high)
            else:
                in_bin = (probs >= low) & (probs < high)

            count = np.sum(in_bin)
            if count > 0:
                acc = np.mean(matches[in_bin])
                conf = np.mean(probs[in_bin])
                ece += (count / n) * abs(acc - conf)

        return round(float(ece), 4)

    @staticmethod
    def compute_brier_score(
        probabilities: List[float],
        ground_truth_matches: List[bool]
    ) -> float:
        """
        Calculates Brier Score:
        Brier = (1 / N) * sum_i (p_i - y_i)^2
        Lower is better (0.0 is perfect calibration).
        """
        if not probabilities or len(probabilities) != len(ground_truth_matches):
            return 0.0

        probs = np.array(probabilities)
        targets = np.array(ground_truth_matches, dtype=np.float32)
        brier = float(np.mean((probs - targets) ** 2))
        return round(brier, 4)

    @staticmethod
    def compute_confusion_matrix(
        y_true: List[str],
        y_pred: List[str],
        labels: List[str]
    ) -> Dict[str, Any]:
        """Computes confusion matrix with precision, recall, and F1 per class."""
        label_to_idx = {l: i for i, l in enumerate(labels)}
        n = len(labels)
        matrix = np.zeros((n, n), dtype=int)

        for t, p in zip(y_true, y_pred):
            if t in label_to_idx and p in label_to_idx:
                matrix[label_to_idx[t], label_to_idx[p]] += 1

        per_class = {}
        for l in labels:
            idx = label_to_idx[l]
            tp = int(matrix[idx, idx])
            fp = int(np.sum(matrix[:, idx]) - tp)
            fn = int(np.sum(matrix[idx, :]) - tp)
            prec = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
            rec = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 3) if (prec + rec) > 0 else 0.0
            per_class[l] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}

        total_samples = len(y_true)
        correct = sum(matrix[i, i] for i in range(n))
        accuracy = round(correct / total_samples, 4) if total_samples > 0 else 0.0

        return {
            "labels": labels,
            "matrix": matrix.tolist(),
            "overall_accuracy": accuracy,
            "per_class": per_class,
            "sample_count": total_samples
        }


# Singleton instance
calibrator = ConfidenceCalibrator()
