"""
YORVYN Intelligence Platform (YIP) — Owner-Isolated Preference Profile & Data Governance.

Coordinates existing Layer A PersonalizationService and Model E PreferenceLearningService
without introducing a separate auth or database layer. Strictly separates explicit user
preferences from inferred behavioral preferences, blocks weak product views from turning
into fake positive preferences, applies exponential time decay, supports session-scoped
browsing context, enforces sensitive-attribute filtering, retention expiry, and user reset.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from backend.app.services.intelligence.recommendation_taxonomy import (
    RecommendationGarmentAttributes,
    normalize_category_and_subcategory,
    normalize_item,
)
from backend.app.services.learning.personalization_service import personalization_service
from backend.app.services.ml.preference_learning import preference_learning_service

# Weak viewing signals never promote long-term preference automatically
WEAK_VIEW_SIGNALS: Set[str] = {"view", "viewed", "detail_view", "garment_detail_view", "hover", "browse"}
POSITIVE_SIGNALS: Set[str] = {
    "liked", "like", "saved", "save", "worn", "outfit_selected",
    "recommendation_clicked", "click_positive", "repeated_selection", "purchase",
}
NEGATIVE_SIGNALS: Set[str] = {
    "disliked", "dislike", "rejected", "reject", "recommendation_dismissed", "dismissed",
}

SIGNAL_WEIGHTS: Dict[str, float] = {
    "saved": 1.0,
    "save": 1.0,
    "liked": 0.9,
    "like": 0.9,
    "outfit_selected": 0.85,
    "repeated_selection": 0.8,
    "worn": 0.75,
    "purchase": 1.1,
    "recommendation_clicked": 0.55,
    "click_positive": 0.55,
    "search": 0.25,
    "disliked": -1.2,
    "dislike": -1.2,
    "rejected": -1.2,
    "reject": -1.2,
    "recommendation_dismissed": -0.75,
    "dismissed": -0.75,
    "view": 0.0,
    "viewed": 0.0,
    "detail_view": 0.0,
    "garment_detail_view": 0.0,
}

# Privacy guard: never infer or store sensitive demographic/personal traits
SENSITIVE_ATTRIBUTE_BLOCKLIST: Set[str] = {
    "race", "ethnicity", "religion", "political", "sexual_orientation",
    "health_condition", "disability", "income_bracket", "age_exact", "biometric_identity",
}

VALID_ATTRIBUTE_KEYS: Tuple[str, ...] = (
    "category", "subcategory", "style", "fit", "color", "material", "occasion", "season", "silhouette",
)


class InteractionRecord(BaseModel):
    interaction_id: str
    owner_id: str
    item_id: str
    interaction_type: str
    timestamp_s: float
    session_id: Optional[str] = None
    explicit: bool = False
    is_purchase: bool = False
    purchase_authorized: bool = False
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SessionBrowsingContext(BaseModel):
    session_id: str
    owner_id: str
    search_terms: List[str] = Field(default_factory=list)
    viewed_item_ids: List[str] = Field(default_factory=list)
    active_categories: Dict[str, float] = Field(default_factory=dict)
    active_colors: Dict[str, float] = Field(default_factory=dict)
    active_styles: Dict[str, float] = Field(default_factory=dict)
    active_occasion: Optional[str] = None
    anchor_garment: Optional[Dict[str, Any]] = None
    updated_at_s: float = Field(default_factory=time.time)


class UserPreferenceProfile(BaseModel):
    owner_id: str
    consent_granted: bool = True
    private_uploads_excluded_from_training: bool = True
    sensitive_traits_inferred: bool = False
    explicit_preferences: Dict[str, List[str]] = Field(default_factory=dict)
    inferred_preferences: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    category_affinity: Dict[str, float] = Field(default_factory=dict)
    subcategory_affinity: Dict[str, float] = Field(default_factory=dict)
    saved_item_ids: List[str] = Field(default_factory=list)
    liked_item_ids: List[str] = Field(default_factory=list)
    disliked_item_ids: List[str] = Field(default_factory=list)
    dismissed_item_ids: List[str] = Field(default_factory=list)
    interaction_count: int = 0
    positive_interaction_count: int = 0
    view_only_count: int = 0
    is_cold_start: bool = True
    half_life_days: float = 30.0
    retention_days: int = 180


class PreferenceProfileStore:
    """Owner-isolated preference memory with decay, consent, session scope & governance."""

    def __init__(self, half_life_days: float = 30.0, retention_days: int = 180, *, sync_remote: bool = True) -> None:
        self.half_life_days = float(half_life_days)
        self.retention_days = int(retention_days)
        self.sync_remote = bool(sync_remote)
        self._consents: Dict[str, bool] = {}
        self._explicit: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._interactions: Dict[str, List[InteractionRecord]] = defaultdict(list)
        self._sessions: Dict[Tuple[str, str], SessionBrowsingContext] = {}

    def set_consent(self, owner_id: str, consent_granted: bool) -> Dict[str, Any]:
        uid = str(owner_id)
        self._consents[uid] = bool(consent_granted)
        if self.sync_remote:
            try:
                personalization_service.repo.update_learning_consent(
                    uid, personalization_enabled=bool(consent_granted)
                )
            except Exception:
                pass
        return {"owner_id": uid, "consent_granted": self._consents[uid]}

    def get_consent(self, owner_id: str) -> bool:
        uid = str(owner_id)
        if uid in self._consents:
            return self._consents[uid]
        if self.sync_remote:
            try:
                c = personalization_service.repo.get_learning_consent(uid)
                if isinstance(c, dict) and "personalization_enabled" in c:
                    return bool(c["personalization_enabled"])
            except Exception:
                pass
        return True

    def _sanitize_attributes(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        clean: Dict[str, Any] = {}
        for k, v in (attrs or {}).items():
            kl = str(k).strip().lower()
            if kl in SENSITIVE_ATTRIBUTE_BLOCKLIST:
                continue
            clean[kl] = v
        return clean

    def set_explicit_preferences(
        self,
        owner_id: str,
        preferences: Dict[str, List[str]],
        *,
        replace: bool = False,
    ) -> UserPreferenceProfile:
        uid = str(owner_id)
        if replace:
            self._explicit[uid] = defaultdict(set)

        sanitized = self._sanitize_attributes(preferences)
        for dim, values in sanitized.items():
            if dim not in VALID_ATTRIBUTE_KEYS and dim != "disliked_categories" and dim != "disliked_colors":
                continue
            vals = [values] if isinstance(values, str) else list(values or [])
            for v in vals:
                v_clean = str(v).strip().lower()
                if not v_clean:
                    continue
                if dim == "category":
                    norm_cat, _ = normalize_category_and_subcategory(v_clean)
                    self._explicit[uid]["category"].add(norm_cat)
                    if self.sync_remote:
                        try:
                            personalization_service.upsert_user_preference(
                                uid, "category", norm_cat, norm_cat, source="explicit", confidence=0.95
                            )
                        except Exception:
                            pass
                elif dim == "subcategory":
                    _, norm_sub = normalize_category_and_subcategory(None, v_clean)
                    self._explicit[uid]["subcategory"].add(norm_sub)
                else:
                    self._explicit[uid][dim].add(v_clean)
                    if self.sync_remote:
                        try:
                            pcat = "colour" if dim == "color" else dim
                            personalization_service.upsert_user_preference(
                                uid, pcat, v_clean, v_clean, source="explicit", confidence=0.95
                            )
                        except Exception:
                            pass
        return self.get_profile(uid)

    def record_interaction(
        self,
        *,
        owner_id: str,
        interaction_type: str,
        item_data: Optional[Dict[str, Any]] = None,
        search_query: Optional[str] = None,
        session_id: Optional[str] = None,
        timestamp_s: Optional[float] = None,
        consent_granted: Optional[bool] = None,
        purchase_authorized: bool = False,
    ) -> Dict[str, Any]:
        uid = str(owner_id)
        effective_consent = self.get_consent(uid) if consent_granted is None else bool(consent_granted)
        itype = str(interaction_type or "view").strip().lower()
        now_s = float(timestamp_s if timestamp_s is not None else time.time())

        if not effective_consent:
            return {
                "recorded": False,
                "reason": "Personalization consent is disabled for this owner.",
                "treated_as_positive_preference": False,
            }

        if itype == "purchase" and not purchase_authorized:
            return {
                "recorded": False,
                "reason": "Purchase history ingestion requires an authorized purchase integration flag.",
                "treated_as_positive_preference": False,
            }

        raw = self._sanitize_attributes(item_data or {})
        norm_item: Optional[RecommendationGarmentAttributes] = None
        if raw.get("category") or raw.get("item_id") or raw.get("id") or raw.get("name"):
            norm_item = normalize_item(raw)

        # Session context ALWAYS captures transient search / product views without corrupting long-term profile
        if session_id:
            sess = self.get_or_create_session(uid, session_id)
            sess.updated_at_s = now_s
            if search_query:
                q_clean = search_query.strip().lower()
                if q_clean and q_clean not in sess.search_terms:
                    sess.search_terms.append(q_clean)
                    sess.search_terms = sess.search_terms[-20:]
            if norm_item is not None:
                if norm_item.item_id not in sess.viewed_item_ids:
                    sess.viewed_item_ids.append(norm_item.item_id)
                    sess.viewed_item_ids = sess.viewed_item_ids[-30:]
                boost = 0.25 if itype in WEAK_VIEW_SIGNALS else (0.7 if itype in POSITIVE_SIGNALS else -0.5)
                if boost > 0:
                    sess.active_categories[norm_item.category] = min(
                        1.0, sess.active_categories.get(norm_item.category, 0.0) + boost
                    )
                    sess.active_colors[norm_item.color] = min(
                        1.0, sess.active_colors.get(norm_item.color, 0.0) + boost
                    )
                    for st in norm_item.style:
                        sess.active_styles[st] = min(1.0, sess.active_styles.get(st, 0.0) + boost)

        item_id = norm_item.item_id if norm_item else str(raw.get("item_id") or raw.get("id") or "search")
        attrs_payload = norm_item.model_dump(exclude={"visual_embedding"}) if norm_item else raw
        if search_query:
            attrs_payload["search_query"] = search_query

        rec = InteractionRecord(
            interaction_id=f"int_{uid}_{len(self._interactions[uid]) + 1}",
            owner_id=uid,
            item_id=item_id,
            interaction_type=itype,
            timestamp_s=now_s,
            session_id=session_id,
            explicit=False,
            is_purchase=(itype == "purchase"),
            purchase_authorized=purchase_authorized,
            attributes=attrs_payload,
        )
        self._interactions[uid].append(rec)
        if timestamp_s is None:
            self.purge_expired_interactions(uid)

        # Forward only strong signals to Model E PreferenceLearningService (never auto-promote weak views)
        treated_as_positive = itype in POSITIVE_SIGNALS
        if self.sync_remote and norm_item and (itype in POSITIVE_SIGNALS or itype in NEGATIVE_SIGNALS):
            model_e_type = "rejected" if itype in {"disliked", "dislike", "recommendation_dismissed", "dismissed"} else (
                "saved" if itype in {"saved", "save", "outfit_selected", "purchase"} else itype
            )
            try:
                preference_learning_service.record_interaction(
                    user_id=uid,
                    interaction_type=model_e_type,
                    item_or_outfit_data=attrs_payload,
                )
            except Exception:
                pass

        return {
            "recorded": True,
            "interaction_id": rec.interaction_id,
            "interaction_type": itype,
            "treated_as_positive_preference": treated_as_positive,
            "session_only": itype in WEAK_VIEW_SIGNALS,
        }

    def get_or_create_session(self, owner_id: str, session_id: str) -> SessionBrowsingContext:
        key = (str(owner_id), str(session_id))
        if key not in self._sessions:
            self._sessions[key] = SessionBrowsingContext(session_id=str(session_id), owner_id=str(owner_id))
        return self._sessions[key]

    def update_session_context(
        self,
        *,
        owner_id: str,
        session_id: str,
        occasion: Optional[str] = None,
        anchor_garment: Optional[Dict[str, Any]] = None,
        search_query: Optional[str] = None,
    ) -> SessionBrowsingContext:
        sess = self.get_or_create_session(owner_id, session_id)
        sess.updated_at_s = time.time()
        if occasion:
            sess.active_occasion = occasion.strip().lower()
        if anchor_garment:
            sess.anchor_garment = self._sanitize_attributes(anchor_garment)
        if search_query:
            q_clean = search_query.strip().lower()
            if q_clean and q_clean not in sess.search_terms:
                sess.search_terms.append(q_clean)
        return sess

    def purge_expired_interactions(
        self,
        owner_id: str,
        *,
        retention_days: Optional[int] = None,
        reference_time_s: Optional[float] = None,
    ) -> int:
        uid = str(owner_id)
        days = int(retention_days if retention_days is not None else self.retention_days)
        now_s = float(reference_time_s if reference_time_s is not None else time.time())
        cutoff = now_s - (days * 86400.0)
        before = len(self._interactions[uid])
        self._interactions[uid] = [r for r in self._interactions[uid] if r.timestamp_s >= cutoff]
        return before - len(self._interactions[uid])

    def reset_profile(self, owner_id: str, scope: str = "all") -> Dict[str, Any]:
        uid = str(owner_id)
        scope_l = (scope or "all").lower()
        purged_interactions = 0
        purged_explicit = 0
        if scope_l in {"all", "inferred"}:
            purged_interactions = len(self._interactions.get(uid, []))
            self._interactions[uid] = []
        if scope_l in {"all", "explicit"}:
            purged_explicit = sum(len(v) for v in self._explicit.get(uid, {}).values())
            self._explicit[uid] = defaultdict(set)
            try:
                personalization_service.reset_user_preferences(uid)
            except Exception:
                pass
        if scope_l in {"all", "session"}:
            for k in [k for k in self._sessions if k[0] == uid]:
                del self._sessions[k]
        return {
            "owner_id": uid,
            "scope": scope_l,
            "purged_interactions": purged_interactions,
            "purged_explicit_preferences": purged_explicit,
        }

    def get_interactions(self, owner_id: str, *, before_timestamp_s: Optional[float] = None) -> List[InteractionRecord]:
        recs = list(self._interactions.get(str(owner_id), []))
        if before_timestamp_s is not None:
            recs = [r for r in recs if r.timestamp_s < before_timestamp_s]
        return recs

    def get_all_owner_positive_items(self, *, min_positive_interactions: int = 3) -> Dict[str, Set[str]]:
        """Privacy-preserving anonymous owner->positive item IDs for CF eligibility checks."""
        out: Dict[str, Set[str]] = {}
        for uid, recs in self._interactions.items():
            if not self.get_consent(uid):
                continue
            pos = {r.item_id for r in recs if r.interaction_type in POSITIVE_SIGNALS}
            if len(pos) >= min_positive_interactions:
                out[uid] = pos
        return out

    def get_profile(
        self,
        owner_id: str,
        *,
        reference_time_s: Optional[float] = None,
        before_timestamp_s: Optional[float] = None,
    ) -> UserPreferenceProfile:
        uid = str(owner_id)
        now_s = float(reference_time_s if reference_time_s is not None else time.time())
        consent = self.get_consent(uid)
        if not consent:
            return UserPreferenceProfile(owner_id=uid, consent_granted=False, is_cold_start=True)

        # Merge stored Layer A explicit preferences read-only without mutating ownership
        explicit_map: Dict[str, Set[str]] = defaultdict(set)
        for k, vals in self._explicit.get(uid, {}).items():
            explicit_map[k].update(vals)
        if self.sync_remote:
            try:
                for p in personalization_service.get_user_preferences(uid) or []:
                    pcat = str(p.get("preference_category") or p.get("category") or "").lower()
                    pval = str(p.get("preference_value") or p.get("value") or "").lower()
                    src = str(p.get("source") or "explicit").lower()
                    if pval and src in {"explicit", "correction"}:
                        if "color" in pcat or "colour" in pcat:
                            explicit_map["color"].add(pval)
                        elif "category" in pcat:
                            nc, _ = normalize_category_and_subcategory(pval)
                            explicit_map["category"].add(nc)
                        elif "fit" in pcat:
                            explicit_map["fit"].add(pval)
                        elif "style" in pcat and pval not in {"true", "false"}:
                            explicit_map["style"].add(pval)
            except Exception:
                pass

        inferred_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        cat_aff: Dict[str, float] = defaultdict(float)
        subcat_aff: Dict[str, float] = defaultdict(float)

        saved_ids: Set[str] = set()
        liked_ids: Set[str] = set()
        disliked_ids: Set[str] = set()
        dismissed_ids: Set[str] = set()
        pos_count = 0
        view_count = 0

        recs = self.get_interactions(uid, before_timestamp_s=before_timestamp_s)
        for r in recs:
            itype = r.interaction_type
            if itype in WEAK_VIEW_SIGNALS:
                view_count += 1
                continue  # Never automatically promote view to positive preference

            base_w = SIGNAL_WEIGHTS.get(itype, 0.0)
            if base_w == 0.0:
                continue

            age_days = max(0.0, (now_s - r.timestamp_s) / 86400.0)
            decay = math.exp(-math.log(2.0) * age_days / max(1.0, self.half_life_days))
            w = base_w * decay

            if itype in {"saved", "save"}:
                saved_ids.add(r.item_id)
            elif itype in {"liked", "like"}:
                liked_ids.add(r.item_id)
            elif itype in {"disliked", "dislike", "rejected", "reject"}:
                disliked_ids.add(r.item_id)
            elif itype in {"recommendation_dismissed", "dismissed"}:
                dismissed_ids.add(r.item_id)

            if base_w > 0:
                pos_count += 1

            attrs = r.attributes or {}
            if attrs.get("category"):
                nc, ns = normalize_category_and_subcategory(str(attrs.get("category")), str(attrs.get("subcategory", "")))
                cat_aff[nc] += w
                if ns:
                    subcat_aff[ns] += w
                inferred_scores["category"][nc] += w
                if ns:
                    inferred_scores["subcategory"][ns] += w
            if attrs.get("color"):
                inferred_scores["color"][str(attrs["color"]).lower()] += w
            if attrs.get("fit"):
                inferred_scores["fit"][str(attrs["fit"]).lower()] += w
            if attrs.get("material"):
                inferred_scores["material"][str(attrs["material"]).lower()] += w
            if attrs.get("silhouette"):
                inferred_scores["silhouette"][str(attrs["silhouette"]).lower()] += w
            for st in (attrs.get("style") or []):
                inferred_scores["style"][str(st).lower()] += w
            for occ in (attrs.get("occasion") or []):
                inferred_scores["occasion"][str(occ).lower()] += w
            for sea in (attrs.get("season") or []):
                inferred_scores["season"][str(sea).lower()] += w

        # Normalize positive category affinity to [0, 1] scale while preserving negative signals cleanly
        norm_cat_aff: Dict[str, float] = {}
        max_pos_c = max([v for v in cat_aff.values() if v > 0.0] or [1.0])
        for k, v in cat_aff.items():
            norm_cat_aff[k] = round(max(-1.0, min(1.0, v / max_pos_c)), 4)

        norm_sub_aff: Dict[str, float] = {}
        max_pos_s = max([v for v in subcat_aff.values() if v > 0.0] or [1.0])
        for k, v in subcat_aff.items():
            norm_sub_aff[k] = round(max(-1.0, min(1.0, v / max_pos_s)), 4)

        has_explicit = any(len(v) > 0 for v in explicit_map.values())
        is_cold = (pos_count == 0 and not has_explicit)

        return UserPreferenceProfile(
            owner_id=uid,
            consent_granted=True,
            explicit_preferences={k: sorted(list(v)) for k, v in explicit_map.items() if v},
            inferred_preferences={
                dim: {k: round(float(val), 4) for k, val in sorted(m.items(), key=lambda x: x[1], reverse=True)}
                for dim, m in inferred_scores.items()
                if m
            },
            category_affinity=norm_cat_aff,
            subcategory_affinity=norm_sub_aff,
            saved_item_ids=sorted(saved_ids),
            liked_item_ids=sorted(liked_ids),
            disliked_item_ids=sorted(disliked_ids),
            dismissed_item_ids=sorted(dismissed_ids),
            interaction_count=len(recs),
            positive_interaction_count=pos_count,
            view_only_count=view_count,
            is_cold_start=is_cold,
            half_life_days=self.half_life_days,
            retention_days=self.retention_days,
        )


recommendation_profile_store = PreferenceProfileStore()
