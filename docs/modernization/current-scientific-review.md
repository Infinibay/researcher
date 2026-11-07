# Evaluación actual: cálculo observado, entrega fallida

Una ejecución real con el catálogo 9, Codex por suscripción y Ken 0.18.0. Se usa
material de un [resumen primario de 1986](https://pmc.ncbi.nlm.nih.gov/articles/PMC1339981/),
sin lectura verificada del artículo completo ni recomendación clínica actual.
La tarea exige explicar la comparación, sus límites y los puntos porcentuales.

La fuente se capturó y leyó. Ken devolvió el código completo registrado; el
cálculo terminó con salida 0 y cierre comprobado. La salida original registra:

- 273/350: 78 %.
- 289/350: 82,571429 %.
- Diferencia: 4,571429 puntos porcentuales; cambio relativo: 5,860806 %.

No se guardó ningún informe ni se entregó explicación final. Los criterios de
claridad, inferencia causal y fidelidad de la explicación quedan sin evaluar.
No se reemplaza esa ausencia por una respuesta escrita por el evaluador.

## Presupuesto y cierre

El techo 120000 era una decisión del ensayo, menor que el del operador. Después
de siete solicitudes de herramientas se observaron 140692 tokens; el host detuvo
el intento. Los incrementos de consumo llegan después de trabajo nativo, por
lo que el límite observable no garantiza una cifra final exacta. No equivale
a coste facturado ni cuota de suscripción restante.

Se conserva un único despacho con consumo final desconocido, sin devolver esa
reserva por suposición. El servidor original terminó por SIGTERM (-15), los cinco
peers están cerrados y no quedan grants activos. La base pasa integridad/FK y
conserva una fuente, cero informes y cero findings. No hubo reintento.

Ruling: usar en futuras inscripciones el techo 350000 del harness general y el
menor límite del operador. El 120000 original y su fallo permanecen intactos.
El antecedente ya advertía de un techo insuficiente; elegir otra vez 120000 fue
una limitación evitable del diseño del ensayo. Este cambio no demuestra que
un caso futuro vaya a entregar correctamente.

Pasan tres comprobaciones sin cuenta: límites efectivos en la política,
integridad de fuentes/recursos y rechazo de reejecución. Siete funciones nuevas
tienen docstrings. No se cambió el backend instalado ni se creó una rueda nueva.
[Resultados y rúbrica](current-scientific-results.json),
[inscripción original](current-scientific-evidence/registration.json),
[observación original](current-scientific-evidence/original-observation.json).

La evaluación continúa abierta. No se cierra U08, no se demuestra superioridad
de prompts ni se sustituye una evaluación humana. El trabajo independiente
siguiente es la aceptación de las páginas, empezando por Proyectos.
