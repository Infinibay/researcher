# Código aceptado como entrada de una tarea dependiente

Aceptar un candidato no modifica el repositorio de origen. Por ejemplo, la tarea
A puede producir `fact.txt=200` y recibir revisión independiente y aceptación,
mientras el origen todavía contiene `137`. La tarea B necesita los bytes de A
y sus requisitos originales para decidir qué aplicar en su propia copia.
Recibir un hash o el estado «terminada» no proporciona ese contexto.

## Entrega y lectura

`PlanExecutions` selecciona el resultado productivo aceptado de cada dependencia.
Una revisión aceptada más reciente no sustituye a ese resultado. Las entregas
nuevas usan esquema 4 (la descripción de código se introdujo en el3) y describen el candidato, su aceptación y tres materiales:
paquete del candidato, entrada original del autor y diff binario completo.
Cada descriptor identifica hash y tamaño; no copia recursivamente prompts de
predecesoras. Las entregas ya preparadas con esquema2/3 conservan sus bytes y hash.
El esquema4 también describe [informes documentales](predecessor-research-material.md)
sin incrustarlos completos en la entrada del sucesor.

El host ofrece `researcher_prerequisite_code` cuando la entrega original contiene
código aceptado. El modelo elige solamente `task_id`, sección, offset y tamaño
de ventana, hasta 16384 bytes. No elige proyecto, run, ruta ni permisos. La
respuesta contiene bytes base64, hash del material completo, tamaño total,
cobertura y siguiente offset. Una página posterior no demuestra haber leído las
anteriores. Una entrada original ausente se informa como desconocida.

`PredecessorMaterials` reutiliza la transacción, lease y validación de candidato
aceptado de `CodeReviews`. Comprueba dependencia real, aceptación exacta, versión
del contexto, cierre original, hashes y mismo repositorio registrado. Una tarea
sin esa dependencia no puede consultar el material por compartir proyecto.
El revisor independiente obtiene el alcance de la entrega del autor exacto que
revisa; tampoco puede seleccionar un autor arbitrario.

`PredecessorTools` se incorpora al catálogo antes de admitir el thread nativo,
reutiliza `ProjectTools` y drena sus lecturas al retirar el alcance. No crea otro
loop, tabla, servicio, credencial ni autorización HTTP. No escribe archivos,
ejecuta Git, publica ni acepta tareas.

La captura posterior del candidato nuevo conserva un único plazo total: el
presupuesto temporal seleccionado para el run, con mínimo60 y máximo300 segundos.
El controlador conserva además su plazo global y las comprobaciones de cierre.
Agotar el plazo conserva el estado para inspección; no reintenta la captura.

## Interpretación humana y del agente

La entrada histórica demuestra qué se suministró a A; no demuestra comprensión
ni convierte sus instrucciones en requisitos actuales de B. El diff demuestra
el cambio capturado; no demuestra que exista en el origen. La aceptación de A
no aprueba el candidato de B. El autor compara requisitos y bases, aplica o adapta
solamente lo justificado y explica qué leyó, qué cambió y qué sigue desconocido.
Los prompts de autoría, investigación y revisión expresan estas distinciones.

## Verificación

Las pruebas de almacenamiento distinguen sus testigos sintéticos de la ejecución
física. Cubren identidad, alcance, contexto obsoleto, ventanas exactas y
compatibilidad de entregas. `test_owned_code_dependencies.py` ensaya el recorrido
plan → autor A → revisión A → aceptación → autor B → revisión B → aceptación
con kernel, broker, Git y SQLite reales; la generación y Ken son controlados.
El resultado y sus límites se registran en el tablero y los recibos de esta
entrega. Este contrato no demuestra calidad de un modelo real ni cierre integral
de un proyecto.
