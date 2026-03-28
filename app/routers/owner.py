from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner

router = APIRouter(prefix="/owners", tags=["Owners"])

# Nuevo schema
class OwnerCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    identification: Optional[str] = None

@router.post("/")
def create_owner(owner_data: OwnerCreate, db: Session = Depends(get_db)):
    owner = Owner(
        full_name=owner_data.full_name,
        email=owner_data.email,
        phone=owner_data.phone,
        identification=owner_data.identification
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner

@router.get("/")
def get_owners(db: Session = Depends(get_db)):
    return db.query(Owner).all()


@router.put("/{owner_id}")
def update_owner(owner_id: int, owner_data: OwnerCreate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    owner.full_name = owner_data.full_name
    owner.email = owner_data.email
    owner.phone = owner_data.phone
    owner.identification = owner_data.identification

    db.commit()
    db.refresh(owner)
    return owner


@router.delete("/{owner_id}")
def delete_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    # Desactivar cualquier relación activa
    ownerships = db.query(UnitOwner).filter(
        UnitOwner.owner_id == owner_id,
        UnitOwner.is_active == True
    ).all()

    for o in ownerships:
        o.is_active = False

    db.delete(owner)
    db.commit()

    return {"message": "Propietario eliminado correctamente"}