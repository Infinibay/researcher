# Vista del repositorio admitido en los peers

Este cambio fija la identidad del directorio raíz para los peers nativos y de
comandos que tienen un vínculo de admisión durable. **No implementa todavía la
exclusión global entre workspaces ni habilita edición productiva.**

## Contrato

`PeerRegistry.workspace_binding` recupera la selección original del intento,
independiente de la selección actual del proyecto. Antes de crear el namespace,
el guard abre el directorio sin seguir un symlink final y compara dispositivo e
inode con esa admisión. Si difieren, impide ejecutar el payload.
Conserva el descriptor hasta cerrar el peer.

Dentro del peer, la fuente está en `/run/researcher-source`. Es un montaje del
descriptor admitido bajo un `/run` privado; sus otros destinos directos conservan
los mounts/symlinks del host. Esa ubicación no depende de nombres de directorios
de la fuente que el usuario pueda renombrar. Cada peer tiene su propio namespace:
el mismo nombre lógico no identifica el mismo repositorio entre ejecuciones.

La fábrica nativa usa esa vista para cwd, permisos, confianza del proyecto, Ken y
comprobación del thread. La fábrica de comandos usa la misma vista en el perfil.
El ejecutor traduce únicamente el cwd relativo a esa raíz. El journal conserva
la admisión y el fingerprint del host; no cambia su identidad para adaptarla a
un nombre dentro del sandbox. No se reescriben cadenas arbitrarias de `argv`.

Las herramientas y el caché de modelos de Ken se resuelven una sola vez y se
validan contra la fuente física antes de componer esos argumentos. Cambiar el
nombre visible no debe ocultar un solapamiento entre la fuente y activos confiables.
Dos pruebas adicionales observaron el rechazo ausente y luego su corrección.

Usar rutas relativas al repositorio sigue siendo el contrato de los comandos.
Las rutas absolutas del host no se convierten en grants del peer; tampoco se
amplía el perfil para hacer funcionar enlaces absolutos hacia esas rutas. Un
thread histórico con otro cwd requiere conciliación: no se reanuda silenciosamente
sobre la nueva vista. No se añade otro loop de agente ni inferencia auxiliar.

## Qué demostraron las pruebas

Los seis casos iniciales fallaron con el guard anterior: ambos tipos de peer
actuaban sobre el sustituto antes del arranque, entre validación y montaje, o tras
liberar el gate. Ahora también se comprueba renombrar el directorio padre.

- Una sustitución anterior a la apertura rechaza el payload y conserva cerrado el
  peer, sin escribir en la carpeta sustituta.
- Un wrapper de prueba renombra el directorio después de abrir el FD y antes de
  ejecutar Bubblewrap. El payload lee la fuente admitida y su efecto controlado
  llega sólo al objeto original.
- Después del gate, renombrar y recrear la fuente o su padre no redirige ese efecto.
  Son namespaces reales, no una simulación de `Path.resolve`.
- La fábrica se prueba por el wire: thread/cwd, permisos y argumentos de Ken usan
  la vista lógica mientras la admisión persistida conserva su valor original.
- Codex CLI real ejecutó siete casos sobre una admisión durable: cálculo, lectura,
  rechazo de escritura, acceso externo, symlink de escape, red y credenciales.
  Se comprobó explícitamente el perfil de la vista; no bastó con leer la ruta
  original mientras todavía existía. Todos los peers cerraron y la fuente no cambió.
- Codex/Ken reales hicieron preparación, búsqueda y lectura con esa vista y la
  identidad original. Ambos resultados MCP tenían `isError=false`; no se enviaron
  turnos de modelo ni se ejecutaron los tests del código ficticio leído.

## Decisiones que explican el montaje

Montar el FD sobre la ruta original no bastaba: el mountpoint seguía la dentry
del host al renombrarla. Reconstruir todos sus ancestros y vecinos en un árbol
privado pasó los casos pequeños, pero la suite completa encontró el límite de
9000 argumentos de Bubblewrap al enumerar miles de entradas temporales. Se
descartó esa implementación; las pruebas finales usan la ruta lógica privada.

Tampoco se usa OverlayFS sobre `/` vivo: modificar sus árboles subyacentes durante
el montaje tiene comportamiento no definido por su contrato. Además podría
convertir escrituras persistentes en cambios efímeros. La decisión no depende de
que una combinación particular llegue a pasar unos casos de rename.
[Documentación primaria de OverlayFS](https://docs.kernel.org/filesystems/overlayfs.html#changes-to-underlying-filesystems).

El guard conserva su responsabilidad de identidad/lifetime. La política de
lectura, escritura, credenciales y red sigue perteneciendo a los perfiles internos
de Codex y del worker de Ken. Su vista amplia del host no se presenta como un
sandbox del payload. El nombre privado bajo `/run` es parte del entorno Linux
soportado; no se protege de un administrador que altere el sistema de montajes.

## Cierre y límites pendientes

Los peers rápidos expusieron una carrera anterior: `/proc/PID/stat` podía devolver
`ESRCH` después de abrir el pidfd. Un diagnóstico local recuperó ese traceback,
manteniendo la redacción de errores productiva. Dos casos nuevos reproducen
metadatos desaparecidos mientras el proceso termina. Se espera el pidfd con plazo
acotado; sólo su barrera terminal demuestra cierre. No se señaliza por ausencia
de metadatos ni se transforma un error de permisos en ausencia de proceso.

Los ensayos sin turno de modelo se retiran explícitamente con outcome `failed`
después de comprobar todos sus peers cerrados: no producen una propuesta nativa.
Ese estado del intento diagnóstico no representa un fallo de las comprobaciones
ni acepta una tarea. Se conciliaron también cinco intentos de diagnóstico previos,
con cero dispatches de inferencia y sin repetir jobs.

Un FD fija el objeto raíz, **no congela sus archivos**. Cambios externos de
contenido/hijos, alias entre árboles, escritores heredados, arbitraje global,
publicación global anterior a G y bootstrap/restore siguen pendientes. El peer
de negocio no usa la fuente y conserva su contrato de transporte. Los diagnósticos
antiguos sin admisión no adquieren retroactivamente esta garantía.

La admisión actual registra dispositivo/inode; no conserva una referencia viva
desde aquel instante hasta la apertura del peer. Este cambio no demuestra esa
continuidad frente a eliminación/recreación con reutilización de identidad o un
restore anterior a la apertura. Ese ciclo de vida también pertenece al trabajo
pendiente de autoridad, no a los casos de rename ya comprobados.

Evidencia: [resultados](../modernization/peer-workspace-results.json),
[ensayos nativos](../modernization/peer-workspace-native.json) y
[hashes y límites](../modernization/peer-workspace-evidence.json).
