from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.unit_owner import UnitOwner
from app.models.unit import Unit
from app.models.owner import Owner
from app.services.ownership_service import assign_owner_to_unit as assign_owner_to_unit_service

router = APIRouter(prefix="/unit-owners", tags=["UnitOwner"])

# Nuevo schema
class UnitOwnerCreate(BaseModel):
    unit_id: int
    owner_id: int
    start_date: date

@router.post("/")
def assign_owner_to_unit(
    data: UnitOwnerCreate,
    db: Session = Depends(get_db)
):
    return assign_owner_to_unit_service(db, data.unit_id, data.owner_id, data.start_date)

@router.get("/by-unit/{unit_id}")
def get_owners_by_unit(unit_id: int, db: Session = Depends(get_db)):
    ownerships = db.query(UnitOwner).filter(UnitOwner.unit_id == unit_id).all()
    result = []
    for ownership in ownerships:
        owner = db.query(Owner).filter(Owner.id == ownership.owner_id).first()
        result.append({
            "owner_name": owner.full_name if owner else "Desconocido",
            "role": "Propietario Actual" if ownership.is_active else "Propietario Anterior",
            "start_date": ownership.start_date,
            "end_date": ownership.end_date
        })
    return result

@router.get("/all")
def get_all_unit_owners(db: Session = Depends(get_db)):
    """Obtener todas las relaciones unit-owner (para owners.html)"""
    results = db.query(UnitOwner).all()
    return [
        {
            "id": uo.id,
            "unit_id": uo.unit_id,
            "owner_id": uo.owner_id,
            "is_active": uo.is_active,
            "start_date": uo.start_date,
            "end_date": uo.end_date
        }
        for uo in results
    ]