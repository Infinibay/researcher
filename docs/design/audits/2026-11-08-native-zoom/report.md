# Zoom nativo sobre el espacio de trabajo instalado

Las doce rutas pasan el recorrido al **200 % y 400 % de zoom nativo**, con
teclado, desplazamiento y análisis Axe de página completa: **24 estados, cero
fallos**. Se corrigió la distribución compartida de la cabecera y el acceso al
contenido en ventanas de poca altura. La comprobación adicional a1440/320px sin
zoom pasa otros24estados. [Resultados](../../../modernization/native-zoom-results.json).

Este resultado no acredita lector de pantalla, comprensión humana, todos los
estados posibles de cada página ni conformidad universal con WCAG. La evaluación
usa contenido sintético: dos proyectos, un grupo/hito y dos tareas con dependencia
y corrección del propietario. Documentos, hallazgos e informes no reciben nuevos
registros para esta prueba; sus anteriores recorridos poblados conservan su alcance.

## Resultado y cambios

| Observación | Corrección / comprobación final |
|---|---|
| A640px CSS, los controles de ejecución dejaban el nombre corto del proyecto en14líneas | Una fila propia para ejecución bajo700px; nombre observado en una línea en ambos factores |
| La cabecera fija dejaba43px CSS de contenido al400% | En viewport corto, el documento puede desplazar la cabecera y dejar la pantalla para leer el contenido |
| El foco de ruta impedía ese desplazamiento del documento | Se conserva el reinicio de main y se permite que el navegador revele su foco; JSDoc describe la responsabilidad |
| Controles junto al borde al navegar por teclado | Margen de desplazamiento de media rem para controles; los24primeros controles de contenido comprobados quedan totalmente visibles |
| Axe puede mover el foco durante su inspección | Las observaciones de teclado ocurren antes del análisis; se registran los focos anterior/posterior a Axe |
| PageDown seguía animándose cuando el ensayo pulsaba Tab | Se espera el evento real `scrollend` antes del siguiente control; no se fuerza foco ni desplazamiento por JavaScript |

Los pequeños recortes del ensayo inicial no se presentan como violaciones
normativas demostradas. Las capturas y medidas sí muestran la pérdida de espacio
de lectura y la distribución defectuosa del nombre. El ajuste conserva el diseño
Expediente, los controles y las acciones existentes.

## Evidencia del recorrido

Chromium156.0.8078.4 completo, headless, con perfiles nuevos y preferencias nativas.
Ventana exterior1280×1024; viewport CSS640×468 al200% y320×234 al400%; DPR2/4.
Zoom CSS1, transformnone y escala visual1. No se usa `setViewportSize`, zoom CSS
ni emulación de escala para representar el zoom.

Cada perfil se empareja mediante el formulario real y selecciona el proyecto por
teclado. Se comprueban salto al contenido, doce enlaces de navegación, foco en
main, PageDown/PageUp con final observado, un control visible del contenido por
ruta y Escape del menú con retorno al disparador. No se ejecutan agentes ni se
activan acciones de planificación/desarrollo para probar estos controles.

Se conservan48capturas completas1280×937 mediante `Page.captureScreenshot` sin
clip; las dimensiones se contrastan con el viewport físico de CDP. La captura
normal de Playwright, que recortaba con zoom, no se usa para este gate.
[Antes al400%](control-clipping-red/400-overview.png),
[después al400%](scrollend-final/400-overview.png),
[lectura al200%](scrollend-final/200-overview.png),
[recibo final](scrollend-final/zoom-evidence.json).

El backend se ejecuta desde la instalación no editable de Python3.12. La web es
el build actual del worktree; su índice y todos los assets se identifican por
SHA256 en los resultados. Los hosts tienen cuenta sintética, datos nuevos y API
y SQLite reales. Sus recibos registran integridadok y cero
runs/dispatches/native_starts antes y después del cierre. Se observaron las
salidas de los supervisores originales,143 tras SIGTERM; los perfiles finales
de Chromium terminaron en estadoNormal, contrastado por el revisor.

## Fallos conservados y revisión

[Historial de ejecuciones](runs.json) conserva los intentos fallidos y el pase
anterior que todavía no comprobaba el recorte de controles. No se cuentan como
aceptación final. La primera excepción también expuso un fallo del recolector:
intentaba leer una página del navegador de seed ya cerrado. Ahora comprueba que
la página siga abierta antes de capturar el error.

La reproducción dirigida usa el mismo host sintético retenido y el mismo CSS:
con la espera temprana, `planning-new` termina en top−16,207px; esperando
scrollend, top154,793px y bottom198,793px dentro de234px. La base no cambia.
[Recibo](scroll-probe/evidence.json), [host](scroll-probe/result.json),
[programa](zoom-scroll-probe.mjs). Esto respalda la carrera de instrumentación;
no atribuye al CSS todos los fallos intermedios.

**167contratos y80pruebas UI pasan**, sin omisiones; build aprobado con el aviso
previo de chunks grandes. [Log](native-zoom-frontend-tests.log),
[build](native-zoom-build.log). El recorrido sin zoom pasa24estados a1440/320px,
sin Axe ni reflujo: [recibo](baseline/navigation-evidence.json). No es una nueva
suite global de backend ni un nuevo paquete final. Lint dirigido de App aprobado;
el diff fuera de logs no tiene avisos de espacios. Se conservan dos diagnósticos
de formato de logs crudos en [el recibo](whitespace-check.log), sin reescribirlos.

[Revisión independiente](independent-review.md) sólo de lectura. Primer host
sintético creado22:06:02,730UTC; último recibo baseline22:17:24,488UTC:
**11min21,758s entre esos archivos observados**. Preparación anterior y
documentación/checkpoint posteriores quedan fuera de ese intervalo.

## Pendientes preservados

Lector de pantalla real; U08 humano; elección Ken/ONNX; documentación relevante
frontend/C; detalles diferidos y aceptación integrada de paquete, suite global
y revisión final. Se mantienen42/43escenarios y12/12páginas por alcance. El ajuste
parcial de cabecera no cierra todos los puntos de densidad deDD041.
