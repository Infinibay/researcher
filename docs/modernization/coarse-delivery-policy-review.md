# Política de entrega en pasos gruesos: conectada, ensayo fallido

El catálogo **11** incorpora orientación de adquisición y entrega en pasos gruesos
al perfil de investigación. Las comprobaciones de integración pasan; **el nuevo
ensayo real volvió a agotar el presupuesto sin entregar una explicación**.
El resultado no acredita eficacia ni aceptación humana.

[Resultados](coarse-delivery-policy-results.json),
[registro previo](coarse-delivery-policy-evidence/registration.json),
[resultado original](coarse-delivery-policy-evidence/native-result.json),
[análisis del recorrido](coarse-delivery-policy-evidence/live-analysis.json).

## Cambio implementado

El modelo recibe orientación para agrupar lecturas independientes conocidas,
encadenar argumentos derivados de recibos y detenerse cuando haga falta nueva
interpretación. Después de inspeccionar evidencia suficiente, debe encadenar
hallazgos → resumen tipado → propuesta explícita usando IDs reales, comprobar
cada respuesta y reservar margen para explicar el resultado al usuario. Un error
o respuesta incierta detiene la cadena y conserva claves/recibos originales.
La programación no cambia permisos, citas, presupuestos o aceptación.

La política común y las otras seis capacidades conservan sus cuerpos; sus
cabeceras pasan a 11. `instruction_identity` sigue reconociendo versiones 2–10
con sus hashes originales. El consumidor `OwnedCodexRuntime.open` conserva su
código: compone y congela la instrucción antes del thread. Las 48 descripciones,
esquemas y anotaciones de negocio permanecen iguales.

La documentación oficial recomienda aplicar composición programática a etapas
con flujo predecible, argumentos documentados y fallos definidos; los resultados
que necesitan juicio deben volver al modelo. Aquí se aplica ese criterio al
code host local, cuya viabilidad se probó por separado. No demuestra que esta
política produzca mejores resultados en Researcher.
[OpenAI: Programmatic Tool Calling](https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling).

## Comprobaciones del código y del paquete

- Primero siete casos fallaron porque el contrato esperaba catálogo 11 y el
  runtime aún emitía 10. Después pasan **55 pruebas fuente**, sin omisiones,
  en 19,04 s: catálogo/procedencia, investigación, composición, presupuesto e input.
- Sdist y wheel construidos offline: **700 archivos Python/SQL coinciden**, 371
  de producto. Se excluye únicamente el seed de desarrollo declarado. El wheel
  incluye los docstrings anteriores y la política nueva.
- Instalación aislada, fuera del checkout: **55 pruebas pasan**, sin omisiones,
  en 20,53 s; 235 módulos backend se cargan sólo desde el paquete y sus fuentes
  coinciden. No es una suite global nueva.
- Inventario **85 candidatos/322 archivos vigente**. Doce deltas revisados:
  política de investigación e identidad cambian semánticamente; el resto conserva
  su AST/cuerpo y cambia fuente de módulo o consumidor/cabecera. Las otras 73
  decisiones no se renuevan. La medición de perfiles conserva el baseline original
  y sólo informa bytes/hashes.

El chequeo de espacios pasa salvo siete líneas del log RED bruto que genera
pytest. Se conserva ese archivo literal; no se modifica evidencia para limpiar
su formato.

## Qué ocurrió en la observación real

Se mantuvieron pregunta, código/documentación, criterios, modelo/esfuerzo y
límites del ensayo anterior; una sola admisión. El paquete incorpora también las
cuatro descripciones de argumentos de análisis ya revisadas. **No es una prueba
causal aislada ni un caso reservado**. La pregunta y el feedback son históricos;
no equivalen a una nueva corrección o comprensión del propietario.

Se comprobó la política 11 exacta registrada y la lectura Ken completa de las
118 líneas originales. El agente hizo cuatro `exec`: descubrimiento/listado,
lectura Ken más captura documental e inicio de `cat`, lectura de documentación
más salida del comando, y captura del comando. Esta última tuvo una finalidad
válida de procedencia: Ken no crea una fuente inmutable de investigación.

Los totales observados fueron **26 195 → 53 773 → 84 586 → 126 302**, frente al
límite de 120 000. El conteo incluye entradas cacheadas; no es una estimación de
facturación. El host retiró autoridad al observar el exceso de una ronda ya
consumida. Quedaron dos fuentes, **cero hallazgos, informes, propuestas o aceptación**,
y ninguna explicación final. Duración del ensayo: 38,842 s; cinco peers cerrados,
cero grants sin revocar, servicio cerrado. El fallo anterior se conserva.

## Siguiente acción fundamentada

El resultado refuta que esta orientación, por sí sola, haya resuelto la entrega.
La [revisión con contexto limpio](u08-delivery-proportionality-review.md) identifica
una adquisición todavía fragmentada. `command_read` volvió a imprimir la salida
como texto y base64: 20 562 caracteres en sus bloques de texto, frente a 9 157
de la lectura Ken. `capture_command` puede leer los bytes del recibo persistido
por `job_id` después del cierre; no necesita que el modelo reciba esa copia base64.

Validar una composición ejecutable de inicio → observación acotada/cierre →
captura → lectura canónica, seguida de la entrega ya comprobada. Debe preservar
Ken real, citas exactas, cobertura, identidad original y parada ante fallos,
truncación o autoridad retirada. También debe contemplar la ronda nativa final:
un draft renderizado no satisface ese criterio. No hay otra inferencia prevista
antes de esa validación. DD157 sigue diferido; no se atribuye a él todo el fallo.

Persistir directamente salidas Ken exigiría otra frontera de almacenamiento y
procedencia; no se ha demostrado su necesidad. El catálogo pesa 59 363 bytes JSON
UTF-8 compactos y conserva 54 herramientas; una compactación futura deberá
preservar capacidades y medir efecto real, sin convertir bytes en ahorro supuesto.

U08, comprensión/adaptación humana, Ken/ONNX, documentación restante,
accesibilidad y cierre integrado siguen abiertos. **19:22:51–19:35:06 UTC:
12 min 15 s** hasta comprobación y análisis; informe/checkpoint posteriores aparte.
