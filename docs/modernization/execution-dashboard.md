# Tablero de ejecución de la actualización

Actualizado: 2026-11-02. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Codex por suscripción y Ken publicado ensayados; fuentes/citas e informes draft conectados. Continúan consumidores y loops heredados, coordinación, revisión y desarrollo pendientes.
- Interfaz: 6 pilotos, 18/36 conceptos de escritorio y 6/12 móviles. Quedan seis rutas por implementar; 0/12 tienen aceptación completa.
- Última suite: 1792 casos: 1689 pasan, 100 fallos heredados y 3 omitidos. No hay fallos nuevos frente a la línea base; la suite sigue roja.
- Los 43 escenarios amplios continúan abiertos en [coverage.json](coverage.json). Se registran resultados y límites; no hay un porcentaje global defendible.

## Última entrega verificada: Hallazgos con evidencia contrastable

**Resultado:** listado/filtros/cursor/resumen estructurado por proyecto; texto, citas y declaraciones históricas paginados; captura citada comprobada por hash. Categorías, confianza y flags antiguas conservadas con su procedencia, sin inferir revisión independiente.

**Búsqueda:** encoder local fijado sobre títulos/cuerpos completos de un conjunto explícito acotado. Sin muestra oculta ni fallback; continuación ligada a huellas y revalidación de corpus/autoridad. La similitud no expresa certeza científica.

**Interfaz:** registro con evidencia y lector móvil separado. 18 estados funcionales y lectura a 1440/390/320 px pasan controles automáticos; siguen pendientes comprensión/aceptación integral.

**Validación:** wheel aislado: 371 pasan y 1 fallo heredado explícito, 621 fuentes Python/SQL coinciden.55 pruebas frontend y build. Sin nuevos turnos de investigación ni embeddings remotos. [Contrato](../architecture/finding-registry.md), [resultados](findings-results.json), [paquete](findings-packaging.json), [navegador](../design/audits/2026-11-01-findings/report.md).

**Siguiente acción:** completar búsqueda web y coordinación/review realmente admitidos, y migrar consumidores por capacidades. Los adaptadores/roles/flows antiguos siguen activos; una etiqueta no sustituye al engine ni acredita independencia. Reutilizar el dueño durable, las capturas y la recuperación existentes.

## Cola posterior, manteniendo el alcance

1. Completar investigación útil: búsqueda web, documentos/PDF, conocimiento/wiki y revisión científica; migrar herramientas por capacidades, con sus prompts y contratos.
2. Desarrollo completo: edición/candidato, pruebas, revisión, Git/CI y efectos externos reconciliables. Resolver requisitos de aislamiento antes de habilitar cada efecto.
3. Migrar autonomía, roles, flows y comunicación entre agentes al mismo dueño durable; no añadir otro loop LLM. La comunicación humano–agente se verifica en cada recorrido.
4. Extender diseño a las demás páginas, con conceptos y selección por página; completar aceptación de los seis pilotos existentes.
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
