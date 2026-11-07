# Conservación y recuperación de copias: D08

Base `437ef3f`. Inicio real: **2026-11-07 21:25:39 UTC**.
Comprobado el **2026-11-07 22:04:07 UTC**: **38 min 28 s** hasta verificar,
excluyendo documentación/checkpoint posteriores. **D08 comprobado** dentro de
las fronteras siguientes. [Resultados](workspace-retention-results.json) y
[paquete](workspace-retention-packaging.json).

## Qué puede hacer el propietario

En Repositorios, **Copias de trabajo** permite elegir un intento concreto,
ponerlo en cuarentena y conservar un archivo verificado de sus datos. Incluye
cambios tracked, archivos nuevos e ignorados por Git y el contenido literal de
enlaces. El propietario elige de 1 a 3650 días de retención; la web propone 7.
El plazo empieza con esa decisión y el borrado siempre exige una segunda acción
explícita. Consultar la página o reiniciar la aplicación no inicia limpieza.

Por ejemplo: un intento dejó una solución útil sin publicar. El propietario puede
archivarla, retirar después su copia original y recuperar los archivos en una
carpeta nueva. Esa recuperación no inicia un agente, acepta código ni publica
cambios. El archivo permanece conservado después de retirar el original.

La cuarentena mantiene la historia y las rutas originales registradas, pero
invalida la disponibilidad para revisión, aceptación/publicación, reutilización
de candidatos e importación de esa copia privada. Una aceptación histórica
no equivale a una autorización actual sobre bytes archivados. La interfaz pide
reconocer esta pérdida de disponibilidad antes de la decisión.

## Fronteras implementadas

| Situación | Comportamiento y evidencia |
| --- | --- |
| Tarea etiquetada como terminada, pero aún hay procesos | La admisión comprueba el journal de autoridad real, la identidad física de la DB, proyecto, tarea, intento y fence. Exige cierre de grants, operaciones y peers originales; también rechaza consumidores de la misma tarea todavía vivos. Una prueba conserva un dominio real abierto y cambia sólo la etiqueta SQL: se rechaza la cuarentena. |
| Nuevo consumidor de una copia en cuarentena | La decisión y los controles de disponibilidad usan las transacciones de admisión existentes. `DevelopmentWorkspaces.read_view` exige `ready`; revisión, reutilización e importación comprueban además el registro de retención. No se modifican retrospectivamente los recibos de ejecución. |
| Disco lleno o archivo incompleto | Se registra intención antes de copiar. La copia tiene presupuesto, inventario completo, hashes y controles de identidad antes/después. Los parciales quedan fuera del árbol verificado. No habilita borrado ni declara éxito; admite reconciliar la operación original o solicitar otro archivo explícito. |
| Copia modificada después de archivarla | El borrado exige el archivo observado, plazo cumplido y la revisión original exacta. Un cambio posterior deja la operación pendiente y conserva los datos; no hereda el permiso anterior. |
| Interrupción durante el borrado | Primero registra el traslado y mueve la asignación original a un directorio privado sin sobrescribir. Luego elimina sólo sus entradas originales verificadas. Descriptores de directorios y `nofollow` impiden que un enlace sustituido redirija la eliminación. Un fallo conserva estado pendiente y el archivo de recuperación. |
| Crash entre filesystem y recibo | Tres casos terminan un proceso hijo tras el efecto real de archivar, borrar o restaurar y antes del recibo. Reabrir permite reconciliar la misma decisión; una carpeta nueva en la ruta antigua no se borra. |
| Respuesta perdida o recarga web | El navegador conserva proyecto, intento, clave y cuerpo originales antes del POST. Permite consultar o reenviar esa misma solicitud; no la reproduce automáticamente. El servidor devuelve el recibo original y rechaza cambiar sus argumentos con la misma clave. |
| Apagado mientras copia | El servicio conserva el handle del thread, rechaza nuevas decisiones y espera el trabajo original antes de liberar el bloqueo de dueño. La prueba retiene una copia real mientras empieza el cierre. |
| Backup restaurado en otra ruta | El backup incluye archivo e historial. Una decisión copiada no puede borrar archivos del host anterior, incluso si sigue accesible. Una nueva recuperación usa los bytes verificados en una carpeta de la instalación restaurada. No transfiere testigos de cierre, inodos ni autoridad. |
| Otro proyecto o permisos inventados en HTTP | La API deriva el dueño de la sesión y conserva proyecto/intento/clave. Rechaza CSRF incorrecto, proyecto ajeno y campos de cierre suministrados por el cliente. No acepta rutas arbitrarias. |

La migración **68** registra la copia original y operaciones de archivo, borrado
y recuperación. Protege origen e intención contra cambios, y conserva recibos
terminados. La inversa sólo admite un esquema sin historia utilizada ni versiones
posteriores. Historia, estado y eventos se confirman en la misma transacción.

## Verificación y límites

El paquete instalado fuera del checkout completa **291 casos correctos, cero
fallos y cero omisiones, en 222,793 s**. Coinciden 673 fuentes Python/SQL entre
checkout, wheel e instalación, 360 de producto; los 301 módulos backend observados
proceden de la instalación no editable. Incluye los casos finales de reemplazo
de un directorio padre, cierre con copia en marcha y controles de autoridad del
dueño. La advertencia heredada de Starlette/httpx queda para dependencias; no
se presenta esta selección dirigida como una suite global verde.

Las pruebas de almacenamiento usan directorios y Git reales, con un testigo
sintético declarado. Las integraciones de dueño comprueban por separado el
journal y los dominios reales, con inferencia controlada. Las selecciones incluyen
consumidores de revisión, aceptación, reutilización, importación, publicación,
API, migraciones y backup. No se suman corridas solapadas como pruebas distintas.

Se conservan los fallos de desarrollo: colección antes de crear el módulo,
fixture de raíz configurada con modo distinto del de asignación privada y una
consulta incorrecta a `runtime_peers.grant_id`. El contrato real usa el `peer_id`
registrado por las operaciones del broker; no se añadió una columna ficticia ni
se sustituyó el testigo físico por una etiqueta SQL.

La interfaz tiene **5 pruebas DOM** dirigidas y compilación comprobadas. La
[auditoría del panel](../design/audits/2026-11-07-workspace-retention/report.md)
verifica escritorio/móvil, decisiones explícitas y recuperación visible. Usa
respuestas HTTP controladas; no demuestra un recorrido completo navegador–kernel
ni aceptación integral de Repositorios. No hubo turnos de modelos o escrituras
en cuentas externas en este bloque.

[85 definiciones Python nuevas o modificadas](workspace-retention-docstrings.json)
tienen docstrings; los módulos y helpers frontend relevantes tienen JSDoc. El
inventario de prompts conserva 85 candidatos revisados sobre 314 fuentes: se
revalidaron consumidores modificados, sin atribuir una mejora de eficacia a esa
comprobación estática. No se afirma cobertura documental de todo el código histórico.

Los worktrees antiguos sin testigos fiables siguen preservados detrás de las
entradas peligrosas retiradas en el bloque anterior. Esta entrega no inventa
autoridad para eliminarlos. Tampoco elimina archivos de recuperación, parciales
ambiguos o datos históricos del usuario. La gestión más amplia de restos y la
aceptación de restauración siguen en D13/datos históricos.

Una eliminación pendiente que encuentra bytes cambiados o un archivo corrupto
se conserva para resolverla: no hay todavía un recorrido de cancelación de esa
intención. Los archivos verificables pueden recuperarse como datos nuevos; antes
de pedir borrado se puede solicitar un archivo actualizado. El sistema depende
de raíces privadas del operador y de cierre comprobado del dominio nativo; no
declara protección absoluta ante un proceso host malicioso con el mismo usuario.
Entradas no soportadas y límites de volumen/tiempo dejan una operación pendiente.

Los ajustes secundarios de presentación quedan en DD118 para la pasada final.
No se declara una suite global verde, evaluación de comprensión humana ni
aceptación de las doce páginas. Primero las capacidades principales restantes.
