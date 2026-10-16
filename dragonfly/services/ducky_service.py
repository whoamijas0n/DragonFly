"""
dragonfly/services/ducky_service.py - Servicio de inyección HID Rubber Ducky.
Lee scripts DuckyScript desde la carpeta payloads/ y los transmite hacia /dev/hidg0.
Ejecuta el payload en un subproceso aislado (matable) y transmite su stdout en vivo.
"""

import os
import glob
import subprocess
import threading
from dragonfly.config import DIR_PAYLOADS


class DuckyService:
    """
    Gestiona la ejecución de payloads Duckyscript a través del gadget USB HID.
    """

    def __init__(self):
        self.current_process = None
        self.is_running = False
        self._stop_event = threading.Event()

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

    def execute_payload(self, payload_name: str, layout: str = "ES", on_output=None) -> bool:
        """
        Ejecuta un payload DuckyScript en /dev/hidg0 usando el layout indicado ('ES' o 'US').

        La inyección corre en un subproceso independiente (sudo python3 -c ...) para:
          1. Poder leer su stdout en tiempo real y volcarlo a la consola visual.
          2. Poder abortarla en caliente con terminate()/kill() (stop_payload).
        El layout se normaliza a minúsculas ('es'/'us') porque ducky_logic lo compara así.
        """
        ruta = self.get_payload_path(payload_name)
        if not os.path.exists(ruta):
            if on_output:
                on_output(f"[!] El archivo de payload no existe: {ruta}")
            return False

        if not self.is_hid_available():
            if on_output:
                on_output("[!] /dev/hidg0 no encontrado. Verifique que el perfil USB Ducky esté activo.")
            return False

        if self.is_running:
            if on_output:
                on_output("[!] Ya hay un payload en ejecución.")
            return False

        layout_lower = (layout or "us").lower()
        if on_output:
            on_output(f"[*] Ejecutando payload: {payload_name} (Layout: {layout_lower.upper()})")

        script_cmd = (
            f"from modules import ducky_logic; "
            f"ducky_logic.ejecutar_script_ducky('{ruta}', layout='{layout_lower}')"
        )
        cmd = ["sudo", "python3", "-c", script_cmd]

        self._stop_event.clear()
        self.is_running = True
        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self.current_process = proc

            # Transmitir la salida del subproceso a la consola visual línea a línea
            for line in proc.stdout:
                if on_output:
                    on_output(line.rstrip())

            proc.wait()
            if self._stop_event.is_set():
                if on_output:
                    on_output("[!] Payload detenido por el usuario.")
                return False
            if on_output:
                on_output("[+] Inyección HID completada exitosamente.")
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al ejecutar Rubber Ducky: {e}")
            return False
        finally:
            if self.current_process is proc:
                self.current_process = None
            self.is_running = False

    def stop_payload(self, on_output=None) -> bool:
        """
        Aborta de forma forzosa la inyección del payload en curso.
        Termina el subproceso y limpia procesos huérfanos de ducky_logic.
        """
        if on_output:
            on_output("\n[!] Deteniendo inyección Ducky...")

        self._stop_event.set()

        proc = self.current_process
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.current_process = None

        # Limpieza global por si algún proceso quedó zombie
        subprocess.run(
            ["sudo", "pkill", "-f", "ducky_logic"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if on_output:
            on_output("[+] Payload detenido.")
        return True
