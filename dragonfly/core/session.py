"""
dragonfly/core/session.py - Gestor de almacenamiento de sesiones y auditorías.
Organiza y recupera los resultados generados por cada vector de ataque.
"""

import os
import glob
from datetime import datetime


class SessionManager:
    """
    Gestiona la creación, listado y lectura de carpetas de auditoría con marca temporal.
    """

    @staticmethod
    def create_session(base_dir: str, prefix: str = "Auditoria") -> str:
        """
        Crea y retorna una subcarpeta con marca de tiempo única dentro del directorio base.
        Formato: {base_dir}/{prefix}-YYYY-MM-DD-HH-MM-SS
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        session_path = os.path.join(base_dir, f"{prefix}-{timestamp}")
        os.makedirs(session_path, exist_ok=True)
        return os.path.abspath(session_path)

    @staticmethod
    def list_sessions(base_dir: str):
        """
        Retorna la lista ordenada de directorios de sesión existentes dentro de base_dir.
        """
        if not os.path.exists(base_dir):
            return []
        try:
            sessions = [
                d for d in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, d))
            ]
            return sorted(sessions, reverse=True)
        except Exception:
            return []

    @staticmethod
    def list_session_files(session_dir: str):
        """
        Retorna los archivos contenidos en una carpeta de sesión específica.
        """
        if not os.path.exists(session_dir):
            return []
        try:
            files = [
                f for f in os.listdir(session_dir)
                if os.path.isfile(os.path.join(session_dir, f))
            ]
            return sorted(files)
        except Exception:
            return []

    @staticmethod
    def read_file(file_path: str) -> str:
        """
        Lee y retorna el contenido de texto de un archivo de evidencia.
        """
        if not os.path.exists(file_path):
            return f"[!] El archivo no existe: {file_path}"
        try:
            with open(file_path, "r", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"[!] Error al leer el archivo: {e}"
