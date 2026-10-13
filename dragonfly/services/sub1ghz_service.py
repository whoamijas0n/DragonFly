"""
dragonfly/services/sub1ghz_service.py - Servicio de manipulación de radiofrecuencia Sub-1GHz (CC1101 + ESP32).
Gestiona la comunicación con el firmware Sub-1GHz para recepción y transmisión de señales RF.
"""


class Sub1GHzService:
    """
    Abstracción de servicio para el módulo de RF Sub-1GHz.
    """

    def __init__(self):
        self._controller = None

    def get_controller(self, port: str = None, on_output=None):
        """
        Retorna la instancia del controlador Sub-1GHz conectada y escuchando.
        """
        try:
            from modules.sub1ghz_logic import Sub1GHzController
        except ImportError:
            if on_output:
                on_output("[!] Requiere 'pyserial'. Instale con: sudo apt install python3-serial o pip install pyserial")
            return None

        if self._controller is None or not self._controller.running:
            self._controller = Sub1GHzController(port=port, callback=on_output)
        return self._controller

    def is_connected(self) -> bool:
        """Verifica si el módulo RF está conectado y activo."""
        return self._controller is not None and self._controller.running

    def send_rf_command(self, cmd: str, on_output=None) -> bool:
        """
        Envía un comando de control de radiofrecuencia al microcontrolador.
        """
        ctrl = self.get_controller(on_output=on_output)
        if not ctrl or not ctrl.running:
            if on_output:
                on_output("[!] Módulo Sub-1GHz no conectado.")
            return False

        try:
            if hasattr(ctrl, 'send_command'):
                ctrl.send_command(cmd)
            elif ctrl.ser and ctrl.ser.is_open:
                ctrl.ser.write((cmd + "\n").encode())
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al transmitir comando Sub-1GHz: {e}")
            return False
