# Hallazgos: afirmaciones, citas y evaluación registrada

Estado: implementación parcial del plan completo. El registro nativo y la página
Hallazgos comparten lectores por proyecto. La admisión de reviewers independientes,
sus decisiones versionadas y la retirada de roles/flows/proveedores anteriores siguen
pendientes. Una etiqueta nueva no acredita esas capacidades.

## Qué conoce el sistema

El texto del hallazgo es una afirmación registrada. Las citas enlazan fragmentos de
fuentes capturadas y su identidad. `quote_is_exact` comprueba pertenencia textual al
contenido guardado; no determina si una cita apoya o contradice la afirmación. Al
abrir una captura desde Hallazgos se comprueba también su SHA-256.

Ejemplo: un documento puede describir una regla sin demostrar que el sistema la
cumple. Encontrar la frase correcta permite inspeccionar la regla; todavía hace
falta comprobar la aplicación. La interfaz dice **Fuentes citadas** y permite
contrastar el texto exacto, sin convertir todas las citas en evidencia favorable.

Las columnas antiguas `active`, `proof`, `confidence`, `validation_method` y
`reproducibility_score` se conservan. Describen categorías, estados y declaraciones
guardadas. No acreditan por sí solas una revisión independiente ni confianza científica.
Los valores ausentes permanecen desconocidos; los valores numéricos inválidos se
identifican sin reescribir los datos originales. La API declara
`scientific_confidence=null`, y distingue `not_recorded` de `unverified_legacy`.

## Lecturas con alcance explícito

El propietario debe indicar proyecto e ID. El adaptador usa la identidad de la base
servida, antes de recurrir a la configuración global transitoria. Los agentes usan
`findings.read` y el proyecto derivado del grant; no pueden sustituir proyecto,
tarea o actor mediante argumentos. `for_task_id` es sólo un filtro de lectura dentro
de ese proyecto. Un ID ajeno no revela texto ni citas.

El índice usa IDs ascendentes, cursor y conteo del conjunto filtrado. Búsqueda FTS,
tipo, estado, tarea y umbral de confianza declarada se combinan. Sin umbral se
incluyen registros sin número; seleccionar un umbral los excluye explícitamente.
La sintaxis FTS inválida produce un error de entrada; no activa otro buscador.
El resumen devuelve conteos completos por tipo/estado y estadísticas declaradas,
sin otro turno de modelo ni síntesis automática de conclusiones.

El texto y las citas tienen continuaciones independientes. El lector sustituye el
fragmento visible y señala su posición en el registro actual. No ofrece un historial
inmutable de hallazgos. Los metadatos son previas acotadas: título hasta 1200 caracteres,
autor 128 y método 4000. El cuerpo se lee en ventanas de hasta 20000 caracteres; las citas
en páginas de 20, con previa de hasta 8000 caracteres y truncamiento declarado.

`sources_json` antiguo conserva su texto literal con paginación independiente. Sus
declaraciones y URLs no se transforman en capturas verificadas ni se consultan
automáticamente. La captura abierta debe estar relacionada con el hallazgo del
proyecto y conservar su hash; una fuente no citada o corrupta se rechaza.

## Recuperación por significado

Se reutilizan `SemanticRetriever`, el encoder multilingüe fijado y su worker limitado.
Un corpus transitorio contiene títulos completos y cuerpos completos, ordenados por
ID, con offsets y huellas de cada registro. No crea una fuente científica ni altera
el conocimiento. Se admiten como máximo 500 registros y 200000 bytes normalizados;
el presupuesto se calcula con el texto, IDs y separadores reales. Si excede el límite,
se pide acotar filtros o seleccionar 1–50 IDs distintos. No se toma una muestra oculta.

Los resultados identifican el corpus, sus miembros y la cobertura. Los offsets de
cada coincidencia corresponden a **título + dos saltos de línea + cuerpo**. El score
pertenece al chunk recuperado; no expresa confianza científica ni una evaluación
independiente del hallazgo. Para citar se inspeccionan las fuentes originales.

La continuación exige ambas huellas observadas: texto y conjunto/metadatos. Una
mutación entre páginas se rechaza antes de iniciar el worker; la interfaz también
rechaza páginas de conjuntos distintos. Tras ejecutar se revalidan grant, autoridad
viva y corpus completo. Editar, insertar, revocar o retirar autoridad durante la
consulta impide entregar el resultado pendiente. Un conjunto vacío se declara vacío
sin iniciar encoder; la falta de assets o capacidad se mantiene como error explícito.

## Catálogo e interfaz

El catálogo de negocio contiene 22 herramientas. Se añaden
`researcher_finding_list`, `researcher_finding_summary` y
`researcher_finding_query`; `researcher_finding_read` declara ventanas de texto y
citas, evaluación histórica y fuentes declaradas. Las firmas/esquemas son comunes al
MCP y al cliente del host, sin credenciales ni identidad de ejecución en los argumentos.
[Schemas](../modernization/findings-tool-schema.json).

El diseño seleccionado es un registro con evidencia: índice persistente y lector
amplio, con desplazamiento independiente en escritorio. Móvil separa lista, detalle y
captura. El foco acompaña la lectura y vuelve al elemento que la abrió. Las claves de
consulta conservan proyecto, filtros, ID y fragmento; una lectura tardía no puede
aparecer en otro proyecto. Los errores distinguen consulta fallida, conjunto vacío,
captura inconsistente y recuperación pendiente.

[Conceptos y procedencia](../design/concepts/findings/manifest.json),
[recorrido y límites](../design/audits/2026-11-01-findings/report.md).

## Trabajo necesario para completar el plan

Migrar consumidores de lectura/búsqueda/resumen heredados y retirar sus proveedores
cuando exista paridad comprobada. Sustituir validación/rechazo por decisiones
versionadas con método, evidencia, reviewer realmente admitido y separación del
productor. Invalidar/revisar dependencias tras correcciones; incorporar retención,
restauración y evaluación representativa. Completar aceptación humana, accesibilidad
y escenarios de todas las rutas. Este registro no completa el engine ni la revisión
científica, ni acepta tareas o autoriza publicación.
