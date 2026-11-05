# Investigación científica con el propietario nativo

El recorrido científico ya utiliza la sesión Codex admitida, Ken MCP y los mismos
hallazgos, informes, wiki, preguntas, revisión independiente y aceptación del resto
del producto. No necesita otro loop LLM, un segundo registro de hipótesis ni otro
almacén de síntesis. El corte exploratorio anterior sigue vigente.

## Resultados de dominio conservados

| Recorrido anterior | Recorrido nativo |
| --- | --- |
| Asignación y descomposición de la pregunta | Input versionado del propietario; pregunta, unidad y subpreguntas pertinentes. PICO sólo cuando encaja. Una reformulación es una interpretación corregible. |
| Revisión de literatura y conocimiento existente | Ken, fuentes capturadas, búsqueda configurada y wiki; estrategia, cobertura, exclusiones, dependencia y lagunas explícitas. Una lectura local no se presenta como revisión sistemática. |
| Registro de hipótesis | `researcher_finding_record`, tipo `hypothesis`, con base citada y razonamiento atribuido. `CreateHypothesisTool` ya era un wrapper sobre ese tipo de hallazgo. |
| Contraste de alternativas y experimentos | Predicciones, evidencia favorable/contraria y razones; análisis admitido y salida real capturada. No se elige la explicación contando inconsistencias. |
| Síntesis temática e informe | Informes y findings existentes: pregunta, métodos, temas, alternativas, contraevidencia, resultados, límites y próximos pasos. |
| Actualización de conocimiento | Wiki versionada con atribución; una nota no valida un hallazgo ni acepta la tarea. |
| Revisión y revisión del autor | Intento independiente sobre un sujeto exacto; feedback consultable por el autor y continuación admitida por el propietario. No se activa otro agente por palabras del modelo. |
| Finalización | Propuesta de informes exactos y aceptación explícita del propietario; sólo después se libera la tarea dependiente. Publicar artefactos requiere su recorrido separado. |

`SCIENTIFIC_RESEARCH_INSTRUCTIONS` se compone con las instrucciones existentes de
fuentes, búsqueda, wiki, análisis y conversación; no reemplaza sus límites de
captura, permisos o reintento. El input del autor congela el perfil
`scientific_research`, su metodología y el acceso de lectura al repositorio.
La implementación no obliga a inventar hipótesis o una evaluación formal cuando
la pregunta no las necesita.

## Salida de comandos como evidencia

Faltaba un puente entre ejecutar un análisis y citar su salida real.
`researcher_capture_command(operation_key, job_id)` resuelve el job del intento
actual; el modelo no proporciona salida, proyecto, actor, procedencia ni cierre.
La transacción comprueba permiso, autor nativo, run/intento original, recibo terminal
y peer cerrado. Un proceso con estado desconocido no se convierte en éxito.

Se capturan stdout/stderr UTF-8 exactos con argv, directorio lógico, identificadores,
estado, código de salida, errores, cancelación, truncamiento, tiempos y hashes de
los bytes originales. Una salida no decodificable sin pérdida o fuera del presupuesto
completo se rechaza. Un fallo con salida terminal puede conservarse como evidencia
limitada; sus flags siguen visibles en el documento y la procedencia.

La fuente usa el tipo de transporte existente `attachment`, con locator
`command-receipt:<job>` y origen explícito `retained_command_receipt`; no se la
presenta como archivo subido por el usuario. Reutiliza la inserción y recibos de
fuentes, sus lectores, citas, snapshots de resultados y revisión. El mismo reintento
recupera el documento original; otra ejecución bajo la misma clave se rechaza.
No se repite el comando para fabricar un recibo perdido.

El catálogo del autor científico y exploratorio ofrece esa captura. Se excluye de
los catálogos de revisión y desarrollo: no anuncia una operación que la política
actual de autor documental rechazaría. Integrar otros artefactos y tipos de ejecución
sigue siendo trabajo de sus recorridos.

Ejemplo comprobado: una fuente registra137 unidades; otro documento conserva el
cálculo que suma63 y produce200. El informe distingue hipótesis, ejecución y
conclusión aritmética. No afirma haber repetido la medición, identificado unidades
muestrales independientes o probado un efecto causal sobre una población.

## Correcciones metodológicas

Se retiraron del recorrido activo la aceptación automática al agotar revisiones,
los rescates automáticos y la finalización por `VALIDATED`. También se sustituyó la
regla de asignar bandas numéricas “inspiradas en GRADE”. Las instrucciones separan
calidad de reporte, riesgo de sesgo, certeza de un cuerpo de evidencia y decisiones;
piden nombre/versión, unidad y razones cuando se aplique un marco formal.

Esa corrección sigue los [criterios del grupo GRADE](https://www.gradeworkinggroup.org/):
una evaluación identificada como GRADE debe explicitar dominios y certeza por
resultado, con los métodos y evidencias considerados. Contar fuentes o traducir
una impresión del agente a un número no cumple ese contrato. El sistema conserva
`scientific_confidence: null`; la revisión documental es una decisión atribuida.

Se usó la skill local `scientific-critical-thinking` para orientar estas distinciones.
Referencia verificada el5de noviembre de2026: Kassis et al. (2026),
[Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065).
Su registro no declara una evaluación de tareas que permita atribuir mejoras de
calidad al proyecto. Aquí tampoco se infiere calidad científica ni comprensión
humana de pruebas de integración con generación controlada.

## Entradas antiguas y conservación

`ResearchFlow` y `ResearchReviewFlow` conservan `kickoff` y sus modelos de estado
como entradas de sólo lectura. Devuelven referencias originales o la acción para
abrir la tarea con su proyecto real. No inicializan CrewAI, seleccionan agentes,
revisan, validan ni aceptan por un contador histórico.

`research` se incorpora al mismo límite owner-only que `investigation`.
TaskFlowHandler, TakeTask, handlers de revisión/retrabajo, MainProjectFlow y
scavenger ya aplican ese límite. Las ramas directas de despacho registran un
handoff, no `research_flow_completed`. El esquema53 bloquea claims y finalización
antiguos antes de la primera admisión; conserva los informes y tareas históricos,
incluidos sus estados anteriores, sin inventar una aceptación nativa retrospectiva.

Esto retira el recorrido científico de esos consumidores. **No demuestra la
exclusión física global de AgentLoop, MessageHandler, listeners, FlowManager o
writers de los demás tipos.** La indicación de abrir la tarea no prueba cierre;
se mantienen las comprobaciones físicas del propietario antes de ejecutar.

## Casos «qué pasaría si…» comprobados

| Caso | Comportamiento |
| --- | --- |
| Se intenta citar un job activo, desconocido o cuyo peer no cerró | Captura rechazada; no crea fuente ni presupone éxito. |
| Otro intento o un grant sin admisión ofrece un job | Rechaza el préstamo de origen/autoridad. |
| Un experimento falla o limita su salida | Conserva esas condiciones explícitas; no lo califica como experimento válido. |
| Se pierde el recibo y se reintenta la captura | Devuelve la fuente original, sin otra ejecución. |
| Se cambia de job bajo la misma clave | Conflicto de intención; conserva el primer documento. |
| Un evento antiguo pide revisión o retrabajo científico | Sólo indicación owner; no claim, revisión, reintento ni aceptación automática. |
| Falla la instalación del esquema53 | Revierte sus guards; un reintento conserva el esquema52 y los registros históricos. |

Los tests de las antiguas etapas CrewAI se sustituyeron por el contrato público de
handoff y pruebas del recorrido nativo. No se mantienen expectativas de métodos
retirados o aprobación por etiquetas. Los tests de datos históricos siguen
comprobando la lectura de hipótesis y puntuaciones atribuidas.

[Resultados y límites](../modernization/scientific-results.json),
[paquete instalable](../modernization/scientific-packaging.json),
[docstrings](../modernization/scientific-docstrings.json).
Los escenarios globales, evaluación real de modelos/prompting/comunicación,
instalación limpia y restauración completa siguen pendientes.
