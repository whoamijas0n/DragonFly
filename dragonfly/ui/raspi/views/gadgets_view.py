"""
dragonfly/ui/raspi/views/gadgets_view.py - Vista de hardware NRF24 y Sub-1GHz para Raspberry Pi.
Optimizado para pantalla TFT de 320x240 con detección asíncrona, soporte hot-plug y manejo de errores.
"""

import gc
import threading
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame
from dragonfly.ui.raspi.theme import FONT_BODY_B


class GadgetsView(BaseView):
    """
    Vista de control para módulos de radiofrecuencia NRF24 (ESP32) y Sub-1GHz (CC1101).
    """

    def render(self):
        """Menú del NRF24 Jammer con detección asíncrona no bloqueante."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="NRF24 JAMMER (ESP32)", style='Title.TLabel').pack(pady=2)

        loading_lbl = ttk.Label(self.main_frame, text="Detectando puerto USB...", style='Gray.TLabel')
        loading_lbl.pack(pady=20)

        def async_check():
            connected = self.services.jammer.is_connected()
            if not connected:
                g = self.services.jammer.get_gadget(force_reconnect=True)
                connected = g.is_available() if g else False
            port = self.services.jammer.get_port()
            self.run_on_ui(lambda: self._build_interface(connected, port, loading_lbl))

        threading.Thread(target=async_check, daemon=True).start()

    def _build_interface(self, connected: bool, port: str = None, loading_lbl=None):
        """Construye la interfaz según el estado de conexión del ESP32."""
        if loading_lbl is not None and loading_lbl.winfo_exists():
            loading_lbl.destroy()

        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)
        ttk.Label(self.main_frame, text="NRF24 JAMMER (ESP32)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=12)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if connected and port:
            status_txt = f"Conectado ({port})"
        elif connected:
            status_txt = "Conectado"
        else:
            status_txt = "Desconectado"

        status_clr = "#00ff00" if connected else "#ff4d4d"
        ttk.Label(
            scroll.scrollable_frame,
            text=f"Estado: {status_txt}",
            foreground=status_clr,
            font=FONT_BODY_B
        ).pack(pady=(2, 8))

        if connected:
            scroll.add_button("Activar Jamming", self._on_start_jam, style='Red.TButton', width=28)
            scroll.add_button("Detener Jamming", self._on_stop_jam, style='Danger.TButton', width=28)
            scroll.add_button("Consultar Estado", self._on_status, style='Gray.TButton', width=28)
            scroll.add_button("Reconectar / Reset", self._async_reconnect, style='Gray.TButton', width=28)
        else:
            ttk.Label(scroll.scrollable_frame, text="Conecta el ESP32 por USB.", style='Gray.TLabel').pack(pady=5)
            scroll.add_button("Buscar Dispositivo", self._async_reconnect, style='Red.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _async_reconnect(self):
        """Maneja la reconexión forzando la limpieza y reinicio del enlace serie."""
        self.write_console("[*] Buscando dispositivo...")

        def do_reconnect():
            g = self.services.jammer.get_gadget(force_reconnect=True)
            connected = g.is_available() if g else False
            port = self.services.jammer.get_port()

            if not connected:
                hint = self.services.jammer.get_usb_mode_hint()

                def _notify():
                    self.write_console("[!] No se detectó el hardware.")
                    if hint:
                        self.write_console(hint)

                self.run_on_ui(_notify)
            else:
                p_text = f" en {port}" if port else ""
                self.run_on_ui(lambda: self.write_console(f"[+] Gadget NRF24 conectado{p_text}."))

            self.run_on_ui(lambda: self._build_interface(connected, port))

        threading.Thread(target=do_reconnect, daemon=True).start()

    def _on_start_jam(self):
        """Lanza el barrido de radiofrecuencia en hilo secundario."""
        threading.Thread(
            target=lambda: self.services.jammer.start_sweep_jam(on_output=self.write_console),
            daemon=True
        ).start()

    def _on_stop_jam(self):
        """Detiene el barrido en hilo secundario."""
        threading.Thread(
            target=lambda: self.services.jammer.stop_sweep_jam(on_output=self.write_console),
            daemon=True
        ).start()

    def _on_status(self):
        """Consulta el estado del microcontrolador en hilo secundario."""
        threading.Thread(
            target=lambda: self.services.jammer.get_status(on_output=self.write_console),
            daemon=True
        ).start()

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
