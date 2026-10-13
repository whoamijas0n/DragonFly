"""
dragonfly/services/cracking_service.py - Servicio de fuerza bruta offline para handshakes WPA/WPA2.
Utiliza aircrack-ng contra archivos de captura .cap y diccionarios de contraseñas.
"""

import os
import subprocess
from dragonfly.config import DEFAULT_WORDLIST
from dragonfly.core.executor import CommandExecutor


class CrackingService:
    """
    Gestiona ataques de diccionario offline aprovechando recursos de CPU en equipos Desktop.
    """

    def __init__(self, executor: CommandExecutor = None):
        self.executor = executor or CommandExecutor()
        self.is_running = False

    @staticmethod
    def get_default_wordlist() -> str:
        """Retorna la ruta al diccionario predeterminado si existe."""
        if os.path.exists(DEFAULT_WORDLIST):
            return DEFAULT_WORDLIST
        return ""

    def start_crack(self, cap_path: str, wordlist_path: str, on_output=None, on_finish=None):
        """
        Lanza aircrack-ng contra el archivo de captura con el diccionario proporcionado.
        """
        if not os.path.exists(wordlist_path):
            if on_output:
                on_output(f"\n[!] ERROR: El diccionario no existe en: {wordlist_path}")
            if on_finish:
                on_finish(-1)
            return None

        if not os.path.exists(cap_path):
            if on_output:
                on_output(f"\n[!] ERROR: El archivo CAP no existe en: {cap_path}")
            if on_finish:
                on_finish(-1)
            return None

        cmd = ["sudo", "aircrack-ng", "-w", wordlist_path, cap_path]

        if on_output:
            on_output("\n[*] Preparando ataque de fuerza bruta con aircrack-ng...")
            on_output(f"[*] Diccionario: {wordlist_path}")
            on_output(f"[*] Archivo CAP: {cap_path}")

        self.is_running = True

        def finish_wrapper(rc):
            self.is_running = False
            if on_finish:
                on_finish(rc)

        return self.executor.run_async(
            comando=cmd,
            on_output=on_output,
            on_finish=finish_wrapper,
            use_shell=False
        )

    def stop_crack(self, on_output=None):
        """Detiene forzosamente el proceso aircrack-ng en curso."""
        if on_output:
            on_output("\n[!] Abortando el ataque de fuerza bruta...")
        self.executor.stop_current()
        subprocess.run(["sudo", "pkill", "aircrack-ng"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.is_running = False
