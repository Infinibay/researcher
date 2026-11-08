# Comunicación: evidencia vigente y trabajo pendiente

Conciliación del 8 de noviembre de 2026 sobre `d4c5419`, contrastada por un
revisor con contexto limpio. No hubo nuevas generaciones, cambios de política
ni repetición de evaluaciones. Los resultados originales permanecen intactos.

## Fallos históricos y comprobaciones posteriores

| Problema observado | Evidencia posterior | Alcance comprobado |
| --- | --- | --- |
| Auditoría sin explicación final por límite de herramientas, catálogo3 | [Regresión catálogo4](delivery-budget-review.md), 346386/350000 tokens observados, 89,093 s | Entregó informe y explicación; distingue proceso exitoso de pruebas ejecutadas. |
| Medias de grupos atribuidas a cada individuo, catálogo3 | Misma regresión, 305543/350000 tokens, 97,675 s; [texto entregado](delivery-budget-responses.json) | Calcula 80→79,2 y contribuciones +1/−1,8; declara que las medias no demuestran cambios iguales por lote. |
| Plan guardado sin explicación, catálogos3–5 | [Entrega atómica catálogo6](atomic-planning-review.md), 81685/120000 tokens, 57,738 s | Guarda propuesta y explicación juntas; no acepta el plan ni ejecuta sus tareas. |
| Preguntas materiales y continuidad | [Recorrido funcional](communication-flow-review.md) | Pregunta estructurada, respuesta guionada, continuación y corrección durante ejecución; no observación humana. |
| Preguntar antes de entregar el trabajo independiente | [C10](c10-independent-review.md) | Resultado 50 EUR durable y visible; conserva la pregunta sobre unidades sin elegir una por el usuario. |
| Vigencia de prompts | [Revisión estática](../prompts/review-2026-11-08.md) | 85 candidatos en 322 archivos; 85 decisiones vigentes. No acredita eficacia general. |

Los ensayos posteriores son regresiones de desarrollo sobre casos ya conocidos,
no nuevas reservas ni comparaciones causales. Sus catálogos y presupuestos son
distintos; no convierten los ocho turnos originales en ocho éxitos ni acreditan
la política final en todos los perfiles. Los tokens observados no son facturación
ni cuota restante. Tampoco es necesario repetirlos para volver a demostrar lo mismo.

## Pendientes concretos

- **U08 y observación humana:** el usuario rechazó el ejemplo inicial y pidió
  entender la idea, los datos, sus relaciones y las entradas/salidas. Su respuesta
  no acredita comprensión ni aceptación. La siguiente evaluación debe partir de
  una tarea reconocible, explicar objetivo y ejemplo de entrada/salida, y permitir
  una corrección útil; evitar otro cuestionario abstracto. La adaptación posterior
  también necesita observarse. [Registro humano](interaction-human-review.json).
- **Comparaciones de comunicación:** faltan casos nuevos antes/después para
  `development`, `code_review` y `finding_review`. Los revisores sí tienen turnos
  funcionales reales históricos: [código](native-code-review-live.json) y
  [hallazgos](native-review-live.json). Eso no es una comparación de comunicación
  bajo la política final ni una prueba de calidad general.
- **Recorridos del §7.7:** evaluar conjuntamente en la UI real la explicación de
  espera larga, fallo recuperable y resultado parcial, con intervención del usuario.
  Reutilizar persistencia/Stop ya comprobados. Falta observar un ejemplo o diagrama
  pertinente seguido de corrección/adaptación bajo política final.
- **Ciencia representativa:** el [caso primario actual](current-scientific-final-review.md)
  entregó cálculo e informe con cinco criterios completos y uno parcial. Se conserva
  esa rúbrica. Otro ensayo sólo ampliaría cobertura con pregunta/material distinto
  y preregistrado; no regenerar para obtener seis de seis. Un resumen no demuestra
  lectura del artículo completo ni representatividad.

El contraste relativo innecesario, la prosa técnica dentro de la explicación y
la atribución ambigua de «evaluador» son pulido DD145. Se atienden después de las
capacidades principales. No hay aceptación humana, suite global final verde ni
cierre general de comunicación. Siguen 42/43 escenarios amplios y 12/12 páginas
aceptadas dentro de sus respectivos alcances.
