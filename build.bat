@echo off
REM ═══════════════════════════════════════════════════════
REM  ALIANZA RESIDENCIAL — Build .exe para Windows
REM  Resultado: dist\AlianzaResidencial\AlianzaResidencial.exe
REM  Requiere Python + pip install pyinstaller
REM ═══════════════════════════════════════════════════════

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  ALIANZA RESIDENCIAL — Generando .exe   ║
echo  ╚══════════════════════════════════════════╝
echo.

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo  Instalando PyInstaller...
    pip install pyinstaller
)

if exist dist\AlianzaResidencial rmdir /s /q dist\AlianzaResidencial
if exist build rmdir /s /q build
if exist AlianzaResidencial.spec del AlianzaResidencial.spec

echo  Compilando... (puede tardar 2-5 minutos)
echo.

pyinstaller ^
  --name "AlianzaResidencial" ^
  --onedir ^
  --windowed ^
  --add-data "app;app" ^
  --add-data ".env;." ^
  --add-data "requirements.txt;." ^
  --hidden-import "uvicorn.logging" ^
  --hidden-import "uvicorn.loops.auto" ^
  --hidden-import "uvicorn.protocols.http.auto" ^
  --hidden-import "uvicorn.protocols.websockets.auto" ^
  --hidden-import "uvicorn.lifespan.on" ^
  --hidden-import "passlib.handlers.bcrypt" ^
  --hidden-import "jose" ^
  --hidden-import "sqlalchemy.dialects.sqlite" ^
  --hidden-import "pydantic_settings" ^
  --collect-all "fastapi" ^
  --collect-all "sqlalchemy" ^
  --noconfirm ^
  launcher.py

if errorlevel 1 (
    echo.
    echo  ERROR durante la compilacion.
    pause & exit /b 1
)

echo.
echo  Copiando archivos de datos...
copy .env "dist\AlianzaResidencial\" >nul 2>&1
mkdir "dist\AlianzaResidencial\database" 2>nul
mkdir "dist\AlianzaResidencial\logs"     2>nul
mkdir "dist\AlianzaResidencial\invoices" 2>nul

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  Build completado exitosamente  ✓        ║
echo  ║                                          ║
echo  ║  Carpeta: dist\AlianzaResidencial\       ║
echo  ║  Archivo: AlianzaResidencial.exe         ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  Para distribuir: comprime dist\AlianzaResidencial\
echo.
pause
