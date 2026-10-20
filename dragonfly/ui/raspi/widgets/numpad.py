"""
dragonfly/ui/raspi/widgets/numpad.py - Teclado numérico táctil emergente (Popup modal).
Optimizado para introducir IPs y rangos CIDR con los dedos en pantallas de 320x240.
"""

import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.theme import COLOR_FONDO_PRINCIPAL


class TecladoNumerico(tk.Toplevel):
    """
    Teclado numérico táctil de pantalla completa integrada.
    """

    def __init__(self, parent, variable_destino, titulo="Ingresar IP/Rango"):
        super().__init__(parent)
        self.variable_destino = variable_destino

        self.title(titulo)
        self.configure(bg=COLOR_FONDO_PRINCIPAL)
        self.attributes('-topmost', True)
        self.overrideredirect(True)

        w = parent.winfo_width() or 320
        h = parent.winfo_height() or 240
        x = parent.winfo_x()
        y = parent.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

        main_frame = ttk.Frame(self, style='Dark.TFrame')
        main_frame.pack(fill='both', expand=True, padx=4, pady=4)

        self.display_var = tk.StringVar(value=variable_destino.get())
        display = ttk.Entry(
            main_frame,
            textvariable=self.display_var,
            font=('Helvetica', 13, 'bold'),
            justify='center',
            style='Dark.TEntry'
        )
        display.pack(fill='x', pady=(0, 4))

        grid_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        grid_frame.pack(fill='both', expand=True)

        for i in range(4):
            grid_frame.grid_columnconfigure(i, weight=1)
            grid_frame.grid_rowconfigure(i, weight=1)

        botones = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2), ('DEL', 0, 3),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2), ('/', 1, 3),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2), ('.', 2, 3),
            ('0', 3, 0), ('-', 3, 1), ('CANCEL', 3, 2), ('OK', 3, 3)
        ]

        for (texto, fila, col) in botones:
            estilo = 'Red.TButton' if texto in ('OK', 'CANCEL', 'DEL') else 'Gray.TButton'
            btn = ttk.Button(
                grid_frame,
                text=texto,
                style=estilo,
                command=lambda t=texto: self._procesar_tecla(t)
            )
            btn.grid(row=fila, column=col, sticky='nsew', padx=2, pady=2)

    def _procesar_tecla(self, tecla):
        actual = self.display_var.get()
        if tecla == 'OK':
            self.variable_destino.set(actual)
            self.destroy()
        elif tecla == 'CANCEL':
            self.destroy()
        elif tecla == 'DEL':
            self.display_var.set(actual[:-1])
        else:
            self.display_var.set(actual + tecla)
