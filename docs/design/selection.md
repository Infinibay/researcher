# Selección visual

Fecha: 2026-10-31. El usuario delegó explícitamente la selección en el implementador.
Se comparan imágenes generadas e inspeccionadas, no pantallas ejecutadas. La
accesibilidad y el responsive se puntúan como expectativas de diseño; necesitan
pruebas sobre el producto. La escala es de 1 a 5 y el total se expresa sobre 100.

## Tareas: lista editorial con inspector

| Concepto independiente | Claridad 30% | Lectura 25% | Coherencia 20% | Accesibilidad prevista 15% | Responsive previsto 10% | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Lista editorial con inspector](concepts/tasks/editorial-inspector.png) | 4,5 | 4,5 | 4,5 | 4 | 4 | **87,5** |
| [Tablero operativo](concepts/tasks/operational-board.png) | 3,5 | 4 | 3,5 | 3,5 | 3 | 71,5 |
| [Cuaderno de investigación](concepts/tasks/research-notebook.png) | 4 | 4,5 | 4 | 4,5 | 4 | 84 |

La lista editorial conserva la selección entre tareas mientras deja un documento
amplio para leer evidencia y corregir el contexto. El tablero dedica demasiado
alto de pantalla a otras tareas y exige reorganizar dos columnas de evidencia en
móvil. El cuaderno tiene buena continuidad de lectura, pero esconde la cola detrás
de un selector y su composición agrega destinos que el producto no tiene.

La ganadora establece papel cálido, tinta oscura, acento verde funcional, títulos
editoriales y listas con separadores. La fila activa usa texto y borde además de
color. El panel conserva Trabajo, Detalles, Comentarios y Dependencias. No se
importan sus datos sintéticos, iconos inventados ni destinos inexistentes.

Correcciones necesarias de la referencia:

- La imagen de escritorio mezcla la corrección de contexto con la nueva solicitud.
  La UI los separa y explica qué operación inicia inferencia.
- Un resultado nativo sigue siendo una propuesta. El botón de iniciar permanece
  deshabilitado si el protocolo no permite otra ejecución, aunque la imagen de
  escritorio lo muestre habilitado. La [adaptación móvil](concepts/tasks/editorial-inspector-mobile.png)
  incorpora esta corrección.
- La evidencia visible en el concepto es una ficción de diseño identificada en el
  brief. El producto muestra únicamente sus fuentes, correcciones y resultados
  guardados. No convierte la hipótesis sobre reintentos en un diagnóstico real.
- La columna de procedencia se repliega debajo de la lectura si no cabe; nunca se
  reduce el texto para forzar tres columnas. En móvil se alterna entre la lista y
  el panel con un control de regreso. El compositor participa del flujo del
  documento y no tapa la explicación.

## Estado de implementación y límites

El piloto cambia la lista, el inspector, el trabajo y la navegación responsive
compartida. El panel anterior se reemplaza por `TaskInspector.tsx`, sin overlay.
La selección y los borradores se reinician al cambiar de proyecto. Consultar la
lista o cambiar sus filtros no desmonta el inspector abierto. Elegir una tarea
no inicia una ejecución. Las operaciones de runtime conservan sus contratos.

Hay comprobaciones de HTML renderizado en servidor y compilación. No equivalen
a una captura, a una interacción de navegador ni a una prueba de comprensión.
El registro inicial sólo tenía SSR/build. Ahora hay un [recorrido real en Chromium](audits/2026-11-01-owner-workspace/report.md)
con capturas de escritorio/móvil comparadas con las referencias, axe y comprobaciones
de salto inicial y navegación con foco. Faltan zoom, lector de pantalla, diálogos,
todos los estados de interacción y comprensión humana.

La cabecera aún conserva controles del engine anterior. Las diez páginas sin piloto
todavía necesitan conceptos, selección y rediseño. Faltan los bloques de
explicación/diagrama estructurados y su aceptación humana. Consultar
[inventario](inventory.md) y [estado de QA](../../design-qa.md).

## Conversación: conversación con evidencia — 2026-11-01

Se generaron tres alternativas independientes y una adaptación móvil de la elegida,
con el concepto editorial de Tareas adjunto como referencia de estilo. No fue una
captura de la aplicación. El usuario delegó la selección; no se repitió una solicitud
de aprobación. Las puntuaciones son evaluación del concepto, no resultados de uso.

| Concepto | Claridad 30% | Lectura 25% | Coherencia 20% | Accesibilidad prevista 15% | Responsive previsto 10% | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Conversación con evidencia](concepts/chat/conversation-with-evidence.png) | 4,5 | 4,5 | 4,5 | 4 | 4,5 | **88,5** |
| [Cuaderno del caso](concepts/chat/case-notebook.png) | 4 | 4,5 | 4 | 4 | 3,5 | 81,5 |
| [Mesa de intervención](concepts/chat/intervention-desk.png) | 2,5 | 4 | 3,5 | 4 | 3,5 | 68 |

La primera conserva contexto y continuidad del intercambio, con separación clara
entre tareas, conversación y fuentes. El cuaderno lee bien, pero pierde el índice
de otras preguntas y su margen de anotaciones complica la adaptación móvil. La mesa
hace evidente la próxima acción, pero la imagen inventa como comprobado que no hay
una clave estable: confunde hipótesis con evidencia, por lo que se descarta esa
jerarquía. Una imagen no prueba hechos del proyecto.

La [adaptación móvil](concepts/chat/conversation-with-evidence-mobile.png) recompone
las columnas como lectura, fuentes desplegables y respuesta, con regreso explícito
a tareas. El producto usa contexto y fuentes reales, no el ejemplo Atlas.

Correcciones de contrato respecto al mock:

- No se añade una hipótesis verificada, confianza o fuente inventada para rellenar
  la columna lateral. Se muestran sólo capturas y procedencias guardadas.
- Responder conserva pregunta/opciones/versiones y no inicia otra ejecución. Las
  preguntas durante cierre aparecen en la bandeja, pero su formulario espera el
  cierre confirmado. El diseño no habilita un inicio incompatible con ese estado.
- La UI explica qué contexto recibe actualmente el próximo trabajo: tarea,
  correcciones y respuestas. Ver el historial no equivale a que todo se entregue
  automáticamente al modelo. La entrada inicial y su continuidad acotada ya se
  registran; siguen pendientes compactación larga y procedencia de entradas posteriores.
- Se conservan cabecera, sesión y controles reales del producto; no se inventan los
  destinos reducidos del menú generado. Índice más compacto, contenido en flujo y
  columna de contexto apilada cuando no cabe, con medidas por contenedor.
- No se extraen fotos, texturas ni avatares: los conceptos contienen controles,
  tipografía y separadores. La implementación usa HTML/CSS y el sistema existente.

El código integra la bandeja de todas las solicitudes del proyecto, selección
validada de tarea, conversación corriente visible y archivo de hilos de sólo
lectura. Hay pruebas SSR, transporte/API y build. El [recorrido en navegador](audits/2026-11-01-owner-workspace/report.md)
ya incluye conversación guardada y adaptación móvil. La aceptación visual completa,
la navegación integral por teclado y la comprensión humana siguen pendientes.
Después de este avance quedan diez rutas por generar/seleccionar/implementar y
las doce por aceptar visualmente, además de los componentes compartidos.


## Informes: lectura con trazabilidad — 2026-11-01

Se capturó primero el producto actual sobre una copia de un ensayo sintético.
Sus imágenes y la referencia de Tareas se adjuntaron a tres llamadas independientes
de ImageGen. La adaptación móvil recibió la elegida; no es un recorte de escritorio.
El usuario delegó la selección. La implementación de esta página sigue pendiente.

| Concepto | Claridad30% | Lectura25% | Coherencia20% | Accesibilidad prevista15% | Móvil previsto10% | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Lectura con trazabilidad](concepts/reports/reading-with-provenance.png) | 4,5 | 4,5 | 4,5 | 4 | 4,5 | **88,5** |
| [Biblioteca con vista previa](concepts/reports/library-preview.png) | 4 | 3,5 | 4,5 | 4 | 3,5 | 78,5 |
| [Cuaderno de evidencia](concepts/reports/evidence-notebook.png) | 3,5 | 4,5 | 4,5 | 4 | 4,5 | 82,5 |

La elegida deja espacio para leer y mantiene las fuentes cerca del argumento. La
biblioteca dedica más ancho al índice y estrecha el documento. El cuaderno lee
bien, pero esconde la colección y afirma que el contexto sigue siendo el mismo,
algo que la imagen no puede demostrar y los datos actuales podrían contradecir.
Las puntuaciones juzgan conceptos; no acreditan accesibilidad ni uso humano.

Correcciones obligatorias al llevar la referencia a código:
- Las líneas18–24/7 de la primera imagen son inventadas por el generador. Mostrar
  sólo citas, locator/hash/fecha guardados; no copiar números de línea ni fuentes
  sintéticas como hechos. Tampoco copiar un agente o versión no registrados.
- Conservar el Markdown original. La lectura puede evitar el encabezado inicial
  duplicado cuando coincide con el título, sin reescribir el contenido persistido
  ni insertar el ejemplo100×1,21 del mock en un informe que no lo contiene.
- «Ver tarea y corregir contexto» necesita selección de tarea por URL y proyecto
  correcta. TasksPage actualmente ignora ese enlace; probar el destino antes de
  declarar el recorrido terminado. Abrir una tarea no inicia inferencia.
- Las fuentes guardadas deben venir de relaciones del informe bajo el proyecto
  autorizado, no de buscar números en el Markdown o de conceder al usuario un token
  de herramientas. Mostrar paginación/ausencia y errores de lectura con claridad.
- Móvil alterna índice/lector y sitúa las fuentes debajo del documento, con regreso
  explícito y controles en flujo. Comprobar límites de los elementos, porque el
  scrollWidth del documento no detectó el recorte observado en la captura inicial.
- Mostrar fechas con una zona definida y comprensible; la referencia ilustrativa
  no acredita «hace X» ni que el contexto esté actualizado.

[Brief y procedencia](concepts/reports/brief.md), [manifest](concepts/reports/manifest.json),
[audit inicial](audits/2026-11-01-reports/report.md).
