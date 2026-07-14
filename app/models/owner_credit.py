from sqlalchemy import Column, Integer, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class OwnerCredit(Base):
    __tablename__ = "owner_credits"

    id = Column(Integer, primary_key=True, index=True)

    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    # Pago del que provino el excedente, si aplica (puede ser None si el crédito se originó de otra forma).
    source_payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    amount = Column(Numeric(10, 2), nullable=False)
    # Cuánto queda por usar de este crédito. Permite uso parcial (ej. un crédito
    # de 50 puede aplicarse 30 a un cargo y 20 a otro, en momentos distintos).
    remaining_amount = Column(Numeric(10, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner")
    source_payment = relationship("Payment")
