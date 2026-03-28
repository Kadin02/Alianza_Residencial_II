from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.unit import Unit
from app.models.property import Property

router = APIRouter(prefix="/units", tags=["Units"])

# Nuevo schema
class UnitCreate(BaseModel):
    property_id: int
    unit_number: str
    floor: Optional[str] = None

@router.post("/")
def create_unit(unit_data: UnitCreate, db: Session = Depends(get_db)):
    property_obj = db.query(Property).filter(Property.id == unit_data.property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    total_units = db.query(Unit).filter(Unit.property_id == unit_data.property_id).count()

    if total_units >= property_obj.max_units:
        raise HTTPException(status_code=400, detail="Se alcanzó el máximo de unidades")

    unit = Unit(
        property_id=unit_data.property_id,
        unit_number=unit_data.unit_number,
        floor=unit_data.floor
    )

    db.add(unit)
    db.commit()
    db.refresh(unit)

    return unit

@router.get("/")
def get_units(db: Session = Depends(get_db)):
    return db.query(Unit).all()