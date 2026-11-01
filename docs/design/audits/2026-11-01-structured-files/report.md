# Comprobación de previas estructuradas en Archivos

Se amplía el cuarto piloto existente, sin otra dirección visual ni nuevas páginas
aceptadas. La vista mantiene su catálogo e inspector; sólo cambia el alcance de
extracción y el texto que explica sus límites.

Se comprobaron ocho estados reales: CSV, JSON, XML y DOCX a 1440 × 1024 y 390 × 844.
En cada formato se subió el archivo mediante la interfaz, se extrajo la previa,
se descargaron los bytes originales y se confirmó el borrado. No hubo errores de
página, violaciones detectadas por axe ni overflow horizontal. La inspección visual
de CSV en escritorio y DOCX en móvil confirmó el ajuste del texto, las marcas de
estructura y la legibilidad de los avisos.

La interfaz distingue adjunto, previa y fuente capturada. CSV explica que usar
la primera fila como encabezados es una suposición. DOCX explica qué se omite y
que no comprueba el diseño visual. La previa no crea una fuente ni demuestra que
el agente haya leído el documento. Los textos extraídos son evidencia no confiable,
mostrada literalmente.

[Evidencia y capturas](evidence.json), [invariantes de los datos](fixture-invariants.json).
Se conservó el informe previo y la cuenta de despachos nativos; no se generó ninguna
inferencia. La cuenta de adjuntos volvió a su valor inicial después de borrar las
cuatro subidas sintéticas. Un proyecto ajeno no pudo abrir las previas.

Esto no comprueba comprensión con lector de pantalla, todos los estados de error,
zoom, aceptación humana de la página completa ni calidad de síntesis. Las comprobaciones
previas del piloto se conservan en el [informe de Archivos](../2026-11-01-files/report.md).
