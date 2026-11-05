# Planificación nativa: recorrido de interfaz

Se amplía el estilo del piloto de Tareas ya seleccionado. El propietario puede
iniciar la planificación, leer su fundamento y supuestos, aceptar la propuesta
exacta y consultar las tareas creadas pendientes. Se comprobaron escritorio
1440×1100 y móvil 390×844.

| Estado | Captura |
| --- | --- |
| Inicio desde el proyecto | [01](01-native-project-start.png) |
| Respuesta de inicio perdida | [02](02-start-response-lost.png) |
| Recarga conserva el inicio original | [03](03-reload-original-start.png) |
| Propuesta en escritorio | [04](04-desktop-proposal.png) |
| Propuesta móvil | [05](05-mobile-proposal.png) |
| Respuesta de aceptación perdida | [06](06-accept-response-lost.png) |
| Recarga conserva la aceptación | [07](07-reload-original-acceptance.png) |
| Tareas pendientes en móvil | [08](08-mobile-accepted-pending.png) |
| Tareas pendientes en escritorio | [09](09-desktop-accepted-pending.png) |

[Evidencia](evidence.json): sin errores de página, desbordamiento horizontal ni
infracciones Axe en el header y panel examinados. Dos POST idénticos después de
pérdida de respuesta/recarga producen un turno/propuesta y un grafo. Las tareas
creadas permanecen pendientes y sin runs. Se inspeccionaron visualmente las
capturas 04, 05 y 09.

El navegador usa API owner, scheduler, herramientas host, SQLite y React reales;
la generación y los testigos de cierre de peers son sintéticos explícitos. El
recorrido físico nativo se comprueba por separado con generación controlada. No
hubo inferencia real ni modificación de repositorios del usuario en esta prueba.

El alcance es el recorrido añadido: siguen 0/12 páginas completamente aceptadas.
No se afirma accesibilidad de toda la aplicación ni comprensión humana evaluada.
Selector de repositorio, textos secundarios y claridad del resumen histórico tras
aceptación quedan registrados en DD-009; no bloquean la capacidad principal.
