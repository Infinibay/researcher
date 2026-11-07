# Cobertura contrastada con el producto actual

**U06 queda comprobado; diez listas de pendientes dejan de pedir migraciones ya
realizadas.** Permanecen42escenarios amplios abiertos y0/12páginas plenamente
aceptadas. Esto corrige la planificación; no convierte actividad histórica en
aceptación global ni elimina las obligaciones de datos, operación y personas.

Base `6a142a8`. Bloque 7 noviembre 2026, 14:38:11–14:44:49 UTC: **6 min 38 s**
hasta validar.36pruebas dirigidas pasan en12,09s, sin omisiones. Cero turnos de
modelo y ninguna modificación de lógica productiva. No se repite la suite global.
[Resultados y casos](coverage-reconciliation-results.json).

## U06: configuración durante una tarea o guardado interrumpido

Se contrastó el texto de13.6 del plan con estos criterios, sin exigir que cada
modelo comercial esté disponible en la cuenta para probar el contrato local:

| Requisito | Evidencia actual |
| --- | --- |
| Snapshot por intento | `test_attempt_model_selection_is_frozen_before_inference_even_after_policy_changes` conserva la elección original; un intento distinto toma el cambio. |
| Cambio durante trabajo real del runtime | `test_owner_configuration_changes_future_choices_without_retargeting_actual_native_attempt` pausa el catálogo después de guardar la selección y cambia la política vía HTTP. Broker, SQLite y proceso de protocolo controlado mantienen modelo/esfuerzo/revisión originales. |
| Escritura interrumpida | Tres casos nuevos terminan un proceso independiente con `os._exit(73)` después de la mutación SQL real y antes del commit: global, proyecto y agente. El lector conserva pareja/revisión anteriores; un reintento con la revisión original avanza a2. |
| Dos editores | Revisión vieja produce conflicto; no reemplaza la pareja nueva ni mezcla sus campos. El recorrido HTTP comprueba409. |
| Validación y ausencia de sustitución | Pareja inválida o no disponible se rechaza; el catálogo no envía un turno y la elección original se conserva. |
| Proveedor/cuenta estables | Ajustes no admiten una clave API; pruebas de sesión permiten refrescar la misma cuenta y retiran la conexión ante cambio de cuenta, sin replay. |
| Explicación al propietario | El diálogo distingue cambios para intentos futuros, herencia y catálogo observado. El recorrido web real previo conserva borrador tras respuesta perdida y muestra aislamiento global/proyecto/agente. |
| Configuración antigua | Las opciones del motor retirado se rechazan; el JSON histórico se conserva y no reemplaza el entorno explícito. |

Los tres procesos de escritura comparan además el hash del módulo ejecutado con
el del padre: se ejercita la misma implementación. Las pruebas nuevas verifican
una caída de proceso, no pérdida eléctrica del dispositivo. Ese escenario físico
pertenece a recuperación de storage y continúa abierto.

[Contrato de modelos](../architecture/model-configuration.md),
[UI real conservada](../design/audits/2026-11-06-model-settings/report.md),
[configuración retenida](../architecture/retained-configuration.md).
La disponibilidad de modelos de una cuenta, compatibilidad de otros hosts y
comprensión humana no se deducen de los dobles de protocolo. Se mantienen en sus
entregables respectivos; U06 describe atomicidad, selección y continuidad.

## Pendientes de migración que estaban obsoletos

Se comprobaron otra vez la ausencia de los21módulos de flows y54de autonomía,
plantillas y lectores de proveedor listados en los inventarios de retirada.
El análisis AST de581archivos backend/scripts no encuentra imports estáticos de
las familias retiradas examinadas. Las pruebas actuales confirman que el engine,
constructores por rol y memoria CrewAI no están disponibles; los lectores
históricos y el control de trabajadores realmente registrados siguen funcionando.
[Inventario y límites](coverage-reconciliation-inventory.json).

También se compararon328archivos productivos Python/SQL con el entorno instalado:
coinciden todos. Ninguna de las cinco bibliotecas antiguas está instalada allí.
La primera comprobación incluía `db/seeds/dev_data.sql`; ese archivo de desarrollo
no entra en la regla explícita `db/*.sql` del paquete ni en el wheel. Se conserva
esa distinción en el [recibo de instalación](coverage-reconciliation-installed.json).
No se reconstruyó un paquete sin cambios productivos.

Chroma sigue existiendo en el exportador histórico aislado y su entorno específico.
La retirada de la dependencia del servicio no cierra sus avisos de seguridad ni
demuestra recuperación de datos reales. Tampoco la ausencia de módulos prueba que
un proceso externo de una instalación antigua haya terminado.

Se actualizan pendientes de fuentes estructuradas, Wiki, registro/revisión/lectores
de hallazgos y cinco entregables de planificación/continuidad/terminal. Se conservan
las formulaciones anteriores y sus reemplazos en
[cambios exactos](coverage-reconciliation-changes.json). La evidencia de retiro
precedente conserva sus límites históricos; el registro actual enlaza esta revisión.

## Trabajo que sigue siendo principal

- Planificación/continuidad: adopción de trabajo manual o interrumpido, material
  precedente que excede el presupuesto y ciclo de vida integral según los casos
  todavía no aceptados. Contrastar cada pendiente con su implementación antes de
  abrir otro bloque; no asumir que las listas antiguas son exactas.
- Datos/operación: instalación existente, productores externos, datos históricos
  del propietario, recuperación física y límites agregados aún no demostrados.
- Evaluaciones representativas de comunicación, fuentes y perfiles; comprensión
  humana y aceptación de las12páginas.
- Dependencias publicadas compatibles y distribución concreta.

La pasada de detalles, incluida accesibilidad/reflow registrados, va después de
las capacidades principales. La validación global y la revisión independiente
siguen pendientes. No se infiere un porcentaje global de cerrar uno de43escenarios.
