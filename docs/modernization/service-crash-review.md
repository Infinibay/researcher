# Recuperación tras la caída de un servicio activo

Se corrigió un fallo real: la recuperación cerraba los peers y conservaba la
pregunta, pero dejaba activa la concesión global del intento anterior. Una nueva
instrucción explícita fallaba con `AuthorityConflict` antes de inferir. La versión
corregida recuperó una pregunta tras SIGKILL, permitió responderla y completó la
continuación sin limpieza de emergencia ni repetición del trabajo original.

## Cambio del motor

`RuntimeService` exige ahora el retiro del dominio original al runtime propio,
antes de confirmar la recuperación. Reutiliza la implementación que ya verificaba
las publicaciones: origen de base, proyecto, tarea, intento, fence, dueño anterior,
cierre del dominio y proyección de los recibos. Las validaciones específicas de
publicación se conservan. Si aún existe un trabajador local, se espera su
finalizador; una prueba de cierre fallida mantiene la recuperación incompleta.

La misma comprobación se hace al consultar un recibo antiguo de recuperación.
Así una instalación que ya había guardado un recibo local no omite otra vez el
recurso global. No se reenvía el prompt, no se aceptan propuestas, no se repiten
efectos y no se convierte el consumo desconocido en consumo liquidado.
[Contrato](../architecture/peer-recovery.md).

## Ensayos y límites de la evidencia

| Caso | Qué se observó | Límite conservado |
| --- | --- | --- |
| Captura confirmada y respuesta retenida | Se mató el servicio con el namespace nativo vivo. La fuente, el recibo, la corrección y el input sobrevivieron. La continuación utilizó la fuente existente y explicó21% sin volver a capturar. | El evaluador falló al emparejar el servicio reiniciado; su limpieza retiró la concesión antes de retomar. No se atribuye ese cierre a la API. |
| Pregunta confirmada, antes de su callback; versión anterior | La API recuperó la pregunta y aceptó la respuesta sin inferencia. La continuación falló antes del modelo porque seguía ocupada la concesión global. | Fallo real conservado, no un resultado aprobado. La limpieza posterior se registra aparte. |
| Mismo caso de pregunta, paquete corregido | SIGKILL con actor activo; recuperación HTTP repetible, dominio retirado, pregunta pendiente, respuesta guardada y nueva admisión explícita. Explicación final:7,5minutos=450segundos. | Datos y respuesta humana guionados. No demuestra comprensión humana, otros perfiles ni reinicio de máquina. |

El último caso verifica el pidfd original, todos los peers cerrados, ninguna
concesión activa y ningún dominio residual retirado por el evaluador. Los efectos,
preguntas, correcciones e inputs permanecen idénticos durante la recuperación.
El consumo del intento interrumpido sigue `unknown`; el turno nuevo termina en
`needs_review`, sin aceptación ni publicación.

El fallo del evaluador era suponer un único archivo de emparejamiento: una muerte
abrupta deja el anterior. El helper ahora identifica el archivo creado por el
arranque observado, sin borrar archivos antiguos ni elegir por fecha. Se retomó
la captura original; no se ejecutó de nuevo desde cero. Sólo se repitió el caso
de pregunta después de corregir el defecto del producto.

Hubo6 admisiones y5 despachos reales: uno de los pedidos falló antes de inferir.
Los7 procesos de servicio observados terminaron. Hay3 recibos de uso desconocido
y2 liquidados, con276484 tokens observados en total, incluidos valores parciales.
Eso no representa facturación ni cuota. [Recibos y respuestas](service-crash-live.json).

## Validación

Bloque medido08:03:22–08:25:01UTC: **21min39s**, hasta el corte de validación y registro.

Tres pruebas fallaban por omitir el retiro global, incluidos recibos anteriores.
Pasan59 pruebas de fuente/evaluador y38 desde el wheel fuera del checkout.
Coinciden606 archivos Python/SQL,324 productivos;226 módulos backend proceden de
la instalación. Se comprobaron40 definiciones documentadas. Los6 avisos Ruff van
a DD085, después de todas las capacidades principales.
[Resultados](service-crash-results.json), [paquete](recovery-domain-packaging.json),
[docstrings](service-crash-docstrings.json), [procedimiento](../../evals/runtime/service_crash.md).

No se repitió la suite global ni se modificó el frontend. Continúan abiertos43
escenarios amplios y la aceptación integral de12 páginas. El siguiente bloque
debe cubrir el reinicio de la VM con un proceso activo: el ensayo anterior sólo
tenía un registro preparado. No se reinició la máquina del propietario. También
siguen pendientes pérdida de energía/otros fallos, datos históricos reales,
comunicación humana y científica, revisión de prompts, seguridad/licencias y la
revisión independiente del conjunto.
