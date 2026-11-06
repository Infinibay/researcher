# Comunicación e historial sin los servicios antiguos

Se retiran nueve módulos: `service`, `thread_manager`, `loop_guard`, `listeners`,
`notifications`, `protocol` y `brainstorm_coordinator` de comunicación, más
`flows/event_listeners` y `flows/listener_base`. Las funciones nativas de mensajes,
notas del propietario y comprobación de procedencia permanecen. No se elimina
ningún dato histórico ni se cambia el esquema.

## Capacidades y decisión

| Responsabilidad antigua | Destino |
| --- | --- |
| Envío por identificadores/roles supuestos | Mensajería nativa con destinatarios admitidos, emisor del intento, contexto, pregunta antecedente y recibos exactos. |
| Detección de ping-pong y mensajes repetidos | Los mensajes nativos no disparan agentes. Sus límites de capacidad, claves de operación y acuses explícitos se conservan; los presupuestos globales siguen en su bloque principal. |
| Check-in con un supuesto líder y aprobación textual | Instrucción/contexto conservados, propuesta revisable, corrección, revisión independiente y aceptación nativas. Comprensión, recepción y permiso no se equiparan. |
| Notificación a un agente, rol o todo el equipo | Mensaje dirigido al destinatario real o proyección del evento al propietario. No se conserva el broadcast como asignación implícita. |
| Brainstorming iniciado por estancamiento o etiquetas de tareas | Planificación exploratoria admitida explícitamente. Un temporizador, etiqueta de finalización o mensaje no autoriza otra ejecución. Los registros históricos se conservan. |
| Polling y traducción de cambios a trabajo de agentes | Coordinación y eventos durables del runtime nativo. El `EventBus` compartido sigue sirviendo proyecciones existentes, sin importar ni arrancar pollers. |
| Leer mensajes históricos por destinatario | `OwnerHistory.legacy_inbox`, mediante la ruta autenticada del propietario. Es un filtro histórico y no una identidad de agente nativo. |
| Archivar un hilo | `OwnerHistory.archive`, con proyecto real, transacción y evento durable; no cancela trabajo ni confirma comprensión. |
| Parar un controlador ya registrado | `FlowManager` conserva referencias y observa el cierre real, aunque la fábrica de listeners ya no exista. |

Las búsquedas de consumidores se verificaron en el worktree de implementación:
el índice Ken del checkout original no representa automáticamente estos cambios.
El análisis AST incluye imports relativos y tests; imports dinámicos o usuarios
externos desconocidos quedan fuera de esa evidencia.

## Correcciones necesarias para conservar el contrato

El archivado anterior recibía `project_id`, pero actualizaba por `thread_id`
únicamente. La prueba reprodujo que una petición con otro proyecto devolvía 200
y archivaba el hilo. Ahora un hilo ausente o de otro proyecto devuelve 404 sin
modificarlo. La actualización y `conversation.archived` se confirman juntas;
si falla el evento se revierte el archivo. Repetir la petición no añade otro
evento. El mensaje, su cuerpo y su acuse permanecen; las ejecuciones siguen en
su estado real. Contestar dentro de una conversación cerrada se rechaza mediante
el contrato nativo existente, sin inventar silenciosamente otra conversación.

El lector histórico conserva filtros de destinatario/rol, marcas antiguas de
lectura y límite, ordenando por ID. Además de los marcadores de compatibilidad,
comprueba las relaciones canónicas de conversaciones e intercambios nativos:
quitar metadatos de una fila no la convierte en mensaje histórico. La vista del
propietario sigue mostrando ese mensaje con su procedencia y recibo nativos.
Leer el historial no escribe marcas de lectura ni activa trabajo.

Los imports de `EventBus`, `FlowEvent` y su instancia pasan al módulo que los
implementa. Se conservan sus siete pruebas y el recorrido de reconexión WebSocket.
La prueba de un controlador registrado usa un trabajador real: mientras ignore
Stop, permanece registrado y se informa que sigue abierto; sólo se libera la
referencia después de observar su terminación. El alcance continúa siendo los
controladores registrados, no una prueba de ausencia global de procesos viejos.

## Evidencia y trabajo restante

Se retiran 54 funciones de test específicas de implementaciones eliminadas;
no se cuentan como fallos corregidos. Se conservan las pruebas de mensajes,
preguntas, notas, propuestas, correcciones, contexto y controles del propietario.
Las nuevas pruebas cubren archivo por proyecto, repetición, rollback, historial
y conservación de identidad nativa después de quitar metadatos.

Véanse [resultados](../modernization/communication-services-results.json),
[paquete instalado](../modernization/communication-services-packaging.json) e
[inventario de módulos y tests retirados](../modernization/communication-services-imports.json).
Los cinco fallos de helpers/routers de flows que se reproducen en el paquete
anterior siguen como trabajo principal. No se modifica su semántica para volver
verde este corte. No hay evaluación con modelos, comprensión humana, aceptación
global ni cierre de los 43 escenarios amplios.

Continúan los helpers y entradas históricas de flows, los controladores de
autonomía restantes, operación, migración/restauración, historial completo y
presupuestos, evaluación integral y aceptación de páginas. Los avisos de estilo
quedan para la pasada final, después de todas las capacidades principales.
