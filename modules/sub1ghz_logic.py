import os
import threading
import time
from datetime import datetime

import serial
import serial.tools.list_ports


class Sub1GHzController:
    """
    Maneja la conexión serie con el ESP32 (firmware SubGHz_Firmware.ino).
    Inicia un hilo lector en segundo plano y ofrece métodos para comandos RF.
    """

    # Posibles pares VID:PID de adaptadores USB-Serie comunes en ESP32
    _KNOWN_VID_PID = [
        (0x10C4, 0xEA60),  # Silabs CP210x
        (0x1A86, 0x7523),  # Qinheng CH340
        (0x0403, 0x6001),  # FTDI FT232
    ]

    def __init__(self, port=None, baudrate=115200, callback=None):
        """
        :param port:     Puerto serie (ej. '/dev/ttyUSB0'). None -> autodetección.
        :param baudrate: Velocidad en baudios (por defecto 115200).
        :param callback: Función a la que se pasan mensajes de log (se llamará desde el hilo lector).
        """
        self.baudrate = baudrate
        self.callback = callback
        self.ser = None
        self.running = False
        self.reader_thread = None

        # Autodetectar puerto si no se especifica
        if port is None:
            port = self._detect_esp32_port()

        if port is None:
            self._log("[!] No se detectó ningún adaptador serie USB compatible.")
            return

        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            # Pequeña pausa para que el ESP32 termine de iniciar
            time.sleep(1.0)
            self._log(f"[+] Conectado al ESP32 en {port}")
        except serial.SerialException as e:
            self._log(f"[!] Error al abrir {port}: {e}")
            self.ser = None
            return

        # Iniciar hilo lector
        self.running = True
        self.reader_thread = threading.Thread(target=self._read_serial, daemon=True)
        self.reader_thread.start()

    # ------------------------------------------------------------------
    # Autodetección inteligente del puerto
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_esp32_port():
        """Busca un puerto serie que parezca un ESP32."""
        ports = serial.tools.list_ports.comports()
        # Prioridad: primero ttyUSB, luego ttyACM, luego por VID/PID
        for p in ports:
            if 'ttyUSB' in p.device or 'ttyACM' in p.device:
                return p.device

        for p in ports:
            if p.vid is not None and p.pid is not None:
                if (p.vid, p.pid) in Sub1GHzController._KNOWN_VID_PID:
                    return p.device

        return None

    # ------------------------------------------------------------------
    # Hilo de lectura continua del puerto serie
    # ------------------------------------------------------------------
    def _read_serial(self):
        """Lee líneas del ESP32 y procesa tramas DATA:HEX:."""
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting == 0:
                    time.sleep(0.05)
                    continue

                line = self.ser.readline()
                if not line:
                    continue

                line_str = line.decode('utf-8', errors='replace').strip()
                if not line_str:
                    continue

                # Mostrar siempre lo que llega (útil para depuración)
                self._log(f"[ESP32] {line_str}")

                # Procesar tramas de datos capturados
                if line_str.startswith("DATA:HEX:"):
                    parts = line_str.split(':', 2)
                    if len(parts) >= 3:
                        hex_code = parts[2].strip()
                        self._save_capture(hex_code)

            except (serial.SerialException, OSError) as e:
                self._log(f"[!] Error lectura serie: {e}")
                time.sleep(1)  # esperar antes de reintentar
            except Exception as e:
                self._log(f"[!] Excepción en hilo lector: {e}")

        self._log("[*] Hilo lector terminado.")

    # ------------------------------------------------------------------
    # Guardado de capturas en Resultados_RF/
    # ------------------------------------------------------------------
    def _save_capture(self, hex_data):
        """Guarda el código hexadecimal en un archivo con marca de tiempo."""
        try:
            os.makedirs("Resultados_RF", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Capturas-{timestamp}.txt"
            filepath = os.path.join("Resultados_RF", filename)
            with open(filepath, "w") as f:
                f.write(hex_data + "\n")
            self._log(f"[✓] Código guardado en {filepath}")
        except Exception as e:
            self._log(f"[!] Error al guardar captura: {e}")

    # ------------------------------------------------------------------
    # Envío de comandos al ESP32
    # ------------------------------------------------------------------
    def _send(self, cmd):
        """Envía una línea de comando (sin \n, se añade aquí)."""
        if not self.ser or not self.ser.is_open:
            self._log("[!] Puerto serie no disponible.")
            return
        try:
            self.ser.write((cmd + "\n").encode('utf-8'))
            self.ser.flush()
            self._log(f"[CMD] {cmd}")
        except serial.SerialException as e:
            self._log(f"[!] Error al enviar '{cmd}': {e}")

    def start_sniff(self):
        self._send("CMD:SNIFF:433")

    def start_jam(self, duration=10):
        self._send(f"CMD:JAM:433:{duration}")

    def start_rolljam(self):
        self._send("CMD:ROLLJAM:START")

    def stop_all(self):
        self._send("CMD:STOP")

    # ------------------------------------------------------------------
    # Cierre limpio
    # ------------------------------------------------------------------
    def close(self):
        """Detiene el hilo lector y cierra el puerto."""
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                self._log("[*] Puerto serie cerrado.")
            except Exception as e:
                self._log(f"[!] Error al cerrar puerto: {e}")

    # ------------------------------------------------------------------
    # Utilidad de logging interna
    # ------------------------------------------------------------------
    def _log(self, message):
        if self.callback:
            try:
                self.callback(message)
            except Exception:
                pass
        else:
            print(message)


# Pequeña prueba autónoma (ejecutar directamente si se desea)
if __name__ == "__main__":
    def print_cb(msg):
        print(f"UI: {msg}")

    ctrl = Sub1GHzController(callback=print_cb)
    if ctrl.ser is None:
        print("No se pudo conectar.")
        exit(1)

    print("Enviando sniff...")
    ctrl.start_sniff()
    time.sleep(3)
    ctrl.stop_all()
    ctrl.close()
