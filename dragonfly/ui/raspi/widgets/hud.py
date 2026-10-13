"""
dragonfly/ui/raspi/widgets/hud.py - Elementos HUD y tarjetas para Raspberry Pi.
Contiene crear_card, crear_separador y crear_statusbar.
"""

import tkinter as tk
from dragonfly.ui.raspi.theme import (
    COLOR_FONDO_BASE,
    COLOR_FONDO_CARD,
    COLOR_BOTON_ROJO,
    COLOR_BORDE_SUTIL,
    COLOR_TEXTO_SECUNDARIO,
    COLOR_TEXTO_EXITO,
    FONT_MICRO
)


def crear_card(parent, titulo=None, color_borde=None):
    """
    Pseudo-card con borde de 1 px y fondo diferenciado del principal.
    Retorna el inner_frame donde colocar los widgets hijos.
    """
    if color_borde is None:
        color_borde = COLOR_BORDE_SUTIL
    border_frame = tk.Frame(parent, bg=color_borde, padx=1, pady=1)
    border_frame.pack(fill='x', padx=4, pady=3)
    inner_frame = tk.Frame(border_frame, bg=COLOR_FONDO_CARD)
    inner_frame.pack(fill='both', expand=True)
    if titulo:
        tk.Frame(inner_frame, bg=COLOR_BOTON_ROJO, height=2).pack(fill='x')
        tk.Label(inner_frame,
                 text=f" {titulo.upper()}",
                 bg=COLOR_FONDO_CARD, fg=COLOR_TEXTO_SECUNDARIO,
                 font=FONT_MICRO, anchor='w').pack(fill='x', padx=4, pady=(2, 0))
        tk.Frame(inner_frame, bg=COLOR_BORDE_SUTIL, height=1).pack(fill='x')
    return inner_frame


def crear_separador(parent, color=None, padx=6, pady=4):
    """Línea horizontal de 1 px para separar secciones dentro de un frame."""
    if color is None:
        color = COLOR_BORDE_SUTIL
    tk.Frame(parent, bg=color, height=1).pack(fill='x', padx=padx, pady=pady)


def crear_statusbar(root_app):
    """
    Barra de estado HUD de 14 px fija al fondo de la ventana.
    Retorna (bar_frame, lbl_ip, lbl_iface).
    """
    bar = tk.Frame(root_app, bg=COLOR_FONDO_BASE, height=14)
    bar.pack(fill='x', side='bottom')
    bar.pack_propagate(False)
    lbl_ip = tk.Label(bar, text=" [NET] ---.---.---",
                      bg=COLOR_FONDO_BASE, fg=COLOR_TEXTO_SECUNDARIO,
                      font=FONT_MICRO, anchor='w')
    lbl_ip.pack(side='left', padx=2)
    lbl_iface = tk.Label(bar, text="---  ●",
                         bg=COLOR_FONDO_BASE, fg=COLOR_TEXTO_EXITO,
                         font=FONT_MICRO, anchor='e')
    lbl_iface.pack(side='right', padx=2)
    return bar, lbl_ip, lbl_iface
