"""
dragonfly/core/wifi_interfaces.py - Capacidades reales de las interfaces WiFi.

Centraliza la consulta de los modos soportados por cada ``phy`` para que las
vistas y los servicios no ofrezcan interfaces que no pueden hacer monitor mode
o AP. En adaptadores FullMAC (por ejemplo el brcmfmac de la Raspberry Pi) el
``phy`` de la WiFi onboard soporta AP pero no monitor, mientras que un adaptador
USB puede soportar ambos. Elegir la interfaz equivocada provoca fallos de
``aireplay-ng`` del tipo "No such BSSID available" o "Device or resource busy".
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

from dragonfly.core.hardware import get_wifi_interfaces
from dragonfly.core.subprocess_utils import safe_run

# Rutas habituales cuando ``iw`` no está en el PATH del proceso (p. ej. la app
# se lanza desde una sesión sin /sbin). ``shutil.which`` se consulta primero.
_IW_CANDIDATES = ("/sbin/iw", "/usr/sbin/iw", "/usr/bin/iw")
_MONITOR_MODE = "monitor"
_AP_MODE = "ap"


def get_iw_binary() -> str | None:
    """Retorna la ruta de ``iw`` o ``None`` si no está instalado."""
    found = shutil.which("iw")
    if found:
        return found
    for candidate in _IW_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_iw(args, timeout=3):
    """Ejecuta ``iw`` capturando salida. Retorna ``CompletedProcess`` o ``None``."""
    binary = get_iw_binary()
    if not binary:
        return None
    try:
        return safe_run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def get_phy_name(iface: str) -> str | None:
    """Obtiene el nombre del ``phy`` asociado a una interfaz (``phy0``, ``phy1``...)."""
    phy_link = f"/sys/class/net/{iface}/phy80211"
    if os.path.islink(phy_link):
        try:
            return os.path.basename(os.readlink(phy_link))
        except OSError:
            pass

    result = _run_iw(["dev", iface, "info"])
    if result is None or result.returncode != 0:
        return None
    for line in (result.stdout or "").splitlines():
        match = re.match(r"^\s*wiphy\s+(\S+)", line)
        if match:
            return match.group(1)
    return None


def parse_supported_modes(phy_output: str) -> set[str]:
    """
    Extrae los modos del bloque ``Supported interface modes`` de ``iw phy``.

    Retorna un conjunto vacío si el bloque no existe o está vacío.
    """
    if not phy_output:
        return set()

    lines = phy_output.splitlines()
    for index, line in enumerate(lines):
        if "Supported interface modes:" not in line:
            continue

        modes = set()
        cursor = index + 1
        # El bloque son líneas con viñeta. Se detiene en la primera sección
        # posterior (Band, valid interface combinations, etc.).
        while cursor < len(lines):
            candidate = lines[cursor].strip()
            if not candidate:
                cursor += 1
                continue
            if not candidate.startswith("*"):
                break
            mode = candidate.lstrip("*").strip().lower()
            if mode:
                modes.add(mode)
            cursor += 1
        return modes

    return set()


def parse_iw_dev_info(dev_output: str) -> dict:
    """
    Parsea la salida de ``iw dev <iface> info``.

    Retorna ``{"type": str|None, "channel": int|None, "ssid": str|None}``.
    """
    info = {"type": None, "channel": None, "ssid": None}
    if not dev_output:
        return info

    for line in dev_output.splitlines():
        stripped = line.strip()
        match = re.match(r"^type\s+(\S+)", stripped)
        if match:
            info["type"] = match.group(1).lower()
            continue

        match = re.match(r"^channel\s+(\d+)", stripped)
        if match:
            try:
                info["channel"] = int(match.group(1))
            except ValueError:
                info["channel"] = None
            continue

        match = re.match(r"^ssid\s+(.+)$", stripped)
        if match:
            info["ssid"] = match.group(1).strip()

    return info


def get_interface_info(iface: str) -> dict:
    """Estado actual de la interfaz: tipo, canal y SSID (si aplica)."""
    result = _run_iw(["dev", iface, "info"])
    if result is None or result.returncode != 0:
        return {"type": None, "channel": None, "ssid": None}
    return parse_iw_dev_info(result.stdout or "")


def get_interface_type(iface: str) -> str | None:
    """Tipo nl80211 actual de la interfaz en minúsculas (``monitor``, ``ap``...)."""
    return get_interface_info(iface).get("type")


def get_interface_channel(iface: str) -> int | None:
    """Canal actual de la interfaz o ``None`` si no se puede determinar."""
    return get_interface_info(iface).get("channel")


def get_supported_modes(iface: str) -> set[str] | None:
    """
    Modos soportados por el ``phy`` de ``iface``.

    Retorna ``None`` cuando no se puede consultar (iw ausente o error), de modo
    que los llamadores puedan degradar a "desconocido" en lugar de bloquear la
    interfaz. Un conjunto vacío significa que el bloque se consultó pero no
    contenía modos.
    """
    if not iface or not os.path.exists(f"/sys/class/net/{iface}"):
        return None

    phy = get_phy_name(iface)
    if not phy:
        return None

    result = _run_iw(["phy", phy, "info"])
    if result is None or result.returncode != 0:
        return None
    return parse_supported_modes(result.stdout or "")


def supports_monitor(iface: str) -> bool:
    """True si la interfaz soporta monitor mode (o no se pudo determinar)."""
    modes = get_supported_modes(iface)
    return modes is None or _MONITOR_MODE in modes


def supports_ap(iface: str) -> bool:
    """True si la interfaz soporta modo AP (o no se pudo determinar)."""
    modes = get_supported_modes(iface)
    return modes is None or _AP_MODE in modes


def share_phy(iface1: str, iface2: str) -> bool:
    """
    True si ambas interfaces pertenecen a la misma radio física.

    Dos vif del mismo ``phy`` no pueden hacer monitor y AP a la vez en adaptadores
    que no anuncian combinaciones de interfaces (la mayoría de los USB).
    """
    phy1 = get_phy_name(iface1)
    phy2 = get_phy_name(iface2)
    return bool(phy1 and phy2 and phy1 == phy2)


def unique_phy_interfaces(ifaces) -> list[str]:
    """Conserva una sola interfaz por radio física, en orden estable."""
    result = []
    seen = set()
    for iface in ifaces:
        phy = get_phy_name(iface) or f"iface:{iface}"
        if phy in seen:
            continue
        seen.add(phy)
        result.append(iface)
    return result


def get_monitor_interfaces(unique_phys: bool = False) -> list[str]:
    """Interfaces WiFi utilizables para monitor mode, en orden estable."""
    interfaces = [iface for iface in get_wifi_interfaces() if supports_monitor(iface)]
    return unique_phy_interfaces(interfaces) if unique_phys else interfaces


def get_ap_interfaces(unique_phys: bool = False) -> list[str]:
    """Interfaces WiFi utilizables como punto de acceso, en orden estable."""
    interfaces = [iface for iface in get_wifi_interfaces() if supports_ap(iface)]
    return unique_phy_interfaces(interfaces) if unique_phys else interfaces


def get_deauth_interfaces(ap_iface: str) -> list[str]:
    """
    Interfaces de monitor utilizables para deauth mientras ``ap_iface`` hace AP.

    Excluye la propia interfaz AP y cualquier vif de su misma radio.
    """
    return [
        iface for iface in get_monitor_interfaces(unique_phys=True)
        if iface != ap_iface and not share_phy(iface, ap_iface)
    ]


def get_evil_twin_ap_interfaces() -> list[str]:
    """
    Interfaces que pueden ser AP dejando al menos otra radio para deauth.

    En un equipo con una sola radio (sin combinaciones AP+monitor) no se puede
    montar un Evil Twin con deauth; es mejor no ofrecer esa combinación que
    lanzar un ataque que fallará.
    """
    return [
        iface for iface in get_ap_interfaces()
        if get_deauth_interfaces(iface)
    ]
