"""
YORVYN Intelligence Platform (YIP) — Phase 17.4 Owner-Safe Live Experimentation Framework.

Provides:
- Deterministic owner-hashed experiment bucket assignment (respecting consent opt-outs)
- Impression, click, save, dismissal, and authorized purchase logging
- Arm-level acceptance rate, unique category diversity, & statistical power validation
  (never claims A/B significance below minimum sample size requirements)
"""
from __future__ import annotations

import hashlib
import math
import threading
import time
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from backend.app.services.intelligence.recommendation_profile import recommendation_profile_store

MIN_IMPRESSIONS_FOR_POWER = 100


class ExperimentImpression(BaseModel):
    impression_id: str
    experiment_id: str
    arm: str
    owner_id: str
    recommended_item_ids: List[str]
    recommended_categories: List[str]
    timestamp_s: float


class ExperimentOutcome(BaseModel):
    impression_id: str
    owner_id: str
    item_id: str
    outcome_type: str  # click | save | like | dismiss | purchase
    purchase_authorized: bool = False
    timestamp_s: float


class ArmAnalytics(BaseModel):
    arm: str
    impressions: int
    clicks: int
    saves: int
    dismissals: int
    authorized_purchases: int
    acceptance_rate: float
    mean_category_diversity: float


class ExperimentReport(BaseModel):
    experiment_id: str
    total_impressions: int
    min_impressions_per_arm_required: int = MIN_IMPRESSIONS_FOR_POWER
    statistically_powered: bool
    power_note: str
    arms: Dict[str, ArmAnalytics] = Field(default_factory=dict)


class RecommendationExperimentManager:
    """Owner-isolated consent-aware recommendation A/B & shadow traffic coordinator."""

    DEFAULT_EXPERIMENT_ID = "rec_v17_4_hybrid_vs_neural_shadow"
    ARMS = ("control_hybrid", "neural_hybrid_shadow", "exploration_boosted")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._impressions: Dict[str, ExperimentImpression] = {}
        self._outcomes: List[ExperimentOutcome] = []

    def assign_arm(
        self,
        *,
        owner_id: str,
        experiment_id: str = DEFAULT_EXPERIMENT_ID,
    ) -> Dict[str, Any]:
        uid = str(owner_id)
        consent = recommendation_profile_store.get_consent(uid)
        if not consent:
            return {
                "experiment_id": experiment_id,
                "owner_id": uid,
                "consent_granted": False,
                "assigned_arm": "control_unpersonalized",
                "reason": "Consent disabled; owner excluded from personalized treatment arms.",
            }
        digest = hashlib.sha256(f"{experiment_id}:{uid}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % len(self.ARMS)
        return {
            "experiment_id": experiment_id,
            "owner_id": uid,
            "consent_granted": True,
            "assigned_arm": self.ARMS[bucket],
        }

    def log_impression(
        self,
        *,
        owner_id: str,
        recommended_items: List[Dict[str, Any]],
        arm: Optional[str] = None,
        experiment_id: str = DEFAULT_EXPERIMENT_ID,
        impression_id: Optional[str] = None,
    ) -> ExperimentImpression:
        uid = str(owner_id)
        eff_arm = arm or self.assign_arm(owner_id=uid, experiment_id=experiment_id)["assigned_arm"]
        with self._lock:
            iid = impression_id or f"imp_{len(self._impressions) + 1}_{uid}"
            rec = ExperimentImpression(
                impression_id=iid,
                experiment_id=experiment_id,
                arm=eff_arm,
                owner_id=uid,
                recommended_item_ids=[str(it.get("item_id") or it.get("id") or "") for it in recommended_items],
                recommended_categories=[str(it.get("category") or "unknown") for it in recommended_items],
                timestamp_s=time.time(),
            )
            self._impressions[iid] = rec
            return rec

    def log_outcome(
        self,
        *,
        impression_id: str,
        owner_id: str,
        item_id: str,
        outcome_type: str,
        purchase_authorized: bool = False,
    ) -> Dict[str, Any]:
        uid = str(owner_id)
        otype = str(outcome_type).strip().lower()
        if otype == "purchase" and not purchase_authorized:
            return {"recorded": False, "reason": "Unauthorized purchase outcome rejected."}
        with self._lock:
            imp = self._impressions.get(impression_id)
            if imp is None:
                return {"recorded": False, "reason": f"Impression '{impression_id}' not found."}
            if imp.owner_id != uid:
                raise PermissionError("Cannot log outcome against another owner's recommendation impression.")
            self._outcomes.append(ExperimentOutcome(
                impression_id=impression_id,
                owner_id=uid,
                item_id=str(item_id),
                outcome_type=otype,
                purchase_authorized=purchase_authorized,
                timestamp_s=time.time(),
            ))
            return {"recorded": True, "impression_id": impression_id, "outcome_type": otype}

    def get_report(self, *, experiment_id: str = DEFAULT_EXPERIMENT_ID) -> ExperimentReport:
        with self._lock:
            imps = [im for im in self._impressions.values() if im.experiment_id == experiment_id]
            imp_ids = {im.impression_id: im for im in imps}
            outs = [o for o in self._outcomes if o.impression_id in imp_ids]

        by_arm_imps: Dict[str, List[ExperimentImpression]] = {}
        for im in imps:
            by_arm_imps.setdefault(im.arm, []).append(im)

        arms_out: Dict[str, ArmAnalytics] = {}
        for arm_name, arm_imps in by_arm_imps.items():
            arm_imp_ids: Set[str] = {im.impression_id for im in arm_imps}
            arm_outs = [o for o in outs if o.impression_id in arm_imp_ids]
            clicks = sum(1 for o in arm_outs if o.outcome_type == "click")
            saves = sum(1 for o in arm_outs if o.outcome_type in {"save", "like"})
            dismiss = sum(1 for o in arm_outs if o.outcome_type == "dismiss")
            purch = sum(1 for o in arm_outs if o.outcome_type == "purchase" and o.purchase_authorized)
            denom = max(1, len(arm_imps))
            acc = round((clicks + saves + purch) / denom, 4)
            divs = [
                len(set(im.recommended_categories)) / max(1, len(im.recommended_categories))
                for im in arm_imps
            ]
            arms_out[arm_name] = ArmAnalytics(
                arm=arm_name,
                impressions=len(arm_imps),
                clicks=clicks,
                saves=saves,
                dismissals=dismiss,
                authorized_purchases=purch,
                acceptance_rate=min(1.0, acc),
                mean_category_diversity=round(sum(divs) / max(1, len(divs)), 4),
            )

        min_arm = min([a.impressions for a in arms_out.values()] or [0])
        powered = (len(arms_out) >= 2) and (min_arm >= MIN_IMPRESSIONS_FOR_POWER)
        note = (
            "Minimum statistical impression power met; review diversity and acceptance deltas."
            if powered
            else (
                f"Insufficient experiment traffic ({len(imps)} total impressions across {len(arms_out)} arms; "
                f"need >= {MIN_IMPRESSIONS_FOR_POWER} per arm). Do NOT declare an A/B winner."
            )
        )
        return ExperimentReport(
            experiment_id=experiment_id,
            total_impressions=len(imps),
            statistically_powered=powered,
            power_note=note,
            arms=arms_out,
        )


recommendation_experiments = RecommendationExperimentManager()
