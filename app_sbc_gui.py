"""
Interfaz Visual Moderna (Tkinter) para el SBC - Ingenio La Esperanza.

Diseño contemporáneo con soporte High-DPI en Windows, tema Oscuro por defecto
con alternador a tema Claro, tarjetas de conversación en lenguaje natural,
chips interactivos de ejemplos, compositor autoexpandible, tira de KPIs en vivo,
pestañas segmentadas y trazabilidad completa RDF/SPARQL + PyVis.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from sbc_motor import (
    ETIQUETAS_EVENTOS,
    ETIQUETAS_MEDICIONES,
    PROPIEDADES_EVENTO,
    PROPIEDADES_MEDICION,
    crear_caso_vacio,
    evaluar_caso,
    exportar_grafo_pyvis,
)
from sbc_pln import (
    CASOS_EJEMPLO,
    generar_respuesta_natural,
    traducir_consulta_a_hechos,
)

ACCIONES_SEGUIMIENTO = [
    "EnfriarTacho",
    "AumentarSemilla",
    "DisminuirSemilla",
    "AumentarTiempoLavado",
    "ReducirTiempoLavado",
]

TEMAS: dict[str, dict[str, str]] = {
    "dark": {
        "nombre": "dark",
        "bg": "#0B1120",
        "surface": "#111827",
        "card": "#1E293B",
        "card_alt": "#162033",
        "border": "#2D3A4F",
        "text": "#F1F5F9",
        "muted": "#94A3B8",
        "accent": "#38BDF8",
        "accent_hover": "#0EA5E9",
        "accent_fg": "#082F49",
        "user_bubble": "#172E4D",
        "user_border": "#294D7A",
        "ok": "#10B981",
        "ok_bg": "#064E3B",
        "bad": "#F43F5E",
        "bad_bg": "#4C0519",
        "warn": "#F59E0B",
        "warn_bg": "#451A03",
        "info": "#38BDF8",
        "info_bg": "#0C4A6E",
        "row_even": "#1E293B",
        "row_odd": "#162033",
        "sel_bg": "#1D4ED8",
        "inferred_fg": "#38BDF8",
        "initial_fg": "#94A3B8",
        "input_bg": "#0F172A",
        "btn_sec": "#263349",
        "btn_sec_hover": "#334155",
        "trough": "#0F172A",
        "thumb": "#334155",
        "thumb_active": "#475569",
    },
    "light": {
        "nombre": "light",
        "bg": "#F1F5F9",
        "surface": "#FFFFFF",
        "card": "#FFFFFF",
        "card_alt": "#F8FAFC",
        "border": "#CBD5E1",
        "text": "#0F172A",
        "muted": "#64748B",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "accent_fg": "#FFFFFF",
        "user_bubble": "#E0F2FE",
        "user_border": "#BAE6FD",
        "ok": "#059669",
        "ok_bg": "#D1FAE5",
        "bad": "#E11D48",
        "bad_bg": "#FFE4E6",
        "warn": "#D97706",
        "warn_bg": "#FEF3C7",
        "info": "#0284C7",
        "info_bg": "#E0F2FE",
        "row_even": "#FFFFFF",
        "row_odd": "#F8FAFC",
        "sel_bg": "#BAE6FD",
        "inferred_fg": "#0369A1",
        "initial_fg": "#64748B",
        "input_bg": "#FFFFFF",
        "btn_sec": "#E2E8F0",
        "btn_sec_hover": "#CBD5E1",
        "trough": "#E2E8F0",
        "thumb": "#CBD5E1",
        "thumb_active": "#94A3B8",
    },
}


def _habilitar_high_dpi_windows() -> None:
    """Activa DPI awareness en Windows para evitar fuentes borrosas."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _aplicar_titulo_dwm_windows(root: tk.Tk, dark: bool) -> None:
    """Sincroniza la barra de título nativa de Windows con el tema activo."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        valor = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(valor), ctypes.sizeof(valor)
            )
    except Exception:
        pass


class ModernButton(tk.Label):
    """Botón plano moderno con efecto hover, variantes semánticas y soporte de tema."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None] | None = None,
        variant: str = "secondary",
        padx: int = 14,
        pady: int = 7,
        font: tuple[Any, ...] = ("Segoe UI", 9, "bold"),
        tema: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent, text=text, padx=padx, pady=pady, font=font, cursor="hand2")
        self._command = command
        self._variant = variant
        self._enabled = True
        self._hover = False
        self._tema = tema or TEMAS["dark"]

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.apply_theme(self._tema)

    def _on_enter(self, _e: Any = None) -> None:
        if self._enabled:
            self._hover = True
            self._refrescar_colores()

    def _on_leave(self, _e: Any = None) -> None:
        self._hover = False
        self._refrescar_colores()

    def _on_click(self, _e: Any = None) -> None:
        if self._enabled and self._command is not None:
            self._command()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._refrescar_colores()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._refrescar_colores()

    def apply_theme(self, tema: dict[str, str]) -> None:
        self._tema = tema
        self._refrescar_colores()

    def _refrescar_colores(self) -> None:
        t = self._tema
        if not self._enabled:
            self.configure(
                bg=t["btn_sec"],
                fg=t["muted"],
                highlightthickness=1,
                highlightbackground=t["border"],
            )
            return

        if self._variant == "primary":
            bg = t["accent_hover"] if self._hover else t["accent"]
            fg = t["accent_fg"]
            bd = bg
        elif self._variant == "accent":
            bg = t["info_bg"] if not self._hover else t["accent"]
            fg = t["accent"] if not self._hover else t["accent_fg"]
            bd = t["accent"]
        elif self._variant == "ghost":
            bg = t["card"] if self._hover else t["surface"]
            fg = t["text"]
            bd = t["border"] if self._hover else t["surface"]
        elif self._variant == "pill_active":
            bg = t["accent"]
            fg = t["accent_fg"]
            bd = t["accent"]
        elif self._variant == "pill":
            bg = t["btn_sec_hover"] if self._hover else t["card_alt"]
            fg = t["muted"] if not self._hover else t["text"]
            bd = t["border"]
        else:  # secondary
            bg = t["btn_sec_hover"] if self._hover else t["btn_sec"]
            fg = t["text"]
            bd = t["border"]

        self.configure(
            bg=bg,
            fg=fg,
            highlightthickness=1,
            highlightbackground=bd,
        )


class SBCApp:
    """Aplicación de escritorio Tkinter moderna para el SBC del Ingenio La Esperanza."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SBC Ingenio La Esperanza — Asesor Virtual en Lenguaje Natural")
        self.root.geometry("1420x860")
        self.root.minsize(1120, 700)

        self.tema_actual: str = "dark"
        self.t: dict[str, str] = TEMAS[self.tema_actual]
        self.root.configure(bg=self.t["bg"])

        self.api_key: str = os.environ.get("GEMINI_API_KEY", "").strip()
        self.ultimo_resultado: dict[str, Any] | None = None
        self.ultima_meta: dict[str, Any] | None = None
        self.consultando = False
        self.tab_activa = "traduccion"

        self.var_modo = tk.StringVar(value="Local (100% Python Offline)")
        self.var_autocompletar = tk.BooleanVar(value=True)
        self.var_ejemplo = tk.StringVar(value="Cargar consulta de ejemplo...")
        self.var_filtro_bh = tk.StringVar(value="Todos")
        self.var_busqueda_bh = tk.StringVar(value="")

        self._mensajes_chat: list[dict[str, Any]] = []
        self._widgets_tema: list[tuple[tk.Widget, dict[str, str]]] = []
        self._botones_modernos: list[ModernButton] = []
        self._tarjetas_texto_chat: list[tk.Text] = []

        self._configurar_estilos_ttk()
        self._construir_barra_superior()
        self._construir_cuerpo_principal()
        self._aplicar_tema_global()
        self._mostrar_bienvenida()
        self.root.after(50, lambda: _aplicar_titulo_dwm_windows(self.root, True))

    def _registrar_tema(self, widget: tk.Widget, mapa: dict[str, str]) -> tk.Widget:
        self._widgets_tema.append((widget, mapa))
        return widget

    def _configurar_estilos_ttk(self) -> None:
        t = self.t
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Scrollbar plano sin flechas (con respaldo si clam difiere)
        try:
            style.layout(
                "Flat.Vertical.TScrollbar",
                [
                    (
                        "Vertical.Scrollbar.trough",
                        {
                            "sticky": "ns",
                            "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
                        },
                    )
                ],
            )
            self._scrollbar_style = "Flat.Vertical.TScrollbar"
        except tk.TclError:
            self._scrollbar_style = "Vertical.TScrollbar"

        style.configure(
            self._scrollbar_style,
            background=t["thumb"],
            troughcolor=t["trough"],
            bordercolor=t["trough"],
            arrowcolor=t["muted"],
            relief="flat",
            borderwidth=0,
            width=10,
        )
        style.map(
            self._scrollbar_style,
            background=[("active", t["thumb_active"]), ("pressed", t["accent"])],
        )

        style.configure("App.TFrame", background=t["bg"])
        style.configure("Surface.TFrame", background=t["surface"])
        style.configure("TPanedwindow", background=t["bg"])
        style.configure("Sash", sashthickness=6, sashrelief="flat")

        style.configure(
            "Modern.Treeview",
            background=t["card"],
            fieldbackground=t["card"],
            foreground=t["text"],
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 9),
            rowheight=30,
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", t["sel_bg"])],
            foreground=[("selected", t["text"] if self.tema_actual == "light" else "#FFFFFF")],
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=t["card_alt"],
            foreground=t["muted"],
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 8),
        )
        style.map("Modern.Treeview.Heading", background=[("active", t["btn_sec"])])

        style.configure(
            "Modern.TCombobox",
            fieldbackground=t["input_bg"],
            background=t["btn_sec"],
            foreground=t["text"],
            arrowcolor=t["muted"],
            bordercolor=t["border"],
            lightcolor=t["border"],
            darkcolor=t["border"],
            padding=5,
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", t["input_bg"])],
            foreground=[("readonly", t["text"])],
            selectbackground=[("readonly", t["input_bg"])],
            selectforeground=[("readonly", t["text"])],
        )

        style.configure(
            "Modern.TEntry",
            fieldbackground=t["input_bg"],
            foreground=t["text"],
            insertcolor=t["text"],
            bordercolor=t["border"],
            lightcolor=t["border"],
            darkcolor=t["border"],
            padding=5,
        )

        self.root.option_add("*TCombobox*Listbox.background", t["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["accent_fg"])

    def _construir_barra_superior(self) -> None:
        # Cabecera principal minimalista
        self.header = tk.Frame(self.root, padx=18, pady=12)
        self.header.pack(fill="x")
        self._registrar_tema(self.header, {"bg": "surface"})

        izq = tk.Frame(self.header)
        izq.pack(side="left", fill="x", expand=True)
        self._registrar_tema(izq, {"bg": "surface"})

        fila_titulo = tk.Frame(izq)
        fila_titulo.pack(anchor="w")
        self._registrar_tema(fila_titulo, {"bg": "surface"})

        self.badge_brand = tk.Label(
            fila_titulo,
            text="INGENIO LA ESPERANZA · SBC",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=3,
        )
        self.badge_brand.pack(side="left", padx=(0, 10))
        self._registrar_tema(self.badge_brand, {"bg": "info_bg", "fg": "accent"})

        self.lbl_titulo = tk.Label(
            fila_titulo,
            text="Asesor Virtual de Control de Calidad",
            font=("Segoe UI", 14, "bold"),
        )
        self.lbl_titulo.pack(side="left")
        self._registrar_tema(self.lbl_titulo, {"bg": "surface", "fg": "text"})

        self.lbl_subtitulo = tk.Label(
            izq,
            text="Motor RDF/SPARQL CONSTRUCT (56 reglas R1–R56 · supuestos S1–S12) + Traductor Híbrido LN↔SBC",
            font=("Segoe UI", 9),
        )
        self.lbl_subtitulo.pack(anchor="w", pady=(3, 0))
        self._registrar_tema(self.lbl_subtitulo, {"bg": "surface", "fg": "muted"})

        # Acciones de cabecera
        der = tk.Frame(self.header)
        der.pack(side="right")
        self._registrar_tema(der, {"bg": "surface"})

        self.lbl_badge_motor = tk.Label(
            der,
            text="● PLN Local Offline",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
        )
        self.lbl_badge_motor.pack(side="left", padx=(0, 8))
        self._registrar_tema(self.lbl_badge_motor, {"bg": "ok_bg", "fg": "ok"})

        self.btn_tema = ModernButton(
            der,
            text="☀ Tema Claro",
            command=self._alternar_tema,
            variant="secondary",
            padx=11,
            pady=6,
            tema=self.t,
        )
        self.btn_tema.pack(side="left", padx=(0, 8))
        self._botones_modernos.append(self.btn_tema)

        self.btn_api_key = ModernButton(
            der,
            text="🔑 API Key",
            command=self._configurar_api_key,
            variant="secondary",
            padx=11,
            pady=6,
            tema=self.t,
        )
        self.btn_api_key.pack(side="left", padx=(0, 8))
        self._botones_modernos.append(self.btn_api_key)

        self.btn_grafo = ModernButton(
            der,
            text="🕸 Ver Grafo RDF",
            command=self._abrir_grafo_pyvis,
            variant="accent",
            padx=12,
            pady=6,
            tema=self.t,
        )
        self.btn_grafo.pack(side="left")
        self._botones_modernos.append(self.btn_grafo)

        # Separador fino 1px
        self.sep_header = tk.Frame(self.root, height=1)
        self.sep_header.pack(fill="x")
        self._registrar_tema(self.sep_header, {"bg": "border"})

        # Barra de herramientas secundaria limpia
        self.toolbar = tk.Frame(self.root, padx=18, pady=8)
        self.toolbar.pack(fill="x")
        self._registrar_tema(self.toolbar, {"bg": "card_alt"})

        lbl_m = tk.Label(self.toolbar, text="Modo PLN:", font=("Segoe UI", 9, "bold"))
        lbl_m.pack(side="left", padx=(0, 6))
        self._registrar_tema(lbl_m, {"bg": "card_alt", "fg": "muted"})

        self.cb_modo = ttk.Combobox(
            self.toolbar,
            textvariable=self.var_modo,
            values=["Local (100% Python Offline)", "Híbrido (Gemini API + Fallback Local)"],
            state="readonly",
            style="Modern.TCombobox",
            width=31,
        )
        self.cb_modo.pack(side="left", padx=(0, 14))
        self.cb_modo.bind("<<ComboboxSelected>>", lambda _e: self._actualizar_badge_motor())

        self.chk_auto = tk.Checkbutton(
            self.toolbar,
            text="Autocompletar ficha normal si faltan datos",
            variable=self.var_autocompletar,
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.chk_auto.pack(side="left", padx=(0, 16))
        self._registrar_tema(
            self.chk_auto,
            {
                "bg": "card_alt",
                "activebackground": "card_alt",
                "fg": "text",
                "activeforeground": "text",
                "selectcolor": "card",
            },
        )

        lbl_e = tk.Label(self.toolbar, text="Ejemplos rápidos:", font=("Segoe UI", 9, "bold"))
        lbl_e.pack(side="left", padx=(0, 6))
        self._registrar_tema(lbl_e, {"bg": "card_alt", "fg": "muted"})

        titulos_ej = [c["titulo"] for c in CASOS_EJEMPLO]
        self.cb_ejemplos = ttk.Combobox(
            self.toolbar,
            textvariable=self.var_ejemplo,
            values=titulos_ej,
            state="readonly",
            style="Modern.TCombobox",
            width=44,
        )
        self.cb_ejemplos.pack(side="left", fill="x", expand=True)
        self.cb_ejemplos.bind("<<ComboboxSelected>>", self._cargar_ejemplo_seleccionado)

        self.sep_toolbar = tk.Frame(self.root, height=1)
        self.sep_toolbar.pack(fill="x")
        self._registrar_tema(self.sep_toolbar, {"bg": "border"})

    def _construir_cuerpo_principal(self) -> None:
        self.paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=14, pady=12)

        # ==================== PANEL IZQUIERDO: CHAT ====================
        self.panel_chat = tk.Frame(self.paned, highlightthickness=1)
        self.paned.add(self.panel_chat, weight=11)
        self._registrar_tema(self.panel_chat, {"bg": "surface", "highlightbackground": "border"})

        cab_chat = tk.Frame(self.panel_chat, padx=14, pady=10)
        cab_chat.pack(fill="x")
        self._registrar_tema(cab_chat, {"bg": "card_alt"})

        lbl_cc = tk.Label(
            cab_chat,
            text="Diálogo con el Asesor Virtual (Lenguaje Natural)",
            font=("Segoe UI", 10, "bold"),
        )
        lbl_cc.pack(side="left")
        self._registrar_tema(lbl_cc, {"bg": "card_alt", "fg": "text"})

        self.lbl_estado_proc = tk.Label(
            cab_chat,
            text="● Listo",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_estado_proc.pack(side="right")
        self._registrar_tema(self.lbl_estado_proc, {"bg": "card_alt", "fg": "ok"})

        sep_cc = tk.Frame(self.panel_chat, height=1)
        sep_cc.pack(fill="x")
        self._registrar_tema(sep_cc, {"bg": "border"})

        # Canvas scrollable para tarjetas/burbujas del chat
        frame_hist = tk.Frame(self.panel_chat)
        frame_hist.pack(fill="both", expand=True)
        self._registrar_tema(frame_hist, {"bg": "surface"})

        self.scroll_chat = ttk.Scrollbar(frame_hist, orient="vertical", style=self._scrollbar_style)
        self.scroll_chat.pack(side="right", fill="y", padx=(0, 3), pady=4)

        self.canvas_chat = tk.Canvas(frame_hist, highlightthickness=0, bd=0)
        self.canvas_chat.pack(side="left", fill="both", expand=True)
        self.scroll_chat.config(command=self.canvas_chat.yview)
        self.canvas_chat.configure(yscrollcommand=self.scroll_chat.set)
        self._registrar_tema(self.canvas_chat, {"bg": "surface"})

        self.frame_chat_msgs = tk.Frame(self.canvas_chat, padx=14, pady=10)
        self._registrar_tema(self.frame_chat_msgs, {"bg": "surface"})
        self._chat_win_id = self.canvas_chat.create_window((0, 0), window=self.frame_chat_msgs, anchor="nw")

        self.frame_chat_msgs.bind(
            "<Configure>",
            lambda _e: self.canvas_chat.configure(scrollregion=self.canvas_chat.bbox("all")),
        )
        self.canvas_chat.bind("<Configure>", self._on_canvas_chat_resize)
        self._vincular_scroll_mouse(self.canvas_chat, self.canvas_chat)
        self._vincular_scroll_mouse(self.frame_chat_msgs, self.canvas_chat)

        # Compositor moderno inferior
        sep_comp = tk.Frame(self.panel_chat, height=1)
        sep_comp.pack(fill="x")
        self._registrar_tema(sep_comp, {"bg": "border"})

        self.frame_compositor = tk.Frame(self.panel_chat, padx=14, pady=10)
        self.frame_compositor.pack(fill="x")
        self._registrar_tema(self.frame_compositor, {"bg": "card_alt"})

        lbl_hint = tk.Label(
            self.frame_compositor,
            text="Escribí mediciones del tacho, laboratorio o contingencias (Ctrl+Enter para consultar)",
            font=("Segoe UI", 9, "bold"),
        )
        lbl_hint.pack(anchor="w", pady=(0, 6))
        self._registrar_tema(lbl_hint, {"bg": "card_alt", "fg": "muted"})

        self.frame_txt_input = tk.Frame(self.frame_compositor, highlightthickness=1)
        self.frame_txt_input.pack(fill="x", pady=(0, 8))
        self._registrar_tema(
            self.frame_txt_input, {"bg": "input_bg", "highlightbackground": "border"}
        )

        self.scroll_input = ttk.Scrollbar(
            self.frame_txt_input, orient="vertical", style=self._scrollbar_style
        )
        self.scroll_input.pack(side="right", fill="y", padx=2, pady=2)

        self._altura_input_min = 4
        self._altura_input_max = 14
        self._altura_input_actual = self._altura_input_min

        self.txt_input = tk.Text(
            self.frame_txt_input,
            height=self._altura_input_min,
            wrap="word",
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            yscrollcommand=self.scroll_input.set,
        )
        self.txt_input.pack(side="left", fill="x", expand=True)
        self.scroll_input.config(command=self.txt_input.yview)
        self._registrar_tema(
            self.txt_input,
            {"bg": "input_bg", "fg": "text", "insertbackground": "text"},
        )

        self.txt_input.bind(
            "<FocusIn>",
            lambda _e: self.frame_txt_input.configure(highlightbackground=self.t["accent"]),
        )
        self.txt_input.bind(
            "<FocusOut>",
            lambda _e: self.frame_txt_input.configure(highlightbackground=self.t["border"]),
        )
        self.txt_input.bind("<Control-Return>", self._on_ctrl_enter)
        self.txt_input.bind("<KeyRelease>", self._ajustar_altura_input)
        self.txt_input.bind("<<Modified>>", self._on_input_modified)
        self.txt_input.bind("<Configure>", self._ajustar_altura_input)

        btns = tk.Frame(self.frame_compositor)
        btns.pack(fill="x")
        self._registrar_tema(btns, {"bg": "card_alt"})

        self.btn_consultar = ModernButton(
            btns,
            text="Consultar al SBC  ▶",
            command=self._enviar_desde_ui,
            variant="primary",
            padx=16,
            pady=7,
            tema=self.t,
        )
        self.btn_consultar.pack(side="left")
        self._botones_modernos.append(self.btn_consultar)

        self.btn_limpiar = ModernButton(
            btns,
            text="Limpiar Chat",
            command=self._limpiar_chat,
            variant="secondary",
            padx=12,
            pady=7,
            tema=self.t,
        )
        self.btn_limpiar.pack(side="left", padx=(8, 0))
        self._botones_modernos.append(self.btn_limpiar)

        self.lbl_atajo = tk.Label(btns, text="Autoexpansión activa (4–14 líneas)", font=("Segoe UI", 8))
        self.lbl_atajo.pack(side="right")
        self._registrar_tema(self.lbl_atajo, {"bg": "card_alt", "fg": "muted"})

        # ==================== PANEL DERECHO: KPIs + INSPECTOR ====================
        self.panel_der = tk.Frame(self.paned)
        self.paned.add(self.panel_der, weight=10)
        self._registrar_tema(self.panel_der, {"bg": "bg"})

        self._construir_tira_kpi()
        self._construir_barra_tabs_segmentada()

        self.contenedor_tabs = tk.Frame(self.panel_der, highlightthickness=1)
        self.contenedor_tabs.pack(fill="both", expand=True)
        self._registrar_tema(
            self.contenedor_tabs, {"bg": "surface", "highlightbackground": "border"}
        )

        self.frames_tabs: dict[str, tk.Frame] = {}
        self._construir_tab_traduccion()
        self._construir_tab_ciclos()
        self._construir_tab_bh()
        self._construir_tab_formulario()
        self._seleccionar_tab("traduccion")

    def _construir_tira_kpi(self) -> None:
        tira = tk.Frame(self.panel_der)
        tira.pack(fill="x", pady=(0, 10))
        self._registrar_tema(tira, {"bg": "bg"})

        self.kpis: dict[str, tuple[tk.Frame, tk.Label, tk.Label]] = {}
        defs = [
            ("lote", "LOTE / TIPO", "—"),
            ("dictamen", "DICTAMEN", "Sin evaluar"),
            ("ciclos", "INFERENCIA", "0 ciclos"),
            ("tripletas", "BASE DE HECHOS", "0 tripletas"),
        ]
        for idx, (clave, titulo, valor_ini) in enumerate(defs):
            card = tk.Frame(tira, padx=12, pady=8, highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 8, 0))
            self._registrar_tema(card, {"bg": "card", "highlightbackground": "border"})

            lbl_t = tk.Label(card, text=titulo, font=("Segoe UI", 8, "bold"))
            lbl_t.pack(anchor="w")
            self._registrar_tema(lbl_t, {"bg": "card", "fg": "muted"})

            lbl_v = tk.Label(card, text=valor_ini, font=("Segoe UI", 11, "bold"))
            lbl_v.pack(anchor="w", pady=(2, 0))
            self._registrar_tema(lbl_v, {"bg": "card", "fg": "text"})

            self.kpis[clave] = (card, lbl_t, lbl_v)

    def _construir_barra_tabs_segmentada(self) -> None:
        barra = tk.Frame(self.panel_der, padx=4, pady=4, highlightthickness=1)
        barra.pack(fill="x", pady=(0, 8))
        self._registrar_tema(barra, {"bg": "card_alt", "highlightbackground": "border"})

        self.botones_tab: dict[str, ModernButton] = {}
        tabs_def = [
            ("traduccion", "1. Traducción LN→Hechos"),
            ("ciclos", "2. Inferencia (Ciclos)"),
            ("bh", "3. Hechos RDF"),
            ("formulario", "4. Formulario"),
        ]
        for idx, (clave, texto) in enumerate(tabs_def):
            btn = ModernButton(
                barra,
                text=texto,
                command=lambda c=clave: self._seleccionar_tab(c),
                variant="pill",
                padx=12,
                pady=6,
                font=("Segoe UI", 9, "bold"),
                tema=self.t,
            )
            btn.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 4, 0))
            self.botones_tab[clave] = btn
            self._botones_modernos.append(btn)

    def _seleccionar_tab(self, clave: str) -> None:
        self.tab_activa = clave
        for k, frame in self.frames_tabs.items():
            if k == clave:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for k, btn in self.botones_tab.items():
            btn.set_variant("pill_active" if k == clave else "pill")

    def _construir_tab_traduccion(self) -> None:
        tab = tk.Frame(self.contenedor_tabs, padx=12, pady=12)
        self.frames_tabs["traduccion"] = tab
        self._registrar_tema(tab, {"bg": "surface"})

        lbl1 = tk.Label(
            tab,
            text="Análisis del Traductor PLN (parámetros, inferencias cualitativas y autocompletado)",
            font=("Segoe UI", 9, "bold"),
        )
        lbl1.pack(anchor="w", pady=(0, 4))
        self._registrar_tema(lbl1, {"bg": "surface", "fg": "muted"})

        card_meta = tk.Frame(tab, highlightthickness=1)
        card_meta.pack(fill="x", pady=(0, 12))
        self._registrar_tema(card_meta, {"bg": "card", "highlightbackground": "border"})

        self.txt_meta_pln = tk.Text(
            card_meta,
            height=9,
            wrap="word",
            font=("Consolas", 9),
            relief="flat",
            padx=10,
            pady=8,
            state="disabled",
        )
        self.txt_meta_pln.pack(fill="x")
        self._registrar_tema(self.txt_meta_pln, {"bg": "card", "fg": "text"})

        lbl2 = tk.Label(
            tab,
            text="Hechos traducidos cargados al caso (DATOS_CASO)",
            font=("Segoe UI", 9, "bold"),
        )
        lbl2.pack(anchor="w", pady=(0, 4))
        self._registrar_tema(lbl2, {"bg": "surface", "fg": "muted"})

        frame_tv = tk.Frame(tab, highlightthickness=1)
        frame_tv.pack(fill="both", expand=True)
        self._registrar_tema(frame_tv, {"bg": "card", "highlightbackground": "border"})

        sc = ttk.Scrollbar(frame_tv, style=self._scrollbar_style)
        sc.pack(side="right", fill="y")

        self.tv_hechos_caso = ttk.Treeview(
            frame_tv,
            columns=("Campo", "Valor", "Unidad"),
            show="headings",
            style="Modern.Treeview",
            yscrollcommand=sc.set,
        )
        self.tv_hechos_caso.heading("Campo", text="Parámetro / Evento")
        self.tv_hechos_caso.heading("Valor", text="Valor Traducido")
        self.tv_hechos_caso.heading("Unidad", text="Referencia / Tipo")
        self.tv_hechos_caso.column("Campo", width=230)
        self.tv_hechos_caso.column("Valor", width=155)
        self.tv_hechos_caso.column("Unidad", width=155)
        self.tv_hechos_caso.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_hechos_caso.yview)

    def _construir_tab_ciclos(self) -> None:
        tab = tk.Frame(self.contenedor_tabs, padx=12, pady=12)
        self.frames_tabs["ciclos"] = tab
        self._registrar_tema(tab, {"bg": "surface"})

        frame_tv = tk.Frame(tab, highlightthickness=1)
        frame_tv.pack(fill="both", expand=True, pady=(0, 10))
        self._registrar_tema(frame_tv, {"bg": "card", "highlightbackground": "border"})

        sc = ttk.Scrollbar(frame_tv, style=self._scrollbar_style)
        sc.pack(side="right", fill="y")

        self.tv_ciclos = ttk.Treeview(
            frame_tv,
            columns=("Ciclo", "Regla", "Prioridad", "Hechos", "Descripcion"),
            show="headings",
            style="Modern.Treeview",
            yscrollcommand=sc.set,
        )
        self.tv_ciclos.heading("Ciclo", text="Ciclo")
        self.tv_ciclos.heading("Regla", text="Regla Seleccionada")
        self.tv_ciclos.heading("Prioridad", text="Prioridad")
        self.tv_ciclos.heading("Hechos", text="Nuevos")
        self.tv_ciclos.heading("Descripcion", text="Descripción")
        self.tv_ciclos.column("Ciclo", width=52, anchor="center")
        self.tv_ciclos.column("Regla", width=205)
        self.tv_ciclos.column("Prioridad", width=65, anchor="center")
        self.tv_ciclos.column("Hechos", width=60, anchor="center")
        self.tv_ciclos.column("Descripcion", width=250)
        self.tv_ciclos.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_ciclos.yview)
        self.tv_ciclos.bind("<<TreeviewSelect>>", self._mostrar_detalle_ciclo)

        lbl = tk.Label(
            tab,
            text="Tripletas RDF agregadas en el ciclo seleccionado",
            font=("Segoe UI", 9, "bold"),
        )
        lbl.pack(anchor="w", pady=(0, 4))
        self._registrar_tema(lbl, {"bg": "surface", "fg": "muted"})

        card_det = tk.Frame(tab, highlightthickness=1)
        card_det.pack(fill="x")
        self._registrar_tema(card_det, {"bg": "card", "highlightbackground": "border"})

        self.txt_detalle_ciclo = tk.Text(
            card_det,
            height=6,
            wrap="word",
            font=("Consolas", 9),
            relief="flat",
            padx=10,
            pady=8,
            state="disabled",
        )
        self.txt_detalle_ciclo.pack(fill="x")
        self._registrar_tema(self.txt_detalle_ciclo, {"bg": "card", "fg": "accent"})

    def _construir_tab_bh(self) -> None:
        tab = tk.Frame(self.contenedor_tabs, padx=12, pady=12)
        self.frames_tabs["bh"] = tab
        self._registrar_tema(tab, {"bg": "surface"})

        barra = tk.Frame(tab)
        barra.pack(fill="x", pady=(0, 10))
        self._registrar_tema(barra, {"bg": "surface"})

        lbl_f = tk.Label(barra, text="Filtrar:", font=("Segoe UI", 9, "bold"))
        lbl_f.pack(side="left")
        self._registrar_tema(lbl_f, {"bg": "surface", "fg": "muted"})

        cb_filtro = ttk.Combobox(
            barra,
            textvariable=self.var_filtro_bh,
            values=["Todos", "Solo Inferidos", "Solo Iniciales"],
            state="readonly",
            style="Modern.TCombobox",
            width=16,
        )
        cb_filtro.pack(side="left", padx=(6, 12))
        cb_filtro.bind("<<ComboboxSelected>>", lambda _e: self._refrescar_tabla_bh())

        lbl_b = tk.Label(barra, text="Buscar:", font=("Segoe UI", 9, "bold"))
        lbl_b.pack(side="left")
        self._registrar_tema(lbl_b, {"bg": "surface", "fg": "muted"})

        ent_busq = ttk.Entry(
            barra, textvariable=self.var_busqueda_bh, style="Modern.TEntry", width=26
        )
        ent_busq.pack(side="left", padx=(6, 8))
        ent_busq.bind("<KeyRelease>", lambda _e: self._refrescar_tabla_bh())

        self.lbl_count_bh = tk.Label(barra, text="0 tripletas", font=("Segoe UI", 9, "bold"))
        self.lbl_count_bh.pack(side="right")
        self._registrar_tema(self.lbl_count_bh, {"bg": "surface", "fg": "accent"})

        frame_tv = tk.Frame(tab, highlightthickness=1)
        frame_tv.pack(fill="both", expand=True)
        self._registrar_tema(frame_tv, {"bg": "card", "highlightbackground": "border"})

        sc = ttk.Scrollbar(frame_tv, style=self._scrollbar_style)
        sc.pack(side="right", fill="y")

        self.tv_bh = ttk.Treeview(
            frame_tv,
            columns=("Sujeto", "Predicado", "Objeto", "Origen"),
            show="headings",
            style="Modern.Treeview",
            yscrollcommand=sc.set,
        )
        self.tv_bh.heading("Sujeto", text="Sujeto")
        self.tv_bh.heading("Predicado", text="Predicado")
        self.tv_bh.heading("Objeto", text="Objeto")
        self.tv_bh.heading("Origen", text="Origen")
        self.tv_bh.column("Sujeto", width=110)
        self.tv_bh.column("Predicado", width=165)
        self.tv_bh.column("Objeto", width=185)
        self.tv_bh.column("Origen", width=165)
        self.tv_bh.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_bh.yview)

    def _construir_tab_formulario(self) -> None:
        tab = tk.Frame(self.contenedor_tabs)
        self.frames_tabs["formulario"] = tab
        self._registrar_tema(tab, {"bg": "surface"})

        canvas = tk.Canvas(tab, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview, style=self._scrollbar_style)
        contenedor = tk.Frame(canvas, padx=12, pady=12)

        self._registrar_tema(canvas, {"bg": "surface"})
        self._registrar_tema(contenedor, {"bg": "surface"})

        contenedor.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=contenedor, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y", padx=(0, 3), pady=4)
        self._vincular_scroll_mouse(canvas, canvas)
        self._vincular_scroll_mouse(contenedor, canvas)

        def crear_seccion(titulo: str) -> tk.Frame:
            card = tk.Frame(contenedor, padx=12, pady=10, highlightthickness=1)
            card.pack(fill="x", pady=(0, 10))
            self._registrar_tema(card, {"bg": "card", "highlightbackground": "border"})
            lbl = tk.Label(card, text=titulo, font=("Segoe UI", 9, "bold"))
            lbl.pack(anchor="w", pady=(0, 8))
            self._registrar_tema(lbl, {"bg": "card", "fg": "accent"})
            body = tk.Frame(card)
            body.pack(fill="x")
            self._registrar_tema(body, {"bg": "card"})
            self._vincular_scroll_mouse(card, canvas)
            self._vincular_scroll_mouse(body, canvas)
            return body

        # Datos generales
        sec_gen = crear_seccion("DATOS DEL LOTE")
        self.form_id_lote = tk.StringVar(value="Lote_001")
        self.form_tipo = tk.StringVar(value="CTA")
        self.form_color_max = tk.StringVar(value="")

        for col_i, (txt, w) in enumerate([("ID Lote:", 0), ("Tipo Azúcar:", 2), ("Color Máx Cliente:", 4)]):
            l = tk.Label(sec_gen, text=txt, font=("Segoe UI", 9))
            l.grid(row=0, column=w, sticky="w", padx=(0 if col_i == 0 else 10, 4), pady=2)
            self._registrar_tema(l, {"bg": "card", "fg": "muted"})

        ttk.Entry(sec_gen, textvariable=self.form_id_lote, style="Modern.TEntry", width=13).grid(
            row=0, column=1, padx=4, pady=2
        )
        ttk.Combobox(
            sec_gen,
            textvariable=self.form_tipo,
            values=["CTA", "Crudo", "Organica"],
            state="readonly",
            style="Modern.TCombobox",
            width=10,
        ).grid(row=0, column=3, padx=4, pady=2)
        ttk.Entry(sec_gen, textvariable=self.form_color_max, style="Modern.TEntry", width=9).grid(
            row=0, column=5, padx=4, pady=2
        )

        # Mediciones numéricas
        sec_med = crear_seccion("MEDICIONES NUMÉRICAS")
        self.form_mediciones: dict[str, tk.StringVar] = {}
        for idx, clave in enumerate(PROPIEDADES_MEDICION):
            nombre, unidad = ETIQUETAS_MEDICIONES[clave]
            var = tk.StringVar(value="")
            self.form_mediciones[clave] = var
            fila, col = divmod(idx, 2)
            l = tk.Label(sec_med, text=f"{nombre} ({unidad}):", font=("Segoe UI", 9))
            l.grid(row=fila, column=col * 2, sticky="w", padx=(0 if col == 0 else 12, 4), pady=3)
            self._registrar_tema(l, {"bg": "card", "fg": "text"})
            ttk.Entry(sec_med, textvariable=var, style="Modern.TEntry", width=11).grid(
                row=fila, column=col * 2 + 1, sticky="w", padx=4, pady=3
            )

        # Eventos booleanos
        sec_ev = crear_seccion("EVENTOS Y OBSERVACIONES")
        self.form_eventos: dict[str, tk.BooleanVar] = {}
        for idx, clave in enumerate(PROPIEDADES_EVENTO):
            var = tk.BooleanVar(value=False)
            self.form_eventos[clave] = var
            fila, col = divmod(idx, 2)
            chk = tk.Checkbutton(
                sec_ev,
                text=ETIQUETAS_EVENTOS.get(clave, clave),
                variable=var,
                font=("Segoe UI", 9),
                relief="flat",
                bd=0,
                highlightthickness=0,
                anchor="w",
                cursor="hand2",
            )
            chk.grid(row=fila, column=col, sticky="w", padx=4, pady=2)
            self._registrar_tema(
                chk,
                {
                    "bg": "card",
                    "activebackground": "card",
                    "fg": "text",
                    "activeforeground": "text",
                    "selectcolor": "input_bg",
                },
            )
            self._vincular_scroll_mouse(chk, canvas)

        # Seguimiento
        sec_seg = crear_seccion("SEGUIMIENTO Y ACCIONES APLICADAS")
        self.form_horas = tk.StringVar(value="0")
        self.form_dos_muestras = tk.BooleanVar(value=False)

        lh = tk.Label(sec_seg, text="Horas desde corrección:", font=("Segoe UI", 9))
        lh.grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self._registrar_tema(lh, {"bg": "card", "fg": "text"})
        ttk.Entry(sec_seg, textvariable=self.form_horas, style="Modern.TEntry", width=8).grid(
            row=0, column=1, sticky="w", padx=4, pady=3
        )
        chk_2m = tk.Checkbutton(
            sec_seg,
            text="2 muestras horarias seguidas dentro de ficha",
            variable=self.form_dos_muestras,
            font=("Segoe UI", 9),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        chk_2m.grid(row=0, column=2, columnspan=2, sticky="w", padx=10, pady=3)
        self._registrar_tema(
            chk_2m,
            {
                "bg": "card",
                "activebackground": "card",
                "fg": "text",
                "activeforeground": "text",
                "selectcolor": "input_bg",
            },
        )

        self.form_acciones_aplicadas: dict[str, tk.BooleanVar] = {}
        for idx, acc in enumerate(ACCIONES_SEGUIMIENTO):
            var = tk.BooleanVar(value=False)
            self.form_acciones_aplicadas[acc] = var
            chk_acc = tk.Checkbutton(
                sec_seg,
                text=f"Aplicada: {acc}",
                variable=var,
                font=("Segoe UI", 9),
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )
            chk_acc.grid(
                row=1 + idx // 2, column=(idx % 2) * 2, columnspan=2, sticky="w", padx=4, pady=2
            )
            self._registrar_tema(
                chk_acc,
                {
                    "bg": "card",
                    "activebackground": "card",
                    "fg": "text",
                    "activeforeground": "text",
                    "selectcolor": "input_bg",
                },
            )

        self.btn_reevaluar = ModernButton(
            contenedor,
            text="Re-evaluar desde Formulario  ▶",
            command=self._reevaluar_desde_formulario,
            variant="primary",
            padx=16,
            pady=8,
            tema=self.t,
        )
        self.btn_reevaluar.pack(anchor="e", pady=(2, 8))
        self._botones_modernos.append(self.btn_reevaluar)

    # ==================== TEMA DUAL Y SCROLL ====================

    def _vincular_scroll_mouse(self, widget: tk.Widget, canvas_destino: tk.Canvas) -> None:
        widget.bind(
            "<MouseWheel>",
            lambda e: canvas_destino.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            add="+",
        )

    def _on_canvas_chat_resize(self, event: Any) -> None:
        self.canvas_chat.itemconfigure(self._chat_win_id, width=event.width)
        self.root.after_idle(self._recalcular_alturas_tarjetas_chat)

    def _recalcular_alturas_tarjetas_chat(self) -> None:
        for txt in self._tarjetas_texto_chat:
            if txt.winfo_exists():
                self._ajustar_altura_text_card(txt)

    def _alternar_tema(self) -> None:
        self.tema_actual = "light" if self.tema_actual == "dark" else "dark"
        self.t = TEMAS[self.tema_actual]
        self.btn_tema.configure(
            text="☀ Tema Claro" if self.tema_actual == "dark" else "🌙 Tema Oscuro"
        )
        self._aplicar_tema_global()
        _aplicar_titulo_dwm_windows(self.root, self.tema_actual == "dark")

    def _aplicar_tema_global(self) -> None:
        t = self.t
        self.root.configure(bg=t["bg"])
        self._configurar_estilos_ttk()

        for widget, mapa in self._widgets_tema:
            if not widget.winfo_exists():
                continue
            kwargs = {prop: t[clave] for prop, clave in mapa.items()}
            try:
                widget.configure(**kwargs)
            except tk.TclError:
                pass

        for btn in self._botones_modernos:
            if btn.winfo_exists():
                btn.apply_theme(t)

        # Tags de tablas Treeview
        self.tv_hechos_caso.tag_configure("odd", background=t["row_odd"])
        self.tv_hechos_caso.tag_configure("even", background=t["row_even"])
        self.tv_ciclos.tag_configure("odd", background=t["row_odd"])
        self.tv_ciclos.tag_configure("even", background=t["row_even"])
        self.tv_bh.tag_configure("inferred", background=t["row_even"], foreground=t["inferred_fg"])
        self.tv_bh.tag_configure("initial", background=t["row_odd"], foreground=t["initial_fg"])

        self._actualizar_badge_motor()
        self._reconstruir_chat_desde_historial()
        if self.ultimo_resultado:
            self._actualizar_kpis(self.ultimo_resultado)
            self._refrescar_tabla_bh()

    def _actualizar_badge_motor(self) -> None:
        t = self.t
        es_hibrido = self.var_modo.get().startswith("Híbrido")
        if es_hibrido and self.api_key:
            self.lbl_badge_motor.configure(text="● Híbrido Gemini API", bg=t["info_bg"], fg=t["info"])
        elif es_hibrido:
            self.lbl_badge_motor.configure(
                text="● Híbrido (sin clave → Local)", bg=t["warn_bg"], fg=t["warn"]
            )
        else:
            self.lbl_badge_motor.configure(text="● PLN Local Offline", bg=t["ok_bg"], fg=t["ok"])

    # ==================== CHAT CON TARJETAS MODERNAS ====================

    def _mostrar_bienvenida(self) -> None:
        self._mensajes_chat.clear()
        self._mensajes_chat.append({"tipo": "bienvenida"})
        self._reconstruir_chat_desde_historial()

    def _reconstruir_chat_desde_historial(self) -> None:
        for hijo in self.frame_chat_msgs.winfo_children():
            hijo.destroy()
        self._tarjetas_texto_chat.clear()

        for msg in self._mensajes_chat:
            if msg["tipo"] == "bienvenida":
                self._render_tarjeta_bienvenida()
            else:
                self._render_tarjeta_mensaje(msg)

        self.root.after_idle(self._scroll_chat_al_final)

    def _scroll_chat_al_final(self) -> None:
        self._recalcular_alturas_tarjetas_chat()
        self.canvas_chat.update_idletasks()
        self.canvas_chat.yview_moveto(1.0)

    def _render_tarjeta_bienvenida(self) -> None:
        t = self.t
        card = tk.Frame(
            self.frame_chat_msgs,
            bg=t["card"],
            highlightthickness=1,
            highlightbackground=t["border"],
            padx=14,
            pady=12,
        )
        card.pack(fill="x", pady=(2, 10))
        self._vincular_scroll_mouse(card, self.canvas_chat)

        lbl_t = tk.Label(
            card,
            text="Bienvenido al Asesor Virtual del SBC",
            bg=t["card"],
            fg=t["accent"],
            font=("Segoe UI", 11, "bold"),
        )
        lbl_t.pack(anchor="w")

        lbl_d = tk.Label(
            card,
            text=(
                "Describí lo que ocurre en planta o laboratorio en lenguaje natural. "
                "El sistema traduce tu consulta a tripletas RDF, ejecuta las 72 reglas SPARQL "
                "(R1–R56) por prioridad y responde con el dictamen, la causa raíz y las órdenes correctivas."
            ),
            bg=t["card"],
            fg=t["text"],
            font=("Segoe UI", 9),
            justify="left",
            wraplength=560,
        )
        lbl_d.pack(anchor="w", pady=(4, 10))

        lbl_ch = tk.Label(
            card,
            text="Probar un escenario con un clic:",
            bg=t["card"],
            fg=t["muted"],
            font=("Segoe UI", 8, "bold"),
        )
        lbl_ch.pack(anchor="w", pady=(0, 6))

        chips_box = tk.Frame(card, bg=t["card"])
        chips_box.pack(fill="x")

        for ej in CASOS_EJEMPLO[:4]:
            chip = ModernButton(
                chips_box,
                text="▶  " + ej["titulo"],
                command=lambda q=ej["consulta"]: self.procesar_consulta(q, sincrono=False),
                variant="secondary",
                padx=10,
                pady=5,
                font=("Segoe UI", 8, "bold"),
                tema=t,
            )
            chip.pack(anchor="w", pady=2)

    def _ajustar_altura_text_card(self, txt_widget: tk.Text) -> None:
        try:
            txt_widget.update_idletasks()
            conteo = txt_widget.count("1.0", "end", "displaylines")
            if conteo and conteo[0] is not None:
                lineas = max(1, int(conteo[0]))
            else:
                texto = txt_widget.get("1.0", "end-1c")
                ancho = max(txt_widget.winfo_width(), 380)
                cpl = max(42, ancho // 8)
                lineas = sum(max(1, (len(l) + cpl - 1) // cpl) for l in texto.split("\n"))
            txt_widget.configure(height=lineas)
        except tk.TclError:
            pass

    def _render_tarjeta_mensaje(self, msg: dict[str, Any]) -> None:
        t = self.t
        es_usuario = msg["es_usuario"]

        fila = tk.Frame(self.frame_chat_msgs, bg=t["surface"])
        fila.pack(fill="x", pady=(0, 10))
        self._vincular_scroll_mouse(fila, self.canvas_chat)

        if es_usuario:
            bubble = tk.Frame(
                fila,
                bg=t["user_bubble"],
                highlightthickness=1,
                highlightbackground=t["user_border"],
                padx=12,
                pady=10,
            )
            bubble.pack(side="right", fill="x", padx=(70, 0), expand=True)
            self._vincular_scroll_mouse(bubble, self.canvas_chat)

            hdr = tk.Label(
                bubble,
                text=f"👤  {msg['emisor']}",
                bg=t["user_bubble"],
                fg=t["accent"],
                font=("Segoe UI", 9, "bold"),
            )
            hdr.pack(anchor="w", pady=(0, 4))

            txt = tk.Text(
                bubble,
                wrap="word",
                bg=t["user_bubble"],
                fg=t["text"],
                font=("Segoe UI", 10),
                relief="flat",
                bd=0,
                highlightthickness=0,
                height=2,
            )
            txt.insert("1.0", msg["texto"].strip())
            txt.configure(state="disabled")
            txt.pack(fill="x")
            self._tarjetas_texto_chat.append(txt)
            self._vincular_scroll_mouse(txt, self.canvas_chat)
            self.root.after_idle(lambda w=txt: self._ajustar_altura_text_card(w))
            return

        # Tarjeta de respuesta del SBC con barra lateral de estado
        estado = msg.get("estado_badge", "info")
        if estado == "ok":
            color_estado, bg_badge, txt_badge = t["ok"], t["ok_bg"], "● LOTE APROBADO"
        elif estado == "bad":
            color_estado, bg_badge, txt_badge = t["bad"], t["bad_bg"], "● NO CONFORME / RECHAZADO"
        elif estado == "warn":
            color_estado, bg_badge, txt_badge = t["warn"], t["warn_bg"], "● EVALUACIÓN EN CURSO"
        else:
            color_estado, bg_badge, txt_badge = t["info"], t["info_bg"], "● ORGÁNICA / CONTEXTO"

        card = tk.Frame(
            fila,
            bg=t["card"],
            highlightthickness=1,
            highlightbackground=t["border"],
        )
        card.pack(side="left", fill="x", padx=(0, 28), expand=True)
        self._vincular_scroll_mouse(card, self.canvas_chat)

        barra_lat = tk.Frame(card, bg=color_estado, width=4)
        barra_lat.pack(side="left", fill="y")

        cuerpo = tk.Frame(card, bg=t["card"], padx=12, pady=10)
        cuerpo.pack(side="left", fill="both", expand=True)
        self._vincular_scroll_mouse(cuerpo, self.canvas_chat)

        cab = tk.Frame(cuerpo, bg=t["card"])
        cab.pack(fill="x", pady=(0, 6))

        tk.Label(
            cab,
            text=f"🏭  {msg['emisor']}",
            bg=t["card"],
            fg=t["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        tk.Label(
            cab,
            text=txt_badge,
            bg=bg_badge,
            fg=color_estado,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        ).pack(side="right")

        txt = tk.Text(
            cuerpo,
            wrap="word",
            bg=t["card"],
            fg=t["text"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=0,
            height=4,
        )
        txt.tag_configure("sec", font=("Segoe UI", 10, "bold"), foreground=t["accent"], spacing1=6)
        txt.tag_configure("ok", font=("Segoe UI", 10, "bold"), foreground=t["ok"])
        txt.tag_configure("bad", font=("Segoe UI", 10, "bold"), foreground=t["bad"])
        txt.tag_configure("warn", font=("Segoe UI", 10, "bold"), foreground=t["warn"])
        txt.tag_configure("body", font=("Segoe UI", 10), foreground=t["text"])

        lineas = msg["texto"].strip().splitlines()
        for i, linea in enumerate(lineas):
            tag = "body"
            if re.match(r"^\d+\.\s+[A-ZÁÉÍÓÚÑ\s]+$", linea.strip()):
                tag = "sec"
            elif "NO CONFORME" in linea or "RECHAZADO" in linea:
                tag = "bad"
            elif "APROBADO" in linea:
                tag = "ok"
            elif "ADVERTENCIA" in linea or "crítico" in linea.lower():
                tag = "warn"
            sufijo = "\n" if i < len(lineas) - 1 else ""
            txt.insert("end", linea + sufijo, tag)

        txt.configure(state="disabled")
        txt.pack(fill="x")
        self._tarjetas_texto_chat.append(txt)
        self._vincular_scroll_mouse(txt, self.canvas_chat)
        self.root.after_idle(lambda w=txt: self._ajustar_altura_text_card(w))

    # ==================== LÓGICA DE CONSULTA Y EVENTOS ====================

    def _configurar_api_key(self) -> None:
        t = self.t
        dlg = tk.Toplevel(self.root)
        dlg.title("Configurar API Key de Gemini")
        dlg.configure(bg=t["surface"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        frame = tk.Frame(dlg, bg=t["surface"], padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="API Key de Google Gemini",
            bg=t["surface"],
            fg=t["text"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frame,
            text=(
                "Se almacena únicamente en memoria durante esta sesión.\n"
                "Si la dejás vacía, el SBC usará el motor PLN local offline."
            ),
            bg=t["surface"],
            fg=t["muted"],
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        var_key = tk.StringVar(value=self.api_key)
        ent = ttk.Entry(frame, textvariable=var_key, show="*", style="Modern.TEntry", width=46)
        ent.pack(fill="x", pady=(0, 8))
        ent.focus_set()

        var_mostrar = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            frame,
            text="Mostrar clave",
            variable=var_mostrar,
            command=lambda: ent.configure(show="" if var_mostrar.get() else "*"),
            bg=t["surface"],
            activebackground=t["surface"],
            fg=t["muted"],
            activeforeground=t["text"],
            selectcolor=t["input_bg"],
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        chk.pack(anchor="w", pady=(0, 12))

        btns = tk.Frame(frame, bg=t["surface"])
        btns.pack(fill="x")

        def guardar() -> None:
            self.api_key = var_key.get().strip()
            if self.api_key:
                self.var_modo.set("Híbrido (Gemini API + Fallback Local)")
            else:
                self.var_modo.set("Local (100% Python Offline)")
            self._actualizar_badge_motor()
            dlg.destroy()

        ModernButton(btns, text="Guardar", command=guardar, variant="primary", tema=t).pack(side="right")
        ModernButton(
            btns, text="Cancelar", command=dlg.destroy, variant="secondary", tema=t
        ).pack(side="right", padx=(0, 8))

        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dlg.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _cargar_ejemplo_seleccionado(self, _event: Any = None) -> None:
        titulo = self.var_ejemplo.get()
        for ej in CASOS_EJEMPLO:
            if ej["titulo"] == titulo:
                self.txt_input.delete("1.0", "end")
                self.txt_input.insert("1.0", ej["consulta"])
                self.root.after_idle(self._ajustar_altura_input)
                break

    def _on_ctrl_enter(self, _event: Any = None) -> str:
        self._enviar_desde_ui()
        return "break"

    def _on_input_modified(self, _event: Any = None) -> None:
        if self.txt_input.edit_modified():
            self.txt_input.edit_modified(False)
            self._ajustar_altura_input()

    def _ajustar_altura_input(self, _event: Any = None) -> None:
        """Ajusta dinámicamente la altura del cuadro de consulta entre min y max líneas."""
        texto = self.txt_input.get("1.0", "end-1c")
        if not texto:
            lineas_visibles = self._altura_input_min
        else:
            conteo = self.txt_input.count("1.0", "end", "displaylines")
            if conteo and conteo[0] is not None:
                lineas_visibles = int(conteo[0])
            else:
                ancho_px = max(self.txt_input.winfo_width(), 320)
                chars_por_linea = max(35, ancho_px // 8)
                lineas_visibles = sum(
                    max(1, (len(linea) + chars_por_linea - 1) // chars_por_linea)
                    for linea in texto.split("\n")
                )

        nueva_altura = max(self._altura_input_min, min(self._altura_input_max, lineas_visibles))
        if nueva_altura != self._altura_input_actual:
            self._altura_input_actual = nueva_altura
            self.txt_input.configure(height=nueva_altura)

    def _limpiar_chat(self) -> None:
        self._mostrar_bienvenida()

    def _agregar_mensaje_chat(
        self, emisor: str, texto: str, es_usuario: bool, estado_badge: str = "info"
    ) -> None:
        msg = {
            "tipo": "mensaje",
            "emisor": emisor,
            "texto": texto,
            "es_usuario": es_usuario,
            "estado_badge": estado_badge,
        }
        self._mensajes_chat.append(msg)
        self._render_tarjeta_mensaje(msg)
        self.root.after_idle(self._scroll_chat_al_final)

    def _enviar_desde_ui(self) -> None:
        if self.consultando:
            return
        texto = self.txt_input.get("1.0", "end").strip()
        if not texto:
            return
        self.txt_input.delete("1.0", "end")
        self._ajustar_altura_input()
        self.procesar_consulta(texto, sincrono=False)

    def procesar_consulta(self, texto: str, sincrono: bool = True) -> dict[str, Any] | None:
        """Procesa una consulta en LN (síncrono para tests o asíncrono en hilo para GUI)."""
        self._agregar_mensaje_chat("Jefe de Turno (Consulta)", texto, es_usuario=True)

        usar_gemini = self.var_modo.get().startswith("Híbrido")
        autocompletar = self.var_autocompletar.get()

        if sincrono:
            datos, meta = traducir_consulta_a_hechos(
                texto,
                autocompletar_normales=autocompletar,
                usar_gemini=usar_gemini,
                api_key=self.api_key,
            )
            resultado = evaluar_caso(datos)
            respuesta = generar_respuesta_natural(
                texto, resultado, meta, usar_gemini=usar_gemini, api_key=self.api_key
            )
            self._aplicar_resultado_ui(respuesta, resultado, meta)
            return resultado

        self.consultando = True
        self.btn_consultar.set_enabled(False)
        self.lbl_estado_proc.configure(text="● Procesando...", fg=self.t["warn"])

        def tarea() -> None:
            try:
                datos, meta = traducir_consulta_a_hechos(
                    texto,
                    autocompletar_normales=autocompletar,
                    usar_gemini=usar_gemini,
                    api_key=self.api_key,
                )
                resultado = evaluar_caso(datos)
                respuesta = generar_respuesta_natural(
                    texto, resultado, meta, usar_gemini=usar_gemini, api_key=self.api_key
                )
                self.root.after(0, lambda: self._finalizar_consulta_async(respuesta, resultado, meta, None))
            except Exception as exc:
                self.root.after(0, lambda: self._finalizar_consulta_async("", None, None, exc))

        threading.Thread(target=tarea, daemon=True).start()
        return None

    def _finalizar_consulta_async(
        self,
        respuesta: str,
        resultado: dict[str, Any] | None,
        meta: dict[str, Any] | None,
        error: Exception | None,
    ) -> None:
        self.consultando = False
        self.btn_consultar.set_enabled(True)
        self.lbl_estado_proc.configure(text="● Listo", fg=self.t["ok"])
        if error is not None:
            messagebox.showerror("Error en el SBC", str(error), parent=self.root)
            return
        if resultado is not None and meta is not None:
            self._aplicar_resultado_ui(respuesta, resultado, meta)

    def _aplicar_resultado_ui(
        self, respuesta: str, resultado: dict[str, Any], meta: dict[str, Any]
    ) -> None:
        self.ultimo_resultado = resultado
        self.ultima_meta = meta

        estados = resultado["estado_lote"]
        if "NoConforme" in estados or "EnDeposito" in estados:
            badge = "bad"
        elif "Aprobado" in estados:
            badge = "ok"
        elif resultado["datos_entrada"]["tipo_azucar"] == "Organica":
            badge = "info"
        else:
            badge = "warn"

        self._agregar_mensaje_chat(
            f"SBC Asesor Virtual · {meta['metodo']}",
            respuesta,
            es_usuario=False,
            estado_badge=badge,
        )
        self._actualizar_kpis(resultado)
        self._actualizar_tab_traduccion(resultado, meta)
        self._actualizar_tab_ciclos(resultado)
        self._refrescar_tabla_bh()
        self._sincronizar_formulario(resultado["datos_entrada"])

    def _actualizar_kpis(self, resultado: dict[str, Any]) -> None:
        t = self.t
        datos = resultado["datos_entrada"]
        estados = resultado["estado_lote"]

        _, _, v_lote = self.kpis["lote"]
        v_lote.configure(text=f"{datos['id_lote']} · {datos['tipo_azucar']}", fg=t["text"])

        _, _, v_dict = self.kpis["dictamen"]
        if "NoConforme" in estados or "EnDeposito" in estados:
            v_dict.configure(text="No Conforme", fg=t["bad"])
        elif "Aprobado" in estados:
            v_dict.configure(text="Aprobado", fg=t["ok"])
        elif datos["tipo_azucar"] == "Organica":
            v_dict.configure(text="Orgánica (R47)", fg=t["info"])
        else:
            v_dict.configure(text="En curso", fg=t["warn"])

        _, _, v_cic = self.kpis["ciclos"]
        n_cic = len(resultado["activaciones"])
        v_cic.configure(text=f"{n_cic} ciclos", fg=t["accent"])

        _, _, v_tri = self.kpis["tripletas"]
        n_tri = len(resultado["historial_bh"])
        n_inf = sum(1 for r in resultado["historial_bh"] if r["origen"] != "Inicial")
        v_tri.configure(text=f"{n_tri} ({n_inf} inf.)", fg=t["text"])

    def _actualizar_tab_traduccion(self, resultado: dict[str, Any], meta: dict[str, Any]) -> None:
        lineas = [f"Método utilizado: {meta.get('metodo', 'Local')}"]
        if meta.get("parametros_extraidos"):
            lineas.append("\n[Parámetros Numéricos Extraídos]")
            lineas.extend(f"  + {p}" for p in meta["parametros_extraidos"])
        if meta.get("inferencias_cualitativas"):
            lineas.append("\n[Inferencias Cualitativas S1–S8]")
            lineas.extend(f"  ~ {i}" for i in meta["inferencias_cualitativas"])
        if meta.get("eventos_detectados"):
            lineas.append("\n[Eventos Detectados]")
            lineas.extend(f"  * {e}" for e in meta["eventos_detectados"])
        if meta.get("autocompletados"):
            lineas.append("\n[Ficha Autocompletada con Referencia Normal]")
            lineas.extend(f"  . {a}" for a in meta["autocompletados"])
        if meta.get("notas"):
            lineas.append("\n[Notas]")
            lineas.extend(f"  ! {n}" for n in meta["notas"])

        self.txt_meta_pln.config(state="normal")
        self.txt_meta_pln.delete("1.0", "end")
        self.txt_meta_pln.insert("1.0", "\n".join(lineas))
        self.txt_meta_pln.config(state="disabled")

        for item in self.tv_hechos_caso.get_children():
            self.tv_hechos_caso.delete(item)

        filas: list[tuple[str, str, str]] = []
        datos = resultado["datos_entrada"]
        filas.append(("ID Lote", datos["id_lote"], "Identificador"))
        filas.append(("Tipo de azúcar", datos["tipo_azucar"], "CTA / Crudo / Organica"))
        lim_col = datos.get("ficha_cliente", {}).get("color_max_ui")
        if lim_col is not None:
            filas.append(("Color máx. ficha cliente", str(lim_col), "UI"))

        for k, val in datos["mediciones"].items():
            if val is not None:
                nombre, unidad = ETIQUETAS_MEDICIONES[k]
                filas.append((nombre, f"{val:g}", unidad))

        for k, activo in datos["eventos"].items():
            if activo:
                filas.append((ETIQUETAS_EVENTOS.get(k, k), "true", "Evento"))

        if datos["acciones_aplicadas"]:
            filas.append(
                ("Acciones ya aplicadas", ", ".join(datos["acciones_aplicadas"]), "Seguimiento")
            )
        seg = datos["seguimiento"]
        if seg["horas_desde_correccion"]:
            filas.append(("Horas desde corrección", str(seg["horas_desde_correccion"]), "h"))
        if seg["dos_muestras_horarias_dentro_ficha"]:
            filas.append(("2 muestras horarias conformes", "true", "R56"))

        for idx, valores in enumerate(filas):
            tag = "even" if idx % 2 == 0 else "odd"
            self.tv_hechos_caso.insert("", "end", values=valores, tags=(tag,))

    def _actualizar_tab_ciclos(self, resultado: dict[str, Any]) -> None:
        for item in self.tv_ciclos.get_children():
            self.tv_ciclos.delete(item)

        for idx, act in enumerate(resultado["activaciones"]):
            tag = "even" if idx % 2 == 0 else "odd"
            self.tv_ciclos.insert(
                "",
                "end",
                iid=str(act["ciclo"]),
                values=(
                    act["ciclo"],
                    act["regla"],
                    act["prioridad"],
                    act["hechos_nuevos"],
                    act["descripcion"],
                ),
                tags=(tag,),
            )

        self.txt_detalle_ciclo.config(state="normal")
        self.txt_detalle_ciclo.delete("1.0", "end")
        if resultado["activaciones"]:
            self.txt_detalle_ciclo.insert(
                "1.0", "Seleccioná un ciclo de la tabla para inspeccionar las tripletas RDF deducidas."
            )
        self.txt_detalle_ciclo.config(state="disabled")

    def _mostrar_detalle_ciclo(self, _event: Any = None) -> None:
        if not self.ultimo_resultado:
            return
        sel = self.tv_ciclos.selection()
        if not sel:
            return
        ciclo_num = int(sel[0])
        for act in self.ultimo_resultado["activaciones"]:
            if act["ciclo"] == ciclo_num:
                self.txt_detalle_ciclo.config(state="normal")
                self.txt_detalle_ciclo.delete("1.0", "end")
                self.txt_detalle_ciclo.insert(
                    "1.0",
                    f"Ciclo {act['ciclo']} — {act['regla']} (Prioridad {act['prioridad']}):\n"
                    + "\n".join(f"  + {t}" for t in act["tripletas"]),
                )
                self.txt_detalle_ciclo.config(state="disabled")
                break

    def _refrescar_tabla_bh(self) -> None:
        for item in self.tv_bh.get_children():
            self.tv_bh.delete(item)
        if not self.ultimo_resultado:
            self.lbl_count_bh.config(text="0 tripletas")
            return

        filtro = self.var_filtro_bh.get()
        busq = self.var_busqueda_bh.get().strip().lower()
        filas = []
        for row in self.ultimo_resultado["historial_bh"]:
            if filtro == "Solo Inferidos" and row["origen"] == "Inicial":
                continue
            if filtro == "Solo Iniciales" and row["origen"] != "Inicial":
                continue
            if busq:
                texto_fila = f"{row['sujeto']} {row['predicado']} {row['objeto']} {row['origen']}".lower()
                if busq not in texto_fila:
                    continue
            filas.append(row)

        for row in filas:
            tag = "initial" if row["origen"] == "Inicial" else "inferred"
            self.tv_bh.insert(
                "",
                "end",
                values=(row["sujeto"], row["predicado"], row["objeto"], row["origen"]),
                tags=(tag,),
            )
        self.lbl_count_bh.config(text=f"{len(filas)} tripletas")

    def _sincronizar_formulario(self, datos: dict[str, Any]) -> None:
        self.form_id_lote.set(datos.get("id_lote", "Lote_001"))
        self.form_tipo.set(datos.get("tipo_azucar", "CTA"))
        lim = datos.get("ficha_cliente", {}).get("color_max_ui")
        self.form_color_max.set("" if lim is None else str(lim))

        for k, var in self.form_mediciones.items():
            val = datos.get("mediciones", {}).get(k)
            var.set("" if val is None else f"{val:g}")

        for k, var in self.form_eventos.items():
            var.set(bool(datos.get("eventos", {}).get(k, False)))

        seg = datos.get("seguimiento", {})
        self.form_horas.set(str(seg.get("horas_desde_correccion", 0)))
        self.form_dos_muestras.set(bool(seg.get("dos_muestras_horarias_dentro_ficha", False)))

        aplicadas = set(datos.get("acciones_aplicadas", []))
        for acc, var in self.form_acciones_aplicadas.items():
            var.set(acc in aplicadas)

    def _reevaluar_desde_formulario(self) -> None:
        try:
            datos = crear_caso_vacio(
                id_lote=self.form_id_lote.get().strip() or "Lote_001",
                tipo_azucar=self.form_tipo.get() or "CTA",
            )
            col_max_str = self.form_color_max.get().strip()
            if col_max_str:
                datos["ficha_cliente"]["color_max_ui"] = float(col_max_str.replace(",", "."))

            for k, var in self.form_mediciones.items():
                txt = var.get().strip()
                if txt:
                    datos["mediciones"][k] = float(txt.replace(",", "."))

            for k, var in self.form_eventos.items():
                datos["eventos"][k] = bool(var.get())

            horas_txt = self.form_horas.get().strip() or "0"
            datos["seguimiento"]["horas_desde_correccion"] = float(horas_txt.replace(",", "."))
            datos["seguimiento"]["dos_muestras_horarias_dentro_ficha"] = bool(
                self.form_dos_muestras.get()
            )
            datos["acciones_aplicadas"] = [
                acc for acc, var in self.form_acciones_aplicadas.items() if var.get()
            ]
        except ValueError as exc:
            messagebox.showerror(
                "Dato numérico inválido", f"Revisá los valores ingresados: {exc}", parent=self.root
            )
            return

        meta = {
            "metodo": "Formulario Manual",
            "parametros_extraidos": [
                f"{k} = {v}" for k, v in datos["mediciones"].items() if v is not None
            ],
            "inferencias_cualitativas": [],
            "eventos_detectados": [
                ETIQUETAS_EVENTOS[k] for k, v in datos["eventos"].items() if v
            ],
            "autocompletados": [],
            "notas": ["Caso evaluado directamente desde el formulario manual."],
        }
        resultado = evaluar_caso(datos)
        consulta_desc = f"Evaluación manual desde formulario para {datos['id_lote']} ({datos['tipo_azucar']})."
        self._agregar_mensaje_chat("Jefe de Turno (Formulario)", consulta_desc, es_usuario=True)
        respuesta = generar_respuesta_natural(
            consulta_desc,
            resultado,
            meta,
            usar_gemini=self.var_modo.get().startswith("Híbrido"),
            api_key=self.api_key,
        )
        self._aplicar_resultado_ui(respuesta, resultado, meta)

    def _abrir_grafo_pyvis(self) -> None:
        if not self.ultimo_resultado:
            messagebox.showinfo(
                "Sin caso evaluado",
                "Primero realizá una consulta al SBC para generar el grafo RDF del caso.",
                parent=self.root,
            )
            return
        ruta = exportar_grafo_pyvis(
            self.ultimo_resultado["grafo"],
            self.ultimo_resultado["lote_uri"],
            ruta_salida="grafo_ingenio.html",
        )
        webbrowser.open(Path(ruta).as_uri())


def main() -> None:
    _habilitar_high_dpi_windows()
    root = tk.Tk()
    SBCApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
