from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    invoice_number = Column(String, unique=True, nullable=False)       # interno sistema
    fiscal_invoice_number = Column(String, nullable=True)              # manual facturero físico

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)

    pdf_path = Column(String, nullable=True)

    # ✅ CORREGIDO: cambiado de backref="invoice" a back_populates="invoice"
    # para que no entre en conflicto con la relación definida en Payment
    payment = relationship("Payment", back_populates="invoice")

    created_at = Column(DateTime, default=datetime.utcnow)
