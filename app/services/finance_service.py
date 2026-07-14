from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.models.charge import Charge
from app.models.payment import Payment
from app.models.payment_application import PaymentApplication
from app.models.owner import Owner
from app.models.unit_owner import UnitOwner
from app.models.unit import Unit
from app.models.property import Property
from app.models.invoice import Invoice
from app.models.owner_credit import OwnerCredit
from app.models.credit_application import CreditApplication


def _to_dec(val) -> Decimal:
    """Convierte cualquier valor numérico a Decimal de forma segura."""
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ──────────────────────────────────────────────
# Helpers anti N+1: calculan balance/estado de un Charge a partir de
# relaciones YA CARGADAS en memoria (via selectinload), sin disparar
# queries adicionales. Úsalos únicamente cuando el Charge fue cargado con
# selectinload(Charge.applications) y selectinload(Charge.credit_applications)
# -- si no, el resultado sería incorrecto por no reflejar todas las filas.
# Misma fórmula que get_charge_balance/get_charge_status (Función 1/2),
# que se mantienen intactas para el resto de los call sites.
# ──────────────────────────────────────────────
def _charge_balance_from_relations(charge: "Charge") -> dict:
    total_applied_payments = sum((a.applied_amount for a in charge.applications), Decimal("0.00"))
    total_applied_credits = sum((c.applied_amount for c in charge.credit_applications), Decimal("0.00"))

    amount        = _to_dec(charge.amount)
    total_applied = _to_dec(total_applied_payments) + _to_dec(total_applied_credits)
    balance       = amount - total_applied

    return {
        "charge_id":      charge.id,
        "total_amount":   amount,
        "applied_amount": total_applied,
        "balance":        balance,
    }


def _charge_status_from_balance(bd: dict) -> str:
    if bd["applied_amount"] == Decimal("0.00"):
        return "PENDIENTE"
    elif bd["balance"] > Decimal("0.00"):
        return "PARCIAL"
    else:
        return "PAGADO"


# ──────────────────────────────────────────────
# Función 1 — Balance de un cargo específico
# ──────────────────────────────────────────────
def get_charge_balance(db: Session, charge_id: int):
    charge = db.query(Charge).filter(Charge.id == charge_id).first()

    if not charge:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")

    total_applied_payments_raw = (
        db.query(func.coalesce(func.sum(PaymentApplication.applied_amount), 0))
        .filter(PaymentApplication.charge_id == charge_id)
        .scalar()
    )
    total_applied_credits_raw = (
        db.query(func.coalesce(func.sum(CreditApplication.applied_amount), 0))
        .filter(CreditApplication.charge_id == charge_id)
        .scalar()
    )

    # ✅ Todo en Decimal para evitar errores float vs Decimal (SQLite y PostgreSQL)
    amount        = _to_dec(charge.amount)
    total_applied = _to_dec(total_applied_payments_raw) + _to_dec(total_applied_credits_raw)
    balance       = amount - total_applied

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
    new_balance = charge_balance["balance"] - amount_dec

    if new_balance <= Decimal("0.00"):
        charge.status = "PAGADO"
    else:
        charge.status = "PARCIAL"

    db.commit()
    db.refresh(application)
    return application


# ──────────────────────────────────────────────
# Función 3b — Aplicar saldo a favor (OwnerCredit) a un cargo
# ──────────────────────────────────────────────
def apply_credit_to_charge(db: Session, credit_id: int, charge_id: int, amount: float):
    amount_dec = _to_dec(amount)

    if amount_dec <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    credit = db.query(OwnerCredit).filter(OwnerCredit.id == credit_id).first()
    if not credit:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")

    credit_remaining = _to_dec(credit.remaining_amount)
    if amount_dec > credit_remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Monto ${float(amount_dec):.2f} supera el saldo disponible del crédito (${float(credit_remaining):.2f})"
        )

    charge_balance = get_charge_balance(db, charge_id)
    if amount_dec > charge_balance["balance"]:
        raise HTTPException(
            status_code=400,
            detail=f"Monto ${float(amount_dec):.2f} supera el saldo del cargo (${float(charge_balance['balance']):.2f})"
        )

    credit_application = CreditApplication(
        credit_id=credit_id,
        charge_id=charge_id,
        applied_amount=amount_dec,
    )
    db.add(credit_application)

    credit.remaining_amount = credit_remaining - amount_dec

    charge = db.query(Charge).filter(Charge.id == charge_id).first()
    new_balance = charge_balance["balance"] - amount_dec

    if new_balance <= Decimal("0.00"):
        charge.status = "PAGADO"
    else:
        charge.status = "PARCIAL"

    db.commit()
    db.refresh(credit_application)
    return credit_application


# ──────────────────────────────────────────────
# Función 4 CORREGIDA — Estado de cuenta por propietario
# ──────────────────────────────────────────────
# Función 4b — Estado de cuenta unificado, organizado por UNIDAD
# Única fuente de verdad: usa get_charge_balance/get_charge_status para
# cada cargo, nunca recalcula el balance por su cuenta.
# ──────────────────────────────────────────────
def get_unit_account_statement(db: Session, unit_id: int, include_history: bool = False, from_date: "date | None" = None):
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

    property_obj = unit.property

    # Anti N+1: una sola query trae los Charges de la unidad, y selectinload
    # trae de una vez TODAS sus PaymentApplication (+ el Payment de cada una)
    # y CreditApplication en 3 queries adicionales fijas, sin importar cuántos
    # cargos/pagos tenga la unidad (antes: 2 queries por cargo por balance/
    # estado + N queries más si include_history, y encima la lista de charges
    # se volvía a traer completa para el ledger).
    charges = (
        db.query(Charge)
        .filter(Charge.unit_id == unit_id)
        .options(
            selectinload(Charge.applications).selectinload(PaymentApplication.payment),
            selectinload(Charge.credit_applications),
        )
        .order_by(Charge.date_created)
        .all()
    )

    # Facturas fiscales de los pagos aplicados a estos cargos, batch en una
    # sola query (antes: 1 query de Invoice por cada PaymentApplication).
    payment_ids_referenced = {app.payment_id for c in charges for app in c.applications}
    invoices_by_payment = {}
    if payment_ids_referenced:
        invs = db.query(Invoice).filter(Invoice.payment_id.in_(payment_ids_referenced)).all()
        invoices_by_payment = {inv.payment_id: inv for inv in invs}

    statement = []
    total_due = Decimal("0.00")
    apps_by_payment = {}  # payment_id -> [PaymentApplication, ...], reutilizado abajo para el ledger

    for charge in charges:
        for app in charge.applications:
            apps_by_payment.setdefault(app.payment_id, []).append(app)

        bd     = _charge_balance_from_relations(charge)
        status = _charge_status_from_balance(bd)

        if not include_history and status == "PAGADO":
            continue

        if status != "PAGADO":
            total_due += bd["balance"]

        entry = {
            "charge_id":   charge.id,
            "unit_id":     unit.id,
            "unit_number": unit.unit_number,
            "owner_name":  owner.full_name if owner else "Sin propietario",
            "owner_id":    owner.id if owner else None,
            "description":  charge.description,
            "date_created": str(charge.date_created),
            "due_date":     str(charge.due_date) if charge.due_date else None,
            "amount":      float(bd["total_amount"]),
            "total":       float(bd["total_amount"]),
            "paid":        float(bd["applied_amount"]),
            "balance":     float(bd["balance"]),
            "status":      status,
        }

        if include_history:
            payments_info = []
            for app in charge.applications:
                pmt = app.payment
                inv = invoices_by_payment.get(app.payment_id)
                payments_info.append({
                    "payment_id":            app.payment_id,
                    "payment_date":          str(pmt.payment_date) if pmt else None,
                    "applied_amount":        float(app.applied_amount),
                    "fiscal_invoice_number": inv.fiscal_invoice_number if inv else None,
                    "reference":             pmt.reference if pmt else None,
                })
            entry["payments"] = payments_info

        statement.append(entry)

    # ── Ledger agrupado (Parte 2c/2d) ───────────────────────────────
    # Estado de cuenta = SIEMPRE todos los conceptos mezclados en una sola
    # tabla cronológica (nunca filtrado por concepto), con balance corrido
    # real (nunca solo cargos-pagos del período visible). Un mismo Payment
    # con varias PaymentApplication (repartido vía FIFO) se colapsa en UNA
    # sola fila. Reutiliza `charges` y `apps_by_payment` ya cargados arriba
    # -- antes esto volvía a traer todos los Charges y PaymentApplication
    # desde cero, más un query de Payment por cada payment_id único.
    all_charges = charges
    charge_desc_by_id = {c.id: c.description for c in all_charges}

    ledger_rows = []
    for c in all_charges:
        ledger_rows.append({
            "fecha":     str(c.date_created),
            "tipo":      "CARGO",
            "documento": "—",
            "concepto":  c.description,
            "cargo":     float(c.amount),
            "pago":      0.0,
            "_order":    0,
        })

    for payment_id, apps in apps_by_payment.items():
        payment = apps[0].payment  # ya precargado via selectinload, sin query extra
        if not payment:
            continue
        total_pago = sum((a.applied_amount for a in apps), Decimal("0.00"))
        conceptos = {charge_desc_by_id.get(a.charge_id, "—") for a in apps}
        concepto = conceptos.pop() if len(conceptos) == 1 else "Varios conceptos"
        documento = (
            getattr(payment, "receipt_number", None)
            or payment.invoice_number
            or payment.reference
            or f"Pago #{payment.id}"
        )
        ledger_rows.append({
            "fecha":     str(payment.payment_date) if payment.payment_date else "",
            "tipo":      "PAGO",
            "documento": documento,
            "concepto":  concepto,
            "cargo":     0.0,
            "pago":      float(total_pago),
            "_order":    1,
        })

    # Orden cronológico ascendente; en la misma fecha, el cargo va antes que su pago.
    ledger_rows.sort(key=lambda r: (r["fecha"], r["_order"]))

    saldo = Decimal("0.00")
    for row in ledger_rows:
        saldo += _to_dec(row["cargo"]) - _to_dec(row["pago"])
        row["saldo"] = float(saldo)

    saldo_actual = float(saldo)

    # Si se filtra desde una fecha que no es el origen de la cuenta, se
    # antepone una fila "Saldo inicial al [fecha]" con el acumulado hasta
    # ese punto, y el resto del ledger arranca desde ahí.
    if from_date is not None:
        from_date_str = str(from_date)
        saldo_previo = Decimal("0.00")
        visibles = []
        for row in ledger_rows:
            if row["fecha"] < from_date_str:
                saldo_previo += _to_dec(row["cargo"]) - _to_dec(row["pago"])
            else:
                visibles.append(row)
        if visibles or saldo_previo != Decimal("0.00"):
            ledger_rows = [{
                "fecha":     from_date_str,
                "tipo":      "INICIAL",
                "documento": "—",
                "concepto":  f"Saldo inicial al {from_date_str}",
                "cargo":     0.0,
                "pago":      0.0,
                "saldo":     float(saldo_previo),
                "_order":    -1,
            }] + visibles
        else:
            ledger_rows = visibles

    for row in ledger_rows:
        row.pop("_order", None)

    # Totales para las tarjetas resumen (Parte 4b): sobre TODO el historial,
    # no solo lo visible tras un from_date.
    total_cargos  = sum((_to_dec(c.amount) for c in all_charges), Decimal("0.00"))
    total_pagos   = sum((_to_dec(a.applied_amount) for apps in apps_by_payment.values() for a in apps), Decimal("0.00"))
    total_recargos = sum(
        (_to_dec(c.amount) for c in all_charges if c.related_charge_id is not None),
        Decimal("0.00"),
    )

    return {
        "unit_id":           unit.id,
        "unit_number":       unit.unit_number,
        "owner_name":        owner.full_name if owner else "Sin propietario",
        "owner_id":          owner.id if owner else None,
        "property_name":     property_obj.name if property_obj else None,
        "property_address":  property_obj.address if property_obj else None,
        "property_phone":    getattr(property_obj, "phone", None) if property_obj else None,
        "property_email":    getattr(property_obj, "email", None) if property_obj else None,
        "property_website":  getattr(property_obj, "website", None) if property_obj else None,
        "total_due":         float(total_due),
        "total_cargos":      float(total_cargos),
        "total_pagos":       float(total_pagos),
        "total_recargos":    float(total_recargos),
        "charges":           statement,
        "ledger":            ledger_rows,
        "saldo_actual":      saldo_actual,
    }


# ──────────────────────────────────────────────
# Wrapper — Estado de cuenta por propietario (lista plana, todas sus unidades)
# Usado por el flujo de pago "por propietario" del frontend. No recalcula
# balance por su cuenta: agrega los resultados de get_unit_account_statement
# por cada unidad que el propietario tiene o ha tenido.
# ──────────────────────────────────────────────
def get_owner_account_statement(db: Session, owner_id: int):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    unit_ids = [
        row[0] for row in
        db.query(UnitOwner.unit_id).filter(UnitOwner.owner_id == owner_id).distinct().all()
    ]

    charges = []
    for unit_id in unit_ids:
        stmt = get_unit_account_statement(db, unit_id, include_history=True)
        charges.extend(stmt["charges"])

    charges.sort(key=lambda c: c["due_date"])
    return charges


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
            amount=amount_dec,
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

    # Anti N+1: 1 query (con join) + 2 selectinload en vez de 2 queries por
    # cada cargo de la propiedad.
    charges = (
        db.query(Charge)
        .join(Unit, Charge.unit_id == Unit.id)
        .filter(Unit.property_id == property_id)
        .options(
            selectinload(Charge.applications),
            selectinload(Charge.credit_applications),
        )
        .all()
    )

    total_charged = Decimal("0.00")
    total_paid    = Decimal("0.00")

    for charge in charges:
        bd = _charge_balance_from_relations(charge)
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
# nueva función 8b — Crear pago con aplicaciones (corrección de bugs y mejoras)
def create_payment_with_applications(db, payment_data):
    """
    FIX: Ahora también guarda receipt_number si el modelo Payment lo soporta.
    """
    def _to_dec(v):
        return Decimal(str(v)) if v is not None else Decimal("0.00")

    total_to_apply = _to_dec(sum(app.amount for app in payment_data.applications))
    payment_amount = _to_dec(payment_data.amount)

    if total_to_apply > payment_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Las aplicaciones (${float(total_to_apply):.2f}) superan el monto del pago (${float(payment_amount):.2f})"
        )

    payment = Payment(
        owner_id       = payment_data.owner_id,
        payment_date   = payment_data.payment_date,
        amount         = payment_amount,
        invoice_number = getattr(payment_data, "invoice_number", None),
        reference      = getattr(payment_data, "reference", None),
        concept        = getattr(payment_data, "concept", None),
    )
    # Guardar receipt_number si el modelo lo tiene
    if hasattr(payment, 'receipt_number'):
        payment.receipt_number = getattr(payment_data, 'receipt_number', None)

    try:
        db.add(payment)
        db.flush()

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
                charge.status = "PAGADO"
            else:
                charge.status = "PARCIAL"

        # Excedente del pago sobre lo efectivamente aplicado a cargos: se guarda
        # como saldo a favor del propietario, en vez de perderse o fallar.
        excess = payment_amount - total_to_apply
        if excess > Decimal("0.00"):
            db.add(OwnerCredit(
                owner_id=payment_data.owner_id,
                source_payment_id=payment.id,
                amount=excess,
                remaining_amount=excess,
            ))

        db.commit()
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
    # Anti N+1: 1 query para todos los Charges (con sus aplicaciones
    # precargadas) + 3 queries batch (units, active ownerships, owners) en
    # vez de ~6 queries por cada cargo (balance x2, unit, ownership, owner,
    # último pago).
    charges = (
        db.query(Charge)
        .options(
            selectinload(Charge.applications),
            selectinload(Charge.credit_applications),
        )
        .all()
    )

    unit_ids = {c.unit_id for c in charges}
    unit_by_id = {}
    if unit_ids:
        units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all()
        unit_by_id = {u.id: u for u in units}

    active_ownerships = []
    if unit_ids:
        active_ownerships = db.query(UnitOwner).filter(
            UnitOwner.unit_id.in_(unit_ids),
            UnitOwner.is_active == True,
        ).all()
    owner_ids = {ao.owner_id for ao in active_ownerships}
    owner_by_id = {}
    if owner_ids:
        owners = db.query(Owner).filter(Owner.id.in_(owner_ids)).all()
        owner_by_id = {o.id: o for o in owners}
    active_owner_by_unit = {ao.unit_id: owner_by_id.get(ao.owner_id) for ao in active_ownerships}

    result = []
    for charge in charges:
        bd     = _charge_balance_from_relations(charge)
        status = _charge_status_from_balance(bd)

        unit  = unit_by_id.get(charge.unit_id)
        owner = active_owner_by_unit.get(charge.unit_id)

        # Último pago aplicado (charge.applications ya viene precargado,
        # ordenar en memoria evita otra query por cargo).
        last_app = max(charge.applications, key=lambda a: a.id, default=None)
        last_payment_id = last_app.payment_id if last_app else None

        result.append({
            "id":           charge.id,
            "charge_id":    charge.id,
            "unit_id":      charge.unit_id,
            "unit_number":  unit.unit_number if unit else None,
            "owner_name":   owner.full_name if owner else None,
            "owner_id":     owner.id if owner else None,
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


def _resolve_payment_context(db: Session, payment, applications):
    owner = db.query(Owner).filter(Owner.id == payment.owner_id).first() if payment.owner_id else None
    unit = None
    property_obj = None

    if applications:
        first_charge = db.query(Charge).filter(Charge.id == applications[0].charge_id).first()
        unit = db.query(Unit).filter(Unit.id == first_charge.unit_id).first() if first_charge else None
        property_obj = db.query(Property).filter(Property.id == unit.property_id).first() if unit else None

        if not owner and unit:
            ownership = db.query(UnitOwner).filter(
                UnitOwner.unit_id == unit.id,
                UnitOwner.is_active == True
            ).first()
            owner = db.query(Owner).filter(Owner.id == ownership.owner_id).first() if ownership else None

    if not unit and owner:
        ownership = db.query(UnitOwner).filter(
            UnitOwner.owner_id == owner.id,
            UnitOwner.is_active == True
        ).first()
        unit = ownership.unit if ownership else None
        property_obj = unit.property if unit else None

    return owner, unit, property_obj

# nueva función 10b — Detalle completo de un pago para factura (corrección de bugs en owner/unit/property)
def get_payment_detail_full(db, payment_id: int):
    """
    Obtiene detalle completo de un pago para factura.
    FIX: Incluye owner, unit, property y receipt_number correctamente.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    # Factura vinculada
    invoice = db.query(Invoice).filter(Invoice.payment_id == payment_id).first()

    # Aplicaciones — ordenadas por date_created del cargo (nunca due_date)
    applications = (
        db.query(PaymentApplication)
        .join(Charge, Charge.id == PaymentApplication.charge_id)
        .filter(PaymentApplication.payment_id == payment_id)
        .order_by(Charge.date_created)
        .all()
    )

    # ── Resolver propietario ───────────────────────────────
    owner = db.query(Owner).filter(Owner.id == payment.owner_id).first() if payment.owner_id else None

    # ── Resolver unidad desde las aplicaciones ─────────────
    unit         = None
    property_obj = None

    if applications:
        first_charge = db.query(Charge).filter(Charge.id == applications[0].charge_id).first()
        unit = db.query(Unit).filter(Unit.id == first_charge.unit_id).first() if first_charge else None
        if unit:
            property_obj = db.query(Property).filter(Property.id == unit.property_id).first()

        # Si aun no tenemos owner, buscarlo desde la unidad
        if not owner and unit:
            ownership = db.query(UnitOwner).filter(
                UnitOwner.unit_id == unit.id,
                UnitOwner.is_active == True
            ).first()
            if ownership:
                owner = db.query(Owner).filter(Owner.id == ownership.owner_id).first()

    # ── Si todavía no tenemos unidad, buscarla desde el owner ─
    if not unit and owner:
        ownership = db.query(UnitOwner).filter(
            UnitOwner.owner_id == owner.id,
            UnitOwner.is_active == True
        ).first()
        if ownership:
            unit = db.query(Unit).filter(Unit.id == ownership.unit_id).first()
            if unit:
                property_obj = db.query(Property).filter(Property.id == unit.property_id).first()

    apps_detail = []
    subtotal = Decimal("0.00")
    recargo  = Decimal("0.00")
    for app in applications:
        charge = db.query(Charge).filter(Charge.id == app.charge_id).first()
        charge_balance = get_charge_balance(db, app.charge_id) if charge else None
        is_recargo = bool(charge and charge.related_charge_id is not None)
        applied = Decimal(str(app.applied_amount))
        if is_recargo:
            recargo += applied
        else:
            subtotal += applied
        apps_detail.append({
            "charge_id": app.charge_id,
            "description": charge.description if charge else f"Cargo #{app.charge_id}",
            "applied_amount": float(app.applied_amount),
            "is_recargo": is_recargo,
            # Monto total del cargo y su saldo actual (vivo, refleja también
            # pagos posteriores a este) — para la columna "Cargo"/"Saldo"
            # del recibo estilo banco.
            "charge_amount":  float(charge.amount) if charge else None,
            "charge_balance": float(charge_balance["balance"]) if charge_balance else None,
        })

    return {
        "payment_id":            payment.id,
        "payment_date":          str(payment.payment_date),
        "amount":                float(payment.amount),
        "subtotal":              float(subtotal),
        "recargo":               float(recargo),
        "total":                 float(subtotal + recargo),
        "reference":             payment.reference,
        "invoice_number":        invoice.invoice_number if invoice else None,
        "fiscal_invoice_number": invoice.fiscal_invoice_number if invoice else None,
        # Número de recibo físico (campo opcional en Payment)
        "receipt_number":        getattr(payment, 'receipt_number', None),
        # Datos del propietario — antes podían venir vacíos (BUG corregido)
        "owner_name":            owner.full_name if owner else "—",
        "owner_id":              owner.id if owner else None,
        # Datos de la unidad — antes podían venir vacíos (BUG corregido)
        "unit_number":           unit.unit_number if unit else "—",
        "property_name":         property_obj.name if property_obj else "—",
        "property_address":      property_obj.address if property_obj else "—",
        "property_phone":        getattr(property_obj, "phone", None) if property_obj else None,
        "property_email":        getattr(property_obj, "email", None) if property_obj else None,
        "property_website":      getattr(property_obj, "website", None) if property_obj else None,
        "applications":          apps_detail,
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

    applications = db.query(PaymentApplication).filter(
        PaymentApplication.payment_id == payment.id
    ).all()
    if not applications:
        raise HTTPException(status_code=400, detail="El pago no tiene cargos aplicados")

    owner, unit, property_obj = _resolve_payment_context(db, payment, applications)

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
# Wrapper — Estado de cuenta detallado de un propietario (documento imprimible)
# Toma la unidad activa del propietario y delega todo el cálculo a
# get_unit_account_statement(include_history=True); no recalcula nada.
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

    stmt = get_unit_account_statement(db, ownership.unit_id, include_history=True)

    return {
        "property_name":    stmt["property_name"],
        "property_address": stmt["property_address"],
        "owner_name":       stmt["owner_name"],
        "unit_number":      stmt["unit_number"],
        "statement":        stmt["charges"],
    }


# ──────────────────────────────────────────────
# Función 17 — Aplicación FIFO de un pago sobre los cargos pendientes de una unidad
# ──────────────────────────────────────────────
def apply_payment_fifo(db: Session, unit_id: int, owner_id: int, amount: float):
    amount_dec = _to_dec(amount)
    if amount_dec <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Propietario no encontrado")

    payment = Payment(owner_id=owner_id, payment_date=date.today(), amount=amount_dec)
    db.add(payment)
    db.flush()

    charges = db.query(Charge).filter(Charge.unit_id == unit_id).order_by(Charge.due_date.asc()).all()

    remaining = amount_dec
    applications_made = []

    for charge in charges:
        if remaining <= Decimal("0.00"):
            break

        charge_balance = _to_dec(charge.balance)
        if charge_balance <= Decimal("0.00"):
            continue

        apply_amount = min(remaining, charge_balance)
        application = apply_payment_to_charge(db, payment.id, charge.id, float(apply_amount))
        applications_made.append(application)
        remaining -= apply_amount

    # Sobrante tras cubrir todos los cargos pendientes: se guarda como saldo a favor.
    if remaining > Decimal("0.00"):
        db.add(OwnerCredit(
            owner_id=owner_id,
            source_payment_id=payment.id,
            amount=remaining,
            remaining_amount=remaining,
        ))
        db.commit()

    db.refresh(payment)

    return {
        "payment": payment,
        "applications_count": len(applications_made),
        "credit_generated": float(remaining) if remaining > Decimal("0.00") else 0.0,
    }


# ──────────────────────────────────────────────
# Función 15 — Generar cuotas mensuales fijas por unidad
# ──────────────────────────────────────────────
def generate_monthly_charges(
    db: Session,
    property_id: int | None = None,
    month: int | None = None,
    year: int | None = None,
):
    today = date.today()
    month = month or today.month
    year = year or today.year

    query = db.query(Unit).filter(Unit.monthly_fee.isnot(None))
    if property_id is not None:
        query = query.filter(Unit.property_id == property_id)
    units = query.all()

    description = f"Cuota mensual {month:02d}/{year}"
    due_date = date(year, month, 5)

    created_count = 0
    skipped_count = 0
    created_charges = []

    for unit in units:
        existing = db.query(Charge).filter(
            Charge.unit_id == unit.id,
            Charge.description == description,
        ).first()

        if existing:
            skipped_count += 1
            continue

        charge = Charge(
            unit_id=unit.id,
            description=description,
            amount=_to_dec(unit.monthly_fee),
            status="PENDIENTE",
            date_created=today,
            due_date=due_date,
        )
        db.add(charge)
        db.flush()
        created_charges.append(charge)
        created_count += 1

        # Aplicación automática de saldo a favor del propietario activo (más antiguo primero).
        active_ownership = db.query(UnitOwner).filter(
            UnitOwner.unit_id == unit.id,
            UnitOwner.is_active == True,
        ).first()

        if active_ownership:
            available_credits = db.query(OwnerCredit).filter(
                OwnerCredit.owner_id == active_ownership.owner_id,
                OwnerCredit.remaining_amount > 0,
            ).order_by(OwnerCredit.created_at.asc()).all()

            remaining_charge_amount = _to_dec(charge.amount)
            for credit in available_credits:
                if remaining_charge_amount <= Decimal("0.00"):
                    break
                apply_amount = min(_to_dec(credit.remaining_amount), remaining_charge_amount)
                if apply_amount <= Decimal("0.00"):
                    continue
                apply_credit_to_charge(db, credit.id, charge.id, float(apply_amount))
                remaining_charge_amount -= apply_amount

    db.commit()

    return {
        "created": created_count,
        "skipped": skipped_count,
        "month": month,
        "year": year,
        "charges": created_charges,
    }


# ──────────────────────────────────────────────
# Función 16 — Aplicar mora manual sobre un cargo vencido
# ──────────────────────────────────────────────
def apply_late_fee(db: Session, charge_id: int, amount: float):
    original = db.query(Charge).filter(Charge.id == charge_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")

    amount_dec = _to_dec(amount)
    if amount_dec <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="El monto de la mora debe ser mayor a 0")

    if original.due_date >= date.today():
        raise HTTPException(status_code=400, detail="No se puede aplicar mora: el cargo aún no está vencido")

    if original.balance <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="No se puede aplicar mora: el cargo ya está pagado en su totalidad")

    late_fee_charge = Charge(
        unit_id=original.unit_id,
        description=f"Mora - cargo #{charge_id}",
        amount=amount_dec,
        status="PENDIENTE",
        date_created=date.today(),
        due_date=date.today(),
        related_charge_id=charge_id,
    )
    db.add(late_fee_charge)
    db.commit()
    db.refresh(late_fee_charge)
    return late_fee_charge


# ──────────────────────────────────────────────
# Función 14 — Total pendiente por propiedad
# ──────────────────────────────────────────────
def property_accounts_receivable(db: Session, property_id: int):
    # Anti N+1 (mismo patrón que get_property_financial_summary).
    charges = (
        db.query(Charge)
        .join(Unit, Charge.unit_id == Unit.id)
        .filter(Unit.property_id == property_id)
        .options(
            selectinload(Charge.applications),
            selectinload(Charge.credit_applications),
        )
        .all()
    )
    total = Decimal("0.00")
    for charge in charges:
        bd = _charge_balance_from_relations(charge)
        total += bd["balance"]
    return {"property_id": property_id, "total_pending": float(total)}
