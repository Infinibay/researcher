# Navegación real de las doce rutas: teclado y espacio estrecho

**Se completaron las 24 transiciones por teclado; la prueba completa sigue fallando
por cuatro desbordamientos internos.** No se presenta como una aceptación de
accesibilidad. Se anotan los ajustes para después de las capacidades principales,
siguiendo la política del usuario; no se cambió lógica ni estilo del producto.

Base `fc863f3`. Bloque 7 noviembre 2026, 14:30:24–14:36:09 UTC: **5 min 45 s**
hasta examinar el resultado y las doce capturas estrechas. API, SQLite y servidor
instalado reales; cuenta y datos sintéticos. Cero inferencias. Chromium del
repositorio continúa el fallback por host de navegador integrado indisponible.

## Recorrido y resultado

El propietario crea dos proyectos, un grupo, un hito, dos tareas, una dependencia
y una corrección mediante los formularios reales. Sobre ese estado, la prueba
recorre todas las rutas con Tab y Enter a 1440 y 320 píxeles CSS. No fuerza foco
con JavaScript ni simula respuestas HTTP. Comprueba que el foco quede en el área
de contenido, admitiendo que la página enfoque su propio encabezado.

| Comprobación | Resultado |
| --- | --- |
| Doce rutas, dos anchos | 24 transiciones completas; contenido enfocado |
| Salto al contenido | Funciona en ambos anchos |
| Menú móvil | Se abre por teclado, navega y se cierra; Escape devuelve el foco al botón |
| Errores HTTP / JavaScript | Ninguno observado |
| Desborde del documento exterior | Ninguno observado |
| Desborde dentro del contenido | Documentos, Hallazgos, Informes y Archivos a320px |
| Axe en toda la página | Nombre accesible del contador en24estados; falta de H1 en índice móvil de Informes |
| Resultado del harness | Exit1 por los cuatro casos de reflow; se conserva el fallo |

La base y sus registros permanecen iguales después de cerrar el servicio; integridad
`ok`, cero runs/dispatches. El proceso termina143 y el grupo de recursos se elimina.
[Prueba completa](evidence.json), [operación](operation.json), [cierre](service-closure.json),
[hashes y alcance](../../../modernization/web-navigation-results.json).

## Hallazgos para la pasada final

DD106 conserva la discrepancia entre el contador visible de actividad y el nombre
accesible del botón, y el H1 ausente del índice móvil de Informes. Axe clasifica
el primero como `serious` y el segundo como `moderate`; no se rebaja su severidad
ni se declara conformidad por diferirlos. Los enlaces y acciones siguen accesibles
por teclado. Su corrección pertenece a la aceptación final de accesibilidad.

DD107 conserva los cuatro desbordamientos internos. Las capturas permiten leer
las acciones principales, pero el contenedor tiene más ancho desplazable que
espacio disponible. La lectura de estilos muestra márgenes de -1.5rem junto a
padding móvil de1rem: es una hipótesis del origen, pendiente de verificar con
medidas de elementos al corregirlo. La ausencia de overflow del documento exterior
no bastaba para detectar este problema; la prueba nueva mide también el main.

## Capturas inspeccionadas

Se guardaron24capturas; se abrieron las doce de320px. Las de escritorio son evidencia
capturada, sin atribuirles una revisión visual individual en este bloque.

| Ruta | Captura estrecha inspeccionada | Captura de escritorio |
| --- | --- | --- |
| Resumen | [320px](320-overview.png) | [1440px](1440-overview.png) |
| Proyectos | [320px](320-projects.png) | [1440px](1440-projects.png) |
| Planificación | [320px](320-epics.png) | [1440px](1440-epics.png) |
| Tareas | [320px](320-tasks.png) | [1440px](1440-tasks.png) |
| Agentes | [320px](320-agents.png) | [1440px](1440-agents.png) |
| Conversación | [320px](320-chat.png) | [1440px](1440-chat.png) |
| Documentos | [320px](320-wiki.png) | [1440px](1440-wiki.png) |
| Hallazgos | [320px](320-findings.png) | [1440px](1440-findings.png) |
| Informes | [320px](320-reports.png) | [1440px](1440-reports.png) |
| Archivos | [320px](320-files.png) | [1440px](1440-files.png) |
| Repositorios | [320px](320-repositories.png) | [1440px](1440-repositories.png) |
| Ejecución | [320px](320-flow.png) | [1440px](1440-flow.png) |

## Límites y primer intento

El primer intento llegó a seis rutas y se detuvo al exigir foco exactamente sobre
el main. Documentos dirige el foco al encabezado de su índice. Se corrigió el
verificador para exigir foco dentro del contenido; el producto no cambió.
[Recibo original](initial-evidence.json). El segundo intento no se repite para
ocultar sus fallos: completó todas las acciones y conservó los hallazgos.

320px CSS prueba espacio estrecho; no es zoom real, evaluación con lector de
pantalla ni comprensión humana. Varias páginas están vacías porque no se ejecutó
investigación. Los estados de contenido, error y ejecución conservan sus ensayos
previos y no se consideran recién verificados aquí. Siguen0/12páginas aceptadas.
