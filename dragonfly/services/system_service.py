"""
dragonfly/services/system_service.py - Servicio de soporte del sistema operativo y hardware.
Gestiona redes Wi-Fi (nmcli), Bluetooth (bluetoothctl), métricas de hardware y perfiles USB OTG.
"""

import os
import re
import subprocess
from dragonfly.core.executor import CommandExecutor
from dragonfly.core.hardware import get_network_interfaces, get_bluetooth_interfaces


class SystemService:
    """
    Gestiona utilidades del sistema operativo, conexiones y configuración de periféricos.
    """

    def __init__(self, executor: CommandExecutor = None):
        self.executor = executor or CommandExecutor()

    # -------------------------------------------------------------
    # GESTIÓN DE REDES WI-FI (CLIENTE NMCLI)
    # -------------------------------------------------------------
    def scan_wifi_networks(self, iface: str):
        """
        Escanea puntos de acceso disponibles para conexión mediante nmcli.
        Retorna una lista de diccionarios [{'ssid': ..., 'security': ..., 'signal': ...}].
        """
        cmd = f"sudo nmcli -t -f SSID,SECURITY,SIGNAL dev wifi list ifname {iface} --rescan yes"
        stdout, stderr, rc = self.executor.run_sync(cmd)
        redes = []
        ssids_vistos = set()
        for linea in stdout.splitlines():
            partes = linea.split(":")
            if partes and partes[0].strip():
                ssid = partes[0].strip()
                if ssid not in ssids_vistos:
                    ssids_vistos.add(ssid)
                    sec = partes[1].strip() if len(partes) > 1 else "Abierta"
                    sig = partes[2].strip() if len(partes) > 2 else ""
                    redes.append({"ssid": ssid, "security": sec, "signal": sig})
        return redes

    def connect_wifi(self, iface: str, ssid: str, password: str = None, on_output=None, on_finish=None):
        """
        Conecta la interfaz Wi-Fi a un punto de acceso mediante NetworkManager.
        """
        if password:
            cmd = f"sudo nmcli dev wifi connect '{ssid}' password '{password}' ifname '{iface}'"
        else:
            cmd = f"sudo nmcli dev wifi connect '{ssid}' ifname '{iface}'"
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    # -------------------------------------------------------------
    # GESTIÓN BLUETOOTH (BLUETOOTHCTL)
    # -------------------------------------------------------------
    def get_bluetooth_adapters(self):
        """Retorna los adaptadores Bluetooth locales."""
        return get_bluetooth_interfaces()

    def scan_bluetooth(self, duration: int = 10):
        """
        Escanea dispositivos Bluetooth cercanos durante el tiempo indicado.
        Retorna lista de tuplas (mac, nombre).
        """
        try:
            subprocess.run(f"sudo bluetoothctl --timeout {duration} scan on", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            salida = subprocess.check_output("sudo bluetoothctl devices", shell=True, text=True)
            dispositivos = []
            for linea in salida.splitlines():
                partes = linea.split(" ")
                if len(partes) >= 3 and partes[0] == "Device":
                    mac = partes[1]
                    nombre = " ".join(partes[2:])
                    dispositivos.append((mac, nombre))
            return dispositivos
        except Exception:
            return []

    def pair_and_connect_bluetooth(self, mac: str, on_output=None) -> str:
        """
        Empareja y establece conexión con un dispositivo Bluetooth por su dirección MAC.
        """
        try:
            if on_output:
                on_output(f"[*] Emparejando con {mac}...")
            pair = subprocess.run(f"sudo bluetoothctl -- pair {mac}", shell=True, capture_output=True, text=True, timeout=30)
            if "Pairing successful" in pair.stdout or "Paired: yes" in pair.stdout:
                if on_output:
                    on_output("[+] Emparejamiento exitoso. Conectando...")
                conn = subprocess.run(f"sudo bluetoothctl -- connect {mac}", shell=True, capture_output=True, text=True, timeout=30)
                if "Connection successful" in conn.stdout or "Connected: yes" in conn.stdout:
                    return "ÉXITO: Dispositivo conectado."
                return f"ERROR: Fallo de conexión ({conn.stderr.strip()})"
            return f"ERROR: Fallo en emparejamiento ({pair.stderr.strip()})"
        except Exception as e:
            return f"EXCEPCIÓN: {e}"

    # -------------------------------------------------------------
    # MÉTRICAS Y CONTROL DE ENERGÍA
    # -------------------------------------------------------------
    def get_system_metrics(self, metric_type: str, on_output=None, on_finish=None):
        """
        Ejecuta comandos de telemetría del sistema operativo:
        'storage', 'memory', 'cpu', 'connections'.
        """
        comandos = {
            "storage": "df -h",
            "memory": "free -h",
            "cpu": "ps aux --sort=-%cpu | head -n 15",
            "connections": "ss -tulnp"
        }
        cmd = comandos.get(metric_type, "uptime")
        return self.executor.run_async(cmd, on_output=on_output, on_finish=on_finish)

    def power_off(self):
        """Apaga el sistema de forma segura."""
        subprocess.run("sudo poweroff", shell=True)

    def reboot(self):
        """Reinicia el sistema de forma segura."""
        subprocess.run("sudo reboot", shell=True)

    # -------------------------------------------------------------
    # CAMBIO DINÁMICO DE PERFILES USB OTG (RASPBERRY PI ZERO)
    # -------------------------------------------------------------
    def configure_usb_gadget_profile(self, modo: str, on_output=None) -> bool:
        """
        Reconfigura el puerto OTG de la Raspberry Pi Zero (Host, Rubber Ducky HID, RNDIS, ECM).
        Genera el script libcomposite y actualiza config.txt.
        """
        modo = modo.lower()
        if modo not in ["host", "gadget", "rndis", "ecm"]:
            if on_output:
                on_output(f"[!] Perfil no soportado: {modo}")
            return False

        if on_output:
            on_output(f"[*] Configurando perfil USB: {modo.upper()}...")

        cfg = "/boot/firmware/config.txt" if os.path.exists("/boot/firmware/config.txt") else "/boot/config.txt"
        gadget_script = "/usr/local/bin/usb_gadget.sh"
        service_path = "/etc/systemd/system/usb_gadget.service"

        # 1. Asegurar servicio systemd
        if not os.path.exists(service_path):
            servicio_systemd = """[Unit]
Description=USB HID/Net Gadget Initialization
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/bin/bash /usr/local/bin/usb_gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
"""
            subprocess.run(f"sudo sh -c 'echo \"{servicio_systemd}\" > {service_path}'", shell=True)
            subprocess.run("sudo systemctl daemon-reload", shell=True)

        # 2. Configurar overlay en config.txt
        subprocess.run(f"sudo sed -i '/dtoverlay=dwc2/d' {cfg}", shell=True)

        if modo == "host":
            subprocess.run(f"sudo sh -c 'echo \"dtoverlay=dwc2,dr_mode=host\" >> {cfg}'", shell=True)
            subprocess.run("sudo systemctl disable usb_gadget.service", shell=True, stderr=subprocess.DEVNULL)
            if on_output:
                on_output("[+] Modo Host puro configurado (Antena Wi-Fi/Periféricos externos).")
        else:
            subprocess.run(f"sudo sh -c 'echo \"dtoverlay=dwc2,dr_mode=peripheral\" >> {cfg}'", shell=True)
            subprocess.run("sudo systemctl enable usb_gadget.service", shell=True, stderr=subprocess.DEVNULL)

            # Generación de script libcomposite
            sh_script = """#!/bin/bash
modprobe libcomposite
cd /sys/kernel/config/usb_gadget/

for dir in /sys/kernel/config/usb_gadget/*; do
    if [ -d "$dir" ]; then
        echo "" > "$dir/UDC" 2>/dev/null
        sleep 0.2
        rm -rf "$dir" 2>/dev/null
    fi
done

if [ -d dragonfly ]; then
    echo "" > dragonfly/UDC 2>/dev/null
    sleep 0.2
    rm -rf dragonfly 2>/dev/null
fi

mkdir -p dragonfly
cd dragonfly
"""
            if modo == "rndis":
                sh_script += "echo 0x0525 > idVendor\necho 0xa4a2 > idProduct\n"
            elif modo == "ecm":
                sh_script += "echo 0x0525 > idVendor\necho 0xa4a1 > idProduct\n"
            else:  # gadget (Rubber Ducky)
                sh_script += "echo 0x1d6b > idVendor\necho 0x0104 > idProduct\n"

            sh_script += """echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "DragonFly" > strings/0x409/manufacturer
"""
            if modo == "gadget":
                sh_script += 'echo "DragonFly HID (Keyboard)" > strings/0x409/product\n'
            elif modo == "rndis":
                sh_script += 'echo "DragonFly RNDIS Ethernet" > strings/0x409/product\n'
            elif modo == "ecm":
                sh_script += 'echo "DragonFly CDC ECM Ethernet" > strings/0x409/product\n'

            sh_script += """mkdir -p configs/c.1/strings/0x409
echo "Config 1" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower
"""
            if modo == "gadget":
                sh_script += """mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
printf "\\\\x05\\\\x01\\\\x09\\\\x06\\\\xa1\\\\x01\\\\x05\\\\x07\\\\x19\\\\xe0\\\\x29\\\\xe7\\\\x15\\\\x00\\\\x25\\\\x01\\\\x75\\\\x01\\\\x95\\\\x08\\\\x81\\\\x02\\\\x95\\\\x01\\\\x75\\\\x08\\\\x81\\\\x03\\\\x95\\\\x05\\\\x75\\\\x01\\\\x05\\\\x08\\\\x19\\\\x01\\\\x29\\\\x05\\\\x91\\\\x02\\\\x95\\\\x01\\\\x75\\\\x03\\\\x91\\\\x03\\\\x95\\\\x06\\\\x75\\\\x08\\\\x15\\\\x00\\\\x25\\\\x65\\\\x05\\\\x07\\\\x19\\\\x00\\\\x29\\\\x65\\\\x81\\\\x00\\\\xc0" > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/
"""
            elif modo == "rndis":
                sh_script += """mkdir -p functions/rndis.usb0
echo 1 > os_desc/use
echo 0xcd > os_desc/b_vendor_code
echo MSFT100 > os_desc/qw_sign
mkdir -p functions/rndis.usb0/os_desc/interface.rndis
echo RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
ln -s functions/rndis.usb0 configs/c.1/
ln -s configs/c.1 os_desc
"""
            elif modo == "ecm":
                sh_script += """mkdir -p functions/ecm.usb0
HOST_MAC=$(printf '02:%02x:%02x:%02x:%02x:%02x' $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)))
echo "$HOST_MAC" > functions/ecm.usb0/host_addr
echo "02:11:22:33:44:56" > functions/ecm.usb0/dev_addr
ln -s functions/ecm.usb0 configs/c.1/
"""
            sh_script += "ls /sys/class/udc > UDC\nsleep 2\n"

            with open("/tmp/usb_gadget.sh", "w") as f:
                f.write(sh_script)

            subprocess.run(f"sudo mv /tmp/usb_gadget.sh {gadget_script}", shell=True)
            subprocess.run(f"sudo chmod +x {gadget_script}", shell=True)

            if on_output:
                on_output(f"[+] Perfil {modo.upper()} generado correctamente.")

        return True
