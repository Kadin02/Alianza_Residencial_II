from sqlalchemy import Column, Integer, ForeignKey, Date, String, Numeric
from sqlalchemy.orm import relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ CORREGIDO: se agregó owner_id, amount e invoice_number que faltaban
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=True)

    payer_name = Column(String, nullable=True)
    payment_date = Column(Date)

    payment_method = Column(String, nullable=True)
    reference = Column(String, nullable=True)

    # amount es el campo que usa el service internamente
    amount = Column(Numeric(10, 2))
    # total_amount queda como alias para compatibilidad con el PRD
    total_amount = Column(Numeric(10, 2), nullable=True)

    invoice_number = Column(String, nullable=True)

    # Concepto del pago: "Mantenimiento", "Cuota de Ascensor", "Gas", "Abono"
    concept = Column(String, nullable=True)

    property = relationship("Property")
    owner = relationship("Owner")

    applications = relationship(
        "PaymentApplication",
        back_populates="payment"
    )

    # ✅ CORREGIDO: usa back_populates en lugar de backref para evitar conflicto con Invoice
    invoice = relationship(
        "Invoice",
        back_populates="payment",
        uselist=False
    )
