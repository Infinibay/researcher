# Dependencias causales de tareas manuales y planificadas

`blocks` exige un resultado aceptado vigente antes de admitir trabajo nativo,
tanto manual como derivado de un plan. `related_to` y `parent_of` no añaden esa
barrera. La aceptación del plan sigue siendo una condición adicional de sus
hijas. Es una decisión de implementación para cerrar la asimetría encontrada;
no se presenta como una regla universal que el usuario hubiese especificado.

## Cambio de una premisa

Un cambio de contexto produce una causa durable con contexto anterior/nuevo.
La migración71 materializa su conjunto de afectados antes de modificarlo:

- descendientes de relaciones `blocks` dentro del proyecto;
- hijas de un plan cuyo contexto cambió;
- miembros del grafo autorizado cuya premisa efectiva coincidía con la versión
  anterior. Se conserva la política existente de invalidar todo ese grafo.

El recorrido usa un conjunto de tareas, de modo que ciclos y caminos que
convergen no multiplican sus revisiones. La pertenencia del grafo usa la vista
efectiva de reautorizaciones. Un indicador transaccional evita que los cambios
internos vuelvan a iniciar la misma propagación, con recursive_triggers activo
o inactivo. Cada descendiente recibe una versión nueva y evidencia atribuida a
la causa; se retiran grants/fences, vencen preguntas y los intentos pasan a
reconciliación. Las tareas con resultados nativos aceptados se reabren, conservando
informe, candidato, aceptación y recibos originales. Reaceptar al padre no renueva
la versión ni los permisos del hijo anterior.

El contexto raíz sigue retirándose por sus fronteras existentes de corrección y
metadatos. El nuevo mecanismo cubre sus consumidores en la misma transacción.
Ambos productores retenidos quedan cubiertos: `_advance_context` y el trigger
`version_task_inputs`, incluida la primera creación de contexto por una edición.
Se sustituyen los dos disparadores de propagación anteriores; no se superpone una
recursión independiente. El fallo de una revisión/evento revierte toda la causa.
La pérdida de autoridad no prueba cierre físico; ese cierre mantiene los controles
existentes y bloquea otro trabajo mientras quede una ejecución por reconciliar.

## Qué recibe el agente

Una admisión manual captura un paquete inmutable con las identidades exactas de
sus prerrequisitos aceptados, contexto, aceptación y descriptores de material.
Reutiliza los lectores de evidencia documental/código de los planes. El input
incluye `prerequisite_material`, instrucciones de lectura y límites: una referencia
no demuestra lectura o comprensión; aceptación de código no implica publicación;
el input histórico ausente sigue siendo desconocido. Los lectores sólo sirven
prerrequisitos del paquete de esa ejecución y revalidan evidencia/aceptación.
Las premisas no conceden autoridad ni aceptación a la tarea actual.

Un revisor de código resuelve el autor exacto desde su request independiente.
Validación, input y lectores usan esa misma resolución causal, conservando el
scope del revisor. No se crea una entrega ficticia del revisor ni se selecciona
otro autor por tarea. El helper no adquiere autoridad del autor ni llama al ciclo
de validación del lease.

## Persistencia y compatibilidad

Migración71 agrega causas/afectados y paquetes manuales, sin reconstruir eventos o
inputs históricos. Un run manual antiguo con dependencias y sin paquete conserva
su recibo, pero no inicia otro intento con premisas inventadas; hace falta una
solicitud explícita nueva después de resolver la anterior. Las entregas de planes
y sus versiones anteriores conservan sus bytes originales.

La inversa sólo admite esquema71 sin causas ni paquetes registrados; restaura los
triggers históricos exactos dentro de una transacción. Rechaza actividad retenida,
una conexión con transacción abierta o esquemas futuros. No cambia migraciones
anteriores ni afirma que haya datos del usuario que migrar.

## Verificación y límites

Los ensayos cubren SQLite real, permisos/leases, material/identidad, ciclos y
convergencia, ambos productores, tareas aceptadas, reaceptación, rollback y
compatibilidad sin backfill. Los fixtures declaran sus cierres/IDs sintéticos;
no prueban comprensión humana ni un resultado científico. El recibo de selección
fuente/instalada se guarda en `docs/modernization/dependency-authority-*.json`.
La revisión parcial independiente encontró y ayudó a corregir la frontera del
revisor. No sustituye la revisión final de todo el branch ni una suite global.
