from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy import DateTime
from datetime import datetime


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)

    unit_number = Column(String, nullable=False)
    floor = Column(String, nullable=True)

    property = relationship("Property", backref="units")
    created_at = Column(DateTime, default=datetime.utcnow)
    charges = relationship("Charge", back_populates="unit")

