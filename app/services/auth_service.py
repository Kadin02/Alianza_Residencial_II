"""
app/services/auth_service.py
JWT + creación de usuario admin por defecto al arrancar.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.security import verify_password, hash_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# ── JWT ──────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Autenticar ───────────────────────────────
def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ── get_current_user (dependencia FastAPI) ────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise exc
    username = payload.get("sub")
    if not username:
        raise exc
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise exc
    return user


# ── Crear admin por defecto al arrancar ───────
def create_default_admin(db: Session):
    """
    Se llama desde app/main.py al iniciar.
    Crea el usuario admin si no existe usando las variables del .env:
      DEFAULT_ADMIN_USER / DEFAULT_ADMIN_PASS
    """
    username = settings.DEFAULT_ADMIN_USER
    password = settings.DEFAULT_ADMIN_PASS

    if not db.query(User).filter(User.username == username).first():
        db.add(User(
            username=username,
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
        ))
        db.commit()
        print(f"[AUTH] Usuario admin creado: {username}")
