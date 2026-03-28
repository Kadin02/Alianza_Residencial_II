from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Time
from app.database import Base
from datetime import datetime


class AgendaEvent(Base):
    """Eventos, citas y tareas del edificio."""
    __tablename__ = "agenda_events"

    id           = Column(Integer, primary_key=True, index=True)
    title        = Column(String,  nullable=False)
    description  = Column(String,  nullable=True)
    event_type   = Column(String,  nullable=False)   # CITA | EVENTO | TAREA
    event_date   = Column(Date,    nullable=False)
    event_time   = Column(String,  nullable=True)    # "09:00" como string simple
    location     = Column(String,  nullable=True)
    status       = Column(String,  default="PENDIENTE")  # PENDIENTE | COMPLETADO | CANCELADO
    priority     = Column(String,  default="NORMAL")     # ALTA | NORMAL | BAJA
    created_at   = Column(DateTime, default=datetime.utcnow)
