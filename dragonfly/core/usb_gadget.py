"""
dragonfly/core/usb_gadget.py - Motor de perfiles USB compuestos (configfs) para Raspberry Pi Zero.

Construye, destruye y conmuta EN CALIENTE las funciones del gadget USB (teclado HID,
red ECM/RNDIS o combinaciones) sin reiniciar el sistema, siempre que el puerto OTG esté
en modo periférico. Alternar entre host y periférico sí requiere reinicio, porque
``dr_mode`` se define en /boot/firmware/config.txt al arrancar.

CLI de administración:

    python3 -m dragonfly.core.usb_gadget status            # estado actual
    python3 -m dragonfly.core.usb_gadget list              # perfiles disponibles
    python3 -m dragonfly.core.usb_gadget apply <perfil>    # conmutación en caliente
    python3 -m dragonfly.core.usb_gadget teardown          # retira el gadget
    python3 -m dragonfly.core.usb_gadget dr-mode host|peripheral
    python3 -m dragonfly.core.usb_gadget enable|disable    # servicio de arranque
    python3 -m dragonfly.core.usb_gadget persist <perfil>  # perfil persistente
    python3 -m dragonfly.core.usb_gadget install-assets    # script + unidad systemd
    python3 -m dragonfly.core.usb_gadget boot              # reconstrucción al arranque
"""

import contextlib
import glob
import os
import random
import subprocess
import sys
import time

from dragonfly.core.subprocess_utils import safe_run

# -------------------------------------------------------------
# RUTAS Y CONSTANTES
# -------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GADGET_NAME = "dragonfly"
CONFIGFS_ROOT = "/sys/kernel/config"
GADGET_DIR = os.path.join(CONFIGFS_ROOT, "usb_gadget", GADGET_NAME)
HIDG_DEVICE = "/dev/hidg0"

BOOT_SCRIPT = "/usr/local/bin/usb_gadget.sh"
SERVICE_NAME = "usb_gadget.service"
SERVICE_PATH = "/etc/systemd/system/usb_gadget.service"
PROFILE_STATE_DIR = "/etc/dragonfly"
PROFILE_STATE_FILE = os.path.join(PROFILE_STATE_DIR, "gadget_profile")

DEFAULT_PROFILE = "hid"

# Descriptor de reporte HID de teclado estándar (45 bytes, report length 8).
HID_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01,
    0x75, 0x08, 0x81, 0x03, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65,
    0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xC0,
])

# Perfiles disponibles. Cada PID distinto evita que Windows cachee el driver
# de un conjunto de funciones y lo aplique a otro tras una conmutación.
PROFILES = {
    "hid": {
        "id_vendor": 0x1D6B,
        "id_product": 0x0104,
        "product": "HID (Keyboard)",
        "functions": ("hid",),
    },
    "ecm": {
        "id_vendor": 0x0525,
        "id_product": 0xA4A1,
        "product": "CDC ECM Ethernet",
        "functions": ("ecm",),
    },
    "rndis": {
        "id_vendor": 0x0525,
        "id_product": 0xA4A2,
        "product": "RNDIS Ethernet",
        "functions": ("rndis",),
    },
    "hid_ecm": {
        "id_vendor": 0x0525,
        "id_product": 0xA4A3,
        "product": "HID + CDC ECM Gadget",
        "functions": ("hid", "ecm"),
    },
    "hid_rndis": {
        "id_vendor": 0x0525,
        "id_product": 0xA4A4,
        "product": "HID + RNDIS Gadget",
        "functions": ("hid", "rndis"),
    },
}

# Nombres legibles para la interfaz gráfica (orden de presentación incluido).
PROFILE_LABELS = {
    "hid": "Rubber Ducky (HID)",
    "rndis": "Poison Windows (RNDIS)",
    "ecm": "Poison Mac/Linux (ECM)",
    "hid_rndis": "Ducky + Poison Windows (HID+RNDIS)",
    "hid_ecm": "Ducky + Poison Linux (HID+ECM)",
}
PROFILE_ORDER = ["hid", "rndis", "ecm", "hid_rndis", "hid_ecm"]

# Alias tolerantes para llamadas heredadas o desde CLI.
ALIASES = {
    "gadget": "hid",
    "ducky": "hid",
    "keyboard": "hid",
    "teclado": "hid",
    "windows": "rndis",
    "win": "rndis",
    "linux": "ecm",
    "mac": "ecm",
    "hid+ecm": "hid_ecm",
    "hid-ecm": "hid_ecm",
    "hid+rndis": "hid_rndis",
    "hid-rndis": "hid_rndis",
}


def _logger(log):
    return log if callable(log) else (lambda _msg: None)


def normalize_profile(name) -> str:
    """Normaliza el nombre de un perfil ('gadget' -> 'hid', minúsculas, sin espacios)."""
    key = str(name or "").strip().lower()
    return ALIASES.get(key, key)


# -------------------------------------------------------------
# ESCRITURA / LIMPIEZA DE CONFIGFS
# -------------------------------------------------------------
def _write_bytes(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


def _write_str(path: str, value):
    _write_bytes(path, str(value).encode())


def _rmdir(path: str, retries: int = 5, delay: float = 0.3) -> bool:
    """rmdir tolerante a EBUSY/ENOTEMPTY transitorios de configfs."""
    for intento in range(retries):
        try:
            os.rmdir(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(delay)
    return not os.path.exists(path)


# -------------------------------------------------------------
# ESTADO DEL SISTEMA
# -------------------------------------------------------------
def configfs_available() -> bool:
    """
    True si configfs está montado en /sys/kernel/config.

    Nota: el subdirectorio 'usb_gadget' solo aparece cuando libcomposite está
    cargado, por lo que se verifica el montaje real en /proc/mounts.
    """
    if not os.path.isdir(CONFIGFS_ROOT):
        return False
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for linea in f:
                partes = linea.split()
                if len(partes) >= 3 and partes[1] == CONFIGFS_ROOT and partes[2] == "configfs":
                    return True
    except OSError:
        pass
    return False


def udc_controllers():
    """Controladores UDC registrados. Solo existen en modo periférico."""
    return sorted(glob.glob("/sys/class/udc/*"))


def is_peripheral_mode() -> bool:
    """True si el puerto OTG está en modo periférico (gadget) y puede emular funciones."""
    return bool(udc_controllers())


def current_profile():
    """Perfil activo deducido de las funciones presentes en configfs."""
    if not os.path.isdir(GADGET_DIR):
        return None
    funciones = set()
    for entry in glob.glob(os.path.join(GADGET_DIR, "functions", "*")):
        nombre = os.path.basename(entry)
        if nombre.startswith("hid"):
            funciones.add("hid")
        elif nombre.startswith("ecm"):
            funciones.add("ecm")
        elif nombre.startswith("rndis"):
            funciones.add("rndis")
    if not funciones:
        return None
    for key, meta in PROFILES.items():
        if set(meta["functions"]) == funciones:
            return key
    return "desconocido"


def gadget_net_interfaces():
    """Interfaces de red creadas por el gadget (usb0 / enx*)."""
    interfaces = []
    try:
        for iface in sorted(os.listdir("/sys/class/net")):
            if iface == "lo":
                continue
            if iface.startswith("usb") or iface.startswith("enx"):
                interfaces.append(iface)
    except OSError:
        pass

    # Refuerzo: cualquier netdev cuyo enlace de dispositivo apunte al gadget.
    try:
        for iface in sorted(os.listdir("/sys/class/net")):
            if iface in interfaces or iface == "lo":
                continue
            enlace = os.path.realpath(f"/sys/class/net/{iface}/device")
            if "gadget" in enlace:
                interfaces.append(iface)
    except OSError:
        pass
    return interfaces


def service_enabled() -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "is-enabled", SERVICE_NAME],
            capture_output=True, text=True, timeout=5,
            stdin=subprocess.DEVNULL,
        )
        return proc.stdout.strip() == "enabled"
    except Exception:
        return False


def status() -> dict:
    """Estado completo del gadget para diagnóstico y para la interfaz gráfica."""
    return {
        "configfs": configfs_available(),
        "peripheral": is_peripheral_mode(),
        "udc": [os.path.basename(u) for u in udc_controllers()],
        "profile": current_profile(),
        "persisted": load_persisted_profile(),
        "hidg": os.path.exists(HIDG_DEVICE),
        "net_ifaces": gadget_net_interfaces(),
        "service_enabled": service_enabled(),
        "boot_script": os.path.exists(BOOT_SCRIPT),
    }


# -------------------------------------------------------------
# PERSISTENCIA DEL PERFIL DE ARRANQUE
# -------------------------------------------------------------
def load_persisted_profile() -> str:
    try:
        with open(PROFILE_STATE_FILE, "r", encoding="utf-8") as f:
            key = normalize_profile(f.read())
        if key in PROFILES:
            return key
    except OSError:
        pass
    return DEFAULT_PROFILE


def persist_profile(profile: str, log=None) -> bool:
    key = normalize_profile(profile)
    if key not in PROFILES:
        _logger(log)(f"[!] Perfil desconocido: {profile}")
        return False
    try:
        os.makedirs(PROFILE_STATE_DIR, exist_ok=True)
        _write_str(PROFILE_STATE_FILE, key + "\n")
        _logger(log)(f"[+] Perfil '{key}' guardado para el próximo arranque.")
        return True
    except OSError as exc:
        _logger(log)(f"[!] No se pudo persistir el perfil: {exc}")
        return False


# -------------------------------------------------------------
# CONSTRUCCIÓN DEL GADGET
# -------------------------------------------------------------
def _ensure_modules(log=None):
    """Carga los módulos necesarios. modprobe es idempotente."""
    for modulo in ("libcomposite", "usb_f_hid", "usb_f_ecm", "usb_f_rndis", "u_ether"):
        try:
            safe_run(["modprobe", modulo], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            _logger(log)(f"[!] Aviso: no se pudo cargar el módulo {modulo}")


def _random_mac() -> str:
    return "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))


def _create_hid_function(log=None):
    path = os.path.join(GADGET_DIR, "functions", "hid.usb0")
    os.mkdir(path)
    _write_str(os.path.join(path, "protocol"), "1")
    _write_str(os.path.join(path, "subclass"), "1")
    _write_str(os.path.join(path, "report_length"), "8")
    _write_bytes(os.path.join(path, "report_desc"), HID_REPORT_DESCRIPTOR)
    return path


def _create_ecm_function(log=None):
    path = os.path.join(GADGET_DIR, "functions", "ecm.usb0")
    os.mkdir(path)
    # MAC del host aleatoria por sesión: evita que NetworkManager ignore la interfaz.
    _write_str(os.path.join(path, "host_addr"), _random_mac())
    _write_str(os.path.join(path, "dev_addr"), "02:11:22:33:44:56")
    return path


def _create_rndis_function(log=None):
    path = os.path.join(GADGET_DIR, "functions", "rndis.usb0")
    os.mkdir(path)
    return path


def _configure_rndis_os_desc(log=None):
    """Descriptores Microsoft OS para que Windows asocie el driver RNDIS sin firmar."""
    os_desc = os.path.join(GADGET_DIR, "os_desc")
    _write_str(os.path.join(os_desc, "use"), "1")
    _write_str(os.path.join(os_desc, "b_vendor_code"), "0xcd")
    _write_str(os.path.join(os_desc, "qw_sign"), "MSFT100")

    interfaz = os.path.join(GADGET_DIR, "functions", "rndis.usb0", "os_desc", "interface.rndis")
    os.makedirs(interfaz, exist_ok=True)
    _write_str(os.path.join(interfaz, "compatible_id"), "RNDIS")
    _write_str(os.path.join(interfaz, "sub_compatible_id"), "5162001")


@contextlib.contextmanager
def _chdir(path):
    """Cambio temporal de directorio (configfs resuelve symlinks relativos al cwd)."""
    previo = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previo)


def _link_function(nombre_funcion: str):
    """
    Enlaza una función a la configuración c.1.

    Importante: configfs resuelve el destino del symlink con kern_path() usando el
    cwd del proceso, por lo que el enlace debe crearse estando dentro del gadget
    (equivalente al clásico `ln -s functions/hid.usb0 configs/c.1/`).
    """
    with _chdir(GADGET_DIR):
        os.symlink(
            os.path.join("functions", nombre_funcion),
            os.path.join("configs", "c.1", nombre_funcion),
        )


def _link_os_desc():
    """
    Publica la configuración que transporta los descriptores Microsoft OS del RNDIS.

    En kernels modernos el grupo 'os_desc' ya existe dentro del gadget y no se puede
    eliminar (EPERM); el enlace correcto se crea DENTRO del grupo:
    ``os_desc/c.1 -> configs/c.1`` (equivalente a `cd gadget && ln -s configs/c.1 os_desc/`).
    """
    with _chdir(GADGET_DIR):
        os.symlink(os.path.join("configs", "c.1"), os.path.join("os_desc", "c.1"))


def _bind_udc(log=None, retries: int = 3):
    """Activa el gadget en el primer controlador UDC disponible."""
    udcs = udc_controllers()
    if not udcs:
        raise RuntimeError(
            "No hay controlador UDC: el puerto OTG está en modo host. "
            "Se requiere dr_mode=peripheral (solo se cambia con reinicio)."
        )

    ultimo_error = None
    for intento in range(retries):
        try:
            _write_str(os.path.join(GADGET_DIR, "UDC"), os.path.basename(udcs[0]))
            return
        except OSError as exc:
            ultimo_error = exc
            time.sleep(1.0)
    raise RuntimeError(f"No se pudo enlazar el gadget al UDC {udcs[0]}: {ultimo_error}")


def _bring_up_network_interfaces(log=None, timeout: float = 5.0) -> list:
    """
    Levanta las interfaces de red del gadget INMEDIATAMENTE tras enlazar el UDC.

    Crítico en Linux: si ``usb0`` se queda abajo, el host ve el carrier caer a
    los pocos segundos y NetworkManager cancela la transacción DHCP. Levantar
    el enlace más tarde (por ejemplo, al pulsar "Lanzar Ataque Poison") vuelve
    a generar un ciclo carrier-off/on que en dwc2 deja el endpoint OUT con
    EPENA+EPDIS: el host transmite pero los URBs nunca completan y aparecen
    NETDEV WATCHDOG. Por eso el enlace se sube aquí, antes de que el host
    retire la interfaz y sin ciclos down/up posteriores.
    """
    log = _logger(log)
    limite = time.monotonic() + timeout
    interfaces = []

    while time.monotonic() < limite:
        interfaces = gadget_net_interfaces()
        if interfaces:
            break
        time.sleep(0.1)

    if not interfaces:
        log("[!] El perfil no creó interfaces de red del gadget.")
        return []

    activas = []
    for iface in interfaces:
        try:
            safe_run(
                ["ip", "link", "set", iface, "up"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            activas.append(iface)
        except Exception:
            pass

    if activas:
        log(f"[+] Enlace de red del gadget activo: {', '.join(activas)}.")
    else:
        log("[!] No se pudieron levantar las interfaces de red del gadget.")
    return activas


def build(profile: str, log=None) -> bool:
    """Crea el gadget completo para el perfil indicado y lo enlaza al UDC."""
    log = _logger(log)
    key = normalize_profile(profile)
    if key not in PROFILES:
        log(f"[!] Perfil desconocido: {profile}")
        return False
    if not configfs_available():
        log("[!] configfs no está disponible en /sys/kernel/config.")
        return False

    meta = PROFILES[key]
    log(f"[*] Construyendo gadget USB compuesto: {key} ({', '.join(meta['functions'])})...")
    _ensure_modules(log)

    if not os.path.isdir(os.path.join(CONFIGFS_ROOT, "usb_gadget")):
        log("[!] El subsistema usb_gadget de configfs no está disponible (¿libcomposite cargado?).")
        return False

    os.mkdir(GADGET_DIR)
    _write_str(os.path.join(GADGET_DIR, "idVendor"), "0x%04x" % meta["id_vendor"])
    _write_str(os.path.join(GADGET_DIR, "idProduct"), "0x%04x" % meta["id_product"])
    _write_str(os.path.join(GADGET_DIR, "bcdDevice"), "0x0100")
    _write_str(os.path.join(GADGET_DIR, "bcdUSB"), "0x0200")

    strings = os.path.join(GADGET_DIR, "strings", "0x409")
    os.makedirs(strings)
    _write_str(os.path.join(strings, "serialnumber"), "fedcba9876543210")
    _write_str(os.path.join(strings, "manufacturer"), "DragonFly")
    _write_str(os.path.join(strings, "product"), meta["product"])

    config = os.path.join(GADGET_DIR, "configs", "c.1")
    os.makedirs(os.path.join(config, "strings", "0x409"))
    _write_str(os.path.join(config, "strings", "0x409", "configuration"), "DragonFly config")
    _write_str(os.path.join(config, "MaxPower"), "250")

    for funcion in meta["functions"]:
        if funcion == "hid":
            _create_hid_function(log)
        elif funcion == "ecm":
            _create_ecm_function(log)
        elif funcion == "rndis":
            _create_rndis_function(log)

    # Los descriptores OS del RNDIS deben configurarse antes del symlink de la función.
    if "rndis" in meta["functions"]:
        _configure_rndis_os_desc(log)

    for funcion in meta["functions"]:
        _link_function({"hid": "hid.usb0", "ecm": "ecm.usb0", "rndis": "rndis.usb0"}[funcion])

    if "rndis" in meta["functions"]:
        _link_os_desc()

    # Pausa de asentamiento antes de activar el UDC (evita fallos intermitentes de enumeración).
    time.sleep(2.0)
    _bind_udc(log)
    time.sleep(0.4)

    # Los perfiles con red deben subir su interfaz ya: el host Linux solo
    # inicia (y mantiene) el DHCP si el carrier no desaparece poco después.
    if {"ecm", "rndis"} & set(meta["functions"]):
        _bring_up_network_interfaces(log)

    log(f"[+] Gadget '{key}' activo en {os.path.basename(udc_controllers()[0])}.")
    return True


def teardown(log=None) -> bool:
    """
    Desvincula el gadget del UDC y elimina su árbol de configfs.

    Mecánica verificada en kernel 6.18 / Pi Zero 2 W:
      - Los grupos por defecto del kernel (functions, configs, strings, os_desc,
        webusb) NO se pueden eliminar individualmente (EPERM); desaparecen al
        eliminar el directorio raíz del gadget.
      - Una función no se puede rmdir mientras exista su symlink en la
        configuración (EBUSY): primero se eliminan los enlaces.
    """
    log = _logger(log)
    if not os.path.isdir(GADGET_DIR):
        return True

    # 1. Desvincular del UDC para que el kernel libere las funciones.
    udc = os.path.join(GADGET_DIR, "UDC")
    if os.path.exists(udc):
        try:
            _write_str(udc, "")
        except OSError:
            pass
    time.sleep(0.5)

    # 2. Eliminar enlaces: funciones -> config, config -> os_desc.
    for enlace in glob.glob(os.path.join(GADGET_DIR, "configs", "*", "*")):
        if os.path.islink(enlace):
            try:
                os.unlink(enlace)
            except OSError:
                pass
    for enlace in glob.glob(os.path.join(GADGET_DIR, "os_desc", "*")):
        if os.path.islink(enlace):
            try:
                os.unlink(enlace)
            except OSError:
                pass
    os_desc = os.path.join(GADGET_DIR, "os_desc")
    if os.path.islink(os_desc):
        # Variante clásica (kernels antiguos): os_desc era un symlink al config.
        try:
            os.unlink(os_desc)
        except OSError:
            pass

    # 3. Configuraciones (su grupo por defecto 'strings' se va con el rmdir).
    for config in glob.glob(os.path.join(GADGET_DIR, "configs", "*")):
        if not os.path.isdir(config):
            continue
        for sub in glob.glob(os.path.join(config, "strings", "*")):
            _rmdir(sub)
        _rmdir(config)

    # 4. Funciones, ya sin referencias desde la configuración.
    for funcion in glob.glob(os.path.join(GADGET_DIR, "functions", "*")):
        _rmdir(funcion)

    # 5. Strings del propio gadget.
    for sub in glob.glob(os.path.join(GADGET_DIR, "strings", "*")):
        _rmdir(sub)

    # 6. Directorio raíz: arrastra los grupos por defecto del kernel.
    _rmdir(GADGET_DIR, retries=10, delay=0.5)
    if os.path.isdir(GADGET_DIR):
        log("[!] No se pudo eliminar por completo el gadget anterior.")
        return False
    return True


def apply(profile: str, log=None) -> bool:
    """
    Conmutación en caliente: destruye el gadget actual y construye el del perfil pedido.
    No requiere reinicio mientras el OTG esté en modo periférico.
    """
    log = _logger(log)
    key = normalize_profile(profile)
    if key not in PROFILES:
        log(f"[!] Perfil desconocido: {profile}")
        return False
    if not is_peripheral_mode():
        log("[!] El puerto OTG no está en modo periférico (¿modo host?). Se requiere reinicio.")
        return False

    try:
        teardown(log)
        return build(key, log)
    except Exception as exc:
        log(f"[!] Error aplicando el perfil '{key}': {exc}")
        try:
            teardown(log)
        except Exception:
            pass
        return False


# -------------------------------------------------------------
# MODO HOST / PERIFÉRICO Y SERVICIO DE ARRANQUE
# -------------------------------------------------------------
def _config_txt_path() -> str:
    for candidato in ("/boot/firmware/config.txt", "/boot/config.txt"):
        if os.path.exists(candidato):
            return candidato
    return "/boot/firmware/config.txt"


def set_dr_mode(mode: str, log=None) -> bool:
    """
    Fija dr_mode (host|peripheral) en config.txt. El cambio surte efecto al reiniciar.
    Realiza una copia de seguridad única del archivo original.
    """
    log = _logger(log)
    mode = str(mode).strip().lower()
    if mode not in ("host", "peripheral"):
        log(f"[!] dr_mode inválido: {mode}")
        return False

    cfg = _config_txt_path()
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            lineas = f.read().splitlines()
    except OSError as exc:
        log(f"[!] No se pudo leer {cfg}: {exc}")
        return False

    backup = cfg + ".dragonfly.bak"
    if not os.path.exists(backup):
        try:
            with open(backup, "w", encoding="utf-8") as f:
                f.write("\n".join(lineas) + "\n")
        except OSError:
            pass

    filtradas = [linea for linea in lineas if not linea.strip().startswith("dtoverlay=dwc2")]
    if filtradas and filtradas[-1].strip():
        filtradas.append("")
    filtradas.append(f"dtoverlay=dwc2,dr_mode={mode}")

    try:
        with open(cfg, "w", encoding="utf-8") as f:
            f.write("\n".join(filtradas) + "\n")
    except OSError as exc:
        log(f"[!] No se pudo escribir {cfg}: {exc}")
        return False

    log(f"[+] config.txt actualizado: dtoverlay=dwc2,dr_mode={mode} (efectivo tras reiniciar).")
    return True


def _write_if_changed(path: str, content: str, mode=None) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == content:
                return False
    except OSError:
        pass

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if mode is not None:
        os.chmod(path, mode)
    return True


def install_boot_assets(log=None) -> dict:
    """
    Genera/actualiza el script de arranque y la unidad systemd que reconstruyen
    el perfil persistido al bootear. Idempotente: solo escribe si hay cambios.
    """
    log = _logger(log)
    script = (
        "#!/bin/bash\n"
        "# DragonFly System - Construccion del gadget USB al arranque (generado automaticamente)\n"
        "set -u\n"
        f'cd "{PROJECT_ROOT}" || exit 1\n'
        "exec /usr/bin/python3 -m dragonfly.core.usb_gadget boot\n"
    )
    unidad = (
        "[Unit]\n"
        "Description=DragonFly USB Gadget (perfil persistente)\n"
        "After=systemd-modules-load.service\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/bin/bash " + BOOT_SCRIPT + "\n"
        "RemainAfterExit=yes\n"
        "\n"
        "[Install]\n"
        "WantedBy=sysinit.target\n"
    )

    cambios = {
        "script": _write_if_changed(BOOT_SCRIPT, script, mode=0o755),
        "unit": _write_if_changed(SERVICE_PATH, unidad, mode=0o644),
    }
    if cambios["unit"]:
        safe_run(["systemctl", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if any(cambios.values()):
        log("[+] Activos de arranque del gadget instalados/actualizados (/usr/local/bin/usb_gadget.sh + usb_gadget.service).")
    return cambios


def enable_service(log=None) -> bool:
    _logger(log)("[*] Habilitando reconstrucción del gadget al arranque...")
    proc = safe_run(["systemctl", "enable", SERVICE_NAME], capture_output=True, text=True)
    return proc.returncode == 0


def disable_service(log=None) -> bool:
    _logger(log)("[*] Deshabilitando reconstrucción del gadget al arranque...")
    proc = safe_run(["systemctl", "disable", SERVICE_NAME], capture_output=True, text=True)
    return proc.returncode == 0


# -------------------------------------------------------------
# ARRANQUE (systemd oneshot)
# -------------------------------------------------------------
def boot(log=None) -> bool:
    """
    Punto de entrada del servicio systemd: espera a que configfs y el UDC estén
    listos y construye el perfil persistido.
    """
    log = _logger(log)
    for _ in range(30):
        if configfs_available() and udc_controllers():
            break
        time.sleep(1.0)
    else:
        log("[!] configfs/UDC no disponibles: puerto OTG en modo host. Nada que construir.")
        return False

    key = load_persisted_profile()
    log(f"[*] Arranque: reconstruyendo perfil USB persistido '{key}'...")
    try:
        # Limpieza defensiva: puede haber restos de un servicio reiniciado en
        # caliente o de un arranque anterior interrumpido.
        teardown(log)
        return build(key, log)
    except Exception as exc:
        log(f"[!] Fallo construyendo el gadget de arranque: {exc}")
        return False


# -------------------------------------------------------------
# CLI
# -------------------------------------------------------------
def _print_status():
    st = status()
    print("=== DragonFly USB Gadget ===")
    print(f"  configfs disponible : {st['configfs']}")
    print(f"  modo periférico     : {st['peripheral']}  (UDC: {', '.join(st['udc']) or 'ninguno'})")
    print(f"  perfil activo       : {st['profile'] or 'ninguno'}")
    print(f"  perfil persistente  : {st['persisted']}")
    print(f"  /dev/hidg0          : {st['hidg']}")
    print(f"  interfaces de red   : {', '.join(st['net_ifaces']) or 'ninguna'}")
    print(f"  servicio habilitado : {st['service_enabled']}")
    print(f"  script de arranque  : {st['boot_script']}")


def _main(argv):
    cmd = argv[0] if argv else "status"

    if cmd == "status":
        _print_status()
        return 0
    if cmd == "list":
        for key in PROFILE_ORDER:
            print(f"  {key:10s} - {PROFILE_LABELS.get(key, key)}")
        return 0
    if cmd == "apply":
        if len(argv) < 2:
            print("Uso: apply <perfil>")
            return 2
        return 0 if apply(argv[1], log=print) else 1
    if cmd == "teardown":
        return 0 if teardown(log=print) else 1
    if cmd == "dr-mode":
        if len(argv) < 2:
            print("Uso: dr-mode host|peripheral")
            return 2
        return 0 if set_dr_mode(argv[1], log=print) else 1
    if cmd == "enable":
        return 0 if enable_service(log=print) else 1
    if cmd == "disable":
        return 0 if disable_service(log=print) else 1
    if cmd == "persist":
        if len(argv) < 2:
            print("Uso: persist <perfil>")
            return 2
        return 0 if persist_profile(argv[1], log=print) else 1
    if cmd == "install-assets":
        install_boot_assets(log=print)
        return 0
    if cmd == "boot":
        return 0 if boot(log=print) else 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
