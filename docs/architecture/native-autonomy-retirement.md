# Autonomía nativa y retirada de los lectores antiguos

Se retiran 54 módulos: los doce de autonomía, el scope de cancelación que sólo
usaba ese loop, 39 plantillas/constructores históricos de prompts y los dos
configuradores de proveedor antiguos. No se eliminan tablas, eventos, mensajes,
snapshots ni ajustes guardados. El catálogo nativo conserva sus instrucciones.

## Responsabilidades conservadas

| Componente retirado | Destino o razón de retirada |
| --- | --- |
| `AgentLoop`, evaluadores por rol y watchdog | Admisión, coordinación, intentos y recuperación del runtime nativo. Las entradas antiguas ya devolvían la política del propietario; no se conserva otro scheduler. |
| Eventos, claims y handlers antiguos | Operaciones tipadas y eventos durables nativos. Los registros `agent_events` siguen siendo historia, sin replay ni conversión de mensajes en autorización. |
| Scavenger y recuperación por heartbeat | Observación y recuperación nativas con identidad del intento. La falta de un heartbeat antiguo no libera una tarea ni borra su asignación. |
| Proxy especial de DB de autonomía | Las entradas de proyecto retenidas usan directamente `backend.tools.base.db`. Ya no hace falta fabricar paquetes en `sys.modules` para evitar imports circulares históricos. |
| Hints por tarea usados sólo por handlers retirados | Se retiran con esos consumidores. Las entradas de proyecto todavía utilizadas mantienen `native_project_handoff`, `project_owner_entry` y `legacy_project_handoff`. Un hint no crea una ejecución. |
| Templates de seis roles, instrucciones de tecnologías y adaptación de pseudoherramientas | Catálogo versionado `backend/prompts/native.py` y políticas de capacidades nativas. Las revisiones históricas quedan archivadas; esas instrucciones no se concatenan al catálogo nuevo. |
| Resumen auxiliar y lector de contexto de las plantillas | Lectores actuales de conversación del propietario y entrada nativa atribuida. Se conservan los textos originales; no se genera un resumen como sustituto de comprensión compartida. Historial completo/presupuestos siguen siendo un bloque principal pendiente. |
| Fábrica/probes/ajustes de LiteLLM y metadata de capacidades antiguas | Configuración nativa de modelo y comprobación del protocolo real. No hay fallback hacia claves de API ni probes de esos proveedores. Sus ajustes históricos almacenados no se borran en este corte. |

Los consumidores se comprobaron en el worktree de implementación mediante
lectura y análisis AST, incluyendo imports relativos y tests. El grafo Ken del
checkout original sigue siendo una pista histórica, no evidencia del estado de
esta rama. No se afirma compatibilidad con imports dinámicos externos desconocidos.

## Parada: un registro de control, sin otro motor

`FlowManager` conserva el registro existente de controladores, hilos y señales
ya conocidos por la API. Se elimina el registro duplicado del antiguo manager
de loops junto con su fábrica, que ya no iniciaba esos loops. No se introduce
un sustituto que pueda recrearlos. No se promete migrar objetos de un proceso
antiguo mediante hot reload ni detectar procesos externos no registrados.

Una señal de Stop es una petición. Mientras el hilo siga vivo, el registro y el
bloqueo de admisión nativa permanecen. Sólo la observación del cierre permite
retirar la referencia. Los controles de un propietario opaco siguen sin presumirse
cerrados. Se conserva además el último snapshot histórico de un flow registrado.

La revisión encontró un fallo concreto de cierre: un hilo podía existir en
`_threads` sin entrada en `_flows`, `_autonomy` o `_listeners`, y el shutdown lo
omitía. La prueba lo reprodujo: su señal permanecía sin activar. Ahora
`registered_project_ids()` reúne las cuatro colecciones. El cierre consulta el
recibo y registra explícitamente si algún trabajador sigue terminando; ya no
anuncia éxito incondicional después de una espera agotada.

## Qué ocurre en los casos difíciles

- **El trabajador ignora temporalmente Stop.** Se activa su señal, se conserva su
  identidad y la admisión nativa sigue bloqueada. Al terminar realmente, una nueva
  observación permite retirar la referencia. No se modifica su historia en DB.
- **Sólo queda un hilo, sin objeto de flow.** El cierre de la aplicación también
  lo incluye; la prueba usa un hilo real retenido, no una etiqueta de estado.
- **Quedan mensajes o tareas antiguos pendientes.** No se recorren para arrancar
  agentes, reconocer mensajes ni reabrir tareas. El propietario puede consultar
  el material mediante los lectores existentes y admitir trabajo nativo explícito.
- **Una plantilla antigua contiene una aprobación o una instrucción de proveedor.**
  Queda archivada; no entra al catálogo ni permite llamar un proveedor alternativo.
  El catálogo nativo sigue diferenciando evidencia, ejemplos, supuestos y decisiones.

## Evidencia y límites

Se mantienen los recorridos de conversación autenticada, preguntas/contexto,
entradas congeladas, selección de políticas, investigación, planificación y
parada de trabajadores registrados. Las nuevas pruebas cubren el cierre omitido,
retención tras timeout, bloqueo nativo, invariancia de datos y ausencia de los
módulos retirados. Dos pruebas de la entrada de proyecto/parada se renombran y
conservan; los tests específicos de implementaciones eliminadas no se cuentan
como fallos reparados.

Véanse [resultados](../modernization/autonomy-retirement-results.json),
[paquete instalado](../modernization/autonomy-retirement-packaging.json),
[inventario e imports](../modernization/autonomy-retirement-imports.json) y
[docstrings](../modernization/autonomy-retirement-docstrings.json).
Las pruebas con generación controlada no prueban comprensión humana ni calidad
científica. No se da por aceptada ninguna página ni escenario amplio con este corte.

Siguen operación e imágenes, fixtures antiguos de integración, migraciones e
inversas, restauración real de datos, historial completo/presupuestos y evaluación
integral de modelos, personas, resultados y doce páginas. Los detalles secundarios
se resuelven después de todas las capacidades principales.
