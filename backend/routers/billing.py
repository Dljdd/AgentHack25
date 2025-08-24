from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db_sa import get_db
from ..models import Customer, AgentRun, BillingEvent
from ..services.stripe_service import create_stripe_customer, create_and_finalize_invoice

router = APIRouter(prefix="/billing", tags=["billing"])


class StripeCustomerCreate(BaseModel):
    customer_id: int


class InvoiceCreate(BaseModel):
    customer_id: int
    margin_percent: float = Field(default=10.0, ge=0.0)
    days: int = Field(default=30, ge=1, le=60)


@router.post("/stripe/create_customer")
async def create_stripe_customer_route(body: StripeCustomerCreate, db: Session = Depends(get_db)):
    cust = db.get(Customer, body.customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if cust.stripe_customer_id:
        return {"stripe_customer_id": cust.stripe_customer_id}

    stripe_id = create_stripe_customer(name=cust.name, email=cust.email)
    cust.stripe_customer_id = stripe_id
    db.add(cust)
    db.commit()
    return {"stripe_customer_id": stripe_id}


@router.post("/invoice/create")
async def create_invoice(body: InvoiceCreate, db: Session = Depends(get_db)):
    cust = db.get(Customer, body.customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not cust.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Stripe customer not set for this customer")

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=body.days)

    totals = db.query(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)).filter(
        AgentRun.customer_id == body.customer_id,
        AgentRun.started_at >= period_start,
        AgentRun.started_at < period_end,
    ).scalar() or 0.0

    subtotal = float(totals)
    total = round(subtotal * (1.0 + body.margin_percent / 100.0), 4)

    invoice_id = create_and_finalize_invoice(
        customer_id=cust.stripe_customer_id,
        description=f"AI Agent usage {period_start.date()} - {period_end.date()} (incl. margin {body.margin_percent}%)",
        amount_usd=total,
    )

    be = BillingEvent(
        customer_id=body.customer_id,
        period_start=period_start,
        period_end=period_end,
        subtotal_usd=subtotal,
        margin_percent=body.margin_percent,
        total_usd=total,
        stripe_invoice_id=invoice_id,
    )
    db.add(be)
    db.commit()

    return {
        "stripe_invoice_id": invoice_id,
        "subtotal_usd": subtotal,
        "margin_percent": body.margin_percent,
        "total_usd": total,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
