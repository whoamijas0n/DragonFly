"""
dragonfly/services/poison_service.py - Servicio de envenenamiento de red USB (PoisonTap).
Emula un adaptador Ethernet sobre USB y realiza captura y redirección de tráfico de red.
El ataque corre SIEMPRE en un hilo secundario: su bucle de lectura es bloqueante
y jamás debe ejecutarse en el hilo principal de Tkinter (congelaría la interfaz).
"""

import os
import subprocess
import threading
from dragonfly.config import BASE_DIR_POISON
from dragonfly.core.session import SessionManager
import modules.poison_logic as poison_logic


class PoisonService:
    """
    Gestiona el ciclo de vida del ataque PoisonTap emulando Ethernet USB (RNDIS / CDC ECM).
    """

    def __init__(self):
        self._attack_instance = None
        self.worker_thread = None
        self.is_running = False

    def start_attack(self, interface: str = None, on_output=None, on_finish=None) -> bool:
        """
        Inicia el ataque de envenenamiento USB en un hilo secundario y retorna
        inmediatamente sin bloquear el hilo principal de la interfaz gráfica.
        """
        if self.is_running:
            if on_output:
                on_output("[!] Ya hay un ataque Poison en curso.")
            return False

        session_dir = SessionManager.create_session(BASE_DIR_POISON)
        if on_output:
            on_output(f"[*] Iniciando ataque PoisonTap en {session_dir}...")

        try:
            self._attack_instance = poison_logic.PoisonAttack(
                interface=interface,
                callback_consola=on_output,
                session_dir=session_dir
            )
        except Exception as e:
            if on_output:
                on_output(f"[!] Error al preparar Poison: {e}")
            self._attack_instance = None
            self.is_running = False
            return False

        attack = self._attack_instance

        def run():
            try:
                if hasattr(attack, 'iniciar'):
                    attack.iniciar()
                elif hasattr(attack, 'start'):
                    attack.start()
            except Exception as e:
                if on_output:
                    on_output(f"[!] Error en el ataque Poison: {e}")
            finally:
                self.is_running = False
                if on_finish:
                    on_finish()

        self.is_running = True
        self.worker_thread = threading.Thread(target=run, daemon=True)
        self.worker_thread.start()
        return True

    def stop_attack(self, on_output=None) -> bool:
        """Detiene la interceptación, espera al hilo y restaura las interfaces."""
        if on_output:
            on_output("\n[!] Deteniendo ataque Poison...")

        attack = self._attack_instance
        if attack:
            try:
                if hasattr(attack, 'detener'):
                    attack.detener()
                elif hasattr(attack, 'stop'):
                    attack.stop()
            except Exception as e:
                if on_output:
                    on_output(f"[!] Error al detener Poison: {e}")

        # El hilo saldrá del bucle bloqueante y ejecutará su _cleanup() (finally)
        thread = self.worker_thread
        if thread and thread.is_alive():
            thread.join(timeout=3)

        # Matado de seguridad para procesos huérfanos que sigan escuchando
        subprocess.run(["sudo", "pkill", "-f", "responder"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", "dnsmasq"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._attack_instance = None
        self.worker_thread = None
        self.is_running = False
        if on_output:
            on_output("[+] Ataque Poison detenido.")
        return True

    def list_saved_sessions(self):
        """Retorna las sesiones de auditoría de Poison registradas."""
        return SessionManager.list_sessions(BASE_DIR_POISON)

    def list_session_logs(self, session_name: str):
        """Retorna los registros de una sesión de Poison."""
        session_path = os.path.join(BASE_DIR_POISON, session_name)
        return SessionManager.list_session_files(session_path)
