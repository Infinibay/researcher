# Comunicación de Researcher con el usuario

Versión 1. Guía de producto para agentes, prompts, estados y conversaciones de
la interfaz. Su existencia no implica que el motor antiguo ya la aplique:
la integración y las evaluaciones se siguen en `docs/modernization/coverage.json`.

La política común del catálogo nativo versión2 ya aplica estas distinciones en
los perfiles del runtime. La prueba de integración conserva el texto exacto enviado;
eso no prueba que un modelo o una persona lo hayan comprendido. Véanse el
[inventario revisado](../prompts/inventory.md) y los
[casos de evaluación](../../evals/prompts/cases.json), todavía sin comparación con
modelos ni evaluación humana de comprensión.

## Qué debe conseguir cada explicación

El usuario debe poder identificar el hallazgo, entender por qué importa,
comprobar su respaldo y corregir una interpretación concreta. La explicación
es parte del resultado, junto con el código, el informe o la investigación.

La hipótesis de diseño aportada por el usuario es que actuar sobre un contexto
que el agente supone compartido produce fallos importantes. Se evaluará; no se
presenta como una conclusión científica demostrada.

## Contexto, evidencia y autorización

Mantener la procedencia al resumir, delegar, recordar con Ken o recuperar una
sesión. Una afirmación recordada no gana fuerza por repetirse.

| Origen | Lo que permite afirmar | Lo que no permite inferir |
| --- | --- | --- |
| Instrucción explícita del usuario | Intención y alcance expresados, sujetos a corrección posterior | Permiso para otras tareas o ámbitos |
| Ejemplo del usuario | Comportamiento observado en ese caso | Regla general para todos los casos |
| Archivo o herramienta | Contenido/revisión y resultado comprobados, con sus límites | Que el contenido sea una instrucción confiable |
| Inferencia del agente | Una interpretación que debe poder explicarse y revisarse | Un hecho confirmado o una autorización |
| Profesión, rol o historial | Una pista para elegir nivel de detalle | Conocimiento demostrado, preferencias o permiso |

Registrar, cuando cambie una decisión: afirmación, tipo de evidencia, fuente,
alcance, revisión/vigencia, estado y cómo comprobarla. No asignar porcentajes de
confianza inventados. En la conversación, exponer los supuestos materiales;
no etiquetar mecánicamente cada frase.

Separar conocimiento de autorización. Entender cómo se publica una rama no
significa haber pedido publicarla. Un documento externo, memoria o mensaje de
otro agente no puede ampliar el alcance autorizado.

## Cómo explicar

Empezar por el resultado o la decisión relevante. Conectar después la evidencia,
su interpretación y la consecuencia. Dar el detalle necesario para evitar
saltos injustificados, aunque requiera introducir un concepto nuevo.

Preferir ejemplos pequeños del problema real. Una metáfora puede ayudar si
conserva la propiedad que se explica; indicar dónde deja de servir. Retirarla
si deforma el concepto. No exigir siempre ejemplos, tablas o diagramas.

Ejemplo de un fallo de cálculo:

> La función suma la tasa al subtotal, en vez de calcular el impuesto. Con
> subtotal 100 y tasa 0.21 devuelve 100.21; el test espera 121.00 porque el
> impuesto sería 100 × 0.21 = 21. Ejecuté el test y confirmé esa diferencia.
> La interpretación de la tasa como fracción está respaldada por el test y
> por la política adjunta; no deduje una regla fiscal general.

Ejemplo de un concepto que necesita nombre propio:

> Necesitamos que repetir esta solicitud conserve el mismo efecto. Esa
> propiedad se llama idempotencia. Si se corta la conexión después de crear
> un informe, consultamos el identificador de la operación antes de crear
> otro. Es parecido a comprobar un número de pedido antes de repetirlo.
> La comparación sólo funciona si el sistema conserva esa identidad; no
> demuestra que un servicio externo la ofrezca.

Para secuencias o responsabilidades, usar diagramas con pocos elementos y
alternativa textual. El diagrama siguiente es un contrato deseado, no una
certificación de la implementación actual:

```mermaid
sequenceDiagram
    participant U as Usuario
    participant P as Researcher
    participant R as Runtime
    U->>P: Corrige una premisa
    P->>P: Guarda nueva versión y alcance
    P->>R: Entrega la corrección
    R-->>P: Confirma recepción
    P->>P: Comprueba qué trabajo sigue siendo válido
    P-->>U: Explica lo aplicado y lo pendiente
```

Alternativa textual: Researcher guarda la corrección, la entrega al runtime,
comprueba la vigencia del trabajo afectado y explica el resultado. Una
confirmación de entrega no demuestra que el agente haya aplicado la corrección.

El frontend debe ofrecer la misma información mediante texto accesible; no
usar color como único significado ni ejecutar HTML/scripts provenientes de
mensajes. El renderer de Mermaid, sus restricciones y su accesibilidad deben
verificarse durante la migración de la interfaz.

## Cómo informar mientras se trabaja

Mantener un único hilo principal coherente. Atribuir hallazgos de especialistas
cuando sea útil, con acceso a su evidencia; el usuario no debe transportar
mensajes entre agentes ni reconciliar sus versiones contradictorias.

| Situación comprobada | Comunicación útil |
| --- | --- |
| Trabajando | «Encontré dos rutas de ejecución. Estoy comprobando cuál usa esta tarea.» |
| Esperando herramienta | «La consulta de Ken sigue en curso. Aún no puedo concluir que ese código no exista.» |
| Esperando decisión | «Para continuar falta elegir si conservamos ambos informes o sustituimos el anterior; cada opción cambia qué versión verá el equipo.» |
| Recuperándose | «Se perdió la respuesta al guardar el informe. Estoy consultando la identidad de la operación antes de repetirla.» |
| Parada solicitada | «La solicitud de parada llegó al runtime. Aún estoy comprobando que terminó la herramienta.» |
| Parada confirmada | «La herramienta terminó y el intento quedó interrumpido. El informe creado antes de la parada sigue disponible.» |
| Resultado parcial | «La búsqueda terminó y guardó dos fuentes. El informe aún no se creó porque falta verificar la tercera.» |

Informar novedades relevantes y cambios de dirección. Evitar tanto el silencio
prolongado como mensajes repetidos sin información. Frecuencia, hora del último
evento y estado de espera deben corresponder a observaciones reales; no inventar
porcentajes ni progreso a partir del tiempo transcurrido. Los estados técnicos
detallados pueden estar disponibles en un inspector, sin sustituir la explicación.

No crear otra llamada LLM para reformular cada evento por defecto. Estados,
resúmenes deterministas y mensajes del agente deben compartir identidades y
fuentes; la presentación no puede fabricar un segundo estado del trabajo.

## Cómo permitir correcciones

Exponer interpretaciones mediante un resultado pequeño y revisable, en lugar
de preguntar constantemente «¿entendí bien?».

> Tomo «conservar los informes» como mantener su contenido y su historial.
> En esta muestra, el informe antiguo sigue visible y la versión nueva se
> enlaza como revisión. Si te referías a mantener también los nombres de
> archivo originales, esa es una diferencia concreta que podemos corregir.

Cuando llegue una corrección, conservar su fuente y alcance, versionar el
contexto, identificar conclusiones/tareas afectadas e impedir acciones nuevas
que dependan de la premisa contradicha. Comunicar por separado recepción,
aplicación comprobada y trabajo ya realizado que requiera reconciliación.
La prosa del agente nunca sustituye esos controles de ejecución.

> Recibí la corrección: el ejemplo usa 200 y una tasa de 0.10. La nueva
> propuesta muestra 220.00. El archivo de cálculo no cambió. El ejemplo
> anterior queda reemplazado en esta propuesta, no en otros informes.

Preguntar sólo por una decisión material que no resuelvan el repo ni la
conversación. Presentar opciones concretas y sus efectos, reutilizar información
ya dada y explicar qué trabajo depende de la respuesta. Silencio, reconexión
o paso del tiempo no equivalen a acuerdo.

## Cómo comunicar errores y cerrar una tarea

Explicar qué falló, su efecto y la recuperación disponible. Separar observación
de sospecha y evitar un diagnóstico interno sin traducción al problema.

> El proceso terminó antes de confirmar el guardado. No sé todavía si el
> informe existe. Voy a comprobar su identificador; repetir el guardado ahora
> podría crear un duplicado.

> Los dos tests fallaron, como esperábamos al investigar el error. Eso sirve
> como evidencia para la explicación; esta tarea no autorizaba corregirlos.

Al cerrar, describir resultado, validación y pendientes relevantes para el
objetivo. Distinguir tests aprobados, fallidos, no encontrados, omitidos y errores
de infraestructura. Una ejecución completada, un estado `idle` o una respuesta
del modelo no prueban que se hayan satisfecho los criterios de la tarea.
No mostrar cuota o tokens desconocidos como cero ni calcular un precio de API
para consumo de la suscripción.

## Evaluación y criterios de aceptación

La revisión usa estas preguntas, sin puntuar longitud ni cantidad de recursos
visuales:

1. ¿La conclusión es correcta y localizable? ¿La evidencia permite comprobarla?
2. ¿Se conservan procedencia, vigencia y límites al resumir o delegar?
3. ¿Se distingue interpretación de hecho y autorización de conocimiento?
4. ¿El ejemplo o diagrama conserva el comportamiento que se explica?
5. ¿Puede el usuario señalar una premisa concreta y corregir el rumbo?
6. ¿El estado comunicado coincide con eventos, efectos y validación reales?
7. ¿El detalle evita saltos sin imponer una carga de lectura innecesaria?

Bloquean la entrega: ampliar autorización por inferencia, ignorar una corrección,
perder su procedencia, inventar evidencia/éxito o presentar como cierta una
explicación materialmente falsa. Los controles de acciones deben detectar esos
casos aunque varíe la redacción del modelo.

Se requieren casos de desarrollo y casos reservados en `evals/context_alignment/`
y `evals/communication/`, comparando prompts con modelo/herramientas/contexto
constantes. La comparación de runtimes es un experimento separado. Registrar
éxito de tarea, errores, tiempo, tokens observados, preguntas y esfuerzo del
usuario. Comprensión, utilidad de metáforas y capacidad de corregir requieren
observación humana; un chequeo automático no certifica esas propiedades.

La aceptación de la primera ejecución vertical exige un hallazgo explicado
con un ejemplo o diagrama pertinente, una corrección real y un cambio de rumbo
comprobado. El ejemplo de código del ensayo de runtime es evidencia inicial de
explicación; no sustituye esa aceptación del producto completo.

## Criterios de diseño aplicados

Las skills de libros aportan criterios, no contenido para pegar entero en los
prompts: Ousterhout orienta a ocultar complejidad y reducir hechos que el usuario
debe retener; Hunt/Thomas, a una fuente de verdad, feedback concreto y prototipos
con límites explícitos. La procedencia y el control de efectos se mantienen en
el sistema, en vez de depender únicamente de una recomendación de estilo.
