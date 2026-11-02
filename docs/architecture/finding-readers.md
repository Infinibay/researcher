# Lectores de hallazgos: identidad, versiones y feedback

Los lectores heredados de hallazgos comparten ahora las proyecciones del registro
canónico. Una declaración de confianza, la etiqueta `proof`, el estado `active` o
un nombre de rol no acreditan revisión independiente ni certeza científica.

## Contrato de lectura

| Entrada retenida | Comportamiento |
| --- | --- |
| `read_findings` | Metadatos paginados; `finding_id` abre texto y citas con cursores independientes |
| `summarize_findings` | Cuenta todo el conjunto elegido y devuelve una página de temas, en el mismo snapshot SQL |
| `search_findings` | Recuperación semántica local sobre títulos y cuerpos completos, con límites explícitos y huellas del conjunto |
| `read_finding_reviews` | Historial real, decisión o sujeto original congelado; lectura sin permiso para decidir |
| `search_knowledge` | Búsqueda léxica por fuentes con cobertura, cursores y fallos separados |

Siempre se exige proyecto. La tarea es un filtro dentro de ese proyecto, no un
sustituto de su identidad. `task_id=0` amplía a las tareas del proyecto elegido;
no permite consultar otros proyectos. Una tarea de otro proyecto produce un
conjunto vacío dentro del alcance seleccionado, sin revelar sus registros.

La confianza desconocida se conserva por defecto. `min_confidence` sólo se aplica
si se elige expresamente y filtra declaraciones históricas; excluirá los valores
desconocidos. Los metadatos distinguen esa procedencia, las antiguas declaraciones
de revisión y la presencia real de intentos/decisiones. `currentness=not_checked`
no significa que una decisión siga vigente.

La página de metadatos contiene `content_excerpt`; no es el texto completo.
Para inspeccionarlo hay que elegir `finding_id` y seguir `next_offset`, y
`next_evidence_offset` para las citas. El resumen estructurado tampoco demuestra
que se haya leído todo el contenido de cada hallazgo.

## Revisiones legibles sin nuevas escrituras

`read_feedback` en `knowledge/reviews.py` proyecta el mismo historial y las mismas
ventanas de decisión/sujeto para lectores nativos y retenidos. El lector nativo
comprueba su permiso `findings.read` y autoridad vigente dentro de esa misma
transacción. La interfaz retenida usa su contexto del host, que no equivale a un
grant nativo ni habilita `findings.review`.

Los catálogos de roles y tipos de tarea que ofrecen lectura de hallazgos también
permiten inspeccionar las decisiones y límites. El estado `subject_current` se
mantiene diferenciado: `true` indica coincidencia de dependencias, `false` una
versión anterior, y `null` una vigencia no comprobable. Ninguno asigna certeza
científica ni acepta la tarea.

## Contexto explícito en las interfaces antiguas

Se distingue omitir un campo de retirarlo:

- Omitirlo conserva el valor del mismo actor.
- Pasar `None` lo borra y bloquea el fallback a una variable de entorno antigua.
- Cambiar a un actor conocido recupera su propio snapshot.
- Cambiar a uno desconocido empieza sin proyecto/tarea; no hereda los del actor anterior.
- Una herramienta ligada a un actor retirado no toma el contexto de otro actor del hilo.

Por ejemplo, el actor A trabajó en el proyecto 101. Al retirar su proyecto, una
variable de entorno que aún diga 202 no autoriza a leer 202. El lector informa que
falta proyecto. Si empieza B sin declarar proyecto, tampoco se supone que comparte
101. Esta diferencia evita tratar un contexto supuesto como evidencia de alcance.

Los ContextVars pertenecen a la ejecución, incluidos contextos asíncronos copiados.
El thread-local queda como espejo de compatibilidad. Los workers con herramientas
ligadas a un actor usan su registro, sin caer al actor ambiental cuando falta.
Estas correcciones no convierten el contexto heredado en el permiso cercado del
runtime nuevo; la retirada de los loops y efectos antiguos sigue pendiente.

## Semántica local y límites visibles

Se reutilizan el corpus completo, los pesos/tokenizer fijados y el worker offline
existentes. No se consultan BLOBs de embeddings sin versión, no se descargan pesos
al buscar y no se cambia a otro proveedor si falta preparación.

El conjunto completo admite hasta 500 registros y 200000 bytes según el contrato
canónico. Si no cabe, se rechaza sin buscar una muestra de los 500 más recientes.
Se vuelve a comprobar texto, metadatos y pertenencia después del worker. Un cambio
invalida el resultado antes de publicarlo.

`limit` admite 1–20 chunks, con posibilidad de varios del mismo hallazgo. Para
continuar se envían `next_rank` y ambas huellas del corpus; no se mezclan páginas de
versiones distintas. `include_content` añade una ventana acotada, con `next_offset`,
no una promesa de cuerpo completo dentro de un resultado de búsqueda. El umbral de
similitud filtra chunks y no mide certeza científica. Los operadores léxicos
OR/AND/prefijo corresponden a `read_findings`, no a la nueva consulta semántica natural.

API y adaptadores retenidos comparten una plaza semántica **por proceso**. Crear
otra instancia ya no permite iniciar un segundo worker concurrente en ese proceso.
Esto no prueba un presupuesto global de varios procesos/hosts, que sigue abierto.

## Cobertura de búsqueda combinada

`KnowledgeSearchStore` conserva proyecto, conteos, previews y cursores en un único
snapshot de sólo lectura. La respuesta identifica cada fuente pedida como
`searched` o `failed`, con su `next_after_id`. Un fallo deja `total_matching=null`.
Los aciertos de otras fuentes se conservan con `partial=true`; si fallan todas,
la respuesta también contiene un error explícito. No se informa ausencia porque
falte una tabla FTS o falle una fuente.

Los previews mantienen su alcance: hallazgos actuales del registro; wiki con
namespace explícito; metadatos de adjuntos, sin afirmar que se buscó su contenido;
y texto/filename del artefacto de informe. El namespace global de wiki se elige
expresamente, sin fallback desde una ausencia local. Los resultados no son
capturas científicas ni prueba de haber leído documentos completos.

## Retirada del índice mutable de hallazgos

`FindingsKnowledgeSource` deja de seleccionarse en los constructores por proyecto
y rol. Los lectores actuales son su destino. Sus llamadas directas antiguas fallan
con una instrucción de migración antes de leer filas o crear embeddings, en lugar
de devolver `[]` o reconstruir una colección que puede contener conclusiones viejas.

La clase y su constructor se conservan provisionalmente para ese error explícito.
No se borran los índices históricos ni se mezclan sus vectores con los nuevos.
Otros sources, memoria CrewAI, productores heredados y sus loops todavía necesitan
su propia retirada; esta entrega no declara migrada toda la inferencia auxiliar.

## Evidencia

Las pruebas usan SQLite real, fuentes/citas reales y permisos nativos admitidos
para el feedback. Se cubren ámbito ausente/ajeno, retirada y cambio de actor,
contextos asíncronos, confianza desconocida, lectura larga, contraevidencia fuera del
recorte, rechazo de muestreo y de resultados tras cambiar el corpus, cobertura
parcial, retiro de la fuente mutable y disponibilidad de feedback en los catálogos.
El modelo local se prueba sólo con assets preparados expresamente; no genera texto
ni usa una cuenta. El ensayo de revisión por suscripción de la entrega anterior
se conserva, sin repetirlo por este cambio de lectura.
