"""
dragonfly/core/process_manager.py - Gestor de ciclo de vida de procesos ofensivos.
Controla procesos en segundo plano como hostapd, dnsmasq, airodump-ng y limpieza de iptables.
"""

import subprocess
import os
import signal
import time


class ProcessManager:
    """
    Rastrea y finaliza procesos hijos del sistema operativo de forma controlada y segura.
    """

    def __init__(self):
        self._procs = {}

    def register(self, name: str, proc: subprocess.Popen):
        """Registra un proceso Popen con un identificador único."""
        self._procs[name] = proc

    def get(self, name: str):
        """Obtiene el proceso Popen asociado al nombre."""
        return self._procs.get(name)

    def is_running(self, name: str) -> bool:
        """Verifica si el proceso indicado está activo."""
        proc = self._procs.get(name)
        return proc is not None and proc.poll() is None

    def terminate_proc(self, name: str, timeout: int = 5):
        """
        Detiene un proceso específico con SIGTERM y posterior SIGKILL si no responde.
        """
        proc = self._procs.get(name)
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, Exception):
                try:
                    proc.kill()
                except Exception:
                    pass
            self._procs[name] = None

    def terminate_all(self, timeout: int = 5):
        """Finaliza todos los procesos registrados."""
        for name in list(self._procs.keys()):
            self.terminate_proc(name, timeout=timeout)

    @staticmethod
    def pkill(pattern: str):
        """Mata procesos usando pkill (SIGTERM). Usa -f solo para scripts o patrones con espacios."""
        try:
            cmd = ["sudo", "pkill"]
            if " " in pattern or pattern.endswith(".py"):
                cmd.append("-f")
            cmd.append(pattern)
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def pkill_force(pattern: str):
        """Mata procesos forzosamente con SIGKILL (-9)."""
        try:
            cmd = ["sudo", "pkill", "-9"]
            if " " in pattern or pattern.endswith(".py"):
                cmd.append("-f")
            cmd.append(pattern)
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def flush_iptables(ap_iface: str = None):
        """
        Limpia completamente las reglas NAT y de filtrado de iptables y restaura interfaces.
        """
        try:
            subprocess.run(["sudo", "iptables", "--flush"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "iptables", "--table", "nat", "--flush"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], stderr=subprocess.DEVNULL)
            if ap_iface:
                subprocess.run(["sudo", "ip", "link", "set", ap_iface, "down"], stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "iw", "dev", ap_iface, "set", "type", "managed"], stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "ip", "link", "set", ap_iface, "up"], stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def restart_network_manager(timeout: int = 15):
        """Reinicia el servicio NetworkManager con timeout de seguridad."""
        try:
            subprocess.run(
                ["sudo", "systemctl", "restart", "NetworkManager"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
            )
        except Exception:
            pass
