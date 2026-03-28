from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Charge(Base):
    __tablename__ = "charges"

    id = Column(Integer, primary_key=True, index=True)

    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)

    description = Column(String, nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    balance = Column(Numeric(10, 2), nullable=False)

    status = Column(String, default="PENDIENTE")

    date_created = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    unit = relationship("Unit", back_populates="charges")
    # ✅ CORREGIDO: back_populates coincide con PaymentApplication
    applications = relationship("PaymentApplication", back_populates="charge")