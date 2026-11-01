# Bandeja de preguntas y conversación del propietario

`GET /api/projects/{project_id}/questions` es una lectura del propietario, disponible
sin configurar inferencia. Cookie/sesión del propietario; un bearer de herramientas
no autoriza esta ruta. Responde no-store, con un máximo de cien registros por página
(cincuenta en el cliente), cursor after_id y total pendiente. La lectura completa
cada página en una transacción. No inicia, reintenta, responde ni acepta trabajo.

Cada solicitud nativa conserva request_id, tarea, ejecución, hilo, versión de la
pregunta, versión actual y las preguntas originales con IDs/opciones. ready_for_answer
sólo se anuncia cuando la ejecución está waiting_input bajo la versión actual; una
pregunta durante el cierre todavía aparece, explicando por qué no puede responderse.
El controlador de respuesta conserva sus propias comprobaciones de alcance/versión;
la bandeja nunca concede autoridad por sí misma.

Se muestran todas las solicitudes pendientes, con paginación por ID estable. Las
respuestas registradas y preguntas vencidas salen de la bandeja. Una escritura de
metadata invalidada por la migración 29 también vence su pregunta. El proyecto ajeno
no aparece. No se usa semejanza de texto para reemplazar una respuesta o asociación.

Las solicitudes del motor anterior permanecen visibles como historial pendiente,
con título/cuerpo, sin inventar tarea o versión. No se convierten sus opciones de
objetos a etiquetas que luego puedan confundirse con valores. Tampoco se habilita
el antiguo POST para responder preguntas nativas. Su migración y respuesta tipada
siguen pendientes; el chat anterior ya tenía ese historial en modo de sólo lectura.

## Una conversación que no presupone contexto compartido

La página selecciona una tarea existente del proyecto actual, nunca a partir del
número del URL sin comprobar el catálogo del proyecto. Cambiar de proyecto remonta
selección/borradores; filtrar la lista no desmonta la tarea elegida. Abrir una tarea,
pregunta o hilo no inicia inferencia. Los controles de pregunta continúan usando
prepareAnswer y el endpoint de tarea/versión, separados del inicio de una solicitud.

El intercambio se lee como un documento cronológico, con emisor, recibo, tarea y
versión por mensaje. Un resultado anterior se rotula conservado; needs_review se
rotula propuesta, sin aceptación implícita. Mensajes de otra tarea en el mismo hilo
llevan aviso explícito. Las preguntas pendientes se presentan mediante sus controles,
sin repetir además el mismo texto del mensaje dentro de la cronología. Una propuesta
actual ya presente en el historial no se duplica; si falta el historial o falla su
lectura, el resultado durable conserva su presentación independiente.

La web explica el contrato actual: el siguiente inicio recibe tarea actual,
correcciones y respuestas, más los cambios de entrada registrados. Mostrar un mensaje
antiguo no equivale a comprobar que se entregó o aplicó al modelo. Queda pendiente
el snapshot integral de contexto efectivo y una política explícita de continuidad
conversacional; no se fabricó esa capacidad cambiando el diseño del chat.

Fuentes, correcciones, diferencias de metadata y recuperación reutilizan sus controles
existentes. No se infieren hipótesis/fuentes verificadas a partir del estilo de una
frase. Los datos de las imágenes son ficción de diseño y no aparecen en producción.
El archivo de hilos conserva lectura completa con errores/reintento visibles, sin
compositor que pueda activar roles del engine anterior accidentalmente.

## Verificación y límites

SQLite/HTTP prueban alcance, múltiples tareas, preguntas en cierre frente a listas
para responder, expiración/respuesta, cursor y datos anteriores sin autoridad
inventada. API sin sesión y con bearer se rechaza; la lectura no reserva inferencia.
React SSR prueba integración real del chat/controles, dos pendientes visibles,
versiones históricas, texto escapado, errores y rechazo de una tarea ajena en el URL.
No son pruebas de interacción de navegador. La selección y los cuatro conceptos
están en [el manifiesto](../design/concepts/chat/manifest.json).

El cliente consulta periódicamente el hilo elegido y la bandeja; invalida consultas
tras respuestas/corrección/Stop. Cada página tiene su snapshot, sin prometer uno
común entre varias páginas mientras cambia el proyecto. Faltan catch-up por eventos,
paginación/retención integral de hilos y workspaces, continuidad efectiva al modelo,
migración de preguntas heredadas, interacción/teclado/foco/zoom/lector de pantalla
y comprensión observada. CUA sigue sin navegador; design-qa.md conserva resultado
blocked. No se presenta este piloto como una interfaz aceptada visualmente.
