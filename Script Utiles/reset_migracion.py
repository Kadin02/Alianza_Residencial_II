"""
Script Utiles/reset_migracion.py

Vacía las tablas pobladas por migrar_historial_2024_2025.py (owners, units,
unit_owners, charges, payments, payment_applications, owner_credits,
credit_applications, invoices) para poder volver a correr esa migración
desde cero, sin duplicar datos.

NO borra "properties" (la propiedad "PH Park View I" se reutiliza por nombre
si ya existe). Si de verdad quieres partir 100% de cero, corre con --with-properties.

USO:
    python "Script Utiles/reset_migracion.py"                    # pide confirmación
    python "Script Utiles/reset_migracion.py" --yes              # sin confirmación
    python "Script Utiles/reset_migracion.py" --yes --with-properties
"""

import argparse
import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import app.main  # noqa: F401,E402  (registra todos los modelos)
from app.database import SessionLocal  # noqa: E402

# Orden de borrado: hijos antes que padres, para respetar las foreign keys.
TABLES_IN_DELETE_ORDER = [
    "credit_applications",
    "payment_applications",
    "invoices",
    "owner_credits",
    "payments",
    "charges",
    "unit_owners",
    "units",
    "owners",
]


def run_reset(with_properties: bool):
    tables = TABLES_IN_DELETE_ORDER + (["properties"] if with_properties else [])

    db = SessionLocal()
    try:
        from sqlalchemy import text

        print("\n" + "=" * 60)
        print("RESET DE MIGRACIÓN — borrando tablas")
        print("=" * 60)
        for table in tables:
            result = db.execute(text(f"DELETE FROM {table}"))
            print(f"  {table:<24} -> {result.rowcount} filas borradas")
        db.commit()
        print("\n[OK] COMMIT realizado. Tablas vacías.")
        if not with_properties:
            print("Nota: 'properties' NO se tocó (usa --with-properties para incluirla).")
        print("\nAhora puedes correr:")
        print('  python "Script Utiles/migrar_historial_2024_2025.py" --commit\n')
    except Exception:
        db.rollback()
        print("\n[ERROR] Se hizo ROLLBACK, no se borró nada.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset de datos migrados (owners/units/charges/payments/...)")
    parser.add_argument("--yes", action="store_true", help="No pedir confirmación interactiva")
    parser.add_argument("--with-properties", action="store_true", help="También borra la tabla properties")
    args = parser.parse_args()

    if not args.yes:
        tablas = ", ".join(TABLES_IN_DELETE_ORDER + (["properties"] if args.with_properties else []))
        resp = input(
            f"Esto borrará TODOS los datos de: {tablas}\n"
            f"Esta acción es directa sobre la BD real y no se puede deshacer. ¿Continuar? (escribe 'si' para confirmar): "
        )
        if resp.strip().lower() not in ("si", "sí", "yes"):
            print("Cancelado. No se borró nada.")
            sys.exit(0)

    run_reset(with_properties=args.with_properties)
