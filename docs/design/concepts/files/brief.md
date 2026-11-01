# Brief: Archivos de referencia del proyecto

Objetivo: que el propietario pueda subir, identificar y recuperar el adjunto
correcto, entender qué se comprobó de él y llevarlo a una tarea de investigación.
Ruta `/files`, aplicación web de escritorio/móvil. `/wiki` corresponde a Documentos
(wiki), otra capacidad; no fusionarlas por compartir el término «documento».

Referencias inspeccionadas: [escritorio actual](../../audits/2026-11-01-files/before-desktop.png),
[móvil actual](../../audits/2026-11-01-files/before-mobile.png),
[Informes seleccionado](../reports/reading-with-provenance.png) y su dirección
editorial ya implementada. El usuario delegó elegir el mejor concepto; no requiere
otra aprobación de selección. Se mantienen tres alternativas independientes de
escritorio1440×1024 y una adaptación390×844 de la elegida, no recortes.

## Tarea y contenido

La persona trabaja con un proyecto explícito de la cabecera. Ve tres adjuntos:
`politica-fiscal.pdf`, `policy.txt`, `invoice.txt`. El PDF es un fixture de962B;
subirlo no comprueba que tenga texto ni que sus páginas se hayan leído. La lista
actual no contiene estado de extracción: la imagen no debe inventar procedencia,
confianza, resumen semántico, captura completada ni una ejecución activa.

Acciones: subir un archivo con descripción opcional bien etiquetada, consultar
su identidad, descargarlo y eliminarlo mediante confirmación concreta. Llevar al
usuario a las tareas del mismo proyecto sin iniciar inferencia por abrir/subir.
La previa de texto/páginas sólo puede prometerse si se implementa una consulta de
propietario con sus límites y estados; no simularla con texto de una maqueta.

Necesita vacío, carga, error/reintento, subida en progreso, rechazo por límites o
formato, nombre largo, cambio de proyecto, confirmación y éxito reales. En móvil,
las acciones quedan junto al archivo sin desplazamiento horizontal oculto.
Teclado, foco visible, labels, contraste, lectura ampliada y lector de pantalla
forman parte de aceptación; una captura o axe no sustituyen tareas con una persona.

## Dirección profesional y alternativas

Continuar papel cálido, tinta oscura, serif en títulos y sans en controles, acento
verde funcional; jerarquía editorial coherente con Tareas/Conversación/Informes.
Evitar tarjetas decorativas, métricas ficticias, gradientes, orbes/estrellas y
copy de marketing. No «diseño hecho por AI» ni mensajes sobre tecnología interna.
La interfaz y sus estados se explican en español; MIME técnico queda en detalle
si ayuda a diagnosticar compatibilidad, no como etiqueta dominante del listado.

Variar composición y prioridades, manteniendo el lenguaje visual:

1. **Archivo con inspector:** registro de referencias a la izquierda y detalle del
   archivo elegido a la derecha; upload compacto y alcance por proyecto claros.
2. **Biblioteca de fuentes:** lista editorial de ancho cómodo, detalles en la propia
   fila y upload desplegable; prioriza lectura y accesibilidad móvil.
3. **Registro de adjuntos:** tabla compacta en escritorio, detalle inferior y subida
   lateral; comparar si su densidad mejora o perjudica elegir el archivo correcto.

Elegir por claridad de estado/acciones, trazabilidad sin datos inventados,
continuidad con las otras páginas, teclado/móvil y densidad útil. Documentar
puntuación, defectos corregidos y desviaciones necesarias antes de implementar.

## Contratos a conectar

Reutilizar la captura y el worker PDF existentes. La API heredada de uploads
necesita límites de cuerpo, alcance de rutas/archivos y errores antes de prometer
un máximo en la imagen. El parser limita1MB de archivo y200KB de texto extraído;
subida y extracción son operaciones diferentes. Los reportes siguen siendo
borradores y el usuario puede corregir contexto en su tarea.

Estado: alternativas, selección y adaptación móvil generadas e inspeccionadas;
implementación y aceptación **pendientes**. Véase [manifest](manifest.json). Este brief no reduce el alcance de las
otras rutas, formatos, engine, prompts, migración ni evaluación humana.
