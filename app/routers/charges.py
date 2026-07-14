"""
app/routers/charges.py  v2
Agrega:
  PUT  /charges/{charge_id}   — editar cargo (solo ADMIN)
  DELETE /charges/{charge_id} — eliminar cargo (solo ADMIN)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.unit import Unit
from app.models.payment_application import PaymentApplication
from app.schemas.charge import ChargeCreate, ChargeResponse
from app.database import get_db
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter(prefix="/charges", tags=["Charges"])


def _require_admin(current_user: User):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción")


@router.post("/", response_model=ChargeResponse)
def create_charge(
    charge_data: ChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unit = db.query(Unit).filter(Unit.id == charge_data.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    if charge_data.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    if charge_data.due_date < charge_data.date_created:
        raise HTTPException(
            status_code=400,
            detail="La fecha de vencimiento no puede ser menor a la fecha de registro",
        )

    new_charge = Charge(
        unit_id=charge_data.unit_id,
        description=charge_data.description,
        amount=charge_data.amount,
        status="PENDIENTE",
        date_created=charge_data.date_created,
        due_date=charge_data.due_date,
    )
    db.add(new_charge)
    db.commit()
    db.refresh(new_charge)
    return new_charge


@router.put("/{charge_id}")
def update_charge(
    charge_id: int,
    charge_data: ChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Editar un cargo existente — solo ADMIN."""
    _require_admin(current_user)

    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")

    if charge_data.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    if charge_data.due_date < charge_data.date_created:
        raise HTTPException(
            status_code=400,
            detail="La fecha de vencimiento no puede ser menor a la fecha de registro",
        )

    from decimal import Decimal
    from sqlalchemy import func
    from app.models.payment_application import PaymentApplication

    new_amount = Decimal(str(charge_data.amount))

    if charge.balance == Decimal("0.00"):
        # Cargo ya pagado en su totalidad: no se permite tocar lo financiero.
        if new_amount != charge.amount or charge_data.due_date != charge.due_date:
            raise HTTPException(
                status_code=400,
                detail="No se puede editar un cargo ya pagado en su totalidad.",
            )

        charge.description  = charge_data.description
        charge.date_created = charge_data.date_created

        db.commit()
        db.refresh(charge)
        return charge

    # Calcular ya aplicado
    applied = db.query(
        func.coalesce(func.sum(PaymentApplication.applied_amount), 0)
    ).filter(PaymentApplication.charge_id == charge_id).scalar()

    new_balance = new_amount - Decimal(str(applied))

    charge.description  = charge_data.description
    charge.amount       = new_amount
    charge.date_created = charge_data.date_created
    charge.due_date     = charge_data.due_date

    # Recalcular estado
    if new_balance <= 0:
        charge.status = "PAGADO"
    elif applied > 0:
        charge.status = "PARCIAL"
    else:
        charge.status = "PENDIENTE"

    db.commit()
    db.refresh(charge)
    return charge


@router.delete("/{charge_id}")
def delete_charge(
    charge_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar un cargo y sus aplicaciones de pago — solo ADMIN."""
    _require_admin(current_user)

    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    if not charge:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")

    # Eliminar aplicaciones asociadas primero
    db.query(PaymentApplication).filter(
        PaymentApplication.charge_id == charge_id
    ).delete()
    db.delete(charge)
    db.commit()
    return {"message": "Cargo eliminado correctamente"}
