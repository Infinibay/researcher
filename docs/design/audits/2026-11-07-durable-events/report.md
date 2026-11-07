# Reconexión real y límite del historial

Servidor instalado fuera del checkout y frontend compilado, con HTTP/WebSocket
reales sobre loopback. Datos SQLite sintéticos; cero ejecuciones admitidas y cero
despachos de inferencia. Se cierra sólo el socket del navegador de prueba para
provocar una reconexión; no se simula un reboot ni pérdida de energía.

Se recuperan488 eventos en varias páginas y con fechas iguales:237 iniciales y
251 guardados durante la desconexión. La siguiente conexión usa el último ID
aplicado. No faltan ni se duplican esos eventos. Después, un borrado controlado
produce `reset_required`, advertencia visible y lectura de los eventos posteriores.
Cambiar de proyecto elimina las observaciones del anterior.

Tres estados de navegador,1440/390px; sin errores JavaScript ni desbordamiento
horizontal. Se inspeccionaron las capturas de escritorio y advertencia móvil.
[Evidencia](evidence.json), [operación/cierre](operation.json),
[cierre del servidor](server-exit.json).

**La interfaz todavía no está aceptada.** Axe detectó contraste en las tres
capturas y una región desplazable sin foco en dos. Las primeras capturas incluyen
la animación de entrada; revisar el contraste con animaciones estabilizadas en
la etapa de aceptación. El panel conserva estilos anteriores y necesita integrarse
al rediseño completo.

El primer ensayo también mostró que el panel abierto tapa el desplegable del
selector en móvil. Se conserva el [fallo](evidence-before-navigation-workaround.json).
El ensayo final cierra Actividad, cambia de proyecto y vuelve a abrirla, sin
clic forzado. DD079 conserva la corrección de esa superposición y los hallazgos
de accesibilidad para la aceptación de interfaz; no se ocultan como fallos del
fixture. Las12 páginas siguen pendientes de aceptación integral.
