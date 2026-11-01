# Tablero de ejecución de la actualización

Actualizado: 2026-11-01. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Hay un primer recorrido de investigación con Codex, suscripción, Ken, análisis y reporte persistido. La prueba real de entrada de producto terminó; su monitor falló y se recuperó evidencia durable sin repetir inferencia. No se recuperaron las métricas de memoria perdidas.
- Las 43 entradas de escenarios siguen abiertas en `coverage.json`: 33 en progreso y 10 pendientes. Son escenarios amplios; esto no significa que sus componentes no funcionen.
- Interfaz: 4 pilotos, 12/36 conceptos de escritorio y 4/12 móviles; 0/12 páginas con aceptación completa.
- Última suite registrada: 1645 aprobadas, 100 fallos heredados y 3 omitidas. Falta resolver o retirar con justificación los casos del sistema reemplazado.
- No hay porcentaje global defendible todavía. El 30% anterior era una impresión, no una medición de alcance ponderado.

## Última entrega verificada: arranque del recorrido existente

**Resultado:** una instalación nueva se inicializa explícitamente; servir con base ausente/vacía o autoridad perdida no recrea estado; un fallo de arranque limpia los recursos que alcanzó a abrir.

**Salida:** CLI de inicialización probado sobre datos sintéticos, arranque y segundo arranque verificados, rechazos sin modificación de datos, cleanup probado antes de `yield`, guía operativa y comprobación del recorrido existente. Abrir estado de autoridad existente sigue siendo distinto de inicializarlo.

**Límite:** reutilizar journal, broker y fábrica actuales. Un defecto nuevo amplía este bloque sólo si impide esa salida o demuestra un riesgo obligatorio del plan; dejar evidencia y coste de la ampliación.

Verificado: inicializadores explícitos, guardias de API/CLI/launcher y cleanup ante fallos/cancelación; 23 casos nuevos pasan. Fuente: [guía y límites](bootstrap.md), [resultados](bootstrap-results.json) y [paquete](bootstrap-packaging.json). El host completo y restore siguen pendientes.

## Última entrega funcional: informe visible y corregible

**Resultado:** ver el informe real desde la web, entender sus fuentes y límites, corregir una premisa y comprobar el nuevo estado sin perder el informe anterior.

**Salida:** página de informes con tres conceptos de escritorio, adaptación móvil, selección razonada e implementación; recorrido conectado a tarea/conversación, lectura y error reales, teclado y comprobaciones responsive. Incluir una explicación con ejemplo o diagrama cuando ayude y una evaluación de comprensión/corrección. Diferenciar prueba funcional de evaluación con una persona.

**Entrega funcional y visual verificada:** tres conceptos y móvil; implementada Lectura con trazabilidad, lector de citas del propietario y navegación a la tarea por URL. Veinte estados de escritorio/móvil pasan controles de layout/axe; teclado, paginación, aislamiento por proyecto y corrección conservando el informe anterior comprobados. [Recorrido y límites](../design/audits/2026-11-01-reports/report.md), [resultados](reports-results.json).

**Pendiente de aceptación:** comprensión con una persona, lector de pantalla, zoom y cobertura íntegra de estados; no equivale a una página aceptada. La comprobación funcional distingue corrección registrada de nueva ejecución. Próxima entrega funcional: investigación útil de la cola posterior.

**Criterio añadido por el usuario:** cada módulo, clase, método y pieza relevante nueva o modificada llevará docstring/JSDoc semántico: propósito, contrato, límites y términos buscables por Ken. Revisar también los módulos ya añadidos en esta rama; no dar por cubierta esa revisión global con la entrega de Informes.

**Dependencias:** reutilizar persistencia, fuentes y fixture de producto existentes. No desarrollar otra fábrica de inferencia para esta entrega.

## Bloque activo: investigación sobre documentos/PDF

**Resultado:** referencia PDF del proyecto → texto capturado con identidad y páginas → lectura/búsqueda → cita exacta → borrador consultable. Mantener autoridad, retry y explicación honesta de lo que no se pudo leer.

**Ya verificado en este bloque:** extracción de PDF con texto, hash binario, offsets de página, páginas sin texto, rechazo de cifrado/formato/tamaño, sin truncar; repetición tras borrar el original y revocación antes del commit. Recorridos HTTP y fachada nativa sobre API/SQLite reales;104 pruebas dirigidas aprobadas también desde wheel aislado. [Contrato y límites](../architecture/pdf-sources.md), [resultados](pdf-results.json), [paquete](pdf-packaging.json).

**Paso de parser verificado:** [resultados](parser-results.json), [paquete](parser-packaging.json). Worker fijo con CPU/AS/plazo/IPC, sin credenciales o FD heredados, retirada por HTTP y cierre al morir el padre. Finalización y recuperación esperan el cierre real; cierre incierto mantiene reconciliación.

**PDF por URL implementado:** [resultados](pdf-web-results.json), [paquete](pdf-web-packaging.json). Usa el mismo parser, conserva URL/hash/páginas y respeta el plazo restante; las operaciones siguen registradas hasta cerrar I/O y parser.

**Falta para cerrar la capacidad:** consumidores antiguos e interfaz Archivos (`/files`): conceptos/selección/móvil ya preparados; piloto de subida/previa/descarga/borrado implementado y comprobado. Documentos (`/wiki`) es otra ruta y conserva su propia migración/rediseño. La extracción actual no hace OCR ni certifica orden visual/tablas/imágenes. Sin aceptación humana ni nuevo ensayo con modelo.

**Archivos verificado:** [resultados](files-results.json), [paquete](files-packaging.json)
y [navegador](../design/audits/2026-11-01-files/report.md).185 pruebas dirigidas
pasan desde fuente y wheel;15 casos nuevos,41 frontend. Subida explícita y limitada,
previa sin crear fuente, descarga exacta, borrado que conserva capturas/informes,
paginación, teclado y errores. Incluye docstrings/JSDoc semánticos de las piezas
nuevas/modificadas; la revisión documental global sigue pendiente.

**Captura de artículos añadida al recorrido nativo:** `researcher_capture_paper`
acepta exactamente un URL/DOI/arXiv y conserva petición/versión, URL final, hashes y
páginas. DOI que devuelve HTML no se presenta como texto completo. Catálogo de negocio
12 herramientas, sin embeddings ni generación nueva.245 comprobaciones dirigidas
pasan desde fuente/wheel;31 casos nuevos. Suite1688:1585 aprobadas,los100 fallos
heredados exactos y3 omitidas. [Contrato y consumidores](../architecture/paper-capture.md),
[resultados](paper-results.json), [paquete](paper-packaging.json).

**Recuperación semántica implementada en el backend nativo:** `researcher_source_query`
usa un modelo multilingüe local preparado explícitamente. Devuelve pasajes exactos,
modelo/hash/páginas y cobertura computacional. Límite CPU/AS/plazo/IPC, una plaza por
aplicación, cancelación/reap y revalidación de permisos.271 comprobaciones dirigidas
desde fuente/wheel. Suite1714:1611 aprobadas,los100 fallos heredados exactos y3
omitidas;26 casos nuevos. Ensayo real de la fachada sobre contraevidencia al final del PDF,
con informe draft y tarea aún en progreso. No es una evaluación de comprensión LLM.
[Contrato](../architecture/semantic-source-retrieval.md), [ensayo](semantic-product-evidence.json),
[resultados](semantic-results.json), [paquete](semantic-packaging.json).

**Formatos estructurados implementados:** DOCX/CSV/JSON/XML reutilizan la captura,
worker, búsqueda y citas existentes. Estructura paginada; Word declara omisiones y CSV
su interpretación de encabezados.305 casos dirigidos desde wheel;41 frontend y8 estados
de navegador. Suite1748:1645 aprobadas,100 fallos
heredados exactos y3 omitidas. No hubo turnos LLM nuevos ni más páginas aceptadas.
[Contrato](../architecture/structured-sources.md), [resultados](formats-results.json),
[paquete](formats-packaging.json), [previas](../design/audits/2026-11-01-structured-files/report.md).

**Siguiente acción:** cortar los consumidores heredados por recorridos completos.
Los roles/flows de investigación todavía requieren capacidades de conocimiento/wiki,
búsqueda y revisión; no basta con cambiar imports de sus lectores documentales.
Completar esas operaciones nativas y sus prompts antes de retirar el registro RAG
viejo. Reutilizar captura/recuperación actuales, sin otra fábrica de inferencia.

## Cola posterior, manteniendo el alcance

1. Completar investigación útil: búsqueda web, documentos/PDF, conocimiento/wiki y revisión científica; migrar herramientas por capacidades, con sus prompts y contratos.
2. Desarrollo completo: edición/candidato, pruebas, revisión, Git/CI y efectos externos reconciliables. Resolver requisitos de aislamiento antes de habilitar cada efecto.
3. Migrar autonomía, roles, flows y comunicación entre agentes al mismo dueño durable; no añadir otro loop LLM. La comunicación humano–agente se verifica en cada recorrido.
4. Extender diseño a las demás páginas, con conceptos y selección por página; completar aceptación de los cuatro pilotos existentes.
5. Completar inventario/evaluaciones de todos los prompts y llamadas auxiliares, migraciones/restauración, dependencias, instalación, CLI/TUI y retirada del motor anterior. Trabajar estas obligaciones dentro de las entregas que las toquen; este orden no las aplaza todas al final.
6. Verificación global, revisión independiente de toda la rama y entrega. No cerrar el objetivo con un subconjunto.

## Reglas de ejecución desde este diagnóstico

- Un recorrido activo. Como máximo, otro frente independiente con archivos y contrato separados; delegar investigación o trabajo definido, evitando revisiones genéricas recurrentes.
- Cada bloque declara resultado observable, criterio de salida, dependencias y pruebas necesarias **antes** de editar. Un experimento de 45–60 minutos sin resolver una incertidumbre exige reconsiderar la alternativa y registrar qué falta; no autoriza ignorar un requisito.
- Antes de ampliar infraestructura, identificar el escenario obligatorio y el fallo reproducido que bloquea el recorrido. Si no lo bloquea, asignarle una entrega posterior y una prueba, conservándolo en el plan.
- Ejecutar pruebas dirigidas durante el desarrollo. Si cambia bootstrap/importación de procesos, probar primero el wheel con el recorrido dirigido antes de lanzar la suite global. Ampliar al cambiar contratos compartidos, persistencia o fronteras de aislamiento; ejecutar la suite global al cerrar entregas y antes de la aceptación final. No repetirla sobre los mismos bytes por redactar documentación.
- Repetir un ensayo real sólo por un cambio relevante o una pregunta sin resolver. Conservar resultados parciales y comprobar el verificador sin inferencia antes de usar la suscripción.
- Reusar evidencia válida para la misma revisión/configuración. Un cambio de esos inputs invalida únicamente las conclusiones afectadas.
- Mantener aquí sólo estado actual y próximos resultados; detalles y logs en el ledger/evidencias. Al retomar: leer este tablero, el último bloque relevante y los archivos necesarios, sin reconstruir toda la historia.
- Reportar: resultado utilizable nuevo, criterio cumplido, bloqueo concreto y siguiente entrega. Contar commits/tests como validación o actividad, no como porcentaje del producto.
- Registrar por entrega tiempo transcurrido, esperas identificables, retrabajo y criterio aceptado. Recalibrar previsiones con las próximas dos entregas; no prometer una aceleración ni fecha sin esos datos.
