from decimal import Decimal

from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Charge(Base):
    __tablename__ = "charges"

    id = Column(Integer, primary_key=True, index=True)

    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)

    description = Column(String, nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)

    status = Column(String, default="PENDIENTE")

    date_created = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    # Vincula un cargo de mora con el cargo original vencido que la generó. Nullable: solo aplica a cargos de mora.
    related_charge_id = Column(Integer, ForeignKey("charges.id"), nullable=True)

    unit = relationship("Unit", back_populates="charges")
    # ✅ CORREGIDO: back_populates coincide con PaymentApplication
    applications = relationship("PaymentApplication", back_populates="charge")
    credit_applications = relationship("CreditApplication", back_populates="charge")

    @property
    def balance(self) -> Decimal:
        """Saldo pendiente, derivado siempre de pagos + créditos aplicados (fuente única de verdad)."""
        total_applied = sum((a.applied_amount for a in self.applications), Decimal("0.00"))
        total_applied += sum((c.applied_amount for c in self.credit_applications), Decimal("0.00"))
        return self.amount - total_applied