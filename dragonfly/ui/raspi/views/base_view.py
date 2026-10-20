"""
dragonfly/ui/raspi/views/base_view.py - Clase base para las vistas de Raspberry Pi (Tkinter).
"""

import threading
import tkinter as tk
from tkinter import ttk


class BaseView:
    """
    Vista base con métodos de acceso a la aplicación principal, contenedor y consola.
    """

    def __init__(self, app):
        self.app = app
        self.services = app.services
        self.main_frame = app.main_frame

    def render(self):
        """Método abstracto a implementar por cada vista."""
        raise NotImplementedError

    def clear_frame(self):
        """Limpia el contenedor principal."""
        self.app.limpiar_main_frame()

    def add_back_button(self, callback):
        """Agrega botón de retroceso superior."""
        self.app.agregar_boton_atras(callback)

    def show_console(self, parent=None):
        """Empaca la terminal gráfica en el contenedor indicado o el principal."""
        self.app.mostrar_consola(parent=parent)

    def write_console(self, text: str):
        """Envía una línea al búfer de consola."""
        self.app.escribir_consola(text)

    def run_on_ui(self, callback):
        """Invoca la función en el hilo de la GUI de forma segura entre hilos."""
        if threading.current_thread() is threading.main_thread():
            callback()
        elif hasattr(self.app, '_ui_queue'):
            self.app._ui_queue.put(callback)
        else:
            try:
                self.app.after(0, callback)
            except Exception:
                pass
