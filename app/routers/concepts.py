from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.charge_concept import ChargeConcept
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter(prefix="/concepts", tags=["Concepts"])


def _require_admin(current_user: User):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción")


class ConceptCreate(BaseModel):
    name: str


class ConceptUpdate(BaseModel):
    name: str
    active: bool


@router.get("/")
def list_concepts(
    only_active: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ChargeConcept)
    if only_active:
        q = q.filter(ChargeConcept.active == True)
    return q.order_by(ChargeConcept.name).all()


@router.post("/")
def create_concept(
    data: ConceptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del concepto no puede estar vacío")

    existing = db.query(ChargeConcept).filter(ChargeConcept.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un concepto con ese nombre")

    concept = ChargeConcept(name=name, active=True)
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept


@router.put("/{concept_id}")
def update_concept(
    concept_id: int,
    data: ConceptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    concept = db.query(ChargeConcept).filter(ChargeConcept.id == concept_id).first()
    if not concept:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del concepto no puede estar vacío")

    duplicate = db.query(ChargeConcept).filter(
        ChargeConcept.name == name, ChargeConcept.id != concept_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Ya existe un concepto con ese nombre")

    concept.name = name
    concept.active = data.active
    db.commit()
    db.refresh(concept)
    return concept


@router.delete("/{concept_id}")
def delete_concept(
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    concept = db.query(ChargeConcept).filter(ChargeConcept.id == concept_id).first()
    if not concept:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")

    db.delete(concept)
    db.commit()
    return {"message": "Concepto eliminado correctamente"}
