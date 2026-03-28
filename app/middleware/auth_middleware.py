from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
import re

from app.config import settings

security = HTTPBearer(auto_error=False)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Rutas públicas (no requieren token)
        public_paths = [
            r'^/login$',
            r'^/static/.*',
            r'^/auth/token$',
            r'^/auth/login$',
            r'^/$'
        ]
        
        path = request.url.path
        
        # Verificar si es ruta pública
        for pattern in public_paths:
            if re.match(pattern, path):
                return await call_next(request)
        
        # Verificar token
        token = request.headers.get("Authorization")
        if not token:
            # Si no hay token, redirigir al login
            return RedirectResponse(url="/login")
        
        try:
            token = token.replace("Bearer ", "")
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            request.state.user = payload
        except JWTError:
            return RedirectResponse(url="/login")
        
        return await call_next(request)