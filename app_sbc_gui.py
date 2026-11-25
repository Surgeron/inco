"""
Interfaz Visual de Escritorio (Tkinter) para el SBC - Ingenio La Esperanza.

Permite ingresar consultas en lenguaje natural, visualizar la traducción a
hechos RDF, inspeccionar ciclo por ciclo el motor de inferencia SPARQL,
explorar la trazabilidad de la Base de Hechos, ajustar parámetros en un
formulario manual y abrir el grafo interactivo PyVis en el navegador.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

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


class SBCApp:
    """Aplicación de escritorio Tkinter para el SBC del Ingenio La Esperanza."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("SBC Ingenio La Esperanza — Asesor Virtual en Lenguaje Natural")
        self.root.geometry("1380x840")
        self.root.minsize(1100, 680)
        self.root.configure(bg="#EEF2F6")

        self.api_key: str = os.environ.get("GEMINI_API_KEY", "").strip()
        self.ultimo_resultado: dict[str, Any] | None = None
        self.ultima_meta: dict[str, Any] | None = None
        self.consultando = False

        self.var_modo = tk.StringVar(value="Local (100% Python Offline)")
        self.var_autocompletar = tk.BooleanVar(value=True)
        self.var_ejemplo = tk.StringVar(value="Cargar consulta de ejemplo...")
        self.var_filtro_bh = tk.StringVar(value="Todos")
        self.var_busqueda_bh = tk.StringVar(value="")

        self._configurar_estilos()
        self._construir_barra_superior()
        self._construir_cuerpo_principal()
        self._mostrar_bienvenida()

    def _configurar_estilos(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#EEF2F6")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#EEF2F6", foreground="#1F2937", font=("Segoe UI", 9))
        style.configure("Header.TLabel", background="#1B365D", foreground="#FFFFFF", font=("Segoe UI", 12, "bold"))
        style.configure("SubHeader.TLabel", background="#1B365D", foreground="#CBD5E1", font=("Segoe UI", 9))
        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 6))
        style.configure("TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=(10, 5))
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _construir_barra_superior(self) -> None:
        header = tk.Frame(self.root, bg="#1B365D", padx=14, pady=10)
        header.pack(fill="x")

        izq = tk.Frame(header, bg="#1B365D")
        izq.pack(side="left", fill="x", expand=True)

        tk.Label(
            izq,
            text="SBC Ingenio La Esperanza — Asesor Virtual de Control de Calidad",
            bg="#1B365D",
            fg="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            izq,
            text="Motor RDF/SPARQL CONSTRUCT (56 reglas R1–R56, supuestos S1–S12) + Traductor Híbrido LN↔SBC",
            bg="#1B365D",
            fg="#CBD5E1",
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        controles = tk.Frame(self.root, bg="#DDE6F0", padx=12, pady=8, bd=1, relief="groove")
        controles.pack(fill="x")

        tk.Label(controles, text="Modo PLN:", bg="#DDE6F0", fg="#1F2937", font=("Segoe UI", 9, "bold")).pack(
            side="left", padx=(0, 4)
        )
        cb_modo = ttk.Combobox(
            controles,
            textvariable=self.var_modo,
            values=["Local (100% Python Offline)", "Híbrido (Gemini API + Fallback Local)"],
            state="readonly",
            width=33,
        )
        cb_modo.pack(side="left", padx=(0, 8))

        ttk.Button(controles, text="Configurar API Key", command=self._configurar_api_key).pack(
            side="left", padx=(0, 12)
        )

        chk_auto = tk.Checkbutton(
            controles,
            text="Autocompletar ficha normal si faltan datos",
            variable=self.var_autocompletar,
            bg="#DDE6F0",
            activebackground="#DDE6F0",
            font=("Segoe UI", 9),
        )
        chk_auto.pack(side="left", padx=(0, 12))

        tk.Label(controles, text="Ejemplos:", bg="#DDE6F0", fg="#1F2937", font=("Segoe UI", 9, "bold")).pack(
            side="left", padx=(0, 4)
        )
        titulos_ej = [c["titulo"] for c in CASOS_EJEMPLO]
        self.cb_ejemplos = ttk.Combobox(
            controles,
            textvariable=self.var_ejemplo,
            values=titulos_ej,
            state="readonly",
            width=40,
        )
        self.cb_ejemplos.pack(side="left", padx=(0, 8))
        self.cb_ejemplos.bind("<<ComboboxSelected>>", self._cargar_ejemplo_seleccionado)

        self.btn_grafo = ttk.Button(
            controles,
            text="Ver Grafo RDF (PyVis)",
            command=self._abrir_grafo_pyvis,
        )
        self.btn_grafo.pack(side="right")

    def _construir_cuerpo_principal(self) -> None:
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Panel Izquierdo: Chat en Lenguaje Natural
        panel_chat = tk.Frame(paned, bg="#FFFFFF", bd=1, relief="solid")
        paned.add(panel_chat, weight=11)

        cabecera_chat = tk.Frame(panel_chat, bg="#F1F5F9", padx=10, pady=6)
        cabecera_chat.pack(fill="x")
        tk.Label(
            cabecera_chat,
            text="Conversación en Lenguaje Natural (Jefe de Turno ↔ SBC)",
            bg="#F1F5F9",
            fg="#0F172A",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        self.lbl_estado_proc = tk.Label(
            cabecera_chat,
            text="Listo",
            bg="#F1F5F9",
            fg="#475569",
            font=("Segoe UI", 9),
        )
        self.lbl_estado_proc.pack(side="right")

        frame_hist = tk.Frame(panel_chat, bg="#FFFFFF")
        frame_hist.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        scroll_chat = ttk.Scrollbar(frame_hist)
        scroll_chat.pack(side="right", fill="y")

        self.txt_chat = tk.Text(
            frame_hist,
            wrap="word",
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg="#1E293B",
            relief="flat",
            padx=8,
            pady=8,
            yscrollcommand=scroll_chat.set,
            state="disabled",
        )
        self.txt_chat.pack(side="left", fill="both", expand=True)
        scroll_chat.config(command=self.txt_chat.yview)

        self.txt_chat.tag_configure("user_header", font=("Segoe UI", 10, "bold"), foreground="#1D4ED8", spacing1=8)
        self.txt_chat.tag_configure("user_body", font=("Segoe UI", 10), foreground="#1E293B", lmargin1=12, lmargin2=12)
        self.txt_chat.tag_configure("sbc_header", font=("Segoe UI", 10, "bold"), foreground="#0F766E", spacing1=10)
        self.txt_chat.tag_configure("sbc_body", font=("Segoe UI", 10), foreground="#1E293B", lmargin1=12, lmargin2=12)
        self.txt_chat.tag_configure("sbc_ok", font=("Segoe UI", 10, "bold"), foreground="#15803D", lmargin1=12, lmargin2=12)
        self.txt_chat.tag_configure("sbc_bad", font=("Segoe UI", 10, "bold"), foreground="#B91C1C", lmargin1=12, lmargin2=12)
        self.txt_chat.tag_configure("sbc_warn", font=("Segoe UI", 10, "bold"), foreground="#B45309", lmargin1=12, lmargin2=12)
        self.txt_chat.tag_configure("sep", foreground="#CBD5E1")

        # Zona de entrada de consulta
        frame_input = tk.Frame(panel_chat, bg="#F8FAFC", padx=8, pady=8, bd=1, relief="groove")
        frame_input.pack(fill="x", padx=8, pady=(4, 8))

        tk.Label(
            frame_input,
            text="Escribí tu consulta o reporte del tacho/laboratorio (Ctrl+Enter para enviar):",
            bg="#F8FAFC",
            fg="#334155",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        frame_txt_input = tk.Frame(frame_input, bg="#FFFFFF", bd=1, relief="solid")
        frame_txt_input.pack(fill="x", pady=(0, 6))

        self.scroll_input = ttk.Scrollbar(frame_txt_input, orient="vertical")
        self.scroll_input.pack(side="right", fill="y")

        self._altura_input_min = 4
        self._altura_input_max = 14
        self._altura_input_actual = self._altura_input_min

        self.txt_input = tk.Text(
            frame_txt_input,
            height=self._altura_input_min,
            wrap="word",
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            relief="flat",
            padx=6,
            pady=4,
            yscrollcommand=self.scroll_input.set,
        )
        self.txt_input.pack(side="left", fill="x", expand=True)
        self.scroll_input.config(command=self.txt_input.yview)

        self.txt_input.bind("<Control-Return>", self._on_ctrl_enter)
        self.txt_input.bind("<KeyRelease>", self._ajustar_altura_input)
        self.txt_input.bind("<<Modified>>", self._on_input_modified)
        self.txt_input.bind("<Configure>", self._ajustar_altura_input)

        btns = tk.Frame(frame_input, bg="#F8FAFC")
        btns.pack(fill="x")
        self.btn_consultar = ttk.Button(
            btns,
            text="Consultar al SBC",
            style="Primary.TButton",
            command=self._enviar_desde_ui,
        )
        self.btn_consultar.pack(side="left")

        ttk.Button(btns, text="Limpiar Chat", command=self._limpiar_chat).pack(side="left", padx=(8, 0))

        # Panel Derecho: Transparencia Técnica (4 pestañas)
        panel_der = tk.Frame(paned, bg="#EEF2F6")
        paned.add(panel_der, weight=10)

        self.notebook = ttk.Notebook(panel_der)
        self.notebook.pack(fill="both", expand=True)

        self._construir_tab_traduccion()
        self._construir_tab_ciclos()
        self._construir_tab_bh()
        self._construir_tab_formulario()

    def _construir_tab_traduccion(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="1. Traducción LN → Hechos")

        tk.Label(
            tab,
            text="Análisis del Traductor PLN (parámetros, inferencias cualitativas y autocompletado):",
            font=("Segoe UI", 9, "bold"),
            bg="#EEF2F6",
            fg="#1F2937",
        ).pack(anchor="w", padx=8, pady=(8, 2))

        self.txt_meta_pln = tk.Text(tab, height=11, wrap="word", font=("Consolas", 9), bg="#FFFFFF", state="disabled")
        self.txt_meta_pln.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(
            tab,
            text="Hechos traducidos cargados al caso (DATOS_CASO):",
            font=("Segoe UI", 9, "bold"),
            bg="#EEF2F6",
            fg="#1F2937",
        ).pack(anchor="w", padx=8, pady=(0, 2))

        frame_tv = tk.Frame(tab)
        frame_tv.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        sc = ttk.Scrollbar(frame_tv)
        sc.pack(side="right", fill="y")

        self.tv_hechos_caso = ttk.Treeview(
            frame_tv,
            columns=("Campo", "Valor", "Unidad"),
            show="headings",
            yscrollcommand=sc.set,
        )
        self.tv_hechos_caso.heading("Campo", text="Parámetro / Evento")
        self.tv_hechos_caso.heading("Valor", text="Valor Traducido")
        self.tv_hechos_caso.heading("Unidad", text="Referencia / Tipo")
        self.tv_hechos_caso.column("Campo", width=230)
        self.tv_hechos_caso.column("Valor", width=160)
        self.tv_hechos_caso.column("Unidad", width=160)
        self.tv_hechos_caso.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_hechos_caso.yview)

    def _construir_tab_ciclos(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="2. Motor de Inferencia (Ciclos)")

        frame_tv = tk.Frame(tab)
        frame_tv.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        sc = ttk.Scrollbar(frame_tv)
        sc.pack(side="right", fill="y")

        self.tv_ciclos = ttk.Treeview(
            frame_tv,
            columns=("Ciclo", "Regla", "Prioridad", "Hechos", "Descripcion"),
            show="headings",
            yscrollcommand=sc.set,
        )
        self.tv_ciclos.heading("Ciclo", text="Ciclo")
        self.tv_ciclos.heading("Regla", text="Regla Seleccionada")
        self.tv_ciclos.heading("Prioridad", text="Prioridad")
        self.tv_ciclos.heading("Hechos", text="Nuevos")
        self.tv_ciclos.heading("Descripcion", text="Descripción")
        self.tv_ciclos.column("Ciclo", width=50, anchor="center")
        self.tv_ciclos.column("Regla", width=210)
        self.tv_ciclos.column("Prioridad", width=65, anchor="center")
        self.tv_ciclos.column("Hechos", width=60, anchor="center")
        self.tv_ciclos.column("Descripcion", width=260)
        self.tv_ciclos.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_ciclos.yview)
        self.tv_ciclos.bind("<<TreeviewSelect>>", self._mostrar_detalle_ciclo)

        tk.Label(
            tab,
            text="Tripletas agregadas en el ciclo seleccionado:",
            font=("Segoe UI", 9, "bold"),
            bg="#EEF2F6",
            fg="#1F2937",
        ).pack(anchor="w", padx=8, pady=(4, 2))
        self.txt_detalle_ciclo = tk.Text(tab, height=6, wrap="word", font=("Consolas", 9), bg="#FFFFFF", state="disabled")
        self.txt_detalle_ciclo.pack(fill="x", padx=8, pady=(0, 8))

    def _construir_tab_bh(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="3. Base de Hechos RDF")

        barra = tk.Frame(tab, bg="#EEF2F6")
        barra.pack(fill="x", padx=8, pady=8)

        tk.Label(barra, text="Mostrar:", bg="#EEF2F6", font=("Segoe UI", 9, "bold")).pack(side="left")
        cb_filtro = ttk.Combobox(
            barra,
            textvariable=self.var_filtro_bh,
            values=["Todos", "Solo Inferidos", "Solo Iniciales"],
            state="readonly",
            width=16,
        )
        cb_filtro.pack(side="left", padx=(4, 10))
        cb_filtro.bind("<<ComboboxSelected>>", lambda _e: self._refrescar_tabla_bh())

        tk.Label(barra, text="Buscar:", bg="#EEF2F6", font=("Segoe UI", 9, "bold")).pack(side="left")
        ent_busq = ttk.Entry(barra, textvariable=self.var_busqueda_bh, width=28)
        ent_busq.pack(side="left", padx=(4, 6))
        ent_busq.bind("<KeyRelease>", lambda _e: self._refrescar_tabla_bh())

        self.lbl_count_bh = tk.Label(barra, text="0 tripletas", bg="#EEF2F6", fg="#475569", font=("Segoe UI", 9))
        self.lbl_count_bh.pack(side="right")

        frame_tv = tk.Frame(tab)
        frame_tv.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        sc = ttk.Scrollbar(frame_tv)
        sc.pack(side="right", fill="y")

        self.tv_bh = ttk.Treeview(
            frame_tv,
            columns=("Sujeto", "Predicado", "Objeto", "Origen"),
            show="headings",
            yscrollcommand=sc.set,
        )
        self.tv_bh.heading("Sujeto", text="Sujeto")
        self.tv_bh.heading("Predicado", text="Predicado")
        self.tv_bh.heading("Objeto", text="Objeto")
        self.tv_bh.heading("Origen", text="Origen")
        self.tv_bh.column("Sujeto", width=110)
        self.tv_bh.column("Predicado", width=165)
        self.tv_bh.column("Objeto", width=190)
        self.tv_bh.column("Origen", width=165)
        self.tv_bh.pack(side="left", fill="both", expand=True)
        sc.config(command=self.tv_bh.yview)

    def _construir_tab_formulario(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="4. Formulario Manual / Ajuste")

        canvas = tk.Canvas(tab, bg="#EEF2F6", highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        contenedor = tk.Frame(canvas, bg="#EEF2F6")

        contenedor.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=contenedor, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Datos generales
        lf_gen = tk.LabelFrame(contenedor, text="Datos del Lote", bg="#EEF2F6", padx=8, pady=6, font=("Segoe UI", 9, "bold"))
        lf_gen.pack(fill="x", padx=8, pady=6)

        self.form_id_lote = tk.StringVar(value="Lote_001")
        self.form_tipo = tk.StringVar(value="CTA")
        self.form_color_max = tk.StringVar(value="")

        tk.Label(lf_gen, text="ID Lote:", bg="#EEF2F6").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(lf_gen, textvariable=self.form_id_lote, width=16).grid(row=0, column=1, padx=4, pady=2)

        tk.Label(lf_gen, text="Tipo Azúcar:", bg="#EEF2F6").grid(row=0, column=2, sticky="w", padx=4, pady=2)
        ttk.Combobox(lf_gen, textvariable=self.form_tipo, values=["CTA", "Crudo", "Organica"], state="readonly", width=12).grid(
            row=0, column=3, padx=4, pady=2
        )

        tk.Label(lf_gen, text="Color Máx Cliente (opcional):", bg="#EEF2F6").grid(row=0, column=4, sticky="w", padx=4, pady=2)
        ttk.Entry(lf_gen, textvariable=self.form_color_max, width=10).grid(row=0, column=5, padx=4, pady=2)

        # Mediciones numéricas
        lf_med = tk.LabelFrame(contenedor, text="Mediciones Numéricas", bg="#EEF2F6", padx=8, pady=6, font=("Segoe UI", 9, "bold"))
        lf_med.pack(fill="x", padx=8, pady=6)

        self.form_mediciones: dict[str, tk.StringVar] = {}
        for idx, clave in enumerate(PROPIEDADES_MEDICION):
            nombre, unidad = ETIQUETAS_MEDICIONES[clave]
            var = tk.StringVar(value="")
            self.form_mediciones[clave] = var
            fila, col = divmod(idx, 2)
            tk.Label(lf_med, text=f"{nombre} ({unidad}):", bg="#EEF2F6").grid(
                row=fila, column=col * 2, sticky="w", padx=4, pady=2
            )
            ttk.Entry(lf_med, textvariable=var, width=12).grid(row=fila, column=col * 2 + 1, sticky="w", padx=4, pady=2)

        # Eventos booleanos
        lf_ev = tk.LabelFrame(contenedor, text="Eventos y Observaciones", bg="#EEF2F6", padx=8, pady=6, font=("Segoe UI", 9, "bold"))
        lf_ev.pack(fill="x", padx=8, pady=6)

        self.form_eventos: dict[str, tk.BooleanVar] = {}
        for idx, clave in enumerate(PROPIEDADES_EVENTO):
            var = tk.BooleanVar(value=False)
            self.form_eventos[clave] = var
            fila, col = divmod(idx, 2)
            tk.Checkbutton(
                lf_ev,
                text=ETIQUETAS_EVENTOS.get(clave, clave),
                variable=var,
                bg="#EEF2F6",
                activebackground="#EEF2F6",
                anchor="w",
            ).grid(row=fila, column=col, sticky="w", padx=4, pady=1)

        # Seguimiento y acciones aplicadas
        lf_seg = tk.LabelFrame(contenedor, text="Seguimiento y Acciones ya Aplicadas", bg="#EEF2F6", padx=8, pady=6, font=("Segoe UI", 9, "bold"))
        lf_seg.pack(fill="x", padx=8, pady=6)

        self.form_horas = tk.StringVar(value="0")
        self.form_dos_muestras = tk.BooleanVar(value=False)
        tk.Label(lf_seg, text="Horas desde corrección:", bg="#EEF2F6").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(lf_seg, textvariable=self.form_horas, width=8).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        tk.Checkbutton(
            lf_seg,
            text="2 muestras horarias seguidas dentro de ficha",
            variable=self.form_dos_muestras,
            bg="#EEF2F6",
            activebackground="#EEF2F6",
        ).grid(row=0, column=2, columnspan=2, sticky="w", padx=8, pady=2)

        self.form_acciones_aplicadas: dict[str, tk.BooleanVar] = {}
        for idx, acc in enumerate(ACCIONES_SEGUIMIENTO):
            var = tk.BooleanVar(value=False)
            self.form_acciones_aplicadas[acc] = var
            tk.Checkbutton(
                lf_seg,
                text=f"Aplicada: {acc}",
                variable=var,
                bg="#EEF2F6",
                activebackground="#EEF2F6",
            ).grid(row=1 + idx // 2, column=(idx % 2) * 2, columnspan=2, sticky="w", padx=4, pady=1)

        ttk.Button(
            contenedor,
            text="Re-evaluar desde Formulario",
            style="Primary.TButton",
            command=self._reevaluar_desde_formulario,
        ).pack(pady=10)

    def _mostrar_bienvenida(self) -> None:
        bienvenida = (
            "Bienvenido al Asesor Virtual del SBC — Ingenio La Esperanza.\n"
            "Escribí una situación o consulta en lenguaje natural (por ejemplo: mediciones del tacho, "
            "resultados de laboratorio, observaciones del maestro azucarero o seguimiento tras corrección) "
            "y el sistema:\n"
            "  1) Traducirá tu consulta a la Base de Hechos RDF.\n"
            "  2) Ejecutará las 72 reglas SPARQL CONSTRUCT (R1–R56) por prioridad.\n"
            "  3) Te responderá en lenguaje natural con dictamen, causa raíz, directivas y trazabilidad.\n\n"
            "Tip: Podés probar rápidamente seleccionando un caso en 'Ejemplos' arriba."
        )
        self._agregar_mensaje_chat("SBC Asesor Virtual", bienvenida, es_usuario=False)

    def _configurar_api_key(self) -> None:
        nueva = simpledialog.askstring(
            "Configurar API Key de Gemini",
            "Ingresá tu API Key de Google Gemini (se guarda solo en esta sesión).\n"
            "Si lo dejás vacío, el sistema usará el motor PLN local offline:",
            initialvalue=self.api_key,
            show="*",
            parent=self.root,
        )
        if nueva is not None:
            self.api_key = nueva.strip()
            if self.api_key:
                self.var_modo.set("Híbrido (Gemini API + Fallback Local)")
                messagebox.showinfo("API Key configurada", "Modo híbrido con Gemini API habilitado.", parent=self.root)
            else:
                self.var_modo.set("Local (100% Python Offline)")

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
        self.txt_chat.config(state="normal")
        self.txt_chat.delete("1.0", "end")
        self.txt_chat.config(state="disabled")
        self._mostrar_bienvenida()

    def _agregar_mensaje_chat(self, emisor: str, texto: str, es_usuario: bool) -> None:
        self.txt_chat.config(state="normal")
        if self.txt_chat.index("end-1c") != "1.0":
            self.txt_chat.insert("end", "\n" + "─" * 72 + "\n", "sep")

        if es_usuario:
            self.txt_chat.insert("end", f"👤 {emisor}:\n", "user_header")
            self.txt_chat.insert("end", texto.strip() + "\n", "user_body")
        else:
            self.txt_chat.insert("end", f"🏭 {emisor}:\n", "sbc_header")
            for linea in texto.strip().splitlines():
                tag = "sbc_body"
                if "NO CONFORME" in linea or "RECHAZADO" in linea:
                    tag = "sbc_bad"
                elif "APROBADO" in linea:
                    tag = "sbc_ok"
                elif "ADVERTENCIA" in linea or "crítico" in linea.lower():
                    tag = "sbc_warn"
                self.txt_chat.insert("end", linea + "\n", tag)

        self.txt_chat.see("end")
        self.txt_chat.config(state="disabled")

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
        self.btn_consultar.config(state="disabled")
        self.lbl_estado_proc.config(text="Traduciendo e infiriendo...")

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
        self.btn_consultar.config(state="normal")
        self.lbl_estado_proc.config(text="Listo")
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

        self._agregar_mensaje_chat(f"SBC Asesor Virtual [{meta['metodo']}]", respuesta, es_usuario=False)
        self._actualizar_tab_traduccion(resultado, meta)
        self._actualizar_tab_ciclos(resultado)
        self._refrescar_tabla_bh()
        self._sincronizar_formulario(resultado["datos_entrada"])

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

        datos = resultado["datos_entrada"]
        self.tv_hechos_caso.insert("", "end", values=("ID Lote", datos["id_lote"], "Identificador"))
        self.tv_hechos_caso.insert("", "end", values=("Tipo de azúcar", datos["tipo_azucar"], "CTA / Crudo / Organica"))
        lim_col = datos.get("ficha_cliente", {}).get("color_max_ui")
        if lim_col is not None:
            self.tv_hechos_caso.insert("", "end", values=("Color máx. ficha cliente", str(lim_col), "UI"))

        for k, val in datos["mediciones"].items():
            if val is not None:
                nombre, unidad = ETIQUETAS_MEDICIONES[k]
                self.tv_hechos_caso.insert("", "end", values=(nombre, f"{val:g}", unidad))

        for k, activo in datos["eventos"].items():
            if activo:
                self.tv_hechos_caso.insert("", "end", values=(ETIQUETAS_EVENTOS.get(k, k), "true", "Evento"))

        if datos["acciones_aplicadas"]:
            self.tv_hechos_caso.insert(
                "", "end", values=("Acciones ya aplicadas", ", ".join(datos["acciones_aplicadas"]), "Seguimiento")
            )
        seg = datos["seguimiento"]
        if seg["horas_desde_correccion"]:
            self.tv_hechos_caso.insert(
                "", "end", values=("Horas desde corrección", str(seg["horas_desde_correccion"]), "h")
            )
        if seg["dos_muestras_horarias_dentro_ficha"]:
            self.tv_hechos_caso.insert(
                "", "end", values=("2 muestras horarias conformes", "true", "R56")
            )

    def _actualizar_tab_ciclos(self, resultado: dict[str, Any]) -> None:
        for item in self.tv_ciclos.get_children():
            self.tv_ciclos.delete(item)

        for act in resultado["activaciones"]:
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
            )

        self.txt_detalle_ciclo.config(state="normal")
        self.txt_detalle_ciclo.delete("1.0", "end")
        if resultado["activaciones"]:
            self.txt_detalle_ciclo.insert(
                "1.0", "Seleccioná un ciclo de la tabla para ver las tripletas RDF deducidas."
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
            self.tv_bh.insert(
                "", "end", values=(row["sujeto"], row["predicado"], row["objeto"], row["origen"])
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
            datos["seguimiento"]["dos_muestras_horarias_dentro_ficha"] = bool(self.form_dos_muestras.get())
            datos["acciones_aplicadas"] = [
                acc for acc, var in self.form_acciones_aplicadas.items() if var.get()
            ]
        except ValueError as exc:
            messagebox.showerror("Dato numérico inválido", f"Revisá los valores ingresados: {exc}", parent=self.root)
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
    root = tk.Tk()
    SBCApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
