from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.unit import Unit
from app.models.property import Property
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner
from app.models.charge import Charge
from app.services.ownership_service import assign_owner_to_unit, get_or_create_owner

router = APIRouter(prefix="/units", tags=["Units"])

# Nuevo schema
class NewOwnerData(BaseModel):
    full_name: str
    identification: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UnitCreate(BaseModel):
    property_id: int
    unit_number: str
    floor: Optional[str] = None
    monthly_fee: Optional[Decimal] = None
    start_date: date
    # Debe venir uno de los dos: un propietario existente, o los datos de uno nuevo.
    owner_id: Optional[int] = None
    owner: Optional[NewOwnerData] = None


class UnitUpdate(BaseModel):
    unit_number: Optional[str] = None
    floor: Optional[str] = None
    monthly_fee: Optional[Decimal] = None


class UnitResponse(BaseModel):
    id: int
    property_id: int
    unit_number: str
    floor: Optional[str] = None
    monthly_fee: Optional[Decimal] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.post("/", response_model=UnitResponse)
def create_unit(unit_data: UnitCreate, db: Session = Depends(get_db)):
    property_obj = db.query(Property).filter(Property.id == unit_data.property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    if not unit_data.owner_id and not unit_data.owner:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar un owner_id existente o los datos de un propietario nuevo",
        )

    total_units = db.query(Unit).filter(Unit.property_id == unit_data.property_id).count()

    if total_units >= property_obj.max_units:
        raise HTTPException(status_code=400, detail="Se alcanzó el máximo de unidades")

    if unit_data.owner_id:
        owner = db.query(Owner).filter(Owner.id == unit_data.owner_id).first()
        if not owner:
            raise HTTPException(status_code=404, detail="Propietario no encontrado")
    else:
        owner = get_or_create_owner(
            db,
            full_name=unit_data.owner.full_name,
            identification=unit_data.owner.identification,
            email=unit_data.owner.email,
            phone=unit_data.owner.phone,
        )

    unit = Unit(
        property_id=unit_data.property_id,
        unit_number=unit_data.unit_number,
        floor=unit_data.floor,
        monthly_fee=unit_data.monthly_fee,
    )

    db.add(unit)
    db.flush()

    assign_owner_to_unit(db, unit.id, owner.id, unit_data.start_date)

    db.refresh(unit)
    return unit


@router.put("/{unit_id}", response_model=UnitResponse)
def update_unit(unit_id: int, data: UnitUpdate, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    if data.unit_number is not None:
        unit.unit_number = data.unit_number
    if data.floor is not None:
        unit.floor = data.floor
    if data.monthly_fee is not None:
        unit.monthly_fee = data.monthly_fee

    db.commit()
    db.refresh(unit)
    return unit


@router.get("/", response_model=list[UnitResponse])
def get_units(db: Session = Depends(get_db)):
    return db.query(Unit).all()


@router.delete("/{unit_id}")
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    try:
        charge_count = db.query(Charge).filter(Charge.unit_id == unit_id).count()
        if charge_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar la unidad: tiene {charge_count} cargo(s) registrado(s).",
            )

        # Sin cargos: se permite eliminar la unidad y su historial de UnitOwner (ocupación, no dinero).
        db.query(UnitOwner).filter(UnitOwner.unit_id == unit_id).delete(synchronize_session=False)

        db.delete(unit)
        db.commit()

    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno")

    return {"message": "Unidad eliminada correctamente"}