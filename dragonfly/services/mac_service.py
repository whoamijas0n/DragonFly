"""
dragonfly/services/mac_service.py - Servicio de manipulación y spoofing de direcciones MAC.
Soporta macchanger aleatorio, restablecimiento de fábrica, mismo fabricante y MAC personalizada.
"""

import re
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.hardware import get_network_interfaces


class MacService:
    """
    Gestiona la verificación y cambio de dirección física (MAC) en tarjetas de red.
    """

    PATRON_MAC = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"

    def __init__(self, executor: CommandExecutor = None):
        self.executor = executor or CommandExecutor()

    def get_interfaces(self):
        """Retorna las interfaces disponibles para manipular."""
        return get_network_interfaces()

    @classmethod
    def validate_mac(cls, mac: str) -> bool:
        """Valida que una cadena cumpla el formato de dirección MAC de 48 bits."""
        if not mac:
            return False
        return bool(re.match(cls.PATRON_MAC, mac.strip()))

    def show_status(self, iface: str, on_output=None, on_finish=None):
        """Muestra el estado actual y la MAC permanente de la interfaz."""
        cmd = f"sudo macchanger -s {iface}"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def set_random(self, iface: str, on_output=None, on_finish=None):
        """Asigna una dirección MAC totalmente aleatoria."""
        cmd = f"sudo ifconfig {iface} down && sudo macchanger -r {iface} && sudo ifconfig {iface} up"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def reset_original(self, iface: str, on_output=None, on_finish=None):
        """Restablece la dirección MAC de fábrica grabada en el hardware."""
        cmd = f"sudo ifconfig {iface} down && sudo macchanger -p {iface} && sudo ifconfig {iface} up"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def set_same_vendor(self, iface: str, on_output=None, on_finish=None):
        """Genera una MAC aleatoria conservando el prefijo OUI del fabricante original."""
        cmd = f"sudo ifconfig {iface} down && sudo macchanger -a {iface} && sudo ifconfig {iface} up"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def set_custom(self, iface: str, custom_mac: str, on_output=None, on_finish=None):
        """
        Asigna una dirección MAC específica tras validar su sintaxis.
        """
        mac_clean = custom_mac.strip() if custom_mac else ""
        if not self.validate_mac(mac_clean):
            if on_output:
                on_output(f"[!] Formato de MAC inválido: '{custom_mac}'. Use formato XX:XX:XX:XX:XX:XX.")
            if on_finish:
                on_finish(-1)
            return None

        cmd = f"sudo ifconfig {iface} down && sudo macchanger -m {mac_clean} {iface} && sudo ifconfig {iface} up"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)
