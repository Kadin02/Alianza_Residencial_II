from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base
from datetime import datetime


class PreRegistro(Base):
    """Pre-registros de visitas autorizadas por residentes."""
    __tablename__ = "garita_preregistros"

    id               = Column(Integer, primary_key=True, index=True)
    unit_id          = Column(Integer, nullable=False)
    unit_number      = Column(String, nullable=False)
    codigo           = Column(String, unique=True, nullable=False, index=True)
    nombre_visitante = Column(String, nullable=True)
    fecha_esperada   = Column(String, nullable=True)
    motivo           = Column(String, nullable=True)
    notas            = Column(String, nullable=True)
    activo           = Column(Boolean, default=True)
    created_at       = Column(String, default=lambda: datetime.utcnow().isoformat())
