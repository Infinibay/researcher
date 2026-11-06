# Documentación Context7 como fuentes del proyecto

Fecha: 2026-11-06. Sustituye `Context7SearchTool` y `Context7DocsTool`, que
dependían de CrewAI y suponían respuestas con una forma anterior. La integración
actual usa el MCP de negocio, la API local y el almacén canónico de fuentes.
No cambia el motor Codex ni reemplaza Ken para código local.

## Configuración y recorrido

Configurar `CONTEXT7_API_KEY` **en el proceso servidor**. Se acepta también el
nombre anterior `INFINIBAY_CONTEXT7_API_KEY`; el nombre nuevo tiene prioridad
cuando contiene un valor. Sin clave, la adquisición falla explícitamente antes
de resolver DNS. No se requiere instalar un extra ni otro SDK. No poner la clave
en prompts, argumentos de herramientas, configuración del actor o repositorios.
Es una integración opcional con cuota propia; la suscripción OpenAI no la paga.

1. `researcher_context7_search(operation_key, library_name, query)` guarda la
   respuesta de búsqueda. Por ejemplo, nombre `fastapi` y pregunta específica
   `How do I set a request timeout?`.
2. Leer el `source_id` devuelto con `researcher_source_read`; continuar mientras
   haya `next_offset`. Elegir un ID concreto a partir de los resultados.
3. `researcher_context7_docs(operation_key, library_id, query, format)` guarda
   la documentación. `format` admite `json` —predeterminado— o `txt`.
4. Leer esa fuente antes de citarla. Se integra con búsqueda, hallazgos y borradores
   existentes; una cita debe aparecer exactamente en el texto guardado.

Las rutas son `POST /api/research-tools/sources/context7/search` y
`POST /api/research-tools/sources/context7/docs`. Proyecto, tarea, actor y permiso
`sources.capture` proceden de la credencial emitida por el host. Investigación,
investigación exploratoria y desarrollo reciben las herramientas; los catálogos
de revisión no adquieren nuevas fuentes mediante ellas. El catálogo disponible
no demuestra que el servidor tenga configurado Context7.

## Evidencia, compatibilidad y límites

Se conserva la respuesta UTF-8 completa, con hash de bytes, URL/endpoint, petición,
tipo y proveedor. JSON conserva snippets, URLs, filtros y notas de versión;
texto conserva la representación recibida. Las reglas incluidas por el proveedor
son datos no confiables, no instrucciones del agente ni autorización del usuario.
Puntuaciones, actualidad y compatibilidad de versión no se verifican de forma
independiente. No convertir una búsqueda vacía en ausencia demostrada de una
biblioteca ni una respuesta satisfactoria en una versión confirmada.

La documentación oficial mantiene el recorrido de selección de biblioteca en
`/api/v2/libs/search` y `/api/v2/context`; las respuestas JSON actuales usan
`results` o `codeSnippets`/`infoSnippets`, respectivamente. Puede devolver una
versión distinta de la pedida, descrita en su respuesta.
[Guía API](https://context7.com/docs/api-guide),
[búsqueda](https://context7.com/docs/api-reference/search/search-for-libraries),
[contexto](https://context7.com/docs/api-reference/context/get-documentation-context).
Contrato consultado en la fecha indicada; los ensayos no contactan ese servicio.

El adaptador sólo conecta a `context7.com:443`, con todas las respuestas DNS
públicas verificadas y la dirección elegida fijada a la conexión TLS. No sigue
redirecciones ni usa proxies/cookies del entorno. Presupuesto de 12 segundos y
200.000 bytes por respuesta, sin descompresión, recorte ni retries automáticos.
Los estados 202, 301, errores de credencial, cuota y proveedor se explican sin
copiar cuerpos de error ni revelar la clave. Una petición que excede límites,
termina incompleta o tiene un schema desconocido no produce una fuente.

El recibo ya guardado se devuelve sin otra consulta, incluso si después falta
la clave del proveedor. Cambiar el contenido de una petición con la misma clave
de operación produce conflicto. La autorización se revisa al guardar; una
revocación durante la adquisición impide persistir la respuesta tardía. El host
mantiene la operación registrada hasta cerrar la conexión: Stop no significa
que el proveedor haya cancelado su propio trabajo o devuelto su cuota. Peticiones
concurrentes o interrumpidas antes del commit pueden consumir cuota adicional;
no se promete ejecución exactamente una vez en el servicio externo.

Se retiran los tres módulos Python anteriores; imports externos de esas clases
deben migrar a las herramientas descritas. Se conserva el mapping de nombres en
plantillas históricas, fuera de la política nativa, y todos los datos existentes.
[Inventario de retirada](../modernization/context7-retirement.json).

## Verificación

Los tests conservan el parsing HTTP real y sustituyen sólo DNS/socket del
proveedor. El recorrido integra MCP → cliente HTTP asíncrono → API → adquisición
→ SQLite → cita de hallazgo. Comprueba JSON/texto, versión no confirmada, respuestas
incompletas, cuota, redirects, alcance, recibos, revocación y cierre físico.
La selección incluye captura web/PDF existente, catálogo, MCP stdio y un turno
de investigación controlado. [Resultados](../modernization/context7-results.json)
y [paquete instalado](../modernization/context7-packaging.json).

Esto no demuestra disponibilidad real del proveedor, calidad documental,
comprensión humana ni aceptación integral. Spider, las demás herramientas e
índices antiguos y la retirada final de dependencias siguen pendientes.
