"""
dragonfly/ui/raspi/views/mac_view.py - Vista de MAC Changer para Raspberry Pi.
Permite cambiar la MAC a aleatoria, de fábrica o manual mediante TecladoCompleto.
"""

import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame, TecladoCompleto


class MacView(BaseView):
    """
    Vista de spoofing de direcciones físicas (MAC) para Raspberry Pi.
    """

    def __init__(self, app):
        super().__init__(app)
        self.interfaz_var = tk.StringVar(value="")

    def render(self):
        """Dibuja el menú de MAC Changer."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="DIRECCION MAC", style='Title.TLabel').pack(pady=2)

        interfaces = self.services.mac.get_interfaces()
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces.", style='Dark.TLabel').pack()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if not self.interfaz_var.get() or self.interfaz_var.get() not in interfaces:
            self.interfaz_var.set(interfaces[0])

        sel_frame = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        sel_frame.pack(pady=3)
        ttk.Label(sel_frame, text="Iface: ", style='Dark.TLabel').pack(side='left')
        ttk.OptionMenu(sel_frame, self.interfaz_var, self.interfaz_var.get(),
                       *interfaces, style='Dark.TMenubutton').pack(side='left')

        scroll.add_button("Ver Estado", self._on_status, style='Red.TButton', width=28)
        scroll.add_button("MAC Random", self._on_random, style='Red.TButton', width=28)
        scroll.add_button("Reset Original", self._on_reset, style='Red.TButton', width=28)
        scroll.add_button("Mismo Fabricante", self._on_same_vendor, style='Red.TButton', width=28)
        scroll.add_button("MAC Personalizada", self._on_custom, style='Danger.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

    def _on_status(self):
        self.services.mac.show_status(self.interfaz_var.get(), on_output=self.write_console)

    def _on_random(self):
        self.services.mac.set_random(self.interfaz_var.get(), on_output=self.write_console)

    def _on_reset(self):
        self.services.mac.reset_original(self.interfaz_var.get(), on_output=self.write_console)

    def _on_same_vendor(self):
        self.services.mac.set_same_vendor(self.interfaz_var.get(), on_output=self.write_console)

    def _on_custom(self):
        var_mac = tk.StringVar()
        teclado = TecladoCompleto(self.app, var_mac, titulo="MAC (ej. 00:11...)")
        self.app.wait_window(teclado)
        nueva_mac = var_mac.get().strip()

        if nueva_mac == "CANCELADO" or not nueva_mac:
            self.write_console("[*] Cancelado.")
            return

        self.services.mac.set_custom(self.interfaz_var.get(), nueva_mac, on_output=self.write_console)
