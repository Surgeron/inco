"""
Motor de Inferencia RDF y Base de Conocimiento del SBC - Ingenio La Esperanza.

Extrae y modulariza la ontología, hechos, base de reglas SPARQL CONSTRUCT
(13 reglas auxiliares + 56 reglas oficiales R1-R56 en 72 consultas) y el
motor de encadenamiento hacia adelante definido en SBC-IngenioLaEsperanza-Colab.ipynb.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

from pyvis.network import Network
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef, XSD

ing = Namespace("http://ingenio-la-esperanza.edu/ontologia#")

PREFIJOS = f"""
PREFIX ing: <{ing}>
PREFIX rdf: <{RDF}>
PREFIX rdfs: <{RDFS}>
PREFIX owl: <{OWL}>
PREFIX xsd: <{XSD}>
""".strip()

ACCIONES: dict[str, str] = {
    "AvisarTachero": "Avisar al tachero y revisar el vacío; todavía no enfriar.",
    "RevisarVacio": "Revisar el nivel de vacío del tacho.",
    "EnfriarTacho": "Enfriar el tacho hasta 60-70 °C.",
    "DescargarTachoUrgente": "Descargar el tacho lo más rápido posible, sin esperar 92 °Bx.",
    "DescargarTachoPorBrix92": "Descargar el tacho al alcanzar 92 °Bx.",
    "AumentarSemilla": "Aumentar la semilla dentro del rango de 100 a 150 por tacho.",
    "DisminuirSemilla": "Disminuir la semilla dentro del rango de 100 a 150 por tacho.",
    "RecuperarVacio": "Recuperar el vacío hasta 60-62 cm Hg.",
    "ConcentrarJugoEvaporacion": "Solicitar a evaporación mayor concentración: Brix 60-63 y masa más pura.",
    "SepararMasaParaReproceso": "Separar la masa como mala calidad para reproceso.",
    "PararTacho": "Parar el tacho para realizar la limpieza indicada.",
    "LimpiarTacho": "Limpiar el tacho; duración y cantidad a criterio del jefe de turno.",
    "AvisarMaestrosAzucareros": "Avisar a los maestros azucareros por grano chico.",
    "AumentarTiempoLavado": "Aumentar gradualmente el tiempo de lavado en centrífuga, sin cifra fija.",
    "ReducirTiempoLavado": "Reducir el tiempo de lavado en centrífuga.",
    "AjustarZaranda": "Ajustar la zaranda.",
    "RevisarTachosYZaranda": "Revisar tachos de cocimiento y zaranda como posibles orígenes de sedimentos.",
    "VerificarEfecto": "Verificar el efecto de la corrección a las 2-3 horas (hasta 3 muestras horarias).",
    "MuestrearMaestroCada15Min": "Mientras se espera, el maestro toma una muestra cada 15 minutos.",
    "TomarMuestraLaboratorio": "El laboratorio toma una muestra horaria; primera muestra a los 10-15 minutos del turno.",
    "AvisarLaboratorio": "Avisar al laboratorio para tomar muestras instantáneas.",
    "TomarMuestrasInstantaneas": "Tomar hasta 2-3 muestras instantáneas por hora.",
    "MuestraSedimentos": "Tomar una muestra para medir sedimentos al descargar a centrífugas.",
    "LicuarAzucarYReingresar": "Licuar el azúcar del depósito para convertirlo en miel y reingresarla al circuito.",
    "OpcionTanqueJugoEncalado": "Opción de destino: tanque de jugo encalado.",
    "OpcionMielSegunda": "Opción de destino: miel de segunda.",
    "OpcionDiluirOtroSector": "Opción de destino: diluir en otro sector.",
    "DecisionJefeTurno": "La elección entre destinos queda a cargo del jefe de turno; no se automatiza.",
    "AjustarLavado": "Ajustar el lavado.",
    "AjustarCentrifugado": "Ajustar el centrifugado.",
    "AjustarZarandeado": "Ajustar el zarandeado.",
    "AjustarCocimiento": "Ajustar el cocimiento.",
    "MonitorearHastaCumplir": "Monitorear hasta lograr la calidad requerida.",
    "MaestroSegundaPasaPrimera": "El maestro de segunda pasa a primera por ausencia del maestro de primera.",
    "RespetarGranoYTemperatura": "Indicar que respete el grano y la temperatura, especialmente la temperatura.",
    "RevisarTemperaturaYBrix": "Revisar primero la temperatura del tacho y el Brix del jugo.",
    "SembrarCantidadEstandar": "Usar una cantidad de semilla de 100 a 150 por tacho y mantener el Brix parejo.",
    "NoRetamizarDuranteProceso": "No retamizar mientras el proceso continuo está en marcha.",
    "RetamizarLoteTerminado": "Se puede retamizar porque el lote terminó de producirse.",
    "AvisarTerronesSecador": "Avisar y registrar la observación de azúcar con terrones (humedad baja).",
    "AvisarAzucarHumedaSecador": "Avisar y registrar azúcar húmeda que escurre miel; resulta difícil de vender.",
    "UsarSoloCal": "Para orgánica: usar solo cal, sin azufre ni floculantes.",
    "UsarAditivosDOR": "Para CTA: usar azufre, cal y floculantes en DOR, más buen tiempo de lavado.",
    "VolverMuestreoNormal": "Volver al esquema de muestreo normal tras dos muestras horarias conformes.",
}

CAUSAS_DESCRIPCION: dict[str, tuple[str, str]] = {
    "QuemadoPorTemperatura": (
        "Quemado por temperatura",
        "El color fuera de ficha coincide con temperatura del tacho excedida (> 85 °C o ebullición alta).",
    ),
    "PerdidaDeVacio": (
        "Pérdida de vacío",
        "La pérdida de vacío (< 60 cmHg) elevó la temperatura de ebullición y quemó el azúcar.",
    ),
    "LavadoCentrifuga": (
        "Ciclo de lavado en centrífuga",
        "El color está fuera de ficha con temperatura normal (<= 70 °C); la causa radica en el lavado centrífugo.",
    ),
    "SemillaInsuficiente": (
        "Semilla insuficiente",
        "Granulometría con grano grande combinada con Brix alto (> 63 °Bx) y poca semilla (< 100).",
    ),
    "ExcesoDeSemilla": (
        "Exceso de semilla",
        "Granulometría con grano chico provocada por dosificación excesiva de semilla (> 150).",
    ),
    "ConcentracionBajaEnTacho": (
        "Concentración baja en tacho",
        "Grano chico acompañado de Brix de entrada bajo (< 60 °Bx).",
    ),
    "JugoDeEntradaPobre": (
        "Jugo de entrada pobre",
        "El Brix bajo (< 60 °Bx) afecta color o granulometría y reduce pureza.",
    ),
    "TachoSucio": (
        "Tacho sucio (falla recurrente)",
        "Tras 3 horas de corrección el desvío persiste, indicando incrustaciones o suciedad en el tacho.",
    ),
}

PROPIEDADES_MEDICION: dict[str, URIRef] = {
    "vacio_cm_hg": ing.vacioCmHg,
    "temperatura_tacho_c": ing.temperaturaTachoC,
    "brix_entrada_tacho": ing.brixEntradaTacho,
    "brix_masa_cocida": ing.brixMasaCocida,
    "semilla": ing.cantidadSemilla,
    "color_ui": ing.colorUI,
    "granulometria_mm": ing.granulometriaMm,
    "retenido_malla25_pct": ing.retenidoMalla25Pct,
    "pol_pct": ing.polPct,
    "sedimentos_mg_kg": ing.sedimentosMgKg,
}

PROPIEDADES_EVENTO: dict[str, URIRef] = {
    "tacho_en_coccion": ing.tachoEnCoccion,
    "paso_una_hora": ing.pasoUnaHora,
    "primera_muestra_turno": ing.primeraMuestraTurno,
    "jefe_ve_color_distinto": ing.jefeVeColorDistinto,
    "tacho_descargado_centrifugas": ing.tachoDescargadoACentrifugas,
    "tachero_ve_grano_grande": ing.tacheroVeGranoGrande,
    "color_demasiado_claro": ing.colorDemasiadoClaro,
    "color_oscuro_observado": ing.colorOscuroObservado,
    "lote_terminado": ing.loteTerminado,
    "detectado_en_zaranda": ing.detectadoEnZaranda,
    "proceso_continuo": ing.procesoContinuo,
    "falta_maestro_primera": ing.faltaMaestroPrimera,
    "reemplazo_turno": ing.reemplazoTurno,
    "se_va_a_sembrar": ing.seVaASembrar,
    "secador_terroneado": ing.secadorTerroneado,
    "secador_azucar_humeda": ing.secadorAzucarHumeda,
    "tachero_nota_color_oscuro_antes_laboratorio": ing.tacheroNotaColorOscuroAntesLaboratorio,
}

ETIQUETAS_MEDICIONES: dict[str, tuple[str, str]] = {
    "vacio_cm_hg": ("Vacío del tacho", "cmHg"),
    "temperatura_tacho_c": ("Temperatura del tacho", "°C"),
    "brix_entrada_tacho": ("Brix jugo de entrada", "°Bx"),
    "brix_masa_cocida": ("Brix masa cocida", "°Bx"),
    "semilla": ("Dosificación de semilla", "unidades/tacho"),
    "color_ui": ("Color ICUMSA", "UI"),
    "granulometria_mm": ("Granulometría", "mm"),
    "retenido_malla25_pct": ("Retenido malla 25", "%"),
    "pol_pct": ("Polarización (Pol)", "°Z / %"),
    "sedimentos_mg_kg": ("Sedimentos", "mg/kg"),
}

ETIQUETAS_EVENTOS: dict[str, str] = {
    "tacho_en_coccion": "Tacho en cocción",
    "paso_una_hora": "Transcurrió 1 hora de operación",
    "primera_muestra_turno": "Primera muestra del turno (10-15 min)",
    "jefe_ve_color_distinto": "Jefe advierte color distinto a simple vista",
    "tacho_descargado_centrifugas": "Tacho descargado a centrífugas",
    "tachero_ve_grano_grande": "Tachero detecta grano grande en toma-muestras",
    "color_demasiado_claro": "Color observado demasiado claro",
    "color_oscuro_observado": "Color oscuro observado",
    "lote_terminado": "Lote terminado de producir",
    "detectado_en_zaranda": "Desvío detectado en zaranda",
    "proceso_continuo": "Proceso continuo en marcha",
    "falta_maestro_primera": "Falta maestro azucarero de primera",
    "reemplazo_turno": "Hay reemplazo de otro turno",
    "se_va_a_sembrar": "Se va a efectuar sembrado",
    "secador_terroneado": "Secador: azúcar con terrones (humedad baja)",
    "secador_azucar_humeda": "Secador: azúcar húmeda escurriendo miel",
    "tachero_nota_color_oscuro_antes_laboratorio": "Tachero nota color oscuro antes del laboratorio",
}


def _construir_esquema() -> Graph:
    """Construye el grafo esquema reutilizable con clases, tipos y acciones."""
    grafo = Graph()
    for prefijo, namespace in [
        ("ing", ing),
        ("rdf", RDF),
        ("rdfs", RDFS),
        ("owl", OWL),
        ("xsd", XSD),
    ]:
        grafo.bind(prefijo, namespace)

    grafo.add((ing.Lote, RDF.type, OWL.Class))
    grafo.add((ing.TipoAzucar, RDF.type, OWL.Class))
    grafo.add((ing.Accion, RDF.type, OWL.Class))
    grafo.add((ing.Causa, RDF.type, OWL.Class))

    for tipo, etiqueta in [
        (ing.CTA, "CTA (azúcar tipo A)"),
        (ing.Crudo, "Azúcar crudo"),
        (ing.Organica, "Azúcar orgánica"),
    ]:
        grafo.add((tipo, RDF.type, ing.TipoAzucar))
        grafo.add((tipo, RDFS.label, Literal(etiqueta, lang="es")))

    for nombre, descripcion in ACCIONES.items():
        recurso = ing[nombre]
        grafo.add((recurso, RDF.type, ing.Accion))
        grafo.add((recurso, RDFS.label, Literal(descripcion, lang="es")))

    for recurso, etiqueta in [
        (ing.Lote, "Lote de azúcar"),
        (ing.TipoAzucar, "Tipo de azúcar"),
        (ing.Accion, "Acción o recomendación"),
        (ing.Causa, "Causa probable"),
    ]:
        grafo.add((recurso, RDFS.label, Literal(etiqueta, lang="es")))

    return grafo


G_ESQUEMA = _construir_esquema()


def crear_regla(id_regla: str, prioridad: int, descripcion: str, consulta: str) -> dict[str, Any]:
    return {
        "id": id_regla,
        "prioridad": prioridad,
        "descripcion": descripcion,
        "query": PREFIJOS + "\n" + consulta.strip(),
    }


base_de_reglas: list[dict[str, Any]] = [
    # ---------------------------------------------------------
    # REGLAS AUXILIARES: interpretación de mediciones / ficha
    # ---------------------------------------------------------
    crear_regla(
        "AUX_ColorFuera_CTA",
        5,
        "Color CTA supera el máximo de la ficha (S5: 150 UI por defecto; 200 si la ficha lo indica).",
        """
        CONSTRUCT { ?lote ing:colorFuera true . }
        WHERE { ?lote ing:tipoAzucar ing:CTA ; ing:colorUI ?v ; ing:colorMaxFichaUI ?lim . FILTER(xsd:decimal(?v) > xsd:decimal(?lim)) }
        """,
    ),
    crear_regla(
        "AUX_ColorFuera_Crudo",
        5,
        "Color crudo supera el máximo de la ficha (S5: 400 UI por defecto; 600 si la ficha lo indica).",
        """
        CONSTRUCT { ?lote ing:colorFuera true . }
        WHERE { ?lote ing:tipoAzucar ing:Crudo ; ing:colorUI ?v ; ing:colorMaxFichaUI ?lim . FILTER(xsd:decimal(?v) > xsd:decimal(?lim)) }
        """,
    ),
    crear_regla(
        "AUX_ColorFuera_Observacion",
        5,
        "Color demasiado claro por observación en tipos con ficha de color definida.",
        """
        CONSTRUCT { ?lote ing:colorFuera true . }
        WHERE {
          ?lote ing:colorDemasiadoClaro true ; ing:tipoAzucar ?tipo .
          VALUES ?tipo { ing:CTA ing:Crudo }
        }
        """,
    ),
    crear_regla(
        "AUX_GranoGrande_CTA",
        5,
        "Granulometría CTA mayor a 0.55 mm.",
        """
        CONSTRUCT { ?lote ing:granoGrande true . }
        WHERE { ?lote ing:tipoAzucar ing:CTA ; ing:granulometriaMm ?v . FILTER(xsd:decimal(?v) > 0.55) }
        """,
    ),
    crear_regla(
        "AUX_GranoGrande_Crudo",
        5,
        "Granulometría crudo mayor a 0.65 mm.",
        """
        CONSTRUCT { ?lote ing:granoGrande true . }
        WHERE { ?lote ing:tipoAzucar ing:Crudo ; ing:granulometriaMm ?v . FILTER(xsd:decimal(?v) > 0.65) }
        """,
    ),
    crear_regla(
        "AUX_GranoChico_CTA",
        5,
        "Granulometría CTA menor a 0.50 mm.",
        """
        CONSTRUCT { ?lote ing:granoChico true . }
        WHERE { ?lote ing:tipoAzucar ing:CTA ; ing:granulometriaMm ?v . FILTER(xsd:decimal(?v) < 0.50) }
        """,
    ),
    crear_regla(
        "AUX_GranoChico_Crudo",
        5,
        "Granulometría crudo menor a 0.60 mm.",
        """
        CONSTRUCT { ?lote ing:granoChico true . }
        WHERE { ?lote ing:tipoAzucar ing:Crudo ; ing:granulometriaMm ?v . FILTER(xsd:decimal(?v) < 0.60) }
        """,
    ),
    crear_regla(
        "AUX_RetenidoFuera_CTA",
        5,
        "Retenido en malla 25 CTA mayor a 20 %.",
        """
        CONSTRUCT { ?lote ing:granulometriaFuera true . }
        WHERE { ?lote ing:tipoAzucar ing:CTA ; ing:retenidoMalla25Pct ?v . FILTER(xsd:decimal(?v) > 20) }
        """,
    ),
    crear_regla(
        "AUX_PolFuera_CTA",
        5,
        "Pol CTA menor a 99.6 %.",
        """
        CONSTRUCT { ?lote ing:purezaFuera true . }
        WHERE { ?lote ing:tipoAzucar ing:CTA ; ing:polPct ?v . FILTER(xsd:decimal(?v) < 99.6) }
        """,
    ),
    crear_regla(
        "AUX_PolFuera_Crudo",
        5,
        "Pol crudo menor a 98.4 %.",
        """
        CONSTRUCT { ?lote ing:purezaFuera true . }
        WHERE { ?lote ing:tipoAzucar ing:Crudo ; ing:polPct ?v . FILTER(xsd:decimal(?v) < 98.4) }
        """,
    ),
    crear_regla(
        "AUX_SedimentosFuera",
        5,
        "Sedimentos mayores a 30 mg/kg.",
        """
        CONSTRUCT { ?lote ing:sedimentosFuera true . }
        WHERE { ?lote ing:sedimentosMgKg ?v . FILTER(xsd:decimal(?v) > 30) }
        """,
    ),
    crear_regla(
        "AUX_SemillaPoca",
        5,
        "Semilla menor a 100 por tacho.",
        """
        CONSTRUCT { ?lote ing:semillaPoca true . }
        WHERE { ?lote ing:cantidadSemilla ?v . FILTER(xsd:decimal(?v) < 100) }
        """,
    ),
    crear_regla(
        "AUX_SemillaMucha",
        5,
        "Semilla mayor a 150 por tacho.",
        """
        CONSTRUCT { ?lote ing:semillaMucha true . }
        WHERE { ?lote ing:cantidadSemilla ?v . FILTER(xsd:decimal(?v) > 150) }
        """,
    ),
    # ---------------------------------------------------------
    # A. MECANISMO DEL TACHO
    # ---------------------------------------------------------
    crear_regla(
        "R1_VacioBajo",
        10,
        "Vacío menor a 60 cm Hg: vacío bajo y ebullición alta.",
        """
        CONSTRUCT { ?lote ing:vacioBajo true ; ing:tempEbullicionAlta true . }
        WHERE { ?lote ing:vacioCmHg ?v . FILTER(xsd:decimal(?v) < 60) }
        """,
    ),
    crear_regla(
        "R2_TemperaturaExcedida",
        10,
        "Ebullición alta o temperatura mayor a 85 °C.",
        """
        CONSTRUCT { ?lote ing:tempExcedida true . }
        WHERE {
          { ?lote ing:tempEbullicionAlta true . }
          UNION
          { ?lote ing:temperaturaTachoC ?t . FILTER(xsd:decimal(?t) > 85) }
        }
        """,
    ),
    crear_regla(
        "R55_TemperaturaAlerta",
        10,
        "Temperatura entre más de 70 y 85 °C: avisar y revisar vacío, sin enfriar todavía.",
        """
        CONSTRUCT {
          ?lote ing:tempAlerta true ;
                ing:recomiendaAccion ing:AvisarTachero, ing:RevisarVacio .
        }
        WHERE { ?lote ing:temperaturaTachoC ?t . FILTER(xsd:decimal(?t) > 70 && xsd:decimal(?t) <= 85) }
        """,
    ),
    crear_regla(
        "R3_AzucarQuemado",
        10,
        "Temperatura excedida implica azúcar quemado.",
        """
        CONSTRUCT { ?lote ing:azucarQuemado true . }
        WHERE { ?lote ing:tempExcedida true . }
        """,
    ),
    crear_regla(
        "R4_ColorOscuro",
        10,
        "Azúcar quemado implica color oscuro.",
        """
        CONSTRUCT { ?lote ing:colorOscuro true . }
        WHERE { ?lote ing:azucarQuemado true . }
        """,
    ),
    crear_regla(
        "R5_GranoGrande",
        10,
        "Brix alto y semilla poca implican grano grande.",
        """
        CONSTRUCT { ?lote ing:granoGrande true . }
        WHERE { ?lote ing:brixAlto true ; ing:semillaPoca true . }
        """,
    ),
    crear_regla(
        "R6_GranoChico",
        10,
        "Brix bajo o semilla mucha implican grano chico.",
        """
        CONSTRUCT { ?lote ing:granoChico true . }
        WHERE {
          { ?lote ing:brixBajo true . }
          UNION
          { ?lote ing:semillaMucha true . }
        }
        """,
    ),
    crear_regla(
        "R7_GranulometriaFuera",
        10,
        "Grano grande o chico implican granulometría fuera de rango.",
        """
        CONSTRUCT { ?lote ing:granulometriaFuera true . }
        WHERE {
          { ?lote ing:granoGrande true . }
          UNION
          { ?lote ing:granoChico true . }
        }
        """,
    ),
    crear_regla(
        "R8_PurezaBajaPorBrix",
        10,
        "Brix bajo implica pureza baja (regla tomada como confirmada).",
        """
        CONSTRUCT { ?lote ing:purezaBaja true . }
        WHERE { ?lote ing:brixBajo true . }
        """,
    ),
    crear_regla(
        "R9_GranulometriaPorPureza",
        10,
        "Pureza baja implica granulometría fuera.",
        """
        CONSTRUCT { ?lote ing:granulometriaFuera true . }
        WHERE { ?lote ing:purezaBaja true . }
        """,
    ),
    crear_regla(
        "R10_ObservacionGranoGrande",
        10,
        "El tachero observa o toca grano grande.",
        """
        CONSTRUCT { ?lote ing:granoGrande true . }
        WHERE { ?lote ing:tacheroVeGranoGrande true . }
        """,
    ),
    crear_regla(
        "R52_BrixBajo",
        10,
        "Brix de entrada al tacho menor a 60.",
        """
        CONSTRUCT { ?lote ing:brixBajo true . }
        WHERE { ?lote ing:brixEntradaTacho ?b . FILTER(xsd:decimal(?b) < 60) }
        """,
    ),
    crear_regla(
        "R52_BrixAlto",
        10,
        "Brix de entrada al tacho mayor a 63.",
        """
        CONSTRUCT { ?lote ing:brixAlto true . }
        WHERE { ?lote ing:brixEntradaTacho ?b . FILTER(xsd:decimal(?b) > 63) }
        """,
    ),
    crear_regla(
        "R52_BrixNormal",
        10,
        "Brix de entrada entre 60 y 63: rango normal según S3.",
        """
        CONSTRUCT { ?lote ing:brixNormal true . }
        WHERE { ?lote ing:brixEntradaTacho ?b . FILTER(xsd:decimal(?b) >= 60 && xsd:decimal(?b) <= 63) }
        """,
    ),
    crear_regla(
        "R53_Descarga92Brix",
        15,
        "Masa cocida llega a 92 °Bx: descargar tacho.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:DescargarTachoPorBrix92 . }
        WHERE { ?lote ing:brixMasaCocida ?b . FILTER(xsd:decimal(?b) >= 92) }
        """,
    ),
    crear_regla(
        "R54_MuestreoTachero",
        15,
        "Tacho en cocción: maestro toma muestra cada 15 minutos.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:MuestrearMaestroCada15Min . }
        WHERE { ?lote ing:tachoEnCoccion true . }
        """,
    ),
    # ---------------------------------------------------------
    # B. MUESTREO Y DICTAMEN
    # ---------------------------------------------------------
    crear_regla(
        "R49_MuestraLaboratorio",
        15,
        "Primera muestra del turno, pasó una hora o se reinicia muestreo normal.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:TomarMuestraLaboratorio . }
        WHERE {
          { ?lote ing:primeraMuestraTurno true . }
          UNION { ?lote ing:pasoUnaHora true . }
          UNION { ?lote ing:correccionLograda true . }
        }
        """,
    ),
    crear_regla(
        "R50_ColorVisualMuestreoInstantaneo",
        15,
        "Color visual distinto al pedido: avisar al laboratorio y tomar hasta 2-3 muestras por hora.",
        """
        CONSTRUCT {
          ?lote ing:recomiendaAccion ing:AvisarLaboratorio, ing:TomarMuestrasInstantaneas ;
                ing:frecuenciaMuestrasInstantaneas "hasta 2 o 3 por hora" .
        }
        WHERE { ?lote ing:jefeVeColorDistinto true . }
        """,
    ),
    crear_regla(
        "R51_MuestraSedimentosDescarga",
        15,
        "Descarga del tacho a centrífugas: laboratorio toma muestra de sedimentos.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:MuestraSedimentos . }
        WHERE { ?lote ing:tachoDescargadoACentrifugas true . }
        """,
    ),
    crear_regla(
        "R11_LoteAprobado_CTA",
        20,
        "Los cuatro parámetros CTA cumplen la ficha.",
        """
        CONSTRUCT { ?lote ing:loteAprobado true ; ing:estadoLote ing:Aprobado . }
        WHERE {
          ?lote rdf:type ing:Lote ; ing:tipoAzucar ing:CTA ;
                ing:colorUI ?color ; ing:granulometriaMm ?grano ;
                ing:retenidoMalla25Pct ?ret ; ing:polPct ?pol ; ing:sedimentosMgKg ?sed .
          ?lote ing:colorMaxFichaUI ?limColor .
          FILTER(xsd:decimal(?color) <= xsd:decimal(?limColor) && xsd:decimal(?grano) >= 0.50 && xsd:decimal(?grano) <= 0.55 && xsd:decimal(?ret) <= 20 && xsd:decimal(?pol) >= 99.6 && xsd:decimal(?sed) <= 30)
          FILTER NOT EXISTS { ?lote ing:colorDemasiadoClaro true . }
        }
        """,
    ),
    crear_regla(
        "R11_LoteAprobado_Crudo",
        20,
        "Los cuatro parámetros de azúcar crudo cumplen la ficha.",
        """
        CONSTRUCT { ?lote ing:loteAprobado true ; ing:estadoLote ing:Aprobado . }
        WHERE {
          ?lote rdf:type ing:Lote ; ing:tipoAzucar ing:Crudo ;
                ing:colorUI ?color ; ing:granulometriaMm ?grano ;
                ing:polPct ?pol ; ing:sedimentosMgKg ?sed ; ing:colorMaxFichaUI ?limColor .
          FILTER(xsd:decimal(?color) <= xsd:decimal(?limColor) && xsd:decimal(?grano) >= 0.60 && xsd:decimal(?grano) <= 0.65 && xsd:decimal(?pol) >= 98.4 && xsd:decimal(?sed) <= 30)
          FILTER NOT EXISTS { ?lote ing:colorDemasiadoClaro true . }
        }
        """,
    ),
    crear_regla(
        "R12_LoteNoConforme",
        20,
        "Al menos un parámetro está fuera de la ficha y se activa diagnóstico.",
        """
        CONSTRUCT { ?lote ing:loteNoConforme true ; ing:diagnosticoActivado true ; ing:estadoLote ing:NoConforme . }
        WHERE {
          ?lote ing:tipoAzucar ?tipo .
          VALUES ?tipo { ing:CTA ing:Crudo }
          {
            ?lote ing:colorFuera true .
          } UNION {
            ?lote ing:granulometriaFuera true .
          } UNION {
            ?lote ing:purezaFuera true .
          } UNION {
            ?lote ing:sedimentosFuera true .
          }
        }
        """,
    ),
    crear_regla(
        "R43_RechazoDeposito",
        35,
        "Lote no conforme: laboratorio rechaza y envía a depósito.",
        """
        CONSTRUCT {
          ?lote ing:loteEnDeposito true ; ing:estadoLote ing:EnDeposito ;
                ing:recomiendaAccion ing:SepararMasaParaReproceso .
        }
        WHERE { ?lote ing:loteNoConforme true . }
        """,
    ),
    # ---------------------------------------------------------
    # C. DIAGNOSTICO
    # ---------------------------------------------------------
    crear_regla(
        "R13_CausaColorQuemado",
        30,
        "Lote no conforme, color fuera y temperatura excedida: quemado por temperatura.",
        """
        CONSTRUCT { ?lote ing:causaColor ing:QuemadoPorTemperatura . }
        WHERE { ?lote ing:loteNoConforme true ; ing:colorFuera true ; ing:tempExcedida true . }
        """,
    ),
    crear_regla(
        "R14_CausaRaizPerdidaVacio",
        30,
        "Quemado por temperatura y vacío bajo: pérdida de vacío.",
        """
        CONSTRUCT { ?lote ing:causaRaiz ing:PerdidaDeVacio . }
        WHERE { ?lote ing:causaColor ing:QuemadoPorTemperatura ; ing:vacioBajo true . }
        """,
    ),
    crear_regla(
        "R37_CausaColorLavado",
        30,
        "Lote no conforme, color fuera y temperatura normal hasta 70 °C: revisar lavado de centrífuga.",
        """
        CONSTRUCT { ?lote ing:causaColor ing:LavadoCentrifuga . }
        WHERE {
          ?lote ing:loteNoConforme true ; ing:colorFuera true ; ing:temperaturaTachoC ?t .
          FILTER(xsd:decimal(?t) <= 70)
        }
        """,
    ),
    crear_regla(
        "R15_CausaSemillaInsuficiente",
        30,
        "Grano grande, Brix alto y semilla poca: semilla insuficiente.",
        """
        CONSTRUCT { ?lote ing:causaTecnica ing:SemillaInsuficiente . }
        WHERE {
          ?lote ing:loteNoConforme true ; ing:granulometriaFuera true ; ing:granoGrande true ;
                ing:brixAlto true ; ing:semillaPoca true .
        }
        """,
    ),
    crear_regla(
        "R16_CausaExcesoSemilla",
        30,
        "Grano chico y semilla mucha: exceso de semilla.",
        """
        CONSTRUCT { ?lote ing:causaTecnica ing:ExcesoDeSemilla . }
        WHERE { ?lote ing:loteNoConforme true ; ing:granulometriaFuera true ; ing:granoChico true ; ing:semillaMucha true . }
        """,
    ),
    crear_regla(
        "R34_CausaConcentracionBajaTacho",
        31,
        "Grano chico y Brix bajo: concentración baja en tacho.",
        """
        CONSTRUCT { ?lote ing:causaTecnica ing:ConcentracionBajaEnTacho . }
        WHERE { ?lote ing:granoChico true ; ing:brixBajo true . }
        """,
    ),
    crear_regla(
        "R17_CausaJugoEntradaPobre",
        30,
        "Brix bajo y color o granulometría fuera: jugo de entrada pobre.",
        """
        CONSTRUCT { ?lote ing:causaTecnica ing:JugoDeEntradaPobre . }
        WHERE {
          ?lote ing:brixBajo true .
          { ?lote ing:colorFuera true . } UNION { ?lote ing:granulometriaFuera true . }
        }
        """,
    ),
    crear_regla(
        "R32_OrigenPosibleSedimentos",
        30,
        "Sedimentos mayores a 30 mg/kg: revisar tachos y zaranda.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:RevisarTachosYZaranda . }
        WHERE { ?lote ing:sedimentosFuera true . }
        """,
    ),
    crear_regla(
        "R18_CausaTachoSucio",
        70,
        "Color o granulometría fuera y corrección sin efecto: tacho sucio.",
        """
        CONSTRUCT { ?lote ing:causaTecnica ing:TachoSucio . }
        WHERE {
          ?lote ing:correccionSinEfecto true .
          { ?lote ing:colorFuera true . } UNION { ?lote ing:granulometriaFuera true . }
        }
        """,
    ),
    # ---------------------------------------------------------
    # D. ORDENES CORRECTIVAS
    # ---------------------------------------------------------
    crear_regla(
        "R19_OrdenEnfriarTacho",
        40,
        "Temperatura excedida: enfriar hasta 60-70 °C.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:EnfriarTacho . }
        WHERE { ?lote ing:tempExcedida true . }
        """,
    ),
    crear_regla(
        "R20_DescargaUrgenteGranoGrande",
        45,
        "Grano grande: descargar lo antes posible sin esperar 92 °Bx.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:DescargarTachoUrgente . }
        WHERE { ?lote ing:granoGrande true . }
        """,
    ),
    crear_regla(
        "R21_AumentarSemilla",
        40,
        "Causa semilla insuficiente: aumentar dentro de 100-150.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AumentarSemilla . }
        WHERE { ?lote ing:causaTecnica ing:SemillaInsuficiente . }
        """,
    ),
    crear_regla(
        "R22_DisminuirSemilla",
        40,
        "Causa exceso de semilla: disminuir dentro de 100-150.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:DisminuirSemilla . }
        WHERE { ?lote ing:causaTecnica ing:ExcesoDeSemilla . }
        """,
    ),
    crear_regla(
        "R23_RecuperarVacio",
        40,
        "Pérdida de vacío: recuperar hasta 60-62 cm Hg.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:RecuperarVacio . }
        WHERE { ?lote ing:causaRaiz ing:PerdidaDeVacio . }
        """,
    ),
    crear_regla(
        "R24_AjusteEvaporacion",
        40,
        "Jugo pobre o concentración baja: solicitar a evaporación Brix 60-63 y masa más pura.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:ConcentrarJugoEvaporacion . }
        WHERE {
          { ?lote ing:causaTecnica ing:JugoDeEntradaPobre . }
          UNION
          { ?lote ing:causaTecnica ing:ConcentracionBajaEnTacho . }
        }
        """,
    ),
    crear_regla(
        "R25_ReprocesoTachoSucio",
        75,
        "Tacho sucio: separar masa para reproceso, parar y limpiar tacho.",
        """
        CONSTRUCT {
          ?lote ing:recomiendaAccion ing:SepararMasaParaReproceso, ing:PararTacho, ing:LimpiarTacho .
          ?lote ing:masaSeparadaParaReproceso true .
        }
        WHERE { ?lote ing:causaTecnica ing:TachoSucio . }
        """,
    ),
    crear_regla(
        "R33_AvisarMaestrosGranoChico",
        40,
        "Grano chico: avisar a los maestros azucareros.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AvisarMaestrosAzucareros . }
        WHERE { ?lote ing:granoChico true . }
        """,
    ),
    crear_regla(
        "R38_AumentarLavado",
        40,
        "Color oscuro (por inferencia u observación) y causa lavado: aumentar gradualmente el tiempo de lavado.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AumentarTiempoLavado . }
        WHERE {
          ?lote ing:causaColor ing:LavadoCentrifuga .
          { ?lote ing:colorOscuro true . } UNION { ?lote ing:colorOscuroObservado true . }
        }
        """,
    ),
    crear_regla(
        "R39_ReducirLavado",
        40,
        "Color demasiado claro por observación y causa lavado: reducir tiempo de lavado.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:ReducirTiempoLavado . }
        WHERE {
          ?lote ing:causaColor ing:LavadoCentrifuga ; ing:colorDemasiadoClaro true .
        }
        """,
    ),
    crear_regla(
        "R40_AdvertenciaMieles",
        41,
        "Aumentar tiempo de lavado incrementa la cantidad de mieles: advertencia.",
        """
        CONSTRUCT { ?lote ing:advertencia "Aumentar el tiempo de lavado incrementa la cantidad de mieles."@es . }
        WHERE { ?lote ing:recomiendaAccion ing:AumentarTiempoLavado . }
        """,
    ),
    crear_regla(
        "R31_AjustarZaranda",
        40,
        "Sedimentos fuera: ordenar ajustar la zaranda.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AjustarZaranda . }
        WHERE { ?lote ing:sedimentosFuera true . }
        """,
    ),
    # ---------------------------------------------------------
    # E. SEGUIMIENTO
    # ---------------------------------------------------------
    crear_regla(
        "R26_ProgramarSeguimiento",
        60,
        "Tras órdenes correctivas: verificar en 2-3 horas y muestrear cada 15 minutos.",
        """
        CONSTRUCT {
          ?lote ing:seguimientoProgramado true ;
                ing:recomiendaAccion ing:VerificarEfecto, ing:MuestrearMaestroCada15Min .
          ?lote ing:plazoVerificacion "2 a 3 horas (hasta 3 muestras horarias)"@es .
        }
        WHERE {
          ?lote ing:recomiendaAccion ?accion .
          VALUES ?accion {
            ing:EnfriarTacho ing:DescargarTachoUrgente ing:AumentarSemilla ing:DisminuirSemilla
            ing:RecuperarVacio ing:ConcentrarJugoEvaporacion
            ing:SepararMasaParaReproceso ing:PararTacho ing:LimpiarTacho
            ing:AjustarZaranda ing:AvisarMaestrosAzucareros
            ing:AumentarTiempoLavado ing:ReducirTiempoLavado
          }
        }
        """,
    ),
    crear_regla(
        "R27_CorreccionSinEfecto",
        65,
        "Tras 3 horas de una corrección indicada, el parámetro asociado sigue fuera.",
        """
        CONSTRUCT { ?lote ing:correccionSinEfecto true . }
        WHERE {
          ?lote ing:horasDesdeCorreccion ?horas .
          FILTER(xsd:decimal(?horas) >= 3)
          FILTER NOT EXISTS { ?lote ing:dosMuestrasHorariasDentroFicha true . }
          {
            ?lote ing:accionAplicada ing:EnfriarTacho ; ing:tempExcedida true .
          } UNION {
            ?lote ing:accionAplicada ing:AumentarSemilla ; ing:granulometriaFuera true .
          } UNION {
            ?lote ing:accionAplicada ing:DisminuirSemilla ; ing:granulometriaFuera true .
          } UNION {
            ?lote ing:accionAplicada ing:AumentarTiempoLavado ; ing:colorFuera true .
          } UNION {
            ?lote ing:accionAplicada ing:ReducirTiempoLavado ; ing:colorFuera true .
          }
        }
        """,
    ),
    crear_regla(
        "R56_CorreccionLograda",
        65,
        "Dos muestras horarias seguidas dentro de ficha tras una corrección: volver al muestreo normal.",
        """
        CONSTRUCT {
          ?lote ing:correccionLograda true ;
                ing:recomiendaAccion ing:VolverMuestreoNormal .
        }
        WHERE {
          ?lote ing:accionAplicada ?accion ; ing:dosMuestrasHorariasDentroFicha true .
          VALUES ?accion {
            ing:EnfriarTacho ing:AumentarSemilla ing:DisminuirSemilla
            ing:AumentarTiempoLavado ing:ReducirTiempoLavado
          }
        }
        """,
    ),
    # ---------------------------------------------------------
    # F. DESTINO DEL LOTE RECHAZADO
    # ---------------------------------------------------------
    crear_regla(
        "R44_LicuarYReingresar",
        50,
        "Lote en depósito: licuar azúcar, convertir en miel y reingresar.",
        """
        CONSTRUCT {
          ?lote ing:azucarLicuar true ; ing:mielReingresada true ;
                ing:recomiendaAccion ing:LicuarAzucarYReingresar .
        }
        WHERE { ?lote ing:loteEnDeposito true . }
        """,
    ),
    crear_regla(
        "R45_OpcionesDestinoMiel",
        51,
        "Miel reingresada: mostrar tres opciones; decide el jefe de turno.",
        """
        CONSTRUCT {
          ?lote ing:opcionDestinoMiel ing:OpcionTanqueJugoEncalado,
                                     ing:OpcionMielSegunda,
                                     ing:OpcionDiluirOtroSector .
          ?lote ing:recomiendaAccion ing:DecisionJefeTurno .
        }
        WHERE { ?lote ing:mielReingresada true . }
        """,
    ),
    crear_regla(
        "R46_AjustesProcesoLoteDeposito",
        45,
        "Lote en depósito: ajustar lavado, centrifugado, zarandeado, cocimiento y monitorear.",
        """
        CONSTRUCT {
          ?lote ing:recomiendaAccion ing:AjustarLavado, ing:AjustarCentrifugado,
                ing:AjustarZarandeado, ing:AjustarCocimiento, ing:MonitorearHastaCumplir .
        }
        WHERE { ?lote ing:loteEnDeposito true . }
        """,
    ),
    # ---------------------------------------------------------
    # G. REGLAS DE CONTEXTO
    # ---------------------------------------------------------
    crear_regla(
        "R28_ReemplazoMaestro",
        15,
        "Falta maestro de primera y no hay reemplazo de otro turno.",
        """
        CONSTRUCT {
          ?lote ing:recomiendaAccion ing:MaestroSegundaPasaPrimera, ing:RespetarGranoYTemperatura .
          ?lote ing:prioridadControl "Temperatura"@es .
        }
        WHERE { ?lote ing:faltaMaestroPrimera true ; ing:reemplazoTurno false . }
        """,
    ),
    crear_regla(
        "R29_AlertaColorAntesLaboratorio",
        15,
        "Tachero observa color oscuro antes del laboratorio: revisar primero temperatura y Brix.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:RevisarTemperaturaYBrix . }
        WHERE { ?lote ing:tacheroNotaColorOscuroAntesLaboratorio true . }
        """,
    ),
    crear_regla(
        "R30_CriterioSiembra",
        15,
        "Al sembrar: cantidad constante entre 100-150 y Brix parejo.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:SembrarCantidadEstandar . }
        WHERE { ?lote ing:seVaASembrar true . }
        """,
    ),
    crear_regla(
        "R35_NoRetamizarProcesoContinuo",
        15,
        "Granulometría fuera detectada en zaranda y proceso continuo: no retamizar durante proceso.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:NoRetamizarDuranteProceso . }
        WHERE { ?lote ing:granulometriaFuera true ; ing:detectadoEnZaranda true ; ing:procesoContinuo true . }
        """,
    ),
    crear_regla(
        "R36_RetamizarLoteTerminado",
        15,
        "Lote terminado y granulometría fuera: se puede retamizar.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:RetamizarLoteTerminado . }
        WHERE { ?lote ing:loteTerminado true ; ing:granulometriaFuera true . }
        """,
    ),
    crear_regla(
        "R41_TerronesSecador",
        15,
        "Azúcar con terrones (humedad baja): avisar y registrar observación.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AvisarTerronesSecador . }
        WHERE { ?lote ing:secadorTerroneado true . }
        """,
    ),
    crear_regla(
        "R42_AzucarHumedaSecador",
        15,
        "Azúcar húmeda que escurre miel: avisar y registrar observación.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:AvisarAzucarHumedaSecador . }
        WHERE { ?lote ing:secadorAzucarHumeda true . }
        """,
    ),
    crear_regla(
        "R47_TratamientoOrganica",
        15,
        "Azúcar orgánica: usar solo cal, sin azufre ni floculantes.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:UsarSoloCal . }
        WHERE { ?lote ing:tipoAzucar ing:Organica . }
        """,
    ),
    crear_regla(
        "R48_TratamientoCTA",
        15,
        "CTA: usar azufre, cal y floculantes en DOR y buen tiempo de lavado.",
        """
        CONSTRUCT { ?lote ing:recomiendaAccion ing:UsarAditivosDOR . }
        WHERE { ?lote ing:tipoAzucar ing:CTA . }
        """,
    ),
]


def crear_caso_vacio(id_lote: str = "Lote_001", tipo_azucar: str = "CTA") -> dict[str, Any]:
    """Devuelve una estructura DATOS_CASO limpia lista para poblar."""
    return {
        "id_lote": id_lote,
        "tipo_azucar": tipo_azucar,
        "ficha_cliente": {"color_max_ui": None},
        "mediciones": {clave: None for clave in PROPIEDADES_MEDICION},
        "eventos": {clave: False for clave in PROPIEDADES_EVENTO},
        "acciones_aplicadas": [],
        "seguimiento": {
            "horas_desde_correccion": 0,
            "dos_muestras_horarias_dentro_ficha": False,
        },
    }


def format_valor(valor: Any) -> str:
    """Convierte URI y literales RDF a texto legible."""
    if isinstance(valor, Literal):
        return f'"{str(valor)}"'
    texto = str(valor)
    return texto.split("#")[-1] if "#" in texto else texto.rstrip("/").split("/")[-1]


def validar_entrada(datos: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Valida si están los datos mínimos para evaluar la ficha y retorna (faltantes, notas)."""
    tipo = datos.get("tipo_azucar", "CTA")
    mediciones = datos.get("mediciones", {})
    requeridos = ["color_ui", "granulometria_mm", "pol_pct", "sedimentos_mg_kg"]
    if tipo == "CTA":
        requeridos.append("retenido_malla25_pct")

    faltantes = [x for x in requeridos if mediciones.get(x) is None]
    notas: list[str] = []

    if faltantes:
        notas.append(
            "Faltan mediciones analíticas para dictaminar Aprobado/No Conforme (R11/R12): "
            + ", ".join(faltantes)
            + "."
        )
    elif tipo == "Organica":
        notas.append(
            "El documento no define una ficha numérica para Azúcar Orgánica; se aplica R47 sin inventar dictamen numérico."
        )
    else:
        notas.append("Datos mínimos de ficha técnica presentes para evaluar conformidad.")

    brix = mediciones.get("brix_entrada_tacho")
    if brix is not None:
        val_brix = float(brix)
        if val_brix <= 55 or val_brix >= 65:
            notas.append(
                f"Brix de entrada en nivel crítico explicativo ({val_brix} °Bx; umbral S3 <= 55 o >= 65)."
            )

    return faltantes, notas


def crear_grafo_caso(datos: dict[str, Any]) -> tuple[Graph, URIRef]:
    """Crea un grafo RDF nuevo, copia el esquema y carga los hechos del caso."""
    grafo = Graph()
    for triple in G_ESQUEMA:
        grafo.add(triple)
    for prefijo, namespace in [
        ("ing", ing),
        ("rdf", RDF),
        ("rdfs", RDFS),
        ("owl", OWL),
        ("xsd", XSD),
    ]:
        grafo.bind(prefijo, namespace)

    id_lote = datos.get("id_lote") or "Lote_001"
    lote = ing[id_lote]
    tipo = datos.get("tipo_azucar", "CTA")
    tipos_validos = {"CTA": ing.CTA, "Crudo": ing.Crudo, "Organica": ing.Organica}
    if tipo not in tipos_validos:
        raise ValueError("tipo_azucar debe ser CTA, Crudo u Organica")

    grafo.add((lote, RDF.type, ing.Lote))
    grafo.add((lote, RDFS.label, Literal(id_lote, lang="es")))
    grafo.add((lote, ing.tipoAzucar, tipos_validos[tipo]))

    limite_color = datos.get("ficha_cliente", {}).get("color_max_ui")
    if limite_color is None:
        limite_color = 150 if tipo == "CTA" else (400 if tipo == "Crudo" else None)
    if limite_color is not None:
        grafo.add((lote, ing.colorMaxFichaUI, Literal(Decimal(str(limite_color)), datatype=XSD.decimal)))

    for clave, valor in datos.get("mediciones", {}).items():
        if valor is not None and clave in PROPIEDADES_MEDICION:
            grafo.add(
                (lote, PROPIEDADES_MEDICION[clave], Literal(Decimal(str(valor)), datatype=XSD.decimal))
            )

    for clave, propiedad in PROPIEDADES_EVENTO.items():
        valor = bool(datos.get("eventos", {}).get(clave, False))
        grafo.add((lote, propiedad, Literal(valor, datatype=XSD.boolean)))

    seguimiento = datos.get("seguimiento", {})
    horas = seguimiento.get("horas_desde_correccion", 0)
    grafo.add((lote, ing.horasDesdeCorreccion, Literal(Decimal(str(horas)), datatype=XSD.decimal)))
    dos_muestras = bool(seguimiento.get("dos_muestras_horarias_dentro_ficha", False))
    grafo.add((lote, ing.dosMuestrasHorariasDentroFicha, Literal(dos_muestras, datatype=XSD.boolean)))

    for nombre_accion in datos.get("acciones_aplicadas", []):
        if nombre_accion not in ACCIONES:
            raise ValueError(f"Acción aplicada desconocida: {nombre_accion}")
        grafo.add((lote, ing.accionAplicada, ing[nombre_accion]))

    return grafo, lote


def motor_inferencia(
    grafo: Graph, reglas: list[dict[str, Any]] | None = None, max_ciclos: int = 300
) -> tuple[list[tuple[Any, Any, Any, str]], list[dict[str, Any]]]:
    """Ejecuta encadenamiento hacia adelante con resolución de conflictos por prioridad."""
    if reglas is None:
        reglas = base_de_reglas

    historial = [(s, p, o, "Inicial") for (s, p, o) in grafo]
    activaciones: list[dict[str, Any]] = []
    ciclo = 1

    while ciclo <= max_ciclos:
        conjunto_conflicto = []
        for regla in reglas:
            resultado = grafo.query(regla["query"])
            subgrafo = resultado.graph
            nuevas = [t for t in subgrafo if t not in grafo]
            if nuevas:
                conjunto_conflicto.append({"regla": regla, "tripletas": nuevas})

        if not conjunto_conflicto:
            break

        ganadora = max(conjunto_conflicto, key=lambda x: x["regla"]["prioridad"])
        regla = ganadora["regla"]

        tripletas_fmt = []
        hechos_agregados = 0
        for sujeto, predicado, objeto in ganadora["tripletas"]:
            if (sujeto, predicado, objeto) not in grafo:
                grafo.add((sujeto, predicado, objeto))
                historial.append((sujeto, predicado, objeto, regla["id"]))
                hechos_agregados += 1
                tripletas_fmt.append(
                    f"{format_valor(sujeto)} | {format_valor(predicado)} | {format_valor(objeto)}"
                )

        activaciones.append(
            {
                "ciclo": ciclo,
                "regla": regla["id"],
                "prioridad": regla["prioridad"],
                "descripcion": regla["descripcion"],
                "hechos_nuevos": hechos_agregados,
                "tripletas": tripletas_fmt,
            }
        )
        ciclo += 1

    return historial, activaciones


def evaluar_caso(datos: dict[str, Any]) -> dict[str, Any]:
    """Evalúa un diccionario DATOS_CASO completo y devuelve resultados estructurados."""
    datos_copia = deepcopy(datos)
    faltantes, notas_validacion = validar_entrada(datos_copia)
    grafo, lote = crear_grafo_caso(datos_copia)
    historial, activaciones = motor_inferencia(grafo, base_de_reglas)

    estados = [format_valor(x) for x in grafo.objects(lote, ing.estadoLote)]

    indicadores_map = [
        (ing.vacioBajo, "Vacío bajo (< 60 cmHg)"),
        (ing.tempEbullicionAlta, "Temperatura de ebullición alta"),
        (ing.tempAlerta, "Temperatura en alerta preventiva (70–85 °C)"),
        (ing.tempExcedida, "Temperatura excedida (> 85 °C o por vacío bajo)"),
        (ing.azucarQuemado, "Azúcar quemado"),
        (ing.colorOscuro, "Color oscuro inferido"),
        (ing.brixBajo, "Brix de entrada bajo (< 60 °Bx)"),
        (ing.brixAlto, "Brix de entrada alto (> 63 °Bx)"),
        (ing.brixNormal, "Brix de entrada normal (60–63 °Bx)"),
        (ing.semillaPoca, "Semilla poca (< 100)"),
        (ing.semillaMucha, "Semilla mucha (> 150)"),
        (ing.granoGrande, "Grano grande"),
        (ing.granoChico, "Grano chico"),
        (ing.purezaBaja, "Pureza baja por Brix"),
        (ing.colorFuera, "Color fuera de ficha"),
        (ing.granulometriaFuera, "Granulometría fuera de ficha"),
        (ing.purezaFuera, "Pol/pureza fuera de ficha"),
        (ing.sedimentosFuera, "Sedimentos fuera de ficha (> 30 mg/kg)"),
        (ing.correccionSinEfecto, "Corrección sin efecto tras 3 horas"),
        (ing.correccionLograda, "Corrección lograda (2 muestras OK)"),
        (ing.seguimientoProgramado, "Seguimiento programado (2-3 h)"),
        (ing.mielReingresada, "Miel disuelta reingresada al circuito"),
    ]
    indicadores_detectados = [
        nombre
        for prop, nombre in indicadores_map
        if (lote, prop, Literal(True, datatype=XSD.boolean)) in grafo
    ]

    diagnosticos: list[dict[str, str]] = []
    for pred, tipo_causa in [
        (ing.causaColor, "Causa de Color"),
        (ing.causaRaiz, "Causa Raíz"),
        (ing.causaTecnica, "Causa Técnica"),
    ]:
        for causa_uri in grafo.objects(lote, pred):
            cid = format_valor(causa_uri)
            nombre_legible, exp_legible = CAUSAS_DESCRIPCION.get(cid, (cid, ""))
            diagnosticos.append(
                {
                    "tipo": tipo_causa,
                    "id": cid,
                    "nombre": nombre_legible,
                    "explicacion": exp_legible,
                }
            )

    # Mapa de origen de acciones recomendadas desde historial
    origen_acciones: dict[str, list[str]] = {}
    for s, p, o, origen in historial:
        if s == lote and p == ing.recomiendaAccion:
            aid = format_valor(o)
            origen_acciones.setdefault(aid, [])
            if origen not in origen_acciones[aid]:
                origen_acciones[aid].append(origen)

    acciones_uris = sorted(set(grafo.objects(lote, ing.recomiendaAccion)), key=format_valor)
    acciones_recomendadas: list[dict[str, str]] = []
    for accion_uri in acciones_uris:
        aid = format_valor(accion_uri)
        etiqueta = grafo.value(accion_uri, RDFS.label)
        desc = str(etiqueta) if etiqueta else ACCIONES.get(aid, aid)
        reglas_ori = ", ".join(origen_acciones.get(aid, []))
        acciones_recomendadas.append(
            {
                "id": aid,
                "descripcion": desc,
                "regla_origen": reglas_ori,
            }
        )

    opciones_destino_miel: list[str] = []
    for opcion_uri in sorted(set(grafo.objects(lote, ing.opcionDestinoMiel)), key=format_valor):
        etiqueta = grafo.value(opcion_uri, RDFS.label)
        opciones_destino_miel.append(str(etiqueta) if etiqueta else format_valor(opcion_uri))

    advertencias = [str(a) for a in grafo.objects(lote, ing.advertencia)]
    plazos = [str(p) for p in grafo.objects(lote, ing.plazoVerificacion)]

    historial_bh = [
        {
            "sujeto": format_valor(s),
            "predicado": format_valor(p),
            "objeto": format_valor(o),
            "origen": origen,
        }
        for s, p, o, origen in historial
    ]

    return {
        "datos_entrada": datos_copia,
        "faltantes": faltantes,
        "notas_validacion": notas_validacion,
        "estado_lote": estados,
        "indicadores_detectados": indicadores_detectados,
        "diagnosticos": diagnosticos,
        "acciones_recomendadas": acciones_recomendadas,
        "opciones_destino_miel": opciones_destino_miel,
        "advertencias": advertencias,
        "plazos": plazos,
        "activaciones": activaciones,
        "historial_bh": historial_bh,
        "grafo": grafo,
        "lote_uri": lote,
    }


def exportar_grafo_pyvis(
    grafo: Graph, lote_uri: URIRef, ruta_salida: str | Path = "grafo_ingenio.html"
) -> str:
    """Genera un archivo HTML interactivo con PyVis para inspeccionar el grafo RDF del caso."""
    net = Network(height="750px", width="100%", directed=True, notebook=False, cdn_resources="in_line")
    net.barnes_hut(gravity=-3500, central_gravity=0.25, spring_length=180)

    acciones_del_lote = set(grafo.objects(lote_uri, ing.recomiendaAccion))
    opciones_del_lote = set(grafo.objects(lote_uri, ing.opcionDestinoMiel))
    recursos_con_etiqueta = acciones_del_lote | opciones_del_lote

    triples_visibles = [
        t
        for t in grafo
        if t[0] == lote_uri or (t[0] in recursos_con_etiqueta and t[1] == RDFS.label)
    ]

    nodos = set()
    for s, p, o in triples_visibles:
        if p == RDFS.label:
            continue
        nodos.add(s)
        nodos.add(o)

    for nodo in nodos:
        etiqueta = grafo.value(nodo, RDFS.label)
        label = str(etiqueta) if etiqueta else format_valor(nodo)
        if isinstance(nodo, Literal):
            net.add_node(
                str(nodo),
                label=label,
                shape="box",
                color="#FFF2CC",
                title=f"Literal: {nodo.datatype}",
            )
        elif nodo == lote_uri:
            net.add_node(
                str(nodo),
                label=label,
                shape="ellipse",
                color="#A7C7E7",
                title="Lote evaluado",
            )
        elif (nodo, RDF.type, ing.Accion) in grafo:
            net.add_node(
                str(nodo),
                label=label[:45],
                shape="box",
                color="#C8E6C9",
                title=label,
            )
        else:
            net.add_node(
                str(nodo),
                label=label,
                shape="dot",
                color="#E0E0E0",
                title=str(nodo),
            )

    for s, p, o in triples_visibles:
        if p == RDFS.label:
            continue
        net.add_edge(str(s), str(o), label=format_valor(p), arrows="to")

    net.show_buttons(filter_=["physics"])
    html_grafo = net.generate_html(notebook=False)

    ruta = Path(ruta_salida).resolve()
    ruta.write_text(html_grafo, encoding="utf-8")
    return str(ruta)
