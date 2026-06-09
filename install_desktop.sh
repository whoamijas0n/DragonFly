#!/bin/bash

# ==============================================================
# DRAGON FLY SYSTEM - INSTALADOR UNIVERSAL PARA DESKTOP.PY
# Soporte: Kali, Parrot, Debian, Ubuntu, Arch Linux, Fedora
# ==============================================================

# Colores (Dark Red Theme)
RED='\033[0;31m'
DARK_RED='\033[38;5;88m'
NC='\033[0m'
BOLD='\033[1m'

# Verificar privilegios de root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Por favor, ejecuta este instalador como root (sudo ./install_desktop.sh)${NC}"
  exit 1
fi

# Directorio de instalación
INSTALL_DIR="/opt/dragonfly_desktop"
BIN_PATH="/usr/local/bin/dragonfly-gui"

# Función de autodetección de OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_LIKE=$ID_LIKE
    else
        echo -e "${RED}[!] No se pudo detectar el sistema operativo.${NC}"
        exit 1
    fi
}

# Función para instalar dependencias del sistema
install_dependencies() {
    detect_os
    echo -e "${DARK_RED}[*] Sistema detectado: ${BOLD}${OS} ${OS_LIKE}${NC}"
    echo -e "${DARK_RED}[*] Instalando dependencias del sistema...${NC}"

    if [[ "$OS" == "kali" || "$OS" == "parrot" || "$OS" == "debian" || "$OS" == "ubuntu" || "$OS_LIKE" == *"debian"* || "$OS_LIKE" == *"ubuntu"* ]]; then
        apt-get update
        apt-get install -y python3 python3-pip python3-tk python3-venv nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables bluez x11-xserver-utils
        
    elif [[ "$OS" == "arch" || "$OS_LIKE" == *"arch"* || "$OS" == "manjaro" ]]; then
        pacman -Sy --noconfirm python python-pip tk nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables-nft bluez bluez-utils xorg-xhost
        
    elif [[ "$OS" == "fedora" || "$OS_LIKE" == *"fedora"* ]]; then
        dnf install -y python3 python3-pip python3-tkinter nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables bluez xhost
        
    else
        echo -e "${RED}[!] Sistema operativo no soportado de forma automática. Instala las dependencias manualmente.${NC}"
        exit 1
    fi
}

# Función principal de instalación
install_dragonfly() {
    install_dependencies

    echo -e "${DARK_RED}[*] Configurando directorio de instalación en $INSTALL_DIR...${NC}"
    mkdir -p "$INSTALL_DIR"
    cp -r ./* "$INSTALL_DIR/"

    echo -e "${DARK_RED}[*] Configurando Entorno Virtual de Python (VENV)...${NC}"
    cd "$INSTALL_DIR"
    python3 -m venv venv
    source venv/bin/activate

    echo -e "${DARK_RED}[*] Instalando dependencias de Python (CustomTkinter)...${NC}"
    pip install --upgrade pip
    pip install customtkinter

    echo -e "${DARK_RED}[*] Creando ejecutable global...${NC}"
    cat << 'EOF' > "$BIN_PATH"
#!/bin/bash
# Script de lanzamiento con soporte para Wayland/X11 como Root
if [ "$EUID" -ne 0 ]; then
  echo "Por favor, ejecuta la herramienta como root: sudo dragonfly-gui"
  exit
fi

# Permitir a root usar el display del usuario actual
xhost +SI:localuser:root > /dev/null 2>&1
export DISPLAY=${DISPLAY:-:0}

cd /opt/dragonfly_desktop
source venv/bin/activate
python3 desktop.py

# Revocar permisos de display al salir
xhost -SI:localuser:root > /dev/null 2>&1
EOF

    chmod +x "$BIN_PATH"
    
    echo -e "${RED}${BOLD}[+] Instalación completada con éxito.${NC}"
    echo -e "${DARK_RED}[*] Para iniciar la interfaz, abre una terminal y escribe:${NC} ${BOLD}sudo dragonfly-gui${NC}\n"
}

# Función de desinstalación
uninstall_dragonfly() {
    echo -e "${DARK_RED}[*] Eliminando archivos de DragonFly Desktop...${NC}"
    
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        echo -e "  [-] Directorio $INSTALL_DIR eliminado."
    fi
    
    if [ -f "$BIN_PATH" ]; then
        rm -f "$BIN_PATH"
        echo -e "  [-] Ejecutable $BIN_PATH eliminado."
    fi

    echo -e "${RED}${BOLD}[+] Desinstalación completada.${NC}\n"
}

# ==========================================
# MENÚ INTERACTIVO
# ==========================================
clear
echo -e "${RED}"
cat << "EOF"
  ____                                _____ _       
 |  _ \ _ __ __ _  __ _  ___  _ __   |  ___| |_   _ 
 | | | | '__/ _` |/ _` |/ _ \| '_ \  | |_  | | | | |
 | |_| | | | (_| | (_| | (_) | | | | |  _| | | |_| |
 |____/|_|  \__,_|\__, |\___/|_| |_| |_|   |_|\__, |
                  |___/                       |___/ 
          - Desktop UI Installer -
EOF
echo -e "${NC}"

echo -e "1. ${BOLD}Instalar DragonFly Desktop${NC} (Autodetectar OS y Dependencias)"
echo -e "2. ${BOLD}Desinstalar DragonFly Desktop${NC}"
echo -e "3. ${BOLD}Salir${NC}\n"

read -p "Selecciona una opción [1-3]: " opcion

case $opcion in
    1)
        install_dragonfly
        ;;
    2)
        uninstall_dragonfly
        ;;
    3)
        echo -e "${DARK_RED}Saliendo...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}[!] Opción inválida.${NC}"
        exit 1
        ;;
esac
