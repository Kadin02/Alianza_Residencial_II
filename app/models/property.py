from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy import DateTime
from datetime import datetime


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # PH | CASA | LOCAL
    address = Column(String, nullable=False)
    max_units = Column(Integer, default=50)

    created_at = Column(DateTime, default=datetime.utcnow)

