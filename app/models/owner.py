from sqlalchemy import Column, Integer, String
from app.database import Base
from sqlalchemy import DateTime
from datetime import datetime


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    identification = Column(String, nullable=True)
    # Relación con unidades (opcional)
    created_at = Column(DateTime, default=datetime.utcnow)
