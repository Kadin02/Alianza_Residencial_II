# Alianza Residencial — Instrucciones de instalación de escritorio

## ¿Qué se entrega en este paquete?

| Archivo | Acción |
|---------|--------|
| `launcher.py` | **Reemplaza** `Run.py` como punto de entrada principal |
| `main.js` | **Reemplaza** `app/static/js/main.js` |
| `app_main.py` | **Reemplaza** `app/main.py` (renombrar a `main.py`) |
| `auth_service.py` | **Reemplaza** `app/services/auth_service.py` |
| `build.bat` | Nuevo — genera el `.exe` instalable |

---

## Paso 1 — Copiar archivos

```
launcher.py          →  C:\alianza_backend\launcher.py
main.js              →  C:\alianza_backend\app\static\js\main.js
app_main.py          →  C:\alianza_backend\app\main.py   (renombrar)
auth_service.py      →  C:\alianza_backend\app\services\auth_service.py
build.bat            →  C:\alianza_backend\build.bat
```

---

## Paso 2 — Probar localmente

```bash
cd C:\alianza_backend
python launcher.py
```

Verás una ventana con:
- Indicador LED rojo/verde del servidor
- Log de actividad en tiempo real
- Botón **Iniciar Sistema** → arranca FastAPI + abre el navegador
- Botón **Abrir navegador** → abre `http://localhost:8000`
- Botón **Detener** → para el servidor limpiamente

Al iniciar, el sistema:
1. Verifica dependencias (`pip install -r requirements.txt`)
2. Crea las carpetas `database/`, `logs/`, `invoices/`
3. Arranca uvicorn en el puerto 8000
4. Espera que el servidor responda
5. Abre el navegador automáticamente en el login

---

## Paso 3 — Qué cambió en el código

### `main.js` (frontend)
- Añadido objeto `Auth` — guarda/lee el token JWT en localStorage
- `apiRequest()` ahora envía `Authorization: Bearer <token>` en cada petición
- Si el servidor responde 401, limpia la sesión y redirige al login
- `renderHeader()` muestra el nombre del usuario y botón de logout
- Nueva función `logout()` — limpia localStorage y va al login

### `app/main.py`
- Al arrancar, llama `create_default_admin()` — crea usuario admin si no existe
- Las rutas de API están bajo `/api` (coincide con el frontend)

### `app/services/auth_service.py`
- Nueva función `create_default_admin(db)` — crea admin desde variables del `.env`

---

## Paso 4 — Generar el .exe (opcional, para distribuir)

Instalar PyInstaller:
```bash
pip install pyinstaller
```

Ejecutar el build:
```
Doble clic en build.bat
```

El resultado estará en:
```
dist\AlianzaResidencial\AlianzaResidencial.exe
```

Para distribuir al cliente: comprimir toda la carpeta `dist\AlianzaResidencial\` en un ZIP.

> **Nota:** El `.exe` incluye Python y todas las dependencias. El cliente solo necesita
> hacer doble clic — no necesita instalar Python.

---

## Credenciales por defecto

- **Usuario:** admin  
- **Contraseña:** Admin123

Se pueden cambiar en el archivo `.env`:
```
DEFAULT_ADMIN_USER=admin
DEFAULT_ADMIN_PASS=Admin123
```

---

## Próximos pasos sugeridos

1. Generar el `.exe` y probarlo en una PC limpia (sin Python instalado)
2. Crear un ícono `assets/icon.ico` para personalizar el launcher
3. Agregar un instalador con Inno Setup (crea el típico "siguiente → siguiente → instalar")
4. Cuando estés listo para agregar más funciones, continuar con el desarrollo normal
