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

    def render(self):
        """Menú de control de PoisonTap."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="POISON (RED USB)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button("Lanzar Ataque Poison", lambda: self.services.poison.start_attack(on_output=self.write_console), style='Danger.TButton', width=28)
        scroll.add_button("Detener Ataque", lambda: self.services.poison.stop_attack(on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Explorar Logs Guardados", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_POISON, "Logs Poison", self.render), style='Gray.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)
