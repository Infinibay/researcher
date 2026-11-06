# Retirada de la API interna y del CLI de pods antiguos

Se retiran los tres grupos `/api/internal`, sus 13 operaciones y
`scripts/infinibay_cli.py`. El CLI del propietario en `backend/cli` permanece:
usa la sesión emparejada y las operaciones nativas. El MCP de negocio exige la
identidad y los permisos del intento concedidos por el host.

La API antigua tenía autenticación exterior de propietario, pero sus cuerpos
aceptaban identificadores y decisiones de agentes separados del contrato nativo.
Mantenerla registrada conservaba una segunda implementación para hallazgos,
mensajes, aprobación y publicación. El CLI de pods tampoco aportaba la sesión
de propietario ni la autorización del intento que necesitan esos contratos.

## Destino de las capacidades

| Entrada retirada | Contrato conservado |
| --- | --- |
| Preguntar a team/project lead y enviar chat | Destinatarios admitidos y mensajes nativos, con emisor determinado por el host, pregunta antecedente, contexto y acuse. No se inventa un destinatario a partir de un nombre de rol. |
| Leer chat desde el CLI | Lectura de mensajes nativa y conversación del propietario con procedencia y ventanas explícitas. |
| SQL arbitrario de lectura | Herramientas tipadas de tareas, fuentes, hallazgos, informes, Wiki y búsqueda conjunta. No se transfiere la capacidad de consultar todas las tablas. |
| Registrar y consultar hallazgos | `researcher_finding_record/list/query/read` con fuentes, proyecto e identidad del intento comprobados por el host. |
| Validar/rechazar hallazgos | Revisión independiente del contenido exacto y decisión registrada. El estado administrativo no certifica verdad científica. |
| Aprobar/rechazar tareas | Revisión y aceptación del propietario sobre el resultado observado. Las correcciones conservan contexto e historia; un texto o una etiqueta no completa trabajo. |
| Crear PR desde el CLI/API interna | Publicación nativa vinculada a la aceptación exacta, identidad del repositorio y resultado remoto recuperable. |
| Guardar/cargar notas de sesión | `researcher_continuity_save/read`: notas acotadas y atribuidas que separan observaciones, supuestos y próximos pasos; no conceden autoridad. |
| Leer tareas y añadir comentarios desde el CLI | `researcher_task_list/read/comment` y el espacio de tareas del propietario. |
| Cambiar estado desde el CLI | Transiciones controladas por ejecución, revisión y aceptación nativas; se elimina el cambio genérico como interfaz de agentes. |

No se eliminan tablas ni filas, tampoco notas de sesión, mensajes o hallazgos
históricos. La restauración de un despliegue anterior sigue pendiente en su
bloque principal; retirar endpoints no equivale a migrar sus datos.

La imagen histórica conserva las utilidades de comandos/archivos, pero deja de
instalar el CLI retirado, el antiguo lanzamiento MCP con fastmcp y Claude Code.
No se sustituye por una copia del MCP nativo sin su paquete ni autorización:
el host nativo configura Codex, Ken y el MCP de negocio. El rediseño operativo
y la construcción/aceptación de imágenes siguen pendientes; aquí no se afirma
haber construido o validado un contenedor.

## Verificación

La prueba HTTP nueva usa una sesión real de propietario y CSRF. Comprueba que
los 13 métodos/rutas no están publicados ni son ejecutables y que las peticiones
no alteran el volcado de la base ya inicializada. La respuesta es 404, o 405 para
POST cuando está instalado el fallback GET de la SPA; ninguna devuelve éxito.
Las interfaces nativas permanecen publicadas y tienen pruebas separadas de sus
comportamientos. No se eliminó ningún caso de test.

La batería incluye permisos de propietario, MCP, contexto/comentarios/continuidad,
búsqueda conjunta, mensajes, terminal, revisión y publicación con respuestas
remotas controladas. Los dos fallos de migración/inversa se reproducen en el
paquete instalado anterior `852c34a`, verificando sus bytes antes de compararlo.
Quedan en el trabajo principal de datos, sin relajar sus comprobaciones.

Evidencia: [resultados](../modernization/internal-retirement-results.json),
[paquete instalado](../modernization/internal-retirement-packaging.json) e
[inventario de retiradas/imports](../modernization/internal-retirement-imports.json).
No hay aceptación global, evaluación humana/científica ni llamada a modelos
reales en este corte. Continúan los servicios y listeners de comunicación,
lectores, helpers de flows y demás consumidores antiguos; no se declara retirado
todo ese subsistema.
