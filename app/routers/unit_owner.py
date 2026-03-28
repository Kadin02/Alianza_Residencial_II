from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.unit_owner import UnitOwner
from app.models.unit import Unit
from app.models.owner import Owner

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
    unit = db.query(Unit).filter(Unit.id == data.unit_id).first()
    owner = db.query(Owner).filter(Owner.id == data.owner_id).first()

    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    # Desactivar propietario anterior
    active_ownership = db.query(UnitOwner).filter(
        UnitOwner.unit_id == data.unit_id,
        UnitOwner.is_active == True
    ).first()

    if active_ownership:
        active_ownership.is_active = False
        active_ownership.end_date = data.start_date

    new_ownership = UnitOwner(
        unit_id=data.unit_id,
        owner_id=data.owner_id,
        start_date=data.start_date,
        is_active=True
    )

    db.add(new_ownership)
    db.commit()
    db.refresh(new_ownership)

    return new_ownership

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