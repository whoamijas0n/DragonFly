"""
dragonfly/ui/raspi/app.py - Ventana raíz y controlador de la edición Raspberry Pi (Tkinter).
Diseñado específicamente para pantalla TFT de 320x240 táctil (GPIO/SPI) en Raspberry Pi OS Lite.
"""

import gc
import tkinter as tk
from tkinter import ttk
from dragonfly.services import ServiceContainer
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_FONDO_BASE,
    COLOR_TEXTO_TERMINAL,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER,
    setup_ttk_styles
)
from dragonfly.ui.raspi.widgets import crear_statusbar
from dragonfly.ui.raspi.views import (
    InicioView,
    ReconView,
    MacView,
    WiFiView,
    GadgetsView,
    DuckyView,
    PoisonView,
    UtilsView,
    ExplorerView
)


class RaspiApp(tk.Tk):
    """
    Aplicación principal para Raspberry Pi Zero 2 WH optimizada para pantalla táctil de 320x240.
    """

    def __init__(self):
        super().__init__()

        self.title("DRAGON FLY - RED TEAM TOOLBOX")

        screen_width = self.winfo_screenwidth() or 320
        screen_height = self.winfo_screenheight() or 240
        self.geometry(f"{screen_width}x{screen_height}+0+0")
        self.configure(bg=COLOR_FONDO_PRINCIPAL)

        # Configuración de estilos ttk clam
        self.style = setup_ttk_styles()

        # Tecla Escape para salir
        self.bind("<Escape>", lambda event: self.destroy())

        # Contenedor de servicios de backend compartidos
        self.services = ServiceContainer()

        # Barra de estado inferior HUD
        self.statusbar_frame, self.lbl_ip, self.lbl_iface = crear_statusbar(self)

        # Contenedor principal para vistas
        self.main_frame = tk.Frame(self, bg=COLOR_FONDO_PRINCIPAL)
        self.main_frame.pack(fill='both', expand=True)

        # Variables de búfer de consola táctil
        self.console_frame = None
        self.console_textbox = None
        self.console_scrollbar = None
        self.console_buffer = []
        self.console_pending = False
        self._console_after_id = None
        self._console_drag_start_y = 0

        # Botón atrás
        self.back_btn = None

        # Instanciar vistas
        self.views = {
            'inicio': InicioView(self),
            'recon': ReconView(self),
            'mac': MacView(self),
            'wifi': WiFiView(self),
            'gadgets': GadgetsView(self),
            'ducky': DuckyView(self),
            'poison': PoisonView(self),
            'utils': UtilsView(self),
            'explorer': ExplorerView(self)
        }

        # Actualizar HUD de estado en segundo plano
        self._actualizar_hud()

        # Iniciar con animación de splash
        self.views['inicio'].render_splash()

    def _actualizar_hud(self):
        """Actualiza la IP activa en el HUD inferior."""
        try:
            ip = self.services.recon.get_auto_ip()
            self.lbl_ip.config(text=f" [NET] {ip}")
            ifaces = self.services.mac.get_interfaces()
            if ifaces:
                self.lbl_iface.config(text=f"{ifaces[0]} ●")
        except Exception:
            pass

    def limpiar_main_frame(self):
        """Limpia el contenido del main frame y fuerza recolección de basura."""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.back_btn = None
        self.console_frame = None
        self.console_textbox = None
        gc.collect()

    def agregar_boton_atras(self, callback):
        """Agrega botón Atrás en la esquina superior izquierda."""
        self.back_btn = ttk.Button(self.main_frame, text="← Atrás", style='Gray.TButton', command=callback)
        self.back_btn.pack(anchor="nw", padx=2, pady=2)

    def mostrar_consola(self, parent=None):
        """Crea la consola táctil con buffer y scroll en el contenedor especificado."""
        if parent is None:
            parent = self.main_frame

        self.console_frame = tk.Frame(
            parent,
            bg='#050505',
            highlightbackground="#333333",
            highlightcolor="#333333",
            highlightthickness=1
        )
        self.console_frame.pack(fill='x', padx=4, pady=4)

        self.console_textbox = tk.Text(
            self.console_frame,
            height=4,
            bg='#050505',
            fg=COLOR_TEXTO_TERMINAL,
            font=('Courier', 8, 'bold'),
            state='disabled',
            highlightthickness=0,
            borderwidth=0,
            relief='flat'
        )

        self.console_scrollbar = ttk.Scrollbar(
            self.console_frame,
            orient="vertical",
            command=self.console_textbox.yview,
            style='Dark.Vertical.TScrollbar'
        )

        self.console_textbox.configure(yscrollcommand=self.console_scrollbar.set)
        self.console_scrollbar.pack(side="right", fill="y")
        self.console_textbox.pack(side="left", fill="x", expand=True, padx=(3, 0), pady=1)

        self.console_textbox.bind("<Button-1>", self._on_console_touch_start)
        self.console_textbox.bind("<B1-Motion>", self._on_console_touch_drag)

    def _on_console_touch_start(self, event):
        self._console_drag_start_y = event.y

    def _on_console_touch_drag(self, event):
        dy = self._console_drag_start_y - event.y
        if abs(dy) > 3:
            fraction = 1 if dy > 0 else -1
            if self.console_textbox:
                self.console_textbox.yview_scroll(fraction, "units")
            self._console_drag_start_y = event.y

    def escribir_consola(self, texto: str):
        """Agrega texto al buffer y programa un volcado por lotes (batching) cada 500ms."""
        self.console_buffer.append(texto)
        if not self.console_pending:
            self.console_pending = True
            self._console_after_id = self.after(500, self._flush_console)

    def _flush_console(self):
        """Vuelca las líneas del buffer a la caja de texto."""
        self.console_pending = False
        self._console_after_id = None
        if not self.console_textbox or not self.console_textbox.winfo_exists():
            return
        lines = "\n".join(self.console_buffer) + "\n"
        self.console_buffer.clear()
        try:
            self.console_textbox.configure(state='normal')
            self.console_textbox.insert('end', lines)
            self.console_textbox.see('end')
            self.console_textbox.configure(state='disabled')
        except Exception:
            pass


def run_raspi_app():
    """Punto de arranque de la aplicación para Raspberry Pi."""
    app = RaspiApp()
    app.mainloop()


if __name__ == "__main__":
    run_raspi_app()
