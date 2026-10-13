"""
dragonfly/ui/raspi/views/wifi_view.py - Vista de auditoría WiFi táctil para Raspberry Pi.
Controla modo monitor, captura de Handshakes, Evil Twin (individual y dual) y ataques Deauth.
"""

import threading
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_EVIL
from dragonfly.core.hardware import get_wifi_interfaces


class WiFiView(BaseView):
    """
    Vista táctil de auditoría inalámbrica para pantalla de 320x240 en Raspberry Pi.
    """

    def __init__(self, app):
        super().__init__(app)
        self.wifi_state = {}

    def render(self):
        """Menú principal de auditoría WiFi."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="AUDITORIA WIFI", style='Title.TLabel').pack(pady=2)

        interfaces = get_wifi_interfaces()
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces Wi-Fi.", style='Dark.TLabel').pack()
            return

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if "iface" not in self.wifi_state or self.wifi_state["iface"] not in interfaces:
            self.wifi_state["iface"] = interfaces[0]

        sel_frame = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        sel_frame.pack(pady=3)
        ttk.Label(sel_frame, text="Iface: ", style='Dark.TLabel').pack(side='left')

        var_iface = tk.StringVar(value=self.wifi_state["iface"])

        def on_change(val):
            self.wifi_state["iface"] = val

        ttk.OptionMenu(sel_frame, var_iface, var_iface.get(), *interfaces,
                       command=on_change, style='Dark.TMenubutton').pack(side='left')

        scroll.add_button("Activar / Desactivar Monitor", self._toggle_monitor, style='Red.TButton', width=28)
        scroll.add_button("Captura Handshake", self._flow_handshake_start, style='Red.TButton', width=28)
        scroll.add_button("Ataque Evil Twin", self._flow_evil_twin_start, style='Danger.TButton', width=28)
        scroll.add_button("Ataque Deauth", self._flow_deauth_start, style='Red.TButton', width=28)
        scroll.add_button("Explorar Handshakes", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI, "Handshakes", self.render), style='Gray.TButton', width=28)
        scroll.add_button("Explorar Evil Twin", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_EVIL, "Evil Twin", self.render), style='Gray.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

    # -------------------------------------------------------------
    # MODO MONITOR
    # -------------------------------------------------------------
    def _toggle_monitor(self):
        iface = self.wifi_state.get("iface")
        if not iface:
            return
        mon = self.wifi_state.get("mon_iface")
        if not mon:
            self.write_console(f"[*] Modo monitor en {iface}...")
            mon_res = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon_res
            self.write_console(f"[+] Monitor activo: {mon_res}")
        else:
            self.write_console(f"[*] Deteniendo monitor {mon}...")
            self.services.wifi.disable_monitor_mode(mon)
            self.wifi_state["mon_iface"] = None
            self.write_console("[+] Monitor desactivado.")

    # -------------------------------------------------------------
    # HANDSHAKE FLOW
    # -------------------------------------------------------------
    def _flow_handshake_start(self):
        iface = self.wifi_state.get("iface")
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="ESCANEANDO REDES (15s)", style='Title.TLabel').pack(pady=4)
        self.show_console()

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
        ttk.Label(self.main_frame, text="SELECCIONA RED", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if not redes:
            ttk.Label(scroll.scrollable_frame, text="No hay redes.", style='Gray.TLabel').pack()
            return

        for r in redes:
            texto = f"CH{r['ch']} {r['essid'][:14]}"
            scroll.add_button(text=texto, command=lambda red=r: self._flow_handshake_scan_clients(red), style='Red.TButton', width=28)

    def _flow_handshake_scan_clients(self, red):
        self.wifi_state["target"] = red
        self.clear_frame()
        self.add_back_button(self._flow_handshake_start)
        ttk.Label(self.main_frame, text=f"CLIENTES {red['essid'][:12]}", style='Title.TLabel').pack(pady=2)
        self.show_console()

        def worker():
            mon = self.wifi_state["mon_iface"]
            clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            self.run_on_ui(lambda: self._flow_handshake_show_clients(clientes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_show_clients(self, clientes):
        red = self.wifi_state["target"]
        self.clear_frame()
        self.add_back_button(self._flow_handshake_start)
        ttk.Label(self.main_frame, text="CLIENTES DETECTADOS", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button("FINALIZAR Y RESTAURAR", self._flow_handshake_finish, style='Danger.TButton', width=28)
        scroll.add_button("Todos (Broadcast)", lambda: self._flow_handshake_launch("FF:FF:FF:FF:FF:FF"), style='Danger.TButton', width=28)

        for c in clientes:
            scroll.add_button(text=f"Cli: {c[:14]}", command=lambda mac=c: self._flow_handshake_launch(mac), style='Red.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_handshake_launch(self, client_mac):
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
        self.services.wifi.stop_handshake_audit(mon)
        self.wifi_state["mon_iface"] = None
        self.write_console("[+] Interfaces restauradas.")
        self.render()

    # -------------------------------------------------------------
    # EVIL TWIN FLOW
    # -------------------------------------------------------------
    def _flow_evil_twin_start(self):
        interfaces = get_wifi_interfaces()
        if len(interfaces) < 2:
            self.clear_frame()
            self.add_back_button(self.render)
            ttk.Label(self.main_frame, text="EVIL TWIN", style='Title.TLabel').pack(pady=4)
            ttk.Label(self.main_frame, text="Requiere 2 tarjetas Wi-Fi\n(1 AP + 1 Deauth).", style='Gray.TLabel').pack(pady=10)
            return

        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN: INTERFACES", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        ap_var = tk.StringVar(value=interfaces[0])
        deauth_ifaces = [i for i in interfaces if i != interfaces[0]] or interfaces
        deauth_var = tk.StringVar(value=deauth_ifaces[0])

        f1 = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        f1.pack(fill='x', pady=2)
        ttk.Label(f1, text="AP: ", style='Dark.TLabel').pack(side='left')
        ttk.OptionMenu(f1, ap_var, ap_var.get(), *interfaces, style='Dark.TMenubutton').pack(side='left')

        f2 = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        f2.pack(fill='x', pady=2)
        ttk.Label(f2, text="Deauth: ", style='Dark.TLabel').pack(side='left')
        ttk.OptionMenu(f2, deauth_var, deauth_var.get(), *interfaces, style='Dark.TMenubutton').pack(side='left')

        def proceed():
            self.wifi_state["ap_iface"] = ap_var.get()
            self.wifi_state["deauth_iface"] = deauth_var.get()
            self._flow_evil_twin_scan()

        scroll.add_button("Continuar a Escaneo", proceed, style='Danger.TButton', width=28)

    def _flow_evil_twin_scan(self):
        deauth_iface = self.wifi_state["deauth_iface"]
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_start)
        ttk.Label(self.main_frame, text="ESCANEANDO REDES (15s)", style='Title.TLabel').pack(pady=2)
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
        ttk.Label(self.main_frame, text="SELECCIONA RED CLON", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for r in redes:
            texto = f"CH{r['ch']} {r['essid'][:14]}"
            scroll.add_button(text=texto, command=lambda red=r: self._flow_evil_twin_select_portal(red), style='Red.TButton', width=28)

    def _flow_evil_twin_select_portal(self, red):
        self.wifi_state["evil_target"] = red
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_scan)
        ttk.Label(self.main_frame, text="PORTAL CAUTIVO", style='Title.TLabel').pack(pady=2)

        portales = self.services.evil_twin.list_portals()
        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for p in portales:
            scroll.add_button(text=f"🌐 {p}", command=lambda portal=p: self._flow_evil_twin_launch(portal), style='Red.TButton', width=28)

    def _flow_evil_twin_launch(self, portal_name):
        self.clear_frame()
        ttk.Label(self.main_frame, text="EVIL TWIN ACTIVO", style='Title.TLabel').pack(pady=2)

        btn_stop = ttk.Button(self.main_frame, text="DETENER EVIL TWIN", style='Danger.TButton', command=self._flow_evil_twin_stop)
        btn_stop.pack(pady=4)

        self.show_console()

        ap_iface = self.wifi_state["ap_iface"]
        mon_deauth = self.wifi_state["mon_deauth"]
        red_target = self.wifi_state["evil_target"]

        def on_cred(line):
            self.write_console(f"[!] CREDENCIAL: {line}")

        self.services.evil_twin.start_evil_twin(
            ap_iface=ap_iface,
            mon_deauth=mon_deauth,
            red_target=red_target,
            portal_name=portal_name,
            deauth_mode="broadcast",
            on_output=self.write_console,
            on_cred=on_cred
        )

    def _flow_evil_twin_stop(self):
        self.write_console("[*] Deteniendo Evil Twin...")
        self.services.evil_twin.stop_evil_twin()
        self.app.after(3000, self.render)

    # -------------------------------------------------------------
    # DEAUTH FLOW
    # -------------------------------------------------------------
    def _flow_deauth_start(self):
        iface = self.wifi_state.get("iface")
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="ESCANEANDO REDES (15s)", style='Title.TLabel').pack(pady=2)
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
        ttk.Label(self.main_frame, text="OBJETIVO DEAUTH", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for r in redes:
            texto = f"CH{r['ch']} {r['essid'][:14]}"
            scroll.add_button(text=texto, command=lambda red=r: self._flow_deauth_launch(red), style='Red.TButton', width=28)

    def _flow_deauth_launch(self, red):
        self.clear_frame()
        ttk.Label(self.main_frame, text=f"DEAUTH {red['essid'][:12]}", style='Title.TLabel').pack(pady=2)

        btn_stop = ttk.Button(self.main_frame, text="DETENER ATAQUE", style='Danger.TButton', command=self._flow_deauth_stop)
        btn_stop.pack(pady=4)

        self.show_console()
        mon = self.wifi_state["mon_iface"]

        self.services.wifi.start_deauth_attack(
            mon_iface=mon,
            target_red=red,
            cliente_mac="FF:FF:FF:FF:FF:FF",
            count="0",
            on_output=self.write_console
        )

    def _flow_deauth_stop(self):
        self.write_console("[*] Deteniendo deauth...")
        self.services.wifi.stop_deauth_attack()
        self.app.after(1000, self.render)
