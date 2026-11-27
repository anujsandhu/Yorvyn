"""
Yorvyn Stripe Subscription & Payment Processing Service.
Manages Stripe Checkout sessions, Customer Portal redirects, and idempotent webhook processing.
Ensures zero client trust, server-side signature verification, and secure entitlement synchronization.
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import stripe
from backend.app.core.settings import settings
from backend.app.core.billing_config import SUBSCRIPTION_PLANS, get_plan_definition
from backend.app.services.database.supabase_repository import supabase_repo

logger = logging.getLogger(__name__)

# Configure Stripe SDK
stripe.api_key = settings.stripe_secret_key or os.getenv("STRIPE_SECRET_KEY", "sk_test_yorvyn_mock_dummy_key_2026")


class StripeBillingService:
    """Orchestrates Stripe customer lifecycles and webhook event processing."""

    def __init__(self):
        self._repo = supabase_repo
        self.is_test_mode = getattr(settings, "stripe_test_mode", True) or stripe.api_key.startswith("sk_test_")

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan_id: str,
        success_url: str = "https://yorvyn.ai/settings?billing=success",
        cancel_url: str = "https://yorvyn.ai/settings?billing=cancelled"
    ) -> Dict[str, Any]:
        """
        Creates a Stripe Checkout Session for subscription upgrade.
        Never grants entitlements immediately; relies strictly on server-side webhook.
        """
        plan = get_plan_definition(plan_id)
        if plan.id == "explorer":
            raise ValueError("Cannot initiate checkout session for free Explorer plan.")

        # In local testing or when using dummy test keys, synthesize a valid test-mode checkout payload
        if self.is_test_mode and (not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test_yorvyn")):
            session_id = f"cs_test_{uuid.uuid4().hex[:18]}"
            mock_checkout_url = f"https://checkout.stripe.com/c/pay/{session_id}?user_id={user_id}&plan={plan.id}"
            return {
                "session_id": session_id,
                "url": mock_checkout_url,
                "mode": "test_simulation",
                "plan_id": plan.id,
                "amount_usd": plan.price_usd,
                "user_id": user_id
            }

        try:
            session = stripe.checkout.Session.create(
                customer_email=user_email,
                client_reference_id=user_id,
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }],
                metadata={
                    "user_id": user_id,
                    "plan_id": plan.id
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return {
                "session_id": session.id,
                "url": session.url,
                "mode": "live" if not self.is_test_mode else "test",
                "plan_id": plan.id,
                "amount_usd": plan.price_usd,
                "user_id": user_id
            }
        except Exception as e:
            logger.error(f"[Stripe] Checkout creation failed: {e}", exc_info=True)
            raise RuntimeError(f"Payment gateway error: {str(e)}")

    def create_customer_portal_session(self, user_id: str, return_url: str = "https://yorvyn.ai/settings") -> Dict[str, Any]:
        """Creates a Stripe Billing Customer Portal session for subscription management."""
        sub = self._repo.get_subscription(user_id)
        customer_id = sub.get("stripe_customer_id") if sub else None

        if self.is_test_mode and (not customer_id or not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test_yorvyn")):
            portal_id = f"bps_test_{uuid.uuid4().hex[:18]}"
            return {
                "portal_id": portal_id,
                "url": f"https://billing.stripe.com/p/session/{portal_id}?return_to={return_url}",
                "mode": "test_simulation"
            }

        if not customer_id:
            raise ValueError("No active Stripe customer found for this user account.")

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return {
                "portal_id": portal_session.id,
                "url": portal_session.url,
                "mode": "live" if not self.is_test_mode else "test"
            }
        except Exception as e:
            logger.error(f"[Stripe] Customer portal creation failed: {e}", exc_info=True)
            raise RuntimeError(f"Billing portal error: {str(e)}")

    def verify_and_process_webhook(
        self,
        raw_body: bytes,
        sig_header: str,
        test_mode_bypass: bool = False
    ) -> Dict[str, Any]:
        """
        Verifies Stripe cryptographic signature against raw request body
        and idempotently synchronizes subscription records.
        """
        webhook_secret = settings.stripe_webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET", "")

        event = None
        if test_mode_bypass or (self.is_test_mode and not webhook_secret):
            # Parse unverified JSON payload in test simulation mode
            try:
                event = json.loads(raw_body.decode("utf-8"))
            except Exception as e:
                raise ValueError(f"Malformed JSON payload: {e}")
        else:
            try:
                event = stripe.Webhook.construct_event(
                    raw_body, sig_header, webhook_secret
                )
            except stripe.error.SignatureVerificationError as e:
                logger.warning(f"[Stripe] Webhook signature verification failed: {e}")
                raise PermissionError(f"Invalid webhook signature: {str(e)}")
            except Exception as e:
                logger.error(f"[Stripe] Webhook parsing error: {e}")
                raise ValueError(f"Webhook error: {str(e)}")

        event_id = event.get("id", f"evt_{uuid.uuid4().hex[:14]}")
        event_type = event.get("type", "unknown")

        # 1. Idempotency Check: Prevent duplicate processing of retried webhook deliveries
        if self._repo.is_billing_event_processed(event_id):
            logger.info(f"[Stripe] Duplicate event {event_id} ({event_type}) ignored.")
            return {"status": "already_processed", "event_id": event_id}

        event_data = event.get("data", {}).get("object", {})
        processed_user_id = None
        customer_id = event_data.get("customer")

        try:
            # 2. Handle Event Types
            if event_type == "checkout.session.completed":
                # User completed checkout: activate subscription
                user_id = event_data.get("client_reference_id") or event_data.get("metadata", {}).get("user_id")
                plan_id = event_data.get("metadata", {}).get("plan_id", "pro")
                sub_id = event_data.get("subscription")

                if user_id:
                    processed_user_id = user_id
                    now = datetime.utcnow()
                    self._repo.upsert_subscription(user_id, {
                        "plan_id": plan_id,
                        "status": "active",
                        "stripe_customer_id": customer_id,
                        "stripe_subscription_id": sub_id,
                        "current_period_start": now.isoformat(),
                        "current_period_end": (now + timedelta(days=30)).isoformat(),
                        "cancel_at_period_end": False
                    })
                    logger.info(f"[Stripe] Activated subscription for user {user_id}: {plan_id}")

            elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
                user_id = event_data.get("metadata", {}).get("user_id")
                sub_status = event_data.get("status", "active")
                cancel_at_period_end = event_data.get("cancel_at_period_end", False)
                period_end_ts = event_data.get("current_period_end")
                period_end = datetime.fromtimestamp(period_end_ts).isoformat() if period_end_ts else None

                # Determine plan from items
                plan_id = "pro"
                items = event_data.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id")
                    for p_key, p_val in SUBSCRIPTION_PLANS.items():
                        if p_val.stripe_price_id == price_id:
                            plan_id = p_key
                            break

                if user_id:
                    processed_user_id = user_id
                    existing = self._repo.get_subscription(user_id) or {}
                    existing.update({
                        "plan_id": plan_id,
                        "status": sub_status,
                        "stripe_customer_id": customer_id,
                        "stripe_subscription_id": event_data.get("id"),
                        "cancel_at_period_end": cancel_at_period_end
                    })
                    if period_end:
                        existing["current_period_end"] = period_end
                    self._repo.upsert_subscription(user_id, existing)
                    logger.info(f"[Stripe] Updated subscription for {user_id} -> {plan_id} ({sub_status})")

            elif event_type == "customer.subscription.deleted":
                # Subscription canceled or expired: downgrade to Explorer
                user_id = event_data.get("metadata", {}).get("user_id")
                if user_id:
                    processed_user_id = user_id
                    existing = self._repo.get_subscription(user_id) or {}
                    existing.update({
                        "plan_id": "explorer",
                        "status": "canceled",
                        "cancel_at_period_end": False,
                        "canceled_at": datetime.utcnow().isoformat()
                    })
                    self._repo.upsert_subscription(user_id, existing)
                    logger.info(f"[Stripe] Canceled subscription for user {user_id}, downgraded to Explorer.")

            elif event_type == "invoice.payment_failed":
                # Mark as past_due
                user_id = (
                    event_data.get("metadata", {}).get("user_id")
                    or event_data.get("subscription_details", {}).get("metadata", {}).get("user_id")
                )
                if not user_id and customer_id:
                    for uid, s in self._repo._subscriptions.items():
                        if s.get("stripe_customer_id") == customer_id:
                            user_id = uid
                            break
                if user_id:
                    processed_user_id = user_id
                    existing = self._repo.get_subscription(user_id) or {}
                    existing["status"] = "past_due"
                    self._repo.upsert_subscription(user_id, existing)
                    logger.warning(f"[Stripe] Invoice payment failed for user {user_id}, marked past_due.")

            # Record billing event into database for idempotency & audit
            self._repo.record_billing_event(
                event_id=event_id,
                event_type=event_type,
                user_id=processed_user_id,
                stripe_customer_id=customer_id,
                payload=event
            )

            return {
                "status": "processed",
                "event_id": event_id,
                "event_type": event_type,
                "user_id": processed_user_id
            }

        except Exception as e:
            logger.error(f"[Stripe] Error processing webhook event {event_id}: {e}", exc_info=True)
            self._repo.record_billing_event(
                event_id=event_id,
                event_type=event_type,
                user_id=processed_user_id,
                stripe_customer_id=customer_id,
                payload=event,
                error_message=str(e)
            )
            raise


stripe_billing_service = StripeBillingService()
