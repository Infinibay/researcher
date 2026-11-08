# Comentarios: solicitud y recibo originales

Basecc0434e,10:51:41–11:03:35UTC,**11min54s hasta verificar/inspeccionar**.
Documentación/checkpoint posteriores excluidos. El POST anterior duplicaba filas,
permitía reutilizar una clave con otro contenido y no comprobaba el proyecto
capturado.4REDAPI demostrados;2REDDOM por recarga/fallo de almacenamiento.

TaskComments reutiliza metadata_json: inserta nota y solicitud/recibo original
en una transacción BEGINIMMEDIATE. La repetición exacta devuelve el recibo201;
otro contenido/autor/tipo409, proyecto ajeno404. Concurrencia de4peticiones deja
una fila; un fallo de metadata revierte la nota. No hay migración/backfill ni
reescritura de notas antiguas. Las APIs sólo añaden notas; si se introduce edición
o borrado individual habrá que preservar recibos/tombstones por separado.
Eliminar la tarea deja la recuperación en404, no recrea otra. Sin clave, clientes
antiguos crean notas independientes. Los productores nativos conservan metadata
propia. El autor sigue siendo una etiqueta declarada, no identidad nativa probada.

El formulario persiste proyecto/tarea/cuerpo/clave antes del transporte y recupera
texto/tipo tras recarga aunque la nota ya figure en historia. Valida recibo exacto
antes de retirar la copia; ámbito ajeno/copia dañada/fallo de guardado bloquean
otro envío. Un callback tardío no retira otra solicitud. Retirar copia es explícito
y no elimina la nota. approval no acepta una entrega ni activa trabajo/contexto.

**33fuente/33instaladas,77UI/164contratos** pasan; tipos/build pasan. Wheel limpio
sdist→wheel SHA78250ff767586811df0c6d5fcf96fc1465efdda66c70bb8ad73f60d11c739986,
698fuentes/371producto coinciden;226importsbackend del entorno no editable.
83paquetes compatibles, controladorescpu/memory/pids conservados. Esquema71sin
cambio.16definiciones Python nuevas y módulos/funciones TS relevantes documentados.
No se repite la suite169del bloque anterior: la selección actual cubre este cambio.

Navegador:5estados/9checks,una nota,2HTTP201con mismo cuerpo/clave/recibo.10tablas
observadas no cambian,0runs/dispatches/peers, integridadok/FKsin errores. Servicio143
en las2sesiones. El primer driver falló después del efecto/recuperación por un
encabezado equivocado de enlace ajeno. Se conserva failed; continuación sobre el
mismo host con sólo lecturas pasa. No nueva acción por fallo del evaluador.
No aceptación humana/científica ni nueva inferencia. Lint tiene1anypreexistente,
1C408y1I001del evaluador; DD144al final, no lintglobalverde.

**11/12páginas,41/43escenarios**, sin nueva suiteglobalverde. Idempotencia de
comentarios queda verificada con este alcance. Siguen Proyectos/AuthorityBusy,
cierre no vacío, U08/C10/ciencia, distribución/dependencias, prompts, inversas71,
suite yrevisiónfinal. [Plan](task-comment-recovery-plan.md),
[resultados](task-comment-results.json), [paquete](task-comment-packaging.json),
[capturas](../design/audits/2026-11-08-task-comments/report.md).
