"""
dragonfly/ui/desktop/views/explorer_view.py - Explorador genérico de resultados y evidencias.
Permite navegar por carpetas de sesión y leer archivos de reportes, capturas y credenciales.
"""

import os
import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER,
    COLOR_BOTON_PELIGRO
)
from dragonfly.core.session import SessionManager


class ExplorerView(BaseView):
    """
    Vista modular para explorar sesiones de auditoría y visualizar evidencias.
    """

    def show_sessions(self, base_dir: str, title: str, on_back_callback):
        """Muestra la lista de carpetas de auditoría guardadas."""
        self.clear_frame()
        self.add_back_button(on_back_callback)

        ctk.CTkLabel(self.main_frame, text=title.upper(), font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)

        sesiones = SessionManager.list_sessions(base_dir)
        if not sesiones:
            ctk.CTkLabel(self.main_frame, text="No hay sesiones registradas en este directorio.",
                         text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=350)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for s in sesiones:
            ruta = os.path.join(base_dir, s)
            btn = ctk.CTkButton(
                frame,
                text=f"📁 {s}",
                fg_color=COLOR_BOTON_GRIS,
                hover_color=COLOR_BOTON_GRIS_HOVER,
                anchor="w",
                command=lambda r=ruta, s_title=title, cb=on_back_callback: self.show_files(r, s_title, cb)
            )
            btn.pack(fill="x", pady=3)

    def show_files(self, session_path: str, title: str, on_back_callback):
        """Muestra los archivos contenidos dentro de una sesión."""
        self.clear_frame()
        base_dir = os.path.dirname(session_path)
        self.add_back_button(lambda: self.show_sessions(base_dir, title, on_back_callback))

        nombre_sesion = os.path.basename(session_path)
        ctk.CTkLabel(self.main_frame, text=f"ARCHIVOS DE: {nombre_sesion}",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        archivos = SessionManager.list_session_files(session_path)
        if not archivos:
            ctk.CTkLabel(self.main_frame, text="Esta sesión no contiene archivos.", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for arch in archivos:
            ruta_arch = os.path.join(session_path, arch)
            btn = ctk.CTkButton(
                frame,
                text=f"📄 {arch}",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda ra=ruta_arch: self.view_file_content(ra)
            )
            btn.pack(fill="x", pady=3)

        self.show_console()

    def view_file_content(self, file_path: str):
        """Muestra el contenido de un archivo en la consola."""
        contenido = SessionManager.read_file(file_path)
        self.write_console(f"\n=======================================================")
        self.write_console(f"[*] Visualizando: {os.path.basename(file_path)}")
        self.write_console(f"=======================================================\n")
        self.write_console(contenido)
