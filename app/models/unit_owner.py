from sqlalchemy import Column, Integer, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class UnitOwner(Base):
    __tablename__ = "unit_owners"

    id = Column(Integer, primary_key=True, index=True)

    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True)

    unit = relationship("Unit", backref="ownerships")
    owner = relationship("Owner", backref="units")
