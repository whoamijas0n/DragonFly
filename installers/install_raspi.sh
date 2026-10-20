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
        nmap macchanger aircrack-ng iw ieee-data hostapd dnsmasq iptables \
        network-manager bluez rfkill \
        xserver-xorg xinit x11-xserver-utils \
        xserver-xorg-input-libinput xserver-xorg-input-evdev \
        openbox xfonts-base xfonts-75dpi xserver-xorg-video-fbdev \
        python3-pil python3-pil.imagetk \
        python3-netifaces python3-aioquic git openssl

    print_center "[+] Dependencias instaladas correctamente." "${GREEN}"
    sleep 2
}

# 2. Configurar USB Gadget compuesto (Rubber Ducky / Poison)
configurar_gadget() {
    print_center "[*] Instalando motor de Gadget USB compuesto..." "${RED}"

    cat << EOF > /usr/local/bin/usb_gadget.sh
#!/bin/bash
# DragonFly System - Construccion del gadget USB al arranque (generado por el instalador)
set -u
cd "$PROJECT_DIR" || exit 1
exec /usr/bin/python3 -m dragonfly.core.usb_gadget boot
EOF
    chmod +x /usr/local/bin/usb_gadget.sh

    cat << 'EOF' > /etc/systemd/system/usb_gadget.service
[Unit]
Description=DragonFly USB Gadget (perfil persistente)
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/bin/bash /usr/local/bin/usb_gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF
    systemctl daemon-reload

    mkdir -p /etc/dragonfly
    [ -f /etc/dragonfly/gadget_profile ] || echo "hid" > /etc/dragonfly/gadget_profile

    print_center "[+] Motor de gadget instalado. Los perfiles se conmutan desde la app (en caliente)." "${GREEN}"
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
    # El driver fbdev de X solo acepta rutas /dev/fbN que correspondan a un
    # framebuffer real en /sys/class/graphics/fbN, y ese número puede variar
    # entre arranques (fb0 o fb1). Se detecta el actual y df-tft-recover.sh
    # se encarga de corregirlo en cada boot.
    print_center "[*] Configurando framebuffer para pantalla TFT..." "${RED}"
    mkdir -p /usr/share/X11/xorg.conf.d/
    TFT_FB=""
    for _fbdir in /sys/class/graphics/fb[0-9]*; do
        [ -e "$_fbdir/name" ] || continue
        if [ "$(head -c 10 "$_fbdir/name" 2>/dev/null)" = "fb_ili9340" ]; then
            TFT_FB=$(basename "$_fbdir")
        fi
    done
    cat << EOF > /usr/share/X11/xorg.conf.d/99-fbdev.conf
Section "Device"
    Identifier "TFT Screen"
    Driver "fbdev"
    Option "fbdev" "/dev/${TFT_FB:-fb1}"
EndSection
EOF

    # 3.3. Recuperación automática del framebuffer del TFT (script + servicio)
    print_center "[*] Instalando recuperación automática del TFT..." "${RED}"
    cat << 'EOF' > /usr/local/bin/df-tft-recover.sh
#!/bin/bash
# DragonFly - Asegura el framebuffer del TFT y la config de X (fbdev).
#
# El driver fbdev de X solo acepta rutas /dev/fbN que correspondan a un
# framebuffer real en /sys/class/graphics/fbN (comprueba el basename contra
# sysfs), asi que el numero debe ser el correcto en cada arranque: el kernel
# puede registrar el TFT como fb0 o fb1 segun el timing del boot.
#
# Este script:
#   1) localiza el framebuffer del TFT (nombre "fb_ili9340")
#   2) si no existe, recarga el driver fbtft (el overlay tft9341 hace reset)
#   3) ajusta /usr/share/X11/xorg.conf.d/99-fbdev.conf a /dev/fbN
# Se ejecuta al arranque antes del kiosco (df-tft-recover.service) y tambien
# antes de startx desde ~/.profile.
set -u

CONF=/usr/share/X11/xorg.conf.d/99-fbdev.conf
READY=/run/df-display-ready

log() {
    echo "df-tft-recover: $*" >&2
    timeout 3 logger -t df-tft-recover "$*" 2>/dev/null || true
}

tft_fb() {
    local f
    for f in /sys/class/graphics/fb[0-9]*; do
        [ -e "$f/name" ] || continue
        if [ "$(timeout 2 head -c 10 "$f/name" 2>/dev/null)" = "fb_ili9340" ]; then
            basename "$f"
            return 0
        fi
    done
    return 1
}

# Asegura el arranque del kiosco en ~/.profile: un corte de luz puede dejar
# el fichero vacio (escritura perdida) y entonces startx no se dispararia.
PROF=/home/raspi/.profile
if ! grep -q "Iniciar entorno grafico para DragonFly" "$PROF" 2>/dev/null; then
    cat >> "$PROF" <<'EOF3'

# Iniciar entorno grafico para DragonFly automaticamente
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    sudo -n /usr/local/bin/df-tft-recover.sh >/dev/null 2>&1 || true
    startx
fi
EOF3
    chown --reference=/home/raspi "$PROF" 2>/dev/null || true
    log "bloque de arranque re-insertado en $PROF"
fi

FB=$(tft_fb || true)

# Margen inicial: tras el arranque el driver/udev pueden tardar unos segundos.
if [ -z "${FB:-}" ]; then
    for _ in $(seq 1 10); do
        sleep 1
        FB=$(tft_fb || true)
        [ -n "${FB:-}" ] && break
    done
fi

# Plan B: recargar el driver fbtft hasta 3 veces.
if [ -z "${FB:-}" ]; then
    for intento in 1 2 3; do
        log "TFT no detectado; recargando driver fbtft (intento $intento)"
        modprobe -r fb_ili9340 >/dev/null 2>&1 || true
        sleep 1
        modprobe -r fbtft >/dev/null 2>&1 || true
        modprobe fb_ili9340 >/dev/null 2>&1 || true
        for _ in $(seq 1 10); do
            sleep 1
            FB=$(tft_fb || true)
            [ -n "${FB:-}" ] && break 2
        done
    done
fi

if [ -z "${FB:-}" ]; then
    log "AVISO: no se pudo detectar el TFT (revisar hardware/overlay)"
    exit 1
fi

N=${FB#fb}

# Ajusta la config de Xorg al numero de framebuffer actual (primero el
# fichero, despues el log: el log nunca debe impedir el arreglo).
if ! grep -q "\"/dev/fb$N\"" "$CONF" 2>/dev/null; then
    cat > "$CONF" <<EOF2
Section "Device"
    Identifier "TFT Screen"
    Driver "fbdev"
    Option "fbdev" "/dev/fb$N"
EndSection
EOF2
    log "configurado Xorg -> /dev/fb$N"
fi

touch "$READY"
exit 0
EOF
    chmod +x /usr/local/bin/df-tft-recover.sh

    cat << 'EOF' > /etc/systemd/system/df-tft-recover.service
[Unit]
Description=DragonFly - Framebuffer del TFT y config de X (fbdev)
After=systemd-udevd.service local-fs.target
Before=getty@tty1.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/df-tft-recover.sh
TimeoutStartSec=90

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable df-tft-recover.service > /dev/null 2>&1

    # 3.4. Configurar autologin en consola usando raspi-config
    print_center "[*] Activando autologin en tty1..." "${RED}"
    if command -v raspi-config >/dev/null 2>&1; then
        raspi-config nonint do_boot_behaviour B2
    else
        echo -e "${DARK_GRAY}[!] raspi-config no encontrado. Omitiendo autologin.${NC}"
    fi

    # 3.5. Disparar startx al inicio de sesión desde .profile
    PROFILE_FILE="$TARGET_HOME/.profile"
    if ! grep -q "startx" "$PROFILE_FILE" 2>/dev/null; then
        cat << 'EOF' >> "$PROFILE_FILE"

# Iniciar entorno grafico para DragonFly automaticamente
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    sudo -n /usr/local/bin/df-tft-recover.sh >/dev/null 2>&1 || true
    startx
fi
EOF
    fi

    # 3.6. Otorgar permisos de ejecución
    print_center "[*] Otorgando permisos de ejecución NOPASSWD en sudoers..." "${RED}"
    echo "$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/python3 $PROJECT_DIR/raspi.py" | tee /etc/sudoers.d/010_dragonfly > /dev/null
    chmod 0440 /etc/sudoers.d/010_dragonfly
    echo "$TARGET_USER ALL=(ALL) NOPASSWD: /usr/local/bin/df-tft-recover.sh" | tee /etc/sudoers.d/020_dragonfly_display > /dev/null
    chmod 0440 /etc/sudoers.d/020_dragonfly_display

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
    for GADGET_DIR in /sys/kernel/config/usb_gadget/g1 /sys/kernel/config/usb_gadget/dragonfly; do
        if [ -d "$GADGET_DIR" ]; then
            echo "" > "$GADGET_DIR/UDC" 2>/dev/null
            sleep 1
            rm -rf "$GADGET_DIR"
        fi
    done
    if [ -f /etc/systemd/system/usb_gadget.service ]; then
        systemctl disable usb_gadget.service 2>/dev/null
        rm -f /etc/systemd/system/usb_gadget.service
        systemctl daemon-reload
        print_center "[-] Servicio usb_gadget eliminado." "${DARK_GRAY}"
    fi
    rm -f /etc/dragonfly/gadget_profile

    # 5.3 Limpiar Kiosco y configuraciones X11
    rm -f "$TARGET_HOME/.xinitrc"
    rm -f /usr/share/X11/xorg.conf.d/99-fbdev.conf

    # 5.3b Eliminar recuperación automática del TFT
    if [ -f /etc/systemd/system/df-tft-recover.service ]; then
        systemctl disable df-tft-recover.service 2>/dev/null
        rm -f /etc/systemd/system/df-tft-recover.service
        systemctl daemon-reload
    fi
    rm -f /usr/local/bin/df-tft-recover.sh
    rm -f /run/df-display-ready
    
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
    rm -f /etc/sudoers.d/020_dragonfly_display

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
