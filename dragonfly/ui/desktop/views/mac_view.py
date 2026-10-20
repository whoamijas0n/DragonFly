"""
dragonfly/ui/desktop/views/mac_view.py - Vista de manipulación y spoofing de direcciones MAC para Desktop.
"""

import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_PELIGRO_HOVER
)


class MacView(BaseView):
    """
    Vista para visualizar y modificar la dirección MAC de interfaces de red.
    """

    def __init__(self, app):
        super().__init__(app)
        self.interfaz_seleccionada_var = ctk.StringVar(value="")

    def render(self):
        """Dibuja el selector de interfaz y los botones de acción de MAC."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="DIRECCION MAC (MAC CHANGER)",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 15))

        interfaces = self.services.mac.get_interfaces()
        if not interfaces:
            ctk.CTkLabel(self.main_frame, text="No se detectaron interfaces de red.",
                         text_color="#aaaaaa").pack(pady=20)
            return

        if not self.interfaz_seleccionada_var.get() or self.interfaz_seleccionada_var.get() not in interfaces:
            self.interfaz_seleccionada_var.set(interfaces[0])

        sel_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        sel_frame.pack(pady=5)
        ctk.CTkLabel(sel_frame, text="Interfaz: ").pack(side="left")
        ctk.CTkOptionMenu(
            sel_frame,
            variable=self.interfaz_seleccionada_var,
            values=interfaces,
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(side="left")

        # Botones de acción
        ctk.CTkButton(
            self.main_frame, text="Ver Estado",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, width=320,
            command=self._on_status
        ).pack(pady=5)

        ctk.CTkButton(
            self.main_frame, text="MAC Random (Aleatoria)",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, width=320,
            command=self._on_random
        ).pack(pady=5)

        ctk.CTkButton(
            self.main_frame, text="Reset Original (Fábrica)",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, width=320,
            command=self._on_reset
        ).pack(pady=5)

        ctk.CTkButton(
            self.main_frame, text="MAC Mismo Fabricante (OUI)",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, width=320,
            command=self._on_same_vendor
        ).pack(pady=5)

        ctk.CTkButton(
            self.main_frame, text="MAC Personalizada",
            fg_color=COLOR_BOTON_PELIGRO, hover_color=COLOR_BOTON_PELIGRO_HOVER, width=320,
            command=self._on_custom
        ).pack(pady=5)

        self.show_console()

    def _on_status(self):
        iface = self.interfaz_seleccionada_var.get()
        self.services.mac.show_status(iface, on_output=self.write_console)

    def _on_random(self):
        iface = self.interfaz_seleccionada_var.get()
        self.services.mac.set_random(iface, on_output=self.write_console)

    def _on_reset(self):
        iface = self.interfaz_seleccionada_var.get()
        self.services.mac.reset_original(iface, on_output=self.write_console)

    def _on_same_vendor(self):
        iface = self.interfaz_seleccionada_var.get()
        self.services.mac.set_same_vendor(iface, on_output=self.write_console)

    def _on_custom(self):
        dialog = ctk.CTkInputDialog(text="Ingrese la nueva dirección MAC (XX:XX:XX:XX:XX:XX):", title="MAC Personalizada")
        custom_mac = dialog.get_input()
        if custom_mac:
            iface = self.interfaz_seleccionada_var.get()
            self.services.mac.set_custom(iface, custom_mac, on_output=self.write_console)
