# Tareas: creación recuperable y dependencias sin falsos vacíos

Se corrigen capacidades principales de Tareas; **la página completa sigue abierta**.
Crear metadatos no inicia un agente. El formulario pide objetivo y ejemplo de
entrada/salida; este texto manual no demuestra mejora generativa ni comprensión.

## Cambio y compatibilidad

TaskCreate acepta operation_key opcional; la interfaz captura cuerpo/clave antes
de enviar y conserva una sola intención por proyecto en sessionStorage. El archivo
usa el prefijo researcher: existente para el aislamiento/cambio de instalación.
Recarga o respuesta incierta no fabrican otra clave. El recibo debe coincidir con
proyecto, clave, padres y valores originales antes de retirar la copia local.
Una respuesta tardía no selecciona una tarea en otro proyecto. Si el componente
ya se desmontó y no confirma el recibo, conserva la copia hasta recuperación
explícita; no transforma falta de confirmación en falta de tarea.

OwnerPlanningRecords reutiliza su transacción/recibo para task.create. Validación
de proyecto, grupo/hito y dependencias ocurre antes del INSERT. Reenvío exacto
retorna respuesta original sin revertir ediciones; cuerpo/tipo distintos409 y
recurso retirado409, sin recrearlo. Tareas conservan AUTOINCREMENT. Clientes sin
clave mantienen creación de una llamada; no se promete recuperar su respuesta.
complexity es canónico; estimated_complexity antiguo se reconoce, y dos valores
contradictorios422. La complejidad elegida ya no se pierde silenciosamente.

Migración70 amplía el CHECK del recibo conservando filas anteriores; no reescribe
69. Inversa explícita sólo sin task.create o versiones posteriores, conserva
recibos69 y trigger inmutable; su fallo transaccional restaura la tabla original.
Las dos pruebas históricas de inversa69 seleccionan69 explícitamente para seguir
probando esa frontera, sin rebajar el esquema del producto.

El mapa de prerrequisitos usa transporte autorizado, consulta por proyecto/IDs,
error/recuperación explícitos y no muestra un mapa completo si falla una lectura.
Advierte que los filtros pueden ocultar tareas. Se adaptó la paleta al workbench
para que sus relaciones sean legibles; no otro concepto o nueva generación visual.

## Evidencia y límites

8RED iniciales incluyen duplicación, relaciones ajenas, complejidad perdida y
contrato de recibo ausente. **30fuente y133instalados pasan,0skips**; incluyen
concurrencia real, rollback, inversa70 y cadena forward/interrupciones18–70.
Wheel limpio desde sdist: **689archivos Python/SQL,367producto** coinciden entre
checkout/wheel/instalación;243imports sólo del entorno instalado,83paquetes
compatibles. SHA256b2103c057f25443db82254c626f0f1b7962eaa7f23c35bbf499509d8a74ada51.
No nueva suite global; inversas globales antiguas aún requieren extenderse a70.

La prueba DOM del grafo falla antes de la corrección y pasa después. Cuatro
contratos de paquetes se escribieron antes del módulo nuevo (REDpor módulo ausente,
no un incidente runtime). Última selección: **154contratos/52UI**, tipos y build
pasan; warning de bundleDD121 permanece. Definiciones nuevas/modificadas relevantes
con docstrings/JSDoc; inventario de55definiciones registra12omisiones heredadas en
modelos/helpers que no se modificaron. No afirmar documentación global completa.
Ruff6(4I001/2C408),ESLint2anyheredados; DD138 al final.

Navegador instalado v4: **9estados/13checks**,1440/390,0Axe regional/overflow/
errores. Primera entrega confirma201en el servidor y se corta la respuesta. Tras
recarga, segunda entrega idéntica queda retenida hasta seleccionar otro proyecto;
no lo retargetea. De vuelta, tercera entrega recupera el mismo recibo y retira la
copia confirmada. **Una tarea, una dependencia nueva y un evento**, mismos padres/
complejidad high/prioridad1. Historial previo intacto,0runs/dispatches/IDs de turno,
servicio143. Fallos de lista/dependencias son desconocido, nunca vacío correcto.

Tres fallos anteriores de evaluador retenidos: v1etiqueta select con opciones
(sin POST/estado intacto); v2esperaba un panel de escritorio oculto en móvil;
v3esperaba limpiar la copia tras desmontar el observador. React Query sólo invoca
callbacks de esa llamada con listeners; conservar la intención era correcto.
Se corrigieron aserciones, sin cambiar producto para satisfacerlas. v2/v3
conservaron una sola creación y0runs. Cada caso es un host sintético nuevo y
cerrado; no se repitió trabajo del usuario ni inferencia incierta.

**07:06:21–07:29:21UTC,23min hasta verificar/inspeccionar**; documentación y checkpoint
posteriores excluidos. Siguen **8/12páginas,41/43escenarios**. Falta trabajo/historia/
correcciones/controles de Tareas, luego Conversación/Ejecución/Proyectos y gates
finales. U08/C10 y contención original no cambian. [Resultados](task-creation-results.json),
[paquete](task-creation-packaging.json), [capturas](../design/audits/2026-11-08-task-creation/report.md).
