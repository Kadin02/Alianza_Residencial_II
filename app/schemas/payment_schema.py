from pydantic import BaseModel
from datetime import date
from typing import List


class PaymentApplicationItem(BaseModel):
    charge_id: int
    amount: float


class PaymentCreate(BaseModel):
    owner_id: int
    payment_date: date
    amount: float
    invoice_number: str | None = None
    reference: str | None = None
    applications: List[PaymentApplicationItem]
