# Tablero de ejecución de la actualización

Actualizado: 2026-11-01. Objetivo: implementar **todo** el [plan](../superpowers/plans/2026-10-31-actualizacion-proyecto.md).
Este tablero organiza el trabajo; no reemplaza requisitos ni declara fases terminadas.
Motivos del ajuste: [diagnóstico del proceso](workflow-review.md).

## Estado comprobado

- Runtime Codex por suscripción y Ken publicado ensayados; herramientas de investigación, fuentes/citas e informes draft conectados. Continúan consumidores heredados y capacidades pendientes.
- Interfaz: 5 pilotos, 15/36 conceptos de escritorio y 5/12 móviles. Quedan siete rutas por implementar; 0/12 tienen aceptación completa.
- Última suite: 1767 casos: 1664 pasan, 100 fallos heredados y 3 omitidos. No hay fallos nuevos frente a la línea base; la suite sigue roja.
- Los43 escenarios amplios siguen abiertos. Su evidencia parcial está en [coverage.json](coverage.json).
- No hay un porcentaje global defendible. Se cuentan resultados utilizables y verificaciones, sin convertir actividad en avance ponderado.

## Última entrega verificada: Wiki con alcance y revisiones

**Resultado:** la misma ruta coexiste en proyectos distintos y biblioteca global; las ediciones requieren página/revisión observadas, conservan historia y recuperan recibos sin duplicar. Captura individual/colección permite citas y recuperación semántica local sobre revisiones explícitas.

**Interfaz:** cuaderno elegido entre tres conceptos y móvil, con alcance visible, borrador preservado, comparación de conflictos y respuestas tardías que respetan la vista actual.16 estados funcionales y lectura a1440/390/320px pasaron axe; no constituyen aceptación humana completa.

**Validación:** paquete aislado: 346 pasan y 1 fallo heredado explícito; 618 archivos Python/SQL coinciden. Frontend49 pruebas y build. No hubo nuevos turnos de investigación ni proveedores de embeddings remotos. [Contrato](../architecture/wiki-knowledge.md), [resultados](wiki-results.json), [paquete](wiki-packaging.json), [navegador](../design/audits/2026-11-01-wiki/report.md).

**Límites:** los roles/flows/RAG antiguos y SearchWiki conservan consumidores/proveedor hasta completar su migración. Falta invalidar/revisar conocimiento dependiente de correcciones; una nota guardada no valida científicamente su contenido.

**Siguiente acción:** completar lectura/listado/búsqueda y revisión explícita de hallazgos, con procedencia y estados honestos, y rediseñar `/findings`. Luego completar búsqueda web/coordinación y cortar consumidores por recorridos completos. Reutilizar runtime/fuentes existentes.

## Cola posterior, manteniendo el alcance

1. Completar investigación útil: búsqueda web, documentos/PDF, conocimiento/wiki y revisión científica; migrar herramientas por capacidades, con sus prompts y contratos.
2. Desarrollo completo: edición/candidato, pruebas, revisión, Git/CI y efectos externos reconciliables. Resolver requisitos de aislamiento antes de habilitar cada efecto.
3. Migrar autonomía, roles, flows y comunicación entre agentes al mismo dueño durable; no añadir otro loop LLM. La comunicación humano–agente se verifica en cada recorrido.
4. Extender diseño a las demás páginas, con conceptos y selección por página; completar aceptación de los cinco pilotos existentes.
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
