# Inventario y revisión de prompts

Corte del 7 de noviembre de 2026 sobre `035b46c`: catálogo nativo **versión 3**,
**83 candidatos en 287 archivos**, con **83 decisiones estáticas vigentes**.
Se revalidaron 69 decisiones tras leer instrucciones y consumidores; las otras
14 conservan sus hashes. No se cambiaron instrucciones del producto en este corte.
[Revisión, evidencia y límites](review-2026-11-07.md).

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
`RESEARCHER_POLICY 3 <perfil>` y el hash del texto completo identifican lo enviado;
las instantáneas de versión2 conservan su versión/hash original. El perfil
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
reconstruir las reglas. Este corte la conserva; no añade otro loop ni reescribe
prompts para aparentar avance. La lectura científica mantiene separadas procedencia,
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
