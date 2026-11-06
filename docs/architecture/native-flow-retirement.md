# Retirada de flows y auxiliares antiguos

Se retiran 21 módulos de flujos, parsers, validadores de texto, estados y helpers.
Las ocho clases de flujo ya devolvían una indicación de entrada al propietario;
no ejecutaban el motor nativo. La API conserva las tres operaciones de proyecto
que todavía consumía, ahora en `backend/project_records.py`: crear, consultar
metadatos y conteos, y cambiar etiquetas operativas. No cambia ningún esquema ni
se borra información histórica.

## Destino de cada responsabilidad

| Responsabilidad anterior | Contrato conservado o sustitución |
| --- | --- |
| Plan principal, brainstorming y creación de tickets | Planificación nativa en `backend/planning`: propuesta estructurada, evidencia y supuestos, revisión del propietario, creación atómica y entrega de ejecución. Los wrappers antiguos ya no son entradas públicas. |
| Desarrollo y revisión de código | Admisión nativa de tarea, candidato identificado, comprobaciones sobre ese candidato, revisión independiente y aceptación expresa. Se conserva la prohibición de completar una tarea mediante una etiqueta antigua. |
| Investigación exploratoria y científica | `backend/research/investigation.py`, políticas científicas nativas, hallazgos y resultados con procedencia y revisión. Los informes históricos conservan su identidad; no se convierten en resultados aceptados. |
| Extraer tareas, IDs o veredictos de texto libre | Schemas y operaciones nativas explícitas. Una frase «APPROVED», una tabla Markdown o una traza ReAct no crean trabajo ni aceptan resultados. |
| CI mediante subprocess y parser de resúmenes | Ejecución nativa de comprobaciones, control de proceso y recibo asociado al candidato exacto. Los conteos antiguos de CI siguen siendo datos históricos. |
| Claims, dependencias y promoción por etiquetas | Coordinación nativa y entregas del plan aceptado; una tarea antigua marcada `done` no autoriza por sí sola trabajo nuevo. |
| Mensajes enriquecidos por roles y snapshot | Contexto atribuido, material de planificación y mensajería nativa con identidad real. El historial puede aportar evidencia, pero no aprobación ni permiso. |
| Detección de tecnología y contexto del repositorio | Acceso al repositorio admitido, Ken y herramientas nativas de lectura. No se conserva un scanner de directorios usado sólo por fábricas retiradas. |
| Estancamiento, pausa y reanudación de loops | Controles nativos y parada observada. Los controladores históricos ya registrados siguen retenidos hasta verificar su cierre; su retirada restante pertenece al bloque de autonomía. Los presupuestos completos siguen pendientes. |
| Reporte final y finalización del proyecto | Informe de proyecto y decisión explícita del propietario en `backend/planning/completion.py`. Un conteo de tareas o estado de snapshot no sustituye esa decisión. |
| Metadatos de proyectos y conteos | `backend/project_records.py`, utilizado por las rutas de proyectos y épicas. Se conserva la descripción original del usuario y el rechazo a completar el proyecto desde el helper genérico. |

El paquete `backend.flows` conserva únicamente el bus compartido y el servicio
de snapshots históricos. `FlowManager` aún puede guardar una última observación
de un controlador registrado al pararlo. No se declara eliminado todo el paquete
ni demostrada la ausencia de procesos históricos externos.

## Casos que podrían confundirse

- **Un snapshot dice `completed` y `user_approved=True`.** Su lectura devuelve
  `origin: legacy_snapshot` y `native_resume_supported: false`. Se muestra el
  resumen permitido, sin copiar esa aprobación a una ejecución nativa ni cambiar
  el estado actual del proyecto. Por ejemplo, nueve tareas completadas en ese
  registro describen el pasado; no prueban que el proyecto actual esté aceptado.
- **El usuario corrige la descripción del proyecto.** Se conserva el texto original;
  los conteos se calculan para el proyecto consultado. Crear o editar metadatos
  no inicia agentes. La aceptación integral continúa en su operación específica.
- **Un consumidor intenta importar un flujo eliminado.** Ya no existe esa API de
  compatibilidad. Los consumidores internos verificados usan las operaciones
  nativas o las tres funciones de metadatos retenidas. No se promete compatibilidad
  con imports dinámicos o consumidores externos desconocidos.
- **Un trabajador antiguo no termina al recibir Stop.** No se descarta su referencia
  para aparentar una parada. Se conserva el contrato ya probado de observación del
  cierre. La retirada de autonomía debe respetarlo.

## Verificación y límites

Las pruebas nuevas recorren la API autenticada: creación/edición, descripción
original, épicas y conteos, rechazo de finalización genérica y lectura de snapshots
sin reejecutar aprobaciones. Se mantienen las pruebas de migración 7, metadatos,
EventBus, Stop, WebSocket y los recorridos nativos de planificación, ejecución,
continuidad, corrección, investigación y aceptación.

Se retiran 68 funciones de test específicas de implementaciones eliminadas.
Los cinco fallos antiguos de helpers y `completion_router` desaparecen al retirar
sus implementaciones y pruebas; **no se presentan como fallos reparados**.
Los tres fallos observados en esta selección corresponden a fixtures de migración
que esperan versiones 53, 51 y 52 mientras reciben 56; se reproducen con los
mismos mensajes en el paquete anterior `e579a27`.

El fixture compartido histórico de la API también intenta parchear
`schedule_periodic_cleanup`, ya eliminado. La nueva cobertura usa el fixture
nativo existente de propietario autenticado; no se debilita la autenticación ni
se afirma haber reparado toda la suite API. La actualización de ese fixture es
trabajo principal de integración/operación pendiente.

Evidencia: [resultados](../modernization/flow-retirement-results.json),
[paquete](../modernization/flow-retirement-packaging.json),
[imports y pruebas retiradas](../modernization/flow-retirement-imports.json) y
[docstrings](../modernization/flow-retirement-docstrings.json).
La revisión de prompts archiva seis candidatos y revalida trece candidatos con
AST idéntico frente a los consumidores modificados. No se cambian instrucciones
de agentes ni se declara demostrada su eficacia con modelos o personas.

Siguen pendientes autonomía y lectores restantes; operación e imágenes;
migración, inversas y restauración real; historial completo y presupuestos;
evaluación integral y aceptación de las doce páginas. El pulido se realiza
después de todas esas capacidades principales.
