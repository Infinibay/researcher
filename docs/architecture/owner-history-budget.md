# Historial y presupuesto de trabajo

Tareas permite recorrer ejecuciones anteriores a las últimas 30 del resumen.
Cada ejecución conserva su solicitud, contexto, comandos y entrada disponible;
sus intentos tienen modelo, resultado y observaciones propios. Agentes ofrece
la misma inspección de intentos. Leer historia no cambia el destino de los
controles de la ejecución actual ni inicia trabajo.

Las lecturas autenticadas son `GET /api/projects/{project}/tasks/{task}/run-history`,
`GET /api/projects/{project}/runs/{run}/attempts` y
`GET /api/projects/{project}/work-budget`. Las páginas descendentes usan
`before_seq`, tamaño predeterminado25/máximo100 y `next_before_seq`; no ordenan
por fecha. Cada respuesta se obtiene en una transacción de lectura, comprueba el
proyecto real y lleva `Cache-Control: no-store`. Funcionan sin runtime configurado.
Los cursores pertenecen a la instalación consultada; no son exportables entre
bases restauradas ni garantizan continuidad frente a mantenimiento destructivo.

El presupuesto acumula la historia del proyecto. La vista y la admisión usan
`project_work_usage`: cada envío reservado cuenta una solicitud; un recibo cerrado
con medición cuenta su máximo acumulado registrado. Los demás conservan como
mínimo su reserva, incluyendo excesos observados. No se suman repetidamente
notificaciones acumulativas. Los tokens retenidos ya forman parte de lo
contabilizado; no se suman otra vez. La capacidad disponible nunca se muestra
negativa, pero el exceso se conserva y se informa.

Una observación ausente sigue siendo desconocida. Incluso una medición conservada
en un recibo cerrado puede ser parcial: esta contabilidad limita admisiones y
no demuestra consumo físico exacto, cuota restante ni coste de la suscripción.
La vista no modifica la política ni restablece límites. Un fallo HTTP conserva
la última lectura correcta y ofrece reintento; no se presenta como historial vacío.

La sesión nativa conserva también el máximo acumulado: avisos de40,70,10,60
dejan70tokens observados y un incremento máximo de40, sin devolver capacidad ni
interpretar el aviso atrasado como un nuevo gasto. El mismo principio se mantiene
entre turnos de una sesión. Una transacción de reserva serializa los contendientes
por el último cupo del proyecto; sólo uno obtiene permiso para enviar el turno.

Un rechazo por presupuesto produce `ProjectBudgetExhausted`, compatible con
`RunConflict`, y conserva el snapshot de la decisión: límites, solicitudes
reservadas, tokens contabilizados, consumo desconocido, reserva solicitada y
límites que bloquearon la admisión. El usuario recibe `project_budget_exhausted`
con `inference_started=false` y una explicación concreta, en vez de un fallo
genérico de cierre. Por ejemplo: una solicitud necesita reservar100tokens y el
presupuesto del proyecto permite99; no se envía un turno. Cambios posteriores
en la historia no reescriben el motivo original.

La política sigue fijada por la primera reserva. Una configuración distinta no
la reemplaza; falta una operación del propietario para revisarla explícitamente,
con control de concurrencia y sin borrar consumo ni reanudar trabajo por sí sola.
Este es trabajo funcional pendiente, no pulido. Ver
[ensayos de presupuesto y falta de progreso](../modernization/aggregate-budget-review.md).

Verificación: [resultados](../modernization/history-budget-results.json),
[paquete instalado](../modernization/history-budget-packaging.json) y
[ensayo visual](../design/audits/2026-11-07-history-budget/report.md).
Siguen pendientes los eventos tras desconexión/retención y la aceptación integral
del plan; estas lecturas no constituyen esa aceptación.
