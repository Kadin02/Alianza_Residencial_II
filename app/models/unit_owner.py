from sqlalchemy import Column, Integer, ForeignKey, Date, Boolean, Index
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

    __table_args__ = (
        Index(
            "idx_unit_owners_unit_active",
            "unit_id",
            unique=True,
            postgresql_where=(is_active == True),
            sqlite_where=(is_active == 1),
        ),
    )
