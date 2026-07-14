from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.property import Property



router = APIRouter(prefix="/properties", tags=["Properties"])


from sqlalchemy.exc import SQLAlchemyError
from datetime import date
from pydantic import BaseModel

from app.models.unit import Unit
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner
from app.models.charge import Charge
from app.services.ownership_service import assign_owner_to_unit, get_or_create_owner

class RegisterOccupant(BaseModel):
    unit_number: str
    floor: str | None = None
    full_name: str
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    start_date: date



# Crear propiedad (máximo 10)
from app.schemas.property_schema import PropertyCreate

@router.post("/")
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db)
):
    total_properties = db.query(Property).count()

    if total_properties >= 10:
        raise HTTPException(status_code=400, detail="Máximo de 10 propiedades alcanzado")

    property_obj = Property(**property_data.dict())

    db.add(property_obj)
    db.commit()
    db.refresh(property_obj)

    return property_obj


# Obtener todas las propiedades
@router.get("/")
def get_properties(db: Session = Depends(get_db)):
    return db.query(Property).all()


#  eliminar propiedad 
@router.delete("/{property_id}")
def delete_property(property_id: int, db: Session = Depends(get_db)):
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    try:
        unit_ids = [u.id for u in db.query(Unit).filter(Unit.property_id == property_id).all()]

        charge_count = 0
        if unit_ids:
            charge_count = db.query(Charge).filter(Charge.unit_id.in_(unit_ids)).count()

        if charge_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar la propiedad: tiene {charge_count} cargo(s) registrado(s) en sus unidades.",
            )

        # Ninguna unidad tiene cargos: se puede eliminar la propiedad y sus unidades vacías.
        # El historial de UnitOwner (ocupación, no dinero) se borra en cascada, no bloquea.
        if unit_ids:
            db.query(UnitOwner).filter(UnitOwner.unit_id.in_(unit_ids)).delete(synchronize_session=False)
            db.query(Unit).filter(Unit.id.in_(unit_ids)).delete(synchronize_session=False)

        db.delete(property_obj)
        db.commit()

    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno")

    return {"message": "Propiedad eliminada"}


# Actualizar propiedad
@router.put("/{property_id}")
def update_property(
    property_id: int,
    property_data: PropertyCreate,
    db: Session = Depends(get_db)
):
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    property_obj.name = property_data.name
    property_obj.type = property_data.type
    property_obj.address = property_data.address
    property_obj.phone = property_data.phone
    property_obj.email = property_data.email
    property_obj.website = property_data.website

    db.commit()
    db.refresh(property_obj)

    return property_obj


# Registrar ocupante en unidad de propiedad
@router.post("/{property_id}/register-occupant")
def register_occupant(
    property_id: int,
    data: RegisterOccupant,
    db: Session = Depends(get_db)
):
    try:
        property_obj = db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail="Propiedad no encontrada")

        # Buscar o crear unidad
        unit = db.query(Unit).filter(
            Unit.property_id == property_id,
            Unit.unit_number == data.unit_number
        ).first()

        if not unit:
            unit = Unit(
                property_id=property_id,
                unit_number=data.unit_number,
                floor=data.floor
            )
            db.add(unit)
            db.flush()

        # Esta unidad ya está ocupada: register-occupant es solo para altas nuevas,
        # no para reasignar (eso lo hace el endpoint dedicado de unit-owners).
        active = db.query(UnitOwner).filter(
            UnitOwner.unit_id == unit.id,
            UnitOwner.is_active == True
        ).first()
        if active:
            raise HTTPException(status_code=400, detail="La unidad ya está ocupada")

        # Buscar o crear propietario (evita duplicados por identification/email)
        owner = get_or_create_owner(
            db,
            full_name=data.full_name,
            identification=data.identification,
            email=data.email,
            phone=data.phone,
        )

        # Asignar propietario a la unidad (cierra automáticamente el anterior si lo hay)
        assign_owner_to_unit(db, unit.id, owner.id, data.start_date)

        return {"message": "Ocupante registrado correctamente"}

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno")
