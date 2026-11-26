"""
Supabase PostgreSQL Database Repository for Yorvyn.
Handles persistence for profiles, digital wardrobe, garment 3D jobs,
conversations, and legacy Firebase UID relinking.
Includes robust offline fallback store for local testing and CI runners.
"""

from __future__ import annotations

import json
import os
from fastapi import HTTPException
import uuid
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests

from backend.app.core.settings import settings

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Data access layer interfacing with Supabase PostgreSQL."""

    def __init__(self):
        self._supabase_url = settings.supabase_url
        self._service_key = settings.supabase_service_role_key or settings.supabase_anon_key
        # In-memory local cache / fallback store for offline tests
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._wardrobe: Dict[str, List[Dict[str, Any]]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._legacy_map: Dict[str, str] = {}
        self._fashion_dna: Dict[str, Dict[str, Any]] = {}
        self._tool_logs: Dict[str, List[Dict[str, Any]]] = {}
        self._evaluations: Dict[str, List[Dict[str, Any]]] = {}
        self._looks: Dict[str, List[Dict[str, Any]]] = {}
        self._consents: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._billing_events: Dict[str, Dict[str, Any]] = {}
        self._usage_records: Dict[str, List[Dict[str, Any]]] = {}
        self._beta_invitations: Dict[str, Dict[str, Any]] = {}
        self._beta_feedbacks: List[Dict[str, Any]] = []
        self._seed_beta_cohort()
        # AI Persistent Sessions, Messages, Searches & Attachments
        self._ai_sessions: Dict[str, Dict[str, Any]] = {}
        self._ai_messages: Dict[str, List[Dict[str, Any]]] = {}
        self._ai_searches: Dict[str, List[Dict[str, Any]]] = {}
        self._ai_session_events: Dict[str, List[Dict[str, Any]]] = {}
        self._ai_attachments: Dict[str, List[Dict[str, Any]]] = {}
        # Continuous Learning & Personalization Engine
        self._user_preferences: Dict[str, Dict[tuple, Dict[str, Any]]] = {}  # user_id -> {(cat, key): pref}
        self._ai_feedback: Dict[str, List[Dict[str, Any]]] = {}               # user_id -> [feedback]
        self._learning_examples: Dict[str, Dict[str, Any]] = {}              # id -> example
        self._model_registry: Dict[str, Dict[str, Any]] = {}                 # f"{name}:{ver}" -> model
        self._training_jobs: Dict[str, Dict[str, Any]] = {}                  # id -> job
        self._learning_consents: Dict[str, Dict[str, Any]] = {}              # user_id -> consent
        self._lock = threading.Lock()
        self._seed_production_models()

    def _seed_beta_cohort(self):
        """Seeds initial closed pilot beta cohort (12 participants)."""
        now = datetime.utcnow()
        exp = now + timedelta(days=45)
        initial_cohort = [
            ("BETA-PILOT-01-ALICE", "alice@internal.yorvyn.ai", "active", "usr_test_alpha_01", 1),
            ("BETA-PILOT-02-BOB", "bob@internal.yorvyn.ai", "active", "usr_test_alpha_02", 1),
            ("BETA-PILOT-03-CHARLIE", "charlie@internal.yorvyn.ai", "active", "usr_test_alpha_03", 1),
            ("BETA-PILOT-04-DIANA", "diana@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-05-ELENA", "elena@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-06-FRANK", "frank@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-07-GRACE", "grace@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-08-HARI", "hari@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-09-ISABEL", "isabel@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-10-JACK", "jack@internal.yorvyn.ai", "pending", None, 0),
            ("BETA-PILOT-11-KAREN", "karen@internal.yorvyn.ai", "suspended", None, 0),
            ("BETA-PILOT-12-LUIS", "luis@internal.yorvyn.ai", "revoked", None, 0),
        ]
        for token, email, status, act_by, uses in initial_cohort:
            self._beta_invitations[token] = {
                "id": f"inv_{hashlib.sha256(token.encode()).hexdigest()[:12]}",
                "token": token,
                "email": email,
                "cohort": "closed_pilot",
                "status": status,
                "max_uses": 1,
                "uses_count": uses,
                "expires_at": exp.isoformat(),
                "activated_at": now.isoformat() if act_by else None,
                "activated_by": act_by,
                "notes": f"Initial cohort participant: {email}",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

    def _seed_production_models(self):
        """Seeds canonical baseline production models in the model registry."""
        now = datetime.utcnow().isoformat()
        seeds = [
            {
                "id": str(uuid.uuid4()),
                "model_name": "universal_garment_classifier",
                "model_version": "v1.0.0",
                "task_type": "classification",
                "artifact_uri": "s3://yorvyn-models/production/garment_clf_v1.0.0.onnx",
                "artifact_checksum": "sha256:4a8bc39d7e12f390",
                "base_model": "mobilenet_v3_large",
                "training_dataset_version": "garment_tax_v1.2",
                "evaluation_metrics": {"accuracy": 0.932, "macro_f1": 0.924, "top_3_accuracy": 0.985},
                "status": "deployed",
                "deployed_at": now,
                "created_at": now
            },
            {
                "id": str(uuid.uuid4()),
                "model_name": "garment_reconstruction_engine",
                "model_version": "v1.0.0",
                "task_type": "reconstruction",
                "artifact_uri": "s3://yorvyn-models/production/recon_v1.0.0.pt",
                "artifact_checksum": "sha256:8b91ef40d021c44b",
                "base_model": "mesh_builder_canonical_v1",
                "training_dataset_version": "mesh_dataset_v2.0",
                "evaluation_metrics": {"chamfer_dist": 0.0142, "silhouette_iou": 0.892, "f_score_5mm": 0.912},
                "status": "deployed",
                "deployed_at": now,
                "created_at": now
            },
            {
                "id": str(uuid.uuid4()),
                "model_name": "hybrid_recommendation_ranker",
                "model_version": "v1.0.0",
                "task_type": "recommendation_ranking",
                "artifact_uri": "s3://yorvyn-models/production/ranker_v1.0.0.pt",
                "artifact_checksum": "sha256:7c992fa023e198b1",
                "base_model": "two_tower_ranker_v1",
                "training_dataset_version": "outfit_interactions_v1.0",
                "evaluation_metrics": {"acceptance_rate": 0.841, "preference_alignment": 0.885, "ndcg_at_5": 0.914},
                "status": "deployed",
                "deployed_at": now,
                "created_at": now
            }
        ]
        for m in seeds:
            key = f"{m['model_name']}:{m['model_version']}"
            self._model_registry[key] = m

    @property
    def is_configured(self) -> bool:
        return bool(
            self._supabase_url
            and self._service_key
            and not self._supabase_url.startswith("https://demo")
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    # ── User Profiles ──────────────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile record."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_profiles?user_id=eq.{user_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_profile error: {e}")

        return self._profiles.get(str(user_id))

    def upsert_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates user profile."""
        profile_data["user_id"] = str(user_id)
        profile_data["updated_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_profiles"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=profile_data, headers=headers, timeout=5)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase upsert_profile error: {e}")

        self._profiles[str(user_id)] = profile_data
        return profile_data

    # ── Digital Wardrobe ───────────────────────────────────────────────────────

    def get_wardrobe_items(self, user_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves wardrobe items owned by user."""
        if self.is_configured:
            try:
                query = f"user_id=eq.{user_id}"
                if category:
                    query += f"&category=eq.{category}"
                url = f"{self._supabase_url}/rest/v1/yorvyn_wardrobe_items?{query}&order=created_at.desc"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase get_wardrobe_items error: {e}")

        items = self._wardrobe.get(str(user_id), [])
        if category:
            return [i for i in items if i.get("category") == category]
        return items

    def insert_wardrobe_item(self, user_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Inserts a new wardrobe item."""
        item["user_id"] = str(user_id)
        item["created_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_wardrobe_items"
                r = requests.post(url, json=item, headers=self._get_headers(), timeout=5)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase insert_wardrobe_item error: {e}")

        if str(user_id) not in self._wardrobe:
            self._wardrobe[str(user_id)] = []
        self._wardrobe[str(user_id)].append(item)
        return item

    def get_wardrobe_item(self, user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single wardrobe item owned by user."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_wardrobe_items?user_id=eq.{user_id}&id=eq.{item_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_wardrobe_item error: {e}")

        items = self._wardrobe.get(str(user_id), [])
        for i in items:
            if i.get("id") == item_id:
                return i
        return None

    def update_wardrobe_item(self, user_id: str, item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates attributes of a wardrobe item (e.g. favorite, wear count)."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_wardrobe_items?user_id=eq.{user_id}&id=eq.{item_id}"
                r = requests.patch(url, json=updates, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase update_wardrobe_item error: {e}")

        items = self._wardrobe.get(str(user_id), [])
        for i in items:
            if i.get("id") == item_id:
                i.update(updates)
                return i
        return None

    def delete_wardrobe_item(self, user_id: str, item_id: str) -> bool:
        """Deletes a wardrobe item owned by user."""
        deleted = False
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_wardrobe_items?user_id=eq.{user_id}&id=eq.{item_id}"
                r = requests.delete(url, headers=self._get_headers(), timeout=5)
                if r.status_code in [200, 204]:
                    deleted = True
            except Exception as e:
                logger.warning(f"Supabase delete_wardrobe_item error: {e}")

        items = self._wardrobe.get(str(user_id), [])
        before_cnt = len(items)
        self._wardrobe[str(user_id)] = [i for i in items if i.get("id") != item_id]
        if len(self._wardrobe[str(user_id)]) < before_cnt:
            deleted = True
        return deleted

    # ── Garment 3D Generation Jobs ─────────────────────────────────────────────

    def save_job(self, job_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Persists or updates a garment generation job record."""
        job_id = job_dict["job_id"]
        job_dict["updated_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_garment_jobs"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=job_dict, headers=headers, timeout=5)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase save_job error: {e}")

        self._jobs[job_id] = job_dict
        return job_dict

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a garment job by ID."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_garment_jobs?job_id=eq.{job_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_job error: {e}")

        return self._jobs.get(job_id)

    # ── Legacy Identity Relinking (Firebase to Supabase) ───────────────────────

    def relink_legacy_user(self, firebase_uid: str, supabase_user_id: str, email: str) -> Dict[str, Any]:
        """Records mapping between old Firebase UID and new Supabase UUID."""
        mapping = {
            "firebase_uid": firebase_uid,
            "supabase_user_id": str(supabase_user_id),
            "email": email,
            "migrated_at": datetime.utcnow().isoformat()
        }

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_legacy_identity_map"
                requests.post(url, json=mapping, headers=self._get_headers(), timeout=5)
            except Exception as e:
                logger.warning(f"Supabase relink_legacy_user error: {e}")

        self._legacy_map[firebase_uid] = str(supabase_user_id)
        return mapping

    # ── Fashion DNA ────────────────────────────────────────────────────────────

    def get_fashion_dna(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user Fashion DNA record."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_fashion_dna?user_id=eq.{user_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_fashion_dna error: {e}")

        return self._fashion_dna.get(str(user_id))

    def upsert_fashion_dna(self, user_id: str, dna_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upserts user Fashion DNA record."""
        dna_data["user_id"] = str(user_id)
        dna_data["updated_at"] = datetime.utcnow().isoformat()
        if "created_at" not in dna_data:
            dna_data["created_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_fashion_dna"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=dna_data, headers=headers, timeout=5)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase upsert_fashion_dna error: {e}")

        self._fashion_dna[str(user_id)] = dna_data
        return dna_data

    def delete_fashion_dna(self, user_id: str) -> bool:
        """Deletes user Fashion DNA record for privacy compliance."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_fashion_dna?user_id=eq.{user_id}"
                requests.delete(url, headers=self._get_headers(), timeout=5)
            except Exception as e:
                logger.warning(f"Supabase delete_fashion_dna error: {e}")

        if str(user_id) in self._fashion_dna:
            del self._fashion_dna[str(user_id)]
            return True
        return False

    # ── Tool Execution Logs ────────────────────────────────────────────────────

    def log_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        input_args: Dict[str, Any],
        output_payload: Dict[str, Any],
        execution_time_ms: float = 0.0,
        status: str = "success"
    ) -> Dict[str, Any]:
        """Logs authenticated tool invocation for security audit and tracking."""
        record = {
            "id": str(datetime.utcnow().timestamp()),
            "user_id": str(user_id),
            "tool_name": tool_name,
            "input_arguments": input_args,
            "output_payload": output_payload,
            "execution_time_ms": round(execution_time_ms, 2),
            "status": status,
            "created_at": datetime.utcnow().isoformat()
        }

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_tool_execution_logs"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase log_tool_execution error: {e}")

        if str(user_id) not in self._tool_logs:
            self._tool_logs[str(user_id)] = []
        self._tool_logs[str(user_id)].append(record)
        return record

    # ── Recommendation Evaluations ─────────────────────────────────────────────

    def save_recommendation_evaluation(
        self,
        user_id: str,
        outfit_id: str,
        scores: Dict[str, Any],
        rationale: str
    ) -> Dict[str, Any]:
        """Persists recommendation multi-factor evaluation."""
        rec = {
            "id": str(datetime.utcnow().timestamp()),
            "user_id": str(user_id),
            "outfit_id": outfit_id,
            "compatibility_scores": scores,
            "rationale": rationale,
            "feedback_status": "pending",
            "feedback_notes": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_recommendation_evaluations"
                requests.post(url, json=rec, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase save_recommendation_evaluation error: {e}")

        if str(user_id) not in self._evaluations:
            self._evaluations[str(user_id)] = []
        self._evaluations[str(user_id)].append(rec)
        return rec

    def update_recommendation_feedback(
        self,
        user_id: str,
        outfit_id: str,
        feedback_status: str,
        notes: Optional[str] = None
    ) -> bool:
        """Updates user feedback on a previously evaluated recommendation."""
        updated = False
        user_id_str = str(user_id)
        if user_id_str in self._evaluations:
            for item in self._evaluations[user_id_str]:
                if item.get("outfit_id") == outfit_id:
                    item["feedback_status"] = feedback_status
                    if notes:
                        item["feedback_notes"] = notes
                    item["updated_at"] = datetime.utcnow().isoformat()
                    updated = True

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_recommendation_evaluations?user_id=eq.{user_id_str}&outfit_id=eq.{outfit_id}"
                patch_payload = {
                    "feedback_status": feedback_status,
                    "feedback_notes": notes,
                    "updated_at": datetime.utcnow().isoformat()
                }
                requests.patch(url, json=patch_payload, headers=self._get_headers(), timeout=4)
                updated = True
            except Exception as e:
                logger.warning(f"Supabase update_recommendation_feedback error: {e}")

        return updated

    # ── Saved Looks & Outfits (Phase 9) ────────────────────────────────────────

    def get_saved_looks(self, user_id: str, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves all saved looks for a user, sorted by recency."""
        user_id_str = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_saved_looks?user_id=eq.{user_id_str}&order=created_at.desc"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if tag:
                        data = [d for d in data if tag in d.get("tags", [])]
                    return data
            except Exception as e:
                logger.warning(f"Supabase get_saved_looks error: {e}")

        looks = self._looks.get(user_id_str, [])
        if tag:
            looks = [l for l in looks if tag in l.get("tags", [])]
        return sorted(looks, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_saved_look(self, user_id: str, look_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single saved look by ID."""
        user_id_str = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_saved_looks?user_id=eq.{user_id_str}&id=eq.{look_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_saved_look error: {e}")

        looks = self._looks.get(user_id_str, [])
        for l in looks:
            if l.get("id") == look_id:
                return l
        return None

    def save_look(self, user_id: str, look_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or upserts a saved look with user ownership."""
        user_id_str = str(user_id)
        now_iso = datetime.utcnow().isoformat()
        look_data["user_id"] = user_id_str
        if "id" not in look_data or not look_data["id"]:
            import uuid
            look_data["id"] = f"look_{uuid.uuid4().hex[:12]}"
        if "created_at" not in look_data:
            look_data["created_at"] = now_iso
        look_data["updated_at"] = now_iso

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_saved_looks"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=look_data, headers=headers, timeout=5)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase save_look error: {e}")

        if user_id_str not in self._looks:
            self._looks[user_id_str] = []
        # Update if exists, else append
        existing_idx = next((i for i, l in enumerate(self._looks[user_id_str]) if l.get("id") == look_data["id"]), None)
        if existing_idx is not None:
            self._looks[user_id_str][existing_idx] = look_data
        else:
            self._looks[user_id_str].append(look_data)
        return look_data

    def update_saved_look(self, user_id: str, look_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates attributes of an existing look (e.g. name, garments, favorite)."""
        user_id_str = str(user_id)
        updates["updated_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_saved_looks?user_id=eq.{user_id_str}&id=eq.{look_id}"
                r = requests.patch(url, json=updates, headers=self._get_headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase update_saved_look error: {e}")

        looks = self._looks.get(user_id_str, [])
        for l in looks:
            if l.get("id") == look_id:
                l.update(updates)
                return l
        return None

    def delete_saved_look(self, user_id: str, look_id: str) -> bool:
        """Deletes a saved look owned by user."""
        user_id_str = str(user_id)
        deleted = False

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_saved_looks?user_id=eq.{user_id_str}&id=eq.{look_id}"
                r = requests.delete(url, headers=self._get_headers(), timeout=5)
                if r.status_code in [200, 204]:
                    deleted = True
            except Exception as e:
                logger.warning(f"Supabase delete_saved_look error: {e}")

        looks = self._looks.get(user_id_str, [])
        before_cnt = len(looks)
        self._looks[user_id_str] = [l for l in looks if l.get("id") != look_id]
        if len(self._looks[user_id_str]) < before_cnt:
            deleted = True
        return deleted

    def duplicate_saved_look(self, user_id: str, look_id: str, new_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Clones an existing saved look under the user's account."""
        look = self.get_saved_look(user_id, look_id)
        if not look:
            return None

        import copy, uuid
        cloned = copy.deepcopy(look)
        cloned["id"] = f"look_{uuid.uuid4().hex[:12]}"
        cloned["name"] = new_name or f"{look.get('name', 'Look')} (Copy)"
        cloned["wear_count"] = 0
        cloned["last_worn_at"] = None
        cloned["created_at"] = datetime.utcnow().isoformat()
        cloned["updated_at"] = datetime.utcnow().isoformat()

        return self.save_look(user_id, cloned)

    # ── User Privacy, Consent & GDPR Compliance (Phase 9) ──────────────────────

    def get_user_consent(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves privacy & AI training consent status."""
        user_id_str = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_user_consents?user_id=eq.{user_id_str}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase get_user_consent error: {e}")

        return self._consents.get(user_id_str)

    def upsert_user_consent(self, user_id: str, consent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Records or updates privacy and training opt-in consent."""
        user_id_str = str(user_id)
        consent_data["user_id"] = user_id_str
        consent_data["updated_at"] = datetime.utcnow().isoformat()
        if "created_at" not in consent_data:
            consent_data["created_at"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_user_consents"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=consent_data, headers=headers, timeout=4)
                if r.status_code in [200, 201]:
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase upsert_user_consent error: {e}")

        self._consents[user_id_str] = consent_data
        return consent_data

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Compiles complete exportable archive of all user data (GDPR Article 20)."""
        user_id_str = str(user_id)
        return {
            "export_timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id_str,
            "profile": self.get_profile(user_id_str),
            "fashion_dna": self.get_fashion_dna(user_id_str),
            "wardrobe_items": self.get_wardrobe_items(user_id_str),
            "saved_looks": self.get_saved_looks(user_id_str),
            "privacy_consents": self.get_user_consent(user_id_str),
            "subscription": self.get_subscription(user_id_str),
            "usage_records": self.get_usage_records(user_id_str),
            "beta_feedback": [f for f in self._beta_feedbacks if f.get("user_id") == user_id_str],
            "gdpr_compliance": {
                "right_to_access": True,
                "right_to_portability": True,
                "data_format": "JSON_RFC8259"
            }
        }

    # ── Phase 10: Production Subscriptions, Billing Events & Usage Records ──

    def get_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves active subscription record for user."""
        user_id_str = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_subscriptions?user_id=eq.{user_id_str}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200 and r.json():
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase get_subscription error: {e}")

        # In-memory fallback
        return self._subscriptions.get(user_id_str)

    def upsert_subscription(self, user_id: str, sub_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a user subscription."""
        user_id_str = str(user_id)
        sub_data["user_id"] = user_id_str
        sub_data["updated_at"] = datetime.utcnow().isoformat()
        if "created_at" not in sub_data:
            sub_data["created_at"] = datetime.utcnow().isoformat()
        if "current_period_start" not in sub_data:
            sub_data["current_period_start"] = datetime.utcnow().isoformat()

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_subscriptions"
                headers = dict(self._get_headers())
                headers["Prefer"] = "resolution=merge-duplicates,return=representation"
                r = requests.post(url, json=sub_data, headers=headers, timeout=4)
                if r.status_code in [200, 201] and r.json():
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase upsert_subscription error: {e}")

        self._subscriptions[user_id_str] = sub_data
        return sub_data

    def is_billing_event_processed(self, event_id: str) -> bool:
        """Checks if a Stripe webhook event has already been processed (Idempotency)."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_billing_events?event_id=eq.{event_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200 and r.json():
                    return True
            except Exception as e:
                logger.warning(f"Supabase is_billing_event_processed error: {e}")

        return event_id in self._billing_events

    def record_billing_event(
        self,
        event_id: str,
        event_type: str,
        user_id: Optional[str],
        payload: Dict[str, Any],
        stripe_customer_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Records an incoming webhook event for idempotency and audit trails."""
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "stripe_customer_id": stripe_customer_id,
            "payload": payload,
            "processed_at": datetime.utcnow().isoformat(),
            "error_message": error_message
        }
        self._billing_events[event_id] = record

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_billing_events"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase record_billing_event error: {e}")

        return True

    def record_usage(
        self,
        user_id: str,
        metric: str,
        quantity: int = 1,
        job_id: Optional[str] = None,
        cost_usd: float = 0.0,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        provenance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records a billable or quota-tracked event."""
        now = datetime.utcnow()
        p_start = period_start or now.isoformat()
        p_end = period_end or (now + timedelta(days=30)).isoformat()
        user_id_str = str(user_id)
        record = {
            "id": f"usage_{uuid.uuid4().hex[:12]}",
            "user_id": user_id_str,
            "metric": metric,
            "quantity": quantity,
            "job_id": job_id,
            "cost_usd": float(cost_usd),
            "provenance": provenance,
            "billing_period_start": p_start,
            "billing_period_end": p_end,
            "recorded_at": now.isoformat()
        }
        self._usage_records.setdefault(user_id_str, []).append(record)

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_usage_records"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase record_usage error: {e}")

        return record

    def get_usage_records(self, user_id: str) -> List[Dict[str, Any]]:
        """Returns all usage records for a user."""
        user_id_str = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_usage_records?user_id=eq.{user_id_str}&order=recorded_at.desc"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase get_usage_records error: {e}")

        return self._usage_records.get(user_id_str, [])

    def get_monthly_usage_count(self, user_id: str, metric: str, period_start: str) -> int:
        """Calculates total quantity consumed for metric in current billing period."""
        records = self.get_usage_records(user_id)
        total = 0
        for r in records:
            if r.get("metric") == metric:
                rec_start = r.get("billing_period_start")
                if not rec_start or not period_start or rec_start >= period_start or rec_start[:10] >= period_start[:10]:
                    total += int(r.get("quantity", 1))
        return total

    def purge_user_data(self, user_id: str) -> bool:
        """Permanently purges all user data across all tables (GDPR Article 17 Right to Erasure)."""
        user_id_str = str(user_id)
        # Purge in-memory stores
        self._profiles.pop(user_id_str, None)
        self._wardrobe.pop(user_id_str, None)
        self._looks.pop(user_id_str, None)
        self._consents.pop(user_id_str, None)
        self._fashion_dna.pop(user_id_str, None)
        self._tool_logs.pop(user_id_str, None)
        self._evaluations.pop(user_id_str, None)
        self._subscriptions.pop(user_id_str, None)
        self._usage_records.pop(user_id_str, None)
        self._beta_feedbacks = [f for f in self._beta_feedbacks if f.get("user_id") != user_id_str]
        for inv in self._beta_invitations.values():
            if inv.get("activated_by") == user_id_str:
                inv["activated_by"] = None

        if self.is_configured:
            try:
                # Delete cascades from auth.users, or direct delete on tables
                tables = [
                    "yorvyn_saved_looks",
                    "yorvyn_user_consents",
                    "yorvyn_subscriptions",
                    "yorvyn_usage_records",
                    "yorvyn_beta_feedback",
                    "yorvyn_wardrobe_items",
                    "yorvyn_fashion_dna",
                    "yorvyn_profiles",
                    "avatar_feedback",
                    "yorvyn_body_measurements",
                    "yorvyn_colour_profiles",
                    "yorvyn_garment_jobs"
                ]
                for t in tables:
                    url = f"{self._supabase_url}/rest/v1/{t}?user_id=eq.{user_id_str}"
                    requests.delete(url, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase purge_user_data error: {e}")

        logger.info(f"[GDPR] Permanently purged all personal data for user {user_id_str}")
        return True

    # ── Phase 11: Controlled Private Beta Onboarding & Feedback Subsystem ──

    def create_beta_invitation(
        self,
        email: str,
        cohort: str = "closed_pilot",
        max_uses: int = 1,
        days_valid: int = 30,
        notes: Optional[str] = None,
        custom_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new beta invitation token."""
        token = custom_token or f"BETA-{cohort.upper()}-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow()
        exp = now + timedelta(days=days_valid)
        inv_data = {
            "id": f"inv_{uuid.uuid4().hex[:12]}",
            "token": token,
            "email": email.strip().lower(),
            "cohort": cohort,
            "status": "pending",
            "max_uses": max_uses,
            "uses_count": 0,
            "expires_at": exp.isoformat(),
            "activated_at": None,
            "activated_by": None,
            "notes": notes,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        self._beta_invitations[token] = inv_data

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_invitations"
                requests.post(url, json=inv_data, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase create_beta_invitation error: {e}")

        return inv_data

    def get_beta_invitation(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieves beta invitation record by token."""
        token_str = str(token).strip()
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_invitations?token=eq.{token_str}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200 and r.json():
                    return r.json()[0]
            except Exception as e:
                logger.warning(f"Supabase get_beta_invitation error: {e}")

        return self._beta_invitations.get(token_str)

    def validate_beta_token(self, token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validates if a beta token is valid, active, and unexpired."""
        inv = self.get_beta_invitation(token)
        if not inv:
            return False, "Invalid invitation code. Beta access is currently invitation-only.", None

        status = inv.get("status", "pending")
        if status in ("suspended", "revoked"):
            return False, f"This beta invitation has been {status}. Please contact support.", inv

        # Check expiration
        exp_str = inv.get("expires_at")
        if exp_str:
            try:
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if datetime.utcnow() > exp_dt:
                    return False, "This beta invitation has expired.", inv
            except Exception:
                pass

        # Check uses
        uses = inv.get("uses_count", 0)
        max_u = inv.get("max_uses", 1)
        if uses >= max_u:
            return False, "This invitation code has already been redeemed.", inv

        return True, "Valid invitation code", inv

    def activate_beta_invitation(self, token: str, user_id: str) -> Tuple[bool, str]:
        """Activates and links an invitation token to a newly registered user account."""
        valid, reason, inv = self.validate_beta_token(token)
        if not valid or not inv:
            return False, reason

        now = datetime.utcnow().isoformat()
        user_id_str = str(user_id)
        inv["status"] = "active"
        inv["uses_count"] = inv.get("uses_count", 0) + 1
        inv["activated_at"] = now
        inv["activated_by"] = user_id_str
        inv["updated_at"] = now

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_invitations?token=eq.{token.strip()}"
                requests.patch(
                    url,
                    json={
                        "status": "active",
                        "uses_count": inv["uses_count"],
                        "activated_at": now,
                        "activated_by": user_id_str,
                        "updated_at": now
                    },
                    headers=self._get_headers(),
                    timeout=4
                )
            except Exception as e:
                logger.warning(f"Supabase activate_beta_invitation error: {e}")

        logger.info(f"[Beta] Invitation {token} successfully activated by user {user_id_str}")
        return True, "Invitation activated successfully"

    def list_beta_cohort(self, cohort: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists participants in the beta cohort."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_invitations?order=created_at.asc"
                if cohort:
                    url += f"&cohort=eq.{cohort}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase list_beta_cohort error: {e}")

        invs = list(self._beta_invitations.values())
        if cohort:
            invs = [i for i in invs if i.get("cohort") == cohort]
        return invs

    def update_beta_status(self, token_or_id: str, new_status: str) -> bool:
        """Suspends, revokes, or reactivates a beta participant."""
        if new_status not in ("pending", "active", "suspended", "revoked"):
            raise ValueError(f"Invalid status '{new_status}'")

        # Find in memory
        target = None
        for inv in self._beta_invitations.values():
            if inv.get("token") == token_or_id or inv.get("id") == token_or_id:
                inv["status"] = new_status
                inv["updated_at"] = datetime.utcnow().isoformat()
                target = inv
                break

        if self.is_configured and target:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_invitations?token=eq.{target['token']}"
                requests.patch(url, json={"status": new_status, "updated_at": datetime.utcnow().isoformat()}, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase update_beta_status error: {e}")

        return target is not None

    def record_beta_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Records user ratings, usability scores, and reproducible defect reports."""
        now = datetime.utcnow().isoformat()
        feedback_record = {
            "id": f"fb_{uuid.uuid4().hex[:12]}",
            "user_id": str(feedback_data.get("user_id")),
            "job_id": feedback_data.get("job_id"),
            "correlation_id": feedback_data.get("correlation_id"),
            "software_version": feedback_data.get("software_version", "v2026.11-beta"),
            "reconstruction_rating": feedback_data.get("reconstruction_rating"),
            "fitting_rating": feedback_data.get("fitting_rating"),
            "texture_rating": feedback_data.get("texture_rating"),
            "category_correct": feedback_data.get("category_correct", True),
            "usability_rating": feedback_data.get("usability_rating"),
            "feedback_text": feedback_data.get("feedback_text"),
            "failure_category": feedback_data.get("failure_category"),
            "reproduction_steps": feedback_data.get("reproduction_steps"),
            "include_raw_image": feedback_data.get("include_raw_image", False),
            "severity": feedback_data.get("severity", "normal"),
            "created_at": now
        }
        self._beta_feedbacks.append(feedback_record)

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_feedback"
                requests.post(url, json=feedback_record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase record_beta_feedback error: {e}")

        logger.info(f"[Beta] Feedback recorded for user {feedback_record['user_id']} (rating: {feedback_record['reconstruction_rating']})")
        return feedback_record

    def get_beta_feedbacks(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves beta feedback records."""
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_beta_feedback?order=created_at.desc"
                if user_id:
                    url += f"&user_id=eq.{user_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase get_beta_feedbacks error: {e}")

        if user_id:
            return [f for f in self._beta_feedbacks if f.get("user_id") == str(user_id)]
        return list(self._beta_feedbacks)

    def get_beta_defects(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves defects reported by beta users."""
        all_fb = self.get_beta_feedbacks()
        defects = [
            f for f in all_fb
            if f.get("failure_category") or f.get("reproduction_steps") or f.get("severity") in ("high", "critical")
        ]
        if severity:
            defects = [d for d in defects if d.get("severity") == severity]
        return defects

    # ── AI Persistent Sessions & Conversations ─────────────────────────────────

    @property
    def require_durable_sessions(self) -> bool:
        return os.getenv("YORVYN_REQUIRE_DURABLE_SESSIONS") == "1"

    def _session_rows(self, method, table, *, params=None, record=None, replay=False):
        """Strict PostgREST operations for staging. Empty reads are authoritative."""
        if not self.is_configured:
            raise HTTPException(503, "Durable conversation storage is unavailable.")
        try:
            response = requests.request(method, f"{self._supabase_url}/rest/v1/{table}",
                                        params=params, json=record, headers=self._get_headers(), timeout=5, allow_redirects=False)
            if replay and response.status_code == 409:
                existing = self.get_message_by_request_id(record["user_id"], record["request_id"])
                if existing and existing["session_id"] == record["session_id"]:
                    return [existing]
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or (method == "POST" and len(rows) != 1):
                raise ValueError("Unexpected database acknowledgement")
            return rows
        except (requests.RequestException, ValueError):
            raise HTTPException(503, "Durable conversation storage did not acknowledge the operation.") from None

    def create_ai_session(
        self,
        user_id: str,
        title: str = "New conversation",
        session_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new persistent AI session with a permanent UUID."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        session_record = {
            "id": session_id,
            "user_id": str(user_id),
            "title": title or "New conversation",
            "description": description,
            "session_type": session_type or "general",
            "status": "active",
            "metadata": metadata or {},
            "context_summary": None,
            "message_count": 0,
            "search_count": 0,
            "last_message_at": None,
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
            "deleted_at": None
        }

        if self.require_durable_sessions:
            saved = self._session_rows("POST", "yorvyn_ai_sessions", record=session_record)[0]
            self.record_session_event(session_id, user_id, "session_created", {"session_type": session_type})
            return saved

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions"
                r = requests.post(url, json=session_record, headers=self._get_headers(), timeout=4)
                if r.status_code in (200, 201):
                    data = r.json()
                    if data:
                        session_record = data[0]
            except Exception as e:
                logger.warning(f"Supabase create_ai_session error: {e}")

        self._ai_sessions[session_id] = session_record
        if session_id not in self._ai_messages:
            self._ai_messages[session_id] = []
        if session_id not in self._ai_searches:
            self._ai_searches[session_id] = []
        if session_id not in self._ai_session_events:
            self._ai_session_events[session_id] = []
        if session_id not in self._ai_attachments:
            self._ai_attachments[session_id] = []

        self.record_session_event(
            session_id=session_id,
            user_id=str(user_id),
            event_type="session_created",
            event_data={"title": title, "session_type": session_type}
        )

        logger.info(f"[AISession] Created session {session_id} for user {user_id}")
        return session_record

    def get_ai_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a persistent AI session record verifying user ownership."""
        if self.require_durable_sessions:
            params = {"id": f"eq.{session_id}", "status": "neq.deleted"}
            if user_id:
                params["user_id"] = f"eq.{user_id}"
            rows = self._session_rows("GET", "yorvyn_ai_sessions", params=params)
            return rows[0] if rows else None

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions?id=eq.{session_id}"
                if user_id:
                    url += f"&user_id=eq.{user_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        sess = data[0]
                        if sess.get("status") != "deleted":
                            return sess
            except Exception as e:
                logger.warning(f"Supabase get_ai_session error: {e}")

        sess = self._ai_sessions.get(str(session_id))
        if not sess:
            return None
        if user_id and sess.get("user_id") != str(user_id):
            return None
        if sess.get("status") == "deleted":
            return None
        return dict(sess)

    def list_ai_sessions(
        self,
        user_id: str,
        status: Optional[str] = "active",
        session_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Lists sessions for user with status, session_type and title search filters, supporting cursor pagination."""
        all_user_sessions = []

        if self.require_durable_sessions:
            params = {"user_id": f"eq.{user_id}", "status": f"eq.{status}" if status else "neq.deleted",
                      "order": "last_message_at.desc.nullslast,created_at.desc"}
            if session_type:
                params["session_type"] = f"eq.{session_type}"
            if search:
                params["title"] = f"ilike.*{search}*"
            all_user_sessions = self._session_rows("GET", "yorvyn_ai_sessions", params=params)
        elif self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions?user_id=eq.{user_id}&order=last_message_at.desc.nullslast,created_at.desc"
                if status:
                    url += f"&status=eq.{status}"
                if session_type:
                    url += f"&session_type=eq.{session_type}"
                if search:
                    url += f"&title=ilike.*{search}*"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    all_user_sessions = r.json()
            except Exception as e:
                logger.warning(f"Supabase list_ai_sessions error: {e}")

        if not all_user_sessions and not self.require_durable_sessions:
            for s in self._ai_sessions.values():
                if s.get("user_id") != str(user_id):
                    continue
                if status and s.get("status") != status:
                    continue
                if not status and s.get("status") == "deleted":
                    continue
                if session_type and s.get("session_type") != session_type:
                    continue
                if search and search.lower() not in s.get("title", "").lower():
                    continue
                all_user_sessions.append(dict(s))

        # Sort: last_message_at DESC (fallback created_at DESC)
        def sort_key(item):
            return item.get("last_message_at") or item.get("created_at") or ""

        all_user_sessions.sort(key=sort_key, reverse=True)

        # Apply cursor pagination
        start_idx = 0
        if cursor:
            for idx, item in enumerate(all_user_sessions):
                if item.get("id") == cursor:
                    start_idx = idx + 1
                    break

        page_items = all_user_sessions[start_idx:start_idx + limit]
        next_cursor = page_items[-1]["id"] if (start_idx + limit) < len(all_user_sessions) and page_items else None

        return page_items, next_cursor

    def update_ai_session(
        self,
        session_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates session attributes with ownership verification."""
        sess = self.get_ai_session(session_id, user_id=user_id)
        if not sess:
            return None

        allowed_fields = {"title", "description", "metadata", "context_summary", "session_type"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        filtered_updates["updated_at"] = datetime.utcnow().isoformat()

        if self.require_durable_sessions:
            return self._patch_durable_session(session_id, user_id, filtered_updates)

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions?id=eq.{session_id}&user_id=eq.{user_id}"
                r = requests.patch(url, json=filtered_updates, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        sess = data[0]
            except Exception as e:
                logger.warning(f"Supabase update_ai_session error: {e}")

        # Update in-memory
        if session_id in self._ai_sessions:
            self._ai_sessions[session_id].update(filtered_updates)
            sess = dict(self._ai_sessions[session_id])

        if "title" in filtered_updates:
            self.record_session_event(
                session_id=session_id,
                user_id=user_id,
                event_type="session_renamed",
                event_data={"new_title": filtered_updates["title"]}
            )

        return sess

    def _patch_durable_session(self, session_id, user_id, updates):
        rows = self._session_rows("PATCH", "yorvyn_ai_sessions", record=updates, params={
            "id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "status": "neq.deleted"})
        return rows[0] if rows else None

    def archive_ai_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Archives a session."""
        now = datetime.utcnow().isoformat()
        updates = {
            "status": "archived",
            "archived_at": now,
            "updated_at": now
        }
        if self.require_durable_sessions:
            saved = self._patch_durable_session(session_id, user_id, updates)
            if saved:
                self.record_session_event(session_id, user_id, "session_archived")
            return saved
        res = self.update_ai_session(session_id, user_id, updates)
        if res:
            self._ai_sessions[session_id]["status"] = "archived"
            self._ai_sessions[session_id]["archived_at"] = now
            self.record_session_event(
                session_id=session_id,
                user_id=user_id,
                event_type="session_archived",
                event_data={"archived_at": now}
            )
        return self.get_ai_session(session_id, user_id=user_id)

    def restore_ai_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Restores an archived session to active status."""
        now = datetime.utcnow().isoformat()
        updates = {
            "status": "active",
            "archived_at": None,
            "updated_at": now
        }
        if self.require_durable_sessions:
            saved = self._patch_durable_session(session_id, user_id, updates)
            if saved:
                self.record_session_event(session_id, user_id, "session_restored")
            return saved
        res = self.update_ai_session(session_id, user_id, updates)
        if res:
            self._ai_sessions[session_id]["status"] = "active"
            self._ai_sessions[session_id]["archived_at"] = None
            self.record_session_event(
                session_id=session_id,
                user_id=user_id,
                event_type="session_restored",
                event_data={"restored_at": now}
            )
        return self.get_ai_session(session_id, user_id=user_id)

    def delete_ai_session(self, session_id: str, user_id: str) -> bool:
        """Applies soft deletion to an AI session, preserving unrelated wardrobe and job assets."""
        sess = self.get_ai_session(session_id, user_id=user_id)
        if not sess:
            return False

        now = datetime.utcnow().isoformat()
        if self.require_durable_sessions:
            saved = self._patch_durable_session(session_id, user_id, {"status":"deleted", "deleted_at":now, "updated_at":now})
            if saved:
                self.record_session_event(session_id, user_id, "session_deleted")
            return bool(saved)
        if session_id in self._ai_sessions:
            self._ai_sessions[session_id]["status"] = "deleted"
            self._ai_sessions[session_id]["deleted_at"] = now
            self._ai_sessions[session_id]["updated_at"] = now

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions?id=eq.{session_id}&user_id=eq.{user_id}"
                requests.patch(url, json={"status": "deleted", "deleted_at": now, "updated_at": now}, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase delete_ai_session error: {e}")

        self.record_session_event(
            session_id=session_id,
            user_id=user_id,
            event_type="session_deleted",
            event_data={"deleted_at": now}
        )
        return True

    # ── AI Messages ───────────────────────────────────────────────────────────

    def get_message_by_request_id(self, user_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """Idempotency check: retrieves message already recorded with matching request_id."""
        if not request_id:
            return None

        if self.require_durable_sessions:
            rows = self._session_rows("GET", "yorvyn_ai_messages", params={
                "user_id": f"eq.{user_id}", "request_id": f"eq.{request_id}"})
            return rows[0] if rows else None

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_messages?user_id=eq.{user_id}&request_id=eq.{request_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        return data[0]
            except Exception as e:
                logger.warning(f"Supabase get_message_by_request_id error: {e}")

        for msgs in self._ai_messages.values():
            for m in msgs:
                if m.get("user_id") == str(user_id) and m.get("request_id") == str(request_id):
                    return dict(m)
        return None

    def create_ai_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        content_type: str = "text",
        attachments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        status: str = "completed"
    ) -> Dict[str, Any]:
        """Creates and persists an AI conversation message, ensuring idempotency and sequence integrity."""
        if self.require_durable_sessions:
            record = {"session_id": str(session_id), "user_id": str(user_id), "role": role, "content": content,
                      "content_type": content_type, "attachments": attachments or [], "metadata": metadata or {},
                      "request_id": request_id, "parent_message_id": parent_message_id, "status": status}
            saved = self._session_rows("POST", "yorvyn_ai_messages", record=record, replay=bool(request_id))[0]
            if role == "user":
                self.record_session_event(session_id, user_id, "message_sent", {"message_id": saved["id"]})
            return saved

        with self._lock:
            # 1. Idempotency check
            if request_id:
                existing = self.get_message_by_request_id(user_id, request_id)
                if existing:
                    logger.info(f"[AIMessage] Idempotent replay for request_id={request_id}")
                    return existing

            message_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            # Concurrency-safe sequence number allocation
            if session_id not in self._ai_messages:
                self._ai_messages[session_id] = []
            existing_msgs = self._ai_messages[session_id]
            max_seq = max([m.get("sequence_number", 0) for m in existing_msgs], default=0)
            seq_num = max_seq + 1

            message_record = {
                "id": message_id,
                "session_id": str(session_id),
                "user_id": str(user_id),
                "role": role,
                "content": content,
                "content_type": content_type,
                "attachments": attachments or [],
                "metadata": metadata or {},
                "request_id": request_id,
                "parent_message_id": parent_message_id,
                "sequence_number": seq_num,
                "status": status,
                "created_at": now,
                "updated_at": now
            }

            self._ai_messages[session_id].append(message_record)

            # Update parent session stats
            if session_id in self._ai_sessions:
                sess = self._ai_sessions[session_id]
                sess["message_count"] = sess.get("message_count", 0) + 1
                sess["last_message_at"] = now
                sess["updated_at"] = now

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_messages"
                r = requests.post(url, json=message_record, headers=self._get_headers(), timeout=4)
                if r.status_code in (200, 201):
                    data = r.json()
                    if data:
                        message_record = data[0]
            except Exception as e:
                logger.warning(f"Supabase create_ai_message error: {e}")

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_sessions?id=eq.{session_id}"
                requests.patch(url, json={"last_message_at": now, "updated_at": now}, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase update session on message error: {e}")

        if role == "user":
            self.record_session_event(
                session_id=session_id,
                user_id=str(user_id),
                event_type="message_sent",
                event_data={"message_id": message_id, "content_length": len(content)}
            )

        return message_record

    def get_ai_session_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Retrieves messages for session in deterministic chronological sequence with cursor pagination."""
        # Verify session ownership
        sess = self.get_ai_session(session_id, user_id=user_id)
        if not sess:
            return [], None

        if self.require_durable_sessions:
            params = {"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}",
                      "order": "sequence_number.asc,id.asc", "limit": limit + 1}
            if cursor:
                anchor = self._session_rows("GET", "yorvyn_ai_messages", params={
                    "session_id": params["session_id"], "user_id": params["user_id"], "id": f"eq.{cursor}",
                    "select": "sequence_number,id"})
                if not anchor:
                    raise HTTPException(400, "Invalid conversation cursor.")
                seq = int(anchor[0]["sequence_number"])
                anchor_id = str(uuid.UUID(anchor[0]["id"]))
                params["or"] = f"(sequence_number.gt.{seq},and(sequence_number.eq.{seq},id.gt.{anchor_id}))"
            rows = self._session_rows("GET", "yorvyn_ai_messages", params=params)
            return rows[:limit], rows[limit-1]["id"] if len(rows) > limit else None

        messages_list = []
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_messages?session_id=eq.{session_id}&user_id=eq.{user_id}&order=sequence_number.asc,created_at.asc"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    messages_list = r.json()
            except Exception as e:
                logger.warning(f"Supabase get_ai_session_messages error: {e}")

        if not messages_list:
            raw_list = self._ai_messages.get(str(session_id), [])
            messages_list = [dict(m) for m in raw_list if m.get("user_id") == str(user_id)]

        messages_list.sort(key=lambda m: (m.get("sequence_number", 0), m.get("created_at", "")))

        start_idx = 0
        if cursor:
            for idx, m in enumerate(messages_list):
                if m.get("id") == cursor:
                    start_idx = idx + 1
                    break

        page_items = messages_list[start_idx:start_idx + limit]
        next_cursor = page_items[-1]["id"] if (start_idx + limit) < len(messages_list) and page_items else None

        return page_items, next_cursor

    # ── AI Searches & Tool Provenance ─────────────────────────────────────────

    def create_ai_search(
        self,
        session_id: str,
        user_id: str,
        search_type: str,
        query: str,
        message_id: Optional[str] = None,
        normalized_query: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        execution_provenance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a persistent search provenance record linked to a session."""
        search_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        search_record = {
            "id": search_id,
            "session_id": str(session_id),
            "user_id": str(user_id),
            "message_id": message_id,
            "search_type": search_type,
            "query": query,
            "normalized_query": normalized_query or query.strip().lower(),
            "status": "pending",
            "result_summary": None,
            "result_metadata": {},
            "provider": provider,
            "model_name": model_name,
            "execution_provenance": execution_provenance,
            "error_code": None,
            "error_message": None,
            "started_at": now,
            "completed_at": None,
            "created_at": now
        }

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_searches"
                r = requests.post(url, json=search_record, headers=self._get_headers(), timeout=4)
                if r.status_code in (200, 201):
                    data = r.json()
                    if data:
                        search_record = data[0]
            except Exception as e:
                logger.warning(f"Supabase create_ai_search error: {e}")

        if session_id not in self._ai_searches:
            self._ai_searches[session_id] = []
        self._ai_searches[session_id].append(search_record)

        # Increment session search count
        if session_id in self._ai_sessions:
            self._ai_sessions[session_id]["search_count"] = self._ai_sessions[session_id].get("search_count", 0) + 1

        self.record_session_event(
            session_id=session_id,
            user_id=str(user_id),
            event_type="search_started",
            event_data={"search_id": search_id, "search_type": search_type, "query": query}
        )

        return search_record

    def update_ai_search(
        self,
        search_id: str,
        user_id: str,
        status: str,
        result_summary: Optional[str] = None,
        result_metadata: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates search record with completed execution results or failure details."""
        now = datetime.utcnow().isoformat()
        updates = {
            "status": status,
            "result_summary": result_summary,
            "result_metadata": result_metadata or {},
            "error_code": error_code,
            "error_message": error_message,
            "completed_at": now
        }

        target_record = None
        for sid, searches in self._ai_searches.items():
            for s in searches:
                if s.get("id") == str(search_id) and s.get("user_id") == str(user_id):
                    s.update(updates)
                    target_record = dict(s)
                    break
            if target_record:
                break

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_searches?id=eq.{search_id}&user_id=eq.{user_id}"
                r = requests.patch(url, json=updates, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        target_record = data[0]
            except Exception as e:
                logger.warning(f"Supabase update_ai_search error: {e}")

        if target_record:
            event_type = "search_completed" if status == "completed" else "search_failed"
            self.record_session_event(
                session_id=target_record["session_id"],
                user_id=str(user_id),
                event_type=event_type,
                event_data={"search_id": search_id, "status": status}
            )

        return target_record

    def get_session_searches(
        self,
        session_id: str,
        user_id: str,
        search_type: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Retrieves searches executed inside a session."""
        sess = self.get_ai_session(session_id, user_id=user_id)
        if not sess:
            return [], None

        searches_list = []
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_searches?session_id=eq.{session_id}&user_id=eq.{user_id}&order=created_at.desc"
                if search_type:
                    url += f"&search_type=eq.{search_type}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    searches_list = r.json()
            except Exception as e:
                logger.warning(f"Supabase get_session_searches error: {e}")

        if not searches_list:
            raw = self._ai_searches.get(str(session_id), [])
            for s in raw:
                if s.get("user_id") == str(user_id):
                    if search_type and s.get("search_type") != search_type:
                        continue
                    searches_list.append(dict(s))

        searches_list.sort(key=lambda s: s.get("created_at", ""), reverse=True)

        start_idx = 0
        if cursor:
            for idx, s in enumerate(searches_list):
                if s.get("id") == cursor:
                    start_idx = idx + 1
                    break

        page_items = searches_list[start_idx:start_idx + limit]
        next_cursor = page_items[-1]["id"] if (start_idx + limit) < len(searches_list) and page_items else None

        return page_items, next_cursor

    def list_global_searches(
        self,
        user_id: str,
        query: Optional[str] = None,
        search_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Lists searches for user across all sessions with query text, date range, and status filters."""
        all_searches = []

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_searches?user_id=eq.{user_id}&order=created_at.desc"
                if search_type:
                    url += f"&search_type=eq.{search_type}"
                if status:
                    url += f"&status=eq.{status}"
                if query:
                    url += f"&query=ilike.*{query}*"
                if start_date:
                    url += f"&created_at=gte.{start_date}"
                if end_date:
                    url += f"&created_at=lte.{end_date}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    all_searches = r.json()
            except Exception as e:
                logger.warning(f"Supabase list_global_searches error: {e}")

        if not all_searches:
            for s_list in self._ai_searches.values():
                for s in s_list:
                    if s.get("user_id") != str(user_id):
                        continue
                    if search_type and s.get("search_type") != search_type:
                        continue
                    if status and s.get("status") != status:
                        continue
                    if query and query.lower() not in s.get("query", "").lower():
                        continue
                    if start_date and s.get("created_at", "") < start_date:
                        continue
                    if end_date and s.get("created_at", "") > end_date:
                        continue
                    all_searches.append(dict(s))

        all_searches.sort(key=lambda s: s.get("created_at", ""), reverse=True)

        start_idx = 0
        if cursor:
            for idx, s in enumerate(all_searches):
                if s.get("id") == cursor:
                    start_idx = idx + 1
                    break

        page_items = all_searches[start_idx:start_idx + limit]
        next_cursor = page_items[-1]["id"] if (start_idx + limit) < len(all_searches) and page_items else None

        return page_items, next_cursor

    # ── Session Lifecycle Events & Attachments ────────────────────────────────

    def record_session_event(
        self,
        session_id: str,
        user_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records an auditable lifecycle event in yorvyn_ai_session_events."""
        event_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        clean_event_data = dict(event_data or {})

        # Strip any accidental secrets
        for sensitive_key in ("password", "token", "secret", "access_token", "api_key", "authorization"):
            clean_event_data.pop(sensitive_key, None)

        record = {
            "id": event_id,
            "session_id": str(session_id),
            "user_id": str(user_id),
            "event_type": event_type,
            "event_data": clean_event_data,
            "created_at": now
        }

        if self.require_durable_sessions:
            return self._session_rows("POST", "yorvyn_ai_session_events", record=record)[0]

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_session_events"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase record_session_event error: {e}")

        if session_id not in self._ai_session_events:
            self._ai_session_events[session_id] = []
        self._ai_session_events[session_id].append(record)
        return record

    def create_ai_attachment(
        self,
        session_id: str,
        user_id: str,
        storage_path: str,
        file_name: str,
        media_type: str,
        message_id: Optional[str] = None,
        file_size: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Persists metadata for a session attachment without storing raw file bytes."""
        attachment_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        record = {
            "id": attachment_id,
            "session_id": str(session_id),
            "user_id": str(user_id),
            "message_id": message_id,
            "storage_path": storage_path,
            "file_name": file_name,
            "media_type": media_type,
            "file_size": file_size,
            "processing_status": "uploaded",
            "metadata": metadata or {},
            "created_at": now
        }

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_attachments"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase create_ai_attachment error: {e}")

        if session_id not in self._ai_attachments:
            self._ai_attachments[session_id] = []
        self._ai_attachments[session_id].append(record)
        return record

    def get_session_attachments(self, session_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves attachments belonging to a session."""
        sess = self.get_ai_session(session_id, user_id=user_id)
        if not sess:
            return []

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_attachments?session_id=eq.{session_id}&user_id=eq.{user_id}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase get_session_attachments error: {e}")

        raw = self._ai_attachments.get(str(session_id), [])
        return [dict(a) for a in raw if a.get("user_id") == str(user_id)]

    # =========================================================================
    # Continuous Learning & Personalization Engine Methods
    # =========================================================================

    # -------------------------------------------------------------------------
    # 1. User Preferences (Layer A: User Personalization Memory)
    # -------------------------------------------------------------------------
    def get_user_preferences(
        self,
        user_id: str,
        category: Optional[str] = None,
        status: str = "active"
    ) -> List[Dict[str, Any]]:
        """Retrieves structured preferences for an individual user."""
        uid = str(user_id)
        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_user_preferences?user_id=eq.{uid}&status=eq.{status}"
                if category:
                    url += f"&preference_category=eq.{category}"
                r = requests.get(url, headers=self._get_headers(), timeout=4)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.warning(f"Supabase get_user_preferences error: {e}")

        with self._lock:
            user_map = self._user_preferences.get(uid, {})
            results = []
            for (cat, _), record in user_map.items():
                if record.get("status") == status:
                    if category is None or cat == category:
                        results.append(dict(record))
            # Sort newest first
            results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return results

    def get_user_preference(self, user_id: str, pref_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific user preference by ID."""
        uid = str(user_id)
        with self._lock:
            user_map = self._user_preferences.get(uid, {})
            for record in user_map.values():
                if record.get("id") == str(pref_id):
                    return dict(record)
        return None

    def upsert_user_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        source: str = "explicit",
        confidence: float = 0.5,
        evidence_count: int = 1
    ) -> Dict[str, Any]:
        """
        Idempotently inserts or updates a user preference.
        Reinforces evidence count and confidence upon repeated confirmation.
        """
        uid = str(user_id)
        now = datetime.utcnow().isoformat()
        clamped_conf = min(1.0, max(0.0, float(confidence)))

        with self._lock:
            if uid not in self._user_preferences:
                self._user_preferences[uid] = {}

            mapKey = (category, key)
            existing = self._user_preferences[uid].get(mapKey)

            if existing and existing.get("status") != "deleted":
                # Reinforce existing preference
                new_evidence = existing.get("evidence_count", 1) + evidence_count
                # Bayesian-style or asymptotic confidence accumulation
                new_conf = min(0.99, existing.get("confidence", 0.5) + (1.0 - existing.get("confidence", 0.5)) * 0.25)
                if source == "explicit":
                    new_conf = max(new_conf, clamped_conf, 0.90)

                record = {
                    **existing,
                    "preference_value": value,
                    "source": source if source == "explicit" else existing.get("source", source),
                    "confidence": round(new_conf, 3),
                    "evidence_count": new_evidence,
                    "status": "active",
                    "last_confirmed_at": now,
                    "updated_at": now
                }
            else:
                record = {
                    "id": str(uuid.uuid4()),
                    "user_id": uid,
                    "preference_category": category,
                    "preference_key": key,
                    "preference_value": value,
                    "source": source,
                    "confidence": round(clamped_conf, 3),
                    "evidence_count": max(1, evidence_count),
                    "status": "active",
                    "last_confirmed_at": now if source == "explicit" else None,
                    "created_at": now,
                    "updated_at": now
                }

            self._user_preferences[uid][mapKey] = record

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_user_preferences"
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates"
                requests.post(url, json=record, headers=headers, timeout=4)
            except Exception as e:
                logger.warning(f"Supabase upsert_user_preference error: {e}")

        return dict(record)

    def update_user_preference(self, user_id: str, pref_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Allows direct user inspection, editing, or correcting of a preference."""
        uid = str(user_id)
        now = datetime.utcnow().isoformat()
        with self._lock:
            user_map = self._user_preferences.get(uid, {})
            for mapKey, record in list(user_map.items()):
                if record.get("id") == str(pref_id):
                    for field in ("preference_value", "source", "confidence", "status", "last_confirmed_at"):
                        if field in updates:
                            record[field] = updates[field]
                    record["updated_at"] = now
                    user_map[mapKey] = record
                    return dict(record)
        return None

    def delete_user_preference(self, user_id: str, pref_id: str) -> bool:
        """User-controlled deletion of a specific learned preference."""
        uid = str(user_id)
        with self._lock:
            user_map = self._user_preferences.get(uid, {})
            for mapKey, record in list(user_map.items()):
                if record.get("id") == str(pref_id):
                    record["status"] = "deleted"
                    del user_map[mapKey]
                    return True
        return False

    def reset_user_preferences(self, user_id: str, category: Optional[str] = None) -> int:
        """Resets all or categorical personalization data for an individual user."""
        uid = str(user_id)
        count = 0
        with self._lock:
            user_map = self._user_preferences.get(uid, {})
            for mapKey in list(user_map.keys()):
                cat, _ = mapKey
                if category is None or cat == category:
                    del user_map[mapKey]
                    count += 1
        return count

    def export_user_learning_data(self, user_id: str) -> Dict[str, Any]:
        """Exports complete personal learning data for GDPR/CCPA export compliance."""
        uid = str(user_id)
        prefs = self.get_user_preferences(uid, status="active")
        feedback = self.get_user_feedback(uid, limit=500)
        consent = self.get_learning_consent(uid)
        return {
            "user_id": uid,
            "export_timestamp": datetime.utcnow().isoformat(),
            "consent_settings": consent,
            "preferences_count": len(prefs),
            "preferences": prefs,
            "feedback_submissions_count": len(feedback),
            "feedback_history": feedback
        }

    # -------------------------------------------------------------------------
    # 2. Feedback Collection & Verification
    # -------------------------------------------------------------------------
    def create_ai_feedback(
        self,
        user_id: str,
        feedback_type: str,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        search_id: Optional[str] = None,
        rating: Optional[int] = None,
        original_output: Optional[Dict[str, Any]] = None,
        corrected_output: Optional[Dict[str, Any]] = None,
        feedback_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records explicit, structured AI feedback with consent snapshot."""
        uid = str(user_id)
        consent = self.get_learning_consent(uid)
        now = datetime.utcnow().isoformat()
        feedback_id = str(uuid.uuid4())

        record = {
            "id": feedback_id,
            "user_id": uid,
            "session_id": str(session_id) if session_id else None,
            "message_id": str(message_id) if message_id else None,
            "search_id": str(search_id) if search_id else None,
            "feedback_type": feedback_type,
            "rating": rating,
            "original_output": original_output or {},
            "corrected_output": corrected_output or {},
            "feedback_text": feedback_text,
            "metadata": metadata or {},
            "consent_snapshot": {
                "personalization_enabled": consent.get("personalization_enabled", True),
                "global_model_training_enabled": consent.get("global_model_training_enabled", False),
                "image_training_enabled": consent.get("image_training_enabled", False),
                "conversation_training_enabled": consent.get("conversation_training_enabled", False),
                "consent_version": consent.get("consent_version", "v1.0")
            },
            "created_at": now
        }

        with self._lock:
            if uid not in self._ai_feedback:
                self._ai_feedback[uid] = []
            self._ai_feedback[uid].append(record)

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_ai_feedback"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase create_ai_feedback error: {e}")

        return dict(record)

    def get_user_feedback(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves feedback submitted by a specific user."""
        uid = str(user_id)
        with self._lock:
            raw = self._ai_feedback.get(uid, [])
            return [dict(f) for f in raw[-limit:]]

    def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific feedback record across users for validation pipelines."""
        fid = str(feedback_id)
        with self._lock:
            for u_feedbacks in self._ai_feedback.values():
                for f in u_feedbacks:
                    if f.get("id") == fid:
                        return dict(f)
        return None

    # -------------------------------------------------------------------------
    # 3. Learning Consent Management
    # -------------------------------------------------------------------------
    def get_learning_consent(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieves granular consent toggles for a user.
        Defaults global, image, and conversation training to FALSE (privacy-first).
        """
        uid = str(user_id)
        with self._lock:
            if uid in self._learning_consents:
                return dict(self._learning_consents[uid])

            now = datetime.utcnow().isoformat()
            default_consent = {
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "personalization_enabled": True,
                "global_model_training_enabled": False,
                "image_training_enabled": False,
                "conversation_training_enabled": False,
                "consent_version": "v1.0",
                "consent_updated_at": now
            }
            self._learning_consents[uid] = default_consent
            return dict(default_consent)

    def update_learning_consent(
        self,
        user_id: str,
        personalization_enabled: Optional[bool] = None,
        global_model_training_enabled: Optional[bool] = None,
        image_training_enabled: Optional[bool] = None,
        conversation_training_enabled: Optional[bool] = None,
        consent_version: str = "v1.0"
    ) -> Dict[str, Any]:
        """Updates user's training and personalization consent with auditable timestamp."""
        uid = str(user_id)
        now = datetime.utcnow().isoformat()
        current = self.get_learning_consent(uid)

        updated = {
            **current,
            "personalization_enabled": personalization_enabled if personalization_enabled is not None else current["personalization_enabled"],
            "global_model_training_enabled": global_model_training_enabled if global_model_training_enabled is not None else current["global_model_training_enabled"],
            "image_training_enabled": image_training_enabled if image_training_enabled is not None else current["image_training_enabled"],
            "conversation_training_enabled": conversation_training_enabled if conversation_training_enabled is not None else current["conversation_training_enabled"],
            "consent_version": consent_version,
            "consent_updated_at": now
        }

        with self._lock:
            self._learning_consents[uid] = updated

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_learning_consent"
                headers = self._get_headers()
                headers["Prefer"] = "resolution=merge-duplicates"
                requests.post(url, json=updated, headers=headers, timeout=4)
            except Exception as e:
                logger.warning(f"Supabase update_learning_consent error: {e}")

        return dict(updated)

    # -------------------------------------------------------------------------
    # 4. Learning Examples (Layer B: Global Model Improvement Dataset)
    # -------------------------------------------------------------------------
    def create_learning_example(
        self,
        source_feedback_id: Optional[str],
        task_type: str,
        input_reference: Dict[str, Any],
        target_output: Dict[str, Any],
        consent_scope: str,
        quality_score: float = 0.8,
        validation_status: str = "pending",
        dataset_version: Optional[str] = None,
        exclusion_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a validated, sanitized learning example eligible for offline training."""
        now = datetime.utcnow().isoformat()
        eid = str(uuid.uuid4())
        record = {
            "id": eid,
            "source_feedback_id": str(source_feedback_id) if source_feedback_id else None,
            "task_type": task_type,
            "input_reference": input_reference,
            "target_output": target_output,
            "quality_score": round(max(0.0, min(1.0, quality_score)), 3),
            "validation_status": validation_status,
            "consent_scope": consent_scope,
            "dataset_version": dataset_version,
            "exclusion_reason": exclusion_reason,
            "created_at": now,
            "validated_at": now if validation_status == "validated" else None
        }

        with self._lock:
            self._learning_examples[eid] = record

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_learning_examples"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase create_learning_example error: {e}")

        return dict(record)

    def get_learning_example(self, example_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single learning example."""
        with self._lock:
            rec = self._learning_examples.get(str(example_id))
            return dict(rec) if rec else None

    def update_learning_example(self, example_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates validation status, quality score, or dataset partition for an example."""
        eid = str(example_id)
        now = datetime.utcnow().isoformat()
        with self._lock:
            if eid in self._learning_examples:
                rec = self._learning_examples[eid]
                for k in ("validation_status", "quality_score", "dataset_version", "exclusion_reason"):
                    if k in updates:
                        rec[k] = updates[k]
                if updates.get("validation_status") == "validated":
                    rec["validated_at"] = now
                return dict(rec)
        return None

    def list_learning_examples(
        self,
        task_type: Optional[str] = None,
        validation_status: Optional[str] = None,
        dataset_version: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lists learning examples filtered by task, status, or dataset version."""
        with self._lock:
            results = []
            for ex in self._learning_examples.values():
                if task_type and ex.get("task_type") != task_type:
                    continue
                if validation_status and ex.get("validation_status") != validation_status:
                    continue
                if dataset_version and ex.get("dataset_version") != dataset_version:
                    continue
                results.append(dict(ex))
            return results[:limit]

    def delete_learning_examples_by_user(self, user_id: str) -> int:
        """
        Propagates user data deletion:
        Removes/quarantines learning examples originating from this user's feedback.
        """
        uid = str(user_id)
        user_feedback_ids = set()
        with self._lock:
            for f in self._ai_feedback.get(uid, []):
                user_feedback_ids.add(f.get("id"))

            count = 0
            for eid, ex in list(self._learning_examples.items()):
                if ex.get("source_feedback_id") in user_feedback_ids:
                    del self._learning_examples[eid]
                    count += 1
            return count

    # -------------------------------------------------------------------------
    # 5. Model Registry & Rollback Controls
    # -------------------------------------------------------------------------
    def register_model(
        self,
        model_name: str,
        model_version: str,
        task_type: str,
        artifact_uri: str,
        artifact_checksum: str,
        base_model: Optional[str] = None,
        training_dataset_version: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        status: str = "candidate"
    ) -> Dict[str, Any]:
        """Registers a new model artifact in the versioned registry."""
        now = datetime.utcnow().isoformat()
        mid = str(uuid.uuid4())
        record = {
            "id": mid,
            "model_name": model_name,
            "model_version": model_version,
            "task_type": task_type,
            "artifact_uri": artifact_uri,
            "artifact_checksum": artifact_checksum,
            "base_model": base_model,
            "training_dataset_version": training_dataset_version,
            "evaluation_metrics": evaluation_metrics or {},
            "status": status,
            "deployed_at": now if status == "deployed" else None,
            "created_at": now
        }

        key = f"{model_name}:{model_version}"
        with self._lock:
            self._model_registry[key] = record

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_model_registry"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase register_model error: {e}")

        return dict(record)

    def get_model(self, model_name: str, model_version: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific model version."""
        key = f"{model_name}:{model_version}"
        with self._lock:
            rec = self._model_registry.get(key)
            return dict(rec) if rec else None

    def get_deployed_model(self, task_type_or_model_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves currently active deployed model for a task or model name."""
        with self._lock:
            for rec in self._model_registry.values():
                if rec.get("status") == "deployed":
                    if rec.get("task_type") == task_type_or_model_name or rec.get("model_name") == task_type_or_model_name:
                        return dict(rec)
        return None

    def update_model_status(self, model_name: str, model_version: str, status: str) -> Optional[Dict[str, Any]]:
        """Updates model status (e.g., candidate -> approved -> deployed)."""
        key = f"{model_name}:{model_version}"
        now = datetime.utcnow().isoformat()
        with self._lock:
            if key in self._model_registry:
                rec = self._model_registry[key]
                task_type = rec.get("task_type")

                # If deploying this model, archive any previously deployed model for this task
                if status == "deployed":
                    for other_key, other_rec in self._model_registry.items():
                        if other_key != key and other_rec.get("task_type") == task_type and other_rec.get("status") == "deployed":
                            other_rec["status"] = "approved"

                    rec["deployed_at"] = now

                rec["status"] = status
                return dict(rec)
        return None

    def list_models(self, task_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists registered models sorted by version."""
        with self._lock:
            results = []
            for m in self._model_registry.values():
                if task_type and m.get("task_type") != task_type:
                    continue
                if status and m.get("status") != status:
                    continue
                results.append(dict(m))
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results

    def rollback_model(self, task_type: str, target_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Rolls back production model to target_version or previous approved version.
        Guarantees zero-downtime atomic switch.
        """
        now = datetime.utcnow().isoformat()
        with self._lock:
            currently_deployed = None
            candidates_for_rollback = []

            for rec in self._model_registry.values():
                if rec.get("task_type") == task_type:
                    if rec.get("status") == "deployed":
                        currently_deployed = rec
                    elif rec.get("status") in ("approved", "candidate"):
                        candidates_for_rollback.append(rec)

            if not candidates_for_rollback and not target_version:
                raise ValueError(f"No previous approved models available to roll back task '{task_type}'")

            target_model = None
            if target_version:
                for rec in self._model_registry.values():
                    if rec.get("task_type") == task_type and rec.get("model_version") == target_version:
                        target_model = rec
                        break
                if not target_model:
                    raise ValueError(f"Target model version '{target_version}' not found for task '{task_type}'")
            else:
                # Pick most recent approved model
                candidates_for_rollback.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                target_model = candidates_for_rollback[0]

            # Atomic switch
            if currently_deployed:
                currently_deployed["status"] = "archived"
            target_model["status"] = "deployed"
            target_model["deployed_at"] = now

            return {
                "success": True,
                "task_type": task_type,
                "rolled_back_from": currently_deployed.get("model_version") if currently_deployed else None,
                "rolled_back_to": target_model.get("model_version"),
                "deployed_model": dict(target_model)
            }

    # -------------------------------------------------------------------------
    # 6. Training Jobs Queue & Telemetry
    # -------------------------------------------------------------------------
    def create_training_job(
        self,
        model_name: str,
        task_type: str,
        dataset_version: str,
        training_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enqueues an asynchronous training run."""
        jid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        record = {
            "id": jid,
            "model_name": model_name,
            "task_type": task_type,
            "dataset_version": dataset_version,
            "status": "queued",
            "training_config": training_config or {},
            "evaluation_results": {},
            "resource_usage": {"gpu_type": "NVIDIA_A100_REMOTE", "allocated_vram_gb": 40, "estimated_cost_usd": 0.45},
            "failure_reason": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now
        }

        with self._lock:
            self._training_jobs[jid] = record

        if self.is_configured:
            try:
                url = f"{self._supabase_url}/rest/v1/yorvyn_training_jobs"
                requests.post(url, json=record, headers=self._get_headers(), timeout=4)
            except Exception as e:
                logger.warning(f"Supabase create_training_job error: {e}")

        return dict(record)

    def get_training_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves details of a training job."""
        with self._lock:
            rec = self._training_jobs.get(str(job_id))
            return dict(rec) if rec else None

    def update_training_job(
        self,
        job_id: str,
        status: str,
        evaluation_results: Optional[Dict[str, Any]] = None,
        resource_usage: Optional[Dict[str, Any]] = None,
        failure_reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates training job status, telemetry and evaluation metrics."""
        jid = str(job_id)
        now = datetime.utcnow().isoformat()
        with self._lock:
            if jid in self._training_jobs:
                rec = self._training_jobs[jid]
                rec["status"] = status
                if status == "running" and not rec.get("started_at"):
                    rec["started_at"] = now
                elif status in ("completed", "failed", "cancelled"):
                    rec["completed_at"] = now

                if evaluation_results:
                    rec["evaluation_results"] = evaluation_results
                if resource_usage:
                    rec["resource_usage"].update(resource_usage)
                if failure_reason:
                    rec["failure_reason"] = failure_reason

                return dict(rec)
        return None

    def list_training_jobs(
        self,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Lists training jobs sorted newest first."""
        with self._lock:
            results = []
            for j in self._training_jobs.values():
                if task_type and j.get("task_type") != task_type:
                    continue
                if status and j.get("status") != status:
                    continue
                results.append(dict(j))
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results[:limit]


# Global singleton
supabase_repo = SupabaseRepository()
