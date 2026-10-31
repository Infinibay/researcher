# Conversación, trabajo y evidencia del propietario

Estado: entrega funcional parcial sobre el coordinador nativo. Tareas y Chat
usan ahora el recorrido de investigación con solicitudes explícitas. No es el
rediseño visual final: faltan conceptos generados, selección, implementación
de las doce páginas y comprobación del navegador/accesibilidad.

## Un mensaje no prueba que el trabajo se haya aplicado

La ruta `POST /api/chat/{project}/instructions` recibe tarea, contexto,
repositorio opcional, hilo, texto y clave de operación. La admisión y el mensaje
del usuario se guardan en la misma transacción; su respuesta incluye el recibo
del mensaje y la ejecución. `runtime_chat_links` conserva esa relación. Una
propuesta nativa vigente se guarda en el mismo hilo y transacción que su resultado
y evento. No acepta la tarea ni autoriza publicar. Un resultado obsoleto no se
presenta como respuesta vigente.

El DTO de mensajes distingue `recorded`, `instruction_admitted` y `proposal`.
Proyecto, tarea, contexto y run proceden de joins canónicos, no de metadatos
inventados por el autor. El historial conserva el contexto original y refleja
que su ejecución fue superseded cuando cambia. El texto histórico no se reescribe
para fingir que siempre conoció la corrección.

Un hilo existente debe pertenecer al proyecto, estar activo y corresponder a la
tarea elegida. Un hilo de usuario anterior sin tarea puede vincularse al elegirla
explícitamente. Sus mensajes anteriores siguen siendo historial: no se añaden
silenciosamente al prompt como instrucciones vigentes. La versión y las
correcciones del contexto se construyen por el contrato del coordinador.

La ruta genérica de mensajes conserva su compatibilidad y ahora respeta el hilo
solicitado; rechaza uno ajeno o cerrado. Su recibo significa mensaje guardado.
Todavía existe entrega antigua para conversaciones heredadas: esa ruta no es
el coordinador nativo ni representa el cierre de la migración de roles/flows.
La nueva interfaz escribe instrucciones por la ruta tipada; el historial anterior
se conserva en lectura. Las respuestas a preguntas antiguas y la conversación
general de planificación requieren todavía su reemplazo nativo completo.

## Un dueño de entrega

Los mensajes del runtime no crean eventos de autonomía antigua. Además, los
lectores antiguos y `create_message_event` excluyen conversaciones marcadas por
un run nativo, incluyendo mensajes genéricos posteriores dentro de ese hilo.
El marcador sirve para excluir entrega antigua; **no concede autoridad**. La
proyección humana sigue validando los links de DB. El cursor del poller consume
también los mensajes excluidos, para no reinterpretarlos más tarde si se borra
un marcador ni escanearlos indefinidamente. Un control positivo prueba que un
mensaje de un hilo antiguo sí conserva su entrega.

Esto no migra por sí solo el resto de escritores, coordinadores de proyecto y
herramientas antiguas. No se deben desplegar dos dueños del mismo trabajo.
La retirada integral de esos consumidores sigue en el plan.

## Reintentos y cambios de contexto

La web mantiene una intención inmutable durante el envío y reutiliza su clave
si se perdió la respuesta. Las mutaciones no se reintentan automáticamente.
Consultar o recargar estado sólo lee datos, sin volver a enviar la instrucción.
El usuario puede editar explícitamente una solicitud cuyo envío no se confirmó;
la interfaz advierte que la anterior puede existir y conserva el historial.

El coordinador recupera el recibo antes de aplicar precondiciones de trabajo
nuevo. Así, un reenvío de una instrucción del contexto 1 devuelve su ejecución
original aunque el contexto vigente sea 2. Recuperar una corrección antigua
tampoco interrumpe un intento nuevo del contexto 2. Se conserva el hash de la
intención: cambiar contenido o hilo con la misma clave produce conflicto.
Una reserva nativa anterior nunca autoriza reenviar el turno.

Stop distingue solicitud, espera y cierre confirmado. La corrección muestra
que se registró para el siguiente trabajo; no afirma que se aplicó en el turno
anterior ni inicia otra ejecución. El usuario puede reutilizar explícitamente
la solicitud anterior y volver a iniciar trabajo bajo el contexto vigente.

## Lectura de evidencia sin credenciales de agente

`GET /api/projects/{p}/tasks/{t}/workspace` entrega contexto, ejecuciones,
repositorios identificados por nombre, adjuntos, fuentes y borradores. No
devuelve rutas de control ni tokens. La lectura sigue disponible con el runtime
sin configurar y con la tarea cerrada. Los controles de escritura conservan sus
precondiciones; leer una tarea cerrada no la vuelve ejecutable.

`GET /api/projects/{p}/research-sources/{id}` recupera ventanas de la captura
inmutable, fecha y hash bajo la sesión del propietario. Un bearer de herramientas
no autoriza esta ruta ni los controles humanos. La fuente de otro proyecto no
aparece por conocer su id. Las respuestas de evidencia usan `Cache-Control:
no-store`. Los offsets de la captura son caracteres del servidor; la web usa el
cursor devuelto, sin inferirlo de unidades UTF-16.

El panel Trabajo de una tarea permite consultar su estado, instruir, detener,
registrar una indicación o ejemplo correctivo, leer capturas y abrir informes.
Chat requiere elegir una tarea y conserva la conversación histórica del proyecto.
Los enlaces a informes incluyen proyecto e id; cambiar de proyecto no reutiliza
una selección del otro. Los estados desconocidos bloquean enviar trabajo nuevo.
El historial de ejecuciones usa orden de inserción local, sin depender de que el
reloj avance. No expone ese rowid como cursor de sincronización.

Las páginas de chat hacia delante usan id ascendente; la página inicial conserva
los últimos mensajes en orden cronológico. Se corrigió el salto que ocurría al
aplicar LIMIT a los mensajes más nuevos y luego invertirlos. Sigue pendiente
el catch-up completo frontend/WebSocket, retención, paginación integral de hilos
largos y proyecciones grandes. Los paneles funcionales consultan estado por polling.

## Elección del modelo

El campo `model` del JSON indicado por `INFINIBAY_RUNTIME_CONFIG` selecciona el
modelo global del servidor. La configuración se carga al servir; cambiarla
requiere reiniciar. No hay todavía selector web ni políticas por agente/proyecto.
El modelo debe funcionar por la suscripción administrada; no se añade una ruta
de pago por uso para suplir falta de acceso.

La web muestra el modelo configurado. La migración 23 guarda por separado el
modelo informado y comprobado en la respuesta del thread nativo, antes de reservar
el turno. El modelo forma parte de la identidad de esa reserva: no se puede
cambiar al reenviarla. El historial muestra ese dato del intento; no sustituye
modelos anteriores por el valor actual de la configuración. Los despachos
anteriores sin ese dato quedan NULL, como desconocidos. Una copia de la prueba
real de conversación se actualizó de 22 a 23 sin cambiar sus ocho tablas de
contenido/recibos; la actualización es repetible y no tiene errores de FK.

## Evidencia y límites

`conversation-evidence.json` conserva un turno real por la suscripción: fuente,
cita, informe y propuesta en el mismo hilo; tres POST de la misma intención
produjeron un solo despacho. La corrección dejó el resultado como contexto
anterior, y recuperar el recibo antiguo no inició inferencia. No hubo eventos
de autonomía antigua; las credenciales se revocaron y la tarea no quedó done.

Las pruebas usan SQLite real para atomicidad, proyectos, versiones, recibos y
lectores. La web tiene pruebas Node de transporte/intenciones/estados y pasa
TypeScript/Vite. CUA sigue sin navegador disponible: no hay prueba visual,
recorrido de teclado ni aceptación del diseño. El motor aún debe incorporar
preguntas humanas pendientes, recuperación operable de incertidumbre, roles,
desarrollo/Git/review/CI y demás capacidades del plan; los 100 fallos de la
suite heredada permanecen identificados, no eliminados para simular migración.
