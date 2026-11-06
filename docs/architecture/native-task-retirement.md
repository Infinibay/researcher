# Retirada del catálogo antiguo de tareas

Se retiran los 15 módulos de `backend.tools.task`, que exponían 14 herramientas.
Las capacidades útiles quedan en el host nativo y el espacio de tareas. Las
tablas, IDs, comentarios y notas históricos permanecen intactos.

| Herramientas anteriores | Destino actual y evidencia |
| --- | --- |
| `create_task` | Propuesta tipada de planificación y aceptación del propietario sobre su hash/contexto. La propuesta no crea trabajo; aceptar crea el grafo una sola vez. `test_project_planning.py`. |
| `set_task_dependencies` | DAG validado al planificar; cambios posteriores por edición del propietario y reautorización del grafo observado. No hay edición imperativa de dependencias por el modelo. `test_plan_reauthorization.py`, `test_plan_execution.py`. |
| `take_task` | Admisión y claim del host con un único lease vigente. Dos dueños concurrentes no obtienen el mismo intento. `test_coordination.py`. |
| `update_task_status` | Transiciones de ejecución, parada y corrección del host. Terminar el turno propone revisión; no completa la tarea. `test_coordination.py`, `test_result_acceptance.py`. |
| `approve_task`, `reject_task` | Revisión separada y aceptación explícita del propietario; el veredicto está ligado al resultado/candidato y contexto exactos. El rechazo no habilita una reejecución automática. `test_result_acceptance.py`, `test_code_acceptance.py`. |
| `get_task`, `read_tasks`, `check_dependencies`, `read_task_history` | Lecturas por proyecto, cursor y ventanas; las etiquetas no confieren permiso de inicio. `test_task_workspace.py`. |
| `add_comment`, `read_comments` | Comentarios persistidos, atribuidos e idempotentes; un texto imperativo no modifica estados. `test_task_workspace.py`. |
| `save_session_note`, `load_session_note` | Última nota del actor/tarea con revisión observada y recibo original. Las notas son asesoría y distinguen observaciones de suposiciones. `test_task_workspace.py`. |

Los contratos están en [contexto de tareas](native-task-workspace.md),
[matriz de capacidades](capability-matrix.md) y las implementaciones de
`backend/planning/`, `backend/runtime/` y `backend/task_workspace.py`.

## Decisiones de compatibilidad

La similitud semántica de títulos ya no rechaza automáticamente tareas. La
planificación conserva claves locales únicas, validación del grafo, recibos y
revisión humana de la propuesta. Dos títulos parecidos pueden describir trabajos
distintos; no se transporta el rechazo aproximado y best-effort del wrapper viejo.
El agente puede consultar tareas existentes antes de proponer otras.

Tampoco se transporta el cierre automático de épicas/hitos cuando sus tareas
tienen etiquetas terminales. El cierre del proyecto utiliza entregas aceptadas
y decisión del propietario; una etiqueta `done` aislada no demuestra el objetivo.
Las pruebas de `test_project_completion.py` conservan esa distinción.

No se mantienen aliases importables de los wrappers ni sus schemas antiguos como
una segunda API de ejecución. Los nombres en el catálogo documental histórico
siguen siendo referencias de migración. El análisis estático de imports abarca
`backend/` y `scripts/`; no certifica consumidores externos o imports dinámicos.

## Pruebas y límites

Se eliminan 21 tests específicos de wrappers y seis tests de la integración del
loop anterior. El diálogo de comunicación de esa integración se conserva como
un test independiente; por tanto, 26 tests se retiran y uno se traslada. No se
contabilizan como fallos corregidos. La protección SQL de investigación permanece
probada, aunque ya no se invoque el wrapper eliminado. Los fixtures de conocimiento
crean sus datos directamente, sin usar una herramienta de tareas retirada.

El catálogo nativo y sus reemplazos tienen verificación separada en fuente y
paquete instalado. Los fallos preexistentes de conocimiento y migración/inversa
se conservan con comparación contra `f70fc00`; no se cambia un número de versión
ni se debilita una protección de restauración para hacer pasar el lote.
Véanse [resultados](../modernization/task-retirement-results.json) y
[paquete](../modernization/task-retirement-packaging.json).

Siguen pendientes comunicación, proyecto, conocimiento y cinco dependencias
legacy. La migración/restauración histórica, operación, historial completo,
presupuestos, CLI y evaluación global/humana/científica siguen siendo tareas
principales. Esta retirada no acepta integralmente las páginas ni cierra el plan.
