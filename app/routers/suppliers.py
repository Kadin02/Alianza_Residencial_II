"""
app/routers/suppliers.py  v2
Agrega:
  POST /suppliers/quotes/{quote_id}/upload-pdf  — subir PDF de cotización
  GET  /suppliers/quotes/{quote_id}/pdf          — descargar el PDF
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import date
import os, shutil, uuid

from app.database import get_db
from app.models.supplier import Supplier
from app.models.supplier_payment_quote import SupplierPayment, SupplierQuote

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

CATEGORIES = [
    "PLOMERÍA", "ELECTRICIDAD", "LIMPIEZA", "JARDINERÍA",
    "SEGURIDAD", "ELEVADORES", "PINTURA", "CONSTRUCCIÓN",
    "AIRE ACONDICIONADO", "FUMIGACIÓN", "OTROS"
]

PDF_DIR = "supplier_docs"
os.makedirs(PDF_DIR, exist_ok=True)

# ── Schemas ──────────────────────────────────
class SupplierCreate(BaseModel):
    name:         str
    category:     str
    ruc:          Optional[str] = None
    contact_name: Optional[str] = None
    phone:        Optional[str] = None
    email:        Optional[str] = None
    address:      Optional[str] = None
    notes:        Optional[str] = None

class PaymentCreate(BaseModel):
    description:  str
    amount:       float
    payment_date: date
    status:       str = "PAGADO"
    reference:    Optional[str] = None

class QuoteCreate(BaseModel):
    description:  str
    amount:       float
    quote_date:   date
    valid_until:  Optional[date] = None
    status:       str = "PENDIENTE"
    notes:        Optional[str] = None

# ── Proveedores CRUD ─────────────────────────
@router.get("/")
def list_suppliers(db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all()
    result = []
    for s in suppliers:
        total_paid    = db.query(func.sum(SupplierPayment.amount)).filter(
            SupplierPayment.supplier_id == s.id, SupplierPayment.status == "PAGADO"
        ).scalar() or 0
        total_pending = db.query(func.sum(SupplierPayment.amount)).filter(
            SupplierPayment.supplier_id == s.id, SupplierPayment.status == "PENDIENTE"
        ).scalar() or 0
        result.append({
            "id": s.id, "name": s.name, "category": s.category,
            "ruc": s.ruc, "contact_name": s.contact_name,
            "phone": s.phone, "email": s.email,
            "address": s.address, "notes": s.notes,
            "total_paid": float(total_paid),
            "total_pending": float(total_pending),
            "created_at": str(s.created_at),
        })
    return result

@router.get("/categories")
def get_categories():
    return CATEGORIES

@router.post("/")
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)):
    s = Supplier(**data.dict()); db.add(s); db.commit(); db.refresh(s)
    return s

@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, data: SupplierCreate, db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s: raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    for k, v in data.dict().items(): setattr(s, k, v)
    db.commit(); db.refresh(s); return s

@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s: raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    s.is_active = False; db.commit()
    return {"message": "Proveedor eliminado"}

# ── Detalle completo de un proveedor ─────────
@router.get("/{supplier_id}/detail")
def supplier_detail(supplier_id: int, db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_active == True).first()
    if not s: raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    payments = db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == supplier_id
    ).order_by(SupplierPayment.payment_date.desc()).all()

    quotes = db.query(SupplierQuote).filter(
        SupplierQuote.supplier_id == supplier_id
    ).order_by(SupplierQuote.quote_date.desc()).all()

    total_paid    = sum(float(p.amount) for p in payments if p.status == "PAGADO")
    total_pending = sum(float(p.amount) for p in payments if p.status == "PENDIENTE")

    return {
        "id": s.id, "name": s.name, "category": s.category,
        "ruc": s.ruc, "contact_name": s.contact_name,
        "phone": s.phone, "email": s.email,
        "address": s.address, "notes": s.notes,
        "total_paid": total_paid, "total_pending": total_pending,
        "payments": [{
            "id": p.id, "description": p.description,
            "amount": float(p.amount), "payment_date": str(p.payment_date),
            "status": p.status, "reference": p.reference,
        } for p in payments],
        "quotes": [{
            "id": q.id, "description": q.description,
            "amount": float(q.amount), "quote_date": str(q.quote_date),
            "valid_until": str(q.valid_until) if q.valid_until else None,
            "status": q.status, "notes": q.notes,
            "pdf_path": q.pdf_path if hasattr(q, 'pdf_path') else None,
        } for q in quotes],
    }

# ── Pagos ─────────────────────────────────────
@router.get("/{supplier_id}/payments")
def list_payments(supplier_id: int, db: Session = Depends(get_db)):
    return db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == supplier_id
    ).order_by(SupplierPayment.payment_date.desc()).all()

@router.post("/{supplier_id}/payments")
def create_payment(supplier_id: int, data: PaymentCreate, db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s: raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    p = SupplierPayment(supplier_id=supplier_id, **data.dict())
    db.add(p); db.commit(); db.refresh(p); return p

@router.put("/payments/{payment_id}")
def update_payment(payment_id: int, data: PaymentCreate, db: Session = Depends(get_db)):
    p = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not p: raise HTTPException(status_code=404, detail="Pago no encontrado")
    for k, v in data.dict().items(): setattr(p, k, v)
    db.commit(); db.refresh(p); return p

@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    p = db.query(SupplierPayment).filter(SupplierPayment.id == payment_id).first()
    if not p: raise HTTPException(status_code=404, detail="Pago no encontrado")
    db.delete(p); db.commit()
    return {"message": "Pago eliminado"}

# ── Cotizaciones ──────────────────────────────
@router.get("/{supplier_id}/quotes")
def list_quotes(supplier_id: int, db: Session = Depends(get_db)):
    quotes = db.query(SupplierQuote).filter(
        SupplierQuote.supplier_id == supplier_id
    ).order_by(SupplierQuote.quote_date.desc()).all()
    result = []
    for q in quotes:
        result.append({
            "id": q.id, "description": q.description,
            "amount": float(q.amount), "quote_date": str(q.quote_date),
            "valid_until": str(q.valid_until) if q.valid_until else None,
            "status": q.status, "notes": q.notes,
            "pdf_path": getattr(q, 'pdf_path', None),
        })
    return result

@router.post("/{supplier_id}/quotes")
def create_quote(supplier_id: int, data: QuoteCreate, db: Session = Depends(get_db)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s: raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    q = SupplierQuote(supplier_id=supplier_id, **data.dict())
    db.add(q); db.commit(); db.refresh(q); return q

@router.put("/quotes/{quote_id}")
def update_quote(quote_id: int, data: QuoteCreate, db: Session = Depends(get_db)):
    q = db.query(SupplierQuote).filter(SupplierQuote.id == quote_id).first()
    if not q: raise HTTPException(status_code=404, detail="Cotización no encontrada")
    for k, v in data.dict().items(): setattr(q, k, v)
    db.commit(); db.refresh(q); return q

@router.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int, db: Session = Depends(get_db)):
    q = db.query(SupplierQuote).filter(SupplierQuote.id == quote_id).first()
    if not q: raise HTTPException(status_code=404, detail="Cotización no encontrada")
    # Eliminar PDF si existe
    if getattr(q, 'pdf_path', None) and os.path.exists(q.pdf_path):
        os.remove(q.pdf_path)
    db.delete(q); db.commit()
    return {"message": "Cotización eliminada"}

# ── Upload PDF de cotización ──────────────────
@router.post("/quotes/{quote_id}/upload-pdf")
async def upload_quote_pdf(
    quote_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    q = db.query(SupplierQuote).filter(SupplierQuote.id == quote_id).first()
    if not q: raise HTTPException(status_code=404, detail="Cotización no encontrada")

    # Validar que sea PDF
    if not file.content_type == "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    # Eliminar PDF anterior si existe
    if getattr(q, 'pdf_path', None) and os.path.exists(q.pdf_path):
        os.remove(q.pdf_path)

    # Guardar nuevo PDF
    filename    = f"quote_{quote_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path   = os.path.join(PDF_DIR, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    q.pdf_path = file_path
    db.commit()

    return {"message": "PDF subido correctamente", "pdf_path": file_path}

# ── Descargar PDF de cotización ───────────────
@router.get("/quotes/{quote_id}/pdf")
def download_quote_pdf(quote_id: int, db: Session = Depends(get_db)):
    q = db.query(SupplierQuote).filter(SupplierQuote.id == quote_id).first()
    if not q: raise HTTPException(status_code=404, detail="Cotización no encontrada")

    pdf_path = getattr(q, 'pdf_path', None)
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF no encontrado")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"cotizacion_{quote_id}.pdf"
    )
