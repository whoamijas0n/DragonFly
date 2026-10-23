"""
dragonfly/core/network_manager.py - Coordinación con NetworkManager.

Cuando NetworkManager gestiona una interfaz WiFi mantiene abierta una conexión
con wpa_supplicant y, en muchos drivers, bloquea los cambios de modo nl80211 con
``Device or resource busy``. Los ataques que necesitan monitor mode o modo AP
deben liberar primero la interfaz y devolverla a NetworkManager al terminar.

Este módulo encapsula esas operaciones para no reiniciar NetworkManager (lo que
tumbaría también la interfaz que usa el operador para conectarse por SSH) y para
esperar de forma acotada a que el estado del dispositivo cambie.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

from dragonfly.core.subprocess_utils import safe_run

_NMCLI_CANDIDATES = ("/usr/bin/nmcli", "/usr/sbin/nmcli", "/bin/nmcli", "/sbin/nmcli")
_UNMANAGED = "unmanaged"


def get_nmcli_binary() -> str | None:
    """Retorna la ruta de ``nmcli`` o ``None`` si NetworkManager no está instalado."""
    found = shutil.which("nmcli")
    if found:
        return found
    for candidate in _NMCLI_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_available() -> bool:
    """True si ``nmcli`` está disponible en el sistema."""
    return get_nmcli_binary() is not None


def _run_nmcli(args, timeout=8):
    """Ejecuta ``nmcli`` capturando salida. Retorna ``CompletedProcess`` o ``None``."""
    binary = get_nmcli_binary()
    if not binary:
        return None
    try:
        return safe_run(
            ["sudo", binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _split_terse_fields(line: str) -> list[str]:
    """
    Divide una línea de ``nmcli -t`` respetando los escapes ``\\:`` y ``\\\\``.
    """
    fields = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def parse_device_status(output: str) -> dict[str, dict[str, str]]:
    """
    Parsea la salida de ``nmcli -t -f DEVICE,STATE,CONNECTION device status``.

    Retorna ``{iface: {"state": "connected", "connection": "perfil"}}``.
    """
    devices = {}
    for line in (output or "").splitlines():
        if not line.strip():
            continue
        fields = _split_terse_fields(line)
        if len(fields) < 2:
            continue
        iface = fields[0].strip()
        state = fields[1].strip().lower()
        connection = fields[2].strip() if len(fields) > 2 else ""
        if not iface:
            continue
        devices[iface] = {"state": state, "connection": connection}
    return devices


def get_device_status() -> dict[str, dict[str, str]]:
    """Estado de todos los dispositivos conocidos por NetworkManager."""
    result = _run_nmcli(["-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status"], timeout=5)
    if result is None or result.returncode != 0:
        return {}
    return parse_device_status(result.stdout or "")


def get_device_state(iface: str) -> str | None:
    """Estado de una interfaz según NetworkManager o ``None`` si no la conoce."""
    status = get_device_status()
    entry = status.get(iface)
    return entry["state"] if entry else None


def is_managed(iface: str) -> bool | None:
    """
    True si NetworkManager gestiona la interfaz, False si está ``unmanaged``.

    ``None`` significa que no se pudo determinar (nmcli ausente o interfaz no
    listada), en cuyo caso los llamadores deben continuar en modo best-effort.
    """
    state = get_device_state(iface)
    if state is None:
        return None
    return state != _UNMANAGED


def _wait_for_state(iface: str, states: set[str], timeout: float, interval: float = 0.25) -> str | None:
    """Espera hasta que la interfaz alcance uno de ``states``. Retorna el estado final."""
    deadline = time.monotonic() + max(0.0, timeout)
    last_state = None
    while True:
        last_state = get_device_state(iface)
        if last_state in states:
            return last_state
        if time.monotonic() >= deadline:
            return last_state
        time.sleep(interval)


def release_device(iface: str, timeout: float = 6.0) -> bool:
    """
    Libera una interfaz de NetworkManager (``managed no``) y espera a que quede
    ``unmanaged``.

    Nunca reinicia NetworkManager: el resto de interfaces y las conexiones SSH
    permanecen intactas. Retorna True si la interfaz quedó libre o si nmcli no
    está disponible (no hay nada que liberar).
    """
    if not iface:
        return False
    if not is_available():
        return True

    state = get_device_state(iface)
    if state == _UNMANAGED:
        return True

    result = _run_nmcli(["device", "set", iface, "managed", "no"], timeout=8)
    if result is None or result.returncode != 0:
        # Si la interfaz no la conoce NetworkManager ya está libre en la práctica.
        current = get_device_state(iface)
        return current == _UNMANAGED

    final_state = _wait_for_state(iface, {_UNMANAGED}, timeout=timeout)
    return final_state == _UNMANAGED


def restore_device(iface: str, timeout: float = 10.0, connect: bool = True) -> bool:
    """
    Devuelve una interfaz a NetworkManager (``managed yes``).

    Espera a que deje de estar ``unmanaged`` y, si queda desconectada, intenta
    reconectarla con el perfil guardado. Retorna True si la interfaz vuelve a
    estar gestionada.
    """
    if not iface:
        return False
    if not is_available():
        return True

    state = get_device_state(iface)
    if state is not None and state != _UNMANAGED:
        return True

    result = _run_nmcli(["device", "set", iface, "managed", "yes"], timeout=8)
    if result is None or result.returncode != 0:
        return False

    deadline = time.monotonic() + max(0.0, timeout)
    final_state = None
    while time.monotonic() < deadline:
        final_state = get_device_state(iface)
        if final_state is not None and final_state != _UNMANAGED:
            break
        time.sleep(0.3)

    if final_state is None or final_state == _UNMANAGED:
        return False

    if connect and final_state == "disconnected":
        # Best-effort: NM puede tardar en aplicar autoconnect. No bloquea más
        # allá del timeout y un fallo aquí no invalida la restauración.
        _run_nmcli(["device", "connect", iface], timeout=max(10, int(timeout)))
    return True
