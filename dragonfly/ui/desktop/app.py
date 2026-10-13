"""
dragonfly/ui/desktop/app.py - Ventana principal y controlador de la edición de escritorio.
Integra la barra lateral, el contenedor de vistas y la consola unificada con CustomTkinter.
"""

import os
import customtkinter as ctk
from dragonfly.services import ServiceContainer
from dragonfly.ui.desktop.theme import (
    COLOR_FONDO_SIDEBAR,
    COLOR_FONDO_PRINCIPAL,
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_TEXTO_TERMINAL,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER
)
from dragonfly.ui.desktop.views import (
    InicioView,
    ReconView,
    MacView,
    WiFiView,
    GadgetsView,
    CrackingView,
    UtilsView,
    ExplorerView
)


class DesktopApp(ctk.CTk):
    """
    Aplicación de escritorio DragonFly System con interfaz Red Team en Dark Mode.
    """

    def __init__(self):
        super().__init__()

        self.title("DRAGON FLY - RED TEAM TOOLBOX")

        # Configuración de dimensiones y modo pantalla completa
        self.withdraw()
        ancho = self.winfo_screenwidth()
        alto = self.winfo_screenheight()
        self.geometry(f"{ancho}x{alto}+0+0")
        self.deiconify()

        def aplicar_kiosco():
            try:
                self.attributes('-fullscreen', True)
                self.attributes('-topmost', True)
                self.lift()
                self.focus_force()
                self.update_idletasks()
                self.event_generate('<Motion>', warp=True, x=ancho // 2, y=alto // 2)
            except Exception:
                pass

        self.after(1000, aplicar_kiosco)
        self.bind("<Escape>", lambda event: self.destroy())

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Instanciar contenedor de servicios compartidos
        self.services = ServiceContainer()

        # 2. Construir barra lateral (Sidebar)
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=15, fg_color=COLOR_FONDO_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="DRAGON FLY\nSYSTEM",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#ff4d4d"
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 15))

        # 3. Construir contenedor principal (Main Frame)
        self.main_frame = ctk.CTkScrollableFrame(self, corner_radius=15, fg_color=COLOR_FONDO_PRINCIPAL)
        self.main_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")

        # 4. Elementos dinámicos (Consola y botón Atrás)
        self.console_textbox = None
        self.back_btn = None

        # 5. Instanciar vistas modulares
        self.views = {
            'inicio': InicioView(self),
            'recon': ReconView(self),
            'mac': MacView(self),
            'wifi': WiFiView(self),
            'gadgets': GadgetsView(self),
            'cracking': CrackingView(self),
            'utils': UtilsView(self),
            'explorer': ExplorerView(self)
        }

        # 6. Registrar botones de navegación
        self._crear_botones_sidebar()

        # 7. Iniciar con Splash Screen
        self.views['inicio'].render_splash()

    def _crear_botones_sidebar(self):
        """Crea los botones de la barra lateral izquierda."""
        botones = [
            ("0. Inicio", lambda: self.views['inicio'].render, 1),
            ("1. Reconocimiento", lambda: self.views['recon'].render, 2),
            ("2. MAC Changer", lambda: self.views['mac'].render, 3),
            ("3. Auditoría WiFi", lambda: self.views['wifi'].render, 4),
            ("4. Cracking WPA", lambda: self.views['cracking'].render, 5),
            ("5. NRF24 Jammer", lambda: self.views['gadgets'].render, 6),
            ("6. Utilidades OS", lambda: self.views['utils'].render, 7),
        ]

        for texto, cmd_factory, fila in botones:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=texto,
                command=cmd_factory(),
                fg_color="transparent",
                border_width=2,
                border_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            btn.grid(row=fila, column=0, padx=15, pady=8, sticky="ew")

    def clear_main_frame(self):
        """Limpia todos los widgets del panel principal."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.back_btn = None
        self.console_textbox = None

    def add_back_button(self, callback):
        """Agrega botón de retroceso en la parte superior."""
        self.back_btn = ctk.CTkButton(
            self.main_frame,
            text="← Atrás",
            width=80,
            fg_color=COLOR_BOTON_GRIS,
            hover_color=COLOR_BOTON_GRIS_HOVER,
            command=callback
        )
        self.back_btn.pack(anchor="nw", padx=10, pady=5)

    def show_console(self):
        """Inicializa y empaca la consola de salida gráfica."""
        if self.console_textbox is None or not self.console_textbox.winfo_exists():
            self.console_textbox = ctk.CTkTextbox(
                self.main_frame,
                font=ctk.CTkFont(family="Courier", size=13),
                fg_color="#0a0a0a",
                text_color=COLOR_TEXTO_TERMINAL,
                corner_radius=12,
                height=250
            )
            self.console_textbox.pack(fill="both", expand=True, padx=20, pady=(15, 20))

    def write_console(self, text: str):
        """Escribe texto en la consola de manera segura."""
        def append():
            try:
                if self.console_textbox and self.console_textbox.winfo_exists():
                    self.console_textbox.insert("end", text + "\n")
                    self.console_textbox.see("end")
            except Exception:
                pass
        self.after(0, append)


def run_desktop_app():
    """Función de arranque de la aplicación de escritorio."""
    app = DesktopApp()
    app.mainloop()


if __name__ == "__main__":
    run_desktop_app()
