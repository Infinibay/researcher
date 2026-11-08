# Entrega U08: revisión acotada con contexto limpio

Revisor `/root/u08_delivery_proportionality`, sólo lectura, sin cambios, pruebas,
modelos o instalaciones. El implementador contrastó la secuencia de uso de tokens
con el rollout original y comprobó después la composición propuesta de forma
determinista. No es una revisión final de toda la rama.

## Hechos e incertidumbres

El [ensayo original](purpose-framing-review.md) terminó sin explicación completa.
El rollout de `model_configuration_purpose-candidate` conserva los totales
**25 939 → 52 938 → 82 819 → 114 615 → 147 058**. Cada ronda volvió a cargar
aproximadamente 26–32 mil tokens. Cuando código/documentación ya estaban
 disponibles, la señal de presupuesto indicaba `phase=deliver`. Hubo después una
lectura redundante por comando, su lectura inválida y el guardado de un hallazgo.
Se agotó el límite antes de resumen tipado, propuesta y respuesta final.

Esto demuestra una entrega fallida y un coste importante por ronda. No demuestra
que DD157 causara todo el fallo ni que eliminar el comando garantice caber en el
presupuesto. El protocolo exige hallazgo → resumen tipado → propuesta explícita;
la respuesta nativa final también necesita margen. El
[evaluador](../../evals/communication/purpose_framing.py) exige lectura del módulo
y documentación, no el comando adicional ni investigar disponibilidad actual de
la cuenta. Reusar feedback histórico en esta pregunta tampoco acredita comprensión
ni adaptación aceptadas por el propietario.

## Alternativas y decisión del implementador

1. Aumentar el presupuesto o repetir hasta obtener un ejemplo favorable no resuelve
   la organización del trabajo y contaminaría la interpretación del ensayo.
2. Crear otra API compuesta introduce un contrato y recuperación nuevos antes de
   demostrar que los existentes impiden entregar.
3. **Componer las herramientas existentes en pasos gruesos**, con evidencia lista:
   adquisición conjunta de lecturas conocidas y una llamada `exec` que encadene
   hallazgo, resumen y propuesta con los IDs devueltos. Detenerse ante un error,
   preservar claves originales y reservar margen para finalizar la explicación.

Se elige comprobar la tercera alternativa dentro del alcance ya autorizado de
mejora de prompts/loop/comunicación. Es una decisión técnica del implementador,
no una nueva preferencia atribuida al propietario. Los IDs dependientes se esperan
en orden; agrupar no permite paralelizar mutaciones dependientes ni inventar
recibos. Un resumen sigue siendo draft: no acepta tareas ni prueba comprensión.

## Evidencia y siguiente paso

La [comprobación determinista](composed-investigation-delivery-review.md) confirma
que las herramientas actuales componen recibos reales y un informe legible sin
otra ronda de modelo. El host ya renderiza el resumen en
[investigation.py](../../backend/research/investigation.py); no necesita una
segunda síntesis generativa. Si falta la finalización nativa, el informe retenido
puede inspeccionarse, pero la aceptación queda bloqueada. Esa lectura es una
entrega retenida parcial, no finalización general del recorrido U08.

**Siguiente:** incorporar la orientación de composición a la política nativa,
conservar identidad de versiones históricas y comprobar el input realmente
congelado. Sólo después justificar una nueva observación real registrada por ese
cambio semántico, con los mismos límites y sin reemplazar el ensayo fallido.
Hasta entonces no hay evidencia de que el modelo elija esta estrategia o cumpla
el presupuesto. DD157, pulido y comparaciones adicionales siguen diferidos.

## Seguimiento tras el ensayo de catálogo 11

El mismo revisor inspeccionó el nuevo recorrido en sólo lectura, sin ejecutar
pruebas/modelos ni modificar archivos. El implementador contrastó el resultado,
política exacta, 118 líneas Ken y conteos con los originales.
[Observación y límites](coarse-delivery-policy-review.md).

La orientación no produjo composición suficiente: cuatro rondas consumieron
126 302 tokens antes de hallazgos, resumen, propuesta o final. El `cat` adquiría
procedencia capturable; su lectura completa en texto/base64 era prescindible para
`capture_command`, que obtiene bytes del recibo persistido. La próxima acción
recomendada es probar una composición ejecutable de adquisición y entrega con
wrappers reales, salida canónica interpretable, cobertura/citas y parada ante
fallo o incertidumbre. No otra repetición basada sólo en instrucciones.

El renderizado de `InvestigationSummary` crea un draft; `result_propose` guarda la
selección explícita. La elegibilidad todavía exige finalización nativa. El cierre
anticipado `DeliveryReady` pertenece al planificador; no extenderlo a investigación
para hacer pasar este caso. Una captura Ken automática exigiría semántica nueva de
formato, estabilidad, autoridad y procedencia; el código no demuestra que haga falta.
La reducción de catálogo es otra hipótesis de rendimiento, no ahorro de tokens
probado. DD157 y pulido continúan diferidos.
