"""
dragonfly/ui/raspi/widgets/scrollable.py - ScrollableFrame con soporte táctil (touch drag).
Diseñado para la pantalla táctil de 320x240 de la Raspberry Pi Zero 2 WH.
"""

import gc
import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_TEXTO_TERMINAL,
    FONT_BODY
)


class ScrollableFrame(tk.Frame):
    """
    Frame con scroll vertical fluido usando Canvas y detección de arrastre táctil (touch gestures).
    """

    def __init__(self, parent, max_items=50, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.bg_color = COLOR_FONDO_PRINCIPAL
        self.max_items = max_items
        self.configure(bg=self.bg_color, highlightthickness=0, borderwidth=0)

        # Canvas con scrollbar
        self.canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style='Dark.Vertical.TScrollbar')

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.bg_color, highlightthickness=0, borderwidth=0)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw", tags="scrollable_frame"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Eventos táctiles
        self.canvas.bind("<Button-1>", self._on_touch_start)
        self.canvas.bind("<B1-Motion>", self._on_touch_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_touch_end)

        # Rueda de ratón
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self._drag_start_y = 0
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        """Ajusta el ancho del frame interior al ancho del canvas."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_touch_start(self, event):
        """Inicia arrastre táctil."""
        self._drag_start_y = event.y

    def _on_touch_drag(self, event):
        """Arrastrar para desplazar contenido con física táctil natural."""
        dy = self._drag_start_y - event.y
        if abs(dy) > 3:
            total_height = self.canvas.bbox("all")[3] if self.canvas.bbox("all") else 1
            fraction = dy / total_height
            self.canvas.yview_scroll(int(fraction * 10), "units")
            self._drag_start_y = event.y

    def _on_touch_end(self, event):
        pass

    def clear(self):
        """Limpia los widgets hijos y recolecta memoria explícitamente."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        gc.collect()

    def add_button(self, text, command, style='Red.TButton', width=None):
        """Agrega un botón estilizado con padding uniforme al scroll."""
        current_children = len(self.scrollable_frame.winfo_children())
        if current_children >= self.max_items:
            warning_label = tk.Label(
                self.scrollable_frame,
                text="[!] Límite de elementos alcanzado.",
                bg=self.bg_color,
                fg=COLOR_TEXTO_TERMINAL,
                font=('Helvetica', 8)
            )
            warning_label.pack(fill='x', padx=10, pady=2)
            return None

        if width is None:
            width = 28

        btn = ttk.Button(self.scrollable_frame, text=text, style=style, width=width)
        btn.configure(command=command)
        btn.pack(fill='x', padx=10, pady=3)
        return btn

    def add_widget(self, widget, **pack_options):
        """Agrega un widget genérico verificando el límite de elementos."""
        current_children = len(self.scrollable_frame.winfo_children())
        if current_children >= self.max_items:
            return
        widget.pack(**pack_options)
