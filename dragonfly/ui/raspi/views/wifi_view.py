"""
dragonfly/ui/raspi/views/wifi_view.py - Vista completa de auditoría WiFi para Raspberry Pi.
Restaura todas las opciones originales:
- Clientes Conectados (Single y Dual-Band con enumeración pasiva de 30s)
- Captura Handshake (WPA/WPA2 con inyección deauth)
- Ataque Evil Twin (Single-Band y Dual-Band con 2 interfaces deauth + 1 AP)
- Ataque Deauth (Single-Band y Dual-Band)
- Exploradores de Handshakes, Evil Twin y Clientes
"""

import os
import time
import threading
import gc
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_EVIL, BASE_DIR_CLIENTS
from dragonfly.core.hardware import get_wifi_interfaces, get_network_interfaces
from dragonfly.ui.raspi.theme import (
    COLOR_TEXTO_EXITO,
    COLOR_TEXTO_SECUNDARIO,
    COLOR_TEXTO_ADVERTENCIA
)


class WiFiView(BaseView):
    """
    Vista táctil integral de auditoría inalámbrica para pantalla de 320x240 en Raspberry Pi.
    """

    def __init__(self, app):
        super().__init__(app)
        self.wifi_state = {}
        self.handshake_iface_btns = []
        self.handshake_client_btns = []
        self.client_iface_btns = []
        self.client_scan_btns = []
        self.deauth_iface_btns = []
        self.evil_ap_btns = []
        self.evil_deauth_btns = []
        self.btn_detener_client_enum = None
        self.btn_detener_dual = None
        self.btn_detener_deauth = None
        self.btn_detener_evil = None

    def render(self):
        """Menú principal de auditoría WiFi con las 7 opciones completas."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="AUDITORÍA WIFI", style='Title.TLabel').pack(pady=2)

        scroll_wifi = ScrollableFrame(self.main_frame, max_items=10)
        scroll_wifi.pack(fill='both', expand=True, padx=2, pady=2)

        opciones = [
            ("Clientes Conectados", self._flow_client_list),
            ("Captura Handshake", self._flow_handshake_start),
            ("Ataque Evil Twin", self._flow_evil_twin_start),
            ("Ataque Deauth", self._flow_deauth_menu),
            ("Explorar Handshakes", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI, "Handshakes", self.render)),
            ("Explorar Evil Twin", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_EVIL, "Evil Twin", self.render)),
            ("Explorar Clientes", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_CLIENTS, "Clientes", self.render)),
        ]

        for texto, cmd in opciones:
            scroll_wifi.add_button(text=texto, command=cmd, style='Red.TButton', width=28)

        self.show_console(parent=scroll_wifi.scrollable_frame)

    # =========================================================================
    # 1. CLIENTES CONECTADOS (SINGLE & DUAL-BAND)
    # =========================================================================
    def _flow_client_list(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="ENUMERAR CLIENTES", style='Title.TLabel').pack(pady=2)

        interfaces = get_wifi_interfaces()
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces WiFi.", style='Dark.TLabel').pack(pady=10)
            self.show_console()
            return

        if len(interfaces) < 2:
            self._flow_client_single_select_iface(from_direct=True)
        else:
            scroll = ScrollableFrame(self.main_frame, max_items=10)
            scroll.pack(fill='both', expand=True, padx=2, pady=2)
            ttk.Label(scroll.scrollable_frame, text="Seleccione modalidad:", style='Gray.TLabel').pack(pady=(0, 4))

            scroll.add_button(text="Single-band (1 Interfaz)", command=self._flow_client_single_select_iface, style='Red.TButton', width=28)
            scroll.add_button(text="Dual-band (2 Interfaces)", command=self._flow_client_dual_select_ifaces, style='Danger.TButton', width=28)
            self.show_console(parent=scroll.scrollable_frame)

    def _flow_client_single_select_iface(self, from_direct=False):
        self.clear_frame()
        self.add_back_button(self.render if from_direct else self._flow_client_list)
        ttk.Label(self.main_frame, text="SINGLE-BAND: IFACE", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.client_iface_btns = []
        for iface in get_wifi_interfaces():
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_client_scan(i, mode='single'),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.client_iface_btns.append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_client_dual_select_ifaces(self):
        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="DUAL-BAND: IFACES", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        ttk.Label(scroll.scrollable_frame, text="Seleccione 2 interfaces:", style='Gray.TLabel').pack(pady=(0, 4))

        self.wifi_state.setdefault("dual_client", {})["selected"] = []
        self.wifi_state["dual_client"]["btns"] = []

        for iface in get_wifi_interfaces():
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_client_dual_add(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.wifi_state["dual_client"]["btns"].append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_client_dual_add(self, iface):
        state = self.wifi_state["dual_client"]
        selected = state["selected"]
        if iface in selected:
            return
        selected.append(iface)

        for btn in state["btns"]:
            if btn.cget("text") == iface:
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])
                break

        if len(selected) == 2:
            self.write_console(f"[*] Interfaces seleccionadas: {selected[0]}, {selected[1]}")
            self._flow_client_scan(selected[0], iface_5g=selected[1], mode='dual')

    def _flow_client_scan(self, iface, iface_5g=None, mode='single'):
        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="ESCANEANDO REDES...", style='Title.TLabel').pack(pady=2)
        self.show_console()

        self.wifi_state["client_scan_mode"] = mode
        self.wifi_state["iface_2g"] = iface
        self.wifi_state["iface_5g"] = iface_5g

        def worker():
            mon_2g = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface_2g"] = mon_2g

            mon_5g = None
            if mode == 'dual' and iface_5g:
                mon_5g = self.services.wifi.enable_monitor_mode(iface_5g)
                self.wifi_state["mon_iface_5g"] = mon_5g

            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando espectro (20s)..."))

            if mode == 'dual' and mon_5g:
                redes_unicas, iface_map = self.services.wifi.scan_networks_dual(mon_2g, mon_5g, duration=20)
            else:
                redes = self.services.wifi.scan_networks(mon_2g, duration=20)
                redes_unicas = list({v['bssid']: v for v in redes}.values())
                iface_map = {r['bssid']: mon_2g for r in redes_unicas}

            self.run_on_ui(lambda: self._flow_client_show_networks(redes_unicas, iface_map))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_client_show_networks(self, redes, iface_map):
        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="RED OBJETIVO", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No hay redes detectadas.", style='Dark.TLabel').pack(pady=10)
            return

        mode = self.wifi_state.get("client_scan_mode", "single")
        scroll = ScrollableFrame(self.main_frame, max_items=80)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        if mode == 'dual':
            state = self.wifi_state["dual_client"]
            state["selected_networks"] = []
            state["network_btns"] = []

            self.lbl_dual_selected = ttk.Label(
                scroll.scrollable_frame,
                text="Seleccionadas: 0 de 2",
                style='Mono.TLabel',
                foreground=COLOR_TEXTO_ADVERTENCIA
            )
            self.lbl_dual_selected.pack(anchor='w', padx=5, pady=(5, 0))

            self.btn_dual_enum = ttk.Button(
                scroll.scrollable_frame,
                text="Iniciar Enumeración Dual (2 redes)",
                style='Gray.TButton',
                command=self._flow_client_dual_start_enumeration,
                state='disabled'
            )
            self.btn_dual_enum.pack(pady=5, fill='x', padx=20)

            for red in sorted(redes, key=lambda x: (x.get('banda', ''), x.get('essid', ''))):
                mon_asociada = iface_map.get(red['bssid'])
                texto = f"{red.get('essid', 'Oculta')} (Ch:{red['ch']}, {red.get('banda', '')})"
                btn = ttk.Button(
                    scroll.scrollable_frame,
                    text=texto,
                    style='Gray.TButton',
                    command=lambda r=red, m=mon_asociada: self._flow_client_dual_network_selected(r, m)
                )
                btn.pack(fill='x', padx=10, pady=3)
                state["network_btns"].append(btn)
        else:
            for red in sorted(redes, key=lambda x: (x.get('banda', ''), x.get('essid', ''))):
                texto = f"{red.get('essid', 'Oculta')} (Ch:{red['ch']}, {red.get('banda', '')})"
                mon_asociada = iface_map.get(red['bssid'])
                scroll.add_button(
                    text=texto,
                    command=lambda r=red, m=mon_asociada: self._flow_client_select_target(r, m),
                    style='Gray.TButton',
                    width=28
                )

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_client_dual_network_selected(self, red, iface_mon):
        state = self.wifi_state["dual_client"]
        selected = state.setdefault("selected_networks", [])
        if any(r['bssid'] == red['bssid'] for r, _ in selected) or len(selected) >= 2:
            return
        selected.append((red, iface_mon))
        count = len(selected)
        if hasattr(self, 'lbl_dual_selected'):
            self.lbl_dual_selected.config(text=f"Seleccionadas: {count} de 2")
        self.write_console(f"[*] Red añadida: {red['essid']} ({red.get('banda', '')})")
        if count == 2:
            self.btn_dual_enum.config(style='Red.TButton', state='normal')

    def _flow_client_dual_start_enumeration(self):
        state = self.wifi_state["dual_client"]
        selected = state.get("selected_networks", [])
        if len(selected) != 2:
            self.write_console("[!] Seleccione exactamente 2 redes.")
            return

        self.btn_dual_enum.config(state='disabled', style='Gray.TButton')
        for btn in state.get("network_btns", []):
            btn.config(state='disabled')

        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="ENUMERANDO DUAL (30s)...", style='Title.TLabel').pack(pady=5)

        scroll = ScrollableFrame(self.main_frame, max_items=5)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_detener_client_enum = scroll.add_button(
            text="DETENER ENUMERACIÓN",
            command=self._flow_client_enum_stop,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)
        self.write_console("[*] Iniciando enumeración dual (30s)...")

        def worker():
            resultados = self.services.wifi.scan_clients_dual(selected, duration=30)
            self.services.wifi.save_client_results(resultados, is_dual=True)
            self.run_on_ui(lambda: self._flow_client_dual_show_results(resultados))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_client_dual_show_results(self, resultados):
        self.clear_frame()
        self.add_back_button(self._flow_client_restore)
        ttk.Label(self.main_frame, text="RESULTADOS DUAL", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=15)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        def action_save_restore():
            btn_save.config(style='Gray.TButton')
            btn_save.state(['disabled'])
            self._flow_client_restore()

        btn_save = scroll.add_button(text="Guardar y volver al menú", command=action_save_restore, style='Red.TButton', width=28)
        self.show_console(parent=scroll.scrollable_frame)

        self.write_console("[+] Enumeración dual completada. Datos guardados en Resultados_Clientes/")
        for red, macs in resultados:
            self.write_console(f"\n[+] {red['essid']} ({red.get('banda', '')}) - {len(macs)} clientes")
            if macs:
                for mac in macs:
                    self.write_console(f"  -> {mac}")
            else:
                self.write_console("  -> (ninguno)")
        gc.collect()

    def _flow_client_select_target(self, red, iface_mon):
        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="CONFIRMAR ENUMERACIÓN", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        info = f"ESSID: {red['essid']}\nBSSID: {red['bssid']}\nCanal: {red['ch']} ({red.get('banda', '')})"
        ttk.Label(scroll.scrollable_frame, text=info, style='Mono.TLabel', justify='center').pack(pady=10)

        self.client_scan_btns = []
        btn_iniciar = scroll.add_button(
            text="Iniciar Enumeración (30s)",
            command=lambda: self._flow_client_start_enum(red, iface_mon),
            style='Red.TButton',
            width=28
        )
        if btn_iniciar:
            self.client_scan_btns.append(btn_iniciar)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_client_start_enum(self, red, iface_mon):
        self.clear_frame()
        self.add_back_button(self._flow_client_list)
        ttk.Label(self.main_frame, text="ENUMERANDO CLIENTES...", style='Title.TLabel').pack(pady=5)

        scroll = ScrollableFrame(self.main_frame, max_items=5)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_detener_client_enum = scroll.add_button(
            text="DETENER ENUMERACIÓN",
            command=self._flow_client_enum_stop,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)
        self.write_console(f"[*] Recopilando MACs pasivamente (30s)...")

        def worker():
            clientes = self.services.wifi.scan_clients_passive(iface_mon, red['bssid'], red['ch'], duration=30)
            self.run_on_ui(lambda: self._flow_client_show_results(clientes, red))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_client_show_results(self, clientes, red):
        self.clear_frame()
        self.add_back_button(self._flow_client_restore)
        ttk.Label(self.main_frame, text="CLIENTES ENCONTRADOS", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        if not clientes:
            ttk.Label(scroll.scrollable_frame, text="0 clientes detectados.", style='Dark.TLabel').pack(pady=10)
        else:
            for mac in clientes:
                scroll.add_button(text=f"{mac} (Detectado)", command=lambda: None, style='Gray.TButton', width=28)

        def action_save_restore():
            btn_save.config(style='Gray.TButton')
            btn_save.state(['disabled'])
            try:
                res_dir = self.services.wifi.save_client_results((red, clientes), is_dual=False)
                self.write_console(f"[+] Resultados guardados en {res_dir}/")
            except Exception as e:
                self.write_console(f"[!] Error al guardar: {e}")
            self._flow_client_restore()

        btn_save = scroll.add_button(text="Guardar y volver", command=action_save_restore, style='Red.TButton', width=28)
        self.show_console(parent=scroll.scrollable_frame)
        self.write_console(f"[+] Total clientes: {len(clientes)}. Pulse Guardar y volver.")
        gc.collect()

    def _flow_client_enum_stop(self):
        self.write_console("\n[!] Abortando enumeración de clientes...")
        if self.btn_detener_client_enum and self.btn_detener_client_enum.winfo_exists():
            self.btn_detener_client_enum.config(style='Gray.TButton')
            self.btn_detener_client_enum.state(['disabled'])
        self.services.wifi.stop_client_enum()
        self._flow_client_restore()

    def _flow_client_restore(self):
        self.write_console("[*] Deteniendo monitor y restaurando red...")

        def worker():
            mons = [self.wifi_state.get("mon_iface_2g"), self.wifi_state.get("mon_iface_5g")]
            self.services.wifi.restore_wifi_system([m for m in mons if m])
            self.run_on_ui(self.render)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # 2. CAPTURA HANDSHAKE
    # =========================================================================
    def _flow_handshake_start(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="CAPTURAR: Elija IFace", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        interfaces = get_wifi_interfaces()
        if not interfaces:
            ttk.Label(scroll.scrollable_frame, text="No hay interfaces Wi-Fi.", style='Dark.TLabel').pack()
            self.show_console(parent=scroll.scrollable_frame)
            return

        self.handshake_iface_btns = []
        for iface in interfaces:
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_handshake_scan_networks(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.handshake_iface_btns.append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_handshake_scan_networks(self, iface):
        for btn in getattr(self, 'handshake_iface_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["iface"] = iface
        self.write_console(f"[*] Preparando modo monitor en {iface}...")

        def worker():
            mon = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon
            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando 15s en {mon}..."))
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_handshake_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self._flow_handshake_start)
        ttk.Label(self.main_frame, text="SELECCIONA RED", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No hay redes detectadas.", style='Dark.TLabel').pack()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        for red in redes:
            texto = f"{red['essid']} (CH:{red['ch']})"
            scroll.add_button(
                text=texto,
                style='Gray.TButton',
                width=28,
                command=lambda r=red: self._flow_handshake_select_client(r)
            )

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_handshake_select_client(self, red):
        self.wifi_state["target"] = red
        self.clear_frame()
        self.add_back_button(lambda: self._flow_handshake_show_networks([red]))
        ttk.Label(self.main_frame, text=f"ESCANEANDO CLIENTES\n{red['essid']}", style='Title.TLabel', justify='center').pack(pady=10)
        self.show_console()
        self.write_console(f"[*] Capturando tráfico de {red['essid']} por 10s...")

        def worker():
            mon = self.wifi_state["mon_iface"]
            clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)

            def actualizar_gui():
                self.clear_frame()
                self.add_back_button(lambda: self._flow_handshake_show_networks([red]))
                ttk.Label(self.main_frame, text="CLIENTES ENCONTRADOS", style='Title.TLabel').pack(pady=2)

                scroll = ScrollableFrame(self.main_frame, max_items=50)
                scroll.pack(fill='both', expand=True, padx=5, pady=2)

                self.handshake_client_btns = []

                btn_fin = scroll.add_button(text="FINALIZAR AUDITORÍA", style='Danger.TButton', width=28,
                                            command=self._flow_handshake_finish)
                if btn_fin:
                    self.handshake_client_btns.append(btn_fin)

                btn_broad = scroll.add_button(text="Todos (Broadcast)", style='Danger.TButton', width=28,
                                              command=lambda: self._flow_handshake_launch("FF:FF:FF:FF:FF:FF"))
                if btn_broad:
                    self.handshake_client_btns.append(btn_broad)

                for mac in clientes:
                    btn = scroll.add_button(text=mac, style='Gray.TButton', width=28,
                                            command=lambda m=mac: self._flow_handshake_launch(m))
                    if btn:
                        self.handshake_client_btns.append(btn)

                self.show_console(parent=scroll.scrollable_frame)
                gc.collect()

            self.run_on_ui(actualizar_gui)

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_launch(self, client_mac):
        red = self.wifi_state["target"]
        mon = self.wifi_state["mon_iface"]

        session_dir = self.services.wifi.start_handshake_capture(
            mon_iface=mon,
            target_red=red,
            cliente_mac=client_mac,
            on_output=self.write_console
        )
        self.write_console(f"[+] Captura activa guardándose en {session_dir}")

    def _flow_handshake_finish(self):
        for btn in getattr(self, 'handshake_client_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.write_console("[*] Finalizando auditoría y restaurando red...")

        def worker():
            mon = self.wifi_state.get("mon_iface")
            self.services.wifi.stop_handshake_audit(mon)
            self.wifi_state["mon_iface"] = None
            self.run_on_ui(self.render)

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # 3. ATAQUE EVIL TWIN (SINGLE & DUAL-BAND)
    # =========================================================================
    def _flow_evil_twin_start(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN - IFace AP", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        interfaces = get_network_interfaces()
        if len(interfaces) < 2:
            ttk.Label(scroll.scrollable_frame, text="Requiere al menos 2 interfaces.", style='Dark.TLabel').pack(pady=10)
            self.show_console(parent=scroll.scrollable_frame)
            return

        self.evil_ap_btns = []
        for iface in interfaces:
            btn = scroll.add_button(
                text=f"AP: {iface}",
                command=lambda i=iface: self._flow_evil_twin_select_deauth(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.evil_ap_btns.append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_select_deauth(self, ap_iface):
        for btn in getattr(self, 'evil_ap_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["ap_iface"] = ap_iface
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_start)
        ttk.Label(self.main_frame, text="IFace Deauth", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.evil_deauth_btns = []
        for iface in [i for i in get_network_interfaces() if i != ap_iface]:
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_evil_twin_scan(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.evil_deauth_btns.append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_scan(self, deauth_iface):
        for btn in getattr(self, 'evil_deauth_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["deauth_iface"] = deauth_iface
        self.write_console(f"[*] Preparando interfaces para Evil Twin...")

        def worker():
            mon = self.services.wifi.enable_monitor_mode(deauth_iface)
            self.wifi_state["mon_deauth"] = mon
            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando redes en {mon}..."))
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_evil_twin_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_evil_twin_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self._flow_evil_twin_start)
        ttk.Label(self.main_frame, text="RED OBJETIVO", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No hay redes detectadas.", style='Dark.TLabel').pack()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        for red in redes:
            scroll.add_button(
                text=f"{red['essid']} (CH:{red['ch']})",
                command=lambda r=red: self._flow_evil_twin_select_portal(r),
                style='Gray.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_evil_twin_select_portal(self, red):
        self.wifi_state["evil_target"] = red
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_show_networks([red]))
        ttk.Label(self.main_frame, text="PORTAL CAUTIVO", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        portales = self.services.evil_twin.list_portals()
        for p in portales:
            scroll.add_button(
                text=p,
                command=lambda portal=p: self._flow_evil_twin_modo_deauth(red, portal),
                style='Gray.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_evil_twin_modo_deauth(self, red, portal):
        self.wifi_state["portal_name"] = portal
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_select_portal(red))
        ttk.Label(self.main_frame, text="MODO DEAUTH", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button(
            text="Deauth Single-band",
            command=lambda: self._flow_evil_twin_single_mode(red, portal),
            style='Red.TButton',
            width=28
        )

        interfaces = get_network_interfaces()
        if len(interfaces) >= 3:
            scroll.add_button(
                text="Deauth Dual-band",
                command=lambda: self._flow_evil_twin_dual_select_ifaces(red, portal),
                style='Danger.TButton',
                width=28
            )
        else:
            btn = ttk.Button(
                scroll.scrollable_frame,
                text="Deauth Dual-band (requiere 3 ifaces)",
                style='Gray.TButton',
                state='disabled'
            )
            btn.pack(fill='x', padx=10, pady=4)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_single_mode(self, red, portal):
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_modo_deauth(red, portal))
        ttk.Label(self.main_frame, text="SINGLE DEAUTH MODO", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button(
            text="Broadcast (Todos)",
            command=lambda: self._flow_evil_twin_launch_single(red, portal, "broadcast"),
            style='Danger.TButton',
            width=28
        )

        def escanear_clientes():
            self.write_console("[*] Escaneando clientes para deauth dirigido...")
            mon = self.wifi_state.get("mon_deauth")
            clis = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            if not clis:
                self.write_console("[!] No se detectaron clientes. Lanzando en broadcast.")
                self._flow_evil_twin_launch_single(red, portal, "broadcast")
            else:
                self._flow_evil_twin_launch_single(red, portal, "directed", cliente_mac=clis[0])

        scroll.add_button(text="Cliente específico", command=escanear_clientes, style='Red.TButton', width=28)
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_launch_single(self, red, portal, deauth_mode, cliente_mac=None):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN ACTIVO", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_detener_evil = scroll.add_button(
            text="DETENER EVIL TWIN",
            command=self._flow_evil_twin_stop,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

        ap_iface = self.wifi_state["ap_iface"]
        mon_deauth = self.wifi_state["mon_deauth"]

        def on_cred(line):
            self.write_console(f"[!] CREDENCIAL: {line}")

        self.services.evil_twin.start_evil_twin(
            ap_iface=ap_iface,
            mon_deauth=mon_deauth,
            red_target=red,
            portal_name=portal,
            deauth_mode=deauth_mode,
            cliente_mac=cliente_mac,
            on_output=self.write_console,
            on_cred=on_cred
        )

    def _flow_evil_twin_dual_select_ifaces(self, red, portal):
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_modo_deauth(red, portal))
        ttk.Label(self.main_frame, text="SELEC. 2 IFACES DEAUTH", style='Title.TLabel').pack(pady=2)

        ap_iface = self.wifi_state.get("ap_iface")
        ifaces_disp = [i for i in get_network_interfaces() if i != ap_iface]

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        ttk.Label(scroll.scrollable_frame, text="Marque dos interfaces:", style='Gray.TLabel').pack(pady=(0, 4))

        self.wifi_state.setdefault("dual_evil", {})["selected_ifaces"] = []
        self.wifi_state["dual_evil"]["iface_btns"] = {}

        for iface in ifaces_disp:
            btn = ttk.Button(
                scroll.scrollable_frame,
                text=iface,
                style='Red.TButton',
                command=lambda i=iface: self._flow_evil_twin_dual_add_iface(i, red, portal)
            )
            btn.pack(fill='x', padx=10, pady=3)
            self.wifi_state["dual_evil"]["iface_btns"][iface] = btn

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_dual_add_iface(self, iface, red, portal):
        state = self.wifi_state["dual_evil"]
        selected = state["selected_ifaces"]
        if iface in selected or len(selected) >= 2:
            return
        selected.append(iface)

        if iface in state["iface_btns"]:
            state["iface_btns"][iface].config(style='Gray.TButton', state='disabled')

        if len(selected) == 2:
            self.write_console(f"[*] Interfaces deauth: {selected[0]}, {selected[1]}")
            self._flow_evil_twin_dual_scan(red, portal, selected[0], selected[1])

    def _flow_evil_twin_dual_scan(self, red, portal, iface1, iface2):
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_dual_select_ifaces(red, portal))
        ttk.Label(self.main_frame, text="ESCANEANDO REDES...", style='Title.TLabel').pack(pady=2)
        self.show_console()

        self.wifi_state["dual_evil"]["deauth_iface1"] = iface1
        self.wifi_state["dual_evil"]["deauth_iface2"] = iface2

        def worker():
            mon1 = self.services.wifi.enable_monitor_mode(iface1)
            mon2 = self.services.wifi.enable_monitor_mode(iface2)
            self.wifi_state["dual_evil"]["mon1"] = mon1
            self.wifi_state["dual_evil"]["mon2"] = mon2

            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando con {mon1} (15s)..."))
            redes = self.services.wifi.scan_networks(mon1, duration=15)
            self.run_on_ui(lambda: self._flow_evil_twin_dual_show_networks(redes, red, portal))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_evil_twin_dual_show_networks(self, redes, red_ap, portal):
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_dual_scan(
            red_ap, portal,
            self.wifi_state["dual_evil"]["deauth_iface1"],
            self.wifi_state["dual_evil"]["deauth_iface2"]
        ))
        ttk.Label(self.main_frame, text="SELECCIONA OBJETIVOS", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No se detectaron redes.", style='Dark.TLabel').pack()
            return

        groups = {}
        for r in redes:
            groups.setdefault(r['essid'].lower(), []).append(r)

        dual_pairs = []
        singles = []
        used = set()
        for essid_lower, items in groups.items():
            if len(items) >= 2:
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        if items[i]['ch'] != items[j]['ch']:
                            dual_pairs.append((items[i], items[j]))
                            used.add(items[i]['bssid'])
                            used.add(items[j]['bssid'])
            for item in items:
                if item['bssid'] not in used:
                    singles.append(item)

        scroll = ScrollableFrame(self.main_frame, max_items=80)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        if dual_pairs:
            ttk.Label(scroll.scrollable_frame, text="── Redes dual‑band automáticas ──",
                      style='Mono.TLabel', foreground=COLOR_TEXTO_EXITO).pack(anchor='w', padx=5, pady=(5, 2))
            for r1, r2 in dual_pairs:
                texto = f"{r1['essid']}  (CH{r1['ch']} + CH{r2['ch']})"
                btn = ttk.Button(
                    scroll.scrollable_frame,
                    text=texto,
                    style='Gray.TButton',
                    command=lambda r1=r1, r2=r2: self._flow_evil_twin_dual_launch(r1, r2, red_ap, portal)
                )
                btn.pack(fill='x', padx=10, pady=3)

        if singles:
            ttk.Label(scroll.scrollable_frame, text="── Otras redes (selección manual 2) ──",
                      style='Mono.TLabel', foreground=COLOR_TEXTO_SECUNDARIO).pack(anchor='w', padx=5, pady=(8, 2))
            self.wifi_state["dual_evil"]["manual_sel"] = []
            self.wifi_state["dual_evil"]["manual_btns"] = []
            for red in singles:
                btn = ttk.Button(
                    scroll.scrollable_frame,
                    text=f"{red['essid']} (CH{red['ch']})",
                    style='Gray.TButton',
                    command=lambda r=red: self._flow_evil_twin_dual_add_manual(r, red_ap, portal)
                )
                btn.pack(fill='x', padx=10, pady=2)
                self.wifi_state["dual_evil"]["manual_btns"].append(btn)

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_evil_twin_dual_add_manual(self, red_target, red_ap, portal):
        state = self.wifi_state["dual_evil"]
        manual = state.setdefault("manual_sel", [])
        if any(r['bssid'] == red_target['bssid'] for r in manual) or len(manual) >= 2:
            return
        manual.append(red_target)
        self.write_console(f"[*] Red manual añadida: {red_target['essid']} (CH{red_target['ch']})")
        if len(manual) == 2:
            self._flow_evil_twin_dual_launch(manual[0], manual[1], red_ap, portal)

    def _flow_evil_twin_dual_launch(self, target1, target2, red_ap, portal):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN DUAL ACTIVO", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_detener_evil = scroll.add_button(
            text="DETENER ATAQUE DUAL",
            command=self._flow_evil_twin_stop,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

        ap_iface = self.wifi_state["ap_iface"]
        mon1 = self.wifi_state["dual_evil"]["mon1"]
        mon2 = self.wifi_state["dual_evil"]["mon2"]

        def on_cred(line):
            self.write_console(f"[!] CREDENCIAL: {line}")

        self.services.evil_twin.start_evil_twin_dual(
            ap_iface=ap_iface,
            mon1=mon1,
            mon2=mon2,
            red_ap=red_ap,
            target1=target1,
            target2=target2,
            portal_name=portal,
            on_output=self.write_console,
            on_cred=on_cred
        )

    def _flow_evil_twin_stop(self):
        self.write_console("[*] Deteniendo Evil Twin y restaurando red...")
        if self.btn_detener_evil and self.btn_detener_evil.winfo_exists():
            self.btn_detener_evil.config(style='Gray.TButton')
            self.btn_detener_evil.state(['disabled'])

        self.services.evil_twin.stop_evil_twin()
        self.app.after(3000, self.render)

    # =========================================================================
    # 4. ATAQUE DEAUTH (SINGLE & DUAL-BAND)
    # =========================================================================
    def _flow_deauth_menu(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="MENÚ DEAUTH", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        ttk.Label(scroll.scrollable_frame, text="Seleccione modalidad:", style='Gray.TLabel').pack(pady=(0, 4))

        scroll.add_button(text="Single-band (1 Interfaz)", command=self._flow_deauth_single_start, style='Red.TButton', width=28)
        scroll.add_button(text="Dual-band (2 Interfaces)", command=self._flow_deauth_dual_start, style='Danger.TButton', width=28)

        self.show_console(parent=scroll.scrollable_frame)

    # --- SINGLE-BAND DEAUTH ---
    def _flow_deauth_single_start(self):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_menu)
        ttk.Label(self.main_frame, text="DEAUTH - IFace", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.deauth_iface_btns = []
        for iface in get_wifi_interfaces():
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_deauth_single_scan(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.deauth_iface_btns.append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_deauth_single_scan(self, iface):
        for btn in getattr(self, 'deauth_iface_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["iface"] = iface
        self.write_console(f"[*] Preparando modo monitor para Deauth en {iface}...")

        def worker():
            mon = self.services.wifi.enable_monitor_mode(iface)
            self.wifi_state["mon_iface"] = mon
            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando objetivos..."))
            redes = self.services.wifi.scan_networks(mon, duration=15)
            self.run_on_ui(lambda: self._flow_deauth_single_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_deauth_single_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_single_start)
        ttk.Label(self.main_frame, text="SELECCIONA RED", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No hay redes detectadas.", style='Dark.TLabel').pack()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        for red in redes:
            texto = f"{red['essid']} (CH:{red['ch']})"
            scroll.add_button(
                text=texto,
                command=lambda r=red: self._flow_deauth_single_select_mode(r),
                style='Gray.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_deauth_single_select_mode(self, red):
        self.wifi_state["target"] = red
        self.clear_frame()
        self.add_back_button(self._flow_deauth_single_start)
        ttk.Label(self.main_frame, text="MODO DE ATAQUE", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button(
            text="Broadcast (Todos)",
            command=lambda: self._flow_deauth_single_intensity("FF:FF:FF:FF:FF:FF"),
            style='Danger.TButton',
            width=28
        )
        scroll.add_button(
            text="Cliente específico",
            command=lambda: self._flow_deauth_single_scan_clients(red),
            style='Red.TButton',
            width=28
        )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_deauth_single_scan_clients(self, red):
        self.clear_frame()
        self.add_back_button(lambda: self._flow_deauth_single_select_mode(red))
        ttk.Label(self.main_frame, text=f"RASTREANDO MACs\n{red['essid']}", style='Title.TLabel', justify='center').pack(pady=10)
        self.show_console()
        self.write_console("[*] Escaneando clientes activos en el canal (10s)...")

        def worker():
            mon = self.wifi_state["mon_iface"]
            clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)

            def actualizar_gui():
                self.clear_frame()
                self.add_back_button(lambda: self._flow_deauth_single_select_mode(red))
                ttk.Label(self.main_frame, text="SELECCIONA CLIENTE", style='Title.TLabel').pack(pady=2)

                scroll = ScrollableFrame(self.main_frame, max_items=50)
                scroll.pack(fill='both', expand=True, padx=5, pady=2)

                for mac in clientes:
                    scroll.add_button(
                        text=mac,
                        command=lambda m=mac: self._flow_deauth_single_intensity(m),
                        style='Gray.TButton',
                        width=28
                    )

                self.show_console(parent=scroll.scrollable_frame)
                gc.collect()

            self.run_on_ui(actualizar_gui)

        threading.Thread(target=worker, daemon=True).start()

    def _flow_deauth_single_intensity(self, cliente):
        red = self.wifi_state["target"]
        self.clear_frame()
        self.add_back_button(self._flow_deauth_single_start)
        ttk.Label(self.main_frame, text="INTENSIDAD", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for texto, count in [("Continuo (0)", "0"), ("1 ráfaga (5)", "5"), ("3 ráfagas (15)", "15")]:
            scroll.add_button(
                text=texto,
                command=lambda r=red, c=cliente, cnt=count: self._flow_deauth_single_launch(r, c, cnt),
                style='Red.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_deauth_single_launch(self, red, cliente, count):
        mon = self.wifi_state["mon_iface"]
        self.clear_frame()
        self.add_back_button(lambda: self._flow_deauth_single_select_mode(red))
        ttk.Label(self.main_frame, text="DEAUTH EN CURSO", style='Title.TLabel').pack(pady=5)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        def detener():
            if self.btn_detener_deauth and self.btn_detener_deauth.winfo_exists():
                self.btn_detener_deauth.config(style='Gray.TButton')
                self.btn_detener_deauth.state(['disabled'])

            self.services.wifi.stop_deauth_attack()
            self.write_console("[+] Ataque deauth detenido. Restaurando red...")

            def restore():
                self.services.wifi.restore_wifi_system(self.wifi_state.get("mon_iface"))
                self.run_on_ui(self.render)

            threading.Thread(target=restore, daemon=True).start()

        self.btn_detener_deauth = scroll.add_button(
            text="DETENER DEAUTH",
            command=detener,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

        self.services.wifi.start_deauth_attack(
            mon_iface=mon,
            target_red=red,
            cliente_mac=cliente,
            count=count,
            on_output=self.write_console
        )

    # --- DUAL-BAND DEAUTH ---
    def _flow_deauth_dual_start(self):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_menu)
        ttk.Label(self.main_frame, text="DEAUTH DUAL‑BAND", style='Title.TLabel').pack(pady=2)

        interfaces = get_network_interfaces()
        if len(interfaces) < 2:
            ttk.Label(self.main_frame, text="Se necesitan al menos 2 interfaces físicas.",
                      style='Dark.TLabel', foreground=COLOR_TEXTO_ADVERTENCIA).pack(pady=10)
            self.show_console()
            self.write_console("[!] No hay suficientes interfaces para ataque dual.")
            return

        self.wifi_state.setdefault("dual_deauth", {})["selected"] = []
        self.wifi_state["dual_deauth"]["iface_btns"] = []

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        ttk.Label(scroll.scrollable_frame, text="Seleccione DOS interfaces:", style='Gray.TLabel').pack(pady=(0, 4))
        for iface in interfaces:
            btn = scroll.add_button(
                text=iface,
                style='Red.TButton',
                width=28,
                command=lambda i=iface: self._flow_deauth_dual_select_iface(i)
            )
            if btn:
                self.wifi_state["dual_deauth"]["iface_btns"].append(btn)

        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_deauth_dual_select_iface(self, iface):
        state = self.wifi_state["dual_deauth"]
        selected = state["selected"]
        if iface in selected:
            return
        selected.append(iface)

        for btn in state["iface_btns"]:
            if btn.cget("text") == iface:
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])
                break

        if len(selected) == 2:
            self.write_console(f"[*] Interfaces seleccionadas: {selected[0]}, {selected[1]}")
            self._flow_deauth_dual_scan(selected[0], selected[1])

    def _flow_deauth_dual_scan(self, iface1, iface2):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_dual_start)
        ttk.Label(self.main_frame, text="ESCANEANDO REDES...", style='Title.TLabel').pack(pady=2)
        self.show_console()

        self.wifi_state["dual_deauth"]["iface1"] = iface1
        self.wifi_state["dual_deauth"]["iface2"] = iface2

        def worker():
            mon1 = self.services.wifi.enable_monitor_mode(iface1)
            mon2 = self.services.wifi.enable_monitor_mode(iface2)
            self.wifi_state["dual_deauth"]["mon1"] = mon1
            self.wifi_state["dual_deauth"]["mon2"] = mon2

            self.run_on_ui(lambda: self.write_console(f"[*] Escaneando con {mon1} (15 s)..."))
            redes = self.services.wifi.scan_networks(mon1, duration=15)
            self.run_on_ui(lambda: self._flow_deauth_dual_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_deauth_dual_show_networks(self, redes):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_dual_start)
        ttk.Label(self.main_frame, text="SELECCIONA OBJETIVOS", style='Title.TLabel').pack(pady=2)

        if not redes:
            ttk.Label(self.main_frame, text="No se detectaron redes.", style='Dark.TLabel').pack()
            return

        groups = {}
        for r in redes:
            groups.setdefault(r['essid'].lower(), []).append(r)

        dual_pairs = []
        singles = []
        used = set()
        for essid_lower, items in groups.items():
            if len(items) >= 2:
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        if items[i]['ch'] != items[j]['ch']:
                            dual_pairs.append((items[i], items[j]))
                            used.add(items[i]['bssid'])
                            used.add(items[j]['bssid'])
            for item in items:
                if item['bssid'] not in used:
                    singles.append(item)

        scroll = ScrollableFrame(self.main_frame, max_items=80)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        if dual_pairs:
            ttk.Label(scroll.scrollable_frame, text="── Redes dual‑band detectadas ──",
                      style='Mono.TLabel', foreground=COLOR_TEXTO_EXITO).pack(anchor='w', padx=5, pady=(5, 2))
            for red1, red2 in dual_pairs:
                texto = f"{red1['essid']}  (CH{red1['ch']} + CH{red2['ch']})"
                btn = ttk.Button(
                    scroll.scrollable_frame,
                    text=texto,
                    style='Gray.TButton',
                    command=lambda r1=red1, r2=red2: self._flow_deauth_dual_configure(r1, r2)
                )
                btn.pack(fill='x', padx=10, pady=3)

        if singles:
            ttk.Label(scroll.scrollable_frame, text="── Otras redes disponibles ──",
                      style='Mono.TLabel', foreground=COLOR_TEXTO_SECUNDARIO).pack(anchor='w', padx=5, pady=(8, 2))
            for red in singles:
                texto = f"{red['essid']}  (CH{red['ch']})"
                btn = ttk.Button(
                    scroll.scrollable_frame,
                    text=texto,
                    style='Gray.TButton',
                    command=lambda r=red: self._flow_deauth_dual_add_manual(r)
                )
                btn.pack(fill='x', padx=10, pady=2)

        self.wifi_state["dual_deauth"]["manual_selection"] = []
        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_deauth_dual_add_manual(self, red):
        state = self.wifi_state["dual_deauth"]
        manual = state.setdefault("manual_selection", [])
        if len(manual) >= 2 or any(r['bssid'] == red['bssid'] for r in manual):
            return

        manual.append(red)
        self.write_console(f"[*] Seleccionada manualmente: {red['essid']} (CH{red['ch']})")

        if len(manual) == 2:
            self._flow_deauth_dual_configure(manual[0], manual[1])

    def _flow_deauth_dual_configure(self, red1, red2):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_dual_start)
        ttk.Label(self.main_frame, text="CONFIGURAR ATAQUE DUAL", style='Title.TLabel').pack(pady=2)

        iface1 = self.wifi_state["dual_deauth"]["iface1"]
        iface2 = self.wifi_state["dual_deauth"]["iface2"]

        resumen = (f"Ataque dual:\n"
                   f"{red1['essid']} (CH {red1['ch']}) ← {iface1}\n"
                   f"{red2['essid']} (CH {red2['ch']}) ← {iface2}")
        ttk.Label(self.main_frame, text=resumen, style='Mono.TLabel', justify='center').pack(pady=10)

        ttk.Label(self.main_frame, text="Paquetes por ráfaga:", style='Gray.TLabel').pack(pady=(10, 2))
        burst_var = tk.StringVar(value="0")
        burst_menu = ttk.OptionMenu(self.main_frame, burst_var, "0",
                                    "Continuo (0)", "5", "15", style='Dark.TMenubutton')
        burst_menu.pack()

        def iniciar():
            burst_str = burst_var.get()
            burst = "0" if burst_str == "Continuo (0)" else burst_str
            self._flow_deauth_dual_launch(red1, red2, burst)

        ttk.Button(self.main_frame, text="INICIAR ATAQUE DUAL", style='Red.TButton',
                   command=iniciar).pack(pady=15, fill='x', padx=30)

        self.show_console()
        gc.collect()

    def _flow_deauth_dual_launch(self, red1, red2, burst):
        mon1 = self.wifi_state["dual_deauth"]["mon1"]
        mon2 = self.wifi_state["dual_deauth"]["mon2"]

        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="ATAQUE DUAL EN CURSO", style='Title.TLabel').pack(pady=5)

        scroll = ScrollableFrame(self.main_frame, max_items=5)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        def detener():
            if self.btn_detener_dual and self.btn_detener_dual.winfo_exists():
                self.btn_detener_dual.config(style='Gray.TButton')
                self.btn_detener_dual.state(['disabled'])

            self.services.wifi.stop_dual_deauth()
            self.write_console("[*] Ataque dual detenido. Restaurando interfaces...")

            def restore():
                self.services.wifi.restore_wifi_system([mon1, mon2])
                self.run_on_ui(self.render)

            threading.Thread(target=restore, daemon=True).start()

        self.btn_detener_dual = scroll.add_button(
            text="DETENER DEAUTH DUAL",
            command=detener,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

        self.services.wifi.start_dual_deauth(mon1, mon2, red1, red2, burst=burst, callback=self.write_console)
