from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.database import get_db
from app.models.agenda_event import AgendaEvent

router = APIRouter(prefix="/agenda", tags=["Agenda"])

# ── Schema ────────────────────────────────────

class EventCreate(BaseModel):
    title:       str
    description: Optional[str] = None
    event_type:  str           # CITA | EVENTO | TAREA
    event_date:  date
    event_time:  Optional[str] = None
    location:    Optional[str] = None
    status:      str = "PENDIENTE"
    priority:    str = "NORMAL"

# ── Endpoints ─────────────────────────────────

@router.get("/")
def list_events(db: Session = Depends(get_db)):
    return db.query(AgendaEvent).order_by(
        AgendaEvent.event_date, AgendaEvent.event_time
    ).all()

@router.get("/upcoming")
def upcoming_events(db: Session = Depends(get_db)):
    """Próximos eventos desde hoy (para el dashboard)."""
    from datetime import date as dt
    return db.query(AgendaEvent).filter(
        AgendaEvent.event_date >= dt.today(),
        AgendaEvent.status == "PENDIENTE"
    ).order_by(AgendaEvent.event_date, AgendaEvent.event_time).limit(10).all()

@router.post("/")
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    ev = AgendaEvent(**data.dict())
    db.add(ev); db.commit(); db.refresh(ev)
    return ev

@router.put("/{event_id}")
def update_event(event_id: int, data: EventCreate, db: Session = Depends(get_db)):
    ev = db.query(AgendaEvent).filter(AgendaEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    for k, v in data.dict().items():
        setattr(ev, k, v)
    db.commit(); db.refresh(ev)
    return ev

@router.patch("/{event_id}/status")
def update_status(event_id: int, status: str, db: Session = Depends(get_db)):
    ev = db.query(AgendaEvent).filter(AgendaEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    ev.status = status
    db.commit()
    return {"message": "Estado actualizado", "status": status}

@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    ev = db.query(AgendaEvent).filter(AgendaEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(ev); db.commit()
    return {"message": "Evento eliminado"}
