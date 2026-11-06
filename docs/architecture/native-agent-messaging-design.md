# Comunicación nativa entre agentes: mensajes y recibos

Este bloque ejecuta la decisión ya aprobada en la sección 13.2 del plan:
operaciones tipadas del host y conversación informativa. No añade un scheduler,
una jerarquía de leads ni un loop de respuestas automáticas.

El roster antiguo no tiene proyecto por columna y sus roles no identifican un
destinatario único. La nueva dirección es una ejecución admitida del proyecto,
con tarea, actor y versión de contexto resueltos en el servidor. El emisor sale
del grant ligado al intento actual; el modelo no proporciona su identidad.

Cinco herramientas comparten el MCP de negocio y el host: descubrir
destinatarios, listar mensajes recibidos/enviados, leer contenido completo,
registrar mensaje y reconocer recepción. Cada mensaje tiene intención
informativa/pregunta/respuesta, referencia exacta a su antecedente cuando exista,
observaciones, suposiciones y referencias a fuentes del proyecto. Nada de ese
texto autoriza ejecutar, revisar, aprobar, publicar o completar trabajo.

Un registro canónico se une al chat existente. Mensaje y recibo de operación
se guardan en la misma transacción. El inbox durable permite recuperar tras
reiniciar; no se declara entrega sólo por guardar. La lectura tiene ventanas y
no marca automáticamente recepción. Un acuse explícito vincula el hash observado
con el intento receptor; tampoco demuestra comprensión o aplicación.

Las preguntas a un lead se reemplazan por una pregunta a una ejecución concreta.
No hay búsqueda de respuestas cacheadas por texto, polling bloqueante ni permiso
inferido al vencer un timeout. Las preguntas humanas conservan su canal tipado,
y las respuestas/progreso del agente al usuario conservan el recorrido nativo.
No se activa ningún consumidor a partir de un mensaje informativo.

Se acotan tamaño, paginación y cantidad de mensajes pendientes por ejecución;
una saturación devuelve conflicto explícito, sin pérdida ni retry automático.
Los cambios de contexto y destinatarios terminados invalidan nuevas entregas;
el historial original y los recibos se conservan. La UI distingue registrado
de recepción reconocida, con atribución y supuestos visibles.

El recorrido usa `runtime_agent_messages` (migración56), el store de grants y
recibos existente y cinco métodos compartidos de `ResearchTools`. El servidor
resuelve identidad, intento y contexto. Conserva hasta64 mensajes por ejecución
emisora y32 pendientes por ejecución/contexto receptor; cada cuerpo completo
tiene un máximo de32000 bytes, con texto y listas también acotados. La cuota
rechaza nuevos mensajes sin invalidar el recibo de uno ya guardado.

La proyección canónica alimenta las lecturas del propietario y el archivo de
conversaciones de la página existente, que ya consulta cambios cada3 segundos.
Expone destinatario/tarea/contexto, antecedente exacto, observaciones y
suposiciones del emisor y fuentes citadas. El lector antiguo avanza sobre estos
mensajes sin emitir eventos de activación. Sus marcas `message_reads` no cuentan
como acuse nativo. Los contadores conservan la interpretación histórica de roles
sólo para filas antiguas; el roster no sirve para resolver destinatarios nuevos.

Decisión comprobada: los hilos `team_sync` entre agentes no son hilos de
instrucciones del propietario. El guard existente rechaza admitir trabajo desde
ellos. No se añadió una promoción implícita de su contenido al contexto de otro
agente. Quien necesite actuar debe recibir una operación tipada admitida; leer,
responder o reconocer recepción no la sustituye.

Las pruebas cubren MCP/API/SQLite, propietario emparejado, proyectos y lectores
distintos, fuentes ajenas, retry, respuesta al mensaje equivocado, cambio de
contexto, saturación, reconstrucción de inbox, fallo de recibo transaccional y
migración55→56 con fallo/reintento y chat histórico conservado. La UI se verificó
por renderizado y compilación; eso no es aceptación visual/humana integral.
[Resultados](../modernization/agent-messages-results.json) y
[paquete instalado](../modernization/agent-messages-packaging.json).

**Siguiente dentro de comunicación:** terminar el mapa y retirar los wrappers
antiguos de envío/lectura, preguntas a leads y preguntas/respuestas humanas cuyos
recorridos nativos ya existen. Este avance no declara esa familia retirada.
Siguen abiertos los escenarios amplios, calidad con modelos, comprensión humana,
historial completo y restore real. Los detalles de estilo esperan al final.
