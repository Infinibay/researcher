# D08 — conservación, cuarentena y retención de copias

Preparación documental durante la validación final de D06/D07/D09. La
implementación de este bloque todavía no comenzó; registrar su inicio real
al iniciarla y publicar la transición con la lista actualizada.

## Contrato

Hoy las copias privadas se conservan indefinidamente. El esquema37 contempla
`quarantined`, pero no existe una política completa ni un recorrido de recuperación
y borrado. Las antiguas operaciones de worktree ya rechazan sus efectos peligrosos.

El propietario necesita distinguir «trabajo conservado», «copia en cuarentena»,
«archivo de recuperación verificado», «borrado pendiente» y «borrado confirmado».
Una etiqueta de tarea terminada no demuestra cierre de procesos ni autoriza
destruir sus archivos. Todo efecto tendrá identidad original, precondiciones,
recibo durable y recuperación explícita. Primero este recorrido funcional completo;
la presentación secundaria se anotará para el final.

## Hallazgos comprobados y fronteras

- `development_state.py` registra la asignación antes del filesystem. Sus
  identidades de origen y copia preparada son inmutables; `read_view` sólo admite
  `ready`. No se debe mover un directorio y modificar esos recibos para ocultarlo.
- `candidate_state.py` ubica el candidato en `allocation/candidate`, dentro de
  la misma asignación del intento. Borrar la asignación entera también destruye
  bytes usados por revisiones y publicación. Hay que identificar dependencias
  activas y explicar qué disponibilidad se perderá, conservando historia y archivo.
- `file_imports.py` admite copias privadas como datos explícitamente seleccionados;
  no prueba cierre físico de escritores. Debe coordinarse con la retención y no
  leer una copia a mitad de borrado ni conceder autoridad al recuperarla.
- `publication_closure.py::close_original_attempt` verifica journal y peers, pero
  exige que el intento sea el actual. No sirve sin cambios como autorización para
  borrar cualquier intento histórico. Reutilizar las pruebas de origen/cierre,
  conservando esa diferencia; desconocido y restaurado no equivalen a cerrado.
- `snapshot_files.py` ya inventaría archivos, directorios y enlaces sin seguirlos,
  limita recursos y comprueba identidad durante copias. Revisar su contrato antes
  de duplicarlo. `installation_backup.py` conserva las fuentes y datos de control;
  el nuevo archivo/estado de retención debe entrar también en backup y restore.
- Ken devuelve «file not indexed» para la nueva arquitectura del worktree; los
  hallazgos anteriores se verificaron leyendo los archivos del worktree administrado.
  No se infiere un grafo completo de consumidores de ese resultado vacío.

## Implementación principal

- [ ] Registrar el alcance original por proyecto, intento, asignación e identidad
  física; política/versionado de retención e intenciones idempotentes. Leer no
  inicia limpieza. Los registros históricos ambiguos se conservan y se explican.
- [ ] Conectar cuarentena lógica que conserve las rutas originales. Bloquear
  nuevas admisiones dependientes bajo la misma exclusión que decide cuarentena;
  comprobar cierre real y referencias activas antes de autorizar efectos. No
  retirar a ciegas otro dueño ni deducir cierre de una fila ausente.
- [ ] Inventariar cambios tracked, untracked e ignorados, incluyendo enlaces y
  contenido no publicable. Crear y verificar archivo privado de recuperación
  mediante presupuesto y comprobaciones de identidad. Disco lleno o cambios
  concurrentes conservan original y operación incompleta.
- [ ] Aplicar retención antes del borrado explícito. Revalidar alcance y archivo;
  registrar intención antes del efecto, borrar sólo entradas originales verificadas
  sin seguir enlaces y no declarar éxito hasta confirmar la ausencia duradera.
  Un cambio de identidad exige otra decisión; no hereda el permiso anterior.
- [ ] Recuperar operaciones interrumpidas sin repetir decisiones sobre archivos
  nuevos. Restaurar contenido como una copia nueva, con comprobación de huellas;
  no recrear concesiones, inodos ni aceptaciones antiguas como si siguieran vigentes.
- [ ] Exponer inventario, motivo de bloqueo, plazo, espacio y acciones en la web,
  con ejemplos breves: «esta copia contiene cambios sin publicar; el archivo permite
  recuperarlos, pero restaurar los archivos no vuelve a aceptar ni publicar código».
- [ ] Integrar historial, backup/restore y migración inversa que rechace historia
  utilizada. Docstrings y documentación de límites para búsqueda con Ken.

## Validación que define la entrega

Probar el recorrido completo en directorios reales con cambios útiles y archivos
ignorados; otro proyecto con igual nombre permanece intacto. Incluir escritor o
consumidor vivo, enlaces/ruta reemplazada, deadline de retención, fallo de copia,
fallo de borrado, crash entre archivo/DB/borrado, reintento tras respuesta perdida
y recuperación a destino nuevo. Verificar que archivos nuevos nunca heredan
un borrado anterior y que ninguna recuperación publica o ejecuta código.

La prueba de cierre físico debe usar el journal y dominio reales; los helpers
de almacenamiento con testigos sintéticos no bastan para ese límite. Validar
la UI mediante decisiones y recibos originales, y el paquete instalado fuera
del checkout. Mantener por separado cualquier fallo y los límites de cobertura.

Preguntas de diseño todavía a resolver durante el contraste: política inicial
de retención, conservación de candidatos aceptados, alcance de worktrees antiguos
y copias restauradas sin testigos locales. No presentarlas como decisiones ya
implementadas ni convertirlas en permisos implícitos para eliminar datos.
