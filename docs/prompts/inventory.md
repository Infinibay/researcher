# Inventario y revisión de prompts

Catálogo nativo versión2; revisión inicial sobre `85f7acd`, actualizada después de
retirar autonomía, plantillas de roles y lectores de proveedores antiguos sobre `c5a7775`. El [inventario detallado](inventory.json)
contiene 83 entradas candidatas de 279 archivos Python. **No son 83 prompts distintos
ni 83 evaluaciones con modelos.** Se archivan 515 entradas de los módulos eliminados,
conservando sus decisiones históricas en `retired_entries`.
El corte de autonomía archiva 144 candidatos de las plantillas históricas y
revalida dos candidatos con AST idéntico frente a consumidores modificados.
El cambio de línea de la descripción de la API conserva su `previous_id`.
Se mantiene íntegro el catálogo nativo; retirar las plantillas sin consumidores
no equivale a validar sus sustitutos con personas o modelos reales.
El corte de flows archiva seis candidatos de mensajes y estados históricos;
revalida trece candidatos con AST idéntico frente a sus consumidores modificados.
No cambia instrucciones nativas. Las tres funciones de metadatos de proyecto
retenidas ya no dependen de flujos ejecutables.
El corte de servicios elimina nueve módulos y añade el lector de historial del
propietario; no modifica candidatos ni decisiones de prompts. Los protocolos
antiguos retirados no se trasladan a instrucciones del runtime nativo.
El corte de API interna archiva la descripción del parser del CLI y revalida
las dos descripciones de metadatos sin cambios cuyos consumidores incluyen la
factoría HTTP. No cambia instrucciones de agentes ni incorpora prompts nuevos.
La retirada de bibliotecas/auxiliares elimina cinco módulos de la fuente inventariada
sin cambiar candidatos, descripciones ni decisiones semánticas de prompts.
El corte de conocimiento archiva45 candidatos y revisa dos descripciones:
búsqueda conjunta con cobertura/permisos por fuente y lectura de informes con
procedencia histórica explícita. Se revalidan48 AST sin cambios contra los
consumidores modificados; no hay revisiones estáticas pendientes.
El corte de proyecto archiva31 candidatos y revisa cuatro instrucciones/descripciones
para hitos opcionales y lectores de épicas/hitos: evidencia, suposiciones y fechas
propuestas diferenciadas; contexto mutable sin autoridad. Se revalidan57 AST
sin cambios contra los consumidores modificados. El cambio de línea del catálogo
de planificación conserva su identidad previa en `previous_id`.
Las cinco descripciones nuevas de comunicación explicitan identidad admitida,
pregunta exacta, observaciones frente a suposiciones, límites de lectura y
recepción sin comprensión ni autoridad. Se revalidaron42 candidatos cuyo AST
no cambió contra el registro de rutas, permisos y consumidores modificados.
La retirada posterior archiva28 candidatos y añade dos descripciones de lectura
de avisos: alcance proyecto/global, vigencia, atribución histórica no verificada,
texto mutable y ausencia de autoridad. Se revalidan45 candidatos con AST idéntico
contra el catálogo de lecturas y consumidores de preguntas retirados. Otros
servicios y protocolos antiguos siguen pendientes; no se declaran aceptados por
la existencia de un reemplazo.
Incluye plantillas, constructores, descripciones de herramientas, campos de schema,
valores de entrada y falsos positivos explícitamente excluidos.
Los baselines/casos de evaluación y los prompts de conceptos visuales se conservan
como artefactos de sus propios ensayos; no se convierten en política de agentes.
Las siete descripciones de tareas/continuidad se revisaron contra sus schemas,
permisos y recorrido MCP/API/SQLite: distinguen contexto de autoridad,
observaciones de suposiciones y recibo original de nota actual. Se revalidaron
35 candidatos con AST idéntico afectados por los cambios de consumidores.
La retirada posterior del paquete de tareas archiva 56 candidatos, conservando
sus decisiones históricas; no cambia los prompts nativos.
Tampoco se reescriben arbitrariamente textos del usuario, fuentes o errores recibidos.
Context7 añade dos descripciones revisadas contra el handler, sus permisos y el
recorrido MCP/HTTP/SQLite; se archivan seis entradas antiguas. Las 29 descripciones
previas del mismo módulo se revalidaron comprobando AST literal y consumidores
directos sin cambios; no se aprueban automáticamente instrucciones nuevas.
Spider añade una descripción revisada y archiva cuatro anteriores. Se comprobaron
31 literales nativos sin cambios y 20 fuentes históricas cuyo único consumidor
cambiado fue el export del paquete web al retirar Spider. La nueva descripción
explicita cuota separada, modos, captura/cita y límites de la parada remota.

La consolidación de código archiva 95 entradas adicionales y revisa la política
de desarrollo: Ken para descubrir/leer, comandos para escribir, referencias y
literales diferenciados, revisión del diff y comprobación del candidato.

La retirada de adaptadores archiva57entradas adicionales;17textos web conservan
bytes idénticos y se revalidan contra el único cambio de su consumidor directo:
retirar el export CodeDocsSearch. Ese corte era previo a la política y retirada web actual.

La retirada web archiva otras 17 entradas. Se revisan las descripciones de captura
web y Spider: snapshot Markdown/citas, robots/frecuencia y límites de comprobación
remota. Otros 30 candidatos conservan AST literal y se revalidan sólo contra ese
diff. La eficacia con modelos y comprensión humana siguen pendientes.

Cada entrada identifica módulo/símbolo/líneas, objetivo, variables, consumidores
directos, bytes de fuente y tamaño UTF-8 cuando el literal es conocido, reglas o
conflictos de revisión y casos de evaluación. Un tamaño dinámico desconocido queda
nulo; no se inventan tokens ni costes. Los consumidores por imports son un límite
inferior: una lista vacía no prueba ausencia de uso.

Las [decisiones explícitas](review-decisions.json) están ligadas al hash de la
fuente y de los consumidores directos del módulo. Una plantilla nueva no queda
revisada por pertenecer a una familia conocida. Un cambio relevante marca su
decisión como obsoleta; el comprobador rechaza entradas sin revisar. Es evidencia
de qué se decidió sobre qué fuente, no una prueba automática de que la decisión
sea correcta o de que se conozcan todos los consumidores dinámicos.

| Familia | Entradas | Decisión y motivo |
| --- | ---: | --- |
| Política común y composición nativa |5| Fusionada/reimplementada: una sola política de contexto, evidencia, corrección, Ken y autoridad; selección por capacidad |
| Perfiles nativos y recetas del host |8| Seis reescritos y dos conservados; reglas específicas separadas de las comunes |
| Descripciones de herramientas nativas |43| Conservadas tras leer su texto y comprobar el productor; límites, identidad original, paginación y resultados desconocidos explícitos |
| Plantillas de roles anteriores |144| Conservadas como históricas, fuera de la composición nativa; no adaptar el protocolo de un loop retirado |
| Schemas/descripciones del catálogo anterior |104| Conservados para lectores históricos opt-in; no exponer sus permisos por rol, SQL, push o certeza aparente al runtime nativo |
| Coordinación antigua restante |6| Retirada de consumidores pendiente; no son instrucciones del runtime nuevo. Engine y constructores eliminados quedan archivados |
| Proyección de entrada/fuentes/feedback |3| Conservada como datos atribuidos; no convertir texto recibido en política confiable |
| CLI/OpenAPI, instrumentación y readiness |15| Excluidos como instrucciones de agente: metadatos humanos/de entrada, scanner o fixture fijo de protocolo |

La retirada física de código heredado sigue siendo una tarea del plan. Su
conservación documental no valida los comportamientos anteriores ni habilita
sus modelos. El único warmup directo todavía encontrado se reemplazó por un
rechazo antes de HTTP, renderizado de roles o lectura de credenciales.

## Catálogo que realmente se envía

`backend/prompts/native.py` selecciona investigación científica, investigación
exploratoria, planificación, desarrollo, revisión de hallazgos, revisión de
candidato o auditoría readonly. Conserva además el perfil de referencia del
adaptador Codex anterior. Los runtimes ya no reconstruyen la combinación de
políticas mediante sus propios ternarios e imports de cada rol.

La cabecera `RESEARCHER_POLICY 2 <perfil>` y el hash de todo el texto permiten
identificar la política efectivamente enviada. La instantánea original existente
conserva esos bytes y el catálogo de herramientas. No se etiqueta retrospectivamente
una instrucción histórica sin cabecera ni se confunde entrega con comprensión.

Los nombres de herramientas y sus límites siguen en sus contratos tipados.
En `business_definitions.py`, `inspect.getdoc(handler)` produce la descripción
real: los docstrings afectan tanto a Ken como al contexto que recibe el modelo.
Los catálogos de comandos/revisión/planificación tienen descripciones explícitas.
La variante de workspace privado writable se anuncia sólo después de comprobar
la autoridad real de desarrollo. Una descripción nunca concede ese permiso.

## Cambios de prompting y criterio de libros

Se aplicaron las skills de *A Philosophy of Software Design* y *The Pragmatic
Programmer*: una interfaz de selección que oculta la composición, una fuente de
verdad para reglas compartidas, cambios completos observables y feedback que
distingue resultados de suposiciones. No se pegaron libros ni se añadieron capas
para simular otro loop LLM.

Las instrucciones separan política del host y datos atribuidos; distinguen
testimonio, ejemplo, observación, interpretación y suposición. La profesión no
prueba contexto compartido. Piden el camino explicativo con menos saltos
injustificados, permitiendo introducir un concepto nuevo antes que una metáfora
deformante. Un ejemplo, una interpretación explícita o un resultado inspeccionable
permiten corregir; no se exige confirmación repetitiva ni pensamiento interno.

Se mantuvieron las garantías específicas sobre citas, ventanas sin leer,
prerrequisitos, revisión operacional frente a corrección, límites científicos y
aceptación del propietario. Se retiraron del destino las jerarquías antiguas de
contacto humano, pseudoherramientas y bandas numéricas de certeza inventadas.
La estructura y ejemplos siguen la [guía oficial de prompting](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml),
pero su eficacia en este producto todavía necesita evaluación.

## Comprobación y evaluación pendiente

```bash
python scripts/audit_prompt_inventory.py --check
python -m evals.prompts.measure_profiles
python -m pytest backend/tests/runtime/test_prompt_catalog.py backend/tests/runtime/test_prompt_inventory.py
```

La [comparación](profile-comparison.json) mide bytes/hashes, no eficacia. El texto
de investigación científica pasó de13581a10250bytes, auditoría de10155a6363 y
desarrollo de5773a4999. Planificación, exploración y revisión crecieron al añadir
reglas comunes antes ausentes. No se presenta como reducción universal de consumo.

El [baseline exacto](../../evals/prompts/baseline.json) y los
[casos de desarrollo/reservados](../../evals/prompts/cases.json) permiten comparar
sin cambiar simultáneamente modelo, esfuerzo, herramientas o fuentes. Las pruebas
de código verifican selección, hashes, revisión obsoleta, rechazo de warmup y la
política enviada/conservada en un turno con generación/Ken controlados. **No prueban
calidad del modelo, comprensión humana ni validez científica.** Esas evaluaciones
continúan pendientes y usarán la suscripción OpenAI, sin fallback de API facturada.
