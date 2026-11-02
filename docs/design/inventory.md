# Inventario visual de la modernización

El requisito completo sigue siendo 36 imágenes independientes de escritorio,
12 adaptaciones móviles, selección y ejecución de las doce rutas. Los componentes
compartidos llevan cobertura adicional. Los números de esta tabla cuentan
archivos generados e inspeccionados, no pantallas aceptadas.

| Ruta | Escritorio / 3 | Móvil / 1 | Selección | Implementación | Aceptación visual |
| --- | ---: | ---: | --- | --- | --- |
| `/` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/projects` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/epics` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/tasks` | 3 | 1 | Lista editorial con inspector | Piloto en código | Parcial: capturas reales; aceptación pendiente |
| `/agents` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/chat` | 3 | 1 | Conversación con evidencia | Piloto en código | Parcial: capturas reales; aceptación pendiente |
| `/wiki` | 3 | 1 | Cuaderno con alcance | Piloto en código | Parcial: lectura/conflictos/recibos/móvil; aceptación pendiente |
| `/findings` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/reports` | 3 | 1 | Lectura con trazabilidad | Piloto en código | Parcial: recorrido y capturas; aceptación humana pendiente |
| `/files` | 3 | 1 | Archivo con inspector | Piloto en código | Parcial: recorrido/teclado; aceptación humana pendiente |
| `/repositories` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| `/flow` | 0 | 0 | Pendiente | Pendiente | Pendiente |
| **Total** | **15 / 36** | **5 / 12** | **5 / 12** | **5 pilotos** | **0 / 12** |

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
[recorrido y límites](audits/2026-11-01-files/report.md). Cinco pilotos en código,
siete rutas pendientes de implementar y cero rutas con aceptación completa.

Wiki tiene cuatro conceptos inspeccionados y selección delegada: [procedencia](concepts/wiki/manifest.json). La captura previa detectó contraste bajo y recorte del lector móvil; [piloto verificado y límites](audits/2026-11-01-wiki/report.md).
