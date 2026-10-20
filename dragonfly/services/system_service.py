"""
dragonfly/services/system_service.py - Servicio de soporte del sistema operativo y hardware.
Gestiona redes Wi-Fi (nmcli), Bluetooth (bluetoothctl), métricas de hardware y perfiles USB OTG.
"""

import os
import re
import subprocess
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.hardware import get_network_interfaces, get_bluetooth_interfaces
from dragonfly.core.subprocess_utils import safe_run, safe_check_output
from dragonfly.core import usb_gadget


class SystemService:
    """
    Gestiona utilidades del sistema operativo, conexiones y configuración de periféricos.
    """

    def __init__(self, executor: CommandExecutor = None):
        self.executor = executor or CommandExecutor()

    # -------------------------------------------------------------
    # GESTIÓN DE REDES WI-FI (CLIENTE NMCLI)
    # -------------------------------------------------------------
    def scan_wifi_networks(self, iface: str):
        """
        Escanea puntos de acceso disponibles para conexión mediante nmcli.
        Retorna una lista de diccionarios [{'ssid': ..., 'security': ..., 'signal': ...}].
        """
        cmd = f"sudo nmcli -t -f SSID,SECURITY,SIGNAL dev wifi list ifname {iface} --rescan yes"
        stdout, stderr, rc = self.executor.run_sync(cmd)
        redes = []
        ssids_vistos = set()
        for linea in stdout.splitlines():
            partes = linea.split(":")
            if partes and partes[0].strip():
                ssid = partes[0].strip()
                if ssid not in ssids_vistos:
                    ssids_vistos.add(ssid)
                    sec = partes[1].strip() if len(partes) > 1 else "Abierta"
                    sig = partes[2].strip() if len(partes) > 2 else ""
                    redes.append({"ssid": ssid, "security": sec, "signal": sig})
        return redes

    def connect_wifi(self, iface: str, ssid: str, password: str = None, on_output=None, on_finish=None):
        """
        Conecta la interfaz Wi-Fi a un punto de acceso mediante NetworkManager.
        """
        if password:
            cmd = f"sudo nmcli dev wifi connect '{ssid}' password '{password}' ifname '{iface}'"
        else:
            cmd = f"sudo nmcli dev wifi connect '{ssid}' ifname '{iface}'"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    # -------------------------------------------------------------
    # GESTIÓN BLUETOOTH (BLUETOOTHCTL)
    # -------------------------------------------------------------
    def get_bluetooth_adapters(self):
        """Retorna los adaptadores Bluetooth locales."""
        return get_bluetooth_interfaces()

    def scan_bluetooth(self, duration: int = 10):
        """
        Escanea dispositivos Bluetooth cercanos durante el tiempo indicado.
        Retorna lista de tuplas (mac, nombre).
        """
        try:
            safe_run(f"sudo bluetoothctl --timeout {duration} scan on", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            salida = safe_check_output("sudo bluetoothctl devices", shell=True, text=True)
            dispositivos = []
            for linea in salida.splitlines():
                partes = linea.split(" ")
                if len(partes) >= 3 and partes[0] == "Device":
                    mac = partes[1]
                    nombre = " ".join(partes[2:])
                    dispositivos.append((mac, nombre))
            return dispositivos
        except Exception:
            return []

    def pair_and_connect_bluetooth(self, mac: str, on_output=None) -> str:
        """
        Empareja y establece conexión con un dispositivo Bluetooth por su dirección MAC.
        """
        try:
            if on_output:
                on_output(f"[*] Emparejando con {mac}...")
            pair = safe_run(f"sudo bluetoothctl -- pair {mac}", shell=True, capture_output=True, text=True, timeout=30)
            if "Pairing successful" in pair.stdout or "Paired: yes" in pair.stdout:
                if on_output:
                    on_output("[+] Emparejamiento exitoso. Conectando...")
                conn = safe_run(f"sudo bluetoothctl -- connect {mac}", shell=True, capture_output=True, text=True, timeout=30)
                if "Connection successful" in conn.stdout or "Connected: yes" in conn.stdout:
                    return "ÉXITO: Dispositivo conectado."
                return f"ERROR: Fallo de conexión ({conn.stderr.strip()})"
            return f"ERROR: Fallo en emparejamiento ({pair.stderr.strip()})"
        except Exception as e:
            return f"EXCEPCIÓN: {e}"

    # -------------------------------------------------------------
    # MÉTRICAS Y CONTROL DE ENERGÍA
    # -------------------------------------------------------------
    def get_system_metrics(self, metric_type: str, on_output=None, on_finish=None):
        """
        Ejecuta comandos de telemetría del sistema operativo:
        'storage', 'memory', 'cpu', 'connections'.
        """
        comandos = {
            "storage": "df -h",
            "memory": "free -h",
            "cpu": "ps aux --sort=-%cpu | head -n 15",
            "connections": "ss -tulnp"
        }
        cmd = comandos.get(metric_type, "uptime")
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def power_off(self):
        """Apaga el sistema de forma segura."""
        safe_run("sudo poweroff", shell=True)

    def reboot(self):
        """Reinicia el sistema de forma segura."""
        safe_run("sudo reboot", shell=True)

    # -------------------------------------------------------------
    # PERFILES USB OTG (RASPBERRY PI ZERO) - GADGET COMPUESTO
    # -------------------------------------------------------------
    def get_usb_gadget_status(self) -> dict:
        """
        Retorna el estado actual del gadget USB (perfil activo, modo OTG,
        interfaces, servicio de arranque) para mostrarlo en la interfaz.
        """
        return usb_gadget.status()

    def configure_usb_gadget_profile(self, modo: str, on_output=None) -> dict:
        """
        Aplica un perfil USB OTG.

        - Perfiles gadget (hid, ecm, rndis, hid_ecm, hid_rndis): se construyen y
          conmutan EN CALIENTE si el puerto ya está en modo periférico (sin reinicio).
        - Perfil host: actualiza config.txt, deshabilita el gadget y exige reinicio.
        - Si el puerto estaba en host y se pide un perfil gadget, se deja configurado
          para el siguiente arranque y se avisa que hace falta reiniciar UNA vez.

        Retorna {'ok': bool, 'mode': 'live'|'reboot'|'error', 'message': str}.
        """
        log = on_output if callable(on_output) else (lambda _m: None)
        key = usb_gadget.normalize_profile(modo)

        if key == "host":
            usb_gadget.teardown(log)
            usb_gadget.set_dr_mode("host", log)
            usb_gadget.disable_service(log)
            return {
                "ok": True,
                "mode": "reboot",
                "message": "[!] Modo Host configurado. El sistema se apagará para que reconecte los periféricos USB.",
            }

        if key not in usb_gadget.PROFILES:
            log(f"[!] Perfil no soportado: {modo}")
            return {"ok": False, "mode": "error", "message": f"Perfil no soportado: {modo}"}

        # Activos de arranque (script + systemd) y perfil persistente, siempre al día.
        usb_gadget.install_boot_assets(log)
        usb_gadget.persist_profile(key, log)

        if not usb_gadget.is_peripheral_mode():
            # El OTG está en host: se programa el perfil y se pide UN reinicio.
            usb_gadget.set_dr_mode("peripheral", log)
            usb_gadget.enable_service(log)
            etiqueta = usb_gadget.PROFILE_LABELS.get(key, key)
            mensaje = (
                f"[!] El puerto OTG estaba en modo Host. Perfil '{etiqueta}' programado: "
                "REINICIA la Raspberry Pi para activarlo. Después, los cambios de perfil serán en caliente."
            )
            log(mensaje)
            return {"ok": True, "mode": "reboot", "message": mensaje}

        # Modo periférico: conmutación en caliente sin reinicio.
        if usb_gadget.current_profile() == key:
            log(f"[*] El perfil '{key}' ya está activo.")
            return {"ok": True, "mode": "live", "message": f"El perfil '{key}' ya estaba activo."}

        log(f"[*] Conmutando gadget USB en caliente al perfil '{key}'...")
        ok = usb_gadget.apply(key, log)
        if ok:
            etiqueta = usb_gadget.PROFILE_LABELS.get(key, key)
            mensaje = f"[+] Perfil '{etiqueta}' activo en caliente (sin reinicio)."
            log(mensaje)
            return {"ok": True, "mode": "live", "message": mensaje}

        mensaje = f"[!] No se pudo aplicar el perfil '{key}'. Revise la consola."
        log(mensaje)
        return {"ok": False, "mode": "error", "message": mensaje}
