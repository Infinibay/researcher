# Proyectos: regresiones corregidas y aceptación abierta

Bloque desde `107240c`, **2026-11-07 23:58:35–2026-11-08 00:37:32 UTC**:
**38 min 57 s hasta verificar**, sin documentación/checkpoint posteriores.
Se corrigieron cuatro problemas funcionales; la página todavía no se acepta
integralmente. [Resultados](projects-page-results.json).

## Correcciones de producto

1. Una creación cuyo formulario ya se abandonó actualiza el registro y su recibo
   sin seleccionar el proyecto nuevo sobre la elección actual.
2. La respuesta tardía de una planificación no redirige otra visita del mismo
   proyecto después de A→B→A. Se invalida el contexto visual retirado, además de
   comprobar el ID del proyecto.
3. La observación actualiza la existencia de una planificación pendiente. Un
   botón de recuperación obsoleto no puede crear una solicitud nueva cuando
   otro contexto ya recibió el recibo original.
4. Las solicitudes nuevas del cliente piden tareas, criterios y explicación en
   español, idioma de esta interfaz. Las solicitudes antiguas con `prompt:null`
   se recuperan intactas; no se reescribe un intento para cambiar su idioma.

Las dos primeras pruebas fallaron antes del arreglo; la sincronización del
recibo y la petición de idioma también tuvieron reproducciones fallidas.
Ahora pasan **3 pruebas DOM y 11 contratos** de creación, fuente, planificación,
aceptación, cierre y recuperación. TypeScript/Vite compilan. La interfaz mantiene
la dirección visual elegida; los detalles de densidad/copy se conservan en DD123.

## Recorrido real y límites

Se probó creación con respuesta realmente confirmada por el servidor y retenida
en transporte; cambiar de proyecto conserva la elección actual al liberarla.
Edición y registro de carpeta usan HTTP/SQLite reales y conservan el contenido
del archivo original. La automatización necesitó corregir contexto de Axe,
selector de textarea y retiro prematuro de una ruta interceptada. Los primeros
dos ensayos no llegaron a admitir trabajo nativo; el siguiente dejó un intento
cancelado antes de enviar inferencia, sin representar un clic de Stop.

Se continuó sobre la instalación original. Su proyecto conservaba una reserva
de preparación de una solicitud/350000 tokens: la siguiente solicitud fue
rechazada antes de inferir. Es configuración del ensayo, no una cuota de la
suscripción ni una preferencia atribuida al usuario. La reserva no se borró ni
se elevaron sus límites. El runner combinado ahora comprueba previamente que
pueda reservar ambas solicitudes; con esos recursos rechaza sin crear un host.

En otro proyecto de prueba, con su propio presupuesto inicial, hubo **un turno
real** con suscripción, Ken y catálogo 9. Produjo un plan de dos tareas; la
revisión del propietario desde la UI creó tareas pendientes sin ejecutarlas.
Recarga, protección del proyecto con historia, diálogo y eliminación del proyecto
sin historia y aislamiento de otro proyecto pasaron. Consumo observado 139193,
despacho settled; esto no es una cifra facturada.

La propuesta salió en inglés. Esa evidencia originó la corrección del cuarto
punto; el plan original queda guardado. La comprobación posterior registró la
solicitud española en el servidor pero terminó con **AuthorityBusy antes de
inferir**. No se obtuvo una respuesta española que pueda declararse verificada.

El recorrido de lectura separado pasó escritorio, móvil, retorno/foco, corte
controlado de un GET y recuperación conservando el plan aceptado. No se fabricó
una respuesta de negocio. Las capturas muestran partes visibles de paneles con
desplazamiento, no todo su contenido simultáneamente. El renderer no cambió al
añadir después la petición de idioma.

Todos los servidores originales están cerrados, todos los peers retirados y
cero grants activos. La base pasa integridad/FK. Se preservan cuatro registros
de ejecución: cancelado, rechazado por presupuesto, aceptado y fallo de
preparación. Sólo uno llegó a un turno del modelo.

## Pruebas del backend y trabajo principal pendiente

La selección instalada pasa **40 casos** y falla en un test cuyo actor controlado
ahora llama a `researcher_plan_deliver`, mientras el test espera el antiguo
`researcher_plan_propose`. No es una suite verde. El otro parámetro del mismo
caso no se ejecutó tras `maxfail`; DD124 conserva ambos alcances. La selección
incluye Stop del trabajador original con kernel/broker y generación controlada;
ese cierre físico no se atribuye al navegador del ensayo fallido.

El log original distingue **AuthorityConflict** en la primera preparación y
**AuthorityBusy** en la comprobación española. El journal puede declarar Busy
por contención de flock o SQLite. Esto es evidencia del tipo de fallo, no de su
llamador ni de la causa exacta. Investigar la concurrencia durante preparación
antes de intentar otra inferencia; mantener la exclusión, la validación de
identidades, los recibos y las reservas inciertas.

Además, `runtime_failed` habla de cierre sin confirmar aunque el evento previo
acredita peers retirados. La comunicación debe distinguir fallo de preparación
y cierre desconocido. Ambos son trabajo funcional principal, no pulido visual.

Siguen **0/12 páginas aceptadas** y 41/43 escenarios comprobados. U08, C10 y la
evaluación científica conservan su alcance pendiente. No se solicita otra
evaluación humana sobre un resultado que todavía no está listo.


## Cierre acotado de aceptación — 2026-11-08

La [recuperación instalada actual](projects-original-recovery-review.md) cubre el
intento fallido original, recarga, retorno y presupuesto sin admisión. Se conserva
el fallo del verificador por consulta anterior al emparejamiento y su continuación
sobre el mismo host. El gate revisado está explícito en el plan correctivo; no se
impone producir una corrección de carrera que no fue demostrada. Proyectos queda
aceptado técnica y visualmente por alcance, manteniendo el incidente desconocido
y U08 separados. El mensaje histórico no se reemplaza por wording actual.
