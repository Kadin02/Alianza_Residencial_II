from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.unit import Unit
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner


def get_or_create_owner(
    db: Session,
    full_name: str,
    identification: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Owner:
    """Busca un propietario existente por identification o email antes de crear uno nuevo."""
    owner = None
    if identification:
        owner = db.query(Owner).filter(Owner.identification == identification).first()
    if not owner and email:
        owner = db.query(Owner).filter(Owner.email == email).first()

    if owner:
        return owner

    owner = Owner(
        full_name=full_name,
        identification=identification,
        email=email,
        phone=phone,
    )
    db.add(owner)
    db.flush()
    return owner


def assign_owner_to_unit(db: Session, unit_id: int, owner_id: int, start_date: date) -> UnitOwner:
    """
    Única fuente de verdad para asignar/reasignar el propietario de una unidad.
    Cierra automáticamente el ownership activo anterior (si existe) y crea el nuevo.
    """
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    active_ownership = db.query(UnitOwner).filter(
        UnitOwner.unit_id == unit_id,
        UnitOwner.is_active == True,
    ).first()

    if active_ownership:
        active_ownership.is_active = False
        active_ownership.end_date = start_date

    new_ownership = UnitOwner(
        unit_id=unit_id,
        owner_id=owner_id,
        start_date=start_date,
        is_active=True,
    )
    db.add(new_ownership)
    db.commit()
    db.refresh(new_ownership)
    return new_ownership
