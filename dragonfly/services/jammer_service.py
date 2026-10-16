"""
dragonfly/services/jammer_service.py - Servicio de control del Gadget NRF24 Jammer (Blue-Fly ESP32).
Gestiona la comunicación serie USB, autoconexión hot-plug, consultas de estado y emisión de radiofrecuencia.
"""

import os
import time
import threading


class JammerService:
    """
    Abstracción de servicio para el hardware externo NRF24 Jammer basado en ESP32.
    """

    def __init__(self):
        self._gadget = None
        self._lock = threading.Lock()

    def _destroy_gadget(self):
        """
        Libera por completo la instancia serie: cierra el descriptor del puerto
        (evitando descriptores huérfanos tras un hot-unplug) y descarta el objeto.
        """
        if self._gadget is not None:
            try:
                self._gadget.close()
            except Exception:
                pass
            self._gadget = None

    def get_gadget(self, force_reconnect: bool = False):
        """
        Retorna la instancia del gadget BLE/NRF24, reconectando si es necesario.
        En cada reconexión se destruye la instancia previa para garantizar la
        liberación total del descriptor serie antes de re-instanciarla.
        """
        try:
            from modules.gadget_handler import BLEGadget
        except ImportError:
            return None

        with self._lock:
            try:
                if self._gadget is None:
                    self._gadget = BLEGadget()
                elif force_reconnect or not self._gadget.is_available():
                    # Teardown total: cierra el puerto y descarta el objeto huérfano
                    self._destroy_gadget()
                    time.sleep(0.3)  # margen de re-asentamiento del bus USB / udev
                    self._gadget = BLEGadget()
            except Exception:
                self._gadget = None
            return self._gadget

    def get_usb_mode_hint(self) -> str:
        """
        Retorna una pista de diagnóstico si el puerto OTG está ocupado por un
        gadget USB (dr_mode=peripheral): en ese estado no alimenta ni enumera
        los puertos serie /dev/ttyUSB* / /dev/ttyACM* del ESP32.
        """
        try:
            udc_dir = "/sys/class/udc"
            if os.path.isdir(udc_dir) and os.listdir(udc_dir):
                return ("[!] El puerto OTG está en modo gadget (peripheral). "
                        "Cambie al perfil USB 'Host' y reconecte el ESP32.")
        except Exception:
            pass
        return ""

    def is_connected(self) -> bool:
        """Verifica si el ESP32 está conectado y sincronizado por puerto serie."""
        try:
            g = self.get_gadget()
            return g.is_available() if g else False
        except Exception:
            return False

    def get_port(self) -> str:
        """Retorna el puerto serie asignado al dispositivo."""
        try:
            g = self.get_gadget()
            if g and g.is_available():
                return getattr(g, 'port', getattr(g, '_port', None))
            return None
        except Exception:
            return None

    def start_sweep_jam(self, module: int = 0, duration: int = 0, on_output=None) -> bool:
        """
        Inicia el barrido continuo de interferencias en la banda de 2.4 GHz.
        """
        try:
            import serial
        except ImportError:
            if on_output:
                on_output("[!] Requiere 'pyserial'. Instale con: sudo apt install python3-serial")
            return False

        g = self.get_gadget()
        if not g or not g.is_available():
            if on_output:
                on_output("[!] Gadget NRF24 no conectado. Conecte el ESP32 por USB.")
                hint = self.get_usb_mode_hint()
                if hint:
                    on_output(hint)
            return False

        port_name = self.get_port() or "USB"
        if on_output:
            on_output(f"[*] Iniciando Sweep Jammer en {port_name}...")

        try:
            success = g.sweep_jam(module, duration)
            if success:
                if on_output:
                    on_output("[+] Jamming activado.")
                return True
            else:
                if on_output:
                    on_output("[!] Sin confirmación del Gadget.")
                return False
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al iniciar Jammer: {e}")
            return False

    def stop_sweep_jam(self, module: int = 0, on_output=None) -> bool:
        """Detiene el barrido de interferencias."""
        g = self.get_gadget()
        if not g or not g.is_available():
            if on_output:
                on_output("[!] Gadget desconectado.")
            return False

        if on_output:
            on_output("[*] Deteniendo transmisiones...")

        try:
            g.stop(module)
            if on_output:
                on_output("[+] Transmisión detenida.")
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al detener Jammer: {e}")
            return False

    def get_status(self, on_output=None) -> str:
        """Consulta el estado del firmware ESP32."""
        g = self.get_gadget()
        if not g or not g.is_available():
            msg = "[!] Gadget desconectado."
            if on_output:
                on_output(msg)
                hint = self.get_usb_mode_hint()
                if hint:
                    on_output(hint)
            return msg

        try:
            st = g.status()
            if on_output:
                on_output(f"[+] Estado ESP32: {st}")
            return st
        except Exception as e:
            msg = f"[!] Error consultando estado: {e}"
            if on_output:
                on_output(msg)
            return msg
