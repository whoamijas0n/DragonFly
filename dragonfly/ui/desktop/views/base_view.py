"""
dragonfly/ui/desktop/views/base_view.py - Clase base para las vistas modulares de Desktop.
Proporciona acceso a los servicios compartidos y métodos auxiliares de interfaz.
"""

import customtkinter as ctk
from dragonfly.ui.desktop.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_DESHABILITADO,
    COLOR_TEXTO_TERMINAL
)


class BaseView:
    """
    Vista base con utilidades de manipulación del main_frame, consola y navegación.
    """

    def __init__(self, app):
        self.app = app
        self.services = app.services
        self.main_frame = app.main_frame

    def render(self):
        """Método a implementar por cada vista para renderizar su contenido."""
        raise NotImplementedError

    def clear_frame(self):
        """Limpia el contenedor principal."""
        self.app.clear_main_frame()

    def add_back_button(self, callback):
        """Agrega botón de retorno."""
        self.app.add_back_button(callback)

    def show_console(self):
        """Asegura que la consola esté visible."""
        self.app.show_console()

    def write_console(self, text: str):
        """Escribe una línea en la consola gráfica."""
        self.app.write_console(text)

    def run_on_ui(self, callback):
        """Ejecuta una función en el hilo principal de Tkinter."""
        self.app.after(0, callback)
