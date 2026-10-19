"""
dragonfly/ui/raspi/views/utils_view.py - Vista de utilidades OS y cambio de perfiles USB para Raspberry Pi.
Controla nmcli con TecladoCompleto, Bluetooth, telemetría y reconfiguración del puerto OTG en config.txt.
"""

import threading
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame, TecladoCompleto
from dragonfly.core.hardware import get_wifi_interfaces
from dragonfly.core import usb_gadget


class UtilsView(BaseView):
    """
    Vista de herramientas de administración del sistema y cambio de perfiles de hardware USB.
    """

    def __init__(self, app):
        super().__init__(app)
        self.var_iface_wifi = tk.StringVar(value="")
        self._usb_ultimo_mensaje = ""

    def render(self):
        """Menú general de utilidades OS."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="UTILIDADES DEL SISTEMA", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        # Botones de categorías
        scroll.add_button("Gestor Wi-Fi (Conectar)", self._flow_wifi_select, style='Red.TButton', width=28)
        scroll.add_button("Gestor Bluetooth", self._flow_bt_scan, style='Red.TButton', width=28)
        scroll.add_button("Cambio de Perfil USB OTG", self._flow_usb_profiles, style='Danger.TButton', width=28)

        # Telemetría
        scroll.add_button("Uso de Almacenamiento", lambda: self.services.system.get_system_metrics("storage", on_output=self.write_console), style='Gray.TButton', width=28)
        scroll.add_button("Uso de Memoria RAM", lambda: self.services.system.get_system_metrics("memory", on_output=self.write_console), style='Gray.TButton', width=28)
        scroll.add_button("Top Procesos CPU", lambda: self.services.system.get_system_metrics("cpu", on_output=self.write_console), style='Gray.TButton', width=28)
        scroll.add_button("Conexiones de Red Activas", lambda: self.services.system.get_system_metrics("connections", on_output=self.write_console), style='Gray.TButton', width=28)

        # Control de Energía (doble toque: evita reinicios/apagados por toques accidentales)
        self._boton_peligro(scroll, "REINICIAR SISTEMA", self.services.system.reboot, "CONFIRMAR REINICIO")
        self._boton_peligro(scroll, "APAGAR SISTEMA", self.services.system.power_off, "CONFIRMAR APAGADO")
        self._boton_peligro(scroll, "Cerrar Interfaz", self.app.destroy, "CONFIRMAR CIERRE", style='Gray.TButton')

        self.show_console(parent=scroll.scrollable_frame)

    # -------------------------------------------------------------
    # ACCIONES DESTRUCTIVAS: DOBLE TOQUE DE CONFIRMACIÓN (TÁCTIL)
    # -------------------------------------------------------------
    def _boton_peligro(self, scroll, texto, accion, texto_confirmar, style='Danger.TButton', segundos=8):
        """
        Botón de doble toque: el primero arma la acción y muestra 'texto_confirmar';
        el segundo la ejecuta. Si no se confirma en 'segundos', vuelve a la normalidad.
        Evita reiniciar/apagar la Pi por un roce accidental en la pantalla táctil.
        """
        boton = scroll.add_button(texto, None, style=style, width=28)
        if boton is None:
            return None

        estado = {"armado": False, "timer": None}

        def _restaurar():
            estado["armado"] = False
            if boton.winfo_exists():
                boton.configure(text=texto)

        def _al_pulsar():
            if estado["armado"]:
                if estado["timer"] is not None:
                    try:
                        boton.after_cancel(estado["timer"])
                    except Exception:
                        pass
                    estado["timer"] = None
                estado["armado"] = False
                boton.configure(text=texto)
                accion()
                return
            estado["armado"] = True
            boton.configure(text=texto_confirmar)
            estado["timer"] = boton.after(int(segundos * 1000), _restaurar)

        boton.configure(command=_al_pulsar)
        return boton

    # -------------------------------------------------------------
    # SUBFLUJO: WI-FI CLIENTE CON TECLADO VIRTUAL
    # -------------------------------------------------------------
    def _flow_wifi_select(self):
        interfaces = get_wifi_interfaces()
        if not interfaces:
            self.write_console("[!] No hay interfaces Wi-Fi.")
            return

        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="INTERFAZ WI-FI", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if not self.var_iface_wifi.get() or self.var_iface_wifi.get() not in interfaces:
            self.var_iface_wifi.set(interfaces[0])

        sel_f = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        sel_f.pack(pady=3)
        ttk.Label(sel_f, text="Iface: ", style='Dark.TLabel').pack(side='left')
        ttk.OptionMenu(sel_f, self.var_iface_wifi, self.var_iface_wifi.get(), *interfaces, style='Dark.TMenubutton').pack(side='left')

        scroll.add_button("Escanear Redes Disponibles", self._flow_wifi_scan, style='Red.TButton', width=28)
        self.show_console(parent=scroll.scrollable_frame)

    def _flow_wifi_scan(self):
        iface = self.var_iface_wifi.get()
        self.clear_frame()
        self.add_back_button(self._flow_wifi_select)
        ttk.Label(self.main_frame, text="ESCANEANDO WI-FI...", style='Title.TLabel').pack(pady=2)
        self.show_console()

        def worker():
            redes = self.services.system.scan_wifi_networks(iface)
            self.run_on_ui(lambda: self._flow_wifi_show_networks(redes))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_wifi_show_networks(self, redes):
        iface = self.var_iface_wifi.get()
        self.clear_frame()
        self.add_back_button(self._flow_wifi_select)
        ttk.Label(self.main_frame, text="REDES DETECTADAS", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        for red in redes:
            texto = f"📶 {red['ssid'][:16]}"
            scroll.add_button(
                text=texto,
                command=lambda s=red['ssid'], sec=red['security']: self._flow_wifi_connect_prompt(iface, s, sec),
                style='Red.TButton',
                width=28
            )

        self.show_console(parent=scroll.scrollable_frame)

    def _flow_wifi_connect_prompt(self, iface: str, ssid: str, security: str):
        password = None
        if "WPA" in security or "WEP" in security:
            pass_var = tk.StringVar()
            teclado = TecladoCompleto(self.app, pass_var, titulo=f"Pass: {ssid[:10]}")
            self.app.wait_window(teclado)
            entered = pass_var.get()
            if entered == "CANCELADO" or not entered:
                return
            password = entered

        self.write_console(f"[*] Conectando a '{ssid}'...")
        self.services.system.connect_wifi(iface, ssid, password, on_output=self.write_console)

    # -------------------------------------------------------------
    # SUBFLUJO: BLUETOOTH
    # -------------------------------------------------------------
    def _flow_bt_scan(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="ESCANEANDO BT (10s)", style='Title.TLabel').pack(pady=2)
        self.show_console()

        def worker():
            devs = self.services.system.scan_bluetooth(duration=10)
            self.run_on_ui(lambda: self._flow_bt_show(devs))

        threading.Thread(target=worker, daemon=True).start()

    def _flow_bt_show(self, devs):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="DISPOSITIVOS BLUETOOTH", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        if not devs:
            ttk.Label(scroll.scrollable_frame, text="No hay dispositivos cercanos.", style='Gray.TLabel').pack()
        else:
            for mac, nombre in devs:
                scroll.add_button(
                    text=f"🔵 {nombre[:14]}",
                    command=lambda m=mac: self.services.system.pair_and_connect_bluetooth(m, on_output=self.write_console),
                    style='Red.TButton',
                    width=28
                )

        self.show_console(parent=scroll.scrollable_frame)

    # -------------------------------------------------------------
    # SUBFLUJO: PERFILES USB OTG (RASPBERRY PI ZERO)
    # -------------------------------------------------------------
    def _flow_usb_profiles(self):
        self.clear_frame()
        self.add_back_button(self.render)
        ttk.Label(self.main_frame, text="PERFILES USB OTG", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        estado = self.services.system.get_usb_gadget_status()
        activo = estado.get("profile") or "ninguno"
        modo = "periférico" if estado.get("peripheral") else "host"
        ttk.Label(
            scroll.scrollable_frame,
            text=f"Activo: {activo}  |  OTG: {modo}",
            style='Gray.TLabel'
        ).pack(pady=1)
        ttk.Label(
            scroll.scrollable_frame,
            text="Perfiles gadget: en caliente (sin reiniciar).\n'Modo Host' apaga la Pi (encender después).",
            style='Gray.TLabel'
        ).pack(pady=1)

        if self._usb_ultimo_mensaje:
            ttk.Label(
                scroll.scrollable_frame,
                text=self._usb_ultimo_mensaje,
                style='Gray.TLabel',
                wraplength=290,
                justify='left'
            ).pack(pady=1, padx=4)
            self._usb_ultimo_mensaje = ""

        for key in usb_gadget.PROFILE_ORDER:
            etiqueta = usb_gadget.PROFILE_LABELS.get(key, key)
            marcador = "● " if key == activo else ""
            scroll.add_button(
                text=f"{marcador}{etiqueta}",
                command=lambda k=key: self._apply_usb_profile(k),
                style='Red.TButton',
                width=28
            )

        self._boton_peligro(
            scroll,
            "Modo Host (Antena Wi-Fi/Hub)",
            lambda: self._apply_usb_profile("host"),
            "CONFIRMAR MODO HOST"
        )

        self.show_console(parent=scroll.scrollable_frame)

    def _apply_usb_profile(self, modo: str):
        self.write_console(f"[*] Aplicando perfil USB: {modo}...")

        def worker():
            resultado = self.services.system.configure_usb_gadget_profile(modo, on_output=self.write_console)
            self.run_on_ui(lambda: self._after_usb_profile(modo, resultado))

        threading.Thread(target=worker, daemon=True).start()

    def _after_usb_profile(self, modo: str, resultado: dict):
        resultado = resultado or {}
        mensajes = []

        if resultado.get("mode") == "reboot":
            if modo == "host":
                mensajes.append("[!] Modo Host listo. Apagando en 5 segundos para reconectar los periféricos USB...")
            else:
                mensajes.append("[!] Primer uso del modo gadget: apagando en 5 segundos. Enciende la Pi y el perfil quedará activo (los siguientes cambios serán en caliente).")
        elif resultado.get("ok"):
            mensajes.append(resultado.get("message", "[+] Perfil aplicado en caliente."))
            if modo != "host":
                estado = self.services.system.get_usb_gadget_status()
                if estado.get("hidg"):
                    mensajes.append("[+] /dev/hidg0 disponible (Rubber Ducky listo).")
                if estado.get("net_ifaces"):
                    mensajes.append(f"[+] Interfaz de red del gadget: {', '.join(estado['net_ifaces'])}.")
        else:
            mensajes.append(resultado.get("message", "[!] No se pudo aplicar el perfil."))

        # El último mensaje se muestra también arriba (la consola queda fuera de pantalla).
        self._usb_ultimo_mensaje = mensajes[0] if mensajes else ""

        # Re-render para refrescar el perfil activo; después se escribe la consola.
        self._flow_usb_profiles()
        for mensaje in mensajes:
            self.write_console(mensaje)

        # Host <-> periférico exige reinicio: se apaga para que el cambio surta efecto.
        if resultado.get("mode") == "reboot":
            self.app.after(5000, self.services.system.power_off)
