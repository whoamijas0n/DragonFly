"""
dragonfly/services/jammer_service.py - Servicio de control del Gadget NRF24 Jammer (Blue-Fly ESP32).
Gestiona la comunicación serie USB, autoconexión hot-plug y emisión de interferencias de 2.4 GHz.
"""


class JammerService:
    """
    Abstracción de servicio para el hardware externo NRF24 Jammer basado en ESP32.
    """

    def __init__(self):
        self._gadget = None

    def get_gadget(self, force_reconnect: bool = False):
        """
        Retorna la instancia del gadget BLE/NRF24, reconectando si es necesario.
        """
        try:
            from modules.gadget_handler import BLEGadget
        except ImportError:
            return None

        if self._gadget is None or force_reconnect:
            self._gadget = BLEGadget()
        elif not self._gadget.is_connected():
            self._gadget.connect()
        return self._gadget

    def is_connected(self) -> bool:
        """Verifica si el ESP32 está conectado y sincronizado por puerto serie."""
        g = self.get_gadget()
        return g.is_connected() if g else False

    def get_port(self) -> str:
        """Retorna el puerto serie asignado al dispositivo."""
        g = self.get_gadget()
        return g.port if g else None

    def start_sweep_jam(self, on_output=None) -> bool:
        """
        Inicia el barrido continuo de interferencias en la banda de 2.4 GHz.
        """
        try:
            import serial
        except ImportError:
            if on_output:
                on_output("[!] Requiere 'pyserial'. Instale con: sudo apt install python3-serial o pip install pyserial")
            return False

        g = self.get_gadget()
        if not g or not g.is_connected():
            if on_output:
                on_output("[!] Gadget NRF24 no conectado. Conecte el ESP32 por USB.")
            return False

        if on_output:
            on_output(f"[*] Iniciando Sweep Jammer en {g.port}...")

        try:
            if hasattr(g, 'start_jam'):
                g.start_jam()
            elif hasattr(g, 'send_command'):
                g.send_command("JAM_START\n")
            if on_output:
                on_output("[+] Barrido de interferencias activo.")
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al iniciar Jammer: {e}")
            return False

    def stop_sweep_jam(self, on_output=None) -> bool:
        """Detiene el barrido de interferencias."""
        g = self.get_gadget()
        if not g or not g.is_connected():
            return False

        try:
            if hasattr(g, 'stop_jam'):
                g.stop_jam()
            elif hasattr(g, 'send_command'):
                g.send_command("JAM_STOP\n")
            if on_output:
                on_output("[+] Barrido de interferencias detenido.")
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al detener Jammer: {e}")
            return False
