"""Billing: Stripe subscriptions and license enforcement.

Turns the app into something that can take money on its own: a Checkout
session is created for one of the plans, Stripe calls back via webhook on
successful payment, and a license key is issued and persisted. Autopilot
channel creation is gated by the per-plan channel limits when billing is
enabled (`[stripe] enabled = true` in config.toml).

Stripe is called through its plain REST API with `requests`, so no new
dependency is needed. With billing disabled (the default) nothing changes
for self-hosters.
"""

import hashlib
import hmac
import json
import os
import threading
import time
from typing import Optional

import requests
from loguru import logger

from app.config import config
from app.utils import utils

_STRIPE_API = "https://api.stripe.com/v1"
# Reject webhook events older than this to limit replay attacks.
_SIGNATURE_TOLERANCE_SECONDS = 300

stripe_cfg = config._cfg.get("stripe", {})

PLAN_LIMITS = {
    "starter": {"channels": 1, "videos_per_month": 30},
    "creator": {"channels": 5, "videos_per_month": 150},
    "agency": {"channels": 25, "videos_per_month": 0},  # 0 = unlimited
}


def billing_enabled() -> bool:
    return bool(stripe_cfg.get("enabled", False))


def create_checkout_session(plan: str, customer_email: str = "") -> str:
    """Create a Stripe Checkout session for a plan; returns the payment URL."""
    if plan not in PLAN_LIMITS:
        raise ValueError(f"unknown plan: {plan}")
    price_id = stripe_cfg.get(f"price_{plan}", "")
    if not price_id:
        raise ValueError(f"no Stripe price configured for plan: {plan}")

    payload = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": stripe_cfg.get("success_url", ""),
        "cancel_url": stripe_cfg.get("cancel_url", ""),
        "metadata[plan]": plan,
    }
    if customer_email:
        payload["customer_email"] = customer_email

    response = requests.post(
        f"{_STRIPE_API}/checkout/sessions",
        data=payload,
        auth=(stripe_cfg.get("secret_key", ""), ""),
        timeout=30,
    )
    body = response.json()
    if response.status_code != 200:
        message = body.get("error", {}).get("message", "stripe error")
        raise ValueError(message)
    return body["url"]


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify Stripe's `Stripe-Signature: t=...,v1=...` header."""
    secret = stripe_cfg.get("webhook_secret", "")
    if not secret or not signature_header:
        return False
    parts = dict(
        item.split("=", 1) for item in signature_header.split(",") if "=" in item
    )
    timestamp = parts.get("t", "")
    candidate = parts.get("v1", "")
    if not timestamp or not candidate:
        return False
    try:
        if abs(time.time() - int(timestamp)) > _SIGNATURE_TOLERANCE_SECONDS:
            return False
    except ValueError:
        return False
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, candidate)


class LicenseStore:
    """Persists issued licenses as JSON under storage/billing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._file = os.path.join(
            utils.storage_dir("billing", create=True), "licenses.json"
        )
        self._licenses = {}
        if os.path.isfile(self._file):
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    self._licenses = json.load(f)
            except Exception as e:
                logger.error(f"billing failed to load licenses: {str(e)}")

    def _save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._licenses, f, ensure_ascii=False, indent=2)

    def issue(self, plan: str, email: str, subscription_id: str = "") -> str:
        key = utils.get_uuid(remove_hyphen=True)
        with self._lock:
            self._licenses[key] = {
                "plan": plan,
                "email": email,
                "subscription_id": subscription_id,
                "status": "active",
                "created_at": time.time(),
            }
            self._save()
        logger.success(f"license issued for plan {plan}: {key[:8]}…")
        return key

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            return self._licenses.get(key)

    def deactivate_by_subscription(self, subscription_id: str) -> bool:
        if not subscription_id:
            return False
        with self._lock:
            for record in self._licenses.values():
                if record.get("subscription_id") == subscription_id:
                    record["status"] = "inactive"
                    self._save()
                    return True
        return False


licenses = LicenseStore()


def handle_webhook_event(event: dict) -> Optional[str]:
    """Process a verified Stripe event; returns an issued license key if any."""
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        plan = obj.get("metadata", {}).get("plan", "")
        if plan not in PLAN_LIMITS:
            logger.warning(f"billing webhook with unknown plan: {plan}")
            return None
        email = obj.get("customer_details", {}).get("email", "") or obj.get(
            "customer_email", ""
        )
        return licenses.issue(plan, email, obj.get("subscription", ""))
    if event_type == "customer.subscription.deleted":
        licenses.deactivate_by_subscription(obj.get("id", ""))
    return None


def channel_quota(license_key: str) -> int:
    """Max autopilot channels allowed; 0 means unlimited (billing disabled)."""
    if not billing_enabled():
        return 0
    record = licenses.get(license_key or "")
    if not record or record.get("status") != "active":
        raise PermissionError("active license required")
    return PLAN_LIMITS[record["plan"]]["channels"]
