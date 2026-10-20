"""
dragonfly/ui/desktop/views/recon_view.py - Vista de reconocimiento e inteligencia con Nmap para Desktop.
"""

import customtkinter as ctk
from dragonfly.ui.desktop.views.base_view import BaseView
from dragonfly.ui.desktop.theme import (
    COLOR_BOTON_ROJO,
    COLOR_BOTON_HOVER,
    COLOR_BOTON_PELIGRO,
    COLOR_BOTON_DESHABILITADO,
    COLOR_BOTON_GRIS,
    COLOR_BOTON_GRIS_HOVER
)
from dragonfly.config import NMAP_PROFILES, BASE_DIR_NMAP


class ReconView(BaseView):
    """
    Vista interactiva para lanzar y monitorear escaneos Nmap.
    """

    def __init__(self, app):
        super().__init__(app)
        self.target_ip_var = ctk.StringVar(value="127.0.0.1")
        self.usar_rango_var = ctk.BooleanVar(value=False)
        self.rango_cidr_var = ctk.StringVar(value="/24")
        self.scan_buttons = []
        self.btn_detener = None

    def render(self):
        """Dibuja el panel de configuración de objetivos y los perfiles de Nmap."""
        self.clear_frame()
        self.add_back_button(self.app.views['inicio'].render)

        ctk.CTkLabel(self.main_frame, text="RECONOCIMIENTO E INTELIGENCIA (NMAP)",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 5))

        # Configuración de Target
        config_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        config_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(config_frame, text="Target IP:").pack(side="left", padx=5)
        entry_target = ctk.CTkEntry(config_frame, textvariable=self.target_ip_var, width=150)
        entry_target.pack(side="left", padx=5)

        chk_rango = ctk.CTkCheckBox(config_frame, text="Usar rango", variable=self.usar_rango_var)
        chk_rango.pack(side="left", padx=10)

        ctk.CTkOptionMenu(config_frame, values=["/24", "/16", "/8"],
                          variable=self.rango_cidr_var, width=60).pack(side="left", padx=5)

        ctk.CTkButton(
            config_frame,
            text="Actualizar",
            width=80,
            fg_color=COLOR_BOTON_ROJO,
            command=self._on_update_target
        ).pack(side="left", padx=10)

        # Botones de perfiles Nmap
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.scan_buttons = []
        for i, (nombre, _) in enumerate(NMAP_PROFILES):
            row = i // 2
            col = i % 2
            btn = ctk.CTkButton(
                btn_frame,
                text=nombre,
                fg_color=COLOR_BOTON_ROJO,
                hover_color=COLOR_BOTON_HOVER,
                command=lambda idx=i: self._on_execute_scan(idx)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            self.scan_buttons.append({"widget": btn, "color": COLOR_BOTON_ROJO})

        # Botón Detener
        self.btn_detener = ctk.CTkButton(
            self.main_frame,
            text="DETENER ESCANEO",
            fg_color=COLOR_BOTON_DESHABILITADO,
            state="disabled",
            command=self._on_stop_scan
        )
        self.btn_detener.pack(pady=(10, 5))

        # Botón Explorar
        btn_explorar = ctk.CTkButton(
            self.main_frame,
            text="EXPLORAR RESULTADOS GUARDADOS",
            fg_color=COLOR_BOTON_GRIS,
            hover_color=COLOR_BOTON_GRIS_HOVER,
            height=40,
            command=lambda: self.app.views['explorer'].show_sessions(BASE_DIR_NMAP, "Resultados Nmap", self.render)
        )
        btn_explorar.pack(pady=(5, 15))
        self.scan_buttons.append({"widget": btn_explorar, "color": COLOR_BOTON_GRIS})

        self.show_console()

        # Detección automática de IP si está en 127.0.0.1
        if self.target_ip_var.get() == "127.0.0.1":
            ip_auto = self.services.recon.get_auto_ip()
            if ip_auto != "127.0.0.1":
                self.target_ip_var.set(ip_auto)
                self.write_console(f"[*] Red local detectada automáticamente: {ip_auto}")

    def _on_update_target(self):
        target = self.services.recon.format_target(
            self.target_ip_var.get(),
            self.usar_rango_var.get(),
            self.rango_cidr_var.get()
        )
        if target:
            self.write_console(f"[+] Target actualizado: {target}")
        else:
            self.write_console("[!] Target inválido. Use formato IPv4 y máscara /8, /16, /24, /32.")

    def _on_execute_scan(self, profile_index: int):
        target = self.services.recon.format_target(
            self.target_ip_var.get(),
            self.usar_rango_var.get(),
            self.rango_cidr_var.get()
        )
        if not target:
            self.write_console("[!] Target inválido. No se ejecutará el comando.")
            return

        # Bloquear botones
        for item in self.scan_buttons:
            try:
                item["widget"].configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
            except Exception:
                pass

        if self.btn_detener and self.btn_detener.winfo_exists():
            self.btn_detener.configure(state="normal", fg_color=COLOR_BOTON_PELIGRO)

        def on_finish(rc):
            def restore():
                for item in self.scan_buttons:
                    try:
                        item["widget"].configure(state="normal", fg_color=item["color"])
                    except Exception:
                        pass
                if self.btn_detener and self.btn_detener.winfo_exists():
                    self.btn_detener.configure(state="disabled", fg_color=COLOR_BOTON_DESHABILITADO)
            self.run_on_ui(restore)

        self.services.recon.start_scan(
            target=target,
            profile_index=profile_index,
            on_output=self.write_console,
            on_finish=on_finish
        )

    def _on_stop_scan(self):
        self.services.recon.stop_scan(on_output=self.write_console)
