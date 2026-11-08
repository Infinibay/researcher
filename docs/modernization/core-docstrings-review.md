# Documentación del núcleo de ejecución para Ken

Se añadieron **88docstrings en inglés**, revisados contra las implementaciones,
en cuatro módulos que definen coordinación, contratos, persistencia y propiedad
de procesos. No se completaron automáticamente por el nombre del método ni se
declara terminada toda la documentación del proyecto.

| Módulo | Definiciones documentadas | Contratos que aclara |
| --- | ---: | --- |
| [service.py](../../backend/runtime/service.py) | 11 | Propietario local, retirada inmediata de permisos, interrupción, espera y recuperación compartida de un intento. |
| [contracts.py](../../backend/runtime/contracts.py) | 19 | Solicitud frente a lease, contexto, identidad física, límites de comandos y resultado nativo frente a aceptación. |
| [sqlite_runs.py](../../backend/runtime/sqlite_runs.py) | 41 | Transacciones, recibos originales, correcciones, concesiones, observaciones y comandos sin repetición. |
| [peer_registry.py](../../backend/runtime/peer_registry.py) | 17 | Registro antes de liberar procesos, origen de la base, cierre físico e identidades retenidas. |
| **Total** | **88** | Propósito, efectos y límites útiles para localizar y usar código. |

Las88piezas eran definiciones sin docstring en el AST. Los módulos ya tenían
descripción. En estos cuatro archivos no quedan clases/funciones/métodos sin
docstring, incluidas las funciones anidadas. Eso no certifica el contenido de
todos los docstrings previos ni la documentación de otros módulos.

## Distinciones útiles al buscar

- `RuntimeService.stop` documenta la retirada de autoridad antes de SQL; solicitar
  interrupción no se presenta como prueba de cierre físico.
- `SQLiteRunStore._original_attempt` identifica quién produjo una observación
  histórica sin restaurar permiso para mutar el contexto actual.
- `SQLiteRunStore.reserve_job` separa recuperar un recibo de autorizar el primer
  despacho; `finish_job` conserva prefijos de salida y resultados desconocidos.
- `WorkspaceBinding` separa validar valores suministrados de verificar el
  directorio real. `AttemptLease` sigue requiriendo validación en el almacén.
- `AttemptPeers.closed` contempla el conjunto legítimamente vacío de publicación
  sin inferencia. `aclose` propaga errores y no promete que todos los cierres
  hayan terminado después de una excepción.

Se usa el criterio de Clean Code de documentar contratos y restricciones, con
responsabilidades concretas. En este bloque no se renombra, divide ni refactoriza
código. El requisito del propietario es que Ken pueda usar esa información;
no se ha medido una mejora de ranking ni reindexado el MCP conectado al checkout
original. El código autoritativo sigue en el worktree de modernización.

## Verificación y límites

[Resultados y hashes](core-docstrings-results.json),
[equivalencia de AST](core-docstrings-evidence/ast-equivalence.json),
[textos revisados por identidad](core-docstrings-evidence/authored-docstrings.json).

- El AST de cada módulo es idéntico al de416abed al quitar únicamente docstrings.
  No cambian firmas, decoradores, valores, sentencias ni expresiones ejecutables.
  Los atributos `__doc__` y los números de línea sí cambian intencionadamente.
- Se compararon exactamente las siete instrucciones del selector y las
  descripciones, esquemas y anotaciones de48herramientas de negocio: sin cambios.
  No es una auditoría de todo posible consumidor de introspección externo.
- **51pruebas fuente pasan**, sin omisiones: `test_runtime_service.py`,
  `test_peer_ownership.py` y `test_run_recovery.py`. Incluyen procesos controlados;
  no hubo generaciones por suscripción ni repetición del ensayo de explicación.
- El inventario sigue en85candidatos/322archivos: tres revisiones se invalidaron
  por el hash del consumidor SQLite. Se revisó que sus fuentes no cambiaron,
  que el único consumidor cambiado sólo añade docstrings y que las políticas
  emitidas permanecen iguales. Se revalidaron esas tres, conservando82vigentes.
- No se construye otro wheel por este bloque documental; el paquete del árbol
  final sigue pendiente. El recibo anterior de699archivos corresponde a su corte
  histórico y no acredita los nuevos bytes de documentación.

La auditoría de presencia baja de621a**533definiciones restantes** en el backend
propio sin tests. No todas tienen igual relevancia. Siguen prioritarios autoridad,
RPC nativo, comandos y fronteras de proceso; revisar contratos y contenido en vez
de completar frases genéricas. También siguen abiertos U08/entrega humana,
Ken/ONNX, accesibilidad integral y revisión/suite global finales.

Inicio del bloque actual18:23:48UTC. El tablero registra el corte de verificación;
el tiempo de51pruebas fue38,760s y no representa lectura, escritura ni documentación.
