"""
dragonfly/ui/raspi/views/ducky_view.py - Vista de inyección HID Rubber Ducky para Raspberry Pi.
Permite seleccionar payloads desde payloads/ y ejecutarlos emulando un teclado USB (/dev/hidg0).
"""

import threading
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.views.base_view import BaseView
from dragonfly.ui.raspi.widgets import ScrollableFrame


class DuckyView(BaseView):
    """
    Vista táctil para ejecución de Rubber Ducky en la Raspberry Pi Zero 2 WH.
    """

    def __init__(self, app):
        super().__init__(app)
        self.layout_var = tk.StringVar(value="ES")
        self.payload_buttons = []
        self.btn_detener_ducky = None

    def render(self):
        """Lista los payloads disponibles y la opción de layout."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ttk.Label(self.main_frame, text="RUBBER DUCKY (HID)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        # Selección de Layout
        lay_frame = ttk.Frame(scroll.scrollable_frame, style='Dark.TFrame')
        lay_frame.pack(fill='x', padx=10, pady=2)
        ttk.Label(lay_frame, text="Layout: ", style='Dark.TLabel').pack(side='left')
        ttk.Radiobutton(lay_frame, text="ES (Español)", variable=self.layout_var, value="ES").pack(side='left', padx=2)
        ttk.Radiobutton(lay_frame, text="US (Inglés)", variable=self.layout_var, value="US").pack(side='left', padx=2)

        # Botones de payloads (referencias de instancia para bloquearlos en ejecución)
        self.payload_buttons = []
        payloads = self.services.ducky.list_payloads()
        if not payloads:
            ttk.Label(scroll.scrollable_frame, text="No hay payloads .txt en payloads/", style='Gray.TLabel').pack(pady=10)
        else:
            for p in payloads:
                btn = scroll.add_button(
                    text=f"⚡ {p[:22]}",
                    command=lambda name=p: self._on_execute_payload(name),
                    style='Red.TButton',
                    width=28
                )
                if btn:
                    self.payload_buttons.append(btn)

        # Botón Detener Payload (inicia deshabilitado en gris)
        self.btn_detener_ducky = scroll.add_button(
            text="DETENER PAYLOAD",
            command=self._on_stop_payload,
            style='Gray.TButton',
            width=28
        )
        if self.btn_detener_ducky:
            self.btn_detener_ducky.state(['disabled'])

        self.show_console(parent=scroll.scrollable_frame)

        # Si se vuelve a entrar a la vista con un payload activo, reflejar el bloqueo
        if self.services.ducky.is_running:
            self._apply_payload_state(True)

    def _apply_payload_state(self, running: bool):
        """
        Bloquea o restaura los botones de payloads y el botón Detener.
        Se usa btn.state([...]) para un bloqueo táctil consistente en ttk plano.
        """
        for btn in self.payload_buttons:
            if btn and btn.winfo_exists():
                if running:
                    btn.config(style='Gray.TButton')
                    btn.state(['disabled'])
                else:
                    btn.config(style='Red.TButton')
                    btn.state(['!disabled'])
        if self.btn_detener_ducky and self.btn_detener_ducky.winfo_exists():
            if running:
                self.btn_detener_ducky.config(style='Danger.TButton')
                self.btn_detener_ducky.state(['!disabled'])
            else:
                self.btn_detener_ducky.config(style='Gray.TButton')
                self.btn_detener_ducky.state(['disabled'])

    def _on_execute_payload(self, payload_name: str):
        if self.services.ducky.is_running:
            self.write_console("[!] Ya hay un payload en ejecución.")
            return

        layout = self.layout_var.get()

        # 1. Bloquear botones de payloads y habilitar Detener
        self._apply_payload_state(True)

        def worker():
            # 2. Lanzar el payload (subproceso matable) fuera del hilo de la GUI
            try:
                self.services.ducky.execute_payload(
                    payload_name, layout=layout, on_output=self.write_console
                )
            finally:
                # 3. Restaurar estados visuales en el hilo de la UI
                self.run_on_ui(lambda: self._apply_payload_state(False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_stop_payload(self):
        """Aborta el payload en curso y restaura los botones."""
        # Deshabilitar al instante para evitar doble pulsación
        if self.btn_detener_ducky and self.btn_detener_ducky.winfo_exists():
            self.btn_detener_ducky.config(style='Gray.TButton')
            self.btn_detener_ducky.state(['disabled'])

        self.services.ducky.stop_payload(on_output=self.write_console)
        self._apply_payload_state(False)
