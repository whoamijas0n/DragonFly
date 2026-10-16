import serial
import serial.tools.list_ports
import threading
import time
import glob
import os

class BLEGadget:
    """Encapsula la conexión serie con el gadget BLE (ESP32). Soporta reconexión segura y hot-plugging."""
    _CANDIDATE_PATTERNS = ['/dev/ttyUSB*', '/dev/ttyACM*']

    def __init__(self, baudrate=115200, timeout=2):
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser = None
        self._available = False
        self._lock = threading.Lock()
        self._stop_events = {}
        self._scan_threads = {}
        self._port = None
        self.connect()

    def _handle_disconnect(self):
        """Limpia el estado y cierra el puerto fantasma de forma segura."""
        self._available = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def _auto_detect_port(self, retries=4, delay=0.35):
        """
        Escanea puertos serie con reintentos para tolerar el retardo de enumeración
        del kernel (udev) cuando el ESP32 se conecta en caliente.
        """
        candidate_hints = [
            'cp210', 'ch340', 'ch341', 'ch910', 'usb2.0-serial', 'usb serial',
            'usb uart', 'ft232', 'ftdi', 'espressif', 'esp32', 'single serial',
            'cdc'
        ]

        for attempt in range(retries):
            # 1. Búsqueda por descriptores USB mediante comports()
            try:
                ports = list(serial.tools.list_ports.comports())
                for p in ports:
                    desc = f"{p.description or ''} {p.manufacturer or ''}".lower()
                    if any(hint in desc for hint in candidate_hints):
                        if os.path.exists(p.device):
                            return p.device
            except Exception:
                pass

            # 2. Búsqueda directa por patrones en /dev/
            for pattern in self._CANDIDATE_PATTERNS:
                candidates = sorted(glob.glob(pattern))
                for cand in candidates:
                    if os.path.exists(cand):
                        return cand

            if attempt < retries - 1:
                time.sleep(delay)

        return None

    def connect(self):
        """Intenta abrir el puerto y sincronizar con el ESP32 (Soporte Hot-Plug)."""
        self._handle_disconnect() # Limpieza previa garantizada
        self._port = self._auto_detect_port(retries=4, delay=0.35)
        if not self._port:
            return False

        try:
            self._ser = serial.Serial()
            self._ser.port = self._port
            self._ser.baudrate = self.baudrate
            self._ser.timeout = 0.2  # Timeout corto no bloqueante para sondeo continuo
            self._ser.write_timeout = 1

            self._ser.dtr = False
            self._ser.rts = False

            self._ser.open()

            # Estabilización breve del canal UART tras apertura
            time.sleep(0.2)
            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
            except Exception:
                pass

            start = time.time()
            ready = False
            last_status_time = 0

            # Ventana de sincronización de 4.5 segundos:
            # Tolera tanto el reboot del ESP32 por DTR/RTS (~2.5s) como el caso
            # donde ya estaba encendido y responde a STATUS periódicamente.
            while time.time() - start < 4.5:
                now = time.time()

                # Emitir consulta STATUS cada 500ms para capturar al ESP32 tan pronto entra a loop()
                if now - last_status_time >= 0.5:
                    try:
                        self._ser.write(b"STATUS\n")
                        self._ser.flush()
                        last_status_time = now
                    except Exception:
                        pass

                try:
                    line = self._ser.readline().decode(errors='ignore').strip()
                    if line:
                        # 1. Señal de arranque del firmware Blue-Fly
                        if "Gadget listo" in line:
                            ready = True
                            break
                        # 2. Respuestas al comando STATUS
                        if "JAMMING_" in line or "JAM" in line or "IDLE" in line:
                            ready = True
                            break
                        # 3. Confirmación de inicio de radios
                        if "VSPI Started" in line or "HSPI Started" in line:
                            # Gadget en fase de arranque; continuamos el ciclo
                            pass
                        # 4. Cualquier respuesta sustancial no errónea
                        elif len(line) > 2 and "Unknown command" not in line and "STATUS" not in line and not line.startswith("ERROR:"):
                            ready = True
                            break
                except Exception:
                    break

                time.sleep(0.05)

            if not ready:
                # Intento final de sondeo directo tras completar la ventana
                try:
                    self._ser.reset_input_buffer()
                    self._ser.write(b"STATUS\n")
                    self._ser.flush()
                    time.sleep(0.25)
                    resp = self._ser.readline().decode(errors='ignore').strip()
                    if "JAM" in resp or "IDLE" in resp or "Gadget" in resp or len(resp) > 2:
                        ready = True
                except Exception:
                    pass

            if ready:
                self._ser.timeout = self.timeout
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass
                self._available = True
                return True
            else:
                self._handle_disconnect()
                return False

        except Exception:
            self._handle_disconnect()
            return False

    def reconnect(self):
        """Cierra conexión actual e intenta reconectar."""
        return self.connect()

    def is_available(self) -> bool:
        """Verifica el estado del objeto y la existencia física del dispositivo."""
        try:
            if not (self._available and self._ser is not None and self._ser.is_open):
                return False
            # Magia para evitar bloqueos: verificar en el SO si el archivo USB existe
            if self._port and not os.path.exists(self._port):
                self._handle_disconnect()
                return False
            return True
        except:
            return False

    @property
    def is_connected(self) -> bool:
        """Alias compatible para is_available."""
        return self.is_available()

    @property
    def port(self) -> str:
        """Retorna el puerto serie asignado al dispositivo."""
        return self._port

    def _send_command(self, cmd: str):
        if not self.is_available():
            raise RuntimeError("Gadget desconectado.")
        with self._lock:
            try:
                self._ser.write((cmd + "\n").encode())
                self._ser.flush()
            except (serial.SerialException, OSError) as e:
                self._handle_disconnect()
                raise RuntimeError(f"Desconexión abrupta del USB: {e}")

    def _read_line(self):
        if not self.is_available(): return ""
        try:
            line = self._ser.readline().decode(errors='ignore').strip()
        except (serial.SerialException, OSError):
            self._handle_disconnect()
            return ""
        return line

    def _wait_for_ack(self, expected_prefix, timeout_secs=5):
        start = time.time()
        while time.time() - start < timeout_secs:
            line = self._read_line()
            if line.startswith(expected_prefix):
                return True
        return False

    def sweep_jam(self, module: int, duration_sec: int):
        try:
            self._send_command(f"SWEEP_JAM {module} {duration_sec}")
            return self._wait_for_ack("JAMMING_STARTED", 3)
        except RuntimeError:
            return False

    def stop(self, module: int):
        try:
            if not self.is_available(): return
            if module in self._stop_events:
                self._stop_events[module].set()
                self._send_command(f"STOP {module}")
            else:
                self._send_command(f"STOP {module}")
                return self._wait_for_ack("STOPPED", 2)
        except RuntimeError:
            pass

    def status(self) -> str:
        try:
            self._send_command("STATUS")
            line = self._read_line()
            return line if line else "ERROR: sin respuesta"
        except RuntimeError:
            return "ERROR: Gadget desconectado"

    def close(self):
        self._available = False
        for ev in list(self._stop_events.values()): ev.set()
        self._handle_disconnect()
