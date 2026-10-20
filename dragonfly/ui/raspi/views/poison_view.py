"""
dragonfly/ui/raspi/views/poison_view.py - Vista de envenenamiento de red USB (PoisonTap) para Raspberry Pi.
"""

import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame
from dragonfly.config import BASE_DIR_POISON


class PoisonView(BaseView):
    """
    Vista táctil para controlar el ataque de envenenamiento de red USB (PoisonTap).
    """

    def __init__(self, app):
        super().__init__(app)
        self.btn_lanzar = None
        self.btn_detener = None

    def render(self):
        """Menú de control de PoisonTap."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="POISON (RED USB)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_lanzar = scroll.add_button(
            "Lanzar Ataque Poison",
            self._on_start_attack,
            style='Danger.TButton',
            width=28
        )
        self.btn_detener = scroll.add_button(
            "Detener Ataque",
            self._on_stop_attack,
            style='Gray.TButton',
            width=28
        )
        # El botón Detener inicia bloqueado en gris
        if self.btn_detener:
            self.btn_detener.state(['disabled'])

        scroll.add_button("Explorar Logs Guardados", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_POISON, "Logs Poison", self.render), style='Gray.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

        # Si se vuelve a entrar a la vista con el ataque activo, reflejar el estado
        if self.services.poison.is_running:
            self._apply_attack_state(True)

    def _apply_attack_state(self, running: bool):
        """Alterna visualmente los botones Lanzar/Detener según el estado del ataque."""
        if self.btn_lanzar and self.btn_lanzar.winfo_exists():
            if running:
                self.btn_lanzar.config(style='Gray.TButton')
                self.btn_lanzar.state(['disabled'])
            else:
                self.btn_lanzar.config(style='Danger.TButton')
                self.btn_lanzar.state(['!disabled'])
        if self.btn_detener and self.btn_detener.winfo_exists():
            if running:
                self.btn_detener.config(style='Danger.TButton')
                self.btn_detener.state(['!disabled'])
            else:
                self.btn_detener.config(style='Gray.TButton')
                self.btn_detener.state(['disabled'])

    def _on_start_attack(self):
        if self.services.poison.is_running:
            return

        # Bloquear Lanzar y habilitar Detener ANTES de arrancar el ataque
        self._apply_attack_state(True)

        started = self.services.poison.start_attack(
            on_output=self.write_console,
            on_finish=lambda: self.run_on_ui(lambda: self._apply_attack_state(False))
        )
        if not started:
            self._apply_attack_state(False)

    def _on_stop_attack(self):
        # Deshabilitar al instante para evitar doble pulsación
        if self.btn_detener and self.btn_detener.winfo_exists():
            self.btn_detener.config(style='Gray.TButton')
            self.btn_detener.state(['disabled'])

        self.services.poison.stop_attack(on_output=self.write_console)
        self._apply_attack_state(False)
