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


## Instalación — `install.sh`

</div>

### Clonar el repositorio

```bash
git clone https://github.com/whoamijas0n/DragonFly.git
cd DragonFly
sudo ./install.sh
```

El script requiere privilegios de root. Si se ejecuta con `sudo`, detecta automáticamente el usuario real mediante `$SUDO_USER` para aplicar la configuración de autostart en el directorio home correcto.

### Opciones del menú de instalación


| Opción | Descripción |
|---|---|
| 1) Instalación Completa | Ejecuta las tres fases en secuencia (Todo-en-Uno) |
| 2) Solo Dependencias | Instala paquetes APT y librerías Python |
| 3) Solo USB Gadget | Configura el script HID en `/usr/local/bin/usb_gadget.sh` |
| 4) Solo Auto-Inicio | Crea la entrada `.desktop` de autostart y regla sudoers |
| 5) Salir | Termina sin realizar cambios |


---

### Flujo recomendado: Edición Raspberry Pi

La instalación para la Pi Zero 2 W requiere las tres fases. Se recomienda ejecutarlas en el orden que ofrece la opción 1 (Todo-en-Uno) o manualmente en este orden:

**Paso 1 — Dependencias (Opción 2)**

Instala todos los paquetes de sistema necesarios:

```
python3, python3-tk, python3-serial
nmap, macchanger, aircrack-ng, hostapd, dnsmasq, iptables
network-manager, bluez, rfkill, lxterminal
```

**Paso 2 — USB Gadget (Opción 3)**

Crea el script `/usr/local/bin/usb_gadget.sh` que configura el descriptor HID de teclado en el subsistema `configfs` del kernel (`/sys/kernel/config/usb_gadget/g1`). El descriptor reporta al host anfitrión como un teclado HID estándar con report length de 8 bytes y el descriptor HID completo embebido. Este script debe ejecutarse antes de iniciar `raspi.py` para que `/dev/hidg0` esté disponible.

**Paso 3 — Auto-Inicio (Opción 4)**

Crea la entrada `~/.config/autostart/raspy.desktop` para que LXDE/Openbox lance automáticamente `raspi.py` al iniciar el entorno gráfico, dentro de un terminal `lxterminal` con permisos sudo. Además, añade una regla `NOPASSWD` en `/etc/sudoers.d/010_dragonfly` para que el script pueda ejecutar comandos privilegiados sin solicitar contraseña, requisito indispensable para las funciones de red y HID.

Tras completar las tres fases, se recomienda reiniciar la Raspberry Pi para que todos los módulos del kernel y la configuración de autostart tomen efecto.

---

### Flujo recomendado: Edición Desktop

Para laptops con Kali Linux, solo es necesaria la opción de dependencias:

**Paso 1 — Dependencias (Opción 2)**

El proceso es idéntico al descrito para Raspi. Una vez completado, la herramienta se lanza manualmente:

```bash
cd DragonFly
sudo python3 desktop.py
```

No se configura autostart ni USB Gadget, ya que los portátiles estándar no disponen del controlador USB OTG necesario para emular un dispositivo HID. Si el operador dispone de un adaptador USB HID externo compatible, puede configurar el gadget manualmente y ajustar la variable `HID_DEVICE` en `ducky_logic.py` si la ruta del dispositivo difiere de `/dev/hidg0`.

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

```
DragonFly/
├── raspi.py                # Interfaz táctil para Raspberry Pi
├── desktop.py              # Interfaz desktop para Kali Linux
├── ducky_logic.py          # Motor de inyección HID Rubber Ducky
├── gadget_handler.py       # Gestor de comunicación serie con ESP32
├── install.sh              # Instalador automatizado
├── payloads/               # Scripts Rubber Ducky (.txt)
├── evil_portals/           # Portales cautivos HTML
│   ├── portal_01/
│   │   └── index.html
│   └── portal_02/
│       └── index.html
└── gadgets/
    └── BlueFly_Firmware.ino
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
