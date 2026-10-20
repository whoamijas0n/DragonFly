"""
dragonfly/core - Núcleo de bajo nivel de DragonFly.
Proporciona ejecutor de comandos asíncronos, gestión de procesos, hardware y sesiones.
"""

from dragonfly.core.executor import CommandExecutor
from dragonfly.core.process_manager import ProcessManager
from dragonfly.core.session import SessionManager
from dragonfly.core.hardware import (
    get_network_interfaces,
    get_wifi_interfaces,
    get_local_ip,
    get_bluetooth_interfaces,
    detect_serial_port,
    is_raspberry_pi
)

__all__ = [
    "CommandExecutor",
    "ProcessManager",
    "SessionManager",
    "get_network_interfaces",
    "get_wifi_interfaces",
    "get_local_ip",
    "get_bluetooth_interfaces",
    "detect_serial_port",
    "is_raspberry_pi"
]
