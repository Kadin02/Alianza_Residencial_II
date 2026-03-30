"""
app/main.py — Aplicación principal FastAPI
Versión Railway: maneja proxy HTTPS y crea admin por defecto
"""

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
import os

from app.database import engine, Base, SessionLocal
from app.routers import property, unit, owner, unit_owner, finance, charges, auth
from app.routers import suppliers, agenda
from app.routers import garita

# ── Crear tablas ─────────────────────────────
Base.metadata.create_all(bind=engine)


# ── Crear usuario admin por defecto ──────────
def _seed_admin():
    from app.services.auth_service import create_default_admin
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()

_seed_admin()


# ── Crear carpetas necesarias ─────────────────
for folder in ["database", "logs", "invoices", "supplier_docs"]:
    os.makedirs(folder, exist_ok=True)


# ── App principal ────────────────────────────
app = FastAPI(title="Alianza Residencial", version="1.0.0")

# ── Middleware para proxy HTTPS (Railway) ─────
# Railway termina SSL en el proxy y reenvía como HTTP internamente.
# Este middleware lee los headers del proxy para que FastAPI
# sepa que está detrás de HTTPS y no genere URLs con http://.
from starlette.middleware.trustedhost import TrustedHostMiddleware

@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    # Si viene del proxy de Railway, marcar como HTTPS
    if request.headers.get("x-forwarded-proto") == "https":
        request.scope["scheme"] = "https"
    response = await call_next(request)
    return response

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
api_app.include_router(garita.router)

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
