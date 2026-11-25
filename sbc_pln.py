"""
Traductor Híbrido Lenguaje Natural ↔ SBC - Ingenio La Esperanza.

Convierte consultas en español natural a la estructura DATOS_CASO del SBC
(motor PLN local basado en reglas/regex con conector opcional a Gemini API)
y redacta las inferencias del grafo RDF en respuestas claras y explicadas
para el Jefe de Turno.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from copy import deepcopy
from typing import Any

import requests

from sbc_motor import (
    ACCIONES,
    ETIQUETAS_EVENTOS,
    ETIQUETAS_MEDICIONES,
    PROPIEDADES_EVENTO,
    PROPIEDADES_MEDICION,
    crear_caso_vacio,
)

CASOS_EJEMPLO: list[dict[str, str]] = [
    {
        "titulo": "1. Color oscuro + grano grande + vacío bajo (CTA)",
        "consulta": (
            "Lote 001 de azúcar CTA: el tacho está en cocción, pasó una hora y el jefe ve "
            "color distinto a simple vista. Medimos vacío en 55 cmHg, temperatura en 88 °C, "
            "Brix de entrada 64, masa cocida en 88 °Bx, semilla 80, color 180 UI, "
            "granulometría 0.56 mm, retenido malla 25 del 15%, Pol 99.7% y sedimentos 10 mg/kg. "
            "Además se va a sembrar en proceso continuo."
        ),
    },
    {
        "titulo": "2. Color oscuro con temperatura normal (lavado centrífuga)",
        "consulta": (
            "Tenemos un lote CTA con color de 185 UI y se observa color oscuro, pero la "
            "temperatura del tacho es normal de 65 °C y el vacío está en 61 cmHg. "
            "¿Cuál es la causa y qué debemos hacer?"
        ),
    },
    {
        "titulo": "3. Grano chico por exceso de semilla y Brix bajo",
        "consulta": (
            "En azúcar CTA el laboratorio reportó granulometría de 0.46 mm (grano chico), "
            "dosificación de semilla en 170 por tacho y Brix de entrada bajo en 58 °Bx."
        ),
    },
    {
        "titulo": "4. Sedimentos altos al descargar a centrífugas (Crudo)",
        "consulta": (
            "Se descargó el tacho a centrífugas con azúcar crudo y el análisis dio "
            "sedimentos en 45 mg/kg, color 320 UI, granulometría 0.62 mm y Pol 98.8%."
        ),
    },
    {
        "titulo": "5. Falla recurrente tras 3 horas (Tacho sucio)",
        "consulta": (
            "Lote CTA: hace 3 horas se aplicó enfriamiento del tacho porque estaba excedido, "
            "pero la temperatura sigue en 89 °C y el color continúa fuera en 190 UI. ¿Qué hacemos?"
        ),
    },
    {
        "titulo": "6. Lote Aprobado conforme a ficha (CTA)",
        "consulta": (
            "Lote 205 CTA en operación normal: vacío 61 cmHg, temperatura 64 °C, Brix entrada 61.5, "
            "color 115 UI, granulometría 0.52 mm, retenido malla 25 de 12%, Pol 99.75% y "
            "sedimentos 12 mg/kg. Masa cocida llegó a 92 °Bx."
        ),
    },
    {
        "titulo": "7. Contingencias: Orgánica, falta maestro y terrones",
        "consulta": (
            "Estamos produciendo azúcar orgánica, falta el maestro de primera y no hay relevo "
            "de otro turno. Además en el secador salió azúcar con terrones."
        ),
    },
]

VALORES_NORMALES_FICHA: dict[str, dict[str, float]] = {
    "CTA": {
        "color_ui": 110.0,
        "granulometria_mm": 0.52,
        "retenido_malla25_pct": 12.0,
        "pol_pct": 99.7,
        "sedimentos_mg_kg": 10.0,
    },
    "Crudo": {
        "color_ui": 300.0,
        "granulometria_mm": 0.62,
        "pol_pct": 98.8,
        "sedimentos_mg_kg": 10.0,
    },
}


def _normalizar_texto(texto: str) -> str:
    """Pasa a minúsculas y quita tildes (conservando ñ) para matching robusto."""
    texto_min = texto.lower().strip()
    descompuesto = unicodedata.normalize("NFD", texto_min)
    sin_tildes = "".join(
        ch for ch in descompuesto if unicodedata.category(ch) != "Mn" or ch == "\u0303"
    )
    return unicodedata.normalize("NFC", sin_tildes)


def _a_float(valor_str: str) -> float:
    return float(valor_str.replace(",", "."))


def _extraer_numero(norm: str, patrones: list[str]) -> tuple[float | None, str | None]:
    for pat in patrones:
        m = re.search(pat, norm)
        if m:
            try:
                return _a_float(m.group(1)), m.group(0).strip()
            except ValueError:
                continue
    return None, None


def _traducir_local(texto: str, autocompletar_normales: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    norm = _normalizar_texto(texto)

    # 1. Tipo de azúcar
    tipo_azucar = "CTA"
    if re.search(r"\borganic[ao]s?\b", norm):
        tipo_azucar = "Organica"
    elif re.search(r"\bcrudo\b", norm):
        tipo_azucar = "Crudo"
    elif re.search(r"\b(cta|tipo\s*a|blanco(\s+directo)?)\b", norm):
        tipo_azucar = "CTA"

    # 2. ID de Lote
    id_lote = "Lote_001"
    m_lote = re.search(r"\blote\s*(?:n[°ºo.]?\s*|#)?([a-z0-9_-]+)\b", norm)
    if m_lote:
        sufijo = re.sub(r"[^a-zA-Z0-9_-]", "", m_lote.group(1))
        if sufijo and sufijo not in {"de", "en", "con", "cta", "crudo", "organica", "organico", "no"}:
            id_lote = f"Lote_{sufijo.upper()}" if not sufijo.lower().startswith("lote") else sufijo

    datos = crear_caso_vacio(id_lote=id_lote, tipo_azucar=tipo_azucar)
    meta: dict[str, Any] = {
        "metodo": "Local (PLN Reglas/Regex)",
        "parametros_extraidos": [],
        "inferencias_cualitativas": [],
        "eventos_detectados": [],
        "autocompletados": [],
        "notas": [],
        "error_gemini": None,
    }

    # 3. Ficha cliente especial para color (200 o 600 UI)
    m_ficha_color = re.search(
        r"(?:ficha(?:\s+de\s+cliente)?|limite(?:\s+de\s+color)?|color\s+max(?:imo)?)"
        r"[^.\n]{0,35}?\b(200|600)\s*(?:ui|icumsa)?\b",
        norm,
    )
    if m_ficha_color:
        lim = int(m_ficha_color.group(1))
        datos["ficha_cliente"]["color_max_ui"] = lim
        meta["parametros_extraidos"].append(
            f"ficha_cliente.color_max_ui = {lim} UI (detectado de '{m_ficha_color.group(0).strip()}')"
        )

    # 4. Extracción numérica explícita de las 10 mediciones
    med = datos["mediciones"]

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:vacio|presion\s+de\s+vacio)\s*(?:en|de|a|:|=|es|bajo\s+a|cayo\s+a)?\s*(\d+(?:[.,]\d+)?)\s*(?:cm\s*hg|cmhg)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:cm\s*hg|cmhg)\b",
        ],
    )
    if val is not None:
        med["vacio_cm_hg"] = val
        meta["parametros_extraidos"].append(f"vacio_cm_hg = {val} cmHg ('{frag}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:temperatura|temp\.?)(?:\s+del\s+tacho|\s+en\s+tacho)?\s*(?:normal\s+de|excedida\s+de|en|de|a|:|=|es|subio\s+a|llego\s+a)?\s*(\d+(?:[.,]\d+)?)\s*(?:°\s*c|grados(?:\s*c)?)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:°\s*c|grados(?:\s+centigrados|\s+celsius)?)\b",
        ],
    )
    if val is not None:
        med["temperatura_tacho_c"] = val
        meta["parametros_extraidos"].append(f"temperatura_tacho_c = {val} °C ('{frag}')")

    # Masa cocida (92 °Bx)
    val_mc, frag_mc = _extraer_numero(
        norm,
        [
            r"(?:brix\s+(?:de\s+)?masa\s+cocida|masa\s+cocida(?:\s+llego|\s+alcanzo|\s+esta|\s+en|\s+de|\s+a)?)\s*(?:en|de|a|:|=)?\s*(\d+(?:[.,]\d+)?)\s*(?:°?\s*bx|brix|bx)?",
            r"(?:llego|alcanzo|descarga(?:r)?)\s+(?:a|los)?\s*(9[0-9](?:[.,]\d+)?)\s*(?:°?\s*bx|brix|bx)",
        ],
    )
    if val_mc is not None:
        med["brix_masa_cocida"] = val_mc
        meta["parametros_extraidos"].append(f"brix_masa_cocida = {val_mc} °Bx ('{frag_mc}')")
    elif re.search(r"masa\s+cocida\s+(?:lista|en\s+punto|para\s+descarga)", norm):
        med["brix_masa_cocida"] = 92.0
        meta["inferencias_cualitativas"].append(
            "brix_masa_cocida = 92.0 °Bx (inferido de masa cocida lista para descarga, R53)"
        )

    # Brix de entrada al tacho (cuidando S12: 33-37 °Bx de evaporadores preliminares)
    norm_sin_mc = norm.replace(frag_mc, "") if frag_mc else norm
    val_bx, frag_bx = _extraer_numero(
        norm_sin_mc,
        [
            r"(?:brix(?:\s+de\s+(?:entrada|alimentacion|jugo))?(?:\s+al\s+tacho)?(?:\s+(?:bajo|alto|normal))?)\s*(?:en|de|a|:|=|es)?\s*(\d+(?:[.,]\d+)?)\s*(?:°?\s*bx|brix|bx)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:°?\s*bx|brix|bx)\b",
        ],
    )
    if val_bx is not None:
        if 33 <= val_bx <= 37 and re.search(r"evaporador(?:es)?\s+preliminar|salida\s+de\s+evaporador", norm):
            meta["notas"].append(
                f"Lectura {val_bx} °Bx detectada como etapa previa de evaporación (S12: desacoplada del tacho)."
            )
        else:
            med["brix_entrada_tacho"] = val_bx
            meta["parametros_extraidos"].append(f"brix_entrada_tacho = {val_bx} °Bx ('{frag_bx}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:dosificacion\s+de\s+semilla|cantidad\s+de\s+semilla|semilla)\s*(?:en|de|a|:|=|con|es)?\s*(\d+(?:[.,]\d+)?)",
        ],
    )
    if val is not None:
        med["semilla"] = val
        meta["parametros_extraidos"].append(f"semilla = {val} ('{frag}')")

    # Color UI (evitando capturar el límite de ficha de cliente ya extraído)
    norm_sin_ficha = norm.replace(m_ficha_color.group(0), "") if m_ficha_color else norm
    val, frag = _extraer_numero(
        norm_sin_ficha,
        [
            r"color(?:\s+icumsa)?(?:\s+fuera)?\s*(?:en|de|a|:|=|es|dio)?\s*(\d+(?:[.,]\d+)?)\s*(?:ui|icumsa)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:ui|icumsa)\b",
        ],
    )
    if val is not None:
        med["color_ui"] = val
        meta["parametros_extraidos"].append(f"color_ui = {val} UI ('{frag}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:granulometria|tamano\s+de\s+grano)\s*(?:en|de|a|:|=|es|dio)?\s*(\d+(?:[.,]\d+)?)\s*(?:mm)?",
            r"(\d+(?:[.,]\d+)?)\s*mm\b",
        ],
    )
    if val is not None:
        med["granulometria_mm"] = val
        meta["parametros_extraidos"].append(f"granulometria_mm = {val} mm ('{frag}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:retenido(?:\s+en)?(?:\s+malla\s*25)?|malla\s*25)\s*(?:en|de|del|a|:|=|es)?\s*(\d+(?:[.,]\d+)?)\s*%?",
        ],
    )
    if val is not None:
        med["retenido_malla25_pct"] = val
        meta["parametros_extraidos"].append(f"retenido_malla25_pct = {val}% ('{frag}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:pol(?:arizacion)?)\s*(?:en|de|a|:|=|es|dio)?\s*(\d+(?:[.,]\d+)?)\s*(?:°\s*z|%|z)?",
            r"(\d+(?:[.,]\d+)?)\s*°\s*z\b",
        ],
    )
    if val is not None:
        med["pol_pct"] = val
        meta["parametros_extraidos"].append(f"pol_pct = {val}% ('{frag}')")

    val, frag = _extraer_numero(
        norm,
        [
            r"(?:sedimentos?(?:\s+e\s+insolubles?)?)\s*(?:en|de|a|:|=|es|dio)?\s*(\d+(?:[.,]\d+)?)\s*(?:mg/kg|ppm)?",
            r"(\d+(?:[.,]\d+)?)\s*(?:mg/kg|ppm)\b",
        ],
    )
    if val is not None:
        med["sedimentos_mg_kg"] = val
        meta["parametros_extraidos"].append(f"sedimentos_mg_kg = {val} mg/kg ('{frag}')")

    # 5. Inferencias cualitativas si no se indicó el número explícito
    if med["vacio_cm_hg"] is None:
        if re.search(r"\b(vacio\s+bajo|perdida\s+de\s+vacio|bajo\s+vacio|sin\s+vacio|fuga\s+de\s+vacio)\b", norm):
            med["vacio_cm_hg"] = 55.0
            meta["inferencias_cualitativas"].append(
                "vacio_cm_hg = 55.0 cmHg (inferido de vacío bajo / pérdida de vacío, umbral S2 < 60)"
            )
        elif re.search(r"\bvacio\s+normal\b", norm):
            med["vacio_cm_hg"] = 61.0
            meta["inferencias_cualitativas"].append("vacio_cm_hg = 61.0 cmHg (inferido de vacío normal)")

    if med["temperatura_tacho_c"] is None:
        if re.search(
            r"\b(temperatura\s+(?:excedida|muy\s+alta|altisima|elevada)|sigue\s+excedid[ao]|estaba\s+excedid[ao]|azucar\s+quemad[oa])\b",
            norm,
        ):
            med["temperatura_tacho_c"] = 88.0
            meta["inferencias_cualitativas"].append(
                "temperatura_tacho_c = 88.0 °C (inferido de temperatura excedida / azúcar quemado, S1 > 85)"
            )
        elif re.search(r"\btemperatura\s+(?:en\s+alerta|preventiva|algo\s+alta)\b", norm):
            med["temperatura_tacho_c"] = 78.0
            meta["inferencias_cualitativas"].append(
                "temperatura_tacho_c = 78.0 °C (inferido de temperatura en alerta, S1 70–85)"
            )
        elif re.search(r"\btemperatura\s+(?:del\s+tacho\s+)?(?:es\s+)?normal\b", norm):
            med["temperatura_tacho_c"] = 65.0
            meta["inferencias_cualitativas"].append("temperatura_tacho_c = 65.0 °C (inferido de temperatura normal)")

    if med["brix_entrada_tacho"] is None:
        if re.search(r"\b(brix\s+alto|brix\s+elevado|jugo\s+muy\s+concentrado)\b", norm):
            med["brix_entrada_tacho"] = 64.0
            meta["inferencias_cualitativas"].append(
                "brix_entrada_tacho = 64.0 °Bx (inferido de Brix alto, S3 > 63)"
            )
        elif re.search(r"\b(brix\s+bajo|jugo\s+(?:de\s+entrada\s+)?pobre|jugo\s+diluido|concentracion\s+baja)\b", norm):
            med["brix_entrada_tacho"] = 58.0
            meta["inferencias_cualitativas"].append(
                "brix_entrada_tacho = 58.0 °Bx (inferido de Brix bajo / jugo pobre, S3 < 60)"
            )
        elif re.search(r"\bbrix\s+normal\b", norm):
            med["brix_entrada_tacho"] = 61.5
            meta["inferencias_cualitativas"].append("brix_entrada_tacho = 61.5 °Bx (inferido de Brix normal)")

    if med["semilla"] is None:
        if re.search(r"\b(poca\s+semilla|semilla\s+poca|falta\s+semilla|semilla\s+insuficiente)\b", norm):
            med["semilla"] = 80.0
            meta["inferencias_cualitativas"].append(
                "semilla = 80.0 (inferido de poca semilla, S4 < 100)"
            )
        elif re.search(r"\b(mucha\s+semilla|semilla\s+mucha|exceso\s+de\s+semilla|demasiada\s+semilla)\b", norm):
            med["semilla"] = 170.0
            meta["inferencias_cualitativas"].append(
                "semilla = 170.0 (inferido de exceso de semilla, S4 > 150)"
            )
        elif re.search(r"\bsemilla\s+normal\b", norm):
            med["semilla"] = 125.0
            meta["inferencias_cualitativas"].append("semilla = 125.0 (inferido de semilla normal)")

    if med["color_ui"] is None:
        if re.search(r"\b(color\s+(?:alto|fuera|elevado|excedido)|color\s+oscuro|azucar\s+oscuro)\b", norm):
            val_col = 450.0 if tipo_azucar == "Crudo" else 180.0
            med["color_ui"] = val_col
            meta["inferencias_cualitativas"].append(
                f"color_ui = {val_col} UI (inferido de color fuera/oscuro para {tipo_azucar})"
            )

    if med["granulometria_mm"] is None:
        if re.search(r"\b(grano\s+grande|grano\s+grueso|cristal\s+grande)\b", norm):
            val_gr = 0.68 if tipo_azucar == "Crudo" else 0.58
            med["granulometria_mm"] = val_gr
            meta["inferencias_cualitativas"].append(
                f"granulometria_mm = {val_gr} mm (inferido de grano grande para {tipo_azucar})"
            )
        elif re.search(r"\b(grano\s+chico|grano\s+fino|grano\s+pequeno|cristal\s+chico)\b", norm):
            val_gr = 0.56 if tipo_azucar == "Crudo" else 0.46
            med["granulometria_mm"] = val_gr
            meta["inferencias_cualitativas"].append(
                f"granulometria_mm = {val_gr} mm (inferido de grano chico para {tipo_azucar})"
            )

    if med["retenido_malla25_pct"] is None and re.search(r"\bretenido(?:\s+en\s+malla\s*25)?\s+(?:alto|fuera|excedido)\b", norm):
        med["retenido_malla25_pct"] = 24.0
        meta["inferencias_cualitativas"].append("retenido_malla25_pct = 24.0% (inferido de retenido fuera de ficha)")

    if med["pol_pct"] is None and re.search(r"\b(pol(?:arizacion)?\s+baj[ao]|pureza\s+fuera|baja\s+pol)\b", norm):
        val_pol = 98.0 if tipo_azucar == "Crudo" else 99.2
        med["pol_pct"] = val_pol
        meta["inferencias_cualitativas"].append(f"pol_pct = {val_pol}% (inferido de Pol baja para {tipo_azucar})")

    if med["sedimentos_mg_kg"] is None and re.search(r"\b(sedimentos?\s+(?:altos|fuera|excedidos)|muchos\s+sedimentos)\b", norm):
        med["sedimentos_mg_kg"] = 42.0
        meta["inferencias_cualitativas"].append("sedimentos_mg_kg = 42.0 mg/kg (inferido de sedimentos altos)")

    # 6. Eventos booleanos
    ev = datos["eventos"]
    patrones_eventos: list[tuple[str, str]] = [
        ("tacho_en_coccion", r"\b(tacho\s+(?:esta\s+)?en\s+coccion|en\s+coccion|cocinando|en\s+cocimiento)\b"),
        ("paso_una_hora", r"\b(paso\s+(?:una|1)\s+hora|muestra\s+horaria|control\s+horario)\b"),
        ("primera_muestra_turno", r"\b(primera\s+muestra|inicio\s+de(?:l)?\s+turno|arranque\s+de(?:l)?\s+turno)\b"),
        ("jefe_ve_color_distinto", r"\b(color\s+distinto|veo?\s+(?:el\s+)?color\s+distinto|a\s+simple\s+vista.*color)\b"),
        ("tacho_descargado_centrifugas", r"\b(descarg[oa](?:do)?\s+(?:el\s+tacho\s+)?a\s+centrifugas?|descarga\s+a\s+centrifugas?)\b"),
        ("tachero_ve_grano_grande", r"\b(tachero\s+(?:ve|detecta|observa|palpa|toca).*grano\s+grande|toma[- ]?muestras.*grano\s+grande)\b"),
        ("color_demasiado_claro", r"\b(color\s+(?:demasiado|excesivamente|muy)\s+claro)\b"),
        ("color_oscuro_observado", r"\b(color\s+oscuro|se\s+ve\s+oscuro|salio\s+oscuro)\b"),
        ("lote_terminado", r"\b(lote\s+(?:terminado|cerrado)|termino\s+(?:de\s+producirse|el\s+lote)|culmino\s+la\s+produccion)\b"),
        ("detectado_en_zaranda", r"\b(en\s+(?:la\s+)?zaranda|detectado\s+en\s+zaranda|zaranda\s+vibratoria)\b"),
        ("proceso_continuo", r"\b(proceso\s+continuo|marcha\s+continua|en\s+linea)\b"),
        ("falta_maestro_primera", r"\b(falta\s+(?:el\s+)?maestro(?:\s+azucarero)?\s+de\s+primera|ausente.*maestro.*primera)\b"),
        ("se_va_a_sembrar", r"\b(se\s+va\s+a\s+sembrar|al\s+sembrar|efectuar\s+sembrado)\b"),
        ("secador_terroneado", r"\b(con\s+terrones|terroneado|terrones\s+en\s+secador)\b"),
        ("secador_azucar_humeda", r"\b(azucar\s+humeda|escurre\s+miel|exuda\s+miel)\b"),
        ("tachero_nota_color_oscuro_antes_laboratorio", r"\b(tachero.*color\s+oscuro.*antes|antes\s+del?\s+laboratorio.*color\s+oscuro)\b"),
    ]
    for clave, patron in patrones_eventos:
        if re.search(patron, norm):
            ev[clave] = True
            meta["eventos_detectados"].append(ETIQUETAS_EVENTOS.get(clave, clave))

    # Caso especial reemplazo_turno (por defecto False; True solo si hay relevo explícito)
    if re.search(r"\b(no\s+hay\s+relevo|sin\s+relevo|no\s+media\s+relevo|sin\s+reemplazo|no\s+hay\s+reemplazo)\b", norm):
        ev["reemplazo_turno"] = False
    elif re.search(r"\b(hay\s+relevo|con\s+relevo|hay\s+reemplazo|reemplazo\s+de\s+otro\s+turno)\b", norm):
        ev["reemplazo_turno"] = True
        meta["eventos_detectados"].append(ETIQUETAS_EVENTOS["reemplazo_turno"])

    # 7. Seguimiento y acciones ya aplicadas
    m_horas = re.search(
        r"(?:hace|tras|luego\s+de|despues\s+de|pasaron|cumplidas)?\s*(\d+(?:[.,]\d+)?)\s*horas?(?:\s+(?:de|desde|despues))?",
        norm,
    )
    if m_horas and re.search(r"\b(hace|tras|luego|despues|pasaron|cumplidas|correccion|aplico|sigue)\b", norm):
        horas = _a_float(m_horas.group(1))
        datos["seguimiento"]["horas_desde_correccion"] = horas
        meta["parametros_extraidos"].append(f"horas_desde_correccion = {horas} h")

    if re.search(
        r"\b(?:2|dos)\s+muestras(?:\s+horarias)?(?:\s+consecutivas|\s+seguidas)?\s*(?:ok|conformes|dentro\s+de\s+ficha|normales|en\s+ficha)\b",
        norm,
    ):
        datos["seguimiento"]["dos_muestras_horarias_dentro_ficha"] = True
        meta["eventos_detectados"].append("2 muestras horarias consecutivas dentro de ficha")

    acciones_patrones = [
        ("EnfriarTacho", r"\b(se\s+aplico\s+enfriamiento|se\s+enfrio|aplicamos\s+enfriamiento|enfriar\s+el\s+tacho)\b"),
        ("AumentarSemilla", r"\b(se\s+aumento\s+(?:la\s+)?semilla|aumentamos\s+(?:la\s+)?semilla)\b"),
        ("DisminuirSemilla", r"\b(se\s+(?:disminuyo|redujo|bajo)\s+(?:la\s+)?semilla)\b"),
        ("AumentarTiempoLavado", r"\b(se\s+(?:aumento|extendio)\s+(?:el\s+tiempo\s+de\s+)?lavado)\b"),
        ("ReducirTiempoLavado", r"\b(se\s+(?:redujo|disminuyo)\s+(?:el\s+tiempo\s+de\s+)?lavado)\b"),
    ]
    for nombre_accion, pat_acc in acciones_patrones:
        if re.search(pat_acc, norm):
            datos["acciones_aplicadas"].append(nombre_accion)
            meta["parametros_extraidos"].append(f"accionAplicada = {nombre_accion}")

    # Si reporta horas >= 3 y persistencia de falla sin haber explicitado acción previa, inferir la más coherente
    if datos["seguimiento"]["horas_desde_correccion"] >= 3 and not datos["acciones_aplicadas"]:
        if med["temperatura_tacho_c"] is not None and med["temperatura_tacho_c"] > 85:
            datos["acciones_aplicadas"].append("EnfriarTacho")
            meta["inferencias_cualitativas"].append(
                "accionAplicada = EnfriarTacho (inferido por seguimiento >= 3 h con temperatura excedida)"
            )
        elif med["granulometria_mm"] is not None:
            datos["acciones_aplicadas"].append("AumentarSemilla")
            meta["inferencias_cualitativas"].append(
                "accionAplicada = AumentarSemilla (inferido por seguimiento >= 3 h con granulometría fuera)"
            )
        elif med["color_ui"] is not None:
            datos["acciones_aplicadas"].append("AumentarTiempoLavado")
            meta["inferencias_cualitativas"].append(
                "accionAplicada = AumentarTiempoLavado (inferido por seguimiento >= 3 h con color fuera)"
            )

    # 8. Autocompletado conservador de ficha técnica cuando solo se mencionan algunos parámetros
    if autocompletar_normales and tipo_azucar in VALORES_NORMALES_FICHA:
        normales = VALORES_NORMALES_FICHA[tipo_azucar]
        # Solo autocompletamos parámetros analíticos de ficha si al menos se mencionó algún parámetro analítico o desvío de lote
        hay_datos_lote = any(med[k] is not None for k in med) or ev["color_demasiado_claro"] or ev["color_oscuro_observado"]
        if hay_datos_lote:
            for k, val_norm in normales.items():
                if med[k] is None:
                    med[k] = val_norm
                    nombre_leg, unidad = ETIQUETAS_MEDICIONES[k]
                    meta["autocompletados"].append(f"{nombre_leg} = {val_norm} {unidad} (valor normal de referencia)")

    return datos, meta


def _llamar_gemini(prompt: str, api_key: str) -> str:
    """Llama a la API REST de Gemini con timeout acotado."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key.strip()}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    candidatos = data.get("candidates", [])
    if not candidatos:
        raise RuntimeError("La API de Gemini no devolvió candidatos.")
    partes = candidatos[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in partes).strip()


def _extraer_json_texto(texto: str) -> dict[str, Any]:
    bloque = re.search(r"\{.*\}", texto, flags=re.DOTALL)
    if not bloque:
        raise ValueError("No se encontró objeto JSON en la respuesta de Gemini.")
    return json.loads(bloque.group(0))


def traducir_consulta_a_hechos(
    texto: str,
    autocompletar_normales: bool = True,
    usar_gemini: bool = False,
    api_key: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Traduce una consulta en lenguaje natural a DATOS_CASO y metadatos de traducción."""
    datos_local, meta_local = _traducir_local(texto, autocompletar_normales=autocompletar_normales)

    clave = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not usar_gemini or not clave:
        return datos_local, meta_local

    prompt = f"""
Eres un traductor estricto de lenguaje natural al esquema JSON del SBC del Ingenio La Esperanza.
Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta (usa null si no se menciona una medición numérica, o el valor numérico representativo si se describe cualitativamente):
{{
  "id_lote": "Lote_001",
  "tipo_azucar": "CTA" | "Crudo" | "Organica",
  "ficha_cliente": {{"color_max_ui": null | 200 | 600}},
  "mediciones": {{
    "vacio_cm_hg": number | null,
    "temperatura_tacho_c": number | null,
    "brix_entrada_tacho": number | null,
    "brix_masa_cocida": number | null,
    "semilla": number | null,
    "color_ui": number | null,
    "granulometria_mm": number | null,
    "retenido_malla25_pct": number | null,
    "pol_pct": number | null,
    "sedimentos_mg_kg": number | null
  }},
  "eventos": {{
    {", ".join(f'"{k}": boolean' for k in PROPIEDADES_EVENTO)}
  }},
  "acciones_aplicadas": ["EnfriarTacho" | "AumentarSemilla" | "DisminuirSemilla" | "AumentarTiempoLavado" | "ReducirTiempoLavado"],
  "seguimiento": {{
    "horas_desde_correccion": number,
    "dos_muestras_horarias_dentro_ficha": boolean
  }}
}}
Umbrales: S1 Temp >85 excedida, 70-85 alerta, <=70 normal; S2 Vacío <60 bajo, 60-62 normal; S3 Brix <60 bajo, 60-63 normal, >63 alto (92 masa cocida); S4 Semilla <100 poca, 100-150 normal, >150 mucha; S5 Color CTA<=150, Crudo<=400; S6 Pol CTA>=99.6, Crudo>=98.4; S7 Sedimentos<=30; S8 Grano CTA 0.50-0.55, Crudo 0.60-0.65.

Consulta del usuario:
\"\"\"{texto}\"\"\"
""".strip()

    try:
        respuesta_raw = _llamar_gemini(prompt, clave)
        parsed = _extraer_json_texto(respuesta_raw)

        tipo = parsed.get("tipo_azucar", datos_local["tipo_azucar"])
        if tipo not in {"CTA", "Crudo", "Organica"}:
            tipo = datos_local["tipo_azucar"]

        datos_gem = crear_caso_vacio(
            id_lote=str(parsed.get("id_lote") or datos_local["id_lote"]),
            tipo_azucar=tipo,
        )
        lim_col = parsed.get("ficha_cliente", {}).get("color_max_ui")
        if lim_col in (200, 600):
            datos_gem["ficha_cliente"]["color_max_ui"] = lim_col
        else:
            datos_gem["ficha_cliente"]["color_max_ui"] = datos_local["ficha_cliente"]["color_max_ui"]

        for k in PROPIEDADES_MEDICION:
            v = parsed.get("mediciones", {}).get(k)
            if isinstance(v, (int, float)):
                datos_gem["mediciones"][k] = float(v)
            elif datos_local["mediciones"][k] is not None and not autocompletar_normales:
                datos_gem["mediciones"][k] = datos_local["mediciones"][k]

        if autocompletar_normales and tipo in VALORES_NORMALES_FICHA:
            hay_datos = any(datos_gem["mediciones"][k] is not None for k in PROPIEDADES_MEDICION)
            if hay_datos:
                for k, val_norm in VALORES_NORMALES_FICHA[tipo].items():
                    if datos_gem["mediciones"][k] is None:
                        datos_gem["mediciones"][k] = val_norm
                        nombre_leg, unidad = ETIQUETAS_MEDICIONES[k]
                        meta_local["autocompletados"].append(f"{nombre_leg} = {val_norm} {unidad} (referencia)")

        for k in PROPIEDADES_EVENTO:
            datos_gem["eventos"][k] = bool(parsed.get("eventos", {}).get(k, datos_local["eventos"][k]))

        acciones_val = [a for a in parsed.get("acciones_aplicadas", []) if a in ACCIONES]
        datos_gem["acciones_aplicadas"] = acciones_val or datos_local["acciones_aplicadas"]

        seg = parsed.get("seguimiento", {})
        horas = seg.get("horas_desde_correccion", datos_local["seguimiento"]["horas_desde_correccion"])
        datos_gem["seguimiento"]["horas_desde_correccion"] = float(horas) if isinstance(horas, (int, float)) else 0
        datos_gem["seguimiento"]["dos_muestras_horarias_dentro_ficha"] = bool(
            seg.get(
                "dos_muestras_horarias_dentro_ficha",
                datos_local["seguimiento"]["dos_muestras_horarias_dentro_ficha"],
            )
        )

        meta_local["metodo"] = "Híbrido (Gemini API + Validación Local)"
        return datos_gem, meta_local
    except Exception as exc:
        meta_local["error_gemini"] = str(exc)
        meta_local["notas"].append(f"Gemini no disponible ({exc}); se utilizó el traductor PLN local.")
        return datos_local, meta_local


def _generar_respuesta_local(
    consulta: str, resultado: dict[str, Any], meta: dict[str, Any]
) -> str:
    """Redacta una respuesta en español natural clara, trazable y orientada al Jefe de Turno."""
    datos = resultado["datos_entrada"]
    tipo = datos["tipo_azucar"]
    lote = datos["id_lote"]
    estados = resultado["estado_lote"]
    indicadores = resultado["indicadores_detectados"]
    diagnosticos = resultado["diagnosticos"]
    acciones = resultado["acciones_recomendadas"]
    opciones_miel = resultado["opciones_destino_miel"]
    advertencias = resultado["advertencias"]
    activaciones = resultado["activaciones"]
    reglas_disparadas = [a["regla"].split("_")[0] for a in activaciones if not a["regla"].startswith("AUX_")]

    secciones: list[str] = []

    # 1. Interpretación de la consulta
    meds_activas = []
    for k, val in datos["mediciones"].items():
        if val is not None:
            nombre, unidad = ETIQUETAS_MEDICIONES[k]
            meds_activas.append(f"{nombre}: {val:g} {unidad}".strip())
    evs_activos = [ETIQUETAS_EVENTOS[k] for k, v in datos["eventos"].items() if v]

    resumen_entrada = f"Analicé tu consulta para **{lote}** (Azúcar **{tipo}**)."
    if meds_activas:
        resumen_entrada += "\n• Parámetros considerados: " + "; ".join(meds_activas[:6])
        if len(meds_activas) > 6:
            resumen_entrada += f" (+{len(meds_activas) - 6} parámetros de ficha)."
    if evs_activos:
        resumen_entrada += "\n• Situaciones operativas detectadas: " + "; ".join(evs_activos) + "."
    if meta.get("autocompletados"):
        resumen_entrada += (
            "\n• Nota: Se completaron con valores normales de referencia los parámetros de ficha no informados "
            "para poder evaluar conformidad (podés desactivarlo arriba si querés evaluación parcial)."
        )
    secciones.append("1. INTERPRETACIÓN DE LA CONSULTA\n" + resumen_entrada)

    # 2. Dictamen de Calidad
    if "NoConforme" in estados or "EnDeposito" in estados:
        dictamen = (
            "DICTAMEN: LOTE NO CONFORME — RECHAZADO Y DERIVADO A DEPÓSITO DE RETENCIÓN [R12, R43].\n"
            "Al menos un parámetro analítico o de calidad transgrede la ficha técnica vigente, por lo que "
            "el laboratorio formaliza el rechazo y ordena separar la masa para reproceso."
        )
    elif "Aprobado" in estados:
        dictamen = (
            "DICTAMEN: LOTE APROBADO (CONFORME A FICHA TÉCNICA) [R11].\n"
            "Los parámetros analíticos de color, granulometría, polarización y sedimentos satisfacen "
            "todos los límites establecidos para este tipo de azúcar."
        )
    elif tipo == "Organica":
        dictamen = (
            "DICTAMEN: OPERACIÓN EN AZÚCAR ORGÁNICA (SIN FICHA NUMÉRICA ESTÁNDAR) [R47].\n"
            "El SBC aplica las reglas de tratamiento químico exclusivo y contingencias operativas, "
            "sin inventar límites numéricos de calidad."
        )
    else:
        dictamen = (
            "DICTAMEN: EVALUACIÓN OPERATIVA EN CURSO (SIN DICTAMEN DE LOTE) [Validación].\n"
            "Faltan mediciones analíticas completas de laboratorio para emitir Aprobado o No Conforme, "
            "pero se ejecutan las reglas de proceso y contingencia aplicables."
        )
    secciones.append("2. DICTAMEN DEL LOTE\n" + dictamen)

    # 3. Cadena Causal y Diagnóstico
    if indicadores or diagnosticos:
        lineas_diag: list[str] = []
        if indicadores:
            lineas_diag.append("• Condiciones inferidas por el motor: " + ", ".join(indicadores) + ".")
        if diagnosticos:
            lineas_diag.append("• Diagnóstico causal:")
            for d in diagnosticos:
                lineas_diag.append(f"  - {d['tipo']}: {d['nombre']} ({d['explicacion']})")
        else:
            lineas_diag.append("• No se registró una causa de falla específica con las reglas activadas.")
        secciones.append("3. DIAGNÓSTICO Y RAZONAMIENTO CAUSAL\n" + "\n".join(lineas_diag))

    # 4. Directivas y Órdenes Correctivas
    if acciones:
        criticas_ids = {
            "PararTacho",
            "LimpiarTacho",
            "SepararMasaParaReproceso",
            "DescargarTachoUrgente",
            "EnfriarTacho",
            "RecuperarVacio",
        }
        muestreo_ids = {
            "TomarMuestraLaboratorio",
            "AvisarLaboratorio",
            "TomarMuestrasInstantaneas",
            "MuestraSedimentos",
            "MuestrearMaestroCada15Min",
            "VerificarEfecto",
            "VolverMuestreoNormal",
        }
        reproceso_ids = {
            "LicuarAzucarYReingresar",
            "DecisionJefeTurno",
            "AjustarLavado",
            "AjustarCentrifugado",
            "AjustarZarandeado",
            "AjustarCocimiento",
            "MonitorearHastaCumplir",
        }

        criticas, operativas, muestreo, reproceso = [], [], [], []
        for acc in acciones:
            aid = acc["id"]
            linea = f"  - {acc['descripcion']} [{acc['regla_origen']}]"
            if aid in criticas_ids:
                criticas.append(linea)
            elif aid in muestreo_ids:
                muestreo.append(linea)
            elif aid in reproceso_ids:
                reproceso.append(linea)
            else:
                operativas.append(linea)

        bloques_acc: list[str] = []
        if criticas:
            bloques_acc.append("• Prioridad Crítica / Intervención Inmediata:\n" + "\n".join(criticas))
        if operativas:
            bloques_acc.append("• Ajustes Operativos y Contexto:\n" + "\n".join(operativas))
        if reproceso:
            bloques_acc.append("• Reproceso de Lote en Depósito:\n" + "\n".join(reproceso))
        if opciones_miel:
            bloques_acc.append(
                "• Alternativas de Destino de Miel Disuelta (decide el Jefe de Turno - R45):\n"
                + "\n".join(f"  - {op}" for op in opciones_miel)
            )
        if muestreo:
            bloques_acc.append("• Plan de Muestreo y Seguimiento:\n" + "\n".join(muestreo))

        secciones.append("4. DIRECTIVAS Y ACCIONES RECOMENDADAS\n" + "\n".join(bloques_acc))

    # 5. Advertencias y trazabilidad resumida
    extras: list[str] = []
    for adv in advertencias:
        extras.append(f"• ADVERTENCIA [R40]: {adv}")
    for nota in resultado["notas_validacion"]:
        if "crítico" in nota.lower() or "faltan" in nota.lower():
            extras.append(f"• {nota}")
    if reglas_disparadas:
        extras.append(
            f"• Reglas oficiales disparadas ({len(reglas_disparadas)} en {len(activaciones)} ciclos): "
            + ", ".join(dict.fromkeys(reglas_disparadas))
            + "."
        )
    if extras:
        secciones.append("5. ADVERTENCIAS Y TRAZABILIDAD\n" + "\n".join(extras))

    return "\n\n".join(secciones)


def generar_respuesta_natural(
    consulta: str,
    resultado: dict[str, Any],
    meta: dict[str, Any],
    usar_gemini: bool = False,
    api_key: str = "",
) -> str:
    """Genera la respuesta final en lenguaje natural (local o enriquecida con Gemini)."""
    respuesta_local = _generar_respuesta_local(consulta, resultado, meta)

    clave = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not usar_gemini or not clave:
        return respuesta_local

    resumen_hechos = {
        "lote": resultado["datos_entrada"]["id_lote"],
        "tipo_azucar": resultado["datos_entrada"]["tipo_azucar"],
        "estado_lote": resultado["estado_lote"],
        "indicadores_detectados": resultado["indicadores_detectados"],
        "diagnosticos": resultado["diagnosticos"],
        "acciones_recomendadas": resultado["acciones_recomendadas"],
        "opciones_destino_miel": resultado["opciones_destino_miel"],
        "advertencias": resultado["advertencias"],
        "notas_validacion": resultado["notas_validacion"],
        "reglas_activadas": [a["regla"] for a in resultado["activaciones"]],
    }

    prompt = f"""
Eres el Asesor Virtual del SBC del Ingenio La Esperanza respondiendo al Jefe de Turno.
Redacta una respuesta clara, profesional y directa en español rioplatense/técnico usando EXCLUSIVAMENTE los hechos e inferencias provistos en el JSON siguiente (no inventes reglas, límites ni acciones fuera del JSON).
Estructura brevemente: Dictamen del lote, Explicación causal conectada, Órdenes prioritarias a ejecutar y Seguimiento/Advertencias.

Consulta original:
\"\"\"{consulta}\"\"\"

Resultados exactos del motor RDF/SPARQL:
{json.dumps(resumen_hechos, ensure_ascii=False, indent=2)}
""".strip()

    try:
        texto_gem = _llamar_gemini(prompt, clave)
        if texto_gem:
            return texto_gem + "\n\n[Respuesta redactada en modo Híbrido con Gemini API sobre los hechos exactos del motor RDF]"
    except Exception as exc:
        meta["error_gemini"] = str(exc)

    return respuesta_local
