"""Thin wrapper around the Paystack API. The secret key never leaves the
backend - the frontend only ever sees the `authorization_url` we hand back,
same pattern as app/services/grok_service.py for its provider.

Paystack amounts are always in the currency's smallest subunit (pesewas for
GHS - 1 GHS = 100 pesewas), never the major unit - every function here takes
or returns pesewas, and callers (billing_service.py) are responsible for
converting a human GHS price before calling in.
"""

import hashlib
import hmac
import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.paystack.co"


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.paystack_secret_key}", "Content-Type": "application/json"}


async def initialize_transaction(
    *, email: str, plan_code: str, callback_url: str, metadata: dict
) -> dict:
    """Starts a Paystack checkout for a recurring plan. Passing `plan`
    (rather than a raw `amount`) is what makes this recurring - Paystack
    auto-creates the subscription once the first charge succeeds, using the
    plan's own amount/interval, so the amount here need never drift out of
    sync with what PLAN_CATALOG says the plan costs.

    Card only, by Paystack's own design, not a choice made here: passing
    `plan` restricts checkout to card regardless of a `channels` list or the
    account's enabled payment methods, confirmed against the live API -
    auto-renewal needs a reusable saved payment authorization, and only a
    card authorization is reusable for that on Paystack. Mobile Money/Bank
    Transfer become possible again only by dropping recurring billing
    entirely (one-time charges + a manual/reminder-based renewal flow),
    which is a deliberate product trade-off, not something to route around
    here.

    Returns Paystack's `data` object: {authorization_url, access_code, reference}.
    """
    if not settings.paystack_secret_key:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as client:
        try:
            response = await client.post(
                "/transaction/initialize",
                headers=_headers(),
                json={
                    "email": email,
                    "plan": plan_code,
                    "callback_url": callback_url,
                    "metadata": metadata,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _logger.exception("Paystack initialize failed: %s", exc.response.text[:500])
            raise HTTPException(status_code=502, detail="Could not start checkout with Paystack") from exc
        except httpx.RequestError as exc:
            _logger.exception("Failed to reach Paystack")
            raise HTTPException(status_code=502, detail="Could not reach Paystack") from exc

    return response.json()["data"]


async def verify_transaction(reference: str) -> dict:
    """Confirms a transaction actually succeeded - never trust a client-
    supplied "it worked" without checking with Paystack directly. Returns
    Paystack's `data` object (status, customer, plan, authorization, etc.).
    """
    if not settings.paystack_secret_key:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as client:
        try:
            response = await client.get(f"/transaction/verify/{reference}", headers=_headers())
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _logger.exception("Paystack verify failed: %s", exc.response.text[:500])
            raise HTTPException(status_code=502, detail="Could not verify payment with Paystack") from exc
        except httpx.RequestError as exc:
            _logger.exception("Failed to reach Paystack")
            raise HTTPException(status_code=502, detail="Could not reach Paystack") from exc

    return response.json()["data"]


async def disable_subscription(*, subscription_code: str, email_token: str) -> None:
    """Cancels future billing - Paystack requires both the subscription
    code AND the customer's one-time email_token together (returned on the
    subscription.create webhook event), not the subscription code alone."""
    if not settings.paystack_secret_key:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as client:
        try:
            response = await client.post(
                "/subscription/disable",
                headers=_headers(),
                json={"code": subscription_code, "token": email_token},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _logger.exception("Paystack disable-subscription failed: %s", exc.response.text[:500])
            raise HTTPException(status_code=502, detail="Could not cancel the subscription with Paystack") from exc
        except httpx.RequestError as exc:
            _logger.exception("Failed to reach Paystack")
            raise HTTPException(status_code=502, detail="Could not reach Paystack") from exc


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """Paystack signs every webhook body with HMAC-SHA512 using the secret
    key - this is the ONLY thing that should ever be trusted to mean "this
    request really came from Paystack" (never the payload's own content,
    and never that the request merely arrived at the webhook URL)."""
    if not signature or not settings.paystack_secret_key:
        return False
    expected = hmac.new(settings.paystack_secret_key.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
