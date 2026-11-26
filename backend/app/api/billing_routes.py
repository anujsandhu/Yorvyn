"""
Yorvyn Production Billing API Routes.
Exposes endpoints for Stripe checkout, billing portal, webhook ingestion,
subscription inspection, and monthly usage accounting.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from pydantic import BaseModel

from backend.app.core.settings import settings
from backend.app.core.security import get_current_user_optional, UserContext
from backend.app.core.billing_config import SUBSCRIPTION_PLANS
from backend.app.services.billing.stripe_service import stripe_billing_service
from backend.app.services.billing.entitlement_service import entitlement_service
from backend.app.services.database.supabase_repository import supabase_repo

router = APIRouter(prefix="/api/billing", tags=["Billing & Subscriptions"])


def _resolve_billing_user_id(client_user_id: Optional[str], current_user: Optional[UserContext]) -> str:
    """Enforces strict authentication and ownership for billing operations (no client_user_id fallback)."""
    if isinstance(current_user, UserContext):
        if client_user_id and client_user_id not in ("default_user", "guest") and client_user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot access or modify billing for another user."
            )
        return current_user.user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for billing management."
    )


class CheckoutSessionRequest(BaseModel):
    plan_id: str
    user_id: Optional[str] = None
    success_url: Optional[str] = "https://yorvyn.ai/settings?billing=success"
    cancel_url: Optional[str] = "https://yorvyn.ai/settings?billing=cancelled"


class PortalSessionRequest(BaseModel):
    user_id: Optional[str] = None
    return_url: Optional[str] = "https://yorvyn.ai/settings"


@router.get("/plans")
def list_subscription_plans():
    """Returns catalog of public subscription tiers and feature entitlements."""
    return {
        "status": "success",
        "plans": [p.model_dump() for p in SUBSCRIPTION_PLANS.values()]
    }


@router.get("/subscription")
def get_user_subscription(
    user_id: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retrieves current user's active subscription tier, renewal date, and quotas."""
    effective_uid = _resolve_billing_user_id(user_id, current_user)
    entitlements = entitlement_service.get_user_entitlements(effective_uid)
    return {
        "status": "success",
        "entitlements": entitlements
    }


@router.get("/usage")
def get_user_usage_records(
    user_id: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retrieves itemized billable usage events and reconstruction counts."""
    effective_uid = _resolve_billing_user_id(user_id, current_user)
    records = supabase_repo.get_usage_records(effective_uid)
    entitlements = entitlement_service.get_user_entitlements(effective_uid)
    return {
        "status": "success",
        "user_id": effective_uid,
        "reconstructions_used": entitlements["reconstructions"]["used"],
        "reconstructions_quota": entitlements["reconstructions"]["quota"],
        "usage_records": records
    }


@router.post("/create-checkout-session")
def create_checkout_session(
    req: CheckoutSessionRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Initiates a Stripe Checkout session for subscription upgrade."""
    effective_uid = _resolve_billing_user_id(req.user_id, current_user)
    email = current_user.email if isinstance(current_user, UserContext) else f"{effective_uid}@user.yorvyn.ai"

    try:
        session_info = stripe_billing_service.create_checkout_session(
            user_id=effective_uid,
            user_email=email,
            plan_id=req.plan_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )
        return {
            "status": "success",
            "session": session_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-portal-session")
def create_portal_session(
    req: PortalSessionRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Generates a Stripe Billing Customer Portal session link."""
    effective_uid = _resolve_billing_user_id(req.user_id, current_user)
    try:
        portal_info = stripe_billing_service.create_customer_portal_session(
            user_id=effective_uid,
            return_url=req.return_url
        )
        return {
            "status": "success",
            "portal": portal_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook_handler(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """
    Receives and processes asynchronous webhook events from Stripe.
    Validates cryptographic payload signature and guarantees idempotency.
    """
    raw_body = await request.body()
    try:
        result = stripe_billing_service.verify_and_process_webhook(
            raw_body=raw_body,
            sig_header=stripe_signature or ""
        )
        return {"status": "success", "result": result}
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
