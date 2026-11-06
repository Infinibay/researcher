# Retirada de la ejecución antigua por tarea

El corte sustituye la ejecución de `DevelopmentFlow` y `CodeReviewFlow` por las
capacidades nativas existentes. Sus `kickoff` conservan el formato de estado
histórico y devuelven referencias del proyecto y la tarea comprobados en SQLite.
No seleccionan agentes, ejecutan CI, interpretan una aprobación, completan trabajo
ni fusionan una PR. Una rama o identidad recibida del llamador no se toma como
procedencia comprobada.

## Resultados conservados y comportamiento retirado

| Antes | Recorrido actual |
| --- | --- |
| Asignación y loop de desarrollo/reparación antiguos | Admisión explícita del propietario, copia privada nativa y candidato exacto. |
| CI omitido tratado como aprobado | Comprobaciones nativas registradas con su resultado real; omisión no demuestra éxito. |
| Texto `APPROVED` y rework automático | Revisión independiente del candidato exacto; una revisión rechazada no se convierte en aceptación. |
| Marcar `done` y fusionar la PR desde el flow | Aceptación explícita del propietario; publicación local/remota requiere su operación separada. |
| Reiniciar asignaciones `in_progress`, lanzar hilos o esperar una hora | El tramo de ejecución de MainProjectFlow devuelve `native_owner_required`, también con tareas históricas terminadas o sin tareas. No deduce la finalización del proyecto. |
| Scavenger reconstruye eventos y elimina worktrees antiguos | Hook compatible sin efectos; los archivos pendientes de importar se conservan. |

## Perfiles de las doce categorías persistidas

Esta clasificación es una decisión de implementación basada en los resultados
que antes producía el fallback de desarrollo; no es una afirmación del usuario
sobre cada tipo de tarea.

- `code`, `bug_fix`, `test`, `design`, `integrate`, `documentation`,
  `experimentation` y `optimization`: entregables del repositorio mediante el
  recorrido de desarrollo nativo. Las instrucciones y criterios concretos delimitan
  el trabajo; la etiqueta no autoriza cambios adicionales ni publicación.
- `research` e `investigation`: resultados documentales ya conectados.
- `review`: auditoría de código de solo lectura con fuentes, hallazgos e informe.
  Debe identificar el material/revisión observado y declarar un objetivo desconocido.
  Un informe de esta tarea no aprueba el candidato de otra tarea ni demuestra
  independencia por tener otro nombre de actor. La revisión formal sigue usando
  el candidato exacto y su entrada específica `code_review`.
- `plan`: planificación nativa y expansión del grafo aceptada por el propietario.
  El catálogo de tareas hijas admite las otras once categorías, sin planes recursivos.

La API publica los perfiles de desarrollo realmente soportados por el adaptador
configurado y los tipos cuyo ciclo pertenece al propietario. La interfaz usa esa
información para ofrecer importación de archivos/candidatos a todos los perfiles
correspondientes y evitar el selector antiguo de estado incluso antes de la
primera admisión. El tipo TypeScript de propuestas también conserva la categoría
real, sin presentar todas como «Desarrollo».

## Historia, migración y límites

El esquema 54 instala guardas atómicas contra nuevos claims y finalizaciones
antiguas antes de la primera admisión de las categorías recién migradas. Después
se conserva la guarda de aceptación existente para código, informes y planes;
admitir un run por sí solo tampoco permite completar la tarea. No reescribe
estados, asignaciones, ramas o aprobaciones históricas ni fabrica runs/aceptaciones.
Las inversas 43–54 y el ensayo de restauración integral continúan pendientes.

El handoff distingue una política de entrada nativa de la evidencia de una
admisión existente: sin historial, `native_admission_run_id` es `null`. Tampoco
certifica que los productores antiguos se hayan detenido. El registro de
actividad y Stop siguen siendo necesarios antes de autorizar inferencia nativa.

**Pendiente principal:** productores de proyecto de FlowManager/AgentLoop,
planificación/configuración/brainstorm/finalización de MainProjectFlow e inferencia
auxiliar; su exclusión física global y la retirada de dependencias requieren su
propio corte. Los cuerpos privados de handlers antiguos ya inaccesibles desde
su entrada por la política compartida se retirarán con esos consumidores, sin
reabrir esta capacidad para pulirlos. Los escenarios amplios, el resto visual,
modelos/prompts/evaluaciones humanas y científicas, instalación/restauración y
revisión final de toda la rama siguen abiertos.

Ver [resultados](../modernization/code-flow-results.json) y
[paquete](../modernization/code-flow-packaging.json) para el alcance observado.
