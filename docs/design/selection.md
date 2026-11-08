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


### Informes: implementación y comparación verificadas

El piloto reproduce la jerarquía editorial, papel cálido, índice lateral, documento y fuentes de Lectura con trazabilidad; en móvil el índice y lector alternan, las fuentes y la acción de corregir siguen al cuerpo. Se compararon juntas referencias y capturas finales a1440×1024/390×844. Se corrigieron foco con borde negro en el título, márgenes oscuros móviles y aviso de proyecto oculto.

Se conserva el contenido real del informe: la maqueta contiene un ejemplo numérico, líneas y actor ilustrativos que no están registrados en el resultado original. No se inventaron para imitar la imagen. Se mantiene la navegación compartida de doce rutas del producto; fuentes/tamaños del shell siguen sujetos al trabajo global. El enlace abre la tarea exacta y una corrección queda registrada para el próximo intento, sin iniciar inferencia ni aceptar/reemplazar el borrador. [Resultado y límites](audits/2026-11-01-reports/report.md).


## Archivos: Archivo con inspector

Las tres imágenes se generaron de forma independiente y se inspeccionaron antes de elegir. Se adjuntaron la captura real de Archivos y la referencia editorial de Informes. El usuario delegó la selección; no se repite una aprobación. Las puntuaciones son juicio de diseño sobre estas imágenes, no avance del proyecto ni pruebas de usabilidad.

| Dirección | Claridad /10 (25) | Continuidad /10 (15) | Densidad /10 (20) | Honestidad del estado /10 (25) | Móvil previsto /10 (15) | Total /100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Archivo con inspector | 9 | 9.5 | 8.5 | 8 | 9 | **87.25** |
| Biblioteca de fuentes | 8.5 | 9.5 | 7.5 | 8 | 8.5 | 83.25 |
| Registro de adjuntos | 7.5 | 9 | 7 | 7.5 | 7 | 75.5 |

Se elige **Archivo con inspector**: permite comparar nombres/tipos en la lista y mantener acciones/contexto del archivo elegido a la vista. Continúa la jerarquía de Tareas e Informes. Biblioteca repite varios datos y su banda explicativa consume mucho espacio; Registro duplica acciones y texto, con una tabla más frágil en móvil.

La adaptación móvil generada usa detalle del archivo y regreso a la lista, sin encoger una tabla de escritorio. Se inspeccionó su imagen, incluidos nombre, estado y acciones. Reducir duplicación de descripción al implementar; no adoptar el peso excesivo de Eliminar ni un logo PDF como nuevo sistema de iconos. Mantener el shell real compartido, foco/teclado y tamaños responsive.

**Correcciones de contrato antes de código:** «texto no consultado en ninguna tarea» no se deduce de esta pantalla. Usar «lectura no comprobada en esta vista» o un estado sustentado por registros concretos; una captura no prueba lectura completa ni validez. Un adjunto registrado tampoco prueba que el archivo físico siga intacto. La futura previa debe diferenciar extracción puntual de fuente persistida y no inventar páginas/texto. Las fechas/Atlas del mock son ilustrativas y se sustituyen por datos reales. Subir/abrir no inicia inferencia; Eliminar necesita confirmación concreta. Si se muestra un límite de subida, debe estar aplicado por la API.

[Brief](concepts/files/brief.md), [manifest con hashes](concepts/files/manifest.json), [recorrido y límites](audits/2026-11-01-files/report.md). Implementado como cuarto piloto; doce conceptos de escritorio y cuatro móviles, cero rutas completamente aceptadas.


### Archivos: implementación y comparación

Se conserva el catálogo ancho con inspector lateral, fondo papel, títulos Georgia,
acciones verdes y selección discreta. En móvil se alternan lista y detalle con
regreso y restauración de foco. Las referencias y capturas se inspeccionaron juntas;
se corrigieron márgenes oscuros, foco de título con apariencia de campo, encabezado
móvil inaccesible y nombre accesible del selector de proyecto.

El shell compartido conserva sus controles reales y nombre de proyecto; el ejemplo
Atlas y las fechas del mock no son datos del producto. El orden real es por fecha e
identidad, sin copiar una flecha de orden alfabético sin funcionalidad. La descripción
aparece una vez en el inspector. El borrado tiene menor peso visual y confirmación
concreta. En lugar de un supuesto estado de lectura se ofrece una extracción explícita
con fecha/hash/páginas y distinción entre previa y fuente capturada. No se dibujaron
miniaturas de páginas o datos de lectura inexistentes. No hay nuevos activos raster
necesarios: los elementos del concepto son texto/controles, sin imágenes de contenido.

La tipografía del título móvil y densidad del shell difieren del mock; quedan como
ajustes P3 de coherencia global. No impiden el recorrido probado ni cierran la
aceptación humana/lector de pantalla/zoom de esta ruta.


## Wiki / Documentos — 2026-11-01

Tres alternativas de escritorio generadas de forma independiente con capturas reales
y el lenguaje editorial de Informes. Orden mostrado: Cuaderno con alcance, Biblioteca
documental y Lectura con margen. La selección fue delegada explícitamente por el usuario.
Se elige **Cuaderno con alcance**: índice persistente para cambiar entre notas y lector
amplio con alcance/revisión a la vista. Biblioteca documental ocupa demasiada altura con
la lista al leer; Lectura con margen duplica contexto y exige un paso extra para cambiar
de documento. Juicio de diseño, no medición de avance ni aceptación humana.

[Imágenes, prompts y procedencia](concepts/wiki/manifest.json). Móvil generado desde la
imagen seleccionada: lista y lector como vistas separadas. Implementar sin repetir el
título gigante de la página, sin usar «Espacio de nombres» como jerga innecesaria y sin
presentar las notas como resultados validados. Usar «Este proyecto / Biblioteca global»
y explicar el alcance global. Conservar borradores ante error/conflicto/cambio de proyecto.
Piloto implementado y verificado en16 estados funcionales y tres anchos de lectura.
Cinco pilotos en código,15/36 conceptos de escritorio y5/12 móviles; cero rutas con
aceptación completa. [Recorrido y límites](audits/2026-11-01-wiki/report.md).

## Hallazgos — 2026-11-01

Tres alternativas independientes y una adaptación móvil generadas e inspeccionadas.
Se elige **Registro con evidencia**: índice persistente y lector amplio conservan la
orientación al contrastar varias afirmaciones. La tabla empuja la lectura bajo el
listado; el dossier duplica metadatos y estrecha el texto. Juicio delegado de diseño,
no aceptación humana. [Imágenes/procedencia](concepts/findings/manifest.json).

El contenido ilustrativo de las imágenes no se utiliza como evidencia real. Implementar
con citas/fechas/autorías guardadas; no inventar modificación ni un campo de explicación
que no exista. Usar Fuentes citadas, porque pueden apoyar o contradecir la afirmación.
La confianza declarada heredada no equivale a certeza científica; la revisión independiente
requiere admisión real del reviewer. Móvil separa lista/lector. Piloto implementado y verificado en18 estados funcionales; aceptación completa pendiente.

## Proyectos: expediente — 2026-11-06

Tres alternativas independientes y una adaptación móvil generadas e inspeccionadas.
El usuario delegó elegir: [comparación y elección](concepts/projects/selection.md),
[procedencia](concepts/projects/manifest.json). El expediente conserva contexto y
lectura sin convertir metadata en actividad. La implementación mantiene lista y
documento en escritorio; en móvil abre el expediente con regreso/foco a su fila.
Se comprobaron estados reales y errores/recuperación; no es aceptación completa.
[Capturas, comparación y límites](audits/2026-11-06-projects/report.md).

## Repositorios: explorador con registro — 2026-11-06

Se eligió la primera de tres imágenes independientes por autorización del usuario;
[comparación](concepts/repositories/selection.md), [prompts/hashes](concepts/repositories/manifest.json).
Mantiene fuente, árbol y documento; revisiones en una lectura separada. El piloto
usa objetos Git reales completos, registro existente y origen de PR. El móvil
recompone la navegación y revela el archivo tras cargarlo. Alta/clonado/remoto/
reparación y aceptación integral siguen pendientes.
[QA final acotado](audits/2026-11-06-repositories/report.md).


## Aceptación de Documentos — 2026-11-08

El concepto `scoped-notebook` conserva su selección. La ruta completa tiene
aceptación técnica/visual mediante HTTP/SQLite reales,25estados canónicos,
recuperación de sesión/recibos/borradores, historia/paginación y lectura actual.
No se generan más alternativas ni se cambia el estilo. Es la primera de12páginas
aceptadas; U08 y el cierre global siguen abiertos. La magnificación CSS exploratoria
no se acepta como prueba de zoom nativo. [Auditoría](audits/2026-11-08-wiki-acceptance/report.md).

## Aceptación de Archivos — 2026-11-08

Se mantiene `archive-inspector` y su adaptación móvil. La aceptación técnica y
visual delegada cubre 25 estados con HTTP/SQLite/filesystem reales y cero
inferencias. El historial confirmado se abre a demanda para priorizar el catálogo;
los intentos pendientes cargados siguen visibles y los anteriores son accesibles.
Se comprueban bytes exactos, cinco formatos de documento, recuperación y borrado.
Dos capturas iniciales de vacío se rechazan; la revisión corregida espera el
proyecto y mensaje final. Son **2 de 12 páginas** junto con Documentos; DD127 y
U08 quedan abiertos. [Auditoría](audits/2026-11-08-files-acceptance/report.md).
