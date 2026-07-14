from pydantic import BaseModel
from typing import Optional


class PropertyCreate(BaseModel):
    name: str
    type: str
    address: str
    max_units: int = 50
    phone:   Optional[str] = None
    email:   Optional[str] = None
    website: Optional[str] = None
