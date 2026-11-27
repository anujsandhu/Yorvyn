"""
Yorvyn Centralized Entitlement & Quota Enforcement Service.
Controls server-side feature access, monthly reconstruction quotas,
saved look limits, priority queue routing, and commercial asset rights.
"""

import logging
import threading
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

from backend.app.core.billing_config import SUBSCRIPTION_PLANS, get_plan_definition, PlanEntitlements
from backend.app.services.database.supabase_repository import supabase_repo

logger = logging.getLogger(__name__)


class EntitlementService:
    """Enforces subscription entitlements, quotas, and feature flags."""

    def __init__(self):
        self._repo = supabase_repo
        self._lock = threading.Lock()
        self._pending_reconstructions: Dict[str, int] = {}

    def get_user_plan_and_sub(self, user_id: str) -> Tuple[PlanEntitlements, Dict[str, Any]]:
        """Retrieves user's active subscription and corresponding plan definition."""
        sub = self._repo.get_subscription(user_id) or {
            "user_id": user_id,
            "plan_id": "explorer",
            "status": "active",
            "current_period_start": datetime.utcnow().isoformat()
        }
        plan_id = sub.get("plan_id", "explorer")
        status = sub.get("status", "active")

        # If subscription is past_due or canceled, degrade to explorer entitlements
        if status not in ("active", "trialing"):
            plan_id = "explorer"

        plan = get_plan_definition(plan_id)
        return plan, sub

    def get_user_entitlements(self, user_id: str) -> Dict[str, Any]:
        """Provides full entitlement and usage status for frontend telemetry."""
        plan, sub = self.get_user_plan_and_sub(user_id)
        period_start = sub.get("current_period_start", datetime.utcnow().isoformat())

        used_reconstructions = self._repo.get_monthly_usage_count(
            user_id=user_id,
            metric="garment_reconstruction",
            period_start=period_start
        )

        quota = plan.monthly_reconstructions
        remaining = max(0, quota - used_reconstructions) if quota != -1 else -1

        return {
            "user_id": user_id,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "subscription_status": sub.get("status", "active"),
            "current_period_end": sub.get("current_period_end"),
            "cancel_at_period_end": sub.get("cancel_at_period_end", False),
            "reconstructions": {
                "quota": quota,
                "used": used_reconstructions,
                "remaining": remaining,
                "is_unlimited": quota == -1,
                "fair_use_limit": plan.fair_use_reconstructions
            },
            "features": {
                "max_saved_looks": plan.max_saved_looks,
                "high_res_textures": plan.high_res_textures,
                "priority_queue": plan.priority_queue,
                "commercial_export": plan.commercial_export,
                "multi_avatar": plan.multi_avatar,
                "custom_materials": plan.custom_materials
            }
        }

    def check_reconstruction_entitlement(self, user_id: str) -> Tuple[bool, str]:
        """
        Server-side validation before job creation.
        Returns (is_allowed, reason).
        Takes into account in-flight reserved slots to prevent race-condition quota bypass.
        """
        plan, sub = self.get_user_plan_and_sub(user_id)
        period_start = sub.get("current_period_start", datetime.utcnow().isoformat())

        used = self._repo.get_monthly_usage_count(
            user_id=user_id,
            metric="garment_reconstruction",
            period_start=period_start
        )
        pending = self._pending_reconstructions.get(user_id, 0)
        total_in_flight = used + pending

        # Unlimited plans (Pro Atelier & Studio)
        if plan.monthly_reconstructions == -1:
            # Check Pro fair use soft ceiling
            if plan.fair_use_reconstructions > 0 and total_in_flight >= plan.fair_use_reconstructions:
                logger.info(
                    f"[Entitlement] User {user_id} on {plan.name} reached fair use soft cap "
                    f"({total_in_flight}/{plan.fair_use_reconstructions}). Queue priority de-escalated to standard."
                )
                return True, "FAIR_USE_WARNING: Fair use threshold reached; queue priority shifted to standard."
            return True, "OK"

        if total_in_flight >= plan.monthly_reconstructions:
            return (
                False,
                f"Monthly 3D garment reconstruction quota reached ({total_in_flight}/{plan.monthly_reconstructions}). "
                f"Upgrade to Pro Atelier for unlimited reconstructions."
            )

        return True, "OK"

    def reserve_reconstruction_slot(self, user_id: str) -> Tuple[bool, str]:
        """Atomically checks entitlement and reserves a reconstruction quota slot."""
        with self._lock:
            allowed, reason = self.check_reconstruction_entitlement(user_id)
            if not allowed:
                return False, reason
            self._pending_reconstructions[user_id] = self._pending_reconstructions.get(user_id, 0) + 1
            return True, "OK"

    def release_reconstruction_slot(self, user_id: str):
        """Releases the reserved slot (on completion or failure)."""
        with self._lock:
            count = self._pending_reconstructions.get(user_id, 0)
            if count > 1:
                self._pending_reconstructions[user_id] = count - 1
            elif user_id in self._pending_reconstructions:
                del self._pending_reconstructions[user_id]

    def record_reconstruction_usage(
        self,
        user_id: str,
        job_id: str,
        cost_usd: float = 0.0,
        provenance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records completed reconstruction into usage accounting."""
        plan, sub = self.get_user_plan_and_sub(user_id)
        period_start = sub.get("current_period_start", datetime.utcnow().isoformat())
        period_end = sub.get("current_period_end", datetime.utcnow().isoformat())

        return self._repo.record_usage(
            user_id=user_id,
            metric="garment_reconstruction",
            quantity=1,
            job_id=job_id,
            cost_usd=cost_usd,
            period_start=period_start,
            period_end=period_end,
            provenance=provenance
        )

    def can_save_look(self, user_id: str, current_look_count: int) -> Tuple[bool, str]:
        """Validates saved look capacity for plan."""
        plan, _ = self.get_user_plan_and_sub(user_id)
        if plan.max_saved_looks == -1:
            return True, "OK"

        if current_look_count >= plan.max_saved_looks:
            return (
                False,
                f"Saved looks capacity reached ({current_look_count}/{plan.max_saved_looks}). "
                f"Upgrade to Pro Atelier for unlimited saved looks."
            )

        return True, "OK"

    def can_export_commercial_glb(self, user_id: str) -> Tuple[bool, str]:
        """Validates commercial 3D asset export entitlement."""
        plan, _ = self.get_user_plan_and_sub(user_id)
        if plan.commercial_export:
            return True, "OK"
        return (
            False,
            "Commercial 3D GLB export requires an active Brand / Studio tier subscription."
        )

    def is_priority_queue(self, user_id: str) -> bool:
        """Determines if user's job should be routed to high-priority worker pool."""
        plan, sub = self.get_user_plan_and_sub(user_id)
        if not plan.priority_queue:
            return False
        # If fair-use cap reached on Pro, shift to standard priority
        if plan.fair_use_reconstructions > 0:
            period_start = sub.get("current_period_start", datetime.utcnow().isoformat())
            used = self._repo.get_monthly_usage_count(user_id, "garment_reconstruction", period_start)
            if used >= plan.fair_use_reconstructions:
                return False
        return True


entitlement_service = EntitlementService()

