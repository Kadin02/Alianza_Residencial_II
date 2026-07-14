from sqlalchemy import Column, Integer, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class CreditApplication(Base):
    """Registro equivalente a PaymentApplication, pero para saldo a favor (OwnerCredit) aplicado a un cargo."""
    __tablename__ = "credit_applications"

    id = Column(Integer, primary_key=True, index=True)

    credit_id = Column(Integer, ForeignKey("owner_credits.id"), nullable=False)
    charge_id = Column(Integer, ForeignKey("charges.id"), nullable=False)

    applied_amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    credit = relationship("OwnerCredit")
    charge = relationship("Charge", back_populates="credit_applications")
