# Comunicación al revisar un hallazgo: un par real

Dos revisores reales por suscripción OpenAI, `gpt-6.1-sol/low`, con Ken publicado,
revisaron el mismo hallazgo y sus fuentes. Ambos registraron **needs_revision** y
explicaron que 28 de 40 mejoras reportadas describen un 70% observado, sin demostrar
una causa o un resultado aplicable a otras personas.
[Recibos](finding-communication-live.json), [verificación](finding-communication-results.json),
[respuestas y decisiones](finding-communication-responses.json).

## Material y controles

El autor es un fixture controlado, **sin generación ni reserva de inferencia**.
Guarda fuente, hallazgo deliberadamente excesivo e informe mediante transacciones
productivas. Sus IDs y fechas son sintéticos declarados antes de revisar; no son
fechas de captura empírica. Cada instalación tiene almacenamiento y autoridad nuevos.
No se copian credenciales ni autoridad de un host anterior.

Se verificó igualdad exacta del paquete completo: afirmación, citas, metadatos de
fuente, informe y procedencia del autor. El [registro](finding-communication-evidence/registration.json)
congela fuentes, petición, criterios, políticas, recursos y cinco archivos del
evaluador antes de generar. La base era `aca6728` y los hashes identifican los
cambios del evaluador aún sin commit. No se ajustaron criterios tras ver respuestas.

La capacidad es `finding_review` con admisión propietaria y sujeto hash exacto.
Ambos modelos tienen las mismas herramientas, entrada sustantiva y modelo/esfuerzo.
Sólo se normalizan identidades de la ejecución actual; el nuevo alias `review.run_id`
se elimina únicamente si coincide con `scope.run_id`. Autor y subject hash no se
normalizan. Una referencia ajena continúa siendo un control distinto.

| Brazo | Resultado | Tokens observados | Tiempo |
| --- | --- | ---: | ---: |
| Actual, catálogo9 | Decisión y explicación entregadas | 102930 | 59,497 s |
| Histórico | Decisión y explicación entregadas | 123862 | 57,075 s |

Total: **226792 tokens observados y116,572 s**. Preparación, análisis y documentación
fuera de ese tiempo; no es facturación ni cuota restante. Un turno por brazo,
180 segundos,20 herramientas y350000 tokens como techos, respetando límites menores.
No hubo reintentos ni ampliación de presupuesto.

## Lectura comprobada y límites

La revisión del implementador, **sin cegamiento**, encuentra apoyo para los cuatro
criterios registrados en ambos brazos:

- El rastro devuelve el sujeto completo y la fuente completa, desde offset0 hasta
  el final. Su contenido coincide con los originales. Ken devuelve `evidence.py`
  completo; no se confunde el código aritmético con un protocolo experimental.
- Ambas explicaciones conservan 28/40=70% como autorreporte sintético, distinguen
  asociación de causalidad y no convierten métodos no documentados en métodos
  necesariamente omitidos. No afirman que el programa carezca de efecto.
- Cada brazo guarda una decisión tipada `needs_revision`, checks explicados y
  límites. Sus citas y offsets coinciden con el texto y hash de la fuente guardada.
- Las respuestas explican en español qué se revisó, qué se puede conservar y qué
  significa atribuir una causa. El ejemplo de otro cambio concurrente es condicional,
  no un hecho inventado sobre los participantes.

No ejecutaron el código ni repitieron mediciones; lo dicen. El hallazgo permanece
provisional, el informe draft y la tarea in_progress. Sujetos y código sin cambios;
una revisión no acepta ni publica. Cuatro peers cerrados por brazo, cero grants
activos y ambos servicios cerrados con -15.

## Validación y trabajo restante

Cuatro fallos iniciales demostraron las brechas de alias, registro/autor y techo
actual del operador. Después pasan **36 comprobaciones dirigidas**, sin omisiones.
El inventario sigue en322 archivos/85 candidatos, cero revisiones pendientes.
Ruff deja dos avisos I001 de imports en el evaluador nuevo: pulido DD152.
Los módulos y funciones nuevos tienen docstrings ingleses.

No hubo nueva política productiva ni instalación de wheel. El nuevo test del
evaluador dentro de backend aún no forma parte del wheel anterior; la verificación
de paquete final sigue pendiente. Tampoco se ejecutó aquí la suite global.

Este par exploratorio no demuestra superioridad causal de prompts, representatividad,
validez científica calibrada o comprensión humana. U08 sigue abierto. Quedan la
comparación `code_review`, comunicación conjunta en UI de espera/error/parcial,
observación humana/adaptación y controles finales; no repetir este par para pulirlo.
