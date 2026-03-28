from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class Supplier(Base):
    __tablename__ = "suppliers"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String, nullable=False)
    category       = Column(String, nullable=False)   # PLOMERIA, ELECTRICIDAD, etc.
    ruc            = Column(String, nullable=True)
    contact_name   = Column(String, nullable=True)
    phone          = Column(String, nullable=True)
    email          = Column(String, nullable=True)
    address        = Column(String, nullable=True)
    notes          = Column(String, nullable=True)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    payments       = relationship("SupplierPayment",  back_populates="supplier", cascade="all, delete-orphan")
    quotes         = relationship("SupplierQuote",    back_populates="supplier", cascade="all, delete-orphan")
