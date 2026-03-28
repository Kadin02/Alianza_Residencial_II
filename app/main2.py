from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import engine, Base
from app.routers import property, unit, owner, unit_owner, finance, charges, auth

# Crear app principal
app = FastAPI(title="Alianza Residencial API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== RUTAS DE API (con prefijo /api) =====
api_app = FastAPI()

# Incluir routers en la API
api_app.include_router(property.router)
api_app.include_router(unit.router)
api_app.include_router(owner.router)
api_app.include_router(unit_owner.router)
api_app.include_router(finance.router)
api_app.include_router(charges.router)
api_app.include_router(auth.router)

# Montar la API bajo /api
app.mount("/api", api_app)

# ===== RUTAS DE FRONTEND =====
# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    """Redirigir al login"""
    return RedirectResponse(url="/login")

@app.get("/login")
async def serve_login():
    return FileResponse(os.path.join("app/static", "login.html"))

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(os.path.join("app/static", "index.html"))

# Crear tablas
Base.metadata.create_all(bind=engine)

# Middleware de autenticación (opcional, lo agregamos después)
#from app.middleware.auth_middleware import AuthMiddleware
#app.add_middleware(AuthMiddleware)