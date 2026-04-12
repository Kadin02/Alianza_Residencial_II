"""
Alianza Residencial — Launcher de escritorio
Ventana nativa con tkinter que controla el servidor FastAPI.
Ejecutar: python launcher.py
"""

import tkinter as tk
from tkinter import messagebox
import threading
import subprocess
import sys
import os
import time
import webbrowser
import socket
from pathlib import Path

# ─── Configuración ──────────────────────────
APP_NAME = "Alianza Residencial"
APP_URL  = "http://localhost:8000"
PORT     = 8000

C_BG      = "#f0f2f5"
C_DARK    = "#0a2c5e"
C_DARK2   = "#1e4a8c"
C_WHITE   = "#ffffff"
C_SUCCESS = "#10b981"
C_DANGER  = "#ef4444"
C_MUTED   = "#5a6a7e"
C_BORDER  = "#e6e9f0"
C_TEXT    = "#1a2639"


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def wait_server(port: int, timeout=30) -> bool:
    t = time.time()
    while time.time() - t < timeout:
        if not port_free(port):
            return True
        time.sleep(0.4)
    return False


def get_python() -> str:
    for p in [Path("venv/Scripts/python.exe"), Path("venv/bin/python")]:
        if p.exists():
            return str(p)
    return sys.executable


# ─── Ventana principal ───────────────────────
class Launcher:
    def __init__(self):
        self.proc    = None
        self.running = False

        self.root = tk.Tk()
        self.root.title("Alianza Residencial — Launcher")
        self.root.resizable(False, False)
        self.root.configure(bg=C_BG)

        w, h = 460, 550
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        for ico in [Path("assets/icon.ico"), Path("app/static/favicon.ico")]:
            if ico.exists():
                try: self.root.iconbitmap(str(ico))
                except: pass
                break

        self._ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ── Construir UI ─────────────────────────
    def _ui(self):
        # Header azul
        hdr = tk.Frame(self.root, bg=C_DARK, height=112)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        logo = tk.Frame(hdr, bg=C_DARK2, width=52, height=52)
        logo.place(x=22, y=30)
        logo.pack_propagate(False)
        tk.Label(logo, text="AR", bg=C_DARK2, fg=C_WHITE,
                 font=("Segoe UI", 17, "bold")).place(relx=.5, rely=.5, anchor="center")

        tk.Label(hdr, text="ALIANZA RESIDENCIAL", bg=C_DARK, fg=C_WHITE,
                 font=("Segoe UI", 13, "bold")).place(x=90, y=30)
        tk.Label(hdr, text="Sistema de Administración de Propiedades",
                 bg=C_DARK, fg="#7aa8d4", font=("Segoe UI", 9)).place(x=90, y=57)
        tk.Label(hdr, text="v1.0  ·  Base de datos local",
                 bg=C_DARK, fg="#3a5e82", font=("Segoe UI", 8)).place(x=90, y=79)

        # Body
        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        # — Tarjeta de estado —
        sc = tk.Frame(body, bg=C_WHITE, highlightbackground=C_BORDER, highlightthickness=1)
        sc.pack(fill="x", pady=(0, 12))

        tk.Label(sc, text="ESTADO DEL SERVIDOR", bg=C_WHITE, fg=C_MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=14, pady=(11, 3))

        srow = tk.Frame(sc, bg=C_WHITE)
        srow.pack(fill="x", padx=14, pady=(0, 4))

        self.led_cv = tk.Canvas(srow, width=14, height=14, bg=C_WHITE, highlightthickness=0)
        self.led_cv.pack(side="left")
        self.led = self.led_cv.create_oval(2, 2, 12, 12, fill=C_DANGER, outline="")

        self.lbl_status = tk.Label(srow, text="Detenido", bg=C_WHITE, fg=C_DANGER,
                                   font=("Segoe UI", 11, "bold"))
        self.lbl_status.pack(side="left", padx=(8, 0))

        self.lbl_url = tk.Label(sc, text="", bg=C_WHITE, fg=C_MUTED,
                                font=("Segoe UI", 8), cursor="hand2")
        self.lbl_url.pack(anchor="w", padx=14, pady=(0, 11))
        self.lbl_url.bind("<Button-1>", lambda _: self._open())

        # — Log —
        lc = tk.Frame(body, bg=C_WHITE, highlightbackground=C_BORDER, highlightthickness=1)
        lc.pack(fill="both", expand=True, pady=(0, 12))

        tk.Label(lc, text="REGISTRO DE ACTIVIDAD", bg=C_WHITE, fg=C_MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(10, 3))

        self.log = tk.Text(lc, height=11, wrap="word", bg="#f8fafc", fg=C_TEXT,
                           font=("Consolas", 8), relief="flat",
                           padx=10, pady=6, state="disabled", cursor="arrow")
        self.log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log.tag_config("ok",   foreground=C_SUCCESS)
        self.log.tag_config("err",  foreground=C_DANGER)
        self.log.tag_config("warn", foreground="#d97706")

        # — Botones —
        bf = tk.Frame(body, bg=C_BG)
        bf.pack(fill="x")

        self.btn_start = tk.Button(
            bf, text="▶   Iniciar Sistema",
            bg=C_DARK, fg=C_WHITE, font=("Segoe UI", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground=C_DARK2, activeforeground=C_WHITE,
            padx=18, pady=11, command=self._start)
        self.btn_start.pack(fill="x", pady=(0, 8))

        br = tk.Frame(bf, bg=C_BG)
        br.pack(fill="x")

        self.btn_open = tk.Button(
            br, text="🌐  Abrir navegador",
            bg=C_WHITE, fg=C_DARK, font=("Segoe UI", 9),
            relief="flat", cursor="hand2",
            highlightbackground=C_BORDER, highlightthickness=1,
            padx=12, pady=9, command=self._open, state="disabled")
        self.btn_open.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_stop = tk.Button(
            br, text="⏹  Detener",
            bg=C_WHITE, fg=C_DANGER, font=("Segoe UI", 9),
            relief="flat", cursor="hand2",
            highlightbackground=C_BORDER, highlightthickness=1,
            padx=12, pady=9, command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", fill="x", expand=True)

        tk.Label(self.root, text="© 2026 Alianza Residencial — Mercedes Bienes Raíces",
                 bg=C_BG, fg=C_MUTED, font=("Segoe UI", 7)).pack(pady=(0, 10))

        self._log("Launcher listo. Presiona Iniciar Sistema para comenzar.")

    # ── Logging ──────────────────────────────
    def _log(self, msg: str, level="info"):
        ts  = time.strftime("%H:%M:%S")
        sym = {"ok": "✓", "err": "✕", "warn": "⚠"}.get(level, "·")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] {sym} {msg}\n", level if level != "info" else "")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ── Estado UI ────────────────────────────
    def _set_running(self, on: bool):
        if on:
            self.led_cv.itemconfig(self.led, fill=C_SUCCESS)
            self.lbl_status.config(text="Activo", fg=C_SUCCESS)
            self.lbl_url.config(text=f"↗  {APP_URL}   (clic para abrir)")
            self.btn_start.config(state="disabled", bg="#94a3b8", text="▶   Activo")
            self.btn_open.config(state="normal")
            self.btn_stop.config(state="normal")
        else:
            self.led_cv.itemconfig(self.led, fill=C_DANGER)
            self.lbl_status.config(text="Detenido", fg=C_DANGER)
            self.lbl_url.config(text="")
            self.btn_start.config(state="normal", bg=C_DARK, text="▶   Iniciar Sistema")
            self.btn_open.config(state="disabled")
            self.btn_stop.config(state="disabled")

    # ── Control servidor ─────────────────────
    def _start(self):
        if not port_free(PORT):
            self._log(f"Puerto {PORT} ya en uso — conectando", "warn")
            self._set_running(True)
            self._open()
            return
        self.btn_start.config(state="disabled", text="⏳  Iniciando...", bg="#94a3b8")
        self.running = True
        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        py = get_python()
        self._log(f"Python: {py}")

        for d in ["database", "logs", "invoices", "supplier_docs"]:
            os.makedirs(d, exist_ok=True)

        if Path("requirements.txt").exists():
            self._log("Verificando dependencias...")
            try:
                subprocess.run([py, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                               capture_output=True, timeout=180)
                self._log("Dependencias OK", "ok")
            except Exception as e:
                self._log(f"pip: {e}", "warn")

        self._log(f"Iniciando servidor en :{PORT}...")
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(
                [py, "-m", "uvicorn", "app.main:app",
                 "--host", "0.0.0.0", "--port", str(PORT), "--log-level", "warning"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=flags)
        except Exception as e:
            self._log(f"Error al iniciar: {e}", "err")
            self.root.after(0, lambda: self._set_running(False))
            return

        if wait_server(PORT, 30):
            self._log(f"Servidor activo — {APP_URL}", "ok")
            self.root.after(0, lambda: self._set_running(True))
            self.root.after(800, self._open)
        else:
            self._log("El servidor no respondió a tiempo", "err")
            self.root.after(0, lambda: self._set_running(False))
            self.root.after(0, lambda: self.btn_start.config(
                state="normal", bg=C_DARK, text="▶   Iniciar Sistema"))

        if self.proc:
            for line in self.proc.stdout:
                l = line.strip()
                if l: self._log(l)

    def _stop(self):
        if self.proc:
            self._log("Deteniendo servidor...")
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try: self.proc.kill()
                except: pass
            self.proc = None
        self.running = False
        self._set_running(False)
        self._log("Servidor detenido", "ok")

    def _open(self):
        if not port_free(PORT):
            webbrowser.open(APP_URL)
        else:
            self._log("El servidor no está activo aún", "warn")

    def _close(self):
        if self.running and self.proc:
            if messagebox.askyesno("Cerrar",
                    "El servidor está activo.\n¿Deseas detenerlo y cerrar?",
                    icon="warning"):
                self._stop()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.resolve())
    Launcher().run()
