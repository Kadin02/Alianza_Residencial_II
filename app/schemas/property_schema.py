from pydantic import BaseModel


class PropertyCreate(BaseModel):
    name: str
    type: str
    address: str
    max_units: int = 50
