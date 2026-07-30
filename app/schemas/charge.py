from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional

class ChargeCreate(BaseModel):
    unit_id: int
    description: str
    amount: Decimal
    date_created: date
    due_date: date
    concept: Optional[str] = None


class ChargeResponse(BaseModel):
    id: int
    unit_id: int
    description: str
    amount: Decimal
    balance: Decimal
    status: str
    date_created: date
    due_date: date
    concept: Optional[str] = None

    class Config:
        from_attributes = True