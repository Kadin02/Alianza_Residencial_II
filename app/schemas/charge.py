from pydantic import BaseModel
from datetime import date
from decimal import Decimal

class ChargeCreate(BaseModel):
    unit_id: int
    description: str
    amount: Decimal
    date_created: date
    due_date: date


class ChargeResponse(BaseModel):
    id: int
    unit_id: int
    description: str
    amount: Decimal
    balance: Decimal
    status: str
    date_created: date
    due_date: date

    class Config:
        from_attributes = True