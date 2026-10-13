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

        payloads = self.services.ducky.list_payloads()
        if not payloads:
            ttk.Label(scroll.scrollable_frame, text="No hay payloads .txt en payloads/", style='Gray.TLabel').pack(pady=10)
        else:
            for p in payloads:
                scroll.add_button(
                    text=f"⚡ {p[:22]}",
                    command=lambda name=p: self._on_execute_payload(name),
                    style='Red.TButton',
                    width=28
                )

        self.show_console(parent=scroll.scrollable_frame)

    def _on_execute_payload(self, payload_name: str):
        layout = self.layout_var.get()

        def worker():
            self.services.ducky.execute_payload(payload_name, layout=layout, on_output=self.write_console)

        threading.Thread(target=worker, daemon=True).start()
