"""
dragonfly/core/hardware.py - Utilidades de detección de hardware y red.
Identifica adaptadores de red, módulos inalámbricos, bluetooth, puertos serie y perfil SBC.
"""

import os
import glob
import socket
import subprocess


def get_network_interfaces():
    """
    Retorna la lista ordenada de interfaces de red activas en el sistema excluyendo loopback.
    """
    try:
        return sorted([i for i in os.listdir('/sys/class/net/') if i != "lo"])
    except Exception:
        return ["wlan0", "eth0"]


def get_wifi_interfaces():
    """
    Retorna las interfaces de red que son exclusivamente adaptadores inalámbricos.
    """
    wifi_ifaces = []
    for iface in get_network_interfaces():
        if os.path.exists(f"/sys/class/net/{iface}/wireless") or os.path.exists(f"/sys/class/net/{iface}/phy80211"):
            wifi_ifaces.append(iface)
    return wifi_ifaces if wifi_ifaces else [i for i in get_network_interfaces() if i.startswith("wl")]


def get_local_ip():
    """
    Detecta automáticamente la IP local activa en la red. Retorna 127.0.0.1 si no hay conexión.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_bluetooth_interfaces():
    """
    Retorna las interfaces Bluetooth detectadas en el sistema (ej. ['hci0']).
    """
    try:
        salida = subprocess.check_output("hciconfig", shell=True, text=True, stderr=subprocess.DEVNULL)
        return [linea.split(":")[0].strip() for linea in salida.splitlines() if linea.startswith("hci")]
    except Exception:
        # Fallback a sysfs
        try:
            return sorted(os.listdir('/sys/class/bluetooth/'))
        except Exception:
            return []


def detect_serial_port(candidate_patterns=None):
    """
    Autodetecta el puerto serie conectado a adaptadores USB-Serie o ESP32.
    """
    if candidate_patterns is None:
        candidate_patterns = ['/dev/ttyACM*', '/dev/ttyUSB*']

    for pattern in candidate_patterns:
        ports = glob.glob(pattern)
        if ports:
            return ports[0]
    return None


def detect_gadget_interface():
    """
    Busca la interfaz de red que actúa como gadget USB (RNDIS/ECM).
    Verifica que sea Ethernet (tipo 1) y pertenezca al subsistema gadget.
    """
    try:
        for iface in os.listdir('/sys/class/net/'):
            if iface == 'lo':
                continue
            type_path = f'/sys/class/net/{iface}/type'
            if not os.path.exists(type_path):
                continue
            with open(type_path) as f:
                iface_type = f.read().strip()
            if iface_type != '1':
                continue

            device_path = f'/sys/class/net/{iface}/device'
            if os.path.exists(device_path):
                try:
                    link = os.readlink(device_path)
                    if 'gadget' in link:
                        return iface
                except OSError:
                    pass

            if iface.startswith('usb') or iface.startswith('enx'):
                return iface
    except Exception:
        pass

    for candidate in ['usb0', 'enx']:
        if os.path.exists(f'/sys/class/net/{candidate}'):
            return candidate
    return 'usb0'


def is_raspberry_pi():
    """
    Verifica si el entorno de ejecución actual es una Raspberry Pi.
    """
    model_path = "/proc/device-tree/model"
    if os.path.exists(model_path):
        try:
            with open(model_path, "r") as f:
                return "Raspberry Pi" in f.read()
        except Exception:
            pass
    return False
