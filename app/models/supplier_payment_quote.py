"""
app/models/supplier_payment_quote.py  v2
Agrega el campo pdf_path a SupplierQuote para guardar la ruta del PDF adjunto.
"""

from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id            = Column(Integer, primary_key=True, index=True)
    supplier_id   = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    description   = Column(String,  nullable=False)
    amount        = Column(Numeric(10, 2), nullable=False)
    payment_date  = Column(Date,    nullable=False)
    status        = Column(String,  default="PAGADO")
    reference     = Column(String,  nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    supplier      = relationship("Supplier", back_populates="payments")


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"

    id            = Column(Integer, primary_key=True, index=True)
    supplier_id   = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    description   = Column(String,  nullable=False)
    amount        = Column(Numeric(10, 2), nullable=False)
    quote_date    = Column(Date,    nullable=False)
    valid_until   = Column(Date,    nullable=True)
    status        = Column(String,  default="PENDIENTE")
    notes         = Column(String,  nullable=True)
    pdf_path      = Column(String,  nullable=True)   # ← NUEVO: ruta al PDF adjunto
    created_at    = Column(DateTime, default=datetime.utcnow)

    supplier      = relationship("Supplier", back_populates="quotes")
