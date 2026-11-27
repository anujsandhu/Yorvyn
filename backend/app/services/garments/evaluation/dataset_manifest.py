"""Strict sample-level dataset validation for garment reconstruction evaluation.

The loader is intentionally fail-closed: only locally present, hash-verified assets
with explicit rights and consent evidence can enter a verified dataset.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = "1.0.0"
SPLITS = {"training", "calibration", "holdout"}
VIEWS = {"front", "back", "left", "right", "three_quarter", "unknown"}
EVALUATION_STATES = {
    "NOT_EVALUATED", "SYNTHETIC_SMOKE_ONLY", "REAL_DATASET_INCOMPLETE",
    "PROVENANCE_INVALID", "SPLIT_INTEGRITY_FAILED", "READY_FOR_REAL_EVALUATION",
    "REAL_EVALUATION_COMPLETED",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_identity_splits(
    garment_identity_ids: Iterable[str], seed: str = "yorvyn-eval-v1",
    proportions: Optional[Dict[str, float]] = None,
) -> Dict[str, str]:
    """Return stable identity assignments. This never edits a manifest."""
    weights = proportions or {"training": 0.7, "calibration": 0.15, "holdout": 0.15}
    if set(weights) != SPLITS or any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError("Split proportions must define training/calibration/holdout and sum to 1")
    cumulative = []
    acc = 0.0
    for split in ("training", "calibration", "holdout"):
        acc += weights[split]
        cumulative.append((acc, split))
    assignments = {}
    for identity in sorted(set(garment_identity_ids)):
        if not identity:
            raise ValueError("Garment identity IDs must be non-empty")
        fraction = int(hashlib.sha256(f"{seed}:{identity}".encode()).hexdigest()[:16], 16) / float(0xFFFFFFFFFFFFFFFF)
        assignments[identity] = next(split for bound, split in cumulative if fraction <= bound)
    return assignments


class GarmentEvaluationDataset:
    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path).resolve()
        self.root = self.manifest_path.parent
        self.data: Dict[str, Any] = {}
        self.validation_report: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        try:
            self.data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.validation_report = self._empty_report([f"manifest_read_error:{exc}"])
            return self.validation_report
        self.validation_report = self.validate()
        return self.validation_report

    def _empty_report(self, failures: List[str]) -> Dict[str, Any]:
        return {"evaluation_state": "REAL_DATASET_INCOMPLETE", "total_samples": 0,
                "verified_samples": 0, "rejected_samples": 0, "failures": failures,
                "category_distribution": {}, "view_distribution": {}, "split_distribution": {},
                "coverage": {"reference_geometry": 0, "reference_masks": 0, "landmarks": 0, "components": 0, "license": 0, "consent": 0},
                "identity_overlap": {}, "duplicate_image_hashes": [], "missing_assets": []}

    def _asset(self, ref: Any, sample_id: str, field: str, failures: List[str], missing: List[str]) -> Optional[Path]:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            failures.append(f"{sample_id}:{field}:asset_reference_invalid")
            return None
        path = (self.root / ref["path"]).resolve()
        if self.root not in path.parents and path != self.root:
            failures.append(f"{sample_id}:{field}:path_outside_dataset_root")
            return None
        if not path.is_file():
            failures.append(f"{sample_id}:{field}:asset_missing")
            missing.append(str(path))
            return None
        actual = _sha256(path)
        if actual.lower() != ref["sha256"].lower():
            failures.append(f"{sample_id}:{field}:sha256_mismatch")
            return None
        return path

    def validate(self) -> Dict[str, Any]:
        d = self.data
        failures: List[str] = []
        missing: List[str] = []
        samples = d.get("samples") if isinstance(d, dict) else None
        if not isinstance(d, dict) or d.get("schema_version") != SCHEMA_VERSION or not isinstance(samples, list):
            return self._empty_report(["manifest_schema_invalid"])
        if d.get("dataset_kind") == "synthetic":
            return {**self._empty_report([]), "evaluation_state": "SYNTHETIC_SMOKE_ONLY", "total_samples": len(samples)}
        seen_ids: set[str] = set()
        identity_splits: Dict[str, set] = defaultdict(set)
        hash_samples: Dict[str, List[str]] = defaultdict(list)
        verified = []
        category_counts, view_counts, split_counts = Counter(), Counter(), Counter()
        coverage = Counter()
        rejected = []
        for sample in samples:
            local: List[str] = []
            if not isinstance(sample, dict):
                failures.append("<invalid>:sample_must_be_object")
                rejected.append("<invalid>")
                continue
            sid = sample.get("sample_id")
            sid = sid if isinstance(sid, str) else "<invalid>"
            if sid in seen_ids:
                local.append(f"{sid}:duplicate_sample_id")
            seen_ids.add(sid)
            identity = sample.get("garment_identity_id")
            split = sample.get("split")
            if not identity or split not in SPLITS:
                local.append(f"{sid}:identity_or_split_invalid")
            elif isinstance(identity, str):
                identity_splits[identity].add(split)
            category_counts[str(sample.get("category", "unknown"))] += 1
            split_counts[str(split)] += 1
            views = sample.get("views")
            if not isinstance(views, list) or not views:
                local.append(f"{sid}:views_missing")
                views = []
            view_types = set()
            for view in views:
                if not isinstance(view, dict) or view.get("view_type") not in VIEWS:
                    local.append(f"{sid}:view_invalid")
                    continue
                if view["view_type"] in view_types and view["view_type"] != "unknown":
                    local.append(f"{sid}:duplicate_view")
                view_types.add(view["view_type"])
                view_counts[view["view_type"]] += 1
                image_path = self._asset(view.get("image"), sid, "image", local, missing)
                if image_path:
                    image_hash = view["image"]["sha256"].lower()
                    hash_samples[image_hash].append(sid)
                    try:
                        from PIL import Image
                        with Image.open(image_path) as image:
                            image.verify()
                        with Image.open(image_path) as image:
                            expected = view.get("dimensions")
                            if expected != {"width": image.width, "height": image.height}:
                                local.append(f"{sid}:image_dimensions_mismatch")
                    except Exception:
                        local.append(f"{sid}:image_decode_failed")
                camera = view.get("camera")
                if camera is not None and (not isinstance(camera, dict) or not all(k in camera for k in ("intrinsics", "extrinsics"))):
                    local.append(f"{sid}:camera_metadata_invalid")
            provenance = sample.get("provenance", {})
            license_info = provenance.get("license", {}) if isinstance(provenance, dict) else {}
            consent = provenance.get("consent", {}) if isinstance(provenance, dict) else {}
            license_ok = (
                isinstance(license_info, dict)
                and license_info.get("license_id")
                and license_info.get("source_url")
                and license_info.get("evaluation_allowed") is True
                and isinstance(license_info.get("redistribution_allowed"), bool)
                and isinstance(license_info.get("attribution_required"), bool)
                and "restrictions" in license_info
            )
            if license_ok and license_info.get("expires_at"):
                try:
                    license_ok = date.fromisoformat(license_info["expires_at"]) >= date.today()
                except (TypeError, ValueError):
                    license_ok = False
            if not license_ok:
                local.append(f"{sid}:license_provenance_invalid")
            else:
                coverage["license"] += 1
            if not (isinstance(consent, dict) and consent.get("evidence_id") and consent.get("evaluation_allowed") is True):
                local.append(f"{sid}:consent_provenance_invalid")
            else:
                coverage["consent"] += 1
            annotations = sample.get("annotations", {})
            status = annotations.get("status") if isinstance(annotations, dict) else None
            if status != "complete":
                local.append(f"{sid}:annotations_incomplete")
            elif not annotations.get("annotation_owner") or not annotations.get("provenance"):
                local.append(f"{sid}:annotation_provenance_invalid")
            for key, coverage_key in (("landmarks", "landmarks"), ("components", "components")):
                values = annotations.get(key) if isinstance(annotations, dict) else None
                if isinstance(values, list) and values:
                    coverage[coverage_key] += 1
                else:
                    local.append(f"{sid}:{key}_missing")
            geometry = sample.get("reference_geometry")
            if isinstance(geometry, dict) and geometry.get("asset"):
                if self._asset(geometry["asset"], sid, "reference_geometry", local, missing):
                    coverage["reference_geometry"] += 1
            else:
                local.append(f"{sid}:reference_geometry_missing")
            masks = sample.get("reference_masks", [])
            valid_masks = 0
            if isinstance(masks, list):
                for mask in masks:
                    if self._asset(mask.get("asset") if isinstance(mask, dict) else None, sid, "reference_mask", local, missing):
                        valid_masks += 1
            if valid_masks:
                coverage["reference_masks"] += 1
            if local:
                failures.extend(local)
                rejected.append(sid)
            else:
                verified.append(sample)
        overlaps = {identity: sorted(splits) for identity, splits in identity_splits.items() if len(splits) > 1}
        duplicate_hashes = sorted(h for h, ids in hash_samples.items() if len(set(ids)) > 1)
        if overlaps:
            failures.append("garment_identity_cross_split_leakage")
        if duplicate_hashes:
            failures.append("duplicate_image_hash_leakage")
        state = "READY_FOR_REAL_EVALUATION" if samples and len(verified) == len(samples) and not failures else "REAL_DATASET_INCOMPLETE"
        return {"evaluation_state": state, "total_samples": len(samples), "verified_samples": len(verified),
                "rejected_samples": len(rejected), "rejected_sample_ids": rejected, "failures": failures,
                "category_distribution": dict(category_counts), "view_distribution": dict(view_counts),
                "split_distribution": dict(split_counts), "coverage": dict(coverage),
                "identity_overlap": overlaps, "duplicate_image_hashes": duplicate_hashes,
                "missing_assets": missing, "verified_sample_ids": [s["sample_id"] for s in verified]}

    def evaluation_gate(self, metric: str, split: str = "holdout") -> Dict[str, Any]:
        report = self.validation_report or self.load()
        if report["evaluation_state"] == "SYNTHETIC_SMOKE_ONLY":
            return {"evaluation_state": "SYNTHETIC_SMOKE_ONLY", "allowed": False, "metric": metric}
        if report["evaluation_state"] != "READY_FOR_REAL_EVALUATION":
            return {"evaluation_state": report["evaluation_state"], "allowed": False, "metric": metric,
                    "failures": report["failures"]}
        selected = [s for s in self.data["samples"] if s.get("split") == split]
        requirements = {
            "geometry": lambda s: bool((s.get("reference_geometry") or {}).get("asset")),
            "silhouette": lambda s: bool(s.get("reference_masks")),
            "landmarks": lambda s: bool((s.get("annotations") or {}).get("landmarks")),
            "components": lambda s: bool((s.get("annotations") or {}).get("components")),
        }
        if metric not in requirements or not selected or any(not requirements[metric](s) for s in selected):
            return {"evaluation_state": "REAL_DATASET_INCOMPLETE", "allowed": False, "metric": metric,
                    "reason": "metric_reference_requirements_not_met"}
        return {"evaluation_state": "READY_FOR_REAL_EVALUATION", "allowed": True, "metric": metric, "sample_count": len(selected)}

    def write_report(self, output_path: str | Path) -> None:
        report = self.validation_report or self.load()
        Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
