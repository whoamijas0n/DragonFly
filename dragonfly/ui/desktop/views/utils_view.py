"""
dragonfly/ui/desktop/views/utils_view.py - Vista de utilidades del sistema y conectividad para Desktop.
Gestiona redes Wi-Fi (nmcli), Bluetooth (bluetoothctl), métricas de hardware y opciones de energía.
"""

import threading
import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_PELIGRO_HOVER,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER
)
from dragonfly.core.hardware import get_wifi_interfaces


class UtilsView(BaseView):
    """
    Vista de herramientas de administración del sistema y periféricos inalámbricos.
    """

    def __init__(self, app):
        super().__init__(app)
        self.var_iface_wifi = ctk.StringVar(value="")
        self.var_iface_bt = ctk.StringVar(value="")

    def render(self):
        """Menú general de utilidades."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="UTILIDADES DEL SISTEMA", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 15))

        # Sección Wi-Fi
        wifi_frame = ctk.CTkFrame(self.main_frame, fg_color=COLOR_FONDO_PRINCIPAL, border_width=1, border_color="#333")
        wifi_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(wifi_frame, text="CONECTIVIDAD WI-FI (NMCLI)", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ff4d4d").pack(pady=5)

        ctk.CTkButton(
            wifi_frame, text="Seleccionar Interfaz y Conectar a Red",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, height=40,
            command=self._wifi_select_interface
        ).pack(fill="x", padx=40, pady=5)

        ctk.CTkButton(
            wifi_frame, text="Ver Estado Wi-Fi Actual",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, height=40,
            command=self._wifi_status
        ).pack(fill="x", padx=40, pady=5)

        # Sección Bluetooth
        bt_frame = ctk.CTkFrame(self.main_frame, fg_color=COLOR_FONDO_PRINCIPAL, border_width=1, border_color="#333")
        bt_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(bt_frame, text="CONECTIVIDAD BLUETOOTH", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#ff4d4d").pack(pady=5)

        ctk.CTkButton(
            bt_frame, text="Escanear y Conectar Dispositivo Bluetooth",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, height=40,
            command=self._bt_scan
        ).pack(fill="x", padx=40, pady=5)

        ctk.CTkButton(
            bt_frame, text="Ver Estado Bluetooth",
            fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER, height=40,
            command=self._bt_status
        ).pack(fill="x", padx=40, pady=5)

        # Sección Monitoreo
        ctk.CTkLabel(self.main_frame, text="MONITOREO DEL SISTEMA",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#ff4d4d").pack(pady=(10, 5))

        btn_grid = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_grid.pack(fill="x", padx=15, pady=5)
        btn_grid.grid_columnconfigure((0, 1), weight=1)

        metricas = [
            ("Uso de Almacenamiento", "storage"),
            ("Uso de RAM", "memory"),
            ("Top Procesos CPU", "cpu"),
            ("Conexiones Activas", "connections")
        ]
        for i, (nombre, m_key) in enumerate(metricas):
            row = i // 2
            col = i % 2
            ctk.CTkButton(
                btn_grid, text=nombre, fg_color=COLOR_BOTON_ROJO, hover_color=COLOR_BOTON_HOVER,
                command=lambda k=m_key: self.services.system.get_system_metrics(k, on_output=self.write_console)
            ).grid(row=row, column=col, padx=5, pady=5, sticky="ew")

        # Botones de Energía y Salida
        ctk.CTkButton(self.main_frame, text="REINICIAR SISTEMA", fg_color=COLOR_BOTON_PELIGRO,
                      hover_color=COLOR_BOTON_PELIGRO_HOVER, width=220, command=self.services.system.reboot).pack(pady=10)
        ctk.CTkButton(self.main_frame, text="APAGAR SISTEMA", fg_color=COLOR_BOTON_PELIGRO,
                      hover_color=COLOR_BOTON_PELIGRO_HOVER, width=220, command=self.services.system.power_off).pack(pady=5)
        ctk.CTkButton(self.main_frame, text="CERRAR INTERFAZ (SALIR)", fg_color=COLOR_BOTON_GRIS,
                      hover_color=COLOR_BOTON_GRIS_HOVER, width=220, command=self.app.destroy).pack(pady=15)

        self.show_console()

    # -------------------------------------------------------------
    # SUBFLUJO: WI-FI CLIENTE
    # -------------------------------------------------------------
    def _wifi_select_interface(self):
        interfaces = get_wifi_interfaces()
        if not interfaces:
            self.write_console("[!] No hay interfaces Wi-Fi disponibles.")
            return

        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="SELECCIONA INTERFAZ WI-FI", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        if not self.var_iface_wifi.get() or self.var_iface_wifi.get() not in interfaces:
            self.var_iface_wifi.set(interfaces[0])

        ctk.CTkOptionMenu(self.main_frame, variable=self.var_iface_wifi, values=interfaces, fg_color=COLOR_BOTON_ROJO).pack(pady=10)

        ctk.CTkButton(
            self.main_frame, text="Escanear Redes", fg_color=COLOR_BOTON_ROJO,
            command=self._wifi_scan_networks
        ).pack(pady=10)
        self.show_console()

    def _wifi_scan_networks(self):
        iface = self.var_iface_wifi.get()
        self.clear_frame()
        self.add_back_button(self._wifi_select_interface)
        ctk.CTkLabel(self.main_frame, text=f"ESCANEANDO REDES CON {iface}...", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        self.show_console()
        self.write_console(f"[*] Buscando puntos de acceso disponibles en {iface}...")

        def worker():
            redes = self.services.system.scan_wifi_networks(iface)
            self.run_on_ui(lambda: self._wifi_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _wifi_show_networks(self, redes):
        iface = self.var_iface_wifi.get()
        self.clear_frame()
        self.add_back_button(self._wifi_select_interface)
        ctk.CTkLabel(self.main_frame, text=f"REDES ENCONTRADAS ({iface})", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for red in redes:
            texto = f"📶 {red['ssid']} | Seg: {red['security']} | Señal: {red['signal']}"
            ctk.CTkButton(
                frame,
                text=texto,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda s=red['ssid'], sec=red['security']: self._wifi_connect_prompt(iface, s, sec)
            ).pack(fill="x", pady=3)

        self.show_console()

    def _wifi_connect_prompt(self, iface: str, ssid: str, security: str):
        password = None
        if "WPA" in security or "WEP" in security:
            dialog = ctk.CTkInputDialog(text=f"Introduce contraseña para '{ssid}':", title="Conectar Wi-Fi")
            password = dialog.get_input()
            if password is None:
                return

        self.write_console(f"[*] Conectando a '{ssid}' en {iface}...")
        self.services.system.connect_wifi(iface, ssid, password, on_output=self.write_console)

    def _wifi_status(self):
        self.services.executor.run_async("sudo nmcli dev wifi list", on_output=self.write_console)

    # -------------------------------------------------------------
    # SUBFLUJO: BLUETOOTH
    # -------------------------------------------------------------
    def _bt_scan(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="ESCANEANDO DISPOSITIVOS BLUETOOTH (10s)...", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        self.show_console()
        self.write_console("[*] Escaneando dispositivos cercanos...")

        def worker():
            dispositivos = self.services.system.scan_bluetooth(duration=10)
            self.run_on_ui(lambda: self._bt_show_devices(dispositivos))

        threading.Thread(target=worker, daemon=True).start()

    def _bt_show_devices(self, dispositivos):
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="DISPOSITIVOS BLUETOOTH ENCONTRADOS", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        if not dispositivos:
            ctk.CTkLabel(self.main_frame, text="No se encontraron dispositivos cercanos.", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for mac, nombre in dispositivos:
            ctk.CTkButton(
                frame,
                text=f"🔵 {nombre} ({mac})",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda m=mac: self.services.system.pair_and_connect_bluetooth(m, on_output=self.write_console)
            ).pack(fill="x", pady=3)

        self.show_console()

    def _bt_status(self):
        adapters = self.services.system.get_bluetooth_adapters()
        if not adapters:
            self.write_console("[!] No se detectaron adaptadores Bluetooth.")
            return
        for adp in adapters:
            self.services.executor.run_async(f"hciconfig {adp} -a && bluetoothctl -- show {adp}", on_output=self.write_console)
