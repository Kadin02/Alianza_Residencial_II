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

    db.delete(property_obj)
    db.commit()

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

        # Verificar ocupación activa
        active = db.query(UnitOwner).filter(
            UnitOwner.unit_id == unit.id,
            UnitOwner.is_active == True
        ).first()

        if active:
            raise HTTPException(status_code=400, detail="La unidad ya está ocupada")

        # Crear propietario
        owner = Owner(
            full_name=data.full_name,
            identification=data.identification,
            email=data.email,
            phone=data.phone
        )
        db.add(owner)
        db.flush()

        # Crear relación
        occupancy = UnitOwner(
            unit_id=unit.id,
            owner_id=owner.id,
            start_date=data.start_date,
            is_active=True
        )
        db.add(occupancy)

        db.commit()

        return {"message": "Ocupante registrado correctamente"}

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno")
