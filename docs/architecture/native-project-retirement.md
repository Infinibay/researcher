# Proyecto: capacidades nativas y retirada de herramientas antiguas

Se retiran ocho herramientas y nueve módulos de `backend.tools.project`.
Antes de retirarlos se añade la capacidad que faltaba: hitos opcionales en la
propuesta del plan, revisión visible y creación atómica junto con épicas y tareas.
Las tablas y los registros históricos no se borran ni se migran en este corte.

| Herramienta anterior | Reemplazo y decisión |
| --- | --- |
| `create_epic` | `researcher_plan_propose` propone el grafo; el propietario acepta su hash y contexto exactos. Crear una épica ya no completa otras automáticamente ni rechaza títulos por similitud aproximada. |
| `create_milestone` | Propuesta opcional con clave local, épica, título, descripción y fecha propuesta. La aceptación crea los hitos y asigna las tareas en la misma transacción. |
| `read_epics`, `read_milestones` | `researcher_project_structure` y `researcher_project_structure_read`: catálogo por proyecto con cursor, filtros y ventanas completas de título/descripción. Reutilizan el permiso `tasks.read`. |
| `create_repository` | Operaciones explícitas del propietario en `SourceOperations`, con directorio, modo e intención observados. Se elimina el stub que ya rechazaba la creación por el modelo. |
| `update_project` | Edición del propietario por la API de proyectos, con comprobación opcional del hash de alcance. El cierre requiere el informe completo y su aceptación explícita. No se conserva la escritura arbitraria de metadata/estado por el modelo ni el bypass `force`. |
| `read_reference_files` | Catálogo de referencias, captura vinculada y consulta de fuentes nativos. No se inventa una ruta de contenedor a partir del path del host. |
| `create_hypothesis` | `researcher_finding_record` con `finding_type="hypothesis"`, evidencia citada y estado provisional. No se transporta una confianza numérica inventada como validación científica. |

## Hitos, compatibilidad y autoridad

Un plan admite hasta 32 hitos. Cada hito pertenece a una épica del mismo plan;
una tarea sólo puede referir un hito de su propia épica. Se rechazan claves
inexistentes, duplicados, fechas imposibles y campos de autoridad no declarados.
Los planes anteriores sin hitos conservan su forma y sus recibos originales.
El schema del transporte no añade campos opcionales no enviados al material
que se guarda y se calcula para el hash.

El propietario ve todos los hitos, su descripción, fecha propuesta y las tareas
agrupadas antes de aceptar. Una fecha propuesta no acredita acuerdo previo ni
programa ejecuciones. Si falla el recibo de aceptación se revierte toda la
jerarquía; repetir la misma operación recupera los IDs originales. Autorizar
ejecución sigue siendo otra decisión. La entrega al agente conserva el plan
aceptado completo, incluidos los hitos.

Los lectores limitan también los conteos de tareas e hitos al proyecto: una
referencia histórica cruzada no revela contenido ni aumenta los conteos con
filas ajenas. `tasks_labeled_done` describe etiquetas, no resultados aceptados.
Los títulos del catálogo son previews; el texto completo tiene ventanas y cursor.
La metadata es mutable y no reemplaza el contexto admitido ni concede permiso.

## Evidencia y límites

Pruebas de contrato en `test_plan_milestones.py`, `test_project_structure.py` y
`test_task_workspace.py`; regresión dirigida de planificación, ejecución,
continuación, reautorización, cierre, operaciones de fuentes y adquisición.
Se retira un test del stub viejo de creación de repositorios, sin contarlo como
fallo reparado. La ausencia del paquete se comprueba en fuente y paquete instalado.
El análisis de imports incluye Python de `backend/` y `scripts/`, con tests e
imports relativos; no demuestra ausencia de consumidores externos/dinámicos.

Los resultados medidos están en [resultados](../modernization/project-retirement-results.json)
y [paquete instalado](../modernization/project-retirement-packaging.json).
Las pruebas UI verifican el contenido renderizado y la compatibilidad con planes
anteriores; no equivalen a aceptación visual integral ni comprensión humana.
No se cambian dependencias ni se realizan llamadas reales a modelos/proveedores.

Siguen pendientes las herramientas de conocimiento, cinco bibliotecas antiguas,
servicios/CLI restantes, operación, historial/presupuestos, migración/restore y
evaluación integral. Las referencias a nombres antiguos en prompts/guardrails
históricos se mantienen identificadas para retirar sus consumidores; no son
entradas del catálogo nativo. Este corte no cierra el plan general.
