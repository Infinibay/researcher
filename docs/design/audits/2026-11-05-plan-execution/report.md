# Tareas: ejecutar y pausar un plan aceptado

Se mantiene el estilo del piloto elegido. Se añadieron decisión de ejecución,
ejemplo de dependencia, estado por tarea y pausa/reanudación con límites explícitos.
Se inspeccionaron visualmente las capturas01/04/08, en1440×1100 y390×844.

| Estado | Captura |
| --- | --- |
| Decisión distinta de ejecutar | [01](01-desktop-distinct-execution-decision.png) |
| Respuesta de ejecución perdida | [02](02-execution-response-lost.png) |
| Recarga conserva el paquete | [03](03-reload-original-execution.png) |
| Tarea raíz activa en móvil | [04](04-mobile-original-root-running.png) |
| Respuesta de pausa perdida | [05](05-pause-response-lost.png) |
| Recarga conserva la pausa | [06](06-reload-original-pause.png) |
| Pausa y cierre móvil | [07](07-mobile-paused-original-result.png) |
| Estado detenido en escritorio | [08](08-desktop-paused-original-result.png) |

[Evidencia](evidence.json): dos POST idénticos de ejecución y dos de pausa después
de pérdida de respuesta/recarga dejan una autorización y un único run hijo original,
detenido. La dependiente sigue pendiente. Sin errores de página, desbordamiento
horizontal ni infracciones Axe en header y panel examinados.

API owner, scheduler, almacenamiento y React reales; generación y cierre sintéticos
explícitos. Sin inferencia real ni modificación de repositorios del usuario. El
recorrido físico con desarrollo privado se comprueba por separado. No se certifica
la aplicación completa ni comprensión representativa: siguen0/12páginas aceptadas.

Estado del proyecto/resumen histórico quedan enDD009. Localización de impedimentos,
detalle de evidencia y controles de recuperación/reautorización quedan enDD011.
