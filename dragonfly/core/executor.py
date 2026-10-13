"""
dragonfly/core/executor.py - Ejecutor asíncrono y síncrono de comandos de sistema.
Aísla la interacción con el sistema operativo y gestiona el streaming hacia la interfaz gráfica.
"""

import subprocess
import threading
import os
import signal


class CommandExecutor:
    """
    Ejecuta comandos del sistema de forma síncrona o asíncrona en hilos dedicados.
    Permite streaming de salida línea por línea y cancelación forzosa segura.
    """

    def __init__(self):
        self._active_proc = None
        self._lock = threading.Lock()
        self._is_running = False

    @property
    def is_running(self):
        with self._lock:
            return self._is_running

    def run_async(self, comando, on_output=None, on_finish=None, use_shell=True):
        """
        Lanza un comando en un hilo en segundo plano (daemon).
        :param comando: String o lista de argumentos.
        :param on_output: Callback (texto: str) para cada línea generada.
        :param on_finish: Callback (returncode: int) invocado al finalizar.
        :param use_shell: Booleano para usar intérprete de comandos shell.
        :return: El objeto threading.Thread iniciado.
        """
        def worker():
            with self._lock:
                self._is_running = True

            cmd_display = comando if isinstance(comando, str) else " ".join(comando)
            if on_output:
                on_output(f"\nroot@dragonfly:~# {cmd_display}")

            proc = None
            try:
                proc = subprocess.Popen(
                    comando,
                    shell=use_shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid if os.name == 'posix' else None
                )

                with self._lock:
                    self._active_proc = proc

                # Lectura línea a línea en tiempo real
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        cleaned = line.rstrip()
                        if on_output:
                            on_output(cleaned)

                proc.stdout.close()
                returncode = proc.wait()

                if on_output:
                    on_output("\n[+] Tarea finalizada.")

                if on_finish:
                    on_finish(returncode)

            except Exception as e:
                if on_output:
                    on_output(f"\n[!] ERROR de ejecución: {e}")
                if on_finish:
                    on_finish(-1)
            finally:
                with self._lock:
                    self._active_proc = None
                    self._is_running = False

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def stop_current(self):
        """
        Detiene forzosamente el proceso actualmente en ejecución y su grupo de procesos.
        """
        with self._lock:
            proc = self._active_proc

        if proc is not None:
            try:
                if os.name == 'posix':
                    # Matar grupo de procesos para asegurar que hijos mueran
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.terminate()
                proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
                try:
                    if os.name == 'posix':
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    else:
                        proc.kill()
                except Exception:
                    pass

    def run_sync(self, comando, use_shell=True, timeout=None):
        """
        Ejecuta un comando de forma bloqueante y retorna (stdout, stderr, returncode).
        """
        try:
            res = subprocess.run(
                comando,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return res.stdout, res.stderr, res.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout expired", -1
        except Exception as e:
            return "", str(e), -1
