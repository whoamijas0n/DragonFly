"""
dragonfly/ui/desktop/views/inicio_view.py - Pantalla de inicio y animación de splash para Desktop.
"""

import random
import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.config import ARTE_DRAGON


class InicioView(BaseView):
    """
    Vista de bienvenida con animación y arte ASCII en rojo.
    """

    def __init__(self, app):
        super().__init__(app)
        self.ruido_chars = ["░", "▒", "▓", "█", "#", "@", "%", "*"]
        self.frames_totales = 18
        self.frame_actual = 0
        self.splash_label = None
        self.splash_font = None

    def render_splash(self):
        """Muestra la animación inicial de decodificación digital."""
        self.clear_frame()
        container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        self.splash_font = ctk.CTkFont(family="Courier", size=14, weight="bold")
        self.splash_label = ctk.CTkLabel(
            container,
            text="",
            font=self.splash_font,
            text_color="#ff4d4d",
            justify="center"
        )
        self.splash_label.pack(pady=10, fill="both", expand=True)

        lineas_ascii = ARTE_DRAGON.split('\n')
        max_caracteres = max(len(linea) for linea in lineas_ascii) if lineas_ascii else 100

        def adaptar_arte_ascii(event):
            if event.width > 50:
                nuevo_tamano = int((event.width * 0.95) / (max_caracteres * 0.6))
                nuevo_tamano = max(3, min(nuevo_tamano, 18))
                if self.splash_font.cget("size") != nuevo_tamano:
                    self.splash_font.configure(size=nuevo_tamano)

        container.bind("<Configure>", adaptar_arte_ascii)
        self.frame_actual = 0
        self._animar_splash()

    def _animar_splash(self):
        if self.frame_actual > self.frames_totales:
            self.app.after(500, self.render)
            return

        nivel_ruido = 1.0 - (self.frame_actual / self.frames_totales)
        texto_borroso = ""

        for char in ARTE_DRAGON:
            if char not in (" ", "\n"):
                if random.random() < nivel_ruido:
                    texto_borroso += random.choice(self.ruido_chars)
                else:
                    texto_borroso += char
            else:
                texto_borroso += char

        if self.splash_label and self.splash_label.winfo_exists():
            self.splash_label.configure(text=texto_borroso)
            self.frame_actual += 1
            self.app.after(80, self._animar_splash)

    def render(self):
        """Muestra la pantalla de inicio principal."""
        self.clear_frame()
        container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        titulo = ctk.CTkLabel(
            container,
            text="BIENVENIDO A DRAGONFLY SYSTEM",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#ff4d4d"
        )
        titulo.pack(pady=(30, 10))

        subtitulo = ctk.CTkLabel(
            container,
            text="Red Team Toolbox - Auditoría y Pentesting",
            font=ctk.CTkFont(size=16),
            text_color="#aaaaaa"
        )
        subtitulo.pack(pady=(0, 30))

        ascii_font = ctk.CTkFont(family="Courier", size=14, weight="bold")
        ascii_label = ctk.CTkLabel(
            container,
            text=ARTE_DRAGON,
            font=ascii_font,
            text_color="#ff4d4d",
            justify="center"
        )
        ascii_label.pack(pady=10, fill="x", expand=True)

        lineas_ascii = ARTE_DRAGON.split('\n')
        max_caracteres = max(len(linea) for linea in lineas_ascii) if lineas_ascii else 100

        def adaptar_arte_ascii(event):
            if event.width > 50:
                nuevo_tamano = int((event.width * 0.95) / (max_caracteres * 0.6))
                nuevo_tamano = max(3, min(nuevo_tamano, 18))
                if ascii_font.cget("size") != nuevo_tamano:
                    ascii_font.configure(size=nuevo_tamano)

        container.bind("<Configure>", adaptar_arte_ascii)

        ctk.CTkFrame(container, height=2, fg_color="#ff4d4d").pack(fill="x", padx=50, pady=20)

        footer = ctk.CTkLabel(
            container,
            text="Selecciona una herramienta del menú lateral para comenzar.",
            font=ctk.CTkFont(size=14),
            text_color="#888888"
        )
        footer.pack(pady=20)
