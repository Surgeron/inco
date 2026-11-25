# Base de Conocimiento Definitiva: SBC Control de Calidad de Azúcar
**Ingenio La Esperanza - Grupo 10 INCo (4to Año)**

Documento oficial de la base de conocimiento cerrada con **12 supuestos de diseño conservadores (S1 a S12)** y **56 reglas de producción (R1 a R56)**.

---

## 1. Supuestos Adoptados (Criterio Conservador)

Ante la duda, se adoptó siempre el límite más estricto y la acción menos invasiva antes que una orden correctiva fuerte:

* **[S1] Temperatura**: 
  * Normal: hasta 70 °C. (El rango de 50 a 60 °C mencionado previamente queda contenido dentro del rango normal).
  * Alerta preventiva (`temp_alerta`): entre 70 y 85 °C.
  * Excedida crítica (`temp_excedida`): superior a 85 °C.
* **[S2] Vacío**:
  * Unidad: cm de mercurio (cmHg). (60 mmHg representaría prácticamente ausencia de vacío).
  * Vacío normal: 60 a 62 cmHg.
  * Vacío bajo (`vacio_bajo`): menor a 60 cmHg.
* **[S3] Brix al tacho**:
  * Normal: 60 a 63 °Bx.
  * Bajo (`brix_bajo`): menor a 60 °Bx.
  * Alto (`brix_alto`): mayor a 63 °Bx.
  * *Nota*: Los valores 55 y 65 °Bx se reservan como niveles críticos para la justificación explicativa, evitando zonas muertas sin clasificar.
* **[S4] Semilla**:
  * Poca (`semilla_poca`): menos de 100 por tacho.
  * Normal: 100 a 150 por tacho.
  * Mucha (`semilla_mucha`): más de 150 por tacho.
  * *Nota*: La unidad física no altera la lógica algorítmica al compararse estrictamente contra dichos umbrales.
* **[S5] Color**:
  * Se adopta el límite más estricto por defecto: $\le 150$ UI en CTA y $\le 400$ UI en crudo (salvo que la ficha del cliente solicite explícitamente 200 o 600 UI). Cumpliendo el estándar más estricto, se satisfacen ambos.
  * El síntoma "color demasiado claro" se ingresa por inspección cualitativa/observación.
* **[S6] Pol**:
  * CTA: mínimo 99.6 °Z (se asume 9.6 como error tipográfico en la transcripción).
  * Crudo: mínimo 98.4 °Z.
* **[S7] Sedimentos**:
  * Límite máximo: 30 mg/kg (una unidad de 30 % carece de sustento físico en azúcar comercial).
* **[S8] Granulometría del azúcar crudo**:
  * Rango de tamaño aceptable: 0.60 a 0.65 mm (por analogía al intervalo de 0.50 a 0.55 mm del CTA).
* **[S9] Tipología de productos**:
  * CTA y Crudo tienen umbrales analíticos diferenciados. El azúcar crudo se clasifica de forma independiente del azúcar orgánico.
  * Tratamiento químico: solo se formalizan reglas para Orgánica (**R47**) y CTA (**R48**).
* **[S10] Ventanas temporales de seguimiento**:
  * Ventana de evaluación: hasta 3 horas (3 muestras horarias sucesivas) antes de dictaminar inefectividad de una orden correctiva.
  * Corrección lograda: exige 2 muestras horarias consecutivas dentro de los parámetros de la ficha.
  * *Nota*: Las referencias a "días" corresponden a cambios de estándar/zafra y se excluyen del ciclo de control en línea.
* **[S11] Magnitudes cualitativas / supervisadas**:
  * Variables sin cuantificación fija (tiempo de lavado en centrífuga, humedad de secadores, duración de parada y masa purgada) son orientadas por el SBC en sentido direccional, delegando la magnitud al criterio del Jefe de Turno.
  * Humedad se categoriza como: *seca*, *con terrones* o *húmeda*.
* **[S12] Brix de 33 a 37 °Bx**:
  * Corresponde a una fase previa de evaporación ajena a la entrada inmediata del tacho; queda desacoplada de la base de reglas activas.

---

## 2. Base de Conocimiento (56 Reglas de Producción)

### A. Mecanismo del tacho
* **R1**: SI vacío $< 60$ cmHg (`vacio_bajo`) [S2] $\rightarrow$ ENTONCES `temp_ebullicion_alta`.
* **R2**: SI `temp_ebullicion_alta` O temperatura del tacho $> 85$ °C [S1] $\rightarrow$ ENTONCES `temp_excedida`.
* **R55**: SI temperatura del tacho entre 70 y 85 °C [S1] $\rightarrow$ ENTONCES `temp_alerta`: notificar al tachero y verificar vacío, sin accionar enfriamiento forzado.
* **R3**: SI `temp_excedida` $\rightarrow$ ENTONCES `azucar_quemado`.
* **R4**: SI `azucar_quemado` $\rightarrow$ ENTONCES `color_oscuro`.
* **R5**: SI `brix_alto` ($> 63$) [S3] Y `semilla_poca` ($< 100$) [S4] $\rightarrow$ ENTONCES `grano_grande`.
* **R6**: SI `brix_bajo` ($< 60$) [S3] O `semilla_mucha` ($> 150$) [S4] $\rightarrow$ ENTONCES `grano_chico`.
* **R7**: SI `grano_grande` (CTA $> 0.55$ mm, crudo $> 0.65$ mm) O `grano_chico` (CTA $< 0.50$ mm, crudo $< 0.60$ mm) [S8] $\rightarrow$ ENTONCES `granulometria_fuera`.
* **R8**: SI `brix_bajo` $\rightarrow$ ENTONCES `pureza_baja`. *(confirmar)*
* **R9**: SI `pureza_baja` $\rightarrow$ ENTONCES `granulometria_fuera`.
* **R10**: SI el tachero detecta grano grande táctil o visualmente en el toma-muestras $\rightarrow$ ENTONCES `grano_grande`.
* **R52**: SI Brix del jugo de entrada $< 60$ $\rightarrow$ ENTONCES `brix_bajo`. SI $> 63$ $\rightarrow$ ENTONCES `brix_alto`. (Normal: 60 a 63; niveles críticos: $\le 55$ y $\ge 65$) [S3].
* **R53**: SI Brix de masa cocida alcanza 92 °Bx $\rightarrow$ ENTONCES `descargar_tacho`.
* **R54**: SI tacho en cocción $\rightarrow$ ENTONCES maestro azucarero realiza toma de muestra cada 15 minutos.

### B. Muestreo y dictamen
* **R49**: SI transcurrió 1 hora (primera muestra a los 10–15 min de iniciado el turno) $\rightarrow$ ENTONCES laboratorio extrae muestra analítica.
* **R50**: SI jefe de turno advierte desvío de color a simple vista $\rightarrow$ ENTONCES comunica a laboratorio y se activan muestras instantáneas (hasta 2 o 3 por hora).
* **R51**: SI se realiza descarga de tacho a centrífugas $\rightarrow$ ENTONCES laboratorio extrae muestra para determinación de sedimentos.
* **R11**: SI los 4 parámetros analíticos satisfacen la ficha técnica [S5, S6, S7, S8] $\rightarrow$ ENTONCES `lote_aprobado`.
  * *Color*: $\le 150$ UI (CTA) / $\le 400$ UI (crudo).
  * *Granulometría*: 0.50–0.55 mm con retenido malla 25 $\le 20\%$ (CTA) / 0.60–0.65 mm (crudo).
  * *Pol*: $\ge 99.6$ °Z (CTA) / $\ge 98.4$ °Z (crudo).
  * *Sedimentos*: $\le 30$ mg/kg.
* **R12**: SI al menos un parámetro transgrede la ficha $\rightarrow$ ENTONCES `lote_no_conforme` y se habilita la fase diagnóstica.
* **R43**: SI `lote_no_conforme` $\rightarrow$ ENTONCES laboratorio formaliza rechazo de lote con derivación a depósito de retención.

### C. Diagnóstico
* **R13**: SI `lote_no_conforme` Y `color_fuera` Y `temp_excedida` $\rightarrow$ ENTONCES `causa_color = quemado_por_temperatura`.
* **R14**: SI `causa_color = quemado_por_temperatura` Y `vacio_bajo` $\rightarrow$ ENTONCES `causa_raiz = perdida_de_vacio`. *(confirmar)*
* **R37**: SI `lote_no_conforme` Y `color_fuera` Y temperatura normal ($\le 70$ °C) $\rightarrow$ ENTONCES `causa_color = lavado_centrifuga` y se somete a revisión el ciclo de lavado.
* **R15**: SI `lote_no_conforme` Y `granulometria_fuera` Y `grano_grande` Y `brix_alto` Y `semilla_poca` $\rightarrow$ ENTONCES `causa = semilla_insuficiente`.
* **R16**: SI `lote_no_conforme` Y `granulometria_fuera` Y `grano_chico` Y `semilla_mucha` $\rightarrow$ ENTONCES `causa = exceso_de_semilla`.
* **R34**: SI `grano_chico` Y `brix_bajo` $\rightarrow$ ENTONCES `causa = concentracion_baja_en_tacho`. *(confirmar)*
* **R17**: SI `brix_bajo` Y (`color_fuera` O `granulometria_fuera`) $\rightarrow$ ENTONCES `causa = jugo_de_entrada_pobre`. *(confirmar)*
* **R32**: SI `sedimentos_fuera` ($> 30$ mg/kg) $\rightarrow$ ENTONCES auditar tachos de cocimiento y zaranda vibratoria.
* **R18**: SI (`color_fuera` O `granulometria_fuera`) Y `correccion_sin_efecto` $\rightarrow$ ENTONCES `causa = tacho_sucio`.

### D. Órdenes correctivas
* **R19**: SI `temp_excedida` $\rightarrow$ ENTONCES prescribir enfriamiento del tacho hasta restablecer 60 a 70 °C.
* **R20**: SI `grano_grande` $\rightarrow$ ENTONCES ordenar descarga inmediata del tacho sin aguardar los 92 °Bx.
* **R21**: SI `causa = semilla_insuficiente` $\rightarrow$ ENTONCES incrementar dosificación de semilla dentro del rango 100 a 150.
* **R22**: SI `causa = exceso_de_semilla` $\rightarrow$ ENTONCES decrementar dosificación de semilla dentro del rango 100 a 150.
* **R23**: SI `causa_raiz = perdida_de_vacio` $\rightarrow$ ENTONCES ordenar restitución de vacío al intervalo 60 a 62 cmHg.
* **R24**: SI `causa = jugo_de_entrada_pobre` O `causa = concentracion_baja_en_tacho` $\rightarrow$ ENTONCES instruir a evaporación incrementar evaporación para ingresar masa con Brix 60 a 63 °Bx.
* **R25**: SI `causa = tacho_sucio` $\rightarrow$ ENTONCES desviar masa para reproceso, detener tacho e iniciar limpieza física (parámetros regulados por Jefe de Turno [S11]).
* **R33**: SI `grano_chico` $\rightarrow$ ENTONCES emitir advertencia a maestros azucareros.
* **R38**: SI `color_oscuro` Y `causa_color = lavado_centrifuga` $\rightarrow$ ENTONCES extender gradualmente tiempo de lavado en centrífugas [S11].
* **R39**: SI color excesivamente claro (inspección) Y `causa_color = lavado_centrifuga` $\rightarrow$ ENTONCES reducir tiempo de lavado en centrífugas [S11].
* **R40**: SI se incrementa tiempo de lavado en centrífuga $\rightarrow$ ENTONCES emitir notificación de incremento colateral en volumen de mieles.
* **R31**: SI `sedimentos_fuera` $\rightarrow$ ENTONCES disponer regulación y calibración de zaranda.

### E. Seguimiento y ciclo de control
* **R26**: SI se despachó orden correctiva (R19–R25, R31, R33, R38, R39) $\rightarrow$ ENTONCES mantener monitoreo de verificación durante 3 muestras horarias sucesivas [S10] y control táctil cada 15 min.
* **R27**: SI tras aplicar corrección y cumplir 3 horas persiste el apartamiento de ficha [S10] $\rightarrow$ ENTONCES dictaminar `correccion_sin_efecto`.
* **R56**: SI tras una corrección se registran 2 muestras horarias consecutivas conformes a la ficha [S10] $\rightarrow$ ENTONCES dictaminar `correccion_lograda` y retornar a régimen ordinario de muestreo.

### F. Destino del lote rechazado
* **R44**: SI lote transferido a depósito de rechazo $\rightarrow$ ENTONCES proceder a disolución de azúcar a miel para reinyección al circuito productivo.
* **R45**: SI se produce reinyección de miel disuelta $\rightarrow$ ENTONCES presentar al Jefe de Turno alternativas de destino: tanque de jugo encalado, miel de segunda o dilución sectorial.
* **R46**: SI lote en depósito $\rightarrow$ ENTONCES recalibrar lavado, centrifugación, zaranda y cocimiento hasta estabilizar producción.

### G. Reglas de contexto y contingencias operativas
* **R28**: SI ausente maestro de primera y no media relevo de turno $\rightarrow$ ENTONCES promover temporalmente a maestro de segunda con directiva estricta sobre temperatura y calibre de grano.
* **R29**: SI tachero identifica color oscuro previo a reporte de laboratorio $\rightarrow$ ENTONCES verificar inmediatamente temperatura de tacho y Brix de alimentación.
* **R30**: SI se procede al sembrado $\rightarrow$ ENTONCES conservar dosificación uniforme (100 a 150) y perfil constante de Brix.
* **R35**: SI se evidencia `granulometria_fuera` en zaranda bajo marcha continua $\rightarrow$ ENTONCES prohibir retamizado en línea.
* **R36**: SI lote culmina producción con `granulometria_fuera` $\rightarrow$ ENTONCES autorizar retamizado en lote cerrado.
* **R41**: SI secadores exhiben formación de terrones (`humedad_baja`) $\rightarrow$ ENTONCES asentar registro preventivo [S11].
* **R42**: SI secadores exhiben exudación de miel (`humedad_alta`) $\rightarrow$ ENTONCES emitir alarma por riesgo de comercialización [S11].
* **R47**: SI `tipo = orgánica` $\rightarrow$ ENTONCES formular con lechada de cal exclusiva, suprimiendo azufre y floculantes.
* **R48**: SI `tipo = A (CTA)` $\rightarrow$ ENTONCES aplicar azufre, cal y floculantes en sistema DOR, optimizando ciclo de lavado en centrífuga.

---

## 3. Caminos de Inferencia Cerrados

1. **Entrada común**: R54 (tacho) + R49, R50, R51 (laboratorio) $\rightarrow$ R11 (aprobado $\rightarrow$ fin) o R12 (no conforme $\rightarrow$ activa diagnóstico).
2. **Color por temperatura**: R55 (alerta preventiva) $\rightarrow$ R1 $\rightarrow$ R2 $\rightarrow$ R3 $\rightarrow$ R4 $\rightarrow$ R12 $\rightarrow$ R13 $\rightarrow$ R14 $\rightarrow$ R23 (y R19 en paralelo) $\rightarrow$ R26.
3. **Color por lavado**: R12 $\rightarrow$ R37 $\rightarrow$ R38 (o R39) $\rightarrow$ R40 (advertencia) $\rightarrow$ R26.
4. **Grano grande**: R52 $\rightarrow$ R5 $\rightarrow$ R7 $\rightarrow$ R12 $\rightarrow$ R15 $\rightarrow$ R21 $\rightarrow$ R26. (R20 en paralelo; R10 anticipa).
5. **Grano chico**: R6 $\rightarrow$ R7 $\rightarrow$ R12 $\rightarrow$ R16 $\rightarrow$ R22 $\rightarrow$ R26 (R33 en paralelo). *Por Brix bajo*: R52 $\rightarrow$ R12 $\rightarrow$ R34 $\rightarrow$ R24 $\rightarrow$ R26.
6. **Jugo pobre y pureza**: R52 $\rightarrow$ R8 $\rightarrow$ R9 $\rightarrow$ R17 $\rightarrow$ R24 $\rightarrow$ R26.
7. **Sedimentos**: R51 $\rightarrow$ R12 $\rightarrow$ R32 $\rightarrow$ R31 $\rightarrow$ R26.
8. **Descarga normal**: R54 $\rightarrow$ R53 a 92 °Bx. (R20 anticipa si hay grano grande).
9. **Corrección lograda**: R26 $\rightarrow$ R56 $\rightarrow$ retorno a régimen normal R49.
10. **Corrección sin efecto**: R26 $\rightarrow$ R27 $\rightarrow$ R18 $\rightarrow$ R25 $\rightarrow$ R44 $\rightarrow$ R45 $\rightarrow$ reingreso a R49.
11. **Lote rechazado**: R43 $\rightarrow$ R44 $\rightarrow$ R45 (con R46 en paralelo) $\rightarrow$ reingreso a R49.
12. **Alertas tempranas anticipadas**: R10 (grano), R29 y R50 (color).
13. **Reglas de contexto**: R28, R30, R35, R36, R41, R42, R47, R48.
