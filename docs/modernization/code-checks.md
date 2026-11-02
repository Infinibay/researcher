# Comprobaciones ligadas al candidato

El host puede ejecutar comandos y pytest sobre una copia privada del candidato
exacto y conservar sus resultados. La migración 39 guarda reservas, receta,
identidades físicas, operación y evidencia. Este recorrido es interno:
`OwnedInferenceSession.run_check` requiere haber capturado y sellado el candidato.
Las rutas heredadas de CI todavía no han sido sustituidas. Una comprobación
positiva tampoco constituye revisión independiente, aceptación ni permiso para
publicar.

## Identidad antes de interpretar el resultado

`CandidateSubject` conserva proyecto, tarea, repositorio, ejecución, intento,
fence, contexto, base, commit, árbol y hash del diff. `CheckSpec` identifica el
comando completo, protocolo de resultados, entorno seleccionado y límites de
tiempo/salida. Ambos son inmutables y tienen huellas canónicas.

`CheckObservation` representa lo que recoge el ejecutor del host: candidato
observado, receta, código de salida, cierre físico, integridad de la salida,
coincidencia del código ejecutado y, para pytest, los bytes completos de JUnit.
Estos valores deben proceder del ejecutor y sus recibos, no de afirmaciones del
modelo. El clasificador no prueba por sí solo que esos hechos ocurrieran.

`CheckOutcome` conserva la identidad observada incluso si la rechaza. Así, una
comprobación de A no se convierte en una aprobación de B al volver de una llamada.

Ejemplo: A contiene `price.py` con valor 200. B cambia ese valor a 300 o pertenece
a otra versión del contexto. Un resultado de A se clasifica como inválido si se
intenta usar para B, aunque su proceso haya devuelto cero.

## Resultados distintos

| Estado | Qué demuestra el clasificador |
| --- | --- |
| `passed` | Comando terminado correctamente; en pytest exige casos observados y al menos uno sin omitir, sin fallos ni errores. |
| `failed` | Comando no aprobado o casos pytest con fallos/errores; también incluye el límite de advertencias de la versión instalada de pytest. |
| `no_tests` | Informe pytest completo sin casos; no se presenta como pruebas aprobadas. |
| `skipped` | Todos los casos observados fueron omitidos. |
| `infrastructure_error` | Terminación desconocida, salida incompleta, runner interrumpido/no disponible, informe ausente/inválido o resultados contradictorios. |
| `invalidated` | El candidato, receta o código ejecutado no coincide con lo solicitado. |

Un comando genérico puede aprobar una compilación o un formateador sin ofrecer
conteos de pruebas: esos conteos permanecen desconocidos. Para pytest se cuentan
los elementos de casos del informe, sin confiar en atributos que declaren un
número. El parser rechaza entidades XML y reportes superiores a un MiB. Los
códigos de salida se contrastaron con el enum de la versión instalada; cero
pruebas, uso incorrecto y límite de advertencias tienen resultados diferentes.

## Ejecución y persistencia

La integración reserva cada comprobación antes de crear archivos y registra su
candidato, receta, entorno, peer y operación originales. Utiliza el broker y el
dominio del intento original. Antes de confirmar resultado y evento en la misma
transacción, exige cierre físico, contexto vigente y contenido coincidente.
Repetir la misma clave en la ejecución devuelve el resultado existente; no
autoriza otro comando. Una reserva interrumpida queda en `reconciling` y exige
inspección del recibo original, sin repetición automática.

Cada comprobación obtiene una copia privada derivada del commit exacto. El
candidato y el repositorio original quedan fuera del perfil de ejecución. Los
metadatos Git de validación están en un directorio separado y se montan en modo
de sólo lectura; el host usa esa identidad protegida para verificar commit,
árbol y estado antes y después. Cambiar código seguido o crear archivos no
ignorados invalida el resultado; se permiten productos de compilación ignorados.
El host no confía en una configuración o índice que las pruebas puedan escribir.

El host admite dos entornos explícitos: `system`, sin directorio adicional de
paquetes, y `runtime-python`, con el directorio de paquetes del intérprete que
ejecuta el servicio montado en modo de sólo lectura. El ejecutable se verifica y
pertenece a las vistas de sistema/runtime permitidas. No hay instalación de
dependencias ni selección arbitraria de entornos. Se comprueban ruta canónica,
propietario, permisos y dispositivo/inodo del directorio; esto **no fija todos los
bytes de sus dependencias**. Una política futura de entornos reproducibles debe
versionar esos contenidos.

El proceso no recibe las credenciales ni el directorio personal del host y no
tiene acceso a Internet. Puede usar sockets Unix privados para sus bibliotecas.
Los reportes se recogen dentro del aislamiento con apertura sin seguimiento de
enlaces, sin bloqueo ante FIFO y con límite de tamaño. No se siguen desde el host
rutas controladas por el proyecto. La terminación del colector no sustituye al
recibo de cierre físico del dominio.

La preparación tiene un presupuesto de 60 segundos y la validación posterior de
30 segundos; el comando tiene su propio límite de hasta 300 segundos y salida
acotada. Son presupuestos por fase, no un límite total igual al del comando.
Stop cierra el propietario original y espera las tareas de comprobación antes
de desmontar su ámbito. Si cambió el contexto, se conservan archivos y reserva,
pero el resultado tardío no obtiene autoridad para aprobar el contexto nuevo.

La inversa de la migración 39 sólo retira almacenamiento de comprobaciones sin
uso, sin autoridad activa ni versiones posteriores. Conserva el historial previo
de candidatos. Una reserva de comprobación basta para impedir ese retroceso; no
se borran copias privadas para forzarlo. Las inversas anteriores mantienen sus
propias restricciones y requieren retirar primero las versiones posteriores.

Quedan pendientes la admisión pública del desarrollo, revisión independiente de
código, aceptación/publicación, integración operativa y retirada del CI heredado.
El código de pruebas y sus reportes son evidencia limitada: un proyecto también
puede contener pruebas incompletas o un comando que fabrique un informe. La
revisión debe evaluar su calidad antes de una decisión de publicación.

La ejecución actual tiene evidencia en [owned-checks-results.json](owned-checks-results.json),
[owned-checks-packaging.json](owned-checks-packaging.json) y
[owned-checks-docstrings.json](owned-checks-docstrings.json). El wheel final pasa
393 pruebas sin fallos ni omisiones. La suite completa anterior a la corrección
de importación y las 36 pruebas posteriores se conservan con alcance separado;
no se presentan como una segunda suite global aprobada.

La evidencia anterior de los contratos y del cierre corregido está en
[sealing-checks-results.json](sealing-checks-results.json),
[sealing-checks-packaging.json](sealing-checks-packaging.json) y
[sealing-checks-docstrings.json](sealing-checks-docstrings.json).
