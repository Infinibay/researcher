# Conversación: brief de diseño

Fecha: 2026-11-01. Fuente de implementación: d0f1161.
El usuario delegó explícitamente generar alternativas, escoger la mejor e implementarla.
Se trabaja en el producto existente; no se crea otro starter ni una demo sin backend.

Objetivo: comprender qué ocurre en una tarea, distinguir solicitud/pregunta/propuesta,
responder la pregunta correcta y corregir contexto sin iniciar trabajo por accidente.
Público: propietario de un proyecto de investigación/desarrollo, sin suponer que
comparte la terminología interna del motor. Español claro, lectura y ejemplos.

Referencias: código real de ChatPage, TaskRunWorkspace, contratos de conversación y
preguntas, tokens y concepto editorial de Tareas inspeccionado. El concepto de Tareas
se adjunta como referencia de estilo, no como captura del producto ejecutado.
CUA informó apps=[], browsers=[], browser access host unavailable en esta sesión.
No hay captura ni auditoría visual de la página existente. Se continúa dentro del
rediseño de repo autorizado, dejando aceptación visual/interactiva explícitamente pendiente.
Preflight Product Design: no existe user-context.md guardado.

Tres composiciones independientes a 1440×1024:
- Conversación con evidencia: lectura central, tareas/hilos a la izquierda y contexto lateral.
- Cuaderno del caso: registro documental amplio, índice compacto y evidencia en notas.
- Mesa de intervención: pregunta pendiente como foco, trazabilidad y conversación debajo.
Luego adaptación móvil independiente 390×844 de la elegida. Los tamaños de layout
solicitados pueden diferir de los píxeles nativos que entregue la herramienta.

Usar papel #fffefa, tinta #242d2a, secundario #59655f, verde #24533e,
líneas #d6ddd5 y navegación carbón #20282b. Títulos editoriales, sans para lectura,
controles con textos claros. Sin héroes, fotos de personas, avatares inventados,
ornamentos, métricas de confianza o estado terminado no comprobado.

Escenario ficticio, sólo para diseño: proyecto Atlas, tarea #24 «Comprobar reintentos»;
una solicitud pregunta si se duplican envíos, el agente explica un ejemplo de respuesta
perdida y pregunta qué carpeta revisar. Fuente «registro de prueba»; hipótesis explícita,
no diagnóstico real. Respuesta con IDs estables, fuera del compositor de nueva solicitud.
El ejemplo no se inyecta en datos del producto. Fechas visibles ancladas al 2026-11-01.

Criterios de selección: claridad 30%, lectura 25%, coherencia 20%, accesibilidad prevista
15%, adaptación móvil prevista 10%. Ninguna puntuación equivale a aceptación de navegador.
No se infieren permisos, quiescencia ni calidad científica a partir de una imagen.
