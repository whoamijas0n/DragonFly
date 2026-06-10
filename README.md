<div align="center">

<img src="images/logo.png" alt="logo" width="800" height="auto" />

<h1>DragonFly System</h1>

**Red Team Toolbox** — Auditoría Inalámbrica, HID Attack & Network Offensive

<br/>

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-A22846?style=for-the-badge&logo=Raspberry%20Pi&logoColor=white)
![Kali Linux](https://img.shields.io/badge/Kali_Linux-557C94?style=for-the-badge&logo=kali-linux&logoColor=white)
![Espressif](https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white)

<br/>


<h4>
  <a href="https://github.com/whoamijas0n/DragonFly/">[-]  View Demo</a>
  &nbsp;|&nbsp;
  <a href="https://github.com/whoamijas0n/DragonFly">[-]  Documentation</a>
  &nbsp;|&nbsp;
  <a href="https://github.com/whoamijas0n/DragonFly/issues/new">[-]  Report Bug</a>
  &nbsp;|&nbsp;
  <a href="https://github.com/whoamijas0n/DragonFly/issues/new">[-]  Request Feature</a>
</h4>

</div>

<br/>

DragonFly es una suite de auditoría y pentesting modular diseñada para operaciones de Red Team en entornos controlados. Proporciona una interfaz unificada para ejecutar técnicas de reconocimiento, ataques inalámbricos, inyección de pulsaciones HID y manipulación de señales RF/Bluetooth, con soporte nativo para hardware portátil basado en SBC y estaciones de trabajo convencionales.

La arquitectura del sistema separa claramente la lógica de ataque de la capa de presentación, permitiendo despliegues escalables desde una Raspberry Pi Zero con pantalla táctil hasta un entorno de escritorio completo con Kali Linux.


<div align="center">
  
## Edición Raspberry Pi (raspi.py)

</div>

### Descripción Técnica

Esta variante está optimizada para ejecución en hardware de recursos limitados con interfaces táctiles de baja resolución (320x240 píxeles). Implementa un sistema de navegación por menús jerárquicos con retroalimentación visual en tiempo real, gestión de memoria mediante garbage collection explícito y ejecución asíncrona de comandos para mantener la capacidad de respuesta de la interfaz.

### Hardware y Sistema Operativo

El entorno de ejecución recomendado es el siguiente:





| Componente | Especificación |
|---|---|
| Placa | Raspberry Pi Zero 2 WH |
| Alimentación | Batería PiSugar 3 (o compatible) |
| Pantalla | Pantalla táctil resistiva/capacitiva de 2.4" (320x240) |
| Sistema Operativo | Raspberry Pi OS 32-bits lite (sin entorno grafico) |




> Los siguientes enlaces son referencias de ejemplo para orientar la compra del hardware. Los precios y la disponibilidad pueden variar.
>
> - Raspberry Pi Zero 2 WH: [https://a.co/d/0gV3rUaV](https://a.co/d/0gV3rUaV)
> - Batería PiSugar 3: [https://a.co/d/0bZ2SinO](https://a.co/d/0bZ2SinO)
> - Pantalla Táctil 2.4": [https://es.aliexpress.com/i/1005005770033042.html?gatewayAdapt=glo2esp](https://es.aliexpress.com/i/1005005770033042.html?gatewayAdapt=glo2esp)

---


<div align="center">

<img src="images/raspi-zero.png" alt="raspi-zero" width="800" height="auto" />

</div>

---

### Desglose de Herramientas

#### 1. Reconocimiento (Nmap)

Módulo de escaneo de red basado en `nmap`. El operador introduce una IP objetivo mediante un teclado numérico táctil emergente y opcionalmente activa un modo de rango CIDR (`/8`, `/16`, `/24`, `/32`). Los comandos disponibles cubren los flujos de reconocimiento más comunes en un pentest:



| Opción | Descripción |
|---|---|
| Descubrimiento | Detección de hosts activos (`-sn`) |
| Puertos comunes | Top 1000 puertos TCP (`-sS -T3 --top-ports 1000`) |
| Full TCP | Escaneo completo de los 65535 puertos |
| Servicios/Versión | Detección de versiones de servicios (`-sV`) |
| Detección OS | Identificación del sistema operativo (`-O`) |
| UDP Comunes | Top 100 puertos UDP |
| Vulnerabilidades | Scripts `vuln` y `exploit` de Nmap |
| Agresivo | Escaneo combinado (`-A -p-`) |
| Firewall/IDS | Prueba de reglas de filtrado ACK scan |
| Scripts servicios | Enumeración HTTP, SMB, FTP, SSH |
| SSL/TLS | Auditoría de cifrados y certificados |
| Traceroute | Mapeo de ruta hasta el objetivo |
| Automatizado | Pipeline completo: descubrimiento, puertos y servicios en secuencia |



Cada escaneo crea automáticamente una carpeta de sesión con la marca temporal dentro de `Resultados_Nmap/Auditoria-YYYY-MM-DD-HH-MM-SS/` y guarda la salida en archivos `.txt` numerados. El botón "Ver Resultados" permite navegar y leer estos archivos directamente desde la interfaz táctil.

#### 2. MAC Changer

Permite cambiar la dirección MAC de cualquier interfaz de red detectada en el sistema. Las operaciones disponibles son:

- **Ver Estado**: muestra la MAC actual y la original de fábrica.
- **MAC Random**: genera y aplica una dirección completamente aleatoria.
- **Reset Original**: restaura la MAC de fábrica del adaptador.
- **Mismo Fabricante**: aleatoriza solo la porción de dispositivo manteniendo el OUI del fabricante.

Cada operación baja la interfaz, aplica el cambio con `macchanger` y la vuelve a levantar automáticamente.

#### 3. Auditoría WiFi

Módulo central de auditoría inalámbrica. Agrupa cinco flujos de ataque/análisis:

- **Activar Monitor**: pone la interfaz seleccionada en modo monitor usando `airmon-ng`, terminando procesos conflictivos antes.
- **Captura Handshake**: escanea redes disponibles durante 15 segundos, permite seleccionar el objetivo y un cliente (o broadcast), y lanza `airodump-ng` para captura simultánea con `aireplay-ng -0` para forzar la reautenticación. Los archivos `.cap` se guardan en `Resultados_Handshake/Auditoria-{timestamp}/`.
- **Ataque Evil Twin**: flujo completo de AP falso con portal cautivo (ver sección dedicada más adelante).
- **Desautenticación**: envía paquetes deauth dirigidos a un cliente o en broadcast contra un BSSID objetivo.
- **Explorar Handshakes / Explorar Evil Twin**: navegador de archivos integrado para revisar capturas y credenciales de sesiones anteriores.

#### 4. Gadget NRF24 JAMMER

Interfaz de control para el hardware externo Blue-Fly (ESP32). La aplicación detecta automáticamente el puerto serie (`/dev/ttyACM*`, `/dev/ttyUSB*`) y sincroniza con el firmware esperando el mensaje `Gadget listo`. Si el dispositivo se desconecta durante la sesión, el módulo gestiona la reconexión automática sin bloquear la interfaz gráfica. Las funciones disponibles son: iniciar Sweep Jam, detener la interferencia y consultar el estado activo del módulo.

#### 5. Rubber Ducky

Ejecuta scripts de inyección de pulsaciones a través del dispositivo HID USB configurado (`/dev/hidg0`). El módulo lista automáticamente todos los archivos `.txt` contenidos en la carpeta `payloads/` y permite ejecutarlos con un toque. Antes de ejecutar cualquier payload, espera 2 segundos para que el operador posicione el cursor en el sistema objetivo.

#### 6. Ataque Poison (Envenenamiento de Red USB)

Módulo diseñado para interceptar tráfico emulando un adaptador Ethernet sobre USB (ataque estilo PoisonTap). Para utilizarlo, la Raspberry Pi debe estar configurada previamente en el modo de red adecuado desde el menú de Utilidades OS (RNDIS para víctimas Windows o CDC ECM para Mac/Linux). 

La interfaz permite gestionar el ciclo de vida del ataque subyacente (ejecutado a través de `poison_logic.py`):
- **Lanzar Ataque**: Inicia la instancia de envenenamiento en la interfaz `usb0`, delegando la manipulación de red y captura de tráfico a la lógica del backend.
- **Detener Ataque**: Finaliza los procesos de intercepción de manera segura, limpia las reglas de red y guarda la sesión.
- **Explorar Logs**: Abre el navegador de archivos integrado apuntando a `Resultados_Poison/`, permitiendo revisar las carpetas de sesión (generadas con marca temporal) y leer directamente los registros capturados desde la interfaz táctil.

#### 7. Utilidades OS

Conjunto de herramientas de soporte operacional, ampliado para gestionar los nuevos perfiles de hardware y conexiones de red de forma nativa:

- **Cambio de Perfil USB**: Permite reconfigurar el puerto OTG de la Pi Zero con reinicio controlado. Opciones disponibles:
  - **Modo Host**: Para conectar antenas Wi-Fi externas o periféricos.
  - **Rubber Ducky (HID)**: Emula un teclado USB.
  - **Poison (Red USB)**: Despliega un submenú para elegir entre el perfil de red para **Windows (RNDIS)** o **Mac/Linux (CDC ECM)**.
- **Gestor de Redes Wi-Fi**: Escaneo de redes, conexión táctil (con teclado alfanumérico emergente) y gestión de redes previamente guardadas mediante `nmcli`.
- **Gestor Bluetooth**: Escaneo, emparejamiento y conexión a dispositivos Bluetooth directamente desde la GUI utilizando `bluetoothctl`.
- **Sistema**: Monitoreo de almacenamiento, RAM, uso de CPU, conexiones activas, actualización del sistema (APT) y opciones de energía (Reiniciar/Apagar).



---

### Gestión de Archivos y Sesiones

El script crea y mantiene tres directorios raíz en la misma ubicación desde donde se ejecuta:


| Directorio | Contenido |
|---|---|
| `Resultados_Nmap/` | Carpetas de sesión con archivos `.txt` de salida de Nmap |
| `Resultados_Handshake/` | Capturas `.cap` de handshakes WPA/WPA2 |
| `Resultados_EvilTwin/` | Archivos `credentials.log` con datos capturados por el portal |


Cada sesión genera su propia subcarpeta con nombre `Auditoria-{YYYY-MM-DD-HH-MM-SS}`, garantizando que múltiples ejecuciones no sobreescriban datos anteriores.

---

### Evil Twin y Portales Cautivos

El flujo del ataque Evil Twin opera en cuatro fases coordinadas:

1. **Selección de interfaz de AP**: el operador elige la interfaz que emitirá el AP falso.
2. **Selección de red objetivo**: la herramienta escanea y muestra las redes disponibles. Al seleccionar una, clona su SSID y canal.
3. **Selección de portal cautivo**: el script lee la carpeta `evil_portals/` y lista todos los subdirectorios que contengan un archivo `index.html`. Cada subdirectorio es un portal independiente.
4. **Modo de desautenticación**: el operador elige entre deauth broadcast (expulsa a todos los clientes simultáneamente) o deauth dirigido (escanea clientes asociados y selecciona uno o varios).

Durante el ataque, la herramienta levanta `hostapd` para el AP falso, `dnsmasq` como servidor DHCP/DNS con resolución universal hacia la IP del AP, y un servidor web Python integrado en el puerto 80 que sirve el portal seleccionado. Cualquier petición HTTP que no corresponda a un archivo local es redirigida a `index.html`, completando la trampa del portal cautivo. Las credenciales enviadas por formularios GET y POST se escriben en tiempo real en `Resultados_EvilTwin/Auditoria-{timestamp}/credentials.log`.

#### Estructura de la carpeta `evil_portals/`


```
evil_portals/
└── nombre_del_portal/
    ├── index.html          # Página principal del portal (obligatorio)
    ├── success.html        # Página de redirección post-credencial (opcional)
    ├── assets/             # Recursos estáticos: CSS, JS, imágenes (opcional)
    └── capture.php         # Alternativa backend para procesamiento de credenciales (opcional)
```


El repositorio incluye dos portales por defecto. Para crear un portal personalizado funcional, el usuario debe cumplir los siguientes requisitos:

- Crear un subdirectorio dentro de `evil_portals/` con cualquier nombre sin espacios.
- El directorio debe contener obligatoriamente un archivo `index.html` en su raíz. Sin él, el portal no aparecerá listado en la interfaz.
- El formulario de captura debe enviar los datos mediante `method="GET"` o `method="POST"` con `action="/"` o sin atributo de acción. El servidor de captura registra ambos métodos.
- Los archivos estáticos (CSS, imágenes, JS) deben referenciarse con rutas relativas. El servidor copia todo el contenido del directorio del portal a `/tmp/` antes de servirlo.
- El portal debe ser autónomo: no puede depender de recursos externos (CDNs, APIs) ya que el dispositivo víctima no tendrá acceso a internet durante el ataque.

---

### Rubber Ducky — Payloads y Sintaxis

Los scripts de inyección se almacenan como archivos `.txt` dentro de la carpeta `payloads/`. El módulo `ducky_logic.py` los lee línea por línea y los traduce a reportes HID de 8 bytes escritos directamente en `/dev/hidg0`.

#### Sintaxis básica soportada


| Comando | Argumento | Descripción |
|---|---|---|
| `STRING` | texto | Escribe la cadena carácter por carácter |
| `DELAY` | milisegundos | Pausa la ejecución el tiempo indicado |
| `ENTER` | — | Tecla Enter |
| `GUI` | tecla | Tecla Windows/Super + tecla adicional |
| `ALT` | tecla | Alt + tecla adicional |
| `CTRL` | tecla | Control + tecla adicional |
| `SHIFT` | tecla | Shift + tecla adicional |
| `TAB` | — | Tecla Tab |
| `ESC` | — | Tecla Escape |
| `UP / DOWN / LEFT / RIGHT` | — | Teclas de dirección |
| `SPACE` | — | Barra espaciadora |
| `BACKSPACE` | — | Retroceso |
| `DELETE` | — | Suprimir |
| `REM` | comentario | Línea ignorada (comentario) |


Los caracteres en mayúscula son tratados automáticamente como `Shift + minúscula`. Los caracteres especiales que requieren Shift en distribución US (`:`  `?`  `_`  `+`  `"`  `>`  `<`  `|`  `{`  `}` `~`) están mapeados correctamente. Las combinaciones de dos teclas se escriben en la misma línea separadas por espacio (`GUI r`, `CTRL ALT t`).

**Ejemplo de payload:**

```
REM Abrir terminal en Windows
DELAY 500
GUI r
DELAY 400
STRING cmd
ENTER
DELAY 800
STRING whoami
ENTER
```

---
### Cambio de Interfaz USB: Host, HID y Red (Poison)

La Pi Zero 2 W dispone de un único puerto USB OTG. La suite aprovecha el framework `libcomposite` y el subsistema `configfs` del kernel para reescribir dinámicamente los descriptores USB, permitiendo que la placa asuma diferentes identidades ante el ordenador víctima. Modificar este comportamiento requiere un reinicio completo del sistema, proceso que la GUI automatiza.

Los perfiles disponibles desde el menú "Utilidades OS" son:

- **Modo Host (`dr_mode=host`)**: La Pi actúa como controladora, habilitando el uso de tarjetas de red inalámbricas externas o hubs USB.
- **Modo Gadget HID (Rubber Ducky)**: Emula un teclado USB genérico (`idVendor=0x1d6b`, `idProduct=0x0104`). Habilita el dispositivo `/dev/hidg0` para la inyección de pulsaciones del módulo Ducky.
- **Modo Gadget de Red RNDIS (Poison - Windows)**: Emula un adaptador de red compatible con el protocolo NDIS remoto de Microsoft (`idVendor=0x0525`, `idProduct=0xa4a2`). Presenta al host víctima un dispositivo "DragonFly RNDIS Ethernet".
- **Modo Gadget de Red CDC ECM (Poison - Mac/Linux)**: Emula un adaptador de red estándar CDC ECM (`idVendor=0x0525`, `idProduct=0xa4a1`). El script de generación (`usb_gadget.sh`) está programado para asignar una **dirección MAC aleatoria** (`HOST_MAC`) en cada inicialización. Esto es una contramedida crítica para evitar que gestores de red estrictos (como NetworkManager en distribuciones Linux modernas) bloqueen o ignoren la interfaz tras múltiples conexiones.

*Nota técnica: Al seleccionar un perfil de Gadget, la aplicación genera dinámicamente el script `/usr/local/bin/usb_gadget.sh` con los descriptores precisos, lo enlaza mediante un servicio `systemd` (`usb_gadget.service`) de ejecución única (oneshot) y reconfigura las superposiciones del kernel en `/boot/firmware/config.txt` antes de reiniciar.*

---

<div align="center">
  
## Edición de Escritorio — `desktop.py`

</div>

### Descripción Técnica

La edición de escritorio está adaptada para entornos de escritorio convencionales, estaciones de trabajo o placas de alto rendimiento. A diferencia de la versión para Raspberry Pi, esta variante es completamente multiplataforma dentro del ecosistema Linux, siendo compatible con **Kali Linux, Parrot OS, Debian, Ubuntu, Arch Linux, Manjaro y Fedora**. Esta amplia compatibilidad es posible gracias al script de autoinstalación unificado (`install_desktop.sh`), el cual automatiza por completo la detección del entorno de ejecución y el despliegue correlativo de dependencias (proceso que se detallará de forma minuciosa en las siguientes secciones).

La interfaz gráfica está construida utilizando `customtkinter`, lo que proporciona widgets modernos, bordes redondeados y una estética *Dark Mode* refinada. La ventana arranca en modo pantalla completa con la propiedad *topmost* activa, presentando un *sidebar* fijo con los módulos de navegación a la izquierda y un panel de contenido con scroll interactivo a la derecha.

Esta versión elimina intencionalmente los vectores de ataque físico y de proximidad (Rubber Ducky, PoisonTap, Bluetooth) que dependen del controlador USB OTG exclusivo de la Raspberry Pi Zero, enfocándose en el aprovechamiento de los recursos de hardware locales para la auditoría de redes inalámbricas y fuerza bruta offline.

### Diferencias respecto a la edición Raspberry Pi

| Característica | Edición Raspi (`raspi.py`) | Edición Desktop (`desktop.py`) |
|---|---|---|
| Framework GUI | `tkinter` nativo (Optimizado táctil) | `customtkinter` (Moderno, Dark Mode) |
| Layout | Menús apilados en panel único | Sidebar lateral fijo + panel principal |
| Rubber Ducky / PoisonTap | Soportado nativamente (Hardware OTG) | **No disponible** (hardware estándar sin OTG) |
| Cracking WPA (Fuerza Bruta) | **No disponible** (Limitación de CPU) | **Soportado** (`aircrack-ng` + explorador de diccionarios) |
| NRF24 Jammer (Blue-Fly) | Vía USB serie | Vía USB serie |
| Cambio de Perfiles USB | Disponible (Host, Gadget, RNDIS, ECM) | No aplicable |

---

### Módulos Exclusivos y Modificaciones

#### 1. Cracking WPA (Ataque de Diccionario)
Aprovechando la potencia de CPU de una estación de trabajo, la versión de escritorio incluye un módulo dedicado para romper handshakes capturados previamente.
- **Navegador de Capturas**: El operador selecciona la carpeta de la sesión dentro de `Resultados_Handshake/` y elige el archivo `.cap` objetivo.
- **Explorador de Diccionarios**: Permite abrir un cuadro de diálogo del sistema (`filedialog`) para buscar diccionarios `.txt` personalizados, cargando por defecto `/usr/share/wordlists/rockyou.txt`.
- **Ejecución Controlada**: Lanza `aircrack-ng` en un hilo separado mostrando el progreso de la fuerza bruta en la consola en tiempo real, con botones de bloqueo de seguridad para iniciar y detener el ataque forzosamente sin congelar la interfaz.

#### 2. NRF24 Jammer Adaptado
El control del gadget físico Blue-Fly (ESP32) se mantiene funcional. Se rediseñó la interfaz con los componentes de `customtkinter` para mostrar indicadores visuales de estado (Conectado en verde / Desconectado en rojo) y botones de acción rápida para iniciar o detener el barrido de radiofrecuencia en la banda de 2.4 GHz.

#### 3. Utilidades OS Purificadas
El módulo de utilidades se ha limpiado de todas las funciones exclusivas de la Pi Zero. Ahora se centra estrictamente en:
- **Gestión Inalámbrica**: Escaneo y conexión a redes Wi-Fi a través de `nmcli`, solicitando contraseñas mediante pop-ups nativos (`CTkInputDialog`).
- **Monitoreo de Recursos**: Botones de acceso rápido para consultar el almacenamiento (`df -h`), RAM (`free -h`), top de procesos por CPU y conexiones activas (`ss -tulnp`).
- **Control de Energía**: Comandos directos para apagar o reiniciar la máquina.

---

<div align="center">

## Instalación

</div>

El sistema DragonFly utiliza **dos instaladores independientes** ubicados en la carpeta `installers/`, uno para cada variante de la suite. La separación responde a que los entornos de ejecución son radicalmente diferentes: la edición Raspberry Pi se despliega sobre un sistema sin entorno gráfico (OS Lite) y requiere construir un modo kiosco desde cero, mientras que la edición de escritorio debe ser portable entre distribuciones y registrarse como un binario global del sistema.

Ambos scripts comparten la misma lógica de detección de la ruta raíz del proyecto: al estar alojados dentro de `installers/`, resuelven automáticamente el directorio padre con `$(dirname "$0")/..`, por lo que **no es necesario moverlos ni copiarlos** antes de ejecutarlos.

### Clonar el repositorio

```bash
git clone https://github.com/whoamijas0n/DragonFly.git
cd DragonFly
```

A partir de aquí, el proceso de instalación diverge según el hardware de destino. Elige la sección correspondiente a continuación.

---

<div align="center">

## Instalación — `installers/install_raspi.sh`
### Edición Raspberry Pi OS Lite (Sin Entorno Gráfico)

</div>

### Descripción General

Este instalador automatiza el despliegue completo de `raspi.py` sobre **Raspberry Pi OS 32-bits Lite**, una imagen sin entorno de escritorio preinstalado. A diferencia de la versión anterior (que dependía de LXDE y `lxterminal`), la nueva arquitectura construye un entorno gráfico minimalista propio basado en **X11 + Openbox** que arranca directamente en modo kiosco, sin barra de tareas, sin gestor de archivos y sin ningún proceso de escritorio innecesario que compita por los recursos de la Pi Zero 2 W.

El modo kiosco se activa automáticamente en el arranque: la Pi realiza autologin en consola en `tty1` y lanza `startx`, que a su vez ejecuta `openbox` en segundo plano y arranca `raspi.py` como proceso principal del display. Si la aplicación se cierra, la sesión X termina con ella.

El script debe ejecutarse con privilegios de root y detecta automáticamente el usuario real (incluso bajo `sudo`) a través de `$SUDO_USER`, de forma que todos los archivos de configuración del espacio de usuario (`.xinitrc`, `.profile`) se escriben en el directorio home correcto y con la propiedad correcta.

```bash
sudo ./installers/install_raspi.sh
```

---

### Opciones del menú de instalación (`install_raspi.sh`)

| Opción | Descripción |
|---|---|
| **1) Instalación Completa** | Ejecuta las cuatro fases en secuencia (Todo-en-Uno OS Lite). Recomendado para un despliegue limpio desde cero. |
| **2) Solo Dependencias** | Instala únicamente los paquetes APT (sistema base, motor X11, herramientas de red y auditoría). |
| **3) Solo USB Gadget** | Crea y registra el script `/usr/local/bin/usb_gadget.sh` con el descriptor HID de teclado. |
| **4) Solo Entorno Kiosco y Sudoers** | Genera `.xinitrc`, configura la pantalla TFT, activa el autologin y escribe la regla `sudoers`. |
| **5) Solo Responder** | Clona o actualiza el repositorio de Responder en `/opt/Responder` y genera sus certificados SSL. |
| **6) Eliminar Instalación** | Deshace todas las acciones del instalador de forma selectiva, sin tocar los paquetes APT del sistema. |
| **7) Salir** | Termina sin realizar cambios. |

---

### Flujo recomendado: Edición Raspberry Pi OS Lite

La instalación para la Pi Zero 2 W comprende **cuatro fases**. Se recomienda ejecutarlas en el orden que ofrece la opción `1` (Todo-en-Uno) o de forma modular si se desea un despliegue más controlado.

---

#### Fase 1 — Dependencias del sistema (Opción 2)

Actualiza los repositorios APT e instala todos los paquetes necesarios para que `raspi.py` opere con capacidades completas. El bloque de paquetes es significativamente más amplio que en la versión anterior, ya que ahora incluye el motor gráfico completo para construir el entorno X11 desde cero:

**Paquetes de aplicación y auditoría:**
```
python3  python3-tk  python3-serial  python3-pil  python3-pil.imagetk
python3-netifaces  python3-aioquic
nmap  macchanger  aircrack-ng  hostapd  dnsmasq  iptables
network-manager  bluez  rfkill
git  openssl
```

**Motor gráfico X11 y controladores:**
```
xserver-xorg  xinit  x11-xserver-utils
xserver-xorg-input-libinput  xserver-xorg-input-evdev
openbox
xfonts-base  xfonts-75dpi
xserver-xorg-video-fbdev
```

> **Nota sobre `python3-aioquic` y `python3-netifaces`:** estas librerías se instalan directamente desde APT (sin `pip`) para garantizar la compatibilidad con la arquitectura ARMv7 de 32-bits del OS Lite, donde compilar extensiones C desde PyPI puede fallar por ausencia de herramientas de compilación.

> **Nota sobre `lxterminal`:** la dependencia de `lxterminal` presente en la versión anterior ha sido eliminada. El nuevo modo kiosco no necesita un emulador de terminal, ya que `raspi.py` se ejecuta directamente como proceso X11 gestionado por Openbox.

---

#### Fase 2 — USB Gadget HID (Opción 3)

Genera el script `/usr/local/bin/usb_gadget.sh` y lo hace ejecutable. Este script es invocado automáticamente por `raspi.py` cuando el operador activa el modo Rubber Ducky desde el menú de Utilidades OS.

La lógica interna del script realiza las siguientes operaciones en orden:

1. **Limpieza de gadget anterior:** si existe un gadget `g1` previo en `/sys/kernel/config/usb_gadget/`, desvincula su UDC, espera 1 segundo y elimina el árbol de directorios completo para partir siempre de un estado limpio.
2. **Carga de módulos del kernel:** carga `libcomposite` y `usb_f_hid` explícitamente por si el sistema no los cargó aún.
3. **Creación del descriptor USB:**
   - `idVendor`: `0x1d6b` (Linux Foundation)
   - `idProduct`: `0x0104` (Multifunction Composite Gadget)
   - Fabricante declarado: `Raspberry Pi` / Producto: `Pi Zero HID Keyboard`
4. **Registro del descriptor HID:** embebe el descriptor de reporte de teclado estándar (45 bytes, report length 8) directamente en `functions/hid.usb0/report_desc` sin depender de archivos externos.
5. **Enlace y activación:** vincula la función HID a la configuración `c.1` y escribe el nombre del UDC activo (detectado dinámicamente con `ls /sys/class/udc | head -1`) en el archivo `UDC` para activar el gadget.

> El script incluye una pausa de 2 segundos antes de la activación del UDC para permitir que el subsistema USB del kernel complete la enumeración del bus, evitando errores de inicialización intermitentes.

---

#### Fase 3 — Entorno Kiosco X11 y Permisos (Opción 4)

Esta es la fase más diferente respecto al instalador anterior. En lugar de crear una entrada `.desktop` para LXDE, se construye un entorno de arranque gráfico mínimo desde cero. El proceso se divide en cinco sub-pasos:

**3.1 — Archivo `.xinitrc`**

Se genera `~/.xinitrc` en el home del usuario real. Este archivo es invocado por `startx` y define la sesión X completa:

```sh
xset -dpms        # Desactiva la gestión de energía del monitor (DPMS)
xset s off        # Desactiva el protector de pantalla
xset s noblank    # Impide que la pantalla se ponga en negro

openbox &         # Lanza el gestor de ventanas en segundo plano

# Ejecuta raspi.py como proceso principal de la sesión
exec sudo /usr/bin/python3 /ruta/del/proyecto/raspi.py
```

Cuando `raspi.py` termina (por un apagado del sistema desde la propia GUI, por ejemplo), el `exec` hace que la sesión X se cierre junto con él, devolviendo el control a la consola en `tty1`.

**3.2 — Configuración del framebuffer TFT (`99-fbdev.conf`)**

Crea el archivo `/usr/share/X11/xorg.conf.d/99-fbdev.conf` para que Xorg use el framebuffer de la pantalla TFT conectada a la Pi (`/dev/fb1`) como dispositivo de vídeo principal, en lugar del HDMI:

```
Section "Device"
    Identifier "TFT Screen"
    Driver     "fbdev"
    Option     "fbdev" "/dev/fb1"
EndSection
```

> Si tu pantalla TFT requiere una superposición específica en `/boot/firmware/config.txt` (por ejemplo, `dtoverlay=ili9341`), ese paso debe realizarse manualmente antes de instalar, ya que varía según el modelo exacto de pantalla.

**3.3 — Autologin en consola**

Invoca `raspi-config nonint do_boot_behaviour B2` para configurar el modo de arranque **"Console Autologin"**, de forma que la Pi inicie sesión automáticamente en `tty1` con el usuario configurado sin requerir contraseña en la consola. Si `raspi-config` no está disponible en el sistema, esta sub-fase se omite con un aviso y debe configurarse manualmente (habitualmente editando el servicio `getty@tty1.service` con `systemd`).

**3.4 — Disparo automático de `startx` desde `.profile`**

Añade el siguiente bloque al final de `~/.profile` del usuario real:

```bash
# Iniciar entorno grafico para DragonFly automaticamente
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    startx
fi
```

Esta condición garantiza que `startx` solo se invoque cuando:
- No existe una variable `$DISPLAY` activa (no hay sesión X ya corriendo).
- El login ocurre específicamente en `tty1` (la consola del autologin).

De este modo, las sesiones SSH o logins desde otras TTYs no intentarán lanzar X11.

El instalador verifica antes de escribir si el bloque ya existe en `.profile` (comprobando la presencia de `startx`) para evitar duplicados en caso de re-ejecución del instalador.

**3.5 — Regla `sudoers` sin contraseña**

Escribe `/etc/sudoers.d/010_dragonfly` con los permisos correctos (`0440`):

```
<usuario> ALL=(ALL) NOPASSWD: /usr/bin/python3 /ruta/proyecto/raspi.py
```

Esta regla es necesaria porque `raspi.py` es lanzado desde `.xinitrc` con `sudo` y el entorno X11 no dispone de ningún agente de contraseñas. La regla se limita estrictamente al binario Python con la ruta exacta del proyecto, minimizando la superficie de exposición del `NOPASSWD`.

---

#### Fase 4 — Responder (Opción 5)

Instala y configura **Responder** (herramienta de envenenamiento LLMNR/NBT-NS/mDNS) en `/opt/Responder`:

1. **Clonado:** si `/opt/Responder` no existe, clona el repositorio oficial `https://github.com/lgandx/Responder.git`. Si ya existe (reinstalación), ejecuta `git pull` para actualizarlo al último commit disponible.
2. **Permisos de directorio:** aplica `chmod -R 755` para garantizar que `raspi.py` pueda leer y ejecutar los scripts sin errores de permisos.
3. **Generación de certificados SSL:** crea el directorio `/opt/Responder/certs/` y genera un certificado autofirmado RSA-2048 válido por 10 años de forma desatendida:
   ```
   /opt/Responder/certs/responder.key   (chmod 600 — solo root)
   /opt/Responder/certs/responder.crt   (chmod 644 — lectura pública)
   ```
   El CN del certificado se establece en `DragonFly`. Estos certificados son utilizados por Responder para los módulos HTTPS y LDAPS, y deben existir antes de lanzarlo por primera vez.

---

#### Desinstalación (Opción 6)

El proceso de desinstalación es **quirúrgico**: elimina únicamente los componentes que el instalador creó, preservando los paquetes APT instalados para evitar romper otras herramientas que el operador pueda tener en el sistema. Las acciones son:

| Componente | Acción |
|---|---|
| `/opt/Responder` | Eliminado con `rm -rf` |
| `/usr/local/bin/usb_gadget.sh` | Eliminado |
| Gadget activo en `sysfs` | Desvinculado del UDC y eliminado de `/sys/kernel/config/usb_gadget/g1` |
| `~/.xinitrc` | Eliminado |
| `/usr/share/X11/xorg.conf.d/99-fbdev.conf` | Eliminado |
| Bloque en `~/.profile` | Extraído limpiamente línea por línea con `awk` |
| `/etc/sudoers.d/010_dragonfly` | Eliminado |
| Paquetes APT | **No eliminados** (por diseño) |

---

### Primer arranque tras la instalación

Tras completar las cuatro fases, se recomienda reiniciar:

```bash
sudo reboot
```

En el siguiente inicio, la secuencia completa es automática:

```
Encendido → Autologin en tty1 → .profile ejecuta startx
→ .xinitrc configura X11 + Openbox → raspi.py arranca en pantalla completa
```

El operador verá directamente la interfaz táctil de DragonFly sin ninguna interacción manual.

---

<div align="center">

## Instalación — `installers/install_desktop.sh`
### Edición de Escritorio — Multiplataforma

</div>

### Descripción General

Este instalador despliega `desktop.py` como una **aplicación de sistema** en cualquier distribución Linux de escritorio compatible. A diferencia de la edición Raspberry Pi (que opera en un entorno controlado con hardware fijo), la edición de escritorio está diseñada para ejecutarse en hardware heterogéneo, por lo que el instalador necesita gestionar gestores de paquetes y nombres de paquetes distintos según la distribución detectada.

El proceso instala la aplicación en `/opt/dragonfly_desktop/`, crea un entorno virtual Python aislado dentro de ese directorio (evitando conflictos con el Python del sistema) y registra un ejecutable global en `/usr/local/bin/dragonfly-gui`. A partir de ese momento, la herramienta puede lanzarse desde cualquier directorio con un único comando.

El instalador requiere privilegios de root:

```bash
sudo ./installers/install_desktop.sh
```

---

### Distribuciones soportadas

La autodetección de SO lee `/etc/os-release` y bifurca la instalación según el campo `$ID` o `$ID_LIKE`:

| Distribución / Familia | Gestor de paquetes |
|---|---|
| Kali Linux | `apt-get` |
| Parrot OS | `apt-get` |
| Debian | `apt-get` |
| Ubuntu (y derivados) | `apt-get` |
| Arch Linux | `pacman` |
| Manjaro | `pacman` |
| Fedora (y derivados) | `dnf` |

Si la distribución no encaja en ninguna de estas familias, el instalador muestra un mensaje de error y se detiene, solicitando al operador que instale las dependencias manualmente.

---

### Opciones del menú de instalación (`install_desktop.sh`)

| Opción | Descripción |
|---|---|
| **1) Instalar DragonFly Desktop** | Ejecuta el flujo completo: dependencias → copia de archivos → venv → ejecutable global. |
| **2) Desinstalar DragonFly Desktop** | Elimina `/opt/dragonfly_desktop` y el binario `/usr/local/bin/dragonfly-gui`. |
| **3) Salir** | Termina sin realizar cambios. |

---

### Flujo recomendado: Edición Desktop

La instalación completa se realiza con la opción `1` y comprende **cuatro fases internas** que se ejecutan en secuencia automática.

---

#### Fase 1 — Autodetección del sistema operativo e instalación de dependencias

El script lee `/etc/os-release` e invoca el gestor de paquetes correspondiente. El conjunto de paquetes equivalente es el mismo en todas las distribuciones, aunque los nombres varían:

**Paquetes instalados (nombres en Debian/Ubuntu/Kali):**
```
python3  python3-pip  python3-tk  python3-venv
nmap  macchanger  aircrack-ng  hostapd  dnsmasq
net-tools  iptables  bluez  x11-xserver-utils
```

**Equivalentes en Arch Linux:**
```
python  python-pip  tk
nmap  macchanger  aircrack-ng  hostapd  dnsmasq
net-tools  iptables-nft  bluez  bluez-utils  xorg-xhost
```

**Equivalentes en Fedora:**
```
python3  python3-pip  python3-tkinter
nmap  macchanger  aircrack-ng  hostapd  dnsmasq
net-tools  iptables  bluez  xhost
```

> **Nota sobre `python3-tk`:** en sistemas Debian/Ubuntu, el módulo `tkinter` es un paquete separado del intérprete Python. Su ausencia provoca un `ImportError` al iniciar `desktop.py` con un mensaje poco descriptivo. El instalador garantiza su presencia independientemente de la distribución.

---

#### Fase 2 — Copia de archivos al directorio de instalación

```
/opt/dragonfly_desktop/
```

El instalador crea este directorio si no existe y copia el contenido completo de la raíz del repositorio dentro de él mediante `cp -r`. Esto incluye `desktop.py`, `ducky_logic.py`, `gadget_handler.py`, la carpeta `payloads/`, `evil_portals/` y cualquier otro recurso presente en el proyecto.

La ruta de instalación `/opt/` es la ubicación estándar de FHS (Filesystem Hierarchy Standard) para aplicaciones de terceros que no son gestionadas por el gestor de paquetes del sistema, garantizando coexistencia sin interferir con el árbol de directorios del SO.

---

#### Fase 3 — Entorno Virtual Python (venv) y dependencias de Python

Dentro de `/opt/dragonfly_desktop/`, el instalador crea un entorno virtual Python aislado:

```bash
cd /opt/dragonfly_desktop
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install customtkinter
```

El uso de un `venv` dedicado ofrece tres ventajas críticas en el contexto de un escritorio de auditoría:

1. **Aislamiento total:** `customtkinter` y sus dependencias no contaminan el Python del sistema ni entran en conflicto con versiones instaladas vía APT/pacman.
2. **Portabilidad:** la instalación en `/opt/dragonfly_desktop/venv` es autocontenida. Si el operador actualiza el Python del sistema, la suite sigue funcionando desde su propio intérprete.
3. **Desinstalación limpia:** eliminar `/opt/dragonfly_desktop` borra también el venv completo sin dejar residuos en el sistema.

---

#### Fase 4 — Creación del ejecutable global `dragonfly-gui`

El instalador genera el script `/usr/local/bin/dragonfly-gui` y le otorga permisos de ejecución. Este script actúa como **wrapper de lanzamiento** y resuelve dos problemas habituales al ejecutar aplicaciones gráficas como root en sistemas modernos:

**Problema 1 — Display Wayland/X11 como root:**
En distribuciones modernas con Wayland o X11 con restricciones de Xauth, el usuario root no tiene permiso por defecto para abrir ventanas en el display del usuario que inició sesión. El wrapper resuelve esto con:

```bash
xhost +SI:localuser:root > /dev/null 2>&1
export DISPLAY=${DISPLAY:-:0}
```

`xhost +SI:localuser:root` añade a root a la lista de control de acceso del servidor X del display activo, sin abrir el acceso a todos los usuarios del sistema (que sería el caso de `xhost +`). La variable `${DISPLAY:-:0}` garantiza que, si `$DISPLAY` no está definida en el entorno de root (común al usar `sudo` sin `-E`), se use `:0` como fallback.

**Problema 2 — Activación del venv:**
El wrapper activa el entorno virtual antes de lanzar Python:

```bash
cd /opt/dragonfly_desktop
source venv/bin/activate
python3 desktop.py
```

**Limpieza post-cierre:**
Al terminar `desktop.py`, el wrapper revoca inmediatamente el permiso que había concedido a root:

```bash
xhost -SI:localuser:root > /dev/null 2>&1
```

Esto garantiza que la política de acceso al display queda exactamente como estaba antes de lanzar la herramienta, sin dejar permisos residuales.

**Uso tras la instalación:**

```bash
sudo dragonfly-gui
```

El binario está disponible en `$PATH` de forma global. No es necesario navegar al directorio del proyecto ni activar manualmente el venv.

---

#### Desinstalación (Opción 2)

```bash
sudo ./installers/install_desktop.sh
# → Seleccionar opción 2
```

El proceso elimina:

| Componente | Ruta |
|---|---|
| Directorio de instalación completo (incluyendo venv) | `/opt/dragonfly_desktop/` |
| Ejecutable global | `/usr/local/bin/dragonfly-gui` |
| Paquetes APT/pacman/dnf | **No eliminados** (por diseño) |

---

### Comparativa de arquitecturas de instalación

| Característica | `install_raspi.sh` | `install_desktop.sh` |
|---|---|---|
| Sistema operativo objetivo | Raspberry Pi OS Lite 32-bits (sin GUI) | Kali, Parrot, Debian, Ubuntu, Arch, Fedora |
| Motor gráfico | X11 + Openbox (construido por el instalador) | Entorno de escritorio existente del sistema |
| Arranque automático | Sí (autologin consola → startx → kiosco) | No (lanzamiento manual con `dragonfly-gui`) |
| Directorio de instalación | Ruta del repositorio (in-place) | `/opt/dragonfly_desktop/` (sistema) |
| Ejecutable global | No (lanzado por `.xinitrc`) | Sí (`/usr/local/bin/dragonfly-gui`) |
| Entorno Python | Python de sistema (APT) | venv aislado en `/opt/dragonfly_desktop/venv/` |
| Dependencias Python extra | `python3-netifaces`, `python3-aioquic` (APT) | `customtkinter` (pip, dentro del venv) |
| Responder | Instalado en `/opt/Responder/` | No incluido |
| USB Gadget HID | Configurado en `/usr/local/bin/usb_gadget.sh` | No aplicable |
| Desinstalación | Módular (por componentes individuales) | Completa (directorio + binario) |

---



<div align="center">



## Gadgets de Hardware — Firmware


</div>

La carpeta `gadgets/` contiene el firmware para extender las capacidades físicas del sistema más allá de lo que ofrece el software puro. Estos módulos de hardware se comunican con la aplicación principal a través del puerto serie USB y son gestionados por `gadget_handler.py`.

---

### Blue-Fly

**Archivo de firmware:** `BlueFly_Firmware.ino`
**Gestor de software:** `gadget_handler.py`

Blue-Fly es un gadget de interferencia y análisis de radiofrecuencia en la banda de 2.4 GHz, construido sobre un ESP32 con dos módulos nRF24L01 conectados a los buses VSPI y HSPI del microcontrolador. El firmware aprovecha la arquitectura dual-core del ESP32 para maximizar la cobertura espectral: Core 0 gestiona el módulo VSPI (comenzando en el canal 45) y Core 1 gestiona el módulo HSPI (comenzando en el canal 60) de forma completamente paralela e independiente.

#### Capacidades

- **Jammer de 2.4 GHz (Sweep Jam)**: los dos módulos nRF24L01 recorren los 84 canales de la banda de 2.4 GHz a máxima potencia (`RF24_PA_MAX`), tasa de datos de 2 Mbps y sin CRC, transmitiendo payloads de ruido de 5 bytes. La saturación simultánea desde dos módulos en canales complementarios maximiza la densidad de interferencia, afectando comunicaciones Wi-Fi, Bluetooth y Zigbee que operen en la misma banda.
- **Frequency Hopping**: un toggle switch físico conectado al GPIO 33 selecciona el modo de salto entre **SWEEP** (barrido secuencial) y **RANDOM** (salto aleatorio), sin necesidad de modificar el firmware ni reiniciar el dispositivo.
- **Control por duración**: el comando `SWEEP_JAM <modo> <segundos>` activa la interferencia durante un tiempo definido y la detiene automáticamente al expirar. Pasar `0` segundos activa el modo indefinido.
- **Pantalla OLED**: un display SSD1306 de 128x64 conectado por I2C muestra el estado del gadget (Iniciado / Detenido) con un indicador parpadeante durante la operación activa.
- **Protocolo serie**: la comunicación con el software anfitrión se realiza a 115200 baudios. Los comandos soportados son `SWEEP_JAM`, `STOP` y `STATUS`. El firmware responde con `JAMMING_STARTED`, `STOPPED`, `JAMMING_ACTIVE` o `JAMMING_INACTIVE` según corresponda.

El módulo `gadget_handler.py` gestiona la conexión serie con reconexión automática y hot-plugging. Al iniciar, espera la cadena `Gadget listo` que el firmware emite en `setup()`. Si el dispositivo se desconecta físicamente durante la sesión, el gestor detecta la ausencia del archivo de dispositivo en `/dev/` y limpia el estado de forma segura, permitiendo una reconexión posterior sin reiniciar la aplicación.

---


<div align="center">

<img src="images/blue-fly.png" alt="jammer" width="700" height="auto" />

</div>


---

### Pinout Físico — Blue-Fly



### HSPI

| 1st nRF24L01 module Pin | HSPI Pin (ESP32) | 10uf capacitor |
|---------------|------------------|--------------------|
| VCC           | 3.3V             | (+) capacitor |
| GND           | GND              | (-) capacitor |
| CE            | GPIO 16          |
| CSN           | GPIO 15          |
| SCK           | GPIO 14          |
| MOSI          | GPIO 13          |
| MISO          | GPIO 12          |
| IRQ           |                  |



### VSPI 



| 2nd nRF24L01 module Pin | VSPI Pin (ESP32) | 10uf capacitor |
|---------------|------------------|--------------------|
| VCC           | 3.3V             | (+) capacitor |
| GND           | GND              | (-) capacitor |
| CE            | GPIO 22          |
| CSN           | GPIO 21          |
| SCK           | GPIO 18          |
| MOSI          | GPIO 23          |
| MISO          | GPIO 19          |
| IRQ           |                  |



> Se recomienda colocar un condensador electrolítico de 100 µF entre VCC y GND en cada módulo nRF24L01 para estabilizar la alimentación durante los picos de transmisión a máxima potencia. La ausencia de este condensador puede causar reinicios inesperados del ESP32 o comportamiento errático de los módulos de radio.

### OLED Display I2C 



| 0.96" OLED Display I2C | ESP32 |
|------------------------|-------|
|          GND           |  GND  |
|          VCC           | 3.3V  |
|          SCL           |GPIO 5 |
|          SDA           |GPIO 4 |


---

<div align="center">

## Estructura del Repositorio

</div>

```text
DragonFly/
├── LICENSE
├── README.md
├── desktop.py              # Interfaz desktop multiplataforma
├── raspi.py                # Interfaz táctil para Raspberry Pi
├── evil_portals/           # Portales cautivos HTML
│   ├── portal_01/
│   │   └── index.html
│   └── portal_02/
│       └── index.html
├── gadgets/                # Firmware para hardware externo
│   └── BlueFly_Firmware.ino
├── icons/                  # Iconos para la interfaz gráfica
│   ├── destroy.png
│   ├── ducky.png
│   ├── jammer.png
│   ├── mac.png
│   ├── poison.png
│   ├── recon.png
│   ├── utils.png
│   └── wifi.png
├── installers/             # Instaladores automatizados
│   ├── install_desktop.sh
│   └── install_raspi.sh
├── modules/                # Lógica central e integraciones backend
│   ├── __init__.py
│   ├── ducky_logic.py      # Motor de inyección HID Rubber Ducky
│   ├── gadget_handler.py   # Gestor de comunicación serie con ESP32
│   └── poison_logic.py     # Lógica de intercepción de red
└── payloads/               # Scripts Rubber Ducky (.txt)
    ├── auditoria.txt
    ├── cmatrix_flood.txt
    ├── prueba_teclas.txt
    ├── rickroll.txt
    ├── windows_fake_update.txt
    ├── windows_rickroll.txt
    └── windows_tts.txt
```

---

<div align="center">


## Top de contribuidores

</div>

<div align="center">

<a href="https://github.com/whoamijas0n/DragonFly/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=whoamijas0n/DragonFly" alt="contrib.rocks image" />
</a>

</div>

---


<div align="center">

## Advertencia Legal:


</div>

DragonFly ha sido desarrollado exclusivamente con fines educativos y para la realización de auditorías de seguridad autorizadas por escrito. El uso de esta herramienta contra sistemas o redes sin el consentimiento explícito del propietario constituye una violación de las leyes de ciberseguridad en la mayoría de jurisdicciones. Los desarrolladores no asumen responsabilidad por el mal uso de este software. La ética profesional y el cumplimiento normativo son responsabilidad exclusiva del operador.

---

<div align="center">

## Licencia

</div>

Este proyecto se distribuye bajo los términos de la licencia MIT. Consulta el archivo `LICENSE` en la raíz del repositorio para más información.

---
