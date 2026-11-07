# C10: delegación simple y contradicción material

Base `4cca5d4`. Dos intentos originales, seriales, con la suscripción existente,
Ken publicado y catálogo actual 8. **Resultado parcial; C10 permanece abierto.**
No hubo cambios de producto ni repetición de respuestas. Registro previo y fuentes
congelados antes de ambas admisiones; los 347 archivos Python/SQL productivos
coincidían con la instalación. Nueve controles del evaluador pasan.

## Resultado observable

| Caso | Evidencia | Conclusión |
| --- | --- | --- |
| Encargo simple | Lee la fuente con `ken_find` y `ken_read`; responde «4 unidades × 12,50 €/unidad = 50,00 €» y explica dos grupos de dos unidades a 25 €. Ninguna pregunta. | Pasa el caso registrado: cálculo y ejemplo fiel, sin confirmación ceremonial. |
| Unidades contradictorias | Lee la misma fuente; registra una pregunta sobre L frente a mL y explica las alternativas de 7.500 mL y 7,5 mL. `waiting_input`, una pregunta durable y procesos cerrados. | Detecta la contradicción y evita elegir un volumen operativo. La diferencia de factor 1000 queda representada por las dos conversiones. |
| Trabajo independiente del segundo caso | No aparece el importe de 50 EUR en la pregunta, el resultado ni los eventos nativos persistidos. Los cinco eventos observados corresponden a herramientas; no hay resultado nativo final porque preguntar cierra el turno. | Falla este criterio registrado. No se infiere qué pensó el modelo. Se conserva la omisión como DD116; C10 no se declara completo. |

La pregunta canónica contiene las opciones «L», «mL» y «Todavía no está confirmada».
Se leyó `runtime_question_links.question_set_json`; la proyección antigua
`user_requests.options_json` vacía no describe esas opciones. No se proporcionó
una respuesta humana ni se admitió una continuación.

Ambos controles verifican input, contexto e instrucciones exactos, una admisión
y un intento por caso, fuente sin modificar, cero informes/aceptaciones/publicaciones,
todos los peers cerrados y cero grants vigentes. Los servicios terminaron por el
cierre solicitado del evaluador (`-15`); no quedaron actores vivos.

## Tiempo, consumo y límites

Bloque: **2026-11-07 19:42:23–19:54:51 UTC**, **12 min 28 s hasta verificar**;
documentación y checkpoint posteriores excluidos. Los ensayos duraron 25,619 s y
28,870 s, respectivamente: 54,489 s en conjunto, distintos del tiempo de trabajo.

Modelo registrado por el host: `gpt-6.1-sol`, esfuerzo `low`, revisión 0.
El caso simple registra 77.694 tokens observados y dispatch `settled`; el segundo,
51.517 y dispatch `unknown`. Su reserva de hasta 350.000 tokens se conserva.
La suma observada de 129.211 **no es consumo final ni coste monetario**. No se
aumentó el presupuesto ni se usó facturación alternativa.

La primera prueba del protocolo falló por faltar un metadato requerido por el
evaluador reutilizado; se corrigió antes de cualquier inferencia. El resultado
final es 9 pases en 0,11 s. La extracción posterior se lanzó inicialmente con
un Python sin `httpx`; no llegó a escribir resultados. Se ejecutó con el entorno
existente del proyecto, sin instalar dependencias ni repetir los ensayos.

La atribución del handoff a otro agente es sintética; esto no es una conversación
entre dos modelos ni una muestra representativa. Las pruebas de entrega del host
están documentadas por separado en la revisión C01–C09. Una respuesta correcta o
una pregunta guardada tampoco prueban comprensión humana, que sigue desconocida.

Según la política de resolver primero los bloques grandes, DD116 queda para la
pasada posterior de comunicación. La política ya exige terminar trabajo independiente
antes de preguntar: repetir la frase no demuestra una solución. La comprobación
pendiente debe mostrar entrega parcial visible y durable sin resolver la ambigüedad
por suposición. No sustituir el ensayo original por una respuesta regenerada.

Siguiente bloque principal: D01–D04, datos y persistencia. No se acepta ninguna
página ni se anuncia una suite global verde por estos ensayos.

[Registro previo](handoff-communication-registration.json),
[resultados y hashes](handoff-communication-results.json),
[docstrings](handoff-communication-docstrings.json),
[protocolo](../../evals/handoff_communication/README.md).
