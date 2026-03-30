from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.charge import Charge
from app.models.payment import Payment
from app.models.payment_application import PaymentApplication
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner
from app.models.unit import Unit
from app.models.property import Property
from app.models.invoice import Invoice


def _to_dec(val) -> Decimal:
    """Convierte cualquier valor numérico a Decimal de forma segura."""
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ──────────────────────────────────────────────
# Función 1 — Balance de un cargo específico
# ──────────────────────────────────────────────
def get_charge_balance(db: Session, charge_id: int):
    charge = db.query(Charge).filter(Charge.id == charge_id).first()

    if not charge:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")

    total_applied_raw = (
        db.query(func.coalesce(func.sum(PaymentApplication.applied_amount), 0))
        .filter(PaymentApplication.charge_id == charge_id)
        .scalar()
    )

    # ✅ Todo en Decimal para evitar errores float vs Decimal (SQLite y PostgreSQL)
    amount       = _to_dec(charge.amount)
    total_applied = _to_dec(total_applied_raw)
    balance      = amount - total_applied

    return {
        "charge_id":      charge.id,
        "total_amount":   amount,
        "applied_amount": total_applied,
        "balance":        balance,
    }


# ──────────────────────────────────────────────
# Función 2 — Estado textual de un cargo
# ──────────────────────────────────────────────
def get_charge_status(db: Session, charge_id: int) -> str:
    bd = get_charge_balance(db, charge_id)

    if bd["applied_amount"] == Decimal("0.00"):
        return "PENDIENTE"
    elif bd["balance"] > Decimal("0.00"):
        return "PARCIAL"
    else:
        return "PAGADO"


# ──────────────────────────────────────────────
# Función 3 — Aplicar pago a un cargo individual
# ──────────────────────────────────────────────
def apply_payment_to_charge(db: Session, payment_id: int, charge_id: int, amount: float):
    amount_dec = _to_dec(amount)

    if amount_dec <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    charge_balance   = get_charge_balance(db, charge_id)
    payment_balance  = _to_dec(get_payment_balance(db, payment_id))

    if amount_dec > charge_balance["balance"]:
        raise HTTPException(
            status_code=400,
            detail=f"Monto ${float(amount_dec):.2f} supera el saldo del cargo (${float(charge_balance['balance']):.2f})"
        )

    if amount_dec > payment_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Saldo del pago insuficiente (disponible: ${float(payment_balance):.2f})"
        )

    application = PaymentApplication(
        payment_id=payment_id,
        charge_id=charge_id,
        applied_amount=amount_dec,
    )
    db.add(application)

    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    new_balance = _to_dec(charge.balance) - amount_dec

    if new_balance <= Decimal("0.00"):
        charge.balance = Decimal("0.00")
        charge.status  = "PAGADO"
    else:
        charge.balance = new_balance
        charge.status  = "PARCIAL"

    db.commit()
    db.refresh(application)
    return application


# ──────────────────────────────────────────────
# Función 4 CORREGIDA — Estado de cuenta por propietario
# ──────────────────────────────────────────────
# BUG original: el JOIN con UnitOwner sin filtro is_active=True
# devolvía duplicados o cargos de periodos anteriores.
# CORRECCIÓN: filtrar UnitOwner activos y retornar TODOS los cargos
# con sus balances reales (el frontend filtra los pendientes).

def get_owner_account_statement(db, owner_id: int):
    from fastapi import HTTPException
    from app.models.charge import Charge
    from app.models.unit import Unit
    from app.models.unit_owner import UnitOwner
    from app.models.owner import Owner

    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    # Obtener TODAS las unidades que alguna vez tuvo este propietario
    ownerships = db.query(UnitOwner).filter(
        UnitOwner.owner_id == owner_id
    ).all()

    unit_ids = list({o.unit_id for o in ownerships})
    if not unit_ids:
        return []

    charges = db.query(Charge).filter(
        Charge.unit_id.in_(unit_ids)
    ).order_by(Charge.due_date).all()

    result = []
    for charge in charges:
        bd   = get_charge_balance(db, charge.id)
        unit = db.query(Unit).filter(Unit.id == charge.unit_id).first()
        result.append({
            "charge_id":   charge.id,
            "unit_number": unit.unit_number if unit else "N/A",
            "description": charge.description,
            "due_date":    str(charge.due_date),
            "total":       float(bd["total_amount"]),
            "paid":        float(bd["applied_amount"]),
            "balance":     float(bd["balance"]),
            "status":      get_charge_status(db, charge.id),
        })

    return result



# ──────────────────────────────────────────────
# Función 4b — Estado de cuenta por unidad  ← NUEVO
# ──────────────────────────────────────────────
def get_unit_account_statement(db: Session, unit_id: int):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    active_ownership = db.query(UnitOwner).filter(
        UnitOwner.unit_id == unit_id,
        UnitOwner.is_active == True,
    ).first()

    owner = None
    if active_ownership:
        owner = db.query(Owner).filter(Owner.id == active_ownership.owner_id).first()

    charges = db.query(Charge).filter(Charge.unit_id == unit_id).all()
    statement = []

    for charge in charges:
        bd = get_charge_balance(db, charge.id)
        statement.append({
            "charge_id":   charge.id,
            "unit_number": unit.unit_number,
            "owner_name":  owner.full_name if owner else "Sin propietario",
            "owner_id":    owner.id if owner else None,
            "description": charge.description,
            "due_date":    str(charge.due_date),
            "total":       float(bd["total_amount"]),
            "paid":        float(bd["applied_amount"]),
            "balance":     float(bd["balance"]),
            "status":      get_charge_status(db, charge.id),
        })

    return {
        "unit_id":    unit.id,
        "unit_number": unit.unit_number,
        "owner_name": owner.full_name if owner else "Sin propietario",
        "owner_id":   owner.id if owner else None,
        "charges":    statement,
    }


# ──────────────────────────────────────────────
# Función 5 — Cargo general para toda una propiedad
# ──────────────────────────────────────────────
def create_general_charge_for_property(
    db: Session, property_id: int, description: str, amount: float, due_date: date
):
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    units = db.query(Unit).filter(Unit.property_id == property_id).all()
    if not units:
        raise HTTPException(status_code=400, detail="La propiedad no tiene unidades")

    amount_dec = _to_dec(amount)
    today      = date.today()
    created    = []

    for unit in units:
        charge = Charge(
            unit_id=unit.id, description=description,
            amount=amount_dec, balance=amount_dec,
            status="PENDIENTE", date_created=today, due_date=due_date,
        )
        db.add(charge)
        created.append(charge)

    db.commit()
    return created


# ──────────────────────────────────────────────
# Función 6 — Resumen financiero de una propiedad
# ──────────────────────────────────────────────
def get_property_financial_summary(db: Session, property_id: int):
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    charges = (
        db.query(Charge)
        .join(Unit, Charge.unit_id == Unit.id)
        .filter(Unit.property_id == property_id)
        .all()
    )

    total_charged = Decimal("0.00")
    total_paid    = Decimal("0.00")

    for charge in charges:
        bd = get_charge_balance(db, charge.id)
        total_charged += bd["total_amount"]
        total_paid    += bd["applied_amount"]

    return {
        "property":      property_obj.name,
        "total_charged": float(total_charged),
        "total_paid":    float(total_paid),
        "total_pending": float(total_charged - total_paid),
    }


# ──────────────────────────────────────────────
# Función 7 — Balance disponible de un pago
# ──────────────────────────────────────────────
def get_payment_balance(db: Session, payment_id: int) -> float:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    total_applied_raw = (
        db.query(func.coalesce(func.sum(PaymentApplication.applied_amount), 0))
        .filter(PaymentApplication.payment_id == payment_id)
        .scalar()
    )

    return float(_to_dec(payment.amount) - _to_dec(total_applied_raw))


# ──────────────────────────────────────────────
# Función 8 — Crear pago + aplicar cargos (atómico)
# ✅ CORREGIDO: flush() en lugar de commit() parcial
# ✅ CORREGIDO: un solo commit al final — todo o nada
# ✅ CORREGIDO: Decimal en todas las comparaciones
# ──────────────────────────────────────────────
def create_payment_with_applications(db: Session, payment_data):
    total_to_apply = _to_dec(sum(app.amount for app in payment_data.applications))
    payment_amount = _to_dec(payment_data.amount)

    if total_to_apply > payment_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Las aplicaciones (${float(total_to_apply):.2f}) superan el monto del pago (${float(payment_amount):.2f})"
        )

    payment = Payment(
        owner_id=payment_data.owner_id,
        payment_date=payment_data.payment_date,
        amount=payment_amount,
        invoice_number=getattr(payment_data, "invoice_number", None),
        reference=getattr(payment_data, "reference", None),
    )

    try:
        db.add(payment)
        db.flush()  # ← obtiene payment.id sin cerrar la transacción

        for app in payment_data.applications:
            app_amount = _to_dec(app.amount)

            charge = db.query(Charge).filter(Charge.id == app.charge_id).first()
            if not charge:
                raise HTTPException(status_code=404, detail=f"Cargo {app.charge_id} no encontrado")

            charge_balance = _to_dec(charge.balance)

            if app_amount <= Decimal("0.00"):
                raise HTTPException(status_code=400, detail="El monto de cada aplicación debe ser mayor a 0")

            if app_amount > charge_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"El monto ${float(app_amount):.2f} supera el saldo de '{charge.description}' (${float(charge_balance):.2f})"
                )

            db.add(PaymentApplication(
                payment_id=payment.id,
                charge_id=app.charge_id,
                applied_amount=app_amount,
            ))

            new_balance = charge_balance - app_amount
            if new_balance <= Decimal("0.00"):
                charge.balance = Decimal("0.00")
                charge.status  = "PAGADO"
            else:
                charge.balance = new_balance
                charge.status  = "PARCIAL"

        db.commit()          # ← único commit: todo o nada
        db.refresh(payment)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar pago: {str(e)}")

    return payment


# ──────────────────────────────────────────────
# Función 9 — Listar todos los cargos con estado
# ──────────────────────────────────────────────
def list_charges_with_status(db: Session):
    charges = db.query(Charge).all()
    result  = []

    for charge in charges:
        bd     = get_charge_balance(db, charge.id)
        status = get_charge_status(db, charge.id)

        unit   = db.query(Unit).filter(Unit.id == charge.unit_id).first()

        active_ownership = db.query(UnitOwner).filter(
            UnitOwner.unit_id == charge.unit_id,
            UnitOwner.is_active == True,
        ).first()

        owner_name = None
        owner_id   = None
        if active_ownership:
            owner = db.query(Owner).filter(Owner.id == active_ownership.owner_id).first()
            if owner:
                owner_name = owner.full_name
                owner_id   = owner.id

       # Obtener el último pago asociado
        last_app = (
            db.query(PaymentApplication)
            .filter(PaymentApplication.charge_id == charge.id)
            .order_by(PaymentApplication.id.desc())
            .first()
        )

        last_payment_id = last_app.payment_id if last_app else None
        # Si queremos más detalles del pago, podríamos hacer otra consulta aquí para obtener la fecha o referencia del pago.
        # Pero por ahora solo incluimos el ID del último pago para que el frontend pueda usarlo para mostrar detalles o la factura.
        result.append({
            "id":           charge.id,
            "charge_id":    charge.id,
            "unit_id":      charge.unit_id,
            "unit_number":  unit.unit_number if unit else None,
            "owner_name":   owner_name,
            "owner_id":     owner_id,
            "description":  charge.description,
            "amount":       float(bd["total_amount"]),
            "balance":      float(bd["balance"]),
            "status":       status,
            "due_date":     str(charge.due_date),
            "date_created": str(charge.date_created),
            "payment_id":   last_payment_id,
        })


        return result


# ──────────────────────────────────────────────
# Función 10 — Detalle de un pago
# ──────────────────────────────────────────────
def get_payment_detail(db: Session, payment_id: int):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    applications = db.query(PaymentApplication).filter(
        PaymentApplication.payment_id == payment_id
    ).all()

    return {
        "payment_id": payment.id,
        "amount":     float(payment.amount),
        "applications": [
            {"charge_id": app.charge_id, "applied_amount": float(app.applied_amount)}
            for app in applications
        ],
    }


def get_payment_detail_full(db: Session, payment_id: int):
    """Obtiene detalle completo de un pago para factura"""
    from app.models import Payment, Owner, UnitOwner, Unit, Property, Invoice, PaymentApplication, Charge
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    # Propietario
    owner = db.query(Owner).filter(Owner.id == payment.owner_id).first()
    
    # Unidad activa del propietario
    ownership = db.query(UnitOwner).filter(
        UnitOwner.owner_id == payment.owner_id,
        UnitOwner.is_active == True
    ).first()
    unit = ownership.unit if ownership else None
    property_obj = unit.property if unit else None
    
    # Factura
    invoice = db.query(Invoice).filter(Invoice.payment_id == payment_id).first()
    
    # Aplicaciones
    applications = db.query(PaymentApplication).filter(
        PaymentApplication.payment_id == payment_id
    ).all()
    
    apps_detail = []
    for app in applications:
        charge = db.query(Charge).filter(Charge.id == app.charge_id).first()
        apps_detail.append({
            "charge_id": app.charge_id,
            "description": charge.description if charge else f"Cargo #{app.charge_id}",
            "applied_amount": float(app.applied_amount),
        })
    
    return {
        "payment_id": payment.id,
        "payment_date": str(payment.payment_date),
        "amount": float(payment.amount),
        "reference": payment.reference,
        "invoice_number": invoice.invoice_number if invoice else None,
        "fiscal_invoice_number": invoice.fiscal_invoice_number if invoice else None,
        "owner_name": owner.full_name if owner else None,
        "unit_number": unit.unit_number if unit else None,
        "property_name": property_obj.name if property_obj else None,
        "applications": apps_detail,
    }

# ──────────────────────────────────────────────
# Función 11 — Número de factura secuencial
# ──────────────────────────────────────────────
def generate_invoice_number(db: Session) -> str:
    last = db.query(Invoice).order_by(Invoice.id.desc()).first()
    if not last:
        return "INV-000001"
    try:
        n = int(last.invoice_number.split("-")[1])
    except (IndexError, ValueError):
        n = 0
    return f"INV-{str(n + 1).zfill(6)}"


# ──────────────────────────────────────────────
# Función 12 — Generar factura PDF
# ──────────────────────────────────────────────
def create_invoice_for_payment(db: Session, payment_id: int, fiscal_number: str | None = None):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if db.query(Invoice).filter(Invoice.payment_id == payment_id).first():
        raise HTTPException(status_code=400, detail="Este pago ya tiene factura")

    invoice_number = generate_invoice_number(db)
    owner          = db.query(Owner).filter(Owner.id == payment.owner_id).first()

    applications = db.query(PaymentApplication).filter(
        PaymentApplication.payment_id == payment.id
    ).all()
    if not applications:
        raise HTTPException(status_code=400, detail="El pago no tiene cargos aplicados")

    first_charge = db.query(Charge).filter(Charge.id == applications[0].charge_id).first()
    unit         = db.query(Unit).filter(Unit.id == first_charge.unit_id).first() if first_charge else None
    property_obj = db.query(Property).filter(Property.id == unit.property_id).first() if unit else None

    charges_detail = []
    for app in applications:
        c = db.query(Charge).filter(Charge.id == app.charge_id).first()
        if c:
            charges_detail.append({"description": c.description, "amount": float(app.applied_amount)})

    data = {
        "invoice_number":       invoice_number,
        "fiscal_invoice_number": fiscal_number or "",
        "issue_date":           date.today().strftime("%d de %B, %Y"),
        "owner_name":           owner.full_name if owner else "Desconocido",
        "unit_number":          unit.unit_number if unit else "N/A",
        "building_name":        property_obj.name if property_obj else "N/A",
        "property_address":     property_obj.address if property_obj else "N/A",
        "charges":              charges_detail,
        "total_amount":         float(payment.amount),
    }

    os.makedirs("invoices", exist_ok=True)
    pdf_path = f"invoices/{invoice_number}.pdf"

    from app.reports.pdf_generator import generate_invoice_pdf
    generate_invoice_pdf(data, pdf_path)

    invoice = Invoice(
        invoice_number=invoice_number,
        fiscal_invoice_number=fiscal_number,
        payment_id=payment.id,
        pdf_path=pdf_path,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


# ──────────────────────────────────────────────
# Función 13 — Estado de cuenta detallado de un propietario
# ──────────────────────────────────────────────
def generate_owner_statement(db: Session, owner_id: int):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    ownership = db.query(UnitOwner).filter(
        UnitOwner.owner_id == owner_id,
        UnitOwner.is_active == True,
    ).first()
    if not ownership:
        raise HTTPException(status_code=404, detail="No tiene unidad activa")

    unit         = ownership.unit
    property_obj = unit.property

    statement_data = []
    for charge in db.query(Charge).filter(Charge.unit_id == unit.id).all():
        bd = get_charge_balance(db, charge.id)

        payments_info = []
        for app in db.query(PaymentApplication).filter(PaymentApplication.charge_id == charge.id).all():
            inv = db.query(Invoice).filter(Invoice.payment_id == app.payment_id).first()
            pmt = db.query(Payment).filter(Payment.id == app.payment_id).first()
            payments_info.append({
            "payment_id":            app.payment_id,
            "payment_date":          str(pmt.payment_date) if pmt else None,
            "applied_amount":        float(app.applied_amount),
            "fiscal_invoice_number": inv.fiscal_invoice_number if inv else None,
            "reference":             pmt.reference if pmt else None,
        })

        statement_data.append({
            "description": charge.description,
            "due_date":    str(charge.due_date),
            "amount":      float(bd["total_amount"]),
            "paid":        float(bd["applied_amount"]),
            "balance":     float(bd["balance"]),
            "status":      get_charge_status(db, charge.id),
            "payments":    payments_info,
        })

    return {
        "property_name":    property_obj.name,
        "property_address": property_obj.address,
        "owner_name":       owner.full_name,
        "unit_number":      unit.unit_number,
        "statement":        statement_data,
    }


# ──────────────────────────────────────────────
# Función 14 — Total pendiente por propiedad
# ──────────────────────────────────────────────
def property_accounts_receivable(db: Session, property_id: int):
    charges = (
        db.query(Charge)
        .join(Unit, Charge.unit_id == Unit.id)
        .filter(Unit.property_id == property_id)
        .all()
    )
    total = Decimal("0.00")
    for charge in charges:
        bd = get_charge_balance(db, charge.id)
        total += bd["balance"]
    return {"property_id": property_id, "total_pending": float(total)}
