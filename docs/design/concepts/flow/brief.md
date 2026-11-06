# Ejecución — inspector del recorrido real

Objetivo: comprender qué recibió cada tarea, qué resultado espera y dónde necesita
una intervención. Los estados provienen del plan nativo y sus entregas; la página
anterior dibujaba fases fijas del engine sin demostrar que hubieran ocurrido.

Se generaron tres alternativas independientes: inspector, mapa de estados y diario
([manifest, imágenes y prompts](manifest.json)). Se eligió **inspector**, primera
imagen mostrada, por mantener juntos plan, dependencias y evidencia del bloqueo.
El mapa agrupa bien los estados pero diluye la identidad de la entrega. El diario
sugiere una secuencia temporal que los registros no siempre justifican. La imagen
móvil deriva del inspector seleccionado; no es un recorte de la captura desktop.

La implementación conserva índice de planes, lista de tareas y detalle de evidencia.
Usa Georgia/sans del producto, papel/tinta/verde, reglas y agrupación sin activos
raster decorativos ni marca de IA. En móvil se navega plan → tareas → inspector,
con retorno y foco; el título de página permanece accesible. Las relaciones se
presentan mediante listas semánticas y enlaces; su orden no afirma cronología.

Datos: projectWorkspace incluye planes aceptados, también históricos/pausados;
executionState verifica project/task/planRun originales y ofrece manifest y entregas.
Sólo current=true cuenta como entrega actual. Si cambia el contexto, no se convierte
la historia en avance vigente ni se inventan dependencias. Handoff muestra los
resultados previos realmente entregados y sus versiones.

Controles: reutilización sin cambios de PlanExecution, sus paquetes persistidos,
pausa/reanudación, continuación y revisión del grafo. No se implementan los botones
ilustrativos «rechazar plan» o «recuperar plan» inventados por las imágenes. Los
errores/contexto/configuración limitan nuevas acciones; abrir no inicia ejecución.

[Recorrido y límites](../../audits/2026-11-06-flow/report.md).
