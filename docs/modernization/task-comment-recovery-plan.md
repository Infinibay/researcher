# Comentarios de tarea: conservar la solicitud original

Contrato anterior: POST añade una fila sin clave. La UI conserva sólo texto en
memoria; después de pérdida de recibo/recarga una repetición puede duplicarlo.
Nuevo contrato: capturar proyecto/tarea, texto/tipo/autor y clave antes del envío;
recuperar el recibo exacto y rechazar el mismo identificador con otro contenido.
La nota sigue siendo advisory, incluso con etiqueta approval.

Decisión de implementación: reutilizar metadata_json del comentario para guardar
solicitud/recibo dentro de la transacción SQLite existente, sin backfill ni nueva
migración. Las APIs soportadas añaden comentarios, no editan o borran notas
individuales. Borrar la tarea retira sus notas; recuperar su solicitud falla404,
no recrea la tarea. Sin clave, un cliente antiguo sigue creando notas distintas.
El endpoint acepta el proyecto capturado y comprueba su relación real con la tarea.
No se generaliza el almacén de planificación ni se inventa un run para una nota.

Afectados: nuevo store TaskComments, modelos/rutas de notas, paquete local con
identidad proyecto/tarea, hook y formulario/inspector. Otros productores nativos
mantienen sus metadata y recibos propios. Ken apunta al checkout antiguo: sus
relaciones son incompletas y se verificaron consumidores con fuente gestionada.

Pruebas: repetición/concurrencia, contenido distinto, proyecto ajeno y rollback
nota+recibo; compatibilidad de notas previas. DOM pérdida real del transporte,
remount y fallo de almacenamiento; contratos de ámbito/recibo ajeno/copia dañada.
Después tipos/build, selección backend instalada y navegador real con respuesta
201perdida, recarga yrecibo original. Accesibilidad completa/densidad quedan al final.
