"""
Script Utiles/reset_v2.py

Reset de V2: vacía cargos/pagos/aplicaciones (Gas incluido) para pasar del
modelo antiguo (cuadrar todo contra el Excel histórico) a un ledger simple.
Property/Owner/Unit/UnitOwner/User NO se tocan.

Nadie re-migra nada automáticamente después de este script: al terminar con
--commit, "charges" y "payments" quedan en 0 filas a propósito. Los datos se
vuelven a cargar a mano, vía app/static/imports.html (pestañas Cargos/Pagos)
o "Script Utiles/importar_plantillas_simple.py" cuando se decida usarlo.

Pasos (siempre, incluso en dry-run):
  1. Backup del archivo de base de datos.
  2. Agregar Charge.concept si la columna todavía no existe (ALTER TABLE).
Luego, solo con --commit:
  3. Borrar en orden (por las FK): CreditApplication -> PaymentApplication ->
     Invoice -> OwnerCredit -> Payment -> Charge.

USO:
    python "Script Utiles/reset_v2.py"              # dry-run: backup + ALTER, sin borrar nada
    python "Script Utiles/reset_v2.py" --commit      # corre el borrado de verdad
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import app.main  # noqa: F401,E402  (registra todos los modelos)
from app.database import SessionLocal, engine  # noqa: E402

TABLES_IN_DELETE_ORDER = [
    "credit_applications",
    "payment_applications",
    "invoices",
    "owner_credits",
    "payments",
    "charges",
]


def backup_database():
    """Copia el archivo de base de datos antes de tocar nada. Si DATABASE_URL
    no apunta a SQLite (ej. Postgres en producción), no hay archivo que
    copiar -- se aborta en vez de proceder sin respaldo real."""
    if engine.dialect.name != "sqlite":
        print(f"[ERROR] DATABASE_URL apunta a '{engine.dialect.name}', no a SQLite.")
        print("Este script solo sabe respaldar por copia de archivo. Contra Postgres,")
        print("respalda manualmente (ej. pg_dump) antes de correr --commit; este script")
        print("se detiene para no proceder sin un backup real.")
        sys.exit(1)

    db_path = engine.url.database
    if not db_path or not os.path.exists(db_path):
        print(f"[ERROR] No se encontró el archivo de base de datos en '{db_path}'")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak_{timestamp}_pre_reset_v2"
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Backup creado: {backup_path}")
    return backup_path


def add_concept_column():
    """Charge.concept es nueva -- se agrega con ALTER TABLE porque el
    proyecto no usa Alembic. Sintaxis compatible con SQLite y Postgres.
    Ignora el error si la columna ya existe (por si el script se corre
    más de una vez)."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE charges ADD COLUMN concept VARCHAR"))
            conn.commit()
        print("[OK] Columna 'concept' agregada a charges.")
    except Exception as e:
        print(f"[INFO] No se agregó la columna 'concept' (probablemente ya existe): {e}")


def run_reset(commit: bool):
    backup_database()
    add_concept_column()

    from sqlalchemy import text
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("RESET V2 — vaciando charges/payments (Gas incluido)")
        print("=" * 60)

        for table in TABLES_IN_DELETE_ORDER:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:<24} -> {count} filas {'a borrar' if not commit else ''}")

        if commit:
            print()
            for table in TABLES_IN_DELETE_ORDER:
                result = db.execute(text(f"DELETE FROM {table}"))
                print(f"  {table:<24} -> {result.rowcount} filas borradas")
            db.commit()
            print("\n[OK] COMMIT realizado. 'charges' y 'payments' quedan en 0 filas.")
            print("Properties/Owners/Units/UnitOwners/Users NO se tocaron.")
            print("Nadie re-migró nada automáticamente. Para volver a cargar datos:")
            print('  - app/static/imports.html (pestañas Cargos / Pagos)')
            print('  - o "Script Utiles/importar_plantillas_simple.py" (no se corrió aquí)')
        else:
            db.rollback()
            print("\n[DRY-RUN] No se borró nada. Corre con --commit para confirmar.")

    except Exception:
        db.rollback()
        print("\n[ERROR] Se hizo ROLLBACK, no se borró nada.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset de V2 -- vacía charges/payments para pasar al ledger simple")
    parser.add_argument("--commit", action="store_true", help="Confirma el borrado (por defecto es dry-run)")
    args = parser.parse_args()

    run_reset(commit=args.commit)
