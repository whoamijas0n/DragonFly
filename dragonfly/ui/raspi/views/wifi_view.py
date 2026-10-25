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
from dragonfly.ui.raspi.widgets import ScrollableFrame, TecladoCompleto
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_EVIL, BASE_DIR_CLIENTS, BASE_DIR_WIFI_AUDIT
from dragonfly.core.wifi_interfaces import (
    build_internet_candidate,
    get_deauth_interfaces,
    get_evil_twin_ap_interfaces,
    get_internet_ap_interfaces,
    get_internet_scan_interface,
    get_internet_upstream_options,
    get_monitor_interfaces,
)
from dragonfly.services.wifi_audit_service import (
    format_network_compact,
    format_network_detail,
    format_summary,
)
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
        self.handshake_target_btns = []
        self.btn_handshake_finalizar = None
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
        """Menú principal de auditoría WiFi con reconocimiento pasivo y flujos ofensivos."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="AUDITORÍA WIFI", style='Title.TLabel').pack(pady=2)

        scroll_wifi = ScrollableFrame(self.main_frame, max_items=10)
        scroll_wifi.pack(fill='both', expand=True, padx=2, pady=2)

        opciones = [
            ("Reconocimiento WiFi", self._flow_audit_menu),
            ("Clientes Conectados", self._flow_client_list),
            ("Captura Handshake", self._flow_handshake_start),
            ("Ataque Evil Twin", self._flow_evil_twin_start),
            ("Evil Twin + Internet", self._flow_internet_start),
            ("Ataque Deauth", self._flow_deauth_menu),
            ("Explorar Handshakes", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI, "Handshakes", self.render)),
            ("Explorar Evil Twin", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_EVIL, "Evil Twin", self.render)),
            ("Explorar Clientes", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_CLIENTS, "Clientes", self.render)),
            ("Explorar Auditorías WiFi", lambda: self.app.views['explorer'].show_sessions(BASE_DIR_WIFI_AUDIT, "Auditorías WiFi", self.render)),
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

        interfaces = get_monitor_interfaces(unique_phys=True)
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces con modo monitor.", style='Dark.TLabel').pack(pady=10)
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
        for iface in get_monitor_interfaces(unique_phys=True):
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

        for iface in get_monitor_interfaces(unique_phys=True):
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
            try:
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
            except Exception as exc:
                self._flow_worker_error("ERROR DE MONITOR", exc, self._flow_client_list)

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
            try:
                resultados = self.services.wifi.scan_clients_dual(selected, duration=30)
                self.services.wifi.save_client_results(resultados, is_dual=True)
                self.run_on_ui(lambda: self._flow_client_dual_show_results(resultados))
            except Exception as exc:
                self._flow_worker_error("ERROR DE ENUMERACIÓN", exc, self._flow_client_list)

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
            try:
                clientes = self.services.wifi.scan_clients_passive(iface_mon, red['bssid'], red['ch'], duration=30)
                self.run_on_ui(lambda: self._flow_client_show_results(clientes, red))
            except Exception as exc:
                self._flow_worker_error("ERROR DE ENUMERACIÓN", exc, self._flow_client_list)

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

    def _flow_worker_error(self, title, message, back_callback):
        """Muestra un error de un worker sin dejar la pantalla bloqueada."""
        message = str(message) or "Error desconocido."

        def show():
            self.clear_frame()
            self.add_back_button(back_callback)
            ttk.Label(self.main_frame, text=title, style='Title.TLabel').pack(pady=2)
            ttk.Label(
                self.main_frame,
                text=message,
                style='Mono.TLabel',
                justify='left',
                wraplength=290,
            ).pack(padx=8, pady=10)
            self.show_console()
            self.write_console(f"[!] {message}")

        self.run_on_ui(show)

    # =========================================================================
    # 2. CAPTURA HANDSHAKE
    # =========================================================================
    def _flow_handshake_start(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="CAPTURAR: Elija IFace", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        interfaces = get_monitor_interfaces(unique_phys=True)
        if not interfaces:
            ttk.Label(scroll.scrollable_frame, text="No hay interfaces con modo monitor.", style='Dark.TLabel').pack()
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
            try:
                mon = self.services.wifi.enable_monitor_mode(iface)
                self.wifi_state["mon_iface"] = mon
                self.run_on_ui(lambda: self.write_console(f"[*] Escaneando 15s en {mon}..."))
                redes = self.services.wifi.scan_networks(mon, duration=15)
                self.run_on_ui(lambda: self._flow_handshake_show_networks(redes))
            except Exception as exc:
                self._flow_worker_error("ERROR DE MONITOR", exc, self._flow_handshake_start)

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
        self.wifi_state["handshake_capturing"] = False
        self.clear_frame()
        self.add_back_button(lambda: self._flow_handshake_show_networks([red]))
        ttk.Label(self.main_frame, text=f"ESCANEANDO CLIENTES\n{red['essid']}", style='Title.TLabel', justify='center').pack(pady=10)
        self.show_console()
        self.write_console(f"[*] Capturando tráfico de {red['essid']} por 10s...")

        def worker():
            mon = self.wifi_state["mon_iface"]
            try:
                clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE ESCANEO",
                    exc,
                    lambda: self._flow_handshake_show_networks([red]),
                )
                return

            def on_back_handshake():
                if self.wifi_state.get("handshake_capturing"):
                    if self.wifi_state.get("handshake_finishing"):
                        return
                    self.wifi_state["handshake_finishing"] = True
                    self.wifi_state["handshake_capturing"] = False
                    self.write_console("[*] Deteniendo captura de handshake...")

                    def cleanup_and_back():
                        try:
                            self.services.wifi.stop_handshake_capture()
                            self.write_console("[+] Captura de handshake detenida.")
                        except Exception as e:
                            self.write_console(f"[!] Error al detener captura: {e}")
                        finally:
                            self.wifi_state["handshake_finishing"] = False
                            self.run_on_ui(lambda: self._flow_handshake_show_networks([red]))

                    threading.Thread(target=cleanup_and_back, daemon=True).start()
                    return

                self._flow_handshake_show_networks([red])

            def actualizar_gui():
                self.clear_frame()
                self.add_back_button(on_back_handshake)
                ttk.Label(self.main_frame, text="CLIENTES ENCONTRADOS", style='Title.TLabel').pack(pady=2)

                scroll = ScrollableFrame(self.main_frame, max_items=50)
                scroll.pack(fill='both', expand=True, padx=5, pady=2)

                self.handshake_client_btns = []
                self.handshake_target_btns = []

                # Botón de Finalizar Auditoría: siempre desbloqueado y visible
                btn_fin = scroll.add_button(text="FINALIZAR AUDITORÍA", style='Danger.TButton', width=28,
                                            command=self._flow_handshake_finish)
                self.btn_handshake_finalizar = btn_fin
                if btn_fin:
                    self.handshake_client_btns.append(btn_fin)

                # Opción Broadcast
                btn_broad = scroll.add_button(text="Todos (Broadcast)", style='Danger.TButton', width=28,
                                              command=lambda: self._flow_handshake_launch("FF:FF:FF:FF:FF:FF"))
                if btn_broad:
                    self.handshake_target_btns.append(btn_broad)
                    self.handshake_client_btns.append(btn_broad)

                # Clientes detectados
                for mac in clientes:
                    btn = scroll.add_button(text=mac, style='Gray.TButton', width=28,
                                            command=lambda m=mac: self._flow_handshake_launch(m))
                    if btn:
                        self.handshake_target_btns.append(btn)
                        self.handshake_client_btns.append(btn)

                self.show_console(parent=scroll.scrollable_frame)
                gc.collect()

            self.run_on_ui(actualizar_gui)

        threading.Thread(target=worker, daemon=True).start()

    def _flow_handshake_launch(self, client_mac):
        if self.wifi_state.get("handshake_capturing"):
            return

        self.wifi_state["handshake_capturing"] = True

        # Bloquear opciones de clientes y broadcast en gris para que no se pueda seleccionar otro cliente
        for btn in getattr(self, 'handshake_target_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        # La opción de finalizar auditoría SIEMPRE tiene que estar desbloqueada
        if getattr(self, 'btn_handshake_finalizar', None) and self.btn_handshake_finalizar.winfo_exists():
            self.btn_handshake_finalizar.config(style='Danger.TButton')
            self.btn_handshake_finalizar.state(['!disabled'])

        red = self.wifi_state["target"]
        mon = self.wifi_state["mon_iface"]

        # Lanzar en segundo plano para no congelar la GUI en los tiempos de espera
        def launch_worker():
            try:
                session_dir = self.services.wifi.start_handshake_capture(
                    mon_iface=mon,
                    target_red=red,
                    cliente_mac=client_mac,
                    on_output=self.write_console
                )
                self.write_console(f"[+] Captura activa guardándose en {session_dir}")
            except Exception as e:
                self.write_console(f"[!] Error al iniciar captura: {e}")

        threading.Thread(target=launch_worker, daemon=True).start()

    def _flow_handshake_finish(self):
        # Evitar dobles pulsaciones mientras la limpieza está en curso
        if self.wifi_state.get("handshake_finishing"):
            return
        self.wifi_state["handshake_finishing"] = True

        # Desactivar botón finalizar para prevenir doble clic y dar respuesta táctil inmediata
        if getattr(self, 'btn_handshake_finalizar', None) and self.btn_handshake_finalizar.winfo_exists():
            self.btn_handshake_finalizar.config(style='Gray.TButton')
            self.btn_handshake_finalizar.state(['disabled'])

        # Asegurar que los botones objetivos sigan bloqueados en gris
        for btn in getattr(self, 'handshake_target_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.write_console("[*] Deteniendo captura de handshake...")

        def cleanup():
            # stop_handshake_capture() espera a sudo/airodump-ng: nunca en el hilo de Tkinter.
            try:
                self.services.wifi.stop_handshake_capture()
                self.write_console("[+] Captura de handshake detenida. Restaurando red...")
            except Exception as e:
                self.write_console(f"[!] Error al detener captura: {e}")

            try:
                mon = self.wifi_state.get("mon_iface")
                self.services.wifi.restore_wifi_system(mon)
            except Exception as e:
                self.write_console(f"[!] Error al restaurar red: {e}")
            finally:
                self.wifi_state["mon_iface"] = None
                self.wifi_state["handshake_capturing"] = False
                self.wifi_state["handshake_finishing"] = False
                self.run_on_ui(self.render)

        threading.Thread(target=cleanup, daemon=True).start()

    # =========================================================================
    # 3. ATAQUE EVIL TWIN (SINGLE & DUAL-BAND)
    # =========================================================================
    def _flow_evil_twin_start(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN - IFace AP", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        interfaces = get_evil_twin_ap_interfaces()
        if not interfaces:
            ttk.Label(
                scroll.scrollable_frame,
                text="Se requieren 2 radios WiFi:\nuna para el AP y otra para deauth.",
                style='Mono.TLabel',
                justify='center',
            ).pack(pady=10)
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
        deauth_ifaces = get_deauth_interfaces(ap_iface)
        if not deauth_ifaces:
            ttk.Label(
                scroll.scrollable_frame,
                text="No hay otra radio con modo monitor\npara lanzar el deauth.",
                style='Mono.TLabel',
                justify='center',
            ).pack(pady=10)
        for iface in deauth_ifaces:
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
            try:
                mon = self.services.wifi.enable_monitor_mode(deauth_iface)
                self.wifi_state["mon_deauth"] = mon
                self.run_on_ui(lambda: self.write_console(f"[*] Escaneando redes en {mon}..."))
                redes = self.services.wifi.scan_networks(mon, duration=15)
                self.run_on_ui(lambda: self._flow_evil_twin_show_networks(redes))
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE MONITOR",
                    exc,
                    self._flow_evil_twin_start,
                )

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

        deauth_ifaces = get_deauth_interfaces(self.wifi_state.get("ap_iface", ""))
        if len(deauth_ifaces) >= 2:
            scroll.add_button(
                text="Deauth Dual-band",
                command=lambda: self._flow_evil_twin_dual_select_ifaces(red, portal),
                style='Danger.TButton',
                width=28
            )
        else:
            btn = ttk.Button(
                scroll.scrollable_frame,
                text="Deauth Dual-band (requiere 2 radios deauth)",
                style='Gray.TButton',
                state='disabled'
            )
            btn.pack(fill='x', padx=10, pady=4)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_single_mode(self, red, portal):
        self.wifi_state["evil_scan_pending"] = False
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
        scroll.add_button(
            text="Cliente específico",
            command=lambda: self._flow_evil_twin_scan_clients(red, portal),
            style='Red.TButton',
            width=28
        )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_evil_twin_scan_clients(self, red, portal):
        """Escanea en segundo plano los clientes asociados a la red objetivo."""
        self.wifi_state["evil_scan_pending"] = True
        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_cancel_client_scan(red, portal))
        ttk.Label(self.main_frame, text=f"BUSCANDO CLIENTES\n{red['essid']}",
                  style='Title.TLabel', justify='center').pack(pady=10)
        self.show_console()
        self.write_console("[*] Rastreando clientes asociados (10s)...")

        def worker():
            try:
                mon = self.wifi_state.get("mon_deauth")
                if not mon:
                    deauth_iface = self.wifi_state.get("deauth_iface")
                    if deauth_iface:
                        mon = self.services.wifi.enable_monitor_mode(deauth_iface)
                        self.wifi_state["mon_deauth"] = mon
                if not mon:
                    self.run_on_ui(lambda: self._flow_evil_twin_show_clients(
                        red, portal, [], error="No hay interfaz en modo monitor."))
                    return
                clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
                self.run_on_ui(lambda: self._flow_evil_twin_show_clients(red, portal, clientes))
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE ESCANEO",
                    exc,
                    lambda: self._flow_evil_twin_single_mode(red, portal),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _flow_evil_twin_cancel_client_scan(self, red, portal):
        """Aborta la espera del escaneo y descarta resultados tardíos."""
        self.wifi_state["evil_scan_pending"] = False
        self._flow_evil_twin_single_mode(red, portal)

    def _flow_evil_twin_show_clients(self, red, portal, clientes, error=None):
        """Muestra la lista de MACs detectadas para elegir la víctima del deauth dirigido."""
        if not self.wifi_state.get("evil_scan_pending"):
            # El operador abandonó la pantalla de escaneo: descartar resultados tardíos.
            return
        self.wifi_state["evil_scan_pending"] = False

        self.clear_frame()
        self.add_back_button(lambda: self._flow_evil_twin_single_mode(red, portal))
        ttk.Label(self.main_frame, text="SELECCIONAR MAC", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        scroll.add_button(
            text="Todos (Broadcast)",
            command=lambda: self._flow_evil_twin_launch_single(red, portal, "broadcast"),
            style='Danger.TButton',
            width=28
        )

        if clientes:
            for mac in clientes:
                scroll.add_button(
                    text=mac,
                    command=lambda m=mac: self._flow_evil_twin_launch_single(red, portal, "directed", cliente_mac=m),
                    style='Gray.TButton',
                    width=28
                )
        else:
            scroll.add_button(
                text="Reintentar escaneo",
                command=lambda: self._flow_evil_twin_scan_clients(red, portal),
                style='Red.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)

        if error:
            self.write_console(f"[!] {error} Use Broadcast o reintente el escaneo.")
        elif clientes:
            self.write_console(f"[+] Clientes detectados: {len(clientes)}. Pulse la MAC objetivo.")
        else:
            self.write_console("[!] No se detectaron clientes. Puede reintentar el escaneo o usar Broadcast.")

        gc.collect()

    def _flow_evil_twin_launch_single(self, red, portal, deauth_mode, cliente_mac=None):
        self.wifi_state["evil_scan_pending"] = False
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

        ap_iface = self.wifi_state.get("ap_iface")
        mon_deauth = self.wifi_state.get("mon_deauth")
        if not ap_iface:
            self._flow_worker_error(
                "ERROR EVIL TWIN",
                "No hay interfaz AP seleccionada.",
                self._flow_evil_twin_start,
            )
            return
        if not mon_deauth:
            self.write_console("[!] Sin interfaz de monitor: el AP arrancará sin deauth.")

        if deauth_mode == "directed" and cliente_mac:
            self.write_console(f"[*] Deauth dirigido al cliente: {cliente_mac}")
        else:
            self.write_console("[*] Deauth en modo broadcast (todos los clientes).")

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
        ifaces_disp = get_deauth_interfaces(ap_iface) if ap_iface else []

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
            try:
                mon1 = self.services.wifi.enable_monitor_mode(iface1)
                mon2 = self.services.wifi.enable_monitor_mode(iface2)
                self.wifi_state["dual_evil"]["mon1"] = mon1
                self.wifi_state["dual_evil"]["mon2"] = mon2

                self.run_on_ui(lambda: self.write_console(f"[*] Escaneando con {mon1} (15s)..."))
                redes = self.services.wifi.scan_networks(mon1, duration=15)
                self.run_on_ui(lambda: self._flow_evil_twin_dual_show_networks(redes, red, portal))
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE MONITOR",
                    exc,
                    lambda: self._flow_evil_twin_dual_select_ifaces(red, portal),
                )

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

        ap_iface = self.wifi_state.get("ap_iface")
        mon1 = self.wifi_state.get("dual_evil", {}).get("mon1")
        mon2 = self.wifi_state.get("dual_evil", {}).get("mon2")
        if not ap_iface or not mon1 or not mon2:
            self._flow_worker_error(
                "ERROR EVIL TWIN DUAL",
                "Faltan interfaces AP o deauth.",
                self.render,
            )
            return

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

        def stopper():
            self.services.evil_twin.stop_evil_twin()
            self.services.evil_twin.wait_until_stopped(timeout=25)
            self.run_on_ui(self.render)

        threading.Thread(target=stopper, daemon=True).start()

    # =========================================================================
    # 3b. EVIL TWIN + INTERNET (NAT)
    # =========================================================================
    @staticmethod
    def _internet_band_text(bands):
        bands = bands or {}
        if bands.get("2.4") and bands.get("5"):
            return "2.4/5G"
        if bands.get("5"):
            return "5G"
        return "2.4G"

    def _flow_internet_start(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN + INTERNET",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        interfaces = get_internet_ap_interfaces()
        if not interfaces:
            ttk.Label(
                scroll.scrollable_frame,
                text=("No hay una radio AP libre con salida a Internet.\n"
                      "Conecte el upstream por WiFi/Ethernet o añada otro adaptador."),
                style='Mono.TLabel',
                justify='center',
                wraplength=290,
            ).pack(pady=10)
            self.show_console(parent=scroll.scrollable_frame)
            return

        ttk.Label(
            scroll.scrollable_frame,
            text=("Elija la radio que emitirá el AP. Después podrá elegir\n"
                  "la interfaz por la que saldrá Internet.\n"
                  "Si usa como AP la interfaz de SSH, perderá el acceso remoto."),
            style='Gray.TLabel',
            justify='center',
            wraplength=290,
        ).pack(pady=(0, 4))

        for option in interfaces:
            ap_iface = option["ap_iface"]
            scroll.add_button(
                text=(f"AP: {ap_iface} "
                      f"({self._internet_band_text(option.get('bands'))})"),
                command=lambda i=ap_iface: self._flow_internet_select_upstream(i),
                style='Red.TButton',
                width=30,
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_select_upstream(self, ap_iface):
        self.wifi_state["inet_ap_iface"] = ap_iface
        self.clear_frame()
        self.add_back_button(self._flow_internet_start)
        ttk.Label(self.main_frame, text="INTERNET (UPSTREAM)",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        upstreams = get_internet_upstream_options(ap_iface)
        if not upstreams:
            ttk.Label(
                scroll.scrollable_frame,
                text=("No hay una interfaz con salida a Internet para este AP.\n"
                      "Conecte el upstream o elija otra radio para el AP."),
                style='Mono.TLabel',
                justify='center',
                wraplength=290,
            ).pack(pady=10)
            self.show_console(parent=scroll.scrollable_frame)
            return

        ttk.Label(
            scroll.scrollable_frame,
            text=f"AP seleccionado: {ap_iface}",
            style='Gray.TLabel',
            justify='center',
            wraplength=290,
        ).pack(pady=(0, 4))

        for upstream in upstreams:
            iface = upstream.get("iface", "?")
            ip = upstream.get("ip", "?")
            scroll.add_button(
                text=f"Internet: {iface} ({ip})",
                command=lambda u=upstream: self._flow_internet_select_roles(
                    ap_iface, u
                ),
                style='Red.TButton',
                width=30,
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_select_roles(self, ap_iface, upstream):
        candidate = build_internet_candidate(ap_iface, upstream)
        if not candidate:
            self._flow_worker_error(
                "COMBINACIÓN INVÁLIDA",
                "El AP y el upstream no pueden ser la misma interfaz ni "
                "compartir radio.",
                self._flow_internet_start,
            )
            return
        self.wifi_state["inet_candidate"] = candidate
        self._flow_internet_select_mode(candidate)

    def _flow_internet_select_mode(self, candidate):
        self.wifi_state["inet_candidate"] = candidate
        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_internet_select_upstream(candidate["ap_iface"])
        )
        ttk.Label(self.main_frame, text="MODO DEAUTH",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        upstream = candidate.get("upstream") or {}
        ttk.Label(
            scroll.scrollable_frame,
            text=f"AP {candidate['ap_iface']} | Internet {upstream.get('iface', '?')}",
            style='Gray.TLabel',
            justify='center',
            wraplength=290,
        ).pack(pady=(0, 4))

        scroll.add_button(
            text="Sin deauth (recomendado)",
            command=lambda: self._flow_internet_ssid_mode(candidate, "none", []),
            style='Red.TButton',
            width=30,
        )

        monitors = candidate.get("monitor_ifaces") or []
        if monitors:
            scroll.add_button(
                text=f"Deauth single ({monitors[0]})",
                command=lambda: self._flow_internet_ssid_mode(
                    candidate, "single", monitors[:1]
                ),
                style='Danger.TButton',
                width=30,
            )
        else:
            ttk.Label(
                scroll.scrollable_frame,
                text="Deauth single: requiere una radio monitor libre.",
                style='Gray.TLabel',
                wraplength=290,
            ).pack(pady=2)

        if len(monitors) >= 2:
            scroll.add_button(
                text="Deauth dual (2 monitores)",
                command=lambda: self._flow_internet_ssid_mode(
                    candidate, "dual", monitors[:2]
                ),
                style='Danger.TButton',
                width=30,
            )
        else:
            ttk.Label(
                scroll.scrollable_frame,
                text="Deauth dual: requiere 2 radios monitor libres.",
                style='Gray.TLabel',
                wraplength=290,
            ).pack(pady=2)

        ttk.Label(
            scroll.scrollable_frame,
            text="Con deauth hay que clonar el SSID de la red objetivo.",
            style='Gray.TLabel',
            justify='center',
            wraplength=290,
        ).pack(pady=(4, 0))
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_ssid_mode(self, candidate, mode, monitors):
        self.wifi_state["inet_mode"] = mode
        self.wifi_state["inet_monitors"] = list(monitors)
        self.clear_frame()
        self.add_back_button(lambda: self._flow_internet_select_mode(candidate))
        ttk.Label(self.main_frame, text="SSID DEL AP",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if mode == "none":
            scroll.add_button(
                text="Nombre personalizado",
                command=lambda: self._flow_internet_custom_ssid(
                    candidate, mode, monitors
                ),
                style='Red.TButton',
                width=30,
            )
            scroll.add_button(
                text="Clonar red escaneada",
                command=lambda: self._flow_internet_scan(
                    candidate, mode, monitors
                ),
                style='Danger.TButton',
                width=30,
            )
        else:
            ttk.Label(
                scroll.scrollable_frame,
                text=("El deauth solo tiene sentido si el AP clona la red\n"
                      "cuyos clientes se van a expulsar."),
                style='Mono.TLabel',
                justify='center',
                wraplength=290,
            ).pack(pady=4)
            scroll.add_button(
                text="Clonar red objetivo",
                command=lambda: self._flow_internet_scan(
                    candidate, mode, monitors
                ),
                style='Danger.TButton',
                width=30,
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_cancel_scan(self, candidate, mode, monitors):
        """Vuelve a la selección de SSID restaurando la radio de escaneo."""
        mon = self.wifi_state.pop("inet_scan_mon", None)
        temporary = bool(self.wifi_state.pop("inet_scan_temp", False))
        if not mon or not temporary:
            self._flow_internet_ssid_mode(candidate, mode, monitors)
            return

        self.write_console(f"[*] Restaurando radio de escaneo {mon}...")

        def worker():
            try:
                self.services.wifi.disable_monitor_mode(mon)
            except Exception as exc:
                self.write_console(f"[!] No se pudo restaurar {mon}: {exc}")
            self.run_on_ui(
                lambda: self._flow_internet_ssid_mode(candidate, mode, monitors)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _flow_internet_custom_ssid(self, candidate, mode, monitors):
        variable = tk.StringVar(value="")
        teclado = TecladoCompleto(
            self.app, variable, titulo="SSID personalizado"
        )
        self.app.wait_window(teclado)

        ssid = (variable.get() or "").strip()
        if not ssid or ssid == "CANCELADO":
            return
        try:
            ssid = self.services.evil_twin.validate_ssid(ssid)
        except ValueError as exc:
            self._flow_worker_error(
                "SSID INVÁLIDO",
                exc,
                lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
            )
            return

        self._flow_internet_select_band(candidate, mode, monitors, ssid)

    def _flow_internet_select_band(self, candidate, mode, monitors, ssid,
                                   deauth_targets=None):
        bands = candidate.get("bands") or {}
        options = [("2.4 GHz (CH 6)", 6)]
        if bands.get("5"):
            options.append(("5 GHz (CH 36)", 36))

        if len(options) == 1:
            self._flow_internet_options(
                candidate, mode, monitors,
                {"essid": ssid, "ch": options[0][1], "banda": "2.4"},
                deauth_targets=deauth_targets,
            )
            return

        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_internet_cancel_scan(candidate, mode, monitors)
        )
        ttk.Label(self.main_frame, text="BANDA DEL AP",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        ttk.Label(
            scroll.scrollable_frame,
            text=f"SSID: {ssid}",
            style='Gray.TLabel',
            wraplength=290,
        ).pack(pady=(0, 4))
        for label, channel in options:
            scroll.add_button(
                text=label,
                command=lambda ch=channel: self._flow_internet_options(
                    candidate, mode, monitors,
                    {"essid": ssid, "ch": ch,
                     "banda": "5" if ch > 14 else "2.4"},
                    deauth_targets=deauth_targets,
                ),
                style='Red.TButton',
                width=30,
            )
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_scan(self, candidate, mode, monitors,
                            deauth_targets=None, second_target=False):
        upstream = candidate.get("upstream") or {}
        scan_iface, temporary = get_internet_scan_interface(
            candidate["ap_iface"], monitors, upstream.get("iface")
        )
        if not scan_iface:
            self._flow_worker_error(
                "SIN RADIO MONITOR",
                "No hay una radio monitor libre para escanear. "
                "Use un SSID personalizado o añada otro adaptador.",
                lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
            )
            return

        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_internet_cancel_scan(candidate, mode, monitors)
        )
        title = "SEGUNDA RED (DEAUTH)" if second_target else "ESCANEANDO REDES..."
        ttk.Label(self.main_frame, text=title, style='Title.TLabel').pack(pady=2)
        self.show_console()
        self.write_console(f"[*] Escaneando con {scan_iface} (15s)...")

        def worker():
            try:
                mon = self.services.wifi.enable_monitor_mode(scan_iface)
                self.wifi_state["inet_scan_mon"] = mon
                self.wifi_state["inet_scan_temp"] = bool(temporary)
                redes = self.services.wifi.scan_networks(mon, duration=15)
                self.run_on_ui(lambda: self._flow_internet_show_networks(
                    redes, candidate, mode, monitors,
                    temporary, deauth_targets, second_target,
                ))
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE ESCANEO",
                    exc,
                    lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _flow_internet_show_networks(self, redes, candidate, mode, monitors,
                                     temporary, deauth_targets=None,
                                     second_target=False):
        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_internet_cancel_scan(candidate, mode, monitors)
        )
        title = "SEGUNDA RED (DEAUTH)" if second_target else "RED A CLONAR"
        ttk.Label(self.main_frame, text=title, style='Title.TLabel').pack(pady=2)

        validas = [red for red in (redes or []) if str(red.get("essid") or "").strip()]
        if not validas:
            ttk.Label(
                self.main_frame,
                text="No se detectaron redes con SSID visible.",
                style='Dark.TLabel',
            ).pack(pady=6)
            self.show_console()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for red in validas:
            essid = str(red.get("essid") or "").strip()
            channel = red.get("ch", "?")
            scroll.add_button(
                text=f"{essid[:19]} (CH:{channel})",
                command=lambda r=red: self._flow_internet_target_selected(
                    r, candidate, mode, monitors,
                    temporary, deauth_targets, second_target,
                ),
                style='Gray.TButton',
                width=30,
            )
        self.show_console(parent=scroll.scrollable_frame)
        gc.collect()

    def _flow_internet_target_selected(self, red, candidate, mode, monitors,
                                       temporary, deauth_targets=None,
                                       second_target=False):
        original = dict(red)
        try:
            essid = self.services.evil_twin.validate_ssid(original.get("essid"))
        except ValueError as exc:
            self._flow_worker_error(
                "SSID INVÁLIDO", exc,
                lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
            )
            return

        if mode == "dual" and not second_target:
            self.wifi_state["inet_dual_first"] = original
            self._flow_internet_scan(
                candidate, mode, monitors,
                deauth_targets=[original], second_target=True,
            )
            return

        if mode == "dual":
            first = self.wifi_state.get("inet_dual_first") or original
            try:
                first_essid = self.services.evil_twin.validate_ssid(
                    first.get("essid")
                )
            except ValueError as exc:
                self._flow_worker_error(
                    "SSID INVÁLIDO", exc,
                    lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
                )
                return
            ap_source = dict(first)
            ap_source["essid"] = first_essid
            targets = [dict(first), dict(original)]
        elif mode == "single":
            ap_source = dict(original)
            ap_source["essid"] = essid
            targets = [dict(original)]
        else:
            ap_source = dict(original)
            ap_source["essid"] = essid
            targets = []

        ap_target = dict(ap_source)
        bands = candidate.get("bands") or {}
        channel = ap_source.get("ch") or 6
        try:
            channel = int(channel)
        except (TypeError, ValueError):
            channel = 6
        if channel > 14 and not bands.get("5"):
            self.write_console(
                f"[!] {candidate['ap_iface']} no soporta 5 GHz; el AP usará CH 6."
            )
            channel = 6
        elif 52 <= channel <= 144:
            self.write_console(
                "[!] Canal DFS clonado; el AP usará CH 36 para evitar CAC."
            )
            channel = 36
        ap_target["ch"] = channel
        ap_target["banda"] = "5" if channel > 14 else "2.4"

        # Si el escaneo usó una radio temporal distinta del AP, devolverla a NM.
        scan_mon = self.wifi_state.get("inet_scan_mon")
        if temporary and scan_mon and scan_mon != candidate["ap_iface"]:
            def restore_scan():
                try:
                    self.services.wifi.disable_monitor_mode(scan_mon)
                except Exception as exc:
                    self.write_console(f"[!] No se pudo restaurar {scan_mon}: {exc}")
                self.wifi_state["inet_scan_mon"] = None
                self.wifi_state["inet_scan_temp"] = False
                self.run_on_ui(lambda: self._flow_internet_options(
                    candidate, mode, monitors, ap_target,
                    deauth_targets=targets,
                ))
            self.write_console(f"[*] Restaurando radio de escaneo {scan_mon}...")
            threading.Thread(target=restore_scan, daemon=True).start()
            return

        self._flow_internet_options(
            candidate, mode, monitors, ap_target, deauth_targets=targets
        )

    def _flow_internet_options(self, candidate, mode, monitors, target,
                               deauth_targets=None):
        self.wifi_state["inet_target"] = target
        self.wifi_state["inet_deauth_targets"] = list(deauth_targets or [])
        self.clear_frame()
        self.add_back_button(
            lambda: self._flow_internet_cancel_scan(candidate, mode, monitors)
        )
        ttk.Label(self.main_frame, text="CONFIRMAR EVIL TWIN",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        upstream = candidate.get("upstream") or {}
        deauth_text = {"none": "sin deauth", "single": "single",
                       "dual": "dual"}.get(mode, mode)
        ttk.Label(
            scroll.scrollable_frame,
            text=(f"SSID: {target.get('essid')}\n"
                  f"AP: {candidate['ap_iface']}  CH: {target.get('ch')}\n"
                  f"Internet: {upstream.get('iface', '?')}\n"
                  f"Deauth: {deauth_text}"),
            style='Mono.TLabel',
            justify='left',
            wraplength=292,
        ).pack(anchor='w', padx=4, pady=3)

        capture = bool(self.wifi_state.get("inet_capture", False))
        capture_available = self.services.evil_twin.capture_available()
        if capture_available:
            scroll.add_button(
                text=f"Captura pcap: {'SÍ' if capture else 'NO'}",
                command=lambda: self._flow_internet_toggle_capture(
                    candidate, mode, monitors, target, deauth_targets
                ),
                style='Gray.TButton',
                width=30,
            )
        else:
            ttk.Label(
                scroll.scrollable_frame,
                text="Captura pcap: no disponible (instale tcpdump).",
                style='Gray.TLabel',
                wraplength=290,
            ).pack(pady=2)

        scroll.add_button(
            text="INICIAR EVIL TWIN + INTERNET",
            command=lambda: self._flow_internet_launch(
                candidate, mode, monitors, target, deauth_targets, capture
            ),
            style='Danger.TButton',
            width=30,
        )
        ttk.Label(
            scroll.scrollable_frame,
            text=("Los clientes navegan por NAT. HTTPS no se descifra;\n"
                  "la captura pcap solo guarda tráfico cifrado."),
            style='Gray.TLabel',
            justify='center',
            wraplength=290,
        ).pack(pady=(4, 0))
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_internet_toggle_capture(self, candidate, mode, monitors, target,
                                      deauth_targets):
        self.wifi_state["inet_capture"] = not bool(
            self.wifi_state.get("inet_capture", False)
        )
        self._flow_internet_options(
            candidate, mode, monitors, target, deauth_targets=deauth_targets
        )

    def _flow_internet_launch(self, candidate, mode, monitors, target,
                              deauth_targets, capture):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="EVIL TWIN + INTERNET",
                  style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        self.btn_detener_internet = scroll.add_button(
            text="DETENER EVIL TWIN",
            command=self._flow_internet_stop,
            style='Danger.TButton',
            width=30,
        )
        self.show_console(parent=scroll.scrollable_frame)

        upstream = candidate.get("upstream") or {}
        self.write_console(
            f"[*] AP {candidate['ap_iface']} | Internet {upstream.get('iface', '?')} "
            f"| SSID {target.get('essid')} | Deauth {mode}"
        )

        def worker():
            actual_monitors = []
            try:
                for base in monitors:
                    actual_monitors.append(
                        self.services.wifi.enable_monitor_mode(base)
                    )
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE MONITOR",
                    exc,
                    lambda: self._flow_internet_ssid_mode(candidate, mode, monitors),
                )
                return

            mon1 = actual_monitors[0] if actual_monitors else None
            mon2 = actual_monitors[1] if len(actual_monitors) > 1 else None
            self.services.evil_twin.start_internet_ap(
                ap_iface=candidate["ap_iface"],
                red_target=target,
                upstream_iface=upstream.get("iface"),
                deauth_mode=mode,
                mon_deauth=mon1,
                mon_deauth2=mon2,
                deauth_targets=deauth_targets,
                capture=bool(capture),
                on_output=self.write_console,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _flow_internet_stop(self):
        self.write_console("[*] Deteniendo Evil Twin + Internet...")
        if (getattr(self, "btn_detener_internet", None)
                and self.btn_detener_internet.winfo_exists()):
            self.btn_detener_internet.config(style='Gray.TButton')
            self.btn_detener_internet.state(['disabled'])

        def stopper():
            self.services.evil_twin.stop_evil_twin()
            self.services.evil_twin.wait_until_stopped(timeout=30)
            self.run_on_ui(self.render)

        threading.Thread(target=stopper, daemon=True).start()

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
        monitor_ifaces = get_monitor_interfaces(unique_phys=True)
        if not monitor_ifaces:
            ttk.Label(
                scroll.scrollable_frame,
                text="No hay interfaces con modo monitor.",
                style='Dark.TLabel',
            ).pack(pady=10)
        for iface in monitor_ifaces:
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
            try:
                mon = self.services.wifi.enable_monitor_mode(iface)
                self.wifi_state["mon_iface"] = mon
                self.run_on_ui(lambda: self.write_console(f"[*] Escaneando objetivos..."))
                redes = self.services.wifi.scan_networks(mon, duration=15)
                self.run_on_ui(lambda: self._flow_deauth_single_show_networks(redes))
            except Exception as exc:
                self._flow_worker_error("ERROR DE MONITOR", exc, self._flow_deauth_single_start)

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
            try:
                clientes = self.services.wifi.scan_clients(mon, red['bssid'], red['ch'], duration=10)
            except Exception as exc:
                self._flow_worker_error(
                    "ERROR DE ESCANEO",
                    exc,
                    lambda: self._flow_deauth_single_select_mode(red),
                )
                return

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

        try:
            self.services.wifi.start_deauth_attack(
                mon_iface=mon,
                target_red=red,
                cliente_mac=cliente,
                count=count,
                on_output=self.write_console
            )
        except Exception as exc:
            self._flow_worker_error(
                "ERROR DE DEAUTH",
                exc,
                lambda: self._flow_deauth_single_select_mode(red),
            )

    # --- DUAL-BAND DEAUTH ---
    def _flow_deauth_dual_start(self):
        self.clear_frame()
        self.add_back_button(self._flow_deauth_menu)
        ttk.Label(self.main_frame, text="DEAUTH DUAL‑BAND", style='Title.TLabel').pack(pady=2)

        interfaces = get_monitor_interfaces(unique_phys=True)
        if len(interfaces) < 2:
            ttk.Label(self.main_frame, text="Se necesitan 2 radios con modo monitor.",
                      style='Dark.TLabel', foreground=COLOR_TEXTO_ADVERTENCIA).pack(pady=10)
            self.show_console()
            self.write_console("[!] No hay suficientes interfaces monitor para ataque dual.")
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
            try:
                mon1 = self.services.wifi.enable_monitor_mode(iface1)
                mon2 = self.services.wifi.enable_monitor_mode(iface2)
                self.wifi_state["dual_deauth"]["mon1"] = mon1
                self.wifi_state["dual_deauth"]["mon2"] = mon2

                self.run_on_ui(lambda: self.write_console(f"[*] Escaneando con {mon1} (15 s)..."))
                redes = self.services.wifi.scan_networks(mon1, duration=15)
                self.run_on_ui(lambda: self._flow_deauth_dual_show_networks(redes))
            except Exception as exc:
                self._flow_worker_error("ERROR DE MONITOR", exc, self._flow_deauth_dual_start)

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

        try:
            self.services.wifi.start_dual_deauth(mon1, mon2, red1, red2, burst=burst, callback=self.write_console)
        except Exception as exc:
            self._flow_worker_error("ERROR DE DEAUTH DUAL", exc, self._flow_deauth_dual_start)

    # =========================================================================
    # 8. RECONOCIMIENTO WIFI (WIFI AUDIT 2.0 - V1)
    # =========================================================================
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

    def _flow_audit_menu(self):
        """Menú del reconocimiento pasivo: single-band o dual-band."""
        self.wifi_state["audit_token"] = None
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="RECONOCIMIENTO WIFI", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=8)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        scroll.add_button(
            text="Single-band (1 interfaz)",
            command=self._flow_audit_single_select_iface,
            style='Red.TButton',
            width=28
        )
        scroll.add_button(
            text="Dual-band (2 interfaces)",
            command=self._flow_audit_dual_select_ifaces,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_audit_single_select_iface(self):
        self.clear_frame()
        self.add_back_button(self._flow_audit_menu)
        ttk.Label(self.main_frame, text="SINGLE-BAND: IFACE", style='Title.TLabel').pack(pady=2)

        interfaces = get_monitor_interfaces(unique_phys=True)
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces con modo monitor.", style='Dark.TLabel').pack(pady=10)
            self.show_console()
            return

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        ttk.Label(scroll.scrollable_frame, text="Seleccione interfaz:", style='Gray.TLabel').pack(pady=(0, 4))

        for iface in interfaces:
            scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_audit_select_band(i),
                style='Red.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_audit_select_band(self, iface):
        self.clear_frame()
        self.add_back_button(self._flow_audit_single_select_iface)
        ttk.Label(self.main_frame, text=f"BANDA: {iface}", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=8)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        ttk.Label(
            scroll.scrollable_frame,
            text="Auto no filtra la banda y puede tardar más.",
            style='Gray.TLabel',
            wraplength=290,
            justify='center'
        ).pack(anchor='center', padx=6, pady=(0, 4))

        for label, band in (("2.4 GHz", "2.4"), ("5 GHz", "5"), ("Auto", None)):
            scroll.add_button(
                text=label,
                command=lambda b=band: self._flow_audit_scan(iface, band=b),
                style='Red.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_audit_dual_select_ifaces(self):
        interfaces = get_monitor_interfaces(unique_phys=True)
        if len(interfaces) < 2:
            self.clear_frame()
            self.add_back_button(self._flow_audit_menu)
            ttk.Label(self.main_frame, text="DUAL-BAND", style='Title.TLabel').pack(pady=2)
            ttk.Label(
                self.main_frame,
                text="Se requieren 2 radios WiFi independientes\ncon modo monitor:\n"
                     "1 para 2.4 GHz y 1 para 5 GHz.",
                style='Mono.TLabel',
                justify='left',
                wraplength=290
            ).pack(padx=8, pady=10)
            self.show_console()
            return

        self.clear_frame()
        self.add_back_button(self._flow_audit_menu)
        ttk.Label(self.main_frame, text="DUAL-BAND: IFACES", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        ttk.Label(
            scroll.scrollable_frame,
            text="1ª = 2.4 GHz | 2ª = 5 GHz\nSeleccione en ese orden.",
            style='Mono.TLabel',
            justify='center'
        ).pack(pady=(0, 4))

        self.wifi_state["audit_dual"] = {"selected": [], "btns": []}
        for iface in interfaces:
            btn = scroll.add_button(
                text=iface,
                command=lambda i=iface: self._flow_audit_dual_add(i),
                style='Red.TButton',
                width=28
            )
            if btn:
                self.wifi_state["audit_dual"]["btns"].append(btn)

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_audit_dual_add(self, iface):
        state = self.wifi_state.get("audit_dual")
        if not state:
            return
        selected = state["selected"]
        if iface in selected or len(selected) >= 2:
            return
        selected.append(iface)

        for btn in state["btns"]:
            if btn.cget("text") == iface:
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])
                break

        if len(selected) == 2:
            self.write_console(f"[*] Interfaz 2.4 GHz: {selected[0]}")
            self.write_console(f"[*] Interfaz 5 GHz: {selected[1]}")
            self._flow_audit_scan(selected[0], band="2.4", iface_5g=selected[1])

    def _flow_audit_scan(self, iface, band=None, iface_5g=None):
        token = object()
        self.wifi_state["audit_token"] = token
        self.wifi_state["audit_result"] = {}
        self.clear_frame()
        self.add_back_button(self._flow_audit_menu)
        ttk.Label(self.main_frame, text="RECONOCIENDO...", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=4)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        ttk.Label(
            scroll.scrollable_frame,
            text="Escaneo pasivo: no se inyecta tráfico.\nLa interfaz se restaura al finalizar.",
            style='Gray.TLabel',
            justify='center',
            wraplength=290
        ).pack(anchor='center', padx=6, pady=(2, 4))
        scroll.add_button(
            text="FINALIZAR AUDITORÍA",
            command=self._flow_audit_finish,
            style='Danger.TButton',
            width=28
        )
        self.show_console(parent=scroll.scrollable_frame)

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
        self.add_back_button(self._flow_audit_menu)
        ttk.Label(self.main_frame, text=f"REDES DETECTADAS ({len(redes)})", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=80)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)

        ttk.Label(
            scroll.scrollable_frame,
            text=format_summary(summary),
            style='Gray.TLabel',
            justify='center',
            wraplength=290
        ).pack(anchor='center', padx=6, pady=(2, 4))

        scroll.add_button(
            text="FINALIZAR AUDITORÍA",
            command=self._flow_audit_finish,
            style='Danger.TButton',
            width=28
        )

        if not redes:
            ttk.Label(
                scroll.scrollable_frame,
                text="No se detectaron redes en el rango.",
                style='Dark.TLabel'
            ).pack(pady=10)
        else:
            for net in redes:
                score = int(net.get("honeypot_score") or 0)
                if score >= 50:
                    style = 'Red.TButton'
                elif score >= 25:
                    style = 'Danger.TButton'
                else:
                    style = 'Gray.TButton'
                scroll.add_button(
                    text=format_network_compact(net),
                    command=lambda n=net: self._flow_audit_detail(n),
                    style=style,
                    width=28
                )

        self.show_console(parent=scroll.scrollable_frame)
        if session_dir:
            self.write_console(f"[+] Reporte: {session_dir}")
        gc.collect()

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
        ttk.Label(
            self.main_frame,
            text=str(net.get("essid", "Detalle"))[:22],
            style='Title.TLabel'
        ).pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=8)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        ttk.Label(
            scroll.scrollable_frame,
            text=format_network_detail(net),
            style='Mono.TLabel',
            justify='left',
            wraplength=292
        ).pack(anchor='w', padx=5, pady=3)
        if session_dir:
            ttk.Label(
                scroll.scrollable_frame,
                text=f"Guardado: {os.path.basename(session_dir)}",
                style='Gray.TLabel',
                justify='left',
                wraplength=292
            ).pack(anchor='w', padx=5, pady=(0, 3))
        gc.collect()

    def _flow_audit_error(self, message):
        self.clear_frame()
        self.add_back_button(self._flow_audit_menu)
        ttk.Label(self.main_frame, text="ERROR DE RECONOCIMIENTO", style='Title.TLabel').pack(pady=2)
        ttk.Label(
            self.main_frame,
            text=str(message),
            style='Mono.TLabel',
            justify='left',
            wraplength=290
        ).pack(padx=8, pady=10)
        self.show_console()
        self.write_console(f"[!] {message}")
