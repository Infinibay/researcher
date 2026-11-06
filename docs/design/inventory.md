# Inventario visual de la modernización

El requisito completo sigue siendo 36 imágenes independientes de escritorio,
12 adaptaciones móviles, selección y ejecución de las doce rutas. Los componentes
compartidos llevan cobertura adicional. Los números de esta tabla cuentan
archivos generados e inspeccionados, no pantallas aceptadas.

| Ruta | Escritorio / 3 | Móvil / 1 | Selección | Implementación | Aceptación visual |
| --- | ---: | ---: | --- | --- | --- |
| `/` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/projects` | 3 | 1 | Expediente del proyecto | Piloto en código | Parcial: selección/fuentes/recuperación/borrado/móvil; aceptación pendiente |
| `/epics` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/tasks` | 3 | 1 | Lista editorial con inspector | Piloto en código | Parcial: capturas reales; aceptación pendiente |
| `/agents` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/chat` | 3 | 1 | Conversación con evidencia | Piloto en código | Parcial: capturas reales; aceptación pendiente |
| `/wiki` | 3 | 1 | Cuaderno con alcance | Piloto en código | Parcial: lectura/conflictos/recibos/móvil; aceptación pendiente |
| `/findings` | 3 | 1 | Registro con evidencia | Piloto en código | Parcial: filtros/citas/semántica/móvil; aceptación pendiente |
| `/reports` | 3 | 1 | Lectura con trazabilidad | Piloto en código | Parcial: recorrido y capturas; aceptación humana pendiente |
| `/files` | 3 | 1 | Archivo con inspector | Piloto en código | Parcial: recorrido/teclado; aceptación humana pendiente |
| `/repositories` | 3 | 1 | Explorador con registro de fuentes | Piloto de exploración; alta completa pendiente | Parcial: snapshot/errores/origen/foco/móvil; aceptación pendiente |
| `/flow` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| **Total** | **24 / 36** | **8 / 12** | **8 / 12** | **8 pilotos** | **0 / 12** |

Los prompts, archivos, hashes, tamaños y procedencia del piloto están en
[concepts/tasks/manifest.json](concepts/tasks/manifest.json). Las tres alternativas
tienen composiciones distintas y se generaron mediante llamadas independientes
a la herramienta integrada. La variante móvil recibió la imagen elegida como
referencia; no se recortó una captura de escritorio para simularla.

Los cuatro conceptos de Conversación están en
[concepts/chat/manifest.json](concepts/chat/manifest.json), con referencia de estilo
adjunta, selección y correcciones de contrato documentadas.

Hay capturas reales de ambos pilotos en escritorio y móvil: [recorrido y límites](audits/2026-11-01-owner-workspace/report.md).
Diecisiete estados pasan axe y se probaron salto al contenido y navegación con foco.
No cierra toda la aceptación: faltan estados de interacción, zoom, lector de pantalla
y comprensión humana. Continuar con esas comprobaciones y las rutas aún pendientes.

Los conceptos de Informes y su adaptación están en [el manifest](concepts/reports/manifest.json).
El rediseño está implementado y su [recorrido](audits/2026-11-01-reports/report.md) verifica 20 estados en escritorio/móvil, citas paginadas y corrección en la tarea. La aceptación completa sigue pendiente.


Archivos (`/files`) implementa el archivo con inspector y el detalle móvil, con
subida explícita, previa de texto/PDF, descarga original y borrado confirmado.
[Conceptos y hashes](concepts/files/manifest.json),
[recorrido y límites](audits/2026-11-01-files/report.md). Seis pilotos en código,
seis rutas pendientes de implementar y cero rutas con aceptación completa.

Wiki tiene cuatro conceptos inspeccionados y selección delegada: [procedencia](concepts/wiki/manifest.json). La captura previa detectó contraste bajo y recorte del lector móvil; [piloto verificado y límites](audits/2026-11-01-wiki/report.md).

Hallazgos tiene [18 estados funcionales y lectura en tres anchos](audits/2026-11-01-findings/report.md), con valores históricos atribuidos y citas contrastables. La revisión independiente y aceptación integral permanecen abiertas.

Actualización 2026-11-02: el piloto de Hallazgos incorpora revisión independiente admitida,
historial, fuentes con hash revisado y recuperación de recibos. [Nueve estados y tres
anchos finales](audits/2026-11-02-finding-review/report.md). La aceptación integral
sigue pendiente; continúan seis pilotos y cero páginas plenamente aceptadas.

Actualización 2026-11-06: Proyectos usa el [expediente seleccionado](concepts/projects/manifest.json).
[Quince capturas y límites](audits/2026-11-06-projects/report.md) verifican lectura,
fuentes, edición concurrente, recuperación de creación/planificación/Stop y borrado.
Siete pilotos, cinco rutas aún sin conceptos/implementación y cero páginas con
aceptación completa. Los totales anteriores son registros históricos.

Actualización 2026-11-06, Repositorios: [cuatro conceptos y selección](concepts/repositories/manifest.json),
[quince capturas/comparación y límites](audits/2026-11-06-repositories/report.md).
Exploración, registro existente y revisión histórica implementados; crear/clonar/
remoto/reparar aún pendientes como capacidad principal. Ocho pilotos, cuatro rutas
sin conceptos/código y cero páginas con aceptación completa.


La preparación de Repositorios incorpora ahora remoto vacío separado, identidad
HTTP original y recuperación readonly de su respuesta perdida; cinco capturas
adicionales en [el recorrido](audits/2026-11-06-remote-source/report.md). Conserva
la selección visual y las cuentas24/36,8/12,8pilotos,0aceptadas. Reparación local,
historia entre navegadores y evaluación integral siguen pendientes.


La preparación añade [continuación explícita de Git interrumpido](audits/2026-11-06-source-repair/report.md)
con5capturas adicionales de escritorio/móvil. Conserva la dirección seleccionada
y las cuentas24/36desktop,8/12mobile,8pilotos,0aceptadas. Historial entre navegadores,
resolución de reservas/adopción, formatos/límites y aceptación integral siguen abiertos.


La historia de Repositorios se puede abrir desde otro navegador sin crear otra
preparación ni sustituir un packet pendiente; [recorrido y límites](audits/2026-11-06-source-history/report.md).
Tres contextos owner y cinco capturas finales, con respuestas tardías entre
operaciones/proyectos. Conserva24/36desktop,8/12mobile,8pilotos,0aceptadas.
