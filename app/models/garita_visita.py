from sqlalchemy import Column, Integer, String
from app.database import Base


class Visita(Base):
    """Registro de visitas en garita."""
    __tablename__ = "garita_visitas"

    id               = Column(Integer, primary_key=True, index=True)
    nombre_visitante = Column(String, nullable=False)
    cedula           = Column(String, nullable=True)
    unit_id          = Column(Integer, nullable=False)
    unit_number      = Column(String, nullable=False)
    motivo           = Column(String, nullable=False)
    tipo_visita      = Column(String, default="Personal")
    placa            = Column(String, nullable=True)
    observaciones    = Column(String, nullable=True)
    preregistro_id   = Column(Integer, nullable=True)
    fecha_ingreso    = Column(String, nullable=False)   # ISO string
    fecha_salida     = Column(String, nullable=True)
    estado           = Column(String, default="INGRESO")  # INGRESO | SALIDA
