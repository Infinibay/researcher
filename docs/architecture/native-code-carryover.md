# Reutilizar un candidato anterior con autoridad nueva

## Resultado de producto

El propietario puede elegir cambios de un candidato nativo anterior como material
para otra ejecución de desarrollo. Tareas muestra la solicitud y el contexto que
recibió su autor, la base Git y el diff completo; permite descargar sus bytes.
La selección se envía junto a la solicitud nueva tanto desde Tareas como desde
Conversación. Si hay una propuesta activa, se puede retirar con Stop antes de
iniciar otro intento. Consultar o seleccionar material no inicia trabajo.

Ejemplo: una implementación anterior sirve, pero una corrección exige conservar
la API. La solicitud nueva puede pedir «reutiliza estos cambios manteniendo la
API». El autor nuevo recibe ambos contextos y los cambios anteriores como datos,
para inspeccionarlos y adaptarlos en su copia privada. No se infiere que los
requisitos o la base siguen siendo equivalentes.

No se heredan permisos, sesiones, presupuestos, pruebas, revisión ni aceptación.
La ejecución nueva produce su propio candidato y necesita comprobaciones nuevas,
revisión independiente y aceptación explícita. El candidato y el repositorio
originales permanecen intactos; retirar el autor anterior no borra sus cambios.

## Contrato y persistencia

`PriorCodeTarget` identifica intento original y SHA-256 de un paquete completo.
`CodeCarryovers` exige candidato listo de la misma tarea/proyecto, autor nativo
real con hilo/turno registrados, cierre de peers y entrada original disponible.
Rechaza trabajo con origen desconocido; no reconstruye lo que recibió un autor
histórico a partir del estado actual. El diff se conserva en base64 para incluir
bytes binarios sin sustituciones. Un paquete mayor de600000bytes se rechaza
completo, sin recortar historia ni cambios para hacerlo caber.

La admisión comprueba el mismo repositorio y directorio registrados, la huella
observada y el contexto actual. Guarda el paquete en el recibo existente de
`runtime_commands`, en la misma transacción que crea la ejecución. No introduce
otro journal, tabla, migración o planificador. Las solicitudes sin selección
mantienen sus hashes históricos. Un reintento idéntico devuelve la ejecución
original antes de volver a consultar el candidato; otra selección con la misma
clave entra en conflicto. Perder una respuesta no permite cambiar el material.

`freeze_input` agrega `prior_code` a la entrada del intento nuevo, separado de
`request` y de los requisitos actuales. Conserva la entrada anterior completa y
su hash, la identidad de autor/intento/hilo/turno, la base/tree/head/diff originales
y declaraciones explícitas `data_only` y `not_granted`. El límite de entrada total
sigue vigente. El registro literal permanece consultable después del reinicio.
No se copia ni habilita la carpeta anterior como workspace del intento nuevo.

Los endpoints owner son GET `.../tasks/{task_id}/prior-code/{attempt_id}` y las
admisiones existentes de runs/instructions con `prior_code` opcional. El cliente
sólo envía intento y huella; no puede suministrar bytes o afirmar autoría. Tareas
congela la selección dentro de la intención original de envío y distingue la
inspección de la acción «usar estos cambios» y del inicio del trabajo.

## Progreso observado durante herramientas

El ensayo de reutilización encontró que un comando podía terminar correctamente
y el turno fallar por inactividad. `CodexSession` sólo renovaba ese reloj con
notificaciones de herramientas, aunque ya hubiese respondido a solicitudes
reales del host. Ahora una respuesta de host completada en el hilo/turno correcto
cuenta como progreso. Una solicitud pendiente, el texto de razonamiento o una
notificación ajena no amplían el plazo. El límite absoluto y los demás controles
siguen aplicándose. Hay una reproducción corta mediante un peer real del
protocolo y un callback que tarda más que el plazo de inactividad.

## Alcance que sigue pendiente

Este recorrido reutiliza candidatos nativos capturados y con entrada original.
La importación explícita de worktrees antiguos enlazados/sucios y copias
interrumpidas sin candidato capturado continúa pendiente. No se los etiqueta como
autores nativos para sortear las comprobaciones. También falta conectar este
material al despacho automático de sucesoras de planes, retirar DevelopmentFlow/
CodeReviewFlow y otros consumidores antiguos, y demostrar exclusión global.

La interfaz conserva su dirección visual existente; este control no completa la
aceptación de la página ni demuestra comprensión humana o calidad de modelos.
El resto del plan —prompts/libros, todas las pantallas, instalación, restore,
inversas43–53, suite global y revisión final— permanece activo.

La evidencia comprobada de esta entrega se guarda en
[resultados](../modernization/code-carryover-results.json) y
[paquete](../modernization/code-carryover-packaging.json).
