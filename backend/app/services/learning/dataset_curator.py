"""
YORVYN Intelligence Platform (YIP) — Offline Dataset Curation & PyTorch Learning Pipeline (Phase 17.0 Stage 7).

Provides:
- Dataset manifests with image/payload SHA-256 deduplication
- Identity-group leakage prevention across train / val / holdout splits
- License & explicit consent gating (rejects unconsented private uploads)
- Controlled offline reproducible PyTorch training + holdout evaluation + ECE calibration
- Release bundle creation with checkpoint SHA-256, model card, and NO auto-promotion
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
import time
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from pydantic import BaseModel, Field

from backend.app.services.ai.evaluation.calibration import ConfidenceCalibrator


APPROVED_DATASET_LICENSES = {
    "CC-BY-4.0",
    "CC0-1.0",
    "MIT",
    "Apache-2.0",
    "YORVYN Consented User Upload",
    "YORVYN Internal Verified",
}


class CuratedSample(BaseModel):
    sample_id: str
    identity_group: str  # Garment or user identity group; guarantees zero cross-split leakage
    label: str
    image_sha256: str
    license: str
    consent_verified: bool
    annotation_valid: bool = True
    features: List[float] = Field(default_factory=list)


class DatasetAuditReport(BaseModel):
    dataset_name: str
    dataset_version: str
    manifest_sha256: str
    total_submitted: int
    accepted_count: int
    rejected_no_consent: int
    rejected_invalid_license: int
    rejected_invalid_annotation: int
    duplicates_removed: int
    splits: Dict[str, int]
    leakage_detected: bool
    leakage_groups: List[str] = Field(default_factory=list)
    ready_for_offline_training: bool


class OfflineTrainingReport(BaseModel):
    model_name: str
    version: str
    seed: int
    epochs: int
    train_loss_final: float
    holdout_accuracy: float
    holdout_calibration_ece: Optional[float] = None
    per_category_accuracy: Dict[str, float] = Field(default_factory=dict)
    checkpoint_path: str
    checkpoint_sha256: str
    promoted_to_production: bool = False  # Strictly False: offline runs never auto-promote
    model_card: Dict[str, Any]
    duration_ms: float


class OfflineDatasetCurator:
    """Validates datasets and executes reproducible offline PyTorch fine-tuning runs."""

    @staticmethod
    def audit_and_split(
        samples: List[CuratedSample],
        *,
        dataset_name: str = "yorvyn_curated_garments",
        dataset_version: str = "17.0.0",
        seed: int = 42,
    ) -> TupleResult:
        seen_hashes: set = set()
        accepted: List[CuratedSample] = []
        rej_consent = rej_lic = rej_ann = dups = 0

        for s in samples:
            if not s.consent_verified:
                rej_consent += 1
                continue
            if s.license not in APPROVED_DATASET_LICENSES:
                rej_lic += 1
                continue
            if not s.annotation_valid or not s.label.strip():
                rej_ann += 1
                continue
            if s.image_sha256 in seen_hashes:
                dups += 1
                continue
            seen_hashes.add(s.image_sha256)
            accepted.append(s)

        # Group by identity_group so all views/items from same identity stay together
        groups: Dict[str, List[CuratedSample]] = {}
        for item in accepted:
            groups.setdefault(item.identity_group, []).append(item)

        group_ids = sorted(groups.keys())
        rng = random.Random(seed)
        rng.shuffle(group_ids)

        split_map: Dict[str, List[CuratedSample]] = {"train": [], "val": [], "holdout": []}
        for i, gid in enumerate(group_ids):
            mod = i % 10
            bucket = "holdout" if mod in (8, 9) else ("val" if mod == 7 else "train")
            split_map[bucket].extend(groups[gid])

        # Ensure non-empty holdout & val when >= 3 independent identity groups exist
        if len(group_ids) >= 3 and not split_map["holdout"]:
            last_g = group_ids[-1]
            split_map["holdout"] = [x for b in ("train", "val") for x in split_map[b] if x.identity_group == last_g]
            split_map["train"] = [x for x in split_map["train"] if x.identity_group != last_g]
            split_map["val"] = [x for x in split_map["val"] if x.identity_group != last_g]
        if len(group_ids) >= 3 and not split_map["val"]:
            val_g = group_ids[-2]
            split_map["val"] = [x for x in split_map["train"] if x.identity_group == val_g]
            split_map["train"] = [x for x in split_map["train"] if x.identity_group != val_g]

        # Verify zero identity overlap across splits
        tr_g = {x.identity_group for x in split_map["train"]}
        va_g = {x.identity_group for x in split_map["val"]}
        ho_g = {x.identity_group for x in split_map["holdout"]}
        overlap = sorted((tr_g & va_g) | (tr_g & ho_g) | (va_g & ho_g))

        manifest_bytes = json.dumps(
            [{"id": x.sample_id, "sha": x.image_sha256, "grp": x.identity_group} for x in accepted],
            sort_keys=True,
        ).encode("utf-8")
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()

        report = DatasetAuditReport(
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            manifest_sha256=manifest_sha,
            total_submitted=len(samples),
            accepted_count=len(accepted),
            rejected_no_consent=rej_consent,
            rejected_invalid_license=rej_lic,
            rejected_invalid_annotation=rej_ann,
            duplicates_removed=dups,
            splits={k: len(v) for k, v in split_map.items()},
            leakage_detected=bool(overlap),
            leakage_groups=overlap,
            ready_for_offline_training=(len(split_map["train"]) >= 2 and len(split_map["holdout"]) >= 1 and not overlap),
        )
        return TupleResult(report=report, splits=split_map)

    @staticmethod
    def train_offline_probe(
        splits: Dict[str, List[CuratedSample]],
        *,
        model_name: str = "yorvyn_category_probe_v17",
        version: str = "17.0.0-rc1",
        epochs: int = 12,
        lr: float = 0.05,
        seed: int = 42,
        artifact_dir: Optional[str] = None,
    ) -> OfflineTrainingReport:
        t0 = time.perf_counter()
        train_items = splits.get("train") or []
        holdout_items = splits.get("holdout") or []
        if not train_items or not holdout_items:
            raise ValueError("Both non-empty train and holdout splits are required for offline evaluation.")

        labels = sorted({x.label for x in (train_items + holdout_items)})
        label_to_idx = {lbl: idx for idx, lbl in enumerate(labels)}
        feat_dim = len(train_items[0].features)
        if feat_dim == 0:
            raise ValueError("Feature vectors must be non-empty for probe training.")

        torch.manual_seed(seed)
        np.random.seed(seed)

        x_tr = torch.tensor([s.features for s in train_items], dtype=torch.float32)
        y_tr = torch.tensor([label_to_idx[s.label] for s in train_items], dtype=torch.long)
        x_ho = torch.tensor([s.features for s in holdout_items], dtype=torch.float32)
        y_ho = torch.tensor([label_to_idx[s.label] for s in holdout_items], dtype=torch.long)

        model = nn.Sequential(
            nn.Linear(feat_dim, max(8, len(labels) * 4)),
            nn.ReLU(),
            nn.Linear(max(8, len(labels) * 4), len(labels)),
        )
        opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        loss_fn = nn.CrossEntropyLoss()

        final_loss = 0.0
        model.train()
        for _ in range(max(1, min(epochs, 50))):
            opt.zero_grad()
            logits = model(x_tr)
            loss = loss_fn(logits, y_tr)
            loss.backward()
            opt.step()
            final_loss = float(loss.item())

        model.eval()
        with torch.no_grad():
            ho_logits = model(x_ho)
            probs = torch.softmax(ho_logits, dim=-1)
            confs, preds = torch.max(probs, dim=-1)
            hits = (preds == y_ho).tolist()
            ho_acc = round(float(sum(hits) / len(hits)), 4)

        per_cat: Dict[str, float] = {}
        for lbl, idx in label_to_idx.items():
            mask = [i for i, yv in enumerate(y_ho.tolist()) if yv == idx]
            if mask:
                per_cat[lbl] = round(float(sum(hits[i] for i in mask) / len(mask)), 4)

        ece = ConfidenceCalibrator.compute_ece(confs.tolist(), hits) if len(hits) >= 4 else None

        out_dir = artifact_dir or os.path.join(tempfile.gettempdir(), "yorvyn_offline_models")
        os.makedirs(out_dir, exist_ok=True)
        ckpt_path = os.path.join(out_dir, f"{model_name}_{version}.pt")
        payload = {"state_dict": model.state_dict(), "labels": labels, "feat_dim": feat_dim, "seed": seed}
        torch.save(payload, ckpt_path)
        with open(ckpt_path, "rb") as fh:
            ckpt_sha = hashlib.sha256(fh.read()).hexdigest()

        model_card = {
            "model_name": model_name,
            "version": version,
            "labels": labels,
            "train_samples": len(train_items),
            "holdout_samples": len(holdout_items),
            "holdout_accuracy": ho_acc,
            "calibration_ece": ece,
            "promoted_to_production": False,
            "release_gate_note": "Offline evaluation completed; requires independent human/admin sign-off before production rollout.",
        }
        return OfflineTrainingReport(
            model_name=model_name,
            version=version,
            seed=seed,
            epochs=epochs,
            train_loss_final=round(final_loss, 5),
            holdout_accuracy=ho_acc,
            holdout_calibration_ece=ece,
            per_category_accuracy=per_cat,
            checkpoint_path=ckpt_path,
            checkpoint_sha256=ckpt_sha,
            promoted_to_production=False,
            model_card=model_card,
            duration_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


class TupleResult(BaseModel):
    report: DatasetAuditReport
    splits: Dict[str, List[CuratedSample]]


dataset_curator = OfflineDatasetCurator()
