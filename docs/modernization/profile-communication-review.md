# Evaluación de comunicación en otros perfiles

Se ejecutaron **cuatro comparaciones y ocho turnos reales** con la suscripción de
OpenAI y Ken publicado. Los controles coinciden en los cuatro pares tras corregir
una identidad del comparador. **Sólo dos pares entregaron ambas explicaciones.**
No se cambiaron prompts productivos ni se repitieron respuestas fallidas.
[Resultados](profile-communication-results.json),
[respuestas e informes originales](profile-communication-responses.json),
[material A/B](profile-communication-human-review.md).

| Caso | Política anterior | Política actual, catálogo3 |
| --- | --- | --- |
| Plan CSV | Propuesta y explicación entregadas | Propuesta guardada;131499tokens frente al límite120000, sin explicación final |
| Lecturas repetidas | Informe y explicación entregados | Informe y explicación entregados; cuatro dispositivos no son veinte unidades independientes |
| Subgrupo favorable | Media80→79,2; explicación entregada | Agregado correcto; el informe atribuye indebidamente la mejora media a cada lote |
| Salida0 sin tests | Auditoría entregada con reproducción y límites | Informe guardado; llamada21con límite20, sin entrega final |

Los brazos suman **608,478 segundos**, aproximadamente **10min8s**, y
**2065880 tokens observados**. La duración del bloque incluye preparación,
análisis y registro. Los tokens no son coste facturado ni cuota restante conocida.
Seis despachos quedan settled y dos unknown; no se inventa su consumo final.
Los ocho servicios y los recibos de sus peers están cerrados, sin concesiones
locales pendientes de revocar.

## Hallazgos

Ambas versiones calculan50/60/10 en el caso de dispositivos y80/79,2/−0,8 en el
caso agregado. Distinguen repetición de lecturas de otra unidad experimental,
resúmenes duplicados de replicación y asociación de causalidad. No convierten
procedimientos no reportados en procedimientos necesariamente omitidos. Las citas
y cálculos son recuperables. Esto prueba resultados concretos, no ciencia o
comprensión humana en general.

Un cálculo correcto no basta: el informe actual afirma «diez lotes ganan 10
unidades cada uno». Sólo hay medias por subgrupo,
no cambios individuales. Una formulación fiel sería «la media del subgrupo de diez
lotes subió10; su contribución al cambio total es100». Un ejemplo donde cada lote
mejora10 tendría que declararse hipotético. La desviación está en el informe
persistido, con la cita literal en los resultados.

Los fallos de planificación y auditoría conservaron trabajo útil, pero no cerraron
la comunicación. En planificación hubo lecturas repetidas y consultas Ken que no
pudieron resolver un símbolo/analizar Python: límite observado del entorno, cuya
causa todavía no está diagnosticada. En auditoría se ejecutaron además tests de
facturación ajenos al helper pedido. Los controles cortaron la ejecución antes de
que el agente entregara; no se retocaron esas respuestas ni se elevó retrospectivamente
su presupuesto para convertirlas en éxitos.

**Siguiente tarea principal:** visibilidad de presupuestos durante la ejecución,
margen para entrega/explicación y cierre de exploración secundaria cuando amenaza
el objetivo central. Mantener los cortes duros y resultados desconocidos honestos.
También mejorar la explicación del trabajo parcial guardado y la fidelidad de
los ejemplos basados en promedios. Son pendientes funcionales, no detalles de
estilo ni cambios ya implementados.

## Controles y enmiendas

Se reutilizó `context_alignment` con casos, rúbricas, fuentes y políticas congelados.
Modelo/esfuerzo, herramientas reales y contexto sustantivo coinciden por par.
Ken devolvió el código completo registrado. Fuentes e informes persistidos pasan
hashes, las citas coinciden con el texto capturado y las bases pasan integridad/FKs.
No hubo aceptación, publicación ni cambios del código de los ensayos. Hay dos
propuestas de plan, seis informes draft y cinco entregas de informes; un draft
no se cuenta como entrega.

El límite inicial120000 resultó insuficiente para el primer candidato. Su fallo
se conserva. Antes de ejecutar los otros tres pares, una segunda inscripción
fijó350000, respetando límites menores del operador. No cambió prompts, fuentes,
criterios u orden. Es una adaptación de desarrollo explícita, no un experimento
confirmatorio intacto ni una nueva respuesta de planificación.

El primer par científico produjo ambas respuestas, pero el comparador rechazó
`request_history.cutoff_run_id`, alias del identificador nuevo de su propio run.
Se conservan el rechazo y ambos hashes. La enmienda ignora ese alias sólo cuando
coincide con el run actual; preserva historial y cutoffs ajenos. Se recalcularon
los controles desde los inputs originales sin regenerarlos, antes de los
reservados. Pasan27 pruebas dirigidas, incluidas esas fronteras y los límites del
operador.34 definiciones documentadas;3 avisos de imports se difieren en DD087.

## Límites

La revisión del implementador no fue ciega. Comprensión y esfuerzo humanos siguen
sin observarse. Cuatro casos sintéticos seleccionados no representan usuarios ni
investigación real; una observación por versión no demuestra superioridad causal.
Siguen otros perfiles, fuentes científicas reales y recorridos más largos. No
hubo nuevo wheel, frontend, suite global ni aceptación de páginas:43 escenarios
amplios abiertos y0/12 páginas completamente aceptadas.

Se aplicó `scientific-critical-thinking`. Su referencia verificada y los comandos
están en [la guía del evaluador](../../evals/profile_communication/README.md).
La referencia no valida estos resultados. Los prompts productivos siguen en3.
