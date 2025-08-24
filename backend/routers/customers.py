from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional, List

from ..db_sa import get_db
from ..models import Customer

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    external_id: Optional[str] = None


class CustomerOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    external_id: Optional[str]
    stripe_customer_id: Optional[str]

    class Config:
        from_attributes = True


@router.post("/", response_model=CustomerOut)
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    c = Customer(name=body.name, email=body.email, external_id=body.external_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/", response_model=List[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).order_by(Customer.created_at.desc()).all()
