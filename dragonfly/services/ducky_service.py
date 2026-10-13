"""
dragonfly/services/ducky_service.py - Servicio de inyección HID Rubber Ducky.
Lee scripts DuckyScript desde la carpeta payloads/ y los transmite hacia /dev/hidg0.
"""

import os
import glob
from dragonfly.config import DIR_PAYLOADS
from modules import ducky_logic


class DuckyService:
    """
    Gestiona la ejecución de payloads Duckyscript a través del gadget USB HID.
    """

    @staticmethod
    def is_hid_available() -> bool:
        """Verifica si el dispositivo USB Gadget HID existe en el sistema."""
        return os.path.exists("/dev/hidg0")

    @staticmethod
    def list_payloads():
        """
        Lista todos los scripts de ataque .txt contenidos en la carpeta payloads/.
        """
        if not os.path.exists(DIR_PAYLOADS):
            return []
        try:
            archivos = glob.glob(os.path.join(DIR_PAYLOADS, "*.txt"))
            return sorted([os.path.basename(f) for f in archivos])
        except Exception:
            return []

    @staticmethod
    def get_payload_path(payload_name: str) -> str:
        """Retorna la ruta absoluta a un archivo de payload."""
        return os.path.join(DIR_PAYLOADS, payload_name)

    @classmethod
    def execute_payload(cls, payload_name: str, layout: str = "ES", on_output=None) -> bool:
        """
        Ejecuta un payload DuckyScript en /dev/hidg0 usando el layout indicado ('ES' o 'US').
        """
        ruta = cls.get_payload_path(payload_name)
        if not os.path.exists(ruta):
            if on_output:
                on_output(f"[!] El archivo de payload no existe: {ruta}")
            return False

        if not cls.is_hid_available():
            if on_output:
                on_output("[!] /dev/hidg0 no encontrado. Verifique que el perfil USB Ducky esté activo.")
            return False

        if on_output:
            on_output(f"[*] Ejecutando payload: {payload_name} (Layout: {layout})")
            on_output("[*] Posicione el cursor en el objetivo (2s)...")

        try:
            if hasattr(ducky_logic, 'ejecutar_script_ducky'):
                ducky_logic.ejecutar_script_ducky(ruta, layout=layout, callback=on_output)
            elif hasattr(ducky_logic, 'ejecutar_payload'):
                ducky_logic.ejecutar_payload(ruta, layout=layout)
            if on_output:
                on_output("[+] Inyección HID completada exitosamente.")
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al ejecutar Rubber Ducky: {e}")
            return False
