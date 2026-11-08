# Preparación nativa: cierre comprobado y diagnóstico seguro

Base: `ee39fd2`. La contención observada en Proyectos sigue abierta. Este corte
corrige la explicación del fallo y permite localizar una futura excepción sin
exponer mensajes privados; **no corrige ni declara reproducida la contención**.

## Evidencia y límites

Se conservaron el intento español fallido, el plan inglés aceptado y las reservas
originales en `.researcher/evaluations/projects-acceptance-label-20261107`.
El journal del proyecto5 registra la preparación Ken cerrada, Ken MCP admitido,
reserva nativa y retirada del dominio; no contiene publicación ni gate nativos.
La retirada no registró OOM ni rechazo de procesos. Esto acota la frontera, pero
no identifica la excepción inicial ni demuestra una carrera entre trabajadores.
El `AuthorityConflict` del primer intento coincidió con la terminación del
harness; no se atribuye automáticamente a la misma causa que `AuthorityBusy`.

Cuatro preparaciones independientes en instalaciones desechables utilizaron los
binarios Codex/Ken y la cuenta configurada, con generación interceptada y
prohibida antes de enviar un turno. Tres usaron el event loop de pytest y el
artefacto anterior; una usó `uvloop` y la rueda corregida. Todas llegaron a la
guardia, enviaron **cero turnos** y cerraron todos los peers. Son comprobaciones
de preparación, no respuestas generadas, evaluación de Ken ni prueba de que el
fallo intermitente desapareció. El estado `failed` posterior es deliberado: la
guardia termina el ensayo. La reserva SQL de despacho puede existir antes de esa
guardia; el producto conserva prudentemente `inference_started: null` en ese caso.

## Cambio funcional

El coordinador guardaba `runtime_failed` con un único texto de cierre desconocido,
incluso después de comprobar cierre nativo, empresarial y de herramientas.
Ahora conserva por separado `closure_confirmed` y la observación de inferencia:

| Observación | Explicación |
| --- | --- |
| Preparación falla, ninguna inferencia admitida, cierre comprobado | No se completó la preparación; no se inició inferencia; procesos cerrados. |
| Despacho reservado, sin comienzo observado, cierre comprobado | Ejecución fallida y procesos cerrados; inicio de inferencia desconocido. |
| Inferencia observada, cierre comprobado | Ejecución fallida y procesos cerrados; conserva resultados/recibos. |
| Cierre no comprobado | Conserva la explicación de cierre pendiente. |

No habilita reintentos, no reembolsa reservas y no interpreta un cierre local
como uso o facturación conocidos. El historial previo conserva su texto original.

El log del operador añade hasta cuatro ubicaciones internas por excepción y
hasta cuatro causas. Guarda módulo, función, línea y tipo; excluye mensajes,
rutas de archivos, líneas de fuente y variables locales. La interfaz sigue
recibiendo una explicación española y una acción concreta, sin ese diagnóstico.

Las cuatro pruebas nuevas o reforzadas se observaron fallar antes del cambio y
pasar después. Una usa un dominio kernel real que falla antes del primer proceso;
las otras separan preparación, despacho incierto e inferencia observada. Se
comprueba también que los mensajes privados de excepción y causa no aparecen en
el log ni en la respuesta. La selección instalada y las docstrings están en los
recibos enlazados abajo; no constituyen una nueva suite global verde.

## Incidencia del empaquetado

El primer build directo reutilizó `build/` antiguo: produjo982 fuentes,306 de
módulos ya retirados. Se instaló en el entorno de validación, pero la guardia de
contenido rechazó la rueda antes de ejecutar pruebas. No se lanzó ningún servidor
ni modelo con ese artefacto. Se conserva la incidencia; no se cuenta como producto
validado. Se reconstruyó sdist + wheel con `uv build` sin `--wheel`, conforme a
[la instalación nativa](../architecture/native-python-installation.md), se
comprobaron las676 fuentes actuales y se sustituyó la instalación. El resto de
comprobaciones usa exclusivamente esa rueda limpia.

## Siguiente trabajo principal

La preparación permanece abierta. En una reproducción acotada, leer ahora el
sitio/causa del fallo del log real `host/logs/infinibay.log`; no inferirlo sólo de
la clase `AuthorityBusy`. Si se necesita otra preparación diagnóstica, prohibir
inferencia y conservar el intento como observación independiente. Corregir sólo
la operación demostrada y protegerla con reproducción sin pago. No ignorar
flock/CAS ni devolver reservas por suposición.

Después: verificar un plan español nuevo con auditoría real de llamadas y
resultados Ken; cerrar Proyectos; continuar las otras once páginas. U08, C10,
evaluaciones, dependencias/distribución, detalles y cierre global siguen abiertos.

[Resultados](native-preparation-results.json),
[paquete instalado](native-preparation-packaging.json),
[docstrings](native-preparation-docstrings.json),
[plan vigente](../superpowers/plans/2026-11-08-native-preparation-contention.md).


## Observación posterior de HTTP, 2026-11-08

Una quinta preparación se observó desde HTTP real con uvloop, guardián de servicio
y límites originales. Llegó a la guardia de generación, envió0turnos y cerró sus
peers; no reprodujo la contención. [Recibo independiente](native-preparation-http-results.json).
La causa permanece abierta. Se continúa con capacidades independientes de la web,
sin reclasificar la fiabilidad nativa como detalle ni repetir ensayos equivalentes.
