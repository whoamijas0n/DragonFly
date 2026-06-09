#!/bin/bash

# ==============================================================================
# DRAGON FLY SYSTEM - AUTO INSTALLER (LITE KIOSK EDITION)
# ==============================================================================

# Colores
RED='\033[0;31m'
DARK_GRAY='\033[1;30m'
WHITE='\033[1;37m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Detectar usuario real (incluso si se ejecuta con sudo)
TARGET_USER=${SUDO_USER:-$(whoami)}
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
PROJECT_DIR=$(pwd)

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
    
    print_center "=== INSTALADOR AUTOMATIZADO - RED TEAM TOOLBOX ===" "${WHITE}"
    print_center "Preparando entorno para automatizar tus auditorias (OS Lite)" "${DARK_GRAY}"
    echo ""
}

# 1. Instalar Dependencias
instalar_dependencias() {
    print_center "[*] Actualizando repositorios e instalando dependencias base..." "${RED}"
    apt-get update -y
    
    # Se añade xserver-xorg, xinit y x11-xserver-utils para el motor gráfico en OS Lite
    # Se eliminó lxterminal por ser innecesario
    # Se incluyen openbox, fuentes de x11, fbdev para la pantalla TFT, netifaces, aioquic y git/openssl
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3 python3-tk python3-serial \
        nmap macchanger aircrack-ng hostapd dnsmasq iptables \
        network-manager bluez rfkill \
        xserver-xorg xinit x11-xserver-utils \
        xserver-xorg-input-libinput xserver-xorg-input-evdev \
        openbox xfonts-base xfonts-75dpi xserver-xorg-video-fbdev \
        python3-pil python3-pil.imagetk \
        python3-netifaces python3-aioquic git openssl

    print_center "[+] Dependencias instaladas correctamente." "${GREEN}"
    sleep 2
}

# 2. Configurar USB Gadget (Rubber Ducky)
configurar_gadget() {
    print_center "[*] Creando script USB Gadget (/usr/local/bin/usb_gadget.sh)..." "${RED}"
    
    cat << 'EOF' > /usr/local/bin/usb_gadget.sh
#!/bin/bash
# Limpiar cualquier gadget anterior
if [ -d /sys/kernel/config/usb_gadget/g1 ]; then
    echo "" > /sys/kernel/config/usb_gadget/g1/UDC 2>/dev/null
    sleep 1
    rm -rf /sys/kernel/config/usb_gadget/g1
fi

# Cargar módulos (por si no estaban)
modprobe libcomposite
modprobe usb_f_hid

# Crear gadget
mkdir -p /sys/kernel/config/usb_gadget/g1
cd /sys/kernel/config/usb_gadget/g1

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "1234567890" > strings/0x409/serialnumber
echo "Raspberry Pi" > strings/0x409/manufacturer
echo "Pi Zero HID Keyboard" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Teclado HID" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower

mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
printf "\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0" > functions/hid.usb0/report_desc

ln -s functions/hid.usb0 configs/c.1/

# Pequeña pausa para que el sistema USB esté listo
sleep 2

# Activar
UDC_DEV=$(ls /sys/class/udc | head -1)
echo "$UDC_DEV" > UDC
echo "Gadget HID activado en $UDC_DEV"
EOF

    chmod +x /usr/local/bin/usb_gadget.sh
    print_center "[+] Script USB Gadget configurado." "${GREEN}"
    sleep 2
}

# 3. Configurar Auto-Inicio Kiosco y Permisos (Sudoers)
configurar_sistema() {
    print_center "[*] Configurando Modo Kiosco (Openbox + X11)..." "${RED}"
    
    # 3.1. Archivo de arranque X11 (.xinitrc)
    cat << EOF > "$TARGET_HOME/.xinitrc"
#!/bin/sh
# Desactivar ahorro de energia y protector de pantalla
xset -dpms
xset s off
xset s noblank

# Iniciar el gestor de ventanas ligero en segundo plano
openbox &

# Iniciar DragonFly directamente
cd $PROJECT_DIR
exec sudo /usr/bin/python3 $PROJECT_DIR/raspi.py
EOF
    
    chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.xinitrc"
    chmod +x "$TARGET_HOME/.xinitrc"

    # 3.2. Crear archivo de configuración para TFT Screen fbdev
    print_center "[*] Configurando framebuffer para pantalla TFT..." "${RED}"
    mkdir -p /usr/share/X11/xorg.conf.d/
    cat << 'EOF' > /usr/share/X11/xorg.conf.d/99-fbdev.conf
Section "Device"
    Identifier "TFT Screen"
    Driver "fbdev"
    Option "fbdev" "/dev/fb1"
EndSection
EOF

    # 3.3. Configurar autologin en consola usando raspi-config
    print_center "[*] Activando autologin en tty1..." "${RED}"
    if command -v raspi-config >/dev/null 2>&1; then
        raspi-config nonint do_boot_behaviour B2
    else
        echo -e "${DARK_GRAY}[!] raspi-config no encontrado. Omitiendo autologin.${NC}"
    fi

    # 3.4. Disparar startx al inicio de sesión desde .profile
    PROFILE_FILE="$TARGET_HOME/.profile"
    if ! grep -q "startx" "$PROFILE_FILE" 2>/dev/null; then
        cat << 'EOF' >> "$PROFILE_FILE"

# Iniciar entorno grafico para DragonFly automaticamente
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    startx
fi
EOF
    fi

    # 3.5. Otorgar permisos de ejecución
    print_center "[*] Otorgando permisos de ejecución NOPASSWD en sudoers..." "${RED}"
    echo "$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/python3 $PROJECT_DIR/raspi.py" | tee /etc/sudoers.d/010_dragonfly > /dev/null
    chmod 0440 /etc/sudoers.d/010_dragonfly

    print_center "[+] Entorno de Kiosco y TFT configurado correctamente." "${GREEN}"
    sleep 2
}

# 4. Clonar e instalar Responder
configurar_responder() {
    print_center "[*] Instalando y configurando Responder en /opt/Responder..." "${RED}"
    
    if [ ! -d "/opt/Responder" ]; then
        git clone https://github.com/lgandx/Responder.git /opt/Responder
    else
        print_center "[!] Responder ya está clonado. Actualizando repositorio..." "${DARK_GRAY}"
        cd /opt/Responder && git pull
    fi

    # Dar permisos al directorio
    chmod -R 755 /opt/Responder

    print_center "[*] Generando certificados SSL para Responder..." "${RED}"
    mkdir -p /opt/Responder/certs

    # Generar la llave y el certificado SSL de manera desatendida
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout /opt/Responder/certs/responder.key \
        -out /opt/Responder/certs/responder.crt \
        -days 3650 -subj "/CN=DragonFly" 2>/dev/null

    # Asignar permisos correctos para que Responder pueda leerlos
    chmod 644 /opt/Responder/certs/responder.crt
    chmod 600 /opt/Responder/certs/responder.key

    print_center "[+] Responder configurado correctamente." "${GREEN}"
    sleep 2
}

# 5. Función para eliminar la instalación por completo
eliminar_instalacion() {
    print_center "[*] INICIANDO DESINSTALACIÓN DE DRAGONFLY..." "${RED}"
    
    # 5.1 Eliminar Responder
    if [ -d "/opt/Responder" ]; then
        rm -rf /opt/Responder
        print_center "[-] Directorio /opt/Responder eliminado." "${DARK_GRAY}"
    fi

    # 5.2 Eliminar archivo de gadget y limpiarlo de sysfs
    if [ -f "/usr/local/bin/usb_gadget.sh" ]; then
        rm -f /usr/local/bin/usb_gadget.sh
        print_center "[-] Script de USB Gadget eliminado." "${DARK_GRAY}"
    fi
    if [ -d /sys/kernel/config/usb_gadget/g1 ]; then
        echo "" > /sys/kernel/config/usb_gadget/g1/UDC 2>/dev/null
        sleep 1
        rm -rf /sys/kernel/config/usb_gadget/g1
    fi

    # 5.3 Limpiar Kiosco y configuraciones X11
    rm -f "$TARGET_HOME/.xinitrc"
    rm -f /usr/share/X11/xorg.conf.d/99-fbdev.conf
    
    # 5.4 Limpiar autostart de .profile
    PROFILE_FILE="$TARGET_HOME/.profile"
    if [ -f "$PROFILE_FILE" ]; then
        # Usa awk para encontrar y eliminar el bloque exacto de 4 líneas que agregamos
        awk '/# Iniciar entorno grafico para DragonFly automaticamente/{skip=4; next} skip>0{skip--; next} 1' "$PROFILE_FILE" > "${PROFILE_FILE}.tmp" && mv "${PROFILE_FILE}.tmp" "$PROFILE_FILE"
        chown "$TARGET_USER:$TARGET_USER" "$PROFILE_FILE"
        print_center "[-] Configuraciones de auto-inicio limpiadas en .profile." "${DARK_GRAY}"
    fi

    # 5.5 Remover configuración de sudoers
    if [ -f "/etc/sudoers.d/010_dragonfly" ]; then
        rm -f /etc/sudoers.d/010_dragonfly
        print_center "[-] Excepciones de Sudoers removidas." "${DARK_GRAY}"
    fi

    print_center "[+] SISTEMA LIMPIO." "${GREEN}"
    print_center "Nota: Las dependencias instaladas por APT se han mantenido para evitar romper otras utilidades del SO." "${WHITE}"
    sleep 3
}

# Menú interactivo centrado
main_menu() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Por favor, ejecuta este script como root (sudo ./install-whitout-gui.sh)${NC}"
        exit 1
    fi

    while true; do
        draw_banner
        
        # Opciones centradas visualmente sumando márgenes
        local term_width=$(tput cols 2>/dev/null || echo 80)
        local menu_width=52
        local pad_len=$(( (term_width - menu_width) / 2 ))
        [[ $pad_len -lt 0 ]] && pad_len=0
        local padding=$(printf '%*s' "$pad_len" "")

        echo "${padding}1) Instalación Completa (Todo-en-Uno OS Lite)"
        echo "${padding}2) Instalar Solo Dependencias (APT + X11)"
        echo "${padding}3) Configurar Solo USB Gadget"
        echo "${padding}4) Configurar Solo Entorno Kiosco y Sudoers"
        echo "${padding}5) Instalar y Configurar Responder"
        echo "${padding}6) Eliminar Instalación Completa (Desinstalar)"
        echo "${padding}7) Salir"
        echo ""
        
        # El prompt lo dejamos normal para que el usuario escriba
        read -p "${padding}Selecciona una opción [1-7]: " opcion

        case $opcion in
            1)
                instalar_dependencias
                configurar_gadget
                configurar_sistema
                configurar_responder
                print_center "¡INSTALACIÓN COMPLETADA CON ÉXITO!" "${GREEN}"
                echo ""
                print_center "Se recomienda reiniciar la Raspberry Pi." "${WHITE}"
                read -p "Presiona ENTER para continuar..."
                break
                ;;
            2)
                instalar_dependencias
                ;;
            3)
                configurar_gadget
                ;;
            4)
                configurar_sistema
                ;;
            5)
                configurar_responder
                ;;
            6)
                eliminar_instalacion
                ;;
            7)
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
