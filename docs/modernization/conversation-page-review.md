# Conversación: respuestas y notas que conservan su identidad

QuestionCard conservaba la respuesta sólo en un ref. Ahora persiste el cuerpo,
clave, tarea/proyecto, pregunta y run original antes de enviar. Recupera el mismo
paquete tras recarga aunque el servidor ya muestre la pregunta respondida o vencida.
No sustituye su versión por la actual. Distingue selección por option_id de texto
literal, valida el recibo antes de retirar la copia y bloquea nuevas escrituras si
el almacenamiento está dañado o falla. Retirar copia es explícito y no deshace
respuestas del servidor. Usa el almacén compartido con una identidad de run real.

La página incorpora notas explicativas usando el endpoint OwnerNotes ya existente.
Su ámbito es el hilo del proyecto, incluso si varias tareas lo comparten. Se guarda
texto/hilo/clave antes del transporte y se recupera el recibo exacto; no cambia
instrucciones actuales ni inicia inferencia. No se inventa un run para almacenarlas.
La UI remite a Corregir el contexto para cambiar una premisa. El archivo sigue
siendo lector, separado del compositor del hilo activo.

Las consultas fallidas no anuncian índice/archivo vacíos ni tarea inexistente por
una lista desconocida. La bandeja identifica un contador cacheado como lectura
anterior. Se mantienen controles de pregunta mientras falla la lectura del hilo.
Tres REDDOMreprodujeron pérdida de respuesta, envío pese a fallo de guardado y falso
vacío. La nueva nota tenía una prueba previa de función ausente, no se cuenta como
un defecto de comportamiento anterior. **75UI/161contratos**, tipos/build yESLint
seleccionado pasan.4funciones Python y27definiciones frontend seleccionadas están
documentadas, además de módulos/JSDoc relevantes. Ruff2I001enDD143.

Navegador instalado:11estados/17checks. Índice de tareas e hilos con error/reintento,
archivo original sólo lectura, nota201guardada/respuesta perdida/recarga/mismo
recibo, pregunta nativa con motivo/ejemplo y elección identificada, respuesta200
perdida/recarga/mismo cuerpo/clave/expected_version1/recibo2. Una nota nueva y una
respuesta, un solo cambio de contexto1→2; su dependiente también queda en2.
La búsqueda conserva la tarea seleccionada, teclado abre/focaliza su título y el
proyecto ajeno carece de controles de esa tarea. Nuevo trabajo queda habilitado,
pero nunca se envía. Una ejecución antes/después,0dispatches/modelos,1IDde turno
sintético, peers lógicos cerrados y servicio143 en todas las sesiones. Fuentes y
metadatos conservados. No hay cierre físico de modelo o evaluación científica/humana.

El evaluador inicial confundió visibilidad móvil/escritorio y luego no esperó la
transición al índice antes de pulsar Enter. Finalmente exigía ver el contador
mientras el índice móvil estaba oculto. Se corrigió el evaluador según el CSS y
el estado observado, sin cambiar el producto para hacerlo pasar. Se preservan los
cuatro recibos failed originales. Las continuaciones revalidaron el mismo host,
estado y peers: no repitieron la nota; después de recuperar la respuesta, la última
continuación hizo sólo lecturas. Son cinco sesiones sobre el mismo fixture, no
cinco intentos de inferencia ni cinco notas/respuestas nuevas. Mantener viewport
explícito y esperar estados observables evita repetir esta preparación en lo próximo.

Backend/esquema71sin cambios: mismo wheelSHA59241c4a8460fa623de7d428dbf99a9a1a7ccd85fbe91a62ae572b312bf5f19d.
Sus169pruebas instaladas son el recibo anterior, no otra suite. El index servido
coincide con el build final tras cambios sólo de documentación. No nueva instalación.

**09:43:34–10:19:14UTC,35min40s hasta verificar/inspeccionar.** Preflight previo y
checkpoint/documentación posterior excluidos. Conversación alcanza aceptación
principal técnica/visual delegada: **10/12páginas**,41/43escenarios amplios. Faltan
Ejecución y Proyectos/AuthorityBusy, idempotencia de comentarios de tarea, cierre
no vacío, U08/C10/ciencia, distribución/dependencias, prompts, inversas71, suite y
revisión final. Los comentarios de tarea son otro endpoint; no se les atribuye el
recibo idempotente de las notas del hilo. Detalles DD143 al final.
[Resultados](conversation-page-results.json), [huellas](conversation-page-artifacts.json),
[documentación](conversation-page-docstrings.json),
[capturas](../design/audits/2026-11-08-conversation-page/report.md).
