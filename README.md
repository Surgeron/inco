# inco
cosas top secret
hola mundo("print")


## Interfaz Visual del SBC (Lenguaje Natural ↔ RDF/SPARQL)

Aplicación de escritorio en Python (`Tkinter`) que traduce consultas en lenguaje natural a la Base de Hechos del SBC del **Ingenio La Esperanza** (implementado con `rdflib` + reglas `SPARQL CONSTRUCT` en `SBC-IngenioLaEsperanza-Colab.ipynb`), ejecuta el motor de inferencia por prioridad y devuelve las conclusiones en lenguaje natural junto con la trazabilidad completa.

### Archivos principales
- `sbc_motor.py`: ontología RDF, 72 reglas `SPARQL CONSTRUCT` (13 auxiliares + 56 reglas oficiales `R1`–`R56`), motor de inferencia con resolución de conflictos por prioridad y exportador de grafo `PyVis`.
- `sbc_pln.py`: traductor híbrido Lenguaje Natural ↔ `DATOS_CASO` (motor PLN local 100% offline por defecto + conector opcional con Gemini API) y generador de respuestas explicativas.
- `app_sbc_gui.py`: interfaz gráfica en `Tkinter` con chat en lenguaje natural, casos de ejemplo, visualización de traducción LN → Hechos, traza por ciclos, tabla filtrable de Base de Hechos RDF, formulario manual sincronizado y botón para abrir el grafo interactivo `PyVis`.

### Cómo ejecutar
```bash
python app_sbc_gui.py
```
Opcionalmente, para activar el modo híbrido con Gemini API podés configurar tu clave desde el botón **Configurar API Key** dentro de la interfaz o mediante la variable de entorno `GEMINI_API_KEY`.
