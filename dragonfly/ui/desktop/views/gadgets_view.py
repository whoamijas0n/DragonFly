"""
dragonfly/ui/desktop/views/gadgets_view.py - Vista de periféricos de hardware RF y NRF24 Jammer para Desktop.
"""

import threading
import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_PELIGRO_HOVER,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER,
    COLOR_ESTADO_ACTIVO,
    COLOR_ESTADO_INACTIVO
)


class GadgetsView(BaseView):
    """
    Vista de interacción con hardware microcontrolado externo (ESP32 / NRF24).
    """

    def __init__(self, app):
        super().__init__(app)
        self.btn_jam_start = None
        self.btn_jam_stop = None

    def render(self):
        """Muestra el panel de control del NRF24 Jammer con detección asíncrona."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="NRF24 JAMMER (ESP32 BLUE-FLY)",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 5))

        loading_lbl = ctk.CTkLabel(self.main_frame, text="Detectando/sincronizando hardware por USB...", text_color="#aaaaaa")
        loading_lbl.pack(pady=20)
        self.show_console()

        def async_check():
            conectado = self.services.jammer.is_connected()
            if conectado:
                # Validar el handle con un round-trip real: evita mostrar
                # "Conectado" con un puerto huérfano o un ESP32 reiniciado.
                conectado = self.services.jammer.ping()
            if not conectado:
                g = self.services.jammer.get_gadget(force_reconnect=True)
                conectado = g.is_available() if g else False
            puerto = self.services.jammer.get_port()
            self.run_on_ui(lambda: self._build_interface(conectado, puerto))

        threading.Thread(target=async_check, daemon=True).start()

    def _build_interface(self, conectado: bool, puerto: str = None):
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="NRF24 JAMMER (ESP32 BLUE-FLY)",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)

        estado_txt = f"Conectado ({puerto})" if (conectado and puerto) else ("Conectado" if conectado else "Desconectado")
        estado_color = COLOR_ESTADO_ACTIVO if conectado else COLOR_ESTADO_INACTIVO

        ctk.CTkLabel(
            self.main_frame,
            text=f"Estado del Dispositivo: {estado_txt}",
            text_color=estado_color,
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=(2, 15))

        if conectado:
            self.btn_jam_start = ctk.CTkButton(
                self.main_frame,
                text="Activar Sweep Jamming (2.4 GHz)",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                height=40,
                command=self._on_start_jam
            )
            self.btn_jam_start.pack(fill="x", padx=40, pady=5)

            self.btn_jam_stop = ctk.CTkButton(
                self.main_frame,
                text="Detener Jamming",
                fg_color=COLOR_BOTON_PELIGRO,
                hover_color=COLOR_BOTON_PELIGRO_HOVER,
                height=40,
                command=self._on_stop_jam
            )
            self.btn_jam_stop.pack(fill="x", padx=40, pady=5)

            ctk.CTkButton(
                self.main_frame,
                text="Consultar Estado",
                fg_color=COLOR_BOTON_GRIS,
                hover_color=COLOR_BOTON_GRIS_HOVER,
                height=40,
                command=self._on_status
            ).pack(fill="x", padx=40, pady=5)

            ctk.CTkButton(
                self.main_frame,
                text="Reconectar / Sincronizar",
                fg_color=COLOR_BOTON_GRIS,
                hover_color=COLOR_BOTON_GRIS_HOVER,
                height=40,
                command=self._async_reconnect
            ).pack(fill="x", padx=40, pady=5)
        else:
            ctk.CTkLabel(
                self.main_frame,
                text="Conecta el ESP32 configurado con el firmware NRF24 al puerto USB.",
                text_color="#aaaaaa"
            ).pack(pady=10)

            ctk.CTkButton(
                self.main_frame,
                text="Buscar Dispositivo",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                height=40,
                command=self._async_reconnect
            ).pack(fill="x", padx=40, pady=10)

        self.show_console()

    def _async_reconnect(self):
        self.write_console("[*] Buscando dispositivo...")

        def do_reconnect():
            g = self.services.jammer.get_gadget(force_reconnect=True)
            conectado = g.is_available() if g else False
            puerto = self.services.jammer.get_port()
            if not conectado:
                self.run_on_ui(lambda: self.write_console("[!] No se detectó el hardware."))
            else:
                p_text = f" en {puerto}" if puerto else ""
                self.run_on_ui(lambda: self.write_console(f"[+] Gadget NRF24 conectado{p_text}."))
            self.run_on_ui(lambda: self._build_interface(conectado, puerto))

        threading.Thread(target=do_reconnect, daemon=True).start()

    def _on_start_jam(self):
        threading.Thread(
            target=lambda: self.services.jammer.start_sweep_jam(on_output=self.write_console),
            daemon=True
        ).start()

    def _on_stop_jam(self):
        threading.Thread(
            target=lambda: self.services.jammer.stop_sweep_jam(on_output=self.write_console),
            daemon=True
        ).start()

    def _on_status(self):
        threading.Thread(
            target=lambda: self.services.jammer.get_status(on_output=self.write_console),
            daemon=True
        ).start()
