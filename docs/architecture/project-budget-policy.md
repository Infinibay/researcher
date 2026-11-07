# Revisión del presupuesto por el propietario

El panel «Presupuesto de trabajo» permite cambiar los límites **totales** del
proyecto. El consumo y las reservas anteriores se conservan. Con100tokens
contabilizados, cambiar el total a500 deja400de capacidad; cambiarlo a50 deja0y
mantiene un exceso registrado de50. La cifra no representa cuota de suscripción
ni facturación exacta.

## Decisión y efecto

Cada cambio contiene proyecto, versión consultada, límites, motivo opcional e
identidad de operación. Una transacción compara la versión, actualiza la política
y conserva un recibo con la política anterior y el uso observado. Dos editores
de la misma revisión no se sobrescriben. Reenviar el mismo contenido con la misma
identidad devuelve el recibo original, incluso después de otros cambios; cambiar
su contenido produce conflicto.

Guardar no envía un turno, no reanuda tareas detenidas y no modifica los límites
de un intento ya reservado. Tampoco revoca autorizaciones de planes existentes:
el trabajo previamente autorizado puede usar el nuevo límite en una admisión
posterior mediante sus controles normales. El recibo `inference_started=false`
se refiere a la operación de política, no a la ausencia de actividad simultánea
de todo el proyecto.

La web guarda el paquete antes del POST. Si la respuesta se pierde, conserva
identidad y contenido tras recarga. «Consultar recibo original» hace una lectura;
«Enviar la misma decisión» usa exactamente el paquete anterior. Un rechazo por
versión exige cerrarlo explícitamente y consultar de nuevo antes de preparar otro.
Cambiar de proyecto no retargetea una decisión; el control general de identidad
de instalación protege estos paquetes al cambiar/restaurar el servidor.

## Contrato y migración

- `GET /api/projects/{id}/work-budget`: contabilidad y política con `revision`.
- `POST /api/projects/{id}/work-budget`: decisión del propietario con CSRF,
  `operation_key`, `expected_revision`, `turn_limit`, `token_limit`, `reason`.
- `GET /api/projects/{id}/work-budget/changes/{operation_key}`: recibo original
  de ese proyecto; no crea ni reenvía operaciones.

Los enteros son exactos en navegador, hasta9007199254740991. El motivo es opcional
y admite2000bytes UTF-8. La ruta funciona sin runtime configurado y no concede
esta autoridad a las herramientas de los agentes.

Migración60 añade revisión0 a políticas anteriores, sin inventar decisiones ni
alterar despachos. La configuración del host sigue sembrando proyectos sin
política; en revisión0 un cambio de configuración sigue exigiendo reconciliación.
Desde la primera decisión explícita, la política del propietario gobierna futuras
admisiones. Los recibos se conservan en `runtime_project_budget_changes`.
La inversa de60 sólo admite esquema último y sin decisiones del propietario;
con historia exige reparación hacia delante o restauración de backup validado.

[Plan y casos](../superpowers/plans/2026-11-07-project-budget-policy.md),
[resultados y límites](../modernization/project-budget-policy-review.md).
