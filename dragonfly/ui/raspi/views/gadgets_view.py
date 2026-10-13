"""
dragonfly/ui/raspi/views/gadgets_view.py - Vista de hardware NRF24 y Sub-1GHz para Raspberry Pi.
"""

import threading
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame


class GadgetsView(BaseView):
    """
    Vista de control para módulos de radiofrecuencia NRF24 y Sub-1GHz (CC1101).
    """

    def render(self):
        """Menú del NRF24 Jammer (ESP32)."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="NRF24 JAMMER (ESP32)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button("Iniciar Sweep Jamming (2.4GHz)", lambda: self.services.jammer.start_sweep_jam(on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Detener Jamming", lambda: self.services.jammer.stop_sweep_jam(on_output=self.write_console), style='Danger.TButton', width=28)
        scroll.add_button("Reconectar Gadget USB", self.render, style='Gray.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

    def render_sub1ghz(self):
        """Menú de Sub-1GHz RF (CC1101)."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="SUB-1GHZ RF (CC1101)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button("Escanear Frecuencias", lambda: self.services.sub1ghz.send_rf_command("SCAN", on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Frecuencia 433.92 MHz", lambda: self.services.sub1ghz.send_rf_command("FREQ 433920000", on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Frecuencia 315.00 MHz", lambda: self.services.sub1ghz.send_rf_command("FREQ 315000000", on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Frecuencia 868.35 MHz", lambda: self.services.sub1ghz.send_rf_command("FREQ 868350000", on_output=self.write_console), style='Red.TButton', width=28)
        scroll.add_button("Detener Transmisión", lambda: self.services.sub1ghz.send_rf_command("STOP", on_output=self.write_console), style='Danger.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)
