from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.models.user import User
from app.services.security import verify_password
from app.services.auth_service import create_access_token, authenticate_user, get_current_user
from app.schemas.auth_schema import LoginResponse, UserResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ── Roles válidos del sistema ──────────────────────────────────
# ADMIN   → acceso total
# USER    → acceso estándar (registrar pagos, propietarios, etc.)
# GARITA  → solo puede ver y registrar visitas en el módulo de garita
VALID_ROLES = ("ADMIN", "USER", "GARITA")


@router.post("/token", response_model=LoginResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }


@router.post("/login", response_model=LoginResponse)
async def login_json(
    login_data: dict,
    db: Session = Depends(get_db)
):
    username = login_data.get("username")
    password = login_data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username y password son requeridos")
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(token, db)
    return current_user


def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Se requieren privilegios de administrador")
    return current_user


from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional


class UserCreate(_BaseModel):
    username: str
    password: str
    role: str = "USER"   # ADMIN | USER | GARITA


class UserPasswordChange(_BaseModel):
    new_password: str


# ── Listar todos los usuarios — solo ADMIN ────────────────
@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.username).all()
    return [
        {
            "id":        u.id,
            "username":  u.username,
            "role":      u.role,
            "is_active": u.is_active,
        }
        for u in users
    ]


# ── Crear usuario — solo ADMIN ────────────────────────────
@router.post("/users")
def create_user(
    data: UserCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.security import hash_password

    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Usa: {', '.join(VALID_ROLES)}")

    exists = db.query(User).filter(User.username == data.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    new_user = User(
        username      = data.username,
        password_hash = hash_password(data.password),
        role          = data.role,
        is_active     = True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Usuario creado", "id": new_user.id, "username": new_user.username, "role": new_user.role}


# ── Activar / Desactivar usuario — solo ADMIN ─────────────
@router.patch("/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"Usuario {'activado' if user.is_active else 'desactivado'}", "is_active": user.is_active}


# ── Cambiar contraseña de un usuario — solo ADMIN ─────────
@router.patch("/users/{user_id}/password")
def change_user_password(
    user_id: int,
    data: UserPasswordChange,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.security import hash_password
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not data.new_password or len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}


# ── Eliminar usuario — solo ADMIN ─────────────────────────
@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    db.delete(user)
    db.commit()
    return {"message": "Usuario eliminado"}
