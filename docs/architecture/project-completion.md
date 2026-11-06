# Informe y cierre explícito del proyecto

Terminar un turno, aceptar un informe y cerrar un proyecto son decisiones
distintas. `ProjectCompletion` reúne evidencia guardada y permite al propietario
revisar el alcance completo antes de aceptar su cierre. No genera otra narración
con un modelo ni ejecuta Git. La aceptación expresa una decisión humana sobre
esa versión; no demuestra comprensión compartida ni confianza científica.

## Alcance observado

El informe conserva descripción original y actual, entrada original del plan,
manifiesto vigente, entregas actuales y **todas** las tareas del proyecto. No
oculta trabajo ajeno al plan elegido. Cada tarea necesita una aceptación nativa
vigente: los informes conservan contenido, fuentes, citas y límites; el código
conserva identidad del candidato, comprobaciones, revisión y publicación
registrada. Los planes necesitan una aceptación real o la revisión explícita
del grafo que conserva su procedencia histórica.

Una tarea restaurada con etiqueta «done» y sin aceptación bloquea el cierre. Lo
mismo sucede con entregas sin aceptar, contexto obsoleto, objetivos sin tareas,
trabajo pendiente o incierto, peers sin cerrar y grants sin retirar. El host
aporta la observación real de los dueños antiguos registrados; el constructor
no supone su ausencia. Esta comprobación local no acredita por sí sola el
enrolamiento y cierre de cualquier proceso externo del host.

Hay límites explícitos de 256 tareas, 256 epics/milestones y 4 MiB para informe y
snapshot completos. Excederlos produce un error, sin omitir evidencia ni cerrar.
El snapshot conserva las versiones e identidades necesarias para volver a las
fuentes. La expansión de historial antiguo de efectos y presupuestos, los
proyectos con otras formas de adopción histórica y la paridad terminal completa
siguen dentro del trabajo global pendiente.

## Código aceptado y publicación

Por ejemplo, una tarea puede aceptar `valor=200` en una copia mientras el origen
todavía contiene `137`. El informe muestra ese candidato como **sin publicación
confirmada**. Si el propietario decide cerrar en ese estado, reconoce la lista
exacta de intentos sin publicar. No se genera merge, push ni publicación.

Una publicación registrada informa de lo observado entonces. No acredita que
la rama remota conserve hoy el mismo estado ni sustituye su recuperación de
sólo lectura. Las aceptaciones documentales tampoco se presentan como prueba
automática de validez científica.

## Una decisión sobre bytes concretos

`GET /api/projects/{project}/runs/{plan}/project-plan/completion` funciona sin
runtime de inferencia activo. Devuelve informe Markdown, snapshot, hash del
conjunto, impedimentos, candidatos sin publicar y aceptación histórica con su
vigencia actual. Consultarlo no acepta resultados ni modifica estados.

El `POST .../completion/accept` exige sesión owner/CSRF, clave original, hash del
informe, reconocimiento exacto de los candidatos sin publicar y una declaración
del propietario. La transacción existente guarda informe, snapshot, declaración
y recibo en `runtime_commands`, cambia el estado del proyecto y registra el
evento. No añade tablas, migración, controller ni loop. Otros estados de tareas
y epics no se cambian por deducción. CRUD y helper antiguos rechazan el atajo de
poner `status=completed`.

La misma clave y contenido recuperan el recibo anterior sin otro efecto. Cambiar
la intención con esa clave se rechaza. Una decisión nueva exige evidencia actual.
Después de una corrección o tarea nueva, el informe histórico permanece íntegro
y la consulta deja de presentarlo como cierre vigente. Un estado guardado de
proyecto tampoco se toma como prueba renovada de cumplimiento.

## Interfaz y evidencia

Tareas ofrece informe, fuentes completas, impedimentos con enlaces a tareas,
declaración del propietario y reconocimiento del código sin publicar. Guarda el
paquete antes de enviarlo y lo conserva tras perder una respuesta o recargar.
Las áreas desplazables tienen acceso de teclado. La extensión sigue la dirección
visual ya elegida para Tareas; no representa aceptación visual de toda la página.

Los tests de almacenamiento señalan sus cierres sintéticos. El navegador usa
owner HTTP/SQLite/React reales con esos resultados controlados, sin inferencia.
La prueba instalada del grafo usa kernel, broker, Git y SQLite reales, con
generación y Ken controlados. Sus resultados y límites están separados en el
[tablero](../modernization/execution-dashboard.md) y los recibos de esta entrega.
