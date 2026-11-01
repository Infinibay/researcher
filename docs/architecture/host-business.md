# Herramientas de negocio compartidas y HTTP del host

`host_business` conecta las herramientas de investigación al API local desde el
host. No crea un proceso MCP, otro loop LLM ni un cliente con credenciales dentro
de Codex. Recibe origen/token fijados por el host y un callback explícito para
retirar la autoridad viva del API antes de cerrar conexiones.

## Un contrato, dos transportes

`business_definitions.ResearchTools` contiene las11 firmas, descripciones y rutas
que antes estaban en `scripts/researcher_mcp_server.py`. Es un adaptador exterior:
traduce argumentos a HTTP y reutiliza el DTO de preguntas; no decide permisos,
evidencia, SQL, aceptación o publicación. Esas reglas siguen en los servicios/API.

El cliente del host deriva sus esquemas y validación estricta de esas firmas con
Pydantic. Omite títulos de anotación e inlines de los DTOs locales finitos para
exponer el mismo esquema compacto que FastMCP; conserva campos reales como
`title`. Tipos recursivos o referencias externas requieren una decisión explícita.
El proceso MCP conserva sus nombres y registra los mismos métodos, sin copiarlos.
La configuración y credenciales no son argumentos de ninguna herramienta.

El runtime principal importa el SDK MCP fijado para tipos de resultados, pero no
FastMCP4. El script conserva su entorno aislado: se añadieron explícitamente HTTPX
y Pydantic a su lock. Pydantic2.14.2/FastMCP4.1.4 se conservaron; no se bajó la
versión del script a la del runtime principal. La actualización queda offline y
reproducible. Esto no completa la instalación limpia del producto ni el empaquetado
de todos los consumidores CLI heredados.

## HTTP y cierre

El cliente asíncrono reutiliza `ResearcherEndpoint` del adaptador stdlib existente
para validar origen, token, rutas y JSON. Sólo admite HTTP numérico de loopback,
sin credenciales/path/query en el origen, proxy de ambiente, redirect o retry.
Cada petición conserva la clave que dio el llamador. Un error no confirma ausencia
de efecto y no genera otra clave.

Hay ocho solicitudes admitidas, sin cola ilimitada, hasta ocho conexiones/cuatro
keepalive y deadline de pared completo, con valor predeterminado15s y máximo180s.
El cuerpo de petición y la respuesta están limitados a1MiB; errores a64KiB. Se pide y exige encoding
identity y se leen chunks acotados. Una respuesta inválida, excesiva o no objeto
no se convierte en éxito. Los errores de validación conservan ubicación/mensaje
útiles, omiten el campo `input`, limitan texto y redactan el bearer conocido.

El peer valida el esquema antes de enviar HTTP y comprueba su autoridad antes y
después. Cerrar retira primero la autoridad viva proporcionada por el host,
cancela/draina solicitudes HTTP y cierra el pool antes de afirmar `closed=True`.
La espera del cierre está protegida de cancelación del consumidor. Un cierre que
falla no certifica limpieza ni revocación durable.

El callback debe retirar el grant real del API, por ejemplo `LiveGrants.withdraw`.
Un callback vacío en producción no prueba esa propiedad. Los servicios revalidan
los grants ligados a runtime dentro de sus transacciones, incluso después de
adquisición lenta o de esperar SQLite. Cerrar un socket no deshace un commit del
servidor; los recibos idempotentes y la reconciliación siguen siendo necesarios.

## Evidencia y siguientes conexiones

Las pruebas cubren capacidad, deadline, cierre con solicitudes pendientes, pérdida
de recibo, redirección, JSON/tamaño, credenciales y validación. Un recorrido con
API/SQLite reales captura un adjunto, crea finding e informe borrador, recupera
citas y repite la escritura sin duplicarla; rechaza otra referencia/proyecto y
credenciales revocadas. La tarea no se marca completada por devolver un informe.

Otro ensayo con Uvicorn real, cliente del host y MCP stdio en su lock comprueba
catálogos equivalentes y recibos compartidos. Retirar el grant vivo desde el host
bloquea lecturas posteriores desde MCP aunque la revocación SQL aún no se haya
persistido. Los datos, credenciales de herramienta y actores del ensayo son
sintéticos; no hubo generación ni acceso a la cuenta OpenAI.

Todavía faltan la composición de esta autoridad con el broker productivo y el API
de la aplicación, análisis/desarrollo retenidos, prueba conjunta real por
suscripción con Ken y medición de carga mixta. El API es un actor de control del
host: no se afirma inscripción completa de actores o generaciones por añadir un
cliente HTTP. Las fábricas productivas siguen pendientes de migración.

Evidencia: [contratos](../modernization/host-business-evidence.json),
[resultados](../modernization/host-business-results.json),
[ensayo HTTP/MCP](../modernization/host-business-live.json),
[paquete](../modernization/host-business-packaging.json).
