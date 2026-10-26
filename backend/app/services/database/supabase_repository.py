"""
Supabase PostgreSQL Database Repository for Yorvyn.
Handles persistence for profiles, digital wardrobe, garment 3D jobs,
conversations, and legacy Firebase UID relinking.
Includes robust offline fallback store for local testing and CI runners.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
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


# Global singleton
supabase_repo = SupabaseRepository()
