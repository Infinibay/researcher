# Inventario y revisión de prompts

**Estado vigente: catálogo10,85candidatos en322archivos.** Se revisó el delta de
doce decisiones y se conservaron73vigentes, sin renovar huellas automáticamente.
Incluye propósito/datos/relaciones/entrada-salida y adaptación del encuadre ante
feedback, conservando las identidades históricas2–9. [Cambio y límites](../modernization/purpose-framing-review.md).
La nueva observación real no entregó explicación dentro de120000tokens: no se
acredita eficacia ni comprensión humana. Las cifras y tablas de cortes anteriores
que siguen son históricas; consultar inventory.json para el árbol actual.

La [documentación posterior del núcleo](../modernization/core-docstrings-review.md)
revalida tres consumidores con delta sólo de docstrings y conserva82decisiones;
85/322siguen vigentes. No cambia el texto de las políticas del catálogo10 ni
sus descripciones/esquemas de negocio; no se repiten generaciones.

Los95docstrings siguientes de autoridad/transporte sólo cambian cuatro hashes
del árbol escaneado:85decisiones continúan vigentes, sin renovaciones de revisión.
[Alcance y pruebas](../modernization/authority-transport-docstrings-review.md).

Corte de Planificación del8noviembre2026:318archivos,85candidatos,18revisiones
vigentes y67desactualizadas;0sin revisión previa. El cambio de fuentes/consumidores
no prueba que67textos estén mal; tampoco permite contar sus revisiones anteriores
como vigentes. Revalidar al árbol final. [Resultado actual](../modernization/planning-commands-results.json).


Comprobación de vigencia del8noviembre2026, base `a6855c4` más la reparación Ken:
316archivos,85candidatos,20revisiones vigentes y65desactualizadas;0sin revisión
previa. El inventario/revisiones comprometidos debajo conservan su corte histórico,
no un gate verde del árbol actual. Revalidar textos y consumidores cambiados al
cierre, sin renovar huellas automáticamente. No confundir desactualización con
un fallo semántico demostrado ni revisión estática con eficacia de prompting.
[Recibo actual y límites](../modernization/ken-grammars-results.json).

Corte posterior del 7 de noviembre de 2026 sobre `ab36dc5`: catálogo nativo
**versión 4**, **83 candidatos en 287 archivos**, con **83 decisiones estáticas
vigentes**. Se revisó el cambio en16 decisiones y se conservaron67 sin cambios;
las revisiones anteriores permanecen completas en cada registro. El cambio añade
presupuesto observado, margen de entrega, búsqueda acotada y ejemplos fieles a
la evidencia. La revisión estática no demuestra que un modelo cumpla esas reglas.
[Cambio y comprobaciones](../modernization/delivery-budget-review.md).
La [revisión anterior de catálogo3](review-2026-11-07.md) conserva su propio corte.

Esto no significa 83 prompts distintos, 83 pruebas con modelos ni aceptación de
la comunicación. El inventario selecciona candidatos por sintaxis en Python de
`backend/` y `scripts/`, excluyendo tests. Las instrucciones externas de Codex,
los textos arbitrarios del propietario/fuentes y los prompts de evaluación o
conceptos visuales tienen otro alcance. Los imports directos son sólo un límite
inferior de consumidores: una lista vacía no demuestra que un texto no se use.

## Qué está revisado

| Familia actual | Candidatos | Decisión |
| --- | ---: | --- |
| Política común y composición | 5 | Conservar contexto, evidencia, corrección, preguntas y selección por capacidad |
| Perfiles nativos y recetas del host | 8 | Conservar procedimientos específicos y comprobaciones declaradas sin inventar resultados |
| Instrucciones/descripciones de herramientas | 53 | Conservar límites, identidad, ventanas y distinción entre efecto, recibo y aceptación |
| Proyección de entrada e historial de revisiones | 3 | Conservar datos atribuidos sin elevarlos a instrucciones o permisos |
| Metadatos humanos, instrumentación y fixture | 14 | Excluir de las instrucciones de agentes, sin ocultarlos del inventario |
| **Total** | **83** | **Revisión estática; eficacia pendiente** |

El [inventario detallado](inventory.json) identifica archivo, símbolo, líneas,
variables, tamaño de fuente y tamaño UTF-8 cuando el literal es conocido. Los
valores dinámicos desconocidos quedan nulos. Las [decisiones](review-decisions.json)
se ligan a la fuente y a los consumidores directos del módulo; conservan el motivo,
evidencia, límites y revisión anterior. Cambiar una dependencia invalida la revisión,
aunque después pueda comprobarse que no cambió el comportamiento relevante.

Hay 516 identidades históricas en `retired_entries`: 515 ya archivadas y una
antigua ubicación de línea de la descripción OpenAPI, ahora en la línea111.
**No son 516 archivos ni 516 funcionalidades retiradas.** La revisión anterior de
23 vigentes/60 desactualizadas fue un corte histórico; el inicio de este bloque
ya tenía14/69. No se usa ninguno de esos conteos como estado actual.

## Catálogo que recibe el runtime

`backend/prompts/native.py` selecciona investigación científica, exploración,
planificación, desarrollo, revisión de hallazgos, revisión de candidato o auditoría
de código. La política común aparece una vez. La cabecera
`RESEARCHER_POLICY 4 <perfil>` y el hash del texto completo identifican lo enviado,
incluidos los límites efectivos cuando los aporta el host; las instantáneas de
versiones2/3 conservan su versión/hash original. El perfil
`reference_research` se mantiene en el catálogo como entrada de compatibilidad,
fuera de los siete destinos del selector actual.

El runtime elige herramientas según la capacidad admitida. Las descripciones de
`ResearchTools` proceden de `inspect.getdoc(handler)`: sus docstrings documentan
código para Ken y también afectan al contexto del modelo. Los catálogos de
comandos, planificación, revisión y prerrequisitos tienen sus propias descripciones.
La variante de comandos con escritura privada sólo se anuncia después de verificar
la capacidad de desarrollo. El texto de una descripción no concede acceso.

Las reglas comunes distinguen declaración del usuario, ejemplo, observación,
interpretación y suposición. Una profesión no demuestra conocimiento compartido.
Piden explicar con pocos saltos injustificados, usar ejemplos/metáforas fieles o
un diagrama con alternativa textual cuando ayuden, y permitir correcciones mediante
un resultado inspeccionable. Una pregunta material se registra en su canal
respondible; no se equipara una pregunta en prosa con una solicitud pendiente.

La estructura existente aplica el criterio de *A Philosophy of Software Design*:
composición centralizada y límites de capacidad que no obligan a cada consumidor a
reconstruir las reglas. Este corte conserva esa composición sin añadir otro loop.
La lectura científica mantiene separadas procedencia,
apoyo lógico, dependencia entre fuentes, sesgos, incertidumbre y recomendación.

## Verificación y trabajo pendiente

```bash
python scripts/audit_prompt_inventory.py --check
python -m evals.prompts.measure_profiles
python -m pytest backend/tests/runtime/test_prompt_catalog.py backend/tests/runtime/test_prompt_inventory.py
```

La [comparación actual](profile-comparison.json) conserva el [baseline exacto](../../evals/prompts/baseline.json)
y mide únicamente bytes UTF-8/hashes. El evaluador ahora toma la versión del
catálogo real; antes la etiqueta estaba fijada erróneamente en2. Algunos perfiles
crecen y otros disminuyen: no implica menor coste, mejor resultado ni comprensión.

Los [casos de evaluación](../../evals/prompts/cases.json), las
[comparaciones de contexto](../modernization/context-alignment-review.md) y los
[recorridos de preguntas/correcciones](../modernization/communication-flow-review.md)
conservan sus propios resultados y límites. Este bloque no repite generaciones.
Siguen pendientes la evaluación humana, otros perfiles/recorridos y la evaluación
científica representativa. Las pruebas de contratos y hashes no sustituyen esas
medidas ni cierran los escenarios generales del plan.


La evaluación posterior de [otros perfiles](../modernization/profile-communication-review.md)
conserva8turnos reales y dos fallos de entrega de la política actual, además de
un ejemplo que atribuye una media a cada individuo. Se comprobaron cálculos y
controles, pero no eficacia general ni comprensión humana. Estos resultados
mantienen abierta la mejora funcional de comunicación; no cambian las83 decisiones
estáticas ni la política congelada3 de este corte.


Actualización documental posterior: [broker y canales](../modernization/broker-docstrings-review.md).
El inventario actual conserva 85 candidatos en 322 archivos. Se revalidó únicamente
el consumidor de `read_feedback` modificado por doce docstrings del broker; fuente
del candidato, AST ejecutable, siete políticas y 48 herramientas siguen iguales.
Las otras 84 decisiones no se renovaron. No cambia la eficacia demostrada ni U08.


La [documentación de análisis](../modernization/analysis-docstrings-review.md)
añade cuatro descripciones a los esquemas de argumentos realmente emitidos. Se
revisan como metadata visible al modelo: no cambian campos, límites ni política
de despacho. Una decisión revalidada, 84 conservadas; inventario actual 85/322.
No implica mejor cumplimiento del modelo ni cierre de DD157/U08.
