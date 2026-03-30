"""
app/routers/garita.py
Router para el módulo de control de garita.
Incluye: visitas y pre-registros.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.garita_visita import Visita
from app.models.garita_preregistro import PreRegistro
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/garita", tags=["Garita"])




class VisitaCreate(BaseModel):
    nombre_visitante: str
    cedula:           Optional[str] = None
    unit_id:          int
    unit_number:      str
    motivo:           str
    tipo_visita:      str = "Personal"
    placa:            Optional[str] = None
    observaciones:    Optional[str] = None
    preregistro_id:   Optional[int] = None
    fecha_ingreso:    str
    estado:           str = "INGRESO"


class VisitaSalidaUpdate(BaseModel):
    fecha_salida: str
    estado:       str = "SALIDA"


class PreRegistroCreate(BaseModel):
    unit_id:          int
    unit_number:      str
    codigo:           str
    nombre_visitante: Optional[str] = None
    fecha_esperada:   Optional[str] = None
    motivo:           Optional[str] = None
    notas:            Optional[str] = None
    activo:           bool = True


# ══ Endpoints de Visitas ══════════════════════════════

@router.get("/visitas")
def list_visitas(db: Session = Depends(get_db)):
    """Lista todas las visitas, las más recientes primero."""
    visitas = db.query(Visita).order_by(Visita.id.desc()).all()

    return [
        {
            "id":               v.id,
            "nombre_visitante": v.nombre_visitante,
            "cedula":           v.cedula,
            "unit_id":          v.unit_id,
            "unit_number":      v.unit_number,
            "motivo":           v.motivo,
            "tipo_visita":      v.tipo_visita,
            "placa":            v.placa,
            "observaciones":    v.observaciones,
            "preregistro_id":   v.preregistro_id,
            "fecha_ingreso":    v.fecha_ingreso,
            "fecha_salida":     v.fecha_salida,
            "estado":           v.estado,
        }
        for v in visitas
    ]


@router.post("/visitas")
def create_visita(data: VisitaCreate, db: Session = Depends(get_db)):
    """Registrar ingreso de visitante."""
    v = Visita(
        nombre_visitante = data.nombre_visitante,
        cedula           = data.cedula,
        unit_id          = data.unit_id,
        unit_number      = data.unit_number,
        motivo           = data.motivo,
        tipo_visita      = data.tipo_visita,
        placa            = data.placa,
        observaciones    = data.observaciones,
        preregistro_id   = data.preregistro_id,
        fecha_ingreso    = data.fecha_ingreso,
        estado           = "INGRESO",
    )
    db.add(v); db.commit(); db.refresh(v)
    return {"id": v.id, "message": "Visita registrada"}


@router.patch("/visitas/{visita_id}/salida")
def registrar_salida(visita_id: int, data: VisitaSalidaUpdate, db: Session = Depends(get_db)):
    """Registrar salida de visitante."""
    v = db.query(Visita).filter(Visita.id == visita_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    v.fecha_salida = data.fecha_salida
    v.estado       = "SALIDA"
    db.commit()
    return {"message": "Salida registrada"}


# ══ Endpoints de Pre-registros ════════════════════════

@router.get("/preregistros")
def list_preregistros(activos: bool = False, db: Session = Depends(get_db)):
    """Lista pre-registros, opcionalmente solo los activos."""
    q = db.query(PreRegistro)
    if activos:
        q = q.filter(PreRegistro.activo == True)
    registros = q.order_by(PreRegistro.id.desc()).all()
    return [
        {
            "id":               p.id,
            "unit_id":          p.unit_id,
            "unit_number":      p.unit_number,
            "codigo":           p.codigo,
            "nombre_visitante": p.nombre_visitante,
            "fecha_esperada":   p.fecha_esperada,
            "motivo":           p.motivo,
            "notas":            p.notas,
            "activo":           p.activo,
            "created_at":       p.created_at,
        }
        for p in registros
    ]


@router.get("/preregistros/codigo/{codigo}")
def get_preregistro_by_code(codigo: str, db: Session = Depends(get_db)):
    """Buscar pre-registro por código para la garita."""
    p = db.query(PreRegistro).filter(
        PreRegistro.codigo == codigo.upper(),
        PreRegistro.activo == True
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Código no encontrado o ya utilizado")
    return {
        "id":               p.id,
        "unit_id":          p.unit_id,
        "unit_number":      p.unit_number,
        "codigo":           p.codigo,
        "nombre_visitante": p.nombre_visitante,
        "fecha_esperada":   p.fecha_esperada,
        "motivo":           p.motivo,
    }


@router.post("/preregistros")
def create_preregistro(data: PreRegistroCreate, db: Session = Depends(get_db)):
    """Crear un nuevo pre-registro."""
    # Verificar que el código no exista
    exists = db.query(PreRegistro).filter(PreRegistro.codigo == data.codigo).first()
    if exists:
        raise HTTPException(status_code=400, detail="El código ya existe")

    p = PreRegistro(
        unit_id          = data.unit_id,
        unit_number      = data.unit_number,
        codigo           = data.codigo,
        nombre_visitante = data.nombre_visitante,
        fecha_esperada   = data.fecha_esperada,
        motivo           = data.motivo,
        notas            = data.notas,
        activo           = True,
    )
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "codigo": p.codigo, "message": "Pre-registro creado"}


@router.patch("/preregistros/{preregistro_id}/usar")
def marcar_usado(preregistro_id: int, db: Session = Depends(get_db)):
    """Marcar pre-registro como usado al registrar el ingreso."""
    p = db.query(PreRegistro).filter(PreRegistro.id == preregistro_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pre-registro no encontrado")
    p.activo = False
    db.commit()
    return {"message": "Pre-registro marcado como usado"}


@router.delete("/preregistros/{preregistro_id}")
def delete_preregistro(preregistro_id: int, db: Session = Depends(get_db)):
    """Cancelar y eliminar un pre-registro."""
    p = db.query(PreRegistro).filter(PreRegistro.id == preregistro_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pre-registro no encontrado")
    db.delete(p); db.commit()
    return {"message": "Pre-registro eliminado"}
