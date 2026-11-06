# QA visual de los pilotos de la modernización

Resultado actual: **parcial; ocho pilotos, 24/36 conceptos de escritorio, 8/12 móviles y 0/12 rutas aceptadas completamente**. Cuatro rutas siguen pendientes de conceptos/implementación. Las secciones siguientes conservan evidencia histórica con su alcance original.

El bloqueo inicial de CUA queda como antecedente histórico. El plan autorizado
ya exige Playwright y axe; Chromium local con sandbox funciona. No se necesita
otra confirmación para ese uso. Se capturaron e inspeccionaron ocho estados de
escritorio y nueve móviles sobre copias de un ensayo sintético, sin generación
nueva ni mutaciones del producto desde el navegador.

El [recorrido con capturas](docs/design/audits/2026-11-01-owner-workspace/report.md)
detalla cada paso, problemas corregidos, comparación con los conceptos y límites.
La [evidencia técnica](docs/modernization/browser-evidence.json) conserva versiones,
hashes, pruebas y los 100 fallos heredados que aún mantienen roja la suite global.

Ya comprobado en ese recorrido: render real, elección de proyecto/tarea, propuesta,
lista y salida guardada de comandos, menú móvil y conversación guardada. Los
diecisiete estados pasan los controles seleccionados de axe; Tab/Enter verifican
el primer salto al contenido y el cambio de sección conserva título visible y
foco en el contenido. Las referencias de Tareas y Conversación se compararon con
las capturas reales. No se abrió una base del usuario.

Pendiente: formulario de sesión; solicitud/respuesta/corrección/Stop/recuperación;
preguntas de varias tareas, cambio de proyecto con borrador, errores/paginación,
diálogos, navegación íntegra sólo por teclado, zoom 200/400 %, lector de pantalla,
otros motores, evaluación de comprensión y tareas humanas. También falta reducir
la densidad de contexto en móvil y migrar los controles del engine antiguo.

De las nueve rutas pendientes de código, ocho todavía requieren conceptos y selección; todas necesitan implementación y aceptación.
El [inventario](docs/design/inventory.md) conserva12/36 conceptos de escritorio y4/12
adaptaciones móviles; las capturas de QA no son nuevos conceptos.

## Informes: resultado de este alcance visual y funcional — aprobado

Se compararon las referencias seleccionadas y las capturas finales en una misma
inspección. El piloto conserva composición editorial, índice/documento/fuentes,
paleta y adaptación móvil; usa el informe persistido real, sin copiar actor, líneas
ni ejemplo numérico ilustrativos. Los defectos de título, recorte/gutters móviles y
aviso oculto se corrigieron y recapturaron. No quedan P0/P1/P2 observados en este
recorrido; el shell y la tipografía compartida siguen dentro del rediseño global.

[Veinte estados y límites](docs/design/audits/2026-11-01-reports/report.md),
[evidencia](docs/design/audits/2026-11-01-reports/evidence.json): escritorio1440×1024,
móvil390×844, cero infracciones axe seleccionadas, regreso/selección/foco por teclado,
paginación y aislamiento. Una corrección registrada en la tarea conserva el informe
y no inicia inferencia. Falta evaluación humana, lector de pantalla, zoom y otros
navegadores; **la aceptación global sigue parcial, 0/12**. No se declara una demo
viva lista para entrega.


Archivos ya tiene tres alternativas de escritorio y adaptación móvil generadas e
inspeccionadas; se eligió Archivo con inspector. Su [selección](docs/design/selection.md)
registra las correcciones de estados no demostrados. Las [capturas iniciales](docs/design/audits/2026-11-01-files/report.md)
muestran la tabla móvil de631px; no son aceptación del rediseño. La implementación
y evaluación de Archivos siguen pendientes.

## Archivos: comparación del cuarto piloto

final result: passed — comparación visual/funcional acotada de Archivos, no aceptación
completa de la ruta o el producto. [Informe y referencias](docs/design/audits/2026-11-01-files/report.md).

Referencias1487×1058/853×1844, objetivos1440×1024/390×844; capturas reales a esos
viewports con deviceScaleFactor1. Se compararon juntas las dos parejas de imágenes
por regiones/proporciones; además se inspeccionaron regiones legibles de extracción
y procedencia y detalle a320px. La referencia no contiene activos raster de contenido.
Georgia en títulos/sans en controles, papel cálido/verde, catálogo ancho e inspector,
y detalle móvil conservan la dirección elegida. Se utiliza el shell real; no se
inventan Atlas, fechas, lectura por agentes, miniaturas o validación científica.

Se corrigieron márgenes móviles oscuros, foco de título con apariencia de campo,
encabezado principal inaccesible, selector con nombre accesible distinto del texto
y ciclo de foco del diálogo. Catorce estados pasan controles de layout/axe y el
recorrido confirma bytes originales, texto escapado, subida y borrado con proyecto.
No se observan P0/P1/P2 pendientes dentro de este alcance. P3: densidad del shell y
escala de título móvil respecto al concepto; conservar para coherencia global.

La aceptación global sigue **parcial,0/12**: comprensión humana, lector de pantalla,
zoom real y estados restantes no se dan por verificados. Archivos es el cuarto
piloto; no cierra formatos adicionales, consumidores antiguos ni el motor completo.

## Proyectos — 2026-11-06

[Expediente seleccionado](docs/design/concepts/projects/selection.md) implementado
con alcance/fuentes/actividad/decisiones originales y recuperación de solicitudes.
[Quince capturas, catorce imágenes únicas y límites](docs/design/audits/2026-11-06-projects/report.md),
cero errores JS/infracciones axe en las regiones revisadas/overflow horizontal.
Se inspeccionaron concepto, escritorio y móvil. La fuente no comprobada sigue
siendo desconocida; el borrado exige confirmación y protege historia. Pendientes
aceptación humana/tecnologías de asistencia/zoom/otras rutas y shell integral.

## Repositorios — 2026-11-06

final result: passed — explorador y registro de carpeta existente; no aceptación
integral de Repositorios ni del producto. [Comparación conjunta](docs/design/audits/2026-11-06-repositories/comparison-desktop.png)
y [quince capturas/límites](docs/design/audits/2026-11-06-repositories/report.md).
Se revisaron tipografía, espaciado, colores, calidad y contenido frente al concepto
seleccionado. P2 móvil corregido: abrir archivo ahora revela texto tras cargarlo,
con foco y contexto de fuente/revisión. Evidencia final13–15; sin P0/P1/P2 visuales
observados en ese alcance. P3 DD032: densidad de rutas, líneas/sintaxis y pista de
scroll. Crear/adoptar Git/clonar/remoto/reparar siguen pendientes funcionales, y
comprensión humana/zoom/lector de pantalla/otros motores/aceptación global también.
