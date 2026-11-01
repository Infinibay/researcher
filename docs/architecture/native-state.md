# Estado nativo conservado y reanudación sin replay

Guardar el cuaderno de una ejecución permite consultarlo después. No concede
permiso para volver a ejecutar sus acciones. `NativeState` conserva datos de
Codex y los vincula al intento original; las concesiones y el cierre siguen bajo
el broker, el registro de autoridad y el estado de negocio.

## Propiedad y almacenamiento

El host llama explícitamente a `NativeState.provision` con una admisión nativa
vigente y un directorio nuevo fuera de la fuente. Crea directorios privados0700,
sin credenciales, sincroniza sus entradas y registra en el journal testificado:

- Identidad del directorio raíz y de `home`, mediante dispositivo/inodo.
- Autoridad, origen de DB, proyecto/tarea, intento, fence, contexto y workspace.
- Referencia única del origen al estado; crear otro hogar no reinicia el presupuesto.
- Operación propietaria, intención de sesión, thread y reserva del único turno.

La creación no inicializa autoridad global ni adopta directorios existentes. Un
commit incierto puede dejar datos huérfanos: no se borran ni adoptan automáticamente.
`load` abre sólo el recibo y los objetos existentes. Raíz/home sustituidos, ausentes,
con permisos ajenos o con `auth.json` se rechazan. No se copia el hogar administrado
del usuario. La autenticación externa continúa por el RPC privado del host.

El perfil monta **sólo `home`** con un descriptor fijado en `/home/actor/.codex`.
Codex puede escribir sus datos allí; no ve el journal ni puede editar la identidad
del host. La fuente sigue readonly. Estado mutable no equivale a historial íntegro
certificado: corrupción/restore de sus archivos requieren reconciliación y nunca
habilitan repetir una reserva de turno conservada en el journal.

## Un escritor y conservación del historial

La reserva global vincula el estado a su operación dentro del mismo commit que
reserva el peer. Reutilizarlo exige cierre físico publicado de su escritor anterior,
el mismo intento/origen y la misma concesión. El FD se revalida al montar.

La migración32 modifica únicamente el índice de unicidad de peers: puede existir
otro peer nativo cuando el anterior está `closed`; sólo uno puede estar preparado
o activo. Mantiene la unicidad de negocio, las filas/rowids anteriores, referencias,
triggers y recibos. El fallo de creación del índice revierte toda la migración.
`AttemptPeers` y recuperación conservan y revisan todos los peers del intento.

## Intención, respuesta y reanudación

Antes de `thread/start`, la composición registra modelo, hash del catálogo y hash
de las instrucciones. Después vincula el ID devuelto antes de exponer la sesión.
Si falta ese recibo, no inicia otro thread para ocultar la incertidumbre.

Al reabrir, el llamador debe elegir explícitamente el ID registrado. Se comprueban
la intención y los metadatos de `thread/read`: ID, cwd lógico, modelo y proveedor.
Sólo después se permite `thread/resume`, sin reenviar `dynamicTools`. Codex restaura
el catálogo del thread, según su [contrato oficial](https://learn.chatgpt.com/docs/app-server).
Ken vuelve a validar preparación, catálogo y disponibilidad; el helper pasa otra vez
su prueba local. Una sesión reanudada no evita estos controles ni los grants de negocio.

Antes de `turn/start`, el estado reserva el único dispatch del intento, con hash
de la entrada, en el journal. Una reserva completada o incierta impide otro envío,
incluso si se perdió su acuse antes de que Codex recibiera nada. Reanudar no llama
al modelo por sí mismo. Cambiar texto tampoco convierte un replay en trabajo nuevo.
El servicio mantiene además su propia reserva de entrada, identidad y presupuesto.

Esto permite reabrir una conexión dentro de la concesión original todavía viva.
No revive intentos retirados ni permite adoptar un broker tras morir su propietario.
La continuación tras reiniciar todo el servicio sigue requiriendo reconciliación,
admisión/contexto explícitos y el trabajo pendiente de integración productiva.

## Verificación y límites

Las pruebas usan journal, namespaces y cgroups reales. Codex0.166 real conserva un
thread entre dos procesos, permite leerlo y reanudarlo y mantiene `account:null`.
No se envía `turn/start` ni se llama a una cuenta/modelo. Para materializar el
rollout se inyecta **sólo en el fixture** un mensaje fijo sin generación: Codex no
materializa un thread vacío hasta su primera entrada. No hay inyección/restauración
de historia como fallback en el producto; un thread inexistente falla explícitamente.

La composición con protocolo de modelo controlado conserva catálogo y thread,
rechaza cambios de modelo/instrucciones/catálogo/metadatos o recibo perdido y
bloquea replay tanto después de completar como tras perder el acuse de reserva.
Estas pruebas no demuestran un turno generativo reanudado ni recuperación del API.

Faltan adopción en `configured_runtime`/`RuntimeService`, orígenes e inscripción de
todos los actores, ciclo OAuth administrado, continuidad entre intentos, límites/
retención de disco y aceptación de restore. No se migró una DB del usuario ni se
repitió generación para comprobar esta persistencia. El resto del plan sigue abierto.

Evidencia: [contratos](../modernization/native-state-evidence.json),
[suite](../modernization/native-state-results.json),
[paquete](../modernization/native-state-packaging.json).
