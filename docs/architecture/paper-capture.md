# Captura de artículos por URL, DOI o arXiv

`researcher_capture_paper` sustituye el recorrido de localizadores de `read_paper`
en la fachada nativa del producto. No conecta el antiguo agente CrewAI a un grant
ambiental ni declara migrados sus roles/flows. El catálogo de negocio pasa a doce
herramientas; [schema y anotaciones reales](paper-tool-schema.json). El modelo no
elige proyecto, tarea, actor, credenciales o rutas del host.

La llamada exige `operation_key` y exactamente uno de `url`, `doi`, `arxiv_id` no
nulos. Se rechaza una combinación ambigua en lugar de priorizar silenciosamente
arXiv sobre DOI sobre URL, como hacía el lector anterior. El schema de firma muestra
campos opcionales; la exclusión mutua se valida en el servidor, no sólo en el prompt.

Ejemplos de entrada:

```json
{"operation_key":"paper-tax-v2","arxiv_id":"2301.07041v2"}
```

```json
{"operation_key":"paper-example","doi":"10.1000/example"}
```

Son ejemplos de formato, no afirmaciones de existencia, contenido o pertinencia.
Los ids arXiv modernos y de archivo conservan la versión explícita. Sin versión se
registra `latest_at_capture`: sólo se conoce la revisión capturada, no se promete
que siga siendo la última. Esa distinción sigue la [documentación de identificadores
de arXiv](https://info.arxiv.org/help/arxiv_identifier.html).

Un DOI se trata como identificador suministrado. El sufijo se codifica en UTF-8 y
percent-encoding para que `?`, `#`, `%`, barras y segmentos `..` no cambien la sintaxis
HTTP. No se cambia la caja del identificador ni se adivina un registro bibliográfico.
La [documentación de resolución DOI](https://doi.org/help.html) explica la necesidad
de codificar caracteres reservados/no ASCII; el [manual DOI](https://www.doi.org/doi-handbook/html/)
no establece un límite universal de longitud. El producto sí limita DOI a2048 bytes
UTF-8, URL codificada a4096 bytes y arXiv a256 caracteres. Son límites de aplicación,
no un validador completo de registro DOI. Se rechazan controles/espacios internos.

`ResearchService` comparte entre captura web y de artículos el mismo camino de
lookup de recibo, adquisición y commit. La clave se conserva al recuperar una respuesta
perdida; cambiar localizador o cambiar de entrada de captura con esa clave produce
conflicto. Una nueva captura deliberada necesita una clave nueva. Una repetición
confirmada utiliza el snapshot existente sin descargar otra vez, incluso para un
identificador arXiv sin versión que hoy apunte a otra revisión.

El servicio reutiliza `PublicWebFetcher` y el worker PDF existentes: HTTPS público,
DNS y conexión fijados, validación de cada redirección, bytes/plazo/CPU/AS/IPC,
propiedad del trabajo y revalidación del grant al guardar. Resolver DOI/arXiv no
elude restricciones de red ni añade cookies, claves, login o bypass de paywalls.
HTTP inseguro o una redirección privada fallan explícitamente. El parser no hace OCR.

La fuente conserva URL solicitada, URL final, hash binario/texto, MIME y páginas
cuando hay PDF. Añade `provenance.paper_request` con tipo, valor normalizado, política
de versión e `identifier_verified:false`. Esto registra qué se pidió; no prueba que
el destino corresponda al artículo, su autoría, revisión por pares o calidad científica.
Un DOI puede devolver una página HTML con sólo un resumen. Se captura como HTML;
no se transforma en una afirmación de acceso al texto completo. Las citas deben
provenir del texto guardado y los informes permanecen como borradores.

El prompt nativo distingue esos límites y mantiene una advertencia separada: la
búsqueda actual de fuentes es literal; una frase ausente no demuestra ausencia del
concepto. No se presenta como sustituto completo de `pdf_search` con embeddings.
No se introduce inferencia anidada ni se utiliza la suscripción para una API de
embeddings. El cambio de catálogo/instrucciones altera sus hashes; una sesión con
contratos congelados anteriores no obtiene herramientas nuevas de forma implícita.
El código de continuidad compara catálogo e instrucciones con el contrato guardado;
no se ensayó aquí una actualización de hilos de una versión anterior. No se promete
compatibilidad de reanudación entre catálogos distintos.

## Consumidores y alcance pendiente

| Consumidor observado | Dependencia anterior | Estado |
| --- | --- | --- |
| `backend.tools.WEB_TOOLS` → rol `researcher` | `ReadPaperTool` | Se conserva hasta migrar ese rol/flow; el recorrido nativo ya tiene captura por los tres localizadores |
| `backend.tools.RAG_TOOLS` → rol `researcher` | `PDFSearchTool` y parsers RAG | Pendiente de recuperación documental equivalente y formatos restantes |
| Rol `research_reviewer` | `PDFSearchTool` explícito | Pendiente de migrar revisión científica y herramientas de lectura/revisión |
| `backend.agents.base` → `get_tools_for_role` | Instancia las listas anteriores | No se redirige a credenciales globales ni se da por retirado el motor antiguo |
| Exportaciones `backend.tools.web`, `backend.tools.rag`, `backend.tools` | API Python pública anterior | Conservadas; la ausencia de llamadas directas no demuestra ausencia de consumidores externos |

Se inspeccionaron registros/roles y coincidencias literales de nombres/clases en
`backend` y `scripts`; no se afirma un inventario de integraciones externas. Los
flows heredados de investigación y sus prompts todavía deben migrarse junto con
los roles. La búsqueda semántica, revisión científica, políticas completas de robots/
rate-limit y formatos adicionales no quedan terminados por esta entrega.

[Resultados y límites](../modernization/paper-results.json),
[paquete](../modernization/paper-packaging.json),
[matriz completa](capability-matrix.md).
