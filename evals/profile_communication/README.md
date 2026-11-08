# Comunicación en planificación, ciencia y auditoría

La [conciliación vigente](../../docs/modernization/communication-evidence-reconciliation.md)
separa los fallos históricos descritos aquí de sus regresiones posteriores.

## Comparación adicional de desarrollo

`development.py` registra un par nuevo sobre exportación CSV. La capacidad es
desarrollo real en una copia privada: no se inyecta ese prompt en una tarea de
investigación con herramientas incompatibles. Ambas políticas reciben el mismo
contrato de entrada/salida, código, seis pruebas, base Git, catálogo, modelo y
límites. La política anterior es el texto histórico completo; no se atribuye
una diferencia a una frase aislada ni se llama reservada a esta muestra.

```bash
python -m evals.profile_communication.development --prepare \
  --assets /ruta/recursos-host.json --output /ruta/nueva
python -m evals.profile_communication.development --live \
  --assets /ruta/recursos-host.json --output /ruta/nueva
```

La preparación congela fuente, pruebas, petición, criterios, políticas y hashes
del evaluador antes de admitir un turno. Máximo dos turnos, uno por brazo;
180 segundos, 20 herramientas y 350000 tokens observados por brazo, o los
límites menores del operador. Sin comprobaciones independientes del host
configuradas: conservar por separado las pruebas que el agente efectivamente
ejecute. No se permite aceptar/publicar ni modificar el repositorio original.
Un brazo ya iniciado bloquea replay; un fallo conserva sus recibos. Comprensión
y esfuerzo humanos siguen `null`. Los resultados se registran después de observar
el cierre original; esta descripción no afirma que hayan pasado.

## Comparaciones históricas de planificación, ciencia y auditoría

Este ensayo extiende el evaluador instalado de `context_alignment`: mismo
runtime/suscripción, herramientas, modelo/esfuerzo y material por par; sólo cambia
la política de desarrollador. No implementa un loop de inferencia nuevo.

Se fijan cuatro casos antes de generar respuestas, con un máximo de ocho turnos:

| Caso | Perfil | Partición | Problema observado |
| --- | --- | --- | --- |
| Dependencias de un plan | Planificación | Desarrollo | Reutilización, explicación de dependencias y fecha histórica sin acuerdo |
| Mediciones repetidas | Investigación científica | Desarrollo | Unidad experimental, duplicación de fuentes y causalidad no identificada |
| Subgrupos seleccionados | Investigación científica | Reservada | Media ponderada, conclusión global y límites de un antes/después |
| Comprobaciones omitidas | Auditoría de código | Reservada | Salida0 frente a pruebas ejecutadas, revisión y aceptación |

Son casos sintéticos elegidos para cubrir mecanismos distintos. No representan
una población de usuarios ni la variedad de investigación científica real. No
se declara superioridad estadística o causal de un prompt con un resultado por
versión/caso. La revisión de hallazgos y candidatos, desarrollo, tareas largas y
fuentes científicas reales todavía necesitan su propio alcance de evaluación.

## Ejecución

```bash
python -m evals.profile_communication.run --prepare --output /ruta/nueva
python -m evals.profile_communication.run --live --assets /ruta/recursos-host.json \
  --output /ruta/nueva --split development
python -m evals.profile_communication.run --live --assets /ruta/recursos-host.json \
  --output /ruta/nueva --split reserved
```

La preparación congela políticas, datos, código, solicitudes, criterios y orden.
Cada brazo recibe una instalación vacía, un turno como máximo,180 segundos,
90 segundos sin progreso,20 llamadas y120000 tokens observados como techo inicial; los
límites del host pueden ser menores. Los ficheros de recursos derivados son
privados y no se exportan. Los estudios existentes impiden repetir un brazo.
Ante un fallo se inspecciona su proceso/recibo original; no se reinicia por un
timeout de observación ni se oculta la primera respuesta con otra más conveniente.

Se exige Ken real con el texto completo de `evidence.py`, política realmente
enviada y controles del par iguales, además de cierre de peers, concesiones y
servicio. Esto comprueba condiciones del experimento; no convierte una respuesta
en correcta. Se conserva por separado si produjo un resultado tipado y qué
concluyó el texto. Los registros instrumentados de herramientas pueden incluir
capas anidadas: su número no se etiqueta como número de llamadas del modelo.

## Criterios de lectura

Cada caso registra criterios concretos en `cases.py` y en su registro congelado.
Evaluar apoyo, preocupación o falta de evidencia para cada uno, con cita o recibo,
sin una nota global. Distinguir resultado aritmético, ejecución registrada,
evidencia documental, inferencia causal y calidad de la explicación. No inventar
varianzas, significación, réplicas independientes o procedimientos no reportados.
La ausencia de reporte no demuestra ausencia del procedimiento.

Las respuestas A/B se exportan con la clave separada; quien haya visto los brazos
no puede llamar ciega a su propia revisión. Comprensión y esfuerzo permanecen
`null` hasta observar una persona. La persona debe poder explicar conclusión,
límite y corrección posible; la fluidez de la respuesta no demuestra que lo logre.
No repetir la solicitud humana ya pendiente para forzar una puntuación.

Se aplicó la skill `scientific-critical-thinking`. Referencia verificada el
7noviembre2026: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M.
(2026), [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065), versión actualv2, sin referencia editorial indicada.
La biblioteca aporta criterios metodológicos; no valida este ensayo ni sus resultados.

## Enmienda de desarrollo del7noviembre

El primer candidato de planificación guardó una propuesta, pero terminó sin
explicación final al superar120000tokens observados (131499). Se conserva ese
fallo y no se repite el caso. El registro inicial y sus respuestas permanecen
intactos. La continuación registra sólo los tres casos aún no iniciados, con
350000tokens por brazo, sin cambiar fuentes, prompts, criterios u orden. Se
conservan todos los controles por par y se aplica el menor límite del operador.
La enmienda se decidió viendo el caso de desarrollo, antes de ejecutar ciencia
u observar los reservados. No es una comparación confirmatoria sin adaptaciones.

## Corrección del comparador y resultados conservados

Los dos brazos de dispositivos terminaron, pero el comparador rechazó el alias
`request_history.cutoff_run_id` de su propia identidad actual. La enmienda de
análisis conserva los originales y sólo normaliza ese alias si coincide con
`scope.run_id`; no elimina registros históricos ni una identidad contradictoria.
Los controles se recalculan desde texto original, no desde hashes copiados.
Se corrigió antes de los casos reservados, sin repetir generaciones.

La auditoría candidata también terminó con fallo:21inicios de herramienta con
20permitidos, un informe guardado y sin entrega final. Se ejecutó después sólo
el brazo anterior aún no iniciado, sin reintentar el candidato. Los ocho turnos
y ambos fallos se conservan en la [revisión](../../docs/modernization/profile-communication-review.md).
