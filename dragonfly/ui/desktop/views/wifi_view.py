"""
dragonfly/ui/desktop/views/wifi_view.py - Vista integral de auditoría inalámbrica para Desktop.
Controla modo monitor, captura de Handshakes, Rogue AP Evil Twin y ataques Deauth.
"""

import os
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
    COLOR_BOTON_DESHABILITADO,
    COLOR_TEXTO_TERMINAL,
)
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_EVIL, BASE_DIR_CLIENTS, BASE_DIR_WIFI_AUDIT
from dragonfly.core.hardware import get_wifi_interfaces
from dragonfly.services.wifi_audit_service import (
    format_network_detail,
    format_network_line,
    format_summary,
)


class WiFiView(BaseView):
    """
    Controlador y vistas visuales para ataques e inspección inalámbrica 802.11.
    """

    def __init__(self, app):
        super().__init__(app)
        self.wifi_state = {}
        self.btn_detener_evil = None
        self.btn_detener_deauth = None

    def render(self):
        """Menú principal de auditoría inalámbrica."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="AUDITORÍA INALÁMBRICA (WIFI)",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 15))

        interfaces = get_wifi_interfaces()
        if not interfaces:
            ctk.CTkLabel(self.main_frame, text="No se detectaron interfaces inalámbricas Wi-Fi.",
                         text_color="#aaaaaa").pack(pady=20)
            return

        if "iface" not in self.wifi_state or self.wifi_state["iface"] not in interfaces:
            self.wifi_state["iface"] = interfaces[0]

        sel_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        sel_frame.pack(pady=5)
        ctk.CTkLabel(sel_frame, text="Interfaz Wi-Fi: ").pack(side="left")

        var_iface = ctk.StringVar(value=self.wifi_state["iface"])

        def on_change_iface(val):
            self.wifi_state["iface"] = val

        ctk.CTkOptionMenu(
            sel_frame,
            variable=var_iface,
            values=interfaces,
            command=on_change_iface,
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(side="left")

        # Acciones principales
        botones = [
            ("Reconocimiento WiFi (Pasivo)", self._flow_audit_start, COLOR_BOTON_ROJO),
            ("Activar / Desactivar Modo Monitor", self._toggle_monitor_mode, COLOR_BOTON_ROJO),
            ("Captura de Handshake (WPA/WPA2)", self._flow_handshake_start, COLOR_BOTON_ROJO),
            ("Ataque Evil Twin (Portal Cautivo)", self._flow_evil_twin_start, COLOR_BOTON_PELIGRO),
            ("Ataque de Desautenticación (Deauth)", self._flow_deauth_start, COLOR_BOTON_ROJO),
            ("Explorar Handshakes Capturados", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI, "Handshakes", self.render), COLOR_BOTON_GRIS),
            ("Explorar Credenciales Evil Twin", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_EVIL, "Evil Twin", self.render), COLOR_BOTON_GRIS),
            ("Explorar Clientes Conectados", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_CLIENTS, "Clientes", self.render), COLOR_BOTON_GRIS),
            ("Explorar Auditorías WiFi", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI_AUDIT, "Auditorías WiFi", self.render), COLOR_BOTON_GRIS)
        ]

        for texto, cmd, color in botones:
            ctk.CTkButton(
                self.main_frame,
                text=texto,
                fg_color=color,
                hover_color=COLOR_BOTON_HOVER if color == COLOR_BOTON_ROJO else (COLOR_BOTON_PELIGRO_HOVER if color == COLOR_BOTON_PELIGRO else COLOR_BOTON_GRIS_HOVER),
                width=350,
                height=40,
                command=cmd
            ).pack(pady=5)

        self.show_console()

    # -------------------------------------------------------------
    # MODO MONITOR
    # -------------------------------------------------------------
    def _toggle_monitor_mode(self):
        iface = self.wifi_state.get("iface")
        if not iface:
            return

        mon = self.wifi_state.get("mon_iface")
        if not mon:
            self.write_console(f"[*] Activando modo monitor en {iface}...")
            mon_res = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon_res
            self.write_console(f"[+] Modo monitor activo en {mon_res}.")
        else:
            self.write_console(f"[*] Desactivando modo monitor en {mon}...")
            self.services.wifi.disable_monitor_mode(mon)
            self.wifi_state["mon_iface"] = None
            self.write_console("[+] Modo monitor desactivado. NetworkManager reiniciado.")

    # -------------------------------------------------------------
    # FLUJO: CAPTURA DE HANDSHAKE
    # -------------------------------------------------------------
    def _flow_handshake_start(self):
        iface = self.wifi_state.get("iface")
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="ESCANEANDO REDES CERCANAS (15s)...",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        self.show_console()
        self.write_console(f"[*] Iniciando monitor y escaneo en {iface}...")

        def worker():
            mon = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon
            self.write_console(f"[*] Escaneando 15s en {mon}...")
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_handshake_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="SELECCIONA RED OBJETIVO", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        if not redes:
            ctk.CTkLabel(self.main_frame, text="No se detectaron redes inalámbricas en el rango.", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for red in redes:
            texto = f"CH {red['ch']} | {red['bssid']} | {red['essid']}"
            ctk.CTkButton(
                frame,
                text=texto,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda r=red: self._flow_handshake_scan_clients(r)
            ).pack(fill="x", pady=3)

    def _flow_handshake_scan_clients(self, red):
        self.wifi_state["target"] = red
        self.clear_frame()
        self.add_back_button(lambda: self._flow_handshake_start())
        ctk.CTkLabel(self.main_frame, text=f"ESCANEANDO CLIENTES\n{red['essid']}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        self.show_console()
        self.write_console(f"[*] Capturando tráfico de {red['essid']} ({red['bssid']}) por 10s...")

        def worker():
            mon = self.wifi_state["mon_iface"]
            clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            self.run_on_ui(lambda: self._flow_handshake_show_clients(clientes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_show_clients(self, clientes):
        red = self.wifi_state["target"]
        self.clear_frame()
        self.add_back_button(lambda: self._flow_handshake_start())
        ctk.CTkLabel(self.main_frame, text=f"CLIENTES DETECTADOS EN {red['essid']}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkButton(
            frame,
            text="FINALIZAR AUDITORÍA Y RESTAURAR RED",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            command=self._flow_handshake_finish
        ).pack(fill="x", pady=5)

        ctk.CTkButton(
            frame,
            text="Todos (Broadcast - Desautenticar a todos)",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            command=lambda: self._flow_handshake_launch_attack("FF:FF:FF:FF:FF:FF")
        ).pack(fill="x", pady=5)

        for c in clientes:
            ctk.CTkButton(
                frame,
                text=f"Cliente: {c}",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                command=lambda mac=c: self._flow_handshake_launch_attack(mac)
            ).pack(fill="x", pady=3)

        self.show_console()

    def _flow_handshake_launch_attack(self, client_mac):
        red = self.wifi_state["target"]
        mon = self.wifi_state["mon_iface"]
        self.services.wifi.start_handshake_capture(
            mon_iface=mon,
            target_red=red,
            cliente_mac=client_mac,
            on_output=self.write_console
        )

    def _flow_handshake_finish(self):
        mon = self.wifi_state.get("mon_iface")
        self.write_console("[*] Finalizando auditoría de Handshake y restaurando interfaces...")
        self.services.wifi.stop_handshake_audit(mon)
        self.wifi_state["mon_iface"] = None
        self.write_console("[+] Interfaces restauradas.")
        self.render()

    # -------------------------------------------------------------
    # FLUJO: EVIL TWIN
    # -------------------------------------------------------------
    def _flow_evil_twin_start(self):
        interfaces = get_wifi_interfaces()
        if len(interfaces) < 2:
            self.clear_frame()
            self.add_back_button(self.render)
            ctk.CTkLabel(self.main_frame, text="ATAQUE EVIL TWIN", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
            ctk.CTkLabel(self.main_frame, text="Se requieren al menos 2 interfaces Wi-Fi:\n1 para emitir el Punto de Acceso (AP)\n1 para desautenticar a las víctimas.",
                         text_color="#ff4d4d", font=ctk.CTkFont(size=14)).pack(pady=20)
            return

        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="EVIL TWIN: SELECCIÓN DE INTERFACES", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        ctk.CTkLabel(self.main_frame, text="1. Selecciona tarjeta para emitir el Rogue AP:").pack(pady=5)
        ap_var = ctk.StringVar(value=interfaces[0])
        ctk.CTkOptionMenu(self.main_frame, variable=ap_var, values=interfaces, fg_color=COLOR_BOTON_ROJO).pack(pady=5)

        ctk.CTkLabel(self.main_frame, text="2. Selecciona tarjeta para Desautenticación:").pack(pady=5)
        deauth_ifaces = [i for i in interfaces if i != interfaces[0]] or interfaces
        deauth_var = ctk.StringVar(value=deauth_ifaces[0])
        ctk.CTkOptionMenu(self.main_frame, variable=deauth_var, values=deauth_ifaces, fg_color=COLOR_BOTON_ROJO).pack(pady=5)

        def proceed():
            self.wifi_state["ap_iface"] = ap_var.get()
            self.wifi_state["deauth_iface"] = deauth_var.get()
            self._flow_evil_twin_scan()

        ctk.CTkButton(self.main_frame, text="Continuar a Escaneo", fg_color=COLOR_BOTON_PELIGRO, height=40, command=proceed).pack(pady=20)

    def _flow_evil_twin_scan(self):
        deauth_iface = self.wifi_state["deauth_iface"]
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_start)
        ctk.CTkLabel(self.main_frame, text="ESCANEANDO REDES PARA CLONAR (15s)...", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        self.show_console()

        def worker():
            mon = self.services.wifi.enable_monitor_mode(deauth_iface)
            self.wifi_state["mon_deauth"] = mon
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_evil_twin_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_evil_twin_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_start)
        ctk.CTkLabel(self.main_frame, text="SELECCIONA RED A CLONAR", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for red in redes:
            texto = f"CH {red['ch']} | {red['bssid']} | {red['essid']}"
            ctk.CTkButton(
                frame,
                text=texto,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda r=red: self._flow_evil_twin_select_portal(r)
            ).pack(fill="x", pady=3)

    def _flow_evil_twin_select_portal(self, red):
        self.wifi_state["evil_target"] = red
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_scan)
        ctk.CTkLabel(self.main_frame, text="SELECCIONA PORTAL CAUTIVO", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        portales = self.services.evil_twin.list_portals()
        if not portales:
            ctk.CTkLabel(self.main_frame, text="No se encontraron portales en evil_portals/ con index.html", text_color="#aaaaaa").pack(pady=20)
            return

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for p in portales:
            ctk.CTkButton(
                frame,
                text=f"🌐 Portal: {p}",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda portal_name=p: self._flow_evil_twin_select_deauth_mode(red, portal_name)
            ).pack(fill="x", pady=3)

    def _flow_evil_twin_select_deauth_mode(self, red, portal_name):
        self.wifi_state["evil_scan_pending"] = False
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_select_portal(red))
        ctk.CTkLabel(self.main_frame, text="MODO DE DESAUTENTICACIÓN", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        ctk.CTkButton(
            self.main_frame,
            text="Broadcast (desautenticar a todos los clientes)",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            height=40,
            command=lambda: self._flow_evil_twin_launch(portal_name, "broadcast")
        ).pack(fill="x", padx=40, pady=6)

        ctk.CTkButton(
            self.main_frame,
            text="Cliente específico (escanear y elegir MAC)",
            fg_color=COLOR_BOTON_ROJO,
            hover_color=COLOR_BOTON_HOVER,
            height=40,
            command=lambda: self._flow_evil_twin_scan_clients(red, portal_name)
        ).pack(fill="x", padx=40, pady=6)

        self.show_console()

    def _flow_evil_twin_scan_clients(self, red, portal_name):
        self.wifi_state["evil_scan_pending"] = True
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_cancel_client_scan(red, portal_name))
        ctk.CTkLabel(self.main_frame, text=f"ESCANEANDO CLIENTES\n{red['essid']}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        self.show_console()
        self.write_console(f"[*] Rastreando clientes asociados a {red['bssid']} (10s)...")

        def worker():
            mon = self.wifi_state.get("mon_deauth")
            if not mon:
                deauth_iface = self.wifi_state.get("deauth_iface")
                if deauth_iface:
                    mon = self.services.wifi.enable_monitor_mode(deauth_iface)
                    self.wifi_state["mon_deauth"] = mon
            if not mon:
                self.run_on_ui(lambda: self._flow_evil_twin_show_clients(
                    red, portal_name, [], error="No hay interfaz en modo monitor."))
                return
            clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            self.run_on_ui(lambda: self._flow_evil_twin_show_clients(red, portal_name, clientes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_evil_twin_cancel_client_scan(self, red, portal_name):
        self.wifi_state["evil_scan_pending"] = False
        self._flow_evil_twin_select_deauth_mode(red, portal_name)

    def _flow_evil_twin_show_clients(self, red, portal_name, clientes, error=None):
        if not self.wifi_state.get("evil_scan_pending"):
            # El operador abandonó la pantalla de escaneo: descartar resultados tardíos.
            return
        self.wifi_state["evil_scan_pending"] = False

        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_select_deauth_mode(red, portal_name))
        ctk.CTkLabel(self.main_frame, text="SELECCIONA CLIENTE OBJETIVO", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkButton(
            frame,
            text="Todos (Broadcast - desautenticar a todos)",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            command=lambda: self._flow_evil_twin_launch(portal_name, "broadcast")
        ).pack(fill="x", pady=5)

        if clientes:
            for mac in clientes:
                ctk.CTkButton(
                    frame,
                    text=f"Cliente: {mac}",
                    fg_color=COLOR_BOTON_ROJO,
                    hover_color=COLOR_BOTON_HOVER,
                    command=lambda m=mac: self._flow_evil_twin_launch(portal_name, "directed", m)
                ).pack(fill="x", pady=3)
        else:
            ctk.CTkButton(
                frame,
                text="Reintentar escaneo (10s)",
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                command=lambda: self._flow_evil_twin_scan_clients(red, portal_name)
            ).pack(fill="x", pady=5)

        self.show_console()

        if error:
            self.write_console(f"[!] {error} Use Broadcast o reintente el escaneo.")
        elif clientes:
            self.write_console(f"[+] Clientes detectados: {len(clientes)}. Seleccione la MAC objetivo.")
        else:
            self.write_console("[!] No se detectaron clientes. Puede reintentar el escaneo o usar Broadcast.")

    def _flow_evil_twin_launch(self, portal_name, deauth_mode="broadcast", cliente_mac=None):
        self.wifi_state["evil_scan_pending"] = False
        self.clear_frame()
        ctk.CTkLabel(self.main_frame, text="EVIL TWIN EN EJECUCIÓN", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLOR_BOTON_PELIGRO).pack(pady=10)

        self.btn_detener_evil = ctk.CTkButton(
            self.main_frame,
            text="DETENER EVIL TWIN Y RESTAURAR RED",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            height=40,
            command=self._flow_evil_twin_stop
        )
        self.btn_detener_evil.pack(pady=10)

        self.show_console()

        ap_iface = self.wifi_state["ap_iface"]
        mon_deauth = self.wifi_state["mon_deauth"]
        red_target = self.wifi_state["evil_target"]

        def on_cred(cred_line):
            self.write_console(f"[!] *** CREDENCIAL CAPTURADA ***: {cred_line}")

        if deauth_mode == "directed" and cliente_mac:
            self.write_console(f"[*] Deauth dirigido al cliente: {cliente_mac}")
        else:
            self.write_console("[*] Deauth en modo broadcast (todos los clientes).")

        self.services.evil_twin.start_evil_twin(
            ap_iface=ap_iface,
            mon_deauth=mon_deauth,
            red_target=red_target,
            portal_name=portal_name,
            deauth_mode=deauth_mode,
            cliente_mac=cliente_mac,
            on_output=self.write_console,
            on_cred=on_cred
        )

    def _flow_evil_twin_stop(self):
        if self.btn_detener_evil and self.btn_detener_evil.winfo_exists():
            self.btn_detener_evil.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
        self.write_console("[*] Deteniendo procesos y restaurando red...")
        self.services.evil_twin.stop_evil_twin()
        self.app.after(3000, self.render)

    # -------------------------------------------------------------
    # FLUJO: DEAUTH INDEPENDIENTE
    # -------------------------------------------------------------
    def _flow_deauth_start(self):
        iface = self.wifi_state.get("iface")
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="ESCANEANDO REDES OBJETIVO (15s)...", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        self.show_console()

        def worker():
            mon = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_deauth_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_deauth_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(self.main_frame, text="SELECCIONA RED PARA DESAUTENTICAR", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=10)

        for red in redes:
            texto = f"CH {red['ch']} | {red['bssid']} | {red['essid']}"
            ctk.CTkButton(
                frame,
                text=texto,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                anchor="w",
                command=lambda r=red: self._flow_deauth_select_intensity(r)
            ).pack(fill="x", pady=3)

    def _flow_deauth_select_intensity(self, red):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_start)
        ctk.CTkLabel(self.main_frame, text=f"INTENSIDAD DEATAQUE EN:\n{red['essid']}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        opciones = [
            ("Continuo (Indefinido - Paquetes 0)", "0"),
            ("1 Ráfaga Corta (5 Paquetes)", "5"),
            ("3 Ráfagas (15 Paquetes)", "15")
        ]
        for texto, count in opciones:
            ctk.CTkButton(
                self.main_frame,
                text=texto,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                height=40,
                command=lambda cnt=count: self._flow_deauth_launch(red, cnt)
            ).pack(fill="x", padx=40, pady=5)

    def _flow_deauth_launch(self, red, count):
        self.clear_frame()
        ctk.CTkLabel(self.main_frame, text="ATAQUE DEAUTH EN CURSO", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COLOR_BOTON_PELIGRO).pack(pady=10)

        self.btn_detener_deauth = ctk.CTkButton(
            self.main_frame,
            text="DETENER ATAQUE",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            height=40,
            command=self._flow_deauth_stop
        )
        self.btn_detener_deauth.pack(pady=10)

        self.show_console()
        mon = self.wifi_state["mon_iface"]

        def on_finish(rc):
            self.run_on_ui(lambda: self.write_console("\n[+] Ataque deauth finalizado."))

        self.services.wifi.start_deauth_attack(
            mon_iface=mon,
            target_red=red,
            cliente_mac="FF:FF:FF:FF:FF:FF",
            count=count,
            on_output=self.write_console,
            on_finish=on_finish
        )

    def _flow_deauth_stop(self):
        if self.btn_detener_deauth and self.btn_detener_deauth.winfo_exists():
            self.btn_detener_deauth.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
        self.write_console("[*] Deteniendo inyección de paquetes deauth...")
        self.services.wifi.stop_deauth_attack()
        self.app.after(1000, self.render)

    # -------------------------------------------------------------
    # FLUJO: RECONOCIMIENTO WIFI PASIVO (WIFI AUDIT 2.0 - V1)
    # -------------------------------------------------------------
    def _ensure_audit_report_saved(self, force=False):
        """Garantiza que el resultado actual exista en el directorio de auditorías."""
        result = self.wifi_state.get("audit_result") or {}
        networks = result.get("networks") or []
        if not networks:
            return result.get("session_dir", "")

        session_dir = result.get("session_dir")
        report_path = os.path.join(session_dir, "redes.json") if session_dir else ""
        if not force and report_path and os.path.isfile(report_path):
            return session_dir

        session_dir = self.services.wifi_audit.save_report(
            networks,
            result.get("summary"),
            session_dir=session_dir,
        )
        result["session_dir"] = session_dir
        self.wifi_state["audit_result"] = result
        return session_dir

    def _flow_audit_finish(self):
        """Detiene el escaneo, guarda lo obtenido y vuelve al menú WiFi principal."""
        if self.wifi_state.get("audit_finishing"):
            return
        self.wifi_state["audit_finishing"] = True
        self.wifi_state["audit_token"] = None
        self.write_console("[*] Finalizando auditoría WiFi...")

        try:
            session_dir = self._ensure_audit_report_saved()
            if session_dir:
                self.write_console(f"[+] Resultados guardados en {session_dir}")
        except Exception as exc:
            self.write_console(f"[!] Error al guardar resultados: {exc}")

        def cleanup():
            try:
                self.services.wifi_audit.cancel_scan()
                if not self.services.wifi_audit.wait_for_idle(timeout=15):
                    self.write_console("[!] El escaneo todavía se está deteniendo.")
            except Exception as exc:
                self.write_console(f"[!] Error al finalizar auditoría: {exc}")
            finally:
                self.run_on_ui(self._finish_audit_return)

        threading.Thread(target=cleanup, daemon=True).start()

    def _finish_audit_return(self):
        self.wifi_state["audit_finishing"] = False
        self.wifi_state["audit_result"] = {}
        self.render()

    def _flow_audit_start(self):
        self.wifi_state["audit_token"] = None
        interfaces = get_wifi_interfaces()
        self.clear_frame()
        self.add_back_button(self.render)
        ctk.CTkLabel(
            self.main_frame,
            text="RECONOCIMIENTO WIFI PASIVO",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(10, 5))
        if not interfaces:
            ctk.CTkLabel(
                self.main_frame,
                text="No se detectaron interfaces inalámbricas Wi-Fi.",
                text_color="#ff4d4d"
            ).pack(pady=20)
            return

        ctk.CTkButton(
            self.main_frame,
            text="Single-band (1 interfaz)",
            fg_color=COLOR_BOTON_ROJO,
            hover_color=COLOR_BOTON_HOVER,
            width=350,
            height=40,
            command=lambda: self._flow_audit_single_setup(interfaces)
        ).pack(pady=6)

        ctk.CTkButton(
            self.main_frame,
            text="Dual-band (2 interfaces)",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            width=350,
            height=40,
            command=lambda: self._flow_audit_dual_setup(interfaces)
        ).pack(pady=6)

        self.show_console()

    def _flow_audit_single_setup(self, interfaces):
        self.clear_frame()
        self.add_back_button(self._flow_audit_start)
        ctk.CTkLabel(
            self.main_frame,
            text="RECONOCIMIENTO SINGLE-BAND",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)

        ctk.CTkLabel(self.main_frame, text="Interfaz WiFi:").pack(pady=(8, 2))
        iface_var = ctk.StringVar(value=interfaces[0])
        ctk.CTkOptionMenu(
            self.main_frame,
            variable=iface_var,
            values=interfaces,
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(pady=5)

        ctk.CTkLabel(self.main_frame, text="Banda:").pack(pady=(8, 2))
        band_var = ctk.StringVar(value="Auto")
        ctk.CTkOptionMenu(
            self.main_frame,
            variable=band_var,
            values=["Auto", "2.4 GHz", "5 GHz"],
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(pady=5)

        def proceed():
            band = {"2.4 GHz": "2.4", "5 GHz": "5", "Auto": None}.get(band_var.get())
            self._flow_audit_scan(iface_var.get(), band=band)

        ctk.CTkButton(
            self.main_frame,
            text="INICIAR ESCANEO (20s)",
            fg_color=COLOR_BOTON_ROJO,
            hover_color=COLOR_BOTON_HOVER,
            width=300,
            height=40,
            command=proceed
        ).pack(pady=20)

        self.show_console()

    def _flow_audit_dual_setup(self, interfaces):
        if len(interfaces) < 2:
            self.clear_frame()
            self.add_back_button(self._flow_audit_start)
            ctk.CTkLabel(
                self.main_frame,
                text="RECONOCIMIENTO DUAL-BAND",
                font=ctk.CTkFont(size=18, weight="bold")
            ).pack(pady=10)
            ctk.CTkLabel(
                self.main_frame,
                text="Se requieren 2 interfaces WiFi independientes:\n"
                     "1 para 2.4 GHz y 1 para 5 GHz.",
                text_color="#ff4d4d",
                justify="center"
            ).pack(pady=20)
            return

        self.clear_frame()
        self.add_back_button(self._flow_audit_start)
        ctk.CTkLabel(
            self.main_frame,
            text="RECONOCIMIENTO DUAL-BAND",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        ctk.CTkLabel(
            self.main_frame,
            text="Las dos interfaces deben usar phy distintos.",
            text_color="#aaaaaa"
        ).pack(pady=(0, 10))

        ctk.CTkLabel(self.main_frame, text="Interfaz 2.4 GHz:").pack(pady=(5, 2))
        iface_2g_var = ctk.StringVar(value=interfaces[0])
        ctk.CTkOptionMenu(
            self.main_frame,
            variable=iface_2g_var,
            values=interfaces,
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(pady=5)

        ctk.CTkLabel(self.main_frame, text="Interfaz 5 GHz:").pack(pady=(5, 2))
        iface_5g_var = ctk.StringVar(value=interfaces[1])
        ctk.CTkOptionMenu(
            self.main_frame,
            variable=iface_5g_var,
            values=interfaces,
            fg_color=COLOR_BOTON_ROJO,
            button_color=COLOR_BOTON_HOVER
        ).pack(pady=5)

        error_label = ctk.CTkLabel(self.main_frame, text="", text_color="#ff4d4d")
        error_label.pack(pady=5)

        def proceed():
            iface_2g = iface_2g_var.get()
            iface_5g = iface_5g_var.get()
            if iface_2g == iface_5g:
                error_label.configure(text="Seleccione dos interfaces distintas.")
                return
            self._flow_audit_scan(iface_2g, band="2.4", iface_5g=iface_5g)

        ctk.CTkButton(
            self.main_frame,
            text="INICIAR ESCANEO DUAL (20s)",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            width=300,
            height=40,
            command=proceed
        ).pack(pady=20)

        self.show_console()

    def _flow_audit_scan(self, iface, band=None, iface_5g=None):
        token = object()
        self.wifi_state["audit_token"] = token
        self.wifi_state["audit_result"] = {}
        self.clear_frame()
        self.add_back_button(self._flow_audit_start)
        ctk.CTkLabel(
            self.main_frame,
            text="RECONOCIMIENTO WIFI EN CURSO",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        ctk.CTkButton(
            self.main_frame,
            text="FINALIZAR AUDITORÍA",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            width=300,
            height=40,
            command=self._flow_audit_finish
        ).pack(pady=(0, 10))
        self.show_console()
        self.write_console("[*] Iniciando escaneo pasivo...")

        def worker():
            try:
                if iface_5g:
                    result = self.services.wifi_audit.scan_dual(
                        iface, iface_5g, duration=20, on_output=self.write_console
                    )
                else:
                    result = self.services.wifi_audit.scan_single(
                        iface, duration=20, band=band, on_output=self.write_console
                    )
                self.run_on_ui(
                    lambda: self._flow_audit_show_networks(result)
                    if self.wifi_state.get("audit_token") is token else None
                )
            except Exception as exc:
                message = str(exc)
                self.run_on_ui(
                    lambda e=message: self._flow_audit_error(e)
                    if self.wifi_state.get("audit_token") is token else None
                )

        threading.Thread(target=worker, daemon=True).start()

    def _flow_audit_show_networks(self, result):
        result = result or {}
        self.wifi_state["audit_result"] = result
        redes = result.get("networks", [])
        summary = result.get("summary", {})
        session_dir = result.get("session_dir", "")

        self.clear_frame()
        self.add_back_button(self._flow_audit_start)
        ctk.CTkLabel(
            self.main_frame,
            text=f"REDES DETECTADAS ({len(redes)})",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)
        ctk.CTkLabel(
            self.main_frame,
            text=format_summary(summary),
            text_color="#aaaaaa",
            justify="center"
        ).pack(pady=(0, 8))

        ctk.CTkButton(
            self.main_frame,
            text="FINALIZAR AUDITORÍA",
            fg_color=COLOR_BOTON_PELIGRO,
            hover_color=COLOR_BOTON_PELIGRO_HOVER,
            width=300,
            height=40,
            command=self._flow_audit_finish
        ).pack(pady=(0, 8))

        frame = ctk.CTkScrollableFrame(self.main_frame, height=300)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        if not redes:
            ctk.CTkLabel(
                frame,
                text="No se detectaron redes en el rango.",
                text_color="#aaaaaa"
            ).pack(pady=20)
        else:
            for net in redes:
                score = int(net.get("honeypot_score") or 0)
                if score >= 50:
                    color, hover = COLOR_BOTON_ROJO, COLOR_BOTON_HOVER
                elif score >= 25:
                    color, hover = COLOR_BOTON_PELIGRO, COLOR_BOTON_PELIGRO_HOVER
                else:
                    color, hover = COLOR_BOTON_GRIS, COLOR_BOTON_GRIS_HOVER

                ctk.CTkButton(
                    frame,
                    text=format_network_line(net),
                    fg_color=color,
                    hover_color=hover,
                    anchor="w",
                    height=34,
                    command=lambda n=net: self._flow_audit_detail(n)
                ).pack(fill="x", pady=3)

        self.show_console()
        if session_dir:
            self.write_console(f"[+] Reporte: {session_dir}")

    def _flow_audit_detail(self, net):
        try:
            session_dir = self._ensure_audit_report_saved(force=True)
        except Exception as exc:
            session_dir = ""
            self.write_console(f"[!] Error al guardar resultados: {exc}")

        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_audit_show_networks(self.wifi_state.get("audit_result", {}))
        )
        ctk.CTkLabel(
            self.main_frame,
            text=str(net.get("essid", "Detalle"))[:40],
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=10)

        if session_dir:
            ctk.CTkLabel(
                self.main_frame,
                text=f"Guardado: {os.path.basename(session_dir)}",
                text_color="#aaaaaa"
            ).pack(pady=(0, 5))

        textbox = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Courier", size=13),
            fg_color="#0a0a0a",
            text_color=COLOR_TEXTO_TERMINAL,
            corner_radius=12,
            height=400
        )
        textbox.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        textbox.insert("1.0", format_network_detail(net))
        textbox.configure(state="disabled")

    def _flow_audit_error(self, message):
        self.clear_frame()
        self.add_back_button(self._flow_audit_start)
        ctk.CTkLabel(
            self.main_frame,
            text="ERROR DE RECONOCIMIENTO",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLOR_BOTON_PELIGRO
        ).pack(pady=10)
        ctk.CTkLabel(
            self.main_frame,
            text=str(message),
            text_color="#ff4d4d",
            justify="center",
            wraplength=700
        ).pack(pady=10)
        self.show_console()
        self.write_console(f"[!] {message}")
