"""
dragonfly/ui/raspi/views/inicio_view.py - Menú de inicio y splash screen para Raspberry Pi.
Diseñado para navegación táctil con el pulgar en pantallas de 320x240.
"""

import random
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame, crear_separador
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_ROJO_BRIGHT,
    COLOR_TEXTO_SECUNDARIO,
    FONT_TITLE,
    FONT_MICRO,
    FONT_BODY_B
)
from dragonfly.config import ARTE_DRAGON


class InicioView(BaseView):
    """
    Pantalla de inicio con animación de glitch de inicio y menú táctil principal.
    """

    def __init__(self, app):
        super().__init__(app)
        self.ruido_chars = ["░", "▒", "▓", "█", "#", "@", "%", "*"]
        self.frames_totales = 14
        self.frame_actual = 0
        self.splash_label = None

    def render_splash(self):
        """Animación de arranque."""
        self.clear_frame()
        self.splash_label = tk.Label(
            self.main_frame,
            text="",
            font=('Courier', 6, 'bold'),
            bg=COLOR_FONDO_PRINCIPAL,
            fg=COLOR_ROJO_BRIGHT,
            justify="center"
        )
        self.splash_label.pack(expand=True, fill="both")
        self.frame_actual = 0
        self._animar_splash()

    def _animar_splash(self):
        if self.frame_actual > self.frames_totales:
            self.app.after(300, self.render)
            return

        nivel_ruido = 1.0 - (self.frame_actual / self.frames_totales)
        texto = ""
        # Tomar un subset de líneas del arte para que quepa en 320x240
        lineas = ARTE_DRAGON.strip().split("\n")[20:45]
        arte_reducido = "\n".join(lineas)

        for char in arte_reducido:
            if char not in (" ", "\n"):
                texto += random.choice(self.ruido_chars) if random.random() < nivel_ruido else char
            else:
                texto += char

        if self.splash_label and self.splash_label.winfo_exists():
            self.splash_label.configure(text=texto)
            self.frame_actual += 1
            self.app.after(70, self._animar_splash)

    def render(self):
        """Menú principal táctil."""
        self.clear_frame()

        # Cabecera
        header = ttk.Frame(self.main_frame, style='Dark.TFrame')
        header.pack(fill='x', padx=4, pady=(2, 0))

        ttk.Label(header, text="DRAGON FLY SYSTEM", style='Title.TLabel').pack()
        ttk.Label(header, text="RED TEAM TOOLBOX", style='Gray.TLabel').pack()
        crear_separador(self.main_frame, padx=4, pady=2)

        # Menú apilado en ScrollableFrame táctil
        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        opciones = [
            ("1. Reconocimiento (Nmap)", self.app.views['recon'].render, 'Red.TButton'),
            ("2. MAC Changer", self.app.views['mac'].render, 'Red.TButton'),
            ("3. Auditoría WiFi", self.app.views['wifi'].render, 'Red.TButton'),
            ("4. Gadget NRF24 Jammer", self.app.views['gadgets'].render, 'Red.TButton'),
            ("5. Sub-1GHz RF", self.app.views['gadgets'].render_sub1ghz, 'Red.TButton'),
            ("6. Rubber Ducky (HID)", self.app.views['ducky'].render, 'Red.TButton'),
            ("7. Poison (Red USB)", self.app.views['poison'].render, 'Red.TButton'),
            ("8. Utilidades OS", self.app.views['utils'].render, 'Red.TButton'),
            ("Salir de DragonFly", self.app.destroy, 'Gray.TButton'),
        ]

        for texto, cmd, estilo in opciones:
            scroll.add_button(text=texto, command=cmd, style=estilo, width=28)
