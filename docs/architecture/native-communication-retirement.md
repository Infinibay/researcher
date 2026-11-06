# Retirada de herramientas antiguas de comunicación

Se retiran los siete módulos de `backend.tools.communication` (seis herramientas)
y los dos registros antiguos de preguntas/respuestas. El reemplazo conserva
mensajes, preguntas humanas y lectura de avisos mediante el host nativo; no
mantiene la activación de agentes por texto, identidades supuestas ni respuestas
reutilizadas sólo por parecerse a otra pregunta. No se borran tablas ni datos.

| Herramienta anterior | Recorrido vigente | Cambio deliberado |
|---|---|---|
| `SendMessageTool` | `researcher_peer_message_send`, registro canónico y recibo transaccional | Emisor real del intento y destinatario admitido exacto. Se retiran resolución por nombre/rol, broadcast implícito y prioridad conversacional como influencia sobre ejecución. |
| `ReadMessagesTool` | `researcher_peer_messages`, `researcher_peer_message_read`, acuse explícito y dos lecturas de avisos | Leer no reconoce recepción ni prueba comprensión. Páginas y ventanas exponen el texto todavía no leído. |
| `AskTeamLeadTool` | Pregunta informativa a una ejecución explícita, con respuesta al ID exacto | No hay espera bloqueante, respuesta cacheada por texto ni permiso al vencer un timeout. |
| `AskProjectLeadTool` | El mismo contrato de pregunta/respuesta | No se lanza un Crew ni otro agente desde el envío. La delegación de trabajo pertenece a las operaciones tipadas del host. |
| `AskUserTool` | `researcher_ask_user`, preguntas durables, pausa del intento y respuesta versionada del propietario | Pregunta/chat/intención de pausa comparten una transacción; el host verifica el cierre de los procesos. No hay polling ni reutilización semántica de una respuesta anterior como respuesta actual. |
| `ReplyToUserTool` | Progreso nativo y entrega durable del resultado en la conversación del propietario | El fin de un turno no completa ni acepta la tarea. Se retira el bloqueo de120 segundos por agente/proyecto entre respuestas y la instrucción de cerrar mediante `step_complete`. |

La lectura de avisos era una capacidad útil adicional de `ReadMessagesTool`:
`researcher_notices` lista los del proyecto y los explícitamente globales, con
vigencia y paginación; `researcher_notice_read` recupera título/contenido completo
en ventanas. El nombre histórico del creador no verifica su identidad. Se
conservan prioridad, vencimiento y estado observado como contexto, sin autoridad
implícita, reconocimiento de lectura ni garantía de inmutabilidad. No se añaden
escrituras de avisos en este bloque.

`QuestionRegistry` y `ResponseEventRegistry` ya no tienen consumidores activos
tras la migración. Se retiran la propagación automática de respuestas parecidas
y las esperas por hilo en memoria. El listener histórico conserva su forma de
evento con `is_question=false`, pues ya no existen esos waiters; mantiene el
guard que excluye mensajes nativos. El historial de `clarification_questions`
queda intacto y sus lectores históricos no se convierten en política nativa.

Se retiran31 tests de los contratos anteriores. El diálogo completo se conserva
en una prueba nativa con pregunta/respuesta exactas, acuse de ambos participantes,
inbox sin pendientes y ausencia de cambio de estado de trabajo. No se cuenta
ningún test eliminado como un fallo reparado. La ausencia de módulos está probada
y el barrido AST de670 archivos Python no encuentra imports estáticos restantes,
incluidos relativos y tests; no es una afirmación sobre clientes externos o
imports construidos dinámicamente.

[Resultados](../modernization/communication-retirement-results.json),
[paquete instalado](../modernization/communication-retirement-packaging.json) y
[alcance de imports](../modernization/communication-retirement-imports.json).
El lote conserva un fallo del detector de ping-pong antiguo (`allow` frente a
`escalate`), reproducido en la instalación previa `ad86106`. Esa limitación sigue
en el trabajo principal de servicios heredados/operación, no en pulido.

La retirada aquí es de herramientas y registros antiguos, **no de todo el
subsistema de comunicación**. `CommunicationService`, sus lectores de historial,
`LoopGuard`, otros helpers y rutas internas usadas por la CLI siguen pendientes
de su migración/retirada. Tampoco se declaran cerrados los escenarios amplios,
comprensión humana, eficacia con modelos, restore real ni aceptación de páginas.
