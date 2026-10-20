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
        """
        Abre el puerto y sincroniza con el firmware (soporte hot-plug).

        Nota de oro: NO se declara "listo" por texto de arranque del ESP32
        (spam del bootloader, mensajes de radios o pretty-details). El pulso
        DTR/RTS al abrir el puerto reinicia el chip (~2.5-4.5 s de boot), por
        lo que la única prueba válida de vida es una respuesta real a STATUS.
        """
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

            if not self._sync_with_firmware(window=7.0):
                self._handle_disconnect()
                return False

            self._ser.timeout = self.timeout
            try:
                self._ser.reset_input_buffer()
            except Exception:
                pass
            self._available = True
            return True

        except Exception:
            self._handle_disconnect()
            return False

    def _sync_with_firmware(self, window=7.0) -> bool:
        """
        Ventana de sincronización estricta con el ESP32.

        Consulta STATUS cada 400 ms e ignora TODO el spam de arranque
        (ROM, 'VSPI/HSPI Started', printPrettyDetails, errores no fatales).
        Solo aprueba como listo:
          1. Una respuesta real 'JAMMING_*' (el firmware está en loop()).
          2. 'Gadget listo' confirmado con un round-trip STATUS inmediato.
        La ventana cubre el reinicio del ESP32 provocado por el pulso
        DTR/RTS al abrir el puerto por primera vez.
        """
        start = time.time()
        last_status_time = 0
        listo_candidato = False

        while time.time() - start < window:
            now = time.time()

            # Emitir consulta STATUS periódicamente (o inmediata tras 'Gadget listo')
            if listo_candidato or (now - last_status_time >= 0.4):
                try:
                    self._ser.write(b"STATUS\n")
                    self._ser.flush()
                except Exception:
                    return False
                last_status_time = now
                listo_candidato = False

            try:
                line = self._ser.readline().decode(errors='ignore').strip()
            except Exception:
                return False

            if not line:
                continue

            # 1. Respuesta real del firmware: prueba de vida y de loop()
            if line.startswith("JAMMING_"):
                return True

            # 2. Fin de setup(): candidato, pero exige verificación real
            if "Gadget listo" in line:
                listo_candidato = True
                continue

            # 3. Cualquier otra línea (spam de arranque, ERROR no fatal):
            #    ignorada a propósito; seguimos esperando una prueba real.

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

    def _flush_input(self):
        """Descarta lecturas residuales (spam de arranque, respuestas viejas)."""
        if not self.is_available():
            return
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass

    def _wait_for_ack(self, expected_prefix, timeout_secs=5):
        start = time.time()
        while time.time() - start < timeout_secs:
            line = self._read_line()
            if line.startswith(expected_prefix):
                return True
        return False

    def ping(self, timeout_secs=1.5) -> bool:
        """
        Round-trip STATUS real: True solo si el firmware responde 'JAMMING_*'.
        Verificación ligera de vida del enlace (para validar handles previos).
        """
        if not self.is_available():
            return False
        try:
            with self._lock:
                self._ser.reset_input_buffer()
                self._ser.timeout = 0.25
                self._ser.write(b"STATUS\n")
                self._ser.flush()
            start = time.time()
            while time.time() - start < timeout_secs:
                try:
                    line = self._ser.readline().decode(errors='ignore').strip()
                except (serial.SerialException, OSError):
                    self._handle_disconnect()
                    return False
                if line.startswith("JAMMING_"):
                    return True
            return False
        except Exception:
            self._handle_disconnect()
            return False
        finally:
            try:
                if self._ser and self._ser.is_open:
                    self._ser.timeout = self.timeout
            except Exception:
                pass

    def sweep_jam(self, module: int, duration_sec: int):
        """
        Envía SWEEP_JAM y espera el ACK 'JAMMING_STARTED'.

        Reintenta una vez tras descartar residuos: cubre ACKs perdidos por
        reinicios del ESP32 (picos de corriente al arrancar la RF/brownout)
        o respuestas que quedaron en el búfer.
        """
        cmd = f"SWEEP_JAM {module} {duration_sec}"
        for _ in range(2):
            try:
                self._flush_input()
                self._send_command(cmd)
            except RuntimeError:
                return False
            if self._wait_for_ack("JAMMING_STARTED", 3):
                return True
        return False

    def stop(self, module: int):
        try:
            if not self.is_available(): return
            if module in self._stop_events:
                self._stop_events[module].set()
                self._send_command(f"STOP {module}")
            else:
                self._flush_input()
                self._send_command(f"STOP {module}")
                return self._wait_for_ack("STOPPED", 2)
        except RuntimeError:
            pass

    def status(self) -> str:
        """Consulta STATUS esperando una respuesta 'JAMMING_*' real."""
        try:
            self._flush_input()
            self._send_command("STATUS")
            start = time.time()
            while time.time() - start < 2.0:
                line = self._read_line()
                if line.startswith("JAMMING_"):
                    return line
            return "ERROR: sin respuesta"
        except RuntimeError:
            return "ERROR: Gadget desconectado"

    def close(self):
        self._available = False
        for ev in list(self._stop_events.values()): ev.set()
        self._handle_disconnect()
