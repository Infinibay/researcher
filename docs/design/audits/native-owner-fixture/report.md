# Inspección del propietario con una fixture nativa nueva

Fecha local: 2026-11-06. Backend instalado, web ya compilada y comando real sin
modelo. Se crean fuentes, autoridad y base nuevas; se cierran los procesos antes
de copiar los registros sintéticos para su lectura por HTTP. No se reutiliza un
ensayo antiguo ni una base del usuario.

## Resultado observado

Chromium 156.0.8078.4 completa ocho estados a 1440×1024 y nueve a 390×844:
selección de proyecto, tarea, inspector, comandos, salida y Conversación; móvil
incluye navegación. Sin hallazgos Axe en esos estados, errores JavaScript,
recursos fallidos, orígenes externos o peticiones de escritura desde el navegador.
El enlace de salto mueve el foco al contenido y la navegación conserva el foco
comprobado. [Escritorio](desktop-capture.json), [móvil](mobile-capture.json).

La lectura muestra los 86 bytes del resultado real, incluido UTF-8, sin repetir
el comando. Los nueve conjuntos de tablas comparados permanecen iguales en la
fuente cerrada y su copia. Ambos servidores originales terminaron con código -15;
los procesos nativos ya estaban cerrados. No se enviaron turnos de modelo.

Se revisaron visualmente cuatro capturas concretas:

- [Salida en escritorio](desktop-command-output.png): estado, salida y límites
  de aceptación legibles; los controles de paginación están presentes.
- [Conversación en escritorio](desktop-chat-task.png): tarea/contexto y estado
  separados de las fuentes. El diagnóstico no se presenta como investigación aceptada.
- [Salida en móvil](mobile-command-output.png): resultado ajustado al ancho,
  controles visibles y datos de cierre conservados.
- [Conversación en móvil](mobile-chat-task.png): retorno a tareas, título y estado
  legibles. La cabecera consume una parte considerable del alto; DD070 conserva
  esa observación para el pulido final.

El diagnóstico termina la ejecución como `failed` porque no hubo una investigación
ni una aceptación, aunque su único comando terminó correctamente. Esa distinción
es intencional. El runtime HTTP está sin configurar para generar más trabajo.

## Límites e intentos previos

El primer recorrido falló buscando el nombre accesible antiguo «Seleccionar
proyecto». La captura ARIA mostró el nombre actual con el proyecto incluido;
se corrigió el selector y se conserva el fallo original. No hubo cambios en el
producto para hacer pasar la captura.

La inspección visual se limita a las cuatro imágenes enlazadas. Diecisiete estados
sin hallazgos automáticos no equivalen a aceptación completa de Tareas,
Conversación ni las doce páginas. No se prueban aquí login visual, generación,
preguntas reales, todos los controles por teclado, otros navegadores, colores
forzados, migración de datos o comprensión humana. Las 12 páginas siguen sin
aceptación integral. [Recibos y límites](../../../modernization/remaining-evaluation-runners-results.json).
