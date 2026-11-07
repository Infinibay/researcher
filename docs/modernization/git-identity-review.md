# Identidad y efectos Git: D06, D07 y D09

Base `564b388`. Bloque **2026-11-07 20:43:33–21:22:33 UTC**:
**39 min hasta verificar**, excluyendo documentación/checkpoint posteriores.
**D06, D07 y D09 comprobados; D08 sigue abierto.**

## Cambios y escenarios

| Escenario | Implementación y evidencia |
| --- | --- |
| D06: nombres iguales entre proyectos | La migración67 sustituye la unicidad global de nombres de ramas por identidad del repositorio. Conserva filas, IDs y el máximo histórico de AUTOINCREMENT. Ramas y revisiones guardan `repo_id`; el cierre de una revisión actualiza sólo su rama y guarda el evento en la misma transacción. Un fallo del evento revierte ambas anotaciones. El caso original reproducía la modificación de una rama de otro proyecto. |
| D06: renombrar y reutilizar nombres | La navegación de PRs, selección de código anterior y acceso a comentarios usan el ID registrado. El explorador web incluye ese ID en las consultas y en sus claves de caché; filtra revisiones por proyecto e ID. La API captura registro, ruta y remoto juntos. Un ID ajeno o ausente no se sustituye por otro con igual nombre. Las pruebas leen árboles, ramas y contenido de repositorios Git reales después de reutilizar el nombre. La identidad de wiki conserva sus comprobaciones propias. |
| D07: destino exacto y respuesta perdida | El camino nativo verifica fuente, base, candidato, referencia de destino y recibo de aceptación. Publica una referencia nueva mediante precondiciones exactas; conserva checkout y archivos originales. La recuperación observa la operación original, sin volver a aplicar un efecto incierto. Se comprueba además que una rama homónima de otro clon no cambia. Se retira el merge antiguo de TUI que ignoraba el destino recibido. |
| D09: altas parciales | Se conservan y vuelven a comprobar las operaciones explícitas de crear, adoptar, clonar, reparar y liberar una reserva. Una respuesta remota perdida se reconcilia contra la intención original; no se repite un POST para adivinar el resultado ni se cambia origin o fuerza una historia preexistente. La reparación preserva modificaciones del propietario y rechaza precondiciones cambiadas. |
| D08: conservación, todavía incompleto | Los intentos nativos ya conservan sus copias privadas. Se cierran las antiguas entradas de `WorktreeManager` y `LocalWorktree`, incluidas recreación con reset, borrado forzado y fallback recursivo. Once casos sobre worktrees reales con cambios tracked/untracked verifican rechazo antes de ejecutar o modificar DB. Falta la capacidad explícita de cuarentena, retención, borrado recuperable y su interfaz. Conservar todo indefinidamente no equivale a implementar retención. |

La asociación migrada usa el proyecto y nombre que ya estaban registrados: no
demuestra por sí sola la identidad física de un repositorio histórico. Una fila
sin asociación queda sin `repo_id`; registrar después un homónimo no la adopta.
Ni esa asociación ni un estado antiguo autorizan ejecución o publicación nativas.
La captura de código anterior exige selección explícita y verificaciones actuales.

La migración inversa sólo se admite sin historia de ramas/revisiones y sin un
esquema posterior. Una instalación utilizada requiere reparación hacia adelante
o restauración, conservando su información; no se descartan asociaciones para
hacer que el rollback parezca exitoso.

## Verificación y fallos conservados

- Regresión original de cierre entre proyectos: **1 fallo reproducido** antes de
  corregir. Selección posterior inicial: **42 pasan**. Migraciones y publicación:
  **59 pasan**; incluye interrupciones de todas las versiones soportadas18–67.
- Retirada de worktrees antiguos: **11 fallan antes y 11 pasan después**. Se
  reemplazan expresamente las expectativas de ejecutar ese mecanismo retirado
  por la preservación de archivos y metadatos; no se oculta el cambio de contrato.
- Paquete inicial instalado, fuera del checkout: **363 casos, 358 pasan y 5
  fallan**, sin omisiones. Los cinco recorridos de desarrollo carecían de la
  elección explícita de política de comprobaciones añadida anteriormente.
  Se conserva el [recibo inicial](git-identity-packaging.json).
- Los comandos de comprobación del generador controlado no acreditan un número
  de pruebas ejecutadas. El recorrido debe expresar la política correspondiente
  y reconocer ese límite; no se relaja el backend ni se afirma una suite inexistente.
  Una corrida fuente intermedia conservó21 casos correctos y5 fallos: elegir
  `require_tests` aún bloqueaba correctamente esos comandos. La prueba final
  comprueba ambos bloqueos y la posterior elección explícita `allow_missing`,
  con reconocimiento del límite y revisión de política en el recibo de aceptación.
- Explorador web: **2 DOM y 6 contratos pasan**, junto con la compilación. No es
  aceptación visual completa de Repositorios ni de las otras once páginas.
- El [inventario de prompts](../prompts/inventory.json) conserva85 candidatos
  revisados sobre 308 fuentes. El literal OpenAPI de `BranchCreate` no cambió;
  se revisó su consumidor después de las modificaciones de identidad. Esto es
  revisión estática de metadatos, no evaluación de eficacia de modelos.

El recorrido fuente corregido pasa; después, el [paquete final instalado](git-identity-final-packaging.json)
completa **409 casos correctos, sin fallos ni omisiones, en 471,036 s**. Coinciden
664 fuentes Python/SQL entre checkout, wheel e instalación,353 de producto;
los329módulos backend observados se importaron de la instalación no editable,
fuera del checkout. La selección final incluye los recorridos que habían fallado,
la retirada de worktrees, la política de comprobaciones y todas las familias del
ensayo instalado inicial. Las selecciones se solapan y no se suman como casos distintos.

[64 definiciones Python nuevas o cambiadas](git-identity-docstrings.json) tienen
docstrings; los helpers frontend nuevos conservan JSDoc. [Resultados y duración](git-identity-results.json).
No se atribuye esa cobertura a todas las definiciones históricas del proyecto.

## Límites y siguiente bloque

Git, kernel/cgroups, almacenamiento y los transportes TLS de las pruebas son
reales. La inferencia y el servidor REST Forgejo son controlados, con identidades
sintéticas; no se ejecutan turnos de modelos ni se escribe en cuentas externas.
No se declara una suite global verde ni migración de datos históricos del usuario.

Siguiente capacidad principal: **D08, retención explícita del trabajo**. Debe
comprobar cierre físico, consumidores y revisiones/aceptaciones dependientes;
inventariar cambios tracked, untracked e ignorados; conservar una recuperación
verificable antes de borrar; y registrar intención/resultado sin declarar éxito
ante un error. No mover silenciosamente rutas referenciadas por recibos existentes.
La selección actual, un nombre conocido o un resultado antiguo no son evidencia
suficiente para heredar autorización sobre archivos cuya identidad cambió.
[Plan del siguiente bloque](../superpowers/plans/2026-11-07-workspace-retention.md).

Los detalles secundarios permanecen al final, después de todas las capacidades
principales. El tablero y el chat publican la lista y los tiempos reales al cambiar
de bloque; esta regla persiste después de compactar.
