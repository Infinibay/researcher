# Ken: directorio admitido y modelos locales en el CLI

El worker de Ken ya montaba la fuente por descriptor. Ahora comprueba que ese FD
corresponde a la identidad esperada por el host **antes** de crear o abrir `.ken`.
El CLI también pasa efectivamente el caché de modelos públicos verificados al sandbox.

## Ruta sustituida y fuerza de la evidencia

La admisión conserva path, dispositivo e inode. Una ruta igual puede señalar otro
directorio después de un rename/reemplazo. El runtime consulta el vínculo durable
del intento y lo compara antes de iniciar peers. Entrega dispositivo/inode al MCP
requerido de Ken, cuyo worker los comprueba mediante fstat sobre el FD abierto.
Una sustitución anterior produce rechazo sin crear estado en el nuevo directorio.
Un rename posterior conserva la vista del directorio abierto dentro del sandbox.

Las invocaciones diagnósticas antiguas sin vínculo durable fijan la identidad
observada al entrar en la fábrica; no inventan una admisión histórica. El servicio
productivo sigue exigiendo el vínculo de la solicitud. El modelo no elige estos
valores ni obtiene autoridad de control a partir de ellos. El CLI exige ambos
componentes si se proporciona alguno; datos incompletos fallan antes de crear estado.

## Caché aceptado pero omitido

El CLI aceptaba `--model-cache`, pero main no lo pasaba a `worker_process`. Las
pruebas que llamaban directamente al helper con ese parámetro no cubrían esa pérdida.
Una lectura de archivo tampoco demuestra que la búsqueda disponga de modelos locales.

Ahora main reenvía el caché y conserva el montaje de archivos públicos según
manifiestos/versiones/SHA256. No monta todo el caché ni sus credenciales. La corrección
no instala otra distribución de Ken ni permite descargas o una API alternativa dentro
del sandbox. La prueba nueva ejercita main mediante un subprocess real y verifica
bytes públicos disponibles y token privado ausente.

## Ensayos y límites

Las pruebas con bubblewrap verifican sustitución antes de abrir, rename posterior,
argumentos CLI completos y montaje de caché. La fábrica nativa rechaza una sustitución
del vínculo admitido antes de arrancar peers y pasa la identidad al MCP requerido.

El ensayo `ken-identity-cc7e897d` usa Ken publicado0.18.0, Codex0.166.0 y repo ficticio
independiente. CLI prepare, `ken_find` de la función fiscal y `ken_read` devuelven
código real con `isError=false`. Se comprueban catálogo de15 herramientas, cero
turnos al modelo, peers cerrados, grant revocado y fuentes sin editar. Los tests del
repo ficticio fueron leídos como fuente, no ejecutados ni declarados aprobados.

El primer ensayo, sin repo Git propio, heredó un MCP del repositorio padre. La
prevalidación rechazó servidores ajenos antes de crear un turno. Se conservó la
protección y se aisló el repo de ensayo sin cambiar configuración del usuario. El
intento fallido se concilió después de comprobar cierre; no se reprodujo generación.

Véase [evidencia](../modernization/ken-identity-evidence.json),
[ensayo nativo](../modernization/ken-identity-native.json) y
[resultados](../modernization/ken-identity-results.json).

Un FD fija el directorio, no congela contenido. Esta entrega no fija la vista de
todos los comandos de desarrollo, descubre todos los alias de hijos ni implementa
exclusión entre DBs o transferencia/restauración. La revisión independiente de
[autoridad del workspace](workspace-authority-design.md) conserva esas obligaciones.
La edición sigue pendiente.
