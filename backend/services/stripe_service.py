from __future__ import annotations
from typing import Optional

from ..config import settings

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None  # type: ignore


def _init_stripe() -> None:
    if stripe is None:
        raise RuntimeError("Stripe SDK not installed. Add 'stripe' to requirements and pip install.")
    if not settings.STRIPE_API_KEY:
        raise RuntimeError("STRIPE_API_KEY not configured.")
    stripe.api_key = settings.STRIPE_API_KEY


def create_stripe_customer(name: str, email: Optional[str]) -> str:
    _init_stripe()
    customer = stripe.Customer.create(name=name, email=email)
    return customer["id"]


def create_and_finalize_invoice(customer_id: str, description: str, amount_usd: float) -> str:
    _init_stripe()
    # Create product+price on the fly or use a generic meter; here we use one-off invoice item
    amount_cents = int(round(amount_usd * 100))
    _ = stripe.InvoiceItem.create(
        customer=customer_id,
        amount=amount_cents,
        currency="usd",
        description=description,
    )
    invoice = stripe.Invoice.create(customer=customer_id, auto_advance=False)
    finalized = stripe.Invoice.finalize_invoice(invoice["id"])  # type: ignore
    return finalized["id"]
