# Agentes — registro operativo con detalle

Objetivo: reconocer quién recibió una tarea, consultar su ejecución nativa y el
consumo observado del intento actual, abrir el contexto original o solicitar Stop.
No deducir actividad de un roster legacy, de un rol o de metadatos del proyecto.

Se generaron tres referencias independientes: roster operativo, matriz y diario
([prompts e imágenes](manifest.json)). Selección delegada: **roster**, primera
imagen mostrada. El índice conserva la identidad y la tarea; el detalle permite
leer estado/consumo/control sin una tabla excesivamente ancha. La matriz sirve
para comparar pero comprime el contexto móvil; el diario repite información y
pone énfasis en sesiones pasadas. La adaptación móvil deriva de la imagen elegida.

Estilo: papel/tinta/verde y títulos Georgia del producto existente; cuerpo sans
14–16px, reglas finas, sin avatares, ilustraciones decorativas ni marca de IA.
No hay activos raster nuevos dentro del producto: las imágenes son referencias.
En móvil se muestra índice o detalle con retorno y foco. Identificadores extensos
quedan en un desplegable. La cabecera compartida se conserva para su bloque propio.

Contrato implementado: GET owner `/api/projects/{project_id}/agent-runs`, paginado,
con identidad real de runtime_runs y observaciones del intento actual. Modelo del
envío se distingue de una prueba del modelo efectivamente usado; tokens son máximo
acumulado informado, no cuota ni coste. Sin medición se muestra «No disponible».
Las cantidades de procesos son recibos guardados, no comprobaciones de liveness.
Stop reutiliza el endpoint del runtime y conserva error/incertidumbre. La lectura
no inicia agentes ni convierte finalización en aceptación.

[Recorrido y límites](../../audits/2026-11-06-agents/report.md).
