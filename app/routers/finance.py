from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.invoice import Invoice
from app.models.owner import Owner
from app.models.payment import Payment
from app.services.finance_service import (
    apply_payment_to_charge,
    create_general_charge_for_property,
    create_invoice_for_payment,
    create_payment_with_applications,
    generate_owner_statement,
    get_owner_account_statement,
    get_payment_detail,
    get_payment_detail_full,
    get_property_financial_summary,
    get_unit_account_statement,
    list_charges_with_status,
)
from app.models.payment_application import PaymentApplication
from app.models.unit import Unit
from app.models.unit_owner import UnitOwner
from app.services.auth_service import get_current_user as get_current_user_dep

router = APIRouter(prefix="/finance", tags=["Finance"])


class GeneralChargeCreate(BaseModel):
    description: str
    amount: float
    due_date: date


class PaymentCreate(BaseModel):
    owner_id: int
    payment_date: date
    amount: float
    invoice_number: Optional[str] = None
    reference: Optional[str] = None
    # receipt_number: número de recibo físico opcional — solo se muestra
    # en facturas y estados de cuenta cuando está presente
    receipt_number: Optional[str] = None


class PaymentApplicationItem(BaseModel):
    charge_id: int
    amount: float


class PaymentCompleteCreate(BaseModel):
    owner_id: int
    payment_date: date
    amount: float
    invoice_number: Optional[str] = None
    reference: Optional[str] = None
    # receipt_number: número de recibo físico — aparece en factura y estado de cuenta
    receipt_number: Optional[str] = None
    applications: List[PaymentApplicationItem]


@router.post("/general-charge/{property_id}")
def create_general_charge(property_id: int, charge_data: GeneralChargeCreate, db: Session = Depends(get_db)):
    charges = create_general_charge_for_property(
        db, property_id, charge_data.description, charge_data.amount, charge_data.due_date
    )
    return {"message": f"{len(charges)} cargos creados correctamente"}


@router.get("/owner-statement/{owner_id}")
def owner_statement(owner_id: int, db: Session = Depends(get_db)):
    return get_owner_account_statement(db, owner_id)


@router.get("/unit-statement/{unit_id}")
def unit_statement(unit_id: int, db: Session = Depends(get_db)):
    return get_unit_account_statement(db, unit_id)


@router.post("/payments")
def create_payment(payment_data: PaymentCreate, db: Session = Depends(get_db)):
    payment = Payment(
        owner_id=payment_data.owner_id,
        payment_date=payment_data.payment_date,
        amount=payment_data.amount,
        invoice_number=payment_data.invoice_number,
        reference=payment_data.reference,
    )
    # Guardar receipt_number si el modelo lo soporta
    if hasattr(payment, 'receipt_number'):
        payment.receipt_number = payment_data.receipt_number
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/apply-payment")
def apply_payment(payment_id: int, charge_id: int, amount: float, db: Session = Depends(get_db)):
    application = apply_payment_to_charge(db, payment_id, charge_id, amount)
    return {"message": "Pago aplicado correctamente", "application_id": application.id}


@router.post("/payment-complete")
def create_payment_complete(payment_data: PaymentCompleteCreate, db: Session = Depends(get_db)):
    # Pasar receipt_number al servicio si lo soporta
    payment = create_payment_with_applications(db, payment_data)
    return {"message": "Pago registrado correctamente", "payment_id": payment.id}


@router.get("/charges")
def get_charges(db: Session = Depends(get_db)):
    return list_charges_with_status(db)


@router.get("/payment/{payment_id}")
def payment_detail(payment_id: int, db: Session = Depends(get_db)):
    return get_payment_detail(db, payment_id)


@router.get("/payment-detail-full/{payment_id}")
def payment_detail_full(payment_id: int, db: Session = Depends(get_db)):
    return get_payment_detail_full(db, payment_id)


@router.get("/property-summary/{property_id}")
def property_summary(property_id: int, db: Session = Depends(get_db)):
    return get_property_financial_summary(db, property_id)


@router.post("/generate-invoice/payment/{payment_id}")
def generate_invoice(payment_id: int, fiscal_number: Optional[str] = None, db: Session = Depends(get_db)):
    invoice = create_invoice_for_payment(db, payment_id, fiscal_number)
    return {
        "message": "Factura generada correctamente",
        "internal_number": invoice.invoice_number,
        "fiscal_number": invoice.fiscal_invoice_number,
        "pdf_path": invoice.pdf_path,
    }


@router.get("/owner-statement-detailed/{owner_id}")
def owner_statement_detailed(owner_id: int, db: Session = Depends(get_db)):
    return generate_owner_statement(db, owner_id)


@router.get("/invoices")
def get_invoices(db: Session = Depends(get_db)):
    invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).all()
    result = []
    for inv in invoices:
        payment = db.query(Payment).filter(Payment.id == inv.payment_id).first()
        owner = db.query(Owner).filter(Owner.id == payment.owner_id).first() if payment else None

        # Obtener unidad activa del propietario para la factura
        unit_number = None
        if payment and payment.owner_id:
            uo = db.query(UnitOwner).filter(
                UnitOwner.owner_id == payment.owner_id,
                UnitOwner.is_active == True
            ).first()
            if uo:
                u = db.query(Unit).filter(Unit.id == uo.unit_id).first()
                if u:
                    unit_number = u.unit_number

        result.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "fiscal_invoice_number": inv.fiscal_invoice_number,
            "payment_id": inv.payment_id,
            "owner_name": owner.full_name if owner else "—",
            "unit_number": unit_number or "—",
            "amount": float(payment.amount) if payment else 0,
            "created_at": inv.created_at,
            "pdf_path": inv.pdf_path,
            # receipt_number del pago si existe
            "receipt_number": getattr(payment, 'receipt_number', None) if payment else None,
        })
    return result


@router.get("/invoices/{invoice_id}/download")
def download_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice or not invoice.pdf_path:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    from fastapi.responses import FileResponse
    import os

    if os.path.exists(invoice.pdf_path):
        return FileResponse(
            invoice.pdf_path,
            media_type="application/pdf",
            filename=f"factura_{invoice.invoice_number}.pdf",
        )
    raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")


@router.get("/payments-history")
def payments_history(db: Session = Depends(get_db)):
    """
    Devuelve todos los pagos del sistema con detalle completo.
    Incluye receipt_number si está disponible.
    """
    from app.models.payment import Payment
    from app.models.payment_application import PaymentApplication
    from app.models.charge import Charge
    from app.models.unit import Unit
    from app.models.unit_owner import UnitOwner
    from app.models.owner import Owner

    payments = db.query(Payment).order_by(Payment.payment_date.desc()).all()
    result   = []

    for p in payments:
        owner = db.query(Owner).filter(Owner.id == p.owner_id).first() if p.owner_id else None

        unit_number = None
        if p.owner_id:
            uo = db.query(UnitOwner).filter(
                UnitOwner.owner_id == p.owner_id,
                UnitOwner.is_active == True
            ).first()
            if uo:
                u = db.query(Unit).filter(Unit.id == uo.unit_id).first()
                if u:
                    unit_number = u.unit_number

        apps = db.query(PaymentApplication).filter(
            PaymentApplication.payment_id == p.id
        ).all()

        concepto    = None
        observacion = None

        if apps:
            descs = []
            for app in apps:
                c = db.query(Charge).filter(Charge.id == app.charge_id).first()
                if c:
                    descs.append(c.description)
            if descs:
                concepto = " / ".join(set(descs))

        if not concepto:
            ref = p.reference or ""
            if " — " in ref:
                partes      = ref.split(" — ", 1)
                concepto    = partes[0].strip()
                observacion = partes[1].strip()
            else:
                concepto    = ref.strip() or "—"
                observacion = None

        # Factura vinculada al pago (si existe)
        invoice = db.query(Invoice).filter(Invoice.payment_id == p.id).first()

        result.append({
            "payment_id":    p.id,
            "factura":       p.invoice_number,
            "fecha":         str(p.payment_date) if p.payment_date else None,
            "owner_id":      p.owner_id,
            "owner_name":    owner.full_name if owner else "—",
            "unit_number":   unit_number or "—",
            "concepto":      concepto or "—",
            "observacion":   observacion,
            "monto":         float(p.amount) if p.amount else 0,
            "referencia":    p.reference,
            "receipt_number": getattr(p, 'receipt_number', None),
            "tiene_cargos":  len(apps) > 0,
            "tiene_factura": invoice is not None,
            "invoice_id":    invoice.id if invoice else None,
        })

    return result


# ── Schemas para editar/borrar ────────────────────────────────

class PaymentUpdate(BaseModel):
    payment_date:   date
    amount:         float
    invoice_number: Optional[str] = None
    reference:      Optional[str] = None
    receipt_number: Optional[str] = None


# ── Dependencia admin ─────────────────────────────────────────
def _admin_only(current_user = Depends(get_current_user_dep)):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción")
    return current_user


# ── Editar pago — solo ADMIN ─────────────────────────────────
@router.put("/payment/{payment_id}")
def update_payment(
    payment_id: int,
    data: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(_admin_only),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    from decimal import Decimal
    payment.payment_date   = data.payment_date
    payment.amount         = Decimal(str(data.amount))
    payment.invoice_number = data.invoice_number
    payment.reference      = data.reference
    if hasattr(payment, 'receipt_number'):
        payment.receipt_number = data.receipt_number
    db.commit()
    db.refresh(payment)
    return {"message": "Pago actualizado", "payment_id": payment.id}


# ── Eliminar pago — solo ADMIN ───────────────────────────────
# FIX: El Error 500 al borrar ocurría porque la factura vinculada (Invoice)
# tenía una FK a payment_id y no se eliminaba antes de borrar el pago.
@router.delete("/payment/{payment_id}")
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(_admin_only),
):
    """
    Elimina un pago y revierte los saldos de los cargos afectados.
    También elimina la factura vinculada si existe.
    Solo ADMIN.
    """
    from decimal import Decimal
    from app.models.payment_application import PaymentApplication
    from app.models.charge import Charge

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    try:
        # 1. Revertir saldos de los cargos afectados
        apps = db.query(PaymentApplication).filter(
            PaymentApplication.payment_id == payment_id
        ).all()

        for app in apps:
            charge = db.query(Payment.__class__).filter(
                PaymentApplication.charge_id == app.charge_id
            ).first() if False else db.query(Charge).filter(Charge.id == app.charge_id).first()

            if charge:
                charge.balance = Decimal(str(charge.balance)) + Decimal(str(app.applied_amount))
                if charge.balance >= Decimal(str(charge.amount)):
                    charge.status = "PENDIENTE"
                else:
                    charge.status = "PARCIAL"
            db.delete(app)

        # 2. Eliminar la factura vinculada (si existe) — esto era la causa del Error 500
        invoice = db.query(Invoice).filter(Invoice.payment_id == payment_id).first()
        if invoice:
            db.delete(invoice)

        # 3. Eliminar el pago
        db.delete(payment)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar pago: {str(e)}")

    return {"message": "Pago eliminado y saldos revertidos correctamente"}


# ── Endpoint para que admin vea todos los pagos ───────────────
@router.get("/all-payments")
def get_all_payments(
    db: Session = Depends(get_db),
    current_user = Depends(_admin_only),
):
    from app.models.owner import Owner
    from app.models.unit_owner import UnitOwner
    from app.models.unit import Unit
    from app.models.payment_application import PaymentApplication
    from app.models.charge import Charge

    payments = db.query(Payment).order_by(Payment.payment_date.desc()).all()
    result   = []

    for p in payments:
        owner = db.query(Owner).filter(Owner.id == p.owner_id).first()
        uo    = db.query(UnitOwner).filter(
            UnitOwner.owner_id == p.owner_id, UnitOwner.is_active == True
        ).first()
        unit  = db.query(Unit).filter(Unit.id == uo.unit_id).first() if uo else None

        apps  = db.query(PaymentApplication).filter(
            PaymentApplication.payment_id == p.id
        ).all()
        cargos = []
        for a in apps:
            c = db.query(Charge).filter(Charge.id == a.charge_id).first()
            if c:
                cargos.append({"description": c.description, "applied": float(a.applied_amount)})

        invoice = db.query(Invoice).filter(Invoice.payment_id == p.id).first()

        result.append({
            "payment_id":    p.id,
            "fecha":         str(p.payment_date),
            "owner_name":    owner.full_name if owner else "—",
            "unit_number":   unit.unit_number if unit else "—",
            "amount":        float(p.amount),
            "invoice_number": p.invoice_number,
            "reference":     p.reference,
            "receipt_number": getattr(p, 'receipt_number', None),
            "cargos":        cargos,
            "tiene_factura": invoice is not None,
            "invoice_id":    invoice.id if invoice else None,
        })

    return result
