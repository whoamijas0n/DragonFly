"""
dragonfly/core/subprocess_utils.py - Lanzamiento seguro de subprocesos y señales de job control.

Todos los comandos externos se lanzan sin terminal de control (stdin cerrado y sesión
propia). De este modo ningún hijo puede leer del TTY ni arrastrar a la aplicación a una
parada por SIGTTIN/SIGTTOU cuando sudo reenvía señales a su grupo de procesos.
"""

import os
import signal
import subprocess


def ignore_job_control_signals():
    """
    Ignora SIGTTIN/SIGTTOU para que la aplicación nunca se detenga por usar el TTY.

    En Raspberry Pi la app corre como root en una consola virtual; sudo con ``use_pty``
    puede reenviar estas señales al grupo de procesos de Python y congelar la interfaz.
    Ignorarlas es inofensivo para Tkinter.
    """
    for name in ("SIGTTIN", "SIGTTOU"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (OSError, ValueError):
            pass


def _with_safe_defaults(kwargs):
    """Añade stdin cerrado y sesión propia salvo que el llamador indique otra cosa."""
    safe = dict(kwargs)
    safe.setdefault("stdin", subprocess.DEVNULL)
    if os.name == "posix":
        # start_new_session crea grupo y sesión nuevos: un killpg sobre el hijo jamás
        # alcanza a la aplicación y sudo no puede reenviarle señales de terminal.
        safe.setdefault("start_new_session", True)
    return safe


def safe_popen(args, **kwargs):
    """subprocess.Popen sin terminal de control."""
    return subprocess.Popen(args, **_with_safe_defaults(kwargs))


def safe_run(args, **kwargs):
    """subprocess.run sin terminal de control."""
    return subprocess.run(args, **_with_safe_defaults(kwargs))


def safe_check_output(args, **kwargs):
    """subprocess.check_output sin terminal de control."""
    return subprocess.check_output(args, **_with_safe_defaults(kwargs))


def signal_process_group(proc, sig):
    """
    Envía ``sig`` al grupo del proceso indicado.

    Nunca señaliza el grupo propio: si el hijo quedó en nuestro grupo (por ejemplo un
    Popen antiguo sin sesión nueva) se le envía la señal solo a él para no congelar la app.
    """
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        pass

    if os.name == "posix":
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, PermissionError, OSError):
            pgid = None
        if pgid is not None and pgid != os.getpgrp():
            try:
                os.killpg(pgid, sig)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass

    try:
        proc.send_signal(sig)
    except (ProcessLookupError, ValueError, OSError):
        pass


def terminate_process_group(proc, timeout=3):
    """Termina el proceso y su grupo con SIGTERM y, si no responde, con SIGKILL."""
    if proc is None:
        return
    signal_process_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        return

    signal_process_group(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=1)
    except Exception:
        pass
