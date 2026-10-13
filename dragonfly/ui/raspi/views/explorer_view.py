"""
dragonfly/ui/raspi/views/explorer_view.py - Explorador de evidencias táctil para Raspberry Pi.
"""

import os
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame
from dragonfly.core.session import SessionManager


class ExplorerView(BaseView):
    """
    Vista táctil para explorar sesiones guardadas y revisar archivos .txt y .log.
    """

    def show_sessions(self, base_dir: str, title: str, on_back_callback):
        """Lista las carpetas de sesión en el ScrollableFrame táctil."""
        self.clear_frame()
        self.add_back_button(on_back_callback)

        ttk.Label(self.main_frame, text=title.upper(), style='Title.TLabel').pack(pady=2)

        sesiones = SessionManager.list_sessions(base_dir)
        if not sesiones:
            ttk.Label(self.main_frame, text="No hay sesiones.", style='Gray.TLabel').pack(pady=10)
            return

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for s in sesiones:
            ruta = os.path.join(base_dir, s)
            scroll.add_button(
                text=f"📁 {s}",
                style='Gray.TButton',
                command=lambda r=ruta, s_title=title, cb=on_back_callback: self.show_files(r, s_title, cb)
            )

    def show_files(self, session_path: str, title: str, on_back_callback):
        """Lista los archivos de una sesión específica."""
        self.clear_frame()
        base_dir = os.path.dirname(session_path)
        self.add_back_button(lambda: self.show_sessions(base_dir, title, on_back_callback))

        nombre_sesion = os.path.basename(session_path)
        ttk.Label(self.main_frame, text=nombre_sesion[:25], style='Title.TLabel').pack(pady=2)

        archivos = SessionManager.list_session_files(session_path)
        if not archivos:
            ttk.Label(self.main_frame, text="Sesión vacía.", style='Gray.TLabel').pack(pady=10)
            return

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for arch in archivos:
            ruta_arch = os.path.join(session_path, arch)
            scroll.add_button(
                text=f"📄 {arch}",
                style='Red.TButton',
                command=lambda ra=ruta_arch: self.view_file(ra)
            )

        self.show_console(parent=scroll.scrollable_frame)

    def view_file(self, file_path: str):
        """Vuelca el contenido del archivo en la consola."""
        contenido = SessionManager.read_file(file_path)
        self.write_console(f"--- {os.path.basename(file_path)} ---")
        self.write_console(contenido)
