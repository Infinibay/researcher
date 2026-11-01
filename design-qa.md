# QA visual de los pilotos Tareas, Conversación e Informes

Resultado actual: **parcial; 0/12 rutas aceptadas completamente**.

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
