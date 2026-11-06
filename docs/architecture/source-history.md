# Historia de preparación entre navegadores

Una sesión owner puede abrir la historia de preparación de un proyecto aunque
ese navegador no conserve el POST original. Repositorios ofrece **Historia de
preparación**; cada entrada abre la operación elegida. Se reutilizan la historia
completa de `ProjectWorkspace` y el GET owner de esa operación, sin nuevos listados
parciales ni búsqueda de la operación «más reciente».

La vista conserva un localizador de lectura independiente de `SourcePacket` y
`SourceRepairPacket`. Seleccionar, cambiar de proyecto o recargar esa vista no
crea ni clona, no vuelve a enviar la preparación y no reemplaza una solicitud
pendiente de ese navegador. Un aviso identifica esa solicitud independiente y
permite volver a ella. Desde una vista histórica no se expone el POST de alta;
Stop, observación y reparación conservan sus propias autorizaciones explícitas.

## Evidencia y alcance seleccionado

`SourceHistoryTarget` congela proyecto, clave, ID original, tipo, nombre, carpeta y
fence conocido del resumen elegido. `readSourceHistory` hace un GET exacto y
`sourcePacketFromHistory` comprueba esos datos antes de reconstruir el request.
Un ID reemplazado, proyecto distinto, elecciones incompatibles o un fence inferior
se rechazan. Un fence superior puede mostrarse como una observación posterior de
la misma operación; no se interpreta como el intento antiguo.

El request se valida y normaliza con el mismo contrato de la preparación. No se
inventa otra clave ni un servidor que falte. El orden de campos JSON no cambia la
identidad de la solicitud ni rompe una reparación guardada anteriormente. El
localizador tiene presupuesto completo de12KiB; los límites existentes del request
y su historia siguen vigentes.

Una lectura puede reutilizar la caché de consultas configurada por la aplicación.
**Consultar operación** fuerza una nueva lectura. Los controles usan exactamente
el ID/fence observado y el servidor rechaza un intento que ya cambió; una respuesta
en caché no confiere autoridad sobre otro intento. Forzar una lectura nueva al
reseleccionar y mostrar su fecha queda registrado para el pulido posterior.

## Controles y respuestas tardías

Stop y reparación ya exigen el ID/fence observado. La observación admite ahora ese
mismo cuerpo opcional: la web siempre lo envía y `SourceService.reconcile` lo
comprueba bajo su lock antes de programar. Un cuerpo con otro ID/fence se rechaza
antes de iniciar actores; campos extra como comandos se rechazan por schema.
Se mantiene la llamada bodyless anterior como compatibilidad; no se usa para los
nuevos controles de la vista histórica.

Las consultas se separan por proyecto, clave, identidad seleccionada y fence
mínimo. Al cambiar de operación, una respuesta tardía actualiza su propia caché.
No escribe el estado de la operación que el usuario está viendo ahora. Las
respuestas de mutaciones se atribuyen a la selección con la que se lanzaron y
sólo invalidan caches del proyecto/operación respondidos. El componente padre se
mantiene keyed por proyecto para evitar reutilizar el estado de otro proyecto.

En móvil, abrir una entrada mueve el foco a su resultado cuando termina de cargar.
La entrada de historia puede abrirse de nuevo aunque el usuario haya colapsado su
lista. Los controles de la fuente detenida permiten observar sus archivos y cierre
antes de autorizar una continuación; esa consulta no sustituye la reparación.

## Verificación y límites

-4pruebas de transporte/persistencia comprueban GET exacto, respuesta posterior,
  rechazo de datos ajenos/reemplazados/anteriores, conservación byte a byte de otra
  solicitud y compatibilidad con la reparación previa tras reordenar JSON.
-16pruebas owner/source/remote pasan desde la wheel instalada, con Git, kernel y
  TLS controlados. Incluyen rechazo del ID/fence de observación y compatibilidad
  de los consumidores anteriores; no sustituyen la batería global del proyecto.
-3contextos de navegador owner comprueban otra solicitud pendiente, navegador sin
  request local, recuperación de controles, recarga sin POST y respuestas GET
  reales retenidas hasta después de cambiar de operación/proyecto.

[Resultados](../modernization/source-history-results.json),
[paquete](../modernization/source-history-packaging.json),
[docstrings](../modernization/source-history-docstrings.json) y
[recorrido web](../design/audits/2026-11-06-source-history/report.md).

No se da por resuelta la identidad tras hard delete/restore (DD030), el abandono/
adopción de reservas, una reparación guardada sin programación, límites ampliados
ni aceptación humana de toda la página. La selección local es una referencia de
lectura; no demuestra por sí sola que un repositorio esté sano o aceptado.
