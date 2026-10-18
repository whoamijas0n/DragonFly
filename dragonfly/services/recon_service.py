"""
dragonfly/services/recon_service.py - Servicio de reconocimiento y escaneo con Nmap.
Valida objetivos CIDR/IP, orquesta los 13 perfiles de auditoría y almacena reportes.
"""

import os
import re
from dragonfly.config import BASE_DIR_NMAP, NMAP_PROFILES
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.session import SessionManager
from dragonfly.core.hardware import get_local_ip
from dragonfly.core.subprocess_utils import safe_run


class ReconService:
    """
    Gestiona el ciclo de vida de los escaneos de red con Nmap.
    """

    PATRON_IP = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    PATRON_CIDR = r'^/(8|16|24|32)$'

    def __init__(self, executor: CommandExecutor = None):
        self.executor = executor or CommandExecutor()
        self.current_session_dir = None

    @classmethod
    def validate_target(cls, ip: str, use_range: bool = False, cidr: str = "/24") -> bool:
        """
        Valida sintácticamente la dirección IPv4 y su máscara CIDR.
        """
        ip = ip.strip() if ip else ""
        if use_range:
            cidr = cidr.strip() if cidr else ""
            return bool(re.match(cls.PATRON_IP, ip) and re.match(cls.PATRON_CIDR, cidr))
        return bool(re.match(cls.PATRON_IP, ip))

    @classmethod
    def format_target(cls, ip: str, use_range: bool = False, cidr: str = "/24") -> str:
        """
        Retorna la representación final del objetivo para Nmap o None si es inválido.
        """
        if not cls.validate_target(ip, use_range, cidr):
            return None
        ip_clean = ip.strip()
        if use_range:
            return f"{ip_clean}{cidr.strip()}"
        return ip_clean

    def get_auto_ip(self) -> str:
        """Retorna la IP detectada en la red local."""
        return get_local_ip()

    def start_scan(self, target: str, profile_index: int, on_output=None, on_finish=None):
        """
        Inicia un escaneo Nmap en segundo plano según el perfil seleccionado.
        :param target: Cadena validada del objetivo (ej. '192.168.1.1' o '192.168.1.0/24').
        :param profile_index: Índice en la lista NMAP_PROFILES (0 a 12).
        :param on_output: Callback (str) para streaming de consola.
        :param on_finish: Callback (int) al culminar.
        """
        if not (0 <= profile_index < len(NMAP_PROFILES)):
            if on_output:
                on_output("[!] Índice de perfil Nmap inválido.")
            if on_finish:
                on_finish(-1)
            return None

        # Reutilizar carpeta de sesión o crear una nueva para la ráfaga
        if not self.current_session_dir:
            self.current_session_dir = SessionManager.create_session(BASE_DIR_NMAP)

        nombre_perfil, template = NMAP_PROFILES[profile_index]
        comando_resuelto = template.replace("{TARGET}", target).replace("{SESSION}", self.current_session_dir)
        cmd_completo = f"nmap {comando_resuelto}"

        if on_output:
            on_output(f"[*] Iniciando perfil: {nombre_perfil}")
            on_output(f"[*] Sesión guardada en: {self.current_session_dir}")

        return self.executor.run_async(
            comando=cmd_completo,
            on_output=on_output,
            on_finish=on_finish,
            use_shell=True
        )

    def stop_scan(self, on_output=None):
        """Detiene forzosamente el escaneo Nmap en ejecución."""
        if on_output:
            on_output("\n[!] Deteniendo proceso Nmap en curso...")
        self.executor.stop_current()
        # Matado de seguridad adicional para procesos huérfanos
        import subprocess
        safe_run(["sudo", "pkill", "-f", "nmap"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def list_saved_sessions(self):
        """Retorna las sesiones de auditoría de Nmap disponibles."""
        return SessionManager.list_sessions(BASE_DIR_NMAP)

    def list_session_reports(self, session_name: str):
        """Retorna los reportes .txt generados en una sesión."""
        session_path = os.path.join(BASE_DIR_NMAP, session_name)
        return SessionManager.list_session_files(session_path)

    def read_report(self, session_name: str, file_name: str) -> str:
        """Lee el contenido de un reporte de Nmap."""
        file_path = os.path.join(BASE_DIR_NMAP, session_name, file_name)
        return SessionManager.read_file(file_path)
