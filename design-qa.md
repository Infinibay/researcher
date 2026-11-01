# QA visual de los pilotos Tareas y Conversación

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

Las otras diez rutas requieren todavía sus conceptos, selección, implementación
y aceptación. El [inventario](docs/design/inventory.md) conserva 6/36 conceptos de
escritorio y 2/12 adaptaciones móviles; las capturas de QA no cuentan como nuevos
conceptos generados. No hay un servidor de demo vivo declarado listo para entrega.
