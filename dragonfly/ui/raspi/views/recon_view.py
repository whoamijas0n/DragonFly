"""
dragonfly/ui/raspi/views/recon_view.py - Vista de escaneo con Nmap para Raspberry Pi.
Utiliza TecladoNumerico táctil para ingresar la IP en la pantalla de 320x240.
"""

import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame, TecladoNumerico
from dragonfly.config import NMAP_PROFILES, BASE_DIR_NMAP


class ReconView(BaseView):
    """
    Controlador y vista para escaneos de red Nmap con interfaz táctil en Raspberry Pi.
    """

    def __init__(self, app):
        super().__init__(app)
        self.target_ip_var = tk.StringVar(value="127.0.0.1")
        self.usar_rango_var = tk.BooleanVar(value=False)
        self.rango_cidr_var = tk.StringVar(value="/24")
        self.scan_buttons = []
        self.btn_detener = None
        # Bandera atómica anti-doble-tap: impide escaneos Nmap simultáneos
        self.is_scanning = False

    def render(self):
        """Dibuja el menú de Nmap."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="RECONOCIMIENTO (NMAP)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        # Entrada de IP con botón de teclado numérico emergente
        ip_frame = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        ip_frame.pack(fill='x', padx=10, pady=3)

        ttk.Label(ip_frame, text="IP: ", style='Dark.TLabel').pack(side='left')
        ent_ip = ttk.Entry(ip_frame, textvariable=self.target_ip_var, width=15, style='Dark.TEntry')
        ent_ip.pack(side='left', padx=2)

        def abrir_teclado():
            t = TecladoNumerico(self.app, self.target_ip_var)
            self.app.wait_window(t)

        ttk.Button(ip_frame, text="⌨", width=3, style='Gray.TButton', command=abrir_teclado).pack(side='left', padx=2)

        # Rango CIDR
        rango_frame = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        rango_frame.pack(fill='x', padx=10, pady=2)

        ttk.Checkbutton(rango_frame, text="Rango", variable=self.usar_rango_var).pack(side='left')
        ttk.OptionMenu(rango_frame, self.rango_cidr_var, self.rango_cidr_var.get(),
                       "/24", "/16", "/8", "/32", style='Dark.TMenubutton').pack(side='left', padx=4)

        self.scan_buttons = []
        # Botones de Nmap
        for i, (nombre, _) in enumerate(NMAP_PROFILES):
            btn = scroll.add_button(
                text=nombre,
                command=lambda idx=i: self._on_execute_scan(idx),
                style='Red.TButton',
                width=28
            )
            self.scan_buttons.append(btn)

        # Botón Detener (inicia bloqueado hasta que haya un escaneo en curso)
        self.btn_detener = scroll.add_button(
            text="DETENER ESCANEO",
            command=self._on_stop_scan,
            style='Gray.TButton',
            width=28
        )
        if self.btn_detener:
            self.btn_detener.state(['disabled'])

        # Botón Explorar
        scroll.add_button(
            text="Ver Resultados Guardados",
            command=lambda: self.app.views['explorer'].show_sessions(BASE_DIR_NMAP, "Resultados Nmap", self.render),
            style='Gray.TButton',
            width=28
        )

        self.show_console(parent=scroll.scrollable_frame)

        # Si se vuelve a entrar a la vista con un escaneo activo, reflejar el bloqueo
        if self.is_scanning:
            self._apply_scanning_state(True)

        if self.target_ip_var.get() == "127.0.0.1":
            ip_auto = self.services.recon.get_auto_ip()
            if ip_auto != "127.0.0.1":
                self.target_ip_var.set(ip_auto)
                self.write_console(f"[*] IP detectada: {ip_auto}")

    def _apply_scanning_state(self, scanning: bool):
        """
        Bloquea o restaura los botones de escaneo y el botón Detener.
        Usa btn.state([...]) (no configure(state=...)) para bloquear de forma
        consistente los eventos táctiles en los estilos ttk planos.
        """
        for btn in self.scan_buttons:
            if btn and btn.winfo_exists():
                if scanning:
                    btn.config(style='Gray.TButton')
                    btn.state(['disabled'])
                else:
                    btn.config(style='Red.TButton')
                    btn.state(['!disabled'])
        if self.btn_detener and self.btn_detener.winfo_exists():
            if scanning:
                self.btn_detener.config(style='Danger.TButton')
                self.btn_detener.state(['!disabled'])
            else:
                self.btn_detener.config(style='Gray.TButton')
                self.btn_detener.state(['disabled'])

    def _on_execute_scan(self, profile_index: int):
        # Guarda contra eventos táctiles en cola: sin ella se lanzan múltiples
        # instancias de Nmap simultáneas que saturan la RAM (512MB) de la Zero 2 WH.
        if self.is_scanning:
            self.write_console("[!] Ya hay un escaneo en curso.")
            return

        target = self.services.recon.format_target(
            self.target_ip_var.get(),
            self.usar_rango_var.get(),
            self.rango_cidr_var.get()
        )
        if not target:
            self.write_console("[!] Target inválido.")
            return

        self.is_scanning = True
        self._apply_scanning_state(True)

        def on_finish(rc):
            def restore():
                self.is_scanning = False
                self._apply_scanning_state(False)
            self.run_on_ui(restore)

        self.services.recon.start_scan(
            target=target,
            profile_index=profile_index,
            on_output=self.write_console,
            on_finish=on_finish
        )

    def _on_stop_scan(self):
        # Deshabilitar al instante para evitar doble pulsación; el on_finish del
        # escaneo restaurará los botones cuando el proceso muera (pkill).
        if self.btn_detener and self.btn_detener.winfo_exists():
            self.btn_detener.config(style='Gray.TButton')
            self.btn_detener.state(['disabled'])
        self.services.recon.stop_scan(on_output=self.write_console)
