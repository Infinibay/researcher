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
El navegador CUA no está disponible. El contraste numérico cubre sólo los pares
de tokens listados en el manifiesto; faltan foco efectivo, zoom, lector de
pantalla, comparación visual, diálogos y todos los estados de interacción.

La cabecera aún conserva controles del engine anterior. Las once páginas restantes
todavía necesitan conceptos, selección y rediseño. Faltan los bloques de
explicación/diagrama estructurados y su aceptación humana. Consultar
[inventario](inventory.md) y [estado de QA](../../design-qa.md).
