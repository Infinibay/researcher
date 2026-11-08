# Planificación: margen observado y fallo de entrega

**Corte histórico, catálogo5.** La entrega atómica posterior se comprobó dentro
del presupuesto en [catálogo6](atomic-planning-review.md). El fallo de este
documento se conserva; no representa por sí solo el pendiente actual.

Base `babeaa6`. Bloque **10:33:57–10:52:20 UTC**, **18 min 23 s** hasta la
validación. **La entrega de planificación sigue sin resolver.** Se corrigió el
aviso de presupuesto, se ejecutó un intento nuevo y su fallo cambia el siguiente
paso: necesita un contrato de entrega que conserve también la explicación.

## Qué demuestra el rastro

El intento anterior consumió 135796 tokens observados bajo un techo de 120000.
Cada paso procesó aproximadamente 25–29 mil tokens, principalmente contexto de
entrada; el catálogo tenía 54 herramientas. El contador llega después de la
respuesta de herramienta, de modo que en ese momento aún omite el paso en curso.
Los dos registros de contexto/propuesta en la instrumentación son llamadas a
contenedores `ProjectTools` anidados, no dos solicitudes del modelo.

El aviso del último cuarto dejaba 30000 tokens, insuficientes para varias vueltas
de ese tamaño. Ahora usa como mínimo ese cuarto y, si corresponde, un margen
orientativo de tres incrementos observados con un 25% adicional. Representa el
paso sin contabilizar, guardar el resultado y explicarlo. No es cuota reservada,
una predicción exacta, dinero facturado ni una ampliación del límite. Se conservan
las 54 capacidades, los requisitos de evidencia y todos los límites duros.

La reproducción con un peer de protocolo real fallaba antes: el estado seguía
siendo `work` pese al incremento de 25473. Ahora pasa y dice `deliver`; una
actualización duplicada no borra ese incremento. El caso de incrementos pequeños
sigue en `work`. Catálogo5 conserva las identidades históricas 2/3/4.

## Un ensayo nuevo, conservado aunque falló

Misma solicitud sintética de CSV, suscripción, modelo `gpt-6.1-sol`/low, Ken real,
un turno, 180 segundos, 20 herramientas y 120000 tokens. Se congelaron fuentes,
instrucciones, rúbrica y límites antes de iniciar. Es una regresión de desarrollo,
no un caso reservado ni una comparación causal. No se repitió después del fallo.

| Paso observado | Tokens acumulados |
| --- | ---: |
| Contexto y búsqueda | 25611 |
| Fuente y relaciones | 52339 |
| Lectura completa del archivo | 79460 |
| Guardar propuesta | 107804 |
| Generar explicación final | 137720: supera el límite |

El aviso temprano sí llegó, pero no evitó el último paso. Se conserva una propuesta
con tres tareas y dos citas exactas; cero aceptaciones. El rastro nativo contiene
una explicación final, pero el producto no la entregó: el límite se observó antes
de finalizar el resultado. No se trata ese texto como una entrega válida bajo el
presupuesto. El servicio terminó con -15, los cuatro peers registrados están
cerrados y no quedan grants locales sin revocar. El consumo queda `unknown`,
sin inventar liquidación final. El brazo duró 60,207 segundos.

La lectura adicional de este ensayo era necesaria: `ken_read` sin rango devolvió
la función en líneas 2–4 y omitió la línea 1 del módulo. La recomendación inicial
de usar ese valor por defecto era incorrecta para una lectura de archivo completo.
Se corrigió el texto final para exigir rangos que cubran el material requerido.
Esa corrección se verificó estáticamente y en pruebas, sin otra inferencia. Las
instrucciones exactas del intento fallido permanecen congeladas; no se le atribuye
la política corregida posteriormente.

## Validación y alcance

El primer candidato pasa 105 pruebas distintas de fuente y 82 instaladas. Tras
corregir únicamente el texto de planificación, pasan sus 12 pruebas de fuente y
12 instaladas. Coinciden 608 archivos Python/SQL entre fuente, wheel e instalación;
el único archivo backend distinto del primer wheel es `planning/instructions.py`.
18 definiciones cambiadas tienen docstrings. Se revalidaron 12 decisiones del
inventario de prompts, conservando las anteriores; las 83 quedan vigentes.
Nueve avisos Ruff van a DD092. No se repite la suite global ni se aceptan páginas.

[Diagnóstico anterior](planning-delivery-diagnosis.json),
[intento real](planning-delivery-live.json), [validación](planning-delivery-results.json),
[docstrings](planning-delivery-docstrings.json), [estilo](planning-delivery-lint.json).

## Siguiente cambio de engine: entrega explícita, todavía no implementada

El resultado útil y su explicación deben poder guardarse juntos en una operación
tipada. Añadir otra instrucción al modelo no garantiza que quede margen para una
respuesta posterior. La implementación debe cumplir estas condiciones:

1. Una operación final de planificación guarda atómicamente plan, explicación
   para el usuario, citas/identidad de la propuesta y clave de operación. Una
   propuesta sin explicación sigue siendo borrador. No reinterpretar registros
   históricos ni inventar una explicación en nombre del agente.
2. El recibo durable solicita el cierre del turno sin exigir otra generación.
   Reutilizar el control del engine actual: retirar autoridad, drenar operaciones
   y comprobar cierre físico; no crear otro loop ni liberar recursos por suposición.
3. Registrar por separado entrega y estado nativo. Un turno interrumpido por ese
   cierre no se convierte ficticiamente en `completed`. Consumo desconocido sigue
   desconocido y no acredita haber respetado el techo.
4. Corrección, Stop, límite excedido y pérdida de cierre conservan prioridad sobre
   la elegibilidad del resultado. Guardar algo no autoriza continuar, aceptar ni
   publicar. Una corrección posterior invalida la propuesta para el contexto nuevo.
5. La aceptación del propietario sigue ligada al hash exacto, contexto vigente y
   cierre comprobado. Mostrar la explicación guardada no crea ni ejecuta tareas.
   Revisar expresamente `ProjectPlans._ready`, que hoy exige terminación nativa.
6. Comprobar commit seguido de caída, respuesta perdida, repetición con misma clave,
   cambio de argumentos, corrección/Stop concurrente, ausencia de explicación y
   cierre desconocido. Preservar la compatibilidad de planes anteriores.
7. Verificar el recorrido en API/interfaz y después hacer un único intento nuevo
   registrado bajo el mismo techo. No llamar éxito a una propuesta guardada, un
   recibo incompleto o una explicación producida por encima del límite.

Esta es la siguiente tarea principal dentro de planificación. Los demás pendientes
del tablero permanecen; todos los detalles secundarios se resuelven después de
las capacidades principales.
