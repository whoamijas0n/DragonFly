"""
dragonfly/ui/raspi/theme.py - Tema visual Cyberdeck Flat Design v2 y estilos ttk para Raspberry Pi.
Optimizado para pantallas TFT LCD de 320x240 con alto contraste y bajo consumo de CPU.
"""

import tkinter as tk
from tkinter import ttk

# ──────────────────────────────────────────────────────────────
# PALETA DE COLORES — CYBERDECK FLAT DESIGN v2
# ──────────────────────────────────────────────────────────────
COLOR_FONDO_BASE          = "#0c0c0c"
COLOR_FONDO_PRINCIPAL     = "#000000"
COLOR_FONDO_CARD          = "#000000"
COLOR_FONDO_ELEVADO       = "#272727"
COLOR_BOTON_ROJO          = "#cc0a0a"
COLOR_BOTON_HOVER         = "#900008"
COLOR_ROJO_BRIGHT         = "#ff2222"
COLOR_BOTON_PELIGRO       = "#d97700"
COLOR_BOTON_PELIGRO_HOVER = "#b36200"
COLOR_BOTON_GRIS          = "#2c2c2c"
COLOR_BOTON_GRIS_HOVER    = "#1c1c1c"
COLOR_TEXTO_PRIMARIO      = "#e2e2e2"
COLOR_TEXTO_SECUNDARIO    = "#787878"
COLOR_TEXTO_TERMINAL      = "#ff3333"
COLOR_TEXTO_EXITO         = "#33cc66"
COLOR_TEXTO_ADVERTENCIA   = "#ffaa00"
COLOR_BORDE_SUTIL         = "#282828"
COLOR_BORDE_ACTIVO        = "#cc0a0a"
COLOR_FONDO_SIDEBAR       = "#0c0c0c"

# ──────────────────────────────────────────────────────────────
# JERARQUÍA TIPOGRÁFICA
# ──────────────────────────────────────────────────────────────
FONT_TITLE  = ('Courier', 11, 'bold')
FONT_BODY   = ('Courier',  9        )
FONT_BODY_B = ('Courier',  9, 'bold')
FONT_SMALL  = ('Courier',  8        )
FONT_MICRO  = ('Courier',  7        )


def setup_ttk_styles():
    """Configura el tema ttk clam con estilos planos oscuros sin bordes brillantes."""
    style = ttk.Style()
    style.theme_use('clam')

    # FRAMES
    style.configure('TFrame', background=COLOR_FONDO_PRINCIPAL, borderwidth=0)
    style.configure('Dark.TFrame', background=COLOR_FONDO_PRINCIPAL, borderwidth=0)
    style.configure('Card.TFrame', background=COLOR_FONDO_CARD, borderwidth=0)

    # LABELS
    style.configure('TLabel', background=COLOR_FONDO_PRINCIPAL, foreground=COLOR_TEXTO_PRIMARIO, font=FONT_BODY, borderwidth=0)
    style.configure('Dark.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground=COLOR_TEXTO_PRIMARIO, font=FONT_BODY, borderwidth=0)
    style.configure('Title.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground=COLOR_ROJO_BRIGHT, font=FONT_TITLE, borderwidth=0)
    style.configure('Gray.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground=COLOR_TEXTO_SECUNDARIO, font=FONT_SMALL, borderwidth=0)
    style.configure('Mono.TLabel', background=COLOR_FONDO_PRINCIPAL, foreground=COLOR_TEXTO_TERMINAL, font=FONT_BODY_B, borderwidth=0)
    style.configure('Card.TLabel', background=COLOR_FONDO_CARD, foreground=COLOR_TEXTO_PRIMARIO, font=FONT_BODY, borderwidth=0)

    # BOTÓN BASE
    style.configure('TButton', borderwidth=0, relief='flat', padding=(8, 6))
    style.map('TButton', background=[('active', COLOR_BOTON_HOVER)],
              bordercolor=[('focus', COLOR_BORDE_ACTIVO)], focuscolor=[('focus', COLOR_BORDE_ACTIVO)])

    # BOTÓN ROJO
    style.configure('Red.TButton', background=COLOR_BOTON_ROJO, foreground='white',
                    relief='flat', font=FONT_BODY_B, bordercolor=COLOR_BOTON_ROJO,
                    focuscolor=COLOR_BORDE_ACTIVO, borderwidth=1, focusthickness=2, padding=(8, 9))
    style.map('Red.TButton',
              background=[('pressed', '#660005'), ('active', COLOR_BOTON_HOVER)],
              foreground=[('pressed', '#cccccc'), ('active', 'white')],
              bordercolor=[('focus', COLOR_ROJO_BRIGHT), ('active', COLOR_BOTON_HOVER)],
              relief=[('pressed', 'flat')])

    # BOTÓN GRIS
    style.configure('Gray.TButton', background=COLOR_BOTON_GRIS, foreground=COLOR_TEXTO_PRIMARIO,
                    relief='flat', font=FONT_BODY, bordercolor=COLOR_BOTON_GRIS, focuscolor='#555555',
                    borderwidth=1, focusthickness=1, padding=(8, 9))
    style.map('Gray.TButton',
              background=[('pressed', '#0f0f0f'), ('active', COLOR_BOTON_GRIS_HOVER)],
              foreground=[('pressed', '#888888'), ('active', 'white')])

    # BOTÓN PELIGRO
    style.configure('Danger.TButton', background=COLOR_BOTON_PELIGRO, foreground='#0c0c0c',
                    relief='flat', font=FONT_BODY_B, bordercolor=COLOR_BOTON_PELIGRO,
                    focuscolor=COLOR_BOTON_PELIGRO_HOVER, borderwidth=1, padding=(8, 9))
    style.map('Danger.TButton',
              background=[('pressed', '#8a4a00'), ('active', COLOR_BOTON_PELIGRO_HOVER)],
              foreground=[('pressed', '#000000'), ('active', '#0c0c0c')])

    # ENTRY
    style.configure('Dark.TEntry', fieldbackground='#141414', foreground=COLOR_TEXTO_PRIMARIO,
                    insertcolor=COLOR_ROJO_BRIGHT, borderwidth=1, relief='flat')

    # SCROLLBAR
    style.configure('Dark.Vertical.TScrollbar', background=COLOR_BOTON_GRIS, troughcolor=COLOR_FONDO_PRINCIPAL,
                    borderwidth=0, relief='flat', width=8)

    # OPTIONMENU / MENUBUTTON
    style.configure('Dark.TMenubutton', background=COLOR_BOTON_GRIS, foreground=COLOR_TEXTO_PRIMARIO,
                    font=FONT_BODY, padding=(6, 4), relief='flat')
    style.map('Dark.TMenubutton', background=[('active', COLOR_BOTON_GRIS_HOVER)])

    return style
