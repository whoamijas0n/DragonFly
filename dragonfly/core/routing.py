"""
dragonfly/core/routing.py - Detección de salida a Internet y planificación de red.

El modo Evil Twin con Internet necesita saber por qué interfaz sale el tráfico
del sistema, qué DNS usa el upstream y qué subred puede asignar al AP sin
entrar en conflicto con la red existente. Este módulo centraliza esas consultas
para que el servicio y la interfaz de Raspberry Pi no dupliquen comandos ni
reglas de parseo.
"""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import subprocess

from dragonfly.core.subprocess_utils import safe_run

_IP_CANDIDATES = ("/sbin/ip", "/usr/sbin/ip", "/usr/bin/ip")
_RESOLV_FILES = (
    "/run/systemd/resolve/resolv.conf",
    "/etc/resolv.conf",
)
_DEFAULT_DNS = ("1.1.1.1", "8.8.8.8")
_GATEWAY_CANDIDATES = (
    ipaddress.IPv4Network("10.42.0.0/24"),
    ipaddress.IPv4Network("10.13.37.0/24"),
    ipaddress.IPv4Network("172.16.42.0/24"),
    ipaddress.IPv4Network("192.168.42.0/24"),
)


def get_ip_binary() -> str | None:
    """Retorna la ruta de ``ip`` o ``None`` si no está instalado."""
    found = shutil.which("ip")
    if found:
        return found
    for candidate in _IP_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def _run_ip(arguments, timeout: int = 4):
    """Ejecuta ``ip`` de forma segura y retorna el resultado o ``None``."""
    binary = get_ip_binary()
    if not binary:
        return None
    try:
        return safe_run(
            [binary] + list(arguments),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def parse_default_routes(output: str) -> list[dict]:
    """
    Parsea la salida de ``ip -4 route show default``.

    Cada ruta se devuelve como un diccionario con ``gateway``, ``iface``,
    ``metric``, ``src`` y ``raw``. Se toleran rutas sin gateway (enlace directo)
    y líneas con atributos adicionales como ``proto`` o ``table``.
    """
    routes = []
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("default"):
            continue

        route = {
            "gateway": None,
            "iface": None,
            "metric": 0,
            "src": None,
            "raw": line,
        }
        tokens = line.split()
        index = 1
        while index < len(tokens):
            token = tokens[index]
            value = tokens[index + 1] if index + 1 < len(tokens) else None
            if value is None:
                break
            if token == "via":
                route["gateway"] = value
                index += 2
            elif token == "dev":
                route["iface"] = value
                index += 2
            elif token == "src":
                route["src"] = value
                index += 2
            elif token == "metric":
                try:
                    route["metric"] = int(value)
                except ValueError:
                    route["metric"] = 0
                index += 2
            else:
                index += 1

        if route["iface"]:
            routes.append(route)
    return routes


def get_default_routes() -> list[dict]:
    """Consulta las rutas por defecto IPv4 del sistema."""
    result = _run_ip(["-4", "route", "show", "default"])
    if result is None or result.returncode != 0:
        return []
    return parse_default_routes(result.stdout or "")


def parse_ipv4_interface(output: str):
    """
    Extrae la primera dirección IPv4 de la salida de ``ip -4 -o addr show``.

    Retorna un ``ipaddress.IPv4Interface`` o ``None``.
    """
    match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+/\d+)", output or "")
    if not match:
        return None
    try:
        return ipaddress.IPv4Interface(match.group(1))
    except ValueError:
        return None


def get_interface_ipv4(iface: str):
    """Retorna la dirección IPv4 de una interfaz o ``None``."""
    if not iface:
        return None
    result = _run_ip(["-4", "-o", "addr", "show", "dev", iface])
    if result is None or result.returncode != 0:
        return None
    return parse_ipv4_interface(result.stdout or "")


def get_interface_network(iface: str):
    """Retorna la red IPv4 asociada a una interfaz o ``None``."""
    interface = get_interface_ipv4(iface)
    if interface is None:
        return None
    return interface.network


def find_upstream(ap_iface: str | None = None, exclude_ifaces=None) -> dict | None:
    """
    Encuentra la mejor salida a Internet que no sea la interfaz del AP.

    Ordena las rutas por métrica y descarta las interfaces que no existan, no
    tengan IPv4 o estén en ``exclude_ifaces``. Retorna un diccionario con los
    datos de la ruta y de la interfaz para que el servicio pueda guardarlos en
    la sesión.
    """
    excluded = set(exclude_ifaces or [])
    if ap_iface:
        excluded.add(ap_iface)

    routes = get_default_routes()
    routes.sort(key=lambda item: (item.get("metric", 0), item.get("iface") or ""))

    for route in routes:
        iface = route.get("iface")
        if not iface or iface in excluded:
            continue
        if not os.path.exists(f"/sys/class/net/{iface}"):
            continue
        interface = get_interface_ipv4(iface)
        if interface is None:
            continue
        return {
            **route,
            "ip": str(interface.ip),
            "cidr": str(interface),
            "network": str(interface.network),
        }
    return None


def get_upstream_info_for_iface(iface: str) -> dict | None:
    """
    Retorna la ruta por defecto, IP y red de una interfaz concreta.

    Se usa cuando el operador elige manualmente qué interfaz debe ser el
    upstream, en lugar de aceptar la ruta de menor métrica. Si la interfaz no
    tiene una ruta por defecto o no tiene IPv4, retorna ``None``.
    """
    if not iface:
        return None
    routes = [
        route for route in get_default_routes()
        if route.get("iface") == iface
    ]
    if not routes:
        return None
    route = sorted(
        routes, key=lambda item: (item.get("metric", 0), item.get("raw") or "")
    )[0]
    interface = get_interface_ipv4(iface)
    if interface is None:
        return None
    return {
        **route,
        "ip": str(interface.ip),
        "cidr": str(interface),
        "network": str(interface.network),
    }


def choose_gateway(upstream_iface: str | None = None) -> dict:
    """
    Elige una subred privada para el AP que no choque con el upstream.

    Retorna ``gateway``, ``cidr`` y ``network``. Si todas las candidatas
    solaparan la red del upstream se lanza ``RuntimeError``.
    """
    upstream_network = get_interface_network(upstream_iface) if upstream_iface else None
    for network in _GATEWAY_CANDIDATES:
        if upstream_network is not None and network.overlaps(upstream_network):
            continue
        gateway = network.network_address + 1
        return {
            "gateway": str(gateway),
            "cidr": f"{gateway}/{network.prefixlen}",
            "network": str(network),
        }
    raise RuntimeError(
        "No hay una subred libre para el AP; revise las rutas del sistema."
    )


def _read_nameservers(path: str) -> list[str]:
    servers = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped.startswith("nameserver"):
                    continue
                parts = stripped.split()
                if len(parts) < 2:
                    continue
                candidate = parts[1]
                try:
                    ipaddress.IPv4Address(candidate)
                except ValueError:
                    continue
                servers.append(candidate)
    except OSError:
        pass
    return servers


def _resolvectl_dns(iface: str) -> list[str]:
    """Consulta los DNS asociados a una interfaz con ``resolvectl`` si existe."""
    binary = shutil.which("resolvectl")
    if not binary or not iface:
        return []
    try:
        result = safe_run(
            [binary, "dns", iface],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    if result.returncode != 0:
        return []

    servers = []
    for line in (result.stdout or "").splitlines():
        for candidate in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", line):
            try:
                ipaddress.IPv4Address(candidate)
            except ValueError:
                continue
            servers.append(candidate)
    return servers


def get_dns_servers(upstream_iface: str | None = None) -> list[str]:
    """
    Obtiene DNS reales para reenviar consultas de los clientes.

    Prioriza los DNS DHCP de la interfaz upstream (``resolvectl``), luego los
    ficheros de systemd-resolved/resolv.conf y, por último, DNS públicos.
    """
    candidates = []
    candidates.extend(_resolvectl_dns(upstream_iface) if upstream_iface else [])
    for path in _RESOLV_FILES:
        candidates.extend(_read_nameservers(path))

    result = []
    for candidate in candidates:
        if candidate in result:
            continue
        result.append(candidate)
        if len(result) >= 3:
            break

    if not result:
        result = list(_DEFAULT_DNS)
    return result


def get_primary_upstream_iface() -> str | None:
    """Interfaz de la ruta por defecto de menor métrica, si existe."""
    upstream = find_upstream()
    return upstream.get("iface") if upstream else None


def get_upstream_info(ap_iface: str | None = None) -> dict | None:
    """Retorna ruta, IP y DNS del upstream detectado."""
    upstream = find_upstream(ap_iface=ap_iface)
    if not upstream:
        return None
    return {
        **upstream,
        "dns": get_dns_servers(upstream["iface"]),
    }
