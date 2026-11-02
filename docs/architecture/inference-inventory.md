# Inventario de inferencia y servicios auxiliares

Estado: implementación parcial, con el primer recorrido de investigación conectado
al coordinador y API del propietario. Ver `native-runtime-boundary.md`.
No se afirma todavía que toda la aplicación use exclusivamente la suscripción.
Las rutas antiguas siguen presentes hasta migrar sus consumidores. Los ensayos
reales sí retiraron API keys y rechazaron proveedores alternativos.

## Rutas encontradas y destino

| Entrada y evidencia de código | Proveedor y credenciales actuales | Activación y límites actuales | Destino y comprobación pendiente |
| --- | --- | --- | --- |
| `backend/engine/llm_client.py::call_llm`, invocado desde `loop_engine.py` para ejecución, resumen y guardrail | LiteLLM; `LLM_MODEL`, `LLM_API_KEY`, URL y variables del proveedor vía `config/llm.py` | Un turno del motor; hasta cinco reintentos del cliente. Los contadores del loop no abarcan toda inferencia auxiliar | Retirar junto con LoopEngine. El runtime seleccionado hace inferencia; Researcher conserva presupuesto durable por operación/intento/proyecto. Probar silencio, reintentos y reinicio |
| `backend/agents/base.py` y `flows/helpers/reporting.py::build_crew` / `kickoff_with_retry` | CrewAI con el singleton `get_llm`; también memoria CrewAI | Flows y agentes antiguos; reintentos de kickoff pueden envolver otros reintentos | Migrar todos los flows a un servicio de ejecución con un único dueño. No conservar un coordinador CrewAI paralelo |
| `backend/prompts/team.py::_summarize_messages_llm` | `litellm.completion`, mismas credenciales; salida hasta 600 tokens | Construcción de contexto; caché en memoria por conversación | Contexto recuperable y resumen del runtime cuando haga falta, con referencia al rango resumido y correcciones vigentes. Probar que nunca se abre otro cliente de modelo |
| `backend/tools/web/deep_research.py::_run` y `_arun` | Síntesis con `completion` / `acompletion`; búsqueda y descarga independientes | Herramienta invocada por el agente; síntesis fuera del turno de inferencia que la solicitó | Capturas verificables por MCP, síntesis en el turno del runtime. Conservar fuentes y resultados parciales; no ocultar una llamada LLM dentro de una herramienta |
| `backend/knowledge/service.py::build_crew_memory_kwargs` | `crewai.Memory(llm=get_llm(), embedder=...)` | Creación de Crew/memoria; inferencia y embeddings transitivos de la librería | Retirar memoria CrewAI. Memoria explícita por proyecto y procedencia; recuperación determinista inicial, embeddings locales sólo con modelo fijado y reconstrucción probada |
| `backend/tools/rag/base.py::_OpenAIEmbeddingFunction` | `openai.OpenAI().embeddings.create`; API key del entorno y `EMBEDDING_BASE_URL` | Indexar/consultar PDF, CSV y directorios; singleton y colecciones Chroma | Retirar dependencia de embeddings remotos por defecto. La suscripción de Codex no habilita esta API. Parser local acotado y búsqueda recuperable; índices opcionales con modelo/dimensión/revisión explícitos |
| `backend/tools/web/crewai_tool_config.py`, usado por code docs, DOCX, JSON y XML | Adaptador CrewAI Tools configura embedder y opcionalmente LLM. `default` se traduce a **openai**, con `text-embedding-3-small` si no hay modelo | La herramienta documental construye un proveedor transitivo | Sustituir por extracción local y recuperación explícita. Probar arranque y consultas sin keys y bloquear cualquier cliente remoto accidental; no asumir que `default` significa local en esta ruta |
| `backend/tools/base/dedup.py::_get_embed_fn`, `embeddings.py`, búsquedas de findings/wiki | Chroma `DefaultEmbeddingFunction`, MiniLM local; puede requerir descargar los pesos | Duplicados y embeddings al escribir/buscar; no hay identidad de modelo/dimensión persistida con cada BLOB | Fijar activo/modelo y bootstrap fuera de la solicitud. Separar similitud de validación. No mezclar vectores viejos y nuevos; reconstruir conservando fuentes y avisar si no hay cobertura |
| `backend/config/model_capabilities.py::probe_model` | Hasta varias llamadas LiteLLM para probar opciones del proveedor | Antes se invocaba al arrancar; import/factory, servidor y CLI ya no lo llaman automáticamente | Retirar con el cliente antiguo. Metadata/auth/readiness no deben generar inferencia. Las pruebas de arranque lo caracterizan |
| `backend/scripts/warmup_prefix_cache.py` | POST directo `/v1/chat/completions` a servidor indicado; un token de salida por rol | Sólo ejecución explícita de este script; timeout 120 segundos por llamada | Retirar de la distribución final del runtime nuevo; no ejecutar como instalación, health check o prueba ordinaria |
| `backend/runtime/codex_session.py` | Proceso Codex nativo; exige cuenta `chatgpt` y proveedor `openai` | API autenticada y ensayos explícitos; deadline, falta de progreso, turnos, herramientas y tokens observados. Cuota y llamadas internas desconocidas | `RuntimeService` conserva reservas y uso máximo observado en SQLite. Grants por intento, Stop y corrección probados; falta migrar los demás consumidores y operar presupuestos desde UI |
| `evals/runtime/serve_infinidev_research.py` | Infinidev `openai_subscription`; intercepta el punto central `litellm.completion` y rechaza otra ruta/modelo | Ensayo explícito, aislado; máximo 32 solicitudes y 350.000 tokens si se reportan, más límites externos de tiempo/trabajo | Shim de evaluación, no adaptador productivo. No demuestra cobertura de cada ruta auxiliar posible de Infinidev |

`query_database` recibe SQL del llamador y `summarize_findings` construye una
salida desde registros; sus nombres no prueban inferencia adicional. La síntesis
posterior que haga el agente sí pertenece al turno del runtime.

## Servicios que no son la suscripción OpenAI

| Servicio | Rutas y credenciales | Tratamiento |
| --- | --- | --- |
| Búsqueda web | `web/_backends.py`: Serper con `SERPER_API_KEY`, fallback DDGS según configuración | Inventariar como red/búsqueda; ningún fallback debe activar un servicio de pago no autorizado. Destino: búsqueda explícita, capturas con procedencia y límites |
| Scraping | `spider_scrape.py` con `SPIDER_API_KEY`; wrappers CrewAI de Serper/scrape | Integración opcional independiente. La capacidad de leer web se conserva en el MCP propio; no heredar credenciales de otros proyectos |
| Context7 | `context7/search_library.py`, `get_docs.py`, `INFINIBAY_CONTEXT7_API_KEY` opcional | Documentación externa, no autenticación ChatGPT. Registrar proveedor y fuente; autorización y política de red propias |
| Web pública | `backend/research/web_fetcher.py` | HTTPS público sin cookies, proxy ni Authorization heredados; DNS fijado, TLS, redirects y límites probados. No contiene síntesis LLM |
| Ken | Ejecutable publicado `ken-rank==0.18.0`, proceso MCP por workspace de ensayo | Obligatorio en ambos candidatos. Su preparación/modelos locales y cobertura deben ser visibles; no equivale a un proveedor de completions. El preparado completo del repo no terminó dentro del presupuesto y queda pendiente |
| Forgejo/Git y ejecución | Gestores/repos, MCP antiguo y shell | Efectos y credenciales independientes de inferencia. El runtime no recibe autorización para publicar porque haya terminado un turno |

## Evidencia y límites de la inspección

Se buscaron llamadas `completion`, `acompletion`, `embeddings.create`, `get_llm`,
`call_llm`, construcción Crew/Memory y wrappers documentales; se leyeron los
productores y sus puntos de uso. El snapshot inicial de 71 herramientas, actualizado a 72 declaraciones para los
lectores retenidos de hallazgos, y sus schemas está en `legacy-tool-schemas.json`. Es una inspección del código
propio y de las entradas identificadas a librerías, no una captura exhaustiva
del tráfico de cada dependencia ni una prueba de ausencia de toda inferencia
transitiva. La prueba ordinaria bloquea sockets y no arranca modelos.

Antes del cierre de la migración: retirar las rutas reemplazadas, ejecutar cada
capacidad retenida sin keys de pago, observar/restringir el tráfico a la ruta
elegida y verificar un fallo explícito al intentar otro proveedor. Los tokens
estimados, los reportados y los desconocidos deben conservar su significado;
no presentar un contador ausente como cero ni como cuota disponible.


## Captura de artículos en el catálogo nativo

`researcher_capture_paper` resuelve un único URL/DOI/arXiv y reutiliza el fetcher y
parser PDF locales existentes. No llama al modelo ni crea embeddings. Su recorrido
nativo/HTTP/SQLite se verifica sin generación; el prompt y la descripción de herramienta
explican versión capturada, posible página de resumen y búsqueda literal. No equivalen
a una evaluación de comprensión/síntesis del modelo.

`read_paper` y `pdf_search` siguen en los catálogos CrewAI de researcher/reviewer.
El segundo todavía depende del embedding remoto anterior y NO se ha presentado la
búsqueda literal como reemplazo semántico. La retirada del proveedor/roles antiguos
requiere completar la recuperación documental y migrar sus consumidores.
[Contrato, consumers y límites](paper-capture.md).


## Encoder semántico local explícito

`researcher_source_query` procesa fuentes canónicas en un worker CPU offline, con
pesos/tokenizer fijados y sin proveedor remoto. La preparación es un comando de
bootstrap separado; importar/servir/listar no carga ni descarga el modelo. Se miden
vectores/batches locales y CPU/RSS del hijo, sin equipararlos a tokens LLM o facturación.
Es trabajo de embeddings real, aunque no genere texto ni use una API externa.

PDF y semántica comparten transporte/límites/proceso con propietario. Por proceso hay ahora una plaza semántica compartida entre API y lectores
retenidos; saturación/fallo/modelo ausente son explícitos. El presupuesto
global de todos los actores y su inscripción completa en cgroups/journal todavía
requiere integración: los límites por worker no prueban ese cierre.
[Contrato](semantic-source-retrieval.md), [ensayo retenido](../modernization/semantic-product-evidence.json).


## Lectores retenidos de hallazgos — 2026-11-02

`search_findings` ya usa el corpus completo y el mismo worker local preparado de
las lecturas nativas. No reutiliza BLOBs sin versión ni activa Chroma/downloads como
fallback. La antigua función de deduplicación y otras escrituras/búsquedas heredadas
siguen inventariadas por separado: no se declara retirada toda esa categoría.

`read_findings`, `summarize_findings` y la rama de hallazgos de `search_knowledge`
comparten las proyecciones del registro canónico. El feedback es una lectura de
decisiones existentes, sin síntesis LLM ni nuevos permisos de revisión.
`FindingsKnowledgeSource` dejó de seleccionarse y sus llamadas directas fallan antes
de leer o indexar. Memoria CrewAI y otros sources todavía requieren su migración.

Las pruebas con assets locales preparados sí ejecutan el encoder offline; no generan
completions ni usan una cuenta. El catálogo de declaraciones se refrescó a 72 tipos,
sin construir herramientas o inferencia. [Contrato](finding-readers.md).
