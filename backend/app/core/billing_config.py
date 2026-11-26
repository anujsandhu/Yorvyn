"""
Yorvyn Subscription & Entitlement Configuration Module.
Defines pricing tiers, feature flags, quotas, and fair-use limits.
All values are configurable via environment variables or runtime overrides.
"""

import os
from typing import Dict, Any
from pydantic import BaseModel


class PlanEntitlements(BaseModel):
    id: str
    name: str
    price_usd: float
    stripe_price_id: str
    monthly_reconstructions: int  # -1 for unlimited
    fair_use_reconstructions: int  # Soft alert cap
    max_saved_looks: int  # -1 for unlimited
    high_res_textures: bool
    priority_queue: bool
    commercial_export: bool
    multi_avatar: bool
    custom_materials: bool


SUBSCRIPTION_PLANS: Dict[str, PlanEntitlements] = {
    "explorer": PlanEntitlements(
        id="explorer",
        name="Explorer (Free)",
        price_usd=0.00,
        stripe_price_id="",
        monthly_reconstructions=int(os.getenv("PLAN_EXPLORER_RECONSTRUCTIONS", "5")),
        fair_use_reconstructions=5,
        max_saved_looks=int(os.getenv("PLAN_EXPLORER_SAVED_LOOKS", "10")),
        high_res_textures=False,
        priority_queue=False,
        commercial_export=False,
        multi_avatar=False,
        custom_materials=False,
    ),
    "pro": PlanEntitlements(
        id="pro",
        name="Pro Atelier",
        price_usd=float(os.getenv("PLAN_PRO_PRICE", "19.99")),
        stripe_price_id=os.getenv("STRIPE_PRO_PRICE_ID", "price_yorvyn_pro_monthly"),
        monthly_reconstructions=-1,  # Unlimited
        fair_use_reconstructions=int(os.getenv("PLAN_PRO_FAIR_USE", "100")),
        max_saved_looks=-1,  # Unlimited
        high_res_textures=True,
        priority_queue=True,
        commercial_export=False,
        multi_avatar=False,
        custom_materials=False,
    ),
    "studio": PlanEntitlements(
        id="studio",
        name="Brand / Studio",
        price_usd=float(os.getenv("PLAN_STUDIO_PRICE", "99.00")),
        stripe_price_id=os.getenv("STRIPE_STUDIO_PRICE_ID", "price_yorvyn_studio_monthly"),
        monthly_reconstructions=-1,  # Unlimited
        fair_use_reconstructions=int(os.getenv("PLAN_STUDIO_FAIR_USE", "500")),
        max_saved_looks=-1,  # Unlimited
        high_res_textures=True,
        priority_queue=True,
        commercial_export=True,
        multi_avatar=True,
        custom_materials=True,
    ),
}


def get_plan_definition(plan_id: str) -> PlanEntitlements:
    """Returns the definition for the specified plan ID, defaulting to Explorer."""
    return SUBSCRIPTION_PLANS.get(plan_id.lower(), SUBSCRIPTION_PLANS["explorer"])

