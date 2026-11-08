# Documentación de autoridad, RPC y comandos

Se añadieron **95docstrings en inglés** en cuatro módulos del motor. Junto al
[bloque anterior](core-docstrings-review.md), son183definiciones documentadas en
ocho módulos. No se declara completa la documentación del proyecto.

| Módulo | Docstrings añadidos | Contrato documentado |
| --- | ---: | --- |
| [authority_journal.py](../../backend/runtime/authority_journal.py) | 30 | Secuencia/hash, intención original, testigo durable, recuperación de PREPARE y recibos sin repetir efectos. |
| [codex_rpc.py](../../backend/runtime/codex_rpc.py) | 29 | Correlación de respuestas, barreras de mensajes, controles privados, límites y cierre del transporte. |
| [command_jobs.py](../../backend/runtime/command_jobs.py) | 23 | Reserva previa al despacho, salida acotada, cancelación compartida y retiro del peer original. |
| [execution_domain.py](../../backend/runtime/execution_domain.py) | 13 | Identidad física, nacimiento contenido, observación del hijo y retiro del dominio como hechos separados. |

Se revisó cada texto contra el código. La inserción usa un mapa escrito por
identidad, sin generar frases a partir del nombre. Los getters y setters de
propiedades conservan identidades de auditoría distintas; ambos reciben
documentación. Los cuatro módulos quedan sin clases/funciones/métodos faltantes
en la auditoría sintáctica, pero no se revisa íntegramente todo docstring previo.

## Distinciones que preserva la documentación

- `WitnessedAuthorityJournal.load` puede completar recuperación de almacenamiento:
  no es una operación estrictamente de sólo lectura ni un permiso para lanzar
  procesos. `commit` recupera el recibo de la intención original, sin repetir actores.
- `RpcReply.preceding_messages` permite contabilizar eventos anteriores a una
  respuesta. Una notificación escrita no demuestra recepción o efecto completado.
  Los controles privados permanecen separados de la cola pública.
- `OwnedCommandExecutor.start` reserva antes de despachar y no vuelve a ejecutar
  un comando incierto de otra conexión. La cancelación puede repetir controles
  de terminación dentro del margen, nunca el comando de negocio.
- `ContainedChild.wait` observa al hijo directo. Cerrar streams/pidfd o los
  handles del dominio no equivale a retirar el subárbol completo. `_kill` tampoco
  sustituye la comprobación posterior de vacío y retirada.
- El adaptador stdio conserva su condición de compatibilidad: no se documenta
  como si ofreciera la prueba de contención del broker. Su entorno `None` conserva
  la semántica de herencia del API de subprocess; la propiedad no filtra credenciales.

## Verificación y alcance

[Resultados](authority-transport-docstrings-results.json),
[mapa de textos](authority-transport-docstrings-evidence/authored-docstrings.json),
[equivalencia de AST](authority-transport-docstrings-evidence/ast-equivalence.json).

- AST ejecutable idéntico a30a27a9al retirar sólo docstrings; firmas, decoradores,
  constantes y sentencias no cambian. `__doc__` y números de línea sí cambian.
- Siete políticas nativas y las descripciones/esquemas/anotaciones de48herramientas
  de negocio permanecen exactamente iguales. No se certifica todo consumidor
  posible de introspección externo ni una mejora medida de ranking Ken.
- **83pruebas fuente pasan**, sin omisiones, en12,500s: journal de autoridad y sus
  fallos de proceso, RPC, ejecutor de comandos y dominios de ejecución. Usan
  procesos controlados; cero turnos de modelo nuevos.
- Inventario85candidatos/322archivos: ninguna revisión de candidato o consumidor
  quedó desactualizada. Se actualizan sólo los cuatro hashes del árbol; no se
  renueva una decisión de revisión sin un delta.
- No nuevo wheel ni suite global. Los paquetes instalados anteriores conservan
  su propio corte y no contienen estos nuevos bytes de documentación.

La presencia restante baja de533a**438definiciones** fuera del alcance. Es un
inventario para revisar relevancia y contratos, no438tareas equivalentes que
deban completarse con texto genérico. Siguen broker/perfiles de aislamiento,
suscripción, mediación y otras fronteras relevantes, además de JSDoc donde aplique.
U08/entrega humana, Ken/ONNX, accesibilidad y cierre integrado permanecen abiertos.

Inicio18:36:07UTC, corte de comprobación18:42:00UTC:5min53s. La documentación
del informe y el checkpoint son posteriores;12,500s de pruebas no es el total.
