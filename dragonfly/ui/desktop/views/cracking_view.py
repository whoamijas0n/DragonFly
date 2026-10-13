"""
dragonfly/ui/desktop/views/cracking_view.py - Vista de fuerza bruta WPA/WPA2 con aircrack-ng para Desktop.
"""

import os
from tkinter import filedialog
import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_PELIGRO_HOVER,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER,
    COLOR_BOTON_DESHABILITADO
)
from dragonfly.config import BASE_DIR_WIFI, DEFAULT_WORDLIST
from dragonfly.core.session import SessionManager


class CrackingView(BaseView):
    """
    Vista de ataque de diccionario offline sobre capturas .cap.
    """

    def __init__(self, app):
        super().__init__(app)
        self.var_diccionario = ctk.StringVar(value=DEFAULT_WORDLIST if os.path.exists(DEFAULT_WORDLIST) else "")
        self.btn_iniciar = None
        self.btn_detener = None

    def render(self):
        """Paso 1: Seleccionar carpeta de sesión de Handshake."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="CRACKING WPA (AIRCRACK-NG)", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        ctk.CTkLabel(self.main_frame, text="Selecciona la sesión con el archivo .cap objetivo:", text_color="#aaaaaa").pack(pady=5)

        sesiones = SessionManager.list_sessions(BASE_DIR_WIFI)
        if not sesiones:
            ctk.CTkLabel(self.main_frame, text="No hay capturas guardadas en Resultados_Handshake/.", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for s in sesiones:
            ruta = os.path.join(BASE_DIR_WIFI, s)
            ctk.CTkButton(
                frame,
                text=f"📁 {s}",
                fg_color=COLOR_BOTON_GRIS,
                hover_color=COLOR_BOTON_GRIS_HOVER,
                anchor="w",
                command=lambda r=ruta: self._select_cap_file(r)
            ).pack(fill="x", pady=3)

    def _select_cap_file(self, session_path: str):
        """Paso 2: Seleccionar archivo .cap dentro de la sesión."""
        self.clear_frame()
        self.add_back_button(self.render)

        nombre_sesion = os.path.basename(session_path)
        ctk.CTkLabel(self.main_frame, text=f"SELECCIONA ARCHIVO .CAP\n({nombre_sesion})",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        archivos = [f for f in SessionManager.list_session_files(session_path) if f.endswith(".cap")]
        if not archivos:
            ctk.CTkLabel(self.main_frame, text="No se encontraron archivos .cap en esta sesión.", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=250)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for arch in archivos:
            ruta_cap = os.path.join(session_path, arch)
            ctk.CTkButton(
                frame,
                text=f"🔑 {arch}",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda rc=ruta_cap: self._configure_attack(rc)
            ).pack(fill="x", pady=3)

    def _configure_attack(self, ruta_cap: str):
        """Paso 3: Configurar diccionario y lanzar ataque de fuerza bruta."""
        self.clear_frame()
        self.add_back_button(lambda: self._select_cap_file(os.path.dirname(ruta_cap)))

        ctk.CTkLabel(self.main_frame, text="CONFIGURAR FUERZA BRUTA WPA", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        ctk.CTkLabel(self.main_frame, text=f"Archivo Objetivo: {os.path.basename(ruta_cap)}",
                     font=ctk.CTkFont(size=14), text_color="#aaaaaa").pack(pady=5)

        # Configuración del Diccionario
        dicc_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        dicc_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(dicc_frame, text="Diccionario:").pack(side="left", padx=5)
        entry_dicc = ctk.CTkEntry(dicc_frame, textvariable=self.var_diccionario, width=350)
        entry_dicc.pack(side="left", padx=5)

        def examinar():
            ruta = filedialog.askopenfilename(
                title="Seleccionar Diccionario",
                filetypes=[("Archivos de Texto", "*.txt"), ("Todos los Archivos", "*.*")]
            )
            if ruta:
                self.var_diccionario.set(ruta)

        ctk.CTkButton(
            dicc_frame,
            text="Examinar...",
            width=80,
            fg_color=COLOR_BOTON_GRIS,
            hover_color=COLOR_BOTON_GRIS_HOVER,
            command=examinar
        ).pack(side="left", padx=5)

        # Botones de Control
        ctrl_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=40, pady=15)

        self.btn_iniciar = ctk.CTkButton(
            ctrl_frame,
            text="INICIAR FUERZA BRUTA",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            height=40,
            command=lambda: self._start_crack(ruta_cap)
        )
        self.btn_iniciar.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_detener = ctk.CTkButton(
            ctrl_frame,
            text="DETENER ATAQUE",
            fg_color=COLOR_BOTON_DESHABILITADO,
            state="disabled",
            height=40,
            command=self._stop_crack
        )
        self.btn_detener.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.show_console()

    def _start_crack(self, ruta_cap: str):
        dicc = self.var_diccionario.get().strip()
        if not dicc or not os.path.exists(dicc):
            self.write_console(f"\n[!] ERROR: El diccionario no existe: {dicc}")
            return

        if self.btn_iniciar and self.btn_iniciar.winfo_exists():
            self.btn_iniciar.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
        if self.btn_detener and self.btn_detener.winfo_exists():
            self.btn_detener.configure(state="normal", fg_color=COLOR_BOTON_PELIGRO)

        def on_finish(rc):
            def restore():
                if self.btn_iniciar and self.btn_iniciar.winfo_exists():
                    self.btn_iniciar.configure(state="normal", fg_color=COLOR_BOTON_PELIGRO)
                if self.btn_detener and self.btn_detener.winfo_exists():
                    self.btn_detener.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
            self.run_on_ui(restore)

        self.services.cracking.start_crack(
            cap_path=ruta_cap,
            wordlist_path=dicc,
            on_output=self.write_console,
            on_finish=on_finish
        )

    def _stop_crack(self):
        if self.btn_detener and self.btn_detener.winfo_exists():
            self.btn_detener.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
        self.services.cracking.stop_crack(on_output=self.write_console)
