from sqlalchemy import Column, Integer, ForeignKey, Float, Numeric
from sqlalchemy.orm import relationship
from app.database import Base


class PaymentApplication(Base):
    __tablename__ = "payment_applications"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    charge_id = Column(Integer, ForeignKey("charges.id"), nullable=False)

    applied_amount = Column(Numeric(10, 2), nullable=False)  

    # ✅ CORREGIDO: Usar back_populates en lugar de backref duplicado
    payment = relationship("Payment", back_populates="applications")
    charge = relationship("Charge", back_populates="applications")