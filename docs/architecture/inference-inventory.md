# Inventario de inferencia y servicios auxiliares

Estado comprobado el **2026-11-07**, sobre el producto de `294943d`. Las rutas
antiguas enumeradas en versiones anteriores ya no son rutas activas.
**E08 sigue abierto por la contabilidad acumulada de auxiliares locales**;
el presupuesto durable de turnos ya está conectado.

## Generación del producto actual

| Responsabilidad | Entrada y control actual | Evidencia y límite |
| --- | --- | --- |
| Investigación, desarrollo, revisión documental/de código y planificación | `RuntimeService` selecciona el catálogo, vincula el intento y llama a `SQLiteRunStore.reserve_input` antes de `session.run`. Todas esas variantes pasan por la misma reserva. | El registro conserva intento, política, modelo y uso observado. Una reserva original no permite reenviar el turno tras una respuesta incierta. |
| Turno nativo | `CodexSession.run` contiene el único literal ejecutable `turn/start` encontrado en el AST del backend de producto. Exige cuenta ChatGPT y proveedor OpenAI; limita tiempo, falta de progreso, herramientas, salida y tokens observados. | Las notas no reinician el plazo de progreso. Terminar un turno no acepta una tarea. No se observan todas las llamadas internas de Codex. |
| Presupuesto de proyecto | Reserva transaccional compartida, máximo acumulado observado y retención conservadora si falta consumo. El propietario revisa límites desde la web con versión y recibo originales. | Reiniciar o recibir una observación menor no devuelve capacidad reservada. Consumo desconocido no significa cero, facturación ni cuota disponible. |
| Revisión y continuación | La revisión requiere solicitud explícita y actor independiente. Rechazo/confirmación incierta no crean otra revisión ni rework. Continuar una entrega cerrada requiere nueva decisión del propietario. | La historia conserva objeciones al mismo candidato; el desbordamiento bloquea aceptación sin ocultar la cola. |
| Autenticación y refresco | `subscription_auth.py` y `subscription_provider.py` conservan identidad de cuenta y acotan refrescos/solicitudes pendientes. | No generan texto. Fallo, cambio de cuenta o límite retiran la conexión sin fallback de proveedor ni replay. |

[Presupuesto del proyecto](project-budget-policy.md),
[contabilidad e historial](owner-history-budget.md),
[herramientas antes del efecto](host-tool-budget.md),
[autenticación](subscription-auth.md).

## Trabajo auxiliar que no es generación por suscripción

| Servicio | Qué hace y cómo se acota | Límite o pendiente |
| --- | --- | --- |
| Encoder local | `research/semantic.py` y `semantic_worker.py`: pesos/tokenizer fijados, trabajo offline, respuesta con lotes/vectores y límites observados. Plazos, tamaños, CPU/memoria y una plaza de procesamiento compartida. | No reserva ni acumula duraderamente ese consumo por proyecto. Repetir consultas en distintos intentos no agota un cupo acumulado propio. Pendiente concreto de E08. |
| PDF y extracción | `research/worker_transport.py`: IPC, salida y plazos acotados; cancelación y cierre físico del hijo antes de liberar la plaza compartida con semántica. | Límites por operación/servicio no sustituyen un registro y cupo por proyecto. Bytes, vectores y CPU no son tokens generativos. |
| Ken obligatorio | Herramientas Ken mediante MCP con ámbito de workspace. `ken-rank` publicado fue ensayado; versión y activos del host son explícitos. | Preparación, calidad y compatibilidad publicada tienen requisitos propios. Un candidato local de compatibilidad no equivale a una publicación adoptada. |
| Web pública | `research/web_fetcher.py`: HTTPS público con límites/procedencia, sin cookies, proxy o Authorization heredados. Búsqueda nativa con política explícita. | Capturar una fuente no prueba comprensión. Búsquedas internas del runtime sólo se contabilizan según su telemetría. |
| Git, comprobaciones y publicación | Operaciones con dueño, permisos y recibos propios; terminar inferencia no autoriza publicación. | Efectos/recursos distintos de generación. Recuperación física y límites agregados conservan requisitos propios. |

El launcher limita el servicio y sus descendientes; los actores tienen dominios
separados. Esos límites no equivalen a un cupo acumulado de auxiliares por proyecto.
Arrancar uvicorn directamente tampoco adquiere las garantías del launcher.
[Recursos del servicio](../modernization/service-resources-review.md),
[encoder local](semantic-source-retrieval.md).

## Retirada de las rutas históricas

| Ruta anterior | Estado actual |
| --- | --- |
| Engine, cliente LLM, resumidor y guardrails del loop | Retirados; no queda un segundo bucle de generación. |
| Agentes/CrewAI, flows/helpers y memoria knowledge/service | Constructores, flujos y memoria de framework retirados; leer historia no ejecuta esos productores. |
| Resumen LLM de prompts/team | Lectura atribuida y acotada de conversación, con omisiones explícitas y sin cliente generativo auxiliar. |
| Deep research, herramientas RAG y wrappers documentales CrewAI | Adaptadores retirados; captura/recuperación nativa no abre un cliente remoto de embeddings. |
| Deduplicación/embeddings Chroma y probes antiguos | Implementaciones/proveedores retirados; la recuperación local actual declara identidad del modelo. |
| `backend/scripts/warmup_prefix_cache.py` | **Compatibilidad inerte conservada**: main explica retirada y sale con2; _warmup_one rechaza antes de HTTP. Existir no significa inferencia activa. |
| Serper, Spider y Context7 del catálogo anterior | Adaptadores de tools/web retirados; no se heredan como servicios implícitos. |

CrewAI, crewai-tools, LiteLLM, Ollama, Chroma y el SDK OpenAI no están instalados
en el entorno de producto examinado. Eso no describe instalaciones externas.
El exportador Chroma conserva un entorno aislado y obligaciones de migración/
seguridad pendientes. Los shims Infinidev de `evals/runtime` son evaluación,
no un segundo adaptador productivo.

## Alcance y siguiente requisito funcional

Se analizaron **289 archivos Python de producto** con AST: imports estáticos de
las seis familias indicadas, llamadas generativas conocidas y el literal
`turn/start`. No aparecen esos imports/calls antiguos; se encontró la entrada
nativa indicada. Se conservan hashes y límites en el
[inventario comprobado](../modernization/engine-acceptance-inventory.json).
La aserción inicial de ausencia encontró el stub de warmup; se leyó su código
y se clasificó correctamente sin modificar el producto.

No se afirma ausencia universal de llamadas dinámicas/transitivas ni conocimiento
de la cuota interna de Codex. Las pruebas controladas no evalúan comprensión,
calidad generativa o facturación.
[Comportamiento y aceptación de E07/E08](../modernization/engine-acceptance-review.md).

E08 necesita reservar trabajo auxiliar local **antes de ejecutarlo**, conservar
consumo medido/desconocido y recibos ante respuesta perdida/reinicio, y mostrarlo
al propietario. Debe cubrir consultas del agente y del usuario con una política
por proyecto. Mostrar contadores sin controlar admisión no completa el contrato.
