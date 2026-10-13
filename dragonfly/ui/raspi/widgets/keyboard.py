"""
dragonfly/ui/raspi/widgets/keyboard.py - Teclado alfanumérico táctil completo con modos.
Optimizado para ingreso de contraseñas Wi-Fi, SSIDs y direcciones MAC en pantalla táctil de 320x240.
"""

import tkinter as tk
from tkinter import ttk
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_PRINCIPAL,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER,
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_PELIGRO_HOVER,
    COLOR_TEXTO_PRIMARIO
)


class TecladoCompleto(tk.Toplevel):
    """
    Teclado virtual con modos minúsculas, mayúsculas y símbolos, con escalado elástico.
    """

    def __init__(self, parent, variable_destino, titulo="Ingresar Texto"):
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

        if w <= 320:
            self.kb_font = ('Courier', 8, 'bold')
            self.ent_font = ('Helvetica', 10, 'bold')
            self.kb_pad = (0, 2)
        elif w <= 480:
            self.kb_font = ('Courier', 10, 'bold')
            self.ent_font = ('Helvetica', 14, 'bold')
            self.kb_pad = (1, 6)
        else:
            self.kb_font = ('Courier', 14, 'bold')
            self.ent_font = ('Helvetica', 18, 'bold')
            self.kb_pad = (4, 10)

        style = ttk.Style()
        style.configure('KbGray.TButton', font=self.kb_font, padding=self.kb_pad,
                        background=COLOR_BOTON_GRIS, foreground=COLOR_TEXTO_PRIMARIO, relief='flat')
        style.map('KbGray.TButton', background=[('pressed', '#0f0f0f'), ('active', COLOR_BOTON_GRIS_HOVER)],
                  foreground=[('pressed', '#888888'), ('active', 'white')])

        style.configure('KbRed.TButton', font=self.kb_font, padding=self.kb_pad,
                        background=COLOR_BOTON_ROJO, foreground='white', relief='flat')
        style.map('KbRed.TButton', background=[('pressed', '#660005'), ('active', COLOR_BOTON_HOVER)])

        style.configure('KbDanger.TButton', font=self.kb_font, padding=self.kb_pad,
                        background=COLOR_BOTON_PELIGRO, foreground='#0c0c0c', relief='flat')
        style.map('KbDanger.TButton', background=[('pressed', '#8a4a00'), ('active', COLOR_BOTON_PELIGRO_HOVER)])

        main_frame = ttk.Frame(self, style='Dark.TFrame')
        main_frame.pack(fill='both', expand=True, padx=2, pady=2)

        top_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        top_frame.pack(fill='x', pady=(0, 2))

        ttk.Label(top_frame, text=titulo[:15], style='Gray.TLabel').pack(side='left', padx=2)

        self.display_var = tk.StringVar(value="")
        display = ttk.Entry(top_frame, textvariable=self.display_var, font=self.ent_font,
                            justify='center', style='Dark.TEntry')
        display.pack(side='right', fill='x', expand=True)

        self.kb_container = ttk.Frame(main_frame, style='Dark.TFrame')
        self.kb_container.pack(fill='both', expand=True)
        self.kb_container.grid_rowconfigure(0, weight=1)
        self.kb_container.grid_columnconfigure(0, weight=1)

        self.frames_teclado = {}
        for modo in ("minusculas", "mayusculas", "simbolos"):
            frame = ttk.Frame(self.kb_container, style='Dark.TFrame')
            frame.grid(row=0, column=0, sticky='nsew')
            self.frames_teclado[modo] = frame
            self._construir_teclas(frame, modo)

        self.cambiar_modo("minusculas")

    def cambiar_modo(self, modo):
        self.frames_teclado[modo].tkraise()

    def _construir_teclas(self, parent_frame, modo):
        if modo == "minusculas":
            filas = [
                [('q', 2), ('w', 2), ('e', 2), ('r', 2), ('t', 2), ('y', 2), ('u', 2), ('i', 2), ('o', 2), ('p', 2)],
                [('pad', 1), ('a', 2), ('s', 2), ('d', 2), ('f', 2), ('g', 2), ('h', 2), ('j', 2), ('k', 2), ('l', 2), ('pad', 1)],
                [('pad', 1), ('z', 2), ('x', 2), ('c', 2), ('v', 2), ('b', 2), ('n', 2), ('m', 2), ('DEL', 4), ('pad', 1)],
                [('MAYUS', 3), ('123', 3), ('ESPACIO', 8), ('CANCEL', 3), ('OK', 3)]
            ]
        elif modo == "mayusculas":
            filas = [
                [('Q', 2), ('W', 2), ('E', 2), ('R', 2), ('T', 2), ('Y', 2), ('U', 2), ('I', 2), ('O', 2), ('P', 2)],
                [('pad', 1), ('A', 2), ('S', 2), ('D', 2), ('F', 2), ('G', 2), ('H', 2), ('J', 2), ('K', 2), ('L', 2), ('pad', 1)],
                [('pad', 1), ('Z', 2), ('X', 2), ('C', 2), ('V', 2), ('B', 2), ('N', 2), ('M', 2), ('DEL', 4), ('pad', 1)],
                [('minus', 3), ('123', 3), ('ESPACIO', 8), ('CANCEL', 3), ('OK', 3)]
            ]
        else:  # simbolos
            filas = [
                [('1', 2), ('2', 2), ('3', 2), ('4', 2), ('5', 2), ('6', 2), ('7', 2), ('8', 2), ('9', 2), ('0', 2)],
                [('!', 2), ('@', 2), ('#', 2), ('$', 2), ('%', 2), ('&', 2), ('*', 2), ('-', 2), ('_', 2), ('+', 2)],
                [('pad', 1), ('=', 2), ('/', 2), ('?', 2), ('¡', 2), ('.', 2), ('"', 2), ("'", 2), ('DEL', 4), ('pad', 1)],
                [('abc', 3), ('MAYUS', 3), ('ESPACIO', 8), ('CANCEL', 3), ('OK', 3)]
            ]

        for i in range(4):
            parent_frame.grid_rowconfigure(i, weight=1)
        for j in range(20):
            parent_frame.grid_columnconfigure(j, weight=1)

        for i, fila in enumerate(filas):
            current_col = 0
            for (tecla, span) in fila:
                if tecla == 'pad':
                    frm = ttk.Frame(parent_frame, style='Dark.TFrame')
                    frm.grid(row=i, column=current_col, columnspan=span, sticky='nsew')
                else:
                    if tecla in ('OK', 'CANCEL', 'DEL'):
                        estilo = 'KbRed.TButton'
                    elif tecla in ('MAYUS', 'minus', '123', 'abc', 'ESPACIO'):
                        estilo = 'KbDanger.TButton'
                    else:
                        estilo = 'KbGray.TButton'

                    display_text = " " if tecla == 'ESPACIO' else tecla
                    btn = ttk.Button(
                        parent_frame, text=display_text, style=estilo,
                        command=lambda t=tecla: self._procesar_tecla(t)
                    )
                    btn.grid(row=i, column=current_col, columnspan=span, sticky='nsew', padx=1, pady=1)

                current_col += span

    def _procesar_tecla(self, tecla):
        actual = self.display_var.get()
        if tecla == 'OK':
            self.variable_destino.set(actual)
            self.destroy()
        elif tecla == 'CANCEL':
            self.variable_destino.set("CANCELADO")
            self.destroy()
        elif tecla == 'DEL':
            self.display_var.set(actual[:-1])
        elif tecla == 'ESPACIO':
            self.display_var.set(actual + " ")
        elif tecla == 'MAYUS':
            self.cambiar_modo("mayusculas")
        elif tecla in ('minus', 'abc'):
            self.cambiar_modo("minusculas")
        elif tecla == '123':
            self.cambiar_modo("simbolos")
        else:
            self.display_var.set(actual + tecla)
