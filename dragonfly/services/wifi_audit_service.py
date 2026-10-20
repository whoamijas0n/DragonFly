"""
dragonfly/services/wifi_audit_service.py - Reconocimiento WiFi pasivo (WiFi Audit 2.0 v1).

Este módulo concentra el parseo de airodump-ng, el enriquecimiento de redes y la
generación de reportes. Es deliberadamente independiente de la UI y no ejecuta
ataques: solo observa el espectro y documenta lo detectado.

Alcance v1:
- SSID, BSSID, canal, banda y señal (dBm / %).
- Seguridad, cifrado y autenticación.
- Beacons, data/IV.
- Clientes observados por red.
- Fabricante del AP (OUI).
- Score de honeypot + motivos.

Nota: el CSV de airodump-ng expone una sola columna "# IV" para el contador de
datos/IV del AP. Por compatibilidad se publican las claves ``data`` e ``iv`` con
ese mismo valor.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import subprocess
import threading
import time
from collections import defaultdict
from functools import lru_cache

from dragonfly.config import BASE_DIR_WIFI_AUDIT
from dragonfly.core.session import SessionManager
from dragonfly.core.subprocess_utils import safe_popen, safe_run, terminate_process_group

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BAND_FLAGS = {"2.4": "bg", "5": "a"}
BAND_LABELS = {"2.4": "2.4 GHz", "5": "5 GHz"}
HIDDEN_SSID = "<Oculta>"

# OUI de respaldo para instalaciones sin ieee-data/manuf. La base completa,
# cuando existe, se carga desde el sistema y tiene prioridad.
OUI_FALLBACK = {
    "00000C": "Cisco Systems, Inc.",
    "000C29": "VMware, Inc.",
    "005056": "VMware, Inc.",
    "080027": "PCS Systemtechnik GmbH (VirtualBox)",
    "001C42": "Parallels, Inc.",
    "3C5A37": "Samsung Electronics",
    "F4F5D8": "Google, Inc.",
}

OUI_PATHS = (
    "/usr/share/ieee-data/oui.txt",
    "/var/lib/ieee-data/oui.txt",
    "/usr/share/wireshark/manuf",
    "/usr/share/nmap/nmap-mac-prefixes",
)

_OUI_LINE_RE = re.compile(
    r"^\s*([0-9A-Fa-f]{2})[-:]?([0-9A-Fa-f]{2})[-:]?([0-9A-Fa-f]{2})"
    r"(?:[-:][0-9A-Fa-f]{2})?(?:/\d+)?\s*(?:\(hex\)\s*)?(.+?)\s*$"
)

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?:[:-]?[0-9A-Fa-f]{2}){5}$")
_IFACE_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


# ---------------------------------------------------------------------------
# Utilidades de red / presentación
# ---------------------------------------------------------------------------

def normalize_mac(value) -> str:
    """Devuelve una MAC en formato AA:BB:CC:DD:EE:FF o ``""`` si no es válida."""
    text = str(value or "").strip()
    if not _MAC_RE.match(text):
        return ""
    hex_digits = re.sub(r"[^0-9A-Fa-f]", "", text).upper()
    if len(hex_digits) != 12:
        return ""
    return ":".join(hex_digits[i:i + 2] for i in range(0, 12, 2))


def _first_octet(bssid) -> int | None:
    normalized = normalize_mac(bssid)
    if not normalized:
        return None
    try:
        return int(normalized[:2], 16)
    except ValueError:
        return None


def is_locally_administered(bssid) -> bool:
    """True si el bit U/L de la MAC está activo (MAC administrada localmente)."""
    octet = _first_octet(bssid)
    return bool(octet is not None and octet & 0x02)


def is_multicast(bssid) -> bool:
    """True si el bit multicast de la MAC está activo (BSSID inválido para un AP)."""
    octet = _first_octet(bssid)
    return bool(octet is not None and octet & 0x01)


def channel_to_band(channel) -> str:
    """Convierte un canal 802.11 en una etiqueta de banda legible."""
    try:
        ch = int(str(channel).strip())
    except (TypeError, ValueError):
        return "Desconocida"
    if 1 <= ch <= 14:
        return "2.4 GHz"
    if 32 <= ch <= 196:
        return "5 GHz"
    return "Desconocida"


def dbm_to_quality(dbm) -> int | None:
    """Convierte dBm a porcentaje aproximado de calidad (0-100)."""
    if dbm is None:
        return None
    try:
        value = int(dbm)
    except (TypeError, ValueError):
        return None
    if value == -1:
        return None
    return max(0, min(100, int(2 * (value + 100))))


def format_security(privacy, cipher, auth) -> str:
    """Resume privacidad, cifrado y autenticación en una etiqueta legible."""
    privacy = str(privacy or "").strip()
    cipher = str(cipher or "").strip()
    auth = str(auth or "").strip()

    if not privacy or privacy.upper() in {"OPN", "OPEN"}:
        return "Abierta"

    parts = [privacy]
    if cipher and cipher.upper() not in {"N/A", "-"} and cipher.lower() != privacy.lower():
        parts.append(cipher)
    if auth and auth.upper() not in {"N/A", "-"} and auth.lower() not in {privacy.lower(), cipher.lower()}:
        parts.append(auth)
    return "-".join(parts)


def honeypot_level(score: int) -> str:
    """Nivel cualitativo del score de honeypot."""
    if score >= 75:
        return "Muy alto"
    if score >= 50:
        return "Alto"
    if score >= 25:
        return "Medio"
    return "Bajo"


def _to_int(value, default=0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _to_int_or_none(value):
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Parser CSV de airodump-ng
# ---------------------------------------------------------------------------

def parse_airodump_csv(csv_path: str):
    """
    Parsea un CSV de airodump-ng y retorna ``(access_points, stations)``.

    El parser tolera:
    - ESSID con comas (gracias a csv.reader).
    - SSID oculto/vacío (se normaliza a ``<Oculta>``).
    - ``PWR`` igual a -1 (se conserva como -1; el enriquecimiento lo vuelve None).
    - Filas malformadas o secciones incompletas.
    - Archivos inexistentes (retorna listas vacías).
    """
    aps = []
    stations = []
    if not csv_path or not os.path.exists(csv_path):
        return aps, stations

    try:
        with open(csv_path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            rows = list(csv.reader(handle, skipinitialspace=True))
    except (OSError, csv.Error):
        return aps, stations

    section = None
    for row in rows:
        if not row or all(not str(cell).strip() for cell in row):
            continue

        first = str(row[0]).strip()
        first_lower = first.lower()

        if first_lower == "bssid" and len(row) >= 14:
            section = "ap"
            continue
        if first_lower == "station mac" and len(row) >= 6:
            section = "station"
            continue

        if section == "ap":
            if len(row) < 14:
                continue
            bssid = normalize_mac(row[0])
            if not bssid:
                continue

            channel = str(row[3]).strip()
            essid = str(row[13]).strip()
            if not essid or essid.lower().startswith("<length:") or essid.lower() == "<hidden>":
                essid = HIDDEN_SSID
            power = _to_int_or_none(row[8])
            beacons = _to_int(row[9])
            iv = _to_int(row[10])

            aps.append({
                "bssid": bssid,
                "first_seen": str(row[1]).strip(),
                "last_seen": str(row[2]).strip(),
                "channel": channel,
                "speed": str(row[4]).strip(),
                "privacy": str(row[5]).strip(),
                "cipher": str(row[6]).strip(),
                "auth": str(row[7]).strip(),
                "power": power,
                "beacons": beacons,
                "iv": iv,
                "data": iv,
                "lan_ip": str(row[11]).strip(),
                "id_length": str(row[12]).strip(),
                "essid": essid,
                "key": str(row[14]).strip() if len(row) > 14 else "",
                "band": channel_to_band(channel),
            })

        elif section == "station":
            if len(row) < 6:
                continue
            station_mac = normalize_mac(row[0])
            if not station_mac:
                continue
            stations.append({
                "station_mac": station_mac,
                "first_seen": str(row[1]).strip(),
                "last_seen": str(row[2]).strip(),
                "power": _to_int_or_none(row[3]),
                "packets": _to_int(row[4]),
                "bssid": normalize_mac(row[5]),
                "probed": str(row[6]).strip() if len(row) > 6 else "",
            })

    return aps, stations


# ---------------------------------------------------------------------------
# OUI / fabricante
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_oui_db():
    """Carga la base OUI local. Si no existe, usa el diccionario de respaldo."""
    database = dict(OUI_FALLBACK)

    for path in OUI_PATHS:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if "(base 16)" in line:
                        continue
                    match = _OUI_LINE_RE.match(line)
                    if not match:
                        continue
                    oui = f"{match.group(1)}{match.group(2)}{match.group(3)}".upper()
                    vendor = match.group(4).strip().lstrip(":- ").strip()
                    if vendor:
                        database.setdefault(oui, vendor)
        except OSError:
            continue

    return database


def lookup_vendor(bssid) -> str:
    """Retorna el fabricante asociado al OUI del BSSID."""
    normalized = normalize_mac(bssid)
    if not normalized:
        return "Desconocido"
    if is_locally_administered(normalized):
        return "Localmente administrado"
    oui = normalized.replace(":", "")[:6].upper()
    return load_oui_db().get(oui, "Desconocido")


# ---------------------------------------------------------------------------
# Honeypot
# ---------------------------------------------------------------------------

def score_honeypot(ap: dict, all_aps=None):
    """
    Calcula un score heurístico 0-100 y una lista de motivos.

    No emite un veredicto definitivo: solo señala indicios que el operador debe
    correlacionar. Las reglas son deliberadamente conservadoras para evitar
    falsos positivos en redes domésticas o dual-band normales.
    """
    all_aps = all_aps or []
    score = 0
    reasons = []

    bssid = normalize_mac(ap.get("bssid"))
    essid = str(ap.get("essid") or "").strip()
    if not essid or essid.lower().startswith("<length:") or essid.lower() == "<hidden>":
        essid = HIDDEN_SSID
    privacy = str(ap.get("privacy") or "").strip()
    cipher = str(ap.get("cipher") or "").strip()
    auth = str(ap.get("auth") or "").strip()
    privacy_upper = privacy.upper()
    security = format_security(privacy, cipher, auth)
    vendor = lookup_vendor(bssid)

    if is_multicast(bssid):
        score += 30
        reasons.append("BSSID multicast: no corresponde a un AP físico real.")
    if is_locally_administered(bssid):
        score += 30
        reasons.append("BSSID con MAC localmente administrada (posible suplantación).")

    # Comparaciones contra el resto del vecindario. Un mismo SSID en 2.4 y 5 GHz
    # con igual seguridad y fabricante es normal y no penaliza.
    if essid and essid != HIDDEN_SSID:
        same_ssid = [
            other for other in all_aps
            if normalize_mac(other.get("bssid")) != bssid
            and str(other.get("essid") or "").strip().lower() == essid.lower()
        ]
        if same_ssid:
            other_securities = {
                format_security(other.get("privacy"), other.get("cipher"), other.get("auth"))
                for other in same_ssid
            }
            if other_securities and security not in other_securities:
                score += 20
                reasons.append("SSID repetido con configuraciones de seguridad distintas.")
            elif len(other_securities) > 1:
                score += 20
                reasons.append("SSID repetido con configuraciones de seguridad distintas.")

            other_vendors = {
                lookup_vendor(other.get("bssid")) for other in same_ssid
            }
            known_other_vendors = {v for v in other_vendors if v != "Desconocido"}
            if (
                vendor != "Desconocido"
                and known_other_vendors
                and any(v != vendor for v in known_other_vendors)
            ):
                score += 15
                reasons.append("SSID repetido con fabricantes distintos.")

    if not privacy or privacy_upper in {"OPN", "OPEN"}:
        score += 10
        reasons.append("Red abierta: no utiliza cifrado.")
    if "WEP" in privacy_upper or "WEP" in cipher.upper():
        score += 15
        reasons.append("Cifrado WEP obsoleto y vulnerable.")

    if vendor == "Desconocido":
        score += 5
        reasons.append("Fabricante del AP no identificado por OUI.")

    signal = ap.get("signal_dbm")
    if signal is None:
        signal = ap.get("power")
    if signal is not None:
        try:
            signal = int(signal)
        except (TypeError, ValueError):
            signal = None
    if signal is not None and signal != -1 and signal > -35:
        score += 10
        reasons.append("Señal inusualmente fuerte (> -35 dBm).")

    score = max(0, min(100, score))
    return score, reasons


def enrich_networks(aps, stations=None, interfaces=None):
    """
    Convierte APs crudos del parser en el modelo enriquecido de la v1.
    """
    stations = stations or []

    station_map = defaultdict(set)
    for station in stations:
        station_mac = normalize_mac(station.get("station_mac"))
        bssid = normalize_mac(station.get("bssid"))
        if station_mac and bssid:
            station_map[bssid].add(station_mac)

    enriched = []
    for ap in aps:
        bssid = normalize_mac(ap.get("bssid"))
        if not bssid:
            continue

        essid = str(ap.get("essid") or "").strip()
        if not essid or essid.lower().startswith("<length:") or essid.lower() == "<hidden>":
            essid = HIDDEN_SSID
        channel = str(ap.get("channel") or "").strip()
        band = str(ap.get("band") or channel_to_band(channel))
        if band == "Desconocida" and ap.get("scan_band") in BAND_LABELS:
            band = BAND_LABELS[ap["scan_band"]]

        power = ap.get("power")
        signal_dbm = power if isinstance(power, int) and power != -1 else None
        signal_quality = dbm_to_quality(signal_dbm)

        iv = _to_int(ap.get("iv"))
        raw_data = ap.get("data")
        data = _to_int(raw_data) if raw_data is not None else iv
        score, reasons = score_honeypot(ap, aps)

        enriched.append({
            "essid": essid,
            "bssid": bssid,
            "channel": channel,
            "ch": channel,  # compatibilidad con las vistas existentes
            "band": band,
            "banda": band.replace(" ", ""),  # compatibilidad con las vistas existentes
            "signal_dbm": signal_dbm,
            "signal_quality": signal_quality,
            "privacy": str(ap.get("privacy") or "").strip(),
            "cipher": str(ap.get("cipher") or "").strip(),
            "auth": str(ap.get("auth") or "").strip(),
            "security": format_security(ap.get("privacy"), ap.get("cipher"), ap.get("auth")),
            "beacons": _to_int(ap.get("beacons")),
            "data": data,
            "iv": iv,
            "clients_observed": len(station_map.get(bssid, set())),
            "vendor": lookup_vendor(bssid),
            "honeypot_score": score,
            "honeypot_level": honeypot_level(score),
            "honeypot_reasons": reasons,
        })

    enriched.sort(key=lambda item: (
        -(item["signal_dbm"] if item["signal_dbm"] is not None else -100),
        item["essid"].lower(),
        item["bssid"],
    ))
    return enriched


# ---------------------------------------------------------------------------
# Formato para UI / reportes
# ---------------------------------------------------------------------------

def _signal_text(net: dict) -> str:
    dbm = net.get("signal_dbm")
    quality = net.get("signal_quality")
    if dbm is None:
        return "N/D"
    if quality is None:
        return f"{dbm} dBm"
    return f"{dbm} dBm ({quality}%)"


def format_network_line(net: dict) -> str:
    """Línea compacta para listados de escritorio."""
    return (
        f"{net.get('essid', HIDDEN_SSID)} | CH {net.get('channel', '?')} | "
        f"{_signal_text(net)} | CL {net.get('clients_observed', 0)} | "
        f"HP {net.get('honeypot_score', 0)} ({net.get('honeypot_level', 'Bajo')})"
    )


def format_network_compact(net: dict) -> str:
    """Línea de dos renglones para la pantalla táctil de 320x240."""
    essid = str(net.get("essid", HIDDEN_SSID))[:16]
    dbm = net.get("signal_dbm")
    dbm_text = "N/D" if dbm is None else f"{dbm}dBm"
    return (
        f"{essid}  CH{net.get('channel', '?')}\n"
        f"{dbm_text}  CL:{net.get('clients_observed', 0)}  "
        f"HP:{net.get('honeypot_score', 0)}"
    )


def format_network_detail(net: dict) -> str:
    """Detalle completo de una red para la vista táctil o de escritorio."""
    reasons = net.get("honeypot_reasons") or []
    reasons_text = "\n".join(f"  - {reason}" for reason in reasons) if reasons else "  - Sin indicios relevantes."
    return (
        f"ESSID: {net.get('essid', HIDDEN_SSID)}\n"
        f"BSSID: {net.get('bssid', '')}\n"
        f"Canal: {net.get('channel', '?')} | Banda: {net.get('band', 'Desconocida')}\n"
        f"Señal: {_signal_text(net)}\n"
        f"Seguridad: {net.get('security', 'Desconocida')}\n"
        f"Cifrado: {net.get('cipher') or 'N/A'} | Autenticación: {net.get('auth') or 'N/A'}\n"
        f"Beacons: {net.get('beacons', 0)} | Data: {net.get('data', 0)} | IV: {net.get('iv', 0)}\n"
        f"Clientes observados: {net.get('clients_observed', 0)}\n"
        f"Fabricante: {net.get('vendor', 'Desconocido')}\n"
        f"Honeypot: {net.get('honeypot_score', 0)}/100 ({net.get('honeypot_level', 'Bajo')})\n"
        f"Motivos:\n{reasons_text}"
    )


def format_summary(summary: dict) -> str:
    """Resumen breve para encabezados de UI."""
    return (
        f"Redes: {summary.get('total_redes', 0)} | "
        f"Abiertas: {summary.get('abiertas', 0)} | "
        f"WEP: {summary.get('wep', 0)} | "
        f"WPA2: {summary.get('wpa2', 0)} | "
        f"WPA3: {summary.get('wpa3', 0)} | "
        f"Clientes: {summary.get('clientes_observados', 0)} | "
        f"Score alto: {summary.get('score_alto', 0)}"
    )


def build_summary(networks, interfaces=None, duration=0, stations=None):
    """Construye el resumen que se guarda en el reporte y se muestra en UI."""
    networks = networks or []
    stations = stations or []
    interfaces = interfaces or []

    summary = {
        "total_redes": len(networks),
        "abiertas": 0,
        "wep": 0,
        "wpa2": 0,
        "wpa3": 0,
        "otras": 0,
        "score_alto": 0,
        "clientes_observados": 0,
        "interfaces": list(interfaces),
        "duration": duration,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    unique_stations = set()
    for station in stations:
        station_mac = normalize_mac(station.get("station_mac"))
        bssid = normalize_mac(station.get("bssid"))
        if station_mac and bssid:
            unique_stations.add(station_mac)

    for net in networks:
        security = str(net.get("security") or "").upper()
        if security == "ABIERTA":
            summary["abiertas"] += 1
        elif "WEP" in security:
            summary["wep"] += 1
        elif "WPA3" in security:
            summary["wpa3"] += 1
        elif "WPA2" in security or "WPA" in security:
            summary["wpa2"] += 1
        else:
            summary["otras"] += 1

        if int(net.get("honeypot_score") or 0) >= 50:
            summary["score_alto"] += 1

    if unique_stations:
        summary["clientes_observados"] = len(unique_stations)
    else:
        summary["clientes_observados"] = sum(
            _to_int(net.get("clients_observed")) for net in networks
        )
    return summary


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------

class WiFiAuditService:
    """
    Servicio de reconocimiento WiFi pasivo y generación de reportes.

    ``wifi_service`` se usa únicamente para activar/restaurar modo monitor. Si se
    omite (por ejemplo en tests), se asume que la interfaz ya está en monitor.
    """

    def __init__(self, wifi_service=None, base_dir=None):
        self.wifi_service = wifi_service
        self.base_dir = base_dir or BASE_DIR_WIFI_AUDIT
        self._procs = []
        self._lock = threading.Lock()
        self._scan_done = threading.Event()
        self._scan_done.set()
        self._cancel_requested = threading.Event()

    # -- escaneo ---------------------------------------------------------

    def scan_single(self, iface: str, duration: int = 20, band=None, on_output=None):
        """Escanea una interfaz y guarda un reporte. Retorna un dict de resultado."""
        self._validate_iface(iface)
        duration = self._validate_duration(duration)
        band = self._normalize_band(band)
        log = on_output or (lambda _message: None)

        self._begin_scan()
        session_dir = None
        prefix = None
        mon = iface
        monitor_enabled = False

        try:
            session_dir = self._new_session()
            if self.wifi_service is not None:
                log(f"[*] Activando modo monitor en {iface}...")
                mon = self.wifi_service.enable_monitor_mode(iface)
                monitor_enabled = True

            log(f"[*] Escaneando {duration}s en {mon} (banda: {BAND_LABELS.get(band, 'auto')})...")
            prefix = self._run_airodump(mon, duration, band)
            if self._cancel_requested.is_set():
                raise RuntimeError("Reconocimiento cancelado.")
            csv_path = f"{prefix}-01.csv"
            if not os.path.exists(csv_path):
                raise RuntimeError("airodump-ng no generó el archivo CSV esperado.")

            aps, stations = parse_airodump_csv(csv_path)
            for ap in aps:
                ap["source_iface"] = iface
                ap["scan_band"] = band or ""
            networks = enrich_networks(aps, stations, interfaces=[iface])
            summary = build_summary(networks, [iface], duration, stations)
            self.save_report(networks, summary, session_dir=session_dir)

            log(f"[+] {len(networks)} redes detectadas. Reporte: {session_dir}")
            return {
                "networks": networks,
                "summary": summary,
                "session_dir": session_dir,
                "interfaces": [iface],
                "duration": duration,
            }
        except Exception as exc:
            log(f"[!] Error en reconocimiento WiFi: {exc}")
            raise
        finally:
            if prefix:
                self._cleanup_prefix(prefix)
            if monitor_enabled:
                log(f"[*] Restaurando interfaz {mon}...")
                try:
                    self.wifi_service.disable_monitor_mode(mon)
                except Exception:
                    pass
            self._scan_done.set()

    def scan_dual(self, iface_2g: str, iface_5g: str, duration: int = 20, on_output=None):
        """Escanea 2.4 GHz y 5 GHz en paralelo con dos interfaces y guarda un reporte."""
        self._validate_iface(iface_2g)
        self._validate_iface(iface_5g)
        if iface_2g == iface_5g:
            raise ValueError("Seleccione dos interfaces distintas para dual-band.")
        if self.interfaces_share_phy(iface_2g, iface_5g):
            raise ValueError(
                "Las dos interfaces comparten el mismo phy. Use dos adaptadores "
                "independientes (por ejemplo, la Wi-Fi onboard + un USB)."
            )

        duration = self._validate_duration(duration)
        log = on_output or (lambda _message: None)
        self._begin_scan()
        session_dir = None
        prefixes = {}
        monitors = []
        monitor_enabled = []

        try:
            session_dir = self._new_session()
            if self.wifi_service is not None:
                log(f"[*] Activando modo monitor en {iface_2g}...")
                monitors.append(self.wifi_service.enable_monitor_mode(iface_2g))
                monitor_enabled.append(monitors[-1])
                log(f"[*] Activando modo monitor en {iface_5g}...")
                monitors.append(self.wifi_service.enable_monitor_mode(iface_5g))
                monitor_enabled.append(monitors[-1])
            else:
                monitors = [iface_2g, iface_5g]

            log(f"[*] Escaneando dual-band durante {duration}s...")
            errors = {}

            def run_band(key, mon, band):
                try:
                    prefixes[key] = self._run_airodump(mon, duration, band)
                except Exception as exc:
                    errors[key] = exc

            thread_2g = threading.Thread(
                target=run_band,
                args=("2.4", monitors[0], "2.4"),
                daemon=True,
            )
            thread_5g = threading.Thread(
                target=run_band,
                args=("5", monitors[1], "5"),
                daemon=True,
            )
            thread_2g.start()
            thread_5g.start()
            thread_2g.join()
            thread_5g.join()

            if self._cancel_requested.is_set():
                raise RuntimeError("Reconocimiento cancelado.")
            if errors:
                detail = "; ".join(str(exc) for exc in errors.values())
                raise RuntimeError(f"Falló uno de los escaneos: {detail}")
            if not any(
                prefix and os.path.exists(f"{prefix}-01.csv")
                for prefix in prefixes.values()
            ):
                raise RuntimeError("airodump-ng no generó archivos CSV para dual-band.")

            raw_aps = []
            all_stations = []
            for key, iface, band in (("2.4", iface_2g, "2.4"), ("5", iface_5g, "5")):
                prefix = prefixes.get(key)
                if not prefix:
                    continue
                csv_path = f"{prefix}-01.csv"
                if not os.path.exists(csv_path):
                    continue
                aps, stations = parse_airodump_csv(csv_path)
                for ap in aps:
                    ap["source_iface"] = iface
                    ap["scan_band"] = band
                raw_aps.extend(aps)
                all_stations.extend(stations)

            merged_aps = self._merge_raw_aps(raw_aps)
            merged_stations = self._merge_stations(all_stations)
            networks = enrich_networks(
                merged_aps,
                merged_stations,
                interfaces=[iface_2g, iface_5g],
            )
            summary = build_summary(
                networks,
                [iface_2g, iface_5g],
                duration,
                merged_stations,
            )
            self.save_report(networks, summary, session_dir=session_dir)

            log(f"[+] {len(networks)} redes detectadas. Reporte: {session_dir}")
            return {
                "networks": networks,
                "summary": summary,
                "session_dir": session_dir,
                "interfaces": [iface_2g, iface_5g],
                "duration": duration,
            }
        except Exception as exc:
            log(f"[!] Error en reconocimiento dual-band: {exc}")
            raise
        finally:
            for prefix in prefixes.values():
                self._cleanup_prefix(prefix)
            if self.wifi_service is not None:
                for mon in monitor_enabled:
                    log(f"[*] Restaurando interfaz {mon}...")
                    try:
                        self.wifi_service.disable_monitor_mode(mon)
                    except Exception:
                        pass
            self._scan_done.set()

    def stop_scan(self):
        """Termina cualquier airodump-ng lanzado por este servicio."""
        with self._lock:
            procs = list(self._procs)
        for proc in procs:
            try:
                if proc.poll() is None:
                    terminate_process_group(proc, timeout=2)
            except Exception:
                pass

    def cancel_scan(self):
        """Cancela el escaneo activo y termina airodump-ng."""
        self._cancel_requested.set()
        self.stop_scan()

    def wait_for_idle(self, timeout=15):
        """Espera a que el escaneo activo termine y restaure las interfaces."""
        return self._scan_done.wait(timeout)

    def _begin_scan(self):
        self._cancel_requested.clear()
        self._scan_done.clear()

    # -- reportes --------------------------------------------------------

    def save_report(self, networks, summary=None, session_dir=None):
        """Guarda redes.json, redes.csv y reporte.txt. Retorna la carpeta."""
        session_dir = session_dir or self._new_session()
        os.makedirs(session_dir, exist_ok=True)
        summary = summary or build_summary(networks)

        payload = {
            "metadata": summary,
            "networks": networks,
        }
        json_path = os.path.join(session_dir, "redes.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        csv_path = os.path.join(session_dir, "redes.csv")
        fieldnames = [
            "essid", "bssid", "channel", "band", "signal_dbm", "signal_quality",
            "security", "privacy", "cipher", "auth", "beacons", "data", "iv",
            "clients_observed", "vendor",
            "honeypot_score", "honeypot_level", "honeypot_reasons",
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for net in networks:
                row = dict(net)
                row["honeypot_reasons"] = " | ".join(net.get("honeypot_reasons") or [])
                writer.writerow(row)

        txt_path = os.path.join(session_dir, "reporte.txt")
        with open(txt_path, "w", encoding="utf-8") as handle:
            handle.write("DRAGONFLY - RECONOCIMIENTO WIFI (v1)\n")
            handle.write("=" * 48 + "\n")
            handle.write(format_summary(summary) + "\n")
            handle.write(f"Interfaces: {', '.join(summary.get('interfaces', []))}\n")
            handle.write(f"Fecha: {summary.get('timestamp', '')}\n")
            handle.write("Score de honeypot heurístico; no es un veredicto definitivo.\n")
            handle.write("Data e IV comparten el contador # IV del CSV de airodump-ng.\n\n")
            for index, net in enumerate(networks, start=1):
                handle.write(f"[{index}] {format_network_line(net)}\n")
                handle.write(format_network_detail(net) + "\n\n")

        return session_dir

    def list_sessions(self):
        return SessionManager.list_sessions(self.base_dir)

    def read_report(self, session_name, filename="redes.json"):
        """Lee un archivo de reporte dentro de una sesión concreta."""
        safe_session = os.path.basename(str(session_name))
        safe_filename = os.path.basename(str(filename))
        path = os.path.join(self.base_dir, safe_session, safe_filename)
        return SessionManager.read_file(path)

    # -- helpers ---------------------------------------------------------

    def _new_session(self):
        os.makedirs(self.base_dir, exist_ok=True)
        return SessionManager.create_session(self.base_dir)

    def _run_airodump(self, mon_iface, duration, band):
        prefix = f"/tmp/dragonfly_wifi_audit_{int(time.time())}_{time.monotonic_ns()}"
        cmd = [
            "sudo", "timeout", "-k", "5", f"{int(duration)}s",
            "airodump-ng",
        ]
        band_flag = BAND_FLAGS.get(band)
        if band_flag:
            cmd.extend(["--band", band_flag])
        cmd.extend(["-w", prefix, "--output-format", "csv", mon_iface])

        proc = safe_popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self._lock:
            self._procs.append(proc)
        try:
            proc.wait()
        finally:
            with self._lock:
                if proc in self._procs:
                    self._procs.remove(proc)
        return prefix

    @staticmethod
    def _cleanup_prefix(prefix):
        if not prefix:
            return
        for path in glob.glob(f"{prefix}*"):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass

    @staticmethod
    def _merge_raw_aps(aps):
        """Fusiona APs duplicados usando (BSSID, banda), conservando la mejor señal."""
        merged = {}
        for ap in aps:
            bssid = normalize_mac(ap.get("bssid"))
            if not bssid:
                continue
            band = str(ap.get("band") or channel_to_band(ap.get("channel")))
            key = (bssid, band)
            if key not in merged:
                merged[key] = dict(ap)
                continue

            current = merged[key]
            current_power = current.get("power")
            new_power = ap.get("power")
            if (
                isinstance(new_power, int) and new_power != -1
                and (not isinstance(current_power, int) or current_power == -1 or new_power > current_power)
            ):
                for field in ("power", "channel", "band", "speed", "privacy", "cipher", "auth", "essid"):
                    current[field] = ap.get(field, current.get(field))
            current["beacons"] = max(_to_int(current.get("beacons")), _to_int(ap.get("beacons")))
            current["iv"] = max(_to_int(current.get("iv")), _to_int(ap.get("iv")))
            current["data"] = current["iv"]
            if not current.get("source_iface"):
                current["source_iface"] = ap.get("source_iface", "")
        return list(merged.values())

    @staticmethod
    def _merge_stations(stations):
        """Elimina estaciones duplicadas por (MAC, BSSID) entre dos capturas."""
        merged = {}
        for station in stations:
            station_mac = normalize_mac(station.get("station_mac"))
            if not station_mac:
                continue
            key = (station_mac, normalize_mac(station.get("bssid")))
            if key not in merged:
                merged[key] = dict(station)
            else:
                current = merged[key]
                current["packets"] = max(_to_int(current.get("packets")), _to_int(station.get("packets")))
                current_power = current.get("power")
                new_power = station.get("power")
                if (
                    isinstance(new_power, int) and new_power != -1
                    and (not isinstance(current_power, int) or current_power == -1 or new_power > current_power)
                ):
                    current["power"] = new_power
        return list(merged.values())

    @staticmethod
    def _validate_iface(iface):
        text = str(iface or "")
        if not text or text.startswith("-") or not _IFACE_RE.match(text):
            raise ValueError(f"Interfaz inválida: {iface!r}")

    @staticmethod
    def _validate_duration(duration):
        try:
            value = int(duration)
        except (TypeError, ValueError):
            raise ValueError("La duración debe ser un número entero de segundos.")
        if not 5 <= value <= 120:
            raise ValueError("La duración debe estar entre 5 y 120 segundos.")
        return value

    @staticmethod
    def _normalize_band(band):
        if band is None or str(band).strip().lower() in {"", "auto", "none"}:
            return None
        normalized = str(band).strip().lower()
        if normalized in {"2.4", "2.4ghz", "2.4 ghz", "bg"}:
            return "2.4"
        if normalized in {"5", "5ghz", "5 ghz", "a"}:
            return "5"
        raise ValueError("Banda inválida. Use '2.4', '5' o None/auto.")

    @staticmethod
    def interfaces_share_phy(iface1, iface2):
        """Intenta determinar si dos interfaces pertenecen al mismo phy."""
        try:
            result = safe_run(
                ["iw", "dev"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            output = result.stdout or ""
        except Exception:
            return False

        current_phy = None
        mapping = {}
        for line in output.splitlines():
            phy_match = re.match(r"^\s*phy#(\d+)", line)
            if phy_match:
                current_phy = phy_match.group(1)
                continue
            iface_match = re.match(r"^\s*Interface\s+(\S+)", line)
            if iface_match and current_phy is not None:
                mapping[iface_match.group(1)] = current_phy

        phy1 = mapping.get(iface1)
        phy2 = mapping.get(iface2)
        return bool(phy1 is not None and phy1 == phy2)
