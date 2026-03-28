"""
app/main.py — Aplicación principal FastAPI
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import engine, Base, SessionLocal
from app.routers import property, unit, owner, unit_owner, finance, charges, auth
from app.routers import suppliers, agenda

# ── Crear tablas ─────────────────────────────
Base.metadata.create_all(bind=engine)


# ── Crear usuario admin por defecto ──────────
#def _seed_admin():
    #from app.services.auth_service import create_default_admin
    #db = SessionLocal()
    #try:
        #"create_default_admin(db)
    #finally:
        #db.close()

#_seed_admin()


# ── App principal ────────────────────────────
app = FastAPI(title="Alianza Residencial", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sub-app de API bajo /api ──────────────────
api_app = FastAPI(title="Alianza API")

api_app.include_router(property.router)
api_app.include_router(unit.router)
api_app.include_router(owner.router)
api_app.include_router(unit_owner.router)
api_app.include_router(finance.router)
api_app.include_router(charges.router)
api_app.include_router(auth.router)
api_app.include_router(suppliers.router)
api_app.include_router(agenda.router)

app.mount("/api", api_app)

# ── Archivos estáticos ────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ── Páginas ───────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/login")


@app.get("/login")
async def login_page():
    return FileResponse("app/static/login.html")
