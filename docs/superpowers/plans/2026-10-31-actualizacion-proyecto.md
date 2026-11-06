# Plan de actualización de Researcher / Infinibay

**Fecha:** 31 de octubre de 2026. **Estado:** propuesta fundamentada en inspección; implementación pendiente.

**Objetivo:** convertir el prototipo en un espacio profesional de investigación y desarrollo, con interacción humano–agente como capacidad central, ejecución recuperable mediante Codex CLI o Infinidev, Ken obligatorio, prompts evaluados y una interfaz completamente rediseñada. Contemplar una refactorización profunda del engine y de los loops actuales cuando sus responsabilidades impidan ese objetivo.

**Arquitectura propuesta:** conservar inicialmente FastAPI y los contratos de producto; reemplazar progresivamente el motor de agentes por un adaptador de runtime. La aplicación conserva la propiedad de proyectos, tareas, evidencias, decisiones y datos; el runtime ejecuta trabajo en un workspace aislado.

**Stack propuesto:** Python, FastAPI, Pydantic y SQLite; React, TypeScript y Vite; Codex CLI mediante App Server como primera opción; Infinidev como alternativa evaluada; `ken-rank` mediante MCP en ambas opciones.

**Especificación de origen:** pedido del usuario, ampliaciones sobre contexto supuesto, aclaración sobre `ken-rank`, prioridad crucial de la comunicación humano–agente y posible refactorización amplia del engine/loop. Este documento es una hoja de ruta con decisiones recomendadas y pruebas de aceptación; no representa decisiones de implementación ya aprobadas ni una migración ejecutada. Para ejecutarlo, aplicar `superpowers:executing-plans` por entregables y detallar cada fase con el resultado de la anterior.

**Guía de lectura:** las secciones 3–6 plantean la actualización técnica; 7 define la interacción humano–agente; 8 el rediseño visual; 10 ordena la ejecución. La sección 13 reúne el análisis por subsistema, 43 escenarios «¿qué pasaría si…?», las soluciones debatidas y cómo comprobarlas.

**Criterio de documentación añadido por el usuario (1 de noviembre de 2026):** escribir y mantener docstrings en módulos, clases, métodos y funciones relevantes nuevos o modificados; usar JSDoc en TypeScript. Explicar responsabilidad, contrato, efectos y límites con vocabulario del dominio e identificadores buscables por Ken; evitar repetir el nombre o describir sólo la sintaxis. Documentar también supuestos y fallos relevantes. Revisar el código ya incorporado durante esta modernización: no basta con documentar únicamente las siguientes entregas. Verificar la correspondencia entre documentación y comportamiento al revisar cada cambio.

**Política de ejecución indicada por el usuario (5 de noviembre de 2026):** resolver primero lo grueso de cada tarea y avanzar por capacidades completas. Cuando la idea central funcione, registrar los detalles secundarios pendientes y continuar con la siguiente capacidad; no resolverlos en esa misma pasada ni ampliar la investigación por ellos. Retomarlos únicamente después de terminar todas las tareas gruesas del plan, según reiteración explícita del usuario del 6 de noviembre; no al terminar cada tarea individual. Un defecto que impida el resultado central se resuelve dentro de la tarea. Al reanudar o después de compactar el contexto, recuperar esta política antes de elegir trabajo. [Lista de detalles diferidos](../../modernization/deferred-details.md).

**Seguimiento pedido por el usuario (6 de noviembre de 2026):** en cada cambio de tarea principal, mostrar en el chat una lista actualizada de lo implementado, lo que está en curso y lo pendiente; explicar qué se cerró y qué empieza. Mantener el tablero coherente y esta regla después de compactar, sin porcentajes inventados ni confundir pilotos con aceptación integral.

## 1. Alcance y criterios de éxito

Este documento se redactó inicialmente como plan y su ejecución completa fue autorizada después. La modernización está en curso: [estado y siguiente entrega](../../modernization/execution-dashboard.md). Las observaciones históricas de esta revisión no describen automáticamente la implementación actual. Los requisitos de generación de conceptos, selección e implementación siguen vigentes hasta completar todas las páginas.

Requisitos transversales:

- Usar Codex CLI o Infinidev como runtime; no construir otro bucle LLM propio.
- Usar Ken MCP, provisto por la librería propia del usuario publicada en PyPI como `ken-rank`, en cualquiera de las dos alternativas, también dentro de workers y sandboxes. `../ken` es su código fuente local de referencia, no una dependencia de despliegue obligatoria.
- Si se realizan pruebas con modelos, usar la suscripción OpenAI del usuario mediante la ruta elegida. No cambiar silenciosamente a una API facturada por uso.
- Revisar todos los prompts: roles, tareas, herramientas, resúmenes, memoria, protocolos y contenido generado dinámicamente.
- Generar varias imágenes de concepto por pantalla, seleccionar la mejor con criterio documentado e implementar esa referencia.
- Preservar proyectos, tareas, conversaciones, documentos, findings, reportes y repositorios existentes mediante migraciones verificadas.
- Distinguir instrucciones explícitas, evidencia observada, interpretaciones y suposiciones; permitir corrección sin pedir confirmación continuamente.
- Tratar la comunicación humano–agente como requisito crucial de producto: explicar con claridad, elegir ejemplos simples, metáforas y diagramas que ayuden a comprender, informar del trabajo real y permitir intervenir. Evaluarla desde el primer recorrido funcional, no como pulido final del chat.

Éxito significa poder iniciar un proyecto, investigar con fuentes, producir y revisar un cambio, detenerlo de verdad, reiniciar el servicio y recuperar el trabajo sin duplicar efectos ni perder su procedencia. El usuario debe poder comprender qué ocurre, por qué importa, qué se sabe, qué falta y cómo orientar el resultado, sin reconstruir logs ni conocer la arquitectura interna. La interfaz debe mostrar ese estado real y permitir comprenderlo y corregirlo.

## 2. Estado observado y límites de la revisión

La revisión inicial fue estática, con lectura del código, manifiestos, lockfiles y documentación oficial. La ampliación por escenarios de la sección 13 incluye dos comprobaciones locales acotadas con SQLite en memoria y un módulo puro de estados. No se instalaron dependencias ni se arrancaron servidores, modelos, contenedores o Forgejo. No se ejecutaron las suites ni se consumió la suscripción. Un problema declarado por el README es un caso a reproducir, no un fallo de ejecución confirmado en esta sesión.

| Evidencia | Hallazgo | Consecuencia para el plan |
| --- | --- | --- |
| Último commit: `e7b5719`, 2026-03-30 | Aproximadamente siete meses sin commits posteriores en esta rama | Reconstruir una línea base antes de actualizar |
| `backend/engine/__init__.py`, `backend/agents/base.py` | `get_engine()` construye un singleton `LoopEngine`; el agente fija `_engine_type = "loop"` | El motor seleccionado es el propio; no asumir CrewAI por docstrings antiguos |
| `backend/engine/loop_engine.py`, `loop_context.py`, `loop_tools.py` | Planificación, resúmenes, parsing y despacho propios; protocolo de pasos y pseudoherramientas | Sustituir el runtime y retirar sus instrucciones específicas |
| `backend/config/llm.py`, `backend/tools/web/code_docs_search.py`, `requirements.txt` | CrewAI sigue presente en configuración y herramientas | No eliminar paquetes antes de migrar sus consumidores |
| `pyproject.toml`, `requirements.txt`, `uv.lock` | Dependencias de ejecución fuera de los metadatos; lock con sólo el proyecto editable | `uv sync --locked` no reproduce actualmente las dependencias de `requirements.txt` |
| `README.md`, `pyproject.toml` | Python 3.12+ en README y >=3.11 en manifiesto | Unificar versión soportada, instalación y CI |
| `backend/config/settings.py`, `backend/tools/base/db.py`, `start.sh` | Defaults de DB: `.researcher/researcher.db`, `/research/infinibay.db` y `.data/infinibay.db` | Resolver un único origen y detectar bases previas; los overrides podrían reconciliarlos en ejecución |
| `README.md` | Declara consumo extremo de tokens, Stop defectuoso y herramientas duplicadas | Caracterizar esos escenarios y convertirlos en aceptación obligatoria |
| `backend/api/flow_manager.py` | Ya existen mecanismos de parada, snapshots y recuperación | Reproducir antes de concluir que Stop no tiene implementación |
| `frontend/src/App.tsx` | Doce rutas principales y un feed lateral compartido | El rediseño debe cubrir todo ese inventario |
| `frontend/src/hooks/useWebSocketSync.ts` | IDs de actividad con contador local e invalidaciones manuales por tipo | Diseñar identidad durable, deduplicación, reconexión y contratos de eventos |
| `backend/api/routes/events.py`, `backend/api/websocket.py` | El historial ya devuelve IDs de `events_log` y admite `after_id`; el canal en vivo no incluye ese ID | Extender el mecanismo existente y definir catch-up ordenado; evitar un segundo historial |
| `frontend/package.json` | Scripts dev/build/preview, sin scripts de tests o lint | Incorporar comprobaciones de frontend y recorridos E2E |
| `docker-compose.yml` | Forgejo 9 y puerto publicado sin dirección local explícita | Actualizar rama y revisar exposición del despliegue local |
| `start.sh` | Contraseña administrativa por defecto predecible | Eliminar ese default y separar bootstrap de arranque normal |
| `backend/tests/tools/test_web_search_backends.py` | Un caso de Serper no comprueba el resultado | Revisar calidad de las aserciones y casos realmente protegidos |
| `start.sh:267-285` | Instala una lista propia de paquetes si falta CrewAI | El arranque es una tercera fuente de dependencias, además de los manifiestos; retirarla |
| `scripts/infinibay_mcp_server.py`, `backend/tools/__init__.py` | El MCP no expone todo el catálogo de herramientas de investigación; importa `fastmcp`, no declarado directamente en `requirements.txt` | Inventariar capacidades y fijar el entorno MCP; no asumir equivalencia con las herramientas actuales ni fallo de la instalación existente |
| `backend/prompts/team.py`, `backend/tools/web/deep_research.py`, `backend/tools/rag/base.py` | Hay resúmenes, síntesis y embeddings que invocan modelos fuera del motor | Migrar todas las rutas de inferencia, no sólo `LoopEngine` |
| `backend/db/schema.sql:388-399`, `backend/api/routes/wiki.py:49-60` | Wiki permite `project_id`, pero `path` tiene unicidad global y la API comprueba duplicado por proyecto | Caracterizar rutas iguales en proyectos distintos y corregir el contrato de identidad |

Ken se utilizó para leer el motor, recuperar memoria y consultar su alcance de impacto. La primera búsqueda semántica terminó por timeout a los 300 segundos; otras operaciones respondieron. No equivale a indisponibilidad completa. Su resultado de impacto señala importadores en autonomía y flows, y advierte que es un límite inferior por imports sin resolver. Incluir tiempos de arranque e indexación en la prueba de integración.

## 3. Dependencias, herramientas y versiones

Las versiones de frontend de esta tabla son las resueltas en `frontend/package-lock.json`, no los mínimos declarados en `package.json`. Los mínimos de Python no prueban qué está instalado. Registrar las versiones concretas y compatibilidades al ejecutar; evitar actualizar todo a `latest` en un solo cambio.

| Componente actual | Acción propuesta | Verificación necesaria |
| --- | --- | --- |
| Python >=3.11 / README 3.12+ | Adoptar una versión de Python soportada por el runtime elegido; fijar versión de desarrollo y CI | Instalación limpia, suite backend y compatibilidad de binarios |
| `requirements.txt` con rangos abiertos; `uv.lock` incompleto | Mover dependencias a `project.dependencies`; grupos de desarrollo y extras opcionales; regenerar lock | Instalación limpia con `uv sync --locked`; generar requirements sólo si hay un consumidor real |
| CrewAI >=1.10.0a1, crewai-tools >=1.9.0 | Congelar una línea base reproducible durante transición y eliminar al migrar herramientas | Cero imports y usos pendientes antes de retirarlos; evitar introducir nuevas prereleases |
| FastAPI >=0.129, Uvicorn >=0.41, Pydantic >=2.11, settings >=2.10 | Mantenerlos, actualizar a versiones estables compatibles y bloquear resolución | Contratos HTTP/WS, serialización, validación, lifespan y OpenAPI |
| LiteLLM >=1.81 y Ollama >=0.6 | Mantener sólo si el backend elegido o funciones auxiliares los requieren | Sin un segundo router de modelos o gestor de credenciales en Researcher |
| `duckduckgo-search` y `ddgs` simultáneos | Rastrear imports y consolidar el backend activo; actualizar httpx/trafilatura y clientes opcionales | Búsqueda, fallback, timeouts y errores de proveedor |
| ChromaDB >=1.1, NumPy >=2, pypdf >=5 | Actualizar únicamente con prueba de lectura/migración de colecciones y documentos | Recuperación equivalente; conservar documentos fuente y posibilidad de reconstruir índices |
| React/DOM 19.2.4, Query 5.90.21, Router 7.13.0, Zustand 5.0.11 | Conservar arquitectura SPA; revisar parches estables y compatibilidad conjunta | Rutas, selección de proyecto, caché, mutaciones y reconexión |
| TypeScript 5.9.3 | Evaluar versión estable compatible con Vite y tipos; mantener strictness y corregir `any` en fronteras | `tsc -b`, build y eventos tipados |
| Vite 6.4.1, plugin React 4.7.0 | Migrar a Vite 8 y plugin compatible; revisar cambios de 6→7→8 | Node compatible, dev server, build, assets y targets de navegador |
| Tailwind 3.4.19 | Adoptar Tailwind 4 en el rediseño, migrando tokens, plugins y estilos base | Capturas, tipografía, foco y componentes; respetar soporte de navegadores requerido |
| Recharts 2.15.4 | Evaluar migración de major sólo si se conservan gráficos útiles | Datos vacíos, accesibilidad, tooltips y tamaño responsive |
| react-markdown 9.1.0, KaTeX 0.16.28 y plugins remark/rehype | Actualizar conjunto compatible y revisar render de contenido no confiable | Enlaces, HTML, fórmulas, código, documentos largos y payloads maliciosos |
| pytest >=9, configuración asyncio | Declarar explícitamente plugins y herramientas usados por la suite; añadir Ruff y chequeo de tipos incremental | Tests sin red ni credenciales por defecto; marcador separado para pruebas vivas |
| Frontend sin runner declarado | Incorporar Vitest/Testing Library, Playwright y axe, más lint | Tests de interacción, contratos y accesibilidad; no tests que repitan la implementación |
| MCP propio con import directo de `fastmcp` | Declarar y fijar esa dependencia en el entorno/extra que realmente ejecutará el servidor, si se conserva | Iniciar el servidor desde una instalación limpia y listar/invocar sus herramientas sin depender de paquetes transitivos incidentales |
| Forgejo 9 | Migrar a una rama mantenida; preferencia inicial 15 LTS, verificando ruta de upgrade | Backup, ensayo de saltos requeridos, restore, clone/push/PR y autenticación |
| Imágenes `latest`, scripts de inicio | Fijar tags/digests revisables, unificar config y separar setup de run | Dos arranques consecutivos y cierre limpio sin reinstalación incidental |
| Codex, Infinidev, Ken externos | Fijar versión o commit y protocolo probado de cada runtime | Informe de compatibilidad y diagnóstico sin secretos |

Fuentes verificadas: [migración de Vite](https://vite.dev/guide/migration.html), [Tailwind 3→4](https://tailwindcss.com/docs/upgrade-guide) y [releases de Forgejo](https://forgejo.org/releases/). Forgejo enumera 9 como discontinuada y 15 como LTS. Verificar nuevamente estas fuentes al ejecutar; este plan no certifica compatibilidad de versiones aún no probadas.

Agregar automatización periódica de actualizaciones, auditorías de dependencias y licencias, con PRs separados por familia. Un aviso de auditoría debe evaluarse contra el uso real; no resolverlo mediante upgrades forzados indiscriminados.

## 4. Reimplementación del backend

### 4.1 Alternativas y recomendación

| Opción | Ventajas | Costes y condiciones |
| --- | --- | --- |
| **Codex CLI mediante App Server — recomendada para la primera integración** | Protocolo programático oficial, sesiones, streaming y cancelación; uso del login ChatGPT | Adaptar eventos y permisos; comprobar qué funciones de investigación y herramientas están disponibles en la versión fijada |
| **Infinidev como runtime de Researcher** | Ya ofrece equipos, investigación, memoria, MCP y workspace web | Solapamiento de producto y propiedad de datos; API de integración y compatibilidad de suscripción deben probarse |
| Mantener el LoopEngine como arquitectura final | Menos cambios inmediatos | Mantiene precisamente los problemas de bucle, parsing y prompting que se busca retirar; descartada como destino |

Preferencia de este plan, no elección atribuida al usuario: empezar por Codex y decidir con una prueba comparativa pequeña. `codex exec --json` sirve para tareas acotadas de una sola ejecución; App Server encaja mejor con sesiones web, interrupción y solicitudes de permisos. No parsear texto de una TUI.

La instalación local reporta `codex-cli 0.166.0`. Esto verifica presencia del ejecutable, no login, modelos disponibles ni consumo. La documentación oficial describe App Server con threads/turns y `turn/interrupt`; tomar su esquema de la versión fijada y traducirlo en el adaptador. Véanse [App Server](https://learn.chatgpt.com/docs/app-server) y [referencia CLI](https://learn.chatgpt.com/docs/cli/reference).

La inspección de `../infinidev/README.md`, `docs/web-harness.md`, `src/infinidev/server/app.py` y `config/openai_oauth.py` muestra un harness reutilizado por terminal y web y un proveedor `openai_subscription` que lee y refresca la sesión Codex. Es evidencia de implementación local; no demuestra que todos los flujos de Researcher puedan integrarse sin cambios ni que esa ruta tenga el mismo contrato de soporte que Codex oficial. Evitar duplicar el manejo de OAuth en este repositorio.

Restricción concreta: `../infinidev/src/infinidev/server/app.py:36-42` exige que el directorio de trabajo del proceso sea el workspace; `server/runtime.py:39-47` declara un proyecto por proceso y serializa turnos con un executor de un worker. Researcher tiene varios proyectos, incluso si lo usa una sola persona. No incrustar varios `WebRuntime` en un mismo proceso ni cambiar el cwd global por petición. La prueba debe evaluar un proceso por workspace, o una interfaz desacoplada que elimine esa restricción. Registrar qué operaciones se serializan y qué concurrencia real permite el candidato; no interpretar equipos como ejecución paralela garantizada.

### 4.2 Prueba de decisión antes de la migración

- [ ] Registrar commit de `../infinidev`, versión instalada de `ken-rank`, versión Codex y entorno; si se prueba una versión de desarrollo de Ken, registrar también el commit de `../ken`. Usar un workspace de ensayo y datos ficticios.
- [ ] Ejecutar los mismos escenarios en ambos candidatos: explicar código usando Ken, investigar con fuentes, implementar un cambio pequeño con pruebas, responder una aclaración durante ejecución, cancelar y reanudar tras reinicio.
- [ ] Investigar usando un adjunto de ensayo y una fuente web; persistir un finding y un informe recuperable desde `/reports`. Una respuesta textual sin esos artefactos no supera la prueba de capacidades del producto.
- [ ] Abrir dos proyectos con archivos y nombres de tareas iguales y configuraciones distintas; verificar aislamiento de proceso, workspace, permisos, memoria, DB, eventos y sesión nativa. Si el candidato serializa ejecuciones, reflejarlo en cola y UI.
- [ ] Confirmar que el proveedor elegido usa la suscripción y que una cuota agotada produce un estado claro, sin fallback facturado.
- [ ] Medir éxito verificable, pérdida de contexto, efectos duplicados, latencia, consumo observado, cancelación y complejidad de integración. Repetir casos para observar variabilidad.
- [ ] Registrar una decisión en `docs/architecture/runtime-decision.md`: candidato elegido, evidencia, limitaciones y versión fijada. Si Infinidev resuelve los escenarios con menos duplicación de producto y cumple los contratos, preferirlo.

### 4.3 Límites de responsabilidad

Mantener un monolito modular inicialmente. FastAPI sigue siendo la frontera HTTP; dominio y casos de uso no deben importar Codex, Infinidev, CrewAI ni modelos de transporte. El adaptador encapsula protocolo, sesiones, errores, permisos y cancelación. No crear microservicios, colas distribuidas o múltiples bases por anticipación.

Contrato conceptual del runtime, a concretar después de la prueba:

```text
start(request: RunRequest) -> RunHandle
events(run_id: str, after_event_id: str | None) -> AsyncIterator[RunEvent]
respond(run_id: str, request_id: str, answer: UserAnswer) -> None
steer(run_id: str, correction: ContextCorrection) -> SteerResult
cancel(run_id: str) -> CancelResult
resume(run_id: str) -> RunHandle
```

`RunRequest` contiene workspace, objetivo, criterios de aceptación, herramientas permitidas, límites y una versión de contexto. `RunEvent` tiene ID durable, proyecto, ejecución, secuencia, tipo, fecha y payload validado. Distinguir texto del modelo de resultado de herramienta verificado. `RunHandle` conserva el identificador nativo necesario para recuperar una sesión. Esta interfaz expresa capacidades deseadas: el spike debe determinar cuáles pueden implementarse y qué limitaciones quedan expuestas.

`respond` responde una solicitud pendiente identificada; `steer` entrega una corrección nueva sin exigir que haya una pregunta abierta. Definir acuse de recepción y versión de contexto aplicada antes de despachar acciones dependientes. Si el runtime no admite steering seguro, pausar/cancelar y reanudar con contexto corregido, conservando la relación entre ejecuciones. `resume` debe distinguir reconectar una sesión, continuar un turno y crear un intento nuevo: no prometer checkpoints intercambiables entre motores. Los snapshots de LoopEngine existentes requieren traducción a estado de producto o reanudación desde un límite seguro, nunca cargarlos como estado nativo de Codex/Infinidev.

`start` debe programar la ejecución y devolver su identidad sin bloquear el servidor durante toda la tarea. El servicio conserva un único dueño activo por ejecución; comprobar inicio concurrente, reinicio y proceso huérfano antes de permitir otro dueño. La cancelación puede competir con finalización: registrar el resultado real y no convertir retroactivamente una operación ya realizada en cancelada.

Antes del adaptador productivo, crear `docs/architecture/capability-matrix.md`: herramienta/capacidad actual → nativa del runtime, MCP de negocio, adaptación o retirada justificada; indicar schema, permisos, efectos, persistencia y prueba. Incluir web/PDF/RAG, archivos de referencia, hipótesis, findings, informes, wiki, mensajes, solicitudes al usuario y Git/PR. El MCP actual expone tareas, chat, findings, wiki, consulta SQL, PR y notas de sesión, pero no `write_report`, `read_reference_files` ni el catálogo web/RAG completo. Validar los nombres y argumentos que verá realmente el runtime. Las operaciones SQL genéricas no deben sustituir herramientas de negocio con validación y alcance por proyecto.

Propuesta de archivos, siguiendo las responsabilidades actuales y ajustable tras el spike:

| Crear o modificar | Responsabilidad |
| --- | --- |
| Crear `backend/runtime/contracts.py` | Modelos neutrales y contrato de ejecución |
| Crear `backend/runtime/codex.py` **o** `infinidev.py` | Adaptador del candidato seleccionado; no mantener dos adaptadores productivos sin necesidad |
| Crear `backend/runtime/service.py` | Ciclo de vida, identidad, persistencia y límites por ejecución |
| Modificar `backend/engine/__init__.py`, `base.py`, `backend/orchestrator.py` | Puente temporal y retirada gradual del contrato antiguo |
| Modificar `backend/autonomy/handlers/`, `backend/flows/`, `backend/api/flow_manager.py` | Usar operaciones de ejecución, eliminar suposiciones del LoopEngine |
| Modificar `backend/api/routes/`, `backend/api/websocket.py` | HTTP/WS, control de acceso y traducción de eventos |
| Modificar `backend/db/schema.sql`, `backend/tools/base/db.py` | Migración versionada, ejecuciones, eventos, decisiones y evidencias |
| Modificar `scripts/infinibay_mcp_server.py`, `backend/tools/` | Exponer herramientas de negocio que el runtime necesite, con schemas explícitos |
| Crear `backend/tests/runtime/` | Pruebas de contrato, interrupción, recuperación e idempotencia |

Antes de cada cambio compartido, ejecutar `ken_recall(path=...)`, consultar `ken_related(..., relation="blast_radius")` y leer consumidores y tests. El impacto ya observado de `engine/base.py` incluye handlers de autonomía, message dispatcher y flows de investigación/revisión. No limitar la migración al constructor del motor.

### 4.4 Fiabilidad y datos

- Parada con estados `running → cancelling → cancelled`; dejar de despachar herramientas, cancelar el turno y terminar los procesos propios de esa ejecución si no responden al plazo. No terminar procesos compartidos con otras ejecuciones. La UI no debe anunciar cancelación antes del acuse real.
- Recuperación mediante estado durable y reconciliación con runtime/procesos; una conexión WS perdida no debe reejecutar el prompt.
- Distinguir aclaraciones de producto y solicitudes nativas de autorización. Guardar propósito, alcance, estado y correspondencia con la solicitud del runtime. Tras reinicio, una pregunta persistida no demuestra que su handle nativo siga vigente: reconciliar o regenerar la solicitud antes de responder al motor. Conservar las autorizaciones válidas ya otorgadas por el usuario dentro de su alcance; no convertir la pérdida del handle en una obligación de preguntarle otra vez. Nunca inferir autorización del silencio o de reconectar.
- Reutilizar `events_log` como base del historial. Propagar su identidad durable al canal vivo y definir qué eventos de runtime se persisten. El catch-up debe paginar por una secuencia estable en orden ascendente hasta alcanzar el canal vivo, con deduplicación y sin huecos. El endpoint actual combina `after_id` con orden descendente por fecha y límite; no usarlo como protocolo de recuperación completo sin corregir y probar esa semántica. Incluir más de una página de eventos, fechas iguales, cliente lento y retención/cursor vencido.
- Idempotencia de comandos de negocio y efectos: comentarios, tareas, mensajes, commits y PRs. Persistir clave de operación y resultado; ante éxito remoto desconocido, reconciliar antes de reintentar. No prometer exactly-once sobre sistemas externos.
- Un único dueño del cambio de estado. Guardar transiciones y eventos de salida de forma atómica cuando corresponda; reintentos acotados con backoff y límites de concurrencia.
- Mantener SQLite/WAL para el despliegue local si las mediciones lo permiten. Migrar a PostgreSQL sólo ante concurrencia o despliegue que lo justifique.
- Resolver DB desde una configuración única. Detectar múltiples bases previas y pedir elección únicamente si son ambiguas; nunca elegir silenciosamente una y aparentar pérdida de datos.
- Corregir la identidad de wiki durante la migración: permitir una misma ruta en proyectos diferentes si ése es el contrato, definir el tratamiento de documentos globales con `project_id IS NULL`, la precedencia entre global/local y el alcance de `parent_path`. Actualizar lectores, editores y herramientas junto con constraints/índices; una constraint compuesta nullable por sí sola no fija la unicidad de documentos globales. Probar creación, lectura y edición con rutas repetidas sin afectar otro proyecto.
- Copias consistentes de DB, adjuntos y repositorios; manifiesto con conteos y hashes. Ensayar upgrade y restauración sobre copias. Conservar la versión anterior hasta validar lectura y recorridos esenciales.
- La vuelta atrás después de nuevas escrituras requiere compatibilidad o migración inversa probada; restaurar un backup viejo perdería esas escrituras y no debe presentarse como rollback transparente.

### 4.5 Todas las llamadas a modelos y servicios auxiliares

Crear `docs/architecture/inference-inventory.md` antes de afirmar que se usa exclusivamente la suscripción. Identificar llamadas directas y transitivas, proveedor, credenciales, activación, propósito, límites y destino de migración. Además del motor, revisar `backend/prompts/team.py:588-615` (resumen de chat), `backend/tools/web/deep_research.py:223-237` (síntesis), `backend/knowledge/service.py:74-87` (memoria CrewAI), `backend/tools/rag/base.py:88-105` (embeddings), probes de arranque y librerías de búsqueda documental.

Delegar resúmenes y síntesis al runtime elegido cuando sean necesarios; usar recuperación determinista cuando baste. Para embeddings, escoger explícitamente una opción local reproducible o un servicio autorizado y comprobar sus requisitos. No dar por hecho que el login de suscripción del runtime habilita la API de embeddings. Registrar modelo, dimensión y versión de índices: al cambiar de modelo, reconstruir colecciones compatibles desde fuentes conservadas, sin mezclar vectores ni sobrescribir el único índice recuperable.

La aceptación debe incluir la aplicación sin API keys de pago, tráfico de inferencia restringido a la ruta elegida y pruebas de fallo si una ruta auxiliar intenta usar otro proveedor. Los servicios web con credenciales propias también deben figurar en el inventario; no confundir su autenticación con la suscripción OpenAI. Esto no afirma que se hayan realizado cobros en el estado actual.

### 4.6 Refactorización profunda del engine y los loops

La migración puede requerir rehacer una parte importante de la estructura actual. No asumir que `AgentEngine.execute(...) -> str` más un adaptador resuelve el cambio: ese contrato mezcla agente, prompt, herramientas, validación, reintentos, checkpoints y parámetros específicos del LoopEngine. En `backend/orchestrator.py`, una ejecución que retorna sin excepción se marca como tarea terminada; el nuevo contrato debe distinguir finalización del turno, resultado de negocio verificado, fallo, interrupción y espera del usuario.

Separar explícitamente dos ciclos existentes:

| Ciclo actual | Responsabilidad observada | Destino a evaluar |
| --- | --- | --- |
| `backend/engine/loop_engine.py` y módulos asociados | Interacción LLM/herramientas, planificación, reintentos, resúmenes y contexto | Delegar al runtime elegido; extraer sólo las reglas de producto necesarias y retirar el bucle de inferencia sustituido |
| `backend/autonomy/agent_loop.py::AgentLoop._loop` | Polling, selección y claim de eventos, pausa, presupuestos y despacho; recuperación ligada a `LoopState` | Refactorizar como coordinación de trabajo con propiedad durable y estados explícitos; reutilizar capacidades del runtime cuando cubran el contrato |

El loop de coordinación del producto puede seguir siendo necesario aunque Codex/Infinidev gestione la inferencia. Evitar dos coordinadores que asignen, reintenten o completen la misma tarea. La decisión de conservar, simplificar o sustituir cada parte se documenta con evidencia en `docs/architecture/engine-redesign.md`, antes de extender el primer recorrido a todos los flows.

La revisión parte por parte y los debates de la sección 13 concretan esta decisión: consolidar las rutas actuales de comunicación/activación, retirar coordinadores redundantes y comprobar aceptación sobre un candidato versionado. No limitar el rediseño a renombrar clases o envolver `execute`.

- [ ] Mapear `backend/engine/`, `backend/autonomy/`, handlers, orchestrator, flows, contexto de herramientas y eventos hasta el usuario. Identificar dueño del estado, efectos laterales, datos globales y puntos donde pueden llegar pausa, cancelación y correcciones.
- [ ] Caracterizar comportamiento observable usando `backend/tests/engine/`, `backend/tests/autonomy/test_agent_loop.py` y pruebas de API. No preservar por obligación las pseudoherramientas o los pasos internos que desaparecerán; sí preservar los resultados y reglas de negocio acordados.
- [ ] Diseñar estados y contratos comunes de coordinación, resultado y contexto; convertir los parámetros internos de LoopEngine en configuración del adaptador sólo si siguen teniendo sentido. No propagar `resume_state` o contadores antiguos por toda la aplicación.
- [ ] Introducir una primera ejecución que atienda mensajes del usuario mientras trabaja. Corregir una premisa debe actualizar el trabajo dependiente; la comunicación no puede quedar bloqueada hasta que termine una llamada síncrona larga.
- [ ] Separar cambios estructurales que preservan comportamiento de cambios deliberados de semántica. Migrar por recorridos completos; evitar un parche único que mueva módulos, cambie estados, sustituya el runtime y reescriba todos los prompts a la vez.
- [ ] Probar carreras entre claim, cancelación, corrección, resultado y reinicio; rechazar resultados de intentos obsoletos y conservar evidencia de efectos ya realizados. Retirar el motor anterior cuando sus consumidores tengan un destino comprobado.

Aplicar los criterios de la skill `refactoring` de Fowler junto con Feathers y Ousterhout: transformaciones acotadas, pruebas de comportamiento y responsabilidades claras. La extensión de la refactorización se decide por el cambio necesario y la evidencia, no por mantener los archivos actuales ni por reescribirlos todos por principio.

## 5. Ken MCP obligatorio en ambos runtimes

Ken es una librería propia del usuario publicada en PyPI como `ken-rank`; su comando es `ken` y expone el servidor MCP. `../ken` contiene su código fuente local y permite investigar contratos o corregir la librería, pero la instalación normal no debe depender de ese checkout vecino. Ya existe `.codex/config.toml` con `command = "ken"` y `args = ["mcp"]`, pero eso no demuestra que el proceso o contenedor futuro vea el mismo ejecutable, índice o raíz.

- [ ] Instalar desde PyPI una versión publicada y fijada de `ken-rank` en un entorno aislado de herramientas; por ejemplo, `uv tool install 'ken-rank==<version-validada>'` sustituyendo el marcador por la versión probada. Registrar versión y procedencia, y resolver una ruta inequívoca al ejecutable. Reservar la instalación desde `../ken` para desarrollo o diagnóstico explícito y registrar su commit cuando se use.
- [ ] Ejecutar `ken retrieval prepare --path <workspace>` antes de la primera tarea y comprobar lectura con `ken_find` y `ken_read` desde ese workspace.
- [ ] Configurar el servidor MCP en el runtime elegido. Codex usa su configuración MCP; Infinidev debe verificarse mediante `engine/mcp_client.py` y `engine/mcp_runtime_bridge.py`, no suponiendo equivalencia de formatos.
- [ ] Verificar mounts y traducción de rutas si hay sandbox; aislamiento de índices/memoria entre proyectos y acceso a código actualizado.
- [ ] Hacer una prueba donde el runtime invoque realmente Ken, lea el resultado y cite el archivo. La mera presencia de la configuración no supera la aceptación.
- [ ] Usar consultas naturales en inglés y respuesta al usuario en español. Leer primero los archivos entregados por `<context-rank>`; comprobar memoria antes de rederivar; conservar hallazgos con evidencia, supuestos y paso de revalidación.
- [ ] Medir cold start, actualización del índice y timeout; distinguir preparando, disponible y fallando. Si Ken falla, mantener accesibles diagnóstico y recuperación; no arrancar trabajo de código silenciosamente sin la integración exigida.

Referencia de contrato: documentación y schemas MCP de la versión publicada instalada. Contrastar con `../ken/README.md` y el código local cuando corresponda, registrando diferencias entre versión publicada y checkout. Evitar inventar comandos por similitud con otros servidores.

Revisar el solapamiento con `backend/code_intel/`, `backend/tools/code_intel/` y las tablas `ci_files`/`ci_symbols`. Consolidar descubrimiento, lectura y memoria de código en Ken cuando cubra el contrato, evitando mantener dos índices sin una razón demostrada. Las herramientas de rename/move/edit estructural tienen efectos de escritura: no asumir que una búsqueda Ken las reemplaza. Registrar su destino en la matriz de capacidades, retirar consumidores e índices obsoletos sólo después de validación y mantener separadas la memoria técnica de Ken y las evidencias de investigación del producto.

## 6. Revisión integral de prompts

### 6.1 Inventario y migración

Se encontraron **40 archivos Python** bajo `backend/prompts/`, incluidos auxiliares e inicializadores; no equivalen a 40 prompts independientes. Inventariar también strings fuera de esa carpeta y prompts compuestos en tiempo de ejecución.

| Familia | Archivos de entrada | Cambio esperado |
| --- | --- | --- |
| Identidad y coordinación | `backend/prompts/team.py`, `shared.py`, `tool_refs.py` | Roles mínimos, contexto trazable y herramientas vigentes; retirar catálogos repetidos |
| Planificación y supervisión | `project_lead/`, `team_lead/` | Objetivos y criterios verificables; evitar jerarquía y delegación innecesarias |
| Desarrollo | `developer/system.py`, `tasks.py`, `tech/` | Leer antes de editar, usar Ken, cambios acotados y evidencia de pruebas; cargar guías técnicas bajo demanda |
| Investigación | `researcher/`, `research_reviewer/` | Procedencia, contraevidencia, hipótesis, límites y citas que realmente soporten la afirmación |
| Revisión de código | `code_reviewer/` | Hallazgos concretos con impacto, ubicación y validación; evitar aprobación basada sólo en el relato del autor |
| Motor, herramientas y resúmenes | `backend/engine/loop_context.py`, `summarizer.py`, `loop_tools.py`, `backend/tools/` | Retirar protocolo de pseudoherramientas al retirar el motor; conservar intención y evidencia, no su sintaxis |
| Plantillas en flows, handlers y scripts | `backend/flows/`, `backend/autonomy/`, `scripts/` | Rastrear llamadas e interpolaciones para evitar instrucciones obsoletas fuera del inventario principal |

Crear `docs/prompts/inventory.md` con dueño, consumidores, variables, objetivo, tamaño medido, reglas heredadas, conflictos y casos de evaluación de cada plantilla. Cada entrada termina conservada, reescrita, fusionada o eliminada con motivo. Comprobar ejemplos como `engine="crewai"` y referencias a `claude_code` que ya no describen el destino.

La revisión mínima de prompts y nombres de herramientas forma parte del primer recorrido vertical; no esperar a la fase 5 para descubrir que el runtime recibe instrucciones incompatibles. La fase 5 completa y evalúa todo el catálogo. Vincular cada plantilla a su invocación real en el inventario de inferencia, incluida la generación de resúmenes.

### 6.2 Técnicas a aplicar y medir

1. Expresar objetivo, restricciones, entradas, herramientas y aceptación en secciones claras; separar instrucciones confiables de documentos, resultados web y mensajes externos.
2. Eliminar énfasis repetitivo, biografías largas y reglas mecánicas del antiguo loop. No trasladar literalmente prompts diseñados para modelos pequeños al harness nuevo.
3. Proporcionar sólo contexto relevante, con fuente y vigencia; conservar posibilidad de abrir evidencia completa después de un resumen.
4. Usar esquemas de salida validados para decisiones de máquina; no depender de regex sobre Markdown si puede usarse una herramienta tipada.
5. Incluir pocos ejemplos representativos cuando aclaren una ambigüedad real. Comparar con y sin ejemplos; no asumir que más texto mejora el resultado.
6. Pedir explicación útil y evidencia comprobable, no exposición de cadenas internas de pensamiento. Planificación proporcional y revisión contra criterios concretos.
7. Tratar instrucciones incrustadas en web, archivos o memoria como contenido no confiable; autorización y límites de herramientas se aplican en código.
8. Versionar plantillas y perfiles de capacidad, registrar el contexto efectivamente enviado y medir resultados antes/después. No escoger un modelo por nombre fijo en los prompts.

La guía oficial recomienda estructurar instrucciones, aportar contexto pertinente y usar ejemplos cuando corresponda: [Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering). Las técnicas deben validarse en las tareas de este proyecto, no presentarse como mejoras garantizadas.

### 6.3 Ideas de las skills de libros revisadas

Se revisaron las skills locales y sus guías resumidas. Son criterios de diseño y revisión; no se propone pegar libros completos dentro de cada prompt.

| Skill / libro | Idea aplicada al proyecto | Efecto en prompts y revisión |
| --- | --- | --- |
| `a-philosophy-of-software-design` — Ousterhout | Encapsular decisiones volátiles; reducir carga cognitiva y saltos entre módulos | Solicitar interfaces que oculten complejidad; justificar nuevas capas y evitar resúmenes que omitan decisiones esenciales |
| `clean-architecture` — Martin | Reglas de producto independientes de frameworks y proveedores | Evaluar dependencias hacia dentro y contratos neutrales; no pedir al agente que replique arquitectura ceremonial |
| `working-effectively-with-legacy-code` — Feathers | Caracterizar antes de sustituir; crear seams de prueba | Exigir reproducción y comportamiento preservado antes de retirar LoopEngine |
| `designing-data-intensive-applications` — Kleppmann | Dueño del dato, idempotencia, replay y compatibilidad | Diferenciar comando, evento y proyección; revisar duplicados, éxito desconocido y fallos entre escrituras |
| `release-it` — Nygard | Timeouts, límites, aislamiento y recuperación | Todo trabajo externo debe tener cancelación, retry elegible y comportamiento ante saturación |
| `the-pragmatic-programmer` — Hunt/Thomas | Una fuente de verdad, feedback rápido y pequeños recorridos reales | Probar pronto una tarea completa y conservar evidencia; automatizar verificaciones repetidas |

Consultar otras skills de libros cuando una tarea concreta lo requiera; no activar simultáneamente todas sus reglas, especialmente si generan instrucciones contradictorias. En el inventario, registrar qué guía afecta a qué tipo de tarea.

## 7. Interacción humano–agente: comunicación, comprensión y contexto compartido

**Prioridad explícita del usuario:** la interacción humano–agente es crucial. Explicar bien forma parte del funcionamiento del sistema, de sus prompts, su coordinación y su interfaz. Una tarea técnicamente correcta puede fallar como experiencia si el usuario no comprende el resultado, sus límites o cómo corregir el rumbo.

**Hipótesis del usuario:** una fuente importante de fallos humano–agente es actuar sobre contexto supuesto como compartido sin evidencia suficiente. El plan la adopta como hipótesis de diseño a evaluar, no como conclusión científica ya demostrada.

### 7.1 Fuerza y procedencia de la evidencia

«El usuario lo explicó», «lo demostró con un ejemplo» y «supongo que lo sabe por su profesión» no tienen la misma fuerza. No hay una jerarquía universal: un ejemplo demuestra un caso concreto, no todo un dominio; una instrucción explícita establece intención y alcance, pero puede ser corregida. La profesión es una pista débil y nunca autorización para actuar.

Proponer un registro de contexto que se conserve al resumir, delegar y recuperar:

```text
afirmación / interpretación
tipo: instrucción explícita | ejemplo observado | evidencia de herramienta | inferencia | supuesto
fuente: mensaje, archivo+revisión, ejecución o ejemplo concreto
alcance: tarea, usuario, proyecto o sesión
estado: vigente | contradicho | corregido | pendiente de verificar
consecuencia de equivocarse y siguiente forma concreta de comprobarlo
```

No asignar porcentajes de confianza inventados. Registrar incertidumbre y límites de la evidencia. Una inferencia persistida por Ken no se convierte en hecho por haber sido recordada; un resumen o mensaje de otro agente tampoco la fortalece automáticamente.

### 7.2 Menos saltos injustificados, sin simplificar hasta deformar

- Elegir una explicación que conecte evidencia, interpretación y consecuencia. Reducir saltos inferenciales, no simplemente palabras.
- Introducir un concepto nuevo con una definición breve cuando una analogía conocida lo distorsione. Usar ejemplos del problema real y explicitar dónde termina su validez.
- Hacer visibles sólo los supuestos que cambian una decisión, el alcance o la interpretación del resultado. No llenar la conversación con etiquetas para cada frase.
- Separar explicación de autorización: que el usuario conozca un concepto no significa que haya pedido una acción.

### 7.3 Corrección mediante trabajo concreto

El agente no accede directamente a lo que piensa el usuario. Debe asumir buena parte del esfuerzo de interpretación y ofrecer puntos útiles de corrección:

- Interpretación explícita: «Tomo “actualizar” como preparar este plan; la migración queda descrita para una ejecución posterior».
- Ejemplo: mostrar un before/after de un prompt y el cambio de conducta que se espera, para que el usuario pueda señalar una desviación específica.
- Resultado pequeño: una pantalla o un recorrido de tarea que revele decisiones y permita corregir antes de extenderlas.
- Pregunta dirigida únicamente cuando falte una decisión material que el repo y la evidencia no resuelvan; no reiterar «¿entendí bien?» como ritual.

En la interfaz, mostrar objetivos, decisiones y supuestos relevantes con enlaces a su origen y una acción para corregirlos. Una corrección genera una versión nueva, identifica tareas y conclusiones afectadas y se entrega a los agentes activos antes de continuar acciones dependientes. Conservar el historial; no tratar el silencio, una reconexión o el mero paso del tiempo como acuerdo.

### 7.4 Pruebas de la hipótesis

Crear `evals/context_alignment/` con casos donde: el usuario contradice una interpretación; una profesión sugiere conocimiento que no posee; un ejemplo cubre sólo un caso; una memoria está desactualizada; una analogía deforma; un agente recibe una delegación con supuesto no confirmado; una corrección llega durante ejecución.

Comparar baseline y prompts nuevos en casos reservados, con evaluación ciega cuando sea viable. Medir acciones basadas en supuestos sin respaldo, preservación de procedencia tras resumen, correcciones incorporadas, preguntas innecesarias, comprensión de la explicación y éxito de tarea. Registrar también tiempo, tokens y esfuerzo del usuario: mejorar alineación no debería esconderse detrás de una conversación interminable. No declarar causalidad a partir de unos pocos ejemplos favorables.

Antes de comparar, fijar una rúbrica y casos de aceptación reproducibles, separar ejemplos de desarrollo de casos reservados y definir qué regresiones bloquean la entrega. Mantener constantes modelo, herramientas y contexto al medir un cambio de prompt; comparar runtimes en un experimento separado. Los casos críticos —ampliar autorización por inferencia, ignorar una corrección o perder su procedencia— deben fallar de forma determinista en el control de acciones, aunque el texto del modelo varíe. La comprensión y el esfuerzo del usuario requieren observación humana; una evaluación automática sólo aporta evidencia parcial.

### 7.5 Contrato de comunicación con el usuario

Crear `docs/interaction/communication-guide.md` con ejemplos de conversaciones y criterios de revisión. Aplicarlo a los prompts que hablan con el usuario y al primer recorrido vertical, independientemente del runtime elegido.

- **Explicar con propósito:** empezar por la respuesta, el hallazgo o el cambio relevante; conectar después evidencia, consecuencia y siguiente acción. Explicar términos nuevos cuando son necesarios. Ajustar profundidad a lo pedido y a lo demostrado en la conversación, sin deducir conocimiento sólo por profesión.
- **Ofrecer profundidad gradual:** una explicación principal suficiente y detalles accesibles cuando ayuden. No ocultar límites o decisiones importantes en paneles secundarios. El usuario puede pedir una explicación más simple, más técnica o con otro ejemplo sin perder el contexto de la tarea.
- **Informar durante el trabajo:** comunicar hallazgos y cambios de dirección en lenguaje de producto; diferenciar trabajando, esperando una herramienta y esperando al usuario. No dejar silencios prolongados sin estado ni llenar el chat de cada tool call. La frecuencia depende de duración y novedad; no inventar progreso ni porcentajes.
- **Pedir decisiones concretas:** presentar las opciones y sus consecuencias cuando haga falta una elección material. Una aclaración no debe obligar al usuario a diseñar la solución; reutilizar información ya dada y explicar qué depende de su respuesta.
- **Comunicar errores y desacuerdos:** decir qué falló, qué efecto tuvo y cómo se puede recuperar. Separar lo comprobado de la sospecha; discrepar con razones comprensibles, sin seguridad teatral ni trasladar al usuario el diagnóstico interno sin explicación.
- **Cerrar con evidencia:** describir resultado y validación, qué queda pendiente y qué significa para el objetivo. No confundir “el agente terminó su turno” con “el problema está resuelto”.

Cuando trabajen varios agentes, mantener un hilo principal coherente y atribución de hallazgos. El usuario debe poder consultar quién investigó algo o dirigirse a un especialista, sin convertirse en intermediario obligatorio de mensajes repetidos o contradictorios. Construir esa presentación sobre los eventos y evidencias existentes; no añadir un segundo agente LLM para reformular cada mensaje por defecto.

### 7.6 Ejemplos, metáforas y diagramas como herramientas de comprensión

Elegir el formato por lo que el usuario necesita entender, no por una plantilla que exija siempre un diagrama o una metáfora.

| Necesidad | Recurso preferido | Condición de calidad |
| --- | --- | --- |
| Entender un concepto o un comportamiento | Un ejemplo pequeño con datos concretos y resultado esperado | El caso debe conservar la propiedad que se explica y permitir reconocer un caso parecido |
| Conectar una idea nueva con algo familiar | Metáfora o analogía breve | Explicar la correspondencia y su límite; sustituirla si introduce una intuición falsa |
| Entender una secuencia, dependencia o responsabilidad | Diagrama de flujo, secuencia o estados | Nombres comprensibles, pocas piezas por vista y conexión con el caso real |
| Comparar opciones y consecuencias | Tabla breve o comparación visual | Criterios comunes, tradeoffs explícitos y recomendación fundamentada |
| Explorar cómo cambia un resultado al variar una condición | Visual interactivo cuando aporte valor | Estado inicial claro, controles accesibles y conclusiones que no excedan los datos |

Ejemplo ilustrativo de comunicación: «Si la conexión se corta después de crear un informe, al volver podemos comprobar su identificador antes de crear otro. Es parecido a consultar el número de un pedido antes de repetirlo. Esa comprobación funciona si la operación guarda una identidad; la metáfora no demuestra que todos los servicios externos la ofrezcan». Primero se explica un caso concreto, luego se usa una imagen familiar y se delimita su alcance.

Los diagramas deben estar vinculados a la explicación y tener alternativa textual; no usar color como único significado. Para relaciones técnicas sencillas puede emplearse Mermaid si se incorpora un renderer compatible; para resultados científicos, gráficos derivados de datos y fuentes. No afirmar que el frontend ya renderiza diagramas: `frontend/src/components/common/MarkdownRenderer.tsx` configura Markdown, matemáticas y resaltado, pero no un renderer de diagramas.

Definir bloques de contenido de conversación —texto, ejemplo, tabla, diagrama y referencia— con persistencia y recuperación coherentes. Renderizar contenido no confiable con opciones restrictivas, sin ejecutar HTML/scripts arbitrarios. Incluir copiar, ampliar o exportar cuando ayude al uso real; móvil, teclado y lector de pantalla deben poder acceder a la misma explicación.

### 7.7 Evaluar comprensión y posibilidad de intervención

Crear `evals/communication/` con conversaciones representativas: pregunta sencilla, explicación técnica, comparación, incertidumbre, fallo recuperable, espera larga, corrección a mitad del trabajo y resultado parcial. Incluir ejemplos de metáforas útiles y engañosas y casos donde el formato adecuado sea sólo un párrafo.

Evaluar claridad, fidelidad, utilidad del ejemplo, saltos injustificados, carga de lectura y capacidad de corregir. En pruebas con personas, observar si pueden identificar la conclusión y sus límites, elegir el siguiente paso y señalar una interpretación incorrecta. No medir calidad por cantidad de mensajes, presencia de diagramas o frases más cortas. Conservar ejemplos revisados y una rúbrica común para comparar cambios de prompts y UI.

La aceptación requiere un recorrido temprano donde el sistema explique un hallazgo con un ejemplo o diagrama pertinente, reciba una corrección y adapte el trabajo. Una explicación persuasiva pero falsa o un resultado correcto presentado como certeza sin respaldo incumplen el contrato. La revisión humana complementa los chequeos automáticos de formato, referencias, estados y accesibilidad.

## 8. Rediseño completo de la interfaz

### 8.1 Dirección profesional

Propuesta inicial: un espacio de trabajo editorial y técnico, con tipografía legible, navegación clara, tablas y documentos bien compuestos, estados discretos y alta densidad útil. Paleta sobria con un acento funcional. La jerarquía debe surgir del contenido y las acciones; evitar contadores decorativos, gradientes arbitrarios, vidrio generalizado y pantallas llenas de tarjetas intercambiables.

El resultado no debe incluir “diseño hecho por una AI”, “AI-powered” como relleno ni estética de demo genérica. Los estados reales de agentes sí deben ser comprensibles. No inventar actividad, métricas o personas para llenar una pantalla vacía. Esta dirección es propuesta: la selección final debe apoyarse en imágenes y comportamiento.

Antes de generar conceptos, capturar y recorrer la aplicación actual con datos de ensayo. Usar `product-design:audit` para evidencia, `product-design:ideate` e `imagegen` para conceptos y `product-design:image-to-code` para implementar la referencia elegida. Las skills se aplicarán al ejecutar esas tareas; esta revisión documental no incluye una auditoría visual ya realizada.

### 8.2 Inventario obligatorio por página

Para **cada fila**, generar al menos tres imágenes independientes de concepto, compararlas, elegir una y realizar una variante móvil de la elegida. Son como mínimo **36 conceptos de escritorio y 12 adaptaciones móviles** para las rutas actuales. Diálogos y paneles compartidos requieren cobertura adicional, no otra ruta ficticia.

| Ruta / componente actual | Trabajo principal y contenido obligatorio | Familias de concepto a explorar |
| --- | --- | --- |
| `/` — `Dashboard.tsx` | Salud de proyectos, bloqueos, decisiones pendientes y siguiente acción | Resumen editorial; lista operativa; centro de actividad |
| `/projects` — `ProjectsPage.tsx` | Crear, seleccionar, comparar y archivar proyectos | Tabla con inspector; portafolio sobrio; lista agrupada por estado |
| `/epics` — `EpicsPage.tsx` | Épicas, hitos, dependencias y avance verificable | Roadmap; árbol con detalle; tabla jerárquica |
| `/tasks` — `TasksPage.tsx` | Prioridad, asignación, aceptación, bloqueos y revisión | Lista con inspector; kanban contenido; cola de trabajo |
| `/agents` — `AgentsPage.tsx` | Identidad, responsabilidad, ejecución, consumo y parada | Roster operativo; matriz de responsabilidades; sesiones con detalle |
| `/chat` — `ChatPage.tsx` | Conversación, steering, preguntas pendientes y contexto relevante | Conversación con inspector; cuaderno de trabajo; conversación y evidencias en paralelo |
| `/wiki` — `WikiPage.tsx` | Árbol documental, lectura, edición, fuentes y vigencia | Biblioteca editorial; navegador con lectura; documento con contexto lateral |
| `/findings` — `FindingsPage.tsx` | Afirmación, evidencia, hipótesis, contradicciones y procedencia | Registro de evidencia; tabla con inspector; fichas documentales sobrias |
| `/reports` — `ReportsPage.tsx` | Informes legibles, citas, versiones y exportación | Biblioteca de informes; dossier editorial; lector con índice |
| `/files` — `FilesPage.tsx` | Adjuntos, búsqueda, preview, carga y errores | Explorador dividido; lista con preview; biblioteca filtrable |
| `/repositories` — `RepositoriesPage.tsx` | Repos, branches, árbol, diffs y PRs | Explorador de código; cola de cambios; lista de repos con inspector |
| `/flow` — `FlowPage.tsx` | Ejecución real, progreso, errores, intervención y recuperación | Timeline; mapa de estados; inspector de ejecución |

Diseñar además Sidebar, Header, feed de actividad, detalle de tarea, búsqueda, selección de proyecto, confirmaciones y entrada inicial. Proponer una superficie de configuración para runtime, suscripción y salud de Ken; si se vuelve página propia, se suma al mismo protocolo de tres conceptos y adaptación móvil.

Los briefs de chat, informes, findings y detalle de tarea deben mostrar explicaciones reales con ejemplos y diagramas, acceso a fuentes y una corrección del usuario. Seleccionar conceptos por su capacidad de sostener esa interacción, además de su apariencia. La guía de comunicación de 7.5 y sus evaluaciones son parte de la aceptación del rediseño.

### 8.3 Generar, seleccionar e implementar

- [ ] Preparar briefs con objetivo, contenido realista anonimizado, acciones primarias y estados. Usar dimensiones comparables, por ejemplo 1440×1000 y 390×844.
- [ ] Empezar con una pantalla piloto de alta interacción, como `/chat` o `/tasks`: generar sus tres conceptos, seleccionar, implementar y probar un recorrido con corrección y error. Ajustar el sistema visual antes de producir en bloque el resto; el piloto cuenta dentro del inventario obligatorio, no reduce su cobertura.
- [ ] Generar las tres alternativas por página como imágenes, variando composición y jerarquía, no sólo colores. Guardar prompt, modelo, fecha, entradas y archivos en `docs/design/concepts/<pagina>/`.
- [ ] Puntuar cada propuesta: claridad de tarea 30%, jerarquía y lectura 25%, coherencia 20%, accesibilidad prevista 15%, viabilidad responsive 10%. Registrar evidencia y motivos en `docs/design/selection.md`.
- [ ] Elegir la mejor por criterio del implementador, tal como pidió el usuario; sin exigir una ronda de aprobación por cada pantalla. Justificar la elección y los defectos que deben corregirse. Las imágenes no prueban accesibilidad ni interacción.
- [ ] Unificar las ganadoras en un sistema coherente: tokens, escalas, tipografía, iconos, tablas, formularios, selección y navegación. Si una ganadora rompe ese sistema, iterarla y conservar la decisión.
- [ ] Implementar la composición seleccionada en componentes semánticos y responsive; la imagen es referencia, no una captura incrustada como UI.
- [ ] Probar datos largos, vacíos, carga, error, reconexión, permisos, falta de cuota, cancelación y correcciones. Verificar teclado, foco, contraste, zoom y lector de pantalla; aspirar a WCAG 2.2 AA y comprobarla sobre la implementación.
- [ ] Comparar capturas de escritorio y móvil con la referencia, corrigiendo desviaciones de jerarquía, densidad y contenido. Medir tareas reales y revisar profesionalismo del conjunto.

## 9. Otras mejoras necesarias

- **Seguridad local:** revisar autenticación HTTP/WS y endpoints internos; escuchar en loopback por defecto y validar origen/host. Aislar credenciales del navegador, redactar logs y eliminar contraseñas predecibles. CORS no sustituye autorización.
- **Herramientas:** mínimo privilegio por tarea, schemas validados, límites de shell, rutas normalizadas, symlinks y mounts; ejecutar cambios en un worktree/workspace por tarea. No dar una conexión SQLite arbitraria al runtime.
- **Ingesta y web:** límites de tamaño, timeouts y validación de destinos/redirecciones para fetch; proteger red interna y archivos locales. Las fuentes pueden contener instrucciones adversarias.
- **Observabilidad:** correlacionar proyecto, tarea, ejecución, agente y tool call; logs estructurados, diagnóstico de Ken, duración y cola, tokens observados y cuota si el proveedor la expone. Mostrar “no disponible” si falta el dato; no inferir un precio de API para consumo por suscripción.
- **Contratos de frontend:** generar o validar tipos desde OpenAPI y definir schemas de eventos WS; limitar invalidación al proyecto afectado. Resolver deduplicación de historial/live y reconexión mediante IDs durables, no contadores locales.
- **Calidad científica:** separar investigación, hipótesis y conclusión; citas verificadas, contraejemplos, experimentos reproducibles y limitaciones. Vincular findings con artefactos y versiones.
- **Operación y mantenimiento:** README real, instalación limpia, troubleshooting, backup/restore y upgrades de runtime/Ken; aclarar nombre Researcher/Infinibay, licencia y compatibilidad. Eliminar código muerto sólo tras comprobar uso.

## 10. Fases ejecutables y aceptación

Cada fase termina con evidencia guardada y un cambio revisable. Las fases son secuenciales donde hay dependencias; los conceptos visuales pueden prepararse después de inventariar producto y contratos. No prometer un calendario preciso antes de resolver el runtime y el estado de los datos. Separar la fijación mínima de dependencias y configuración necesaria para reproducir del upgrade completo: elegir el runtime antes de invertir en actualizaciones profundas de CrewAI u otras piezas que se van a retirar. Los upgrades de infraestructura con datos persistentes llevan su propio ensayo y no deben bloquear la prueba aislada del runtime cuando puedan posponerse con seguridad.

| Fase | Acciones y archivos principales | Resultado verificable / condición de salida |
| --- | --- | --- |
| **0. Línea base** | Inventario, copia de datos, `README.md`, manifiestos, tests existentes; `docs/modernization/baseline.md` nuevo | Instalar en entorno limpio; registrar tests/build que pasan o fallan y reproducir Stop/duplicados; no consumir modelos en import o tests comunes |
| **1. Línea base reproducible y configuración** | `pyproject.toml`, lock, `requirements.txt`, `start.sh`, config | Fijación mínima para reproducir, DB única sin pérdida, sin password predeterminada, dos arranques idempotentes y restauración probada |
| **2. Decisión de runtime + Ken** | Spike fuera de datos reales; decisión, matriz de capacidades, inventario de inferencia y alcance de refactorización engine/loop | Suscripción comprobada, llamada Ken real, aislamiento de dos proyectos, investigación con adjunto e informe persistido, streaming, corrección, cancelación y recuperación; elegir un candidato |
| **3. Primera ejecución vertical** | `backend/runtime/`, coordinación engine/autonomía, API/WS, MCP, prompts mínimos, guía de comunicación y tests nuevos | Crear una tarea, explicar un hallazgo, recibir una corrección mientras trabaja y adaptar la ejecución; cancelación, fallo de proceso y reconexión sin duplicado; herramientas y prompts compatibles con la ruta elegida |
| **4. Migrar capacidades y actualizar componentes conservados** | Orchestrator, autonomía, flows, herramientas, DB e infraestructura | Investigación→finding→reporte y tarea→cambio→review completos; wiki por proyecto, llamadas auxiliares, versiones e índices migrados; IDs e historial preservados; efectos idempotentes |
| **5. Prompts, comunicación y alineación** | Inventario, reescrituras, guía de comunicación y `evals/` | 100% de plantillas inventariadas con destino; benchmark antes/después, casos reservados, comprensión y corrección observadas, errores de contexto y coste/esfuerzo reportados |
| **6. Piloto visual y conceptos completos** | Capturas, briefs, imágenes, selección e implementación piloto | Piloto usable antes de extender; tres conceptos por cada página, ganadora razonada y sistema visual coherente; cobertura del inventario completo |
| **7. Implementación web** | `frontend/src/components/`, hooks, API y tipos; nuevos tests | Todas las rutas implementadas según sus referencias; teclado, móvil y estados reales; E2E de tareas y correcciones |
| **8. Retirada y entrega** | Eliminar LoopEngine/CrewAI y configuración obsoleta después de migrar usos | Sin imports activos del motor retirado, instalación limpia, datos migrados, documentación y recuperación ensayadas |

En las fases de código: escribir primero pruebas que fallen por el comportamiento requerido, implementar el cambio y ejecutar la comprobación correspondiente. Para migraciones, probar sobre copia y comparar conteos, relaciones y artefactos. Mantener commits acotados; no incluir cambios preexistentes del usuario.

### Casos de aceptación que no pueden quedar fuera

1. Stop durante generación y durante una herramienta lenta: el trabajo deja de avanzar, termina el proceso correcto y queda estado durable coherente.
2. Respuesta perdida después de crear un comentario o PR: el retry reconcilia y no crea otro.
3. Reinicio del backend y reconexión del navegador: recuperar estado y preguntas pendientes sin reenviar la solicitud original.
4. Usuario corrige una premisa mientras hay tareas delegadas: registrar versión, propagar corrección e impedir nuevas acciones dependientes del contexto contradicho.
5. Memoria antigua o fuente externa intenta ampliar autorización: preservarla como evidencia no confiable y respetar el alcance explícito.
6. Ken sin preparar o con timeout, cuota agotada, credenciales vencidas: estados claros, diagnóstico útil y ausencia de fallback silencioso.
7. Cambio rápido entre proyectos: ningún evento, caché, finding o proceso aparece atribuido a otro proyecto.
8. Base existente en una ruta antigua y datos nuevos tras migrar: selección explícita si hay ambigüedad y recuperación que no descarte escrituras sin advertirlo.
9. Dos proyectos con wiki `overview`, adjuntos homónimos y configuraciones distintas: identidad, lectura y edición aisladas; política global/local explícita.
10. Historial con más eventos que el límite de una página y desconexión concurrente con actividad: recuperar todos una sola vez y en orden, o señalar que hace falta un snapshot por retención vencida.
11. Trabajo de investigación desde adjunto hasta informe visible en `/reports`: herramientas expuestas al runtime y persistencia comprobadas, sin llamada auxiliar a una API no elegida.
12. Explicación de un hallazgo complejo: ejemplo simple o diagrama cuando aporte comprensión, límites explícitos y alternativa textual accesible; el usuario puede corregir una premisa y comprobar el cambio de rumbo.
13. Tarea larga, espera externa o error recuperable: estado comprensible y novedades útiles, sin silencio indefinido, mensajes duplicados ni éxito inventado.
14. Resultado de turno sin aceptación satisfecha, intento obsoleto o ejecución interrumpida: no marcar la tarea de producto como completada sólo porque `execute` devolvió texto.

### Comandos de comprobación previstos

Estos comandos se ejecutarán durante la implementación, una vez corregidos manifiestos y definidos scripts. No se afirma que pasen en el estado actual.

```bash
uv sync --locked
uv run pytest backend/tests
uv run pytest backend/tests/runtime -q
uv run ruff check backend
```

En `frontend/`:

```bash
npm ci
npm run build
npm run lint
npm run test -- --run
npm run test:e2e
```

Los scripts lint/test/test:e2e aún deben crearse. Las pruebas vivas de runtime, Ken y suscripción deben estar separadas, con límites y workspace de ensayo. Las suites comunes usan dobles de protocolo y fixtures; no deben requerir login ni red. Conservar reportes, capturas y resultados de evaluación junto a versiones de runtime, prompts y contexto.

## 11. Orden recomendado y decisiones abiertas

Empezar por reproducibilidad, protección de datos y prueba de runtime/Ken. Después, completar una tarea vertical y sólo entonces extender la migración, los prompts y el rediseño a todo el producto. Eso permite detectar pronto una arquitectura inviable sin reescribir primero las doce pantallas.

Quedan decisiones que la evidencia de implementación debe resolver: Codex o Infinidev; mantener o integrar funciones de equipos de Infinidev; versión exacta de Python/Node y dependencias; ruta de upgrade Forgejo; necesidad real de multiusuario remoto; compatibilidad y conservación de datos históricos. La propuesta inicial es despliegue local para un usuario, SPA React y SQLite. Son supuestos de planificación, no requisitos atribuidos al usuario.

La entrega final debe incluir una matriz que vincule cada requisito de este documento con su implementación, prueba y evidencia visual. Un relato del agente o una captura bonita no bastan para afirmar que la actualización está terminada.

## 12. Revisión independiente del plan

Un subagente con contexto limpio contrastó esta hoja de ruta con el repositorio y el código local de Infinidev. Sus cuatro hallazgos principales se verificaron e incorporaron: inventario de inferencia auxiliar (4.5), cobertura real de herramientas/MCP (4.3), aislamiento multiproyecto del harness Infinidev (4.1–4.2) e identidad de páginas wiki (4.4). También se incorporaron la separación de experimentos de prompting, el tratamiento de solicitudes pendientes al recuperar, la revisión mínima de prompts antes del spike y la corrección de contexto en los recorridos tempranos.

La revisión no probó los runtimes ni convirtió las alternativas en decisiones finales. La publicación de Ken como librería propia `ken-rank` en PyPI queda registrada como aclaración explícita del usuario; el checkout `../ken` se conserva como referencia de desarrollo.

## 13. Revisión por subsistema: «¿qué pasaría si…?»

Esta ampliación responde al pedido de repensar el sistema parte por parte, especialmente la comunicación entre agentes. Tres subagentes revisaron comunicación; engine/coordinación; y datos/fronteras de ejecución. El agente principal cubrió conocimiento, frontend, configuración y entradas CLI, contrastó hallazgos y consolidó los debates. Se revisaron responsabilidades y recorridos concretos; esto no equivale a ejecutar todos los flows ni a demostrar cada carrera de concurrencia.

**Lectura de las matrices:** **H** = mecanismo observado en el código; **P** = comprobación local ejecutada; **R** = consecuencia hipotética que exige reproducción. Un mecanismo confirmado no prueba que su consecuencia ya haya ocurrido con datos reales. **P0** bloquea el recorrido que exponga pérdida de datos, autoridad incorrecta o éxito falso; **P1** se resuelve antes de ampliar el uso del subsistema. Cada propuesta sigue siendo una decisión de diseño a validar, salvo requisitos explícitos del usuario.

### 13.1 Mapa de cobertura y responsabilidades

| Parte del sistema revisada | Archivos o familias inspeccionadas | Decisión que debe resolver el plan |
| --- | --- | --- |
| Identidad y roles | `backend/agents/`, registro de agentes y resolución en comunicación | Identidad estable por proyecto; rol no equivale a autoridad ni responsabilidad única |
| Comunicación entre agentes | `communication/service.py`, listeners, registries, LoopGuard, herramientas y helpers de mensajes | Una vía durable para operaciones; conversación y notificación diferenciadas |
| Intervenciones humanas | AskUser, ReplyToUser, rutas de chat/user_requests y contexto de mensajes | Recepción, respuesta y aplicación comprobables sin bloquear la conversación |
| Contrato y construcción del engine | `engine/base.py`, `__init__.py`, `orchestrator.py` | Resultado por ejecución y un único dueño de coordinación |
| Planificación e inferencia | `loop_engine.py`, `llm_client.py`, `loop_models.py` | Delegar el loop al runtime elegido y conservar políticas de producto necesarias |
| Contexto y compresión | `loop_context.py`, `summarizer.py`, `prompts/team.py` | Evidencia recuperable, vigencia y correcciones que sobrevivan resúmenes |
| Herramientas y parsing | `tool_call_parser.py`, `loop_tools.py`, `tool_executor.py`, registro de herramientas | Protocolo nativo, schemas y efectos autorizados; no compatibilidad textual por inercia |
| Cambios de archivos | `file_change_tracker.py`, herramientas de archivos y Git | Diff completo por candidato e intento; considerar shell, binarios, renames y cambios externos |
| Autonomía | AgentLoop, eventos, evaluadores, scavenger, liveness y handlers | Entrega/reconciliación sin un scheduler competidor del runtime |
| Flows y revisión | Desarrollo, code review, CI/helpers, guardrails, snapshots y FlowManager | Un recorrido de aceptación y recuperación; muestreo de investigación, no auditoría de cada rama científica |
| Estados y dependencias | `state/`, actualizaciones de tareas y sus pruebas | Reglas explícitas de transición y condiciones de versión, independientes de la apariencia del chat |
| Base y migraciones | `db/schema.sql`, `tools/base/db.py`, triggers y rutas de escritura | Transacciones, evolución de contratos y readiness real |
| Evidencia y conocimiento | `knowledge/`, herramientas de findings/wiki/reportes, ingesta web y RAG | Diferenciar fuente, afirmación y validación; conservar su procedencia y vigencia |
| Archivos y artefactos | Upload/download/delete, reportes, referencias y volúmenes | Fuente de verdad por tipo de artefacto y recuperación de operaciones parciales |
| Repositorios y publicación | Repository/branch/PR/worktree managers y cleanup | Identidad de repositorio, candidato exacto y publicación reconciliable |
| Sandbox y credenciales | `security/`, configuración, ejecución shell y CI | Frontera efectiva del runtime y del host, no sólo una carpeta por agente |
| API, MCP y eventos | Routers públicos/internos, script MCP, EventBus y WebSocket | Autorización en el servidor, eventos durables y recuperación con backpressure |
| Frontend y comprensión | Cliente/WS, stores/hooks, chat, solicitudes y renderer; inventario de doce páginas | Estado real, conversación corregible y continuidad entre proyectos y reconexiones |
| Configuración e inferencia auxiliar | Settings, user settings, probes, resúmenes, embeddings y proveedores | Snapshot por ejecución, inferencia inventariada y cambios de proveedor sin mezcla accidental |
| CLI/TUI, inicio y mantenimiento | `cli/main.py`, indexación/watcher, `start.sh`, Compose y manifiestos | Decidir qué superficies se conservan; todas usan los mismos casos de uso y migraciones |
| Ken y code intelligence | Config MCP, `code_intel/`, herramientas estructurales y cachés | Una estrategia de descubrimiento y memoria, con versiones y alcance verificables |
| Prompts y evaluación | Catálogo de roles/tareas/tecnologías, prompts dinámicos y tests | Contratos de comunicación y aceptación medidos, sin preservar reglas obsoletas por pasar tests |

### 13.2 Repensar el protocolo entre agentes

**Recomendación inicial del debate:** comandos de producto tipados más chat informativo. Conservar diálogo natural para explorar y explicar; asignar, corregir, autorizar, revisar, publicar o completar trabajo mediante operaciones validadas. Un mensaje puede expresar la intención de realizar una operación, pero el texto por sí solo no demuestra que se haya entregado, aplicado o autorizado.

Researcher posee la identidad y validez de las operaciones del producto: tarea, intento, contexto, evidencia y aceptación. Codex o Infinidev posee sus turnos, inferencia y planificación interna. Si Infinidev ya coordina un equipo, no reconstruir ese equipo con AgentLoop + flows + Orchestrator al mismo tiempo. Una cola local sirve para persistir y entregar; no debe convertirse en otra planificación LLM.

Contrato conceptual mínimo, usando campos sólo donde sean necesarios:

```text
schema_version, operation_id, project_id
task_id, run_id, attempt_id, context_version
sender_id, resolved_recipient_id
intent, correlation_id, in_reply_to
content_ref, evidence_refs, expected_preconditions
```

`content_ref` permite leer el mensaje completo; una vista previa recortada no reemplaza sus restricciones. `in_reply_to` relaciona una respuesta con la pregunta exacta, no sólo con un hilo. Los IDs de emisor/destinatario no conceden autoridad: se verifican contra las capacidades de la ejecución. El destinatario puede reasignarse de forma explícita si no está disponible, conservando historial.

No imponer una máquina de seis estados a todo comentario. Para operaciones que lo necesitan, distinguir registro durable, entrega al runtime y resultado validado; para correcciones invalidantes, distinguir además recepción de aplicación efectiva. “Leído” sólo describe lectura. Persistir operación y entrega pendiente en una transacción; la notificación en memoria despierta al consumidor, pero no es la única prueba de que haya trabajo pendiente. Un timeout de transporte conserva la misma identidad: consultar/reconciliar antes de volver a ejecutar efectos.

La versión de contexto se aplica al alcance afectado. Una corrección de un informe no invalida automáticamente todos los proyectos. Guardar qué decisiones/evidencias consumió cada intento; invalidar o revalidar sus dependientes. Una corrección recibida durante un efecto ya iniciado no lo deshace: registrar el efecto, intentar detener lo pendiente y explicar reparación o compensación.

Prioridad urgente en la cola no garantiza interrupción. El control humano debe tener un canal atendible durante el trabajo. Si el steering nativo no permite demostrar aplicación antes de un nuevo efecto dependiente, usar interrupción y reanudación desde un límite seguro. No llamar “aplicada” a una corrección por recibir un acuse de transporte. Las herramientas nativas y comandos shell también deben respetar la frontera elegida; una barrera sólo en el MCP de negocio no controla todos los efectos del runtime.

### 13.3 Escenarios de comunicación y coordinación humana

| ID / prioridad | ¿Qué pasaría si…? Evidencia y riesgo | Solución propuesta y prueba observable |
| --- | --- | --- |
| **C01 · P0** | Se guarda un mensaje y el proceso cae antes de activar al receptor. **H:** commits separados y excepción silenciada en `flows/helpers/messaging.py:48-64` y `api/routes/chat.py:86-104`; dispatcher puede retornar sin destinatario (`message_dispatcher.py:194`). **R:** chat visible y trabajo perdido que parece completado. | Operación y entrega pendiente atómicas; error de destinatario explícito. Inyectar caída entre registro y entrega; reinicio conserva intención y no duplica el efecto. |
| **C02 · P0** | Una solicitud “al rol” activa dos responsables o un broadcast no activa ninguno. **H:** fan-out por agentes del rol y retorno vacío sin destinatario en `autonomy/events.py:162-195`. | Separar solicitud con responsable único de notificación grupal. Con dos investigadores, sólo uno reclama el trabajo; un aviso colectivo no obliga a ejecutar ni responder. |
| **C03 · P0** | La respuesta llega antes del registro de espera, tarde o fuera de orden. **H:** `ask_team_lead.py:87-118` envía antes de registrar; luego busca por hilo (`123-143`), con notificación efímera. | Pregunta y respuesta durables por ID; comprobar estado antes/después de esperar. Dos preguntas del mismo hilo y respuestas invertidas deben asociarse correctamente; timeout no borra la respuesta posterior. |
| **C04 · P0** | La condición importante está al final de una delegación larga. **H:** evento guarda sólo 2000 caracteres (`autonomy/events.py:175-183`) y el handler no reabre `message_id` (`misc_handlers.py:21-32`). | Leer contenido completo por referencia y preservar restricciones. Mensaje largo con “no modificar archivos” al final debe llegar íntegro al receptor o producir límite explícito antes de ejecutar. |
| **C05 · P0** | Un agente lee una corrección y cae antes de incorporarla. **H:** `read_messages.py:106-124` marca lectura antes de devolver; no representa aplicación. | Mantener lectura separada de versión aplicada al intento. Tras fallo, la corrección sigue pendiente de aplicación y bloquea únicamente los efectos dependientes. |
| **C06 · P0** | El usuario cambia de criterio pero se reutiliza una respuesta antigua. **H:** QuestionRegistry indexa pregunta/proyecto sin versión (`question_registry.py:36-55`); AskUser reutiliza similitud (`ask_user.py:166-214`). | Respuestas con alcance, procedencia y vigencia; no deduplicar autorizaciones por semejanza. Tras A→B, la misma formulación usa B sólo donde corresponda y conserva el historial de sustitución. |
| **C07 · P0** | El usuario corrige durante una tarea larga o al agotar el presupuesto ordinario. **H:** handler síncrono y chequeo horario en `agent_loop.py:256-305`; prioridad no interrumpe. | Canal de control durable, barrera de versión y steering probado o interrupt/resume. Herramienta lenta + corrección + presupuesto agotado no impiden registrar y atender la intervención. |
| **C08 · P1** | Dos agentes se agradecen o reenvían órdenes en círculo, o un control breve enviado por SendMessageTool se confunde con un acknowledgment. **H:** LoopGuard no cubre todas las vías; `send_message.py:57-61` filtra textos de menos de cinco caracteres. Esto no demuestra que el botón Stop o el chat humano por API sufran ese filtro. | Límites por cadena causal y controles tipados; dedup por operación, no sólo texto. Un ping-pong se acota sin descartar una corrección repetida ni “Stop”; exponer bloqueo y recuperación útil. |
| **C09 · P0** | El usuario envía un segundo mensaje inmediatamente o responde justo al vencer una pregunta. **H:** `reply_to_user.py:50-70` bloquea otra respuesta durante 120 s; `ask_user.py:112-145` hace polling y expira sin condición de estado. | Idempotencia por intervención, agrupación de avisos y transiciones condicionales de solicitud. Dos mensajes distintos reciben atención; empate respuesta/vencimiento no sobrescribe una respuesta válida ni cierra la tarea por throttle. |
| **C10 · P1** | Se supone que una delegación fue comprendida porque existe un protocolo de check-in o porque el receptor comparte rol. **H:** `communication/protocol.py` declara un protocolo, pero desarrollo asigna trabajo directamente; ese archivo no demuestra su aplicación universal. | Handoff con objetivo, restricciones, aceptación, fuentes y versión; aclarar sólo ambigüedad material. Una tarea simple comienza sin ritual; una contradicción detiene su acción dependiente y muestra el motivo. |

### 13.4 Escenarios del engine, ejecución, revisión y contexto

| ID / prioridad | ¿Qué pasaría si…? Evidencia y riesgo | Solución propuesta y prueba observable |
| --- | --- | --- |
| **E01 · P0** | Dos ejecuciones consultan “sus” cambios a la vez. **H:** factory singleton y `_last_file_tracker` mutable (`engine/__init__.py:10-19`; `loop_engine.py:248-326`). **R:** atribución cruzada de diffs. | Resultado inmutable por ejecución/intento; eliminar APIs “último resultado”. A y B editan homónimos, se consultan en orden invertido y cada revisión recibe sólo su candidato. |
| **E02 · P0** | El motor devuelve texto blocked/exhausted o el guardrail rechaza siempre. **H:** `loop_engine.py:957-996,1049-1132` retorna texto; `orchestrator.py:316-321` registra DONE al retornar. | Resultado tipado y aceptación independiente. blocked, invalid, interrupted y exhausted dejan trabajo incompleto; agotamiento del guardrail no devuelve validación exitosa. |
| **E03 · P0** | Stop vence el join pero el thread o herramienta sigue vivo. **H:** parada y join en `agent_loop.py:96-110`, `flow_manager.py:114-153`; retries LLM no reciben el mismo control. | Conservar referencia/propiedad hasta reconciliar, cancelación nativa y aislamiento del proceso adecuado. Probar generación, backoff, CI y herramienta lenta; no anunciar parada completa con trabajo todavía ejecutándose. |
| **E04 · P0** | El watchdog falla un intento todavía activo y su resultado llega después. **H:** `agent_loop.py:465-489` cambia estado por antigüedad; `events.py:323-325` actualiza por ID sin versión esperada. | Propietario/intento y compare-and-set —escribir sólo si la versión esperada sigue vigente—; separar timeout de terminación. Resultado tardío queda obsoleto, sin completar ni publicar como intento actual. |
| **E05 · P0** | Reiniciar descarta las mismas instrucciones que el recovery intenta reanudar. **H:** `flow_manager.py:45-47,205-219` marca pending/in_progress fallidos antes de recuperar; `agent_loop.py:139-167` intenta restaurar in-progress. | Una política de reconciliación, sin purga indiscriminada. Reiniciar con trabajo, preguntas y correcciones pendientes conserva intención y distingue sesión recuperable de intento nuevo. |
| **E06 · P0** | Hay un efecto externo y un crash antes del checkpoint. **H:** checkpoint de paso posterior a efectos (`loop_engine.py:622-632,937-939`). **R:** replay repite comentario, PR, tarea o informe. | ID estable y recibo de operación; consultar efecto existente antes de reintentar. Simular éxito remoto con respuesta perdida y recuperar sin repetir trabajo completo. |
| **E07 · P1** | El runtime produce sólo notas/“think”, o review rechaza indefinidamente. **H:** contadores del while no avanzan con esas pseudoherramientas (`loop_engine.py:452,545-578`); rework sin límite está preservado por tests (`test_code_review_flow.py:139-150`). | Retirar esos mecanismos y exigir presupuestos/deadline/no-progreso también en el runtime nuevo. Un doble que genera actividad sin avance termina con estado y explicación honestos, sin marcar éxito. |
| **E08 · P1** | Resúmenes, reintentos o validaciones consumen recursos fuera del presupuesto mostrado. **H:** `_summarize_step` y `_apply_guardrail` hacen inferencia auxiliar sin actualizar el presupuesto global (`loop_engine.py:182-189,1071-1118`). | Presupuesto por operación, intento y proyecto; incluir todas las llamadas observables y limitar concurrencia/retry desde un dueño. Si falta consumo, mostrar desconocido, no cero. Cuota agotada no activa proveedor alternativo. |
| **E09 · P1** | La evidencia decisiva está al final de una salida o cambia un archivo que el contexto declara actualizado. **H:** truncado a 500 caracteres por mensaje y por inicio de transcript (`loop_engine.py:218-236`); caché pinned sin hash en `loop_models.py`. | Resúmenes con referencias y restricciones vigentes; revalidar contenido por revisión/hash. Insertar contraevidencia al final y editar externamente un archivo: el agente puede recuperar la fuente y detecta el cambio. |
| **E10 · P0** | Review/CI aprueba A y se intenta publicar B. **H:** modelos de revisión referencian rama sin SHA; rework regresa a review sin repetir gate (`code_review_flow.py:324-383`); CI elige un repo sin fijar candidato. | Candidato `(repo_id, base_sha, head_sha, context_version)` y aceptación asociada. Commit nuevo invalida los checks pertinentes; CI/review de otro repo/worktree no autorizan publicación. Independencia del reviewer debe comprobarse, no inferirse por nombre del rol. |
| **E11 · P1** | “No hubo tests” se presenta como “tests pasaron” o se continúa después de agotar arreglos. **H:** `ci_helpers.py:61-67` acepta exit 5 como `ci_passed`; rutas del flow pueden continuar hacia revisión. | Distinguir passed, failed, no_tests, skipped y error de infraestructura; política explícita por proyecto. Repo ausente, comando roto y cero tests producen resultados distintos y ninguna evidencia de éxito inventada. |
| **E12 · P0** | Cambios por shell o tareas anteriores no están en el último tracker y se mergea sólo por DONE. **H:** tracking por herramientas conocidas, último tracker en revisión y merge sin consultar veredicto (`orchestrator.py:369-372,401-413`). | Diff Git completo del candidato, no inferido del relato; aceptación gobierna merge. Dos tareas y un cambio por shell deben estar incluidos; un veredicto rechazado impide publicar aunque el turno termine normalmente. |

El contrato del runtime debe declarar capacidades realmente implementadas. No conservar parámetros como `output_pydantic` o `summarizer_enabled` si la implementación no los cumple. Las pruebas heredadas que protegen mecanismos retirados o rework ilimitado se sustituyen por pruebas de comportamiento deseado, manteniendo visibles los cambios deliberados de semántica.

### 13.5 Escenarios de datos, Git, aislamiento y operación

| ID / prioridad | ¿Qué pasaría si…? Evidencia y riesgo | Solución propuesta y prueba observable |
| --- | --- | --- |
| **D01 · P0** | Falla una migración y el backend sigue aceptando escrituras. **H:** `tools/base/db.py:254-258` captura y no propaga; `api/main.py:63-65` continúa. | Un dueño de migraciones y versión mínima para readiness; fallo visible y reparable. Interrumpir cada migración sobre copia: no aceptar escrituras sobre esquema incompleto, comprobar integridad y claves foráneas antes de habilitarlas. |
| **D02 · P1** | SQLite está ocupado y la petición bloquea el event loop, incluido Stop. **H:** busy timeout/retry con sleep en `db.py:25-72`; rutas async hacen llamadas DB síncronas. | Transacciones cortas y trabajo bloqueante fuera del loop, concurrencia acotada y timeout explícito. Mantener un lock de ensayo: health/WS/control siguen atendibles y no se repiten efectos. Threads no eliminan la contención entre escritores. |
| **D03 · P0** | Se confirma negocio pero no su evento durable. **H:** commits y publicación separados en `api/routes/tasks.py:134-146,238-260`. | Estado y evento durable en la misma transacción; emitir desde lo confirmado. Crash antes/después del commit deja una transición recuperable y no requiere broker distribuido. Revisar interacción con triggers para no generar dos eventos equivalentes. |
| **D04 · P0** | Un resultado tardío devuelve una tarea cancelada a in_progress/done. **H/P:** `state/machine.py:6-8` permite toda transición a otro estado; la comprobación local dio True para backlog→done y done→pending, mientras sus tests esperan False. Escritura de tareas sólo por ID. | Definir grafo de producto y reglas de reapertura explícitas; separar tarea, ejecución e intento y usar versión esperada. Carrera Stop/corrección/completion no revive trabajo obsoleto; reapertura legítima crea un nuevo intento trazable. |
| **D05 · P0** | El informe está en disco, pero falla la DB y la herramienta devuelve éxito. **H:** `write_report.py:66-102` permite `artifact_id=None`; ya existe `artifacts.content`. Upload/delete también tienen pasos separados. | Texto canónico en DB y exportaciones reconstruibles; binarios con publicación comprobada y reconciliación de huérfanos. Disco lleno, error DB o crash no producen éxito sin artefacto recuperable. |
| **D06 · P0** | Dos proyectos usan repo `app`, branch `task/1`, o wiki `overview`. **H:** repos únicos por proyecto, branches únicos globalmente (`schema.sql:182-217`), update de merge sin proyecto (`branch_service.py:153-158`); wiki también presenta conflicto. | Identidad por `repo_id` y claves de dominio con alcance; migrar consultas y referencias ambiguas. Ambos proyectos coexisten y merge/cleanup/edición afecta sólo al elegido; definir documentos globales explícitamente. |
| **D07 · P0** | `target_branch` difiere del checkout actual o se pierde la respuesta de un merge. **H:** `local_worktree.py:123-145` recibe destino pero mergea en checkout actual; `pr_service.py:133-145` separa Git y escrituras DB. | Verificar repo/base/head/destino antes del efecto; operación reconciliable por ID y SHAs. Cambiar checkout o avanzar base invalida la precondición; retry detecta merge ya realizado. |
| **D08 · P0** | Cleanup elimina un worktree con cambios útiles o lo recrea reseteando su rama. **H:** `worktree_manager.py:91-102,168-195` usa `-B`, removal forzado y registro posterior sin comprobar siempre el resultado; workspace cleanup usa rmtree. | Workspace por intento, comprobar dirty/untracked, poner en cuarentena y aplicar retención antes de borrar. Crash/cleanup conserva cambios pendientes y un borrado fallido no figura como completado. Coste: disco y gestión de retención. |
| **D09 · P0** | Se reintenta crear un repo después de haber creado remoto o hecho push. **H:** `repository_manager.py:63-178` crea remoto y puede reutilizar local, cambiar origin, hacer force push y registrar DB al final. | Separar crear, adoptar y reparar; reconciliar remoto/local/DB y verificar precondiciones. Reintentar un alta parcial no cambia origin ni reescribe historia de un repo preexistente por asumir que era nuevo. |
| **D10 · P0** | Un agente evita el MCP y llama directamente al host o a SQL interno. **H:** script MCP envía sólo Content-Type; routers internos no añaden autoridad por ejecución y WS acepta project_id (`api/main.py:129-159`). | Autorización en el servidor con proyecto/run/capacidades derivados de credencial validada; separar sesión humana y autoridad de ejecución. Token A no accede a B por IDs, HTTP, SQL ni WS. Configurar MCP no asegura el host. |
| **D11 · P0** | Un pod lee adjuntos de otro proyecto, sigue un symlink o usa un report_id ajeno. **H:** mounts completos de artifacts/uploads (`pod_manager.py:112-125`); lookup de reporte por ID sin proyecto (`read_report.py:50-56`). | Mounts por ámbito, referencias de entrada de sólo lectura, contención de rutas y autorización por recurso. Pruebas con nombres iguales, symlink externo e IDs cruzados impiden lectura/borrado fuera del alcance. |
| **D12 · P0** | Código del agente o de CI lee credenciales del host y las envía por red. **H:** defaults permiten ejecución sin sandbox, auth Git copiada y token bootstrap amplio; CI declara bypass del sandbox (`ci_helpers.py:16-29`). **R:** exposición por código ejecutado. | Definir la frontera para TODA ejecución, incluido CI; secretos mínimos gestionados por host y controles de red compatibles con el runtime. No montar todo OAuth en workspace. Ensayar código adversario ficticio sin secretos reales; investigar y autenticar la suscripción debe seguir funcionando. |
| **D13 · P1** | Un navegador lento acumula broadcasts o un restore cambia de carpeta. **H:** WS envía secuencialmente sin cola/timeout (`websocket.py:55-96`); archivos conservan rutas absolutas/de pod y Git tiene referencias cruzadas. | Backpressure por cliente y resync; backup consistente con manifiesto de storage y repos/worktrees. Cliente bloqueado no retrasa sanos ni consume memoria ilimitada; restore en otra ruta conserva hashes, relaciones y lectura de artefactos. |

### 13.6 Escenarios de conocimiento, frontend, configuración y superficies de uso

| ID / prioridad | ¿Qué pasaría si…? Evidencia y riesgo | Solución propuesta y prueba observable |
| --- | --- | --- |
| **U01 · P0** | Una fuente web parece consultada pero no se guarda como evidencia. **H/P:** `knowledge_ingest.py:55-60` inserta `title`; el schema exige `topic` y task_id no nulo. SQLite en memoria rechazó el INSERT por columna inexistente; corregir sólo el nombre aún rechaza task_id None. | Unificar ingesta con el contrato de findings o crear una entidad de fuente separada con alcance explícito. Probar contra el schema/migraciones reales; un fallo de persistencia se muestra y no se presenta como evidencia registrada. |
| **U02 · P1** | Una fuente cambia o una inferencia provisional se reutiliza como hecho validado. **H:** ingesta guarda URL y texto truncado; findings tiene tipos/estados, pero `search_findings.py:75-92` no filtra estado y limita candidatos a los 500 más recientes. **R:** pérdida de contraevidencia o certeza falsa. | Fuentes con fecha/revisión/hash y extractos recuperables; preservar tipo/estado/procedencia en recuperación y resumen. Caso con finding superseded y fuente modificada conserva advertencia y no convierte similitud en validación. |
| **U03 · P1** | Cambia el modelo de embeddings o Ken está indexando mientras llega una consulta. **H:** hay varios índices/cachés y configuración derivada de proveedor. | Versionar modelo/dimensión/revisión de corpus; reconstrucción verificable, indicador de cobertura/antigüedad y sin mezcla entre proyectos. Probar índice viejo/nuevo y evidencia ausente: resultado vacío no se explica como “no existe” sin conocer cobertura. |
| **U04 · P1** | Llega historial después de un evento vivo, o un socket antiguo responde tras cambiar de proyecto. **H:** `activityFeed.ts:26-29` reemplaza feed con historial; callbacks de `api/websocket.ts:55-78` usan estado mutable sin generación de conexión. **R:** pérdida visual o mezcla de eventos. | Merge por ID durable y filtros proyecto/run/generación; invalidar callbacks anteriores y recuperar desde cursor. Intercalar historial/live y A→B→A deja el feed correcto, sin borrar eventos nuevos ni reconectar el proyecto equivocado. |
| **U05 · P1** | Hay varias preguntas pendientes, una opción tiene valor distinto de su etiqueta o el hilo se corta. **H:** ChatPage muestra sólo `requests[0]` y normaliza objetos a texto (`47-58`); hook permite thread_id pero el modelo HTTP no lo incluye y la ruta crea un UUID nuevo. | Bandeja visible con contexto, prioridad y estado; conservar option IDs y thread/correlation como contrato. Dos preguntas y una corrección llegan a su solicitud/hilo; cambiar de proyecto no envía la respuesta al contexto anterior. |
| **U06 · P1** | Se actualiza configuración durante una tarea o se corta una escritura de settings. **H:** `user_settings.py:24-31` hace read-modify-write directo y `reload_all` muta settings globales; varios clientes tienen cachés singleton. | Snapshot de configuración por intento, cambios validados y escritura atómica/con control de versión. Indicar qué se aplicará al próximo intento; dos editores no pisan cambios silenciosamente y una tarea no mezcla proveedor o credenciales a mitad del trabajo. |
| **U07 · P1** | El usuario entra por CLI/TUI en vez de web o instala sobre directorio vacío. **H:** CLI usa ProjectOrchestrator, inicialización DB sólo consulta existencia (`cli/main.py:47-68`) e indexa project_id 1 por defecto. | Conservar CLI/TUI sólo con alcance definido y mismos casos de uso/adaptador/migraciones; retirar rutas alternativas obsoletas de forma documentada. Instalación vacía y proyecto cuyo ID no es 1 funcionan sin un motor viejo oculto ni probes de pago inesperados. |
| **U08 · P1** | La explicación suena convincente aunque perdió evidencia, el diagrama no carga o falla una herramienta y la UI calla. **H:** renderer actual no implementa diagramas; cliente/WS y varias rutas tienen manejo silencioso. **R:** usuario interpreta ausencia de estado como éxito. | Bloques explicativos con alternativa textual, errores visibles, fuentes abribles y corrección asociada al intento. Prueba humana identifica conclusión/límite y puede corregir; renderer inválido o desconexión no pierden contenido ni muestran éxito inventado. |

### 13.7 Debates y alternativas que quedan documentadas

| Problema debatido | Alternativas comparadas | Recomendación y condiciones |
| --- | --- | --- |
| Comunicación agente–agente — revisión cruzada comunicación/engine | Chat libre; APIs tipadas con chat informativo; envelope híbrido para todo mensaje | Empezar por APIs tipadas + chat legible. Añadir metadatos de diálogo donde aporten trazabilidad; evitar un protocolo pesado para cada comentario. Mantener exploración natural sin usarla como autorización o resultado validado. |
| Quién coordina el trabajo — comunicación/engine | Conservar AgentLoop + flows + Orchestrator + equipos del runtime; un único recorrido con dueño claro | Researcher controla operaciones y aceptación; runtime controla inferencia. Migración vertical por tarea/proyecto, sin dos dueños del mismo intento. Reemplazo total acotado sólo si conservar contratos cuesta más, con datos y recuperación protegidos antes. |
| Entrega durable — comunicación/engine | Notificación en memoria; cola/outbox local; broker externo | SQLite y entrega reconciliable como mínimo local. Persistir mensaje/operación y entrega en transacción; notificación efímera sólo optimiza latencia. Broker sólo con una necesidad de despliegue/carga demostrada. |
| Correcciones durante ejecución — comunicación/engine | Mensaje urgente al final de la cola; steering nativo; interrupt/resume | Steering si ofrece las garantías probadas; si no, interrumpir y continuar desde estado seguro. Preservar intención del usuario y efectos ya ocurridos; no garantizar deshacer lo irreversible. |
| Publicación de artefactos — datos/engine | Ficheros siempre canónicos; DB siempre canónica; contrato según tipo | Informes de texto en `artifacts.content`, exportaciones reconstruibles; binarios/repos canónicos en storage con hash, metadata y reconciliación. Evitar estados ceremoniales para cada mensaje si una transacción basta. |
| Autonomía frente a pedir aclaración — comunicación/engine | Preguntar por todo; continuar siempre tras timeout; continuar sólo lo independiente | Supuestos reversibles explícitos para trabajo independiente; bloquear efectos cuya autorización o aceptación dependa de la respuesta. No tratar el silencio como acuerdo ni introducir aprobaciones universales por check-in. |
| Red y credenciales — datos/engine | Autoridad completa dentro del workspace; host mediador; egress restringido | Autoridad mínima gestionada por host y frontera probada del runtime, sin prometer aislamiento que no existe. Sigue abierto cómo permitir investigación, instalación y login sin entregar credenciales generales al código; el spike debe demostrarlo. |

Las recomendaciones son conclusiones razonadas del debate, no acuerdos atribuidos al usuario ni resultados ya implementados. Persistencia adicional, restricciones o nuevas capas deben justificarse por los escenarios anteriores; si un mecanismo del runtime ya satisface el contrato, reutilizarlo.

### 13.8 Cómo convertir estos escenarios en ejecución y aceptación

- **Fases 0–1:** reproducir incompatibilidades de schema/estados y fijar una línea base; preservar evidencia y datos. No modificar tests para que legitimen estados o pérdidas accidentales.
- **Fase 2:** la decisión de runtime incluye C01/C04/C07, E02–E08/E10, D10–D12 y U03; comprobar capacidad de herramientas, control humano y aislamiento en un workspace de ensayo. Antes de cualquier prueba real con suscripción, imponer límites mínimos de tiempo, consumo/turnos y concurrencia, más parada ante falta de progreso; comprobarlos primero con dobles. Si falta medición de tokens/cuota, declararla desconocida y mantener límites verificables de tiempo y trabajo. La evaluación exhaustiva de E07/E08 puede continuar después. Los casos no demostrables quedan como limitación explícita del candidato, no como check aprobado.
- **Fase 3:** primera operación durable con identidad de intento, entrega, mensaje completo, corrección aplicada, resultado tipado y evidencia recuperable. Probar fallos con dobles controlados antes de gastar suscripción en prompts.
- **Fase 4:** migrar los demás escenarios de coordinación, revisión, Git, datos y recuperación por recorridos; retirar rutas duplicadas cuando sus consumidores usen el nuevo contrato. Ningún P0 expuesto por un recorrido puede quedar oculto detrás del éxito de una demo.
- **Fases 5–7:** llevar a evaluación de prompts y recorridos UI los casos C04–C10 y U02–U08; observar comprensión y corrección, no sólo snapshots visuales. Incluir explicaciones con ejemplos/diagramas y recuperación de fallos.
- **Fase 8:** matriz `ID de escenario → implementación → test/evidencia → estado → limitación conocida`; ensayar restore, actualización, cuotas, saturación, cleanup y revocación. Pasar una prueba de formato o recibir un reporte del agente no cierra un escenario de negocio.

Durante implementación, cada escenario debe tener un test determinista de contrato o una prueba reproducible adecuada, y las verificaciones con el runtime real que correspondan. Utilizar pausas controladas y fallos inyectados para las carreras; no sustituirlos por sleeps arbitrarios. Las pruebas de código no demuestran por sí solas comprensión humana, aislamiento externo o compatibilidad de un proveedor.
