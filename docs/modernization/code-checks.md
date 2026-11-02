# Comprobaciones ligadas al candidato

Los contratos y el clasificador están implementados. **Todavía no ejecutan CI ni
guardan comprobaciones durables**, y las rutas heredadas de CI no han sido
sustituidas por esta política. Una clasificación positiva tampoco constituye
revisión independiente, aceptación ni permiso para publicar.

## Identidad antes de interpretar el resultado

`CandidateSubject` conserva proyecto, tarea, repositorio, ejecución, intento,
fence, contexto, base, commit, árbol y hash del diff. `CheckSpec` identifica el
comando completo, protocolo de resultados, entorno seleccionado y límites de
tiempo/salida. Ambos son inmutables y tienen huellas canónicas.

`CheckObservation` representa lo que deberá recoger el ejecutor del host: candidato
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

## Ejecutor y persistencia pendientes

La integración debe reservar cada comprobación antes de iniciarla y registrar su
candidato, receta, entorno, peer y operación originales. Debe utilizar el broker
y los límites del intento, comprobar el cierre físico y revalidar contexto y
contenido antes de registrar el resultado. Un crash exige inspeccionar el recibo
original; no permite repetir el comando automáticamente.

La propuesta para admitir compilaciones y pruebas que escriben archivos es una
copia privada por comprobación, derivada del commit exacto. El candidato permanece
protegido y la copia debe coincidir antes y después de ejecutar. Los metadatos Git
usados por el host para esa verificación deben quedar fuera del alcance escribible
de las pruebas: no se puede confiar en filtros, referencias o flags de un índice
que el propio código comprobado pueda modificar.

El entorno de dependencias debe ser una elección explícita del host, con acceso
acotado. La ausencia de intérprete o dependencias produce un error de
infraestructura; no activa un subprocess del host ni un proveedor alternativo.
Los reportes se deben recoger de forma acotada dentro del aislamiento, evitando
leer desde el host rutas o enlaces simbólicos controlados por el proyecto.

Estas condiciones describen trabajo pendiente; todavía no hay un perfil de
comprobaciones ni una migración de almacenamiento para ellas. Las observaciones
de CI siguen siendo evidencia limitada y requieren revisión independiente y una
decisión del propietario antes de publicar.

La evidencia de los contratos y del cierre corregido está en
[sealing-checks-results.json](sealing-checks-results.json),
[sealing-checks-packaging.json](sealing-checks-packaging.json) y
[sealing-checks-docstrings.json](sealing-checks-docstrings.json).
