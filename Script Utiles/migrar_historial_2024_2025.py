"""
Script Utiles/migrar_historial_2024_2025.py

Migración histórica de datos 2024-2025 desde el Excel
"Organizacion_Migracion 2024-2025.xlsx" hacia la base de datos real,
ejecutada directamente contra los modelos SQLAlchemy (no vía API),
dentro de UNA sola transacción atómica.

Ver Observaciones.txt para las reglas de negocio completas.

USO:
    python "Script Utiles/migrar_historial_2024_2025.py"              # dry-run (no persiste nada)
    python "Script Utiles/migrar_historial_2024_2025.py" --commit     # corre y confirma (commit real)

Por defecto corre en modo dry-run: hace todo el trabajo dentro de la
transacción, imprime el reporte final, y siempre hace ROLLBACK al
terminar (con éxito o con error). Solo con --commit se guarda de verdad.

Nota sobre atomicidad: NO se usan las funciones apply_payment_to_charge /
apply_credit_to_charge de finance_service.py porque ambas hacen db.commit()
internamente después de cada aplicación individual, lo cual rompe la
garantía de "todo o nada" de este script. Se reimplementa aquí la misma
lógica de balance/estado (Decimal, FIFO, status PAGADO/PARCIAL/PENDIENTE).

Nota de rendimiento: todos los objetos se enlazan entre sí por relación de
SQLAlchemy (unit=unit_obj, owner=owner_obj, charge=charge_obj, ...) en vez
de por id numérico, y no se hace ningún db.flush() intermedio -- un solo
flush al final resuelve todos los INSERTs agrupados por tabla. Esto evita
miles de round-trips de red individuales (crítico contra una base de datos
remota como Postgres en Railway); el resultado final es idéntico a hacer
flush() fila por fila, solo cambia cómo se agrupan los INSERTs.
"""

import argparse
import calendar
import os
import sys
from datetime import date
from decimal import Decimal

import openpyxl

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import app.main  # noqa: F401,E402  (registra todos los modelos y crea tablas si faltan)
from app.database import SessionLocal
from app.models.property import Property
from app.models.owner import Owner
from app.models.unit import Unit
from app.models.unit_owner import UnitOwner
from app.models.charge import Charge
from app.models.payment import Payment
from app.models.payment_application import PaymentApplication
from app.models.owner_credit import OwnerCredit

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Organizacion_Migracion 2024-2025.xlsx")
PROPERTY_NAME = "PH Park View I"

# "Por definir" y "A001" ya NO se excluyen (Corrección 1): se crean como
# unidades/owners normales, pero NO reciben los 3 cargos anuales fijos del
# paso 4 (no son apartamentos reales ocupados).
NON_REAL_APTOS = {"Por definir", "A001"}


def month_bounds(year: int, month: int):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


CENT = Decimal("0.01")


def to_dec(value) -> Decimal:
    """Redondea a centavo (2 decimales). Corrección 1b: algunos cargos de
    Gas vienen del Excel con más de 2 decimales (prorrateos de factura),
    lo que dejaba remanentes de centésimas de centavo como PaymentApplication
    "fantasma" al aplicar FIFO. Redondear en el origen elimina esa causa raíz."""
    return Decimal(str(value)).quantize(CENT)


class Report:
    def __init__(self):
        self.owners_created = 0
        self.units_created = 0
        self.unit_owners_created = 0

        self.charges_gas = 0
        self.charges_mant = 0
        self.charges_ascensor = 0

        self.payments_gas = 0
        self.payments_mant = 0
        self.payments_ascensor = 0
        self.payments_abono = 0

        self.applied_gas = Decimal("0.00")
        self.applied_mant = Decimal("0.00")
        self.applied_ascensor = Decimal("0.00")
        self.applied_abono = Decimal("0.00")

        self.credit_gas = Decimal("0.00")
        self.credit_mant = Decimal("0.00")
        self.credit_ascensor = Decimal("0.00")
        self.credit_abono = Decimal("0.00")

        self.omitted = []  # list of dict(sheet, row, reason)

    def omit(self, sheet, row, reason):
        self.omitted.append({"sheet": sheet, "row": row, "reason": reason})

    def print_summary(self):
        print("\n" + "=" * 78)
        print("REPORTE DE MIGRACIÓN — Historial 2024-2025")
        print("=" * 78)

        print(f"\nOwners creados:        {self.owners_created}")
        print(f"Units creadas:         {self.units_created}")
        print(f"UnitOwner creados:     {self.unit_owners_created}")

        print(f"\nCharges creados:")
        print(f"  Gas:                 {self.charges_gas}")
        print(f"  Mantenimiento:       {self.charges_mant}")
        print(f"  Cuota Ascensor:      {self.charges_ascensor}")
        print(f"  TOTAL:               {self.charges_gas + self.charges_mant + self.charges_ascensor}")

        total_payments = (
            self.payments_gas + self.payments_mant + self.payments_ascensor + self.payments_abono
        )
        print(f"\nPayments creados:")
        print(f"  Gas:                 {self.payments_gas}")
        print(f"  Mantenimiento:       {self.payments_mant}")
        print(f"  Cuota Ascensor:      {self.payments_ascensor}")
        print(f"  Abono:               {self.payments_abono}")
        print(f"  TOTAL:               {total_payments}")

        total_applied = self.applied_gas + self.applied_mant + self.applied_ascensor + self.applied_abono
        total_credit = self.credit_gas + self.credit_mant + self.credit_ascensor + self.credit_abono

        print(f"\nAplicado a cargos (por origen del pago):")
        print(f"  Gas:                 ${self.applied_gas:.2f}")
        print(f"  Mantenimiento:       ${self.applied_mant:.2f}")
        print(f"  Cuota Ascensor:      ${self.applied_ascensor:.2f}")
        print(f"  Abono (cruzado):     ${self.applied_abono:.2f}")
        print(f"  TOTAL APLICADO:      ${total_applied:.2f}")

        print(f"\nConvertido en OwnerCredit (sobrante, por origen del pago):")
        print(f"  Gas:                 ${self.credit_gas:.2f}")
        print(f"  Mantenimiento:       ${self.credit_mant:.2f}")
        print(f"  Cuota Ascensor:      ${self.credit_ascensor:.2f}")
        print(f"  Abono:               ${self.credit_abono:.2f}")
        print(f"  TOTAL EN CRÉDITO:    ${total_credit:.2f}")

        print(f"\nFilas omitidas: {len(self.omitted)}")
        for o in self.omitted:
            print(f"  [{o['sheet']}] {o['row']} -> {o['reason']}")

        print("\n" + "=" * 78)


def read_sheet_rows(wb, sheet_name):
    """Lee las filas de datos de una hoja, descartando filas completamente
    vacías (Excel suele traer un rango usado más grande que los datos reales,
    lo que generaba cientos de "omitidas" fantasma en el reporte)."""
    ws = wb[sheet_name]
    rows = ws.iter_rows(min_row=2, values_only=True)
    return [r for r in rows if any(v is not None for v in r)]


def run_migration(commit: bool):
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    report = Report()
    db = SessionLocal()

    # unit / owner (objetos, no ids) por apartamento, y estructuras de FIFO
    # en memoria. Todo se enlaza por relación de SQLAlchemy y se deja sin
    # flush hasta el final -- los objetos son válidos como claves de dict
    # (identidad) igual que un id lo sería.
    unit_by_apto = {}
    owner_by_apto = {}
    remaining = {}          # charge (obj) -> Decimal restante
    gas_charges_by_unit = {}   # unit (obj) -> [charge (obj), ...] ordenados por due_date
    all_charges_by_unit = {}  # unit (obj) -> [charge (obj), ...] ordenados por due_date (Gas+Mant+Ascensor)
    annual_charge_id = {}   # (unit (obj), concepto, año) -> charge (obj)

    try:
        # ── PASO 1: Propietarios y Unidades ──────────────────────────
        prop = db.query(Property).filter(Property.name == PROPERTY_NAME).first()
        if not prop:
            prop = Property(
                name=PROPERTY_NAME,
                type="PH",
                address="PH Park View, Av. 17B Nte., Panamá, Provincia de Panamá, Panamá",
                max_units=51,
            )
            db.add(prop)
            db.flush()

        clientes_rows = read_sheet_rows(wb, "Clientes_Datos")
        clientes_incluidos = clientes_rows  # Corrección 1: ya no se excluye ninguna fila

        # Fecha más antigua por apartamento (para start_date), buscando en
        # las otras 3 hojas relevantes.
        earliest_date_by_apto = {}

        def track_earliest(apto, year, month):
            if apto is None or year is None or month is None:
                return
            d = date(int(year), int(month), 1)
            cur = earliest_date_by_apto.get(apto)
            if cur is None or d < cur:
                earliest_date_by_apto[apto] = d

        # Cargos_de_Gas y Pagos_de_Gas traen una columna "fecha" real entre
        # "mes" y "apartamento" (año, mes, fecha, apto, ...) -- el apto quedó
        # en el índice 3. Pagos_Varios también tiene "Fecha" ahora, entre
        # "mes" y "referencia" (año, mes, fecha, referencia, apto, ...) -- el
        # apto quedó en el índice 4.
        for r in read_sheet_rows(wb, "Cargos_de_Gas"):
            track_earliest(r[3], r[0], r[1])
        for r in read_sheet_rows(wb, "Pagos_de_Gas"):
            track_earliest(r[3], r[0], r[1])
        for r in read_sheet_rows(wb, "Pagos_Varios"):
            track_earliest(r[4], r[0], r[1])

        for row in clientes_incluidos:
            apto, propietario, celular, correo, _propiedad = row

            owner = Owner(
                full_name=propietario,
                identification=None,
                email=correo or None,
                phone=celular or None,
            )
            db.add(owner)
            report.owners_created += 1

            unit = Unit(
                property=prop,
                unit_number=apto,
            )
            db.add(unit)
            report.units_created += 1

            start_date = earliest_date_by_apto.get(apto, date(2024, 1, 1))
            unit_owner = UnitOwner(
                unit=unit,
                owner=owner,
                start_date=start_date,
                end_date=None,
                is_active=True,
            )
            db.add(unit_owner)
            report.unit_owners_created += 1

            unit_by_apto[apto] = unit
            owner_by_apto[apto] = owner
            gas_charges_by_unit[unit] = []
            all_charges_by_unit[unit] = []

        # ── PASO 2: Cargos de Gas ─────────────────────────────────────
        # El Excel ahora trae una columna "fecha" real (día 1 del mes de
        # facturación) entre "mes" y "apartamento" -- se usa tal cual en vez
        # de asumir el día 1 manualmente.
        for row in read_sheet_rows(wb, "Cargos_de_Gas"):
            anio, mes, fecha, apto, monto, _propiedad = row

            unit = unit_by_apto.get(apto)
            if unit is None:
                report.omit("Cargos_de_Gas", row, f"apartamento '{apto}' no encontrado en Clientes_Datos")
                continue

            fecha_creacion = fecha.date() if hasattr(fecha, "date") else date(int(anio), int(mes), 1)
            _, last = month_bounds(int(anio), int(mes))
            charge = Charge(
                unit=unit,
                description="Facturación de Gas",
                amount=to_dec(monto),
                status="PENDIENTE",
                date_created=fecha_creacion,
                due_date=last,
            )
            db.add(charge)
            report.charges_gas += 1

            remaining[charge] = to_dec(monto)
            gas_charges_by_unit[unit].append(charge)
            all_charges_by_unit[unit].append(charge)

        # Ordenar listas de cargos de gas por due_date ascendente
        for unit, charges_list in gas_charges_by_unit.items():
            charges_list.sort(key=lambda c: c.date_created)

        # ── PASO 3: Pagos de Gas (FIFO solo contra cargos de Gas) ─────
        # Usa la columna "fecha" real del Excel (fecha exacta del pago) en
        # vez de asumir el día 15 del mes.
        for row in read_sheet_rows(wb, "Pagos_de_Gas"):
            anio, mes, fecha, apto, monto, factura, _propiedad = row

            if anio is None or mes is None or fecha is None:
                report.omit("Pagos_de_Gas", row, "fila con año/mes/fecha vacíos (dato corrupto, no se puede construir fecha de pago)")
                continue

            unit = unit_by_apto.get(apto)
            owner = owner_by_apto.get(apto)
            if unit is None or owner is None:
                report.omit("Pagos_de_Gas", row, f"apartamento '{apto}' no encontrado en Clientes_Datos")
                continue

            fecha_pago = fecha.date() if hasattr(fecha, "date") else date(int(anio), int(mes), 15)
            payment = Payment(
                property=prop,
                owner=owner,
                payer_name=None,
                payment_date=fecha_pago,
                payment_method=None,
                reference=f"Factura {factura}",
                amount=to_dec(monto),
                total_amount=to_dec(monto),
                invoice_number=None,
                concept="Gas",
            )
            db.add(payment)
            report.payments_gas += 1

            remaining_amount = to_dec(monto)
            for charge in gas_charges_by_unit[unit]:
                if remaining_amount <= Decimal("0.00"):
                    break
                charge_remaining = remaining[charge]
                if charge_remaining <= Decimal("0.00"):
                    continue

                apply_amount = min(remaining_amount, charge_remaining)

                pa = PaymentApplication(
                    payment=payment,
                    charge=charge,
                    applied_amount=apply_amount,
                )
                db.add(pa)

                remaining[charge] = charge_remaining - apply_amount
                remaining_amount -= apply_amount
                report.applied_gas += apply_amount

                charge.status = "PAGADO" if remaining[charge] <= Decimal("0.00") else "PARCIAL"

            if remaining_amount > Decimal("0.00"):
                credit = OwnerCredit(
                    owner=owner,
                    source_payment=payment,
                    amount=remaining_amount,
                    remaining_amount=remaining_amount,
                )
                db.add(credit)
                report.credit_gas += remaining_amount

        # ── PASO 4: Cargos anuales fijos (Mantenimiento / Ascensor) ───
        # Los montos ahora vienen de la hoja "Cargos_Fijos_Atrasados" del Excel
        # (año, concepto, monto_anual, propiedad) en vez de estar hardcodeados
        # en el script -- así el usuario puede ajustar montos/años futuros
        # editando el Excel, sin tocar código.
        # match_concepto = texto EXACTO usado en la columna "concepto" de
        # Pagos_Varios, para poder emparejar en el paso 5. display_desc = texto
        # usado en Charge.description.
        annual_defs = []
        for row in read_sheet_rows(wb, "Cargos_Fijos_Atrasados"):
            anio, concepto, monto_anual, _propiedad = row
            if anio is None or concepto is None or monto_anual is None:
                continue
            anio = int(anio)
            if concepto.strip() == "Mantenimiento":
                match_concepto, display_desc = "Mantenimiento", "Mantenimiento"
            elif "Ascensor" in concepto:
                # La hoja usa "Cuota Ascensor"; Pagos_Varios usa "Cuota de Ascensor".
                match_concepto, display_desc = "Cuota de Ascensor", "Cuota Ascensor"
            else:
                report.omit("Cargos_Fijos_Atrasados", row, f"concepto '{concepto}' no reconocido")
                continue
            annual_defs.append((
                match_concepto, display_desc, anio, to_dec(monto_anual),
                date(anio, 1, 1), date(anio, 12, 31),
            ))

        for apto, unit in unit_by_apto.items():
            if apto in NON_REAL_APTOS:
                continue  # Corrección 1: "Por definir"/"A001" no reciben cargos anuales fijos
            for match_concepto, display_desc, anio, monto, d_created, d_due in annual_defs:
                charge = Charge(
                    unit=unit,
                    description=f"{display_desc} {anio}",
                    amount=monto,
                    status="PENDIENTE",
                    date_created=d_created,
                    due_date=d_due,
                )
                db.add(charge)

                if match_concepto == "Mantenimiento":
                    report.charges_mant += 1
                else:
                    report.charges_ascensor += 1

                remaining[charge] = monto
                annual_charge_id[(unit, match_concepto, anio)] = charge
                all_charges_by_unit[unit].append(charge)

        # Reordenar listas completas por unidad (Gas + anuales) por due_date
        for unit, charges_list in all_charges_by_unit.items():
            charges_list.sort(key=lambda c: c.date_created)

        # ── PASO 5: Pagos_Varios — Mantenimiento y Cuota de Ascensor ──
        # La hoja ahora trae "Fecha" real entre "mes" y "referencia".
        for row in read_sheet_rows(wb, "Pagos_Varios"):
            anio, mes, fecha, referencia, apto, monto_pagado, concepto, _propiedad = row

            if concepto not in ("Mantenimiento", "Cuota de Ascensor"):
                continue  # Abono se procesa en el paso 6

            unit = unit_by_apto.get(apto)
            owner = owner_by_apto.get(apto)
            if unit is None or owner is None:
                report.omit("Pagos_Varios", row, f"apartamento '{apto}' no encontrado en Clientes_Datos")
                continue

            # Corrección 1a: si no hay ningún cargo válido contra el cual
            # aplicar (ej. "Por definir"/"A001", que no reciben cargos
            # anuales fijos), el pago SIEMPRE se crea igual -- charge
            # queda en None y el monto completo se va a OwnerCredit más
            # abajo. Ya NO se omite el pago por esta razón; "omitir" solo
            # aplica cuando el apartamento no existe en absoluto (arriba).
            charge = None
            if concepto == "Cuota de Ascensor":
                # Corrección 4: solo existe el charge de 2025 -- se ignora el
                # año de la fila (aplica igual si dice 2025 o 2026).
                charge = annual_charge_id.get((unit, "Cuota de Ascensor", 2025))
            else:
                # Mantenimiento — Corrección 3: sigue exigiendo mismo año exacto.
                charge = annual_charge_id.get((unit, "Mantenimiento", int(anio)))
                if charge is None and int(anio) >= 2026:
                    # Año sin charge fijo: crear uno nuevo por esta fila,
                    # monto exacto del pago, y se aplicará completo abajo.
                    first, last = month_bounds(int(anio), int(mes))
                    new_charge = Charge(
                        unit=unit,
                        description=f"Mantenimiento {int(anio)}",
                        amount=to_dec(monto_pagado),
                        status="PENDIENTE",
                        date_created=first,
                        due_date=last,
                    )
                    db.add(new_charge)
                    report.charges_mant += 1
                    remaining[new_charge] = to_dec(monto_pagado)
                    all_charges_by_unit[unit].append(new_charge)
                    charge = new_charge

            fecha_pago = fecha.date() if hasattr(fecha, "date") else date(int(anio), int(mes), 15)
            payment = Payment(
                property=prop,
                owner=owner,
                payer_name=None,
                payment_date=fecha_pago,
                payment_method=None,
                reference=f"Factura {referencia}",
                amount=to_dec(monto_pagado),
                total_amount=to_dec(monto_pagado),
                invoice_number=None,
                concept=concepto,
            )
            db.add(payment)

            if concepto == "Mantenimiento":
                report.payments_mant += 1
            else:
                report.payments_ascensor += 1

            monto_dec = to_dec(monto_pagado)
            charge_remaining = remaining[charge] if charge is not None else Decimal("0.00")
            apply_amount = min(monto_dec, charge_remaining) if charge is not None else Decimal("0.00")

            if apply_amount > Decimal("0.00"):
                pa = PaymentApplication(
                    payment=payment,
                    charge=charge,
                    applied_amount=apply_amount,
                )
                db.add(pa)
                remaining[charge] = charge_remaining - apply_amount

                charge.status = "PAGADO" if remaining[charge] <= Decimal("0.00") else "PARCIAL"

                if concepto == "Mantenimiento":
                    report.applied_mant += apply_amount
                else:
                    report.applied_ascensor += apply_amount

            leftover = monto_dec - apply_amount
            if leftover > Decimal("0.00"):
                credit = OwnerCredit(
                    owner=owner,
                    source_payment=payment,
                    amount=leftover,
                    remaining_amount=leftover,
                )
                db.add(credit)
                if concepto == "Mantenimiento":
                    report.credit_mant += leftover
                else:
                    report.credit_ascensor += leftover

        # Re-ordenar (el paso 5 pudo agregar charges nuevos de Mantenimiento >=2026)
        for unit, charges_list in all_charges_by_unit.items():
            charges_list.sort(key=lambda c: c.date_created)

        # ── PASO 6: Pagos_Varios — Abono (FIFO cruzando todos los conceptos) ──
        for row in read_sheet_rows(wb, "Pagos_Varios"):
            anio, mes, fecha, referencia, apto, monto_pagado, concepto, _propiedad = row

            if concepto != "Abono":
                continue

            unit = unit_by_apto.get(apto)
            owner = owner_by_apto.get(apto)
            if unit is None or owner is None:
                report.omit("Pagos_Varios", row, f"apartamento '{apto}' no encontrado en Clientes_Datos (Abono)")
                continue

            fecha_pago = fecha.date() if hasattr(fecha, "date") else date(int(anio), int(mes), 15)
            payment = Payment(
                property=prop,
                owner=owner,
                payer_name=None,
                payment_date=fecha_pago,
                payment_method=None,
                reference=f"Abono - Factura {referencia}",
                amount=to_dec(monto_pagado),
                total_amount=to_dec(monto_pagado),
                invoice_number=None,
                concept="Abono",
            )
            db.add(payment)
            report.payments_abono += 1

            remaining_amount = to_dec(monto_pagado)
            for charge in all_charges_by_unit[unit]:
                if remaining_amount <= Decimal("0.00"):
                    break
                charge_remaining = remaining[charge]
                if charge_remaining <= Decimal("0.00"):
                    continue

                apply_amount = min(remaining_amount, charge_remaining)

                pa = PaymentApplication(
                    payment=payment,
                    charge=charge,
                    applied_amount=apply_amount,
                )
                db.add(pa)

                remaining[charge] = charge_remaining - apply_amount
                remaining_amount -= apply_amount
                report.applied_abono += apply_amount

                charge.status = "PAGADO" if remaining[charge] <= Decimal("0.00") else "PARCIAL"

            if remaining_amount > Decimal("0.00"):
                credit = OwnerCredit(
                    owner=owner,
                    source_payment=payment,
                    amount=remaining_amount,
                    remaining_amount=remaining_amount,
                )
                db.add(credit)
                report.credit_abono += remaining_amount

        # ── PASO 7: flush único + Reporte ───────────────────────────────
        # Un solo flush resuelve TODOS los INSERTs pendientes, agrupados por
        # tabla (SQLAlchemy 2.0 hace INSERT multi-fila por lote) -- esto
        # reemplaza los miles de flush() individuales de antes.
        db.flush()
        report.print_summary()

        if commit:
            db.commit()
            print("\n[OK] COMMIT realizado - los datos quedaron guardados en la base de datos real.")
        else:
            db.rollback()
            print("\n[DRY-RUN] Se hizo ROLLBACK, no se guardo nada. Corre con --commit para confirmar.")

    except Exception:
        db.rollback()
        print("\n[ERROR] Se hizo ROLLBACK completo, no quedo nada a medias.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migración histórica 2024-2025")
    parser.add_argument("--commit", action="store_true", help="Confirma los cambios (por defecto es dry-run)")
    args = parser.parse_args()

    run_migration(commit=args.commit)
