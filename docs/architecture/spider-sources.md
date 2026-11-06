# Captura avanzada de páginas con Spider

Fecha: 2026-11-06. `researcher_capture_spider` sustituye `SpiderScrapeTool` sin
CrewAI ni SDK de Spider. La capacidad de capturar una página dinámica se conserva
como integración opcional; captura web ordinaria y Ken mantienen sus funciones.
El transporte acotado es compartido con Context7 en `provider_http.py`.

## Uso y configuración

Configurar en el entorno del **servidor**, antes de arrancarlo:

```sh
export SPIDER_API_KEY='clave-del-proveedor'
export SPIDER_MAX_CREDITS=100
```

El nombre histórico `INFINIBAY_SPIDER_API_KEY` también se acepta; la clave nueva
tiene prioridad si contiene un valor. No se carga una clave desde argumentos del
modelo ni se instala un SDK durante una llamada. La lectura del entorno no
supone que un fichero `.env` haya sido cargado: debe hacerlo el launcher usado
por el operador. El límite predeterminado es 100 créditos por petición/página;
el operador puede configurar otro valor finito y positivo. Spider tiene cuota
propia, separada de la suscripción OpenAI. La ausencia de clave o un presupuesto
inválido producen un error explícito, sin petición al proveedor.

```text
researcher_capture_spider(
  operation_key="manual-timeout-v1",
  url="https://docs.example.org/app",
  mode="browser",
  format="markdown"
)
```

`smart` permite al proveedor elegir HTTP o navegador; `browser` pide renderizado
JavaScript y `http` solicita recuperación ordinaria. `format` admite `markdown`
o `text`. Leer el `source_id` devuelto mediante `researcher_source_read`, siguiendo
su paginación. Para crear un hallazgo, usar después `researcher_finding_record`
con una cita exacta de esa fuente. Se reemplazan así los parámetros históricos
`store_as_finding/topic`, evitando convertir una captura automáticamente en una
afirmación científica sin evidencia explícita.

La ruta es `POST /api/research-tools/sources/spider`; proyecto, tarea, actor y
permiso `sources.capture` se obtienen del grant del host. Investigación,
investigación exploratoria y desarrollo reciben la herramienta; los catálogos
de revisión no obtienen una capacidad nueva para adquirir fuentes.

## Contrato y evidencia

La llamada utiliza únicamente `POST https://api.spider.cloud/scrape`, para una
URL HTTPS pública. Se comprueban formato y DNS públicos del objetivo y todas las
respuestas DNS del proveedor; la conexión TLS al proveedor usa la dirección
verificada. Una coma literal se rechaza porque la API la interpreta como batch;
codificar las comas que formen parte del path/query de una única URL. No hay
cookies, headers del usuario, scripts, crawling, conectores de almacenamiento ni
extracción mediante otro modelo dentro de esta herramienta.

La API oficial distingue la captura de URLs concretas del rastreo de enlaces y
expone los modos de petición indicados. Los parámetros `max_credits_allowed` y
`max_credits_per_page` acotan créditos en el proveedor; `request_timeout` se mide
en segundos. Se verificó el contrato documental en la fecha indicada:
[Scrape](https://spider.cloud/docs/api/scrape/),
[parámetros](https://spider.cloud/docs/api/),
[modos de renderizado](https://spider.cloud/api/scrape/).

El host impone 12 segundos y 1 MB de respuesta JSON; solicita al proveedor un
timeout de 10 segundos, sin sesión persistente ni ejecución en background.
No sigue redirects del endpoint ni reintenta peticiones. La respuesta debe
contener exactamente una página, con estado satisfactorio, sin error declarado
y contenido de texto no vacío. No se acepta un lote parcial, una página fallida,
contenido inválido ni texto mayor de 200.000 bytes. Una captura no demuestra
que el proveedor haya resuelto un desafío, mostrado todos los elementos o leído
correctamente una página: eso requiere evaluación independiente.

Se guarda el campo `content` sin modificar, URL solicitada y URL declarada por
Spider, parámetros efectivos, estado y costes informados, hash de la respuesta
JSON y su tamaño. No se guarda todo el JSON original como otro documento; el
hash identifica la respuesta de origen y las citas usan el texto extraído.
Costes ausentes quedan desconocidos. Renderizado, redirects, subrecursos, DNS
remoto y costes son afirmaciones del proveedor, no observaciones independientes
del host. Comprobar DNS local no prueba qué resolvió el servicio remoto. El texto
de la página sigue siendo evidencia no confiable, nunca instrucciones del agente.

Un recibo guardado se recupera sin otra consulta, incluso después de quitar la
clave. La misma clave de operación con otra URL/modo/formato produce conflicto.
Se comprueba autoridad antes de adquirir y al guardar; una revocación impide
persistir una respuesta tardía. La operación permanece registrada hasta cerrar
la conexión. Una parada local no demuestra cancelación o reembolso remoto.
Interrupciones o carreras anteriores al commit pueden consumir cuota adicional;
los límites por petición no sustituyen los presupuestos agregados del engine.

## Retirada y comprobaciones

Se retiran el módulo anterior y sus tres pruebas específicas de delegación al
SDK; sus identidades/hashes se conservan en el [inventario](../modernization/spider-retirement.json).
No se cuentan como reparación de fallos históricos. Se conservan las pruebas
del otro scraper antiguo y todos los registros de fuentes/hallazgos.
Se elimina el extra `spider`: el lock retira `spider-client`, `spider-browser` e
`ijson`, sin actualizar las versiones de los paquetes restantes. El extra
`legacy` continúa porque otras herramientas e índices aún lo necesitan.

El recorrido de prueba conserva MCP, cliente HTTP asíncrono, API, parsing HTTP,
SQLite y citas reales; sustituye los bytes del proveedor y su DNS. Verifica
modos/formatos, límites, errores, alcance, recuperación del recibo y revocación.
Los ensayos existentes de Context7 también ejercitan el cierre y los límites
del transporte compartido. [Resultados](../modernization/spider-results.json),
[paquete instalado](../modernization/spider-packaging.json).
No hubo consultas a Spider ni modelos reales. Disponibilidad y calidad de
renderizado externas, presupuestos globales y aceptación integral siguen abiertos.
