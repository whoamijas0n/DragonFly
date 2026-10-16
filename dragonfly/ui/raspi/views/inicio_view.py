"""
dragonfly/ui/raspi/views/inicio_view.py - Menú de inicio y splash screen para Raspberry Pi.
Diseñado para navegación táctil con el pulgar en pantallas de 320x240.
"""

import random
import tkinter as tk
from tkinter import ttk
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame, crear_separador
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_ROJO_BRIGHT,
    COLOR_TEXTO_SECUNDARIO,
    COLOR_TEXTO_TERMINAL,
    FONT_TITLE,
    FONT_MICRO,
    FONT_BODY_B
)
from dragonfly.config import ARTE_DRAGON, DIR_ICONS
import os


class InicioView(BaseView):
    """
    Pantalla de inicio con animación de glitch de inicio y menú táctil principal con iconos.
    """

    def __init__(self, app):
        super().__init__(app)
        self.ruido_chars = ["░", "▒", "▓", "█", "#", "@", "%", "*"]
        self.frames_totales = 14
        self.frame_actual = 0
        self.splash_label = None
        self.icon_cache = {}
        self.current_icon_refs = []

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
        """Menú principal táctil con iconos responsivos."""
        self.clear_frame()

        # Cabecera
        ttk.Label(self.main_frame, text="DRAGON FLY SYSTEM", style='Title.TLabel').pack(pady=(8, 2))
        ttk.Label(self.main_frame, text="Red Team Toolbox", style='Gray.TLabel').pack(pady=(0, 6))

        # Detección dinámica de resolución
        ancho_actual = self.app.winfo_width()
        if ancho_actual <= 1:
            ancho_actual = self.app.winfo_screenwidth()

        if ancho_actual <= 320:
            columnas = 2
            tamano_icono = (44, 44)
            padding_celda = 6
        elif ancho_actual <= 480:
            columnas = 3
            tamano_icono = (54, 54)
            padding_celda = 10
        else:
            columnas = 4
            tamano_icono = (72, 72)
            padding_celda = 16

        # ScrollableFrame para habilitar scroll si hay desbordamiento vertical
        scroll_menu = ScrollableFrame(self.main_frame)
        scroll_menu.pack(fill='both', expand=True, padx=2, pady=2)

        # Grid principal
        grid_frame = ttk.Frame(scroll_menu.scrollable_frame, style='Dark.TFrame')
        grid_frame.pack(fill='both', expand=True, padx=4, pady=4)

        opciones = [
            ("Recon", self.app.views['recon'].render, "recon.png"),
            ("MAC Changer", self.app.views['mac'].render, "mac.png"),
            ("Auditoría WiFi", self.app.views['wifi'].render, "wifi.png"),
            ("NRF24 Jammer", self.app.views['gadgets'].render, "jammer.png"),
            ("Rubber Ducky", self.app.views['ducky'].render, "ducky.png"),
            ("PoisonTap", self.app.views['poison'].render, "poison.png"),
            ("Utilidades OS", self.app.views['utils'].render, "utils.png"),
            ("Autodestrucción", self.show_self_destruct_menu, "destroy.png")
        ]

        # Evita que el GC destruya las referencias de imagen
        self.current_icon_refs = []

        for index, (texto, comando, icono_archivo) in enumerate(opciones):
            fila = index // columnas
            columna = index % columnas

            photo = None
            if HAS_PIL:
                icono_ruta = os.path.join(DIR_ICONS, icono_archivo)
                cache_key = (icono_ruta, tamano_icono)

                if cache_key in self.icon_cache:
                    photo = self.icon_cache[cache_key]
                else:
                    try:
                        img = Image.open(icono_ruta).resize(tamano_icono, Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self.icon_cache[cache_key] = photo
                    except Exception:
                        try:
                            img = Image.new('RGBA', tamano_icono, (0, 0, 0, 0))
                            photo = ImageTk.PhotoImage(img)
                            self.icon_cache[cache_key] = photo
                        except Exception:
                            photo = None

            if photo is not None:
                self.current_icon_refs.append(photo)
                texto_con_espacio = f"\n{texto}"
                btn = ttk.Button(grid_frame, text=texto_con_espacio, image=photo, compound="top",
                                 style='AppIcon.TButton', command=comando)
            else:
                btn = ttk.Button(grid_frame, text=texto, style='Menu.TButton', command=comando)

            btn.grid(row=fila, column=columna, padx=padding_celda, pady=padding_celda, sticky="nsew")

            grid_frame.grid_columnconfigure(columna, weight=1)
            grid_frame.grid_rowconfigure(fila, weight=1)

    def show_self_destruct_menu(self):
        """Submenú de confirmación de autodestrucción."""
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="AUTODESTRUCCIÓN", style='Title.TLabel').pack(pady=2)

        scroll_destruct = ScrollableFrame(self.main_frame, max_items=10)
        scroll_destruct.pack(fill='both', expand=True, padx=2, pady=2)

        mensaje = ("Esto ELIMINARÁ TODOS LOS DATOS\nde la tarjeta SD.\n\n"
                   "El sistema quedará INUTILIZABLE.\n\n"
                   "¿Estás ABSOLUTAMENTE SEGURO?")

        lbl_advertencia = ttk.Label(scroll_destruct.scrollable_frame, text=mensaje,
                                    style='Dark.TLabel', wraplength=280, justify='center')
        scroll_destruct.add_widget(lbl_advertencia, pady=(10, 15))

        def ejecutar_destruccion():
            self.write_console("[!] Iniciando autodestrucción...")
            self.app.destroy()

        scroll_destruct.add_button(text="SÍ, DESTRUIR TODO",
                                   command=ejecutar_destruccion,
                                   style='Red.TButton', width=28)
        scroll_destruct.add_button(text="NO, VOLVER AL MENÚ",
                                   command=self.render,
                                   style='Gray.TButton', width=28)
        self.show_console(parent=scroll_destruct.scrollable_frame)
