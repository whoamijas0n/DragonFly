"""
dragonfly/services/poison_service.py - Servicio de envenenamiento de red USB (PoisonTap).
Emula un adaptador Ethernet sobre USB y realiza captura y redirección de tráfico de red.
"""

import os
from dragonfly.config import BASE_DIR_POISON
from dragonfly.core.session import SessionManager
import modules.poison_logic as poison_logic


class PoisonService:
    """
    Gestiona el ciclo de vida del ataque PoisonTap emulando Ethernet USB (RNDIS / CDC ECM).
    """

    def __init__(self):
        self._attack_instance = None
        self.is_running = False

    def start_attack(self, interface: str = None, on_output=None) -> bool:
        """
        Inicia el ataque de envenenamiento USB en la interfaz especificada o autodetectada.
        """
        session_dir = SessionManager.create_session(BASE_DIR_POISON)
        if on_output:
            on_output(f"[*] Iniciando ataque PoisonTap en {session_dir}...")

        try:
            self._attack_instance = poison_logic.PoisonAttack(
                interface=interface,
                callback_consola=on_output,
                session_dir=session_dir
            )
            if hasattr(self._attack_instance, 'iniciar'):
                self._attack_instance.iniciar()
            elif hasattr(self._attack_instance, 'start'):
                self._attack_instance.start()
            self.is_running = True
            return True
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al iniciar Poison: {e}")
            self.is_running = False
            return False

    def stop_attack(self, on_output=None) -> bool:
        """Detiene la interceptación y restaura las interfaces."""
        if self._attack_instance:
            try:
                if hasattr(self._attack_instance, 'detener'):
                    self._attack_instance.detener()
                elif hasattr(self._attack_instance, 'stop'):
                    self._attack_instance.stop()
                if on_output:
                    on_output("[+] Ataque Poison detenido.")
            except Exception as e:
                if on_output:
                    on_output(f"[!] Error al detener Poison: {e}")
            finally:
                self._attack_instance = None
                self.is_running = False
        return True

    def list_saved_sessions(self):
        """Retorna las sesiones de auditoría de Poison registradas."""
        return SessionManager.list_sessions(BASE_DIR_POISON)

    def list_session_logs(self, session_name: str):
        """Retorna los registros de una sesión de Poison."""
        session_path = os.path.join(BASE_DIR_POISON, session_name)
        return SessionManager.list_session_files(session_path)
