# Captura nativa y retirada de herramientas web antiguas

El paquete `backend.tools.web` se retira después de trasladar sus capacidades
útiles al runtime nativo y a las fuentes canónicas. No se modifican registros
históricos, la tabla `web_cache` ni hallazgos existentes.

| Capacidad anterior | Recorrido actual |
| --- | --- |
| Búsqueda Serper/DDG | Búsqueda de Codex con modo explícito y observaciones atribuidas. No hay fallback a otro proveedor. |
| Fetch y scraping ordinario | Captura HTTPS pública con robots, cuota compartida, DNS/TLS fijados, límites y Stop. HTML se extrae localmente en el worker acotado. |
| HTML legible con enlaces/tablas | `trafilatura` se conserva como dependencia del parser nativo. Produce un snapshot Markdown; las citas se refieren a ese texto normalizado. No descarga enlaces ni ejecuta scripts. |
| Páginas dinámicas | Spider opcional, con comprobación inicial local, parámetros explícitos y costes/procedencia atribuidos. |
| Artículos por URL/DOI/arXiv | Resolución nativa y captura HTML/PDF; páginas y citas verificables en el snapshot. |
| Investigación compuesta | Investigación admitida por el runtime, con descubrimiento, captura, hallazgos citados e informe draft. |
| Ingesta automática de scraping | Fuente capturada y hallazgo explícito con cita. Una descarga no se convierte por sí sola en observación científica ni se trunca silenciosamente. |

## Spider comparte la política del host

Antes del POST de pago se comprueban el destino inicial y sus reglas de robots.
La consulta de robots y el POST consumen el mismo presupuesto de inicios HTTP
que la captura directa. Se conservan el plazo original y la operación de Spider:
Stop durante robots espera el cierre del recurso y no inicia el POST posterior.
La clave del proveedor nunca se envía al sitio consultado.

El host solicita `respect_robots=true` y `user_agent="Researcher/0.1 source-reader"`;
ambos parámetros están documentados por
[Spider](https://spider.cloud/docs/api/). Esa solicitud no demuestra cumplimiento
remoto. La procedencia distingue la decisión local inicial de las redirecciones,
subrecursos, DNS, renderizado y costes declarados por el proveedor. Una parada
local tampoco demuestra cancelación ni reembolso remoto.

## Extracción y compatibilidad

HTML usa el mismo `DocumentParser` que ya poseía límites de CPU, memoria, plazo,
entrada/salida y cierre del worker. La página se decodifica según su charset y
se envía como UTF-8 al parser; el hash de adquisición sigue identificando los
bytes originales. El resultado conserva enlaces y tablas, pero no representa la
disposición visual ni todo el contenido omitido por la extracción de lectura.
Una página sin texto legible falla explícitamente. Markdown puede escapar
caracteres como `_`; el modelo debe leer y citar el snapshot guardado.

Los formatos y parámetros de los wrappers viejos no se mantienen como API
alternativa. Los consumidores propios pasan por el contrato canónico anterior;
los consumidores externos/dinámicos no quedan certificados por el análisis de
imports. Los datos que sólo existan en `web_cache` siguen pendientes de migración
o exportación junto a las otras fuentes históricas, sin inventar su procedencia.

## Verificación

Se retiran diez módulos y veinte funciones de prueba de wrappers, incluyendo
una prueba con dos variantes del handoff antiguo. Su retirada no cuenta como
reparación de fallos. El análisis estático de imports no encuentra consumidores
restantes en backend/scripts. El lock pasa de 179 a 177 paquetes: elimina `ddgs`
y `primp`, sin cambiar versiones de los restantes. `trafilatura` conserva ahora
un consumidor nativo; las cinco dependencias del extra `legacy` siguen pendientes.

Pasan 218 pruebas seleccionadas en fuente y 218 en la instalación no editable,
sin omisiones: HTTP/MCP → fuente → cita, parsers y Stop, búsqueda nativa y sus
observaciones persistidas. DNS, sockets públicos, respuestas de proveedor y
generación/Ken están controlados. El SDK real se consulta sin cuenta para su
configuración; no hubo llamadas de pago a modelos o proveedores. El paquete final
añade sólo un docstring de test respecto al ejecutado: se verificó ese diff y
sus hashes sin repetir la batería.

No es una suite global ni aceptación de las doce páginas o de los 43 escenarios.
Migraciones/restore, datos históricos, otras familias de herramientas, operación
y evaluación real/humana/científica siguen dentro del plan.

Evidencia: [retirada](../modernization/web-retirement.json),
[fuente](../modernization/web-retirement-results.json),
[paquete](../modernization/web-retirement-packaging.json),
[docstrings](../modernization/web-retirement-docstrings.json).
