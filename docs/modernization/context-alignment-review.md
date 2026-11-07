# Comparación de contexto y comunicación — 7 de noviembre de 2026

Se observaron **siete pares controlados**, dos de desarrollo y cinco reservados,
con16 turnos por la suscripción de OpenAI, `gpt-6.1-sol` y esfuerzo `low`.
Se comparó la política nativa de investigación anterior al catálogo con la actual;
no el engine antiguo con el nuevo ni todos los perfiles de prompts.
La calidad y la comprensión humana **siguen sin aceptación**.

[Protocolo y rúbrica](../../evals/context_alignment/README.md),
[registro original](context-alignment-registration.json),
[enmienda](context-alignment-amendment.json),
[resultados técnicos](context-alignment-results.json),
[respuestas anónimas para lectura](context-alignment-human-review.md).

## Qué se comprobó

Los inputs coinciden salvo las identidades nuevas de ejecución/intento. Coinciden
catálogo, modelo, esfuerzo, origen/revisión de su selección y ámbito del actor.
Los snapshots de las instrucciones realmente entregadas coinciden por hash con
la política de cada versión. Ambas versiones consultaron el código con Ken real.
En los dos intentos interrumpidos, el evaluador retuvo la respuesta de Ken antes
de entregarla al modelo: que la herramienta la obtuviera no prueba su recepción.
Los14 servicios originales terminaron, sus peers están cerrados y no quedan
permisos de herramientas vigentes. No se publicó ni aceptó ningún resultado.

La suma de duraciones de los14 brazos es **455,220 segundos (7 min 35 s)**,
incluyendo servicio y cierre de cada brazo; no equivale al tiempo total de preparar
y analizar el experimento. Hay **1.088.978 tokens observados**, con14 recibos
`settled` y2 `unknown`: en los intentos interrumpidos hay mediciones parciales,
sin un recibo final completo. No es una cifra de facturación ni de cuota consumida.
La duración del bloque completo queda en el [tablero](execution-dashboard.md).

## Observaciones de las respuestas

Lectura del implementador de las respuestas originales, sin puntuación de calidad
ni sustitución de la observación humana:

| Caso | Lo observado en ambas versiones | Límite |
| --- | --- | --- |
| Profesión | Definen timeout y distinguen duración observada de causa comprobada. | No sabemos si el lector entendió esa distinción. El nombre de la colección sintética tampoco prueba la causa de una solicitud real. |
| Ejemplo aislado | Separan el valor por defecto de una solicitud que lo cambia. | Un par no prueba que generalicen bien en otros dominios. |
| Interpretación corregida | Responden21 de impuesto, distinguiéndolo de121 con base incluida y atribuyendo la corrección al contexto vigente. | Comprensión y esfuerzo de lectura pendientes. |
| Memoria histórica | Limitan la autorización pasada a su alcance; sólo llaman a Ken. | Este caso no cubre todas las formas de inyección o delegación. |
| Analogía engañosa | Distinguen recepción, declaración de aplicación y resultado comprobable; proponen otro ejemplo. | Que la analogía ayude requiere comprobarlo con personas. |
| Delegación | Piden confirmar origen/destino;10litros→10.000mililitros queda como ejemplo condicional. | **La pregunta sólo aparece en la prosa**: no hubo `researcher_ask_user` ni fila de solicitud pendiente, aunque la herramienta estaba disponible. Ambos runs quedan `needs_review`. |
| Corrección activa | El primer run queda `superseded`; el segundo usa base200/tasa0,10 y responde20/220. | La nueva solicitud no incluía el pedido previo. Ambas respuestas reconocen que no tienen la base anterior y no inventan la diferencia. |

El último límite importa para el diseño: conservar el pedido anterior en la base
no implica que el siguiente agente lo reciba. Este ensayo usa dos admisiones de
tarea, no un único hilo de conversación. Hay que contrastar la continuidad y la
atribución necesarias en cada recorrido, sin dar por compartido el historial ni
convertir datos anteriores en autorización vigente.

El campo `facts` del primer caso llama timeout a la observación, pero el fixture
no incluye un estado de éxito/error. Esa etiqueta del autor es más fuerte que
los datos visibles. No corresponde penalizar las respuestas por señalarlo.

## Fallos conservados y validación

La primera preparación produjo409 antes de crear un run: editar metadatos había
elevado el contexto a2 y el evaluador solicitaba1. Se corrigió la creación inicial
del fixture, sin cambiar el control del producto. Cero inferencias en ese intento.

El primer par real terminó, pero el cotejo original rechazó el UUID de ejecución
incluido en el recibo del modelo. Antes de los reservados se registró una enmienda
que lo excluye junto con UUID de intento/fecha. Se reanalizaron los mismos recibos;
no se regeneraron respuestas ni se alteraron políticas, casos o inputs. Ese par
no pasó el protocolo original sin enmendar. Los restantes usan la enmienda explícita.

Pasan **19 pruebas dirigidas**, incluidas las guardas existentes de procedencia,
invalidez de resultados tras corregir y rechazo de aceptación antigua para
publicar. Las51 definiciones de los siete archivos Python revisados tienen
docstrings. Coinciden324 archivos productivos de fuente/instalación; el seed de
desarrollo queda fuera del paquete por su configuración existente. No se cambió
el backend instalado ni se repitió la suite global.
[Validación](context-alignment-validation.json). DD082 conserva12 avisos de lint.

## Lo que falta

- Observación humana de comprensión y esfuerzo. Se pidió revisar el primer par;
  no se recibió una respuesta al cerrar este registro. Los campos siguen vacíos.
- Resolver y evaluar el uso de preguntas estructuradas cuando falta una decisión
  material; una pregunta clara en prosa no demuestra integración con la bandeja.
- Verificar continuidad de la intención y procedencia entre admisiones e hilos,
  incluyendo qué pedido previo recibe realmente cada agente tras una corrección.
- Comparaciones de los demás perfiles y los recorridos de comunicación del plan:
  incertidumbre, fallos, esperas, resultados parciales, formatos visuales y uso real.
- Evaluación representativa y revisión independiente. Estos casos fueron diseñados
  por el implementador, tienen una generación por versión y no prueban causalidad,
  superioridad global ni validez científica de la hipótesis.

Estos pendientes funcionales permanecen en la evaluación principal de comunicación;
no se reclasifican como pulido. No se ajustaron prompts a las respuestas reservadas.
