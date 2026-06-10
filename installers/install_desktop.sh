#!/bin/bash

# ==============================================================
# DRAGON FLY SYSTEM - INSTALADOR UNIVERSAL PARA DESKTOP.PY
# Soporte: Kali, Parrot, Debian, Ubuntu, Arch Linux, Fedora
# ==============================================================

# Colores (Dark Red Theme & UI)
RED='\033[0;31m'
DARK_RED='\033[38;5;88m'
DARK_GRAY='\033[1;30m'
WHITE='\033[1;37m'
GREEN='\033[0;32m'
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
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)

# Función para centrar texto de una sola línea en la terminal
print_center() {
    local text="$1"
    local color="$2"
    local term_width=$(tput cols 2>/dev/null || echo 80)
    local padding="$(printf '%0.1s' ' '{1..500})"
    local text_len=${#text}
    local pad_len=$(( (term_width - text_len) / 2 ))
    [[ $pad_len -lt 0 ]] && pad_len=0
    printf "${color}%*.*s%s${NC}\n" 0 "$pad_len" "$padding" "$text"
}

# Banner con Arte ASCII centrado dinámicamente
draw_banner() {
    clear
    local term_width=$(tput cols 2>/dev/null || echo 80)
    
    # La línea más larga de este ASCII art tiene 61 caracteres
    local max_len=61 
    local pad_len=$(( (term_width - max_len) / 2 ))
    [[ $pad_len -lt 0 ]] && pad_len=0
    
    # Crear el espacio de margen izquierdo
    local padding=$(printf '%*s' "$pad_len" "")

    echo -e "${RED}"
    # Leer el ASCII art línea por línea y agregarle el margen izquierdo
    while IFS= read -r line; do
        echo "${padding}${line}"
    done << 'EOF'


     ·▄▄▄▄  ▄▄▄   ▄▄▄·  ▄▄ •        ▐ ▄ ·▄▄▄▄▄▌   ▄· ▄▌
     ██▪ ██ ▀▄ █·▐█ ▀█ ▐█ ▀ ▪▪     •█▌▐█▐▄▄·██•  ▐█▪██▌
     ▐█· ▐█▌▐▀▀▄ ▄█▀▀█ ▄█ ▀█▄ ▄█▀▄ ▐█▐▐▌██▪ ██▪  ▐█▌▐█▪
     ██. ██ ▐█•█▌▐█ ▪▐▌▐█▄▪▐█▐█▌.▐▌██▐█▌██▌.▐█▌▐▌ ▐█▀·.
     ▀▀▀▀▀• .▀  ▀ ▀  ▀ ·▀▀▀▀  ▀█▄▀▪▀▀ █▪▀▀▀ .▀▀▀   ▀ • 

EOF
    echo -e "${NC}"
    
    print_center "=== DESKTOP UI INSTALLER - RED TEAM TOOLBOX ===" "${WHITE}"
    print_center "Instalador Universal (Kali, Parrot, Debian, Arch, Fedora)" "${DARK_GRAY}"
    echo ""
}

# Función de autodetección de OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_LIKE=$ID_LIKE
    else
        print_center "[!] No se pudo detectar el sistema operativo." "${RED}"
        exit 1
    fi
}

# Función para instalar dependencias del sistema
install_dependencies() {
    detect_os
    echo ""
    print_center "[*] Sistema detectado: ${OS} ${OS_LIKE}" "${DARK_RED}"
    print_center "[*] Instalando dependencias del sistema..." "${DARK_RED}"

    if [[ "$OS" == "kali" || "$OS" == "parrot" || "$OS" == "debian" || "$OS" == "ubuntu" || "$OS_LIKE" == *"debian"* || "$OS_LIKE" == *"ubuntu"* ]]; then
        apt-get update
        apt-get install -y python3 python3-pip python3-tk python3-venv nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables bluez x11-xserver-utils
        
    elif [[ "$OS" == "arch" || "$OS_LIKE" == *"arch"* || "$OS" == "manjaro" ]]; then
        pacman -Sy --noconfirm python python-pip tk nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables-nft bluez bluez-utils xorg-xhost
        
    elif [[ "$OS" == "fedora" || "$OS_LIKE" == *"fedora"* ]]; then
        dnf install -y python3 python3-pip python3-tkinter nmap macchanger aircrack-ng hostapd dnsmasq net-tools iptables bluez xhost
        
    else
        print_center "[!] Sistema operativo no soportado de forma automática." "${RED}"
        print_center "Instala las dependencias manualmente." "${RED}"
        exit 1
    fi
}

# Función principal de instalación
install_dragonfly() {
    install_dependencies

    print_center "[*] Configurando directorio de instalación en $INSTALL_DIR..." "${DARK_RED}"
    mkdir -p "$INSTALL_DIR"
    cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"

    print_center "[*] Configurando Entorno Virtual de Python (VENV)..." "${DARK_RED}"
    cd "$INSTALL_DIR"
    python3 -m venv venv
    source venv/bin/activate

    print_center "[*] Instalando dependencias de Python (CustomTkinter)..." "${DARK_RED}"
    pip install --upgrade pip
    pip install customtkinter

    print_center "[*] Creando ejecutable global..." "${DARK_RED}"
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
    
    echo ""
    print_center "[+] Instalación completada con éxito." "${GREEN}"
    print_center "Para iniciar la interfaz, escribe: sudo dragonfly-gui" "${WHITE}"
    echo ""
    read -p "Presiona ENTER para continuar..."
}

# Función de desinstalación
uninstall_dragonfly() {
    echo ""
    print_center "[*] INICIANDO DESINSTALACIÓN DE DRAGONFLY DESKTOP..." "${RED}"
    
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        print_center "[-] Directorio $INSTALL_DIR eliminado." "${DARK_GRAY}"
    fi
    
    if [ -f "$BIN_PATH" ]; then
        rm -f "$BIN_PATH"
        print_center "[-] Ejecutable $BIN_PATH eliminado." "${DARK_GRAY}"
    fi

    echo ""
    print_center "[+] Desinstalación completada." "${GREEN}"
    echo ""
    read -p "Presiona ENTER para continuar..."
}

# ==========================================
# MENÚ INTERACTIVO
# ==========================================
main_menu() {
    while true; do
        draw_banner
        
        # Opciones centradas visualmente sumando márgenes
        local term_width=$(tput cols 2>/dev/null || echo 80)
        local menu_width=58
        local pad_len=$(( (term_width - menu_width) / 2 ))
        [[ $pad_len -lt 0 ]] && pad_len=0
        local padding=$(printf '%*s' "$pad_len" "")

        echo "${padding}1) Instalar DragonFly Desktop (Autodetectar SO)"
        echo "${padding}2) Desinstalar DragonFly Desktop"
        echo "${padding}3) Salir"
        echo ""
        
        # El prompt lo dejamos normal para que el usuario escriba
        read -p "${padding}Selecciona una opción [1-3]: " opcion

        case $opcion in
            1)
                install_dragonfly
                ;;
            2)
                uninstall_dragonfly
                ;;
            3)
                echo ""
                print_center "Saliendo..." "${DARK_GRAY}"
                exit 0
                ;;
            *)
                echo ""
                print_center "Opción no válida." "${RED}"
                sleep 1
                ;;
        esac
    done
}

main_menu
